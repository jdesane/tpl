from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from supabase import create_client
import os
import json
import hmac
import hashlib
import urllib.request
import urllib.parse
import httpx
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

def check_suppression(to_email: str) -> bool:
    """Check if an email is on the suppression list. Returns True if suppressed."""
    try:
        result = supabase.table("email_suppressions").select("id").eq("email", to_email.lower()).execute()
        return bool(result.data)
    except Exception:
        return False


def check_daily_limit(domain: str, limit: int = 200) -> bool:
    """Check if daily send limit has been reached. Returns True if OK to send."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        result = supabase.table("email_daily_limits").select("sent_count, limit_count").eq("send_date", today).eq("domain", domain).execute()
        if result.data:
            row = result.data[0]
            return row["sent_count"] < row.get("limit_count", limit)
        # No row yet — create one
        supabase.table("email_daily_limits").insert({"send_date": today, "domain": domain, "sent_count": 0, "limit_count": limit}).execute()
        return True
    except Exception:
        return True  # Don't block sends on tracking errors


def increment_daily_count(domain: str):
    """Increment the daily send count for a domain."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        result = supabase.table("email_daily_limits").select("id, sent_count").eq("send_date", today).eq("domain", domain).execute()
        if result.data:
            supabase.table("email_daily_limits").update({"sent_count": result.data[0]["sent_count"] + 1}).eq("id", result.data[0]["id"]).execute()
        else:
            supabase.table("email_daily_limits").insert({"send_date": today, "domain": domain, "sent_count": 1, "limit_count": 200}).execute()
    except Exception:
        pass


def log_email_send(contact_id, from_addr: str, to_addr: str, subject: str, status: str, resend_id: str = "", error: str = "", campaign: str = "", tracking_id: str = ""):
    """Log every email send attempt."""
    try:
        row = {
            "contact_id": contact_id,
            "from_address": from_addr,
            "to_address": to_addr,
            "subject": subject,
            "status": status,
            "resend_id": resend_id,
            "error": error,
            "campaign": campaign
        }
        if tracking_id:
            row["tracking_id"] = tracking_id
        supabase.table("email_send_log").insert(row).execute()
    except Exception:
        pass


UNSUBSCRIBE_FOOTER = """
<div style="margin-top:32px;padding-top:16px;border-top:1px solid #2a2a3d;text-align:center;">
  <p style="font-size:11px;color:#55556a;margin:0;">TPL Collective &middot; tplcollective.ai</p>
  <p style="font-size:11px;color:#55556a;margin:4px 0 0 0;">
    <a href="https://mission.tplcollective.ai/api/email/unsubscribe?email={to_email}" style="color:#6c63ff;text-decoration:none;">Unsubscribe</a>
    &middot; You received this because you engaged with TPL Collective content.
  </p>
</div>
"""


def send_email(smtp_config: dict, to_email: str, subject: str, html_body: str, from_address: str = "", contact_id: int = None, campaign: str = "") -> tuple[bool, str]:
    """Send email via Resend API with rails: suppression check, rate limit, unsubscribe footer, tracking pixel, logging."""
    try:
        api_key = smtp_config.get("pass", "")
        if not api_key:
            return False, "Resend API key not configured"

        # Rail 1: Check suppression list
        if check_suppression(to_email):
            log_email_send(contact_id, from_address, to_email, subject, "suppressed", campaign=campaign)
            return False, f"Email suppressed: {to_email}"

        # Rail 2: Check daily send limit
        domain = from_address.split("@")[1].rstrip(">").strip() if "@" in from_address else "tplcollective.co"
        if not check_daily_limit(domain):
            log_email_send(contact_id, from_address, to_email, subject, "rate_limited", campaign=campaign)
            return False, f"Daily send limit reached for {domain}"

        # Rail 3: Add unsubscribe footer
        unsub = UNSUBSCRIBE_FOOTER.replace("{to_email}", urllib.parse.quote(to_email))
        if "</body>" in html_body:
            html_body = html_body.replace("</body>", unsub + "</body>")
        else:
            html_body += unsub

        # Rail 4: Inject tracking pixel for open tracking
        import uuid
        tracking_id = str(uuid.uuid4())
        pixel = f'<img src="https://mission.tplcollective.ai/api/email/open/{tracking_id}" width="1" height="1" style="display:none;border:0;" alt="" />'
        if "</body>" in html_body:
            html_body = html_body.replace("</body>", pixel + "</body>")
        else:
            html_body += pixel

        # Determine from address
        if not from_address:
            from_address = "Joe DeSane <joe@tplcollective.co>"

        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "from": from_address,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "headers": {
                    "List-Unsubscribe": f"<https://mission.tplcollective.ai/api/email/unsubscribe?email={urllib.parse.quote(to_email)}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
                }
            },
            timeout=30
        )

        if resp.status_code == 200:
            result = resp.json()
            resend_id = result.get("id", "")
            increment_daily_count(domain)
            log_email_send(contact_id, from_address, to_email, subject, "sent", resend_id=resend_id, campaign=campaign, tracking_id=tracking_id)
            return True, ""
        else:
            try:
                err_body = resp.text or resp.content.decode('utf-8', errors='replace')
            except Exception:
                err_body = str(resp.content[:500])
            error_msg = f"Resend API error {resp.status_code}: {err_body[:500]}"
            log_email_send(contact_id, from_address or "", to_email, subject, "failed", error=error_msg, campaign=campaign)
            if resp.status_code == 400 and "bounce" in resp.text.lower():
                try:
                    supabase.table("email_suppressions").insert({"email": to_email.lower(), "reason": "hard_bounce", "source": "resend"}).execute()
                except Exception:
                    pass
            return False, error_msg

    except Exception as e:
        log_email_send(contact_id, from_address or "", to_email, subject, "failed", error=str(e), campaign=campaign)
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
        # Internal notifications use notifications@ address (no suppression check needed for Joe)
        success, error = send_email(smtp, to_email, subject, html, from_address="TPL Mission Control <notifications@tplcollective.ai>")

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
    # Check if contact already exists by email
    existing = None
    if lead.email:
        existing_result = supabase.table("leads").select("id, name, lead_score").eq("email", lead.email).execute()
        if existing_result.data:
            existing = existing_result.data[0]

    if existing:
        # UPDATE existing contact instead of creating duplicate
        lead_id = existing["id"]
        updates = {"updated_at": datetime.utcnow().isoformat()}
        if lead.brokerage:
            updates["current_brokerage"] = lead.brokerage
            updates["brokerage"] = lead.brokerage
        if lead.deals_per_year:
            updates["deals_per_year"] = lead.deals_per_year
        if lead.avg_price:
            updates["avg_price"] = lead.avg_price
        if lead.phone:
            updates["phone"] = lead.phone
        # Bump score if they re-engaged
        old_score = existing.get("lead_score") or 0
        if old_score < 50:
            updates["lead_score"] = 50
            updates["lead_temperature"] = "warming"
        updates["last_contacted_at"] = datetime.utcnow().isoformat()
        supabase.table("leads").update(updates).eq("id", lead_id).execute()

        supabase.table("lead_activity").insert({
            "lead_id": lead_id,
            "activity_type": "re_engaged",
            "description": f"Re-engaged via {lead.source or 'Web'}. Updated production: {lead.deals_per_year} deals, {lead.avg_price} avg."
        }).execute()

        supabase.table("activity_log").insert({
            "type": "lead",
            "message": f"Existing contact re-engaged: {existing['name']} via {lead.source or 'Web'}",
            "meta": {"lead_id": lead_id}
        }).execute()

        # Move opportunity to "Engaged" if in nurture
        try:
            opps = supabase.table("opportunities").select("id, stage").eq("contact_id", lead_id).eq("status", "open").execute()
            if opps.data and opps.data[0]["stage"] in ("nurture_not_ready", "new_fb_lead"):
                supabase.table("opportunities").update({
                    "stage": "engaged", "updated_at": datetime.utcnow().isoformat()
                }).eq("id", opps.data[0]["id"]).execute()
        except Exception:
            pass

    else:
        # CREATE new contact
        result = supabase.table("leads").insert({
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone or "",
            "brokerage": lead.brokerage or "",
            "current_brokerage": lead.brokerage or "",
            "deals_per_year": lead.deals_per_year or "",
            "avg_price": lead.avg_price or "",
            "source": lead.source or "Web",
            "status": "new",
            "first_name": lead.name.split(" ")[0] if lead.name else "",
            "last_name": " ".join(lead.name.split(" ")[1:]) if lead.name and " " in lead.name else "",
        }).execute()

        lead_data = result.data[0]
        lead_id = lead_data["id"]

        supabase.table("activity_log").insert({
            "type": "lead",
            "message": f"New lead: {lead.name} from {lead.brokerage or 'tplcollective.ai'}",
            "meta": {"lead_id": lead_id}
        }).execute()

        # Auto-create opportunity in default pipeline
        try:
            default_pipeline = supabase.table("pipelines").select("id").eq("is_default", True).execute()
            if default_pipeline.data:
                supabase.table("opportunities").insert({
                    "contact_id": lead_id,
                    "pipeline_id": default_pipeline.data[0]["id"],
                    "stage": "new_fb_lead",
                    "source": lead.source or "Web",
                    "status": "open"
                }).execute()
        except Exception:
            pass

    # Auto-enroll into brokerage-specific drip sequence
    brokerage_lower = (lead.brokerage or "").lower()
    funnel_trigger = "new_general_lead"  # default

    if "keller" in brokerage_lower or "kw" in brokerage_lower:
        funnel_trigger = "new_kw_lead"
    elif "exp" in brokerage_lower:
        funnel_trigger = "new_exp_lead"
    elif "remax" in brokerage_lower or "re/max" in brokerage_lower:
        funnel_trigger = "new_remax_lead"
    elif "coldwell" in brokerage_lower or "century" in brokerage_lower or "cb" in brokerage_lower or "c21" in brokerage_lower:
        funnel_trigger = "new_legacy_lead"

    try:
        funnel = supabase.table("email_funnels").select("id").eq("trigger_stage", funnel_trigger).eq("active", True).execute()
        if funnel.data:
            funnel_id = funnel.data[0]["id"]
            existing_enrollment = supabase.table("email_funnel_enrollments").select("id").eq("lead_id", lead_id).eq("funnel_id", funnel_id).execute()
            if not existing_enrollment.data:
                supabase.table("email_funnel_enrollments").insert({
                    "lead_id": lead_id,
                    "funnel_id": funnel_id,
                    "current_step": 1,
                    "status": "active"
                }).execute()
                supabase.table("activity_log").insert({
                    "type": "drip",
                    "message": f"Auto-enrolled into {funnel_trigger} drip sequence",
                    "meta": {"lead_id": lead_id, "funnel_id": funnel_id}
                }).execute()
    except Exception as e:
        print(f"[AUTO-ENROLL] Error: {e}")

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
    # Delete related records first to avoid foreign key constraint errors
    try:
        supabase.table("email_funnel_enrollments").delete().eq("lead_id", lead_id).execute()
    except Exception:
        pass
    try:
        supabase.table("opportunities").delete().eq("contact_id", lead_id).execute()
    except Exception:
        pass
    try:
        supabase.table("lead_activity").delete().eq("lead_id", lead_id).execute()
    except Exception:
        pass
    try:
        supabase.table("lead_notes").delete().eq("lead_id", lead_id).execute()
    except Exception:
        pass
    try:
        supabase.table("drip_queue").delete().eq("lead_id", lead_id).execute()
    except Exception:
        pass
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


