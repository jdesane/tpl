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
