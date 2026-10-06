"""
Meta Lead Ads -> Mission Control.

One code path for both entry points, so they can't drift apart:
  - webhook  POST /api/webhooks/meta-leads (main.py) calls process_leadgen() per lead
  - backfill POST /api/meta-leads/sync (cron every 6h via sync_meta_leads.py) lists
             recent leads on EVERY active form on the Page and processes any leadgen
             ID not already stored, then retries failed ones

Every leadgen ID gets a meta_lead_submissions row (de-dupe key + audit trail).
A lead is fetched with its form, ad, ad set, campaign and all answers, upserted
into leads by email (workspace 1), given an LPT Recruiting opportunity, and Joe
gets an email for every new Meta lead. A failed fetch emails Joe too, so this
can't break silently again. Meta Testing Tool leads (dummy "<test lead: ...>"
values) run the full path and alert as TEST, but never touch a real contact.

No drip enrollment: the Commission Report form promises a personal message from
Joe within 24 hours (Joe, 2026-10-06).

All email goes through main.send_email(). The page token never leaves the server.
"""
from fastapi import APIRouter
from typing import Optional, Any, Dict, List, Tuple
from datetime import datetime, timedelta, timezone
import html as _html
import json
import re
import urllib.parse
import urllib.request
import urllib.error

router = APIRouter(prefix="/api/meta-leads", tags=["meta-leads"])

_supabase: Any = None
WS = 1
GRAPH = "https://graph.facebook.com/v26.0"
LEAD_FIELDS = "created_time,form_id,ad_id,ad_name,adset_name,campaign_name,platform,is_organic,field_data"
REQUIRED_SCOPES = ("leads_retrieval", "pages_manage_ads", "pages_show_list", "pages_read_engagement")
SYNC_LOOKBACK_DAYS = 3
MAX_ATTEMPTS = 5
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_form_names: Dict[str, str] = {}


def setup(db_callable, supabase_client):
    global _supabase
    _supabase = supabase_client


def _t(name: str):
    return _supabase.table(name)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _esc(s) -> str:
    return _html.escape(str(s or ""), quote=True)


def _settings() -> dict:
    from main import load_settings
    return load_settings() or {}


def _token() -> str:
    return _settings().get("meta_page_access_token", "") or ""


# ════════════════════════════════════════════════════════════
# Graph API
# ════════════════════════════════════════════════════════════

def _graph(path: str, **params) -> Tuple[bool, dict]:
    """GET a Graph API path. Returns (ok, data_or_error). Never logs the token."""
    token = _token()
    if not token:
        return False, {"message": "No Meta page access token configured"}
    params["access_token"] = token
    url = f"{GRAPH}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return True, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode() or "{}")
        except Exception:
            body = {}
        err = body.get("error") or {}
        return False, {"status": e.code, "message": err.get("message") or f"HTTP {e.code}",
                       "code": err.get("code"), "type": err.get("type")}
    except Exception as e:
        return False, {"message": str(e)[:300]}


def _form_name(form_id: str) -> str:
    if not form_id:
        return ""
    if form_id not in _form_names:
        ok, data = _graph(form_id, fields="name")
        if ok and data.get("name"):
            _form_names[form_id] = data["name"]
        else:
            return ""
    return _form_names[form_id]


# ════════════════════════════════════════════════════════════
# Answers
# ════════════════════════════════════════════════════════════

def parse_answers(field_data: List[dict]) -> Dict[str, str]:
    """Map Meta field_data to our fields by keyword, so renamed questions and new
    forms keep working. Keys look like 'what_is_your_average_sale_price?'."""
    raw = {}
    for f in field_data or []:
        vals = f.get("values") or []
        if vals:
            raw[(f.get("name") or "").lower()] = str(vals[0]).strip()

    def find(*needles, exclude=()):
        for k, v in raw.items():
            if any(n in k for n in needles) and not any(x in k for x in exclude):
                return v
        return ""

    out = {
        "email": raw.get("email") or find("email"),
        "full_name": raw.get("full_name") or raw.get("name") or "",
        "first_name": raw.get("first_name", ""),
        "last_name": raw.get("last_name", ""),
        "phone": raw.get("phone_number") or raw.get("phone") or find("phone"),
        "deals_per_year": find("transaction", "deals_", "how_many_deals", "closings"),
        "avg_price": find("sale_price", "average_price", "avg_price", "average_sale", "price_point"),
        "commission_split": find("split"),
        "current_brokerage": find("brokerage", exclude=("split",)),
    }
    if not out["full_name"]:
        out["full_name"] = f"{out['first_name']} {out['last_name']}".strip()
    out["raw"] = raw
    return out


