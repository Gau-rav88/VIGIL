from __future__ import annotations

from typing import Sequence

import networkx as nx

from attribution.confidence import calculate_ring_score
from attribution.models import AccountPairLink, EntityCluster


class CommunityDetector:
    """
    Community detection and entity resolution:
    - Connected components on LINKED edges (>= 0.60)
    - Louvain refinement for clusters > 40 nodes
    - Ring score calculation
    - Coordinated volume loop check (>= 25% of symbol volume)
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights = weights or {
            "SHARED_KYC": 0.95,
            "SHARED_DEVICE": 0.90,
            "CIRCULAR_CYCLE": 0.85,
            "SYNCHRONIZED_ORDERS": 0.70,
            "SHARED_NETWORK": 0.60,
            "LATENCY_SIGNATURE": 0.50,
            "REACTION_LATENCY": 0.50,
            "BROKER_PATHWAY": 0.40,
        }

    def resolve_entities(
        self,
        links: Sequence[AccountPairLink],
        account_volumes: dict[str, float] | None = None,
        total_symbol_volume: float = 0.0,
        device_map: dict[str, list[str]] | None = None,
        broker_map: dict[str, str] | None = None,
        asn_map: dict[str, int] | None = None,
        case_id: str | None = None,
    ) -> list[EntityCluster]:
        """
        Group accounts linked at conf >= 0.60 into entities.
        Links < 0.60 are preserved as leads, not findings.
        """
        acc_volumes = account_volumes or {}
        dev_map = device_map or {}
        brk_map = broker_map or {}
        a_map = asn_map or {}

        # Build undirected graph of findings (conf >= 0.60)
        G = nx.Graph()
        findings_by_pair: dict[tuple[str, str], AccountPairLink] = {}
        leads_by_pair: dict[tuple[str, str], AccountPairLink] = {}

        for lk in links:
            pair: tuple[str, str] = (
                min(lk.source_account, lk.target_account),
                max(lk.source_account, lk.target_account),
            )
            if lk.confidence >= 0.60 and not lk.is_vetoed:
                G.add_edge(pair[0], pair[1], weight=lk.confidence, link=lk)
                findings_by_pair[pair] = lk
            else:
                leads_by_pair[pair] = lk

        if G.number_of_nodes() == 0:
            return []

        # Find connected components
        components = list(nx.connected_components(G))
        final_clusters: list[list[str]] = []

        for comp in components:
            if len(comp) > 40:
                # Apply Louvain refinement
                sub_G = G.subgraph(comp)
                louvain_comms = nx.community.louvain_communities(sub_G, weight="weight", seed=42)
                for comm in louvain_comms:
                    final_clusters.append(sorted(list(comm)))
            else:
                final_clusters.append(sorted(list(comp)))

        # Build EntityCluster objects
        clusters: list[EntityCluster] = []
        for idx, cluster_nodes in enumerate(final_clusters):
            c_set = set(cluster_nodes)
            entity_id = f"entity_{idx + 1:03d}"

            # Collect findings links within this cluster
            c_findings: list[AccountPairLink] = []
            for pair, lk in findings_by_pair.items():
                if pair[0] in c_set and pair[1] in c_set:
                    c_findings.append(lk)

            # Collect leads links attached to this cluster
            c_leads: list[AccountPairLink] = []
            for pair, lk in leads_by_pair.items():
                if pair[0] in c_set or pair[1] in c_set:
                    c_leads.append(lk)

            # Volume calculation
            ent_vol = sum(acc_volumes.get(acc, 0.0) for acc in cluster_nodes)
            vol_share = (ent_vol / total_symbol_volume) if total_symbol_volume > 0.0 else 0.0
            vol_share = min(1.0, max(0.0, vol_share))

            # Compute ring score
            ring_score = calculate_ring_score(c_findings, vol_share, self.weights)

            # Collect brokers, devices, ASNs
            brokers = sorted(list({brk_map[acc] for acc in cluster_nodes if acc in brk_map}))
            devices = sorted(list({dev for acc in cluster_nodes for dev in dev_map.get(acc, [])}))
            asns = sorted(list({a_map[acc] for acc in cluster_nodes if acc in a_map}))

            clusters.append(
                EntityCluster(
                    entity_id=entity_id,
                    case_id=case_id,
                    accounts=cluster_nodes,
                    ring_score=ring_score,
                    volume_share=vol_share,
                    brokers=brokers,
                    shared_devices=devices,
                    shared_asns=asns,
                    findings_links=c_findings,
                    leads_links=c_leads,
                )
            )

        # Sort clusters by ring_score descending
        clusters.sort(key=lambda c: c.ring_score, reverse=True)
        return clusters

    def check_coordinated_volume_loop(
        self,
        cluster: EntityCluster,
        threshold: float = 0.25,
    ) -> bool:
        """FR-GRA-05: Flag if combined community volume >= 25% of symbol volume."""
        return cluster.volume_share >= threshold
