-- ════════════════════════════════════════════════════════════
-- Phase 15.5 — CTE-style Detailed Goal-Setting Form
--
-- Adds the fields the legacy CTE Business Plan tab actually captured:
--   - "Big Why" (vision statement)
--   - Team or individual flag
--   - Listing vs buyer income mix
--   - Separate listing vs buyer commission rates (already have separate sale prices)
--   - Royalty % + split cap on the budget model
--   - Per-category activity goals (dials/contacts/nurtures/appts/etc) — new table
--   - Recruiting / rev share goals on the existing recruiting_plans table
-- ════════════════════════════════════════════════════════════

-- 1. coaching_clients additions
ALTER TABLE coaching_clients ADD COLUMN IF NOT EXISTS big_why            TEXT;
ALTER TABLE coaching_clients ADD COLUMN IF NOT EXISTS team_or_individual TEXT CHECK (team_or_individual IN ('INDIVIDUAL','TEAM'));
ALTER TABLE coaching_clients ADD COLUMN IF NOT EXISTS team_name          TEXT;

-- 2. economic_models — separate commission rate for listings vs buyers
-- (sale prices already separate; we keep `commission_rate` as the legacy aggregate
-- and add explicit listing/buyer rates that supersede it when set)
ALTER TABLE economic_models ADD COLUMN IF NOT EXISTS commission_rate_listing NUMERIC(6,5);
ALTER TABLE economic_models ADD COLUMN IF NOT EXISTS commission_rate_buyer   NUMERIC(6,5);

-- 3. budget_models — royalty + split cap (CTE Business Plan top-right block)
ALTER TABLE budget_models ADD COLUMN IF NOT EXISTS royalty_pct  NUMERIC(5,4) DEFAULT 0;       -- e.g. 0.06 = 6%
ALTER TABLE budget_models ADD COLUMN IF NOT EXISTS royalty_cap  NUMERIC(12,2) DEFAULT 0;
ALTER TABLE budget_models ADD COLUMN IF NOT EXISTS split_cap    NUMERIC(12,2) DEFAULT 0;       -- LPT cap lives in paid_to_brokerage; this is a generic split-cap fallback

-- 4. activity_goals — per-category targets (CTE Lead Gen tab)
-- One row per business_plan with all goals; daily/weekly/monthly inferred where needed.
CREATE TABLE IF NOT EXISTS activity_goals (
  id                          BIGSERIAL PRIMARY KEY,
  business_plan_id            BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE UNIQUE,
  -- Daily targets
  dials_daily                 INT DEFAULT 0,
  contacts_daily              INT DEFAULT 0,
  nurtures_daily              INT DEFAULT 0,
  hours_prospecting_daily     NUMERIC(4,1) DEFAULT 0,
  -- Weekly targets
  listing_appts_set_weekly    INT DEFAULT 0,
  listing_appts_held_weekly   INT DEFAULT 0,
  buyer_appts_set_weekly      INT DEFAULT 0,
  buyer_appts_held_weekly     INT DEFAULT 0,
  showings_weekly             INT DEFAULT 0,
  open_houses_weekly          INT DEFAULT 0,
  -- Monthly targets (auto-derived from annual ÷ 12 by default but overridable)
  listings_signed_monthly     INT DEFAULT 0,
  buyers_signed_monthly       INT DEFAULT 0,
  -- Conversion benchmarks (the agent's targets, separate from MREA defaults)
  contact_to_appt_pct_target  NUMERIC(5,4) DEFAULT 0,
  set_to_held_pct_target      NUMERIC(5,4) DEFAULT 0,
  notes                       TEXT,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_activity_goals_plan ON activity_goals(business_plan_id);

ALTER TABLE activity_goals ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='activity_goals' AND policyname='Service role full access') THEN
    CREATE POLICY "Service role full access" ON activity_goals FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;

DROP TRIGGER IF EXISTS trg_activity_goals_updated_at ON activity_goals;
CREATE TRIGGER trg_activity_goals_updated_at BEFORE UPDATE ON activity_goals
  FOR EACH ROW EXECUTE FUNCTION coaching_set_updated_at();

-- 5. coaching_activity_logs — richer daily entry fields
-- Existing columns: contacts_made, appts_set, appts_held, hours_prospected, wins, notes
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS dials                INT DEFAULT 0;
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS nurtures             INT DEFAULT 0;
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS listing_appts_set    INT DEFAULT 0;
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS listing_appts_held   INT DEFAULT 0;
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS listings_signed      INT DEFAULT 0;
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS buyer_appts_set      INT DEFAULT 0;
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS buyer_appts_held     INT DEFAULT 0;
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS buyers_signed        INT DEFAULT 0;
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS showings             INT DEFAULT 0;
ALTER TABLE coaching_activity_logs ADD COLUMN IF NOT EXISTS open_houses_held     INT DEFAULT 0;
