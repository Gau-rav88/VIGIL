CREATE INDEX traded_ticker_ts IF NOT EXISTS FOR ()-[r:TRADED_WITH]-() ON (r.ticker, r.ts);
CREATE INDEX sync_ticker      IF NOT EXISTS FOR ()-[r:SYNCHRONIZED_WITH]-() ON (r.ticker, r.window_start_ms);
CREATE INDEX linked_case      IF NOT EXISTS FOR ()-[r:LINKED]-() ON (r.case_id);
