# TPL Collective — Mission Control + Agent Portal
# Phase 1 Architecture Spec & Build Guide
# For use with Claude Code

---

## SYSTEM CONTEXT

You are building the internal operating system for TPL Collective (tplcollective.ai) — a recruiting, coaching, and community platform built ON TOP of LPT Realty (the brokerage). TPL Collective is NOT a brokerage. Never conflate the two.

### Existing Infrastructure

**VPS:** Hostinger at 187.77.213.230
- SSH key on Joe's Mac: ~/.ssh/id_ed25519
- OS: Ubuntu 24
- Docker Compose running 4 containers: mission-control, openclaw-0rds, discord-bot, traefik

**Current Mission Control:**
- FastAPI (Python) + SQLite
- Docker source: /docker/mission-control/app/
- Settings: /docker/mission-control/data/settings.json
- Database: /data/mission.db
- Traefik reverse proxy with Let's Encrypt auto-SSL
- Basic auth: username `joe` (password is placeholder — needs changing)
- Currently only captures leads via POST to /api/leads
- main.py uses Resend HTTP API for email notifications

**Frontend (tplcollective.ai):**
- Vercel ← GitHub (github.com/jdesane/tpl, local: ~/Desktop/tpl)
- ~30 second auto-deploy via `deploy` terminal alias
- Design system: Bebas Neue (display), DM Sans (body), DM Mono (labels), accent #6c63ff, dark bg #0a0a0f

**CRITICAL Docker note:** Docker rebuilds require full `docker build` — `docker compose restart` does NOT pick up Python file changes.

**NEVER fabricate LPT Realty financial figures.** Compensation numbers, fees, percentages must be sourced from provided documents only.

---

## WHAT WE'RE BUILDING (Phase 1)

Two connected applications sharing the same FastAPI backend and SQLite database:

### 1. Mission Control (mission.tplcollective.ai) — Joe only
The command center for running the entire TPL operation.

### 2. Agent Portal (portal.tplcollective.ai) — TPL agents
The private member dashboard agents get access to after joining through TPL.

### 3. OpenClaw Integration
The existing OpenClaw container becomes the automation engine powering both interfaces.

---

## DATABASE SCHEMA

Redesign the SQLite database. The current `leads` table stays but gets expanded. New tables added.

