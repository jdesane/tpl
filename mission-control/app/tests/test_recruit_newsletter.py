"""
Tests for recruit_newsletter.py against an in-memory fake Supabase.

Covers: audience filtering, rendering (escaping, UTM tagging, placeholders),
the review gate (test-before-approve, frozen content, mailing address),
the batch processor (schedule, daily cap, suppression, domain limit, lease),
cancel / unapprove, and duplicate-for-next-week.

Run:  python tests/test_recruit_newsletter.py   (from mission-control/app,
      any venv with fastapi + pydantic installed)
"""
import os
import sys
import re
import types
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── stub `main` before the module under test imports from it ──
SETTINGS = {"smtp": {"pass": "re_test"}, "recruit_newsletter": {}}
SENT = []            # (to, subject, html, campaign, contact_id)
SEND_BEHAVIOR = {}   # email -> (ok, err) override


def _send_email(smtp, to, subject, html, from_address="", contact_id=None, campaign="", reply_to="", attachments=None):
    if to in SEND_BEHAVIOR:
        return SEND_BEHAVIOR[to]
    SENT.append((to, subject, html, campaign, contact_id))
    return True, ""


main_stub = types.ModuleType("main")
main_stub.load_settings = lambda: SETTINGS
main_stub.save_settings = lambda d: SETTINGS.update(d)
main_stub.send_email = _send_email
sys.modules["main"] = main_stub

os.environ["JWT_SECRET"] = "test-secret"
from fastapi import HTTPException  # noqa: E402
import recruit_newsletter as rn  # noqa: E402

rn.SEND_SPACING_SEC = 0


# ════════════════════════════════════════════════════════════
# Fake Supabase
# ════════════════════════════════════════════════════════════

DB = {}
SEQ = {}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


DEFAULTS = {
    "recruit_newsletter_issues": lambda: {
        "workspace_id": 1, "status": "draft", "subject": "", "preheader": "", "content": {},
        "content_updated_at": _now_iso(), "test_sent_at": None, "approved_at": None,
        "scheduled_for": None, "daily_cap": 150, "processing_until": None,
        "total_recipients": 0, "sent_count": 0, "failed_count": 0, "skipped_count": 0,
    },
    "recruit_newsletter_sends": lambda: {"workspace_id": 1, "status": "queued", "error": None, "sent_at": None, "token": str(uuid.uuid4())},
    "recruit_newsletter_clicks": lambda: {"suspected_bot": False, "clicked_at": _now_iso()},
    "tpl_videos": lambda: {"workspace_id": 1, "published": True, "duration_seconds": None, "description": "", "created_at": _now_iso()},
    "video_watch_sessions": lambda: {"workspace_id": 1, "watched_seconds": 0, "max_position": 0, "duration": 0, "pct": 0, "last_seen_at": _now_iso()},
    "booking_requests": lambda: {"workspace_id": 1, "created_at": _now_iso(), "status": "new", "token": str(uuid.uuid4()),
                                 "proposed_slots": [], "last_nudge_at": None, "prep_sent_at": None, "agent_reminder_sent_at": None,
                                 "confirmed_start": None, "times_sent_at": None, "meeting_type": "phone",
                                 "requested_start": None, "requested_minutes": None, "utm": {}, "source": None},
    "opportunities": lambda: {"status": "open", "pipeline_id": 1},
    "tasks": lambda: {"workspace_id": 1, "status": "pending", "created_at": _now_iso()},
    "leads": lambda: {"workspace_id": 1, "tags": [], "motivations": [], "lead_score": 0, "phone": "", "first_name": "", "last_name": ""},
}


class Res:
    def __init__(self, data, count=None):
        self.data, self.count = data, count


