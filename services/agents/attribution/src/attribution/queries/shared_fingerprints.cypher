// params: $accounts
MATCH (t:Trader)-[u:USES_DEVICE]->(d:Device)
WHERE (size($accounts) = 0 OR t.account_id IN $accounts)
WITH d, collect(DISTINCT t.account_id) AS accounts, sum(u.n_orders) AS n_orders
WHERE size(accounts) >= 2
RETURN 'SHARED_DEVICE' AS method, d.device_fp AS key, accounts, n_orders
UNION
MATCH (t:Trader)-[h:HAS_FINGERPRINT]->(f:NetworkFingerprint)
WHERE (size($accounts) = 0 OR t.account_id IN $accounts)
WITH f, collect(DISTINCT t.account_id) AS accounts, sum(h.n_orders) AS n_orders
WHERE size(accounts) >= 2
RETURN 'SHARED_NETWORK' AS method, f.fp_key AS key, accounts, n_orders;
