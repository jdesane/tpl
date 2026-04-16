# Region 1 Compliance Pipeline Tracker

Internal tool for Georgette (Region 1 Compliance Lead, LPT Realty). Two static HTML pages backed by the existing TPL Supabase. Replaces the twice-a-day Excel workflow with a dashboard she can glance at.

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

This tool piggybacks on the existing **TPL Supabase** project (`zyonidiybzrgklrmalbt`). Credentials are already baked into both HTML files — no swap needed.

### Run the schema (once)

1. Open the TPL Supabase project → **SQL Editor**.
2. Paste the contents of `schema.sql`.
3. Run it. Creates `compliance_entries` with RLS + anon policy. Uses `if not exists`, so safe to re-run.

### Deploy

This folder lives in the marketing repo (`jdesane/tpl`), which Vercel auto-deploys on push to `main`. Once merged, the pages are live at:

- Entry: `https://tplcollective.ai/compliance-pipeline/`
- Dashboard: `https://tplcollective.ai/compliance-pipeline/dashboard.html`

(Swap the domain for whatever Vercel domain the repo deploys to — if it's only on the `*.vercel.app` preview, use that.)

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