class Q:
    def __init__(self, table, op, payload=None, count=None):
        self.t, self.op, self.payload, self.count_mode = table, op, payload, count
        self.filters, self._limit, self._range, self._order = [], None, None, None

    def eq(self, k, v):   self.filters.append(lambda r: r.get(k) == v); return self
    def in_(self, k, v):  self.filters.append(lambda r: r.get(k) in v); return self
    def gte(self, k, v):  self.filters.append(lambda r: r.get(k) is not None and str(r[k]) >= str(v)); return self
    def lte(self, k, v):  self.filters.append(lambda r: r.get(k) is not None and str(r[k]) <= str(v)); return self
    def lt(self, k, v):   self.filters.append(lambda r: r.get(k) is not None and str(r[k]) < str(v)); return self
    def ilike(self, k, v): self.filters.append(lambda r: str(r.get(k) or "").lower() == str(v).lower()); return self

    def or_(self, expr):
        # supports "col.is.null,col.lt.<value>"
        clauses = []
        for part in expr.split(","):
            col, op, val = part.split(".", 2)
            if op == "is" and val == "null":
                clauses.append(lambda r, c=col: r.get(c) is None)
            elif op == "lt":
                clauses.append(lambda r, c=col, v=val: r.get(c) is not None and str(r[c]) < v)
        self.filters.append(lambda r: any(f(r) for f in clauses))
        return self

    def order(self, k, desc=False): self._order = (k, desc); return self
    def limit(self, n): self._limit = n; return self
    def range(self, a, b): self._range = (a, b); return self

    def _rows(self):
        return [r for r in DB.setdefault(self.t, []) if all(f(r) for f in self.filters)]

    def execute(self):
        if self.op == "insert":
            rows = self.payload if isinstance(self.payload, list) else [self.payload]
            staged = []
            for r in rows:
                row = DEFAULTS.get(self.t, dict)()
                row.update(r)
                SEQ[self.t] = SEQ.get(self.t, 0) + 1
                row["id"] = SEQ[self.t]
                if self.t == "recruit_newsletter_sends":
                    key = (row["issue_id"], row["email"].lower())
                    existing = {(x["issue_id"], x["email"].lower()) for x in DB.setdefault(self.t, []) + staged}
                    if key in existing:
                        raise Exception("duplicate key value violates unique constraint")
                staged.append(row)
            DB.setdefault(self.t, []).extend(staged)
            return Res([dict(r) for r in staged])
        rows = self._rows()
        if self.op == "select":
            total = len(rows)
            if self._order:
                k, desc = self._order
                rows = sorted(rows, key=lambda r: (r.get(k) is None, r.get(k)), reverse=desc)
            if self._range:
                rows = rows[self._range[0]: self._range[1] + 1]
            if self._limit is not None:
                rows = rows[: self._limit]
            return Res([dict(r) for r in rows], total if self.count_mode else None)
        if self.op == "update":
            for r in rows:
                r.update(self.payload)
            return Res([dict(r) for r in rows])
        if self.op == "delete":
            DB[self.t] = [r for r in DB[self.t] if r not in rows]
            return Res([dict(r) for r in rows])


class FakeTable:
    def __init__(self, name): self.name = name
    def select(self, *a, count=None, **k): return Q(self.name, "select", count=count)
    def insert(self, payload, *a, **k): return Q(self.name, "insert", payload)
    def update(self, payload, *a, **k): return Q(self.name, "update", payload)
    def delete(self, *a, **k): return Q(self.name, "delete")


class FakeSupabase:
    def table(self, name): return FakeTable(name)


rn.setup(None, FakeSupabase())


class Req:
    def __init__(self, email="joe@desaneteam.com"):
        self.state = type("S", (), {"user": {"sub": 1, "email": email}, "workspace_id": 1})()


# ════════════════════════════════════════════════════════════
# Harness
# ════════════════════════════════════════════════════════════

PASS, FAIL = [0], []


def check(label, cond, extra=""):
    if cond:
        PASS[0] += 1
    else:
        FAIL.append(f"{label} {extra}")
        print(f"FAIL: {label} {extra}")


def raises(label, fn, code, needle=""):
    try:
        fn()
    except HTTPException as e:
        check(label, e.status_code == code and needle.lower() in str(e.detail).lower(), f"(got {e.status_code}: {e.detail})")
        return
    check(label, False, "(no exception)")


def reset():
    DB.clear()
    SEQ.clear()
    SENT.clear()
    SEND_BEHAVIOR.clear()
    SETTINGS["recruit_newsletter"] = {}


