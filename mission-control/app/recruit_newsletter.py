"""
Weekly recruiting email ("The Weekly") to non-LPT agents on the recruit list.

Template, top to bottom (see render_issue):
  1. short personal intro
  2. this week's class      - Joe's pre-recorded YouTube class, watched on
                               tplcollective.ai/watch so viewing ties to a lead
  3. open trainings          - LPT's recurring webinars that accept any agent,
                               auto-filled per week + "see the full schedule"
  4. number of the week      - optional
  5. from the blog
  6. industry pulse          - optional
  7. free tools
  8. book a 1-on-1           - tplcollective.ai/book pre-qualifying form; Joe then offers times (one_on_one.py)
  9. sign-off, socials, P.S.

Architecture (mirrors prospect_engagement.py):
  - `setup(db, supabase)` is called by main.py after both are defined
  - admin router /api/recruit-newsletter is platform-only; every query filters
    workspace_id = PLATFORM_WORKSPACE_ID explicitly so the loopback cron and
    the UI see the same rows
  - public_router  /api/public/weekly/*   (videos, trainings, recipient prefill)
  - the 1-on-1 request form and pick-a-time flow live in one_on_one.py
  - tracking_router /api/tracking/weekly/* (click redirect, video heartbeat)
    both prefixes are already on main.py's public whitelist
  - every outbound email goes through main.send_email()

Per-recipient tracking:
  - each recruit_newsletter_sends row has a random UUID token
  - every link in that recipient's email is wrapped in a signed redirect
    (/api/tracking/weekly/c/<token>?u=<url>&s=<hmac>), and links to our own
    pages also carry ?t=<token> so /watch, /book and /trainings know who it is
  - the signature stops the redirect being used as an open redirect
  - link scanners that "click" everything at delivery are flagged, not counted

Review gate (Joe approves every outbound message before it reaches a lead):
  - approve requires a test sent AFTER the last content edit
  - content is frozen once approved; unapprove only before any real send
  - a mailing address must be configured (CAN-SPAM)

Compliance: nothing here asks about or depends on sponsorship. The booking
form is a pre-qualifying conversation, and none of the free trainings, classes
or tools are conditioned on anything. See CLAUDE.md Rules.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Callable, Any, List, Dict
from datetime import datetime, timedelta, timezone, date
import hashlib
import hmac
import html as _html
import json
import os
import re
import time
import urllib.parse
import uuid

try:
    from zoneinfo import ZoneInfo
    _ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover
    _ET = timezone(timedelta(hours=-4))


router = APIRouter(prefix="/api/recruit-newsletter", tags=["recruit-newsletter"])
public_router = APIRouter(prefix="/api/public/weekly", tags=["recruit-newsletter-public"])
tracking_router = APIRouter(prefix="/api/tracking/weekly", tags=["recruit-newsletter-tracking"])

_db: Optional[Callable[[str], Any]] = None
_supabase: Any = None

WS = 1  # PLATFORM_WORKSPACE_ID - this is a TPL Collective recruiting feature
PER_RUN_CAP = 60          # sends per /process call (keeps each cron request short)
SEND_SPACING_SEC = 0.3    # stay well under Resend's per-second limit
LEASE_MINUTES = 10
SITE = "https://tplcollective.ai"
TRACK_BASE = "https://mission.tplcollective.ai/api/tracking/weekly"
TEST_TOKEN = "test"       # used in test sends: links work, nothing is logged
VIDEO_MILESTONES = (25, 50, 75, 90)
VIDEO_ALERT_AT = 50

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# LPT's recurring webinars that accept any agent (name + email on Zoom, no LPT
# login). Verified 2026-09-28 from LPT's weekly "Upcoming Events" emails.
# Descriptions are ours. Joe toggles / edits these in Weekly Email settings.
DEFAULT_RECURRING_EVENTS = [
    {"key": "motivational-monday", "active": True, "weekday": 0, "start": "11:00", "end": "11:30",
     "title": "Motivational Monday", "host": "LPT Realty",
     "description": "LPT Founder and CEO Robert Palmer and EVP Matthew Hodge on company news, the market headlines that matter, and the mindset to win the week.",
     "url": "https://lptrealty.zoom.us/webinar/register/WN_pT5YNIFxStib9sKx2310FQ"},
    {"key": "tools-tuesday", "active": True, "weekday": 1, "start": "11:00", "end": "11:30",
     "title": "Tools Tuesday", "host": "LPT Realty",
     "description": "A live, hands-on look at the listing marketing and transaction tools LPT agents use every day.",
     "url": "https://lptrealty.zoom.us/webinar/register/WN_GAYpxxQhR2WDW9RAuQDPXg"},
    {"key": "la-esquina-latina", "active": False, "weekday": 3, "start": "11:00", "end": "11:30",
     "title": "La Esquina Latina (en español)", "host": "LPT Realty",
     "description": "Programa semanal en español con agentes invitados: sus historias, estrategias y tendencias del mercado.",
     "url": "https://lptrealty.zoom.us/webinar/register/WN_hwoWn-F_SBOI8xjm6v0RJA"},
    {"key": "exito-en-espanol", "active": False, "weekday": 3, "start": "16:00", "end": "16:30",
     "title": "Éxito en Español", "host": "LPT Realty",
     "description": "Programa semanal en español con Michael Valdes, CEO de LPT Realty Global e Internacional.",
     "url": "https://lptrealty.zoom.us/webinar/register/WN_-ktmOTxZQce583yxSJBCnA"},
    {"key": "reff", "active": True, "weekday": 4, "start": "11:00", "end": "11:30",
     "title": "Real Estate First Friday", "host": "LPT Realty",
     "description": "Top producers and industry leaders on lead generation, marketing and systems you can use the same day. Every Friday, despite the name.",
     "url": "https://lptrealty.zoom.us/webinar/register/WN_7-KY5YIMQ1KGWoFMDfLTlQ"},
]

DEFAULT_SOCIALS = [
    {"label": "YouTube", "url": "https://www.youtube.com/@JoeyDeSaneLPTRealty"},
    {"label": "Instagram", "url": "https://www.instagram.com/joey_desane"},
    {"label": "Facebook", "url": "https://www.facebook.com/profile.php?id=658348823"},
]

DEFAULT_SETTINGS = {
    "from_address": "Joe DeSane <joe@tplcollective.co>",
    "reply_to": "joe@desaneteam.com",
    "notify_email": "joe@desaneteam.com",
    "zoom_link": "",         # Joe's Zoom link for 1-on-1s offered as Zoom calls
    "call_minutes": 30,
    "mailing_address": "",
    "sender_name": "Joe DeSane",
    "sender_title": "Founder, TPL Collective",
    "default_daily_cap": 150,
    "socials": DEFAULT_SOCIALS,
    "recurring_events": DEFAULT_RECURRING_EVENTS,
}

DEFAULT_TOOLS = [
    {"label": "Brokerage Cost Comparator: see what you keep at 20+ brokerages", "url": "https://tplcollective.ai/compare"},
    {"label": "Cap Break-Even Explained", "url": "https://tplcollective.ai/blog/cap-break-even-explained"},
    {"label": "Hidden Brokerage Fees", "url": "https://tplcollective.ai/blog/hidden-brokerage-fees"},
    {"label": "Switching Brokerages Risk Checklist", "url": "https://tplcollective.ai/blog/switching-brokerages-risk-checklist"},
]


def setup(db_callable, supabase_client):
    global _db, _supabase
    _db = db_callable
    _supabase = supabase_client


def _t(name: str):
    return _supabase.table(name)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_ts(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def _user(request: Request) -> dict:
    return getattr(request.state, "user", {}) or {}


# ════════════════════════════════════════════════════════════
# Settings (stored under "recruit_newsletter" in /data/settings.json)
# ════════════════════════════════════════════════════════════

def _settings() -> dict:
    from main import load_settings
    s = (load_settings() or {}).get("recruit_newsletter") or {}
    out = json.loads(json.dumps(DEFAULT_SETTINGS))  # deep copy
    out.update({k: v for k, v in s.items() if v is not None})
    return out


def _smtp_cfg() -> dict:
    from main import load_settings
    return (load_settings() or {}).get("smtp") or {}


def _secret() -> bytes:
    return (os.environ.get("JWT_SECRET") or "").encode()


# ════════════════════════════════════════════════════════════
# Pydantic models
# ════════════════════════════════════════════════════════════

class IssueIn(BaseModel):
    issue_date: Optional[str] = None
    subject: Optional[str] = None
    preheader: Optional[str] = None
    content: Optional[dict] = None


class TestIn(BaseModel):
    to: Optional[str] = None


class ApproveIn(BaseModel):
    scheduled_for: Optional[str] = None   # ISO; omitted = now
    daily_cap: Optional[int] = None


class SettingsIn(BaseModel):
    from_address: Optional[str] = None
    reply_to: Optional[str] = None
    notify_email: Optional[str] = None
    zoom_link: Optional[str] = None
    call_minutes: Optional[int] = None
    mailing_address: Optional[str] = None
    sender_name: Optional[str] = None
    sender_title: Optional[str] = None
    default_daily_cap: Optional[int] = None
    socials: Optional[List[dict]] = None
    recurring_events: Optional[List[dict]] = None


class VideoIn(BaseModel):
    slug: Optional[str] = None
    youtube_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    duration_seconds: Optional[int] = None
    published: Optional[bool] = None


# ════════════════════════════════════════════════════════════
# Audience
# ════════════════════════════════════════════════════════════

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
_EXCLUDED_STATUSES = {"unsubscribed", "active_agent"}
_EXCLUDED_STAGES = {"coaching_client", "signed"}


def _brokerage_bucket(b: str) -> str:
    b = (b or "").lower()
    if not b:
        return "Unknown"
    if "keller" in b or b.startswith("kw"):
        return "Keller Williams"
    if "re/max" in b or "remax" in b:
        return "RE/MAX"
    if "exp" in b.split() or b.startswith("exp"):
        return "eXp"
    if "real brokerage" in b or b == "real":
        return "REAL"
    return "Other"


def _first_name(lead: dict) -> str:
    fn = (lead.get("first_name") or "").strip()
    if not fn:
        fn = ((lead.get("name") or "").strip().split(" ") or [""])[0]
    # never greet someone with an email handle or a stray placeholder
    if not fn or "@" in fn or "{" in fn or "}" in fn or len(fn) > 30:
        return ""
    return fn[:1].upper() + fn[1:]


def _audience() -> List[dict]:
    """Every non-LPT recruit lead with a valid, unsuppressed email, one row per address.

    An address is excluded outright if ANY lead row carrying it is unsubscribed,
    so a duplicate lead record can never re-subscribe someone.
    """
    leads: List[dict] = []
    start = 0
    while True:
        page = (
            _t("leads")
            .select("id, email, first_name, name, status, stage, current_brokerage, tags")
            .eq("workspace_id", WS)
            .order("id")
            .range(start, start + 999)
            .execute()
            .data
            or []
        )
        leads.extend(page)
        if len(page) < 1000:
            break
        start += 1000

    suppressed = set()
    start = 0
    while True:
        page = _t("email_suppressions").select("email").range(start, start + 999).execute().data or []
        suppressed.update((r.get("email") or "").strip().lower() for r in page)
        if len(page) < 1000:
            break
        start += 1000

    blocked = set()
    for l in leads:
        em = (l.get("email") or "").strip().lower()
        if em and (l.get("status") or "") == "unsubscribed":
            blocked.add(em)

    out, seen = [], set()
    for l in leads:
        em = (l.get("email") or "").strip().lower()
        if not em or not _EMAIL_RE.match(em):
            continue
        if em in seen or em in suppressed or em in blocked:
            continue
        if (l.get("status") or "") in _EXCLUDED_STATUSES:
            continue
        if (l.get("stage") or "") in _EXCLUDED_STAGES:
            continue
        if "lpt" in (l.get("current_brokerage") or "").lower():
            continue
        seen.add(em)
        out.append({
            "lead_id": l["id"],
            "email": em,
            "first_name": _first_name(l),
            "bucket": _brokerage_bucket(l.get("current_brokerage")),
        })
    return out


# ════════════════════════════════════════════════════════════
# Recurring events
# ════════════════════════════════════════════════════════════

def _fmt_clock(hhmm: str) -> tuple:
    """"16:30" -> ("4:30", "PM"); "11:00" -> ("11:00", "AM")."""
    try:
        h, m = [int(x) for x in str(hhmm).split(":")[:2]]
    except Exception:
        return str(hhmm or ""), ""
    return f"{h % 12 or 12}:{m:02d}", ("AM" if h < 12 else "PM")


def _fmt_range(start: str, end: str) -> str:
    s, sa = _fmt_clock(start)
    if not end:
        return f"{s} {sa} ET".replace("  ", " ")
    e, ea = _fmt_clock(end)
    return f"{s}-{e} {ea} ET" if sa == ea else f"{s} {sa}-{e} {ea} ET"


def _week_events(issue_date: str, recurring: List[dict]) -> List[dict]:
    """Concrete dated events for the week that starts on (or contains) issue_date."""
    try:
        d = date.fromisoformat(str(issue_date)[:10])
    except Exception:
        return []
    monday = d - timedelta(days=d.weekday())
    out = []
    for ev in sorted(recurring or [], key=lambda e: (int(e.get("weekday") or 0), e.get("start") or "")):
        if not ev.get("active"):
            continue
        try:
            wd = int(ev.get("weekday"))
        except Exception:
            continue
        day = monday + timedelta(days=wd)
        out.append({
            "recurring_key": ev.get("key") or "",
            "host": ev.get("host") or "",
            "when": f"{WEEKDAYS[wd]}, {day.strftime('%b')} {day.day} - {_fmt_range(ev.get('start'), ev.get('end'))}",
            "title": ev.get("title") or "",
            "description": ev.get("description") or "",
            "url": ev.get("url") or "",
            "cta_label": "Register free",
        })
    return out


def _next_occurrence(ev: dict, now_et: datetime) -> Optional[datetime]:
    try:
        wd = int(ev.get("weekday"))
        h, m = [int(x) for x in str(ev.get("start") or "0:0").split(":")[:2]]
    except Exception:
        return None
    days = (wd - now_et.weekday()) % 7
    cand = (now_et + timedelta(days=days)).replace(hour=h, minute=m, second=0, microsecond=0)
    try:
        eh, em = [int(x) for x in str(ev.get("end") or ev.get("start")).split(":")[:2]]
        end = cand.replace(hour=eh, minute=em)
    except Exception:
        end = cand
    if end < now_et:
        cand += timedelta(days=7)
    return cand


# ════════════════════════════════════════════════════════════
# Videos
# ════════════════════════════════════════════════════════════

_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


def _youtube_id(url_or_id: str) -> Optional[str]:
    s = (url_or_id or "").strip()
    if _YT_ID_RE.match(s):
        return s
    try:
        p = urllib.parse.urlparse(s)
    except Exception:
        return None
    host = (p.netloc or "").lower()
    cand = None
    if host.endswith("youtu.be"):
        cand = p.path.strip("/").split("/")[0]
    elif "youtube" in host:
        q = dict(urllib.parse.parse_qsl(p.query))
        if q.get("v"):
            cand = q["v"]
        else:
            parts = [x for x in p.path.split("/") if x]
            if len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v"):
                cand = parts[1]
    return cand if cand and _YT_ID_RE.match(cand) else None


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:60].strip("-")


def _videos_map() -> Dict[str, dict]:
    rows = _t("tpl_videos").select("*").eq("workspace_id", WS).execute().data or []
    return {r["slug"]: r for r in rows}


def _fmt_duration(sec) -> str:
    try:
        sec = int(sec)
    except Exception:
        return ""
    if sec <= 0:
        return ""
    m = round(sec / 60)
    return f"{max(1, m)} min"


# ════════════════════════════════════════════════════════════
# Link tracking
# ════════════════════════════════════════════════════════════

def _sign(token: str, url: str) -> str:
    return hmac.new(_secret(), f"{token}|{url}".encode(), hashlib.sha256).hexdigest()[:24]


def _is_own_page(url: str) -> bool:
    try:
        p = urllib.parse.urlparse(url)
    except Exception:
        return False
    return p.netloc.endswith("tplcollective.ai")


def _with_params(url: str, extra: dict) -> str:
    try:
        p = urllib.parse.urlparse(url)
        q = dict(urllib.parse.parse_qsl(p.query))
        for k, v in extra.items():
            if v:
                q.setdefault(k, v)
        return urllib.parse.urlunparse(p._replace(query=urllib.parse.urlencode(q)))
    except Exception:
        return url


class _Links:
    """Builds every link in one recipient's email."""

    def __init__(self, campaign: str, token: Optional[str]):
        self.campaign = campaign
        self.token = token

    def __call__(self, url: str, label: str = "") -> str:
        if not url:
            return ""
        dest = url
        if _is_own_page(dest):
            dest = _with_params(dest, {
                "utm_source": "weekly-email", "utm_medium": "email",
                "utm_campaign": self.campaign, "utm_content": _slugify(label)[:40],
                "t": self.token,
            })
        if not self.token or not _secret():
            return dest
        q = urllib.parse.urlencode({"u": dest, "s": _sign(self.token, dest), "l": (label or "")[:60]})
        return f"{TRACK_BASE}/c/{self.token}?{q}"