```sql
-- Users & Auth
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'agent',  -- 'admin' (Joe), 'agent' (TPL members)
    avatar_initials TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Leads (expanded from existing)
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    current_brokerage TEXT,
    gci TEXT,
    team_or_solo TEXT,        -- 'team' or 'solo'
    motivations TEXT,         -- JSON array of motivation tags
    objections TEXT,          -- JSON array of objection notes
    source TEXT,              -- 'calculator', 'comparison_kw', 'comparison_exp', 'resource_download', 'worksheet', 'direct'
    source_page TEXT,         -- the specific URL they came from
    stage TEXT DEFAULT 'new', -- 'new', 'contacted', 'discovery_call', 'presentation', 'considering', 'signed', 'onboarding'
    assigned_to INTEGER REFERENCES users(id),
    notes TEXT,               -- JSON array of timestamped notes
    follow_up_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agents (people who have joined LPT through TPL)
CREATE TABLE agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),  -- links to their portal login
    lead_id INTEGER REFERENCES leads(id),  -- links back to their lead record
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    previous_brokerage TEXT,
    lpt_plan TEXT,            -- 'business_builder' or 'brokerage_partner'
    join_date DATE,
    sponsor_agent_id INTEGER REFERENCES agents(id),  -- who referred them (for network tree)
    status TEXT DEFAULT 'active',  -- 'active', 'inactive', 'churned'
    -- Production tracking (manually updated)
    transactions_ytd INTEGER DEFAULT 0,
    volume_ytd REAL DEFAULT 0,
    gci_ytd REAL DEFAULT 0,
    last_closing_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Onboarding Steps
CREATE TABLE onboarding_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id INTEGER REFERENCES agents(id),
    step_key TEXT NOT NULL,   -- 'transfer_license', 'setup_crm', 'setup_dotloop', 'join_discord', 'first_training', 'first_deal', 'first_recruit'
    step_label TEXT NOT NULL,
    step_order INTEGER,
    completed BOOLEAN DEFAULT 0,
    completed_at TIMESTAMP,
    notes TEXT
);

-- Resources / Assets
CREATE TABLE resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,            -- 'getting_started', 'lead_gen', 'social_media', 'ai_tools', 'revshare', 'scripts', 'templates', 'recruiting'
    file_path TEXT,           -- path to file on VPS or URL
    file_type TEXT,           -- 'pdf', 'video', 'link', 'template'
    access_level TEXT DEFAULT 'agent',  -- 'public', 'agent', 'admin'
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Activity Log (powers the activity feed)
CREATE TABLE activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,       -- 'joe', 'openclaw', 'calendly', 'system', or agent name
    action TEXT NOT NULL,      -- 'lead_created', 'lead_updated', 'email_sent', 'stage_changed', 'agent_joined', 'onboarding_step', 'content_published', 'alert'
    target_type TEXT,          -- 'lead', 'agent', 'resource', 'system'
    target_id INTEGER,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Email Sequences
CREATE TABLE email_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER REFERENCES leads(id),
    sequence_name TEXT,       -- 'nurture_5day', 'welcome', 'onboarding'
    step_number INTEGER,
    scheduled_at TIMESTAMP,
    sent_at TIMESTAMP,
    status TEXT DEFAULT 'queued',  -- 'queued', 'sent', 'failed', 'cancelled'
    subject TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Referrals (agent-to-agent tracking)
CREATE TABLE referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referring_agent_id INTEGER REFERENCES agents(id),
    referred_name TEXT NOT NULL,
    referred_email TEXT,
    referred_phone TEXT,
    status TEXT DEFAULT 'interested',  -- 'interested', 'call_scheduled', 'joined', 'declined'
    lead_id INTEGER REFERENCES leads(id),  -- links to leads table if they become a lead
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## API ROUTES

### Auth
```
POST   /api/auth/login          -- returns JWT token
POST   /api/auth/logout
GET    /api/auth/me              -- returns current user info
```

### Leads (admin only)
```
GET    /api/leads                -- list all, filterable by stage/source/date
POST   /api/leads               -- create (existing endpoint, keep backward compatible)
GET    /api/leads/:id
PUT    /api/leads/:id            -- update stage, notes, follow-up date
DELETE /api/leads/:id
GET    /api/leads/stats          -- pipeline counts, conversion rates, source breakdown
```

### Agents (admin only for full CRUD, agent can read own)
```
GET    /api/agents               -- list all agents with production data
POST   /api/agents               -- create new agent (usually from lead conversion)
GET    /api/agents/:id
PUT    /api/agents/:id           -- update production, status
GET    /api/agents/:id/onboarding    -- get onboarding steps
PUT    /api/agents/:id/onboarding/:step_key  -- mark step complete
GET    /api/agents/tree           -- network tree data (sponsor relationships)
GET    /api/agents/stats          -- total agents, growth, retention, avg production
GET    /api/agents/leaderboard    -- top producers
```

### Resources
```
GET    /api/resources             -- list all (filtered by access_level based on auth)
POST   /api/resources             -- admin: upload new resource
GET    /api/resources/:id
PUT    /api/resources/:id
DELETE /api/resources/:id
POST   /api/resources/:id/download  -- increment count, log activity
```

### Activity
```
GET    /api/activity              -- recent activity feed, paginated
POST   /api/activity              -- log new activity (used by OpenClaw)
```

### Email
```
GET    /api/emails/queue          -- admin: view queue
POST   /api/emails/send           -- admin/openclaw: trigger send
GET    /api/emails/stats          -- delivery rates, open rates
```

### Referrals (agent can manage own)
```
GET    /api/referrals             -- agent: their referrals. admin: all referrals
POST   /api/referrals             -- create referral
PUT    /api/referrals/:id         -- update status
```

### Dashboard
```
GET    /api/dashboard/overview    -- all metrics for command center
GET    /api/dashboard/funnel      -- pipeline funnel numbers
GET    /api/dashboard/growth      -- agent growth over time
```

---

## MISSION CONTROL UI (admin only)

Dark theme matching the TPL design system: bg #0a0a0f, surface #111118, accent #6c63ff, Bebas Neue headers, DM Sans body, DM Mono labels.

### Layout
- Fixed sidebar (200px) with nav groups: Command, Performance, Marketing, Systems
- Top bar with logo, system status pill, user avatar
- Main content area with tab bar for time ranges (7d / 30d / 90d / All)

### Dashboard page
- 5 metric cards: Total agents, Pipeline leads, Rev share/mo, Retention rate, Pipeline conversion
- Recruiting funnel (8-stage horizontal bar visualization)
- Recent leads list with avatar, name, source, stage badge
- Agent growth bar chart (12 months)
- Production leaderboard (top 5)
- Activity feed (OpenClaw actions, manual actions, Calendly events)
- OpenClaw automation status (email engine, lead tagger, discord bot, social scheduler, retention monitor, onboarding flow)
- Alerts panel (at-risk agents, stale leads, system issues)

### Leads page
- Kanban board view: columns for each pipeline stage
- Drag cards between columns to update stage
- Click card to expand: full lead details, notes, email history, follow-up date
- Filters: by source, by brokerage, by date range
- Bulk actions: tag, assign, export

### Pipeline page
- Funnel analytics: traffic → lead → contact → call → presentation → signed
- Conversion rates between each stage
- Average time in each stage
- Source attribution: which pages/tools drive the most conversions

### Agents page
- Table view of all TPL agents
- Columns: name, plan, join date, transactions YTD, volume, GCI, status, referrals
- Click to expand: full agent profile, onboarding status, production history, referral tree
- Network tree visualization (sponsor → recruit relationships)

### OpenClaw page
- Automation workflows with on/off toggles
- Queue viewer: pending emails, scheduled posts
- Activity log filtered to OpenClaw actions only
- Error log
- Model selector and credit burn tracker

### Assets page
- Resource library manager
- Upload, tag, categorize, set access level
- Download analytics per resource

---

## AGENT PORTAL UI

Same dark TPL design system but lighter touch — more welcoming, less operational.

### Layout
- Sidebar (200px): Home, Learn, Grow, LPT Tools
- Top bar: TPL Collective logo + "Agent portal", greeting with agent name, avatar
- Main content area

### Dashboard page (home)
- Welcome banner with onboarding progress ring (% complete)
- Onboarding checklist: Transfer license, Setup CRM, Configure Dotloop, Join Discord, First training module, First deal, First recruit. Each step has guide link and completion toggle.
- Quick access cards: Training library, AI tools suite, Resource vault, HybridShare tracker
- My referrals summary: referred count, joined count, in-progress count, with names and status
- Upcoming events: Weekly mastermind, LPT calls, community events

### Training page
- Video library organized by category: Getting Started, Lead Generation, Social Media, AI Tools, Revenue Share
- Each item: thumbnail, title, duration, completion badge
- Progress tracking per agent

### AI Tools page
- Prompt libraries for: listing descriptions, lead follow-up, content generation, market analysis
- GPT workflow templates
- Direct link to Dezzy.ai

### Resources page
- All PDFs, templates, scripts, checklists
- Search and filter by category
- Download tracking

### My Referrals page
- Full referral tracker: name, status, timeline
- Add new referral form
- Link to share with potential recruits

### Community page
- Discord invite link
- Upcoming mastermind schedule
- Book 1-on-1 with Joe (Calendly embed)
- Recognition wall (top producers, milestones)

### LPT Tools (external links)
- Lofty CRM → connect.lpt.com
- LPT Connect
- Dotloop
- Dezzy.ai

---

## OPENCLAW INTEGRATION

OpenClaw is already running at /docker/openclaw-0rds/. It needs API endpoints to call:

### Automated workflows OpenClaw runs:
1. **New lead welcome** — When POST /api/leads fires, OpenClaw sends welcome email via Resend, logs to activity feed
2. **Lead tagging** — OpenClaw reads source_page and auto-tags leads (e.g., "KW comparison lead", "calculator lead")
3. **Nurture sequence** — OpenClaw checks email_queue, sends scheduled emails, updates status
4. **Follow-up alerts** — OpenClaw scans leads older than 48h with no stage change, creates alert in activity log
5. **Onboarding automation** — When agent is created, OpenClaw creates their user account, sends Day 1 email, creates onboarding steps
6. **Retention monitoring** — Weekly scan: flag agents with no activity 30+ days
7. **Content scheduling** — OpenClaw publishes pre-written social posts on schedule (future)

### OpenClaw API endpoints it calls:
```
POST /api/activity          -- log its actions
PUT  /api/leads/:id         -- update lead stage/tags
POST /api/emails/send       -- trigger email sends
GET  /api/leads?stage=new&older_than=48h  -- find stale leads
GET  /api/agents?last_activity_before=30d  -- find inactive agents
```

### OpenClaw reports to Mission Control via:
- Activity log entries (visible in the feed)
- Email queue status
- Error log entries for failed operations

---

## AUTH SYSTEM

Simple JWT-based auth. No OAuth complexity needed.

- Joe logs in at mission.tplcollective.ai → gets admin JWT → sees Mission Control
- Agents log in at portal.tplcollective.ai → gets agent JWT → sees Agent Portal
- Joe creates agent accounts manually from Mission Control (or OpenClaw creates them during onboarding)
- Passwords hashed with bcrypt
- JWT expires in 7 days, refresh on activity
- Role-based route protection: admin routes check role='admin', agent routes check role='agent' or 'admin'

---

## TRAEFIK ROUTING

Add to existing Traefik config:
- mission.tplcollective.ai → mission-control container (admin UI + API)
- portal.tplcollective.ai → same container (agent UI, different frontend, same API)

Both UIs served from the same FastAPI app. The frontend is determined by the subdomain. API routes are shared.

---

## BUILD ORDER

### Step 1: Database migration
- Back up existing mission.db
- Run migration script to create new tables
- Migrate existing leads data into new schema
- Create Joe's admin user account

### Step 2: API routes
- Auth endpoints (login, logout, me)
- Expand leads CRUD with new fields
- Agents CRUD
- Onboarding steps CRUD
- Resources CRUD
- Activity log
- Email queue
- Referrals
- Dashboard aggregate endpoints

### Step 3: Mission Control frontend
- New HTML/CSS/JS frontend replacing the current basic UI
- Dark theme, TPL design system
- Dashboard with all widgets
- Leads kanban
- Agents table + network tree
- OpenClaw status panel
- Assets manager

### Step 4: Agent Portal frontend
- Separate HTML entry point served on portal subdomain
- Auth / login page
- Agent dashboard with onboarding
- Training library
- AI tools page
- Resources vault
- Referrals tracker
- Community page

### Step 5: OpenClaw wiring
- Update OpenClaw to call new API endpoints
- Configure automated workflows
- Test full loop: lead comes in → OpenClaw tags → sends email → logs activity → visible in Mission Control

### Step 6: Traefik + DNS
- Add portal.tplcollective.ai A record in Namecheap
- Update Traefik labels for portal subdomain routing
- SSL auto-provisioned by Traefik/Let's Encrypt

---

## FILE STRUCTURE ON VPS

```
/docker/mission-control/
├── app/
│   ├── main.py              -- FastAPI app, all API routes
│   ├── auth.py              -- JWT auth logic
│   ├── models.py            -- SQLAlchemy/Pydantic models
│   ├── database.py          -- DB connection + migration
│   ├── openclaw_hooks.py    -- webhook handlers for OpenClaw
│   ├── email_service.py     -- Resend integration
│   ├── static/
│   │   ├── admin/           -- Mission Control frontend files
│   │   │   ├── index.html
│   │   │   ├── leads.html
│   │   │   ├── agents.html
│   │   │   ├── openclaw.html
│   │   │   ├── assets.html
│   │   │   └── css/js/
│   │   └── portal/          -- Agent Portal frontend files
│   │       ├── index.html
│   │       ├── login.html
│   │       ├── training.html
│   │       ├── ai-tools.html
│   │       ├── resources.html
│   │       ├── referrals.html
│   │       ├── community.html
│   │       └── css/js/
│   └── requirements.txt
├── data/
│   ├── settings.json
│   └── mission.db
├── Dockerfile
└── docker-compose.yml
```

---

## DESIGN SYSTEM REFERENCE

```css
:root {
  --bg: #0a0a0f;
  --surface: #111118;
  --surface-2: #1a1a24;
  --surface-3: #222230;
  --border: #2a2a3a;
  --accent: #6c63ff;
  --accent-glow: rgba(108, 99, 255, 0.15);
  --green: #34d399;
  --red: #f87171;
  --amber: #fbbf24;
  --blue: #60a5fa;
  --text: #e8e8ed;
  --text-dim: #8888a0;
  --text-muted: #55556a;
}

/* Fonts */
font-family: 'Bebas Neue', sans-serif;  /* Display / headings */
font-family: 'DM Sans', sans-serif;     /* Body text */
font-family: 'DM Mono', monospace;      /* Labels, stats, code */
```

---

## IMPORTANT CONSTRAINTS

1. **Never fabricate financial figures.** LPT compensation numbers must come from provided documents.
2. **TPL Collective ≠ LPT Realty.** Always maintain the distinction in copy and code.
3. **Docker rebuilds require full `docker build`** — `docker compose restart` does NOT pick up Python changes.
4. **Keep the existing /api/leads POST endpoint backward compatible** — the live website (tplcollective.ai) is currently posting to it.
5. **Resend HTTP API for email** — not SMTP. API key goes in settings.json.
6. **SQLite is fine for this scale.** Don't migrate to Postgres unless we hit actual limits.
