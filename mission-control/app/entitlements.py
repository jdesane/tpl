"""
Phase 23 - Entitlement layer.

One backend, one database, two customer-facing brands:
  * TPL Collective (portal.tplcollective.ai) - team members, arrive via recruiting
  * RETechbox      (retechbox.com)           - any agent, any brokerage, paid software

Access to a tool is one `workspace_entitlements` row, regardless of which door the
customer came through. Plans (basic/mid/elite) stay as-is for legacy CRM gating;
entitlements are the source of truth for TOOL access.

COMPLIANCE (read before editing - see the migration header for full context):
  LPT prohibits offering items of value in exchange for being named sponsor.
  Team benefits are permitted. Therefore:
    * No `source` value references sponsorship or recruiting.
    * source='team_member' requires a signed team_agreement (DB CHECK + guard here).
    * Sponsorship status must NEVER be an input to an access decision. Do not read
      it in this module, and do not join it into any query that feeds one.

AUTHORIZATION RULE - do not weaken:
  Never authorize from the JWT. Tokens live 7 days, so a revoked product would stay
  usable for a week. The JWT may carry an entitlement snapshot for rendering nav and
  hiding UI only. Every gated route re-checks here, against the DB (through a short
  TTL cache). Hiding a nav item is not gating.

Wired from main.py the same way coaching.py / cma.py are:
    import entitlements as _ent_mod
    _ent_mod.setup(db, supabase)
    app.include_router(_ent_mod.router)
    app.include_router(_ent_mod.me_router)
    app.include_router(_ent_mod.public_router)

Gate an existing router by adding a dependency at include time:
    app.include_router(
        _cma_mod.router,
        dependencies=[Depends(_ent_mod.require_entitlement("cma-builder"))],
    )

NOTE ON SCOPING: entitlement tables are deliberately NOT added to TENANT_TABLES.
db() would auto-filter to the *caller's* workspace, which silently breaks every admin
endpoint that acts on someone else's workspace. Every query here passes workspace_id
explicitly instead.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Callable, Any, Dict, List
from datetime import datetime, timezone
import threading
import time as _time
import logging

log = logging.getLogger("tpl.entitlements")

# JWT-gated admin surface. `/api/admin` is already platform-only via
# PLATFORM_ONLY_PREFIXES in main.py, so these are workspace-1 only for free.
router = APIRouter(prefix="/api/admin", tags=["entitlements-admin"])

# JWT-gated self-serve surface - any authenticated user, their own workspace.
me_router = APIRouter(prefix="/api/me", tags=["entitlements-me"])

# Public surface for the RETechbox marketing site.
# Requires "/api/public/" in PUBLIC_API_PREFIXES in main.py.
public_router = APIRouter(prefix="/api/public", tags=["entitlements-public"])


# Injected by main.py via setup() - avoids circular imports.
_db: Optional[Callable[[str], Any]] = None
_supabase: Any = None


def setup(db_callable, supabase_client):
    """Called from main.py after `db` and `supabase` are defined."""
    global _db, _supabase
    _db = db_callable
    _supabase = supabase_client


# ════════════════════════════════════════════════════════════
# Constants

VALID_SOURCES = ("purchased", "trial", "team_member", "comp", "internal")
VALID_STATUSES = ("active", "trialing", "past_due", "revoked", "expired")
VALID_TIERS = ("free", "pro")

ACTIVE_STATUSES = ("active", "trialing")

UPGRADE_URL = "https://retechbox.com/pricing"

# Per-worker caches. Multiple uvicorn workers each hold their own; TTL bounds
# staleness. grant()/revoke() clear the acting worker immediately, others catch
# up within ENTITLEMENT_TTL.
ENTITLEMENT_TTL = 60.0    # seconds
PRODUCT_TTL = 300.0       # seconds - registry changes rarely

_ent_cache: Dict[int, tuple] = {}       # workspace_id -> (expires_at, {slug: {...}})
_ent_cache_lock = threading.Lock()

_product_cache: Optional[tuple] = None  # (expires_at, {slug: product_row})
_product_cache_lock = threading.Lock()


# ════════════════════════════════════════════════════════════
# Helpers

def _parse_ts(value) -> Optional[datetime]:
    """Supabase returns ISO timestamps; normalize to aware UTC datetimes."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        txt = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(txt)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _is_active(row: dict) -> bool:
    """An entitlement is usable when it is active/trialing and inside its window."""
    if row.get("status") not in ACTIVE_STATUSES:
        return False
    now = datetime.now(timezone.utc)
    starts = _parse_ts(row.get("starts_at"))
    if starts and starts > now:
        return False
    expires = _parse_ts(row.get("expires_at"))
    if expires and expires <= now:
        return False
    return True