# ════════════════════════════════════════════════════════════
# Rendering
# ════════════════════════════════════════════════════════════

ACCENT = "#6c63ff"
INK = "#1a1a2e"
MUTED = "#5b5b72"
LINE = "#e6e6ef"
SOFT = "#f6f5ff"
FONT = "Helvetica, Arial, sans-serif"

_LINK_MD = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_BOLD_MD = re.compile(r"\*\*(.+?)\*\*")


def _esc(s) -> str:
    return _html.escape(str(s or ""), quote=True)


def _rich(text: str, link: _Links, size: int = 15, color: str = INK) -> str:
    """Escape, then allow **bold** and [label](url). Blank line = new paragraph."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", str(text or "").strip()) if p.strip()]
    out = []
    for p in paras:
        h = _esc(p)
        h = _LINK_MD.sub(
            lambda m: f'<a href="{_esc(link(_html.unescape(m.group(2)), m.group(1)))}" style="color:{ACCENT};">{m.group(1)}</a>',
            h,
        )
        h = _BOLD_MD.sub(r"<strong>\1</strong>", h)
        h = h.replace("\n", "<br>")
        out.append(f'<p style="margin:0 0 14px 0;font-size:{size}px;line-height:1.6;color:{color};">{h}</p>')
    return "".join(out)


def _button(label: str, href: str, secondary: bool = False) -> str:
    if not href:
        return ""
    bg, fg, border = (ACCENT, "#ffffff", ACCENT) if not secondary else ("#ffffff", ACCENT, ACCENT)
    return (
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:6px 0 4px 0;"><tr>'
        f'<td style="background:{bg};border:2px solid {border};border-radius:8px;">'
        f'<a href="{_esc(href)}" style="display:inline-block;padding:11px 22px;'
        f'font-family:{FONT};font-size:14px;font-weight:bold;color:{fg};text-decoration:none;">{_esc(label)}</a>'
        f"</td></tr></table>"
    )


def _section_title(t: str) -> str:
    return (
        f'<div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:{ACCENT};'
        f'font-weight:bold;margin:0 0 12px 0;">{_esc(t)}</div>'
    )


def _divider() -> str:
    return f'<tr><td style="padding:0 32px;"><div style="border-top:1px solid {LINE};height:1px;line-height:1px;">&nbsp;</div></td></tr>'


def _block(inner: str, bg: str = "") -> str:
    style = f"padding:26px 32px;font-family:{FONT};" + (f"background:{bg};" if bg else "")
    return f'<tr><td style="{style}">{inner}</td></tr>'


def _fmt_date(d) -> str:
    try:
        return date.fromisoformat(str(d)[:10]).strftime("%B %-d, %Y")
    except Exception:
        return str(d or "")


def render_issue(issue: dict, first_name: str = "", settings: Optional[dict] = None,
                 token: Optional[str] = None, videos: Optional[Dict[str, dict]] = None) -> str:
    """Full HTML for one recipient. `token` wraps every link for per-recipient
    tracking (None = preview, untracked). send_email() appends its own
    unsubscribe footer + open pixel before </body>."""
    s = settings or _settings()
    c = issue.get("content") or {}
    vids = videos if videos is not None else _videos_map()
    campaign = f"weekly-{issue.get('issue_date') or ''}"
    link = _Links(campaign, token)
    parts: List[str] = []

    # 1. Intro
    greet = f"Hey {first_name}," if first_name else "Hey there,"
    parts.append(_block(
        f'<p style="margin:0 0 14px 0;font-size:15px;line-height:1.6;color:{INK};">{_esc(greet)}</p>'
        + _rich(c.get("intro"), link)
    ))

    # 2. This week's class (the primary action: watch data is the best signal we get)
    cl = c.get("class") or {}
    v = vids.get(cl.get("video_slug") or "")
    if v:
        watch = link(f"{SITE}/watch?v={v['slug']}", "class")
        dur = _fmt_duration(v.get("duration_seconds"))
        thumb = f"https://i.ytimg.com/vi/{v['youtube_id']}/hqdefault.jpg"
        parts.append(_block(
            _section_title(cl.get("kicker") or "This week's class")
            + f'<a href="{_esc(watch)}"><img src="{_esc(thumb)}" width="536" alt="{_esc(v["title"])}" '
            f'style="display:block;width:100%;max-width:536px;height:auto;border:0;border-radius:10px;margin:0 0 14px 0;"></a>'
            + f'<div style="font-size:20px;font-weight:bold;color:{INK};margin:0 0 8px 0;line-height:1.3;">{_esc(cl.get("headline") or v["title"])}</div>'
            + _rich(cl.get("blurb") or v.get("description"), link)
            + _button((cl.get("cta_label") or "Watch the class") + (f" ({dur})" if dur else ""), watch)
        , bg=SOFT))

    # 3. Open trainings this week
    events = [e for e in (c.get("events") or []) if (e.get("title") or "").strip()]
    if events:
        rows = []
        for i, e in enumerate(events):
            edge = f"border-bottom:1px solid {LINE};" if i < len(events) - 1 else ""
            host = (e.get("host") or "").strip()
            badge = (
                f'<span style="display:inline-block;font-size:10px;font-weight:bold;letter-spacing:1px;'
                f'padding:3px 8px;border-radius:4px;background:#efeeff;color:{ACCENT};margin-bottom:6px;">'
                f"HOSTED BY {_esc(host.upper())}</span><br>"
                if host else ""
            )
            rows.append(
                f'<div style="padding:14px 0;{edge}">'
                f"{badge}"
                f'<div style="font-size:13px;color:{MUTED};font-weight:bold;margin-bottom:3px;">{_esc(e.get("when"))}</div>'
                f'<div style="font-size:17px;font-weight:bold;color:{INK};margin-bottom:6px;">{_esc(e.get("title"))}</div>'
                + (_rich(e.get("description"), link, size=14, color=MUTED) if e.get("description") else "")
                + (f'<a href="{_esc(link(e["url"], e.get("title") or "event"))}" style="font-size:14px;font-weight:bold;color:{ACCENT};text-decoration:none;">'
                   f'{_esc(e.get("cta_label") or "Register free")} &rarr;</a>' if e.get("url") else "")
                + "</div>"
            )
        schedule = ""
        if c.get("show_schedule_link", True):
            schedule = (
                f'<div style="margin-top:14px;padding:12px 14px;background:{SOFT};border-radius:8px;font-size:14px;color:{INK};">'
                f'Every open session and every class in one place: '
                f'<a href="{_esc(link(SITE + "/trainings", "full schedule"))}" style="color:{ACCENT};font-weight:bold;">see the full schedule &rarr;</a></div>'
            )
        parts.append(_block(
            _section_title(c.get("events_title") or "Free open trainings this week")
            + (_rich(c.get("events_intro"), link, size=14, color=MUTED) if c.get("events_intro") else "")
            + "".join(rows) + schedule
        ))
        parts.append(_divider())

    # 4. Number of the week (optional)
    n = c.get("numbers") or {}
    if (n.get("headline") or "").strip():
        stat = f'<div style="font-size:34px;font-weight:bold;color:{ACCENT};margin:0 0 6px 0;">{_esc(n.get("stat"))}</div>' if n.get("stat") else ""
        parts.append(_block(
            _section_title("The number of the week") + stat
            + f'<div style="font-size:19px;font-weight:bold;color:{INK};margin:0 0 10px 0;">{_esc(n.get("headline"))}</div>'
            + _rich(n.get("body"), link)
            + _button(n.get("cta_label") or "Run your own numbers", link(n.get("url") or f"{SITE}/compare", "numbers"), secondary=True)
        ))
        parts.append(_divider())

    # 5. From the blog
    posts = [p for p in (c.get("posts") or []) if (p.get("title") or "").strip() and p.get("url")]
    if posts:
        items = "".join(
            f'<div style="margin:0 0 14px 0;">'
            f'<a href="{_esc(link(p["url"], p["title"]))}" style="font-size:16px;font-weight:bold;color:{INK};text-decoration:underline;">{_esc(p["title"])}</a>'
            + (f'<div style="font-size:14px;line-height:1.55;color:{MUTED};margin-top:3px;">{_esc(p.get("blurb"))}</div>' if p.get("blurb") else "")
            + "</div>"
            for p in posts
        )
        parts.append(_block(_section_title("From the blog") + items))
        parts.append(_divider())

    # 6. Industry pulse (optional)
    news = [x for x in (c.get("news") or []) if (x.get("headline") or "").strip()]
    if news:
        items = []
        for x in news:
            head = _esc(x.get("headline"))
            if x.get("url"):
                head = f'<a href="{_esc(link(x["url"], "news"))}" style="color:{INK};text-decoration:underline;">{head}</a>'
            items.append(
                f'<div style="margin:0 0 14px 0;"><div style="font-size:16px;font-weight:bold;color:{INK};margin:0 0 4px 0;">{head}</div>'
                + (f'<div style="font-size:14px;line-height:1.55;color:{MUTED};"><strong style="color:{INK};">My take:</strong> {_esc(x.get("take"))}</div>' if x.get("take") else "")
                + "</div>"
            )
        parts.append(_block(_section_title("Industry pulse") + "".join(items)))
        parts.append(_divider())

    # 7. Free tools
    tools = [x for x in (c.get("tools") or DEFAULT_TOOLS) if (x.get("label") or "").strip() and x.get("url")]
    if tools:
        li = "".join(
            f'<li style="margin:0 0 8px 0;font-size:15px;"><a href="{_esc(link(x["url"], x["label"]))}" style="color:{ACCENT};">{_esc(x["label"])}</a></li>'
            for x in tools
        )
        parts.append(_block(_section_title("Free tools for any agent") + f'<ul style="margin:0;padding:0 0 0 18px;color:{INK};">{li}</ul>'))

    # 8. Book a 1-on-1
    bk = c.get("book") or {}
    parts.append(_block(
        f'<div style="font-size:20px;font-weight:bold;color:{INK};margin:0 0 10px 0;">{_esc(bk.get("headline") or "Want a straight answer on your numbers?")}</div>'
        + _rich(bk.get("body") or "Grab 15 minutes with me. Answer a few quick questions first so I can come prepared with your actual numbers, not a pitch.", link)
        + _button(bk.get("cta_label") or "Book a 1-on-1 with Joe", link(f"{SITE}/book", "book 1-on-1"))
    , bg=SOFT))

    # 9. Sign-off, socials, P.S.
    socials = [x for x in (s.get("socials") or []) if x.get("url") and x.get("label")]
    social_html = ""
    if socials:
        social_html = (
            f'<p style="margin:14px 0 0 0;font-size:13px;color:{MUTED};">Follow along: '
            + " &middot; ".join(f'<a href="{_esc(link(x["url"], x["label"]))}" style="color:{ACCENT};">{_esc(x["label"])}</a>' for x in socials)
            + "</p>"
        )
    ps = (c.get("ps") or "").strip()
    parts.append(_block(
        f'<p style="margin:0;font-size:15px;line-height:1.5;color:{INK};">{_esc(s.get("sender_name"))}<br>'
        f'<span style="color:{MUTED};font-size:13px;">{_esc(s.get("sender_title"))}</span></p>'
        + social_html
        + (f'<div style="margin-top:18px;">{_rich("**P.S.** " + ps, link, size=14)}</div>' if ps else "")
    ))

    addr = _esc(s.get("mailing_address") or "")
    footer = (
        f'<tr><td style="padding:18px 32px 8px 32px;font-family:{FONT};font-size:11px;line-height:1.5;color:#8a8aa0;text-align:center;">'
        "TPL Collective is an agent community, not a brokerage. Trainings marked Hosted by LPT Realty are run by LPT Realty and open to any agent."
        + (f"<br>{addr}" if addr else "")
        + "</td></tr>"
    )
    header = (
        f'<tr><td style="padding:28px 32px 4px 32px;font-family:{FONT};">'
        f'<div style="font-size:22px;font-weight:bold;letter-spacing:2px;color:{INK};">TPL<span style="color:{ACCENT};">.</span></div>'
        f'<div style="font-size:11px;letter-spacing:3px;text-transform:uppercase;color:{MUTED};margin-top:2px;">The Weekly'
        + (f" &middot; {_esc(_fmt_date(issue.get('issue_date')))}" if issue.get("issue_date") else "")
        + "</div></td></tr>"
    )
    preheader = _esc(issue.get("preheader") or "")

    return (
        '<!DOCTYPE html><html><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_esc(issue.get('subject'))}</title></head>"
        f'<body style="margin:0;padding:0;background:#f4f4f8;">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:#f4f4f8;">{preheader}</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f4f4f8;"><tr><td align="center" style="padding:24px 12px;">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;">'
        + header + "".join(parts) + footer
        + "</table></td></tr></table></body></html>"
    )


def _assert_clean(html_body: str):
    """Last line of defense against the {first_name} class of incident."""
    if re.search(r"\{\{|\}\}|\{first_name\}|\{name\}", html_body):
        raise HTTPException(400, "Rendered email still contains an unfilled {placeholder}. Fix the content before sending.")


# ════════════════════════════════════════════════════════════
# Issue helpers
# ════════════════════════════════════════════════════════════

def _get_issue(issue_id: int) -> dict:
    r = _t("recruit_newsletter_issues").select("*").eq("id", issue_id).eq("workspace_id", WS).limit(1).execute()
    if not r.data:
        raise HTTPException(404, "Issue not found")
    return r.data[0]


def _next_monday(from_d: Optional[date] = None) -> date:
    d = from_d or date.today()
    return d + timedelta(days=(7 - d.weekday()) % 7 or 7)


def _counts(issue_id: int) -> dict:
    out = {"queued": 0, "sent": 0, "failed": 0, "skipped": 0}
    for st in out:
        r = (
            _t("recruit_newsletter_sends").select("id", count="exact")
            .eq("issue_id", issue_id).eq("status", st).limit(1).execute()
        )
        out[st] = r.count or 0
    return out


def _opens(issue: dict) -> int:
    try:
        r = (
            _t("email_send_log").select("id", count="exact")
            .eq("campaign", f"weekly-{issue['issue_date']}")
            .in_("status", ["opened", "clicked"])
            .limit(1).execute()
        )
        return r.count or 0
    except Exception:
        return 0


def _blank_content(issue_date: str) -> dict:
    s = _settings()
    return {
        "intro": "",
        "class": {"video_slug": "", "kicker": "This week's class", "headline": "", "blurb": "", "cta_label": "Watch the class"},
        "events_title": "Free open trainings this week",
        "events_intro": "",
        "events": _week_events(issue_date, s.get("recurring_events") or []),
        "show_schedule_link": True,
        "numbers": {"stat": "", "headline": "", "body": "", "cta_label": "Run your own numbers", "url": f"{SITE}/compare"},
        "posts": [],
        "news": [],
        "tools": list(DEFAULT_TOOLS),
        "book": {"headline": "", "body": "", "cta_label": "Book a 1-on-1 with Joe"},
        "ps": "",
    }


# ════════════════════════════════════════════════════════════
# Admin endpoints: settings + audience
# ════════════════════════════════════════════════════════════

@router.get("/settings")
def get_settings():
    return _settings()


@router.put("/settings")
def put_settings(body: SettingsIn):
    from main import load_settings, save_settings
    all_s = load_settings() or {}
    cur = all_s.get("recruit_newsletter") or {}
    for k, v in body.dict(exclude_none=True).items():
        cur[k] = v.strip() if isinstance(v, str) else v
    all_s["recruit_newsletter"] = cur
    save_settings(all_s)
    return _settings()


@router.get("/audience")
def audience_summary():
    rows = _audience()
    buckets: dict = {}
    for r in rows:
        buckets[r["bucket"]] = buckets.get(r["bucket"], 0) + 1
    return {
        "total": len(rows),
        "with_first_name": sum(1 for r in rows if r["first_name"]),
        "by_brokerage": dict(sorted(buckets.items(), key=lambda kv: -kv[1])),
    }


# ════════════════════════════════════════════════════════════
# Admin endpoints: issues
# ════════════════════════════════════════════════════════════

@router.get("/issues")
def list_issues():
    rows = (
        _t("recruit_newsletter_issues")
        .select("id, issue_date, subject, status, scheduled_for, approved_at, test_sent_at, total_recipients, sent_count, failed_count, skipped_count, completed_at, updated_at")
        .eq("workspace_id", WS).order("issue_date", desc=True).limit(100).execute().data
        or []
    )
    return {"issues": rows}


@router.get("/issues/{issue_id}")
def get_issue(issue_id: int):
    issue = _get_issue(issue_id)
    issue["counts"] = _counts(issue_id)
    issue["opens"] = _opens(issue)
    ts, cu = _parse_ts(issue.get("test_sent_at")), _parse_ts(issue.get("content_updated_at"))
    issue["test_is_current"] = bool(ts and cu and ts >= cu)
    return issue


@router.post("/issues")
def create_issue(body: IssueIn, request: Request):
    d = body.issue_date or _next_monday().isoformat()
    row = {
        "workspace_id": WS,
        "issue_date": d,
        "subject": (body.subject or "").strip(),
        "preheader": (body.preheader or "").strip(),
        "content": body.content or _blank_content(d),
        "daily_cap": int(_settings().get("default_daily_cap") or 150),
        "created_by": _user(request).get("sub"),
    }
    return _t("recruit_newsletter_issues").insert(row).execute().data[0]


@router.post("/issues/{issue_id}/duplicate")
def duplicate_issue(issue_id: int, request: Request):
    """Start next week's issue from this one: date +7, evergreen sections kept.
    Events are regenerated from the recurring list for the new week, and dated
    items (class, news, P.S.) are cleared so last week's can't go out again."""
    src = _get_issue(issue_id)
    try:
        new_date = (date.fromisoformat(str(src["issue_date"])[:10]) + timedelta(days=7)).isoformat()
    except Exception:
        new_date = _next_monday().isoformat()
    content = json.loads(json.dumps(src.get("content") or {}))
    content["events"] = _week_events(new_date, _settings().get("recurring_events") or [])
    content["news"] = []
    content["class"] = {**(content.get("class") or {}), "video_slug": "", "headline": "", "blurb": ""}
    content["ps"] = ""
    row = {
        "workspace_id": WS,
        "issue_date": new_date,
        "subject": "",
        "preheader": "",
        "content": content,
        "daily_cap": src.get("daily_cap") or 150,
        "created_by": _user(request).get("sub"),
    }
    return _t("recruit_newsletter_issues").insert(row).execute().data[0]


@router.get("/week-events")
def week_events(issue_date: str):
    """Recurring events for a given week, for the editor's 'reload' button."""
    return {"events": _week_events(issue_date, _settings().get("recurring_events") or [])}


