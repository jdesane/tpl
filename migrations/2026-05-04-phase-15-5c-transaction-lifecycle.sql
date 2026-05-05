-- ════════════════════════════════════════════════════════════
-- Phase 15.5c — Transaction Lifecycle (CTE "My Business" sheet)
--
-- pipeline_entries was a flat 1-10 rating + a closed-bool flag. CTE's
-- My Business tracks the full deal lifecycle: PRE_SIGNED → ACTIVE →
-- PENDING → CLOSED → EXPIRED. Adds list_date, expiration_date, and
-- expected_close_date so the UI can compute DOM and surface expiring-
-- in-30-days alerts.
-- ════════════════════════════════════════════════════════════

ALTER TABLE pipeline_entries
  ADD COLUMN IF NOT EXISTS status TEXT
    CHECK (status IN ('PRE_SIGNED','ACTIVE','PENDING','CLOSED','EXPIRED','WITHDRAWN','CANCELLED'))
    DEFAULT 'PRE_SIGNED';

ALTER TABLE pipeline_entries ADD COLUMN IF NOT EXISTS list_date            DATE;
ALTER TABLE pipeline_entries ADD COLUMN IF NOT EXISTS expiration_date      DATE;
ALTER TABLE pipeline_entries ADD COLUMN IF NOT EXISTS expected_close_date  DATE;
ALTER TABLE pipeline_entries ADD COLUMN IF NOT EXISTS net_commission       NUMERIC(12,2);
ALTER TABLE pipeline_entries ADD COLUMN IF NOT EXISTS mls_number           TEXT;

-- Backfill existing rows that have closed=true to status=CLOSED
UPDATE pipeline_entries SET status = 'CLOSED' WHERE closed = true AND (status IS NULL OR status = 'PRE_SIGNED');

CREATE INDEX IF NOT EXISTS idx_pipeline_entries_status         ON pipeline_entries(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_entries_expiration     ON pipeline_entries(expiration_date);
CREATE INDEX IF NOT EXISTS idx_pipeline_entries_expected_close ON pipeline_entries(expected_close_date);
