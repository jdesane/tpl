# Claude Code Prompt — Mission Control + Agent Portal Phase 1
# Paste this into Claude Code after running: cd ~/Desktop && claude

---

I'm building the Mission Control dashboard and Agent Portal for TPL Collective. The full architecture spec is in this file — read it first:

[paste the contents of tpl-mission-control-architecture.md here, or reference the file path if you've saved it locally]

The existing Mission Control is running on my VPS at 187.77.213.230 in Docker at /docker/mission-control/. SSH key is at ~/.ssh/id_ed25519.

Here's what I need you to do for Phase 1, in order:

## Step 1: SSH into the VPS and audit the current state
- Check what's in /docker/mission-control/app/main.py
- Check the current database schema in /data/mission.db
- Check the docker-compose.yml and Traefik config
- Check what's in /docker/openclaw-0rds/
- Report back what exists before changing anything

## Step 2: Back up and migrate the database
- Back up the existing mission.db
- Run the migration to create all new tables (users, agents, onboarding_steps, resources, activity_log, email_queue, referrals)
- Expand the existing leads table with new columns
- Create my admin account (email: joe@tplcollective.ai, I'll set the password)
- Migrate any existing lead data into the new schema

## Step 3: Build the API layer
- Expand main.py with all the new routes (auth, leads CRUD, agents CRUD, onboarding, resources, activity, email queue, referrals, dashboard aggregates)
- JWT auth with bcrypt password hashing
- Role-based access (admin vs agent)
- Keep the existing POST /api/leads endpoint backward compatible — the live site is hitting it right now

## Step 4: Build the Mission Control frontend
- New admin UI at /docker/mission-control/app/static/admin/
- Dark theme: bg #0a0a0f, surface #111118, accent #6c63ff
- Fonts: Bebas Neue (display), DM Sans (body), DM Mono (labels)
- Dashboard page with: 5 metric cards, recruiting funnel, recent leads, agent growth chart, production leaderboard, activity feed, OpenClaw status, alerts
- Leads page with kanban board (drag between stages)
- Agents page with table + detail view
- OpenClaw status page
- Assets manager page

## Step 5: Build the Agent Portal frontend
- At /docker/mission-control/app/static/portal/
- Login page
- Dashboard: welcome banner with onboarding progress, checklist, quick access cards, referrals summary, upcoming events
- Training library page
- AI tools page
- Resources vault page
- Referrals tracker page
- Community page with Discord link + Calendly embed

## Step 6: Traefik routing for portal.tplcollective.ai
- Update the docker-compose.yml to route portal.tplcollective.ai to the same container
- The FastAPI app serves admin UI on mission.* and portal UI on portal.* based on the Host header

## Step 7: Docker rebuild and test
- Full docker build (not just restart)
- Test all API endpoints
- Test both UIs
- Verify the existing tplcollective.ai lead form still works

Start with Step 1 — audit everything first, then we'll go step by step.
