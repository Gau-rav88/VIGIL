// params: $ticker, $t0 (epoch ms), $t1, $max_cycle_ms (e.g. 900000), $qty_tol (e.g. 0.05), $min_len (2), $max_len (6), $candidates (list of account_id)
MATCH p = (a:Trader)-[rels:TRADED_WITH*2..6 {ticker: $ticker}]->(a)
WHERE (size($candidates) = 0 OR a.account_id IN $candidates)
  AND size(rels) >= $min_len AND size(rels) <= $max_len
  AND rels[0].ts >= $t0 AND rels[-1].ts_end <= $t1
  AND (rels[-1].ts_end - rels[0].ts) <= $max_cycle_ms
  AND ALL(i IN range(0, size(rels) - 2) WHERE rels[i].ts <= rels[i+1].ts)
  AND ALL(r IN rels WHERE abs(r.qty - rels[0].qty) <= $qty_tol * rels[0].qty)
WITH p, rels, a, nodes(p)[0..-1] AS ns
WHERE size(ns) = size(apoc.coll.toSet(ns))
  AND ALL(n IN ns WHERE elementId(a) <= elementId(n))
RETURN [n IN ns | n.account_id]                       AS accounts,
       size(rels)                                     AS length,
       rels[0].qty                                    AS lead_qty,
       reduce(v = 0, r IN rels | v + r.qty)           AS cycle_volume,
       rels[0].ts                                     AS start_ms,
       rels[-1].ts_end                                AS end_ms,
       [r IN rels | r.trade_ids[0]]                   AS evidence_trade_ids
ORDER BY cycle_volume DESC
LIMIT 500;