@router.patch("/issues/{issue_id}")
def update_issue(issue_id: int, body: IssueIn):
    issue = _get_issue(issue_id)
    if issue["status"] != "draft":
        raise HTTPException(409, "Only drafts can be edited. Unapprove it first (only possible before sending starts).")
    upd = {}
    if body.issue_date is not None:
        upd["issue_date"] = body.issue_date
    if body.subject is not None:
        upd["subject"] = body.subject.strip()
    if body.preheader is not None:
        upd["preheader"] = body.preheader.strip()
    if body.content is not None:
        upd["content"] = body.content
    if not upd:
        return issue
    # any content-visible change invalidates the last test
    upd["content_updated_at"] = _iso(_now())
    return _t("recruit_newsletter_issues").update(upd).eq("id", issue_id).eq("workspace_id", WS).execute().data[0]


@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int):
    issue = _get_issue(issue_id)
    if issue["status"] != "draft":
        raise HTTPException(409, "Only drafts can be deleted. Cancel a scheduled issue instead.")
    _t("recruit_newsletter_issues").delete().eq("id", issue_id).eq("workspace_id", WS).execute()
    return {"ok": True}


@router.get("/issues/{issue_id}/preview", response_class=HTMLResponse)
def preview_issue(issue_id: int, first_name: str = "Sharon"):
    return HTMLResponse(render_issue(_get_issue(issue_id), first_name=first_name))


