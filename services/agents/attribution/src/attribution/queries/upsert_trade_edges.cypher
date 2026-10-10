// params: $rows
UNWIND $rows AS row
MERGE (s:Trader {account_id: row.seller}) ON CREATE SET s.first_seen_ms = row.ts_ms, s.is_synthetic = row.is_synthetic SET s.last_seen_ms = row.ts_ms
MERGE (b:Trader {account_id: row.buyer})  ON CREATE SET b.first_seen_ms = row.ts_ms, b.is_synthetic = row.is_synthetic SET b.last_seen_ms = row.ts_ms
MERGE (k:Ticker {symbol: row.ticker}) ON CREATE SET k.exchange = row.exchange
MERGE (s)-[e:TRADED_WITH {ticker: row.ticker, ts: row.bucket_ms}]->(b)
  ON CREATE SET e.qty = row.qty, e.notional = row.notional, e.n_trades = row.n, e.ts_end = row.ts_end_ms, e.trade_ids = row.trade_ids
  ON MATCH  SET e.qty = e.qty + row.qty, e.notional = e.notional + row.notional, e.n_trades = e.n_trades + row.n, e.ts_end = row.ts_end_ms;
