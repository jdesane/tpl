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
