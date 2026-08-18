-- ════════════════════════════════════════════════════════════
-- Phase 13.2 — Multi-Tenant Schema Foundation
-- Adds workspaces table + workspace_id to 23 tenant-scoped tables.
-- All changes are ADDITIVE with safe defaults; production keeps working
-- because every existing INSERT path implicitly assigns workspace_id=1 (Joe).
-- ════════════════════════════════════════════════════════════

-- 1. Workspaces table — one row per tenant
CREATE TABLE IF NOT EXISTS workspaces (
  id            BIGSERIAL PRIMARY KEY,
  owner_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  plan          TEXT NOT NULL DEFAULT 'basic' CHECK (plan IN ('basic','mid','elite')),
  settings      JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_workspaces_owner ON workspaces(owner_user_id);

ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='workspaces' AND policyname='Service role full access') THEN
    CREATE POLICY "Service role full access" ON workspaces FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;

-- 2. Seed Joe's workspace (id=1, elite plan)
INSERT INTO workspaces (id, owner_user_id, name, plan)
VALUES (1, 1, 'TPL Collective', 'elite')
ON CONFLICT (id) DO NOTHING;

SELECT setval('workspaces_id_seq', GREATEST((SELECT COALESCE(MAX(id), 0) FROM workspaces), 1));

-- 3. users.workspace_id — each user's default workspace
ALTER TABLE users ADD COLUMN IF NOT EXISTS workspace_id BIGINT REFERENCES workspaces(id) DEFAULT 1;
UPDATE users SET workspace_id = 1 WHERE workspace_id IS NULL;

-- 4. Add workspace_id to every tenant-scoped table
DO $$
DECLARE
  t TEXT;
  tenant_tables TEXT[] := ARRAY[
    'leads',
    'opportunities',
    'pipelines',
    'tasks',
    'email_funnels',
    'email_funnel_steps',
    'email_funnel_enrollments',
    'smart_lists',
    'lead_notes',
    'lead_activity',
    'lead_stage_history',
    'content_posts',
    'ideas',
    'drip_queue',
    'email_send_log',
    'email_queue',
    'emails_sent',
    'email_daily_limits',
    'automation_runs',
    'automation_settings',
    'goals',
    'contact_communications',
    'magnet_deliveries'
  ];
BEGIN
  FOREACH t IN ARRAY tenant_tables LOOP
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS workspace_id BIGINT REFERENCES workspaces(id) DEFAULT 1', t);
    EXECUTE format('UPDATE %I SET workspace_id = 1 WHERE workspace_id IS NULL', t);
    EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%s_workspace ON %I(workspace_id)', t, t);
  END LOOP;
END $$;

-- NOT NULL constraint deferred until Phase 13.3 confirms scoping is live;
-- defaulting to 1 means current INSERT paths keep working with zero code change.
