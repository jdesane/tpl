"""Behavioural tests for entitlements.py against an in-memory fake Supabase."""
import sys, copy, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

now = datetime.now(timezone.utc)
past = (now - timedelta(days=1)).isoformat()
future = (now + timedelta(days=30)).isoformat()

DB = {
    "products": [
        {"id": 1, "slug": "listing-dashboard", "name": "Listing Dashboard", "status": "active",
         "sort_order": 10, "category": "listing", "icon": "H",
         "free_tier_limits": {"active_listings": 1}},
        {"id": 2, "slug": "cma-builder", "name": "CMA Builder", "status": "active",
         "sort_order": 30, "category": "pricing", "icon": "C",
         "free_tier_limits": {"cmas_per_month": 1}},
        {"id": 3, "slug": "coaching", "name": "Coaching Platform", "status": "active",
         "sort_order": 50, "category": "coaching", "icon": "T", "free_tier_limits": {}},
    ],
    "workspace_entitlements": [
        # ws 7: pro listing-dashboard
        {"id": 100, "workspace_id": 7, "product_id": 1, "status": "active", "source": "purchased",
         "tier": "pro", "starts_at": past, "expires_at": None, "limits": {}, "team_agreement_id": None},
        # ws 7: FREE cma-builder, capped at 1/mo
        {"id": 101, "workspace_id": 7, "product_id": 2, "status": "active", "source": "trial",
         "tier": "free", "starts_at": past, "expires_at": future, "limits": {}, "team_agreement_id": None},
        # ws 7: revoked coaching -> must not appear
        {"id": 102, "workspace_id": 7, "product_id": 3, "status": "revoked", "source": "comp",
         "tier": "pro", "starts_at": past, "expires_at": None, "limits": {}, "team_agreement_id": None},
    ],
    "team_agreements": [
        {"id": 500, "workspace_id": 9, "status": "active",  "agreement_version": "v1"},
        {"id": 501, "workspace_id": 9, "status": "terminated", "agreement_version": "v1"},
        {"id": 502, "workspace_id": 42, "status": "active", "agreement_version": "v1"},
    ],
    "entitlement_events": [],
    "bundles": [], "bundle_products": [],
}

_next_id = [900]


class Q:
    def __init__(self, table, rows, op="select", payload=None):
        self.table, self.rows, self.op, self.payload = table, rows, op, payload
        self.filters = []
        self._limit = None

    def eq(self, k, v):   self.filters.append((k, v)); return self
    def in_(self, k, v):  self.filters.append(("__in__", (k, v))); return self
    def lt(self, k, v):   return self
    def order(self, *a, **k): return self
    def limit(self, n):   self._limit = n; return self
    def single(self):     return self

    def _match(self, row):
        for k, v in self.filters:
            if k == "__in__":
                key, vals = v
                if row.get(key) not in vals: return False
            elif row.get(k) != v:
                return False
        return True

    def execute(self):
        tbl = DB[self.table]
        if self.op == "select":
            out = [copy.deepcopy(r) for r in tbl if self._match(r)]
            if self._limit: out = out[:self._limit]
            return type("R", (), {"data": out})()
        if self.op == "insert":
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            made = []
            for r in rows:
                r = dict(r); _next_id[0] += 1; r.setdefault("id", _next_id[0])
                tbl.append(r); made.append(copy.deepcopy(r))
            return type("R", (), {"data": made})()
        if self.op == "update":
            made = []
            for r in tbl:
                if self._match(r):
                    r.update(self.payload); made.append(copy.deepcopy(r))
            return type("R", (), {"data": made})()
        raise AssertionError(self.op)


class FakeTable:
    def __init__(self, name): self.name = name
    def select(self, *a, **k): return Q(self.name, DB[self.name], "select")
    def insert(self, payload, *a, **k): return Q(self.name, DB[self.name], "insert", payload)
    def update(self, payload, *a, **k): return Q(self.name, DB[self.name], "update", payload)


class FakeSupabase:
    def table(self, name): return FakeTable(name)


import entitlements as e
e.setup(lambda n: FakeTable(n), FakeSupabase())

