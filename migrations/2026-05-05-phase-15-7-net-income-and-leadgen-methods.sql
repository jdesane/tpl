-- ════════════════════════════════════════════════════════════
-- Phase 15.7 — Net-income-driven goal flow + LPT-only onboarding
--
-- The original wizard asked for GCI directly. CTE / MREA actually drives
-- from the net-income-before-taxes goal — GCI is derived. Adds the
-- net_income_goal column and a lead_gen_methods array so the new
-- Step 5 can capture how the agent prospects.
-- ════════════════════════════════════════════════════════════

ALTER TABLE business_plans ADD COLUMN IF NOT EXISTS net_income_goal NUMERIC(12,2);
ALTER TABLE business_plans ADD COLUMN IF NOT EXISTS lead_gen_methods JSONB NOT NULL DEFAULT '[]'::jsonb;
