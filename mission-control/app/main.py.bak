from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import os
import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

app = FastAPI(title="TPL Mission Control")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tplcollective.ai", "https://www.tplcollective.ai", "http://localhost", "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "/data/mission.db"
SETTINGS_PATH = "/data/settings.json"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            brokerage TEXT,
            deals_per_year TEXT,
            avg_price TEXT,
            status TEXT DEFAULT 'new',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            message TEXT,
            meta TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


init_db()


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
    """Send email via SMTP. Returns (success, error_message)."""
    try:
        host = smtp_config.get("host", "")
        port = int(smtp_config.get("port", 465))
        user = smtp_config.get("user", "")
        password = smtp_config.get("pass", "")
        from_addr = smtp_config.get("from", user)

        if not all([host, user, password]):
            return False, "SMTP not fully configured"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context) as server:
                server.login(user, password)
                server.sendmail(from_addr, to_email, msg.as_string())
        else:
            with smtplib.SMTP(host, port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(user, password)
                server.sendmail(from_addr, to_email, msg.as_string())

        return True, ""
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

        conn = get_db()
        if success:
            conn.execute(
                "INSERT INTO activity_log (type, message, meta) VALUES (?,?,?)",
                ("smtp", f"Email notification sent to {to_email} for lead: {lead_data.get('name')}", "{}")
            )
        else:
            conn.execute(
                "INSERT INTO activity_log (type, message, meta) VALUES (?,?,?)",
                ("error", f"Email notification failed: {error}", "{}")
            )
        conn.commit()
        conn.close()
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
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO leads (name, email, phone, brokerage, deals_per_year, avg_price) VALUES (?,?,?,?,?,?)",
            (lead.name, lead.email, lead.phone, lead.brokerage, lead.deals_per_year, lead.avg_price)
        )
        lead_id = cur.lastrowid
        conn.execute(
            "INSERT INTO activity_log (type, message, meta) VALUES (?,?,?)",
            ("lead", f"New lead: {lead.name} from {lead.brokerage or 'tplcollective.ai'}", json.dumps({"lead_id": lead_id}))
        )
        conn.commit()

        # Fire notification (non-blocking, never fails the request)
        maybe_notify_new_lead(lead.dict())

        return {"success": True, "id": lead_id, "message": "Lead captured"}
    finally:
        conn.close()


@app.get("/api/leads")
def get_leads(status: Optional[str] = None):
    conn = get_db()
    try:
        if status:
            rows = conn.execute("SELECT * FROM leads WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM leads ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.patch("/api/leads/{lead_id}")
def update_lead(lead_id: int, update: LeadUpdate):
    conn = get_db()
    try:
        lead = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        if update.status:
            conn.execute("UPDATE leads SET status=?, updated_at=datetime('now') WHERE id=?", (update.status, lead_id))
        if update.notes is not None:
            conn.execute("UPDATE leads SET notes=?, updated_at=datetime('now') WHERE id=?", (update.notes, lead_id))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


@app.delete("/api/leads/{lead_id}")
def delete_lead(lead_id: int):
    conn = get_db()
    try:
        conn.execute("DELETE FROM leads WHERE id=?", (lead_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


@app.get("/api/stats")
def get_stats():
    conn = get_db()
    try:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        new = conn.execute("SELECT COUNT(*) FROM leads WHERE status='new'").fetchone()[0]
        contacted = conn.execute("SELECT COUNT(*) FROM leads WHERE status='contacted'").fetchone()[0]
        qualified = conn.execute("SELECT COUNT(*) FROM leads WHERE status='qualified'").fetchone()[0]
        joined = conn.execute("SELECT COUNT(*) FROM leads WHERE status='joined'").fetchone()[0]
        today = conn.execute("SELECT COUNT(*) FROM leads WHERE DATE(created_at)=DATE('now')").fetchone()[0]
        return {
            "total": total, "new": new, "contacted": contacted,
            "qualified": qualified, "joined": joined, "today": today
        }
    finally:
        conn.close()


@app.get("/api/activity")
def get_activity(limit: int = 40):
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


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
        # Merge — don't overwrite password if not provided
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

    if not smtp.get("host"):
        return {"success": False, "error": "SMTP not configured. Add your SMTP settings first."}

    html = build_lead_email({
        "name": "Test Agent",
        "email": "test@tplcollective.ai",
        "phone": "(555) 123-4567",
        "brokerage": "Test Brokerage",
        "deals_per_year": "24",
        "avg_price": "$425K"
    })

    success, error = send_email(smtp, req.email, "✦ TPL Mission Control — Test Notification", html)

    conn = get_db()
    if success:
        conn.execute(
            "INSERT INTO activity_log (type, message, meta) VALUES (?,?,?)",
            ("smtp", f"Test notification sent to {req.email}", "{}")
        )
    conn.commit()
    conn.close()

    if success:
        return {"success": True}
    return {"success": False, "error": error}


# ── SERVE DASHBOARD ──
app.mount("/static", StaticFiles(directory="/app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with open("/app/static/index.html") as f:
        return f.read()
