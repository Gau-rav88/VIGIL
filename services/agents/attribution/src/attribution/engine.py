from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Sequence

from vigil_common.models.anomaly import AnomalyEvent, EvidenceRef

from attribution.community import CommunityDetector
from attribution.confidence import calculate_pair_confidence, is_finding_link
from attribution.cycles import CycleDetector
from attribution.export import CytoscapeExporter
from attribution.graph_store import Neo4jGraphStore
from attribution.link_methods import LinkMethodEvaluator
from attribution.models import (
    AccountPairLink,
    CyclePath,
    CytoscapeGraph,
    EntityCluster,
    LinkMethod,
    MethodScore,
)
from attribution.reaction import ReactionLatencyAnalyzer


class AttributionEngine:
    """
    Core engine orchestrating the 8 link attribution methods,
    cycle discovery, entity resolution with ring scores, and veto enforcement.
    """

    def __init__(
        self,
        graph_store: Neo4jGraphStore | None = None,
        weights: dict[str, float] | None = None,
        thresholds: dict[str, float] | None = None,
    ) -> None:
        self.store = graph_store or Neo4jGraphStore()
        self.evaluator = LinkMethodEvaluator(weights, thresholds)
        self.cycle_detector = CycleDetector()
        self.community_detector = CommunityDetector(self.evaluator.weights)
        self.reaction_analyzer = ReactionLatencyAnalyzer()
        self.exporter = CytoscapeExporter()

    def attribute_accounts(
        self,
        trades: Sequence[dict[str, Any]],
        symbol: str,
        case_id: str = "default",
        cta_events: Sequence[dict[str, Any]] | None = None,
        known_kyc: dict[str, dict[str, str | None]] | None = None,
        sync_pairs: Sequence[dict[str, Any]] | None = None,
    ) -> tuple[list[AccountPairLink], list[EntityCluster], list[CyclePath]]:
        """
        Run complete attribution over a set of trades and signals.
        Returns (links, entity_clusters, detected_cycles).
        """
        kyc_data = known_kyc or {}
        ctas = cta_events or []
        syncs = sync_pairs or []

        # 1. Gather account metadata and relations from trades
        acc_trades: dict[str, list[dict[str, Any]]] = defaultdict(list)
        acc_devices: dict[str, set[str]] = defaultdict(set)
        acc_asns: dict[str, set[int]] = defaultdict(set)
        acc_brokers: dict[str, set[str]] = defaultdict(set)
        acc_gateways: dict[str, set[str]] = defaultdict(set)
        acc_volumes: dict[str, float] = defaultdict(float)
        acc_trade_times: dict[str, list[int]] = defaultdict(list)
        total_symbol_volume = 0.0

        for t in trades:
            s = str(t.get("seller", ""))
            b = str(t.get("buyer", ""))
            qty = float(t.get("qty", 0.0))
            ts_ms = int(t.get("ts_ms", 0))
            total_symbol_volume += qty

            if s:
                acc_volumes[s] += qty
                acc_trades[s].append(t)
                acc_trade_times[s].append(ts_ms)
                if t.get("seller_device_fp"):
                    acc_devices[s].add(str(t["seller_device_fp"]))
                if t.get("seller_asn"):
                    acc_asns[s].add(int(t["seller_asn"]))
                if t.get("seller_broker_id"):
                    acc_brokers[s].add(str(t["seller_broker_id"]))
                if t.get("seller_gateway_id"):
                    acc_gateways[s].add(str(t["seller_gateway_id"]))

            if b:
                acc_volumes[b] += qty
                acc_trades[b].append(t)
                acc_trade_times[b].append(ts_ms)
                if t.get("buyer_device_fp"):
                    acc_devices[b].add(str(t["buyer_device_fp"]))
                if t.get("buyer_asn"):
                    acc_asns[b].add(int(t["buyer_asn"]))
                if t.get("buyer_broker_id"):
                    acc_brokers[b].add(str(t["buyer_broker_id"]))
                if t.get("buyer_gateway_id"):
                    acc_gateways[b].add(str(t["buyer_gateway_id"]))

        all_accounts = sorted(list(acc_volumes.keys()))

        # 2. Cycle Detection
        cycles = self.cycle_detector.find_cycles(trades)
        cycles_by_pair: dict[tuple[str, str], int] = defaultdict(int)
        for cyc in cycles:
            cyc_accs = cyc.accounts
            for i in range(len(cyc_accs)):
                for j in range(i + 1, len(cyc_accs)):
                    cyc_pair: tuple[str, str] = (min(cyc_accs[i], cyc_accs[j]), max(cyc_accs[i], cyc_accs[j]))
                    cycles_by_pair[cyc_pair] += 1

        # 3. Synchronized orders index
        sync_map: dict[tuple[str, str], dict[str, Any]] = {}
        for sp in syncs:
            a1, a2 = str(sp.get("a", "")), str(sp.get("b", ""))
            if a1 and a2:
                sp_pair: tuple[str, str] = (min(a1, a2), max(a1, a2))
                sync_map[sp_pair] = sp

        # 4. CTA Timestamps for Reaction Latency
        cta_ts = [int(c.get("ts_ms", 0)) for c in ctas if c.get("ts_ms")]
        window_start = min((t["ts_ms"] for t in trades), default=0)
        window_end = max((t["ts_ms"] for t in trades), default=0)

        # 5. Evaluate all account pairs
        evaluated_links: list[AccountPairLink] = []

        for i in range(len(all_accounts)):
            for j in range(i + 1, len(all_accounts)):
                acc_a = all_accounts[i]
                acc_b = all_accounts[j]
                pair = (acc_a, acc_b)

                # Check veto store
                if self.store.is_vetoed(acc_a, acc_b, case_id):
                    continue

                method_scores: list[MethodScore] = []
                used_methods: list[LinkMethod] = []
                evidence_ids: list[str] = []

                # Method 1: SHARED_KYC
                kyc_score = self.evaluator.eval_shared_kyc(
                    kyc_data.get(acc_a, {}), kyc_data.get(acc_b, {})
                )
                if kyc_score:
                    method_scores.append(kyc_score)
                    used_methods.append(LinkMethod.SHARED_KYC)
                    evidence_ids.append(f"kyc_{acc_a}_{acc_b}")

                # Method 2: SHARED_DEVICE
                shared_devs = list(acc_devices[acc_a].intersection(acc_devices[acc_b]))
                dev_score = self.evaluator.eval_shared_device(shared_devs)
                if dev_score:
                    method_scores.append(dev_score)
                    used_methods.append(LinkMethod.SHARED_DEVICE)
                    evidence_ids.extend([f"dev_{d}" for d in shared_devs])

                # Method 3: CIRCULAR_CYCLE
                cyc_count = cycles_by_pair.get(pair, 0)
                cyc_score = self.evaluator.eval_circular_cycle(cyc_count)
                if cyc_score:
                    method_scores.append(cyc_score)
                    used_methods.append(LinkMethod.CIRCULAR_CYCLE)
                    evidence_ids.append(f"cycles_{cyc_count}")

                # Method 4: SYNCHRONIZED_ORDERS
                if pair in sync_map:
                    sp = sync_map[pair]
                    sync_score = self.evaluator.eval_synchronized_orders(
                        best_p=float(sp.get("best_p", 0.0)),
                        co_orders=int(sp.get("co_orders", 0)),
                    )
                    if sync_score:
                        method_scores.append(sync_score)
                        used_methods.append(LinkMethod.SYNCHRONIZED_ORDERS)
                        evidence_ids.append(f"sync_{acc_a}_{acc_b}")

                # Method 5: SHARED_NETWORK (same ASN and gateway)
                shared_asns = acc_asns[acc_a].intersection(acc_asns[acc_b])
                shared_gws = acc_gateways[acc_a].intersection(acc_gateways[acc_b])
                net_score = self.evaluator.eval_shared_network(
                    ip_match=False,  # If raw IP match
                    same_asn=len(shared_asns) > 0,
                    same_gateway=len(shared_gws) > 0,
                )
                if net_score:
                    method_scores.append(net_score)
                    used_methods.append(LinkMethod.SHARED_NETWORK)
                    evidence_ids.extend([f"asn_{a}" for a in shared_asns])

                # Method 6: LATENCY_SIGNATURE
                lat_a = [float(t["ts_ms"] % 1000) for t in acc_trades[acc_a] if "ts_ms" in t]
                lat_b = [float(t["ts_ms"] % 1000) for t in acc_trades[acc_b] if "ts_ms" in t]
                lat_score = self.evaluator.eval_latency_signature(lat_a, lat_b)
                if lat_score:
                    method_scores.append(lat_score)
                    used_methods.append(LinkMethod.LATENCY_SIGNATURE)
                    evidence_ids.append(f"ks_{acc_a}_{acc_b}")

                # Method 7: REACTION_LATENCY
                if cta_ts:
                    res_a = self.reaction_analyzer.analyze_trader_reaction(
                        cta_ts, acc_trade_times[acc_a], window_start, window_end
                    )
                    res_b = self.reaction_analyzer.analyze_trader_reaction(
                        cta_ts, acc_trade_times[acc_b], window_start, window_end
                    )
                    if res_a and res_b:
                        # Both reacted significantly to same CTAs
                        p_joint = max(float(res_a["p_value"]), float(res_b["p_value"]))
                        react_score = MethodScore(
                            method=LinkMethod.REACTION_LATENCY,
                            weight=self.evaluator.get_weight(LinkMethod.REACTION_LATENCY),
                            strength=max(0.0, min(1.0, 1.0 - p_joint)),
                            details={"p_joint": p_joint, "n_a": res_a["n_reactions"], "n_b": res_b["n_reactions"]},
                        )
                        method_scores.append(react_score)
                        used_methods.append(LinkMethod.REACTION_LATENCY)
                        evidence_ids.append(f"react_{acc_a}_{acc_b}")

                # Method 8: BROKER_PATHWAY
                brk_a = next(iter(acc_brokers[acc_a]), "")
                gw_a = next(iter(acc_gateways[acc_a]), "")
                brk_b = next(iter(acc_brokers[acc_b]), "")
                gw_b = next(iter(acc_gateways[acc_b]), "")
                bp_score = self.evaluator.eval_broker_pathway(
                    broker_a=brk_a,
                    gateway_a=gw_a,
                    share_a=1.0 if brk_a else 0.0,
                    broker_b=brk_b,
                    gateway_b=gw_b,
                    share_b=1.0 if brk_b else 0.0,
                )
                if bp_score:
                    method_scores.append(bp_score)
                    used_methods.append(LinkMethod.BROKER_PATHWAY)
                    evidence_ids.append(f"brk_{brk_a}_{gw_a}")

                # Calculate noisy-OR confidence
                if method_scores:
                    conf = calculate_pair_confidence(method_scores)
                    finding = is_finding_link(conf)
                    evaluated_links.append(
                        AccountPairLink(
                            source_account=acc_a,
                            target_account=acc_b,
                            confidence=conf,
                            methods=used_methods,
                            method_scores=method_scores,
                            evidence_ids=evidence_ids,
                            is_finding=finding,
                            is_vetoed=False,
                        )
                    )

        # 6. Entity Resolution & Ring Scores
        dev_map_flat = {acc: list(devs) for acc, devs in acc_devices.items()}
        brk_map_flat = {acc: next(iter(brks), "") for acc, brks in acc_brokers.items()}
        asn_map_flat = {acc: next(iter(asns), 0) for acc, asns in acc_asns.items()}

        entities = self.community_detector.resolve_entities(
            links=evaluated_links,
            account_volumes=dict(acc_volumes),
            total_symbol_volume=total_symbol_volume,
            device_map=dev_map_flat,
            broker_map=brk_map_flat,
            asn_map=asn_map_flat,
            case_id=case_id,
        )

        return evaluated_links, entities, cycles

    def create_anomaly_events(
        self,
        symbol: str,
        entities: Sequence[EntityCluster],
        cycles: Sequence[CyclePath],
        window_start_iso: str,
        window_end_iso: str,
        config_hash: str = "0" * 64,
    ) -> list[AnomalyEvent]:
        """Generate typed AnomalyEvent records from attribution findings."""
        anomalies: list[AnomalyEvent] = []

        # 1. CIRCULAR_RING from detected cycles
        if cycles:
            all_cycle_accs = sorted(list({acc for cyc in cycles for acc in cyc.accounts}))
            cycle_ev_ids = [ref for cyc in cycles for ref in cyc.evidence_trade_ids]
            ev_refs = [
                EvidenceRef(kind="trade_id", ref=tid) for tid in cycle_ev_ids[:10]
            ] or [EvidenceRef(kind="anomaly_id", ref=str(uuid.uuid4()))]

            anomalies.append(
                AnomalyEvent(
                    schema_version="1.0.0",
                    anomaly_id=str(uuid.uuid4()),
                    type="CIRCULAR_RING",
                    source_agent="attribution",
                    symbol=symbol,
                    window_start=window_start_iso,
                    window_end=window_end_iso,
                    score=0.98,
                    severity="CRITICAL",
                    metrics={
                        "cycle_count": len(cycles),
                        "lengths": [cyc.length for cyc in cycles],
                        "total_volume": sum(cyc.cycle_volume for cyc in cycles),
                    },
                    participants=all_cycle_accs,
                    evidence_refs=ev_refs,
                    detector_version="1.0.0",
                    config_hash=config_hash,
                    detected_at=window_end_iso,
                )
            )

        # 2. FINGERPRINT_CLUSTER & COORDINATED_VOLUME_LOOP from top entities
        for ent in entities:
            if ent.ring_score >= 0.70 and len(ent.accounts) >= 2:
                ev_refs = [EvidenceRef(kind="anomaly_id", ref=str(uuid.uuid4()))]
                anomalies.append(
                    AnomalyEvent(
                        schema_version="1.0.0",
                        anomaly_id=str(uuid.uuid4()),
                        type="FINGERPRINT_CLUSTER",
                        source_agent="attribution",
                        symbol=symbol,
                        window_start=window_start_iso,
                        window_end=window_end_iso,
                        score=ent.ring_score,
                        severity="HIGH" if ent.ring_score >= 0.85 else "MEDIUM",
                        metrics={
                            "entity_id": ent.entity_id,
                            "ring_score": ent.ring_score,
                            "account_count": len(ent.accounts),
                            "shared_devices": len(ent.shared_devices),
                            "brokers": len(ent.brokers),
                        },
                        participants=ent.accounts,
                        evidence_refs=ev_refs,
                        detector_version="1.0.0",
                        config_hash=config_hash,
                        detected_at=window_end_iso,
                    )
                )

            # Check coordinated volume loop
            if self.community_detector.check_coordinated_volume_loop(ent, threshold=0.25):
                anomalies.append(
                    AnomalyEvent(
                        schema_version="1.0.0",
                        anomaly_id=str(uuid.uuid4()),
                        type="COORDINATED_VOLUME_LOOP",
                        source_agent="attribution",
                        symbol=symbol,
                        window_start=window_start_iso,
                        window_end=window_end_iso,
                        score=0.92,
                        severity="CRITICAL",
                        metrics={
                            "entity_id": ent.entity_id,
                            "volume_share": ent.volume_share,
                            "accounts": len(ent.accounts),
                        },
                        participants=ent.accounts,
                        evidence_refs=[EvidenceRef(kind="anomaly_id", ref=str(uuid.uuid4()))],
                        detector_version="1.0.0",
                        config_hash=config_hash,
                        detected_at=window_end_iso,
                    )
                )

        return anomalies

    def export_subgraph(
        self,
        cluster: EntityCluster,
        max_nodes: int = 500,
        min_conf: float = 0.60,
    ) -> CytoscapeGraph:
        """Export entity cluster to Cytoscape format."""
        return self.exporter.export_cluster(cluster, max_nodes=max_nodes, min_conf=min_conf)