def seed_leads():
    DB["leads"] = [
        {"id": 1, "workspace_id": 1, "email": "amy@kw.com", "first_name": "amy", "name": "Amy Lee", "status": "new", "stage": "new", "current_brokerage": "Keller Williams Realty Of Psl"},
        {"id": 2, "workspace_id": 1, "email": "AMY@kw.com", "first_name": "Amy", "name": "Amy Lee", "status": "new", "stage": "research", "current_brokerage": "Keller Williams"},  # dup address
        {"id": 3, "workspace_id": 1, "email": "bob@remax.net", "first_name": "", "name": "Bob Stone", "status": "new", "stage": "new_fb_lead", "current_brokerage": "RE/MAX"},
        {"id": 4, "workspace_id": 1, "email": "lpt@lpt.com", "first_name": "Lou", "status": "new", "stage": "new", "current_brokerage": "LPT Realty (joined 2026-04-22)"},
        {"id": 5, "workspace_id": 1, "email": "unsub@x.com", "first_name": "Una", "status": "new", "stage": "new", "current_brokerage": ""},
        {"id": 6, "workspace_id": 1, "email": "unsub@x.com", "first_name": "Una", "status": "unsubscribed", "stage": "new", "current_brokerage": ""},  # any unsub row blocks the address
        {"id": 7, "workspace_id": 1, "email": "supp@x.com", "first_name": "Sue", "status": "new", "stage": "new", "current_brokerage": ""},
        {"id": 8, "workspace_id": 1, "email": "bieker1@gmail.com1", "first_name": "Bad", "status": "new", "stage": "new", "current_brokerage": ""},
        {"id": 9, "workspace_id": 1, "email": "coach@x.com", "first_name": "Cal", "status": "new", "stage": "coaching_client", "current_brokerage": ""},
        {"id": 10, "workspace_id": 1, "email": "handle@x.com", "first_name": "handle@x.com", "status": "new", "stage": "new", "current_brokerage": "eXp Realty"},
        {"id": 11, "workspace_id": 2, "email": "otherws@x.com", "first_name": "Ow", "status": "new", "stage": "new", "current_brokerage": ""},
        {"id": 12, "workspace_id": 1, "email": "nl@x.com", "first_name": "Nia", "status": "new", "stage": "NEWLY LICENSED", "current_brokerage": None},
    ]
    SEQ["leads"] = 100
    DB["email_suppressions"] = [{"email": "supp@x.com"}]
    DB["email_send_log"] = []
    DB["lead_activity"] = []


GOOD_CONTENT = {
    "intro": "Quick one this week. **Three** things worth your time.",
    "events": [{"host": "LPT", "when": "Mon, Oct 5 - 11 AM ET", "title": "Listing Mastery", "description": "Open to any agent.", "url": "https://example.com/reg"}],
    "numbers": {"stat": "$18,800", "headline": "What a $150K agent keeps", "body": "See [the math](https://tplcollective.ai/compare).", "url": "https://tplcollective.ai/compare"},
    "class": {"video_slug": ""},
    "posts": [{"title": "Cap break-even explained", "blurb": "Why the flyer number misleads.", "url": "https://tplcollective.ai/blog/cap-break-even-explained"}],
    "news": [{"headline": "Big change at a franchise", "take": "Watch the fees.", "url": "https://news.example.com/a"}],
    "book": {},
    "ps": "Reply with your split and I'll run it.",
}


def make_ready_issue(**over):
    issue = rn.create_issue(rn.IssueIn(subject="The Weekly: what $150K keeps", content=dict(GOOD_CONTENT)), Req())
    rn.send_test(issue["id"], rn.TestIn(), Req())
    SETTINGS["recruit_newsletter"]["mailing_address"] = "123 Main St, Jupiter, FL 33458"
    return issue


# ════════════════════════════════════════════════════════════
# Tests
# ════════════════════════════════════════════════════════════

def test_audience():
    reset(); seed_leads()
    rows = rn._audience()
    emails = sorted(r["email"] for r in rows)
    check("audience: expected set", emails == ["amy@kw.com", "bob@remax.net", "handle@x.com", "nl@x.com"], str(emails))
    by = {r["email"]: r for r in rows}
    check("audience: dedupes case-insensitively, keeps first row", by["amy@kw.com"]["lead_id"] == 1)
    check("audience: capitalizes first name", by["amy@kw.com"]["first_name"] == "Amy")
    check("audience: falls back to name when first_name blank", by["bob@remax.net"]["first_name"] == "Bob")
    check("audience: never greets with an email handle", by["handle@x.com"]["first_name"] == "")
    check("audience: brokerage buckets", by["amy@kw.com"]["bucket"] == "Keller Williams" and by["bob@remax.net"]["bucket"] == "RE/MAX" and by["handle@x.com"]["bucket"] == "eXp")
    s = rn.audience_summary()
    check("audience summary: total", s["total"] == 4)