# ── CONTACTS (alias for leads — the master database) ──

@app.get("/api/contacts")
def get_contacts(smart_list: Optional[int] = None, search: Optional[str] = None, limit: int = 500):
    query = supabase.table("leads").select("*").order("created_at", desc=True).limit(limit)

    if smart_list:
        sl = supabase.table("smart_lists").select("filters").eq("id", smart_list).execute()
        if sl.data:
            filters = sl.data[0].get("filters", {})
            if filters.get("brokerage"):
                query = query.or_(f"current_brokerage.ilike.%{filters['brokerage']}%,brokerage.ilike.%{filters['brokerage']}%")
            if filters.get("min_score"):
                query = query.gte("lead_score", filters["min_score"])
            if filters.get("source"):
                query = query.ilike("source", f"%{filters['source']}%")
            if filters.get("stale_days"):
                from datetime import timedelta
                cutoff = (datetime.utcnow() - timedelta(days=filters["stale_days"])).isoformat()
                query = query.or_(f"last_contacted_at.is.null,last_contacted_at.lt.{cutoff}")

    if search:
        query = query.or_(f"name.ilike.%{search}%,email.ilike.%{search}%,phone.ilike.%{search}%,current_brokerage.ilike.%{search}%")

    result = query.execute()
    return result.data