def _products_by_slug(force: bool = False) -> Dict[str, dict]:
    """Cached product registry keyed by slug."""
    global _product_cache
    now = _time.monotonic()
    with _product_cache_lock:
        if not force and _product_cache and _product_cache[0] > now:
            return _product_cache[1]
    rows = (_supabase.table("products").select("*").execute().data) or []
    by_slug = {r["slug"]: r for r in rows}
    with _product_cache_lock:
        _product_cache = (now + PRODUCT_TTL, by_slug)
    return by_slug


def _product_or_404(slug: str) -> dict:
    product = _products_by_slug().get(slug)
    if not product:
        # One forced refresh in case the product was just created.
        product = _products_by_slug(force=True).get(slug)
    if not product:
        raise HTTPException(404, f"Unknown product '{slug}'")
    return product


def invalidate(workspace_id: Optional[int] = None):
    """Drop cached entitlements. Called after every grant/revoke."""
    with _ent_cache_lock:
        if workspace_id is None:
            _ent_cache.clear()
        else:
            _ent_cache.pop(int(workspace_id), None)


# ════════════════════════════════════════════════════════════
# Core read API

def get_entitlements(workspace_id: int, force: bool = False) -> Dict[str, dict]:
    """
    Every ACTIVE entitlement for a workspace, keyed by product slug:

        {"listing-dashboard": {"tier": "pro", "status": "active",
                               "source": "purchased", "limits": {...},
                               "expires_at": None, "product": {...}}, ...}

    Inactive rows (revoked/expired/past_due) are omitted - callers only ever
    see what the workspace can currently use.
    """
    ws = int(workspace_id)
    now = _time.monotonic()
    if not force:
        with _ent_cache_lock:
            hit = _ent_cache.get(ws)
            if hit and hit[0] > now:
                return hit[1]

    rows = (
        _supabase.table("workspace_entitlements")
        .select("*")
        .eq("workspace_id", ws)
        .execute()
        .data
    ) or []

    products = _products_by_slug()
    by_id = {p["id"]: p for p in products.values()}

    out: Dict[str, dict] = {}
    for row in rows:
        if not _is_active(row):
            continue
        product = by_id.get(row["product_id"])
        if not product or product.get("status") == "retired":
            continue
        # Workspace override wins over the product default, key by key.
        limits = dict(product.get("free_tier_limits") or {})
        limits.update(row.get("limits") or {})
        out[product["slug"]] = {
            "product_id": product["id"],
            "slug": product["slug"],
            "name": product["name"],
            "icon": product.get("icon"),
            "category": product.get("category"),
            "tier": row.get("tier", "pro"),
            "status": row.get("status"),
            "source": row.get("source"),
            "expires_at": row.get("expires_at"),
            "limits": limits if row.get("tier") == "free" else {},
        }

    with _ent_cache_lock:
        _ent_cache[ws] = (now + ENTITLEMENT_TTL, out)
    return out


def get_entitlement(workspace_id: int, product_slug: str) -> Optional[dict]:
    return get_entitlements(workspace_id).get(product_slug)


def has_entitlement(workspace_id: int, product_slug: str) -> bool:
    return product_slug in get_entitlements(workspace_id)


# ════════════════════════════════════════════════════════════
# Gating