def _is_test(answers: Dict[str, Any]) -> bool:
    vals = list((answers.get("raw") or {}).values())
    return answers.get("email", "").lower() == "test@meta.com" or any(v.lower().startswith("<test lead") for v in vals)


# ════════════════════════════════════════════════════════════
# Alerts (main.send_email)
# ════════════════════════════════════════════════════════════

def _alert(subject: str, rows: List[tuple], intro: str = "", campaign: str = "meta-lead-alert",
           link: Optional[str] = None):
    try:
        from main import send_email
        import recruit_newsletter as rn
        s = rn._settings()
        to = s.get("notify_email") or s.get("reply_to")
        smtp = (_settings().get("smtp") or {})
        if not to or not smtp.get("pass"):
            print(f"[meta] alert skipped (no recipient or Resend key): {subject}")
            return
        body = "".join(
            f'<tr><td style="padding:6px 14px 6px 0;color:#666;font-size:13px;vertical-align:top;white-space:nowrap;">{_esc(k)}</td>'
            f'<td style="padding:6px 0;font-size:14px;color:#1a1a2e;">{_esc(v)}</td></tr>'
            for k, v in rows if v not in (None, "")
        )
        html = (
            '<div style="font-family:Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;padding:24px;">'
            f'<h2 style="color:#6c63ff;margin:0 0 10px 0;font-size:18px;">{_esc(subject)}</h2>'
            + (f'<p style="font-size:15px;line-height:1.55;margin:0 0 14px 0;color:#1a1a2e;">{intro}</p>' if intro else "")
            + f'<table style="border-collapse:collapse;">{body}</table>'
            + (f'<p style="margin-top:20px;"><a href="{link}" style="display:inline-block;background:#6c63ff;color:#fff;padding:10px 18px;'
               'border-radius:6px;text-decoration:none;font-weight:bold;">Open in Mission Control</a></p>' if link else "")
            + '</div>'
        )
        send_email(smtp, to, subject, html, from_address=s.get("from_address") or "", campaign=campaign)
    except Exception as e:
        print(f"[meta] alert failed: {e}")


def _alert_failure(sub: dict, error: str):
    """Once per leadgen ID, so retries don't spam."""
    if sub.get("alerted_failure_at"):
        return
    _alert(
        "Meta lead NOT stored: action needed",
        [("Meta lead ID", sub.get("leadgen_id")), ("Form", sub.get("form_name") or sub.get("form_id")),
         ("Error", error), ("Arrived via", sub.get("via"))],
        intro="A Meta lead arrived but could not be fetched or stored. The 6-hour sync will retry it "
              "automatically; if the error mentions the access token, the Page token needs attention.",
        campaign="meta-lead-failure",
    )
    _t("meta_lead_submissions").update({"alerted_failure_at": _iso(_now())}).eq("leadgen_id", sub["leadgen_id"]).execute()


# ════════════════════════════════════════════════════════════
# Core: one leadgen ID -> stored lead
# ════════════════════════════════════════════════════════════

def _submission(leadgen_id: str) -> Optional[dict]:
    r = _t("meta_lead_submissions").select("*").eq("leadgen_id", leadgen_id).limit(1).execute().data
    return r[0] if r else None


def _fail(sub: dict, error: str) -> dict:
    _t("meta_lead_submissions").update({"status": "failed", "error": error[:500], "processed_at": _iso(_now())}) \
        .eq("leadgen_id", sub["leadgen_id"]).execute()
    _alert_failure({**sub, "status": "failed"}, error)
    return {"leadgen_id": sub["leadgen_id"], "status": "failed", "error": error}


