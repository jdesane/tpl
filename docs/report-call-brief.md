# Context: /report-call booking flow (TPL Collective)

Paste this into a new Claude session before working on the Meta lead-ad booking page.
Repo: ~/Desktop/tpl. CLAUDE.md in the repo root has the full project history and rules.
(This file is excluded from the public site by .vercelignore. Never put secrets in it.)

## What it is
- URL: https://tplcollective.ai/report-call (file: report-call.html, static site on Vercel,
  auto-deploys on push to main).
- THE URL IS LOCKED INTO A PUBLISHED META INSTANT FORM ("Commission Report"). Never rename,
  move or redirect it. Content may change.
- Meta form thank-you button URL:
  https://tplcollective.ai/report-call?utm_source=facebook&utm_medium=lead_form&utm_campaign=commission-report
- Visitors already gave name, email, phone, transactions (12 mo), avg price, split and brokerage
  on Meta. So the page asks ONLY name + email. Never re-ask qualifying questions here.
- /book is a different page for cold traffic (8-step questionnaire, Joe emails times, agent picks
  on /pick). Do not change /book when working on /report-call.

## Non-negotiable rules
- NO SELF-SERVE BOOKING. Nothing lands on Joe's calendar without his approval. A weekend
  auto-booked call (from a Calendly / Zoom Scheduler page) is why this exists. Never add Calendly,
  Zoom Scheduler, Cal.com or any auto-confirming calendar.
- Never ask about sponsorship anywhere in the funnel (LPT compliance).
- TPL Collective is a community, NOT a brokerage. Never conflate it with LPT Realty.
- No em dashes in any copy. Use hyphens or rewrite.
- Joe approves every outbound message before it reaches real leads.
- All email goes through main.send_email() (suppression, rate limits, logging). Never call
  Resend directly from Mission Control.
- Always confirm with Joe before deploying to the VPS.
- Never put passwords, tokens or keys in any repo file.

## How the flow works
1. Page loads open slots from GET https://mission.tplcollective.ai/api/public/one-on-one/slots
   (mobile-first: day chips, then time buttons; nearly all traffic is the FB/IG in-app browser).
