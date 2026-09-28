"""
1-on-1 requests: pre-qualify first, then Joe offers times. Replaces Calendly.

Why: Calendly let anyone put a meeting on Joe's calendar with no review, and a
weekend booking surfaced only when the "starting now" email arrived. Here nothing
reaches the calendar until Joe has read the answers and offered times, and every
stage leaves a trail (task, alert, nudge) so a request cannot sit unnoticed.

Flow:
  1. agent fills tplcollective.ai/book            -> status 'new'
     lead updated, Joe alerted, "Send times to X" task due today
  2. Joe clicks Send times in MC (2-4 slots)       -> status 'times_sent'
     agent gets one button per slot -> tplcollective.ai/pick?r=<token>
  3. agent picks a slot                            -> status 'confirmed'
     both get a calendar file (.ics), call task on the call date,
     lead moves to discovery_call
     ("none of these work" goes back to 'new' with their note, Joe alerted)
  4. /process (cron, every 15 min): nudge Joe on requests waiting 12h+, on
     offers unanswered 48h+ or whose times all passed; prep email to Joe and a
     reminder to the agent before the call.

Every email goes through main.send_email(). Nothing here asks about sponsorship.
Routers:
  router         /api/one-on-one/*          platform-only admin
  public_router  /api/public/one-on-one/*   form + pick-a-time page
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Any, Callable
from datetime import datetime, timedelta, timezone
import base64
import re
import uuid

import recruit_newsletter as rn

router = APIRouter(prefix="/api/one-on-one", tags=["one-on-one"])
public_router = APIRouter(prefix="/api/public/one-on-one", tags=["one-on-one-public"])

_supabase: Any = None
WS = rn.WS
SITE = "https://tplcollective.ai"

NUDGE_NEW_AFTER = timedelta(hours=12)
NUDGE_OFFER_AFTER = timedelta(hours=48)
NUDGE_EVERY = timedelta(hours=24)
PREP_BEFORE = timedelta(minutes=60)
AGENT_REMINDER_BEFORE = timedelta(minutes=90)
STATUSES = ("new", "times_sent", "confirmed", "closed")


def setup(db_callable, supabase_client):
    global _supabase
    _supabase = supabase_client


def _t(name: str):
    return _supabase.table(name)


_now, _iso, _parse_ts, _esc = rn._now, rn._iso, rn._parse_ts, rn._esc


def _settings() -> dict:
    s = rn._settings()
    s.setdefault("zoom_link", "")
    s.setdefault("call_minutes", 30)
    return s


def _how(req: dict) -> str:
    """One line on how the call happens, for the agent."""
    a = req.get("answers") or {}
    if req.get("meeting_type") == "zoom":
        link = _settings().get("zoom_link") or ""
        return f"We'll meet on Zoom: {link}" if link else "We'll meet on Zoom; I'll send the link."
    return f"I'll call you at {a['phone']}." if a.get("phone") else "I'll give you a call."


def _fmt_et(dt: datetime) -> str:
    local = dt.astimezone(rn._ET)
    return local.strftime("%a, %b ") + str(local.day) + " at " + local.strftime("%I:%M %p").lstrip("0") + " ET"


# ════════════════════════════════════════════════════════════
# Models
# ════════════════════════════════════════════════════════════

class RequestIn(BaseModel):
    t: Optional[str] = None
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    current_brokerage: str = ""
    agent_type: str = ""
    deals: str = ""
    avg_price: str = ""
    topics: List[str] = []
    timeline: str = ""
    notes: str = ""
    website: str = ""   # honeypot; real people never fill it


class SendTimesIn(BaseModel):
    slots: List[str]            # ISO datetimes
    minutes: Optional[int] = None
    note: Optional[str] = ""
    meeting: Optional[str] = "phone"   # phone | zoom


class ConfirmIn(BaseModel):
    start: str
    minutes: Optional[int] = None
    meeting: Optional[str] = None      # keeps the request's current choice when omitted


class CloseIn(BaseModel):
    reason: Optional[str] = ""


class PickIn(BaseModel):
    r: str
    s: Optional[int] = None
    none: Optional[bool] = False
    note: Optional[str] = ""


# ════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════

def _get(req_id: int) -> dict:
    r = _t("booking_requests").select("*").eq("id", req_id).eq("workspace_id", WS).limit(1).execute().data
    if not r:
        raise HTTPException(404, "Request not found")
    return r[0]


def _by_token(token: str) -> Optional[dict]:
    if not token or not rn._UUID_RE.match(token):
        return None
    r = _t("booking_requests").select("*").eq("token", token.lower()).limit(1).execute().data
    return r[0] if r else None


def _lead(lead_id) -> dict:
    if not lead_id:
        return {}
    return (_t("leads").select("*").eq("id", lead_id).limit(1).execute().data or [{}])[0]


def _who(req: dict) -> str:
    a = req.get("answers") or {}
    return f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() or a.get("email") or "An agent"


def _answer_rows(req: dict) -> List[tuple]:
    a = req.get("answers") or {}
    return [
        ("Name", _who(req)), ("Email", a.get("email")), ("Phone", a.get("phone")),
        ("Brokerage", a.get("current_brokerage")), ("Describes themselves as", a.get("agent_type")),
        ("Deals last 12 months", a.get("deals")), ("Avg sale price", a.get("avg_price")),
        ("Wants to talk about", ", ".join(a.get("topics") or [])), ("Timeline", a.get("timeline")),
        ("Notes", a.get("notes")),
    ]


def _mc_link(req: dict) -> str:
    return f"https://mission.tplcollective.ai/#one-on-one/{req['id']}"


def _task(req: dict, title: str, due: datetime, due_time: str = "", priority: str = "high"):
    try:
        _t("tasks").insert({
            "workspace_id": WS, "task_type": "one_on_one", "title": title[:200],
            "description": f"1-on-1 request #{req['id']}. {_mc_link(req)}",
            "lead_id": req.get("lead_id"), "priority": priority, "status": "pending",
            "due_date": due.astimezone(rn._ET).date().isoformat(), "due_time": due_time or None,
            "created_by": "one-on-one",
        }).execute()
    except Exception as e:
        print(f"[1on1] task insert failed: {e}")


def _close_tasks(req: dict, prefix: str):
    """Mark this request's open tasks whose title starts with `prefix` done."""
    try:
        rows = (_t("tasks").select("id, title, description").eq("task_type", "one_on_one")
                .eq("status", "pending").eq("lead_id", req.get("lead_id")).execute().data or [])
        ids = [r["id"] for r in rows if (r.get("title") or "").startswith(prefix) and f"#{req['id']}." in (r.get("description") or "")]
        if ids:
            _t("tasks").update({"status": "done", "completed_at": _iso(_now())}).in_("id", ids).execute()
    except Exception as e:
        print(f"[1on1] task close failed: {e}")


