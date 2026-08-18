-- ════════════════════════════════════════════════════════════
-- Phase 13.5 — Invitations
-- Joe creates invitations; recipient hits /signup?token=xxx to claim.
-- Token + 7-day expiry; single-use (used_at set on signup).
-- ════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS invitations (
  id                 BIGSERIAL PRIMARY KEY,
  email              TEXT NOT NULL,
  name               TEXT,
  plan               TEXT NOT NULL DEFAULT 'basic' CHECK (plan IN ('basic','mid','elite')),
  invited_by_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token              TEXT NOT NULL UNIQUE,
  expires_at         TIMESTAMPTZ NOT NULL,
  used_at            TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations(token);
CREATE INDEX IF NOT EXISTS idx_invitations_email ON invitations(email);

ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='invitations' AND policyname='Service role full access') THEN
    CREATE POLICY "Service role full access" ON invitations FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;