def test_render():
    reset()
    SETTINGS["recruit_newsletter"]["mailing_address"] = "123 Main St, Jupiter, FL"
    issue = {"issue_date": "2026-10-05", "subject": "S", "preheader": "P", "content": {
        "intro": "Hello <script>alert(1)</script> **bold** and [compare](https://tplcollective.ai/compare)",
        "events": [{"title": "T & Co", "when": "Mon", "url": "https://tplcollective.ai/x?a=1"}],
        "numbers": {"headline": ""},
        "news": [{"headline": "", "take": "ignored"}],
    }}
    h = rn.render_issue(issue, first_name="Amy")
    check("render: greeting with name", "Hey Amy," in h)
    check("render: greeting fallback", "Hey there," in rn.render_issue(issue, first_name=""))
    check("render: escapes html", "<script>" not in h and "&lt;script&gt;" in h)
    check("render: bold", "<strong>bold</strong>" in h)
    check("render: utm on own links", "utm_source=weekly-email" in h and "utm_campaign=weekly-2026-10-05" in h)
    check("render: keeps existing query params", "a=1" in h)
    check("render: escapes event title", "T &amp; Co" in h)
    check("render: empty numbers section omitted", "number of the week" not in h.lower())
    check("render: blank news items omitted", "Industry pulse" not in h)
    check("render: default tools shown", "Brokerage Cost Comparator" in h)
    check("render: mailing address in footer", "123 Main St, Jupiter, FL" in h)
    check("render: not-a-brokerage disclaimer", "not a brokerage" in h)
    check("render: 1-on-1 goes to the pre-qual form", "tplcollective.ai/book" in h and "calendly.com" not in h)
    check("render: socials in sign-off", "youtube.com/@JoeyDeSaneLPTRealty" in h and "instagram.com/joey_desane" in h)
    ext = rn._Links("c", None)("https://news.example.com/a")
    check("render: no utm on external links", ext == "https://news.example.com/a")
    check("render: no leftover placeholders", "{{" not in h and "{first_name}" not in h)


def test_review_gate():
    reset(); seed_leads()
    issue = rn.create_issue(rn.IssueIn(subject="Subj", content=dict(GOOD_CONTENT)), Req())
    check("create: draft", issue["status"] == "draft")
    check("create: defaults to a Monday", datetime.fromisoformat(issue["issue_date"]).weekday() == 0)

    raises("approve: blocked before any test", lambda: rn.approve_issue(issue["id"], rn.ApproveIn(), Req()), 409, "test")

    raises("test: blocked for loopback system user", lambda: rn.send_test(issue["id"], rn.TestIn(), Req("system@tplcollective.ai")), 400)
    r = rn.send_test(issue["id"], rn.TestIn(), Req())
    check("test: sent to logged-in coach", r["sent_to"] == "joe@desaneteam.com" and SENT[-1][1].startswith("[TEST]"))
    check("test: campaign is weekly-test, not the real campaign", SENT[-1][3] == "weekly-test")

    raises("approve: blocked without mailing address", lambda: rn.approve_issue(issue["id"], rn.ApproveIn(), Req()), 400, "mailing address")
    SETTINGS["recruit_newsletter"]["mailing_address"] = "123 Main St"

    # an edit after the test invalidates it
    import time as _t; _t.sleep(0.01)
    rn.update_issue(issue["id"], rn.IssueIn(subject="Subj v2"))
    raises("approve: blocked when edited after test", lambda: rn.approve_issue(issue["id"], rn.ApproveIn(), Req()), 409, "edited after")
    check("get: test_is_current false after edit", rn.get_issue(issue["id"])["test_is_current"] is False)

    _t.sleep(0.01)
    rn.send_test(issue["id"], rn.TestIn(), Req())
    check("get: test_is_current true after re-test", rn.get_issue(issue["id"])["test_is_current"] is True)
    a = rn.approve_issue(issue["id"], rn.ApproveIn(daily_cap=2), Req())
    check("approve: status approved", a["status"] == "approved")
    check("approve: snapshots audience", a["total_recipients"] == 4, str(a["total_recipients"]))
    check("approve: daily cap stored", a["daily_cap"] == 2)
    check("approve: nothing sent yet (only the 2 tests)", len(SENT) == 2)

    raises("edit: blocked once approved", lambda: rn.update_issue(issue["id"], rn.IssueIn(subject="x")), 409)
    raises("delete: blocked once approved", lambda: rn.delete_issue(issue["id"]), 409)

    u = rn.unapprove_issue(issue["id"])
    check("unapprove: back to draft", u["status"] == "draft")
    check("unapprove: queue cleared", len([s for s in DB["recruit_newsletter_sends"] if s["issue_id"] == issue["id"]]) == 0)


def test_placeholder_guard():
    reset(); seed_leads()
    SETTINGS["recruit_newsletter"]["mailing_address"] = "123 Main St"
    c = dict(GOOD_CONTENT); c["intro"] = "Hi {first_name}, quick one"
    issue = rn.create_issue(rn.IssueIn(subject="S", content=c), Req())
    raises("placeholder: test send refused", lambda: rn.send_test(issue["id"], rn.TestIn(), Req()), 400, "placeholder")
    check("placeholder: nothing sent", len(SENT) == 0)

    raises("validate: subject required", lambda: rn.send_test(rn.create_issue(rn.IssueIn(content=dict(GOOD_CONTENT)), Req())["id"], rn.TestIn(), Req()), 400, "subject")


