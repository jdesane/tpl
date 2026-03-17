# TPL Project

## Infrastructure
- **Database**: Supabase (Postgres) — project `zyonidiybzrgklrmalbt`, region us-west-2
  - 13 tables: leads, activity_log, emails_sent, drip_queue, users, agents, tasks, onboarding_steps, resources, email_queue, referrals, recruiting_links, content_posts
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

## API Endpoints (all sessions complete)
- **Auth**: login, me, set-password
- **Leads**: full CRUD with lead_score, ai_draft, stage, temperature, /stats, /hot, backward-compatible POST
- **Tasks**: CRUD + /today (powers "Today's Actions")
- **Agents**: CRUD + /stats, /leaderboard, /tree, onboarding steps auto-created
- **Dashboard**: /overview, /funnel, /growth, /pipeline-health, /tasks-today
- **Resources**: CRUD + download tracking
- **Referrals**: CRUD with agent relationships
- **Recruiting Links**: CRUD + click tracking (40 seeded)
- **Content Posts**: CRUD + calendar view
- **Email**: /queue, /stats
- **AI Actions**: score-leads, who-to-call, draft-dm, weekly-plan, generate-tasks
- **Drip**: process, status, cancel
- **Settings/Notifications**: Resend API key, notification toggles

## Mission Control Dashboard (mission.tplcollective.ai)
- **Dashboard**: 5 metric cards, recruiting funnel, hottest leads, Today's Actions, pipeline health gauge, 4 AI quick-action buttons, activity feed, system status
- **Leads**: table + kanban, stage filters, search, scored lead cards, Draft DM per lead
- **Pipeline**: full kanban board
- **Agents**: stats cards, agent table with production/engagement, Add Agent with auto-onboarding
- **Email Drips**: stats + 5-step drip sequence reference
- **Content Hub**: social post grid with create/edit
- **Recruiting Links**: brokerage filter dropdown, grouped link tables with Copy button
- **Settings**: notification toggles, Resend API key

## Agent Portal (mission.tplcollective.ai/portal)
- JWT login page (agents use own credentials)
- Dashboard: onboarding progress ring, checklist with toggle-to-complete, referrals summary, quick access cards
- Resources: downloadable resource vault
- Referrals: tracker table + refer form
- Community: Discord invite + Book 1-on-1 with Joe
- LPT Tools: external links to Lofty CRM + Dotloop
- **DNS**: needs portal.tplcollective.ai A record pointing to 187.77.213.230 (Traefik routing ready)

## Local site (this repo)
- Static marketing site deployed via Vercel
- `api/leads.js` — Vercel serverless function, writes leads directly to Supabase
- `package.json` — has `@supabase/supabase-js` dependency
- Key pages: index, why-tpl, fee-plans, lpt-explained, commission-calculator, 27k-worksheet, resources

## Build Plan (v2 Architecture) — ALL COMPLETE
- Session 1: Database migration (13 Supabase tables, 40 recruiting links seeded) ✅
- Session 2: Core API (auth, leads, tasks, agents, dashboard) ✅
- Session 3: Extended API + AI actions (resources, referrals, content, lead scoring, draft DM, weekly plan) ✅
- Session 4: Mission Control frontend — Dashboard + Leads ✅
- Session 5: Mission Control frontend — Agents, Drips, Content Hub, Recruiting Links ✅
- Session 6: Agent Portal (login, onboarding, resources, referrals, community) ✅
- Session 7: Traefik routing, end-to-end testing (14/14 tests pass) ✅

## Remaining DNS Task
- Add A record: `portal.tplcollective.ai` → `187.77.213.230` in Namecheap
- Traefik is already configured to handle it — SSL will auto-provision via Let's Encrypt

## Rules
- TPL Collective ≠ LPT Realty — never conflate the two
- Never fabricate LPT financial figures
- Keep POST /api/leads backward compatible (live website uses it)
- Always confirm before deploying to the VPS