def process_leadgen(leadgen_id: str, form_id_hint: str = "", via: str = "webhook") -> dict:
    leadgen_id = str(leadgen_id or "").strip()
    if not leadgen_id:
        return {"status": "ignored", "error": "no leadgen_id"}

    sub = _submission(leadgen_id)
    if sub and sub["status"] in ("stored", "test"):
        return {"leadgen_id": leadgen_id, "status": "duplicate", "lead_id": sub.get("lead_id")}
    if sub:
        _t("meta_lead_submissions").update({"status": "received", "attempts": int(sub.get("attempts") or 0) + 1, "via": via}) \
            .eq("leadgen_id", leadgen_id).execute()
        sub = {**sub, "attempts": int(sub.get("attempts") or 0) + 1, "via": via}
    else:
        try:
            sub = _t("meta_lead_submissions").insert({"workspace_id": WS, "leadgen_id": leadgen_id, "form_id": form_id_hint or None,
                                                      "status": "received", "attempts": 1, "via": via}).execute().data[0]
        except Exception:
            # the webhook and the sync raced on the same ID; whoever inserted first owns it
            sub = _submission(leadgen_id)
            if not sub:
                return {"leadgen_id": leadgen_id, "status": "failed", "error": "could not record submission"}
            if sub["status"] in ("stored", "test"):
                return {"leadgen_id": leadgen_id, "status": "duplicate", "lead_id": sub.get("lead_id")}

    ok, lead = _graph(leadgen_id, fields=LEAD_FIELDS)
    if not ok:
        return _fail(sub, f"Graph API fetch failed: {lead.get('message')} (code {lead.get('code')})")

    form_id = lead.get("form_id") or form_id_hint or ""
    form_name = _form_name(form_id) or "Meta Lead Form"
    meta = {
        "form_id": form_id, "form_name": form_name, "ad_id": lead.get("ad_id"), "ad_name": lead.get("ad_name"),
        "adset_name": lead.get("adset_name"), "campaign_name": lead.get("campaign_name"),
        "platform": lead.get("platform"), "is_organic": lead.get("is_organic"),
        "field_data": lead.get("field_data") or [],
    }
    _t("meta_lead_submissions").update(meta).eq("leadgen_id", leadgen_id).execute()
    sub = {**sub, **meta}
    answers = parse_answers(meta["field_data"])
    email = (answers.get("email") or "").strip().lower()

    if _is_test(answers):
        _t("meta_lead_submissions").update({"status": "test", "error": None, "processed_at": _iso(_now())}) \
            .eq("leadgen_id", leadgen_id).execute()
        _alert(f"TEST Meta lead received: {form_name}", _alert_rows(answers, meta, leadgen_id),
               intro="Meta's Lead Ads Testing Tool lead: fetched and parsed successfully. Real leads from this form "
                     "will be stored as contacts. Test leads are not.", campaign="meta-lead-test")
        return {"leadgen_id": leadgen_id, "status": "test", "form_name": form_name, "answers": {k: v for k, v in answers.items() if k != "raw"}}

    if not _EMAIL_RE.match(email):
        return _fail(sub, f"No valid email in the lead (got {answers.get('email')!r})")

    lead_id, created = _upsert_lead(answers, meta, email, leadgen_id)
    _t("meta_lead_submissions").update({"status": "stored", "error": None, "lead_id": lead_id, "processed_at": _iso(_now())}) \
        .eq("leadgen_id", leadgen_id).execute()
    _alert(f"New Meta lead: {answers.get('full_name') or email}" + ("" if created else " (existing contact)"),
           _alert_rows(answers, meta, leadgen_id),
           intro=("New contact created" if created else "Matched an existing contact") +
                 f" from <b>{_esc(form_name)}</b>. They were told to expect a message from you within 24 hours.",
           link=f"https://mission.tplcollective.ai/#contacts")
    return {"leadgen_id": leadgen_id, "status": "stored", "lead_id": lead_id, "created": created, "form_name": form_name}


def _alert_rows(a: dict, meta: dict, leadgen_id: str) -> List[tuple]:
    return [
        ("Name", a.get("full_name")), ("Email", a.get("email")), ("Phone", a.get("phone")),
        ("Transactions (12 mo)", a.get("deals_per_year")), ("Avg sale price", a.get("avg_price")),
        ("Current split", a.get("commission_split")), ("Brokerage", a.get("current_brokerage")),
        ("Form", meta.get("form_name")), ("Ad", meta.get("ad_name")), ("Ad set", meta.get("adset_name")),
        ("Campaign", meta.get("campaign_name")),
        ("Platform", {"fb": "Facebook", "ig": "Instagram"}.get(meta.get("platform") or "", meta.get("platform"))),
        ("Meta lead ID", leadgen_id),
    ]