def test_processor():
    reset(); seed_leads()
    issue = make_ready_issue()
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    rn.approve_issue(issue["id"], rn.ApproveIn(scheduled_for=future, daily_cap=2), Req())
    SENT.clear()

    r = rn.process_due()
    check("process: nothing before scheduled time", r["processed"] == [] and SENT == [])

    DB["recruit_newsletter_issues"][0]["scheduled_for"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    r = rn.process_due()["processed"][0]
    check("process: daily cap honored", r["sent"] == 2 and len(SENT) == 2, str(r))
    check("process: real campaign name", SENT[0][3] == f"weekly-{issue['issue_date']}")
    check("process: contact_id passed for logging", SENT[0][4] == 1)
    check("process: personalized", "Hey Amy," in SENT[0][2])
    check("process: status sending", rn.get_issue(issue["id"])["status"] == "sending")
    check("process: lead activity logged", len(DB["lead_activity"]) == 2 and DB["lead_activity"][0]["activity_type"] == "newsletter_sent")
    check("process: lease released", DB["recruit_newsletter_issues"][0]["processing_until"] is None)

    r = rn.process_due()["processed"][0]
    check("process: second run same day stops at cap", r["sent"] == 0 and r["stopped"] == "daily cap reached", str(r))

    # next day: raise the cap, one address now suppressed, one hits the domain limit
    DB["recruit_newsletter_issues"][0]["daily_cap"] = 100
    for s in DB["recruit_newsletter_sends"]:
        if s["status"] == "sent":
            s["sent_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    queued = [s["email"] for s in DB["recruit_newsletter_sends"] if s["status"] == "queued"]
    SEND_BEHAVIOR[queued[0]] = (False, f"Email suppressed: {queued[0]}")
    SEND_BEHAVIOR[queued[1]] = (False, "Daily send limit reached for tplcollective.co")
    SENT.clear()
    r = rn.process_due()["processed"][0]
    check("process: suppressed -> skipped", r["skipped"] == 1, str(r))
    check("process: domain limit stops run, leaves queued", r["stopped"].startswith("Daily send limit") and r["remaining"] == 1, str(r))

    SEND_BEHAVIOR.clear()
    r = rn.process_due()["processed"][0]
    iss = rn.get_issue(issue["id"])
    check("process: completes", r["remaining"] == 0 and iss["status"] == "sent" and iss["completed_at"], str(r))
    check("process: counts", iss["sent_count"] == 3 and iss["skipped_count"] == 1, str(iss["counts"]))
    check("process: done issue not picked again", rn.process_due()["processed"] == [])

    raises("unapprove: blocked after sending", lambda: rn.unapprove_issue(issue["id"]), 409)


def test_failures_and_lease():
    reset(); seed_leads()
    issue = make_ready_issue()
    rn.approve_issue(issue["id"], rn.ApproveIn(), Req())
    SEND_BEHAVIOR["bob@remax.net"] = (False, "Resend API error 422: bad")
    DB["recruit_newsletter_issues"][0]["processing_until"] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    r = rn.process_due()["processed"][0]
    check("lease: held lease blocks a second run", "lease" in r.get("stopped", ""), str(r))

    DB["recruit_newsletter_issues"][0]["processing_until"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    r = rn.process_due()["processed"][0]
    check("lease: expired lease is reclaimed", r["sent"] == 3 and r["failed"] == 1, str(r))
    bob = [s for s in DB["recruit_newsletter_sends"] if s["email"] == "bob@remax.net"][0]
    check("failure: recorded with error", bob["status"] == "failed" and "422" in bob["error"])


def test_cancel():
    reset(); seed_leads()
    issue = make_ready_issue()
    rn.approve_issue(issue["id"], rn.ApproveIn(daily_cap=1), Req())
    SENT.clear()
    rn.process_due()
    c = rn.cancel_issue(issue["id"])
    check("cancel: status cancelled", c["status"] == "cancelled")
    check("cancel: queued -> skipped", c["sent_count"] == 1 and c["skipped_count"] == 3, str(c))
    DB["recruit_newsletter_issues"][0]["daily_cap"] = 100
    rn.process_due()
    check("cancel: nothing further sent", len(SENT) == 1)
    raises("cancel: twice refused", lambda: rn.cancel_issue(issue["id"]), 409)


def test_duplicate():
    reset()
    c = dict(GOOD_CONTENT)
    src = rn.create_issue(rn.IssueIn(issue_date="2026-10-05", subject="S", content=c), Req())
    d = rn.duplicate_issue(src["id"], Req())
    check("duplicate: +7 days", d["issue_date"] == "2026-10-12")
    check("duplicate: news + P.S. cleared", d["content"]["news"] == [] and d["content"]["ps"] == "")
    ev = d["content"]["events"]
    check("duplicate: events regenerated for the new week", [e["title"] for e in ev] == ["Motivational Monday", "Tools Tuesday", "Real Estate First Friday"], str([e["title"] for e in ev]))
    check("duplicate: event dates are the new week", ev[0]["when"].startswith("Monday, Oct 12") and ev[2]["when"].startswith("Friday, Oct 16"), ev[0]["when"])
    check("duplicate: evergreen sections kept", d["content"]["numbers"]["headline"] == c["numbers"]["headline"])
    check("duplicate: subject blank, draft", d["subject"] == "" and d["status"] == "draft")
    check("duplicate: source untouched", src["content"]["events"])


class HReq:
    """Minimal Request for the public click endpoint."""
    def __init__(self, ua="Mozilla/5.0"):
        self.headers = {"user-agent": ua}
        self.state = type("S", (), {"user": {}})()


def seed_video(slug="cap-math", yid="dQw4w9WgXcQ", dur=None):
    return rn.create_video(rn.VideoIn(youtube_url=f"https://www.youtube.com/watch?v={yid}", title="Cap Math in 9 Minutes", slug=slug, duration_seconds=dur))


def approved_issue_with_sends():
    reset(); seed_leads()
    seed_video(dur=600)
    c = dict(GOOD_CONTENT); c["class"] = {"video_slug": "cap-math"}
    issue = rn.create_issue(rn.IssueIn(subject="S", content=c), Req())
    rn.send_test(issue["id"], rn.TestIn(), Req())
    SETTINGS["recruit_newsletter"]["mailing_address"] = "123 Main St"
    rn.approve_issue(issue["id"], rn.ApproveIn(), Req())
    return issue, {x["email"]: x for x in DB["recruit_newsletter_sends"]}


def test_recurring_and_formatting():
    check("clock: 11:00-11:30 AM", rn._fmt_range("11:00", "11:30") == "11:00-11:30 AM ET", rn._fmt_range("11:00", "11:30"))
    check("clock: crosses noon", rn._fmt_range("11:30", "12:15") == "11:30 AM-12:15 PM ET", rn._fmt_range("11:30", "12:15"))
    check("clock: 4 PM", rn._fmt_range("16:00", "16:30") == "4:00-4:30 PM ET")
    ev = rn._week_events("2026-10-07", rn.DEFAULT_RECURRING_EVENTS)  # a Wednesday: snaps to that week
    check("recurring: only active series", [e["recurring_key"] for e in ev] == ["motivational-monday", "tools-tuesday", "reff"])
    check("recurring: dated from the week's Monday", ev[0]["when"] == "Monday, Oct 5 - 11:00-11:30 AM ET", ev[0]["when"])
    check("recurring: host carried for the badge", ev[0]["host"] == "LPT Realty")
    et = datetime(2026, 10, 5, 11, 15, tzinfo=rn._ET)  # Monday during Motivational Monday
    nxt = rn._next_occurrence(rn.DEFAULT_RECURRING_EVENTS[0], et)
    check("next occurrence: still today while it's live", nxt.date().isoformat() == "2026-10-05")
    nxt = rn._next_occurrence(rn.DEFAULT_RECURRING_EVENTS[0], et.replace(hour=12))
    check("next occurrence: next week once it's over", nxt.date().isoformat() == "2026-10-12")
    reset()
    fresh = rn.create_issue(rn.IssueIn(issue_date="2026-10-05"), Req())
    check("new issue: events pre-filled", len(fresh["content"]["events"]) == 3)
    check("new issue: book + class sections present", "book" in fresh["content"] and "class" in fresh["content"])


def test_youtube_and_videos():
    for url in ["https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10", "https://youtu.be/dQw4w9WgXcQ?si=x",
                "https://www.youtube.com/shorts/dQw4w9WgXcQ", "https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"]:
        check(f"youtube id: {url}", rn._youtube_id(url) == "dQw4w9WgXcQ")
    check("youtube id: rejects channel links", rn._youtube_id("https://www.youtube.com/@JoeyDeSaneLPTRealty") is None)
    reset()
    v = rn.create_video(rn.VideoIn(youtube_url="https://youtu.be/dQw4w9WgXcQ", title="Cap Math: What KW Agents Miss!"))
    check("video: slug from title", v["slug"] == "cap-math-what-kw-agents-miss")
    raises("video: duplicate slug", lambda: rn.create_video(rn.VideoIn(youtube_url="dQw4w9WgXcQ", title="Cap Math: What KW Agents Miss")), 409)
    raises("video: bad url", lambda: rn.create_video(rn.VideoIn(youtube_url="https://vimeo.com/1", title="x")), 400)
    check("public: published video listed", [x["slug"] for x in rn.public_videos()["videos"]] == [v["slug"]])
    rn.update_video(v["slug"], rn.VideoIn(published=False))
    check("public: unpublished hidden", rn.public_videos()["videos"] == [])
    raises("public: unpublished 404", lambda: rn.public_video(v["slug"]), 404)

    c = dict(GOOD_CONTENT); c["class"] = {"video_slug": v["slug"]}
    issue = rn.create_issue(rn.IssueIn(subject="S", content=c), Req())
    raises("gate: unpublished class blocks test", lambda: rn.send_test(issue["id"], rn.TestIn(), Req()), 400, "unpublished")
    raises("video: delete blocked while an issue uses it", lambda: rn.delete_video(v["slug"]), 409)


def test_links_and_render_tracking():
    reset()
    seed_video(dur=540)
    c = dict(GOOD_CONTENT); c["class"] = {"video_slug": "cap-math"}
    issue = {"issue_date": "2026-10-05", "subject": "S", "content": c}
    tok = "11111111-2222-3333-4444-555555555555"
    h = rn.render_issue(issue, first_name="Amy", token=tok)
    check("tracking: links go through the redirect", h.count(rn.TRACK_BASE + "/c/" + tok) >= 8)
    check("tracking: no raw calendly/zoom links left", "https://example.com/reg\"" not in h)
    check("class: thumbnail from YouTube", "i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg" in h)
    check("class: duration on the button", "Watch the class (9 min)" in h)
    check("class: hosted-by badge on events", "HOSTED BY LPT" in h)
    # decode one wrapped link and check the destination carries the token
    import html as H
    m = re.search(r'href="(' + re.escape(rn.TRACK_BASE) + r'/c/[^"]+)"', h)
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(H.unescape(m.group(1))).query))
    check("tracking: own-page destination carries t=", "t=" + tok in q["u"] and "utm_source=weekly-email" in q["u"], q["u"])
    check("tracking: signature matches", q["s"] == rn._sign(tok, q["u"]))
    ext = rn._Links("c", tok)("https://lptrealty.zoom.us/webinar/register/X", "MM")
    eq = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(ext).query))
    check("tracking: external destination untouched", eq["u"] == "https://lptrealty.zoom.us/webinar/register/X")
    hp = rn.render_issue(issue, first_name="Amy")
    check("preview: untracked", rn.TRACK_BASE not in hp and "tplcollective.ai/watch?v=cap-math" in hp)
    check("P.S. rendered", "<strong>P.S.</strong>" in h)
    check("blog post rendered", "Cap break-even explained" in h)