# ════════════════════════════════════════════════════════════
# Admin endpoints: review gate
# ════════════════════════════════════════════════════════════

def _validate_sendable(issue: dict, videos: Dict[str, dict]):
    if not (issue.get("subject") or "").strip():
        raise HTTPException(400, "Add a subject line first.")
    c = issue.get("content") or {}
    if not (c.get("intro") or "").strip():
        raise HTTPException(400, "Add an intro first.")
    slug = (c.get("class") or {}).get("video_slug")
    if slug:
        v = videos.get(slug)
        if not v:
            raise HTTPException(400, f"This week's class '{slug}' no longer exists. Pick another or clear it.")
        if not v.get("published"):
            raise HTTPException(400, f"This week's class '{v['title']}' is unpublished, so the watch page would 404.")


@router.post("/issues/{issue_id}/test")
def send_test(issue_id: int, body: TestIn, request: Request):
    from main import send_email
    issue = _get_issue(issue_id)
    vids = _videos_map()
    _validate_sendable(issue, vids)
    to = (body.to or _user(request).get("email") or "").strip()
    if not to or "@" not in to or to.startswith("system@"):
        raise HTTPException(400, "No test recipient. Pass 'to'.")
    s = _settings()
    # TEST_TOKEN: links go through the real redirect so the flow can be checked, but nothing is logged
    html_body = render_issue(issue, first_name="Joe", settings=s, token=TEST_TOKEN, videos=vids)
    _assert_clean(html_body)
    ok, err = send_email(
        _smtp_cfg(), to, "[TEST] " + issue["subject"], html_body,
        from_address=s["from_address"], campaign="weekly-test", reply_to=s["reply_to"],
    )
    if not ok:
        raise HTTPException(502, f"Test send failed: {err}")
    _t("recruit_newsletter_issues").update({"test_sent_at": _iso(_now()), "test_sent_to": to}).eq("id", issue_id).execute()
    return {"ok": True, "sent_to": to}