def _ics(req: dict, start: datetime, minutes: int, for_joe: bool) -> dict:
    s = _settings()
    a = req.get("answers") or {}
    end = start + timedelta(minutes=minutes)
    fmt = "%Y%m%dT%H%M%SZ"
    who = _who(req)
    summary = f"1-on-1: {who} + Joe DeSane" if for_joe else "Call with Joe DeSane (TPL Collective)"
    zoom = req.get("meeting_type") == "zoom"
    location = (s.get("zoom_link") or "Zoom") if zoom else ("Phone: " + (a.get("phone") or ""))
    desc = _how(req)
    if for_joe:
        how = "Zoom" if zoom else f"Call them at {a.get('phone', '')}"
        desc = f"{how}. {who} - {a.get('current_brokerage', '')}. Answers: {_mc_link(req)}"

    def esc(v):
        return str(v or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TPL Collective//1-on-1//EN", "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:one-on-one-{req['id']}-{int(start.timestamp())}@tplcollective.ai",
        f"DTSTAMP:{_now().strftime(fmt)}",
        f"DTSTART:{start.astimezone(timezone.utc).strftime(fmt)}",
        f"DTEND:{end.astimezone(timezone.utc).strftime(fmt)}",
        f"SUMMARY:{esc(summary)}",
        f"DESCRIPTION:{esc(desc)}",
        f"LOCATION:{esc(location)}",
        "BEGIN:VALARM", "TRIGGER:-PT15M", "ACTION:DISPLAY", "DESCRIPTION:Call with Joe", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", "",
    ])
    return {"filename": "call-with-joe.ics" if not for_joe else f"1on1-{rn._slugify(who) or 'agent'}.ics",
            "content": base64.b64encode(body.encode()).decode()}