def require_entitlement(product_slug: str):
    """
    FastAPI dependency factory. Returns a SYNC dependency on purpose: FastAPI runs
    sync dependencies in a threadpool, so the blocking Supabase read never stalls
    the event loop (see Phase 15.9).

        app.include_router(mod.router,
            dependencies=[Depends(require_entitlement("cma-builder"))])
    """
    def _dep(request: Request):
        ws = getattr(request.state, "workspace_id", None)
        if ws is None:
            raise HTTPException(401, "Authentication required")
        ent = get_entitlement(ws, product_slug)
        if not ent:
            product = _products_by_slug().get(product_slug) or {}
            raise HTTPException(
                403,
                {
                    "detail": f"{product.get('name', product_slug)} is not enabled on this account",
                    "error": "entitlement_required",
                    "product": product_slug,
                    "product_name": product.get("name", product_slug),
                    "upgrade_url": UPGRADE_URL,
                },
            )
        return ent
    return _dep


def require_any_entitlement(product_slugs: List[str]):
    """
    Passes when the workspace holds ANY of these products.

    Exists because some surfaces belong to more than one product. The seller net
    sheet ships inside the Listing Dashboard but is also sold standalone, so an
    account holding either one must reach it. Same sync-dependency reasoning as
    require_entitlement().
    """
    def _dep(request: Request):
        ws = getattr(request.state, "workspace_id", None)
        if ws is None:
            raise HTTPException(401, "Authentication required")
        held = get_entitlements(ws)
        for slug in product_slugs:
            if slug in held:
                return held[slug]
        products = _products_by_slug()
        names = [products.get(s, {}).get("name", s) for s in product_slugs]
        raise HTTPException(403, {
            "detail": "This account does not include " + " or ".join(names),
            "error": "entitlement_required",
            "product": product_slugs[0],
            "accepts_any_of": product_slugs,
            "upgrade_url": UPGRADE_URL,
        })
    return _dep


def check_limit(workspace_id: int, product_slug: str, key: str, current: int) -> None:
    """
    Enforce a free-tier cap at the API. Call BEFORE creating the capped resource:

        check_limit(ws, "listing-dashboard", "active_listings", active_count)

    No-ops for pro tier, for missing keys, and for a cap of -1 (unlimited).
    Raises 403 when the cap is reached.
    """
    ent = get_entitlement(workspace_id, product_slug)
    if not ent:
        raise HTTPException(403, {
            "detail": f"{product_slug} is not enabled on this account",
            "error": "entitlement_required",
            "product": product_slug,
            "upgrade_url": UPGRADE_URL,
        })
    if ent.get("tier") != "free":
        return
    cap = (ent.get("limits") or {}).get(key)
    if cap is None or cap == -1:
        return
    if current >= cap:
        raise HTTPException(403, {
            "detail": f"Your free plan allows {cap}. Upgrade to add more.",
            "error": "limit_reached",
            "product": product_slug,
            "limit_key": key,
            "limit": cap,
            "current": current,
            "upgrade_url": UPGRADE_URL,
        })


# ════════════════════════════════════════════════════════════
# Write API

def _log_event(workspace_id: int, product_id: Optional[int], entitlement_id: Optional[int],
               action: str, *, actor_user_id=None, actor_type="admin",
               from_status=None, to_status=None, from_source=None, to_source=None,
               reason=None, meta=None):
    """Append-only. Never raises into the caller - an audit failure must not
    roll back a legitimate grant, but it must be visible in the logs."""
    try:
        _supabase.table("entitlement_events").insert({
            "workspace_id": int(workspace_id),
            "product_id": product_id,
            "entitlement_id": entitlement_id,
            "action": action,
            "actor_user_id": actor_user_id,
            "actor_type": actor_type,
            "from_status": from_status,
            "to_status": to_status,
            "from_source": from_source,
            "to_source": to_source,
            "reason": reason,
            "meta": meta or {},
        }).execute()
    except Exception as e:  # noqa: BLE001
        log.error("entitlement_events insert failed ws=%s action=%s: %s",
                  workspace_id, action, e)


