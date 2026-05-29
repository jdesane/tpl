-- Phase 16: Prospect Engagement
-- Tracks page-level engagement for private prospect briefs
-- (e.g. tplcollective.ai/jay-dural). Reusable per-prospect infra.
--
-- NOTE: A separate `prospects` table already exists for the recruiting
-- pipeline (uuid-keyed). This module uses `prospect_briefs` to avoid
-- collision. Different concept, different table.

CREATE TABLE IF NOT EXISTS prospect_briefs (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    display_name TEXT,
    notify_email TEXT,                -- override notification recipient
    workspace_id INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE prospect_briefs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON prospect_briefs;
CREATE POLICY service_role_all ON prospect_briefs FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS prospect_briefs_updated_at ON prospect_briefs;
CREATE TRIGGER prospect_briefs_updated_at
BEFORE UPDATE ON prospect_briefs
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO prospect_briefs (slug, display_name, notify_email, workspace_id)
VALUES ('jay-dural', 'Jay Dural', 'joe@tplcollective.ai', 1)
ON CONFLICT (slug) DO NOTHING;

CREATE TABLE IF NOT EXISTS prospect_engagement_events (
    id BIGSERIAL PRIMARY KEY,
    prospect_id TEXT NOT NULL,
    visitor_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    visit_number INTEGER DEFAULT 1,
    event TEXT NOT NULL,
    url TEXT,
    referrer TEXT,
    user_agent TEXT,
    data JSONB,
    workspace_id INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_engagement_prospect ON prospect_engagement_events (prospect_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_engagement_visitor ON prospect_engagement_events (visitor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_engagement_session ON prospect_engagement_events (session_id);
CREATE INDEX IF NOT EXISTS idx_engagement_event ON prospect_engagement_events (prospect_id, event, created_at DESC);

ALTER TABLE prospect_engagement_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON prospect_engagement_events;
CREATE POLICY service_role_all ON prospect_engagement_events FOR ALL TO service_role USING (true) WITH CHECK (true);
