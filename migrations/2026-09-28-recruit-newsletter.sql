-- Weekly recruiting newsletter ("The Weekly" to non-LPT agents on the recruit list).
--
-- Deliberately separate from newsletter_issues / newsletter_subscribers: those
-- tables hold the South Florida Thunder baseball newsletter, a different
-- audience and a different shape. Do not merge them.
--
-- Flow: draft -> test sent to Joe -> approved (audience snapshotted into
-- recruit_newsletter_sends as 'queued') -> sending (cron drains the queue in
-- batches through main.send_email()) -> sent. Cancel flips queued rows to
-- 'skipped'. Nothing reaches a lead without an approved issue, and an issue
-- cannot be approved unless a test was sent after its last content edit.
--
-- Platform-only (workspace 1). RLS on with a service_role policy,
-- set_updated_at() trigger, same as the Phase 23 tables.

CREATE TABLE IF NOT EXISTS recruit_newsletter_issues (
  id              BIGSERIAL PRIMARY KEY,
  workspace_id    INTEGER NOT NULL DEFAULT 1,
  issue_date      DATE NOT NULL,
  subject         TEXT NOT NULL DEFAULT '',
  preheader       TEXT NOT NULL DEFAULT '',
  content         JSONB NOT NULL DEFAULT '{}'::jsonb,
  status          TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'approved', 'sending', 'sent', 'cancelled')),
  -- bumped only when subject/preheader/content change, so approval can
  -- require a test that is newer than the last real edit
  content_updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  test_sent_at    TIMESTAMPTZ,
  test_sent_to    TEXT,
  approved_at     TIMESTAMPTZ,
  approved_by     INTEGER,
  scheduled_for   TIMESTAMPTZ,
  -- max sends per calendar day (UTC) for this issue; warms a cold list
  daily_cap       INTEGER NOT NULL DEFAULT 150 CHECK (daily_cap > 0),
  -- lease so overlapping cron runs never double-send
  processing_until TIMESTAMPTZ,
  total_recipients INTEGER NOT NULL DEFAULT 0,
  sent_count      INTEGER NOT NULL DEFAULT 0,
  failed_count    INTEGER NOT NULL DEFAULT 0,
  skipped_count   INTEGER NOT NULL DEFAULT 0,
  completed_at    TIMESTAMPTZ,
  created_by      INTEGER,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recruit_newsletter_issues_status_idx
  ON recruit_newsletter_issues (status, scheduled_for);