@router.post("/issues/{issue_id}/approve")
def approve_issue(issue_id: int, body: ApproveIn, request: Request):
    issue = _get_issue(issue_id)
    if issue["status"] != "draft":
        raise HTTPException(409, f"Issue is {issue['status']}, not draft.")
    vids = _videos_map()
    _validate_sendable(issue, vids)

    ts, cu = _parse_ts(issue.get("test_sent_at")), _parse_ts(issue.get("content_updated_at"))
    if not ts or not cu or ts < cu:
        raise HTTPException(409, "Send yourself a test of the current version before approving. It was edited after the last test.")

    s = _settings()
    if not (s.get("mailing_address") or "").strip():
        raise HTTPException(400, "Set a mailing address in Weekly Email settings first. Bulk email must include one (CAN-SPAM).")
    if not _secret():
        raise HTTPException(500, "JWT_SECRET is not set, so links can't be signed for click tracking.")

    # a stray placeholder must fail here, not mid-batch
    _assert_clean(render_issue(issue, first_name="Test", settings=s, token=TEST_TOKEN, videos=vids))

    when = _parse_ts(body.scheduled_for) if body.scheduled_for else _now()
    if not when:
        raise HTTPException(400, "scheduled_for is not a valid ISO timestamp.")

    recipients = _audience()
    if not recipients:
        raise HTTPException(400, "Audience is empty.")

    # snapshot the audience; the unique index makes a retried approve harmless
    for i in range(0, len(recipients), 200):
        chunk = [
            {"workspace_id": WS, "issue_id": issue_id, "lead_id": r["lead_id"], "email": r["email"],
             "first_name": r["first_name"] or None, "token": str(uuid.uuid4())}
            for r in recipients[i:i + 200]
        ]
        _insert_ignore_dupes(chunk)

    upd = {
        "status": "approved",
        "approved_at": _iso(_now()),
        "approved_by": _user(request).get("sub"),
        "scheduled_for": _iso(when),
        "total_recipients": _counts(issue_id)["queued"],
    }
    if body.daily_cap:
        upd["daily_cap"] = max(1, int(body.daily_cap))
    return _t("recruit_newsletter_issues").update(upd).eq("id", issue_id).execute().data[0]


