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
- Key pages: index, why-tpl, fee-plans, lpt-explained, commission-calculator, 27k-worksheet, resources, join, revshare, two-lanes, franchise-fees, brokerage-fees, privacy-policy, 404, fb-post-scheduler, ideas/index
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
