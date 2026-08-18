-- Phase 22: CMA Tool (FlexCMA)
-- Comparative Market Analysis builder replacing CloudCMA.
-- Agent uploads a Flex CMA export ZIP (textCma.csv + <MLS#>_<n>.jpg photos)
-- from their MLS, fills in the subject property, edits comps, and we produce
-- an interactive shareable report + branded PDF.
--
-- Tables: cmas (top-level report + subject + pricing) and cma_comps (imported
-- comparables with agent overrides + per-line dollar adjustments).
--
-- Storage: photos land in the `cma-photos` Supabase Storage bucket, keyed by
-- <cma_id>/<mls_number>_<n>.jpg. Bucket created via the Supabase dashboard
-- (or the storage.buckets insert at the bottom of this migration).

CREATE TABLE IF NOT EXISTS cmas (
    id BIGSERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL DEFAULT 1,
    created_by_user_id INTEGER,
    share_token UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,

    -- Subject property
    subject_address TEXT,
    subject_city TEXT,
    subject_state TEXT,
    subject_zip TEXT,
    subject JSONB NOT NULL DEFAULT '{}'::jsonb,  -- beds, baths, sqft_living, sqft_total, lot_size, year_built, garage_spaces, pool, waterfront, condition_notes, photo_urls[], features JSONB, latitude, longitude

    -- Client (who this CMA is prepared for)
    client_first_name TEXT,
    client_last_name TEXT,
    client_email TEXT,
    client_phone TEXT,
    lead_id BIGINT REFERENCES leads(id) ON DELETE SET NULL,

    -- Report state
    status TEXT NOT NULL DEFAULT 'draft',  -- draft | ready | sent | archived
    agent_notes TEXT,
    marketing_notes TEXT,

    -- Computed pricing snapshot (see cma._compute_pricing)
    -- { active: {count, median_price, median_ppsf, ...}, pending: {...}, closed: {...},
    --   suggested: {low, target, high, formula}, computed_at: ISO }
    pricing JSONB,

    -- Delivery + engagement
    sent_at TIMESTAMPTZ,
    sent_to TEXT,
    email_resend_id TEXT,
    view_count INTEGER NOT NULL DEFAULT 0,
    last_viewed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cmas_workspace ON cmas (workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cmas_share_token ON cmas (share_token);
CREATE INDEX IF NOT EXISTS idx_cmas_status ON cmas (workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_cmas_lead ON cmas (lead_id);

ALTER TABLE cmas ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON cmas;
CREATE POLICY service_role_all ON cmas FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS cmas_updated_at ON cmas;
CREATE TRIGGER cmas_updated_at
BEFORE UPDATE ON cmas
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


CREATE TABLE IF NOT EXISTS cma_comps (
    id BIGSERIAL PRIMARY KEY,
    cma_id BIGINT NOT NULL REFERENCES cmas(id) ON DELETE CASCADE,
    workspace_id INTEGER NOT NULL DEFAULT 1,

    -- Imported from MLS Flex export (textCma.csv)
    mls_number TEXT,
    status TEXT,                          -- Active | Pending | Closed
    property_type TEXT,                   -- Residential
    style TEXT,                           -- SF (single family), etc

    address TEXT,
    street_number TEXT,
    street_name TEXT,
    unit_number TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    county TEXT,
    subdivision TEXT,
    latitude NUMERIC,
    longitude NUMERIC,

    beds INTEGER,
    baths_total NUMERIC,
    baths_full INTEGER,
    baths_half INTEGER,
    sqft_living INTEGER,
    sqft_total INTEGER,
    lot_size NUMERIC,
    year_built INTEGER,
    garage_spaces NUMERIC,
    stories NUMERIC,
    pool BOOLEAN,
    waterfront BOOLEAN,

    list_price NUMERIC,
    original_list_price NUMERIC,
    current_price NUMERIC,                -- sold price for Closed, list price otherwise
    dom INTEGER,
    pending_date DATE,
    closing_date DATE,
    expiration_date DATE,
    entry_date TIMESTAMPTZ,
    status_change_date DATE,

    listing_agent TEXT,
    listing_agent_phone TEXT,
    listing_agent_email TEXT,

    remarks TEXT,
    features JSONB DEFAULT '{}'::jsonb,   -- roof, cooling, floor, exterior, view, pool_desc, security, etc.

    photos TEXT[] DEFAULT ARRAY[]::TEXT[],  -- Supabase Storage URLs, in filename order
    primary_photo_url TEXT,                  -- convenience: photos[0]

    -- Agent controls
    included BOOLEAN NOT NULL DEFAULT TRUE,  -- uncheck to exclude from report
    agent_notes TEXT,
    -- Per-line dollar adjustments, e.g. [{label: "Pool", amount: -15000}, {label: "Remodeled kitchen", amount: 10000}]
    adjustments JSONB DEFAULT '[]'::jsonb,
    -- Any fields the agent has manually overridden (takes precedence when rendering)
    agent_override JSONB DEFAULT '{}'::jsonb,

    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cma_comps_cma ON cma_comps (cma_id, included);
CREATE INDEX IF NOT EXISTS idx_cma_comps_status ON cma_comps (cma_id, status);
CREATE INDEX IF NOT EXISTS idx_cma_comps_mls ON cma_comps (mls_number);

ALTER TABLE cma_comps ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON cma_comps;
CREATE POLICY service_role_all ON cma_comps FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS cma_comps_updated_at ON cma_comps;
CREATE TRIGGER cma_comps_updated_at
BEFORE UPDATE ON cma_comps
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- Supabase Storage bucket for CMA photos.
-- Public-read so the report/PDF can render <img src="..."> directly without signed URLs.
-- Only service_role can write (backend uploads during ZIP ingest).
INSERT INTO storage.buckets (id, name, public)
VALUES ('cma-photos', 'cma-photos', true)
ON CONFLICT (id) DO NOTHING;