def _insert_ignore_dupes(rows: List[dict]):
    """The unique index is on lower(email), which PostgREST upsert can't target,
    so insert and fall back to row-by-row on a conflict."""
    try:
        _t("recruit_newsletter_sends").insert(rows).execute()
    except Exception:
        for r in rows:
            try:
                _t("recruit_newsletter_sends").insert(r).execute()
            except Exception:
                pass


@router.post("/issues/{issue_id}/unapprove")
def unapprove_issue(issue_id: int):
    issue = _get_issue(issue_id)
    if issue["status"] != "approved":
        raise HTTPException(409, f"Issue is {issue['status']}; only an approved issue that has not started sending can go back to draft.")
    c = _counts(issue_id)
    if c["sent"] or c["failed"]:
        raise HTTPException(409, "Sending already started. Cancel instead.")
    _t("recruit_newsletter_sends").delete().eq("issue_id", issue_id).eq("status", "queued").execute()
    return _t("recruit_newsletter_issues").update({
        "status": "draft", "approved_at": None, "approved_by": None, "scheduled_for": None, "total_recipients": 0,
    }).eq("id", issue_id).execute().data[0]


@router.post("/issues/{issue_id}/cancel")
def cancel_issue(issue_id: int):
    issue = _get_issue(issue_id)
    if issue["status"] not in ("approved", "sending"):
        raise HTTPException(409, f"Issue is {issue['status']}; nothing to cancel.")
    _t("recruit_newsletter_sends").update({"status": "skipped", "error": "cancelled"}) \
        .eq("issue_id", issue_id).eq("status", "queued").execute()
    c = _counts(issue_id)
    return _t("recruit_newsletter_issues").update({
        "status": "cancelled", "sent_count": c["sent"], "failed_count": c["failed"], "skipped_count": c["skipped"],
        "completed_at": _iso(_now()), "processing_until": None,
    }).eq("id", issue_id).execute().data[0]


@router.get("/issues/{issue_id}/sends")
def list_sends(issue_id: int, status: Optional[str] = None):
    q = _t("recruit_newsletter_sends").select("id, lead_id, email, first_name, status, error, sent_at").eq("issue_id", issue_id)
    if status:
        q = q.eq("status", status)
    return {"sends": q.order("id").limit(1000).execute().data or []}


@router.get("/issues/{issue_id}/engagement")
def issue_engagement(issue_id: int):
    """Who did something with this issue: clicked (bots excluded), watched, booked.
    Hottest first: booked, then deepest watch, then most clicks."""
    _get_issue(issue_id)
    sends = {s["id"]: s for s in (_t("recruit_newsletter_sends").select("id, lead_id, email, first_name, status")
                                   .eq("issue_id", issue_id).execute().data or [])}
    clicks = _t("recruit_newsletter_clicks").select("*").eq("issue_id", issue_id).execute().data or []
    watches = _t("video_watch_sessions").select("*").eq("issue_id", issue_id).execute().data or []
    bookings = _t("booking_requests").select("*").eq("issue_id", issue_id).execute().data or []

    people: Dict[int, dict] = {}

    def person(send_id):
        s = sends.get(send_id) or {}
        if send_id not in people:
            people[send_id] = {"send_id": send_id, "lead_id": s.get("lead_id"), "email": s.get("email"),
                               "first_name": s.get("first_name"), "clicks": [], "video_pct": 0,
                               "video_seconds": 0, "booked": False}
        return people[send_id]

    bot_clicks = 0
    for c in clicks:
        if c.get("suspected_bot"):
            bot_clicks += 1
            continue
        person(c["send_id"])["clicks"].append({"label": c.get("label"), "url": c.get("url"), "at": c.get("clicked_at")})
    for w in watches:
        if not w.get("send_id"):
            continue
        p = person(w["send_id"])
        p["video_pct"] = max(p["video_pct"], w.get("pct") or 0)
        p["video_seconds"] = max(p["video_seconds"], w.get("watched_seconds") or 0)
    for b in bookings:
        if b.get("send_id"):
            person(b["send_id"])["booked"] = True

    rows = sorted(people.values(), key=lambda p: (not p["booked"], -p["video_pct"], -len(p["clicks"])))
    return {
        "totals": {
            "clickers": sum(1 for p in rows if p["clicks"]),
            "clicks": sum(len(p["clicks"]) for p in rows),
            "bot_clicks_excluded": bot_clicks,
            "watchers": sum(1 for p in rows if p["video_pct"] > 0),
            "watched_half": sum(1 for p in rows if p["video_pct"] >= 50),
            "bookings": sum(1 for p in rows if p["booked"]),
        },
        "people": rows,
    }


# ════════════════════════════════════════════════════════════
# Admin endpoints: classes (videos)
# ════════════════════════════════════════════════════════════

@router.get("/videos")
def list_videos():
    vids = _t("tpl_videos").select("*").eq("workspace_id", WS).order("created_at", desc=True).execute().data or []
    sessions = _t("video_watch_sessions").select("video_slug, lead_id, pct").eq("workspace_id", WS).execute().data or []
    for v in vids:
        mine = [s for s in sessions if s["video_slug"] == v["slug"]]
        v["views"] = len(mine)
        v["known_viewers"] = len({s["lead_id"] for s in mine if s.get("lead_id")})
        v["watched_half"] = len({s["lead_id"] for s in mine if s.get("lead_id") and (s.get("pct") or 0) >= 50})
    return {"videos": vids}


@router.post("/videos")
def create_video(body: VideoIn):
    yid = _youtube_id(body.youtube_url or "")
    if not yid:
        raise HTTPException(400, "That doesn't look like a YouTube link. Paste the video's URL (youtube.com/watch?v=... or youtu.be/...).")
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(400, "Give the class a title.")
    slug = _slugify(body.slug or title)
    if not slug or not _SLUG_RE.match(slug):
        raise HTTPException(400, "Could not make a URL slug from that title.")
    if _t("tpl_videos").select("id").eq("slug", slug).limit(1).execute().data:
        raise HTTPException(409, f"A class with the slug '{slug}' already exists.")
    row = {"workspace_id": WS, "slug": slug, "youtube_id": yid, "title": title,
           "description": (body.description or "").strip(),
           "published": True if body.published is None else bool(body.published)}
    if body.duration_seconds:
        row["duration_seconds"] = int(body.duration_seconds)
    return _t("tpl_videos").insert(row).execute().data[0]


@router.patch("/videos/{slug}")
def update_video(slug: str, body: VideoIn):
    upd = {}
    if body.title is not None:
        upd["title"] = body.title.strip()
    if body.description is not None:
        upd["description"] = body.description.strip()
    if body.published is not None:
        upd["published"] = bool(body.published)
    if body.duration_seconds is not None:
        upd["duration_seconds"] = int(body.duration_seconds) or None
    if body.youtube_url:
        yid = _youtube_id(body.youtube_url)
        if not yid:
            raise HTTPException(400, "That doesn't look like a YouTube link.")
        upd["youtube_id"] = yid
    if not upd:
        raise HTTPException(400, "Nothing to update.")
    r = _t("tpl_videos").update(upd).eq("slug", slug).eq("workspace_id", WS).execute().data
    if not r:
        raise HTTPException(404, "Class not found")
    return r[0]


@router.delete("/videos/{slug}")
def delete_video(slug: str):
    used = _t("recruit_newsletter_issues").select("id, content, status").eq("workspace_id", WS).execute().data or []
    for i in used:
        if ((i.get("content") or {}).get("class") or {}).get("video_slug") == slug:
            raise HTTPException(409, "An issue uses this class, and old emails still link to it. Unpublish it instead.")
    _t("tpl_videos").delete().eq("slug", slug).eq("workspace_id", WS).execute()
    return {"ok": True}


