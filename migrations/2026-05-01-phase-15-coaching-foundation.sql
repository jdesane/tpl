-- ════════════════════════════════════════════════════════════
-- Phase 15 — Coaching Platform Foundation
-- Adds coaching_clients + business plan / GPS / 4-1-1 / pipeline /
-- activity / coaching call / recruiting tables for the coaching module.
--
-- All tables are workspace-scoped (default 1 = Joe).
-- coaching_clients FK→leads(id) so every client is also a CRM contact.
-- coaching_clients.user_id is nullable; populated when the client is
-- granted a portal login.
-- All tables: RLS enabled, single service-role policy (matches existing pattern).
-- ════════════════════════════════════════════════════════════

-- 1. coaching_clients ─ the spine of the module
CREATE TABLE IF NOT EXISTS coaching_clients (
  id                    BIGSERIAL PRIMARY KEY,
  workspace_id          BIGINT NOT NULL REFERENCES workspaces(id) DEFAULT 1,
  lead_id               BIGINT NOT NULL REFERENCES leads(id) ON DELETE CASCADE UNIQUE,
  user_id               BIGINT REFERENCES users(id) ON DELETE SET NULL,
  brokerage             TEXT CHECK (brokerage IN ('LPT','EXP','KW','REMAX','C21','COMPASS','REAL','OTHER')),
  lpt_comp_plan         TEXT CHECK (lpt_comp_plan IN ('BUSINESS_BUILDER','BROKERAGE_PARTNER')),
  license_date          DATE,
  market_city           TEXT,
  market_state          TEXT,
  avg_sale_price        NUMERIC(12,2),
  avg_commission_rate   NUMERIC(6,5),  -- e.g. 0.02500
  call_cadence          TEXT CHECK (call_cadence IN ('WEEKLY','BIWEEKLY','MONTHLY')) DEFAULT 'WEEKLY',
  coaching_start_date   DATE DEFAULT CURRENT_DATE,
  status                TEXT CHECK (status IN ('ACTIVE','PAUSED','CHURNED')) DEFAULT 'ACTIVE',
  notes                 TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_coaching_clients_workspace ON coaching_clients(workspace_id);
CREATE INDEX IF NOT EXISTS idx_coaching_clients_status    ON coaching_clients(status);
CREATE INDEX IF NOT EXISTS idx_coaching_clients_lead      ON coaching_clients(lead_id);

-- 2. business_plans ─ one per client per year
CREATE TABLE IF NOT EXISTS business_plans (
  id                    BIGSERIAL PRIMARY KEY,
  workspace_id          BIGINT NOT NULL REFERENCES workspaces(id) DEFAULT 1,
  coaching_client_id    BIGINT NOT NULL REFERENCES coaching_clients(id) ON DELETE CASCADE,
  year                  INT NOT NULL,
  gci_target            NUMERIC(12,2) NOT NULL DEFAULT 0,
  notes                 TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (coaching_client_id, year)
);
CREATE INDEX IF NOT EXISTS idx_business_plans_workspace ON business_plans(workspace_id);
CREATE INDEX IF NOT EXISTS idx_business_plans_client    ON business_plans(coaching_client_id);

-- 3. budget_models ─ MREA Budget + Allocation + Survival
CREATE TABLE IF NOT EXISTS budget_models (
  id                            BIGSERIAL PRIMARY KEY,
  business_plan_id              BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE UNIQUE,
  -- Cost of Sale
  paid_to_brokerage             NUMERIC(12,2) DEFAULT 0,
  referrals_to_you_count        INT DEFAULT 0,
  referrals_avg_commission      NUMERIC(12,2) DEFAULT 0,
  referrals_split_pct           NUMERIC(5,4) DEFAULT 0.2500,
  seller_specialist_split_pct   NUMERIC(5,4) DEFAULT 0.3000,
  buyer_specialist_split_pct    NUMERIC(5,4) DEFAULT 0.5000,
  -- Operating Expenses (JSONB: { "label": amount } for flexibility)
  -- Pre-seeded with the MREA line items but UI lets agents add/remove.
  operating_expenses            JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- Allocation %s
  charity_pct                   NUMERIC(5,4) DEFAULT 0.1000,
  retirement_pct                NUMERIC(5,4) DEFAULT 0.1000,
  income_tax_pct                NUMERIC(5,4) DEFAULT 0.3000,
  -- Personal expenses (annual unless agent enters monthly via UI)
  personal_expenses             JSONB NOT NULL DEFAULT '{}'::jsonb,
  -- Survival
  avg_net_commission_per_close  NUMERIC(12,2) DEFAULT 0,
  -- Surplus allocation: array of { item, amount }
  surplus_allocation            JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_budget_models_plan ON budget_models(business_plan_id);

-- 4. economic_models ─ MREA Economic Model
CREATE TABLE IF NOT EXISTS economic_models (
  id                            BIGSERIAL PRIMARY KEY,
  business_plan_id              BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE UNIQUE,
  seller_pct                    NUMERIC(5,4) DEFAULT 0.5000,        -- 0.0–1.0
  seller_avg_sale_price         NUMERIC(12,2) DEFAULT 0,
  buyer_avg_sale_price          NUMERIC(12,2) DEFAULT 0,
  commission_rate               NUMERIC(6,5) DEFAULT 0.02500,
  listings_close_pct            NUMERIC(5,4) DEFAULT 0.8500,
  buyers_close_pct              NUMERIC(5,4) DEFAULT 0.8000,
  listing_appt_to_list_pct      NUMERIC(5,4) DEFAULT 0.6500,
  buyer_appt_to_work_pct        NUMERIC(5,4) DEFAULT 0.7500,
  avg_days_on_market            INT DEFAULT 60,
  avg_buyer_working_days        INT DEFAULT 60,
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_economic_models_plan ON economic_models(business_plan_id);

-- 5. lead_gen_models ─ Met / Haven't-Met split + 36 Ways
CREATE TABLE IF NOT EXISTS lead_gen_models (
  id                            BIGSERIAL PRIMARY KEY,
  business_plan_id              BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE UNIQUE,
  met_pct                       NUMERIC(5,4) DEFAULT 0.8000,
  current_met_db_size           INT DEFAULT 0,
  current_havent_met_db_size    INT DEFAULT 0,
  thirty_six_ways_met           JSONB NOT NULL DEFAULT '[]'::jsonb,  -- 36 strings
  twelve_ways_havent_met        JSONB NOT NULL DEFAULT '[]'::jsonb,  -- 12 strings
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lead_gen_models_plan ON lead_gen_models(business_plan_id);

-- 6. lead_sources ─ many per business plan
CREATE TABLE IF NOT EXISTS lead_sources (
  id                  BIGSERIAL PRIMARY KEY,
  business_plan_id    BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE,
  source_name         TEXT NOT NULL,
  txns_planned        INT DEFAULT 0,
  txns_actual         INT DEFAULT 0,
  cost_to_secure      NUMERIC(12,2) DEFAULT 0,
  income_earned       NUMERIC(12,2) DEFAULT 0,
  sort_order          INT DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lead_sources_plan ON lead_sources(business_plan_id);

-- 7. wealth_goals ─ 1-3 personal wealth goals per plan
CREATE TABLE IF NOT EXISTS wealth_goals (
  id                  BIGSERIAL PRIMARY KEY,
  business_plan_id    BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE,
  label               TEXT NOT NULL,
  category            TEXT CHECK (category IN ('ACTIVE','PASSIVE','SAVINGS')) DEFAULT 'ACTIVE',
  current_value       NUMERIC(12,2) DEFAULT 0,
  target_value        NUMERIC(12,2) DEFAULT 0,
  notes               TEXT,
  sort_order          INT DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wealth_goals_plan ON wealth_goals(business_plan_id);

-- 8. org_models ─ hire planning + roles
CREATE TABLE IF NOT EXISTS org_models (
  id                            BIGSERIAL PRIMARY KEY,
  business_plan_id              BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE UNIQUE,
  seller_specialist_cost_pct    NUMERIC(5,4) DEFAULT 0.3000,
  buyer_specialist_cost_pct     NUMERIC(5,4) DEFAULT 0.5000,
  admin_salary_pct              NUMERIC(5,4) DEFAULT 0.1100,
  admin_hourly_rate             NUMERIC(8,2) DEFAULT 25.00,
  roles                         JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{role, salary, status, hire_by}]
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_org_models_plan ON org_models(business_plan_id);

-- 9. GPS (1-3-5)
CREATE TABLE IF NOT EXISTS gps_goals (
  id                  BIGSERIAL PRIMARY KEY,
  business_plan_id    BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE UNIQUE,
  goal_text           TEXT,
  target_number       NUMERIC(14,2),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gps_priorities (
  id                  BIGSERIAL PRIMARY KEY,
  gps_goal_id         BIGINT NOT NULL REFERENCES gps_goals(id) ON DELETE CASCADE,
  priority_text       TEXT,
  target_number       NUMERIC(14,2),
  sort_order          INT DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gps_priorities_goal ON gps_priorities(gps_goal_id);

CREATE TABLE IF NOT EXISTS gps_strategies (
  id                  BIGSERIAL PRIMARY KEY,
  gps_priority_id     BIGINT NOT NULL REFERENCES gps_priorities(id) ON DELETE CASCADE,
  strategy_text       TEXT,
  target_number       NUMERIC(14,2),
  source_or_method    TEXT,
  sort_order          INT DEFAULT 0,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_gps_strategies_priority ON gps_strategies(gps_priority_id);

-- 10. 4-1-1 ─ annual / monthly / weekly cascade
-- One row per (plan, period_type, period_key, column).
-- period_type: ANNUAL | MONTHLY | WEEKLY
-- period_key:  YYYY for annual, YYYY-MM for monthly, YYYY-Www for weekly
-- column:      JOB | BUSINESS | PERSONAL_FINANCIAL | PERSONAL
CREATE TABLE IF NOT EXISTS four_one_ones (
  id                  BIGSERIAL PRIMARY KEY,
  business_plan_id    BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE,
  period_type         TEXT NOT NULL CHECK (period_type IN ('ANNUAL','MONTHLY','WEEKLY')),
  period_key          TEXT NOT NULL,
  column_key          TEXT NOT NULL CHECK (column_key IN ('JOB','BUSINESS','PERSONAL_FINANCIAL','PERSONAL')),
  items               JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{text, target_number, completed}]
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (business_plan_id, period_type, period_key, column_key)
);
CREATE INDEX IF NOT EXISTS idx_four_one_ones_plan ON four_one_ones(business_plan_id);
CREATE INDEX IF NOT EXISTS idx_four_one_ones_period ON four_one_ones(period_type, period_key);

-- 11. Perfect Week
CREATE TABLE IF NOT EXISTS perfect_weeks (
  id                  BIGSERIAL PRIMARY KEY,
  coaching_client_id  BIGINT NOT NULL REFERENCES coaching_clients(id) ON DELETE CASCADE UNIQUE,
  -- 7 days × 4 slots; structure: { "MON": { "BEFORE_8": "...", "MORNING": "...", ... }, ... }
  schedule            JSONB NOT NULL DEFAULT '{}'::jsonb,
  template_name       TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 12. Pipeline entries (listing + buyer)
CREATE TABLE IF NOT EXISTS pipeline_entries (
  id                  BIGSERIAL PRIMARY KEY,
  workspace_id        BIGINT NOT NULL REFERENCES workspaces(id) DEFAULT 1,
  coaching_client_id  BIGINT NOT NULL REFERENCES coaching_clients(id) ON DELETE CASCADE,
  entry_type          TEXT NOT NULL CHECK (entry_type IN ('LISTING','BUYER')),
  appointment_date    DATE,
  address             TEXT,
  contact_name        TEXT,
  contact_phone       TEXT,
  contact_email       TEXT,
  next_step           TEXT,
  notes               TEXT,
  rating              INT CHECK (rating BETWEEN 1 AND 10),
  closed              BOOLEAN DEFAULT false,
  closed_date         DATE,
  closing_price       NUMERIC(12,2),
  gross_commission    NUMERIC(12,2),
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pipeline_entries_client ON pipeline_entries(coaching_client_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_entries_type   ON pipeline_entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_pipeline_entries_rating ON pipeline_entries(rating);

-- 13. Contact touches (database touch tracking)
CREATE TABLE IF NOT EXISTS contact_touches (
  id                  BIGSERIAL PRIMARY KEY,
  coaching_client_id  BIGINT NOT NULL REFERENCES coaching_clients(id) ON DELETE CASCADE,
  person_name         TEXT NOT NULL,
  person_email        TEXT,
  person_phone        TEXT,
  contact_type        TEXT CHECK (contact_type IN ('MET','HAVENT_MET')) DEFAULT 'MET',
  touch_date          DATE NOT NULL DEFAULT CURRENT_DATE,
  touch_method        TEXT CHECK (touch_method IN ('CALL','TEXT','EMAIL','EVENT','MAIL','SOCIAL','IN_PERSON','OTHER')),
  notes               TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_contact_touches_client ON contact_touches(coaching_client_id);
CREATE INDEX IF NOT EXISTS idx_contact_touches_date   ON contact_touches(touch_date);

-- 14. Activity logs (daily entry by agent)
CREATE TABLE IF NOT EXISTS coaching_activity_logs (
  id                    BIGSERIAL PRIMARY KEY,
  coaching_client_id    BIGINT NOT NULL REFERENCES coaching_clients(id) ON DELETE CASCADE,
  log_date              DATE NOT NULL DEFAULT CURRENT_DATE,
  contacts_made         INT DEFAULT 0,
  appts_set             INT DEFAULT 0,
  appts_held            INT DEFAULT 0,
  hours_prospected      NUMERIC(4,1) DEFAULT 0,
  wins                  TEXT,
  notes                 TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (coaching_client_id, log_date)
);
CREATE INDEX IF NOT EXISTS idx_coaching_activity_client ON coaching_activity_logs(coaching_client_id);
CREATE INDEX IF NOT EXISTS idx_coaching_activity_date   ON coaching_activity_logs(log_date);

-- 15. Coaching calls
CREATE TABLE IF NOT EXISTS coaching_calls (
  id                    BIGSERIAL PRIMARY KEY,
  workspace_id          BIGINT NOT NULL REFERENCES workspaces(id) DEFAULT 1,
  coaching_client_id    BIGINT NOT NULL REFERENCES coaching_clients(id) ON DELETE CASCADE,
  scheduled_at          TIMESTAMPTZ,
  call_type             TEXT CHECK (call_type IN ('WEEKLY','BIWEEKLY','MONTHLY','MONTHLY_REVIEW','QUARTERLY','SEMI_ANNUAL','ANNUAL','ADHOC')),
  status                TEXT CHECK (status IN ('SCHEDULED','COMPLETED','MISSED','RESCHEDULED','CANCELLED')) DEFAULT 'SCHEDULED',
  pre_call_brief        JSONB,                 -- snapshot of metrics at scheduled time
  in_call_notes         TEXT,                  -- markdown
  prior_call_id         BIGINT REFERENCES coaching_calls(id) ON DELETE SET NULL,
  commitment_keep_score NUMERIC(5,2),          -- % of last call action items completed
  completed_at          TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_coaching_calls_client    ON coaching_calls(coaching_client_id);
CREATE INDEX IF NOT EXISTS idx_coaching_calls_scheduled ON coaching_calls(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_coaching_calls_status    ON coaching_calls(status);

-- 16. Action items (tied to calls or standalone)
CREATE TABLE IF NOT EXISTS coaching_action_items (
  id                    BIGSERIAL PRIMARY KEY,
  workspace_id          BIGINT NOT NULL REFERENCES workspaces(id) DEFAULT 1,
  coaching_client_id    BIGINT NOT NULL REFERENCES coaching_clients(id) ON DELETE CASCADE,
  source_call_id        BIGINT REFERENCES coaching_calls(id) ON DELETE SET NULL,
  text                  TEXT NOT NULL,
  measurement           TEXT,                  -- e.g. "150 contacts"
  due_date              DATE,
  owner                 TEXT CHECK (owner IN ('AGENT','COACH')) DEFAULT 'AGENT',
  tag                   TEXT CHECK (tag IN ('LEAD_GEN','PIPELINE','DATABASE','MINDSET','HIRE','RECRUITING','PERSONAL','BUSINESS','OTHER')),
  status                TEXT CHECK (status IN ('OPEN','COMPLETED','MISSED')) DEFAULT 'OPEN',
  completed_at          TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_coaching_action_items_client ON coaching_action_items(coaching_client_id);
CREATE INDEX IF NOT EXISTS idx_coaching_action_items_call   ON coaching_action_items(source_call_id);
CREATE INDEX IF NOT EXISTS idx_coaching_action_items_status ON coaching_action_items(status);

-- 17. Review snapshots (quarterly / semi-annual / annual checkpoints)
CREATE TABLE IF NOT EXISTS review_snapshots (
  id                    BIGSERIAL PRIMARY KEY,
  workspace_id          BIGINT NOT NULL REFERENCES workspaces(id) DEFAULT 1,
  coaching_client_id    BIGINT NOT NULL REFERENCES coaching_clients(id) ON DELETE CASCADE,
  review_type           TEXT NOT NULL CHECK (review_type IN ('QUARTERLY','SEMI_ANNUAL','ANNUAL')),
  review_date           DATE NOT NULL DEFAULT CURRENT_DATE,
  captured_data         JSONB NOT NULL,        -- full BP snapshot
  reflections           TEXT,
  focus_areas_next      TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_review_snapshots_client ON review_snapshots(coaching_client_id);
CREATE INDEX IF NOT EXISTS idx_review_snapshots_type   ON review_snapshots(review_type);

-- 18. Recruits (LPT HybridShare downline tracking)
CREATE TABLE IF NOT EXISTS coaching_recruits (
  id                    BIGSERIAL PRIMARY KEY,
  workspace_id          BIGINT NOT NULL REFERENCES workspaces(id) DEFAULT 1,
  coaching_client_id    BIGINT NOT NULL REFERENCES coaching_clients(id) ON DELETE CASCADE,
  recruit_name          TEXT NOT NULL,
  recruit_email         TEXT,
  recruit_phone         TEXT,
  status                TEXT CHECK (status IN ('HITLIST','WORKING_HOT','IN_PROCESS','SIGNED','UNQUALIFIED','CHURNED')) DEFAULT 'HITLIST',
  tier                  INT CHECK (tier BETWEEN 1 AND 7),
  sponsor_recruit_id    BIGINT REFERENCES coaching_recruits(id) ON DELETE SET NULL,
  co_sponsor_recruit_id BIGINT REFERENCES coaching_recruits(id) ON DELETE SET NULL,
  join_date             DATE,
  comp_plan             TEXT CHECK (comp_plan IN ('BUSINESS_BUILDER','BROKERAGE_PARTNER')),
  current_ytd_core_txns INT DEFAULT 0,
  last_contact_date     DATE,
  source                TEXT,
  notes                 TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_coaching_recruits_client ON coaching_recruits(coaching_client_id);
CREATE INDEX IF NOT EXISTS idx_coaching_recruits_status ON coaching_recruits(status);
CREATE INDEX IF NOT EXISTS idx_coaching_recruits_tier   ON coaching_recruits(tier);

-- 19. Recruiting plans (annual recruit targets + projected HybridShare)
CREATE TABLE IF NOT EXISTS recruiting_plans (
  id                            BIGSERIAL PRIMARY KEY,
  business_plan_id              BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE UNIQUE,
  annual_recruit_goal           INT DEFAULT 0,
  conversation_to_recruit_ratio INT DEFAULT 25,
  pct_brokerage_partner         NUMERIC(5,4) DEFAULT 0.5000,
  expected_recruits_per_recruit NUMERIC(4,2) DEFAULT 1.50,
  cap_hit_rate                  NUMERIC(5,4) DEFAULT 0.3000,
  notes                         TEXT,
  created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ════════════════════════════════════════════════════════════
-- RLS — service role full access on every coaching table
-- ════════════════════════════════════════════════════════════
DO $$
DECLARE
  t TEXT;
  coaching_tables TEXT[] := ARRAY[
    'coaching_clients','business_plans','budget_models','economic_models',
    'lead_gen_models','lead_sources','wealth_goals','org_models',
    'gps_goals','gps_priorities','gps_strategies','four_one_ones',
    'perfect_weeks','pipeline_entries','contact_touches','coaching_activity_logs',
    'coaching_calls','coaching_action_items','review_snapshots',
    'coaching_recruits','recruiting_plans'
  ];
BEGIN
  FOREACH t IN ARRAY coaching_tables LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename=t AND policyname='Service role full access') THEN
      EXECUTE format('CREATE POLICY "Service role full access" ON %I FOR ALL USING (true) WITH CHECK (true)', t);
    END IF;
  END LOOP;
END $$;

-- ════════════════════════════════════════════════════════════
-- updated_at triggers
-- ════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION coaching_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
  t TEXT;
  coaching_tables TEXT[] := ARRAY[
    'coaching_clients','business_plans','budget_models','economic_models',
    'lead_gen_models','lead_sources','wealth_goals','org_models',
    'gps_goals','gps_priorities','gps_strategies','four_one_ones',
    'perfect_weeks','pipeline_entries','coaching_activity_logs',
    'coaching_calls','coaching_action_items','coaching_recruits','recruiting_plans'
  ];
BEGIN
  FOREACH t IN ARRAY coaching_tables LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_updated_at ON %I', t, t);
    EXECUTE format('CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION coaching_set_updated_at()', t, t);
  END LOOP;
END $$;
