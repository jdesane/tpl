-- /report-call: agents from Meta lead ads pick a real open slot, the slot is
-- HELD, and nothing reaches Joe's calendar until he approves it.
--
--   held  agent picked requested_start; slot blocked for everyone else;
--         Joe approves (-> confirmed) or offers other times (-> new)
--
-- requested_start / requested_minutes hold the agent's pick until approval
-- copies it into confirmed_start. utm keeps the ad attribution with the call.

ALTER TABLE booking_requests DROP CONSTRAINT IF EXISTS booking_requests_status_check;
ALTER TABLE booking_requests ADD CONSTRAINT booking_requests_status_check
  CHECK (status IN ('new', 'held', 'times_sent', 'confirmed', 'closed'));

ALTER TABLE booking_requests ADD COLUMN IF NOT EXISTS requested_start   TIMESTAMPTZ;
ALTER TABLE booking_requests ADD COLUMN IF NOT EXISTS requested_minutes INTEGER;
ALTER TABLE booking_requests ADD COLUMN IF NOT EXISTS utm               JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE booking_requests ADD COLUMN IF NOT EXISTS source            TEXT;

-- two people tapping the same slot at the same moment: the second insert fails
CREATE UNIQUE INDEX IF NOT EXISTS booking_requests_one_hold_per_slot
  ON booking_requests (requested_start) WHERE status = 'held';
