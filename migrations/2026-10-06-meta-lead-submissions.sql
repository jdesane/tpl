-- One row per Meta leadgen ID. The de-duplication key for the webhook and the
-- 6-hour backfill, the audit trail of what Meta sent, and what lets a failed
-- fetch be retried instead of silently lost.
--
--   received  webhook/sync saw the ID, fetch in progress
--   stored    lead created or updated in leads (lead_id set)
--   test      Meta Lead Ads Testing Tool lead (dummy data); alerted, not stored as a contact
--   failed    fetch or parse failed; error set; the sync retries it

CREATE TABLE IF NOT EXISTS meta_lead_submissions (
  id                 BIGSERIAL PRIMARY KEY,
  workspace_id       INTEGER NOT NULL DEFAULT 1,
  leadgen_id         TEXT NOT NULL UNIQUE,
  form_id            TEXT,
  form_name          TEXT,
  ad_id              TEXT,
  ad_name            TEXT,
  adset_name         TEXT,
  campaign_name      TEXT,
  platform           TEXT,
  is_organic         BOOLEAN,
  field_data         JSONB NOT NULL DEFAULT '[]'::jsonb,
  status             TEXT NOT NULL DEFAULT 'received'
                     CHECK (status IN ('received', 'stored', 'test', 'failed')),
  error              TEXT,
  lead_id            BIGINT REFERENCES leads(id) ON DELETE SET NULL,
  via                TEXT,              -- webhook | sync
  attempts           INTEGER NOT NULL DEFAULT 0,
  alerted_failure_at TIMESTAMPTZ,
  received_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at       TIMESTAMPTZ,
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS meta_lead_submissions_status_idx ON meta_lead_submissions (status, received_at);
CREATE INDEX IF NOT EXISTS meta_lead_submissions_lead_idx ON meta_lead_submissions (lead_id);

ALTER TABLE meta_lead_submissions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON meta_lead_submissions;
CREATE POLICY service_role_all ON meta_lead_submissions FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS meta_lead_submissions_updated_at ON meta_lead_submissions;
CREATE TRIGGER meta_lead_submissions_updated_at
BEFORE UPDATE ON meta_lead_submissions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