PASS = FAIL = 0
def check(label, cond, extra=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  [PASS] {label}")
    else:    FAIL += 1; print(f"  [FAIL] {label} {extra}")

def raises(label, fn, code, key=None):
    try:
        fn()
        check(label, False, "-> no exception raised")
    except HTTPException as ex:
        d = ex.detail
        got_key = d.get("error") if isinstance(d, dict) else None
        ok = ex.status_code == code and (key is None or got_key == key)
        check(label, ok, f"-> {ex.status_code} {got_key}")


class Req:
    def __init__(self, ws): self.state = type("S", (), {"workspace_id": ws, "user": {"sub": 1}})()


print("\nget_entitlements() — only active rows surface")
ents = e.get_entitlements(7)
check("granted pro product present",  "listing-dashboard" in ents)
check("granted free product present", "cma-builder" in ents)
check("REVOKED product hidden",       "coaching" not in ents)
check("free tier exposes limits",     ents["cma-builder"]["limits"] == {"cmas_per_month": 1})
check("pro tier exposes no limits",   ents["listing-dashboard"]["limits"] == {})

print("\nrequire_entitlement() — the gate")
check("passes for entitled product", e.require_entitlement("listing-dashboard")(Req(7))["tier"] == "pro")
raises("403 for revoked product", lambda: e.require_entitlement("coaching")(Req(7)), 403, "entitlement_required")
raises("403 for workspace with nothing", lambda: e.require_entitlement("listing-dashboard")(Req(999)), 403, "entitlement_required")
raises("401 when unauthenticated", lambda: e.require_entitlement("listing-dashboard")(Req(None)), 401)

print("\ncheck_limit() — free-tier caps enforced at the API")
check("under cap passes", e.check_limit(7, "cma-builder", "cmas_per_month", 0) is None)
raises("at cap blocks", lambda: e.check_limit(7, "cma-builder", "cmas_per_month", 1), 403, "limit_reached")
raises("over cap blocks", lambda: e.check_limit(7, "cma-builder", "cmas_per_month", 5), 403, "limit_reached")
check("pro tier ignores caps", e.check_limit(7, "listing-dashboard", "active_listings", 9999) is None)
check("unknown limit key passes", e.check_limit(7, "cma-builder", "nonexistent_key", 9999) is None)

print("\nCOMPLIANCE GUARD — team_member requires a signed agreement")
raises("team_member with NO agreement rejected",
       lambda: e.grant(9, "listing-dashboard", "team_member"), 400, "team_agreement_required")
raises("team_member with TERMINATED agreement rejected",
       lambda: e.grant(9, "listing-dashboard", "team_member", team_agreement_id=501), 400)
raises("team_member with ANOTHER workspace's agreement rejected",
       lambda: e.grant(9, "listing-dashboard", "team_member", team_agreement_id=502), 400)
raises("team_member with nonexistent agreement rejected",
       lambda: e.grant(9, "listing-dashboard", "team_member", team_agreement_id=99999), 400)
row = e.grant(9, "listing-dashboard", "team_member", team_agreement_id=500)
check("team_member WITH valid agreement accepted", row["source"] == "team_member")
check("agreement id persisted on the row", row["team_agreement_id"] == 500)
check("granted product is now usable", e.has_entitlement(9, "listing-dashboard"))

print("\nsource validation")
raises("invalid source rejected", lambda: e.grant(9, "coaching", "recruited"), 400)
raises("invalid tier rejected", lambda: e.grant(9, "coaching", "comp", tier="platinum"), 400)
check("non-team source clears agreement id",
      e.grant(9, "coaching", "comp", team_agreement_id=500)["team_agreement_id"] is None)

print("\nrevoke() — cache invalidates, history preserved")
check("entitled before revoke", e.has_entitlement(9, "listing-dashboard"))
rev = e.revoke(9, "listing-dashboard", reason="testing")
check("status flipped to revoked", rev["status"] == "revoked")
check("row NOT deleted", any(r["id"] == rev["id"] for r in DB["workspace_entitlements"]))
check("gate closes immediately (cache invalidated)", not e.has_entitlement(9, "listing-dashboard"))
raises("revoked product 403s at the gate",
       lambda: e.require_entitlement("listing-dashboard")(Req(9)), 403, "entitlement_required")

print("\naudit trail")
actions = [ev["action"] for ev in DB["entitlement_events"]]
check("grant recorded", "granted" in actions)
check("revoke recorded", "revoked" in actions)
agreement_events = [ev for ev in DB["entitlement_events"]
                    if (ev.get("meta") or {}).get("team_agreement_id") == 500]
check("team grant records agreement id in audit meta", len(agreement_events) >= 1)

print("\nre-grant restores access")
e.grant(9, "listing-dashboard", "purchased", stripe_subscription_id="sub_123")
check("re-granted product usable again", e.has_entitlement(9, "listing-dashboard"))
check("source updated to purchased", e.get_entitlement(9, "listing-dashboard")["source"] == "purchased")

print(f"\n{'='*46}\n{PASS} passed, {FAIL} failed\n{'='*46}")
sys.exit(1 if FAIL else 0)
