-- Research-stage capture funnel migration
-- Adds stage/magnet tracking to leads + magnet_deliveries table for signed download links
-- Safe to re-run (all IF NOT EXISTS)

ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS stage TEXT DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS magnet TEXT,
  ADD COLUMN IF NOT EXISTS magnet_downloaded_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
CREATE INDEX IF NOT EXISTS idx_leads_magnet ON leads(magnet);

CREATE TABLE IF NOT EXISTS magnet_deliveries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
  magnet TEXT NOT NULL,
  delivered_at TIMESTAMPTZ DEFAULT NOW(),
  download_token TEXT UNIQUE NOT NULL,
  downloaded_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_magnet_deliveries_token ON magnet_deliveries(download_token);
CREATE INDEX IF NOT EXISTS idx_magnet_deliveries_lead ON magnet_deliveries(lead_id);

-- Enable RLS consistent with other tables
ALTER TABLE magnet_deliveries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_all" ON magnet_deliveries;
CREATE POLICY "service_role_all" ON magnet_deliveries
  FOR ALL TO service_role USING (true) WITH CHECK (true);
