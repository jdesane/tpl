-- Fee profiles become AGENT-OWNED. We supply arithmetic, not rates.
--
-- WHY THIS CHANGED
--   The first cut seeded a Florida profile with real rates and shipped it as the
--   system default. That made us the authority on what title insurance and doc
--   stamps cost - in every state the product is sold into. Three problems:
--
--     1. Liability. A net sheet is the document a seller uses to decide whether to
--        accept an offer. If our table is wrong or stale, we produced that error.
--     2. Maintenance. Promulgated schedules get amended. Shipping rates means
--        owning updates in perpetuity, for 50 states, forever.
--     3. Accuracy. Settlement fees, lien searches and abstract fees are set by the
--        agent's OWN title company and vary between them. We would be guessing at
--        numbers the agent can read straight off their last closing statement.
--
--   So: the agent enters their numbers, confirms them, and owns them. We do the
--   arithmetic and show our work.
--
-- WHAT CHANGES
--   * fee_profiles gains is_template / confirmed_at / confirmed_by_user_id.
--   * The seeded Florida row is demoted from "system default" to "starter template".
--     A template is inert: it is never selected automatically and cannot be used for
--     a seller-facing document. An agent copies it into their own workspace profile,
--     reviews every line against their closing statement, and confirms it.
--   * Nothing computes seller-facing output from an unconfirmed profile. The engine
--     returns a blocking warning instead, so a half-configured account cannot hand a
--     seller a number nobody checked.

ALTER TABLE fee_profiles ADD COLUMN IF NOT EXISTS is_template BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE fee_profiles ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;
ALTER TABLE fee_profiles ADD COLUMN IF NOT EXISTS confirmed_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE fee_profiles ADD COLUMN IF NOT EXISTS copied_from_id BIGINT REFERENCES fee_profiles(id) ON DELETE SET NULL;

-- Where the agent got each number, so a later reviewer can retrace it.
-- e.g. {"settlement_fee": "Sunbelt Title quote 8/2026", "doc_stamps": "FL Ch. 201"}
ALTER TABLE fee_profiles ADD COLUMN IF NOT EXISTS source_by_field JSONB NOT NULL DEFAULT '{}'::jsonb;

-- A template belongs to no workspace and is never a default.
UPDATE fee_profiles
SET is_template = TRUE,
    is_default  = FALSE,
    name        = 'Florida starter template (review before use)',
    source_note = 'STARTER TEMPLATE - NOT VERIFIED AND NOT USABLE AS-IS. '
                  'Structure only. Copy into your workspace, replace every number with '
                  'your own title company quote or your last settlement statement, then '
                  'confirm. Seller-facing output is blocked until a profile is confirmed.'
WHERE workspace_id IS NULL AND state = 'FL';

-- The old partial unique index enforced "one system default per state", which no
-- longer describes anything: system rows are templates now and are never defaults.
DROP INDEX IF EXISTS idx_fee_profiles_system_default;

-- One default per workspace per state instead.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fee_profiles_ws_default
    ON fee_profiles (workspace_id, state)
    WHERE is_default AND NOT is_template;

-- A template must not belong to a workspace, and must never be marked default.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fee_profile_template_is_unowned') THEN
    ALTER TABLE fee_profiles ADD CONSTRAINT fee_profile_template_is_unowned
      CHECK (NOT is_template OR (workspace_id IS NULL AND is_default = FALSE));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fee_profiles_templates ON fee_profiles (state)
    WHERE is_template;