def _email_agent(req: dict, subject: str, inner_html: str, attachments=None) -> tuple:
    from main import send_email
    s = _settings()
    a = req.get("answers") or {}
    html = (
        f'<div style="font-family:{rn.FONT};max-width:560px;margin:0 auto;padding:24px;color:{rn.INK};line-height:1.6;font-size:15px;">'
        f'<p>Hey {_esc(a.get("first_name") or "there")},</p>{inner_html}'
        f'<p style="margin-top:22px;">{_esc(s.get("sender_name"))}<br><span style="color:{rn.MUTED};font-size:13px;">{_esc(s.get("sender_title"))}</span></p></div>'
    )
    return send_email(rn._smtp_cfg(), a.get("email"), subject, html, from_address=s["from_address"],
                      contact_id=req.get("lead_id"), campaign="one-on-one", reply_to=s["reply_to"],
                      attachments=attachments)


def _email_joe(subject: str, intro: str, req: dict, attachments=None, campaign: str = "one-on-one-alert"):
    from main import send_email
    s = _settings()
    to = s.get("notify_email") or s.get("reply_to")
    if not to:
        return
    rows = "".join(
        f'<tr><td style="padding:5px 12px 5px 0;color:#666;font-size:13px;vertical-align:top;">{_esc(k)}</td>'
        f'<td style="padding:5px 0;font-size:14px;">{_esc(v)}</td></tr>'
        for k, v in _answer_rows(req) if v
    )
    html = (
        f'<div style="font-family:{rn.FONT};max-width:560px;margin:0 auto;padding:24px;color:{rn.INK};">'
        f'<h2 style="color:{rn.ACCENT};margin:0 0 10px 0;font-size:18px;">{_esc(subject)}</h2>'
        f'<p style="font-size:15px;line-height:1.6;margin:0 0 16px 0;">{intro}</p>'
        f'<table style="border-collapse:collapse;">{rows}</table>'
        f'<p style="margin-top:20px;"><a href="{_mc_link(req)}" style="display:inline-block;background:{rn.ACCENT};color:#fff;'
        f'padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:bold;">Open in Mission Control</a></p></div>'
    )
    try:
        send_email(rn._smtp_cfg(), to, subject, html, from_address=s["from_address"], campaign=campaign, attachments=attachments)
    except Exception as e:
        print(f"[1on1] alert failed: {e}")


def _slots(req: dict) -> List[dict]:
    out = []
    for i, sl in enumerate(req.get("proposed_slots") or []):
        st = _parse_ts(sl.get("start"))
        if st:
            out.append({"i": i, "start": st, "minutes": int(sl.get("minutes") or 30)})
    return out


# ════════════════════════════════════════════════════════════
# Public: the form
# ════════════════════════════════════════════════════════════

