# TPL Project

## Infrastructure
- **Database**: Supabase (Postgres) — project `zyonidiybzrgklrmalbt`, region us-west-2
  - 37 tables including: leads (187), activity_log, emails_sent, drip_queue, users, agents, tasks (1,588), onboarding_steps, resources, email_queue, referrals, recruiting_links (40), content_posts, lead_stage_history, revshare_entries, automation_runs, automation_settings, goals, lead_notes, lead_activity, email_funnels, email_funnel_steps, email_funnel_enrollments (239), pipelines, opportunities (188), smart_lists, contact_communications, email_suppressions, email_send_log (24,804), email_daily_limits, buyer_intake_submissions, ideas, prospects, activities, recruiting_tasks, newsletter_subscribers, newsletter_issues
  - RLS enabled on all tables, service role policies for backend access
- VPS at 187.77.213.230 runs Mission Control in Docker (`/docker/mission-control/`)
- FastAPI backend — modular: `main.py`, `auth.py`, `models.py`, `extended_routes.py`, `report_generator_v2.py`, `coaching.py`
- Traefik: SSL, basic auth for Mission Control UI, all `/api` routes use JWT auth, portal has no basic auth
- **Deploy**: `docker compose build && docker compose up -d` (static files baked into image at build time)

## Environment Variables
- **Vercel** (marketing site): `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `RESEND_API_KEY`
- **VPS Docker** (Mission Control): `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `JWT_SECRET`

## Auth System
- JWT-based auth via `auth.py` (PyJWT + passlib/bcrypt)
- Joe's admin account: joe@tplcollective.ai (password: TplMission2026)
- 7-day token expiry, role-based access (admin/agent)
- Login: POST /api/auth/login returns JWT + user object

## API Endpoints
- **Auth**: login, me, set-password
- **Leads**: full CRUD with lead_score, ai_draft, stage, temperature, /stats, /hot, backward-compatible POST
- **Contacts**: CRUD + profile views, status management, column picker, communications log
- **Tasks**: CRUD + /today (powers "Today's Actions")
- **Agents**: CRUD + /stats, /leaderboard, /tree, onboarding steps auto-created
- **Dashboard**: /overview, /funnel, /growth, /pipeline-health, /tasks-today
- **Resources**: CRUD + download tracking
- **Referrals**: CRUD with agent relationships
- **Recruiting Links**: CRUD + click tracking (40 seeded)
- **Content Posts**: CRUD + calendar view
- **Pipelines & Opportunities**: CRUD, pipeline management (188 opportunities tracked)
- **Email Funnels**: CRUD + steps + enrollments (18 funnels, 48 steps, 239 enrollments)
- **Email**: /queue, /stats, /send-log, /daily-limits, /suppressions, open tracking pixel
- **Smart Lists**: CRUD (7 saved filters)
- **Lead Notes & Activity**: CRUD (112 notes, 1,254 activity entries)
- **AI Actions**: score-leads, who-to-call, draft-dm, weekly-plan, generate-tasks, generate-content, generate-image
- **Drip**: process, status, cancel
- **Webhooks**: POST /api/webhooks/calendly, POST /api/webhooks/resend
- **Newsletter**: subscribers + issues CRUD (4 issues)
- **Ideas Inbox**: CRUD (PWA at /ideas)
- **Automations**: automation_runs, automation_settings (daily briefing, hot alerts)
- **Settings/Notifications**: Resend API key, notification toggles

## Mission Control Dashboard (mission.tplcollective.ai)
- **Dashboard**: 5 metric cards, recruiting funnel, hottest leads, Today's Actions, pipeline health gauge, 4 AI quick-action buttons, activity feed, system status
- **Contacts/Leads**: full CRM with column picker, profile views, status dropdown, stage management, lead notes, activity timeline, communications log, unsubscribe flow with auto-tag
- **Pipeline**: kanban board with opportunities (188 tracked)
- **Email Funnels**: 18 funnels with 48 steps, 239 enrollments, visual builder
- **Smart Lists**: 7 saved filtered views
- **Agents**: stats cards, agent table with production/engagement, Add Agent with auto-onboarding
- **Email System**: send log (24,800+ tracked), daily rate limits, suppression list, open/click tracking
- **Content Hub**: social post grid with create/edit, 30-day content calendar
- **Recruiting Links**: brokerage filter dropdown, grouped link tables with Copy button
- **Ideas Inbox**: capture and track business ideas
- **Newsletter**: subscriber management + issue tracking
- **AI Generators**: Email Writer, Content Generator (multi-model), Image Generator (DALL-E 3)
- **Automations**: daily morning briefing (4 AM EST), hot lead alerts, 1,262 automation runs logged
- **Settings**: notification toggles, Resend API key, automation config

## Agent Portal (portal.tplcollective.ai)
- JWT login page (agents use own credentials)
- Dashboard: onboarding progress ring, checklist with toggle-to-complete, referrals summary, quick access cards
- Resources: downloadable resource vault
- Referrals: tracker table + refer form
- Community: Discord invite + Book 1-on-1 with Joe
- LPT Tools: external links to Lofty CRM + Dotloop
- DNS: portal A record -> 187.77.213.230 (done, SSL auto-provisioned via Traefik)

## Local site (this repo)
- Static marketing site deployed via Vercel (auto-deploy on push to main)
- `api/leads.js` — Vercel serverless function, writes leads directly to Supabase
- `api/fetch-title.js` — Vercel serverless function, fetches page titles
- `package.json` — has `@supabase/supabase-js` dependency
- `tpl-tracking.js` — custom visitor tracking script loaded on all pages
- `downloads/` — 8 PDF resources (20-questions, tax-deductions, buyer-checklist, listing-checklist, 90-day-plan, open-house-sign-in, soi-tracker, 27k-worksheet)
- `social-graphics/` — Puppeteer-based social media graphics generator
- Key pages: index, why-tpl, fee-plans, lpt-explained, commission-calculator, 27k-worksheet, resources, join, join-lpt-realty, revshare, two-lanes, franchise-fees, brokerage-fees, privacy-policy, 404, fb-post-scheduler, ideas/index
- Comparison pages: vs/keller-williams, vs/exp-realty, vs/exp-switch, vs/coldwell-banker, vs/century-21, vs/real-brokerage, vs/remax, vs/epique-realty, vs/compass, vs/homesmart, vs/berkshire-hathaway, vs/index (hub) — 11 comparison pages total
- Blog articles (blog/): lpt-vs-exp-realty, lpt-vs-keller-williams, lpt-vs-real-brokerage, lpt-vs-coldwell-banker, lpt-vs-epique-realty, lpt-vs-century-21, how-to-switch-brokerages, commission-splits-explained, what-is-a-cap-in-real-estate, cloud-brokerage-vs-traditional, hidden-brokerage-fees — 11 blog posts total
- Blog index (blog.html) with filter tabs, comparison + guide categories

## Build Plan (v2 Architecture) — ALL COMPLETE
- Session 1: Database migration (13 Supabase tables, 40 recruiting links seeded) ✅
- Session 2: Core API (auth, leads, tasks, agents, dashboard) ✅
- Session 3: Extended API + AI actions (resources, referrals, content, lead scoring, draft DM, weekly plan) ✅
- Session 4: Mission Control frontend — Dashboard + Leads ✅
- Session 5: Mission Control frontend — Agents, Drips, Content Hub, Recruiting Links ✅
- Session 6: Agent Portal (login, onboarding, resources, referrals, community) ✅
- Session 7: Traefik routing, end-to-end testing (14/14 tests pass) ✅

## Phase 3 — Content Pages ✅
- join.html, revshare.html, two-lanes.html, franchise-fees.html, brokerage-fees.html
- vs/exp-switch.html (eXp refugee page)
- Updated vs/keller-williams.html ($17,883 math)
- Updated lpt-explained.html (Deloitte, Dezzy.ai, awards)

## Phase 4 — Competitor Hub + Calendly Webhook ✅
- vs/remax.html, vs/index.html (comparison hub)
- POST /api/webhooks/calendly — auto-creates/updates leads on Calendly bookings
- Supports invitee.created and invitee.canceled events
- Optional HMAC signature verification via `calendly_signing_key` in settings.json
- To activate: set Calendly webhook URL to `https://mission.tplcollective.ai/api/webhooks/calendly`

## Phase 5 — CRM & Automation Expansion ✅
- Full contacts system with column picker, profile views, status management, unsubscribe flow
- Opportunities & Pipelines (188 opportunities tracked)
- Email Funnels system (18 funnels, 48 steps, 239 enrollments)
- Smart Lists (7 saved filters)
- Email rails: suppression list, daily rate limits, send logging (24,800+ sends), unsubscribe with auto-tag
- Daily morning briefing automation (4 AM EST)
- Hot lead alerts
- Ideas Inbox with PWA capture form at /ideas
- Newsletter system (subscribers + 4 issues)
- AI generators: Email Writer, Content Generator (multi-model), Image Generator (DALL-E 3)
- Visitor tracking + calculator gate bypass
- Short URLs + dedup activities + email engagement tracking
- Facebook ad copy + Google ad copy + 30-day content calendar
- Meta Pixel + Google Ads conversion tags on all pages
- Privacy policy page for Meta app approval
- Database expanded from 13 to 37 tables

