-- ════════════════════════════════════════════════════════════
-- Phase 15.6d — Monthly Financial Statement (CTE Financial Statement tab)
--
-- One row per (business_plan, month). Income / cost-of-sales / opex
-- as JSONB so agents can add custom lines without migrations.
-- Actuals auto-populate from closed pipeline_entries on read.
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS monthly_financials (
  id                 BIGSERIAL PRIMARY KEY,
  business_plan_id   BIGINT NOT NULL REFERENCES business_plans(id) ON DELETE CASCADE,
  month              INT NOT NULL CHECK (month BETWEEN 1 AND 12),
  -- Each is a JSONB object: { "Line Label": numeric_amount }
  income             JSONB NOT NULL DEFAULT '{}'::jsonb,
  cost_of_sales      JSONB NOT NULL DEFAULT '{}'::jsonb,
  operating_expenses JSONB NOT NULL DEFAULT '{}'::jsonb,
  notes              TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (business_plan_id, month)
);
CREATE INDEX IF NOT EXISTS idx_monthly_financials_plan ON monthly_financials(business_plan_id);

ALTER TABLE monthly_financials ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='monthly_financials' AND policyname='Service role full access') THEN
    CREATE POLICY "Service role full access" ON monthly_financials FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;

DROP TRIGGER IF EXISTS trg_monthly_financials_updated_at ON monthly_financials;
CREATE TRIGGER trg_monthly_financials_updated_at BEFORE UPDATE ON monthly_financials
  FOR EACH ROW EXECUTE FUNCTION coaching_set_updated_at();
