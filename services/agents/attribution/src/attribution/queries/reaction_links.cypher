// params: $ticker, $min_conf (0.6)
MATCH (t:Trader)-[r:REACTED_TO {ticker: $ticker}]->(c:Channel)-[p:PROMOTED]->(k:Ticker {symbol: $ticker})
WHERE r.confidence >= $min_conf
RETURN t.account_id AS account, c.channel_key AS channel, r.n_reactions AS n,
       r.median_latency_ms AS median_latency_ms, r.null_median_latency_ms AS null_ms, r.p_value AS p,
       p.peak_hype AS peak_hype
ORDER BY r.confidence DESC;