## Phase 6 — SEO Content Expansion + Cross-Linking ✅
- 3 new comparison pages: vs/compass, vs/homesmart, vs/berkshire-hathaway
- 5 new SEO blog articles: how-to-switch-brokerages, commission-splits-explained, what-is-a-cap-in-real-estate, cloud-brokerage-vs-traditional, hidden-brokerage-fees
- Updated vs/index.html hub with 3 new comparison cards (now 11 total)
- Updated blog.html with Agent Guides section (5 new cards)
- Cross-linked 6 existing pages (index, fee-plans, lpt-explained, why-tpl, join, revshare) with new content
- Added REAL Brokerage, HomeSmart, Epique to homepage lead form brokerage dropdown
- All pages include GA (G-X6WMCMBJ9R), Google Ads (AW-11351310286), Meta Pixel (34463024060012400)
- All competitor numbers marked [VERIFY] for manual review

## Phase 7 — Meta Ads + Lead Pipeline ✅
- Meta ad campaign "TPL Agent Recruiting - April 2026" live at $30/day
- Ad 1A "The 30% Reality" targeting KW agents via Advantage+ with KW employer suggestions
- KW Commission Comparison instant form (Form ID: 2446350272487229)
- POST /api/webhooks/meta-leads — receives Meta leadgen webhooks, fetches lead data via Graph API
- GET /api/webhooks/meta-leads — handles Meta webhook verification challenge
- Auto-detects brokerage from form/campaign name (KW, eXp, RE/MAX, C21, Coldwell Banker)
- Creates opportunity in LPT Recruiting pipeline at new_fb_lead stage
- Auto-enrolls in brokerage-specific email funnel
- "Commission Comparison - KW" email funnel (7 emails over 21 days, funnel ID 20, trigger: new_fb_lead_kw)
- Permanent Meta Page Access Token (never expires) stored in VPS settings
- GHL/LeadConnector fully disconnected from Meta
- Tpl Collective App (911974931609986) webhook subscribed to Page leadgen events
- sync_meta_leads.py cron backup (every 15 min) polls Meta Graph API for missed leads
- Deleted Meta lead emails tracked in settings to prevent sync re-import

## Phase 8 — Contact Enrichment + CRM UX ✅
- Apollo.io API integration (API key in VPS settings, Basic plan with 2,505 credits)
- POST /api/leads/{id}/enrich — Apollo enrichment preview (no auto-apply)
- POST /api/leads/{id}/enrich-web — web-based real estate enrichment via DuckDuckGo search
- POST /api/leads/{id}/enrich-apply — apply user-approved fields only
- Web enrichment finds: Realtor.com, Zillow, Facebook, LinkedIn, FL license lookup URLs
- Enrich button runs Apollo + Web search in parallel, shows combined preview modal
- Preview modal: side-by-side current vs found values, source labels, clickable URLs, checkbox approval
- Empty fields pre-checked, existing fields unchecked to prevent overwrites
- Delete button on contact profile view (clears all related records: enrollments, opportunities, activity, notes, drip)
- Bulk actions on contacts page: select all, bulk delete, bulk status update, bulk tag, bulk enrich
- Date Added column (sortable, default visible)
- Delete function fixed: clears FK-constrained records before deleting lead