def _assert_team_agreement(workspace_id: int, team_agreement_id: Optional[int]):
    """
    COMPLIANCE GUARD. A team_member grant requires an active signed agreement
    belonging to that workspace. The DB has the same CHECK; this exists to return
    a clear 400 instead of a raw constraint violation, and to verify the agreement
    is real, active, and actually theirs.
    """
    if not team_agreement_id:
        raise HTTPException(400, {
            "detail": "A signed team agreement is required before granting team benefits.",
            "error": "team_agreement_required",
        })
    row = (
        _supabase.table("team_agreements")
        .select("id,workspace_id,status")
        .eq("id", int(team_agreement_id))
        .limit(1)
        .execute()
        .data
    )
    if not row:
        raise HTTPException(400, "Team agreement not found")
    agreement = row[0]
    if agreement.get("status") != "active":
        raise HTTPException(400, "Team agreement is not active")
    if int(agreement.get("workspace_id") or 0) != int(workspace_id):
        raise HTTPException(400, "Team agreement belongs to a different workspace")


def grant(workspace_id: int, product_slug: str, source: str, *,
          tier: str = "pro", actor_user_id=None, actor_type: str = "admin",
          team_agreement_id: Optional[int] = None, expires_at=None,
          stripe_subscription_id: Optional[str] = None,
          stripe_subscription_item_id: Optional[str] = None,
          limits: Optional[dict] = None, notes: Optional[str] = None,
          reason: Optional[str] = None) -> dict:
    """Grant or re-grant a product. Idempotent on (workspace_id, product_id)."""
    if source not in VALID_SOURCES:
        raise HTTPException(400, f"Invalid source '{source}'. One of: {', '.join(VALID_SOURCES)}")
    if tier not in VALID_TIERS:
        raise HTTPException(400, f"Invalid tier '{tier}'. One of: {', '.join(VALID_TIERS)}")

    if source == "team_member":
        _assert_team_agreement(workspace_id, team_agreement_id)
    else:
        team_agreement_id = None

    product = _product_or_404(product_slug)
    ws = int(workspace_id)

    existing = (
        _supabase.table("workspace_entitlements")
        .select("*")
        .eq("workspace_id", ws)
        .eq("product_id", product["id"])
        .limit(1)
        .execute()
        .data
    )

    payload = {
        "workspace_id": ws,
        "product_id": product["id"],
        "status": "trialing" if source == "trial" else "active",
        "source": source,
        "tier": tier,
        "team_agreement_id": team_agreement_id,
        "granted_by_user_id": actor_user_id,
        "granted_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
        "revoked_at": None,
        "revoke_reason": None,
        "stripe_subscription_id": stripe_subscription_id,
        "stripe_subscription_item_id": stripe_subscription_item_id,
        "limits": limits or {},
        "notes": notes,
    }

    if existing:
        prior = existing[0]
        row = (
            _supabase.table("workspace_entitlements")
            .update(payload)
            .eq("id", prior["id"])
            .execute()
            .data
        )[0]
        action = "granted" if prior.get("status") not in ACTIVE_STATUSES else "upgraded"
        _log_event(ws, product["id"], row["id"], action,
                   actor_user_id=actor_user_id, actor_type=actor_type,
                   from_status=prior.get("status"), to_status=row["status"],
                   from_source=prior.get("source"), to_source=source,
                   reason=reason,
                   meta={"team_agreement_id": team_agreement_id, "tier": tier})
    else:
        row = (
            _supabase.table("workspace_entitlements").insert(payload).execute().data
        )[0]
        _log_event(ws, product["id"], row["id"],
                   "trial_started" if source == "trial" else "granted",
                   actor_user_id=actor_user_id, actor_type=actor_type,
                   to_status=row["status"], to_source=source, reason=reason,
                   meta={"team_agreement_id": team_agreement_id, "tier": tier})

    invalidate(ws)
    return row