@router.get("/videos/{slug}/viewers")
def video_viewers(slug: str):
    sessions = _t("video_watch_sessions").select("*").eq("video_slug", slug).eq("workspace_id", WS).execute().data or []
    best: Dict[Any, dict] = {}
    anonymous = 0
    for s in sessions:
        if not s.get("lead_id"):
            anonymous += 1
            continue
        b = best.get(s["lead_id"])
        if not b or (s.get("pct") or 0) > b["pct"]:
            best[s["lead_id"]] = {"lead_id": s["lead_id"], "pct": s.get("pct") or 0,
                                  "watched_seconds": s.get("watched_seconds") or 0, "last_seen_at": s.get("last_seen_at")}
    ids = list(best.keys())
    names = {}
    if ids:
        for l in _t("leads").select("id, name, first_name, email, current_brokerage").in_("id", ids).execute().data or []:
            names[l["id"]] = l
    rows = []
    for lid, b in best.items():
        l = names.get(lid) or {}
        rows.append({**b, "name": l.get("name") or l.get("first_name"), "email": l.get("email"), "brokerage": l.get("current_brokerage")})
    rows.sort(key=lambda r: -r["pct"])
    return {"viewers": rows, "anonymous_sessions": anonymous}


# ════════════════════════════════════════════════════════════
# Processor (cron, loopback, every 15 minutes)
# ════════════════════════════════════════════════════════════

def _claim(issue_id: int) -> bool:
    now = _now()
    r = (
        _t("recruit_newsletter_issues")
        .update({"processing_until": _iso(now + timedelta(minutes=LEASE_MINUTES))})
        .eq("id", issue_id)
        .in_("status", ["approved", "sending"])
        .or_(f"processing_until.is.null,processing_until.lt.{_iso(now)}")
        .execute()
    )
    return bool(r.data)


def _process_issue(issue: dict) -> dict:
    from main import send_email
    iid = issue["id"]
    s = _settings()
    smtp = _smtp_cfg()
    vids = _videos_map()
    day_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = (
        _t("recruit_newsletter_sends").select("id", count="exact")
        .eq("issue_id", iid).eq("status", "sent").gte("sent_at", _iso(day_start)).limit(1).execute().count
        or 0
    )
    budget = min(PER_RUN_CAP, max(0, int(issue.get("daily_cap") or 150) - sent_today))
    result = {"issue_id": iid, "sent": 0, "failed": 0, "skipped": 0, "stopped": ""}
    if budget <= 0:
        result["stopped"] = "daily cap reached"
    else:
        queued = (
            _t("recruit_newsletter_sends").select("*")
            .eq("issue_id", iid).eq("status", "queued").order("id").limit(budget).execute().data
            or []
        )
        campaign = f"weekly-{issue['issue_date']}"
        for row in queued:
            html_body = render_issue(issue, first_name=row.get("first_name") or "", settings=s,
                                     token=str(row.get("token") or ""), videos=vids)
            try:
                _assert_clean(html_body)
            except HTTPException as e:
                result["stopped"] = e.detail
                break
            ok, err = send_email(
                smtp, row["email"], issue["subject"], html_body,
                from_address=s["from_address"], contact_id=row.get("lead_id"),
                campaign=campaign, reply_to=s["reply_to"],
            )
            if ok:
                _t("recruit_newsletter_sends").update({"status": "sent", "sent_at": _iso(_now()), "error": None}).eq("id", row["id"]).execute()
                result["sent"] += 1
                if row.get("lead_id"):
                    try:
                        _t("lead_activity").insert({
                            "workspace_id": WS, "lead_id": row["lead_id"], "activity_type": "newsletter_sent",
                            "description": f"Weekly email sent: {issue['subject']}",
                            "metadata": {"issue_id": iid},
                        }).execute()
                    except Exception:
                        pass
            elif (err or "").startswith("Email suppressed"):
                _t("recruit_newsletter_sends").update({"status": "skipped", "error": "suppressed"}).eq("id", row["id"]).execute()
                result["skipped"] += 1
            elif (err or "").startswith("Daily send limit"):
                # domain-wide cap shared with every other sender; leave queued for tomorrow
                result["stopped"] = err
                break
            elif "not configured" in (err or ""):
                result["stopped"] = err
                break
            else:
                _t("recruit_newsletter_sends").update({"status": "failed", "error": (err or "")[:500]}).eq("id", row["id"]).execute()
                result["failed"] += 1
            time.sleep(SEND_SPACING_SEC)

    c = _counts(iid)
    upd = {
        "sent_count": c["sent"], "failed_count": c["failed"], "skipped_count": c["skipped"],
        "processing_until": None,
        "status": "sending",
    }
    if c["queued"] == 0:
        upd["status"] = "sent"
        upd["completed_at"] = _iso(_now())
    # conditional so a cancel that landed mid-run is not flipped back to "sending"
    _t("recruit_newsletter_issues").update(upd).eq("id", iid).in_("status", ["approved", "sending"]).execute()
    result["remaining"] = c["queued"]
    return result


@router.post("/process")
def process_due():
    """Drain every approved issue whose send time has arrived. Safe to call often."""
    due = (
        _t("recruit_newsletter_issues").select("*")
        .eq("workspace_id", WS).in_("status", ["approved", "sending"])
        .lte("scheduled_for", _iso(_now())).order("scheduled_for").execute().data
        or []
    )
    results = []
    for issue in due:
        if not _claim(issue["id"]):
            results.append({"issue_id": issue["id"], "stopped": "another run holds the lease"})
            continue
        try:
            results.append(_process_issue(issue))
        except Exception as e:
            _t("recruit_newsletter_issues").update({"processing_until": None}).eq("id", issue["id"]).execute()
            results.append({"issue_id": issue["id"], "error": str(e)[:300]})
    return {"ok": True, "processed": results}


# ════════════════════════════════════════════════════════════
# Shared lookups for the public side
# ════════════════════════════════════════════════════════════

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _send_for_token(token: Optional[str]) -> Optional[dict]:
    if not token or not _UUID_RE.match(token):
        return None
    r = _t("recruit_newsletter_sends").select("id, issue_id, lead_id, email, first_name").eq("token", token.lower()).limit(1).execute()
    return r.data[0] if r.data else None


def _activity(lead_id, kind: str, description: str, metadata: Optional[dict] = None):
    if not lead_id:
        return
    try:
        _t("lead_activity").insert({"workspace_id": WS, "lead_id": lead_id, "activity_type": kind,
                                    "description": description, "metadata": metadata or {}}).execute()
    except Exception:
        pass


def _notify(subject: str, rows: List[tuple], campaign: str):
    """Internal alert to Joe through the standard send_email rail."""
    try:
        from main import send_email
        s = _settings()
        to = s.get("notify_email") or s.get("reply_to")
        if not to:
            return
        body = "".join(
            f'<tr><td style="padding:6px 12px 6px 0;color:#666;font-size:13px;vertical-align:top;">{_esc(k)}</td>'
            f'<td style="padding:6px 0;font-size:14px;color:#1a1a2e;">{_esc(v)}</td></tr>'
            for k, v in rows if v not in (None, "", [])
        )
        html_body = (
            f'<div style="font-family:{FONT};max-width:560px;margin:0 auto;padding:24px;">'
            f'<h2 style="color:{ACCENT};margin:0 0 16px 0;font-size:18px;">{_esc(subject)}</h2>'
            f'<table style="border-collapse:collapse;">{body}</table>'
            f'<p style="margin-top:20px;"><a href="https://mission.tplcollective.ai/#contacts" style="color:{ACCENT};">Open Mission Control</a></p></div>'
        )
        send_email(_smtp_cfg(), to, subject, html_body, from_address=s["from_address"], campaign=campaign)
    except Exception as e:
        print(f"[weekly] notify failed: {e}")


# ════════════════════════════════════════════════════════════
# Tracking: click redirect
# ════════════════════════════════════════════════════════════

BOT_WINDOW_SEC = 15


