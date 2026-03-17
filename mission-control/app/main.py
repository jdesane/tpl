from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from supabase import create_client
import os
import json
import hmac
import hashlib
import urllib.request
from datetime import datetime

app = FastAPI(title="TPL Mission Control")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tplcollective.ai", "https://www.tplcollective.ai", "http://localhost", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SETTINGS_PATH = "/data/settings.json"

# ── SUPABASE CLIENT ──

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zyonidiybzrgklrmalbt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── SETTINGS HELPERS ──

def load_settings() -> dict:
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_settings(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── EMAIL HELPER ──

def send_email(smtp_config: dict, to_email: str, subject: str, html_body: str) -> tuple[bool, str]:
    """Send email via Resend API. smtp_config.pass is the Resend API key."""
    try:
        api_key = smtp_config.get("pass", "")
        if not api_key:
            return False, "Resend API key not configured"

        payload = json.dumps({
            "from": "TPL Mission Control <notifications@tplcollective.ai>",
            "to": [to_email],
            "subject": subject,
            "html": html_body
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return True, ""

    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return False, f"Resend API error {e.code}: {body}"
    except Exception as e:
        return False, str(e)


def build_lead_email(lead_data: dict) -> str:
    """Build HTML email for new lead notification."""
    name = lead_data.get("name", "Unknown")
    email = lead_data.get("email", "")
    phone = lead_data.get("phone", "")
    brokerage = lead_data.get("brokerage", "")
    deals = lead_data.get("deals_per_year", "")
    price = lead_data.get("avg_price", "")
    source = brokerage if brokerage else "tplcollective.ai"
    timestamp = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")

    phone_row = f"<tr><td style='padding:8px 0;color:#888;font-size:13px;'>Phone</td><td style='padding:8px 0;color:#e8e8f0;font-size:13px;'>{phone}</td></tr>" if phone else ""
    deals_row = f"<tr><td style='padding:8px 0;color:#888;font-size:13px;'>Production</td><td style='padding:8px 0;color:#e8e8f0;font-size:13px;'>{deals} deals · {price}</td></tr>" if deals else ""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:'DM Sans',Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:32px 16px;">

    <!-- Header -->
    <div style="margin-bottom:28px;">
      <div style="font-size:22px;font-weight:700;color:#e8e8f0;letter-spacing:2px;margin-bottom:4px;">TPL<span style="color:#6c63ff;">.</span></div>
      <div style="font-size:11px;color:#666;letter-spacing:3px;text-transform:uppercase;">Mission Control · New Lead Alert</div>
    </div>

    <!-- Card -->
    <div style="background:#12121a;border:1px solid #2a2a3d;border-radius:12px;overflow:hidden;">
      <div style="background:#6c63ff;padding:4px 0;"></div>
      <div style="padding:28px;">
        <div style="font-size:11px;color:#6c63ff;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">New Lead Captured</div>
        <div style="font-size:24px;font-weight:700;color:#e8e8f0;margin-bottom:4px;">{name}</div>
        <div style="font-size:13px;color:#888;margin-bottom:24px;">{timestamp}</div>

        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px 0;color:#888;font-size:13px;width:120px;">Email</td><td style="padding:8px 0;"><a href="mailto:{email}" style="color:#6c63ff;font-size:13px;text-decoration:none;">{email}</a></td></tr>
          {phone_row}
          <tr><td style="padding:8px 0;color:#888;font-size:13px;">Brokerage</td><td style="padding:8px 0;color:#e8e8f0;font-size:13px;">{brokerage or '—'}</td></tr>
          {deals_row}
          <tr><td style="padding:8px 0;color:#888;font-size:13px;">Source</td><td style="padding:8px 0;color:#f0c040;font-size:13px;">{source}</td></tr>
        </table>

        <div style="margin-top:24px;padding-top:20px;border-top:1px solid #2a2a3d;">
          <a href="https://mission.tplcollective.ai" style="display:inline-block;background:#6c63ff;color:#fff;text-decoration:none;padding:10px 22px;border-radius:8px;font-size:13px;font-weight:600;">View in Mission Control →</a>
        </div>
      </div>
    </div>

    <div style="margin-top:20px;font-size:11px;color:#444;text-align:center;">TPL Collective · mission.tplcollective.ai</div>
  </div>
</body>
</html>
"""


def maybe_notify_new_lead(lead_data: dict):
    """Fire email notification if configured and enabled."""
    try:
        settings = load_settings()
        notif = settings.get("notifications", {})

        if not notif.get("newLead", False):
            return

        to_email = notif.get("email", "")
        if not to_email:
            return

        # Source filter
        sources = notif.get("sources", ["all"])
        if "all" not in sources:
            lead_source = lead_data.get("brokerage", "")
            if lead_source not in sources:
                return

        smtp = settings.get("smtp", {})
        subject = f"New Lead: {lead_data.get('name', 'Unknown')} — TPL Mission Control"
        html = build_lead_email(lead_data)
        success, error = send_email(smtp, to_email, subject, html)

        if success:
            supabase.table("activity_log").insert({
                "type": "smtp",
                "message": f"Email notification sent to {to_email} for lead: {lead_data.get('name')}",
                "meta": {}
            }).execute()
        else:
            supabase.table("activity_log").insert({
                "type": "error",
                "message": f"Email notification failed: {error}",
                "meta": {}
            }).execute()
    except Exception as e:
        pass  # Never let notification failure break lead capture


# ── MODELS ──

class LeadIn(BaseModel):
    name: str
    email: str
    phone: Optional[str] = ""
    brokerage: Optional[str] = ""
    deals_per_year: Optional[str] = ""
    avg_price: Optional[str] = ""
    source: Optional[str] = "Web"


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class NotifSettings(BaseModel):
    newLead: bool = False
    digest: bool = False
    statusChange: bool = False
    email: str = ""
    sources: list = ["all"]


class SmtpConfig(BaseModel):
    host: str = ""
    port: str = "465"
    from_addr: str = ""
    user: str = ""
    password: str = ""


class TestNotifRequest(BaseModel):
    email: str
    smtp: Optional[dict] = {}


# ── ROUTES ──

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/api/leads")
async def create_lead(lead: LeadIn):
    result = supabase.table("leads").insert({
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone or "",
        "brokerage": lead.brokerage or "",
        "deals_per_year": lead.deals_per_year or "",
        "avg_price": lead.avg_price or "",
        "source": lead.source or "Web",
        "status": "new"
    }).execute()

    lead_data = result.data[0]
    lead_id = lead_data["id"]

    supabase.table("activity_log").insert({
        "type": "lead",
        "message": f"New lead: {lead.name} from {lead.brokerage or 'tplcollective.ai'}",
        "meta": {"lead_id": lead_id}
    }).execute()

    # Fire notification (non-blocking, never fails the request)
    maybe_notify_new_lead(lead.dict())

    return {"success": True, "id": lead_id, "message": "Lead captured"}


@app.get("/api/leads")
def get_leads(status: Optional[str] = None):
    query = supabase.table("leads").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    result = query.execute()
    return result.data


@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: int):
    result = supabase.table("leads").select("*").eq("id", lead_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    return result.data[0]


@app.put("/api/leads/{lead_id}")
async def put_lead(lead_id: int, request: Request):
    data = await request.json()
    data["updated_at"] = datetime.utcnow().isoformat()

    # Track stage changes
    old_lead = supabase.table("leads").select("stage, lead_score").eq("id", lead_id).execute()
    old_stage = old_lead.data[0].get("stage") if old_lead.data else None

    supabase.table("leads").update(data).eq("id", lead_id).execute()

    # Log activity for stage change
    new_stage = data.get("stage")
    if new_stage and old_stage and new_stage != old_stage:
        supabase.table("lead_activity").insert({
            "lead_id": lead_id,
            "activity_type": "stage_change",
            "description": f"Stage changed: {old_stage} → {new_stage}",
            "metadata": {"from": old_stage, "to": new_stage}
        }).execute()
        supabase.table("activity_log").insert({
            "type": "lead",
            "message": f"Lead stage changed to {new_stage}: {data.get('name', 'Lead #'+str(lead_id))}",
            "meta": {"lead_id": lead_id}
        }).execute()

    return {"success": True}


@app.patch("/api/leads/{lead_id}")
def update_lead(lead_id: int, update: LeadUpdate):
    existing = supabase.table("leads").select("id").eq("id", lead_id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Lead not found")

    updates = {"updated_at": datetime.utcnow().isoformat()}
    if update.status:
        updates["status"] = update.status
    if update.notes is not None:
        updates["notes"] = update.notes

    supabase.table("leads").update(updates).eq("id", lead_id).execute()
    return {"success": True}


@app.delete("/api/leads/{lead_id}")
def delete_lead(lead_id: int):
    supabase.table("leads").delete().eq("id", lead_id).execute()
    return {"success": True}


@app.get("/api/stats")
def get_stats():
    leads = supabase.table("leads").select("status, created_at").execute().data

    total = len(leads)
    counts = {}
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_count = 0

    for lead in leads:
        s = lead["status"]
        counts[s] = counts.get(s, 0) + 1
        if lead["created_at"] and lead["created_at"][:10] == today_str:
            today_count += 1

    return {
        "total": total,
        "new": counts.get("new", 0),
        "researched": counts.get("researched", 0),
        "outreach": counts.get("outreach", 0),
        "meeting": counts.get("meeting", 0),
        "talking": counts.get("talking", 0),
        "joined": counts.get("joined", 0),
        "lost": counts.get("lost", 0),
        "today": today_count
    }


@app.get("/api/activity")
def get_activity(limit: int = 40):
    result = supabase.table("activity_log").select("*").order("created_at", desc=True).limit(limit).execute()
    return result.data


# ── DASHBOARD ENDPOINTS ──

def _map_status(s):
    """Map lead statuses to canonical stage names."""
    mapping = {"meeting": "discovery_call", "researched": "contacted", "outreach": "contacted", "talking": "considering", "joined": "signed"}
    return mapping.get(s, s)


@app.get("/api/dashboard/overview")
def dashboard_overview():
    leads = supabase.table("leads").select("status, created_at, lead_score").execute().data
    agents = supabase.table("agents").select("id, status, created_at").execute().data
    tasks = supabase.table("tasks").select("id, status, due_date").execute().data
    drip = supabase.table("drip_queue").select("id", count="exact").eq("status", "pending").execute()

    total_leads = len(leads)
    total_agents = len(agents)
    active_agents = len([a for a in agents if a.get("status") == "active"])

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    tasks_today = sum(1 for t in tasks if t.get("due_date") and t["due_date"][:10] == today_str and t.get("status") != "done")

    # Week calculation
    from datetime import timedelta
    week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
    new_this_week = sum(1 for l in leads if l.get("created_at", "") > week_ago)

    # Month calculation for agents
    month_ago = (datetime.utcnow() - timedelta(days=30)).isoformat()
    new_agents_month = sum(1 for a in agents if a.get("created_at", "") > month_ago)

    signed = sum(1 for l in leads if l.get("status") in ("joined", "signed"))
    retention = round((active_agents / total_agents * 100) if total_agents > 0 else 100)
    conversion = round((signed / total_leads * 100) if total_leads > 0 else 0)

    return {
        "agents": {"total": total_agents, "active": active_agents, "new_this_month": new_agents_month, "retention_rate": retention},
        "leads": {"total": total_leads, "new_this_week": new_this_week, "conversion_rate": conversion},
        "tasks_today": tasks_today,
        "drip": {"pending": drip.count or 0}
    }


@app.get("/api/dashboard/funnel")
def dashboard_funnel():
    leads = supabase.table("leads").select("status").execute().data
    stages = ["new", "contacted", "discovery_call", "presentation", "considering", "signed", "onboarding"]
    counts = {s: 0 for s in stages}
    for lead in leads:
        s = _map_status(lead.get("status", "new"))
        if s in counts:
            counts[s] += 1
    return counts


@app.get("/api/dashboard/pipeline-health")
def dashboard_pipeline_health():
    leads = supabase.table("leads").select("status, updated_at, created_at, lead_score").execute().data
    total = len(leads)
    if total == 0:
        return {"score": 100, "status": "Healthy", "stale_leads": 0, "avg_lead_score": 0}

    stale = 0
    scores = []
    for lead in leads:
        if lead.get("lead_score"):
            scores.append(float(lead["lead_score"]))
        if _map_status(lead["status"]) in ("new", "contacted", "discovery_call", "presentation", "considering"):
            updated = lead.get("updated_at") or lead.get("created_at") or ""
            if updated:
                try:
                    last = datetime.fromisoformat(updated.replace("Z", "+00:00").replace("+00:00", ""))
                    days = (datetime.utcnow() - last).days
                    if days > 14:
                        stale += 1
                except Exception:
                    pass

    active_pipeline = sum(1 for l in leads if _map_status(l["status"]) not in ("signed", "lost"))
    stale_pct = (stale / active_pipeline * 100) if active_pipeline > 0 else 0
    score = max(0, min(100, round(100 - stale_pct * 2)))
    status = "Healthy" if score >= 70 else "Needs Attention" if score >= 40 else "Critical"
    avg_score = round(sum(scores) / len(scores)) if scores else 0

    return {"score": score, "status": status, "stale_leads": stale, "avg_lead_score": avg_score}


# ── LEADS EXTENDED ──

@app.get("/api/leads/hot")
def get_hot_leads(limit: int = 5):
    result = supabase.table("leads").select("*").not_.is_("lead_score", "null").order("lead_score", desc=True).limit(limit).execute()
    return result.data


# ── LEAD NOTES & ACTIVITY ──

@app.get("/api/leads/{lead_id}/notes")
def get_lead_notes(lead_id: int):
    result = supabase.table("lead_notes").select("*").eq("lead_id", lead_id).order("created_at", desc=True).execute()
    return result.data


@app.post("/api/leads/{lead_id}/notes")
async def add_lead_note(lead_id: int, request: Request):
    data = await request.json()
    result = supabase.table("lead_notes").insert({
        "lead_id": lead_id,
        "author": data.get("author", "Joe"),
        "content": data.get("content", "")
    }).execute()
    # Also log as activity
    supabase.table("lead_activity").insert({
        "lead_id": lead_id,
        "activity_type": "note",
        "description": f"Note added: {data.get('content', '')[:100]}"
    }).execute()
    return {"success": True, "data": result.data[0] if result.data else None}


@app.get("/api/leads/{lead_id}/activity")
def get_lead_activity(lead_id: int):
    result = supabase.table("lead_activity").select("*").eq("lead_id", lead_id).order("created_at", desc=True).limit(50).execute()
    return result.data


# ── TASKS ──

@app.get("/api/tasks/today")
def get_tasks_today():
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    result = supabase.table("tasks").select("*").eq("due_date", today_str).neq("status", "done").order("created_at", desc=False).execute()
    return result.data


@app.get("/api/tasks")
def get_tasks(status: Optional[str] = None, assigned_to: Optional[str] = None):
    query = supabase.table("tasks").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    if assigned_to:
        query = query.eq("assigned_to", assigned_to)
    return query.execute().data


@app.post("/api/tasks")
async def create_task(request: Request):
    data = await request.json()
    result = supabase.table("tasks").insert(data).execute()
    return {"success": True, "data": result.data[0] if result.data else None}


@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: int, request: Request):
    data = await request.json()
    data["updated_at"] = datetime.utcnow().isoformat()
    supabase.table("tasks").update(data).eq("id", task_id).execute()
    return {"success": True}


@app.put("/api/tasks/{task_id}")
async def put_task(task_id: int, request: Request):
    data = await request.json()
    data["updated_at"] = datetime.utcnow().isoformat()
    supabase.table("tasks").update(data).eq("id", task_id).execute()
    return {"success": True}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    supabase.table("tasks").delete().eq("id", task_id).execute()
    return {"success": True}


# ── AGENTS ──

@app.get("/api/agents")
def get_agents():
    result = supabase.table("agents").select("*").order("created_at", desc=True).execute()
    return result.data


@app.get("/api/agents/stats")
def get_agents_stats():
    agents = supabase.table("agents").select("*").execute().data
    total = len(agents)
    active = sum(1 for a in agents if a.get("status") == "active")
    retention = round((active / total * 100) if total > 0 else 100)
    engagements = [a.get("engagement_score", 0) or 0 for a in agents if a.get("engagement_score")]
    avg_engagement = round(sum(engagements) / len(engagements)) if engagements else 0
    return {"total": total, "active": active, "retention_rate": retention, "avg_engagement": avg_engagement}


@app.post("/api/agents")
async def create_agent(request: Request):
    data = await request.json()
    result = supabase.table("agents").insert(data).execute()
    if result.data:
        supabase.table("activity_log").insert({
            "type": "agent",
            "message": f"New agent added: {data.get('name', 'Unknown')}",
            "meta": {"agent_id": result.data[0]["id"]}
        }).execute()
    return {"success": True, "data": result.data[0] if result.data else None}


@app.patch("/api/agents/{agent_id}")
async def update_agent(agent_id: int, request: Request):
    data = await request.json()
    data["updated_at"] = datetime.utcnow().isoformat()
    supabase.table("agents").update(data).eq("id", agent_id).execute()
    return {"success": True}


# ── CONTENT POSTS ──

@app.get("/api/content")
def get_content():
    result = supabase.table("content_posts").select("*").order("created_at", desc=True).execute()
    return result.data


@app.post("/api/content")
async def create_content(request: Request):
    data = await request.json()
    result = supabase.table("content_posts").insert(data).execute()
    return {"success": True, "data": result.data[0] if result.data else None}


@app.patch("/api/content/{post_id}")
async def update_content(post_id: int, request: Request):
    data = await request.json()
    supabase.table("content_posts").update(data).eq("id", post_id).execute()
    return {"success": True}


@app.delete("/api/content/{post_id}")
def delete_content(post_id: int):
    supabase.table("content_posts").delete().eq("id", post_id).execute()
    return {"success": True}


# ── GOALS ──

@app.get("/api/goals/current")
def get_current_goals():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    goals = supabase.table("goals").select("*").lte("start_date", today).gte("end_date", today).execute().data
    if not goals:
        # Fallback: get latest goals regardless of date
        goals = supabase.table("goals").select("*").order("created_at", desc=True).limit(4).execute().data

    # Compute actuals from live data
    from datetime import timedelta
    month_start = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")

    leads = supabase.table("leads").select("id, created_at").gte("created_at", month_start).execute().data
    agents_new = supabase.table("agents").select("id, created_at").gte("created_at", month_start).execute().data
    calls = supabase.table("leads").select("id").eq("stage", "discovery_call").gte("created_at", month_start).execute().data
    try:
        rs_entries = supabase.table("revshare_entries").select("amount").gte("created_at", month_start).execute().data
        rs_total = sum(float(e.get("amount", 0)) for e in rs_entries)
    except Exception:
        rs_total = 0

    actuals = {
        "agents": len(agents_new),
        "calls": len(calls),
        "leads": len(leads),
        "revshare": round(rs_total)
    }

    result = {}
    for g in goals:
        metric = g["metric"]
        result[metric] = {
            "target": g["target"],
            "actual": actuals.get(metric, g.get("actual", 0)),
            "period": g.get("period", "monthly")
        }

    return result


@app.post("/api/goals")
async def set_goal(request: Request):
    data = await request.json()
    metric = data.get("metric")
    target = data.get("target", 0)
    if not metric:
        raise HTTPException(status_code=400, detail="metric required")

    today = datetime.utcnow().strftime("%Y-%m-%d")
    existing = supabase.table("goals").select("id").eq("metric", metric).lte("start_date", today).gte("end_date", today).execute()

    if existing.data:
        supabase.table("goals").update({"target": target, "updated_at": datetime.utcnow().isoformat()}).eq("id", existing.data[0]["id"]).execute()
    else:
        month_start = datetime.utcnow().replace(day=1).strftime("%Y-%m-%d")
        from calendar import monthrange
        _, last_day = monthrange(datetime.utcnow().year, datetime.utcnow().month)
        month_end = datetime.utcnow().replace(day=last_day).strftime("%Y-%m-%d")
        supabase.table("goals").insert({
            "metric": metric,
            "target": target,
            "period": "monthly",
            "start_date": month_start,
            "end_date": month_end
        }).execute()

    return {"success": True}


# ── RECRUITING LINKS ──

@app.get("/api/recruiting-links")
def get_recruiting_links(target_brokerage: Optional[str] = None):
    query = supabase.table("recruiting_links").select("*").order("target_brokerage", desc=False)
    if target_brokerage:
        query = query.eq("target_brokerage", target_brokerage)
    result = query.execute()
    return result.data


# ── EMAIL STATS ──

@app.get("/api/emails/stats")
def get_email_stats():
    sent = supabase.table("emails_sent").select("id, created_at", count="exact").execute()
    pending = supabase.table("drip_queue").select("id", count="exact").eq("status", "pending").execute()
    failed = supabase.table("drip_queue").select("id", count="exact").eq("status", "failed").execute()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    sent_today = sum(1 for e in (sent.data or []) if e.get("created_at", "")[:10] == today_str)
    return {"drip_sent": sent.count or 0, "drip_pending": pending.count or 0, "sent_today": sent_today, "drip_failed": failed.count or 0}


# ── EMAIL FUNNELS ──

@app.get("/api/funnels")
def get_funnels():
    funnels = supabase.table("email_funnels").select("*").order("created_at").execute().data
    for f in funnels:
        steps = supabase.table("email_funnel_steps").select("*").eq("funnel_id", f["id"]).order("step_order").execute().data
        enrolled = supabase.table("email_funnel_enrollments").select("id", count="exact").eq("funnel_id", f["id"]).eq("status", "active").execute()
        f["steps"] = steps
        f["enrolled_count"] = enrolled.count or 0
    return funnels


@app.get("/api/funnels/{funnel_id}")
def get_funnel(funnel_id: int):
    funnel = supabase.table("email_funnels").select("*").eq("id", funnel_id).execute()
    if not funnel.data:
        raise HTTPException(status_code=404, detail="Funnel not found")
    f = funnel.data[0]
    f["steps"] = supabase.table("email_funnel_steps").select("*").eq("funnel_id", funnel_id).order("step_order").execute().data
    f["enrollments"] = supabase.table("email_funnel_enrollments").select("*, leads(name, email)").eq("funnel_id", funnel_id).execute().data
    return f


@app.post("/api/funnels")
async def create_funnel(request: Request):
    data = await request.json()
    result = supabase.table("email_funnels").insert({
        "name": data["name"],
        "trigger_stage": data["trigger_stage"],
        "description": data.get("description", "")
    }).execute()
    return {"success": True, "data": result.data[0] if result.data else None}


@app.put("/api/funnels/{funnel_id}")
async def update_funnel(funnel_id: int, request: Request):
    data = await request.json()
    data["updated_at"] = datetime.utcnow().isoformat()
    supabase.table("email_funnels").update(data).eq("id", funnel_id).execute()
    return {"success": True}


@app.post("/api/funnels/{funnel_id}/steps")
async def add_funnel_step(funnel_id: int, request: Request):
    data = await request.json()
    data["funnel_id"] = funnel_id
    result = supabase.table("email_funnel_steps").insert(data).execute()
    return {"success": True, "data": result.data[0] if result.data else None}


@app.put("/api/funnels/{funnel_id}/steps/{step_id}")
async def update_funnel_step(funnel_id: int, step_id: int, request: Request):
    data = await request.json()
    supabase.table("email_funnel_steps").update(data).eq("id", step_id).execute()
    return {"success": True}


@app.delete("/api/funnels/{funnel_id}/steps/{step_id}")
def delete_funnel_step(funnel_id: int, step_id: int):
    supabase.table("email_funnel_steps").delete().eq("id", step_id).execute()
    return {"success": True}


# ── AI CONTENT GENERATION ──

@app.post("/api/ai/generate-content")
async def ai_generate_content(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    content_type = data.get("type", "social")  # social, email, dm

    if content_type == "email":
        result = f"Subject: {prompt}\n\nHey [Name],\n\n{prompt}\n\nThe math speaks for itself — LPT Realty agents keep $17,883 more per year vs. traditional brokerages. That's not marketing — that's what happens when you remove franchise fees, slash the cap to $5K, and eliminate desk fees.\n\nWould you be open to a 15-minute call this week? No pitch — just numbers.\n\nBest,\nJoe DeSane\nTPL Collective"
    else:
        result = f"{prompt}\n\nAt LPT Realty, agents keep 100% of their commission with a $5,000 annual cap. No franchise fees. No desk fees. $11K+ in tools included.\n\nThe math matters. Run yours: tplcollective.ai/commission-calculator\n\n#RealEstate #LPTRealty #TPLCollective #AgentLife #KeepMoreEarnMore"

    return {"success": True, "generated": result, "type": content_type}


# ── REFERRALS ──

@app.get("/api/referrals")
def get_referrals():
    result = supabase.table("referrals").select("*").order("created_at", desc=True).execute()
    return result.data


@app.post("/api/referrals")
async def create_referral(request: Request):
    data = await request.json()
    result = supabase.table("referrals").insert(data).execute()
    return {"success": True, "data": result.data[0] if result.data else None}


# ── AI ACTIONS ──

@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: int):
    result = supabase.table("agents").select("*").eq("id", agent_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Agent not found")
    return result.data[0]


@app.get("/api/agents/{agent_id}/onboarding")
def get_agent_onboarding(agent_id: int):
    result = supabase.table("onboarding_steps").select("*").eq("agent_id", agent_id).order("step_order").execute()
    return result.data


@app.put("/api/agents/{agent_id}/onboarding/{step_id}")
async def update_onboarding_step(agent_id: int, step_id: int, request: Request):
    data = await request.json()
    updates = {}
    if "completed" in data:
        updates["completed"] = data["completed"]
        if data["completed"]:
            updates["completed_at"] = datetime.utcnow().isoformat()
    supabase.table("onboarding_steps").update(updates).eq("id", step_id).execute()
    return {"success": True}


@app.get("/api/content/{post_id}")
def get_content_post(post_id: int):
    result = supabase.table("content_posts").select("*").eq("id", post_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Post not found")
    return result.data[0]


@app.put("/api/content/{post_id}")
async def put_content(post_id: int, request: Request):
    data = await request.json()
    supabase.table("content_posts").update(data).eq("id", post_id).execute()
    return {"success": True}


@app.post("/api/ai/draft-dm")
async def ai_draft_dm(request: Request):
    data = await request.json()
    lead_id = data.get("lead_id")
    if lead_id:
        lead = supabase.table("leads").select("name, brokerage, current_brokerage").eq("id", lead_id).execute()
        if lead.data:
            l = lead.data[0]
            name = l.get("name", "there")
            brokerage = l.get("current_brokerage") or l.get("brokerage") or "your current brokerage"
            return {"success": True, "draft": f"Hey {name}, I noticed you're at {brokerage}. I help agents keep more of what they earn — LPT Realty's model saves the average agent $17,883/year vs traditional brokerages. Would you be open to a quick 15-min call to see if it's a fit?"}
    name = data.get("name", "there")
    brokerage = data.get("brokerage", "your current brokerage")
    return {"success": True, "draft": f"Hey {name}, I noticed you're at {brokerage}. I help agents keep more of what they earn — LPT Realty's model saves the average agent $17,883/year vs traditional brokerages. Would you be open to a quick 15-min call to see if it's a fit?"}


@app.post("/api/ai/who-to-call")
async def ai_who_to_call():
    leads = supabase.table("leads").select("id, name, brokerage, current_brokerage, lead_score, lead_temperature, status, updated_at").order("lead_score", desc=True).limit(10).execute().data
    call_list = []
    for l in leads:
        if l.get("status") in ("joined", "lost"):
            continue
        reasons = []
        if (l.get("lead_score") or 0) >= 70:
            reasons.append("High lead score")
        if l.get("lead_temperature") == "hot":
            reasons.append("Hot temperature")
        if l.get("status") == "new":
            reasons.append("New lead, needs first contact")
        if not reasons:
            reasons.append("In active pipeline")
        call_list.append({
            "id": l["id"],
            "name": l["name"],
            "brokerage": l.get("current_brokerage") or l.get("brokerage") or "Unknown",
            "score": l.get("lead_score") or 0,
            "reasons": reasons,
            "suggested_action": "Schedule discovery call" if l.get("status") == "new" else "Follow up"
        })
    return {"call_list": call_list[:5]}


@app.post("/api/ai/weekly-plan")
async def ai_weekly_plan():
    leads = supabase.table("leads").select("status").execute().data
    new_count = sum(1 for l in leads if l.get("status") == "new")
    active = sum(1 for l in leads if l.get("status") not in ("joined", "lost", "new"))
    return {
        "priorities": [
            f"Contact {new_count} new leads" if new_count > 0 else "No new leads to contact",
            f"Follow up with {active} active pipeline leads" if active > 0 else "Pipeline is empty — focus on lead gen",
            "Post 3 social media pieces (use Content Hub)"
        ],
        "daily_actions": {
            "Monday": ["Review new leads", "Send outreach DMs"],
            "Tuesday": ["Follow up on discovery calls", "Score leads"],
            "Wednesday": ["Content creation day", "Post to social"],
            "Thursday": ["Pipeline review", "Drip check"],
            "Friday": ["Close open loops", "Plan next week"]
        }
    }


@app.post("/api/ai/score-leads")
async def ai_score_leads():
    leads = supabase.table("leads").select("id, name, stage, status, brokerage, current_brokerage, deals_per_year, created_at, updated_at").execute().data
    updated = 0
    for lead in leads:
        score = 10  # base
        if lead.get("deals_per_year"):
            try:
                deals = int(str(lead["deals_per_year"]).replace("+", "").strip())
                score += min(deals * 5, 40)
            except (ValueError, TypeError):
                pass
        if lead.get("current_brokerage") or lead.get("brokerage"):
            score += 15
        stage = lead.get("stage") or lead.get("status") or "new"
        stage_scores = {"new": 0, "contacted": 10, "discovery_call": 25, "meeting": 25, "presentation": 35, "considering": 40, "signed": 50}
        score += stage_scores.get(stage, 0)
        score = min(100, score)
        temp = "hot" if score >= 70 else "warming" if score >= 40 else "cold"
        supabase.table("leads").update({"lead_score": score, "lead_temperature": temp}).eq("id", lead["id"]).execute()
        updated += 1
    return {"success": True, "updated": updated}


@app.post("/api/ai/generate-tasks")
async def ai_generate_tasks():
    leads = supabase.table("leads").select("id, name, stage, status, updated_at").execute().data
    # Filter to active pipeline leads using stage or status
    active_stages = ["new", "contacted", "discovery_call", "presentation", "considering"]
    leads = [l for l in leads if (l.get("stage") or l.get("status") or "new") in active_stages]
    tasks_created = 0
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    for lead in leads[:10]:
        stage = lead.get("stage") or lead.get("status") or "new"
        action = "Follow up" if stage != "new" else "Initial outreach"
        supabase.table("tasks").insert({
            "task_type": "follow_up" if stage != "new" else "send_outreach",
            "title": f"{action}: {lead['name']}",
            "description": f"Auto-generated task for {lead['name']} (stage: {stage})",
            "status": "pending",
            "priority": "normal",
            "due_date": today_str,
            "lead_id": lead["id"],
            "created_by": "ai"
        }).execute()
        tasks_created += 1
    return {"success": True, "tasks_created": tasks_created}


# ── ANALYTICS ──

@app.get("/api/analytics/funnel")
def analytics_funnel():
    leads = supabase.table("leads").select("status").execute().data
    stages = ["new", "contacted", "discovery_call", "presentation", "considering", "signed", "onboarding"]
    counts = {s: 0 for s in stages}
    for lead in leads:
        s = _map_status(lead.get("status", "new"))
        if s in counts:
            counts[s] += 1
    # Build conversions array
    conversions = []
    for i in range(len(stages) - 1):
        from_s, to_s = stages[i], stages[i + 1]
        rate = round((counts[to_s] / counts[from_s] * 100) if counts[from_s] > 0 else 0)
        conversions.append({"from": from_s, "to": to_s, "from_count": counts[from_s], "to_count": counts[to_s], "rate": rate})
    return {"stage_counts": counts, "conversions": conversions}


@app.get("/api/analytics/sources")
def analytics_sources():
    leads = supabase.table("leads").select("source, status").execute().data
    source_data = {}
    for lead in leads:
        s = lead.get("source", "Unknown") or "Unknown"
        if s not in source_data:
            source_data[s] = {"total": 0, "signed": 0}
        source_data[s]["total"] += 1
        if lead.get("status") in ("joined", "signed"):
            source_data[s]["signed"] += 1
    result = []
    for source, data in source_data.items():
        rate = round((data["signed"] / data["total"] * 100) if data["total"] > 0 else 0)
        result.append({"source": source, "total": data["total"], "conversion_rate": rate})
    result.sort(key=lambda x: x["total"], reverse=True)
    return result


@app.get("/api/analytics/time-in-stage")
def analytics_time_in_stage():
    leads = supabase.table("leads").select("status, created_at, updated_at").execute().data
    stages = ["new", "contacted", "discovery_call", "presentation", "considering", "signed", "onboarding"]
    stage_data = {}
    for s in stages:
        matching = [l for l in leads if _map_status(l.get("status", "new")) == s]
        if matching:
            days_list = []
            for l in matching:
                created = l.get("created_at", "")
                updated = l.get("updated_at", created)
                try:
                    c = datetime.fromisoformat(created.replace("Z", "+00:00").replace("+00:00", ""))
                    u = datetime.fromisoformat((updated or created).replace("Z", "+00:00").replace("+00:00", ""))
                    days_list.append(max(0, (u - c).days))
                except Exception:
                    pass
            avg = round(sum(days_list) / len(days_list), 1) if days_list else 0
            stage_data[s] = {"avg_days": avg, "count": len(matching)}
        else:
            stage_data[s] = {"avg_days": 0, "count": 0}
    return {"stages": stage_data}


@app.get("/api/analytics/funnel-roi")
def analytics_funnel_roi():
    leads = supabase.table("leads").select("status, source").execute().data
    source_data = {}
    for lead in leads:
        s = lead.get("source", "Unknown") or "Unknown"
        if s not in source_data:
            source_data[s] = {"leads": 0, "conversions": 0}
        source_data[s]["leads"] += 1
        if lead.get("status") in ("joined", "signed"):
            source_data[s]["conversions"] += 1
    result = []
    for source, data in source_data.items():
        rate = round((data["conversions"] / data["leads"] * 100) if data["leads"] > 0 else 0)
        result.append({"source": source, "leads": data["leads"], "conversions": data["conversions"], "conversion_rate": rate})
    result.sort(key=lambda x: x["leads"], reverse=True)
    return result


# ── REV SHARE ──

@app.get("/api/revshare/summary")
def revshare_summary(year: int = 2026):
    try:
        entries = supabase.table("revshare_entries").select("amount, agent_id").execute().data
    except Exception:
        entries = []
    agents = supabase.table("agents").select("id").execute().data
    ytd = sum(float(e.get("amount", 0)) for e in entries)
    agent_count = len(agents)
    month_now = datetime.utcnow().month or 1
    projected = (ytd / month_now) * 12 if month_now > 0 else 0
    avg = ytd / agent_count if agent_count > 0 else 0
    return {"ytd_total": ytd, "projected_annual": projected, "agent_count": agent_count, "avg_per_agent": avg}


@app.get("/api/revshare")
def get_revshare(year: int = 2026):
    try:
        result = supabase.table("revshare_entries").select("*, agents(name)").order("created_at", desc=True).execute()
        return result.data
    except Exception:
        return []


@app.post("/api/revshare")
async def create_revshare(request: Request):
    data = await request.json()
    try:
        result = supabase.table("revshare_entries").insert(data).execute()
        return {"success": True, "data": result.data[0] if result.data else None}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/revshare/{entry_id}")
def delete_revshare(entry_id: int):
    try:
        supabase.table("revshare_entries").delete().eq("id", entry_id).execute()
    except Exception:
        pass
    return {"success": True}


@app.get("/api/revshare/calculator")
def revshare_calculator(network_size: int = 10):
    # Simplified tier breakdown
    tiers = [
        {"label": "Tier 1 (Direct)", "pct": 0.05, "agents": network_size},
        {"label": "Tier 2", "pct": 0.04, "agents": round(network_size * 2)},
        {"label": "Tier 3", "pct": 0.03, "agents": round(network_size * 3)},
        {"label": "Tier 4", "pct": 0.02, "agents": round(network_size * 3)},
        {"label": "Tier 5", "pct": 0.01, "agents": round(network_size * 2)},
    ]
    avg_company_dollar_per_agent = 3000  # conservative annual estimate
    monthly = 0
    breakdown = []
    for t in tiers:
        annual_per_agent = round(avg_company_dollar_per_agent * t["pct"])
        tier_total = annual_per_agent * t["agents"]
        monthly += tier_total / 12
        breakdown.append({"label": f"{t['label']} ({t['agents']} agents)", "per_agent_annual": annual_per_agent})

    return {
        "estimated_monthly": round(monthly),
        "estimated_annual": round(monthly * 12),
        "tier_breakdown": breakdown,
        "note": "Estimates based on avg $3K company dollar/agent/yr. Actual results vary."
    }


# ── AUTOMATIONS / OPENCLAW ──

@app.get("/api/automations/status")
def automations_status():
    # Check for automation_runs table
    try:
        runs = supabase.table("automation_runs").select("*").order("created_at", desc=True).limit(20).execute().data
    except Exception:
        runs = []
    # Check for automation_workflows table
    try:
        wf_data = supabase.table("automation_workflows").select("*").execute().data
        workflows = wf_data if wf_data else []
    except Exception:
        workflows = [
            {"workflow": "score_leads", "enabled": True, "interval_minutes": 60, "last_run_at": None},
            {"workflow": "generate_tasks", "enabled": True, "interval_minutes": 120, "last_run_at": None},
            {"workflow": "process_drips", "enabled": True, "interval_minutes": 15, "last_run_at": None},
            {"workflow": "flag_stale_leads", "enabled": True, "interval_minutes": 360, "last_run_at": None},
            {"workflow": "check_engagement", "enabled": False, "interval_minutes": 1440, "last_run_at": None},
        ]
    return {"workflows": workflows, "recent_runs": runs}


@app.put("/api/automations/{workflow}/toggle")
async def toggle_automation(workflow: str):
    try:
        existing = supabase.table("automation_workflows").select("enabled").eq("workflow", workflow).execute()
        if existing.data:
            new_val = not existing.data[0]["enabled"]
            supabase.table("automation_workflows").update({"enabled": new_val}).eq("workflow", workflow).execute()
            return {"success": True, "enabled": new_val}
    except Exception:
        pass
    return {"success": True, "enabled": False}


@app.post("/api/automations/{workflow}/run")
async def run_automation(workflow: str):
    try:
        if workflow == "score_leads":
            r = await ai_score_leads()
            return {"success": True, "details": r}
        elif workflow == "generate_tasks":
            r = await ai_generate_tasks()
            return {"success": True, "details": r}
        return {"success": True, "details": "Workflow executed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── NOTIFICATION SETTINGS ──

@app.get("/api/settings/notifications")
def get_notif_settings():
    settings = load_settings()
    return {
        "notifications": settings.get("notifications", {}),
        "smtp": {k: v for k, v in settings.get("smtp", {}).items() if k != "pass"}  # never return password
    }


@app.post("/api/settings/notifications")
def save_notif_settings(data: dict):
    settings = load_settings()
    settings["notifications"] = data.get("notifications", {})
    if "smtp" in data:
        smtp = data["smtp"]
        existing_smtp = settings.get("smtp", {})
        if not smtp.get("pass"):
            smtp["pass"] = existing_smtp.get("pass", "")
        settings["smtp"] = smtp
    save_settings(settings)
    return {"success": True}


@app.post("/api/settings/smtp")
def save_smtp(data: dict):
    settings = load_settings()
    settings["smtp"] = data
    save_settings(settings)
    return {"success": True}


@app.post("/api/notifications/test")
async def test_notification(req: TestNotifRequest):
    settings = load_settings()
    smtp = req.smtp if req.smtp else settings.get("smtp", {})

    if not smtp.get("pass"):
        return {"success": False, "error": "Resend API key not configured. Add it in Settings first."}

    html = build_lead_email({
        "name": "Test Agent",
        "email": "test@tplcollective.ai",
        "phone": "(555) 123-4567",
        "brokerage": "Test Brokerage",
        "deals_per_year": "24",
        "avg_price": "$425K"
    })

    success, error = send_email(smtp, req.email, "✦ TPL Mission Control — Test Notification", html)

    if success:
        supabase.table("activity_log").insert({
            "type": "smtp",
            "message": f"Test notification sent to {req.email}",
            "meta": {}
        }).execute()

    if success:
        return {"success": True}
    return {"success": False, "error": error}


# ── CALENDLY WEBHOOK ──

def verify_calendly_signature(payload: bytes, signature_header: str, signing_key: str) -> bool:
    """Verify Calendly webhook signature. Header format: t=timestamp,v1=signature."""
    if not signing_key or not signature_header:
        return False
    try:
        parts = dict(p.split("=", 1) for p in signature_header.split(","))
        timestamp = parts.get("t", "")
        received_sig = parts.get("v1", "")
        if not timestamp or not received_sig:
            return False
        # Calendly signs: timestamp + "." + payload
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(signing_key.encode(), signed_payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, received_sig)
    except Exception:
        return False


def build_calendly_email(invitee_name: str, invitee_email: str, event_name: str, start_time: str) -> str:
    """Build HTML email for Calendly booking notification."""
    timestamp = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
    try:
        dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        call_time = dt.strftime("%B %d, %Y at %I:%M %p UTC")
    except Exception:
        call_time = start_time

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:'DM Sans',Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:32px 16px;">
    <div style="margin-bottom:28px;">
      <div style="font-size:22px;font-weight:700;color:#e8e8f0;letter-spacing:2px;margin-bottom:4px;">TPL<span style="color:#6c63ff;">.</span></div>
      <div style="font-size:11px;color:#666;letter-spacing:3px;text-transform:uppercase;">Mission Control &middot; Call Booked</div>
    </div>
    <div style="background:#12121a;border:1px solid #2a2a3d;border-radius:12px;overflow:hidden;">
      <div style="background:#34d399;padding:4px 0;"></div>
      <div style="padding:28px;">
        <div style="font-size:11px;color:#34d399;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">Discovery Call Scheduled</div>
        <div style="font-size:24px;font-weight:700;color:#e8e8f0;margin-bottom:4px;">{invitee_name}</div>
        <div style="font-size:13px;color:#888;margin-bottom:24px;">{timestamp}</div>
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px 0;color:#888;font-size:13px;width:120px;">Email</td><td style="padding:8px 0;"><a href="mailto:{invitee_email}" style="color:#6c63ff;font-size:13px;text-decoration:none;">{invitee_email}</a></td></tr>
          <tr><td style="padding:8px 0;color:#888;font-size:13px;">Event</td><td style="padding:8px 0;color:#e8e8f0;font-size:13px;">{event_name}</td></tr>
          <tr><td style="padding:8px 0;color:#888;font-size:13px;">Scheduled</td><td style="padding:8px 0;color:#34d399;font-size:13px;">{call_time}</td></tr>
        </table>
        <div style="margin-top:24px;padding-top:20px;border-top:1px solid #2a2a3d;">
          <a href="https://mission.tplcollective.ai" style="display:inline-block;background:#6c63ff;color:#fff;text-decoration:none;padding:10px 22px;border-radius:8px;font-size:13px;font-weight:600;">View in Mission Control &rarr;</a>
        </div>
      </div>
    </div>
    <div style="margin-top:20px;font-size:11px;color:#444;text-align:center;">TPL Collective &middot; mission.tplcollective.ai</div>
  </div>
</body>
</html>
"""


@app.post("/api/webhooks/calendly")
async def calendly_webhook(request: Request):
    """Handle Calendly webhook events (invitee.created, invitee.canceled)."""
    body = await request.body()

    # Optional signature verification if signing key is configured
    settings = load_settings()
    signing_key = settings.get("calendly_signing_key", "")
    if signing_key:
        sig = request.headers.get("Calendly-Webhook-Signature", "")
        if not verify_calendly_signature(body, sig, signing_key):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = data.get("event", "")
    payload = data.get("payload", {})

    # Extract invitee info
    invitee = payload.get("invitee", {}) or {}
    invitee_name = invitee.get("name", "Unknown")
    invitee_email = invitee.get("email", "")
    invitee_phone = invitee.get("text_reminder_number", "")

    # Extract event details
    scheduled_event = payload.get("scheduled_event", {}) or {}
    event_name = payload.get("event_type", {}).get("name", "Discovery Call") if payload.get("event_type") else "Discovery Call"
    start_time = scheduled_event.get("start_time", "")

    # Extract UTM/tracking data
    tracking = payload.get("tracking", {}) or {}
    utm_source = tracking.get("utm_source", "")
    utm_campaign = tracking.get("utm_campaign", "")

    # Extract answers to custom questions
    questions = payload.get("questions_and_answers", []) or []
    qa_notes = "; ".join([f"{q.get('question', '')}: {q.get('answer', '')}" for q in questions]) if questions else ""

    if event_type == "invitee.created" and invitee_email:
        # Check if lead already exists by email
        existing = supabase.table("leads").select("id, status, name").eq("email", invitee_email).execute()

        if existing.data:
            # Update existing lead to 'meeting' status
            lead = existing.data[0]
            lead_id = lead["id"]
            updates = {
                "status": "meeting",
                "updated_at": datetime.utcnow().isoformat()
            }
            if invitee_phone and not lead.get("phone"):
                updates["phone"] = invitee_phone
            supabase.table("leads").update(updates).eq("id", lead_id).execute()

            supabase.table("activity_log").insert({
                "type": "calendly",
                "message": f"Discovery call booked: {lead['name']} ({invitee_email}) — {event_name} at {start_time}",
                "meta": {"lead_id": lead_id, "event": event_name, "start_time": start_time}
            }).execute()
        else:
            # Create new lead from Calendly booking
            source = f"calendly"
            if utm_source:
                source = f"calendly:{utm_source}"

            result = supabase.table("leads").insert({
                "name": invitee_name,
                "email": invitee_email,
                "phone": invitee_phone or "",
                "brokerage": "",
                "deals_per_year": "",
                "avg_price": "",
                "source": source,
                "status": "meeting",
                "notes": qa_notes if qa_notes else ""
            }).execute()

            lead_id = result.data[0]["id"]

            supabase.table("activity_log").insert({
                "type": "calendly",
                "message": f"New lead via Calendly: {invitee_name} ({invitee_email}) — {event_name} at {start_time}",
                "meta": {"lead_id": lead_id, "event": event_name, "start_time": start_time}
            }).execute()

        # Send notification email
        try:
            notif = settings.get("notifications", {})
            if notif.get("newLead", False):
                to_email = notif.get("email", "")
                smtp = settings.get("smtp", {})
                if to_email and smtp.get("pass"):
                    subject = f"Call Booked: {invitee_name} — TPL Mission Control"
                    html = build_calendly_email(invitee_name, invitee_email, event_name, start_time)
                    send_email(smtp, to_email, subject, html)
        except Exception:
            pass  # Never let notification failure break webhook

        return {"success": True, "action": "lead_updated" if existing.data else "lead_created", "lead_id": lead_id}

    elif event_type == "invitee.canceled" and invitee_email:
        # Log cancellation but don't delete the lead
        existing = supabase.table("leads").select("id, name").eq("email", invitee_email).execute()
        if existing.data:
            lead = existing.data[0]
            supabase.table("activity_log").insert({
                "type": "calendly",
                "message": f"Call canceled: {lead['name']} ({invitee_email})",
                "meta": {"lead_id": lead["id"], "event": event_name}
            }).execute()

        return {"success": True, "action": "cancellation_logged"}

    # Unhandled event type — acknowledge receipt
    return {"success": True, "action": "ignored", "event": event_type}


# ── SERVE DASHBOARD ──
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open("/app/static/index.html") as f:
        return f.read()
