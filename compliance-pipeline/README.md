# Region 1 Compliance Pipeline Tracker

Internal tool for Georgette (Region 1 Compliance Lead, LPT Realty). Two static HTML pages backed by Supabase. Replaces the twice-a-day Excel workflow with a dashboard she can glance at.

**Important:** this tool does **not** integrate with Connect / SmarterTrack. Numbers are entered manually (AM + PM), by design, so no IT flags.

---

## File map

```
compliance-pipeline/
├── index.html        # Entry form
├── dashboard.html    # Weekly dashboard
├── schema.sql        # One-time Supabase setup
└── README.md         # You are here
```

---

## One-time setup

### 1. Create a fresh Supabase project

1. Go to [supabase.com](https://supabase.com) and create a new project (keep it isolated — do not reuse TPL or Thunder credentials).
2. Note the project URL (e.g. `https://abcdxyz.supabase.co`) and the **anon public** key from **Project Settings → API**.

### 2. Run the schema

1. Open the **SQL Editor** in Supabase.
2. Paste the contents of `schema.sql`.
3. Run it. You should see the `compliance_entries` table created with RLS enabled and a permissive anon policy.

### 3. Wire credentials into the HTML

Both `index.html` and `dashboard.html` have two placeholder strings at the top of their `<script type="module">` blocks:

```js
const SUPABASE_URL = 'SUPABASE_URL_PLACEHOLDER';
const SUPABASE_ANON_KEY = 'SUPABASE_ANON_KEY_PLACEHOLDER';
```

Find-and-replace both placeholders in **both** files with your real values. No env vars, no build step.

### 4. Deploy to GitHub Pages

1. Push this repo (or just the `compliance-pipeline/` folder) to `jdesane/<repo>`.
2. In the repo **Settings → Pages**, set the source to the branch (and `/root` or `/docs` as appropriate).
3. Bookmark:
   - Entry: `https://jdesane.github.io/<repo>/compliance-pipeline/`
   - Dashboard: `https://jdesane.github.io/<repo>/compliance-pipeline/dashboard.html`

---

## How Georgette uses it

### AM pull (~morning)

1. Open Connect → Transactions → Transaction Status Page → **Pre-Compliance**.
2. Filter State = Florida + Georgia (skip Tennessee — no TN compliance).
3. For each of the four date filters, copy the count:
   - Next 3 business days → **Rush 3-Day**
   - Today → **Today**
   - Tomorrow → **Tomorrow**
   - Day after → **Next Day**
4. Switch to Transaction Status Page → **Funds In Compliance Pending**, same FL+GA filter, no date filter → **Funds In**.
5. Open the Entry page. Date defaults to today. AM is auto-selected before noon. Type the 5 numbers. Save.

### PM pull (~afternoon)

Same drill. Toggle to PM. The form will pre-fill if she's already saved a PM entry for today — she can just update it.

### Dashboard

Glance at `dashboard.html`. Arrows navigate weeks. KPIs show the latest snapshot. Week table shows AM Start / PM End / Cleared per weekday. Charts break down the latest rush and the daily cleared trend.

---

## Notes on the math

- **Pipeline Total** = Rush 3-Day + Funds In.
- **Cleared** (per day) = AM Pipeline Total − PM Pipeline Total. A floor, not exact — new files get added through the day, so the real cleared number is likely higher. The dashboard flags this at the top.
- **Week starts Monday.** Weekends are skipped (M–F only).
- **"Latest"** = most recent entry in the displayed week, PM before AM on the same day.

---

## Out of scope for v1

- No login / password gate (single-user internal tool, RLS is permissive for anon)
- No multi-region support
- No CSV export
- No true-cleared math (would need a "files added today" input)
- No Connect integration (deliberate — keeps IT out of it)

If she gets value from it for a month and wants more, iterate then.
