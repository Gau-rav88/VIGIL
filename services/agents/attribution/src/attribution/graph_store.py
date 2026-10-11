from __future__ import annotations

import uuid
from typing import Any, Sequence

import networkx as nx
from neo4j import AsyncDriver, AsyncGraphDatabase
from vigil_common.logging import get_logger

logger = get_logger("attribution.graph_store")


class Neo4jGraphStore:
    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "vigilneo4j",
    ) -> None:
        self.uri = uri
        self.user = user
        self.password = password
        self.driver: AsyncDriver | None = None
        self._connected = False
        self._vetoes: set[tuple[str, str, str]] = set()  # (a, b, case_id)
        # In-memory fallback graph
        self.fallback_nx: nx.MultiDiGraph = nx.MultiDiGraph()
        self.degraded_mode = False

    async def connect(self) -> bool:
        try:
            self.driver = AsyncGraphDatabase.driver(self.uri, auth=(self.user, self.password))
            await self.driver.verify_connectivity()
            self._connected = True
            self.degraded_mode = False
            logger.info("Connected to Neo4j graph store", uri=self.uri)
            await self._load_vetoes()
            return True
        except Exception as exc:
            logger.warning("Could not connect to Neo4j, enabling degraded in-memory mode", error=str(exc))
            self._connected = False
            self.degraded_mode = True
            return False

    async def close(self) -> None:
        if self.driver:
            await self.driver.close()
            self.driver = None
            self._connected = False

    async def _load_vetoes(self) -> None:
        if not self.driver or not self._connected:
            return
        query = "MATCH (v:Veto) RETURN v.a AS a, v.b AS b, v.case_id AS case_id"
        try:
            async with self.driver.session() as s:
                res = await s.run(query)
                records = await res.data()
                for r in records:
                    a, b, cid = str(r["a"]), str(r["b"]), str(r.get("case_id", "default"))
                    pair = tuple(sorted([a, b]))
                    self._vetoes.add((pair[0], pair[1], cid))
        except Exception as exc:
            logger.warning("Failed to load vetoes from Neo4j", error=str(exc))

    def is_vetoed(self, account_a: str, account_b: str, case_id: str = "default") -> bool:
        pair = tuple(sorted([account_a, account_b]))
        return (pair[0], pair[1], case_id) in self._vetoes or (pair[0], pair[1], "default") in self._vetoes

    async def record_veto(self, account_a: str, account_b: str, case_id: str = "default") -> None:
        pair = tuple(sorted([account_a, account_b]))
        self._vetoes.add((pair[0], pair[1], case_id))

        if self.driver and self._connected:
            query = """
            MERGE (v:Veto {a: $a, b: $b, case_id: $case_id})
            ON CREATE SET v.created_at = datetime()
            WITH v
            MATCH (a:Trader {account_id: $a})-[r:LINKED]-(b:Trader {account_id: $b})
            DELETE r
            """
            try:
                async with self.driver.session() as s:
                    await s.run(query, a=pair[0], b=pair[1], case_id=case_id)
            except Exception as exc:
                logger.error("Failed to record veto in Neo4j", error=str(exc))

    async def upsert_traders_and_trades(
        self,
        trades: Sequence[dict[str, Any]],
        symbol: str,
        is_synthetic: bool = True,
    ) -> None:
        if not trades:
            return

        # Always update in-memory fallback graph
        for t in trades:
            s = str(t.get("seller", ""))
            b = str(t.get("buyer", ""))
            qty = float(t.get("qty", 0.0))
            price = float(t.get("price", 0.0))
            ts_ms = int(t.get("ts_ms", 0))
            trade_id = str(t.get("trade_id", ""))
            if s and b:
                self.fallback_nx.add_node(s, type="Trader")
                self.fallback_nx.add_node(b, type="Trader")
                self.fallback_nx.add_edge(
                    s,
                    b,
                    key=trade_id,
                    qty=qty,
                    price=price,
                    ts_ms=ts_ms,
                    symbol=symbol,
                    seller_device_fp=t.get("seller_device_fp"),
                    buyer_device_fp=t.get("buyer_device_fp"),
                    seller_asn=t.get("seller_asn"),
                    buyer_asn=t.get("buyer_asn"),
                    seller_broker_id=t.get("seller_broker_id"),
                    buyer_broker_id=t.get("buyer_broker_id"),
                    seller_gateway_id=t.get("seller_gateway_id"),
                    buyer_gateway_id=t.get("buyer_gateway_id"),
                )

        if not self.driver or not self._connected:
            return

        query = """
        UNWIND $batch AS row
        MERGE (s:Trader {account_id: row.seller})
          ON CREATE SET s.first_seen_ms = row.ts_ms, s.is_synthetic = $is_synthetic
          SET s.last_seen_ms = row.ts_ms
        MERGE (b:Trader {account_id: row.buyer})
          ON CREATE SET b.first_seen_ms = row.ts_ms, b.is_synthetic = $is_synthetic
          SET b.last_seen_ms = row.ts_ms
        MERGE (k:Ticker {symbol: $symbol})

        FOREACH (_ IN CASE WHEN row.seller_dev IS NOT NULL THEN [1] ELSE [] END |
          MERGE (sd:Device {device_fp: row.seller_dev})
          MERGE (s)-[:USES_DEVICE]->(sd)
        )
        FOREACH (_ IN CASE WHEN row.buyer_dev IS NOT NULL THEN [1] ELSE [] END |
          MERGE (bd:Device {device_fp: row.buyer_dev})
          MERGE (b)-[:USES_DEVICE]->(bd)
        )
        FOREACH (_ IN CASE WHEN row.seller_asn IS NOT NULL THEN [1] ELSE [] END |
          MERGE (s_asn:ASN {asn: row.seller_asn})
          MERGE (s)-[:IN_ASN]->(s_asn)
        )
        FOREACH (_ IN CASE WHEN row.buyer_asn IS NOT NULL THEN [1] ELSE [] END |
          MERGE (b_asn:ASN {asn: row.buyer_asn})
          MERGE (b)-[:IN_ASN]->(b_asn)
        )
        FOREACH (_ IN CASE WHEN row.seller_brk IS NOT NULL THEN [1] ELSE [] END |
          MERGE (sb:Broker {broker_id: row.seller_brk})
          MERGE (s)-[:ROUTED_THROUGH]->(sb)
        )
        FOREACH (_ IN CASE WHEN row.buyer_brk IS NOT NULL THEN [1] ELSE [] END |
          MERGE (bb:Broker {broker_id: row.buyer_brk})
          MERGE (b)-[:ROUTED_THROUGH]->(bb)
        )

        MERGE (s)-[e:TRADED_WITH {ticker: $symbol, trade_id: row.trade_id}]->(b)
          ON CREATE SET e.qty = row.qty, e.price = row.price, e.ts = row.ts_ms, e.ts_end = row.ts_ms
        """

        batch = []
        for t in trades:
            batch.append({
                "seller": t.get("seller"),
                "buyer": t.get("buyer"),
                "qty": t.get("qty", 0.0),
                "price": t.get("price", 0.0),
                "ts_ms": t.get("ts_ms", 0),
                "trade_id": t.get("trade_id", ""),
                "seller_dev": t.get("seller_device_fp"),
                "buyer_dev": t.get("buyer_device_fp"),
                "seller_asn": t.get("seller_asn"),
                "buyer_asn": t.get("buyer_asn"),
                "seller_brk": t.get("seller_broker_id"),
                "buyer_brk": t.get("buyer_broker_id"),
            })

        try:
            async with self.driver.session() as session:
                await session.run(query, batch=batch, symbol=symbol, is_synthetic=is_synthetic)
        except Exception as exc:
            logger.error("Failed to batch upsert trades to Neo4j", error=str(exc))
            self.degraded_mode = True

    async def upsert_linked_edges(
        self,
        links: Sequence[dict[str, Any]],
        case_id: str = "default",
    ) -> None:
        """Write LINKED edges between accounts with methods and confidence."""
        if not links or not self.driver or not self._connected:
            return

        # Filter out vetoed links
        valid_links = []
        for lk in links:
            s = lk["source_account"]
            t = lk["target_account"]
            if not self.is_vetoed(s, t, case_id):
                valid_links.append(lk)

        if not valid_links:
            return

        query = """
        UNWIND $batch AS row
        MERGE (a:Trader {account_id: row.source_account})
        MERGE (b:Trader {account_id: row.target_account})
        MERGE (a)-[r:LINKED {case_id: $case_id}]->(b)
          SET r.confidence = row.confidence,
              r.weight = row.confidence,
              r.methods = row.methods,
              r.evidence_ids = row.evidence_ids
        """
        try:
            async with self.driver.session() as s:
                await s.run(query, batch=valid_links, case_id=case_id)
        except Exception as exc:
            logger.error("Failed to upsert LINKED edges in Neo4j", error=str(exc))

    async def upsert_entities(
        self,
        entities: Sequence[Any],
        symbol: str,
        case_id: str = "default",
    ) -> None:
        """Write Ring entity clusters to Neo4j."""
        if not entities or not self.driver or not self._connected:
            return

        query = """
        UNWIND $batch AS row
        MERGE (r:Ring {ring_id: row.ring_id})
          SET r.symbol = $symbol,
              r.entity_id = row.entity_id,
              r.ring_score = row.ring_score,
              r.accounts = row.accounts,
              r.case_id = $case_id
        """
        batch = [
            {
                "ring_id": getattr(e, "entity_id", str(uuid.uuid4())),
                "entity_id": getattr(e, "entity_id", str(uuid.uuid4())),
                "ring_score": float(getattr(e, "ring_score", 0.8)),
                "accounts": list(getattr(e, "accounts", [])),
            }
            for e in entities
        ]
        try:
            async with self.driver.session() as s:
                await s.run(query, batch=batch, symbol=symbol, case_id=case_id)
        except Exception as exc:
            logger.error("Failed to upsert Ring entities in Neo4j", error=str(exc))

    async def get_case_subgraph(
        self,
        case_id: str,
        max_nodes: int = 500,
        min_conf: float = 0.60,
    ) -> dict[str, Any]:
        """Fetch Cytoscape elements for a case."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        if not self.driver or not self._connected:
            # Degraded fallback from in-memory graph
            for n, data in list(self.fallback_nx.nodes(data=True))[:max_nodes]:
                nodes.append({"data": {"id": n, "label": f"Trader {n[:8]}", "type": data.get("type", "Trader")}})
            return {"nodes": nodes, "edges": edges, "degraded": True}

        query = """
        MATCH (a:Trader)-[l:LINKED {case_id: $case_id}]-(b:Trader)
        WHERE l.confidence >= $min_conf
        RETURN DISTINCT a.account_id AS src, b.account_id AS tgt, l.confidence AS conf, l.methods AS methods
        LIMIT $max_nodes
        """
        try:
            async with self.driver.session() as s:
                res = await s.run(query, case_id=case_id, min_conf=min_conf, max_nodes=max_nodes)
                records = await res.data()
                if not records:
                    # Fallback to all linked edges in case case_id was stored with symbol key
                    fallback_query = """
                    MATCH (a:Trader)-[l:LINKED]-(b:Trader)
                    WHERE l.confidence >= $min_conf
                    RETURN DISTINCT a.account_id AS src, b.account_id AS tgt, l.confidence AS conf, l.methods AS methods
                    LIMIT $max_nodes
                    """
                    res = await s.run(fallback_query, min_conf=min_conf, max_nodes=max_nodes)
                    records = await res.data()
                seen_nodes = set()
                for r in records:
                    src, tgt = str(r["src"]), str(r["tgt"])
                    conf = float(r["conf"])
                    if src not in seen_nodes:
                        seen_nodes.add(src)
                        nodes.append({"data": {"id": src, "label": f"Trader {src[:8]}", "type": "Trader"}})
                    if tgt not in seen_nodes:
                        seen_nodes.add(tgt)
                        nodes.append({"data": {"id": tgt, "label": f"Trader {tgt[:8]}", "type": "Trader"}})

                    edges.append({
                        "data": {
                            "id": f"link_{src}_{tgt}",
                            "source": src,
                            "target": tgt,
                            "type": "LINKED",
                            "confidence": conf,
                            "weight": conf,
                        }
                    })
        except Exception as exc:
            logger.error("Error executing case_subgraph query", error=str(exc))

        return {"nodes": nodes, "edges": edges, "degraded": self.degraded_mode}
