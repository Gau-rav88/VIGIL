from __future__ import annotations

from typing import Any, Sequence

from attribution.models import (
    CytoscapeEdge,
    CytoscapeEdgeData,
    CytoscapeGraph,
    CytoscapeNode,
    CytoscapeNodeData,
    EntityCluster,
)


class CytoscapeExporter:
    """Exports case attributed subgraphs into Cytoscape.js format."""

    def export_cluster(
        self,
        cluster: EntityCluster,
        max_nodes: int = 500,
        min_conf: float = 0.60,
    ) -> CytoscapeGraph:
        nodes: dict[str, CytoscapeNode] = {}
        edges: list[CytoscapeEdge] = []

        # 1. Entity Node
        ent_id = f"entity_{cluster.entity_id}"
        nodes[ent_id] = CytoscapeNode(
            data=CytoscapeNodeData(
                id=ent_id,
                label=f"Syndicate {cluster.entity_id} (score {cluster.ring_score:.2f})",
                type="Entity",
                properties={
                    "ring_score": cluster.ring_score,
                    "volume_share": cluster.volume_share,
                    "member_count": len(cluster.accounts),
                },
            )
        )

        # 2. Account / Trader Nodes (capped by max_nodes)
        capped_accounts = cluster.accounts[:max_nodes]
        for acc in capped_accounts:
            nodes[acc] = CytoscapeNode(
                data=CytoscapeNodeData(
                    id=acc,
                    label=f"Trader {acc[:8]}...",
                    type="Trader",
                    properties={"account_id": acc},
                )
            )
            # Edge: Trader -> Entity
            edges.append(
                CytoscapeEdge(
                    data=CytoscapeEdgeData(
                        id=f"ctrl_{acc}_{ent_id}",
                        source=acc,
                        target=ent_id,
                        type="CONTROLLED_BY",
                        confidence=cluster.ring_score,
                    )
                )
            )

        # 3. Device Nodes & Edges
        for dev in cluster.shared_devices:
            if len(nodes) >= max_nodes:
                break
            d_id = f"dev_{dev[:8]}"
            nodes[d_id] = CytoscapeNode(
                data=CytoscapeNodeData(
                    id=d_id,
                    label=f"Device {dev[:6]}",
                    type="Device",
                    properties={"device_fp": dev},
                )
            )
            # Connect traders sharing this device
            for acc in capped_accounts:
                edges.append(
                    CytoscapeEdge(
                        data=CytoscapeEdgeData(
                            id=f"uses_{acc}_{d_id}",
                            source=acc,
                            target=d_id,
                            type="USES_DEVICE",
                            weight=0.90,
                        )
                    )
                )

        # 4. Broker Nodes & Edges
        for brk in cluster.brokers:
            if len(nodes) >= max_nodes:
                break
            b_id = f"brk_{brk}"
            nodes[b_id] = CytoscapeNode(
                data=CytoscapeNodeData(
                    id=b_id,
                    label=f"Broker {brk}",
                    type="Broker",
                    properties={"broker_id": brk},
                )
            )

        # 5. Inter-Trader LINKED Edges (filtered by min_conf)
        edge_id_counter = 1
        for lk in cluster.findings_links:
            if lk.confidence >= min_conf and not lk.is_vetoed:
                s, t = lk.source_account, lk.target_account
                if s in nodes and t in nodes:
                    edges.append(
                        CytoscapeEdge(
                            data=CytoscapeEdgeData(
                                id=f"link_{edge_id_counter}_{s}_{t}",
                                source=s,
                                target=t,
                                type="LINKED",
                                confidence=lk.confidence,
                                weight=lk.confidence,
                                properties={
                                    "methods": [m.value for m in lk.methods],
                                    "evidence_ids": lk.evidence_ids,
                                },
                            )
                        )
                    )
                    edge_id_counter += 1

        return CytoscapeGraph(nodes=list(nodes.values()), edges=edges)

    def export_from_records(
        self,
        records: Sequence[dict[str, Any]],
        max_nodes: int = 500,
        min_conf: float = 0.60,
    ) -> CytoscapeGraph:
        """Export from Neo4j query records."""
        nodes: dict[str, CytoscapeNode] = {}
        edges: list[CytoscapeEdge] = []

        for rec in records:
            if len(nodes) >= max_nodes:
                break
            a_data = rec.get("a")
            if a_data and isinstance(a_data, dict):
                acc_id = a_data.get("account_id", str(a_data))
                if acc_id not in nodes:
                    nodes[acc_id] = CytoscapeNode(
                        data=CytoscapeNodeData(
                            id=acc_id,
                            label=f"Trader {acc_id[:8]}",
                            type="Trader",
                            properties=a_data,
                        )
                    )

            # Process links
            links = rec.get("links", [])
            for lk in links:
                if isinstance(lk, dict):
                    conf = float(lk.get("confidence", 0.0))
                    if conf >= min_conf:
                        src = str(lk.get("source", ""))
                        tgt = str(lk.get("target", ""))
                        if src and tgt:
                            edges.append(
                                CytoscapeEdge(
                                    data=CytoscapeEdgeData(
                                        id=f"edge_{src}_{tgt}",
                                        source=src,
                                        target=tgt,
                                        type="LINKED",
                                        confidence=conf,
                                        weight=conf,
                                    )
                                )
                            )

        return CytoscapeGraph(nodes=list(nodes.values()), edges=edges)