def revoke(workspace_id: int, product_slug: str, *, actor_user_id=None,
           actor_type: str = "admin", reason: Optional[str] = None) -> dict:
    """
    Revoke access. Never deletes the row - status flips to 'revoked' and the
    history stays queryable.
    """
    product = _product_or_404(product_slug)
    ws = int(workspace_id)

    existing = (
        _supabase.table("workspace_entitlements")
        .select("*")
        .eq("workspace_id", ws)
        .eq("product_id", product["id"])
        .limit(1)
        .execute()
        .data
    )
    if not existing:
        raise HTTPException(404, f"No entitlement for '{product_slug}' on this workspace")

    prior = existing[0]
    row = (
        _supabase.table("workspace_entitlements")
        .update({
            "status": "revoked",
            "revoked_at": datetime.now(timezone.utc).isoformat(),
            "revoke_reason": reason,
        })
        .eq("id", prior["id"])
        .execute()
        .data
    )[0]

    _log_event(ws, product["id"], row["id"], "revoked",
               actor_user_id=actor_user_id, actor_type=actor_type,
               from_status=prior.get("status"), to_status="revoked",
               from_source=prior.get("source"), reason=reason)
    invalidate(ws)
    return row


def grant_bundle(workspace_id: int, bundle_slug: str, source: str, **kw) -> List[dict]:
    """Grant every product in a bundle. One entitlement row per product."""
    bundle = (
        _supabase.table("bundles").select("id,slug,name")
        .eq("slug", bundle_slug).limit(1).execute().data
    )
    if not bundle:
        raise HTTPException(404, f"Unknown bundle '{bundle_slug}'")

    links = (
        _supabase.table("bundle_products").select("product_id")
        .eq("bundle_id", bundle[0]["id"]).execute().data
    ) or []

    by_id = {p["id"]: p for p in _products_by_slug().values()}
    out = []
    for link in links:
        product = by_id.get(link["product_id"])
        if product:
            out.append(grant(workspace_id, product["slug"], source, **kw))
    return out


def expire_due() -> int:
    """
    Flip entitlements whose expires_at has passed to 'expired'. Safe to run from
    a cron; reads are already expiry-aware, so this is bookkeeping that keeps the
    admin UI honest rather than a security control.
    """
    now = datetime.now(timezone.utc).isoformat()
    due = (
        _supabase.table("workspace_entitlements")
        .select("id,workspace_id,product_id,status,source")
        .in_("status", list(ACTIVE_STATUSES))
        .lt("expires_at", now)
        .execute()
        .data
    ) or []
    for row in due:
        _supabase.table("workspace_entitlements").update(
            {"status": "expired"}
        ).eq("id", row["id"]).execute()
        _log_event(row["workspace_id"], row["product_id"], row["id"], "expired",
                   actor_type="system", from_status=row.get("status"),
                   to_status="expired", from_source=row.get("source"),
                   reason="expires_at elapsed")
        invalidate(row["workspace_id"])
    return len(due)


# ════════════════════════════════════════════════════════════
# Request models

class GrantIn(BaseModel):
    product: Optional[str] = None          # product slug
    bundle: Optional[str] = None           # bundle slug (alternative to product)
    source: str
    tier: str = "pro"
    team_agreement_id: Optional[int] = None
    expires_at: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    limits: Optional[dict] = None
    notes: Optional[str] = None
    reason: Optional[str] = None


class RevokeIn(BaseModel):
    reason: Optional[str] = None


class ProductIn(BaseModel):
    slug: Optional[str] = None
    name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    monthly_price_cents: Optional[int] = None
    annual_price_cents: Optional[int] = None
    stripe_product_id: Optional[str] = None
    stripe_monthly_price_id: Optional[str] = None
    stripe_annual_price_id: Optional[str] = None
    is_sellable: Optional[bool] = None
    is_public: Optional[bool] = None
    free_tier_limits: Optional[dict] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[str] = None


class TeamAgreementIn(BaseModel):
    workspace_id: int
    agreement_version: str
    signed_at: str
    lead_id: Optional[int] = None
    user_id: Optional[int] = None
    signed_name: Optional[str] = None
    signed_ip: Optional[str] = None
    document_url: Optional[str] = None
    obligations: Optional[dict] = None
    notes: Optional[str] = None