def test_click_endpoint():
    issue, sends = approved_issue_with_sends()
    amy = sends["amy@kw.com"]
    url = "https://tplcollective.ai/compare?t=" + amy["token"]
    r = rn.click(amy["token"], HReq(), u=url, s=rn._sign(amy["token"], url), l="compare")
    check("click: redirects to destination", r.status_code == 302 and r.headers["location"] == url)
    check("click: logged", len(DB["recruit_newsletter_clicks"]) == 1 and DB["recruit_newsletter_clicks"][0]["lead_id"] == 1)
    check("click: on the contact timeline", any(a["activity_type"] == "newsletter_click" for a in DB["lead_activity"]))

    r = rn.click(amy["token"], HReq(), u="https://evil.example.com", s="forged")
    check("click: bad signature -> home, not the attacker's URL", r.headers["location"] == rn.SITE + "/")
    check("click: bad signature not logged", len(DB["recruit_newsletter_clicks"]) == 1)
    r = rn.click("test", HReq(), u=url, s=rn._sign("test", url))
    check("click: test token redirects without logging", r.headers["location"] == url and len(DB["recruit_newsletter_clicks"]) == 1)

    # a scanner hits three different links inside the window
    bob = sends["bob@remax.net"]
    for i, dest in enumerate(["https://a.example.com/1", "https://a.example.com/2", "https://a.example.com/3"]):
        rn.click(bob["token"], HReq("Microsoft SafeLinks"), u=dest, s=rn._sign(bob["token"], dest))
    bobs = [c for c in DB["recruit_newsletter_clicks"] if c["send_id"] == bob["id"]]
    check("bots: burst flagged, including the first click", len(bobs) == 3 and all(c["suspected_bot"] for c in bobs), str([c["suspected_bot"] for c in bobs]))
    e = rn.issue_engagement(issue["id"])
    check("engagement: bot clicks excluded", e["totals"]["clickers"] == 1 and e["totals"]["bot_clicks_excluded"] == 3, str(e["totals"]))


