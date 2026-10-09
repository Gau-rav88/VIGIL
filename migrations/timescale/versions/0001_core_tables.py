"""Core tables, hypertables, continuous aggregates, and evidence ledger

Revision ID: 0001
Revises: None
Create Date: 2026-10-07 00:00:00.000000

"""
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

UPGRADE_SQL = """
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto CASCADE;
CREATE SCHEMA IF NOT EXISTS vigil;
SET search_path TO vigil, public;

-- ===== market =====
CREATE TABLE IF NOT EXISTS trades (
  ts              timestamptz NOT NULL,
  event_id        uuid        NOT NULL,
  exchange        text        NOT NULL,
  symbol          text        NOT NULL,
  trade_id        text        NOT NULL,
  seq             bigint      NOT NULL,
  price           numeric(18,8) NOT NULL,
  qty             bigint      NOT NULL,
  aggressor_side  text        NOT NULL,
  buyer_account   text        NOT NULL,
  seller_account  text        NOT NULL,
  buyer_broker    text        NOT NULL,
  seller_broker   text        NOT NULL,
  buyer_gateway   text, seller_gateway text,
  buy_order_id    text, sell_order_id text,
  buyer_device    text, seller_device text,
  buyer_ip        text, seller_ip text,
  buyer_asn       integer, seller_asn integer,
  buyer_api_client text, seller_api_client text,
  buyer_latency_us integer, seller_latency_us integer,
  market_segment  text, is_synthetic boolean NOT NULL DEFAULT false,
  ts_ingest       timestamptz NOT NULL,
  PRIMARY KEY (symbol, trade_id, ts)
);
SELECT create_hypertable('trades','ts', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS trades_buyer_idx  ON trades (buyer_account,  ts DESC);
CREATE INDEX IF NOT EXISTS trades_seller_idx ON trades (seller_account, ts DESC);

CREATE TABLE IF NOT EXISTS orders_l3 (
  ts timestamptz NOT NULL, event_id uuid NOT NULL, exchange text NOT NULL, symbol text NOT NULL, seq bigint NOT NULL,
  order_id text NOT NULL, orig_order_id text, action text NOT NULL, side text NOT NULL, order_type text,
  price numeric(18,8), qty bigint, leaves_qty bigint, account_id text NOT NULL, broker_id text NOT NULL,
  gateway_id text, device_fp text, ip_hash text, asn integer, api_client_id text, order_to_ack_us integer,
  is_synthetic boolean NOT NULL DEFAULT false, ts_ingest timestamptz NOT NULL,
  PRIMARY KEY (symbol, seq, ts)
);
SELECT create_hypertable('orders_l3','ts', chunk_time_interval => INTERVAL '6 hours', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS orders_l3_acct_idx ON orders_l3 (account_id, ts DESC);

CREATE TABLE IF NOT EXISTS l2_snapshots (
  ts timestamptz NOT NULL, symbol text NOT NULL, seq bigint NOT NULL, exchange text NOT NULL,
  bids jsonb NOT NULL, asks jsonb NOT NULL, depth_levels int NOT NULL, is_synthetic boolean NOT NULL DEFAULT false,
  PRIMARY KEY (symbol, seq, ts)
);
SELECT create_hypertable('l2_snapshots','ts', chunk_time_interval => INTERVAL '6 hours', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS l2_metrics_1s (
  ts timestamptz NOT NULL, symbol text NOT NULL,
  best_bid numeric(18,8), best_ask numeric(18,8), rel_spread double precision,
  bid_depth_5 bigint, ask_depth_5 bigint, depth_imbalance double precision,
  PRIMARY KEY (symbol, ts)
);
SELECT create_hypertable('l2_metrics_1s','ts', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

-- ===== social =====
CREATE TABLE IF NOT EXISTS social_messages (
  ts timestamptz NOT NULL, event_id uuid NOT NULL, platform text NOT NULL, channel_id text NOT NULL, channel_name text,
  channel_visibility text NOT NULL, message_id text NOT NULL, author_id text NOT NULL, text text NOT NULL, lang text,
  reply_to_message_id text, forwarded_from_channel_id text, views int, reactions int, urls text[], raw_sha256 text NOT NULL,
  is_synthetic boolean NOT NULL DEFAULT false, ts_ingest timestamptz NOT NULL,
  PRIMARY KEY (platform, channel_id, message_id, ts)
);
SELECT create_hypertable('social_messages','ts', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS social_signals (
  ts timestamptz NOT NULL, signal_id uuid NOT NULL, message_event_id uuid NOT NULL, platform text NOT NULL, channel_id text NOT NULL,
  author_id text NOT NULL, ticker text NOT NULL, ticker_confidence real NOT NULL, mention_type text, cta_class text NOT NULL,
  cta_confidence real, target_price numeric(18,8), scheduled_action_time timestamptz, urgency real, sentiment real,
  near_dup_cluster_id text, forward_cascade_depth int DEFAULT 0, raw_sha256 text NOT NULL, parser_mode text NOT NULL, parser_version text,
  PRIMARY KEY (signal_id, ts)
);
SELECT create_hypertable('social_signals','ts', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS social_signals_ticker_idx ON social_signals (ticker, ts DESC);

CREATE TABLE IF NOT EXISTS hype_scores (
  ts timestamptz NOT NULL, ticker text NOT NULL, hype_score real NOT NULL,
  f_rate real, f_auth real, f_cta real, f_dup real, f_urg real, f_xch real,
  msg_count int, unique_authors int, channels int,
  PRIMARY KEY (ticker, ts)
);
SELECT create_hypertable('hype_scores','ts', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

-- ===== analytics outputs =====
CREATE TABLE IF NOT EXISTS anomalies (
  detected_at timestamptz NOT NULL, anomaly_id uuid NOT NULL, type text NOT NULL, source_agent text NOT NULL, symbol text NOT NULL,
  window_start timestamptz NOT NULL, window_end timestamptz NOT NULL, score real NOT NULL, severity text NOT NULL,
  metrics jsonb NOT NULL, participants text[], evidence_refs jsonb NOT NULL, detector_version text NOT NULL, config_hash text NOT NULL,
  case_id uuid, PRIMARY KEY (anomaly_id, detected_at)
);
SELECT create_hypertable('anomalies','detected_at', chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS anomalies_symbol_idx ON anomalies (symbol, window_start DESC);

CREATE TABLE IF NOT EXISTS mrs_1m (
  ts timestamptz NOT NULL, symbol text NOT NULL, mrs real NOT NULL, components jsonb NOT NULL, PRIMARY KEY (symbol, ts)
);
SELECT create_hypertable('mrs_1m','ts', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);

-- ===== cases, ledger, dossiers =====
DO $$ BEGIN
  CREATE TYPE case_status AS ENUM ('OPENED','ENRICHING','ALIGNED','ATTRIBUTING','ASSESSING','DRAFTING','VALIDATING','SIGNING',
    'PENDING_REVIEW','APPROVED','PUBLISHED','REJECTED','REWORK','WATCHLIST','CLOSED_NO_ACTION','FAILED');
EXCEPTION
  WHEN duplicate_object THEN null;
END $$;

CREATE TABLE IF NOT EXISTS cases (
  case_id uuid PRIMARY KEY, symbol text NOT NULL, exchange text NOT NULL, status case_status NOT NULL,
  window_start timestamptz NOT NULL, window_end timestamptz NOT NULL, trigger_anomaly_id uuid NOT NULL,
  mrs real, overall_confidence real, completeness real, assigned_to text, state jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  is_synthetic boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS cases_status_idx ON cases (status, updated_at DESC);

CREATE TABLE IF NOT EXISTS case_events (
  id bigserial PRIMARY KEY, case_id uuid NOT NULL REFERENCES cases, ts timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL, kind text NOT NULL, payload jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_objects (
  evidence_id text PRIMARY KEY, case_id uuid NOT NULL REFERENCES cases, type text NOT NULL, sha256 char(64) NOT NULL,
  uri text NOT NULL, bytes bigint NOT NULL, captured_at timestamptz NOT NULL, meta jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS evidence_ledger (
  entry_id bigserial PRIMARY KEY, ts timestamptz NOT NULL DEFAULT now(), case_id uuid,
  entry_type text NOT NULL,
  actor text NOT NULL, subject_sha256 char(64) NOT NULL, payload jsonb NOT NULL DEFAULT '{}',
  prev_entry_hash char(64) NOT NULL, entry_hash char(64) NOT NULL UNIQUE
);

CREATE OR REPLACE FUNCTION forbid_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'evidence_ledger is append-only'; END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ledger_no_update ON evidence_ledger;
CREATE TRIGGER ledger_no_update BEFORE UPDATE OR DELETE ON evidence_ledger FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

DROP TRIGGER IF EXISTS ledger_no_truncate ON evidence_ledger;
CREATE TRIGGER ledger_no_truncate BEFORE TRUNCATE ON evidence_ledger FOR EACH STATEMENT EXECUTE FUNCTION forbid_mutation();

CREATE TABLE IF NOT EXISTS dossiers (
  dossier_id uuid PRIMARY KEY, case_id uuid NOT NULL REFERENCES cases, version int NOT NULL, supersedes uuid,
  json_uri text NOT NULL, pdf_uri text, sig_uri text, bundle_uri text, digest_sha256 char(64) NOT NULL,
  merkle_root char(64) NOT NULL, key_id text NOT NULL, narrative_mode text NOT NULL,
  review_status text NOT NULL DEFAULT 'NOT_REVIEWED', created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (case_id, version)
);

CREATE TABLE IF NOT EXISTS signing_keys (
  key_id text PRIMARY KEY, alg text NOT NULL DEFAULT 'Ed25519', public_key_pem text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), retired_at timestamptz
);

CREATE TABLE IF NOT EXISTS audit_log (
  id bigserial PRIMARY KEY, ts timestamptz NOT NULL DEFAULT now(), user_id text, role text, method text, path text,
  status int, request_hash char(64), meta jsonb
);

CREATE TABLE IF NOT EXISTS link_feedback (
  id bigserial PRIMARY KEY, case_id uuid NOT NULL, user_id text NOT NULL, a_account text NOT NULL, b_account text NOT NULL,
  verdict text NOT NULL CHECK (verdict IN ('CONFIRM','REJECT')), comment text, ts timestamptz NOT NULL DEFAULT now()
);
"""

def upgrade() -> None:
    op.execute(UPGRADE_SQL)

def downgrade() -> None:
    pass
