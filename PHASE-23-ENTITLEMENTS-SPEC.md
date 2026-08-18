# Phase 23 — Entitlement Layer (Two Brands, One Backend)

**Status:** Spec, not yet built
**Depends on:** Phase 13 multi-tenant foundation (`workspaces`, `db()`, JWT `workspace_id`)
**Blocks:** Listing Dashboard build, Stripe billing, tools marketing site

---

## 1. What this is

One backend and one database serving two customer-facing brands:

| Brand | Host | Audience | How they arrive |
|---|---|---|---|
| **TPL Collective** | `portal.tplcollective.ai` | Team members | Recruiting funnel |
| **[Tools brand — TBD]** | own domain | Any agent, any brokerage | Paid software funnel |

Both write to the same `workspaces` table. Access to any given tool is controlled by a
single `workspace_entitlements` row, regardless of which door the customer came through.

The customer sees a software company. Internally it is one ecosystem.

---

## 2. Compliance constraints baked into the schema

LPT prohibits offering items of value in exchange for being named sponsor. Team benefits
are permitted. The schema enforces the distinction so the data never contradicts the
marketing.

**Rules:**

1. There is **no** entitlement `source` value referencing sponsorship or recruiting.
2. `source = 'team_member'` requires a non-null `team_agreement_id`. Enforced by DB CHECK
   constraint, not by application code.
3. `sponsorship_status` may live on the CRM contact for business tracking. It is **never**
   read by the entitlement check. No code path may join it into an access decision.
4. Every `team_member` grant writes the agreement ID into `entitlement_events`, so the
   audit trail shows team membership as the trigger.

**Copy rules (not enforceable in code, enforced in review):**

- Tools marketing never mentions LPT, sponsorship, or joining anything.
- Team benefits appear only in team onboarding material, behind the agreement.
- Pricing page shows real prices. There is no "free if you join" tier.

---

## 3. Schema

Migration: `migrations/2026-08-17-phase-23-entitlements.sql`

All tables: RLS enabled, service-role policy, `updated_at` trigger (Phase 15 convention).
`workspace_entitlements` and `team_agreements` added to `TENANT_TABLES` for `db()` scoping.

### 3.1 `products` — the registry

Tools are data. Adding a seventh tool is an INSERT plus building the tool, never a change
to the entitlement engine.

