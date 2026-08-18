-- Phase 23: Entitlement Layer (two brands, one backend)
--
-- One backend + one database serving two customer-facing brands:
--   • TPL Collective  (portal.tplcollective.ai) — team members, arrive via recruiting
--   • RETechbox       (retechbox.com)           — any agent, any brokerage, paid software
--
-- Access to any tool is a single workspace_entitlements row, regardless of which door
-- the customer came through. Plans (basic/mid/elite) remain for legacy CRM gating;
-- entitlements are the source of truth for TOOL access.
--
-- COMPLIANCE NOTE (read before editing):
--   LPT prohibits offering items of value in exchange for being named sponsor.
--   Team benefits are permitted. This schema enforces the distinction:
--     1. No `source` value references sponsorship or recruiting.
--     2. source='team_member' REQUIRES a team_agreement_id (CHECK constraint below).
--     3. Sponsorship status may live on the CRM contact but must NEVER be read by
--        an entitlement check. Do not add such a column here, and do not join one in.
--   Every team_member grant records the agreement id in entitlement_events, so the
--   audit trail shows team membership as the trigger.
--
-- Tables: products, bundles, bundle_products, team_agreements,
--         workspace_entitlements, entitlement_events
--
-- Adds to workspaces: account_type, brand, lead_id
--
-- Conventions match Phase 22 (cma): workspace_id INTEGER NOT NULL DEFAULT 1 with no FK,
-- RLS on with a service_role policy, set_updated_at() trigger.