@app.get("/api/contacts/{contact_id}")
def get_contact(contact_id: int):
    result = supabase.table("leads").select("*").eq("id", contact_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact = result.data[0]
    # Get active opportunity
    opp = supabase.table("opportunities").select("*, pipelines(name, stages)").eq("contact_id", contact_id).eq("status", "open").execute()
    contact["opportunity"] = opp.data[0] if opp.data else None
    return contact


@app.post("/api/contacts")
async def create_contact(request: Request):
    data = await request.json()
    # Auto-split name into first/last
    if data.get("name") and not data.get("first_name"):
        parts = data["name"].split(" ", 1)
        data["first_name"] = parts[0]
        data["last_name"] = parts[1] if len(parts) > 1 else ""
    if not data.get("name") and data.get("first_name"):
        data["name"] = f"{data['first_name']} {data.get('last_name', '')}".strip()

    result = supabase.table("leads").insert(data).execute()
    contact = result.data[0] if result.data else {}
    contact_id = contact.get("id")

    if contact_id:
        supabase.table("lead_activity").insert({
            "lead_id": contact_id,
            "activity_type": "created",
            "description": f"Contact created: {data.get('name', 'Unknown')}"
        }).execute()
        supabase.table("activity_log").insert({
            "type": "lead",
            "message": f"New contact: {data.get('name', 'Unknown')}",
            "meta": {"lead_id": contact_id}
        }).execute()

    return {"success": True, "data": contact}


@app.put("/api/contacts/{contact_id}")
async def update_contact(contact_id: int, request: Request):
    data = await request.json()
    data["updated_at"] = datetime.utcnow().isoformat()

    # Track changes for activity log
    old = supabase.table("leads").select("stage, lead_score, name").eq("id", contact_id).execute()
    old_data = old.data[0] if old.data else {}

    # Auto-sync name
    if data.get("first_name") or data.get("last_name"):
        fn = data.get("first_name", old_data.get("first_name", ""))
        ln = data.get("last_name", old_data.get("last_name", ""))
        data["name"] = f"{fn} {ln}".strip()

    supabase.table("leads").update(data).eq("id", contact_id).execute()

    # Log score changes
    if "lead_score" in data and data["lead_score"] != old_data.get("lead_score"):
        supabase.table("lead_activity").insert({
            "lead_id": contact_id,
            "activity_type": "score_change",
            "description": f"Score changed: {old_data.get('lead_score', 0)} → {data['lead_score']}",
            "metadata": {"from": old_data.get("lead_score"), "to": data["lead_score"]}
        }).execute()

    return {"success": True}


@app.post("/api/contacts/import")
async def import_contacts(request: Request):
    """Import contacts from CSV data (JSON array of objects)."""
    data = await request.json()
    rows = data.get("contacts", [])
    imported = 0
    for row in rows:
        if row.get("name") and not row.get("first_name"):
            parts = row["name"].split(" ", 1)
            row["first_name"] = parts[0]
            row["last_name"] = parts[1] if len(parts) > 1 else ""
        if not row.get("name") and row.get("first_name"):
            row["name"] = f"{row['first_name']} {row.get('last_name', '')}".strip()
        row["source"] = row.get("source", "csv_import")
        try:
            supabase.table("leads").insert(row).execute()
            imported += 1
        except Exception:
            pass
    return {"success": True, "imported": imported, "total": len(rows)}


# ── OPPORTUNITIES ──

@app.get("/api/opportunities")
def get_opportunities(pipeline_id: Optional[int] = None):
    query = supabase.table("opportunities").select("*, leads(id, name, first_name, last_name, email, phone, current_brokerage, brokerage, lead_score, lead_temperature, source, tags, last_contacted_at, created_at)")
    if pipeline_id:
        query = query.eq("pipeline_id", pipeline_id)
    else:
        # Default to the default pipeline
        default = supabase.table("pipelines").select("id").eq("is_default", True).execute()
        if default.data:
            query = query.eq("pipeline_id", default.data[0]["id"])
    query = query.eq("status", "open").order("created_at", desc=False)
    result = query.execute()
    return result.data


@app.post("/api/opportunities")
async def create_opportunity(request: Request):
    data = await request.json()
    contact_id = data.get("contact_id")
    if not contact_id:
        raise HTTPException(status_code=400, detail="contact_id required")

    # Get default pipeline if not specified
    pipeline_id = data.get("pipeline_id")
    if not pipeline_id:
        default = supabase.table("pipelines").select("id").eq("is_default", True).execute()
        pipeline_id = default.data[0]["id"] if default.data else None
    if not pipeline_id:
        raise HTTPException(status_code=400, detail="No pipeline found")

    result = supabase.table("opportunities").insert({
        "contact_id": contact_id,
        "pipeline_id": pipeline_id,
        "stage": data.get("stage", "new_fb_lead"),
        "opportunity_value": data.get("opportunity_value", 0),
        "source": data.get("source", ""),
        "status": "open"
    }).execute()

    opp = result.data[0] if result.data else {}

    # Log activity
    supabase.table("lead_activity").insert({
        "lead_id": contact_id,
        "activity_type": "opportunity_created",
        "description": f"Added to pipeline: {data.get('stage', 'new_fb_lead')}"
    }).execute()

    return {"success": True, "data": opp}


@app.put("/api/opportunities/{opp_id}")
async def update_opportunity(opp_id: int, request: Request):
    data = await request.json()
    data["updated_at"] = datetime.utcnow().isoformat()

    # Track stage changes
    old = supabase.table("opportunities").select("stage, contact_id").eq("id", opp_id).execute()
    old_data = old.data[0] if old.data else {}
    old_stage = old_data.get("stage")
    new_stage = data.get("stage")

    supabase.table("opportunities").update(data).eq("id", opp_id).execute()

    if new_stage and old_stage and new_stage != old_stage:
        contact_id = old_data.get("contact_id")
        if contact_id:
            # Update last_contacted_at on the contact
            supabase.table("leads").update({
                "last_contacted_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", contact_id).execute()

            supabase.table("lead_activity").insert({
                "lead_id": contact_id,
                "activity_type": "stage_change",
                "description": f"Stage: {old_stage} → {new_stage}",
                "metadata": {"from": old_stage, "to": new_stage}
            }).execute()

            supabase.table("activity_log").insert({
                "type": "opportunity",
                "message": f"Opportunity moved: {old_stage} → {new_stage}",
                "meta": {"opportunity_id": opp_id, "contact_id": contact_id}
            }).execute()

            # If joined_lpt, create agent record
            if new_stage == "joined_lpt":
                contact = supabase.table("leads").select("name, email, phone, current_brokerage").eq("id", contact_id).execute()
                if contact.data:
                    c = contact.data[0]
                    supabase.table("agents").insert({
                        "name": c["name"],
                        "email": c.get("email", ""),
                        "phone": c.get("phone", ""),
                        "previous_brokerage": c.get("current_brokerage", ""),
                        "status": "active",
                        "join_date": datetime.utcnow().strftime("%Y-%m-%d")
                    }).execute()

    return {"success": True}


@app.delete("/api/opportunities/{opp_id}")
def delete_opportunity(opp_id: int):
    supabase.table("opportunities").update({"status": "closed"}).eq("id", opp_id).execute()
    return {"success": True}


# ── PIPELINES ──

@app.get("/api/pipelines")
def get_pipelines():
    result = supabase.table("pipelines").select("*").order("created_at").execute()
    return result.data


@app.get("/api/pipelines/{pipeline_id}")
def get_pipeline(pipeline_id: int):
    result = supabase.table("pipelines").select("*").eq("id", pipeline_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return result.data[0]


@app.post("/api/pipelines")
async def create_pipeline(request: Request):
    data = await request.json()
    result = supabase.table("pipelines").insert(data).execute()
    return {"success": True, "data": result.data[0] if result.data else None}


@app.put("/api/pipelines/{pipeline_id}")
async def update_pipeline(pipeline_id: int, request: Request):
    data = await request.json()
    data["updated_at"] = datetime.utcnow().isoformat()
    supabase.table("pipelines").update(data).eq("id", pipeline_id).execute()
    return {"success": True}


# ── SMART LISTS ──

@app.get("/api/smart-lists")
def get_smart_lists():
    result = supabase.table("smart_lists").select("*").order("sort_order").execute()
    # Add counts
    all_leads = supabase.table("leads").select("id", count="exact").execute()
    for sl in result.data:
        if not sl["filters"]:
            sl["count"] = all_leads.count or 0
        else:
            sl["count"] = "—"  # Computed on click
    return result.data


@app.post("/api/smart-lists")
async def create_smart_list(request: Request):
    data = await request.json()
    result = supabase.table("smart_lists").insert(data).execute()
    return {"success": True, "data": result.data[0] if result.data else None}


@app.delete("/api/smart-lists/{list_id}")
def delete_smart_list(list_id: int):
    supabase.table("smart_lists").delete().eq("id", list_id).execute()
    return {"success": True}


# ── CONTACT COMMUNICATIONS ──

@app.get("/api/contacts/{contact_id}/communications")
def get_contact_communications(contact_id: int):
    result = supabase.table("contact_communications").select("*").eq("contact_id", contact_id).order("created_at", desc=True).execute()
    return result.data


@app.post("/api/contacts/{contact_id}/communications")
async def add_communication(contact_id: int, request: Request):
    data = await request.json()
    data["contact_id"] = contact_id

    # If this is an outbound email, actually send it via Resend
    email_sent = False
    email_error = ""
    if data.get("channel") == "email" and data.get("direction") == "outbound":
        # Look up the contact's email
        contact = supabase.table("leads").select("email, name, first_name").eq("id", contact_id).execute()
        if contact.data and contact.data[0].get("email"):
            to_email = contact.data[0]["email"]
            subject = data.get("subject", "")
            body_text = data.get("body", "")

            # Build HTML email
            html_body = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:'DM Sans',Helvetica,Arial,sans-serif;">
<div style="max-width:580px;margin:0 auto;padding:32px 16px;">
<div style="font-size:15px;color:#e8e8f0;line-height:1.75;white-space:pre-wrap;">{body_text}</div>
</div></body></html>"""

            settings = load_settings()
            smtp = settings.get("smtp", {})
            success, error = send_email(smtp, to_email, subject, html_body,
                                         from_address="Joe DeSane <joe@tplcollective.co>",
                                         contact_id=contact_id,
                                         campaign="direct")
            email_sent = success
            email_error = error
        else:
            email_error = "Contact has no email address"

    # Log the communication record
    result = supabase.table("contact_communications").insert(data).execute()

    supabase.table("lead_activity").insert({
        "lead_id": contact_id,
        "activity_type": "communication",
        "description": f"{data.get('channel', 'email')} {data.get('direction', 'outbound')}: {data.get('subject', '')}"
    }).execute()

    # Update last_contacted_at
    supabase.table("leads").update({
        "last_contacted_at": datetime.utcnow().isoformat()
    }).eq("id", contact_id).execute()

    return {"success": True, "email_sent": email_sent, "email_error": email_error, "data": result.data[0] if result.data else None}


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
    import random
    data = await request.json()
    prompt = data.get("prompt", "").lower()
    content_type = data.get("type", "social")

    # ── KNOWLEDGE BASE ──
    brokerage_data = {
        "kw": {"name": "Keller Williams", "split": "70/30", "cap": "$18K–$25K", "franchise": "6% (capped $3K)", "desk": "$75–$100/mo", "pain": "highest total cost", "savings": "$17,883"},
        "exp": {"name": "eXp Realty", "split": "80/20", "cap": "$16,000", "franchise": "None", "desk": "$0", "tech": "$85/mo ($1,020/yr)", "pain": "8 quarters of declining agent count", "savings": "$10,349"},
        "remax": {"name": "RE/MAX", "split": "varies", "cap": "None (desk fee model)", "franchise": "2–5%", "desk": "$500–$3,000/mo", "pain": "desk fees alone exceed LPT's total cost", "savings": "~$16,960"},
        "cb": {"name": "Coldwell Banker", "split": "50/50 to 90/10", "cap": "None", "franchise": "6–8%", "desk": "$100–$179/mo", "pain": "most expensive model", "savings": "$42,000+"},
        "c21": {"name": "Century 21", "split": "70/30 starting", "cap": "varies", "franchise": "6% royalty every deal", "desk": "varies", "pain": "6% royalty on every closing", "savings": "significant"},
        "real": {"name": "REAL Brokerage", "split": "85/15", "cap": "$12,000", "franchise": "None", "desk": "$0", "pain": "$12K cap vs $5K", "savings": "~$7,000"},
    }

    lpt_facts = {
        "cap": "LPT Realty caps at $5,000/year on the Business Builder plan. That's 10 deals at $500 each — then you close at 100% the rest of the year.",
        "split": "100% commission on Business Builder. You keep your entire GCI. LPT charges a flat $500 per transaction, not a percentage.",
        "fees": "No desk fees. No monthly tech fees. No franchise fees. $195 processing fee per deal. $500 annual fee. That's it.",
        "revshare": "HybridShare is LPT's 7-tier revenue share program. Available on the Brokerage Partner plan (80/20, $15K cap). You earn monthly from your network's production — for life.",
        "tools": "Every LPT agent gets Lofty CRM, Dotloop, Listing Power Tools, and $11K+ in marketing tools at no additional cost.",
        "growth": "LPT Realty is the fastest-growing brokerage in America — Deloitte Fast 500. 21,000+ agents and growing every quarter.",
        "stock": "LPT has reserved ticker LPTA on Nasdaq. Agents earn stock grants — 2x multiplier on the Brokerage Partner plan.",
        "ai": "TPL Collective agents get Dezzy.ai, RecruitAssist, and a full AI media stack. Not a CRM — an AI workforce.",
        "plus": "LPT Plus is an optional add-on: $89/mo (BP) or $149/mo (BB). Includes prospecting leads, AMCards, Zoom Enterprise, RealScout, listing marketing, health benefits via Teladoc, and 2x weekly masterminds.",
    }

    # ── DETECT CONTEXT FROM PROMPT ──
    detected_brokerage = None
    for key, bd in brokerage_data.items():
        if key in prompt or bd["name"].lower() in prompt:
            detected_brokerage = key
            break
    if "keller" in prompt or "kw " in prompt:
        detected_brokerage = "kw"
    elif "exp " in prompt or "exp " in prompt or "exprealty" in prompt:
        detected_brokerage = "exp"
    elif "remax" in prompt or "re/max" in prompt:
        detected_brokerage = "remax"
    elif "coldwell" in prompt or " cb " in prompt:
        detected_brokerage = "cb"
    elif "century" in prompt or "c21" in prompt:
        detected_brokerage = "c21"
    elif "real brokerage" in prompt:
        detected_brokerage = "real"

    detected_topics = []
    topic_keywords = {
        "cap": ["cap", "$5k", "$5,000", "annual cap"],
        "split": ["split", "commission", "100%", "keep more"],
        "fees": ["fee", "desk fee", "franchise fee", "no fee", "zero fee", "hidden"],
        "revshare": ["rev share", "revshare", "hybridshare", "passive income", "residual", "downline", "network"],
        "tools": ["tools", "crm", "lofty", "dotloop", "tech", "technology"],
        "growth": ["growth", "growing", "deloitte", "fastest", "momentum"],
        "stock": ["stock", "equity", "lpta", "nasdaq", "ipo"],
        "ai": ["ai", "dezzy", "recruit assist", "media stack", "artificial intelligence"],
        "plus": ["lpt plus", "leads", "coaching", "mastermind", "health benefit"],
    }
    for topic, keywords in topic_keywords.items():
        if any(kw in prompt for kw in keywords):
            detected_topics.append(topic)

    if not detected_topics:
        detected_topics = random.sample(["cap", "split", "fees", "growth"], 2)

    detected_tone = "professional"
    if any(w in prompt for w in ["casual", "friendly", "conversational", "chill"]):
        detected_tone = "casual"
    elif any(w in prompt for w in ["urgent", "direct", "bold", "aggressive"]):
        detected_tone = "urgent"
    elif any(w in prompt for w in ["story", "testimonial", "personal", "narrative"]):
        detected_tone = "story"

    detected_stage = None
    if any(w in prompt for w in ["discovery", "call", "booked", "pre-call"]):
        detected_stage = "pre_call"
    elif any(w in prompt for w in ["follow up", "follow-up", "after call", "post-call", "didn't commit", "haven't committed"]):
        detected_stage = "post_call"
    elif any(w in prompt for w in ["new lead", "first", "welcome", "intro"]):
        detected_stage = "new"
    elif any(w in prompt for w in ["considering", "on the fence", "thinking", "deciding"]):
        detected_stage = "considering"
    elif any(w in prompt for w in ["no show", "missed", "didn't show", "ghosted"]):
        detected_stage = "no_show"
    elif any(w in prompt for w in ["onboard", "joined", "welcome aboard"]):
        detected_stage = "onboarding"

    bd = brokerage_data.get(detected_brokerage, {})

    # Build shared context
    brokerage_context = ""
    if detected_brokerage and bd:
        brokerage_context = f"\nRecipient's current brokerage: {bd['name']}\n- Their split: {bd.get('split', 'unknown')}\n- Their cap: {bd.get('cap', 'unknown')}\n- Their desk fees: {bd.get('desk', 'unknown')}\n- Their franchise fees: {bd.get('franchise', 'unknown')}\n- Known pain point: {bd.get('pain', 'high costs')}\n- Estimated savings by switching to LPT: {bd.get('savings', 'significant')}"

    settings = load_settings()

    # ── GENERATE EMAIL ──
    if content_type == "email":
        lpt_context = "\n".join([f"- {k}: {v}" for k, v in lpt_facts.items()])

        system_prompt = f"""You are Joe DeSane, founder of TPL Collective, writing recruiting emails to real estate agents about switching to LPT Realty.

IMPORTANT RULES:
- Write exactly what the user asks for. Follow their prompt closely.
- If they mention a name, use that name. If they describe a relationship, reflect it.
- Sound like a real person, not a marketing template. Conversational, direct, no fluff.
- NEVER use em dashes (the long dash). Use regular dashes (-) or rewrite the sentence.
- Keep it concise. Most emails should be under 150 words.
- Use [Name] as placeholder ONLY if no specific name is given in the prompt.
- Always sign off as Joe DeSane, TPL Collective.
- Include calendly.com/discovertpl or tplcollective.ai/commission-calculator as CTA when appropriate.
- TPL Collective is NOT LPT Realty. TPL is the community/team. LPT is the brokerage.

LPT REALTY FACTS (use only when relevant):
{lpt_context}
{brokerage_context}

OUTPUT FORMAT:
First line must be: Subject: [your subject line]
Then a blank line, then the email body.
Do not include any markdown formatting."""

        selected_model = data.get("model", "claude-haiku")
        user_prompt = data.get("prompt", "")

        model_map = {
            "claude-haiku": {"provider": "anthropic", "model_id": "claude-haiku-4-5-20251001"},
            "claude-sonnet": {"provider": "anthropic", "model_id": "claude-sonnet-4-5-20250514"},
            "gpt-4o-mini": {"provider": "openai", "model_id": "gpt-4o-mini"},
            "gpt-4o": {"provider": "openai", "model_id": "gpt-4o"},
        }
        model_info = model_map.get(selected_model, model_map["claude-haiku"])

        try:
            if model_info["provider"] == "anthropic":
                api_key = settings.get("anthropic_api_key", "")
                if not api_key:
                    return {"success": False, "error": "Anthropic API key not configured"}
                ai_resp = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_info["model_id"],
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                        "temperature": 0.8,
                        "max_tokens": 800
                    },
                    timeout=30
                )
                if ai_resp.status_code == 200:
                    result = ai_resp.json()["content"][0]["text"].strip()
                else:
                    return {"success": False, "error": f"Claude API error: {ai_resp.status_code}"}
            else:
                api_key = settings.get("openai_api_key", "")
                if not api_key:
                    return {"success": False, "error": "OpenAI API key not configured"}
                ai_resp = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_info["model_id"],
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.8,
                        "max_tokens": 800
                    },
                    timeout=30
                )
                if ai_resp.status_code == 200:
                    result = ai_resp.json()["choices"][0]["message"]["content"].strip()
                else:
                    return {"success": False, "error": f"OpenAI API error: {ai_resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"AI generation failed: {str(e)}"}

    # ── GENERATE SOCIAL POST ──
    else:
        social_system_prompt = f"""You are Joe DeSane, founder of TPL Collective, writing social media posts to recruit real estate agents to LPT Realty.

IMPORTANT RULES:
- Write exactly what the user asks for. Follow their prompt closely.
- Sound authentic, not corporate. Conversational, punchy, direct.
- NEVER use em dashes (the long dash). Use regular dashes (-) or rewrite the sentence.
- Keep posts concise. Most should be under 200 words.
- Include relevant hashtags at the end (5-7 max).
- Always include a CTA - either tplcollective.ai/commission-calculator or calendly.com/discovertpl or "DM me".
- TPL Collective is NOT LPT Realty. TPL is the community/team. LPT is the brokerage.
- Emojis are fine for social posts but don't overdo it.

LPT REALTY FACTS (use only when relevant):
""" + chr(10).join([f"- {k}: {v}" for k, v in lpt_facts.items()]) + """
""" + brokerage_context + """

Do not include any markdown formatting. Just output the post text with hashtags."""

        selected_model = data.get("model", "claude-haiku")
        user_prompt = data.get("prompt", "")

        model_map = {
            "claude-haiku": {"provider": "anthropic", "model_id": "claude-haiku-4-5-20251001"},
            "claude-sonnet": {"provider": "anthropic", "model_id": "claude-sonnet-4-5-20250514"},
            "gpt-4o-mini": {"provider": "openai", "model_id": "gpt-4o-mini"},
            "gpt-4o": {"provider": "openai", "model_id": "gpt-4o"},
        }
        model_info = model_map.get(selected_model, model_map["claude-haiku"])

        try:
            if model_info["provider"] == "anthropic":
                api_key = settings.get("anthropic_api_key", "")
                if not api_key:
                    return {"success": False, "error": "Anthropic API key not configured"}
                ai_resp = httpx.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_info["model_id"],
                        "system": social_system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                        "temperature": 0.8,
                        "max_tokens": 600
                    },
                    timeout=30
                )
                if ai_resp.status_code == 200:
                    result = ai_resp.json()["content"][0]["text"].strip()
                else:
                    return {"success": False, "error": f"Claude API error: {ai_resp.status_code}"}
            else:
                api_key = settings.get("openai_api_key", "")
                if not api_key:
                    return {"success": False, "error": "OpenAI API key not configured"}
                ai_resp = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_info["model_id"],
                        "messages": [
                            {"role": "system", "content": social_system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.8,
                        "max_tokens": 600
                    },
                    timeout=30
                )
                if ai_resp.status_code == 200:
                    result = ai_resp.json()["choices"][0]["message"]["content"].strip()
                else:
                    return {"success": False, "error": f"OpenAI API error: {ai_resp.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"AI generation failed: {str(e)}"}

    return {"success": True, "generated": result, "type": content_type}


@app.post("/api/ai/generate-image")
async def ai_generate_image(request: Request):
    """Generate an image using DALL-E 3."""
    data = await request.json()
    prompt = data.get("prompt", "")
    size = data.get("size", "1024x1024")
    if not prompt:
        return {"success": False, "error": "No prompt provided"}

    settings = load_settings()
    openai_key = settings.get("openai_api_key", "")
    if not openai_key:
        return {"success": False, "error": "OpenAI API key not configured"}

    try:
        resp = httpx.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": "standard"
            },
            timeout=60
        )
        if resp.status_code == 200:
            result = resp.json()
            image_url = result["data"][0]["url"]
            revised_prompt = result["data"][0].get("revised_prompt", "")
            return {"success": True, "image_url": image_url, "revised_prompt": revised_prompt}
        else:
            return {"success": False, "error": f"DALL-E error: {resp.status_code} - {resp.text}"}
    except Exception as e:
        return {"success": False, "error": f"Image generation failed: {str(e)}"}


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
    leads = supabase.table("leads").select("id, name, email, phone, stage, status, brokerage, current_brokerage, deals_per_year, lead_temperature, created_at, updated_at").execute().data
    updated = 0
    hot_alerts_sent = 0
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
        prev_temp = lead.get("lead_temperature", "cold")
        supabase.table("leads").update({"lead_score": score, "lead_temperature": temp}).eq("id", lead["id"]).execute()
        updated += 1

        # Hot lead alert - only fire when temperature changes TO hot
        if temp == "hot" and prev_temp != "hot":
            try:
                settings = load_settings()
                smtp = settings.get("smtp", {})
                to_email = settings.get("notifications", {}).get("email", "joe@desaneteam.com")
                lead_name = lead.get("name", "Unknown")
                lead_brokerage = lead.get("brokerage") or lead.get("current_brokerage") or "N/A"
                lead_email = lead.get("email", "N/A")
                lead_phone = lead.get("phone", "N/A")
                subject = f"Hot Lead Alert: {lead_name} ({lead_brokerage}) - Score: {score}"
                html_body = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#0e0e1a;font-family:Arial,sans-serif;">
  <div style="max-width:520px;margin:24px auto;background:#161627;border-radius:12px;padding:28px;border:1px solid #6c63ff;">
    <div style="text-align:center;margin-bottom:20px;">
      <span style="background:#ff4d4d;color:#fff;padding:6px 16px;border-radius:20px;font-weight:bold;font-size:14px;">HOT LEAD ALERT</span>
    </div>
    <h2 style="color:#fff;margin:0 0 16px 0;text-align:center;">{lead_name}</h2>
    <table style="width:100%;color:#c4c4d4;font-size:14px;border-collapse:collapse;">
      <tr><td style="padding:6px 0;color:#888;">Email</td><td style="padding:6px 0;color:#fff;">{lead_email}</td></tr>
      <tr><td style="padding:6px 0;color:#888;">Phone</td><td style="padding:6px 0;color:#fff;">{lead_phone}</td></tr>
      <tr><td style="padding:6px 0;color:#888;">Brokerage</td><td style="padding:6px 0;color:#fff;">{lead_brokerage}</td></tr>
      <tr><td style="padding:6px 0;color:#888;">Lead Score</td><td style="padding:6px 0;color:#ff4d4d;font-weight:bold;font-size:18px;">{score}/100</td></tr>
      <tr><td style="padding:6px 0;color:#888;">Temperature</td><td style="padding:6px 0;color:#ff4d4d;font-weight:bold;">HOT</td></tr>
    </table>
    <div style="margin-top:20px;padding:14px;background:#1e1e36;border-radius:8px;border-left:3px solid #ff4d4d;">
      <p style="color:#ff9f43;font-weight:bold;margin:0 0 4px 0;">Suggested Action</p>
      <p style="color:#c4c4d4;margin:0;">Call within 24 hours while interest is high.</p>
    </div>
    <div style="text-align:center;margin-top:20px;">
      <a href="https://mission.tplcollective.ai" style="display:inline-block;background:#6c63ff;color:#fff;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:bold;margin-right:8px;">View in Mission Control</a>
      <a href="https://calendly.com/discovertpl" style="display:inline-block;background:#1e1e36;color:#6c63ff;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:bold;border:1px solid #6c63ff;">Schedule via Calendly</a>
    </div>
    <div style="margin-top:20px;font-size:11px;color:#444;text-align:center;">TPL Mission Control - Hot Lead Alert</div>
  </div>
</body></html>"""
                success, error = send_email(
                    smtp, to_email, subject, html_body,
                    from_address="TPL Mission Control <notifications@tplcollective.ai>",
                    campaign="hot_lead_alert"
                )
                if success:
                    hot_alerts_sent += 1
                    supabase.table("activity_log").insert({
                        "type": "alert",
                        "message": f"Hot lead alert sent for {lead_name} (score: {score})",
                        "meta": {"lead_id": lead["id"], "score": score}
                    }).execute()
            except Exception:
                pass  # Don't let alert failures break scoring

    return {"success": True, "updated": updated, "hot_alerts_sent": hot_alerts_sent}


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


# ── IDEAS INBOX ──

@app.get("/api/ideas")
async def list_ideas():
    """List all ideas, newest first."""
    data = supabase.table("ideas").select("*").order("created_at", desc=True).execute()
    return data.data

@app.patch("/api/ideas/{idea_id}")
async def update_idea(idea_id: str, request: Request):
    """Update an idea (status, notes, etc.)."""
    body = await request.json()
    allowed = {"status", "title", "notes", "type"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(400, "No valid fields to update")
    supabase.table("ideas").update(updates).eq("id", idea_id).execute()
    return {"success": True}

@app.delete("/api/ideas/{idea_id}")
async def delete_idea(idea_id: str):
    """Delete an idea."""
    supabase.table("ideas").delete().eq("id", idea_id).execute()
    return {"success": True}


# ── DAILY MORNING REPORT ──

@app.post("/api/reports/daily")
async def send_daily_report():
    """Generate and email the daily morning briefing to Joe."""
    from datetime import timedelta

    settings = load_settings()
    smtp = settings.get("smtp", {})
    to_email = settings.get("notifications", {}).get("email", "joe@desaneteam.com")

    now = datetime.utcnow()
    yesterday = (now - timedelta(hours=24)).isoformat()
    today_str = now.strftime("%Y-%m-%d")
    seven_days_ago = (now - timedelta(days=7)).isoformat()

    # ── GATHER DATA ──

    # New leads (24h)
    new_leads = supabase.table("leads").select("id, name, email, source, lead_score").gte("created_at", yesterday).order("created_at", desc=True).execute().data

    # Re-engagements (24h)
    re_engagements = supabase.table("lead_activity").select("lead_id, description").in_("activity_type", ["re_engaged", "calculator_used", "page_view"]).gte("created_at", yesterday).execute().data

    # Stage changes (24h)
    stage_changes = supabase.table("lead_activity").select("lead_id, description").eq("activity_type", "stage_change").gte("created_at", yesterday).execute().data

    # Calendly bookings (24h)
    calendly = supabase.table("activity_log").select("message").eq("type", "calendly").gte("created_at", yesterday).execute().data

    # Email stats (24h)
    emails_sent = supabase.table("email_send_log").select("id, status").gte("created_at", yesterday).execute().data
    sent_count = sum(1 for e in emails_sent if e["status"] == "sent")
    bounced = sum(1 for e in emails_sent if e["status"] == "failed")
    suppressed = sum(1 for e in emails_sent if e["status"] == "suppressed")

    # Unsubscribes (24h)
    unsubs = supabase.table("email_suppressions").select("email").eq("reason", "unsubscribe").gte("created_at", yesterday).execute().data

    # Drip progress
    drip_active = supabase.table("email_funnel_enrollments").select("id", count="exact").eq("status", "active").execute()
    drip_completed = supabase.table("email_funnel_enrollments").select("id", count="exact").eq("status", "completed").execute()

    # Today's tasks
    tasks_today = supabase.table("tasks").select("id, title, priority").eq("due_date", today_str).neq("status", "done").execute().data

    # Follow-ups due today
    followups = supabase.table("leads").select("id, name, follow_up_date").eq("follow_up_date", today_str).execute().data

    # Stale leads (no contact in 7+ days, still in active pipeline)
    stale = supabase.table("leads").select("id, name, last_contacted_at").or_(f"last_contacted_at.is.null,last_contacted_at.lt.{seven_days_ago}").not_.in_("stage", ["signed", "onboarding"]).limit(10).execute().data

    # Hot leads
    hot = supabase.table("leads").select("id, name, lead_score, current_brokerage, lead_temperature").not_.is_("lead_score", "null").order("lead_score", desc=True).limit(5).execute().data

    # Pipeline totals
    total_contacts = supabase.table("leads").select("id", count="exact").execute()
    total_opps = supabase.table("opportunities").select("id", count="exact").eq("status", "open").execute()

    # Pipeline health
    try:
        health = await dashboard_pipeline_health()
    except Exception:
        health = {"score": 0, "status": "Unknown"}

    # Daily send limits
    limits = supabase.table("email_daily_limits").select("*").eq("send_date", today_str).execute().data

    # Ideas captured (24h)
    new_ideas = supabase.table("ideas").select("id, title, type, url, created_at").gte("created_at", yesterday).order("created_at", desc=True).execute().data
    ideas_inbox = supabase.table("ideas").select("id", count="exact").eq("status", "inbox").execute()

    # A/B Test performance (Gut Punch variants)
    ab_test_funnels = {8: "A: $467K Story", 10: "B: Curiosity", 11: "C: Personalized", 12: "D: Social Proof", 13: "E: Direct Savings"}
    ab_results = []
    for fid, fname in ab_test_funnels.items():
        enrolled = supabase.table("email_funnel_enrollments").select("lead_id", count="exact").eq("funnel_id", fid).execute()
        sent_logs = supabase.table("email_send_log").select("id, status").ilike("campaign", f"%Step 1%").eq("campaign", f"KW Gut Punch%").execute().data if fid == 8 else []
        # Get emails sent for this funnel by checking campaign field
        funnel_name = supabase.table("email_funnels").select("name").eq("id", fid).execute().data
        fn = funnel_name[0]["name"] if funnel_name else ""
        campaign_logs = supabase.table("email_send_log").select("id, status").ilike("campaign", f"{fn}%").execute().data
        total_sent = sum(1 for e in campaign_logs if e["status"] in ("sent", "delivered", "opened"))
        total_opened = sum(1 for e in campaign_logs if e["status"] == "opened")
        open_rate = f"{round(total_opened/total_sent*100)}%" if total_sent > 0 else "pending"
        ab_results.append({"name": fname, "enrolled": enrolled.count or 0, "sent": total_sent, "opened": total_opened, "open_rate": open_rate})

    # ── BUILD HTML ──

    def section(title, content):
        return f'<div style="margin-bottom:24px;"><div style="font-family:DM Mono,monospace;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#6c63ff;margin-bottom:10px;">{title}</div>{content}</div>'

    def stat_row(label, value, color="#e8e8f0"):
        return f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #2a2a3d;font-size:13px;"><span style="color:#8888aa;">{label}</span><span style="color:{color};font-weight:600;">{value}</span></div>'

    def item_list(items):
        if not items:
            return '<div style="color:#55556a;font-size:12px;padding:8px 0;">None</div>'
        return ''.join(f'<div style="padding:4px 0;font-size:12px;color:#e8e8f0;border-bottom:1px solid #1a1a26;">{item}</div>' for item in items)

    # Pipeline Pulse
    pipeline_html = stat_row("New leads (24h)", f"{len(new_leads)}", "#34d399" if new_leads else "#8888aa")
    pipeline_html += stat_row("Calendly bookings", f"{len(calendly)}", "#34d399" if calendly else "#8888aa")
    pipeline_html += stat_row("Re-engagements", f"{len(set(r['lead_id'] for r in re_engagements))}", "#f0c040" if re_engagements else "#8888aa")
    pipeline_html += stat_row("Stage changes", f"{len(stage_changes)}", "#6c63ff" if stage_changes else "#8888aa")

    if new_leads:
        pipeline_html += '<div style="margin-top:8px;font-size:11px;color:#8888aa;">New: ' + ', '.join(f"{l['name']} ({l.get('source', '')})" for l in new_leads[:5]) + '</div>'

    # Email Performance
    email_html = stat_row("Sent yesterday", str(sent_count), "#34d399" if sent_count else "#8888aa")
    email_html += stat_row("Bounced", str(bounced), "#f87171" if bounced else "#34d399")
    email_html += stat_row("Suppressed", str(suppressed))
    email_html += stat_row("Unsubscribes", str(len(unsubs)), "#f87171" if unsubs else "#34d399")
    email_html += stat_row("Drip queue active", str(drip_active.count or 0))
    email_html += stat_row("Drip completed", str(drip_completed.count or 0))

    if limits:
        lim = limits[0]
        email_html += stat_row("Send limit today", f"{lim['sent_count']}/{lim['limit_count']}")

    # Today's Actions
    task_items = [f"{'🔴' if t.get('priority') == 'urgent' else '🟡'} {t['title']}" for t in tasks_today]
    followup_items = [f"📞 Follow up: {f['name']}" for f in followups]
    action_html = item_list(task_items + followup_items)

    # Stale Leads
    stale_items = [f"⏰ {s['name']} — last contact: {s.get('last_contacted_at', 'never')[:10] if s.get('last_contacted_at') else 'never'}" for s in stale[:5]]
    stale_html = item_list(stale_items)

    # Hot Leads
    hot_items = [f"{'🔥' if (l.get('lead_score') or 0) >= 70 else '🟡'} {l['name']} — {l.get('lead_score', 0)} ({l.get('current_brokerage', '')})" for l in hot]
    hot_html = item_list(hot_items)

    # System Status
    health_color = "#34d399" if health.get("score", 0) >= 70 else "#fbbf24" if health.get("score", 0) >= 40 else "#f87171"
    system_html = stat_row("Pipeline health", f"{health.get('score', 0)} — {health.get('status', 'Unknown')}", health_color)
    system_html += stat_row("Total contacts", str(total_contacts.count or 0))
    system_html += stat_row("Active opportunities", str(total_opps.count or 0))
    system_html += stat_row("Stale leads (7d+)", str(len(stale)))

    # Ideas Captured
    type_icons = {"idea": "\U0001F4A1", "link": "\U0001F517", "video": "\U0001F3AC", "screenshot": "\U0001F4F7", "screen_recording": "\U0001F4F1"}
    bulb = "\U0001F4A1"
    idea_items = [f"{type_icons.get(i.get('type', 'idea'), bulb)} {i['title']}" + (f" - {i['url']}" if i.get('url') else "") for i in new_ideas]
    ideas_html = stat_row("New ideas (24h)", str(len(new_ideas)), "#f0c040" if new_ideas else "#8888aa")
    ideas_html += stat_row("Total in inbox", str(ideas_inbox.count or 0), "#6c63ff" if (ideas_inbox.count or 0) > 0 else "#8888aa")
    if idea_items:
        ideas_html += '<div style="margin-top:8px;">' + item_list(idea_items[:5]) + '</div>'

    # A/B Test HTML
    ab_html = ""
    for ab in ab_results:
        open_color = "#34d399" if ab["open_rate"] not in ("pending", "0%") else "#8888aa"
        ab_html += stat_row(ab["name"], f"{ab['enrolled']} enrolled / {ab['sent']} sent / {ab['opened']} opened ({ab['open_rate']})", open_color)

    # Assemble
    date_display = now.strftime("%A, %B %d, %Y")

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:'DM Sans',Helvetica,Arial,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:32px 20px;">

<div style="margin-bottom:28px;">
  <div style="font-size:24px;font-weight:700;color:#e8e8f0;letter-spacing:2px;margin-bottom:4px;">TPL<span style="color:#6c63ff;">.</span></div>
  <div style="font-size:11px;color:#55556a;letter-spacing:3px;text-transform:uppercase;">Daily Briefing &middot; {date_display}</div>
</div>

<div style="background:#12121a;border:1px solid #2a2a3d;border-radius:12px;padding:24px;margin-bottom:16px;">
{section("Pipeline Pulse", pipeline_html)}
{section("Email Performance", email_html)}
{section("Today's Actions", action_html)}
{section("Stale Leads", stale_html)}
{section("Hottest Leads", hot_html)}
{section("System Status", system_html)}
{section("Ideas Captured", ideas_html)}
{section("A/B Test: Gut Punch Variants", ab_html)}
</div>

<div style="text-align:center;padding:16px 0;">
  <a href="https://mission.tplcollective.ai" style="display:inline-block;background:#6c63ff;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:13px;font-weight:600;">Open Mission Control &rarr;</a>
</div>

<div style="text-align:center;font-size:10px;color:#55556a;margin-top:16px;">TPL Collective &middot; mission.tplcollective.ai</div>

</div></body></html>"""

    subject = f"Daily Briefing — {len(new_leads)} new leads, {sent_count} emails sent — {now.strftime('%b %d')}"

    success, error = send_email(
        smtp, to_email, subject, html,
        from_address="TPL Mission Control <notifications@tplcollective.co>",
        campaign="daily_briefing"
    )

    return {"success": success, "error": error if not success else None}


# ── DRIP PROCESSOR ──

@app.post("/api/drip/process")
async def process_drip_queue():
    """Process the email drip queue. Call this on a cron schedule (every 15 min)."""
    settings = load_settings()
    smtp = settings.get("smtp", {})
    if not smtp.get("pass"):
        return {"success": False, "error": "Resend API key not configured"}

    from_address = "Joe DeSane <joe@tplcollective.co>"
    domain = "tplcollective.co"

    # Check daily limit
    if not check_daily_limit(domain):
        return {"success": True, "sent": 0, "reason": "Daily limit reached"}

    # Get active enrollments that need sending
    enrollments = supabase.table("email_funnel_enrollments").select(
        "*, leads(id, email, first_name, name), email_funnels(name)"
    ).eq("status", "active").execute().data

    sent = 0
    skipped = 0
    errors = 0
    now = datetime.utcnow()

    for enrollment in enrollments:
        # Re-check limit each iteration
        if not check_daily_limit(domain):
            break

        contact = enrollment.get("leads") or {}
        email = contact.get("email", "")
        contact_id = contact.get("id")
        first_name = contact.get("first_name") or contact.get("name", "").split(" ")[0] or "there"

        if not email:
            skipped += 1
            continue

        # Get the current step
        funnel_id = enrollment.get("funnel_id")
        current_step = enrollment.get("current_step", 1)
        last_sent = enrollment.get("last_sent_at")

        # Get the step details
        step = supabase.table("email_funnel_steps").select("*").eq("funnel_id", funnel_id).eq("step_order", current_step).execute()
        if not step.data:
            # No more steps — mark complete
            supabase.table("email_funnel_enrollments").update({
                "status": "completed",
                "completed_at": now.isoformat()
            }).eq("id", enrollment["id"]).execute()
            continue

        step_data = step.data[0]
        delay_days = step_data.get("delay_days", 0)

        # Check if enough time has passed since last send
        if last_sent:
            try:
                last_dt = datetime.fromisoformat(last_sent.replace("Z", "+00:00"))
                days_since = (now - last_dt).days
                if days_since < delay_days:
                    skipped += 1
                    continue
            except Exception as e:
                print(f"[DRIP] Date parse error for enrollment {enrollment.get('id')}: {e}")
                skipped += 1
                continue
        elif current_step > 1:
            # First step has no delay requirement, but subsequent steps need last_sent
            skipped += 1
            continue

        # Personalize the email
        subject = step_data["subject"].replace("[Name]", first_name).replace("[name]", first_name)
        body_text = step_data["body"].replace("[Name]", first_name).replace("[name]", first_name)

        # Replace URLs with clean short links
        if contact_id:
            import re
            short_map = {
                "tplcollective.ai/commission-calculator": f"https://mission.tplcollective.ai/go/calc-{contact_id}",
                "tplcollective.ai/vs/keller-williams": f"https://mission.tplcollective.ai/go/vs-kw-{contact_id}",
                "tplcollective.ai/vs/exp-realty": f"https://mission.tplcollective.ai/go/vs-exp-{contact_id}",
                "tplcollective.ai/vs/coldwell-banker": f"https://mission.tplcollective.ai/go/vs-cb-{contact_id}",
                "tplcollective.ai/fee-plans": f"https://mission.tplcollective.ai/go/fees-{contact_id}",
                "tplcollective.ai/lpt-explained": f"https://mission.tplcollective.ai/go/lpt-{contact_id}",
                "tplcollective.ai/join": f"https://mission.tplcollective.ai/go/join-{contact_id}",
                "calendly.com/discovertpl": f"https://mission.tplcollective.ai/go/book-{contact_id}",
            }
            for original, short in short_map.items():
                body_text = body_text.replace(original, short)
            # Catch any remaining tplcollective.ai URLs
            def add_cid(match):
                url = match.group(0)
                sep = "&" if "?" in url else "?"
                return f"{url}{sep}cid={contact_id}&ref=drip"
            body_text = re.sub(r'tplcollective\.ai/[^\s"\'<>]+', add_cid, body_text)

        # Convert short URLs into clickable HTML links
        import re as _re
        def linkify(text):
            # Match URLs starting with https://mission.tplcollective.ai/go/
            def make_link(m):
                url = m.group(0)
                # Determine anchor text from the URL
                if '/go/calc-' in url:
                    anchor = 'Run your numbers in 30 seconds →'
                elif '/go/vs-kw-' in url:
                    anchor = 'See the full KW vs LPT comparison →'
                elif '/go/vs-exp-' in url:
                    anchor = 'See the eXp vs LPT comparison →'
                elif '/go/vs-cb-' in url:
                    anchor = 'See the Coldwell Banker comparison →'
                elif '/go/book-' in url:
                    anchor = 'Book 15 minutes with me →'
                elif '/go/fees-' in url:
                    anchor = 'See the full fee breakdown →'
                elif '/go/join-' in url:
                    anchor = 'See how to join →'
                elif '/go/lpt-' in url:
                    anchor = 'Learn how LPT works →'
                else:
                    anchor = url
                return f'<a href="{url}" style="color:#6c63ff;text-decoration:none;font-weight:600;">{anchor}</a>'
            text = _re.sub(r'https://mission\.tplcollective\.ai/go/[^\s<>"\']+', make_link, text)
            return text

        body_html = linkify(body_text)

        # Build HTML email
        html_body = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:'DM Sans',Helvetica,Arial,sans-serif;">
<div style="max-width:580px;margin:0 auto;padding:32px 16px;">
<div style="font-size:15px;color:#e8e8f0;line-height:1.75;white-space:pre-wrap;">{body_html}</div>
</div></body></html>"""

        funnel_name = (enrollment.get("email_funnels") or {}).get("name", "drip")
        campaign = f"{funnel_name} - Step {current_step}"

        success, error = send_email(smtp, email, subject, html_body,
                                     from_address=from_address,
                                     contact_id=contact_id,
                                     campaign=campaign)

        if success:
            sent += 1
            # Update enrollment
            next_step = current_step + 1
            next_step_exists = supabase.table("email_funnel_steps").select("id").eq("funnel_id", funnel_id).eq("step_order", next_step).execute()

            updates = {
                "last_sent_at": now.isoformat(),
                "current_step": next_step
            }
            if not next_step_exists.data:
                updates["status"] = "completed"
                updates["completed_at"] = now.isoformat()

            supabase.table("email_funnel_enrollments").update(updates).eq("id", enrollment["id"]).execute()

            # Log activity
            if contact_id:
                supabase.table("lead_activity").insert({
                    "lead_id": contact_id,
                    "activity_type": "email_sent",
                    "description": f"Drip email sent: {subject} ({campaign})"
                }).execute()
        else:
            errors += 1
            if "suppressed" in (error or ""):
                skipped += 1

    # Log summary
    supabase.table("activity_log").insert({
        "type": "drip",
        "message": f"Drip processor ran: {sent} sent, {skipped} skipped, {errors} errors",
        "meta": {"sent": sent, "skipped": skipped, "errors": errors}
    }).execute()

    return {"success": True, "sent": sent, "skipped": skipped, "errors": errors}


@app.get("/api/drip/status")
def drip_status():
    """Get overview of drip queue status."""
    active = supabase.table("email_funnel_enrollments").select("id", count="exact").eq("status", "active").execute()
    completed = supabase.table("email_funnel_enrollments").select("id", count="exact").eq("status", "completed").execute()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    sent_today = supabase.table("email_send_log").select("id", count="exact").gte("created_at", today).eq("status", "sent").execute()
    limits = supabase.table("email_daily_limits").select("*").eq("send_date", today).execute()

    return {
        "active_enrollments": active.count or 0,
        "completed_enrollments": completed.count or 0,
        "sent_today": sent_today.count or 0,
        "daily_limits": limits.data
    }


# ── EMAIL MANAGEMENT ──

@app.get("/api/email/unsubscribe")
def unsubscribe(email: str):
    """One-click unsubscribe. Returns a simple confirmation page."""
    email = email.lower().strip()
    if email:
        try:
            supabase.table("email_suppressions").insert({
                "email": email, "reason": "unsubscribe", "source": "one-click"
            }).execute()
        except Exception:
            pass  # Already suppressed
        # Update contact: add tag, remove from pipelines, log activity
        try:
            contact = supabase.table("leads").select("id, tags").eq("email", email).execute()
            if contact.data:
                cid = contact.data[0]["id"]
                existing_tags = contact.data[0].get("tags") or []
                if "unsubscribed" not in existing_tags:
                    existing_tags.append("unsubscribed")
                supabase.table("leads").update({
                    "tags": existing_tags,
                    "status": "unsubscribed"
                }).eq("id", cid).execute()

                # Close all open opportunities
                supabase.table("opportunities").update({
                    "status": "lost"
                }).eq("contact_id", cid).eq("status", "open").execute()

                # Cancel all active drip enrollments
                supabase.table("email_funnel_enrollments").update({
                    "status": "cancelled"
                }).eq("lead_id", cid).eq("status", "active").execute()

                supabase.table("lead_activity").insert({
                    "lead_id": cid,
                    "activity_type": "unsubscribed",
                    "description": "Unsubscribed from emails. Removed from pipelines and drip sequences."
                }).execute()
        except Exception:
            pass
    return HTMLResponse(content="""
    <!DOCTYPE html><html><head><meta charset="UTF-8"><title>Unsubscribed</title>
    <style>body{background:#0a0a0f;color:#e8e8f0;font-family:'DM Sans',sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}
    .card{text-align:center;max-width:400px;padding:40px;}.h{font-size:28px;font-weight:700;margin-bottom:12px;}.s{color:#8888aa;font-size:14px;line-height:1.6;}</style>
    </head><body><div class="card"><div class="h">You've been unsubscribed</div><div class="s">You won't receive any more emails from TPL Collective. If this was a mistake, reply to any previous email and we'll re-add you.</div></div></body></html>
    """)


@app.get("/api/email/suppressions")
def get_suppressions():
    result = supabase.table("email_suppressions").select("*").order("created_at", desc=True).execute()
    return result.data


@app.delete("/api/email/suppressions/{email}")
def remove_suppression(email: str):
    supabase.table("email_suppressions").delete().eq("email", email.lower()).execute()
    return {"success": True}


@app.get("/api/email/send-limits")
def get_send_limits():
    today = datetime.utcnow().strftime("%Y-%m-%d")
    result = supabase.table("email_daily_limits").select("*").eq("send_date", today).execute()
    return result.data


@app.put("/api/email/send-limits/{domain}")
async def update_send_limit(domain: str, request: Request):
    data = await request.json()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    existing = supabase.table("email_daily_limits").select("id").eq("send_date", today).eq("domain", domain).execute()
    if existing.data:
        supabase.table("email_daily_limits").update({"limit_count": data.get("limit", 50)}).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("email_daily_limits").insert({"send_date": today, "domain": domain, "sent_count": 0, "limit_count": data.get("limit", 50)}).execute()
    return {"success": True}


@app.get("/api/email/log")
def get_email_log(limit: int = 50, campaign: Optional[str] = None):
    query = supabase.table("email_send_log").select("*").order("created_at", desc=True).limit(limit)
    if campaign:
        query = query.eq("campaign", campaign)
    return query.execute().data


# ── SHORT URL REDIRECTOR ──

@app.get("/go/{code}")
def short_redirect(code: str):
    """Short URL redirect. Format: /go/{page}-{cid} e.g., /go/calc-123, /go/vs-kw-123, /go/book-123"""
    parts = code.rsplit("-", 1)
    cid = parts[1] if len(parts) == 2 and parts[1].isdigit() else ""
    slug = parts[0] if len(parts) == 2 else code

    url_map = {
        "calc": "/commission-calculator",
        "vs-kw": "/vs/keller-williams",
        "vs-exp": "/vs/exp-realty",
        "vs-cb": "/vs/coldwell-banker",
        "vs-c21": "/vs/century-21",
        "vs-remax": "/vs/remax",
        "vs-real": "/vs/real-brokerage",
        "vs-switch": "/vs/exp-switch",
        "book": "https://calendly.com/discovertpl",
        "fees": "/fee-plans",
        "join": "/join",
        "why": "/why-tpl",
        "lpt": "/lpt-explained",
    }

    base_url = url_map.get(slug, "/commission-calculator")

    # Build redirect URL with tracking params
    if base_url.startswith("http"):
        # External URL (Calendly)
        sep = "&" if "?" in base_url else "?"
        target = f"{base_url}{sep}utm_source=email&utm_campaign=drip"
        if cid:
            target += f"&cid={cid}"
    else:
        # Internal URL
        target = f"https://tplcollective.ai{base_url}?cid={cid}&ref=email" if cid else f"https://tplcollective.ai{base_url}"
        # Add brokerage hint for calculator
        if slug == "calc" and cid:
            target += "&b=kw"

    # Log click if we have a cid
    if cid:
        try:
            supabase.table("lead_activity").insert({
                "lead_id": int(cid),
                "activity_type": "email_click",
                "description": f"Clicked link: {slug}",
                "metadata": {"url": base_url, "code": code}
            }).execute()
        except Exception:
            pass

    return RedirectResponse(url=target, status_code=302)


# ── EMAIL ENGAGEMENT TRACKING ──

@app.get("/api/email/open/{send_id}")
def track_email_open(send_id: str):
    """1x1 tracking pixel for email opens. Returns transparent GIF."""
    try:
        # Look up by tracking_id first (new UUID-based), then fall back to resend_id (legacy)
        log = supabase.table("email_send_log").select("id, contact_id, subject, status").eq("tracking_id", send_id).execute()
        if not log.data:
            log = supabase.table("email_send_log").select("id, contact_id, subject, status").eq("resend_id", send_id).execute()
        if log.data:
            entry = log.data[0]
            # Only update status if not already a higher-value status
            if entry.get("status") in ("sent", "delivered"):
                supabase.table("email_send_log").update({"status": "opened"}).eq("id", entry["id"]).execute()
            if entry.get("contact_id"):
                # Dedup check - don't log multiple opens within 1 hour
                from datetime import timedelta
                recent = supabase.table("lead_activity").select("id").eq("lead_id", entry["contact_id"]).eq("activity_type", "email_opened").gte("created_at", (datetime.utcnow() - timedelta(hours=1)).isoformat()).execute()
                if not recent.data:
                    supabase.table("lead_activity").insert({
                        "lead_id": entry["contact_id"],
                        "activity_type": "email_opened",
                        "description": f"Opened email: {entry.get('subject', 'Unknown')}",
                    }).execute()
    except Exception:
        pass
    # Return 1x1 transparent GIF
    import base64
    from starlette.responses import Response
    gif = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    return Response(content=gif, media_type="image/gif", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.post("/api/webhooks/resend")
async def resend_webhook(request: Request):
    """Handle Resend webhooks for bounces, complaints, deliveries."""
    data = await request.json()
    event_type = data.get("type", "")
    email_data = data.get("data", {})
    to_email = ""
    if email_data.get("to"):
        to_email = email_data["to"][0] if isinstance(email_data["to"], list) else email_data["to"]
    email_id = email_data.get("email_id", "")

    # Find contact by email
    contact = None
    if to_email:
        result = supabase.table("leads").select("id, name").eq("email", to_email).execute()
        contact = result.data[0] if result.data else None

    if event_type == "email.delivered":
        if email_id:
            supabase.table("email_send_log").update({"status": "delivered"}).eq("resend_id", email_id).execute()
        if contact:
            from datetime import timedelta
            recent = supabase.table("lead_activity").select("id").eq("lead_id", contact["id"]).eq("activity_type", "email_delivered").gte("created_at", (datetime.utcnow() - timedelta(minutes=5)).isoformat()).execute()
            if not recent.data:
                supabase.table("lead_activity").insert({
                    "lead_id": contact["id"],
                    "activity_type": "email_delivered",
                    "description": f"Email delivered to {to_email}"
                }).execute()

    elif event_type == "email.opened":
        if email_id:
            supabase.table("email_send_log").update({"status": "opened"}).eq("resend_id", email_id).execute()
        if contact:
            # Dedup
            from datetime import timedelta
            recent = supabase.table("lead_activity").select("id").eq("lead_id", contact["id"]).eq("activity_type", "email_opened").gte("created_at", (datetime.utcnow() - timedelta(hours=1)).isoformat()).execute()
            if not recent.data:
                supabase.table("lead_activity").insert({
                    "lead_id": contact["id"],
                    "activity_type": "email_opened",
                    "description": f"Opened email"
                }).execute()

    elif event_type == "email.clicked":
        if contact:
            supabase.table("lead_activity").insert({
                "lead_id": contact["id"],
                "activity_type": "email_clicked",
                "description": f"Clicked link in email"
            }).execute()

    elif event_type == "email.bounced":
        if email_id:
            supabase.table("email_send_log").update({"status": "bounced"}).eq("resend_id", email_id).execute()
        if to_email:
            try:
                supabase.table("email_suppressions").insert({"email": to_email.lower(), "reason": "hard_bounce", "source": "resend_webhook"}).execute()
            except Exception:
                pass
        if contact:
            supabase.table("lead_activity").insert({
                "lead_id": contact["id"],
                "activity_type": "email_bounced",
                "description": f"Email bounced: {to_email}"
            }).execute()

    elif event_type == "email.complained":
        if to_email:
            try:
                supabase.table("email_suppressions").insert({"email": to_email.lower(), "reason": "complaint", "source": "resend_webhook"}).execute()
            except Exception:
                pass
        if contact:
            supabase.table("lead_activity").insert({
                "lead_id": contact["id"],
                "activity_type": "email_complained",
                "description": f"Marked as spam: {to_email}"
            }).execute()

    return {"success": True, "event": event_type}


# ── VISITOR TRACKING ──

@app.post("/api/tracking/pageview")
async def track_pageview(request: Request):
    """Track page views from known contacts via cid parameter."""
    data = await request.json()
    cid = data.get("cid")
    page = data.get("page", "")
    referrer = data.get("referrer", "")
    utm_source = data.get("utm_source", "")
    utm_campaign = data.get("utm_campaign", "")

    if not cid:
        return {"success": True, "tracked": False}

    try:
        cid = int(cid)
        # Verify contact exists
        contact = supabase.table("leads").select("id, name").eq("id", cid).execute()
        if not contact.data:
            return {"success": True, "tracked": False}

        # Dedup: don't log same page view within 5 minutes
        from datetime import timedelta
        recent = supabase.table("lead_activity").select("id").eq("lead_id", cid).eq("activity_type", "page_view").eq("description", f"Visited: {page}").gte("created_at", (datetime.utcnow() - timedelta(minutes=5)).isoformat()).execute()
        if not recent.data:
            supabase.table("lead_activity").insert({
                "lead_id": cid,
                "activity_type": "page_view",
                "description": f"Visited: {page}",
                "metadata": {"page": page, "referrer": referrer, "utm_source": utm_source, "utm_campaign": utm_campaign}
            }).execute()

        # Update last_contacted_at to show engagement
        supabase.table("leads").update({
            "last_contacted_at": datetime.utcnow().isoformat()
        }).eq("id", cid).execute()

        return {"success": True, "tracked": True}
    except Exception:
        return {"success": True, "tracked": False}


@app.post("/api/tracking/calculator")
async def track_calculator(request: Request):
    """Track calculator usage and results for a known contact."""
    data = await request.json()
    cid = data.get("cid")

    if not cid:
        return {"success": True, "tracked": False}

    try:
        cid = int(cid)
        contact = supabase.table("leads").select("id, name, lead_score").eq("id", cid).execute()
        if not contact.data:
            return {"success": True, "tracked": False}

        c = contact.data[0]
        updates = {"last_contacted_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()}

        # Save calculator inputs to contact record
        if data.get("deals_per_year"):
            updates["deals_per_year"] = str(data["deals_per_year"])
        if data.get("avg_price"):
            updates["avg_price"] = str(data["avg_price"])
        if data.get("brokerage"):
            updates["current_brokerage"] = data["brokerage"]

        # Bump score — they engaged with the calculator
        old_score = c.get("lead_score") or 20
        new_score = min(100, max(old_score, 50))  # At least 50 if they used calculator
        updates["lead_score"] = new_score
        updates["lead_temperature"] = "hot" if new_score >= 70 else "warming"

        supabase.table("leads").update(updates).eq("id", cid).execute()

        # Log activity with calculator results (dedup: 1 per minute)
        savings = data.get("savings", "")
        from datetime import timedelta
        recent_calc = supabase.table("lead_activity").select("id").eq("lead_id", cid).eq("activity_type", "calculator_used").gte("created_at", (datetime.utcnow() - timedelta(minutes=1)).isoformat()).execute()
        if not recent_calc.data:
            supabase.table("lead_activity").insert({
                "lead_id": cid,
                "activity_type": "calculator_used",
                "description": f"Used commission calculator. {data.get('deals_per_year', '')} deals, ${data.get('avg_price', '')} avg. Savings: ${savings}",
                "metadata": data
            }).execute()

        # Move opportunity to "Engaged" if they were in nurture
        opps = supabase.table("opportunities").select("id, stage").eq("contact_id", cid).eq("status", "open").execute()
        if opps.data:
            opp = opps.data[0]
            if opp["stage"] in ("nurture_not_ready", "new_fb_lead"):
                supabase.table("opportunities").update({
                    "stage": "engaged",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", opp["id"]).execute()
                supabase.table("lead_activity").insert({
                    "lead_id": cid,
                    "activity_type": "stage_change",
                    "description": f"Stage: {opp['stage']} → engaged (calculator engagement)",
                    "metadata": {"from": opp["stage"], "to": "engaged"}
                }).execute()
                supabase.table("activity_log").insert({
                    "type": "opportunity",
                    "message": f"Revival lead engaged: {c['name']} used calculator",
                    "meta": {"contact_id": cid}
                }).execute()

        return {"success": True, "tracked": True, "score": new_score}
    except Exception as e:
        return {"success": True, "tracked": False, "error": str(e)}


@app.get("/api/tracking/identify")
def tracking_identify(cid: int):
    """Return minimal contact info for tracking script to use (no sensitive data)."""
    try:
        contact = supabase.table("leads").select("id, first_name").eq("id", cid).execute()
        if contact.data:
            return {"found": True, "cid": cid, "name": contact.data[0].get("first_name", "")}
    except Exception:
        pass
    return {"found": False}


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


# ── META LEADS WEBHOOK ──

@app.get("/api/webhooks/meta-leads")
async def meta_leads_verify(request: Request):
    """Handle Meta webhook verification challenge (required for setup)."""
    params = request.query_params
    mode = params.get("hub.mode", "")
    token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")

    settings = load_settings()
    verify_token = settings.get("meta_webhook_verify_token", "tpl-meta-leads-2026")

    if mode == "subscribe" and token == verify_token:
        return PlainTextResponse(content=challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/api/webhooks/meta-leads")
async def meta_leads_webhook(request: Request):
    """Handle Meta Lead Ads webhook - fetches lead data from Graph API and creates lead in Supabase."""
    body = await request.body()

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    settings = load_settings()
    page_access_token = settings.get("meta_page_access_token", "")

    leads_created = []

    # Meta sends: {"entry": [{"changes": [{"field": "leadgen", "value": {"leadgen_id": "...", "page_id": "..."}}]}]}
    entries = data.get("entry", [])
    if not entries:
        # Also support direct POST format: {"name": "...", "email": "...", "phone": "..."}
        # This allows Zapier/Make or manual integrations
        if data.get("email"):
            lead_result = await _create_meta_lead(
                name=data.get("full_name") or data.get("name", "Unknown"),
                email=data["email"],
                phone=data.get("phone_number") or data.get("phone", ""),
                form_name=data.get("form_name", "Direct Post"),
                campaign_name=data.get("campaign_name", ""),
                ad_name=data.get("ad_name", ""),
                platform=data.get("platform", "meta"),
                settings=settings
            )
            return {"success": True, "action": "lead_created", "leads": [lead_result]}
        return {"success": True, "action": "no_entries"}

    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            if change.get("field") != "leadgen":
                continue

            value = change.get("value", {})
            leadgen_id = value.get("leadgen_id", "")
            form_id = value.get("form_id", "")

            if not leadgen_id or not page_access_token:
                # If no access token, log what we got and skip Graph API call
                supabase.table("activity_log").insert({
                    "type": "meta_lead",
                    "message": f"Meta lead received but no page access token configured. Leadgen ID: {leadgen_id}",
                    "meta": {"leadgen_id": leadgen_id, "form_id": form_id}
                }).execute()
                continue

            # Fetch lead data from Meta Graph API
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"https://graph.facebook.com/v21.0/{leadgen_id}",
                        params={"access_token": page_access_token}
                    )
                    if resp.status_code != 200:
                        supabase.table("activity_log").insert({
                            "type": "meta_lead",
                            "message": f"Failed to fetch lead {leadgen_id} from Graph API: {resp.status_code}",
                            "meta": {"leadgen_id": leadgen_id, "response": resp.text[:500]}
                        }).execute()
                        continue

                    lead_data = resp.json()
            except Exception as e:
                supabase.table("activity_log").insert({
                    "type": "meta_lead",
                    "message": f"Error fetching lead {leadgen_id}: {str(e)}",
                    "meta": {"leadgen_id": leadgen_id}
                }).execute()
                continue

            # Parse field_data from Meta response
            # Format: {"field_data": [{"name": "email", "values": ["user@example.com"]}, ...]}
            fields = {}
            for field in lead_data.get("field_data", []):
                field_name = field.get("name", "").lower()
                field_values = field.get("values", [])
                if field_values:
                    fields[field_name] = field_values[0]

            email = fields.get("email", "")
            if not email:
                continue

            name = fields.get("full_name", "") or fields.get("name", "Unknown")
            phone = fields.get("phone_number", "") or fields.get("phone", "")

            # Fetch form name for better source tracking
            form_name = lead_data.get("form_name", "Meta Lead Form")

            lead_result = await _create_meta_lead(
                name=name,
                email=email,
                phone=phone,
                form_name=form_name,
                campaign_name="",
                ad_name="",
                platform=lead_data.get("platform", "fb"),
                settings=settings
            )
            leads_created.append(lead_result)

    return {"success": True, "action": "processed", "leads_created": len(leads_created), "leads": leads_created}


async def _create_meta_lead(name: str, email: str, phone: str, form_name: str,
                             campaign_name: str, ad_name: str, platform: str, settings: dict) -> dict:
    """Create or update a lead from Meta Lead Ads."""
    # Parse first/last name
    name_parts = name.strip().split(" ", 1)
    first_name = name_parts[0] if name_parts else "Unknown"
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    source = "Meta Ads"
    source_page = form_name
    if ad_name:
        source_page = f"{ad_name} - {form_name}"

    # Check if lead already exists
    existing = supabase.table("leads").select("id, name, status").eq("email", email).execute()

    if existing.data:
        lead = existing.data[0]
        lead_id = lead["id"]
        updates = {
            "updated_at": datetime.utcnow().isoformat(),
            "lead_temperature": "warm"
        }
        if phone:
            updates["phone"] = phone
        supabase.table("leads").update(updates).eq("id", lead_id).execute()

        supabase.table("activity_log").insert({
            "type": "meta_lead",
            "message": f"Existing lead submitted Meta form: {name} ({email}) - {form_name}",
            "meta": {"lead_id": lead_id, "form": form_name, "platform": platform}
        }).execute()

        # Log lead activity
        try:
            supabase.table("lead_activity").insert({
                "lead_id": lead_id,
                "type": "form_submission",
                "description": f"Submitted Meta lead form: {form_name}",
                "meta": {"form": form_name, "campaign": campaign_name, "ad": ad_name, "platform": platform}
            }).execute()
        except Exception:
            pass

        return {"lead_id": lead_id, "action": "updated", "name": name}
    else:
        # Detect brokerage from form/campaign name for routing
        form_campaign_str = (form_name + " " + (campaign_name or "") + " " + (ad_name or "")).upper()
        if "KW" in form_campaign_str or "KELLER" in form_campaign_str:
            current_brokerage = "Keller Williams"
            funnel_id = 20  # Commission Comparison - KW
        elif "EXP" in form_campaign_str:
            current_brokerage = "eXp Realty"
            funnel_id = 16  # eXp Reality Check
        elif "REMAX" in form_campaign_str or "RE/MAX" in form_campaign_str:
            current_brokerage = "RE/MAX"
            funnel_id = 17  # RE/MAX Wake Up
        elif "CENTURY" in form_campaign_str or "C21" in form_campaign_str:
            current_brokerage = "Century 21"
            funnel_id = 19  # The Numbers Don't Lie (general - until C21 funnel built)
        elif "COLDWELL" in form_campaign_str:
            current_brokerage = "Coldwell Banker"
            funnel_id = 18  # Legacy Brokerage Escape
        else:
            current_brokerage = ""
            funnel_id = 19  # The Numbers Don't Lie (general)

        # Create new lead with pipeline-ready stage
        result = supabase.table("leads").insert({
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone or "",
            "source": source,
            "source_page": source_page,
            "stage": "new_fb_lead",
            "lead_temperature": "warm",
            "status": "new",
            "current_brokerage": current_brokerage,
            "notes": f"Meta Lead Ad submission via {form_name}. Platform: {platform}."
        }).execute()

        lead_id = result.data[0]["id"]

        # Create opportunity in LPT Recruiting pipeline
        try:
            supabase.table("opportunities").insert({
                "contact_id": lead_id,
                "pipeline_id": 1,
                "stage": "new_fb_lead",
                "source": f"Meta Ads - {form_name}",
                "status": "open",
                "notes": f"Auto-created from Meta lead form. Ad: {ad_name or 'N/A'}. Campaign: {campaign_name or 'N/A'}."
            }).execute()
        except Exception:
            pass

        # Auto-enroll in email funnel
        try:
            supabase.table("email_funnel_enrollments").insert({
                "lead_id": lead_id,
                "funnel_id": funnel_id,
                "current_step": 1,
                "status": "active",
                "enrolled_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception:
            pass

        supabase.table("activity_log").insert({
            "type": "meta_lead",
            "message": f"New lead via Meta Ads: {name} ({email}) - {form_name}",
            "meta": {"lead_id": lead_id, "form": form_name, "platform": platform, "funnel_id": funnel_id, "brokerage": current_brokerage}
        }).execute()

        # Log lead activity
        try:
            supabase.table("lead_activity").insert({
                "lead_id": lead_id,
                "type": "form_submission",
                "description": f"Submitted Meta lead form: {form_name}",
                "meta": {"form": form_name, "campaign": campaign_name, "ad": ad_name, "platform": platform}
            }).execute()
        except Exception:
            pass

        # Send notification email
        try:
            notif = settings.get("notifications", {})
            if notif.get("newLead", False):
                to_email = notif.get("email", "")
                smtp = settings.get("smtp", {})
                if to_email and smtp.get("pass"):
                    subject = f"New Meta Lead: {name} - TPL Mission Control"
                    html = _build_meta_lead_email(name, email, phone, form_name, platform)
                    send_email(smtp, to_email, subject, html)
        except Exception:
            pass

        return {"lead_id": lead_id, "action": "created", "name": name, "funnel_id": funnel_id, "brokerage": current_brokerage}


def _build_meta_lead_email(name: str, email: str, phone: str, form_name: str, platform: str) -> str:
    """Build HTML email for Meta lead notification."""
    timestamp = datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
    platform_label = "Facebook" if platform == "fb" else "Instagram" if platform == "ig" else platform.title()

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"/></head>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:'DM Sans',Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:32px 16px;">
    <div style="margin-bottom:28px;">
      <div style="font-size:22px;font-weight:700;color:#e8e8f0;letter-spacing:2px;margin-bottom:4px;">TPL<span style="color:#6c63ff;">.</span></div>
      <div style="font-size:11px;color:#666;letter-spacing:3px;text-transform:uppercase;">Mission Control - Meta Lead</div>
    </div>
    <div style="background:#12121a;border:1px solid #2a2a3d;border-radius:12px;overflow:hidden;">
      <div style="background:#6c63ff;padding:4px 0;"></div>
      <div style="padding:28px;">
        <div style="font-size:11px;color:#6c63ff;letter-spacing:2px;text-transform:uppercase;margin-bottom:10px;">New Lead from {platform_label}</div>
        <div style="font-size:24px;font-weight:700;color:#e8e8f0;margin-bottom:4px;">{name}</div>
        <div style="font-size:13px;color:#888;margin-bottom:24px;">{timestamp}</div>
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px 0;color:#888;font-size:13px;width:120px;">Email</td><td style="padding:8px 0;"><a href="mailto:{email}" style="color:#6c63ff;font-size:13px;text-decoration:none;">{email}</a></td></tr>
          <tr><td style="padding:8px 0;color:#888;font-size:13px;">Phone</td><td style="padding:8px 0;color:#e8e8f0;font-size:13px;">{phone or 'Not provided'}</td></tr>
          <tr><td style="padding:8px 0;color:#888;font-size:13px;">Form</td><td style="padding:8px 0;color:#e8e8f0;font-size:13px;">{form_name}</td></tr>
          <tr><td style="padding:8px 0;color:#888;font-size:13px;">Platform</td><td style="padding:8px 0;color:#e8e8f0;font-size:13px;">{platform_label}</td></tr>
        </table>
        <div style="margin-top:24px;padding-top:20px;border-top:1px solid #2a2a3d;">
          <a href="https://mission.tplcollective.ai" style="display:inline-block;background:#6c63ff;color:#fff;text-decoration:none;padding:10px 22px;border-radius:8px;font-size:13px;font-weight:600;">View in Mission Control &rarr;</a>
        </div>
      </div>
    </div>
    <div style="margin-top:20px;font-size:11px;color:#444;text-align:center;">TPL Collective - mission.tplcollective.ai</div>
  </div>
</body>
</html>
"""


# ── ROBOTS.TXT (block all crawlers from Mission Control) ──

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    return "User-agent: *\nDisallow: /\n"


# ── SERVE DASHBOARD ──
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open("/app/static/index.html") as f:
        return f.read()
