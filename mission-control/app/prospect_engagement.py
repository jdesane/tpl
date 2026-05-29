"""
Phase 16 — Prospect Engagement module.

Tracks page-level engagement on private prospect briefs hosted on
tplcollective.ai (e.g. /jay-dural). Reusable per-prospect infra.

Architecture (mirrors coaching.py):
  - `setup(db, supabase)` is called by main.py after both are defined
  - workspace-scoped via the `db()` wrapper (prospect_engagement_events
    + prospect_briefs added to TENANT_TABLES in main.py)
  - ingest endpoint mounted under /api/tracking/* so it is public
    (the brief page POSTs from the browser with no JWT)
  - read + admin endpoints under /api/prospect-engagement/* live behind
    the standard JWT middleware

Notification rail:
  - Uses main.send_email() so suppression / rate limits / send log all apply
  - Notify recipient resolved per-prospect from prospect_briefs.notify_email,
    falling back to settings.engagement_notify_email
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Callable, Any, List
from datetime import datetime, timezone
import json
import re


# Public ingest sits under /api/tracking/* (already whitelisted in main.py).
# Read + admin endpoints sit under /api/prospect-engagement/* (JWT-gated).
ingest_router = APIRouter(prefix="/api/tracking", tags=["prospect-engagement"])
router = APIRouter(prefix="/api/prospect-engagement", tags=["prospect-engagement"])

_db: Optional[Callable[[str], Any]] = None
_supabase: Any = None


def setup(db_callable, supabase_client):
    global _db, _supabase
    _db = db_callable
    _supabase = supabase_client


# ════════════════════════════════════════════════════════════
# Pydantic models
# ════════════════════════════════════════════════════════════

class ProspectBriefIn(BaseModel):
    slug: str
    display_name: Optional[str] = None
    notify_email: Optional[str] = None


class ProspectBriefUpdate(BaseModel):
    display_name: Optional[str] = None
    notify_email: Optional[str] = None


# ════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
NOTIFIABLE_EVENTS = {"page_open"}


def _is_valid_slug(slug: str) -> bool:
    return bool(slug) and len(slug) <= 80 and bool(SLUG_RE.match(slug))


def _lookup_brief(slug: str) -> Optional[dict]:
    """Look up the brief record for `slug`. Returns None if not seeded."""
    try:
        r = _supabase.table("prospect_briefs").select("*").eq("slug", slug).limit(1).execute()
        if r.data:
            return r.data[0]
    except Exception:
        pass
    return None


def _send_open_notification(slug: str, visit_number: int, visitor_id: str,
                            referrer: Optional[str], user_agent: Optional[str]) -> None:
    """Notify Joe (or the brief's override notify_email) on a fresh page_open."""
    try:
        from main import send_email as _send, load_settings as _load_settings
    except Exception as e:
        print(f"[prospect-engagement] could not import send_email: {e}")
        return

    settings = _load_settings() or {}
    brief = _lookup_brief(slug) or {}
    notify_email = (brief.get("notify_email")
                    or settings.get("engagement_notify_email")
                    or "joe@tplcollective.ai")
    display = brief.get("display_name") or slug

    smtp_cfg = settings.get("smtp") or {}
    subject = f"{display} just opened the brief (visit #{visit_number})"
    dashboard_url = f"https://mission.tplcollective.ai/#engagement/{slug}"

    html = f"""
    <div style="font-family: -apple-system, sans-serif; padding: 24px; max-width: 560px; color: #1a1a26;">
      <h2 style="color: #6c63ff; margin: 0 0 16px;">{display} opened the brief</h2>
      <table style="font-size: 14px; line-height: 1.6;">
        <tr><td style="color: #8888aa; padding-right: 12px;">Visit</td><td><strong>#{visit_number}</strong></td></tr>
        <tr><td style="color: #8888aa; padding-right: 12px;">Visitor</td><td><code>{visitor_id}</code></td></tr>
        <tr><td style="color: #8888aa; padding-right: 12px;">Referrer</td><td>{referrer or '(direct)'}</td></tr>
        <tr><td style="color: #8888aa; padding-right: 12px;">User Agent</td><td style="font-size: 12px;">{user_agent or '-'}</td></tr>
        <tr><td style="color: #8888aa; padding-right: 12px;">Time</td><td>{datetime.now(timezone.utc).isoformat()}</td></tr>
      </table>
      <p style="margin-top: 24px;">
        <a href="{dashboard_url}"
           style="display: inline-block; background: #6c63ff; color: #fff; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: 600;">
          Open engagement dashboard
        </a>
      </p>
      <p style="color: #8888aa; font-size: 12px; margin-top: 24px;">
        TPL Mission Control - prospect engagement notification
      </p>
    </div>
    """
    try:
        _send(smtp_cfg, notify_email, subject, html,
              from_address="TPL Mission Control <alerts@tplcollective.ai>",
              campaign=f"prospect-open-{slug}")
    except Exception as e:
        print(f"[prospect-engagement] notify failed: {e}")


# ════════════════════════════════════════════════════════════
# PUBLIC INGEST  (POST /api/tracking/prospect-engagement)
# ════════════════════════════════════════════════════════════

@ingest_router.post("/prospect-engagement")
async def ingest_engagement(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON")

    if not isinstance(payload, dict):
        raise HTTPException(400, "payload must be an object")

    required = ("event", "prospect_id", "visitor_id", "session_id")
    for k in required:
        if not payload.get(k):
            raise HTTPException(400, f"missing {k}")

    slug = str(payload["prospect_id"])[:80]
    if not _is_valid_slug(slug):
        raise HTTPException(400, "invalid prospect_id")

    event = str(payload["event"])[:64]
    visitor_id = str(payload["visitor_id"])[:64]
    session_id = str(payload["session_id"])[:64]
    try:
        visit_number = int(payload.get("visit_number") or 1)
    except (TypeError, ValueError):
        visit_number = 1

    # Resolve workspace_id from the brief lookup if seeded; otherwise default to 1.
    brief = _lookup_brief(slug)
    ws_id = (brief or {}).get("workspace_id") or 1

    row = {
        "prospect_id": slug,
        "visitor_id": visitor_id,
        "session_id": session_id,
        "visit_number": visit_number,
        "event": event,
        "url": (payload.get("url") or "")[:2000],
        "referrer": (payload.get("referrer") or None),
        "user_agent": (payload.get("user_agent") or "")[:500],
        "data": payload,
        "workspace_id": ws_id,
    }

    try:
        inserted = _supabase.table("prospect_engagement_events").insert(row).execute()
        event_id = (inserted.data or [{}])[0].get("id")
    except Exception as e:
        print(f"[prospect-engagement] insert failed: {e}")
        raise HTTPException(500, "insert failed")

    # Notify on the first page_open of a fresh session.
    if event in NOTIFIABLE_EVENTS:
        try:
            cnt = (_supabase.table("prospect_engagement_events")
                   .select("id", count="exact")
                   .eq("session_id", session_id)
                   .eq("event", "page_open")
                   .execute())
            if (cnt.count or 0) == 1:
                _send_open_notification(
                    slug, visit_number, visitor_id,
                    payload.get("referrer"), payload.get("user_agent"),
                )
        except Exception as e:
            print(f"[prospect-engagement] notify probe failed: {e}")

    # Mirror to activity_log if the event is high-signal.
    try:
        if event in ("page_open", "cta_click", "session_end"):
            desc_map = {
                "page_open": f"{slug} opened the brief (visit #{visit_number})",
                "cta_click": f"{slug} clicked CTA: {payload.get('cta', 'unknown')}",
                "session_end": (
                    f"{slug} left after {payload.get('total_active_seconds', 0)}s, "
                    f"scrolled {payload.get('max_scroll_pct', 0)}%"
                ),
            }
            _supabase.table("activity_log").insert({
                "actor": "engagement",
                "action": event,
                "target_type": "prospect",
                "target_id": None,
                "description": desc_map[event],
                "workspace_id": ws_id,
            }).execute()
    except Exception as e:
        # activity_log shape may vary across environments; never let this break the ingest.
        print(f"[prospect-engagement] activity_log mirror skipped: {e}")

    return JSONResponse({"ok": True, "id": event_id})


# ════════════════════════════════════════════════════════════
# READ ENDPOINTS  (JWT-gated)
# ════════════════════════════════════════════════════════════

@router.get("/_prospects")
async def list_prospects(request: Request):
    """All briefs in the workspace, with a few summary counts each."""
    if _db is None:
        raise HTTPException(500, "module not initialized")
    briefs = _db("prospect_briefs").select("*").order("created_at", desc=True).execute().data or []
    out = []
    for b in briefs:
        slug = b["slug"]
        try:
            sessions_q = (_supabase.table("prospect_engagement_events")
                          .select("session_id", count="exact")
                          .eq("prospect_id", slug)
                          .eq("event", "page_open")
                          .execute())
            session_count = sessions_q.count or 0
            last_q = (_supabase.table("prospect_engagement_events")
                      .select("created_at")
                      .eq("prospect_id", slug)
                      .order("created_at", desc=True)
                      .limit(1).execute())
            last_seen = (last_q.data or [{}])[0].get("created_at")
        except Exception:
            session_count = 0
            last_seen = None
        out.append({
            **b,
            "session_count": session_count,
            "last_seen": last_seen,
        })
    return {"prospects": out}


@router.post("/_prospects")
async def create_prospect(payload: ProspectBriefIn, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    slug = payload.slug.strip().lower()
    if not _is_valid_slug(slug):
        raise HTTPException(400, "invalid slug (use lowercase, digits, hyphens)")
    row = {
        "slug": slug,
        "display_name": payload.display_name or slug,
        "notify_email": payload.notify_email,
    }
    try:
        r = _db("prospect_briefs").insert(row).execute()
    except Exception as e:
        raise HTTPException(400, f"insert failed: {e}")
    return (r.data or [{}])[0]


@router.patch("/_prospects/{slug}")
async def update_prospect(slug: str, payload: ProspectBriefUpdate, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(400, "no fields to update")
    r = _db("prospect_briefs").update(data).eq("slug", slug).execute()
    return (r.data or [{}])[0]


@router.delete("/_prospects/{slug}")
async def delete_prospect(slug: str, request: Request):
    if _db is None:
        raise HTTPException(500, "module not initialized")
    _db("prospect_briefs").delete().eq("slug", slug).execute()
    return {"ok": True}


@router.get("/{prospect_id}")
async def get_engagement(prospect_id: str, request: Request, limit: int = 300):
    """Roll-up summary plus recent event timeline for one prospect."""
    if _db is None:
        raise HTTPException(500, "module not initialized")
    slug = prospect_id.strip().lower()

    # Pull all events for the prospect (within workspace) in one shot, then roll up in Python.
    # At this scale (single prospect, hundreds-to-low-thousands of events) it's fine and
    # avoids needing a half-dozen JSONB aggregation queries against PostgREST.
    rows = (_db("prospect_engagement_events")
            .select("*")
            .eq("prospect_id", slug)
            .order("created_at", desc=True)
            .limit(2000)
            .execute()).data or []

    visitors = set()
    sessions = set()
    sections_viewed = set()
    cta_counts = {}
    max_visit = 0
    max_scroll = 0
    per_session_active = {}
    first_seen = None
    last_seen = None

    for ev in rows:
        visitors.add(ev.get("visitor_id"))
        sessions.add(ev.get("session_id"))
        v = ev.get("visit_number") or 0
        if v > max_visit:
            max_visit = v

        created = ev.get("created_at")
        if created:
            if last_seen is None or created > last_seen:
                last_seen = created
            if first_seen is None or created < first_seen:
                first_seen = created

        data = ev.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}

        try:
            ms = int(data.get("max_scroll_pct") or 0)
            if ms > max_scroll:
                max_scroll = ms
        except (TypeError, ValueError):
            pass

        evt = ev.get("event")
        if evt == "section_view":
            sec = data.get("section")
            if sec:
                sections_viewed.add(sec)
        elif evt == "cta_click":
            cta = data.get("cta") or "unknown"
            cta_counts[cta] = cta_counts.get(cta, 0) + 1
        elif evt in ("heartbeat", "session_end", "visibility_hidden"):
            try:
                ac = int(data.get("active_seconds") or 0)
                sid = ev.get("session_id")
                if sid and ac > per_session_active.get(sid, 0):
                    per_session_active[sid] = ac
            except (TypeError, ValueError):
                pass

    sessions_detail = [
        {"session_id": sid, "active_seconds": secs}
        for sid, secs in sorted(per_session_active.items(), key=lambda kv: -kv[1])
    ]
    total_active = sum(per_session_active.values())

    # Reshape events for the timeline view (most recent first; cap at `limit`).
    timeline = []
    for ev in rows[:limit]:
        data = ev.get("data") or {}
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:
                data = {}
        timeline.append({
            "id": ev.get("id"),
            "event": ev.get("event"),
            "visitor_id": ev.get("visitor_id"),
            "session_id": ev.get("session_id"),
            "visit_number": ev.get("visit_number"),
            "created_at": ev.get("created_at"),
            "data": data,
        })

    return {
        "summary": {
            "unique_visitors": len(visitors),
            "sessions": len(sessions),
            "max_visit": max_visit,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "total_active_seconds": total_active,
            "max_scroll_pct": max_scroll,
            "sections_viewed": sorted(sections_viewed),
            "cta_clicks": [{"cta": k, "n": v} for k, v in sorted(cta_counts.items(), key=lambda kv: -kv[1])],
            "sessions_detail": sessions_detail,
        },
        "events": timeline,
    }