@public_router.post("/request")
def submit_request(body: RequestIn):
    if body.website:  # honeypot tripped: pretend success, store nothing
        return {"ok": True}
    email = (body.email or "").strip().lower()
    first = (body.first_name or "").strip()[:60]
    last = (body.last_name or "").strip()[:60]
    phone = (body.phone or "").strip()[:40]
    if not first or not rn._EMAIL_RE.match(email):
        raise HTTPException(400, "First name and a valid email are required.")
    if len(re.sub(r"\D", "", phone)) < 10:
        raise HTTPException(400, "Please add a phone number so Joe can reach you.")

    answers = {
        "current_brokerage": body.current_brokerage.strip()[:120],
        "agent_type": body.agent_type.strip()[:60],
        "deals": body.deals.strip()[:40],
        "avg_price": body.avg_price.strip()[:40],
        "topics": [x.strip()[:60] for x in (body.topics or [])][:10],
        "timeline": body.timeline.strip()[:60],
        "notes": body.notes.strip()[:2000],
    }

    send = rn._send_for_token(body.t)
    lead = None
    if send and send.get("lead_id"):
        lead = _lead(send["lead_id"]) or None
    if not lead:
        lead = (_t("leads").select("*").eq("workspace_id", WS).ilike("email", email).order("id").limit(1).execute().data or [None])[0]

    upd = {
        "team_or_solo": answers["agent_type"], "deals_per_year": answers["deals"], "avg_price": answers["avg_price"],
        "ready_timeline": answers["timeline"], "lead_temperature": "hot",
    }
    if answers["current_brokerage"]:
        upd["current_brokerage"] = answers["current_brokerage"]
    upd = {k: v for k, v in upd.items() if v}

    if lead:
        if not lead.get("phone"):
            upd["phone"] = phone
        if not lead.get("first_name"):
            upd["first_name"] = first
        if not lead.get("last_name") and last:
            upd["last_name"] = last
        upd["lead_score"] = max(int(lead.get("lead_score") or 0), 70)
        upd["motivations"] = sorted(set((lead.get("motivations") or []) + answers["topics"]))
        upd["tags"] = sorted(set((lead.get("tags") or []) + ["book-call-form"]))
        _t("leads").update(upd).eq("id", lead["id"]).execute()
        lead_id = lead["id"]
    else:
        new = {
            **upd, "workspace_id": WS, "name": f"{first} {last}".strip(), "first_name": first, "last_name": last,
            "email": email, "phone": phone, "source": "weekly-email-book" if send else "tpl-book-page",
            "stage": "research", "status": "new", "lead_score": 70, "motivations": answers["topics"],
            "tags": ["book-call-form"],
        }
        lead_id = _t("leads").insert(new).execute().data[0]["id"]

    req = _t("booking_requests").insert({
        "workspace_id": WS, "lead_id": lead_id, "send_id": send["id"] if send else None,
        "issue_id": send["issue_id"] if send else None, "status": "new", "token": str(uuid.uuid4()),
        "answers": {**answers, "first_name": first, "last_name": last, "email": email, "phone": phone},
    }).execute().data[0]
    rn._activity(lead_id, "booking_form_submitted", "Requested a 1-on-1 (pre-call form)",
                 {**answers, "request_id": req["id"], "issue_id": req.get("issue_id")})
    _task(req, f"Send 1-on-1 times to {_who(req)}", _now())
    _email_joe(
        f"1-on-1 request: {_who(req)}",
        "Nothing is on your calendar yet. Review the answers, then send a few times from Mission Control."
        + (" They came from the weekly email." if send else ""),
        req,
    )
    return {"ok": True}


# ════════════════════════════════════════════════════════════
# Public: pick a time
# ════════════════════════════════════════════════════════════

@public_router.get("/pick")
def pick_info(r: str = ""):
    req = _by_token(r)
    if not req:
        raise HTTPException(404, "This link isn't valid anymore. Reply to Joe's email and he'll sort it out.")
    now = _now()
    a = req.get("answers") or {}
    out = {"first_name": a.get("first_name") or "", "status": req["status"], "note": req.get("times_note") or "", "slots": []}
    if req["status"] == "confirmed":
        st = _parse_ts(req.get("confirmed_start"))
        out["confirmed"] = {"start": _iso(st), "label": _fmt_et(st), "minutes": req.get("confirmed_minutes")} if st else None
    elif req["status"] == "times_sent":
        out["slots"] = [{"i": s["i"], "start": _iso(s["start"]), "label": _fmt_et(s["start"]), "minutes": s["minutes"]}
                        for s in _slots(req) if s["start"] > now]
    return out


@public_router.post("/pick")
def pick(body: PickIn):
    req = _by_token(body.r)
    if not req:
        raise HTTPException(404, "This link isn't valid anymore. Reply to Joe's email and he'll sort it out.")

    if body.none:
        if req["status"] == "confirmed":
            raise HTTPException(409, "You're already confirmed. Reply to Joe's email to change it.")
        note = (body.note or "").strip()[:1000]
        _t("booking_requests").update({"status": "new", "agent_note": note}).eq("id", req["id"]).execute()
        rn._activity(req.get("lead_id"), "call_times_declined", "None of the offered times worked", {"note": note})
        _task(req, f"Send new 1-on-1 times to {_who(req)}", _now())
        _email_joe(f"{_who(req)} needs different times",
                   "None of the times you offered work." + (f" Their note: <b>{_esc(note)}</b>" if note else ""), req)
        return {"ok": True, "status": "new"}

    if req["status"] == "confirmed":
        st = _parse_ts(req.get("confirmed_start"))
        chosen = next((s for s in _slots(req) if s["i"] == body.s), None)
        if chosen and st and chosen["start"] == st:
            return {"ok": True, "status": "confirmed", "label": _fmt_et(st)}  # double click
        raise HTTPException(409, f"You're already confirmed for {_fmt_et(st)}. Reply to Joe's email to change it.")
    if req["status"] != "times_sent":
        raise HTTPException(409, "These times aren't open anymore. Reply to Joe's email and he'll send new ones.")

    chosen = next((s for s in _slots(req) if s["i"] == body.s), None)
    if not chosen:
        raise HTTPException(400, "Pick one of the listed times.")
    if chosen["start"] <= _now():
        raise HTTPException(409, "That time has already passed. Pick another, or tell Joe none of these work.")
    return _confirm(req, chosen["start"], chosen["minutes"], by_agent=True)


