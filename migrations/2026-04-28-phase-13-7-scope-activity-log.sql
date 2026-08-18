-- ════════════════════════════════════════════════════════════
-- Phase 13.7 — Tenant-scope activity_log
-- The audit caught that GET /api/activity returns all activity globally.
-- Adds workspace_id to activity_log + backfills all existing rows to Joe (1).
-- ════════════════════════════════════════════════════════════

ALTER TABLE activity_log ADD COLUMN IF NOT EXISTS workspace_id BIGINT REFERENCES workspaces(id) DEFAULT 1;
UPDATE activity_log SET workspace_id = 1 WHERE workspace_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_activity_log_workspace ON activity_log(workspace_id);
