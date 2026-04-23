# TPL Brokerage Comparator - Build Spec v2.1

**For:** Claude Code
**Target:** tplcollective.ai (static Vercel site, GitHub auto-deploy)
**Route:** `/compare`
**Reference studied:** smartagentalliance.com/brokerage-comparison/
**Goal:** Ship an interactive comparator. User picks 2-5 brokerages from a searchable list of up to 50. Live side-by-side data matrix with total-cost math at adjustable GCI. LPT-favorable by virtue of accurate numbers, not spin.

## v2.1 corrections (from verified LPT flyer + Joe's clarifications)

Previous draft had several inaccuracies. Corrections from the official lpt.com flyer (valid through 4/30/26) plus Joe's direct clarifications on mechanics:

- **LPT has NO monthly fees on either plan.** The $89/$149 figures some competitors cite are optional upgrades, not base plan costs.
- **The $195 per-txn fee is a brokerage fee charged on every deal, regardless of whether the agent passes it through to the client.** Default mechanic is pass-through at closing (cash-flow convenience), but for cost-comparison purposes against other brokerages it must always be counted as a per-txn brokerage cost. `calcTotalCost` includes `195 × txns` in the agent cost total, always.
- **The $500 annual fee covers BOTH technology AND E&O** (withheld from first deal of the year).
- **Business Builders CAN recruit and build a downline on the BB plan.** Their HybridShare earnings don't activate until they upgrade to Brokerage Partner, but the downline tree carries over on upgrade. This reframes BB as a "build now, earn when ready" strategy, not a "no revshare" limitation.
- **How HybridShare actually works:** Each agent's capped company dollar funds the pool for THEIR transactions. BP caps at $15K ($7,500 goes to pool). BB caps at $5K ($2,500 goes to pool). The flyer's "Max per BP / Max per BB" columns show what an UPLINE sponsor can earn from one downline on that plan. T1 sponsor earns 31% of the downline's pool contribution: $2,325 from a capped BP, $775 from a capped BB.
- **HybridShare tier percentages verified:** T1 31%, T2 18%, T3-T5 7% each, T6 10%, T7 20%.
- **Tier unlock requirements:** minimum active direct sponsored agents T1=1, T2=4, T3=8, T4=12, T5=16, T6=19, T7=20.
- **Vesting is 3 years per RSU award** (not the 60/80/100% schedule SAA reported).
- **Stock awards use a Badge system** (White/Silver/Gold/Black) tied to annual Core Transactions. BB gets half shares and cannot earn Black Badge.
- **HybridShare restrictions:** no earnings first 90 days, must complete one Core Transaction first, earnings apply to cap before cash payout.

Source: `lpt.com` flyer provided by Joe, valid through 4/30/26, plus direct clarifications. See `data/brokerages.json` for the full structured breakdown.

---

## 1. What SAA actually built (for context, not to copy)

SAA's `/brokerage-comparison/` is a static hub page with hardcoded links to pre-written editorial articles (one per matchup, 100+ total). No data model, no calculator, no multi-way compare. Pure SEO inventory.

TPL will do better: one `/compare` page, structured JSON data model, interactive matrix, GCI slider, up to 5 brokerages at once, shareable URLs. Existing `/vs/*` static article pages stay untouched.

Important note on SAA's figures: several LPT numbers reported by SAA are incorrect (monthly fees, vesting schedule). Do not treat SAA as authoritative for LPT. Use `data/brokerages.json` (verified against the LPT flyer).

---

## 2. Data model

Single file: `data/brokerages.json`. LPT entry is fully populated and verified. Other brokerages currently in `status: draft` pending Claude Code verification.

### 2.1 Schema highlights (see `brokerages.json` for full structure)

New fields in v2.1 to support verified LPT structure:

