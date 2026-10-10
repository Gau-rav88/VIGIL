// params: $accounts, $min_share (0.8), $min_group (3)
MATCH (t:Trader)-[r:ROUTED_THROUGH]->(b:Broker)
WHERE (size($accounts) = 0 OR t.account_id IN $accounts) AND r.share >= $min_share
WITH b, r.gateway_id AS gw, collect(DISTINCT t.account_id) AS accounts
WHERE size(accounts) >= $min_group
RETURN b.broker_id AS broker, gw AS gateway, accounts, size(accounts) AS n;