## Phase 9 — Unsponsored Agent Capture Funnel ✅
- New `/joining-lpt-realty` long-form landing page (complete LPT joining guide)
- Social-proof strip, author bio block (Joe DeSane), verdict banner, TOC
- Inline comparison table: LPT vs KW/eXp/REMAX (structural, per-deal numbers marked [VERIFY])
- Mid + bottom lead magnet forms (Sponsor Checklist PDF)
- Expanded FAQ with objection-handling entries ("I already have a sponsor", "Not ready yet", "Only KW/eXp?", "What happens after download?")
- Sticky mobile CTA bar (shows after 25% scroll, hides near forms)
- Exit-intent modal (desktop: mouseleave top; mobile: 45s dwell + 70% scroll)
- Token-gated PDF delivery: api/leads.js generates UUID token, stores in magnet_deliveries, sends download email via Resend, enrolls in Research Stage funnel
- api/download.js validates token, serves PDF from private-assets via Vercel includeFiles, stamps downloaded_at
- vercel.json redirects /private-assets/* to /joining-lpt-realty to block direct access
- `/thanks` thank-you page with inline Calendly embed, ?n=&e= personalization, 3-step next-steps grid
- GA4 events: form_start, generate_lead, magnet_requested, scroll_depth, sticky_cta_click, exit_intent_shown, calendly_click (with cta_location), magnet_thank_you_viewed + AW conversion
- 8-page branded Sponsor Checklist PDF (reportlab, Montserrat Black/Bold headings, Dark Luxe palette) at /downloads/lpt-sponsor-checklist.pdf + /private-assets/lpt-sponsor-checklist.pdf
- OG image 1200x630 (Puppeteer render) at /og/joining-lpt-realty.jpg
- JSON-LD: Article + FAQPage schema
- Inbound linkbacks added to: index.html, why-tpl.html, fee-plans.html, lpt-explained.html, vs/index.html, and 11 /vs/*.html pages
- Supabase migration: leads.stage/magnet/magnet_downloaded_at columns, magnet_deliveries table
- Research Stage email funnel (id 22) with 6 steps (days 2,4,6,9,12,14), trigger_stage='research'
- 7 drip email drafts in content/drips/research-stage/ (day-0 delivered direct from Vercel, days 2-14 via funnel)
- sitemap.xml updated with /joining-lpt-realty (thanks page is noindex)

## Phase 10 — Contact Sequences Tab + Lead Activity Timeline ✅
- GET /api/leads/{id}/enrollments returns funnel name, step progress, status, next-send ETA
- POST /api/leads/{id}/stop-drips pauses all active enrollments in one call
- POST /api/enrollments/{id}/pause and /resume for per-funnel control
- Contact profile SEQUENCES tab (was empty) now renders enrollment cards with status badge, progress bar, next-step ETA, and Pause/Resume buttons
- "Stop All Drips" button appears above enrollments list when any are active
- api/leads.js logs form_submission + magnet_requested + funnel_enrolled to lead_activity on every submission
- api/download.js logs magnet_downloaded when PDF is pulled
- Calendly webhook logs meeting_booked / meeting_canceled to lead_activity
- New activity icons in profile timeline: 📅 meeting_booked, ❌ meeting_canceled, 📥 magnet_requested, 📄 magnet_downloaded, ✉️ funnel_enrolled, ⏸️ drips_paused, ▶️ drips_resumed

## Phase 11 — Newly Licensed PBC Campaign ✅
- Imported 124 recently licensed Palm Beach County agents (April 2026 subscription list) from `New agent list.xlsx`
- Names normalized: "LAST, FIRST MIDDLE" → "First Last" (title case, middle names dropped, Mc/hyphen/apostrophe preserved)
- Leads stored with: stage="NEWLY LICENSED", source="PBC New License List - April 2026", market="Palm Beach County", license_state="FL", licensed_since="2026-04", license_type="Sales Associate"
- Tags: `newly-licensed`, `palm-beach-county`, `april-2026-list`, `no-brokerage-yet`, `purchased-list`
- Deduped against existing 400+ leads before import; 1 intra-list duplicate removed (125 → 124)
- Email funnel id 23 "Newly Licensed FL - First Sponsor", trigger_stage="NEWLY LICENSED", 6 steps over 20 days
  - Day 1: Congrats + Sponsor Checklist magnet ({{magnet_url}})
  - Day 4: "The first mistake I see new agents make" (split-optimization trap)
  - Day 8: "What a sponsor should actually do for you" (7 must-haves)
  - Day 12: "The monthly-fee trap" ($99 vs $1,800-$14k year-one math)
  - Day 16: "How LPT works in year one (no hype version)" (structural)
  - Day 20: "Want me to review your top 2 sponsor options?" (Calendly soft invite)
- Drafts in `content/drips/newly-licensed/` (day-1, day-4, day-8, day-12, day-16, day-20)
- Enrollments staggered over 19 days (2026-04-22 → 2026-05-10) at 6-7 leads/day to protect sender reputation
- 124 enrollments inserted directly (current_step=0, status='active', enrolled_at = 10am ET + day_offset)

## Phase 12 — Brokerage Comparator /compare ✅
- **Phase A/B**: New unified comparator at `/compare` (compare.html + assets/compare/*) replacing the gated commission-calculator.html flow
  - Source data in `data/brokerages.json` (20 published brokerages + LPT BP + LPT BB)
  - Client-side calcTotalCost handles splits, caps, per-txn fees, franchise royalty, marketing fee, flat-fee-per-txn, post-cap-only-first-20 (eXp), LPT Plus optional addon
  - URL-persisted state (brokerages, gci, txns, plan, plus, cat, growth) for shareable comparisons
  - Optional price/rate/deals accordion derives GCI from sale price × rate × deals
  - Opt-in "Email me this comparison" modal (name/email/phone) posts to Supabase via /api/leads
  - Mission Control tracking POST to `https://mission.tplcollective.ai/api/tracking/calculator` via navigator.sendBeacon
  - Soft-launch banner on old commission-calculator.html points to /compare
  - Cross-promo sweep: fee-plans.html, join.html, vs/index.html CTAs all point to /compare
- **Phase C**: Two wedge panels
  - Cap Break-Even: per-brokerage cards showing cap, break-even point (GCI or deals), color-coded progress bar
  - 3-Year Projection: growth slider (0-30%), year-by-year table with Δ vs LPT BP baseline
- **Phase D**: State filter + persona quiz
  - State dropdown in selector controls (FL, CA, TX, NY, AZ, VA, MD, DC, NC, SC); nationwide brokerages always show
  - `markets` field added to every brokerages.json entry (most: ["nationwide"], samson: VA/MD/DC/WV, lokation: FL/NC/SC)
  - 5-step persona quiz modal with progress bar; bump-based scoring across brokerage slugs; top 5 matches auto-selected on Apply
- **Phase E**: Matchup generator → 9 new /vs/ pages
  - `tools/matchup-generator/generate.py` reads brokerages.json, skips 10 hand-crafted pages, emits templated pages with nav, hero, verdict, structural comparison table (LPT BP | LPT BB | competitor), who-wins cards, 6-question FAQ, citations, CTA, JSON-LD Article + FAQPage schemas
  - 9 new pages: fathom-realty, sothebys, douglas-elliman, the-agency, redfin, realty-one-group, united-real-estate, samson-properties, lokation
  - vs/index.html updated with 9 new cards (20 total comparisons)
  - sitemap.xml updated with 9 new /vs/ URLs + 4 new blog URLs
- **Content**: 4 new SEO blog articles
  - `/blog/cap-break-even-explained` — explains split-cap vs flat-fee break-even math, worked examples, per-brokerage break-even table
  - `/blog/switching-brokerages-risk-checklist` — 12-item operational checklist (pending deals, referrals, MLS, sponsor vetting, tech stack)
  - `/blog/fl-top-5-brokerages` — LPT/eXp/KW/Compass/LoKation structural comparison for Florida agents
  - `/blog/cloud-brokerages-compared-2026` — LPT vs eXp vs REAL vs Fathom side-by-side economics + revenue share
  - Generator: `tools/blog-generator/generate.py` uses shared template (nav, hero, verdict banner, TOC, article body, CTA block, footer, JSON-LD Article)
  - blog.html index updated with 4 new Guide cards
  - All blog content em-dash-free per Joe's rule

## Phase 13 — Multi-Tenant Foundation ✅
- See [project_multi_tenant.md](memory/project_multi_tenant.md) for full Phase 13 architecture
- workspaces table, db() wrapper for tenant scoping, JWT carries workspace_id+plan
- Plan tiers basic/mid/elite, /api/admin endpoints, impersonation

## Phase 14 — Comparator V2: Custom Brokerages + Recruit Tool + Rich PDF ✅
**Public /compare upgrades:**
- "Don't see your brokerage?" pinned card + custom brokerage modal: agent inputs splits / cap / fees / royalty for any unlisted shop, plugs into the same matrix / breakdown / cap break-even / 3-yr projection. Edit pencil reopens prefilled. Multiple customs allowed.
- "Your Numbers" inputs reworked: avg sale price + avg commission % + deals/year (replaces standalone GCI slider). GCI auto-derived.
- LPT Equity Bonus panel — cumulative shares earned by unit count (White + Silver + Gold + Black). Awards STACK (3 txns = White+Silver = 100/50; 15 txns = +Gold = 700/350; 35 txns = +Black = 2,500/350). 3-year projection sums earned badges per year. Source: official lpt.com flyer (valid 4/30/26).
- Email-share modal now actually sends email (was previously fake-success). Saves full snapshot to recruit_comparisons table; "View Full Comparison" link uses /compare?report=<token> so the recipient gets the exact saved state including custom brokerages (URL state can't encode them).
- Rich 5-page branded PDF attached to the email: header + Your Numbers + Cost Comparison summary; Side-By-Side detail table (model, founded, ticker, plan, splits, caps, fees, royalty, totals, retained %); Where Every Dollar Goes per-brokerage breakdown cards; The Bigger Picture page (cap break-even with progress bars + 3-yr projection table + LPT equity ladder + HybridShare 7-tier table). Per-page footer with source citation + page X of N.

**Mission Control Recruit Comparison Tool:**
- New nav item under Marketing → Recruit Comparison
- Form: recruit info, multi-select competitors, "Add custom brokerage", GCI/txns, LPT plan, +Plus, sender personal email (auto-prefills from logged-in user)
- POST /api/recruit-comparisons creates row + lead (assigned_to=sender) + sends Resend email from "<Sender> via TPL Collective <comparisons@tplcollective.ai>" with reply-to set to sender's personal email + same rich 5-page PDF attached
- Recipient lands on /compare?report=<token>; report-mode hides selectors/inputs/quiz, shows "Comparison prepared for X by Y" banner, increments view count, logs comparison_viewed to lead activity
- Right-side panel on the MC page lists recent comparisons with sent/viewed status

**Schema additions:**
- `recruit_comparisons` table: share_token UUID, created_by_user_id, recruit_first/last/email/phone, recruit_lead_id FK, current_brokerage_name, selection JSONB, gci/txns/avg_gci_per_txn, lpt_plan/lpt_plus, comparison_result JSONB, email_sent_at/email_resend_id/email_status, viewed_at/viewed_count, RLS service-role policy

**Architecture:**
- `api/_lib/comparison-calc.js` — shared JS calc module mirroring compare.js math; loads /data/brokerages.json; buildReportData() builds the full PDF payload from raw inputs
- `api/_lib/comparison-pdf.js` — pdfkit-based PDF generator (LETTER, dark Luxe theme, bufferPages, footer pinned to page 0 within bottom margin)
- `api/compare-share-email.js` — public endpoint, saves snapshot + sends email + attaches PDF; returns share_token + token_url
- `api/generate-comparison-pdf.js` — public Vercel endpoint, returns base64 PDF; called by MC's recruit-comparison flow via httpx (follow_redirects=True)
- `mission-control/app/main.py`: send_email() supports `attachments` param; POST /api/recruit-comparisons fetches PDF from Vercel before sending

## Phase 14.1 — Rail 3 Closure ✅
- Email validation rail was missing on the live `/api/webhooks/meta-leads` endpoint — bad email `bieker1@gmail.com1` (Meta autofill bug) created duplicate lead 482. Merged into canonical 318 (lead_activity + email_send_log repointed, duplicate opportunity + cancelled enrollment removed, full snapshot archived to activity_log).
- Added shared `is_valid_email()` regex helper to main.py and sync_meta_leads.py
- Gated 4 insert paths: webhook direct-POST, webhook entry/changes loop, `_create_meta_lead()` entry, sync backfill loop
- Malformed emails skipped + logged as `webhook_validation_error` / `sync_validation_error`
- Verified: 0 malformed emails remain in leads table

## Phase 15 — Coaching Platform Foundation ✅ (Session 1)
**Goal:** Build a real-estate coaching practice operating system inside Mission Control. Coach (Joe) sets agents' goals, builds business plans, tracks pace, runs accountability calls. Clients are TPL contacts flagged as coaching clients — one source of truth, one CRM.

**Architecture:** New module inside the existing TPL stack rather than a standalone app. Coaching tables live alongside the 37 existing tables. Coaching clients FK to `leads` (every client is also a CRM contact). Workspace-scoped via `db()` wrapper.

**Schema (migration `2026-05-01-phase-15-coaching-foundation.sql`):**
- 21 new tables, all RLS-enabled with service-role policy + `updated_at` triggers
- Spine: `coaching_clients` (FK→leads UNIQUE, optional FK→users for portal login, brokerage/comp plan/cadence/license/market/ASP/comm rate/status)
- Plan: `business_plans` (one per client per year), `budget_models`, `economic_models`, `lead_gen_models`, `lead_sources`, `wealth_goals`, `org_models`
- Goal cascade: `gps_goals` / `gps_priorities` / `gps_strategies`, `four_one_ones`
- Execution: `perfect_weeks`, `pipeline_entries` (1-10 rating), `contact_touches`, `coaching_activity_logs`
- Coaching surface: `coaching_calls`, `coaching_action_items`, `review_snapshots`
- Recruiting: `coaching_recruits` (HybridShare downline), `recruiting_plans`
- Workspace-scoped tables added to `TENANT_TABLES` so `db()` auto-filters

**Backend (`mission-control/app/coaching.py` — new file, wired into main.py via `setup(db, supabase)` + `app.include_router`):**
- `GET /api/coaching/clients` — list (workspace-scoped, lead-enriched)
- `GET /api/coaching/clients/{id}` — detail
- `POST /api/coaching/clients` — create from existing lead (`lead_id`) or new contact (`new_contact: {first_name,last_name,email,phone,current_brokerage}`); auto-creates current-year business plan + budget_model + economic_model + lead_gen_model with seeded defaults
- `PATCH /api/coaching/clients/{id}` — update metadata; commission rate auto-normalized from "2.5" or "0.025"
- `DELETE /api/coaching/clients/{id}` — removes coaching_client row (lead remains)
- `GET /api/coaching/clients/{id}/plan?year=YYYY` — returns the bundle, auto-creating if missing
- `PATCH /api/coaching/clients/{id}/plan` — update gci_target / notes
- `PATCH /api/coaching/clients/{id}/budget-model` — update Budget Model
- `PATCH /api/coaching/clients/{id}/economic-model` — update Economic Model
- `GET /api/coaching/clients/{id}/computed?year=YYYY` — full derived numbers (Cost of Sale, Net Income, Survival, Listings Taken, Buyer Consults, Listings to Carry, Lead Gen gaps, etc.) every value carries its `formula` string for the UI's audit popovers
- `GET /api/coaching/lead-search?q=` — autocomplete for the Invite modal; filters out leads already linked to a coaching client

**Math (mirrors MREA workbook exactly):**
- Per week = annual ÷ 48 (NOT 52 — accounts for vacation/holidays per legacy spreadsheet)
- Required Met DB = Met sales × 12 ÷ 2 (12 touches/yr, 2 contacts per sale)
- Required Haven't-Met DB = Haven't-Met sales × 50
- Survival closings = (annual personal + op exp) × 1.30 ÷ avg net commission per close
- LPT cap defaults: $5K Business Builder, $15K Brokerage Partner — auto-fills `paid_to_brokerage` based on the client's `lpt_comp_plan`
- Verified end-to-end: $350K GCI / $400K ASP / 2.5% comm / 60-40 split → 35 closings, 31.7 listing appts/yr, 0.66 listing appts/wk, $175K seller revenue ✓

**Frontend (Mission Control `static/index.html`):**
- New "Coaching" nav group with "Coaching Clients" item (between Marketing and Capture)
- New `<div id="page-coaching">` page: list view (4 metric cards + table with name/brokerage/plan/cadence/status pill) and detail view
- "+ Invite Client" modal with two tabs: Existing Contact (autocomplete via `/api/coaching/lead-search`) + New Contact (creates lead + coaching_client in one POST)
- Detail view: profile strip (brokerage, comp plan, cadence, license date, ASP, commission, market) + tabs (Plan live; Calls/Pipeline/Activity/Recruiting stubbed for next session)
- Plan tab: Income Target panel + Economic Model panel (10 inputs + 13 derived cards) + Budget Model panel (cost of sale + dynamic operating expense rows + allocation %s + dynamic personal expense rows + survival inputs + 13 derived cards)
- Auto-save on blur for every input; computed cards re-fetch + re-render after each save
- Every derived card has `title="formula"` for hover-to-audit
- Status dropdown (Active/Paused/Churned) in the detail view header

**Deploy:** files rsynced to VPS (`main.py`, `coaching.py`, `static/index.html`); backed up as `*.pre-phase15-{ts}`; rebuilt Docker image; container booted clean. Live at `https://mission.tplcollective.ai` → click **Coaching** in sidebar.

## Phase 15.2 — Coaching: Calls + Action Items + Pipeline + Activity ✅ (Session 2)
**Goal:** Build the killer feature — coaching call workflow with auto-generated pre-call brief — plus the supporting pipeline + activity data sources that feed it.

**Backend (`coaching.py` extended, no new tables — all schema already in place from session 1):**
- `GET/POST/PATCH/DELETE /api/coaching/clients/{id}/pipeline` + `/api/coaching/pipeline/{id}` — listing + buyer entries with 1-10 rating; closed flag with closing_price + gross_commission feed GCI YTD
- `GET/POST /api/coaching/clients/{id}/activity` — daily log with upsert on `(client_id, log_date)`; streak counter helper `_activity_streak()` walks logs back from today, breaks on first day below target contacts
- `GET/POST/PATCH/DELETE /api/coaching/clients/{id}/calls` + `/api/coaching/calls/{id}` — schedule, list, update, delete; auto-snapshots `pre_call_brief` JSONB on creation; `prior_call_id` chain for commitment tracking
- `POST /api/coaching/calls/{id}/refresh-brief` — re-builds the brief from current data right before the call starts
- `POST /api/coaching/calls/{id}/complete` — marks completed + computes `commitment_keep_score` as % of prior call's action items in COMPLETED status
- `GET/POST/PATCH/DELETE /api/coaching/clients/{id}/action-items` + `/api/coaching/action-items/{id}` — text/measurement/due_date/owner/tag/status/source_call_id; auto-stamps completed_at when status=COMPLETED
- `GET /api/coaching/clients/{id}/brief-preview` — ad-hoc brief without creating a call (uses last call if any, else `_build_brief_no_call`)

**Pre-call brief structure (`_build_brief()`):**
- **pace** — GCI YTD vs target with day-of-year gap; status = ahead | on-pace | behind (>10% gap)
- **big_rocks** — listings/buyers closed YTD vs targets from Economic Model
- **pipeline** — open entries by rating (10s/9s/8s/7s/6s/cold/total) split by LISTING vs BUYER
- **activity_14d** — contacts made, appts held, hours prospected, days logged, current streak (consecutive days with contacts ≥ 1)
- **last_call_action_items** — commitments from prior call with completion status
- **commitment_keep_score** — completed ÷ total of prior call's action items
- **talking_points** — heuristically generated red flags (behind pace, empty pipeline, low commit-keep, daily discipline gap, contact volume too low)

**Frontend (Mission Control `static/index.html`):**
- Tab bar in client detail view enabled: Business Plan / Coaching Calls / Pipeline / Daily Activity (Recruiting still stubbed)
- **Calls tab** — list view (date + type + status pill + commitment-keep % + notes preview) and detail view; "+ Schedule Next Call" creates the call and opens it; detail view splits left (brief + in-call markdown notes auto-saving on blur) and right (action items panel with checkbox-toggle to flip OPEN→COMPLETED, inline text edit, prompt-based add/edit, delete); "↻ Refresh Brief" rebuilds from current data; "Mark Complete" computes commitment-keep
- **Pipeline tab** — Listings/Buyers toggle, 7-column rating summary cards (10s/9s/8s/7s/6s/5s/≤4) with hot ratings highlighted in accent color, table with inline rating + next-step editing, full-edit and delete actions
- **Activity tab** — today's log entry form (auto-saves each field on blur, upserts so re-saving doesn't dupe) + last-14-days table

**Math sanity check on VPS:** $350K goal / $0 YTD on May 1 → "behind 33.2%, gap = $116,027"; 1 listing-10 + 1 listing-9 + 1 buyer-cold counted correctly; talking points generated for pace + daily discipline.

## Phase 15.3 — Coaching: Agent Portal + Dashboard + GPS + 4-1-1 + HybridShare ✅ (Session 3)
**Goal:** Ship 4 features in one session — agent self-service portal, coach dashboard, GPS (1-3-5) editor, 4-1-1 goal cascade, LPT HybridShare module with recruiting kanban + 5-year projection.

**Backend (`coaching.py` extended, no new tables — schema already in place):**

*Provisioning:*
- `POST /api/coaching/clients/{id}/provision-portal` — creates a `users` row (role=agent) + dedicated `workspaces` row for the client, links via `coaching_clients.user_id`. Sends invite email with temp password + portal URL. Reuses existing user if email already on file.

*Agent self-service (`/api/coaching/me/*`):*
- All endpoints scoped by `coaching_clients.user_id = current_user.sub` (NOT by workspace, since the agent lives in their own isolated workspace but their coaching_client record lives in Joe's workspace).
- `GET /api/coaching/me` — agent's coaching client + plan + computed numbers
- `GET/POST /api/coaching/me/activity` — daily log (upsert by log_date)
- `GET/POST/PATCH/DELETE /api/coaching/me/pipeline` — agent edits their own pipeline
- `GET /api/coaching/me/calls` — read-only list
- `GET/PATCH /api/coaching/me/action-items` — agent can mark items COMPLETED/MISSED but cannot edit text/owner/tag (only items where `owner = AGENT`)
- `GET /api/coaching/me/brief` — same pre-call brief Joe sees (transparency)

*Coach dashboard:*
- `GET /api/coaching/dashboard` — aggregate book-of-business: totals (active clients, GCI goal/YTD, pace), `behind_pace` (clients with -10%+ gap), `thin_pipeline` (no hot listings or empty), `no_recent_activity` (>3 days since last log), `upcoming_calls` (next 7 days), `low_commitment_keep` (<70% on last call).

*GPS (1-3-5):*
- `GET /api/coaching/clients/{id}/gps` — auto-creates Goal with GCI target if missing, returns priorities (3 max) with strategies (5 max each)
- Full CRUD: `gps-goals/{id}`, `gps-priorities/{id}`, `gps-strategies/{id}`
- UI shows warning when sum of strategy targets < priority target

*4-1-1:*
- `GET /api/coaching/clients/{id}/four-one-one?period_type=ANNUAL|MONTHLY|WEEKLY&period_key=YYYY|YYYY-MM|YYYY-Www` — returns 4 columns (JOB, BUSINESS, PERSONAL_FINANCIAL, PERSONAL); ANNUAL+BUSINESS auto-includes `suggestions` from Big Rocks (Listings taken, Buyers shown, Listing appts, Buyer consults, GCI)
- `PUT /api/coaching/clients/{id}/four-one-one` — upsert by (plan, period_type, period_key, column_key)

*HybridShare / Recruits:*
- `GET/POST/PATCH/DELETE /api/coaching/clients/{id}/recruits` + `/api/coaching/recruits/{id}` — recruit CRUD with status (HITLIST/WORKING_HOT/IN_PROCESS/SIGNED/UNQUALIFIED/CHURNED), tier (1-7), comp plan, sponsor chain
- `GET /api/coaching/clients/{id}/hybridshare` — 7-tier ladder from official LPT flyer constants: tier 1 (31% pool, $2,325/BP, $775/BB, unlock at 1 active), tier 7 (20% pool, $1,500/BP, $500/BB, unlock at 20 active), max $7,500/BP-yr, $2,500/BB-yr. Counts agent's signed recruits per tier, marks unlock state, computes tier subtotals. Performance Awards progress: White Badge (1 txn), Silver Badge (3), Gold Badge (15), Black Badge (35, BP only). Pulls agent's YTD txns from closed pipeline entries.
- `GET /api/coaching/clients/{id}/hybridshare/projection?recruits_per_year=4&pct_bp=0.5&cap_hit_rate=0.30&children_per_recruit=1.5` — 5-year stacked projection: each year direct recruits + trickle (children per existing tier-N → tier-N+1, diminishing past tier 2). Returns network size, tiers unlocked, projected income per year. Verified: 4 recruits/yr, 50% BP, 30% cap-hit, 1.5 children → Y1 $3,480 → Y5 $50,245 with 267 agents in network.

**Frontend — Mission Control (`static/index.html`):**
- Coaching list view now has a Dashboard / All Clients toggle. Dashboard surfaces: active clients, aggregate goal/YTD/pace, then 5 sectioned lists (behind pace, thin pipeline, no recent activity, calls this week, low commit-keep) — every row clickable to drill into the client.
- Detail view tab bar expanded to 7: Plan / GPS (1-3-5) / 4-1-1 / Calls / Pipeline / Activity / HybridShare.
- "Portal Access" button in detail header — provisions a portal login + emails temp password; auto-disables to "✓ Portal Provisioned" once done.
- GPS tab: editable goal (auto-suggests "Earn $X GCI in YYYY"), priorities cards (3 max) with 5-strategy slots each, inline rollup validation warns when strategy sum < priority target.
- 4-1-1 tab: ANNUAL / MONTHLY / WEEKLY toggle, 4-column grid (Job / Business / Personal Financial / Personal), checkbox-toggle complete, ANNUAL+BUSINESS shows clickable suggestion chips from Big Rocks.
- HybridShare tab: gated to LPT comp plans; summary cards (comp plan, projected at full cap, max possible/yr, YTD txns); performance award badges with progress bars; 4-column recruit kanban (Hitlist → Working Hot → In Process → Signed); 7-tier ladder (top-down) with lock/unlock state + per-tier subtotal; 5-year projection panel with editable params and yearly income breakdown.

**Frontend — Agent Portal (`static/portal/index.html`):**
- "My Coaching" nav group appears only for users whose `users.id` matches a `coaching_clients.user_id` (auto-detected on login).
- 4 new pages:
  - **Today** — daily activity log entry (auto-saves on blur), pace/streak summary, open action items with checkbox-toggle
  - **My Plan** — read-only view of GCI goal, all activity targets (Listings taken / Buyers shown / etc.), key money rows (Take Home, Net Income, Survival, Surplus) with hover-to-formula
  - **Pipeline** — Listings/Buyers toggle, rating summary, full CRUD (agents edit their own pipeline)
  - **Calls & Commitments** — read-only call history with notes, all action items they own across all calls

**Smoke tests verified on VPS:** dashboard returns correct totals; GPS auto-creates with $350K goal; 4-1-1 returns Big Rocks suggestions (20.59 listings, 21.88 buyers, 31.7 appts); HybridShare returns 4 awards + 7 tiers + 5-year ladder; provision-portal creates user + workspace + links coaching_client.user_id.

**Out of scope (queued):**
- Reviews (quarterly/semi-annual/annual snapshots) — schema exists, UI deferred
- Perfect Week scheduler — schema exists, UI deferred
- Database touch tracker (`contact_touches`) — schema exists, UI deferred
- Excel imports of legacy worksheets

## Phase 15.4 — Coaching: Invite UX, Surface Isolation, Onboarding Wizard ✅
Three production fixes after first real-world use:

**Invite email never sent.** `coaching.py` provision_portal() looked up `settings.get("resend")` but every other `send_email()` caller in main.py uses `settings.get("smtp")`. The lookup returned None, `smtp_cfg.get("pass")` was empty, send_email short-circuited with "Resend API key not configured", no email_send_log row written. Plus the "+ Invite Client" modal never actually invited — it only created the coaching_client + lead. The Portal Access button on the detail view was a separate step that was easy to miss. Fix: corrected the settings key to `"smtp"`; added a "Send portal invite email now" checkbox to the modal (default ON); `CoachingClientIn` now accepts `send_portal_invite: bool` which chains `provision_portal()` after creating the client. Temp password shown in confirmation alert. Verified end-to-end: existing Joe CoachingTest provisioned, Resend log shows `status=delivered` with `resend_id=50ff8174-e921-4fb7-ba93-c3be52f3d94b`.

**Coaching clients landed on the admin Mission Control UI.** Logging in as a coaching-client agent showed the full MC dashboard (Funnel Analytics, Recruit Comparison, settings page with Joe's notification email pre-filled — a privacy leak). They belong on portal.tplcollective.ai which has the My Coaching tab. Fix: `mcShouldRedirectToPortal()` probes `/api/coaching/me` after login (`mcDoLogin`) and on cached-token init (`mcInit`). If the user is a coaching client (role != admin, not impersonating, /me returns 200), `window.location` bounces to `https://portal.tplcollective.ai`. Joe's admin session and in-progress impersonations are unaffected.

**Portal subdomain redirect loop.** Both mission.tplcollective.ai and portal.tplcollective.ai resolve to the same FastAPI app (Traefik routes by Host but doesn't change the path). The `/` handler unconditionally returned `static/index.html` (Mission Control), so portal.tplcollective.ai/ served the admin UI. The new coaching-client redirect then bounced any portal visit back to itself, infinite refresh loop. Fix: `dashboard()` now reads the Host header — `host.startswith("portal.")` returns `static/portal/index.html`, everything else returns the MC index. The existing `/portal` path-prefix on mission.* still works as before.

**First-login onboarding wizard.** Coaching clients had nowhere to enter their goals — they'd land on the portal's Today tab with an empty plan. Wizard pops up auto when essentials missing (`gci_target=0`, `avg_sale_price=0`, `avg_commission_rate=0`, or `brokerage` empty). 3 steps: (1) Annual GCI Goal, (2) avg sale price + commission % + seller-business mix + license date, (3) brokerage + LPT comp plan + market city/state. Posts to new endpoint `/api/coaching/me/onboard` which updates coaching_clients + business_plans + economic_models + budget_models (auto-fills the LPT cap from the comp plan). Coach can refine on the first call.

## Phase 15.5 — CTE-style Coaching Tools ✅
Original Phase 15 built the spine (clients, calls, dashboard, GPS, 4-1-1, HybridShare). Real first use revealed the surface was too thin compared to the legacy DeSane CTE 2019 spreadsheet. Phase 15.5 brings the tools up to CTE feature parity in three sessions.

### 15.5a — Detailed goal-setting form (replaces 3-step wizard)
**Schema (migration `2026-05-04-phase-15-5-cte-goal-form.sql`):**
- `coaching_clients` adds `big_why`, `team_or_individual`, `team_name`
- `economic_models` adds `commission_rate_listing` + `commission_rate_buyer` (sale prices already separate)
- `budget_models` adds `royalty_pct`, `royalty_cap`, `split_cap`
- New `activity_goals` table with daily/weekly/monthly per-category targets (dials, contacts, nurtures, hours, listing/buyer appts set+held, showings, open houses, listings/buyers signed, conversion benchmarks)
- `coaching_activity_logs` adds `dials`, `nurtures`, `listing_appts_set`, `listing_appts_held`, `listings_signed`, `buyer_appts_set`, `buyer_appts_held`, `buyers_signed`, `showings`, `open_houses_held`

**Backend:** `/api/coaching/me/onboard` accepts a six-section payload (`client`, `plan + pct_listing_income`, `economic`, `budget`, `activity_goals`, `recruiting`). Each section is optional so the wizard saves partial progress on every Next click. New `GET /me/activity-goals` and `GET /clients/{id}/activity-goals`.

**Frontend (portal):** 6-step modal — (1) Identity & Vision (brokerage, comp plan, market, license date, solo/team, big why); (2) Income Goal (GCI + listing/buyer income split slider with live $ preview); (3) Deal Economics (separate listing/buyer ASP + comm + 4 conversion rates); (4) Money Plan (tax/charity/retirement %, brokerage cap, royalty, avg net commission); (5) Activity Goals (12 fields across daily/weekly/monthly); (6) Recruiting (LPT only — annual goal, conversation ratio, % BP, cap-hit rate). Progress bar tracks completion. LPT comp-plan field auto-shows when brokerage = LPT. Recruiting step auto-skips for non-LPT.

### 15.5b — Daily Lead Gen Entry + Scorecard
Daily activity entry expanded from 4 fields to the full CTE Daily Lead Gen lineup: Hours, Dials, Contacts, Nurtures, Listing Appts Set/Held + Listings Signed, Buyer Appts Set/Held + Buyers Signed, Showings, Open Houses Held. Both the coach (MC) and the agent portal Today tab get the new entry form. **Bug fix mid-session:** `ActivityLogIn` Pydantic model was silently stripping the new columns until they were added to the model — caught by inspecting the DB row after a smoke test.

New `/api/coaching/me/scorecard` and `/api/coaching/clients/{id}/scorecard` return CTE-style rollups: this week, this month, last 30 days, YTD, plus monthly Jan-Dec grid. Each period includes totals across all 14 activity fields plus computed conversion %s (contact-to-appt, set-to-held, contacts/hour). Coach Activity tab shows a Scorecard panel with this-week/this-month/YTD columns, goal-vs-actual highlights (green ≥100%, amber 70-99%, red <70%). Agent Today tab shows a "This Week vs Goals" panel with progress bars per metric.

### 15.5c — Transaction lifecycle (CTE My Business sheet)
**Schema (migration `2026-05-04-phase-15-5c-transaction-lifecycle.sql`):**
- `pipeline_entries` adds `status` enum (PRE_SIGNED → ACTIVE → PENDING → CLOSED → EXPIRED, plus WITHDRAWN, CANCELLED)
- Adds `list_date`, `expiration_date`, `expected_close_date`, `net_commission`, `mls_number`
- Existing `closed=true` rows backfilled to `status=CLOSED`

**Backend:** `_ceo_summary()` returns counts by status, listing/buyer active counts, active listing volume + projected GCI, pending volume + GCI, closed YTD units/volume/GCI/net GCI, monthly closed grid Jan-Dec. `_whiteboard()` returns active listings sorted by DOM desc, listings over 90 DOM, listings expiring in the next 30 days. Endpoints: `/api/coaching/me/ceo-summary`, `/me/whiteboard`, `/clients/{id}/ceo-summary`, `/clients/{id}/whiteboard`.

**Coach Pipeline tab redesigned:** 5-card CEO summary at top (Pre-Signed, Active Listings + Vol, Active Buyers, Pending + GCI, Closed YTD + GCI). Yellow alert banner above the table when any listings expire in the next 30 days. Status filter chips (All / Pre-Signed / Active / Pending / Closed) alongside Listings/Buyers toggle. Table rebuilt with Status pill, Rating, Client/Address, List Date, Expiration Date (red if ≤30d), DOM, Price, Next Step. Sort priority: Active → Pending → Pre-Signed (by rating) → Closed → Expired. Add/Edit prompts include status + lifecycle dates + price + GCI.

**Verified end-to-end:** ACTIVE listing with list_date 2026-04-15 / exp 2026-05-25 correctly shows DOM 20d, days_to_expiry 20d, fires the expiring-in-30 alert. CLOSED listing flows into closed YTD totals (1 unit, $380K volume, $9,500 GCI).

## Phase 15.6 — Reviews + Database + Perfect Week ✅
Three deferred features from session 1 (schemas existed, no UI) shipped in one session.

### 15.6a — Reviews (quarterly / semi-annual / annual checkpoints)
`POST /api/coaching/clients/{id}/reviews` with `{review_type}` captures a JSONB snapshot of the entire current state (client meta, plan, computed economic + budget, scorecard with weekly/monthly/30d/YTD/monthly grid, CEO summary). `PATCH` lets coach edit reflections + focus_areas_next, plus a `recapture` flag that re-snapshots from current data while preserving the narrative. Reviews tab on client detail (last in the row): list view with type pill + date + reflections preview + closed YTD; detail view splits left (formatted snapshot rendering plan/CEO/YTD activity/money) and right (reflections + focus-areas-next textareas, auto-save on blur).

### 15.6b — Database touch tracker (Met / Haven't-Met)
`_touches_database()` groups `contact_touches` by `(name lower + email lower)`, computes last_touch / ytd_count / days_since / overdue per person. **Overdue rules:** MET = days_since > 30 (off pace for 12/yr cadence); HAVENT_MET = days_since > 90. Endpoints: `/clients/{id}/database` (grouped + overdue), `/clients/{id}/touches` (raw history), POST/PATCH/DELETE on `/touches/{id}`; mirrored at `/me/*`. Database tab on coach side + "My Database" nav on agent portal — both show 4 stat cards (Total / Met / Haven't-Met / Overdue), filter chips (All / Met / Haven't-Met / Overdue), per-person table with type pill, YTD count + "/12" target for Met, last touch date, days_since (red if overdue), inline "+ Touch" quick-log per person. Verified: 3 touches logged → Mark Lee (61d ago) correctly flagged overdue, Sarah (today) and Jen (30d) within tolerance.

### 15.6c — Perfect Week scheduler
`_ensure_perfect_week()` auto-creates the default 50-dial template on first read (Mon-Fri lead-gen mornings, WED evening reserved for the coaching call, weekend lighter). `/api/coaching/clients/{id}/perfect-week` + `/me/perfect-week` GET / PUT. 7-day × 4-slot (Before 8 / Morning / Afternoon / Evening) grid of textareas with auto-save on blur. Coach can name templates and reset to default; agent edits the same schedule from their portal.

### 15.6d — Monthly Financial Statement (CTE Financial Statement tab)
New `monthly_financials` table — one row per `(business_plan_id, month)`. JSONB columns for `income` / `cost_of_sales` / `operating_expenses` so agents can add custom lines without migrations. `_ensure_financial_months()` auto-creates 12 rows the first time anyone reads, pre-seeded with seven CTE income lines, nine cost-of-sales lines, and seven opex categories. `_financials_with_actuals()` returns the full grid with computed per-month + yearly totals AND auto-pulled actuals from closed `pipeline_entries` (broken out by listing vs buyer). Endpoints: `/clients/{id}/financials` GET + per-month PUT, mirrored at `/me/*`. Coach Financials tab (between Perfect Week and Reviews) renders 5-card top strip + wide grid: 200px label column + 12 month columns + Year total. Sections: Income → Actual listing/buyer overlay (read-only) → Cost of Sales → Gross Profit row → Operating Expenses → Net Profit row (highlighted in accent glow). Every cell editable, saves on blur. "+ Income/+ COGS/+ OpEx Line" buttons add a label across all 12 months. Verified: April actual income $9,500 pulls from a Garcia close, March manual entry computes net profit $10,620.

### 15.6e — CTE / MREA Excel workbook import
Adds `openpyxl 3.1.5` to requirements. `_parse_cte_workbook()` detects CTE 2019 vs MREA Business Plan by sheet names. From the **Business Plan** tab: pulls D7 agent name, D8 individual/team, D9 big why, L7 tax %, L8 split-to-office %, L9 split cap, plus the lead agent row (typically R16) — GCI goal in col E, listing/buyer ASP in cols H/I, listing/buyer commission % in cols J/K. From the **Daily Lead Gen Entry** tab: iterates rows 4+ and emits one activity log per dated row, mapping the 11 columns to hours / dials / contacts / nurtures / listing+buyer appts (set/held/signed) / showings / open houses. `POST /api/coaching/clients/{id}/import-cte` multipart endpoint with `apply` flag — `apply=false` returns preview with counts + parsed values + warnings; `apply=true` persists into `coaching_clients` + `business_plans` + `economic_models` + `budget_models`, then upserts activity logs by `(client_id, log_date)`. "Import .xlsx" button in client detail header → modal with file picker → on selection parses + renders preview → confirm → apply. Verified end-to-end with Joe's actual `DeSane_and_Associates_CTE_2019.xlsx`: extracted GCI $475K, ASP $265K, 2.75% commission, 17% tax, $21K split cap, "DeSane & Associates" team name.

**Phase 15 / 15.5 / 15.6 — coaching platform feature-complete**
Coach detail tab bar now: Plan / GPS (1-3-5) / 4-1-1 / Calls / Pipeline / Activity / HybridShare / Perfect Week / Database / Financials / Reviews. Agent portal nav: Today / My Plan / Pipeline / Database / Perfect Week / Calls & Commitments. Client header has Portal Access + Import .xlsx + Status dropdown.

## Phase 15.8 — Coaching Intake Export (PDF + CSV via email) ✅
Joe needed a way to download each coaching client's onboarding-wizard answers off the system for record-keeping and coaching-call prep. Built per-agent + bulk export that emails attachments straight to the logged-in coach's address (uses the existing send_email() rail, no new infrastructure).

**Backend (`coaching.py`):**
- `_collect_intake_data(client_id)` — gathers coaching_clients + lead + business_plans + economic_models + budget_models + activity_goals + recruiting_plans into one dict; uses `.get()` everywhere so missing columns degrade gracefully to "—" in output
- `_build_intake_pdf(data)` — reportlab one-page branded PDF, dark luxe palette (`#1a1a2e` ink, `#6c63ff` accent), 5 sections: Identity & Vision, Income Goal & Deal Economics, Money Plan, Activity Goals, Recruiting (LPT only)
- `_build_intake_csv(intakes)` — stable 48-column schema, one row per agent
- `_email_intakes()` — single-agent case attaches `intake_<name>.pdf` + `intake_<name>.csv`; bulk case zips per-agent PDFs into `coaching_intakes_<date>.zip` + master `coaching_intakes_<date>.csv`. Routes through `main.send_email()` so suppression / rate-limit / open-tracking / logging rails all apply
- `POST /api/coaching/clients/{id}/email-intake` — per-agent export
- `POST /api/coaching/email-all-intakes` — workspace-wide bulk export (skips broken rows individually rather than failing whole batch)

**Frontend (`static/index.html`):**
- "📧 Email Intake" button on client detail header (next to Import .xlsx / Portal Access)
- "📧 Email All Intakes" button on coaching list view header (next to + Invite Client)
- Both confirm before sending, disable while in-flight, show `sent_to` + agent count on success

**Sends to:** `request.state.user.email` (the logged-in coach). No new env vars, no migrations.

## Phase 15.9 — Async Supabase Layer + Circuit Breaker ✅
The May 18 incident exposed an architectural fragility: every Supabase call in the app is **synchronous and blocking**, but FastAPI is async. When Supabase's PostgREST/Supavisor pooler temporarily wedged for ~48 minutes, every login hung 15s instead of failing fast or retrying. Single bad Supabase moment → org-wide outage. Built a defensive async layer for the user-facing hot paths without rewriting 380+ sync call sites.

**New infrastructure in `main.py`:**
- `supabase_async: AsyncClient` — lazy singleton via `acreate_client()`, one per worker, reused across all async requests. Lives alongside the existing sync `supabase` client (which 380+ call sites still use).
- `get_async_supabase()` — initializes on first use, asyncio.Lock guards double-init.
- `aexecute(builder, route, max_retries=2)` — async retry wrapper with exponential backoff (200ms → 600ms → 1.8s). Detects transient errors by code (`PGRST003`, `522`, `503`, `504`, Postgres `57P03`, `08006`, `08001`) and message fragments ("connection pool", "timed out acquiring connection", "gateway time-out", etc.). Logs successful recoveries to `activity_log` as `supabase_transient_recovered`.
- **Circuit breaker** — trips OPEN after 5 transient failures in 30s. While OPEN, `aexecute()` raises `SupabaseUnavailable` immediately instead of stacking timeouts (prevents thundering-herd recovery). After 30s cooldown → HALF_OPEN for a probe. Success → CLOSED. Failure → OPEN again.
- `_is_transient(exc)` — heuristic distinguishes retry-worthy hiccups from real bugs (permanent errors propagate immediately).

**Migrated endpoints (hot paths):**
- `POST /api/auth/login` — async + retry + circuit breaker. Failed `Authentication service is recovering` 503 instead of 15s hang when pool is wedged.
- `GET /api/auth/me` — fires on every page load; same treatment so the UI shell doesn't freeze.
- `GET /api/health/db` — NEW. Fast Supabase round-trip probe with 3s timeout. Returns `{status, latency_ms, circuit, recent_transients}`. Bypasses the breaker so external monitors (UptimeRobot, etc.) can observe recovery state. Wire this into your status page or alerts.

**Left as sync (intentional):**
The remaining ~380 call sites in `main.py`, `coaching.py`, `extended_routes.py`, `automations.py`, `sync_meta_leads.py` stay on the sync client. FastAPI runs sync `def` routes in a threadpool, which works fine for non-critical paths. The cron + non-request code (e.g., `sync_meta_leads.py`) doesn't benefit from async at all. We migrate further routes only when a specific endpoint becomes a hot path.

**What this fixes:**
- Login no longer hangs when Supabase pool is wedged — fails fast with a clear 503 + retry hint, or auto-retries and recovers.
- /api/auth/me no longer locks the whole UI shell during a hiccup.
- Circuit breaker stops the cascade where every blocked request piles more pressure on the pooler.
- /api/health/db gives an external signal we can monitor.

**What this does NOT fix:**
- Sheer call volume — endpoints that fire 10-20 sync Supabase calls per page load still strain the pooler. Long-term: audit hot endpoints for N+1 patterns, batch reads, cache where safe.
- Supabase-side pooler bugs themselves — we can't fix their internals, just make our app survive them gracefully.

## Phase 16 — Prospect Engagement (private brief tracking) ✅
Reusable per-prospect engagement tracking for private brief pages hosted on `tplcollective.ai/<slug>` (first prospect: Jay Dural). Joe sends one URL, sees opens / time on page / scroll depth / section views / CTA clicks in a live MC dashboard, and gets an email the moment the prospect opens it.

**Schema (`migrations/2026-05-29-phase-16-prospect-engagement.sql`):**
- `prospect_briefs` — registry of briefs, keyed by slug, with `display_name` and `notify_email` override. (Distinct from the existing uuid-keyed `prospects` table used by the recruiting pipeline — different concept, intentionally separate table.)
- `prospect_engagement_events` — event firehose (JSONB `data`, indexed by prospect_id + visitor_id + session_id + event)
- Both workspace-scoped via `db()` wrapper (added to `TENANT_TABLES`)
- Jay seeded with `notify_email = joe@tplcollective.ai`

**Backend (`mission-control/app/prospect_engagement.py` — new module, wired via `setup(db, supabase)` mirroring `coaching.py`):**
- `POST /api/tracking/prospect-engagement` — **public ingest**. Mounted under `/api/tracking/*` so it inherits the existing public-prefix whitelist. Validates slug, looks up workspace_id from `prospect_briefs`, inserts the event, mirrors high-signal events (`page_open` / `cta_click` / `session_end`) to `activity_log`.
- `GET /api/prospect-engagement/{slug}` — JWT-gated roll-up: sessions, total active seconds, max scroll, sections viewed, CTA tally, per-session active time, full event timeline (last 300).
- `GET/POST/PATCH/DELETE /api/prospect-engagement/_prospects` — brief registry CRUD.
- **Open notifications go through `main.send_email()`** so suppression / rate limits / `email_send_log` all apply (no raw Resend calls). Notify-once-per-session de-dupe via a COUNT(session_id, event=page_open) probe — first event of a fresh session fires the email, subsequent page_opens in that session do not.

**Mission Control SPA (`static/index.html`):**
- New "Prospect Engagement" nav item under Marketing (platform-only).
- List view: briefs table with display name, slug, session count, last seen, notify email, View / Open page / Delete actions.
- Detail view: 5-card summary strip (Sessions / Total Active / Max Scroll / Sections Viewed / Visit Count), CTA tally pills, sections viewed pills, event timeline with humanized descriptions.
- Hash deep-link: `#engagement/<slug>` jumps straight to a brief.

**Frontend (`jay-dural.html` at repo root):**
- Verbatim copy of the approved brief — Joe rule, do not edit.
- Tracking endpoint set to `https://mission.tplcollective.ai/api/tracking/prospect-engagement`.
- Includes its own GA4 + custom tracking script. Does NOT include the site-wide `tpl-tracking.js` (would double-track).
- Live at `https://tplcollective.ai/jay-dural` via Vercel `cleanUrls: true` (no route changes needed).

**Verified on deploy:**
- POST ingest returns `{ok: true, id: <int>}`
- Unauth GET returns 401
- Same-session re-open does NOT fire a second notification
- New session DOES fire a fresh notification (visit #2)
- Notification email delivered via Resend through `send_email()` rail, logged in `email_send_log` with `campaign=prospect-open-jay-dural`
- `activity_log` mirror inserted for high-signal events

**Backups on VPS:** `main.py.pre-phase16-20260529-140829`, `static/index.html.pre-phase16-20260529-140829`.

**Adding a new prospect:**
1. In MC → Prospect Engagement → "+ Add Prospect Brief" (slug + display name + notify email override)
2. Drop a new HTML file at repo root: `<slug>.html`, set `PROSPECT_ID` to the slug, leave ENDPOINT alone
3. Commit + push (Vercel auto-deploys)
4. Send the URL. Done.

## Phase 17 — Sponsored Join Page (/join-lpt-realty) ✅
New high-intent capture page for agents who already know they want to join LPT through TPL — distinct from Phase 9's research-stage /joining-lpt-realty (now 302→/).

- **Page** (`join-lpt-realty.html`): 4-step process explainer (submit → we prep → walkthrough video → finish), single form (legal first + last name, email, cell phone, all required), success view with the walkthrough video embedded inline (YouTube unlisted `rvapYIFg-W4`, `?rel=0` to restrict related-video suggestions to Joe's channel), FAQ + HowTo & FAQPage JSON-LD. Phone formatter auto-formats to `(XXX) XXX-XXXX`. Honeypot field for bots. Started as a 2-slot design; collapsed to a single video since only one walkthrough is planned.
- **Submission**: form POSTs to `/api/leads` (Vercel function, NOT Mission Control). Payload includes `first_name`, `last_name`, `email`, `phone`, `source: join-lpt-realty`, `magnet: lpt-walkthrough-video`, `stage: ready-to-join`, `tags: [join-lpt-realty, walkthrough-requested, high-intent]`.
- **api/leads.js patches** (this is where the work landed, NOT mission-control):
  - Now persists `first_name`, `last_name`, and `tags` to discrete columns (previously destructured but dropped — name field had concatenated full name but discrete columns stayed empty)
  - `sendInternalNotification()` is now AWAITED before the response. Was fire-and-forget; Vercel's Node runtime freezes the lambda the instant `res.status(200).json()` returns, so the un-awaited Resend fetch was being killed mid-flight and Joe never got the new-lead email. Adds ~300-800ms latency, fine for a form submit. Failure path now logs Resend status + body explicitly.
  - New `lpt-walkthrough-video` magnet with `type: 'video'` — skips the signed-token + `magnet_deliveries` insert (only needed for PDFs), links direct to the YouTube URL. `buildWalkthroughEmail()` sends the video link with warm Joe-voice copy + Calendly fallback.
  - Magnet delivery flow now branches on `magnetConfig.type` (`'download'` vs `'video'`). Funnel enrollment guarded on `magnetConfig.funnel_id` — walkthrough leads are ready-to-join, not research-stage, so no drip enrollment fires for them. `sponsor-checklist` flow untouched.
  - Mission Control FastAPI `POST /api/leads` is a SEPARATE endpoint with the same name — patch deferred. Handoff doc at `.claude/handoffs/HANDOFF_2026-06-30_0310.md` for that side if any caller starts posting `last_name`/`phone` to the MC endpoint directly.
- **vercel.json**: 302 retire `/joining-lpt-realty` → `/`, repoint `/private-assets/*` fallback from the retired page to `/`.
- **Site nav**: `Join LPT Realty` added across all 36 nav-bearing pages (desktop nav + mobile menu + footer), inserted right after `Compare`. Funnel reads Explore → Why → Fees → Compare → Join → Resources → Blog.
- **sitemap.xml**: `/joining-lpt-realty` swapped for `/join-lpt-realty`.

## Phase 18 — /compare polish + KW → LPT BB recruiting outreach ✅

**Comparator (`/compare`) fixes:**
- `data/brokerages.json`: LPT Realty founded year corrected 2018 → 2022
- Breakdown cards on every non-LPT card show a "You would keep $X/yr more at LPT Realty" row (green when LPT wins, red when it loses, neutral when identical). Baseline is best LPT net across whichever LPT plans are selected in the view.
- HybridShare 7-tier ladder panel hidden when `state.lptPlan === 'bb'` (BB agents can recruit a downline but cannot unlock HybridShare earnings until upgrading to Brokerage Partner).
- Column order rewrite: competitors first in selection order, LPT last (matrix + breakdown cards + cap break-even + 3-year projection). Reads left-to-right as "your current brokerage → LPT alternative".
- Per-brokerage fee override: every non-LPT chip gets an inline ✎ edit button. Modal prefills from the brokerage's published plan via new `planToFormValues()`. On save, `buildCustomBrokerage()` detects "editing a published entry" and spreads the original object (logo, plan_name label, revshare tiers, technology, training, source citations, tier, category, markets, tpl_callout) then replaces only the plan numbers. Result renders under the original brand and plan name; only the math changes. Chip gets a gold "MODIFIED" pill. LPT chip has NO edit button — LPT numbers stay verified against the official flyer per project rules.

**Known follow-up (not blocking):** the server-side PDF generator (`api/generate-comparison-pdf.js` + `api/_lib/comparison-pdf.js`) still renders the HybridShare 7-tier section even when `plan=bb`. The JS/live compare page hides it correctly. Same guard needs porting to the PDF path.

**Active outreach campaign (July 2026, KW Palm Beach + Treasure Coast → LPT BB):**
- Source data: KW production export (LTM through 2026-07-24)
- 16 BB-target agents (10+ LTM txns, KW GCI ≤ $110K, would keep $7,500-$19,500 more/yr at LPT BB). Files in `outbound/kw-bb-target/` (untracked, working drafts): `run-these-analysis.csv`, `run-these-bb-targets.csv`, `messages-run-these.md`.
- Broader pool: 68 "past KW cap" agents (GCI ≥ $110K) still keep ~$18-19K/yr more on LPT BB, just a different pitch angle.
- Delivery mechanic: personalized YouTube-unlisted video (~8 min screen recording using `/compare?report=<token>`) + email from `Joe DeSane <joe@tplcollective.co>` via Resend + attached branded PDF from the comparator.
- **Sent:** Heather Suarez (KW Jupiter, 9 txns, $2.5M vol, delta $17,500) — id `3ddbd7df-ea19-461e-b7c3-465d52beef73`, 2026-06-30.
- **Scheduled:** Stephanie Hays (KW Wellington, 12 deals, $7M vol, delta $17,720, PDF attached) — id `dc3a0bfa-3e58-43cd-8655-3320a8b6b849`, fires 2026-07-27 6:00 PM EDT via Resend `scheduled_at`. Cancel/reschedule via `DELETE`/`PATCH https://api.resend.com/emails/dc3a0bfa-3e58-43cd-8655-3320a8b6b849`.

## DNS — Complete ✅
- `@` → 216.198.79.1 (root domain)
- `mission` → 187.77.213.230 (Mission Control)
- `portal` → 187.77.213.230 (Agent Portal)
- `www` → Vercel CNAME
- `send` MX → Amazon SES (Resend)
- Traefik handles SSL via Let's Encrypt for mission + portal subdomains

## Rules
- TPL Collective ≠ LPT Realty — never conflate the two
- Never fabricate LPT financial figures
- Keep POST /api/leads backward compatible (live website uses it)
- Always confirm before deploying to the VPS
- Comparator PDFs use ASCII-only labels (Helvetica bundled with pdfkit can't render Δ, em-dashes, U+2713 checkmark, etc.). Use "vs LPT BP:" not "Δ vs LPT BP:" and avoid em-dashes in PDF body text.
- pdfkit footer Y coordinates must stay within the bottom margin (page.height - marginBottom) or text auto-paginates to a fresh page even with `lineBreak: false`.