```json
{
  "per_txn_fee_charged_to": "customer" | "agent",
  "annual_fee_note": "Withheld from first deal each year. Covers technology and E&O.",
  "data_valid_until": "2026-04-30",

  "revshare": {
    "program_name": "HybridShare",
    "tier_breakdown": [
      { "tier": 1, "pct_of_pool": 31, "max_per_txn_bp_usd": 2325, "max_per_txn_bb_usd": 775, "min_active_direct_sponsored_to_unlock": 1 }
    ],
    "restrictions": ["No HybridShare in first 90 days", "..."],
    "dual_sponsorship_note": "45% to each sponsor and respective upline"
  },

  "equity": {
    "stock_type": "RSU awards via Performance Awards program",
    "vesting_years": 3,
    "achievement_awards": [
      { "badge": "White", "annual_core_transactions": 1, "shares_bp": 50, "shares_bb": 25 }
    ],
    "sponsorship_award_per_direct_sponsored": {
      "trigger": "Direct sponsored agent's first Core Transaction (one-time)",
      "shares_bp": 100, "shares_bb": 50
    }
  }
}
```

### 2.2 Required top-level fields

| Field | Values | Purpose |
|---|---|---|
| `status` | `published` / `draft` | Only `published` entries appear in UI. |
| `tier` | `1` / `2` / `3` | Rollout priority. |
| `category` | `cloud` / `franchise` / `luxury` / `discount` / `independent` / `hybrid` | Filter dropdown. |
| `aliases` | string[] | Search synonyms (e.g. "KW"). |
| `data_asof` | ISO date | Verification timestamp. |
| `data_valid_until` | ISO date (optional) | Fine print expiration. Show warning in UI when passed. |

### 2.3 Target 50 brokerages (3-tier rollout)

**Tier 1 - Launch set (~20):** LPT Realty (published), eXp Realty, Real Brokerage, Fathom Realty, Keller Williams, RE/MAX, Coldwell Banker, Century 21, Berkshire Hathaway HomeServices, Better Homes & Gardens, Sotheby's International Realty, Compass, Corcoran, Douglas Elliman, The Agency, Redfin, Realty ONE Group, United Real Estate, HomeSmart, Weichert.

**Tier 2 (~15):** Howard Hanna, Long & Foster, @properties, Engel & Völkers, Christie's International Real Estate, William Raveis, John L. Scott, Windermere, Crye-Leike, Baird & Warner, Ebby Halliday, Watson Realty, Pacific Union, Hilton & Hyland, Nest Seekers International.

**Tier 3 (~15):** Side, Partners Trust, Sereno, Pacific Sotheby's, Harcourts, Dale Sorensen, Smith & Associates, Premier Sotheby's, Intero, Alain Pinel, Allen Tate, Dilbeck, Daniel Gale Sotheby's, plus regional additions.

### 2.4 Data sourcing rules (HARD)

- **LPT numbers** come from `lpt.com` flyer (currently loaded) or subsequent Joe-provided documents. Never fabricate.
- **Competitor figures** from publicly documented sources. `source_url` required.
- **Ranges** (e.g. Compass 60/40 to 90/10) stored as `{ "min": 60, "max": 90, "typical": 75 }`. Calc uses typical.
- **`data_asof`** required on every `status: published` entry. Stale badge after 12 months.
- **`data_valid_until`** when source has an expiration (LPT flyers do). UI shows warning when expired.

---

## 3. UI / UX

### 3.1 Route structure

- `/compare` - main page
- `/compare?brokerages=lpt,exp,kw&gci=250000&txns=20` - shareable deep link
- `/compare?tier=1` - filter to featured set

### 3.2 Page layout

**Header:**
- H1: "Compare Brokerages - Real Numbers, Not Pitches"
- Subhead: "Pick up to 5. See splits, caps, fees, revshare, equity, and total annual cost at your actual production."

**Selection UI:**

