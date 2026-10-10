// params: $ticker, $t0, $t1, $max_p (0.01), $min_windows (3)
MATCH (a:Trader)-[s:SYNCHRONIZED_WITH {ticker: $ticker}]->(b:Trader)
WHERE s.window_start_ms >= $t0 AND s.window_end_ms <= $t1 AND s.p_value < $max_p
WITH a, b, count(s) AS windows, sum(s.co_orders) AS co_orders, min(s.p_value) AS best_p, avg(s.median_dt_ms) AS avg_dt_ms
WHERE windows >= $min_windows
RETURN a.account_id AS a, b.account_id AS b, windows, co_orders, best_p, avg_dt_ms
ORDER BY co_orders DESC;