2. Agent picks a time + enters name/email -> POST /api/public/one-on-one/hold with UTMs (+fbclid).
   Creates a booking_requests row with status 'held'. The slot is blocked for everyone.
   Page shows "Your time is held: <time>. I'll confirm by email shortly..." (NOT "you're booked").
   Fires Meta pixel Schedule here (in the agent's browser).
3. Joe gets an email immediately with three HMAC-signed links: Approve (phone) /
   Approve as Zoom / Offer other times. A GET only shows a confirm page; the action is a POST, so
   email link scanners can't approve. Same actions exist in Mission Control:
   1-on-1 Requests -> "Awaiting approval" tab.
4. Approve -> the existing _confirm(): agent + Joe get confirmation emails with an .ics,
   a "1-on-1 call with X" task lands on the call date, lead stage -> discovery_call,
   LPT Recruiting opportunity -> appointment_booked.
   Offer other times -> request goes to 'new' (Needs times); Joe uses Send times (/pick flow).
5. Reminders (cron POST /api/one-on-one/process every 15 min, loopback only):
   held and unapproved after 2h, or within 3h of the call -> nudge Joe (every 2h, with links);
   held time passes unapproved -> released to 'new', agent told new times are coming, Joe alerted;
   confirmed -> Joe prep email 60 min before, agent reminder 90 min before.

## Where things live
- Backend: mission-control/app/one_on_one.py (FastAPI, Mission Control in Docker on the VPS,
  /docker/mission-control). Shared helpers come from recruit_newsletter.py (settings, _activity,
  _send_for_token, signing secret = env JWT_SECRET).
  Public: GET /api/public/one-on-one/slots, POST /hold, GET|POST /approve,
          POST /request (the /book form), GET|POST /pick
  Admin (JWT, platform-only): /api/one-on-one/requests, /counts, /requests/{id}/approve|release|
          send-times|confirm|close|reopen, GET|PUT /availability, POST /process
- Mission Control UI: mission-control/app/static/index.html -> nav "1-on-1 Requests" (badge = new + held),
  tabs Awaiting approval / Needs times / Waiting on agent / Confirmed / Closed, Availability panel.
- Database (Supabase, workspace_id 1):
  booking_requests: status new|held|times_sent|confirmed|closed; requested_start/_minutes (the hold),
    confirmed_start/_minutes, meeting_type phone|zoom, utm jsonb, source ('report-call'), answers jsonb,
    token uuid, proposed_slots, last_nudge_at, prep_sent_at, agent_reminder_sent_at.
    Partial unique index: one 'held' row per requested_start.
  leads: matched by email (ilike) in workspace 1; unknown email -> new lead source='meta-report-call',
    tags report-call + unmatched-meta-lead.
  opportunities: pipeline_id 1 "LPT Recruiting", keyed by contact_id, status 'open'. Only moves
    forward: hold -> engaged; confirm -> appointment_booked.
  lead_activity types: call_time_held, call_confirmed, call_time_released, call_time_expired.
  tasks: task_type one_on_one ("Approve 1-on-1: ...", "1-on-1 call with ...").
- Migrations: migrations/2026-09-28-recruit-newsletter.sql, migrations/2026-10-06-report-call-holds.sql
- Tests: mission-control/app/tests/test_one_on_one.py (120 assertions, in-memory fake Supabase,
  clock frozen at Mon 2026-10-05 8 AM ET). Run with any venv that has fastapi, pydantic,
  python-multipart: `python tests/test_one_on_one.py` from mission-control/app.

## Live settings (VPS data/settings.json, key "recruit_newsletter")
- availability: Mon/Tue/Thu/Fri 09:30-15:00 ET, Wed 10:00-17:00 ET, no weekends;
  slot_minutes 20, buffer_minutes 10, min_notice_hours 4, days_ahead 10.
  Open slots exclude anything held, confirmed, or already offered via Send times (plus buffer).
  Google Calendar is NOT checked; Joe's approval is the double-booking guard.
- from_address: Joe DeSane <joe@tplcollective.co> (cold sends stay on .co to protect the main domain)
- reply_to: joe@tplcollective.ai
- notify_email (Joe's alerts): joe@desaneteam.com
- zoom_link: Joe's recurring "No fixed time" Zoom meeting (waiting room for everyone, no
  join-before-host, no auto-record, meeting chat off; one link reused for all calls)
- mailing_address: EMPTY (only needed for the weekly newsletter, not for calls)

## Tracking
- Meta pixels on the page: BOTH 501610407036223 and 34463024060012400 (PageView on load,
  Schedule on hold). Joe still needs to confirm in Events Manager which is tied to the lead-ad
  account, then drop the other. Also GA4 G-X6WMCMBJ9R.
- Page: noindex, nofollow. No site nav. Logo not a link. Only link is /privacy-policy.
  Footer: "Joe DeSane | TPL Collective | LPT Realty".

## Deploying changes (confirm with Joe first)
1. git pull; compare VPS files with git HEAD (shasum) so you never overwrite work deployed
   from elsewhere.
2. Apply any migration BEFORE shipping code that depends on it.
3. Back up VPS files as <file>.pre-<tag>-<timestamp>, rsync changed files, then
   `docker compose build && docker compose up -d` in /docker/mission-control.
4. Verify the Meta leads webhook verification still echoes its challenge, and
   /api/public/one-on-one/slots returns days.
5. Site: commit + push main (Vercel deploys in ~30s). Exclude .DS_Store and untracked working files.
   After any .vercelignore change, confirm https://tplcollective.ai/CLAUDE.md returns 404.
6. Any new public non-/api path on mission.tplcollective.ai must be added to BOTH Traefik routers
   in the VPS docker-compose.yml or it ends up behind basic auth.
7. Don't create test bookings on production; they email Joe and create real leads.

## Open items
- Joe to confirm which Meta pixel to keep.
- Zoom Scheduler booking page "LPT Realty Intro Call" should be turned off in Zoom
  (the JC Realty recovery email in outbound/ still links to it).
- Possible future: Google Calendar free/busy check so busy times never show as open.
- Meta can't pass the lead's name/email into the button URL, so agents type them; the page asks
  them to use the same email as on the form so the hold matches their lead.
