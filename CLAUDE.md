# TPL Project

## Infrastructure
- **Database**: Supabase (Postgres) — project `zyonidiybzrgklrmalbt`, region us-west-2
  - 37 tables including: leads (187), activity_log, emails_sent, drip_queue, users, agents, tasks (1,588), onboarding_steps, resources, email_queue, referrals, recruiting_links (40), content_posts, lead_stage_history, revshare_entries, automation_runs, automation_settings, goals, lead_notes, lead_activity, email_funnels, email_funnel_steps, email_funnel_enrollments (239), pipelines, opportunities (188), smart_lists, contact_communications, email_suppressions, email_send_log (24,804), email_daily_limits, buyer_intake_submissions, ideas, prospects, activities, recruiting_tasks, newsletter_subscribers, newsletter_issues
  - RLS enabled on all tables, service role policies for backend access
- VPS at 187.77.213.230 runs Mission Control in Docker (`/docker/mission-control/`)
- FastAPI backend — modular: `main.py`, `auth.py`, `models.py`, `extended_routes.py`, `report_generator_v2.py`
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