def _confirm(req: dict, start: datetime, minutes: int, by_agent: bool) -> dict:
    # conditional on the current status so two quick clicks can't confirm twice
    upd = {"status": "confirmed", "confirmed_start": _iso(start), "confirmed_minutes": minutes, "confirmed_at": _iso(_now())}
    res = _t("booking_requests").update(upd).eq("id", req["id"]).eq("status", req["status"]).execute().data
    if not res:
        raise HTTPException(409, "This request just changed. Refresh the page.")
    req = {**req, **upd}
    label = _fmt_et(start)
    lead_upd = {"stage": "discovery_call", "follow_up_date": _iso(start)}
    try:
        _t("leads").update(lead_upd).eq("id", req.get("lead_id")).execute()
    except Exception:
        pass
    rn._activity(req.get("lead_id"), "call_confirmed", f"1-on-1 confirmed for {label}",
                 {"request_id": req["id"], "start": _iso(start), "by": "agent" if by_agent else "joe"})
    _close_tasks(req, "Send ")
    local = start.astimezone(rn._ET)
    _task(req, f"1-on-1 call with {_who(req)}", start, local.strftime("%I:%M %p").lstrip("0") + " ET")

    a = req.get("answers") or {}
    how_joe = "Zoom" if req.get("meeting_type") == "zoom" else f"phone, call them at {a.get('phone', '')}"
    _email_agent(req, f"Confirmed: {label} with Joe",
                 f"<p>You're set for <b>{_esc(label)}</b> ({minutes} minutes). {_esc(_how(req))}</p>"
                 "<p>The calendar invite is attached. If something comes up, just reply to this email.</p>",
                 attachments=[_ics(req, start, minutes, for_joe=False)])
    _email_joe(f"Confirmed: {_who(req)}, {label}",
               f"{'They picked' if by_agent else 'You confirmed'} <b>{_esc(label)}</b> by {_esc(how_joe)}. Calendar file attached; open it to add the call to your calendar.",
               req, attachments=[_ics(req, start, minutes, for_joe=True)], campaign="one-on-one-confirmed")
    return {"ok": True, "status": "confirmed", "label": label}


# ════════════════════════════════════════════════════════════
# Admin
# ════════════════════════════════════════════════════════════

@router.get("/requests")
def list_requests(status: Optional[str] = None):
    q = _t("booking_requests").select("*").eq("workspace_id", WS)
    if status:
        q = q.eq("status", status)
    rows = q.order("created_at", desc=True).limit(300).execute().data or []
    now = _now()
    for r in rows:
        r["who"] = _who(r)
        r["slots"] = [{"i": s["i"], "start": _iso(s["start"]), "label": _fmt_et(s["start"]), "passed": s["start"] <= now,
                       "minutes": s["minutes"]} for s in _slots(r)]
        st = _parse_ts(r.get("confirmed_start"))
        r["confirmed_label"] = _fmt_et(st) if st else None
        r.pop("token", None)
    return {"requests": rows}


@router.get("/counts")
def counts():
    out = {}
    for st in STATUSES:
        out[st] = _t("booking_requests").select("id", count="exact").eq("workspace_id", WS).eq("status", st).limit(1).execute().count or 0
    return out


