-- ════════════════════════════════════════════════════════════
-- Phase 13.8 — Usage tracking + subscriptions
-- usage_events: per-call AI/image/enrichment cost tracking (replaces estimates)
-- subscriptions: per-workspace billing state (MRR, plan history, payment status)
-- ════════════════════════════════════════════════════════════

-- 1. Usage events — every billable API call (AI, image gen, enrichment) writes one row
CREATE TABLE IF NOT EXISTS usage_events (
  id           BIGSERIAL PRIMARY KEY,
  workspace_id BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id      BIGINT REFERENCES users(id) ON DELETE SET NULL,
  event_type   TEXT NOT NULL,                -- 'ai_score_leads', 'ai_draft_dm', 'image_gen', 'apollo_enrich', etc.
  cost_cents   INTEGER NOT NULL DEFAULT 0,   -- our actual cost in US cents
  units        INTEGER NOT NULL DEFAULT 1,   -- e.g. 100 leads scored, 1 image generated
  meta         JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_events_workspace_created ON usage_events(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_usage_events_type ON usage_events(event_type);

ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='usage_events' AND policyname='Service role full access') THEN
    CREATE POLICY "Service role full access" ON usage_events FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;


-- 2. Subscriptions — current + historical billing state per workspace
CREATE TABLE IF NOT EXISTS subscriptions (
  id                   BIGSERIAL PRIMARY KEY,
  workspace_id         BIGINT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  plan                 TEXT NOT NULL CHECK (plan IN ('basic','mid','elite')),
  status               TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','canceled','past_due','trial','beta')),
  monthly_amount_cents INTEGER NOT NULL DEFAULT 0,  -- 0 for free/beta/trial
  payment_method       TEXT,                          -- 'stripe' | 'manual' | 'beta' | 'free'
  external_id          TEXT,                          -- e.g. Stripe subscription_id when wired up
  notes                TEXT,
  started_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  canceled_at          TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_workspace ON subscriptions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
-- Only one ACTIVE/TRIAL/BETA subscription per workspace at a time
CREATE UNIQUE INDEX IF NOT EXISTS uniq_active_sub_per_workspace
  ON subscriptions(workspace_id) WHERE status IN ('active','trial','beta');

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='subscriptions' AND policyname='Service role full access') THEN
    CREATE POLICY "Service role full access" ON subscriptions FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;


-- 3. Seed initial subscriptions for existing workspaces
-- Joe (workspace 1) → elite, beta status (free), $0/mo
-- Jane (workspace 2) → basic, beta status, $0/mo
INSERT INTO subscriptions (workspace_id, plan, status, monthly_amount_cents, payment_method, notes)
SELECT w.id, w.plan, 'beta', 0, 'beta', 'Auto-created during 13.8 migration'
FROM workspaces w
WHERE NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.workspace_id = w.id AND s.status IN ('active','trial','beta'));