def test_video_tracking():
    issue, sends = approved_issue_with_sends()
    amy = sends["amy@kw.com"]
    NOTIFY = []
    orig = rn._notify
    rn._notify = lambda subject, rows, campaign: NOTIFY.append(subject)
    try:
        rn._record_watch("cap-math", "sess-aaaaaaaa", amy["token"], 60, 60, 600, "UA")
        ws = DB["video_watch_sessions"]
        check("video: session tied to lead + issue", ws[0]["lead_id"] == 1 and ws[0]["issue_id"] == issue["id"])
        check("video: pct from time actually played", ws[0]["pct"] == 10)
        rn._record_watch("cap-math", "sess-aaaaaaaa", amy["token"], 40, 590, 600, "UA")
        check("video: skipping ahead doesn't inflate watch time", ws[0]["watched_seconds"] == 60 and ws[0]["max_position"] == 590)
        rn._record_watch("cap-math", "sess-aaaaaaaa", amy["token"], 330, 330, 600, "UA")
        acts = [a["description"] for a in DB["lead_activity"] if a["activity_type"] == "video_watched"]
        check("video: 25% and 50% milestones logged", acts == ['Watched 25% of "Cap Math in 9 Minutes"', 'Watched 50% of "Cap Math in 9 Minutes"'], str(acts))
        check("video: Joe alerted at 50%", len(NOTIFY) == 1 and "watched half" in NOTIFY[0], str(NOTIFY))
        # a second session re-watching the same class must not re-alert
        rn._record_watch("cap-math", "sess-bbbbbbbb", amy["token"], 400, 400, 600, "UA")
        check("video: no duplicate alert on a re-watch", len(NOTIFY) == 1)
        check("video: only new milestones logged", [a for a in DB["lead_activity"] if a["activity_type"] == "video_watched"][-1]["description"].startswith("Watched 50%"))
        rn._record_watch("cap-math", "sess-cccccccc", "", 100, 100, 600, "UA")
        check("video: anonymous session recorded without a lead", DB["video_watch_sessions"][-1]["lead_id"] is None)
        check("video: unknown slug ignored", rn._record_watch("nope", "sess-dddddddd", "", 1, 1, 1, "UA") == {"ok": False})
        check("video: duration learned from the player", rn._videos_map()["cap-math"]["duration_seconds"] == 600)
        e = rn.issue_engagement(issue["id"])
        check("engagement: watcher listed with best pct", e["totals"]["watched_half"] == 1 and e["people"][0]["video_pct"] == 67, str(e["people"][:1]))
        v = rn.video_viewers("cap-math")
        check("viewers: best pct per lead, anon counted", v["viewers"][0]["pct"] == 67 and v["anonymous_sessions"] == 1)
    finally:
        rn._notify = orig


def test_public_trainings():
    reset()
    t = rn.public_trainings()
    check("trainings: active series only", sorted(e["key"] for e in t["events"]) == ["motivational-monday", "reff", "tools-tuesday"])
    check("trainings: sorted by next occurrence", [e["next"] for e in t["events"]] == sorted(e["next"] for e in t["events"]))
    check("trainings: socials included", len(t["socials"]) == 3)


def test_approve_needs_secret():
    reset(); seed_leads()
    issue = make_ready_issue()
    old = os.environ.pop("JWT_SECRET")
    try:
        raises("approve: refuses without a signing secret", lambda: rn.approve_issue(issue["id"], rn.ApproveIn(), Req()), 500, "JWT_SECRET")
    finally:
        os.environ["JWT_SECRET"] = old


if __name__ == "__main__":
    for fn in [test_audience, test_render, test_review_gate, test_placeholder_guard, test_processor, test_failures_and_lease, test_cancel, test_duplicate,
               test_recurring_and_formatting, test_youtube_and_videos, test_links_and_render_tracking, test_click_endpoint,
               test_video_tracking, test_public_trainings, test_approve_needs_secret]:
        fn()
    print(f"\n{PASS[0]} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