@router.post("/requests/{req_id}/send-times")
def send_times(req_id: int, body: SendTimesIn):
    req = _get(req_id)
    if req["status"] in ("confirmed", "closed"):
        raise HTTPException(409, f"This request is {req['status']}. Reopen it first.")
    minutes = int(body.minutes or _settings().get("call_minutes") or 30)
    if not 10 <= minutes <= 120:
        raise HTTPException(400, "Call length should be 10-120 minutes.")
    now = _now()
    slots = []
    for raw in body.slots or []:
        st = _parse_ts(raw)
        if not st:
            raise HTTPException(400, f"'{raw}' isn't a valid time.")
        if st <= now + timedelta(minutes=30):
            raise HTTPException(400, f"{_fmt_et(st)} is too soon or already passed.")
        slots.append(st)
    slots = sorted(set(slots))
    if not 1 <= len(slots) <= 4:
        raise HTTPException(400, "Offer between 1 and 4 times.")

    meeting = (body.meeting or "phone").lower()
    if meeting not in ("phone", "zoom"):
        raise HTTPException(400, "Meeting must be phone or zoom.")
    if meeting == "zoom" and not (_settings().get("zoom_link") or "").strip():
        raise HTTPException(400, "Add your Zoom link in Weekly Email settings first, or offer a phone call.")
    note = (body.note or "").strip()[:1000]
    token = req.get("token") or str(uuid.uuid4())
    link = f"{SITE}/pick?r={token}"
    buttons = "".join(
        f'<tr><td style="padding:0 0 10px 0;"><a href="{link}&s={i}" style="display:block;background:{rn.SOFT};border:2px solid {rn.ACCENT};'
        f'border-radius:8px;padding:12px 16px;color:{rn.INK};text-decoration:none;font-weight:bold;font-size:15px;">{_esc(_fmt_et(st))}</a></td></tr>'
        for i, st in enumerate(slots)
    )
    inner = (
        (f"<p>{_esc(note)}</p>" if note else "<p>Thanks for filling that out. I read through your answers and I'm looking forward to talking.</p>")
        + f"<p>Here are a few times that work for me ({minutes} minutes, {'on Zoom' if meeting == 'zoom' else 'by phone'}). Click one and it's locked in:</p>"
        + f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:420px;">{buttons}</table>'
        + f'<p style="font-size:14px;color:{rn.MUTED};">None of these work? <a href="{link}#none" style="color:{rn.ACCENT};">Tell me what does</a>, or just reply to this email.</p>'
    )
    probe = {**req, "token": token, "meeting_type": meeting}
    ok, err = _email_agent(probe, "A few times for our call", inner)
    if not ok:
        if (err or "").startswith("Email suppressed"):
            raise HTTPException(409, "This agent is on the suppression list (they unsubscribed or bounced), so the email was blocked. Reach out by phone or from your own inbox.")
        raise HTTPException(502, f"Email failed: {err}")
    _t("booking_requests").update({
        "status": "times_sent", "token": token, "times_note": note, "times_sent_at": _iso(now), "meeting_type": meeting,
        "proposed_slots": [{"start": _iso(st), "minutes": minutes} for st in slots], "last_nudge_at": None,
    }).eq("id", req_id).execute()
    rn._activity(req.get("lead_id"), "call_times_sent", f"Offered {len(slots)} call times", {"request_id": req_id})
    _close_tasks(req, "Send ")
    return {"ok": True}


@router.post("/requests/{req_id}/confirm")
def confirm_manual(req_id: int, body: ConfirmIn):
    """For when the agent replied by email or phone instead of clicking."""
    req = _get(req_id)
    if req["status"] in ("confirmed", "closed"):
        raise HTTPException(409, f"This request is {req['status']}.")
    st = _parse_ts(body.start)
    if not st or st <= _now():
        raise HTTPException(400, "Pick a future time.")
    if body.meeting:
        m = body.meeting.lower()
        if m not in ("phone", "zoom"):
            raise HTTPException(400, "Meeting must be phone or zoom.")
        if m == "zoom" and not (_settings().get("zoom_link") or "").strip():
            raise HTTPException(400, "Add your Zoom link in Weekly Email settings first, or confirm a phone call.")
        _t("booking_requests").update({"meeting_type": m}).eq("id", req_id).execute()
        req = {**req, "meeting_type": m}
    return _confirm(req, st, int(body.minutes or _settings().get("call_minutes") or 30), by_agent=False)


