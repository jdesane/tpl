"""
Tests for one_on_one.py (1-on-1 requests replacing Calendly), reusing the
in-memory fake Supabase from test_recruit_newsletter.

Run:  python tests/test_one_on_one.py   (from mission-control/app)
"""
import base64
import re
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_recruit_newsletter as T  # sets up the `main` stub + fake DB  # noqa: E402
from test_recruit_newsletter import check, raises, Req, DB  # noqa: E402

import recruit_newsletter as rn  # noqa: E402
import one_on_one as oo  # noqa: E402

oo.setup(None, T.FakeSupabase())

# record every email including attachments
MAIL = []


def _send(smtp, to, subject, html, from_address="", contact_id=None, campaign="", reply_to="", attachments=None):
    if to in T.SEND_BEHAVIOR:
        return T.SEND_BEHAVIOR[to]
    MAIL.append({"to": to, "subject": subject, "html": html, "campaign": campaign, "attachments": attachments or []})
    return True, ""


sys.modules["main"].send_email = _send


def reset():
    T.reset(); T.seed_leads()
    DB["tasks"] = []
    MAIL.clear()
    T.SETTINGS["recruit_newsletter"] = {"mailing_address": "123 Main St"}


def future(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def submit(**over):
    body = dict(first_name="Amy", last_name="Lee", email="amy@kw.com", phone="(561) 555-0101",
                current_brokerage="KW Jupiter", agent_type="Solo agent", deals="11-20", avg_price="$400K-$600K",
                topics=["Lowering what I pay my brokerage"], timeline="1-3 months", notes="70/30, $21K cap")
    body.update(over)
    return oo.submit_request(oo.RequestIn(**body))


def the_request():
    return DB["booking_requests"][-1]


def test_submit():
    reset()
    raises("submit: phone required", lambda: submit(phone="123"), 400, "phone")
    raises("submit: email required", lambda: submit(email="nope"), 400)
    r = submit()
    check("submit: no calendar link returned", r == {"ok": True})
    req = the_request()
    lead = [l for l in DB["leads"] if l["id"] == 1][0]
    check("submit: request is new, nothing booked", req["status"] == "new" and not req.get("confirmed_start"))
    check("submit: matched existing lead by email", req["lead_id"] == 1 and len([l for l in DB["leads"] if l["email"].lower() == "amy@kw.com"]) == 2)
    check("submit: lead updated + hot", lead["deals_per_year"] == "11-20" and lead["lead_temperature"] == "hot" and lead["lead_score"] == 70)
    check("submit: phone filled when blank", lead["phone"] == "(561) 555-0101")
    check("submit: dashboard task due today", DB["tasks"][0]["title"] == "Send 1-on-1 times to Amy Lee" and DB["tasks"][0]["priority"] == "high")
    check("submit: Joe alerted, told nothing is booked", MAIL and MAIL[0]["subject"] == "1-on-1 request: Amy Lee" and "Nothing is on your calendar" in MAIL[0]["html"])
    check("submit: alert links to the request", f"#one-on-one/{req['id']}" in MAIL[0]["html"])
    check("submit: no sponsor question anywhere", "sponsor" not in str(req["answers"]).lower())

    n = len(DB["leads"])
    submit(first_name="New", last_name="Person", email="new@x.com", phone="5615550103")
    check("submit: unknown email creates a lead", len(DB["leads"]) == n + 1 and DB["leads"][-1]["source"] == "tpl-book-page")
    before = len(DB["booking_requests"])
    submit(email="spam@x.com", website="http://spam")
    check("submit: honeypot stores nothing", len(DB["booking_requests"]) == before)

    # via the weekly email token
    reset()
    T.seed_video(dur=600)
    c = dict(T.GOOD_CONTENT)
    issue = rn.create_issue(rn.IssueIn(subject="S", content=c), Req())
    rn.send_test(issue["id"], rn.TestIn(), Req())
    rn.approve_issue(issue["id"], rn.ApproveIn(), Req())
    bob = [s for s in DB["recruit_newsletter_sends"] if s["email"] == "bob@remax.net"][0]
    submit(t=bob["token"], first_name="Bob", last_name="Stone", email="bob@remax.net")
    req = the_request()
    check("submit (token): tied to the issue + send", req["issue_id"] == issue["id"] and req["send_id"] == bob["id"] and req["lead_id"] == 3)
    e = rn.issue_engagement(issue["id"])
    check("engagement: request counted on the issue", e["totals"]["bookings"] == 1 and e["people"][0]["booked"])


def test_send_times_and_pick():
    reset()
    submit()
    req = the_request()
    MAIL.clear()
    raises("times: none", lambda: oo.send_times(req["id"], oo.SendTimesIn(slots=[])), 400)
    raises("times: past", lambda: oo.send_times(req["id"], oo.SendTimesIn(slots=[future(-2)])), 400, "passed")
    raises("times: too soon", lambda: oo.send_times(req["id"], oo.SendTimesIn(slots=[future(0.2)])), 400)
    raises("times: max 4", lambda: oo.send_times(req["id"], oo.SendTimesIn(slots=[future(h) for h in (24, 25, 26, 27, 28)])), 400)
    slots = [future(48), future(26), future(50)]
    oo.send_times(req["id"], oo.SendTimesIn(slots=slots, minutes=30, note="Great answers, Amy."))
    req = the_request()
    check("times: status times_sent", req["status"] == "times_sent")
    check("times: slots stored sorted", [s["start"] for s in req["proposed_slots"]] == sorted(req["proposed_slots"][i]["start"] for i in range(3)))
    m = MAIL[-1]
    check("times: emailed to the agent", m["to"] == "amy@kw.com" and m["subject"] == "A few times for our call")
    check("times: one button per slot", all(f"/pick?r={req['token']}&amp;s={i}" in m["html"] or f"/pick?r={req['token']}&s={i}" in m["html"] for i in range(3)))
    check("times: Joe's note used", "Great answers, Amy." in m["html"])
    check("times: 'none of these work' path", "#none" in m["html"])
    check("times: send task closed", all(t["status"] == "done" for t in DB["tasks"] if t["title"].startswith("Send ")))

    info = oo.pick_info(req["token"])
    check("pick page: three future slots with ET labels", len(info["slots"]) == 3 and info["slots"][0]["label"].endswith(" ET"), str(info["slots"][:1]))
    raises("pick: bad token", lambda: oo.pick_info("nope"), 404)
    raises("pick: bad index", lambda: oo.pick(oo.PickIn(r=req["token"], s=9)), 400)

    MAIL.clear()
    r = oo.pick(oo.PickIn(r=req["token"], s=1))
    req = the_request()
    lead = [l for l in DB["leads"] if l["id"] == 1][0]
    check("pick: confirmed", r["status"] == "confirmed" and req["status"] == "confirmed" and req["confirmed_start"] == req["proposed_slots"][1]["start"])
    check("pick: lead moves to discovery_call", lead["stage"] == "discovery_call" and lead["follow_up_date"] == req["confirmed_start"])
    call_tasks = [t for t in DB["tasks"] if t["title"].startswith("1-on-1 call with")]
    check("pick: call task on the call date with a time", len(call_tasks) == 1 and call_tasks[0]["due_time"].endswith(" ET"))
    to = sorted(x["to"] for x in MAIL)
    check("pick: agent + Joe both emailed", to == ["amy@kw.com", "joe@desaneteam.com"], str(to))
    ics = [x for x in MAIL if x["attachments"]]
    check("pick: both emails carry a calendar file", len(ics) == 2 and all(x["attachments"][0]["filename"].endswith(".ics") for x in ics))
    body = base64.b64decode(ics[0]["attachments"][0]["content"]).decode()
    start = datetime.fromisoformat(req["confirmed_start"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    check("ics: correct start in UTC", f"DTSTART:{start}" in body and "END:VCALENDAR" in body)
    joe_ics = [x for x in ics if x["to"] == "joe@desaneteam.com"][0]
    check("ics: Joe's copy names the agent", "1-on-1: Amy Lee" in base64.b64decode(joe_ics["attachments"][0]["content"]).decode())

    n = len(MAIL)
    r = oo.pick(oo.PickIn(r=req["token"], s=1))
    check("pick: double click is harmless", r["status"] == "confirmed" and len(MAIL) == n)
    raises("pick: can't switch after confirming", lambda: oo.pick(oo.PickIn(r=req["token"], s=0)), 409, "already confirmed")
    raises("send-times: blocked once confirmed", lambda: oo.send_times(req["id"], oo.SendTimesIn(slots=[future(30)])), 409)


def test_none_work_and_manual():
    reset()
    submit()
    req = the_request()
    oo.send_times(req["id"], oo.SendTimesIn(slots=[future(30), future(31)]))
    MAIL.clear()
    oo.pick(oo.PickIn(r=the_request()["token"], none=True, note="Evenings are better"))
    req = the_request()
    check("none: back to new with their note", req["status"] == "new" and req["agent_note"] == "Evenings are better")
    check("none: Joe alerted with the note", MAIL and "needs different times" in MAIL[0]["subject"] and "Evenings are better" in MAIL[0]["html"])
    check("none: new send task", any(t["title"].startswith("Send new 1-on-1 times") and t["status"] == "pending" for t in DB["tasks"]))

    # the agent replied by phone instead; Joe confirms by hand
    oo.confirm_manual(req["id"], oo.ConfirmIn(start=future(72), minutes=45))
    req = the_request()
    check("manual: confirmed with Joe's length", req["status"] == "confirmed" and req["confirmed_minutes"] == 45)
    check("manual: all send tasks closed", all(t["status"] == "done" for t in DB["tasks"] if t["title"].startswith("Send")))

    oo.close(req["id"], oo.CloseIn(reason="Not a fit"))
    check("close: closed with reason, tasks done", the_request()["status"] == "closed" and all(t["status"] == "done" for t in DB["tasks"]))
    raises("closed: pick refused", lambda: oo.pick(oo.PickIn(r=req["token"], s=0)), 409)
    oo.reopen(req["id"])
    check("reopen: back to new", the_request()["status"] == "new")


def test_suppressed_agent():
    reset()
    submit()
    req = the_request()
    T.SEND_BEHAVIOR["amy@kw.com"] = (False, "Email suppressed: amy@kw.com")
    raises("suppressed: clear message, no silent failure", lambda: oo.send_times(req["id"], oo.SendTimesIn(slots=[future(30)])), 409, "suppression")
    check("suppressed: status unchanged", the_request()["status"] == "new")


def test_reminders():
    reset()
    submit()
    req = the_request()
    MAIL.clear()
    check("nudge: nothing for a fresh request", oo.process()["nudges"] == 0)
    req["created_at"] = (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()
    r = oo.process()
    check("nudge: waiting 12h+ -> Joe nudged", r["nudges"] == 1 and "Still waiting: Amy Lee" in MAIL[-1]["subject"])
    check("nudge: not again within 24h", oo.process()["nudges"] == 0)

    oo.send_times(req["id"], oo.SendTimesIn(slots=[future(30), future(60)]))
    req = the_request()
    req["times_sent_at"] = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
    MAIL.clear()
    r = oo.process()
    check("nudge: unanswered offer 48h+", r["nudges"] == 1 and "hasn't picked a time" in MAIL[-1]["subject"])

    req["last_nudge_at"] = None
    for s in req["proposed_slots"]:
        s["start"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    MAIL.clear()
    oo.process()
    check("nudge: all offered times passed", MAIL and "every time you offered has passed" in MAIL[-1]["subject"])

    # confirmed call starting in 50 minutes
    reset()
    submit()
    req = the_request()
    oo.send_times(req["id"], oo.SendTimesIn(slots=[future(3)]))
    oo.pick(oo.PickIn(r=the_request()["token"], s=0))
    req = the_request()
    req["confirmed_start"] = (datetime.now(timezone.utc) + timedelta(minutes=50)).isoformat()
    MAIL.clear()
    r = oo.process()
    subjects = [x["subject"] for x in MAIL]
    check("prep: Joe gets a prep email with answers", r["preps"] == 1 and any(s.startswith("In ") and "call with Amy Lee" in s for s in subjects), str(subjects))
    check("prep: includes their answers", "70/30, $21K cap" in [x for x in MAIL if x["to"] == "joe@desaneteam.com"][0]["html"])
    check("reminder: agent reminded", r["agent_reminders"] == 1 and any(x["to"] == "amy@kw.com" and x["subject"].startswith("Talk soon") for x in MAIL))
    r = oo.process()
    check("prep + reminder: sent once", r["preps"] == 0 and r["agent_reminders"] == 0)


def test_zoom_vs_phone():
    reset()
    submit()
    req = the_request()
    raises("zoom: needs a link first", lambda: oo.send_times(req["id"], oo.SendTimesIn(slots=[future(30)], meeting="zoom")), 400, "Zoom link")
    T.SETTINGS["recruit_newsletter"]["zoom_link"] = "https://zoom.us/j/123456"
    MAIL.clear()
    oo.send_times(req["id"], oo.SendTimesIn(slots=[future(30)], meeting="zoom"))
    check("zoom: offer says Zoom", "on Zoom" in MAIL[-1]["html"] and the_request()["meeting_type"] == "zoom")
    MAIL.clear()
    oo.pick(oo.PickIn(r=the_request()["token"], s=0))
    agent = [x for x in MAIL if x["to"] == "amy@kw.com"][0]
    check("zoom: confirmation carries the link", "https://zoom.us/j/123456" in agent["html"])
    ics = base64.b64decode(agent["attachments"][0]["content"]).decode()
    check("zoom: ics location is the link", "LOCATION:https://zoom.us/j/123456" in ics)
    joe = [x for x in MAIL if x["to"] == "joe@desaneteam.com"][0]
    check("zoom: Joe told it's Zoom", "by Zoom" in joe["html"])

    reset()
    submit()
    req = the_request()
    MAIL.clear()
    oo.send_times(req["id"], oo.SendTimesIn(slots=[future(30)]))
    check("phone: default, offer says by phone", "by phone" in MAIL[-1]["html"])
    MAIL.clear()
    oo.pick(oo.PickIn(r=the_request()["token"], s=0))
    agent = [x for x in MAIL if x["to"] == "amy@kw.com"][0]
    import html as _h
    check("phone: agent told Joe will call their number", "I'll call you at (561) 555-0101" in _h.unescape(agent["html"]))
    joe = [x for x in MAIL if x["to"] == "joe@desaneteam.com"][0]
    check("phone: Joe gets the number to call", "call them at (561) 555-0101" in joe["html"])
    raises("meeting: rejects junk", lambda: oo.send_times(req["id"], oo.SendTimesIn(slots=[future(40)], meeting="carrier pigeon")), 409)


def test_admin_list():
    reset()
    submit()
    submit(first_name="Bob", email="bob@remax.net", phone="5615550102")
    oo.send_times(DB["booking_requests"][0]["id"], oo.SendTimesIn(slots=[future(30)]))
    rows = oo.list_requests()["requests"]
    check("list: newest first, token hidden", rows[0]["who"].startswith("Bob") and "token" not in rows[0])
    check("list: slots labelled", rows[1]["slots"][0]["label"].endswith(" ET"))
    c = oo.counts()
    check("counts: by status", c["new"] == 1 and c["times_sent"] == 1)
    check("status filter", len(oo.list_requests(status="new")["requests"]) == 1)


def test_fmt():
    dt = datetime(2026, 10, 6, 18, 0, tzinfo=timezone.utc)
    check("fmt: ET label", oo._fmt_et(dt) == "Tue, Oct 6 at 2:00 PM ET", oo._fmt_et(dt))


# ════════════════════════════════════════════════════════════
# /report-call holds
# ════════════════════════════════════════════════════════════

MON_8AM_ET = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)   # Monday 8:00 AM ET (EDT)


class Frozen:
    def __init__(self, t): self.t = t
    def __enter__(self):
        self.orig = oo._now
        oo._now = lambda: self.t
        return self
    def __exit__(self, *a):
        oo._now = self.orig


def reset_hold():
    reset()
    DB["opportunities"] = [{"id": 900, "contact_id": 1, "pipeline_id": 1, "stage": "new_fb_lead", "status": "open"},
                           {"id": 901, "contact_id": 3, "pipeline_id": 1, "stage": "new_fb_lead", "status": "open"}]
    [l for l in DB["leads"] if l["id"] == 3][0]["phone"] = "(561) 555-0103"


def slot_labels(day_iso):
    d = [x for x in oo.public_slots()["days"] if x["date"] == day_iso]
    return [x["label"] for x in d[0]["slots"]] if d else []


def link_parts(html_body, action):
    import html as H, urllib.parse as U
    m = re.search(r'href="([^"]*/approve\?[^"]*a=' + action + r'[^"]*)"', html_body)
    q = dict(U.parse_qsl(U.urlparse(H.unescape(m.group(1))).query))
    return int(q["r"]), q["a"], q["s"]


def test_slots():
    reset_hold()
    with Frozen(MON_8AM_ET):
        days = oo.public_slots()["days"]
        check("slots: 20-minute calls", oo.public_slots()["minutes"] == 20)
        check("slots: today respects 4h notice (from noon)", slot_labels("2026-10-05") == ["12:00 PM", "12:30 PM", "1:00 PM", "1:30 PM", "2:00 PM", "2:30 PM"], str(slot_labels("2026-10-05")))
        check("slots: Tue 9:30 AM-3 PM, last start 2:30", slot_labels("2026-10-06")[0] == "9:30 AM" and slot_labels("2026-10-06")[-1] == "2:30 PM" and len(slot_labels("2026-10-06")) == 11)
        check("slots: Wed 10 AM-5 PM, last start 4:30", slot_labels("2026-10-07")[0] == "10:00 AM" and slot_labels("2026-10-07")[-1] == "4:30 PM" and len(slot_labels("2026-10-07")) == 14)
        check("slots: no weekends", not slot_labels("2026-10-10") and not slot_labels("2026-10-11"))
        check("slots: 10 days ahead, not 11", days[-1]["date"] == "2026-10-15", days[-1]["date"])
        # a time Joe already offered someone is not shown to anyone else
        DB["booking_requests"].append({"id": 77, "workspace_id": 1, "status": "times_sent", "token": "x",
            "proposed_slots": [{"start": "2026-10-06T14:00:00+00:00", "minutes": 30}]})
        tue = slot_labels("2026-10-06")
        check("slots: offered 10:00-10:30 call blocks 10:00", "10:00 AM" not in tue, str(tue[:4]))
        check("slots: 10-min buffer after it also blocks 10:30", "10:30 AM" not in tue)
        check("slots: 9:30 (ends 9:50) and 11:00 stay open", tue[:2] == ["9:30 AM", "11:00 AM"], str(tue[:3]))


def test_hold_and_approve():
    reset_hold()
    with Frozen(MON_8AM_ET):
        tue_10 = "2026-10-06T14:00:00+00:00"
        raises("hold: email required", lambda: oo.hold(oo.HoldIn(start=tue_10, first_name="Amy", email="nope")), 400)
        raises("hold: closed slot rejected", lambda: oo.hold(oo.HoldIn(start="2026-10-10T14:00:00+00:00", first_name="Amy", email="amy@kw.com")), 409)
        MAIL.clear()
        r = oo.hold(oo.HoldIn(start=tue_10, first_name="Amy", last_name="Lee", email="AMY@kw.com",
                              utm={"utm_source": "facebook", "utm_campaign": "commission-report", "evil": "x"}))
        req = the_request()
        check("hold: label for the page", r["label"] == "Tue, Oct 6 at 10:00 AM ET", r["label"])
        check("hold: status held, nothing confirmed", req["status"] == "held" and not req.get("confirmed_start"))
        check("hold: matched the Meta lead by email", req["lead_id"] == 1)
        check("hold: utm kept, junk dropped", req["utm"] == {"utm_source": "facebook", "utm_campaign": "commission-report"})
        check("hold: slot disappears for everyone", "10:00 AM" not in slot_labels("2026-10-06"))
        check("hold: opportunity -> engaged", DB["opportunities"][0]["stage"] == "engaged")
        check("hold: approve task due today", any(t["title"].startswith("Approve 1-on-1: Amy Lee") for t in DB["tasks"]))
        check("hold: no confirmation sent to the agent yet", all(x["to"] != "amy@kw.com" for x in MAIL))
        joe = [x for x in MAIL if x["to"] == "joe@desaneteam.com"][0]
        check("hold: Joe gets 3 approval links", all(f"a={a}" in joe["html"] for a in ("approve", "zoom", "other")))
        check("hold: Joe warned there's no phone", "No phone number on file" in joe["html"])
        raises("hold: same slot twice -> taken", lambda: oo.hold(oo.HoldIn(start=tue_10, first_name="Bob", email="bob@remax.net")), 409, "taken")

        rid, a, sig = link_parts(joe["html"], "approve")
        page = oo.approve_page(rid, a, sig).body.decode()
        check("approve link (GET): shows a button, changes nothing", "<form method=\"post\"" in page and the_request()["status"] == "held")
        bad = oo.approve_page(rid, "zoom", sig).body.decode()
        check("approve link: signature is per action", "isn't valid" in bad)
        res = oo.approve_submit(rid, a, sig).body.decode()
        check("approve phone without a number: refused, still held", "no phone number" in res and the_request()["status"] == "held")
        rid, a, sig = link_parts(joe["html"], "zoom")
        res = oo.approve_submit(rid, a, sig).body.decode()
        check("approve zoom without a link: refused", "Zoom link" in res)
        T.SETTINGS["recruit_newsletter"]["zoom_link"] = "https://zoom.us/j/999"
        MAIL.clear()
        res = oo.approve_submit(rid, a, sig).body.decode()
        req = the_request()
        check("approve zoom: confirmed at the held time", "Confirmed" in res and req["status"] == "confirmed" and req["confirmed_start"] == tue_10 and req["confirmed_minutes"] == 20)
        check("approve: opportunity -> appointment_booked", DB["opportunities"][0]["stage"] == "appointment_booked")
        check("approve: agent gets confirmation + Zoom link + .ics", any(x["to"] == "amy@kw.com" and "zoom.us/j/999" in x["html"] and x["attachments"] for x in MAIL))
        check("approve: approve task closed, call task added", all(t["status"] == "done" for t in DB["tasks"] if t["title"].startswith("Approve")) and any(t["title"].startswith("1-on-1 call with Amy") for t in DB["tasks"]))
        res2 = oo.approve_submit(rid, a, sig).body.decode()
        check("approve: second click is harmless", "Confirmed" in res2 and len([x for x in MAIL if x["to"] == "amy@kw.com"]) == 1)
        check("approve: slot stays blocked once confirmed", "10:00 AM" not in slot_labels("2026-10-06"))


def test_hold_other_and_unknown():
    reset_hold()
    with Frozen(MON_8AM_ET):
        wed_11 = "2026-10-07T15:00:00+00:00"
        oo.hold(oo.HoldIn(start=wed_11, first_name="Bob", email="bob@remax.net"))
        req = the_request()
        rid, a, sig = link_parts([x for x in MAIL if x["to"] == "joe@desaneteam.com"][-1]["html"], "other")
        oo.approve_submit(rid, a, sig)
        req = the_request()
        check("other: back to Needs times, slot released", req["status"] == "new" and req["requested_start"] is None)
        check("other: slot open again", "11:00 AM" in slot_labels("2026-10-07"))
        check("other: send-times task", any(t["title"] == "Send 1-on-1 times to Bob" for t in DB["tasks"]))

        oo.hold(oo.HoldIn(start=wed_11, first_name="Bob", email="bob@remax.net"))
        r = oo.approve_admin(the_request()["id"], oo.ApproveIn(meeting="phone"))
        check("admin approve (phone, number on file)", r["status"] == "confirmed" and the_request()["meeting_type"] == "phone")

        n = len(DB["leads"])
        oo.hold(oo.HoldIn(start="2026-10-08T14:00:00+00:00", first_name="Nina", email="nina@new.com"))
        newl = DB["leads"][-1]
        check("unknown email: new lead flagged for review", len(DB["leads"]) == n + 1 and newl["source"] == "meta-report-call" and "unmatched-meta-lead" in newl["tags"])
        before = len(DB["booking_requests"])
        oo.hold(oo.HoldIn(start="2026-10-08T14:30:00+00:00", first_name="x", email="x@x.com", website="spam"))
        check("hold: honeypot stores nothing", len(DB["booking_requests"]) == before)


def test_hold_reminders():
    reset_hold()
    with Frozen(MON_8AM_ET):
        oo.hold(oo.HoldIn(start="2026-10-06T14:00:00+00:00", first_name="Amy", email="amy@kw.com"))
    req = the_request()
    req["created_at"] = MON_8AM_ET.isoformat()   # the real DB stamps now(); the fake uses the wall clock
    with Frozen(MON_8AM_ET + timedelta(hours=1)):
        MAIL.clear()
        check("held: no nudge in the first 2 hours", oo.process()["nudges"] == 0)
    with Frozen(MON_8AM_ET + timedelta(hours=2, minutes=5)):
        r = oo.process()
        check("held: nudge after 2 hours, with approval links", r["nudges"] == 1 and "Waiting on you: Amy" in MAIL[-1]["subject"] and "a=approve" in MAIL[-1]["html"])
    with Frozen(MON_8AM_ET + timedelta(hours=3)):
        check("held: not again within 2 hours", oo.process()["nudges"] == 0)
    with Frozen(datetime(2026, 10, 6, 14, 1, tzinfo=timezone.utc)):
        MAIL.clear()
        oo.process()
        req = the_request()
        check("held: expires when the time passes", req["status"] == "new" and req["requested_start"] is None)
        check("held: agent told new times are coming", any(x["to"] == "amy@kw.com" and x["subject"] == "New times for our call" for x in MAIL))
        check("held: Joe told it was missed", any(x["subject"].startswith("Missed: Amy") for x in MAIL))


def test_availability_admin():
    reset_hold()
    with Frozen(MON_8AM_ET):
        raises("availability: end before start", lambda: oo.put_availability(oo.AvailabilityIn(hours={"0": [["15:00", "09:30"]]})), 400)
        raises("availability: bad length", lambda: oo.put_availability(oo.AvailabilityIn(slot_minutes=5)), 400)
        oo.put_availability(oo.AvailabilityIn(hours={"5": [["10:00", "11:00"]], **{str(d): oo.DEFAULT_AVAILABILITY["hours"][str(d)] for d in range(5)}}, slot_minutes=15))
        check("availability: Saturday opened, 15-min slots", slot_labels("2026-10-10") == ["10:00 AM", "10:25 AM"], str(slot_labels("2026-10-10")))
        check("availability: preview shows upcoming", len(oo.get_availability()["preview"]) == 12)


if __name__ == "__main__":
    for fn in [test_fmt, test_submit, test_send_times_and_pick, test_none_work_and_manual, test_suppressed_agent, test_reminders, test_zoom_vs_phone, test_admin_list,
               test_slots, test_hold_and_approve, test_hold_other_and_unknown, test_hold_reminders, test_availability_admin]:
        fn()
    print(f"\n{T.PASS[0]} passed, {len(T.FAIL)} failed")
    sys.exit(1 if T.FAIL else 0)