@tracking_router.get("/c/{token}")
def click(token: str, request: Request, u: str = "", s: str = "", l: str = ""):
    safe_home = SITE + "/"
    if not u or not u.startswith(("https://", "http://")):
        return RedirectResponse(safe_home, status_code=302)
    # only follow URLs we signed; otherwise this is an open redirect
    if not _secret() or not hmac.compare_digest(_sign(token, u), s or ""):
        return RedirectResponse(safe_home, status_code=302)
    if token == TEST_TOKEN:
        return RedirectResponse(u, status_code=302)
    try:
        send = _send_for_token(token)
        if send:
            now = _now()
            ua = (request.headers.get("user-agent") or "")[:300]
            # link scanners open every link within seconds of each other
            recent = (
                _t("recruit_newsletter_clicks").select("id, url")
                .eq("send_id", send["id"]).gte("clicked_at", _iso(now - timedelta(seconds=BOT_WINDOW_SEC)))
                .execute().data or []
            )
            distinct_recent = {r["url"] for r in recent if r["url"] != u}
            is_bot = len(distinct_recent) >= 2
            _t("recruit_newsletter_clicks").insert({
                "workspace_id": WS, "issue_id": send["issue_id"], "send_id": send["id"], "lead_id": send.get("lead_id"),
                "url": u[:1000], "label": (l or "")[:80], "suspected_bot": is_bot, "user_agent": ua,
                "clicked_at": _iso(now),
            }).execute()
            if is_bot:
                ids = [r["id"] for r in recent]
                if ids:
                    _t("recruit_newsletter_clicks").update({"suspected_bot": True}).in_("id", ids).execute()
            else:
                _activity(send.get("lead_id"), "newsletter_click",
                          f"Clicked \"{(l or u)[:60]}\" in the weekly email",
                          {"issue_id": send["issue_id"], "url": u[:500]})
    except Exception as e:
        print(f"[weekly] click log failed: {e}")
    return RedirectResponse(u, status_code=302)


# ════════════════════════════════════════════════════════════
# Tracking: video heartbeat from tplcollective.ai/watch
# ════════════════════════════════════════════════════════════

_SID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


@tracking_router.post("/video")
async def video_heartbeat(request: Request):
    # sent as text/plain (sendBeacon / keepalive fetch) to avoid a CORS preflight
    try:
        data = json.loads((await request.body()) or b"{}")
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)
    slug = str(data.get("v") or "")
    sid = str(data.get("sid") or "")
    if not _SLUG_RE.match(slug) or not _SID_RE.match(sid):
        return JSONResponse({"ok": False}, status_code=400)

    def _int(k, hi=36000):
        try:
            return max(0, min(hi, int(float(data.get(k) or 0))))
        except Exception:
            return 0

    watched, pos, dur = _int("watched"), _int("pos"), _int("dur")
    # the heavy lifting is sync Supabase I/O; run it off the event loop
    import asyncio
    res = await asyncio.get_running_loop().run_in_executor(
        None, _record_watch, slug, sid, str(data.get("t") or ""), watched, pos, dur,
        (request.headers.get("user-agent") or "")[:300])
    return JSONResponse(res)


def _record_watch(slug: str, sid: str, token: str, watched: int, pos: int, dur: int, ua: str) -> dict:
    vid = (_t("tpl_videos").select("*").eq("slug", slug).limit(1).execute().data or [None])[0]
    if not vid:
        return {"ok": False}
    if dur and not vid.get("duration_seconds"):
        try:
            _t("tpl_videos").update({"duration_seconds": dur}).eq("id", vid["id"]).execute()
        except Exception:
            pass
    duration = dur or vid.get("duration_seconds") or 0
    send = None if token == TEST_TOKEN else _send_for_token(token)
    lead_id = send.get("lead_id") if send else None

    prev_best = 0
    if lead_id:
        rows = _t("video_watch_sessions").select("pct").eq("lead_id", lead_id).eq("video_slug", slug).execute().data or []
        prev_best = max([r.get("pct") or 0 for r in rows] or [0])

    existing = (_t("video_watch_sessions").select("*").eq("session_id", sid).limit(1).execute().data or [None])[0]
    if existing and existing["video_slug"] != slug:
        return {"ok": False}
    watched = max(watched, (existing or {}).get("watched_seconds") or 0)
    pct = min(100, round(watched * 100 / duration)) if duration else 0
    row = {
        "watched_seconds": watched,
        "max_position": max(pos, (existing or {}).get("max_position") or 0),
        "duration": duration,
        "pct": pct,
        "last_seen_at": _iso(_now()),
    }
    if existing:
        _t("video_watch_sessions").update(row).eq("id", existing["id"]).execute()
    else:
        _t("video_watch_sessions").insert({
            **row, "workspace_id": WS, "session_id": sid, "video_slug": slug,
            "send_id": send["id"] if send else None, "issue_id": send["issue_id"] if send else None,
            "lead_id": lead_id, "user_agent": ua,
        }).execute()
        if lead_id:
            _activity(lead_id, "video_started", f"Started watching \"{vid['title']}\"", {"video": slug})

    if lead_id:
        for m in VIDEO_MILESTONES:
            if prev_best < m <= pct:
                _activity(lead_id, "video_watched", f"Watched {m}% of \"{vid['title']}\"", {"video": slug, "pct": m})
                if m == VIDEO_ALERT_AT:
                    lead = (_t("leads").select("name, first_name, email, current_brokerage, phone").eq("id", lead_id).limit(1).execute().data or [{}])[0]
                    _notify(
                        f"{lead.get('name') or send.get('email')} watched half of \"{vid['title']}\"",
                        [("Agent", lead.get("name") or lead.get("first_name")), ("Email", lead.get("email")),
                         ("Phone", lead.get("phone")), ("Brokerage", lead.get("current_brokerage")),
                         ("Class", vid["title"]), ("Watched so far", f"{pct}%")],
                        "weekly-video-alert",
                    )
    return {"ok": True, "pct": pct}


# ════════════════════════════════════════════════════════════
# Public: classes, trainings page, recipient prefill, booking form
# ════════════════════════════════════════════════════════════

def _public_video(v: dict) -> dict:
    return {"slug": v["slug"], "youtube_id": v["youtube_id"], "title": v["title"],
            "description": v.get("description") or "", "duration_seconds": v.get("duration_seconds")}


@public_router.get("/videos")
def public_videos():
    vids = (_t("tpl_videos").select("*").eq("workspace_id", WS).eq("published", True)
            .order("created_at", desc=True).execute().data or [])
    return {"videos": [_public_video(v) for v in vids]}


@public_router.get("/videos/{slug}")
def public_video(slug: str):
    v = (_t("tpl_videos").select("*").eq("slug", slug).eq("published", True).limit(1).execute().data or [None])[0]
    if not v:
        raise HTTPException(404, "Class not found")
    return _public_video(v)


@public_router.get("/trainings")
def public_trainings():
    s = _settings()
    now_et = _now().astimezone(_ET)
    events = []
    for ev in s.get("recurring_events") or []:
        if not ev.get("active"):
            continue
        nxt = _next_occurrence(ev, now_et)
        try:
            wd = WEEKDAYS[int(ev.get("weekday"))]
        except Exception:
            continue
        events.append({
            "key": ev.get("key"), "title": ev.get("title"), "host": ev.get("host"),
            "description": ev.get("description"), "url": ev.get("url"),
            "day": wd, "time": _fmt_range(ev.get("start"), ev.get("end")),
            "next": nxt.isoformat() if nxt else None,
        })
    events.sort(key=lambda e: e["next"] or "")
    return {"events": events, "videos": public_videos()["videos"], "socials": s.get("socials") or []}


@public_router.get("/recipient")
def public_recipient(t: str = ""):
    """Prefill for /book. Only what the recipient already knows about themselves."""
    send = _send_for_token(t)
    if not send:
        return {"known": False}
    lead = {}
    if send.get("lead_id"):
        lead = (_t("leads").select("first_name, last_name, name, current_brokerage")
                .eq("id", send["lead_id"]).limit(1).execute().data or [{}])[0]
    first = _first_name(lead) if lead else ""
    first = first or send.get("first_name") or ""
    last = lead.get("last_name") or ""
    full = (lead.get("name") or "").strip()
    if not last and full and first and full.lower().startswith(first.lower() + " "):
        last = full[len(first) + 1:]
    return {"known": True, "first_name": first, "last_name": last, "email": send.get("email") or "",
            "current_brokerage": lead.get("current_brokerage") or ""}