@router.post("/requests/{req_id}/close")
def close(req_id: int, body: CloseIn):
    req = _get(req_id)
    _t("booking_requests").update({"status": "closed", "closed_reason": (body.reason or "").strip()[:300]}).eq("id", req_id).execute()
    _close_tasks(req, "")
    rn._activity(req.get("lead_id"), "one_on_one_closed", "1-on-1 request closed" + (f": {body.reason}" if body.reason else ""), {"request_id": req_id})
    return {"ok": True}


@router.post("/requests/{req_id}/reopen")
def reopen(req_id: int):
    _get(req_id)
    _t("booking_requests").update({"status": "new", "closed_reason": None}).eq("id", req_id).execute()
    return {"ok": True}


# ════════════════════════════════════════════════════════════
# Reminders (cron, loopback, every 15 minutes)
# ════════════════════════════════════════════════════════════

def _age(delta: timedelta) -> str:
    h = int(delta.total_seconds() // 3600)
    return f"{h // 24} days" if h >= 48 else f"{h} hours"


@router.post("/process")
def process():
    now = _now()
    done = {"nudges": 0, "preps": 0, "agent_reminders": 0}
    rows = (_t("booking_requests").select("*").eq("workspace_id", WS)
            .in_("status", ["new", "times_sent", "confirmed"]).execute().data or [])
    for req in rows:
        last_nudge = _parse_ts(req.get("last_nudge_at"))
        can_nudge = not last_nudge or now - last_nudge >= NUDGE_EVERY
        try:
            if req["status"] == "new" and can_nudge:
                age = now - (_parse_ts(req.get("created_at")) or now)
                if age >= NUDGE_NEW_AFTER:
                    _email_joe(f"Still waiting: {_who(req)} asked for a 1-on-1 {_age(age)} ago",
                               "No times have gone out yet.", req, campaign="one-on-one-nudge")
                    _t("booking_requests").update({"last_nudge_at": _iso(now)}).eq("id", req["id"]).execute()
                    done["nudges"] += 1
            elif req["status"] == "times_sent" and can_nudge:
                sent = _parse_ts(req.get("times_sent_at")) or now
                open_slots = [s for s in _slots(req) if s["start"] > now]
                if not open_slots:
                    _email_joe(f"{_who(req)}: every time you offered has passed",
                               "They never picked one. Send new times or close the request.", req, campaign="one-on-one-nudge")
                    _t("booking_requests").update({"last_nudge_at": _iso(now)}).eq("id", req["id"]).execute()
                    done["nudges"] += 1
                elif now - sent >= NUDGE_OFFER_AFTER:
                    _email_joe(f"{_who(req)} hasn't picked a time ({_age(now - sent)})",
                               "Worth a quick text or call.", req, campaign="one-on-one-nudge")
                    _t("booking_requests").update({"last_nudge_at": _iso(now)}).eq("id", req["id"]).execute()
                    done["nudges"] += 1
            elif req["status"] == "confirmed":
                st = _parse_ts(req.get("confirmed_start"))
                if not st or st <= now:
                    continue
                if not req.get("prep_sent_at") and st - now <= PREP_BEFORE:
                    _email_joe(f"In {max(1, int((st - now).total_seconds() // 60))} min: call with {_who(req)}",
                               f"Starts <b>{_esc(_fmt_et(st))}</b>, "
                               + ("on Zoom" if req.get("meeting_type") == "zoom" else f"you call them at {_esc((req.get('answers') or {}).get('phone', ''))}")
                               + ". Their answers:", req, campaign="one-on-one-prep")
                    _t("booking_requests").update({"prep_sent_at": _iso(now)}).eq("id", req["id"]).execute()
                    done["preps"] += 1
                if not req.get("agent_reminder_sent_at") and st - now <= AGENT_REMINDER_BEFORE:
                    _email_agent(req, f"Talk soon: {_fmt_et(st)}",
                                 f"<p>Quick reminder about our call <b>{_esc(_fmt_et(st))}</b>. {_esc(_how(req))}</p>"
                                 "<p>If something came up, just reply and we'll find another time.</p>")
                    _t("booking_requests").update({"agent_reminder_sent_at": _iso(now)}).eq("id", req["id"]).execute()
                    done["agent_reminders"] += 1
        except Exception as e:
            print(f"[1on1] reminder failed for {req.get('id')}: {e}")
    return {"ok": True, **done}
