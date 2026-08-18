-- Listing Dashboard - foundation schema
--
-- A per-listing operating system: seller intake -> pricing -> marketing -> offers -> closing.
-- Modelled on Joe's 14-tab "Blank Dashboard" workbook, with deliberate departures noted below.
--
-- Gated behind the `listing-dashboard` entitlement (Phase 23). The net sheet is
-- additionally sellable standalone as `net-sheet`.
--
--
-- DELIBERATE DEPARTURES FROM THE SPREADSHEET
--
-- 1. NO SOCIAL SECURITY NUMBERS, ANYWHERE.
--    The workbook collected full SSNs in three places (Listing Interview A14 for each
--    of three sellers, A76 in the payoff block, Contract to Close A37). In a personal
--    spreadsheet that is one agent's own risk. In a multi-tenant product sold to agents
--    at other brokerages it would make us custodian of thousands of sellers' SSNs -
--    GLBA and state breach-notification exposure, and the highest-value target in the
--    database. The legitimate need is narrow: lenders take the LAST FOUR to pull a
--    payoff. `listing_mortgages.account_number_last4` covers that. There is no SSN
--    column in this schema and one must not be added.
--
-- 2. "Old offer" and "Accepted" tabs collapse into one `offers` table with many rows.
--    They were near-duplicates, and the original carried a broken =#REF! formula.
--    Offer history is worth keeping anyway.
--
-- 3. Contract-to-Close deadlines become ROWS (`transaction_milestones`), not columns.
--    That allows templating per contract type and, more importantly, the query the
--    agent actually wants: "what is due this week across ALL my listings."
--
-- 4. The CMA tab is NOT rebuilt. `listings.cma_id` links to the Phase 22 CMA Builder.
--
-- 5. Dropped: Estimated Mortgage (buyer-side, lender's job), Reverse Prospecting
--    (a manual re-typing of MLS output), MixBook vendor field, DISC personality type.
--
-- 6. Added, because the workbook had no concept of them: listing status as a real
--    lifecycle field, price-change history, and structured showing feedback.
--
--
-- WHY fee_profiles EXISTS (the load-bearing decision)
--    Every number in the workbook's Expense Sheet is Florida law, hardcoded:
--    title insurance at $5.75/K then $5.00/K, doc stamps at $0.70/$100, tax proration
--    on a 365-day year from Jan 1. It also hardcodes `LPT Fee: 195` - and this product
--    is sold to agents at KW, eXp, Compass and elsewhere. Shipping those baked in would
--    produce confidently wrong numbers everywhere outside Florida, and a wrong net sheet
--    is worse than no net sheet: it is the document a seller makes decisions on.
--    So the math lives in data, not code. Florida ships first because it is verifiable;
--    other states become a row, not a rewrite.
--
--
-- JSONB vs COLUMNS
--    Sections that are pure intake forms with no math and no filtering (the HOA
--    questionnaire, showing instructions, mechanicals) live in JSONB - roughly 150
--    fields that would be absurd as columns. Anything computed, sorted, or filtered
--    on gets a real column.


-- ════════════════════════════════════════════════════════════════════
-- 1. fee_profiles - the portability layer
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS fee_profiles (
    id            BIGSERIAL PRIMARY KEY,
    -- NULL workspace_id = system-provided profile available to everyone.
    -- A workspace may fork one to override their own title company's rates.
    workspace_id  INTEGER,
    state         TEXT NOT NULL,              -- 'FL', 'TX', ...
    county        TEXT,                       -- optional county-level override
    name          TEXT NOT NULL,
    config        JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_note   TEXT,                       -- citation for the rates; keep it honest
    verified_at   DATE,
    is_default    BOOLEAN NOT NULL DEFAULT FALSE,
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fee_profiles_state ON fee_profiles (state, status);
CREATE INDEX IF NOT EXISTS idx_fee_profiles_ws    ON fee_profiles (workspace_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fee_profiles_system_default
    ON fee_profiles (state) WHERE workspace_id IS NULL AND is_default;

ALTER TABLE fee_profiles ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON fee_profiles;
CREATE POLICY service_role_all ON fee_profiles FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS fee_profiles_updated_at ON fee_profiles;
CREATE TRIGGER fee_profiles_updated_at
BEFORE UPDATE ON fee_profiles
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 2. listings - the spine
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS listings (
    id                    BIGSERIAL PRIMARY KEY,
    workspace_id          INTEGER NOT NULL DEFAULT 1,
    created_by_user_id    BIGINT REFERENCES users(id) ON DELETE SET NULL,

    status                TEXT NOT NULL DEFAULT 'pre_list',
        -- pre_list | coming_soon | active | pending | closed | expired | withdrawn | cancelled

    -- Property
    address_line1         TEXT,
    address_line2         TEXT,
    city                  TEXT,
    state                 TEXT,
    zip                   TEXT,
    county                TEXT,
    parcel_id             TEXT,
    mls_number            TEXT,
    property_type         TEXT,               -- single_family | condo | townhome | land | multi
    year_built            INTEGER,

    -- Tax-record vs marketing figures are deliberately separate; the workbook
    -- tracked both because they disagree and the discrepancy matters at appraisal.
    beds_tax              NUMERIC(5,1),
    baths_tax             NUMERIC(5,1),
    sqft_tax              INTEGER,
    beds_marketing        NUMERIC(5,1),
    baths_marketing       NUMERIC(5,1),
    sqft_marketing        INTEGER,
    stories               INTEGER,
    garage_spaces         NUMERIC(4,1),
    lot_size_acres        NUMERIC(10,4),
    has_pool              BOOLEAN,

    -- Listing terms
    list_price            NUMERIC(14,2),
    original_list_price   NUMERIC(14,2),
    list_date             DATE,
    expiration_date       DATE,
    commission_pct        NUMERIC(6,4),       -- total, e.g. 0.0500
    coop_commission_pct   NUMERIC(6,4),

    -- Lifecycle dates
    under_contract_date   DATE,
    closed_date           DATE,
    sold_price            NUMERIC(14,2),

    -- Linkage
    lead_id               BIGINT REFERENCES leads(id) ON DELETE SET NULL,
    cma_id                BIGINT REFERENCES cmas(id) ON DELETE SET NULL,
    fee_profile_id        BIGINT REFERENCES fee_profiles(id) ON DELETE SET NULL,

    -- Intake sections (pure forms, no math - see JSONB note at top)
    interview             JSONB NOT NULL DEFAULT '{}'::jsonb,
        -- motivators, occupancy, tenant info, showing instructions, lockbox, sign,
        -- gate/alarm, pets, paperwork checklist, items that do not convey
    property_notes        JSONB NOT NULL DEFAULT '{}'::jsonb,
        -- mechanicals (roof, AC ages, water heater, panel), pool details, features
    hoa                   JSONB NOT NULL DEFAULT '{}'::jsonb,
        -- the full HOA questionnaire + amenities checklist
    marketing             JSONB NOT NULL DEFAULT '{}'::jsonb,
        -- headline, target buyer, top three selling features, neighborhood, challenges

    notes                 TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT listing_status_valid CHECK (status IN
        ('pre_list','coming_soon','active','pending','closed','expired','withdrawn','cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_listings_workspace  ON listings (workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_listings_lead       ON listings (lead_id);
CREATE INDEX IF NOT EXISTS idx_listings_expiring   ON listings (expiration_date)
    WHERE status IN ('active','coming_soon');
CREATE INDEX IF NOT EXISTS idx_listings_mls        ON listings (mls_number);

ALTER TABLE listings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON listings;
CREATE POLICY service_role_all ON listings FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS listings_updated_at ON listings;
CREATE TRIGGER listings_updated_at
BEFORE UPDATE ON listings
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 3. listing_sellers - the workbook allowed 3; this allows any number
--    NOTE: no SSN column. See departure #1.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS listing_sellers (
    id                  BIGSERIAL PRIMARY KEY,
    listing_id          BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    workspace_id        INTEGER NOT NULL DEFAULT 1,

    first_name          TEXT,
    last_name           TEXT,
    email               TEXT,
    phone_cell          TEXT,
    phone_home          TEXT,
    other_contact       TEXT,

    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    marital_status      TEXT,
    mailing_address     TEXT,                 -- if different from property
    forwarding_address  TEXT,                 -- for HUD and tax docs post-closing
    trust_parties       TEXT,

    lead_id             BIGINT REFERENCES leads(id) ON DELETE SET NULL,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_listing_sellers_listing ON listing_sellers (listing_id);

ALTER TABLE listing_sellers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON listing_sellers;
CREATE POLICY service_role_all ON listing_sellers FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS listing_sellers_updated_at ON listing_sellers;
CREATE TRIGGER listing_sellers_updated_at
BEFORE UPDATE ON listing_sellers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 4. listing_mortgages - payoffs feeding the net sheet
--    NOTE: last four only. See departure #1.
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS listing_mortgages (
    id                      BIGSERIAL PRIMARY KEY,
    listing_id              BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    workspace_id            INTEGER NOT NULL DEFAULT 1,

    position                TEXT NOT NULL DEFAULT 'first',   -- first | second | heloc | other
    lender_name             TEXT,
    account_number_last4    TEXT,             -- LAST FOUR ONLY
    estimated_payoff        NUMERIC(14,2),
    payoff_good_through     DATE,
    has_escrow              BOOLEAN,
    notes                   TEXT,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT mortgage_position_valid CHECK (position IN ('first','second','heloc','other')),
    -- Guard against anyone ever widening this into a full account or SSN field.
    CONSTRAINT account_last4_is_short CHECK (account_number_last4 IS NULL OR length(account_number_last4) <= 4)
);

CREATE INDEX IF NOT EXISTS idx_listing_mortgages_listing ON listing_mortgages (listing_id);

ALTER TABLE listing_mortgages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON listing_mortgages;
CREATE POLICY service_role_all ON listing_mortgages FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS listing_mortgages_updated_at ON listing_mortgages;
CREATE TRIGGER listing_mortgages_updated_at
BEFORE UPDATE ON listing_mortgages
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 5. offers - replaces both "Old offer" and "Accepted" tabs
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS offers (
    id                       BIGSERIAL PRIMARY KEY,
    listing_id               BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    workspace_id             INTEGER NOT NULL DEFAULT 1,

    buyer_names              TEXT,
    buyer_agent_name         TEXT,
    buyer_agent_email        TEXT,
    buyer_agent_phone        TEXT,
    buyer_brokerage          TEXT,
    lender_name              TEXT,
    title_company            TEXT,

    offer_price              NUMERIC(14,2),
    earnest_money            NUMERIC(14,2),
    additional_deposit       NUMERIC(14,2),
    additional_deposit_due   DATE,
    financing_type           TEXT,            -- cash | conventional | fha | va | usda | other
    closing_date_requested   DATE,

    seller_concessions       NUMERIC(14,2),
    home_warranty_amount     NUMERIC(14,2),
    home_warranty_paid_by    TEXT,
    repairs_credit           NUMERIC(14,2),

    status                   TEXT NOT NULL DEFAULT 'received',
        -- received | countered | accepted | rejected | withdrawn | backup | expired
    received_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision_at              TIMESTAMPTZ,
    executed_date            DATE,

    contingencies            JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes                    TEXT,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT offer_status_valid CHECK (status IN
        ('received','countered','accepted','rejected','withdrawn','backup','expired'))
);

CREATE INDEX IF NOT EXISTS idx_offers_listing ON offers (listing_id, status);

ALTER TABLE offers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON offers;
CREATE POLICY service_role_all ON offers FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS offers_updated_at ON offers;
CREATE TRIGGER offers_updated_at
BEFORE UPDATE ON offers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 6. net_sheets - replaces BOTH the Expense Sheet and the Offer Sheet.
--    They were the same calculation with different headers.
--
--    Stores inputs AND a computed snapshot. A net sheet handed to a seller is a
--    point-in-time document: if fee rates or the profile change later, the historical
--    document must not silently change underneath it. Same snapshot discipline as
--    recruit_comparisons (Phase 14).
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS net_sheets (
    id                  BIGSERIAL PRIMARY KEY,
    listing_id          BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    workspace_id        INTEGER NOT NULL DEFAULT 1,
    created_by_user_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,

    label               TEXT NOT NULL DEFAULT 'Estimate',   -- "Option 1", "List price", "Offer - Smith"
    kind                TEXT NOT NULL DEFAULT 'estimate',   -- estimate | offer
    offer_id            BIGINT REFERENCES offers(id) ON DELETE SET NULL,

    sale_price          NUMERIC(14,2) NOT NULL,
    closing_date        DATE,
    fee_profile_id      BIGINT REFERENCES fee_profiles(id) ON DELETE SET NULL,

    inputs              JSONB NOT NULL DEFAULT '{}'::jsonb,   -- agent overrides
    computed            JSONB NOT NULL DEFAULT '{}'::jsonb,   -- full snapshot, each line carrying its formula

    prepared_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT net_sheet_kind_valid CHECK (kind IN ('estimate','offer'))
);

CREATE INDEX IF NOT EXISTS idx_net_sheets_listing ON net_sheets (listing_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_net_sheets_offer   ON net_sheets (offer_id);

ALTER TABLE net_sheets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON net_sheets;
CREATE POLICY service_role_all ON net_sheets FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS net_sheets_updated_at ON net_sheets;
CREATE TRIGGER net_sheets_updated_at
BEFORE UPDATE ON net_sheets
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 7. transaction_milestones - Contract to Close, as rows
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS transaction_milestones (
    id                    BIGSERIAL PRIMARY KEY,
    listing_id            BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    offer_id              BIGINT REFERENCES offers(id) ON DELETE CASCADE,
    workspace_id          INTEGER NOT NULL DEFAULT 1,

    key                   TEXT NOT NULL,
        -- escrow_deposit | additional_deposit | loan_application | inspection |
        -- inspection_response | appraisal | loan_commitment | title_ordered |
        -- title_received | walkthrough | closing | other
    label                 TEXT NOT NULL,
    due_date              DATE,
    completed_at          TIMESTAMPTZ,
    completed_by_user_id  BIGINT REFERENCES users(id) ON DELETE SET NULL,
    sort_order            INTEGER NOT NULL DEFAULT 0,
    is_critical           BOOLEAN NOT NULL DEFAULT FALSE,
    notes                 TEXT,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Powers "what is due this week across ALL my listings" - the query the workbook
-- could never answer, because deadlines were columns on one sheet per property.
CREATE INDEX IF NOT EXISTS idx_milestones_due ON transaction_milestones (workspace_id, due_date)
    WHERE completed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_milestones_listing ON transaction_milestones (listing_id, sort_order);

ALTER TABLE transaction_milestones ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON transaction_milestones;
CREATE POLICY service_role_all ON transaction_milestones FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS transaction_milestones_updated_at ON transaction_milestones;
CREATE TRIGGER transaction_milestones_updated_at
BEFORE UPDATE ON transaction_milestones
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 8. listing_price_changes - the workbook had no concept of this
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS listing_price_changes (
    id                 BIGSERIAL PRIMARY KEY,
    listing_id         BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    workspace_id       INTEGER NOT NULL DEFAULT 1,
    old_price          NUMERIC(14,2),
    new_price          NUMERIC(14,2) NOT NULL,
    changed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    reason             TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_price_changes_listing ON listing_price_changes (listing_id, changed_at DESC);

ALTER TABLE listing_price_changes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON listing_price_changes;
CREATE POLICY service_role_all ON listing_price_changes FOR ALL TO service_role USING (true) WITH CHECK (true);


-- ════════════════════════════════════════════════════════════════════
-- 9. listing_showings - structured feedback, replacing "notes for ShowingTime staff"
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS listing_showings (
    id                    BIGSERIAL PRIMARY KEY,
    listing_id            BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    workspace_id          INTEGER NOT NULL DEFAULT 1,

    showed_at             TIMESTAMPTZ,
    agent_name            TEXT,
    agent_email           TEXT,
    agent_phone           TEXT,
    agent_brokerage       TEXT,

    feedback              TEXT,
    buyer_interest_level  INTEGER,            -- 1-10, mirrors the workbook's rating scale
    price_opinion         TEXT,               -- too_high | about_right | good_value
    feedback_requested_at TIMESTAMPTZ,
    feedback_received_at  TIMESTAMPTZ,
    source                TEXT NOT NULL DEFAULT 'manual',  -- manual | showingtime | mls

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT showing_interest_range CHECK (buyer_interest_level IS NULL
        OR (buyer_interest_level BETWEEN 1 AND 10))
);

CREATE INDEX IF NOT EXISTS idx_showings_listing ON listing_showings (listing_id, showed_at DESC);

ALTER TABLE listing_showings ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON listing_showings;
CREATE POLICY service_role_all ON listing_showings FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS listing_showings_updated_at ON listing_showings;
CREATE TRIGGER listing_showings_updated_at
BEFORE UPDATE ON listing_showings
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 10. listing_weekly_reports - the "Wkly Data" tab, and the retention tool
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS listing_weekly_reports (
    id                  BIGSERIAL PRIMARY KEY,
    listing_id          BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    workspace_id        INTEGER NOT NULL DEFAULT 1,

    week_ending         DATE NOT NULL,
    showings_count      INTEGER NOT NULL DEFAULT 0,
    mls_matches         INTEGER NOT NULL DEFAULT 0,
    buyer_views         INTEGER NOT NULL DEFAULT 0,
    buyer_favorites     INTEGER NOT NULL DEFAULT 0,
    agent_rejections    INTEGER NOT NULL DEFAULT 0,
    adjustments_made    TEXT,
    notes_to_seller     TEXT,
    notes_internal      TEXT,

    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (listing_id, week_ending)
);

CREATE INDEX IF NOT EXISTS idx_weekly_reports_listing ON listing_weekly_reports (listing_id, week_ending DESC);

ALTER TABLE listing_weekly_reports ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS service_role_all ON listing_weekly_reports;
CREATE POLICY service_role_all ON listing_weekly_reports FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS listing_weekly_reports_updated_at ON listing_weekly_reports;
CREATE TRIGGER listing_weekly_reports_updated_at
BEFORE UPDATE ON listing_weekly_reports
FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ════════════════════════════════════════════════════════════════════
-- 11. Seed the Florida fee profile
--
--     The workbook encoded only two title-insurance tiers ($5.75/K to $100K,
--     then $5.00/K). That is correct up to $1M and WRONG above it - Florida's
--     promulgated schedule steps down again at $1M, $5M and $10M. Encoding the
--     full ladder here fixes a real defect in the original.
--
--     Doc stamps are $0.70 per $100 statewide EXCEPT Miami-Dade, which is $0.60
--     per $100 plus a $0.45 surtax on anything that is not single-family.
--
--     Who pays the owner's title policy is COUNTY CUSTOM in Florida, not law -
--     seller pays in most counties, buyer pays in Miami-Dade, Broward, Sarasota
--     and Collier. Encoded so the default is right per county.
--
--     RATES MUST BE VERIFIED against the current FLOIR schedule before this is
--     put in front of a seller. verified_at is deliberately NULL until someone does.
-- ════════════════════════════════════════════════════════════════════

INSERT INTO fee_profiles (workspace_id, state, name, is_default, source_note, config)
VALUES (NULL, 'FL', 'Florida (default)', TRUE,
    'Florida promulgated owner title insurance rates + FL doc stamp statute. '
    'UNVERIFIED - confirm against the current FLOIR rate schedule and Ch. 201 F.S. before seller-facing use.',
    '{
      "title_insurance": {
        "basis": "sale_price",
        "tiers": [
          {"up_to": 100000,   "rate_per_1000": 5.75},
          {"up_to": 1000000,  "rate_per_1000": 5.00},
          {"up_to": 5000000,  "rate_per_1000": 2.50},
          {"up_to": 10000000, "rate_per_1000": 2.25},
          {"up_to": null,     "rate_per_1000": 2.00}
        ],
        "minimum": 100.00,
        "paid_by_default": "seller",
        "paid_by_county_overrides": {
          "Miami-Dade": "buyer", "Broward": "buyer",
          "Sarasota": "buyer", "Collier": "buyer"
        }
      },
      "doc_stamps": {
        "rate_per_100": 0.70,
        "rounding": "up_to_next_100",
        "paid_by_default": "seller",
        "county_overrides": {
          "Miami-Dade": {
            "rate_per_100": 0.60,
            "surtax_per_100": 0.45,
            "surtax_applies_to": "non_single_family"
          }
        }
      },
      "tax_proration": {
        "day_count": 365,
        "start": "jan_1",
        "seller_pays_through": "day_before_closing",
        "escrow_refund_estimate_pct": 0.75
      },
      "defaults": {
        "settlement_fee": 525.00,
        "municipal_lien_search": 85.00,
        "title_search": 100.00,
        "deed_recording": 50.00,
        "release_of_mortgage": 100.00,
        "estoppel_fee": 0.00
      }
    }'::jsonb)
ON CONFLICT DO NOTHING;