def _upsert_lead(a: dict, meta: dict, email: str, leadgen_id: str) -> Tuple[int, bool]:
    form_name = meta.get("form_name") or "Meta Lead Form"
    ad_name = meta.get("ad_name") or ""
    source_page = f"{ad_name} - {form_name}" if ad_name else form_name
    name = a.get("full_name") or email
    parts = name.split(" ", 1)
    answers = {k: a[k] for k in ("deals_per_year", "avg_price", "commission_split", "current_brokerage") if a.get(k)}
    form_tag = re.sub(r"[^a-z0-9]+", "-", form_name.lower()).strip("-")[:40]

    existing = (_t("leads").select("*").eq("workspace_id", WS).ilike("email", email).order("id").limit(1).execute().data or [None])[0]
    if existing:
        lead_id = existing["id"]
        upd = {**answers, "updated_at": _iso(_now()), "source_page": source_page,
               "tags": sorted(set((existing.get("tags") or []) + ["meta-ad", form_tag]))}
        if not existing.get("phone") and a.get("phone"):
            upd["phone"] = a["phone"]
        if (existing.get("lead_temperature") or "") not in ("hot",):
            upd["lead_temperature"] = "warm"
        _t("leads").update(upd).eq("id", lead_id).execute()
        created = False
    else:
        lead_id = _t("leads").insert({
            **answers, "workspace_id": WS, "name": name, "first_name": a.get("first_name") or parts[0],
            "last_name": a.get("last_name") or (parts[1] if len(parts) > 1 else ""), "email": email,
            "phone": a.get("phone") or "", "source": "Meta Ads", "source_page": source_page,
            "stage": "new_fb_lead", "status": "new", "lead_temperature": "warm", "tags": ["meta-ad", form_tag],
            "notes": f"Meta Lead Ad via {form_name}" + (f" (ad: {ad_name})" if ad_name else "") + f". Meta lead ID {leadgen_id}.",
        }).execute().data[0]["id"]
        created = True

    # LPT Recruiting opportunity at New FB Lead, unless one is already open
    try:
        opp = (_t("opportunities").select("id").eq("contact_id", lead_id).eq("pipeline_id", 1).eq("status", "open")
               .limit(1).execute().data)
        if not opp:
            _t("opportunities").insert({
                "workspace_id": WS, "contact_id": lead_id, "pipeline_id": 1, "stage": "new_fb_lead",
                "source": f"Meta Ads - {form_name}", "status": "open",
                "notes": f"Meta lead form. Ad: {ad_name or 'N/A'}. Campaign: {meta.get('campaign_name') or 'N/A'}.",
            }).execute()
    except Exception as e:
        print(f"[meta] opportunity insert failed: {e}")

    try:
        _t("lead_activity").insert({
            "workspace_id": WS, "lead_id": lead_id, "activity_type": "form_submission",
            "description": f"Submitted Meta lead form: {form_name}" + (f" (ad: {ad_name})" if ad_name else ""),
            "metadata": {"leadgen_id": leadgen_id, "form_id": meta.get("form_id"), "form": form_name, "ad": ad_name,
                         "adset": meta.get("adset_name"), "campaign": meta.get("campaign_name"),
                         "platform": meta.get("platform"), "answers": {k: v for k, v in a.items() if k != "raw"}},
        }).execute()
    except Exception as e:
        print(f"[meta] lead_activity insert failed: {e}")
    try:
        _t("activity_log").insert({
            "workspace_id": WS, "type": "meta_lead",
            "message": f"{'New' if created else 'Existing'} Meta lead: {name} ({email}) - {form_name}",
            "meta": {"lead_id": lead_id, "leadgen_id": leadgen_id, "form": form_name, "ad": ad_name},
        }).execute()
    except Exception:
        pass
    return lead_id, created


# ════════════════════════════════════════════════════════════
# Webhook helper (called from main.py)
# ════════════════════════════════════════════════════════════

def handle_webhook_payload(data: dict) -> List[dict]:
    out = []
    for entry in data.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            if change.get("field") != "leadgen":
                continue
            v = change.get("value", {}) or {}
            out.append(process_leadgen(v.get("leadgen_id", ""), form_id_hint=str(v.get("form_id") or ""), via="webhook"))
    return out


# ════════════════════════════════════════════════════════════
# Backfill + token health (cron, loopback)
# ════════════════════════════════════════════════════════════

def _active_forms() -> Tuple[List[dict], Optional[str]]:
    page = _settings().get("meta_page_id", "")
    if not page:
        return [], "No meta_page_id configured"
    forms, after = [], None
    for _ in range(20):
        params = {"fields": "id,name,status", "limit": 100}
        if after:
            params["after"] = after
        ok, data = _graph(f"{page}/leadgen_forms", **params)
        if not ok:
            return forms, data.get("message")
        forms += [f for f in data.get("data", []) if f.get("status") == "ACTIVE"]
        after = ((data.get("paging") or {}).get("cursors") or {}).get("after") if (data.get("paging") or {}).get("next") else None
        if not after:
            break
    for f in forms:
        _form_names[f["id"]] = f.get("name") or ""
    return forms, None