```
┌─────────────────────────────────────────────────────┐
│  Selected (3 of 5):                                 │
│  [LPT ×] [eXp ×] [Keller Williams ×]                │
├─────────────────────────────────────────────────────┤
│  Add brokerage:                                     │
│  🔍 [Search by name...___________]                  │
│                                                     │
│  Filter: [All ▾] [Cloud] [Franchise] [Luxury]      │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │  Real Brokerage               Cloud          │  │
│  │  Fathom Realty                Cloud          │  │
│  │  Compass                      Luxury         │  │
│  │  RE/MAX                       Franchise      │  │
│  │  ... (scroll)                                │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

- Autocomplete search over `name` + `aliases`.
- Category filter buttons.
- Results list shows `status: "published"` brokerages only. Sorted by tier then alphabetically.
- Click to add. Max 5. Selected items disabled in list.
- LPT pre-selected on load.
- Mobile: bottom-sheet selector.

**For LPT:** secondary plan toggle (BP / BB / Show Both).

**Inputs panel (sticky on desktop):**
- Slider: Annual GCI ($50K-$1M, default $250K)
- Slider: Transactions/year (1-60, default 20)
- Number input: Avg GCI/txn (auto-calculates, editable)
- Checkbox: "Include LPT Plus upgrade" (default off, adds $89-149/mo)

**Comparison matrix:**

Rows = attributes, columns = selected brokerages.

Row groups:
1. **Overview** - Model, Founded, Public ticker, Data as-of
2. **Cost Structure** - Split, Annual cap, Monthly fee, Annual fee, E&O, Franchise fee, Flat fee per txn
3. **Calculated Total Annual Cost** (highlighted, color-coded)
4. **Net to agent** ($ and %)
5. **Revenue Share** - Program name, Tiers, Pool %, Willable, Vesting, Plan restrictions (e.g. "BB plan not eligible")
6. **Equity / Stock** - Offered, Public, Type, Badge system, Vesting
7. **Technology** - CRM included, Tools
8. **Training & Support** - Mentorship, Support hours, Notable programs
9. **Culture** - Office-based, Community style

**Cost breakdown cards** (one per selected brokerage/plan):

Accurate LPT example with $195 per-txn fee counted as brokerage cost:

```
LPT Business Builder @ $250K GCI, 20 txns
  Flat fees to cap:    $5,000   (10 txns × $500)
  Per-txn brokerage fee: $3,900 (20 txns × $195, default pass-through)
  Monthly fee:         $0       (no monthly fees at LPT)
  Annual fee:          $500     (covers tech + E&O, withheld from first deal)
  ─────────────────────────────
  Total brokerage cost: $9,400
  Net to agent:        $240,600 (96.2% retained)

  Note: The $195 per-txn fee is typically passed through to
  the client at closing, so agent out-of-pocket is often lower
  than this total.

LPT Brokerage Partner @ $250K GCI, 20 txns
  Split to cap:        $15,000  (20% of GCI until $15K cap)
  Per-txn brokerage fee: $3,900 (20 txns × $195)
  Monthly fee:         $0
  Annual fee:          $500
  ─────────────────────────────
  Total brokerage cost: $19,400
  Net to agent:        $230,600 (92.2% retained)

  Plus: Full HybridShare eligibility (up to $2,325/yr per Tier 1 BP downline).
```

**TPL callout** (when LPT is selected):

Dark Luxe panel, gold border. Uses the `tpl_callout` string from the JSON. CTA to `calendly.com/discovertpl`.

**HybridShare section** (when LPT Brokerage Partner is selected, or when user expands "Revenue Share details"):

Below the main matrix, a dedicated panel showing the 7-tier structure pulled from `revshare.tier_breakdown`. Table showing:
- Tier
- % of pool
- Max annual earnings from one BP downline (when they cap)
- Max annual earnings from one BB downline (when they cap)
- Min active direct sponsored to unlock the tier

Explanatory text above the table:
> Each LPT agent's capped company dollar funds the HybridShare Pool for their transactions. A BP agent who caps contributes $7,500 to the pool (50% of $15K). A BB agent who caps contributes $2,500 to the pool (50% of $5K). An upline sponsor earns their tier percentage of that pool contribution.

Note below the table:
> Business Builder agents CAN recruit and build a downline. However, HybridShare earnings only activate once the BB agent upgrades to Brokerage Partner. The downline tree carries over on upgrade, so recruiting activity is not lost.

**Share row:**
- "Copy shareable link"
- "Download as PDF" via print CSS
- GA4 events

### 3.3 Visual design (TPL Dark Luxe - exact colors)

Backgrounds: `#0a0a0f` / `#12121a` / `#1a1a26`
Borders: `#2a2a3d`
Text: `#e8e8f0` / muted `#8888aa` / dim `#55556a`
Purple: `#6c63ff` / Gold: `#f0c040` / Green: `#34d399` / Red: `#f87171` / Amber: `#fbbf24`

