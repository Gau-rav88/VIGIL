from __future__ import annotations

from collections import defaultdict
from typing import Any, Sequence

from attribution.models import CyclePath


class CycleDetector:
    """
    Detects directed wash-trading cycles of length 2-6 with:
    - Time ordering: trade[i].ts <= trade[i+1].ts
    - Quantity matched: abs(r.qty - rels[0].qty) <= qty_tol * rels[0].qty
    - Net position change approximately zero.
    """

    def __init__(
        self,
        min_len: int = 2,
        max_len: int = 6,
        qty_tol: float = 0.05,
        max_cycle_ms: int = 900_000,
    ) -> None:
        self.min_len = min_len
        self.max_len = max_len
        self.qty_tol = qty_tol
        self.max_cycle_ms = max_cycle_ms

    def find_cycles(
        self,
        trades: Sequence[dict[str, Any]],
        candidates: set[str] | None = None,
    ) -> list[CyclePath]:
        """
        In-memory DFS search for wash trading cycles.
        trades format: list of dicts with:
        seller, buyer, qty, price, ts_ms, trade_id
        """
        if not trades:
            return []

        # Build adjacency graph: seller -> list of outgoing edges
        adj: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for t in trades:
            s = str(t.get("seller", ""))
            b = str(t.get("buyer", ""))
            if s and b and s != b:
                adj[s].append({
                    "buyer": b,
                    "qty": float(t.get("qty", 0.0)),
                    "price": float(t.get("price", 0.0)),
                    "ts_ms": int(t.get("ts_ms", 0)),
                    "trade_id": str(t.get("trade_id", "")),
                })

        detected_cycles: list[CyclePath] = []
        seen_cycle_fingerprints: set[tuple[str, ...]] = set()

        all_accounts = list(adj.keys()) if candidates is None else list(candidates)

        for start_acc in all_accounts:
            for first_edge in adj.get(start_acc, []):
                lead_qty = first_edge["qty"]
                t0 = first_edge["ts_ms"]

                # DFS stack: (current_node, visited_nodes, edges_path)
                stack: list[tuple[str, list[str], list[dict[str, Any]]]] = [
                    (first_edge["buyer"], [start_acc], [first_edge])
                ]

                while stack:
                    curr_node, visited, path = stack.pop()
                    path_len = len(path)

                    # Check if returned to start_acc
                    if curr_node == start_acc:
                        if self.min_len <= path_len <= self.max_len:
                            # Canonical rotation check (lowest account id first)
                            cycle_accs = list(visited)
                            min_acc = min(cycle_accs)
                            min_idx = cycle_accs.index(min_acc)
                            canonical = tuple(cycle_accs[min_idx:] + cycle_accs[:min_idx])

                            if canonical not in seen_cycle_fingerprints:
                                seen_cycle_fingerprints.add(canonical)
                                cycle_vol = sum(e["qty"] for e in path)
                                start_ts = path[0]["ts_ms"]
                                end_ts = path[-1]["ts_ms"]
                                trade_ids = [e["trade_id"] for e in path if e["trade_id"]]

                                detected_cycles.append(
                                    CyclePath(
                                        accounts=list(canonical),
                                        length=path_len,
                                        lead_qty=lead_qty,
                                        cycle_volume=cycle_vol,
                                        start_ms=start_ts,
                                        end_ms=end_ts,
                                        evidence_trade_ids=trade_ids,
                                    )
                                )
                        continue

                    if path_len >= self.max_len:
                        continue

                    if curr_node in visited:
                        continue  # no intermediate repeated nodes

                    # Explore outgoing edges from curr_node
                    for next_edge in adj.get(curr_node, []):
                        # Time ordering check
                        if next_edge["ts_ms"] < path[-1]["ts_ms"]:
                            continue

                        # Duration check
                        if (next_edge["ts_ms"] - t0) > self.max_cycle_ms:
                            continue

                        # Quantity matching check
                        if abs(next_edge["qty"] - lead_qty) > (self.qty_tol * lead_qty):
                            continue

                        stack.append((
                            next_edge["buyer"],
                            visited + [curr_node],
                            path + [next_edge],
                        ))

        return detected_cycles
