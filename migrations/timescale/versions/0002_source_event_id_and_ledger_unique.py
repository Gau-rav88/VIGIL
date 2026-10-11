"""Add source_event_id to trades, orders_l3, social_messages and UNIQUE constraint on evidence_ledger(prev_entry_hash)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12 00:00:00.000000

"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UPGRADE_SQL = """
SET search_path TO vigil, public;

ALTER TABLE trades ADD COLUMN IF NOT EXISTS source_event_id text;
ALTER TABLE orders_l3 ADD COLUMN IF NOT EXISTS source_event_id text;
ALTER TABLE social_messages ADD COLUMN IF NOT EXISTS source_event_id text;

ALTER TABLE evidence_ledger DISABLE TRIGGER USER;
DELETE FROM evidence_ledger a
USING evidence_ledger b
WHERE a.entry_id < b.entry_id
  AND a.prev_entry_hash = b.prev_entry_hash
  AND NOT EXISTS (
      SELECT 1 FROM evidence_ledger c WHERE c.prev_entry_hash = a.entry_hash
  );
ALTER TABLE evidence_ledger ENABLE TRIGGER USER;

CREATE UNIQUE INDEX IF NOT EXISTS evidence_ledger_prev_hash_idx ON evidence_ledger (prev_entry_hash);
"""

DOWNGRADE_SQL = """
SET search_path TO vigil, public;

DROP INDEX IF EXISTS evidence_ledger_prev_hash_idx;
ALTER TABLE social_messages DROP COLUMN IF EXISTS source_event_id;
ALTER TABLE orders_l3 DROP COLUMN IF EXISTS source_event_id;
ALTER TABLE trades DROP COLUMN IF EXISTS source_event_id;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