Typography: Montserrat 700 headlines, Open Sans 400 body.

**No em dashes in UI copy.**

LPT column: subtle gold left-border accent.

---

## 4. Calculation logic (v2.1 corrected)

```javascript
function calcTotalCost(brokerage, plan, gci, txns, avgGciPerTxn, includeLptPlus) {
  let splitCost = 0;
  let txnBrokerageFees = 0;
  let monthly = (plan.monthly_fee || 0) * 12;
  let annual = plan.annual_fee || 0;
  let eo = plan.eo_insurance_annual || 0;
  let franchise = 0;
  let marketing = 0;

  // Franchise royalty
  if (plan.franchise_fee_pct > 0) {
    franchise = gci * (plan.franchise_fee_pct / 100);
    if (plan.franchise_fee_cap_annual) {
      franchise = Math.min(franchise, plan.franchise_fee_cap_annual);
    }
  }

  // Marketing fee (Compass, etc.)
  if (plan.marketing_fee_pct) {
    marketing = gci * (plan.marketing_fee_pct / 100);
  }

  // Split-based cost with cap (BP model, eXp, etc.)
  if (plan.split_structure && plan.split_structure.includes('/') && !plan.flat_fee_per_txn) {
    const splitPct = parseInt(plan.split_structure.split('/')[0]);
    const brokerageShare = 1 - splitPct / 100;
    const preCapCost = gci * brokerageShare;
    splitCost = plan.annual_cap ? Math.min(preCapCost, plan.annual_cap) : preCapCost;
  }

  // Flat fee per txn (LPT BB model)
  if (plan.flat_fee_per_txn) {
    const txnsToCap = Math.floor(plan.annual_cap / plan.flat_fee_per_txn);
    splitCost = Math.min(txns, txnsToCap) * plan.flat_fee_per_txn;
  }

  // Per-transaction brokerage fee - ALWAYS counted as a brokerage cost.
  // LPT: $195 on every txn. Default pass-through to client is a cash-flow
  // convenience, not a cost offset. The brokerage still charges it.
  if (plan.per_txn_brokerage_fee) {
    txnBrokerageFees = txns * plan.per_txn_brokerage_fee;
  }

  // eXp-style post-cap-only per-txn fees (first 20 only)
  if (plan.post_cap_per_txn_fee && plan.per_txn_fee_applies_to === 'post_cap_only_first_20') {
    const splitPct = parseInt((plan.split_structure || '80/20').split('/')[0]);
    const brokerageShare = 1 - splitPct / 100;
    const capTxns = Math.ceil((plan.annual_cap || 0) / (brokerageShare * avgGciPerTxn));
    const postCapTxns = Math.max(0, Math.min(txns - capTxns, 20));
    txnBrokerageFees += postCapTxns * plan.post_cap_per_txn_fee;
  }

  // LPT Plus optional upgrade (only if user checks the box)
  let optional = 0;
  if (includeLptPlus && brokerage.slug === 'lpt-realty') {
    optional = (plan.plan_name.includes('Business Builder') ? 149 : 89) * 12;
  }

  const total = splitCost + txnBrokerageFees + monthly + annual + eo + franchise + marketing + optional;
  const net = gci - total;
  const retainedPct = (net / gci) * 100;

  return {
    total,
    net,
    retainedPct,
    breakdown: { splitCost, txnBrokerageFees, monthly, annual, eo, franchise, marketing, optional }
  };
}
```

**Key logic:**
- `per_txn_brokerage_fee` is always counted as a cost. UI shows a contextual note about LPT's default pass-through mechanic, but the dollar figure stays in the total for apples-to-apples comparison against other brokerages' per-txn fees.
- Split-based calc excludes plans with `flat_fee_per_txn` (BB is flat, not split).
- `status: draft` entries hidden from selector.

Edge cases:
- Negotiated splits (Compass): range stored, calc uses typical, UI shows range
- No cap: splitCost = gci × brokerageShare
- KW royalty: 6% of GCI capped at $3,000/yr

---

## 5. Tech stack