-- ════════════════════════════════════════════════════════════════════
-- 1. products — the registry. Tools are data, not code.
--    Adding a new tool = INSERT here + build it. The entitlement engine
--    never changes.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS products (
    id                      BIGSERIAL PRIMARY KEY,
    slug                    TEXT NOT NULL UNIQUE,
    name                    TEXT NOT NULL,
    tagline                 TEXT,
    description             TEXT,
    category                TEXT,                      -- listing | pricing | recruiting | coaching

    -- Pricing. NULL until Joe sets them; a NULL price means "not self-serve purchasable".
    monthly_price_cents     INTEGER,
    annual_price_cents      INTEGER,
    stripe_product_id       TEXT,
    stripe_monthly_price_id TEXT,
    stripe_annual_price_id  TEXT,

    is_sellable             BOOLEAN NOT NULL DEFAULT TRUE,   -- outsiders may buy standalone
    is_public               BOOLEAN NOT NULL DEFAULT TRUE,   -- listed on the RETechbox site

    -- Caps applied when an entitlement is tier='free'. Enforced at the API by
    -- entitlements.check_limit(), never in the UI alone.
    free_tier_limits        JSONB NOT NULL DEFAULT '{}'::jsonb,

    icon                    TEXT,
    sort_order              INTEGER NOT NULL DEFAULT 0,
    status                  TEXT NOT NULL DEFAULT 'active',  -- active | beta | retired

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_public ON products (is_public, sort_order)
    WHERE status = 'active';

ALTER TABLE products ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON products;
CREATE POLICY service_role_all ON products FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS products_updated_at ON products;
CREATE TRIGGER products_updated_at
BEFORE UPDATE ON products
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 2. bundles — presets that grant several products at once.
--    Convenience for granting + Stripe checkout. NOT read at access-check
--    time; buying a bundle writes one entitlement row per product.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS bundles (
    id                      BIGSERIAL PRIMARY KEY,
    slug                    TEXT NOT NULL UNIQUE,
    name                    TEXT NOT NULL,
    description             TEXT,
    monthly_price_cents     INTEGER,
    annual_price_cents      INTEGER,
    stripe_product_id       TEXT,
    stripe_monthly_price_id TEXT,
    stripe_annual_price_id  TEXT,
    is_public               BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order              INTEGER NOT NULL DEFAULT 0,
    status                  TEXT NOT NULL DEFAULT 'active',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bundle_products (
    bundle_id  BIGINT NOT NULL REFERENCES bundles(id)  ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    PRIMARY KEY (bundle_id, product_id)
);

ALTER TABLE bundles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE bundle_products ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON bundles;
CREATE POLICY service_role_all ON bundles FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS service_role_all ON bundle_products;
CREATE POLICY service_role_all ON bundle_products FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS bundles_updated_at ON bundles;
CREATE TRIGGER bundles_updated_at
BEFORE UPDATE ON bundles
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 3. team_agreements — the substantive relationship a team benefit rests on.
--    `obligations` documents what the member commits to (onboarding completion,
--    training cadence, team standards, systems usage). Populate from the real
--    signed agreement text — this is the substance, not a formality.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS team_agreements (
    id                 BIGSERIAL PRIMARY KEY,
    workspace_id       INTEGER NOT NULL DEFAULT 1,
    lead_id            BIGINT REFERENCES leads(id) ON DELETE SET NULL,
    user_id            BIGINT REFERENCES users(id) ON DELETE SET NULL,

    agreement_version  TEXT NOT NULL,
    signed_at          TIMESTAMPTZ NOT NULL,
    signed_name        TEXT,
    signed_ip          TEXT,
    document_url       TEXT,
    obligations        JSONB NOT NULL DEFAULT '{}'::jsonb,

    status             TEXT NOT NULL DEFAULT 'active',   -- active | terminated
    terminated_at      TIMESTAMPTZ,
    terminated_reason  TEXT,
    notes              TEXT,

    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT team_agreement_status_valid CHECK (status IN ('active','terminated'))
);

CREATE INDEX IF NOT EXISTS idx_team_agreements_ws     ON team_agreements (workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_team_agreements_lead   ON team_agreements (lead_id);

ALTER TABLE team_agreements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON team_agreements;
CREATE POLICY service_role_all ON team_agreements FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS team_agreements_updated_at ON team_agreements;
CREATE TRIGGER team_agreements_updated_at
BEFORE UPDATE ON team_agreements
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 4. workspace_entitlements — THE TOGGLE. One row per (workspace, product).
--    Never DELETE a row: revoke by setting status='revoked' + revoked_at.
--    The history is the point.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS workspace_entitlements (
    id                          BIGSERIAL PRIMARY KEY,
    workspace_id                INTEGER NOT NULL DEFAULT 1,
    product_id                  BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,

    status                      TEXT NOT NULL DEFAULT 'active',
        -- active | trialing | past_due | revoked | expired
    source                      TEXT NOT NULL,
        -- purchased | trial | team_member | comp | internal
    tier                        TEXT NOT NULL DEFAULT 'pro',   -- free | pro

    -- Required when source='team_member'. See COMPLIANCE NOTE at top of file.
    team_agreement_id           BIGINT REFERENCES team_agreements(id) ON DELETE RESTRICT,

    granted_by_user_id          BIGINT REFERENCES users(id) ON DELETE SET NULL,
    granted_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    starts_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at                  TIMESTAMPTZ,
    revoked_at                  TIMESTAMPTZ,
    revoke_reason               TEXT,

    stripe_subscription_id      TEXT,
    stripe_subscription_item_id TEXT,

    -- Per-workspace overrides of products.free_tier_limits
    limits                      JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes                       TEXT,

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (workspace_id, product_id),

    CONSTRAINT entitlement_status_valid
        CHECK (status IN ('active','trialing','past_due','revoked','expired')),
    CONSTRAINT entitlement_source_valid
        CHECK (source IN ('purchased','trial','team_member','comp','internal')),
    CONSTRAINT entitlement_tier_valid
        CHECK (tier IN ('free','pro')),

    -- COMPLIANCE GUARDRAIL: a team grant cannot exist without a signed agreement.
    -- Enforced here rather than in application code on purpose.
    CONSTRAINT team_member_requires_agreement
        CHECK (source <> 'team_member' OR team_agreement_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_entitlements_workspace ON workspace_entitlements (workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_entitlements_product   ON workspace_entitlements (product_id, status);
CREATE INDEX IF NOT EXISTS idx_entitlements_stripe    ON workspace_entitlements (stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_entitlements_expiring  ON workspace_entitlements (expires_at)
    WHERE expires_at IS NOT NULL AND status IN ('active','trialing');

ALTER TABLE workspace_entitlements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON workspace_entitlements;
CREATE POLICY service_role_all ON workspace_entitlements FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS workspace_entitlements_updated_at ON workspace_entitlements;
CREATE TRIGGER workspace_entitlements_updated_at
BEFORE UPDATE ON workspace_entitlements
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 5. entitlement_events — append-only audit trail.
--    Answers "I paid for this and it turned off."
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS entitlement_events (
    id              BIGSERIAL PRIMARY KEY,
    workspace_id    INTEGER NOT NULL DEFAULT 1,
    product_id      BIGINT REFERENCES products(id) ON DELETE SET NULL,
    entitlement_id  BIGINT REFERENCES workspace_entitlements(id) ON DELETE SET NULL,

    action          TEXT NOT NULL,
        -- granted | revoked | upgraded | downgraded | expired | renewed
        -- | payment_failed | trial_started | trial_converted | limit_changed
    actor_user_id   BIGINT REFERENCES users(id) ON DELETE SET NULL,
    actor_type      TEXT NOT NULL DEFAULT 'admin',   -- admin | system | stripe | self

    from_status     TEXT,
    to_status       TEXT,
    from_source     TEXT,
    to_source       TEXT,
    reason          TEXT,
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ent_events_workspace ON entitlement_events (workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ent_events_product   ON entitlement_events (product_id, created_at DESC);

ALTER TABLE entitlement_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON entitlement_events;
CREATE POLICY service_role_all ON entitlement_events FOR ALL TO service_role USING (true) WITH CHECK (true);


-- ════════════════════════════════════════════════════════════════════
-- 6. workspaces additions
--    account_type — how this workspace relates to the business
--    brand        — which door they signed up through (theming, email templates)
--    lead_id      — every account is also a CRM contact
-- ════════════════════════════════════════════════════════════════════

ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS account_type TEXT NOT NULL DEFAULT 'customer';
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS brand        TEXT NOT NULL DEFAULT 'tools';
ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS lead_id      BIGINT REFERENCES leads(id) ON DELETE SET NULL;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'workspaces_account_type_valid') THEN
    ALTER TABLE workspaces ADD CONSTRAINT workspaces_account_type_valid
      CHECK (account_type IN ('team','customer','internal'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'workspaces_brand_valid') THEN
    ALTER TABLE workspaces ADD CONSTRAINT workspaces_brand_valid
      CHECK (brand IN ('tpl','tools'));
  END IF;
END $$;

-- Joe's workspace is internal, TPL-branded.
UPDATE workspaces SET account_type = 'internal', brand = 'tpl' WHERE id = 1;

-- Coaching-client portal workspaces live on portal.tplcollective.ai, so they are
-- TPL-branded, not RETechbox customers. brand drives theming and email templates.
UPDATE workspaces SET brand = 'tpl' WHERE (settings->>'coaching_only') = 'true';


-- ════════════════════════════════════════════════════════════════════
-- 7. Seed the product registry.
--    Prices intentionally NULL — set once pricing is decided. A NULL price
--    means the product cannot be self-serve purchased yet; admin grants still work.
-- ════════════════════════════════════════════════════════════════════

INSERT INTO products (slug, name, tagline, category, free_tier_limits, icon, sort_order, status, is_sellable, is_public)
VALUES
-- Icons are stored as literal emoji, not HTML entities, so they render whether the
-- frontend uses textContent or innerHTML.
  ('listing-dashboard', 'Listing Dashboard',
   'Every listing from intake to closing in one place.',
   'listing',  '{"active_listings": 1}'::jsonb,        '🏠', 10, 'active', TRUE, TRUE),

  ('net-sheet', 'Seller Net Sheet',
   'Branded net sheets and offer comparisons in under a minute.',
   'pricing',  '{"net_sheets_per_month": 3}'::jsonb,   '💰', 20, 'active', TRUE, TRUE),

  ('cma-builder', 'CMA Builder',
   'Import your MLS export, get a shareable CMA report.',
   'pricing',  '{"cmas_per_month": 1}'::jsonb,         '📈', 30, 'active', TRUE, TRUE),

  ('comparator', 'Brokerage Comparator',
   'Compare real brokerage economics side by side.',
   'recruiting', '{}'::jsonb,                          '⚖️',  40, 'active', TRUE, TRUE),

  ('coaching', 'Coaching Platform',
   'Business plan, goal cascade, and accountability in one system.',
   'coaching', '{}'::jsonb,                            '🎯', 50, 'active', TRUE, FALSE)
ON CONFLICT (slug) DO NOTHING;


-- Full-suite bundle. Price TBD.
INSERT INTO bundles (slug, name, description, is_public, sort_order)
VALUES ('retechbox-suite', 'RETechbox Suite', 'Every tool, one price.', TRUE, 10)
ON CONFLICT (slug) DO NOTHING;

INSERT INTO bundle_products (bundle_id, product_id)
SELECT b.id, p.id
FROM bundles b
CROSS JOIN products p
WHERE b.slug = 'retechbox-suite'
  AND p.slug IN ('listing-dashboard', 'net-sheet', 'cma-builder', 'comparator', 'coaching')
ON CONFLICT DO NOTHING;


-- ════════════════════════════════════════════════════════════════════
-- 8. Backfill existing workspaces.
--    A migration must never take access away from a current user. Workspace 1
--    gets everything as 'internal'. Every other existing workspace gets the
--    already-live tools as 'comp' so nothing breaks today; trim deliberately
--    from the admin UI later.
-- ════════════════════════════════════════════════════════════════════

-- Workspace 1 (TPL Collective / Joe): all products, internal.
INSERT INTO workspace_entitlements (workspace_id, product_id, status, source, tier, notes)
SELECT 1, p.id, 'active', 'internal', 'pro', 'Phase 23 backfill'
FROM products p
ON CONFLICT (workspace_id, product_id) DO NOTHING;

-- Coaching-client portal workspaces (settings.coaching_only = true): coaching only.
-- These accounts exist solely to log into portal.tplcollective.ai for coaching; granting
-- them tools they never had and cannot reach would just be noise in the admin grid.
INSERT INTO workspace_entitlements (workspace_id, product_id, status, source, tier, notes)
SELECT w.id, p.id, 'active', 'comp', 'pro', 'Phase 23 backfill - preserved prior access'
FROM workspaces w
CROSS JOIN products p
WHERE w.id <> 1
  AND (w.settings->>'coaching_only') = 'true'
  AND p.slug = 'coaching'
ON CONFLICT (workspace_id, product_id) DO NOTHING;

-- Any other workspace: keep everything that was reachable before gating existed.
INSERT INTO workspace_entitlements (workspace_id, product_id, status, source, tier, notes)
SELECT w.id, p.id, 'active', 'comp', 'pro', 'Phase 23 backfill - preserved prior access'
FROM workspaces w
CROSS JOIN products p
WHERE w.id <> 1
  AND COALESCE(w.settings->>'coaching_only', 'false') <> 'true'
  AND p.slug IN ('cma-builder', 'comparator', 'coaching')
ON CONFLICT (workspace_id, product_id) DO NOTHING;

-- Record the backfill in the audit trail.
-- NOT EXISTS guard keeps this idempotent: the entitlement rows survive a re-run,
-- so without it a second run would append duplicate audit events.
INSERT INTO entitlement_events (workspace_id, product_id, entitlement_id, action, actor_type, to_status, to_source, reason)
SELECT e.workspace_id, e.product_id, e.id, 'granted', 'system', e.status, e.source, 'Phase 23 migration backfill'
FROM workspace_entitlements e
WHERE e.notes LIKE 'Phase 23 backfill%'
  AND NOT EXISTS (
      SELECT 1 FROM entitlement_events ev
      WHERE ev.entitlement_id = e.id
        AND ev.reason = 'Phase 23 migration backfill'
  );
