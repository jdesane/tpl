"""
Tests for meta_leads.py: webhook fetch/store/alert, de-dupe on leadgen ID,
answer mapping, test leads, failure alerts + retry, all-forms backfill, and the
token health check. Graph API is faked; reuses the in-memory Supabase fake.

Run:  python tests/test_meta_leads.py   (from mission-control/app)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_recruit_newsletter as T  # sets up the `main` stub + fake DB  # noqa: E402
from test_recruit_newsletter import check, DB  # noqa: E402

import meta_leads as ml  # noqa: E402

ml.setup(None, T.FakeSupabase())
T.DEFAULTS["meta_lead_submissions"] = lambda: {"workspace_id": 1, "status": "received", "attempts": 0, "error": None,
                                               "lead_id": None, "alerted_failure_at": None, "field_data": []}

MAIL = []


def _send(smtp, to, subject, html, from_address="", contact_id=None, campaign="", reply_to="", attachments=None):
    MAIL.append({"to": to, "subject": subject, "html": html, "campaign": campaign})
    return True, ""


sys.modules["main"].send_email = _send

# The real field keys from "Commission Report FINAL - Oct 2026"
REAL_FIELDS = [
    {"name": "how_many_transactions_did_you_close_in_the_last_12_months?", "values": ["12"]},
    {"name": "what_is_your_average_sale_price?", "values": ["$450,000"]},
    {"name": "what_is_your_current_commission_split?", "values": ["70/30"]},
    {"name": "who_is_your_current_brokerage?", "values": ["Keller Williams Jupiter"]},
    {"name": "email", "values": ["Dana.Real@Example.com"]},
    {"name": "full_name", "values": ["Dana Real"]},
    {"name": "phone", "values": ["+15615550199"]},
]
TEST_FIELDS = [{"name": "email", "values": ["test@meta.com"]},
               {"name": "full_name", "values": ["<test lead: dummy data for full_name>"]},
               {"name": "who_is_your_current_brokerage?", "values": ["<test lead: dummy data for who_is_your_current_brokerage?>"]}]

GRAPH = {}       # path -> response dict, or ("ERR", {...})
CALLS = []


def fake_graph(path, **params):
    CALLS.append((path, params))
    r = GRAPH.get(path)
    if r is None:
        return False, {"status": 404, "message": f"Unknown path {path}", "code": 100}
    if isinstance(r, tuple) and r[0] == "ERR":
        return False, r[1]
    return True, r


ml._graph = fake_graph


def reset():
    T.reset(); T.seed_leads()
    DB["meta_lead_submissions"] = []
    DB["opportunities"] = []
    DB["lead_activity"] = []
    DB["activity_log"] = []
    T.SEQ["leads"] = 100
    T.SETTINGS.update({"meta_page_access_token": "page-token", "meta_page_id": "221433304542300", "smtp": {"pass": "re_x"}})
    T.SETTINGS["recruit_newsletter"] = {"notify_email": "joe@desaneteam.com"}
    GRAPH.clear(); CALLS.clear(); MAIL.clear(); ml._form_names.clear()
    GRAPH["1641628107309731"] = {"name": "Commission Report FINAL - Oct 2026"}


def lead_resp(fields, form="1641628107309731", ad="KW 30% Reality - Video", organic=False):
    return {"id": "x", "form_id": form, "ad_name": ad, "adset_name": "PBC KW agents", "campaign_name": "Commission Report Oct",
            "platform": "ig", "is_organic": organic, "field_data": fields}


def webhook(leadgen_id, form="1641628107309731"):
    return ml.handle_webhook_payload({"entry": [{"changes": [{"field": "leadgen", "value": {"leadgen_id": leadgen_id, "form_id": form, "page_id": "p"}}]}]})


def test_answer_mapping():
    a = ml.parse_answers(REAL_FIELDS)
    check("map: transactions -> deals_per_year", a["deals_per_year"] == "12")
    check("map: avg sale price -> avg_price", a["avg_price"] == "$450,000")
    check("map: split -> commission_split", a["commission_split"] == "70/30")
    check("map: brokerage -> current_brokerage (not the split question)", a["current_brokerage"] == "Keller Williams Jupiter")
    check("map: phone key 'phone'", a["phone"] == "+15615550199")
    b = ml.parse_answers([{"name": "first_name", "values": ["Al"]}, {"name": "last_name", "values": ["Bee"]},
                          {"name": "phone_number", "values": ["1"]}, {"name": "work_email", "values": ["a@b.co"]}])
    check("map: first+last fallback, phone_number, email by keyword", b["full_name"] == "Al Bee" and b["phone"] == "1" and b["email"] == "a@b.co")


def test_new_lead_via_webhook():
    reset()
    GRAPH["900001"] = lead_resp(REAL_FIELDS)
    r = webhook("900001")[0]
    lead = DB["leads"][-1]
    check("webhook: stored as a new lead", r["status"] == "stored" and r["created"] and lead["id"] == r["lead_id"])
    check("webhook: email lowercased", lead["email"] == "dana.real@example.com")
    check("webhook: answers mapped onto the lead", lead["deals_per_year"] == "12" and lead["avg_price"] == "$450,000"
          and lead["commission_split"] == "70/30" and lead["current_brokerage"] == "Keller Williams Jupiter")
    check("webhook: form + ad saved on the lead", lead["source_page"] == "KW 30% Reality - Video - Commission Report FINAL - Oct 2026" and lead["source"] == "Meta Ads")
    check("webhook: workspace 1, stage new_fb_lead", lead["workspace_id"] == 1 and lead["stage"] == "new_fb_lead")
    check("webhook: LPT Recruiting opportunity at New FB Lead", any(o["contact_id"] == lead["id"] and o["pipeline_id"] == 1 and o["stage"] == "new_fb_lead" for o in DB["opportunities"]))
    check("webhook: NO drip enrollment", not DB.get("email_funnel_enrollments"))
    act = DB["lead_activity"][-1]
    check("webhook: timeline entry uses the real columns", act["activity_type"] == "form_submission" and act["metadata"]["leadgen_id"] == "900001")
    sub = DB["meta_lead_submissions"][0]
    check("webhook: submission recorded as stored with form/ad", sub["status"] == "stored" and sub["form_name"].startswith("Commission Report FINAL") and sub["ad_name"] == "KW 30% Reality - Video")
    check("webhook: Joe alerted with the answers", MAIL and MAIL[-1]["subject"] == "New Meta lead: Dana Real" and "70/30" in MAIL[-1]["html"] and "Instagram" in MAIL[-1]["html"])
    check("webhook: lead fetched with ad/campaign fields on v26", CALLS[0][0] == "900001" and "ad_name" in CALLS[0][1]["fields"] and ml.GRAPH.endswith("v26.0"))

    n_leads, n_mail = len(DB["leads"]), len(MAIL)
    r = webhook("900001")[0]
    check("de-dupe: same leadgen ID again is ignored", r["status"] == "duplicate" and len(DB["leads"]) == n_leads and len(MAIL) == n_mail)


def test_existing_contact():
    reset()
    GRAPH["900002"] = lead_resp([{"name": "email", "values": ["AMY@kw.com"]}, {"name": "full_name", "values": ["Amy Lee"]},
                                 {"name": "what_is_your_current_commission_split?", "values": ["80/20"]}])
    n = len(DB["leads"])
    r = webhook("900002")[0]
    amy = [l for l in DB["leads"] if l["id"] == 1][0]
    check("existing: matched by email, no duplicate contact", r["status"] == "stored" and not r["created"] and r["lead_id"] == 1 and len(DB["leads"]) == n)
    check("existing: fresh answers saved", amy["commission_split"] == "80/20" and "meta-ad" in amy["tags"])
    check("existing: alert says existing contact", "(existing contact)" in MAIL[-1]["subject"])


def test_test_leads():
    reset()
    GRAPH["4764951233791035"] = lead_resp(TEST_FIELDS, organic=True, ad=None)
    before = [dict(l) for l in DB["leads"]]
    r = webhook("4764951233791035")[0]
    check("test lead: recognized", r["status"] == "test")
    check("test lead: no contact created or changed", DB["leads"] == before)
    check("test lead: alert marked TEST", MAIL and MAIL[-1]["subject"].startswith("TEST Meta lead received"))
    check("test lead: submission status test", DB["meta_lead_submissions"][0]["status"] == "test")


def test_failure_and_retry():
    reset()
    GRAPH["900003"] = ("ERR", {"status": 400, "message": "Error validating access token", "code": 190})
    r = webhook("900003")[0]
    sub = DB["meta_lead_submissions"][0]
    check("fail: recorded as failed with the error", r["status"] == "failed" and sub["status"] == "failed" and "code 190" in sub["error"])
    check("fail: Joe alerted", MAIL and MAIL[-1]["subject"] == "Meta lead NOT stored: action needed")
    n = len(MAIL)
    webhook("900003")
    check("fail: no repeat alert for the same lead", len(MAIL) == n)
    # token fixed; the sync retries and stores it
    GRAPH["900003"] = lead_resp(REAL_FIELDS)
    GRAPH["221433304542300/leadgen_forms"] = {"data": []}
    s = ml.sync()
    check("retry: sync stores the failed lead", s["retried"] == 1 and DB["meta_lead_submissions"][0]["status"] == "stored")

    reset()
    GRAPH["900004"] = lead_resp([{"name": "full_name", "values": ["No Email"]}])
    r = webhook("900004")[0]
    check("fail: lead without a valid email is flagged, not stored", r["status"] == "failed" and "valid email" in r["error"])


def test_sync_all_forms():
    reset()
    GRAPH["221433304542300/leadgen_forms"] = {"data": [
        {"id": "1641628107309731", "name": "Commission Report FINAL - Oct 2026", "status": "ACTIVE"},
        {"id": "2446350272487229", "name": "KW Commission Comparison - 2026", "status": "ACTIVE"},
        {"id": "378726162745119", "name": "Dummy Form", "status": "ARCHIVED"}]}
    GRAPH["1641628107309731/leads"] = {"data": [{"id": "910001"}, {"id": "910002"}]}
    GRAPH["2446350272487229/leads"] = {"data": [{"id": "910003"}]}
    GRAPH["910001"] = lead_resp(REAL_FIELDS)
    GRAPH["910002"] = lead_resp([{"name": "email", "values": ["second@example.com"]}, {"name": "full_name", "values": ["Second Agent"]}])
    GRAPH["910003"] = lead_resp([{"name": "email", "values": ["kw@example.com"]}, {"name": "full_name", "values": ["KW Agent"]}], form="2446350272487229")
    GRAPH["2446350272487229"] = {"name": "KW Commission Comparison - 2026"}
    webhook("910001")  # one arrived via webhook already
    s = ml.sync()
    check("sync: every ACTIVE form read, archived skipped", s["forms"] == 2 and not any(c[0].startswith("378726162745119") for c in CALLS))
    check("sync: only unseen leads processed", s["seen"] == 3 and s["processed"] == 2 and s["stored"] == 2)
    check("sync: lookback filter sent to Meta", any(c[0] == "1641628107309731/leads" and "time_created" in c[1]["filtering"] for c in CALLS))
    emails = sorted(l["email"] for l in DB["leads"] if l["id"] > 100)
    check("sync: leads from both forms stored once", emails == ["dana.real@example.com", "kw@example.com", "second@example.com"], str(emails))
    s2 = ml.sync()
    check("sync: second run is a no-op", s2["processed"] == 0)


def test_token_check():
    reset()
    GRAPH["debug_token"] = {"data": {"type": "PAGE", "is_valid": True, "expires_at": 0, "data_access_expires_at": 0,
                                     "scopes": ["leads_retrieval", "pages_manage_ads", "pages_show_list", "pages_read_engagement"]}}
    r = ml.token_check()
    check("token: healthy token, no alert", r["ok"] and not MAIL)
    GRAPH["debug_token"]["data"]["scopes"] = ["pages_show_list"]
    r = ml.token_check()
    check("token: missing permissions alert", not r["ok"] and "leads_retrieval" in r["problems"][0] and MAIL[-1]["subject"] == "Meta lead token needs attention")
    import time
    GRAPH["debug_token"]["data"].update({"scopes": list(ml.REQUIRED_SCOPES), "expires_at": int(time.time()) + 5 * 86400})
    r = ml.token_check()
    check("token: expiring within 14 days alerts", not r["ok"] and "expires" in r["problems"][0])
    GRAPH["debug_token"] = {"data": {"is_valid": False, "error": {"message": "Session has expired"}}}
    check("token: invalid alerts", "INVALID" in ml.token_check()["problems"][0])
    T.SETTINGS["meta_page_access_token"] = ""
    check("token: missing token alerts", "No Meta page access token" in ml.token_check()["problems"][0])


if __name__ == "__main__":
    for fn in [test_answer_mapping, test_new_lead_via_webhook, test_existing_contact, test_test_leads,
               test_failure_and_retry, test_sync_all_forms, test_token_check]:
        fn()
    print(f"\n{T.PASS[0]} passed, {len(T.FAIL)} failed")
    sys.exit(1 if T.FAIL else 0)