- Plain HTML + vanilla JS (or Alpine.js)
- CSS custom properties for color tokens
- `data/brokerages.json` fetched on page load, filtered by `status === 'published'`
- No backend
- URL state via `URLSearchParams`
- GA4 events via `gtag('event', 'compare_selection', {...})`

**File structure:**
```
/compare.html
/assets/compare/compare.css
/assets/compare/compare.js
/data/brokerages.json            ← source of truth (LPT verified)
/data/_brokerage-template.json   ← schema template for new entries
/assets/logos/                   ← SVG, monochrome/white for dark bg
```

---

## 6. Data entry workflow

1. Copy `data/_brokerage-template.json`
2. Set `status: "draft"` while populating
3. Required for published: `slug`, `name`, `short_name`, `logo`, `color`, `tier`, `category`, at least one plan, `source_url`, `data_asof`
4. Unknown fields = `null` → renders "—"
5. Flip to `status: "published"` when verified
6. Commit, push, Vercel auto-deploys

---

## 7. Build order

**Phase 1 - MVP (launch with LPT + 4-5 competitors verified):**
1. Use the provided `data/brokerages.json` as-is. LPT is fully populated.
2. Verify and populate eXp, Real, KW, Compass, Fathom (flip `status` to `"published"`).
3. Create `data/_brokerage-template.json`.
4. Build `/compare.html` with searchable selector, category filter, GCI/txn sliders, matrix, cost cards.
5. Implement `calcTotalCost` (v2.1 corrected version).
6. HybridShare panel rendering from `revshare.tier_breakdown` when LPT BP is selected.
7. TPL callout when LPT is selected.
8. GA4 tracking (`G-X6WMCMBJ9R`).
9. Shareable URL params.
10. Nav link to `/compare`.

**Phase 2:**
11. Populate remaining Tier 1 brokerages.
12. Print stylesheet for PDF export.
13. Mobile optimization.
14. "Methodology" modal with per-brokerage source links.
15. `data_asof` stale badge (>12 months), `data_valid_until` expired warning.

**Phase 3:**
16. Populate Tier 2-3 brokerages.
17. HybridShare projection calculator (compound across multiple tiers).
18. Multi-year career projection chart.
19. "Email me this comparison" via `POST /api/leads` (preserve contract).

---

## 8. Hard rules

- **TPL is not LPT.** All UI copy reflects this. The numbers belong to LPT, not TPL.
- **No em dashes in UI copy.** Regular hyphens or rewrite.
- **Exact brand colors only.**
- **Clean URLs.** `/compare`, not `/compare.html`.
- **Never fabricate LPT figures.** If the flyer doesn't state it, set `null`.
- **Per-txn brokerage fees always count as brokerage cost in the calc.** LPT's $195 pass-through mechanic is a cash-flow convenience, not a cost reduction. For comparison against other brokerages' per-txn fees, it must always be in the total. UI may add a note explaining the pass-through, but the total figure stays consistent.
- **Business Builder plan eligibility:** BB agents CAN recruit and build a downline. HybridShare earnings activate on upgrade to BP. Never describe BB as having "no revshare" - describe it as "build now, earn on upgrade."
- **Preserve `POST /api/leads` contract** in Phase 3.
- **Confirm with Joe before merging to `main`** (Vercel auto-deploys).
- **GA4:** `G-X6WMCMBJ9R`. **CTA:** `calendly.com/discovertpl`.
- **Only `status: "published"` entries appear in UI.**

---

## 9. Tone / copy

- Headlines: neutral authority, math-driven.
- No superlatives without numbers.
- LPT is "the brokerage," not "our brokerage."
- The comparator is a tool. TPL callout at the bottom is the soft handoff.

---

## 10. Open items

- LPT stock award multipliers by join date / comp plan / benefits plan (flyer mentions these exist but does not list specifics)
- Full list of Black Badge leadership/community engagement requirements (currently waived)
- Logo assets (monochrome white preferred for dark bg)
- Phase 3 lead capture scope decision

---

## 11. Out of scope

- Editorial comparison articles
- Backend/database
- CMS or admin page (GitHub PR workflow)
- Agent reviews aggregation
- Real-time stock feeds
- i18n
- User-submitted brokerages
