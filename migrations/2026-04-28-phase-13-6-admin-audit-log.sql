-- ════════════════════════════════════════════════════════════
-- Phase 13.6 — Admin audit log
-- Records platform-admin actions: impersonation start/stop, invitations,
-- plan changes, and other privileged operations. Used for accountability.
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS admin_audit_log (
  id                  BIGSERIAL PRIMARY KEY,
  actor_user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  action              TEXT NOT NULL,
  target_user_id      BIGINT REFERENCES users(id) ON DELETE SET NULL,
  target_workspace_id BIGINT REFERENCES workspaces(id) ON DELETE SET NULL,
  meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_actor ON admin_audit_log(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_target_user ON admin_audit_log(target_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created ON admin_audit_log(created_at DESC);

ALTER TABLE admin_audit_log ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='admin_audit_log' AND policyname='Service role full access') THEN
    CREATE POLICY "Service role full access" ON admin_audit_log FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;