def _actor(request: Request) -> Optional[int]:
    user = getattr(request.state, "user", None) or {}
    return user.get("sub") if isinstance(user, dict) else None


# ════════════════════════════════════════════════════════════
# Admin endpoints  (/api/admin/* is platform-only via main.py middleware)

@router.get("/products")
def admin_list_products():
    rows = (
        _supabase.table("products").select("*").order("sort_order").execute().data
    ) or []
    return {"products": rows}


@router.post("/products")
def admin_create_product(body: ProductIn):
    if not body.slug or not body.name:
        raise HTTPException(400, "slug and name are required")
    payload = {k: v for k, v in body.dict().items() if v is not None}
    row = (_supabase.table("products").insert(payload).execute().data)[0]
    _products_by_slug(force=True)
    return row


@router.patch("/products/{product_id}")
def admin_update_product(product_id: int, body: ProductIn):
    payload = {k: v for k, v in body.dict().items() if v is not None}
    if not payload:
        raise HTTPException(400, "Nothing to update")
    rows = (
        _supabase.table("products").update(payload).eq("id", product_id).execute().data
    )
    if not rows:
        raise HTTPException(404, "Product not found")
    _products_by_slug(force=True)
    invalidate()  # limits/status may have changed for everyone
    return rows[0]


@router.get("/workspaces")
def admin_list_workspaces():
    """
    Every workspace with an entitlement summary, for the admin toggle grid.

    One query per table rather than per workspace: with a few dozen accounts an
    N+1 here would be a dozen round trips on a page load.
    """
    workspaces = (
        _supabase.table("workspaces")
        .select("id,name,plan,account_type,brand,created_at")
        .order("id").execute().data
    ) or []

    ents = (
        _supabase.table("workspace_entitlements")
        .select("workspace_id,product_id,status,source,tier,expires_at,starts_at")
        .execute().data
    ) or []
    by_id = {p["id"]: p for p in _products_by_slug().values()}

    grouped: Dict[int, list] = {}
    for e in ents:
        if _is_active(e):
            product = by_id.get(e["product_id"])
            if product:
                grouped.setdefault(e["workspace_id"], []).append({
                    "slug": product["slug"], "name": product["name"],
                    "source": e["source"], "tier": e["tier"],
                })

    owners: Dict[int, str] = {}
    for u in (_supabase.table("users").select("id,email,workspace_id")
              .execute().data or []):
        if u.get("workspace_id") and u["workspace_id"] not in owners:
            owners[u["workspace_id"]] = u.get("email")

    for w in workspaces:
        held = grouped.get(w["id"], [])
        w["entitlements"] = held
        w["entitlement_count"] = len(held)
        w["owner_email"] = owners.get(w["id"])
    return {"workspaces": workspaces, "product_count": len(by_id)}


@router.get("/workspaces/{workspace_id}/entitlements")
def admin_list_entitlements(workspace_id: int):
    """
    Every entitlement row for a workspace including inactive ones, joined against
    the full product registry so the admin UI can render a complete toggle grid.
    """
    rows = (
        _supabase.table("workspace_entitlements")
        .select("*")
        .eq("workspace_id", workspace_id)
        .execute()
        .data
    ) or []
    by_product = {r["product_id"]: r for r in rows}

    products = sorted(_products_by_slug().values(), key=lambda p: p.get("sort_order", 0))
    grid = []
    for product in products:
        row = by_product.get(product["id"])
        grid.append({
            "product": {
                "id": product["id"], "slug": product["slug"], "name": product["name"],
                "category": product.get("category"), "icon": product.get("icon"),
                "free_tier_limits": product.get("free_tier_limits") or {},
            },
            "entitlement": row,
            "enabled": bool(row and _is_active(row)),
        })
    return {"workspace_id": workspace_id, "entitlements": grid}