```sql
CREATE TABLE products (
    id                      BIGSERIAL PRIMARY KEY,
    slug                    TEXT NOT NULL UNIQUE,
    name                    TEXT NOT NULL,
    tagline                 TEXT,
    description             TEXT,
    category                TEXT,              -- listing | pricing | recruiting | coaching
    monthly_price_cents     INTEGER,
    annual_price_cents      INTEGER,
    stripe_product_id       TEXT,
    stripe_monthly_price_id TEXT,
    stripe_annual_price_id  TEXT,
    is_sellable             BOOLEAN NOT NULL DEFAULT TRUE,   -- outsiders may buy standalone
    is_public               BOOLEAN NOT NULL DEFAULT TRUE,   -- appears on tools marketing site
    free_tier_limits        JSONB NOT NULL DEFAULT '{}'::jsonb,
    icon                    TEXT,
    sort_order              INTEGER NOT NULL DEFAULT 0,
    status                  TEXT NOT NULL DEFAULT 'active',  -- active | beta | retired
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Seed (prices left NULL — Joe to set):

| slug | name | notes |
|---|---|---|
| `listing-dashboard` | Listing Dashboard | The anchor. 14 sections, full listing lifecycle. |
| `cma-builder` | CMA Builder | Phase 22 FlexCMA, already ~1,600 lines in `cma.py` |
| `net-sheet` | Seller Net Sheet | Falls out of Listing Dashboard, sells standalone |
| `comparator` | Brokerage Comparator | `/compare`, live |
| `coaching` | Coaching Platform | Phase 15, live |

Free tier example: `listing-dashboard` → `{"active_listings": 1}`

### 3.2 `bundles` — presets that grant many products

```sql
CREATE TABLE bundles (
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

CREATE TABLE bundle_products (
    bundle_id  BIGINT NOT NULL REFERENCES bundles(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    PRIMARY KEY (bundle_id, product_id)
);
```

Bundles are a convenience for granting and for Stripe checkout. They are **not** read at
access-check time — purchasing a bundle writes one entitlement row per product.

### 3.3 `team_agreements` — the substantive relationship

```sql
CREATE TABLE team_agreements (
    id                 BIGSERIAL PRIMARY KEY,
    workspace_id       INTEGER NOT NULL,
    lead_id            BIGINT REFERENCES leads(id) ON DELETE SET NULL,
    user_id            INTEGER,
    agreement_version  TEXT NOT NULL,
    signed_at          TIMESTAMPTZ NOT NULL,
    signed_name        TEXT,
    signed_ip          TEXT,
    document_url       TEXT,
    obligations        JSONB NOT NULL DEFAULT '{}'::jsonb,  -- what the member commits to
    status             TEXT NOT NULL DEFAULT 'active',      -- active | terminated
    terminated_at      TIMESTAMPTZ,
    terminated_reason  TEXT,
    notes              TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

`obligations` documents what the member commits to (onboarding completion, training
cadence, team standards, systems usage). This is the substance the team benefit rests on.
Populate it from the actual agreement text.

### 3.4 `workspace_entitlements` — the toggle

```sql
CREATE TABLE workspace_entitlements (
    id                            BIGSERIAL PRIMARY KEY,
    workspace_id                  INTEGER NOT NULL,
    product_id                    BIGINT NOT NULL REFERENCES products(id) ON DELETE CASCADE,

    status                        TEXT NOT NULL DEFAULT 'active',
        -- active | trialing | past_due | revoked | expired
    source                        TEXT NOT NULL,
        -- purchased | trial | team_member | comp | internal
    tier                          TEXT NOT NULL DEFAULT 'pro',   -- free | pro

    team_agreement_id             BIGINT REFERENCES team_agreements(id) ON DELETE RESTRICT,

    granted_by_user_id            INTEGER,
    granted_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    starts_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at                    TIMESTAMPTZ,
    revoked_at                    TIMESTAMPTZ,
    revoke_reason                 TEXT,

    stripe_subscription_id        TEXT,
    stripe_subscription_item_id   TEXT,

    limits                        JSONB NOT NULL DEFAULT '{}'::jsonb,  -- overrides product defaults
    notes                         TEXT,

    created_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (workspace_id, product_id),

    CONSTRAINT entitlement_source_valid
        CHECK (source IN ('purchased','trial','team_member','comp','internal')),

    -- Compliance guardrail: team grants require a signed agreement.
    CONSTRAINT team_member_requires_agreement
        CHECK (source <> 'team_member' OR team_agreement_id IS NOT NULL)
);

CREATE INDEX idx_entitlements_workspace ON workspace_entitlements (workspace_id, status);
CREATE INDEX idx_entitlements_product   ON workspace_entitlements (product_id, status);
CREATE INDEX idx_entitlements_stripe    ON workspace_entitlements (stripe_subscription_id);
CREATE INDEX idx_entitlements_expiring  ON workspace_entitlements (expires_at)
    WHERE expires_at IS NOT NULL AND status IN ('active','trialing');
```

### 3.5 `entitlement_events` — audit trail

```sql
CREATE TABLE entitlement_events (
    id              BIGSERIAL PRIMARY KEY,
    workspace_id    INTEGER NOT NULL,
    product_id      BIGINT REFERENCES products(id) ON DELETE SET NULL,
    entitlement_id  BIGINT REFERENCES workspace_entitlements(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,
        -- granted | revoked | upgraded | downgraded | expired | renewed
        -- | payment_failed | trial_started | trial_converted
    actor_user_id   INTEGER,
    actor_type      TEXT NOT NULL DEFAULT 'admin',  -- admin | system | stripe | self
    from_status     TEXT,
    to_status       TEXT,
    from_source     TEXT,
    to_source       TEXT,
    reason          TEXT,
    meta            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ent_events_workspace ON entitlement_events (workspace_id, created_at DESC);
```

Never delete entitlement rows. Revoke by setting `status='revoked'` + `revoked_at`. The
history is the point — when a customer says "I paid for this and it turned off," this table
answers it.

### 3.6 `workspaces` additions

```sql
ALTER TABLE workspaces
    ADD COLUMN IF NOT EXISTS account_type TEXT NOT NULL DEFAULT 'customer',
        -- team | customer | internal
    ADD COLUMN IF NOT EXISTS brand TEXT NOT NULL DEFAULT 'tools',
        -- tpl | tools   (signup origin; drives email templates + theming)
    ADD COLUMN IF NOT EXISTS lead_id BIGINT REFERENCES leads(id) ON DELETE SET NULL;
```

Every account is also a CRM contact via `lead_id`. A paying non-LPT agent is a customer
*and* a lead with observable production signal.

---

## 4. Backend module

New file `mission-control/app/entitlements.py`, wired the same way `coaching.py`,
`cma.py`, and `prospect_engagement.py` are:

```python
import entitlements as _ent_mod
_ent_mod.setup(db, supabase)
app.include_router(_ent_mod.router)
app.include_router(_ent_mod.public_router)
```

### 4.1 Core API

```python
def has_entitlement(workspace_id: int, product_slug: str) -> bool
def get_entitlement(workspace_id: int, product_slug: str) -> dict | None
def get_entitlements(workspace_id: int) -> dict[str, dict]
    # {"listing-dashboard": {"tier": "pro", "status": "active", "limits": {...}}, ...}

def require_entitlement(product_slug: str)
    # FastAPI dependency. 403 with {error, product, upgrade_url} when missing.

def check_limit(workspace_id: int, product_slug: str, key: str, current: int) -> None
    # Raises 403 when a free-tier cap is hit. Called at the API, not the UI.

def grant(workspace_id, product_slug, source, *, tier="pro", actor_user_id=None,
          team_agreement_id=None, expires_at=None, stripe_subscription_id=None,
          reason=None) -> dict
def revoke(workspace_id, product_slug, *, actor_user_id=None, reason=None) -> dict
def grant_bundle(workspace_id, bundle_slug, source, **kw) -> list[dict]
```

An entitlement is active when:
`status IN ('active','trialing')` AND `starts_at <= now()` AND
(`expires_at IS NULL` OR `expires_at > now()`).

### 4.2 Caching

`get_entitlements()` caches per workspace with a short TTL (30–60s) so gated routes are not
a DB round-trip each. `grant()` / `revoke()` invalidate the workspace's cache entry
immediately, so admin toggles land instantly for the acting workspace.

### 4.3 Authorization rule — non-negotiable

**Never authorize from the JWT.** Tokens live 7 days; a revoked product would stay usable
for a week.

- JWT MAY carry an entitlement snapshot, used **only** to render nav and hide UI.
- Every gated route re-checks via `require_entitlement()` against the DB (through cache).
- Hiding a nav item is not gating. Free-tier caps enforce at the API via `check_limit()`.

### 4.4 Admin endpoints

```
GET    /api/admin/products
POST   /api/admin/products
PATCH  /api/admin/products/{id}

GET    /api/admin/workspaces/{id}/entitlements
POST   /api/admin/workspaces/{id}/entitlements        # grant (product or bundle)
DELETE /api/admin/workspaces/{id}/entitlements/{slug} # revoke, reason required
GET    /api/admin/workspaces/{id}/entitlement-events

GET    /api/admin/team-agreements
POST   /api/admin/team-agreements
PATCH  /api/admin/team-agreements/{id}                # terminate
```

`POST .../entitlements` with `source='team_member'` and no `team_agreement_id` returns 400
before the DB constraint fires, with a message pointing at the agreement requirement.

### 4.5 Self-serve endpoints

```
GET  /api/me/entitlements          # what this workspace can use
GET  /api/products                 # public: registry for the tools marketing site
POST /api/billing/checkout         # Stripe Checkout session (later)
POST /api/webhooks/stripe          # subscription lifecycle → entitlement writes (later)
```

---

## 5. Admin UI

Mission Control → **Admin → Entitlements**.

- Workspace search, then a product × status grid with a toggle per product.
- Each toggle opens a small form: source, tier, expiry, reason. `team_member` shows a
  team-agreement picker and will not submit without one.
- Right panel: entitlement event history for the selected workspace.
- Bulk action: grant a bundle to a workspace in one click.
- Badges surface `source` so a comped account is never mistaken for a paying one.

---

## 6. Host routing

`dashboard()` in `main.py` already branches on the Host header (Phase 15.4:
`host.startswith("portal.")`). Extend to a third brand:

| Host | Serves |
|---|---|
| `portal.tplcollective.ai` | `static/portal/index.html` (TPL brand) |
| `mission.tplcollective.ai` | `static/index.html` (Mission Control) |
| tools domain | `static/tools/index.html` (tools brand) |

Both customer surfaces render nav from `/api/me/entitlements`, so the same account sees
the same tools under whichever brand they signed up through — only theming, copy, and
email templates differ.

---

## 7. Build order

1. **Migration + seed** — tables, constraints, 5 product rows, backfill existing
   workspaces with `account_type` / `brand` / entitlements matching their current plan.
2. **`entitlements.py`** — helpers, dependency, cache, admin CRUD.
3. **Admin toggle UI** in Mission Control.
4. **Retrofit existing tools** — gate `cma.py` and `coaching.py` routes behind
   `require_entitlement()`. Do this before new tools so the pattern is proven.
5. **Nav gating** in portal + Mission Control from `/api/me/entitlements`.
6. **Stripe** — products, checkout, webhook → entitlement writes. (Can defer.)
7. **Listing Dashboard** — built gated from day one, no retrofit.

Steps 1–5 are the foundation. Step 7 is the product Joe actually wants; it is fast once
the gates exist and painful to add afterward.

---

## 8. Open decisions

| # | Decision | Notes |
|---|---|---|
| 1 | **Tools brand name + domain** | Blocks marketing site, PDF branding, Stripe product names. Does not block steps 1–5; spec uses a `TOOLS_BRAND` constant. |
| 2 | **Pricing** | Per-product monthly, and a bundle price. The outside price is what makes the team benefit legible. |
| 3 | **Free tier caps** | Proposed: Listing Dashboard 1 active listing; CMA 1 report/mo. Tune once the tool exists. |
| 4 | **Stripe in v1, or manual invoicing first** | Steps 1–5 work either way. |
| 5 | **SSN handling in Listing Dashboard** | Recommend last-4 only. Still open. |
| 6 | **Team agreement obligations text** | Needs the real agreement. Populate `obligations` from it. |
| 7 | **LPT compliance review** | Get team-benefit wording blessed before the tools site goes live. |
