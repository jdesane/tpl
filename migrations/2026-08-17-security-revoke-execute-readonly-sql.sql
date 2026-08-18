-- SECURITY FIX: close public access to execute_readonly_sql()
--
-- FOUND: 2026-08-17, during Phase 23 verification (Supabase security advisor).
--
-- THE PROBLEM
--   public.execute_readonly_sql(query text) is SECURITY DEFINER, so it executes as
--   its owner and RLS does not apply. EXECUTE was reachable by `anon`, which means
--   anyone holding the public anon key could call it via
--   POST /rest/v1/rpc/execute_readonly_sql and read ANY table -- including
--   users.password_hash, every lead, and settings.
--
--   The anon key is embedded client-side in
--   mission-control/app/static/recruiting/supabase-client.js, and anon keys are
--   public by design. RLS is what normally makes that safe. This function bypassed it.
--
--   The function's only guard was:
--       IF NOT (UPPER(TRIM(query)) LIKE 'SELECT%') THEN RAISE EXCEPTION ...
--   Reading the data IS the attack, so a SELECT-only check prevents nothing.
--
-- BLAST RADIUS CHECK BEFORE APPLYING
--   * grep across the repo (py/js/html/json): zero callers
--   * Supabase edge_logs, 24h window: zero calls to the RPC path
--   Conclusion: removing access is a no-op for the application.
--
-- THE GOTCHA
--   Postgres grants EXECUTE on functions to PUBLIC by default, and `anon` inherits
--   it through that. Revoking from `anon` alone LOOKS like it works but leaves
--   access intact. Revoking from PUBLIC is the part that actually closes it.
--
-- NOTE ON notify_buyer_intake()
--   Also flagged by the advisor, but it RETURNS trigger. PostgREST does not expose
--   trigger functions as RPC endpoints, so it is not callable from outside. No
--   action needed; the linter flags SECURITY DEFINER generically.

REVOKE EXECUTE ON FUNCTION public.execute_readonly_sql(text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.execute_readonly_sql(text) FROM anon;
REVOKE EXECUTE ON FUNCTION public.execute_readonly_sql(text) FROM authenticated;


-- STRONGER OPTION (preferred once you're comfortable nothing external uses it):
-- drop the function outright. An arbitrary-SQL function that bypasses RLS is a
-- standing liability with no upside -- ad-hoc queries can go through the Supabase
-- SQL editor or an authenticated MCP session instead.
--
-- DROP FUNCTION IF EXISTS public.execute_readonly_sql(text);


-- VERIFY: expected to return zero rows after this runs.
-- SELECT r.rolname
-- FROM pg_proc p
-- JOIN pg_namespace n ON n.oid = p.pronamespace
-- CROSS JOIN pg_roles r
-- WHERE n.nspname = 'public'
--   AND p.proname = 'execute_readonly_sql'
--   AND r.rolname IN ('anon','authenticated')
--   AND has_function_privilege(r.rolname, p.oid, 'EXECUTE');