@router.post("/sync")
def sync(lookback_days: int = SYNC_LOOKBACK_DAYS):
    since = int((_now() - timedelta(days=max(1, min(lookback_days, 90)))).timestamp())
    forms, err = _active_forms()
    summary = {"forms": len(forms), "seen": 0, "processed": 0, "stored": 0, "test": 0, "failed": 0, "retried": 0, "errors": []}
    if err:
        summary["errors"].append(err)
    for f in forms:
        after = None
        for _ in range(10):
            params = {"fields": "id", "limit": 100,
                      "filtering": json.dumps([{"field": "time_created", "operator": "GREATER_THAN", "value": since}])}
            if after:
                params["after"] = after
            ok, data = _graph(f"{f['id']}/leads", **params)
            if not ok:
                summary["errors"].append(f"{f.get('name')}: {data.get('message')}")
                break
            for row in data.get("data", []):
                summary["seen"] += 1
                sub = _submission(row["id"])
                if sub and sub["status"] in ("stored", "test"):
                    continue
                res = process_leadgen(row["id"], form_id_hint=f["id"], via="sync")
                summary["processed"] += 1
                summary[res["status"]] = summary.get(res["status"], 0) + 1
            paging = data.get("paging") or {}
            after = (paging.get("cursors") or {}).get("after") if paging.get("next") else None
            if not after:
                break
    # retry anything still failed (e.g. the token was briefly broken)
    failed = (_t("meta_lead_submissions").select("leadgen_id, form_id, attempts").eq("status", "failed")
              .lt("attempts", MAX_ATTEMPTS).execute().data or [])
    for r in failed:
        res = process_leadgen(r["leadgen_id"], form_id_hint=r.get("form_id") or "", via="sync")
        summary["retried"] += 1
        summary[res["status"]] = summary.get(res["status"], 0) + 1
    if summary["errors"]:
        _alert("Meta lead sync hit errors", [("Errors", "; ".join(summary["errors"])[:900])],
               intro="The 6-hour Meta backfill could not read some forms. If this mentions the access token, "
                     "the Page token needs attention.", campaign="meta-sync-error")
    return summary


@router.post("/token-check")
def token_check():
    token = _token()
    problems = []
    info = {}
    if not token:
        problems.append("No Meta page access token configured.")
    else:
        ok, data = _graph("debug_token", input_token=token)
        d = (data.get("data") or {}) if ok else {}
        if not ok:
            problems.append(f"Meta rejected the token check: {data.get('message')}")
        elif not d.get("is_valid"):
            problems.append(f"Token is INVALID: {(d.get('error') or {}).get('message', 'no reason given')}")
        else:
            scopes = d.get("scopes") or []
            missing = [x for x in REQUIRED_SCOPES if x not in scopes]
            if missing:
                problems.append(f"Token is missing permissions: {', '.join(missing)}")
            for key, label in (("expires_at", "Token expires"), ("data_access_expires_at", "Data access expires")):
                ts = int(d.get(key) or 0)
                if ts and datetime.fromtimestamp(ts, timezone.utc) - _now() <= timedelta(days=14):
                    problems.append(f"{label} {datetime.fromtimestamp(ts, timezone.utc).strftime('%b %d, %Y')}")
        info = {"type": d.get("type"), "valid": d.get("is_valid"), "scopes_ok": not any("missing" in p for p in problems),
                "expires_at": d.get("expires_at"), "data_access_expires_at": d.get("data_access_expires_at")}
    if problems:
        _alert("Meta lead token needs attention", [("Problem", p) for p in problems],
               intro="Meta leads may stop arriving in Mission Control until this is fixed.",
               campaign="meta-token-alert")
    return {"ok": not problems, "problems": problems, **info}


@router.get("/submissions")
def submissions(status: Optional[str] = None, limit: int = 50):
    q = _t("meta_lead_submissions").select("leadgen_id, form_name, ad_name, status, error, lead_id, via, attempts, received_at, processed_at")
    if status:
        q = q.eq("status", status)
    return {"submissions": q.order("received_at", desc=True).limit(min(limit, 200)).execute().data or []}