CREATE TABLE IF NOT EXISTS recruit_newsletter_sends (
  id              BIGSERIAL PRIMARY KEY,
  workspace_id    INTEGER NOT NULL DEFAULT 1,
  issue_id        BIGINT NOT NULL REFERENCES recruit_newsletter_issues(id) ON DELETE CASCADE,
  lead_id         BIGINT REFERENCES leads(id) ON DELETE SET NULL,
  email           TEXT NOT NULL,
  first_name      TEXT,
  status          TEXT NOT NULL DEFAULT 'queued'
                  CHECK (status IN ('queued', 'sent', 'failed', 'skipped')),
  error           TEXT,
  sent_at         TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- one email per address per issue, however many lead rows share it
CREATE UNIQUE INDEX IF NOT EXISTS recruit_newsletter_sends_issue_email_uq
  ON recruit_newsletter_sends (issue_id, lower(email));
CREATE INDEX IF NOT EXISTS recruit_newsletter_sends_issue_status_idx
  ON recruit_newsletter_sends (issue_id, status);
CREATE INDEX IF NOT EXISTS recruit_newsletter_sends_lead_idx
  ON recruit_newsletter_sends (lead_id);

ALTER TABLE recruit_newsletter_issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE recruit_newsletter_sends  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_role_all ON recruit_newsletter_issues;
CREATE POLICY service_role_all ON recruit_newsletter_issues FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS service_role_all ON recruit_newsletter_sends;
CREATE POLICY service_role_all ON recruit_newsletter_sends FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS recruit_newsletter_issues_updated_at ON recruit_newsletter_issues;
CREATE TRIGGER recruit_newsletter_issues_updated_at
BEFORE UPDATE ON recruit_newsletter_issues
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ════════════════════════════════════════════════════════════
-- Per-recipient engagement: tracked links, class videos, watch
-- sessions, and the 1-on-1 pre-qualifying form.
-- ════════════════════════════════════════════════════════════

-- Every send gets an unguessable token. It rides on every link in that
-- recipient's email so clicks, video watches and bookings attribute to
-- the right lead. A forwarded email attributes to the original recipient.
ALTER TABLE recruit_newsletter_sends
  ADD COLUMN IF NOT EXISTS token UUID NOT NULL DEFAULT gen_random_uuid();
CREATE UNIQUE INDEX IF NOT EXISTS recruit_newsletter_sends_token_uq
  ON recruit_newsletter_sends (token);

CREATE TABLE IF NOT EXISTS recruit_newsletter_clicks (
  id            BIGSERIAL PRIMARY KEY,
  workspace_id  INTEGER NOT NULL DEFAULT 1,
  issue_id      BIGINT REFERENCES recruit_newsletter_issues(id) ON DELETE CASCADE,
  send_id       BIGINT REFERENCES recruit_newsletter_sends(id) ON DELETE CASCADE,
  lead_id       BIGINT REFERENCES leads(id) ON DELETE SET NULL,
  url           TEXT NOT NULL,
  label         TEXT,
  -- corporate link scanners (Safe Links, Mimecast) "click" every link within
  -- seconds of delivery; those rows are kept but excluded from reports
  suspected_bot BOOLEAN NOT NULL DEFAULT false,
  user_agent    TEXT,
  clicked_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS recruit_newsletter_clicks_issue_idx ON recruit_newsletter_clicks (issue_id);
CREATE INDEX IF NOT EXISTS recruit_newsletter_clicks_send_idx ON recruit_newsletter_clicks (send_id, clicked_at);

-- Joe's pre-recorded classes. Hosted on YouTube, watched on tplcollective.ai/watch
-- so viewing can be tied to a lead (YouTube itself only reports totals).
CREATE TABLE IF NOT EXISTS tpl_videos (
  id               BIGSERIAL PRIMARY KEY,
  workspace_id     INTEGER NOT NULL DEFAULT 1,
  slug             TEXT NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$'),
  youtube_id       TEXT NOT NULL CHECK (youtube_id ~ '^[A-Za-z0-9_-]{11}$'),
  title            TEXT NOT NULL,
  description      TEXT NOT NULL DEFAULT '',
  duration_seconds INTEGER,
  published        BOOLEAN NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS video_watch_sessions (
  id               BIGSERIAL PRIMARY KEY,
  workspace_id     INTEGER NOT NULL DEFAULT 1,
  session_id       TEXT NOT NULL UNIQUE,
  video_slug       TEXT NOT NULL,
  send_id          BIGINT REFERENCES recruit_newsletter_sends(id) ON DELETE SET NULL,
  issue_id         BIGINT REFERENCES recruit_newsletter_issues(id) ON DELETE SET NULL,
  lead_id          BIGINT REFERENCES leads(id) ON DELETE SET NULL,
  -- seconds actually played (skipping ahead does not count)
  watched_seconds  INTEGER NOT NULL DEFAULT 0,
  max_position     INTEGER NOT NULL DEFAULT 0,
  duration         INTEGER NOT NULL DEFAULT 0,
  pct              INTEGER NOT NULL DEFAULT 0,
  user_agent       TEXT,
  started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS video_watch_sessions_lead_idx ON video_watch_sessions (lead_id, video_slug);
CREATE INDEX IF NOT EXISTS video_watch_sessions_issue_idx ON video_watch_sessions (issue_id);

-- 1-on-1 requests (tplcollective.ai/book). Replaces self-serve Calendly booking:
-- nothing lands on Joe's calendar until he has read the answers, offered times,
-- and the agent picked one.
--   new         form submitted, Joe has not offered times yet
--   times_sent  Joe emailed 2-4 options; waiting on the agent
--   confirmed   agent picked a slot (or Joe marked it after a reply)
--   closed      not a fit / no response / done
CREATE TABLE IF NOT EXISTS booking_requests (
  id              BIGSERIAL PRIMARY KEY,
  workspace_id    INTEGER NOT NULL DEFAULT 1,
  lead_id         BIGINT REFERENCES leads(id) ON DELETE SET NULL,
  send_id         BIGINT REFERENCES recruit_newsletter_sends(id) ON DELETE SET NULL,
  issue_id        BIGINT REFERENCES recruit_newsletter_issues(id) ON DELETE SET NULL,
  answers         JSONB NOT NULL DEFAULT '{}'::jsonb,
  status          TEXT NOT NULL DEFAULT 'new'
                  CHECK (status IN ('new', 'times_sent', 'confirmed', 'closed')),
  -- unguessable key for the agent's pick-a-time page
  token           UUID NOT NULL DEFAULT gen_random_uuid(),
  proposed_slots  JSONB NOT NULL DEFAULT '[]'::jsonb,   -- [{"start": ISO, "minutes": 30}]
  times_note      TEXT,
  meeting_type    TEXT NOT NULL DEFAULT 'phone' CHECK (meeting_type IN ('phone', 'zoom')),
  times_sent_at   TIMESTAMPTZ,
  confirmed_start TIMESTAMPTZ,
  confirmed_minutes INTEGER,
  confirmed_at    TIMESTAMPTZ,
  agent_note      TEXT,             -- "none of these work" message from the agent
  closed_reason   TEXT,
  -- reminder bookkeeping so nothing sits unnoticed
  last_nudge_at   TIMESTAMPTZ,
  prep_sent_at    TIMESTAMPTZ,
  agent_reminder_sent_at TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS booking_requests_issue_idx ON booking_requests (issue_id);
CREATE INDEX IF NOT EXISTS booking_requests_status_idx ON booking_requests (status, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS booking_requests_token_uq ON booking_requests (token);

ALTER TABLE recruit_newsletter_clicks ENABLE ROW LEVEL SECURITY;
ALTER TABLE tpl_videos               ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_watch_sessions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE booking_requests         ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS service_role_all ON recruit_newsletter_clicks;
CREATE POLICY service_role_all ON recruit_newsletter_clicks FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS service_role_all ON tpl_videos;
CREATE POLICY service_role_all ON tpl_videos FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS service_role_all ON video_watch_sessions;
CREATE POLICY service_role_all ON video_watch_sessions FOR ALL TO service_role USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS service_role_all ON booking_requests;
CREATE POLICY service_role_all ON booking_requests FOR ALL TO service_role USING (true) WITH CHECK (true);

DROP TRIGGER IF EXISTS tpl_videos_updated_at ON tpl_videos;
CREATE TRIGGER tpl_videos_updated_at
BEFORE UPDATE ON tpl_videos
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS booking_requests_updated_at ON booking_requests;
CREATE TRIGGER booking_requests_updated_at
BEFORE UPDATE ON booking_requests
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