@router.post("/workspaces/{workspace_id}/entitlements")
def admin_grant(workspace_id: int, body: GrantIn, request: Request):
    if not body.product and not body.bundle:
        raise HTTPException(400, "Provide either 'product' or 'bundle'")

    kwargs = dict(
        tier=body.tier,
        actor_user_id=_actor(request),
        team_agreement_id=body.team_agreement_id,
        expires_at=body.expires_at,
        stripe_subscription_id=body.stripe_subscription_id,
        limits=body.limits,
        notes=body.notes,
        reason=body.reason,
    )
    if body.bundle:
        return {"granted": grant_bundle(workspace_id, body.bundle, body.source, **kwargs)}
    return {"granted": [grant(workspace_id, body.product, body.source, **kwargs)]}


@router.delete("/workspaces/{workspace_id}/entitlements/{product_slug}")
def admin_revoke(workspace_id: int, product_slug: str, body: RevokeIn, request: Request):
    if not body.reason:
        raise HTTPException(400, "A reason is required when revoking access")
    return revoke(workspace_id, product_slug,
                  actor_user_id=_actor(request), reason=body.reason)


@router.get("/workspaces/{workspace_id}/entitlement-events")
def admin_entitlement_events(workspace_id: int, limit: int = 100):
    rows = (
        _supabase.table("entitlement_events")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .limit(min(limit, 500))
        .execute()
        .data
    ) or []
    by_id = {p["id"]: p for p in _products_by_slug().values()}
    for row in rows:
        product = by_id.get(row.get("product_id"))
        row["product_name"] = product["name"] if product else None
        row["product_slug"] = product["slug"] if product else None
    return {"events": rows}


@router.get("/team-agreements")
def admin_list_team_agreements(workspace_id: Optional[int] = None):
    q = _supabase.table("team_agreements").select("*")
    if workspace_id is not None:
        q = q.eq("workspace_id", workspace_id)
    return {"agreements": (q.order("signed_at", desc=True).execute().data) or []}


@router.post("/team-agreements")
def admin_create_team_agreement(body: TeamAgreementIn):
    payload = {k: v for k, v in body.dict().items() if v is not None}
    payload.setdefault("obligations", {})
    return (_supabase.table("team_agreements").insert(payload).execute().data)[0]


@router.patch("/team-agreements/{agreement_id}")
def admin_terminate_team_agreement(agreement_id: int, body: RevokeIn):
    """
    Terminating an agreement does NOT auto-revoke entitlements - that is a
    deliberate business decision, not a side effect. The admin UI flags team
    entitlements whose agreement is terminated so they can be handled explicitly.
    """
    rows = (
        _supabase.table("team_agreements")
        .update({
            "status": "terminated",
            "terminated_at": datetime.now(timezone.utc).isoformat(),
            "terminated_reason": body.reason,
        })
        .eq("id", agreement_id)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(404, "Team agreement not found")
    return rows[0]


# ════════════════════════════════════════════════════════════
# Self-serve

@me_router.get("/entitlements")
def my_entitlements(request: Request):
    """What this workspace can use right now. Drives nav rendering on both brands."""
    ws = getattr(request.state, "workspace_id", None)
    if ws is None:
        raise HTTPException(401, "Authentication required")
    ents = get_entitlements(ws)
    return {
        "workspace_id": ws,
        "entitlements": ents,
        "slugs": sorted(ents.keys()),
    }


# ════════════════════════════════════════════════════════════
# Public (RETechbox marketing site)

@public_router.get("/products")
def public_products():
    """Public product registry for the pricing page. Public products only."""
    rows = (
        _supabase.table("products")
        .select("slug,name,tagline,description,category,icon,sort_order,"
                "monthly_price_cents,annual_price_cents,free_tier_limits,is_sellable")
        .eq("is_public", True)
        .eq("status", "active")
        .order("sort_order")
        .execute()
        .data
    ) or []
    bundles = (
        _supabase.table("bundles")
        .select("slug,name,description,monthly_price_cents,annual_price_cents,sort_order")
        .eq("is_public", True)
        .eq("status", "active")
        .order("sort_order")
        .execute()
        .data
    ) or []
    return {"products": rows, "bundles": bundles}
