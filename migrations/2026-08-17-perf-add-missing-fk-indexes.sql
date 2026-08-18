-- PERFORMANCE: add covering indexes on foreign keys that lacked them.
--
-- FOUND: 2026-08-17 by the weekly Supabase performance advisor, then verified
-- directly against pg_index (the advisor rates these INFO, but it does not weigh
-- table size — at 171k rows the email_send_log one is a real full scan).
--
-- Postgres does NOT auto-create an index on the referencing side of a foreign key.
-- Every one of these columns is filtered on hot Mission Control paths:
--   email_send_log.contact_id  -> contact profile + communications log
--   tasks.lead_id / agent_id   -> /api/tasks/today ("Today's Actions")
--   lead_activity.lead_id      -> profile activity timeline
--   leads.assigned_to          -> dashboard + pipeline views
--
-- Row counts at time of writing (note how far CLAUDE.md had drifted):
--   email_send_log 171,713 | tasks 17,158 | lead_activity 3,034 | leads 476
--
-- Plain CREATE INDEX rather than CONCURRENTLY: these complete in well under a
-- second at this scale, and CONCURRENTLY cannot run inside a transaction block.

CREATE INDEX IF NOT EXISTS idx_email_send_log_contact ON email_send_log (contact_id);
CREATE INDEX IF NOT EXISTS idx_tasks_lead             ON tasks (lead_id);
CREATE INDEX IF NOT EXISTS idx_tasks_agent            ON tasks (agent_id);
CREATE INDEX IF NOT EXISTS idx_lead_activity_lead     ON lead_activity (lead_id);
CREATE INDEX IF NOT EXISTS idx_leads_assigned_to      ON leads (assigned_to);
