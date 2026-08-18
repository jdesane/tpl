"""Session 3: Extended API routes — Resources, Referrals, Recruiting Links, Content, AI Actions."""
from fastapi import APIRouter, HTTPException
from models import (
    ResourceIn, ResourceUpdate, ReferralIn, ReferralUpdate,
    RecruitingLinkIn, ContentPostIn, ContentPostUpdate,
    DraftDmRequest, ResearchLeadRequest
)
from typing import Optional
from datetime import datetime, timedelta
from supabase import create_client
import os
import json

router = APIRouter()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ══════════════════════════════════════════
# RESOURCES
# ══════════════════════════════════════════

@router.get("/api/resources")
def list_resources(category: Optional[str] = None, access_level: Optional[str] = None):
    query = supabase.table("resources").select("*").order("created_at", desc=True)
    if category:
        query = query.eq("category", category)
    if access_level:
        query = query.eq("access_level", access_level)
    return query.execute().data


@router.post("/api/resources")
def create_resource(r: ResourceIn):
    result = supabase.table("resources").insert({
        "title": r.title, "description": r.description or "",
        "category": r.category or "", "file_path": r.file_path or "",
        "file_type": r.file_type or "", "access_level": r.access_level or "agent"
    }).execute()
    return {"success": True, "id": result.data[0]["id"]}


@router.get("/api/resources/{resource_id}")
def get_resource(resource_id: int):
    result = supabase.table("resources").select("*").eq("id", resource_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Resource not found")
    return result.data[0]


@router.put("/api/resources/{resource_id}")
def update_resource(resource_id: int, update: ResourceUpdate):
    updates = {}
    for field in ["title", "description", "category", "file_path", "file_type", "access_level"]:
        val = getattr(update, field, None)
        if val is not None:
            updates[field] = val
    if updates:
        supabase.table("resources").update(updates).eq("id", resource_id).execute()
    return {"success": True}


@router.delete("/api/resources/{resource_id}")
def delete_resource(resource_id: int):
    supabase.table("resources").delete().eq("id", resource_id).execute()
    return {"success": True}


@router.post("/api/resources/{resource_id}/download")
def track_download(resource_id: int):
    r = supabase.table("resources").select("download_count, title").eq("id", resource_id).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Resource not found")
    current = r.data[0].get("download_count", 0) or 0
    supabase.table("resources").update({"download_count": current + 1}).eq("id", resource_id).execute()
    supabase.table("activity_log").insert({
        "type": "system", "message": f"Resource downloaded: {r.data[0]['title']}",
        "meta": {"resource_id": resource_id}, "actor": "system", "action": "resource_downloaded",
        "target_type": "resource", "target_id": resource_id
    }).execute()
    return {"success": True}


# ══════════════════════════════════════════
# REFERRALS
# ══════════════════════════════════════════

@router.get("/api/referrals")
def list_referrals(agent_id: Optional[int] = None):
    query = supabase.table("referrals").select("*, agents!referring_agent_id(name)").order("created_at", desc=True)
    if agent_id:
        query = query.eq("referring_agent_id", agent_id)
    return query.execute().data


@router.post("/api/referrals")
def create_referral(r: ReferralIn):
    result = supabase.table("referrals").insert({
        "referring_agent_id": r.referring_agent_id, "referred_name": r.referred_name,
        "referred_email": r.referred_email or "", "referred_phone": r.referred_phone or "",
        "status": "interested"
    }).execute()
    agent = supabase.table("agents").select("name").eq("id", r.referring_agent_id).execute()
    agent_name = agent.data[0]["name"] if agent.data else "Unknown"
    supabase.table("activity_log").insert({
        "type": "lead", "message": f"Referral from {agent_name}: {r.referred_name}",
        "meta": {"referral_id": result.data[0]["id"], "agent_id": r.referring_agent_id},
        "actor": agent_name, "action": "referral_created", "target_type": "referral"
    }).execute()
    return {"success": True, "id": result.data[0]["id"]}


@router.put("/api/referrals/{referral_id}")
def update_referral(referral_id: int, update: ReferralUpdate):
    updates = {"updated_at": datetime.utcnow().isoformat()}
    if update.status is not None:
        updates["status"] = update.status
    if update.lead_id is not None:
        updates["lead_id"] = update.lead_id
    supabase.table("referrals").update(updates).eq("id", referral_id).execute()
    return {"success": True}


# ══════════════════════════════════════════
# RECRUITING LINKS
# ══════════════════════════════════════════

@router.get("/api/recruiting-links")
def list_recruiting_links(target_brokerage: Optional[str] = None):
    query = supabase.table("recruiting_links").select("*").order("target_brokerage").order("page_type")
    if target_brokerage:
        query = query.eq("target_brokerage", target_brokerage)
    return query.execute().data


@router.post("/api/recruiting-links")
def create_recruiting_link(r: RecruitingLinkIn):
    campaign = r.utm_campaign or f"{r.target_brokerage}_{r.page_type}"
    full_url = f"{r.base_url}?utm_source={r.utm_source}&utm_medium={r.utm_medium}&utm_campaign={campaign}"
    result = supabase.table("recruiting_links").insert({
        "target_brokerage": r.target_brokerage, "page_type": r.page_type,
        "page_label": r.page_label, "base_url": r.base_url,
        "utm_source": r.utm_source or "tpl", "utm_medium": r.utm_medium or "recruiting",
        "utm_campaign": campaign, "full_url": full_url
    }).execute()
    return {"success": True, "id": result.data[0]["id"], "full_url": full_url}


@router.get("/api/recruiting-links/{link_id}/click")
def track_click(link_id: int):
    r = supabase.table("recruiting_links").select("click_count, full_url").eq("id", link_id).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Link not found")
    current = r.data[0].get("click_count", 0) or 0
    supabase.table("recruiting_links").update({"click_count": current + 1}).eq("id", link_id).execute()
    return {"success": True, "redirect_url": r.data[0].get("full_url", "")}


# ══════════════════════════════════════════
# CONTENT POSTS
# ══════════════════════════════════════════

@router.get("/api/content")
def list_content(status: Optional[str] = None, platform: Optional[str] = None, category: Optional[str] = None):
    query = supabase.table("content_posts").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    if platform:
        query = query.eq("platform", platform)
    if category:
        query = query.eq("category", category)
    return query.execute().data


@router.post("/api/content")
def create_content(post: ContentPostIn):
    result = supabase.table("content_posts").insert({
        "title": post.title, "body": post.body, "hashtags": post.hashtags or "",
        "platform": post.platform or "all", "category": post.category or "",
        "image_url": post.image_url or "", "recruiting_link_id": post.recruiting_link_id,
        "status": post.status or "draft", "scheduled_at": post.scheduled_at
    }).execute()
    return {"success": True, "id": result.data[0]["id"]}


@router.get("/api/content/analytics")
def content_analytics_inline():
    posts = supabase.table("content_posts").select("platform, impressions, clicks, leads_generated, engagement_rate, status").execute().data
    total_impressions = sum(p.get("impressions", 0) or 0 for p in posts)
    total_clicks = sum(p.get("clicks", 0) or 0 for p in posts)
    total_leads = sum(p.get("leads_generated", 0) or 0 for p in posts)
    posted = [p for p in posts if p.get("status") == "posted"]
    avg_engagement = round(sum(p.get("engagement_rate", 0) or 0 for p in posted) / len(posted), 2) if posted else 0
    platforms = {}
    for p in posts:
        plat = p.get("platform", "all")
        if plat not in platforms:
            platforms[plat] = {"posts": 0, "impressions": 0, "clicks": 0, "leads": 0}
        platforms[plat]["posts"] += 1
        platforms[plat]["impressions"] += p.get("impressions", 0) or 0
        platforms[plat]["clicks"] += p.get("clicks", 0) or 0
        platforms[plat]["leads"] += p.get("leads_generated", 0) or 0
    return {"total_posts": len(posts), "total_impressions": total_impressions, "total_clicks": total_clicks, "total_leads_generated": total_leads, "avg_engagement_rate": avg_engagement, "by_platform": platforms}


@router.get("/api/content/calendar")
def content_calendar_inline(view: str = "monthly", date: str = ""):
    if not date:
        today = datetime.utcnow().date()
    else:
        today = datetime.strptime(date, "%Y-%m-%d").date()
    if view == "weekly":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    else:
        start = today.replace(day=1)
        next_month = (start + timedelta(days=32)).replace(day=1)
        end = next_month - timedelta(days=1)
    posts = supabase.table("content_posts").select("id, title, platform, status, scheduled_at, scheduled_date, posted_at").gte("scheduled_date", start.isoformat()).lte("scheduled_date", end.isoformat()).order("scheduled_date").execute().data
    by_date = {}
    for p in posts:
        sd = p.get("scheduled_date") or (p.get("scheduled_at", "")[:10] if p.get("scheduled_at") else "")
        if sd:
            if sd not in by_date: by_date[sd] = []
            by_date[sd].append(p)
    return {"view": view, "start": start.isoformat(), "end": end.isoformat(), "posts_by_date": by_date}


@router.get("/api/content/{post_id}")
def get_content(post_id: int):
    result = supabase.table("content_posts").select("*").eq("id", post_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Post not found")
    return result.data[0]


@router.put("/api/content/{post_id}")
def update_content(post_id: int, update: ContentPostUpdate):
    updates = {}
    for field in ["title", "body", "hashtags", "platform", "category", "image_url",
                   "recruiting_link_id", "status", "scheduled_at", "posted_at"]:
        val = getattr(update, field, None)
        if val is not None:
            updates[field] = val
    if updates:
        supabase.table("content_posts").update(updates).eq("id", post_id).execute()
    return {"success": True}


@router.delete("/api/content/{post_id}")
def delete_content(post_id: int):
    supabase.table("content_posts").delete().eq("id", post_id).execute()
    return {"success": True}





# ══════════════════════════════════════════
# EMAIL QUEUE
# ══════════════════════════════════════════

@router.get("/api/emails/queue")
def email_queue(status: Optional[str] = None):
    query = supabase.table("email_queue").select("*, leads(name, email)").order("scheduled_at")
    if status:
        query = query.eq("status", status)
    return query.execute().data


@router.get("/api/emails/stats")
def email_stats():
    all_emails = supabase.table("emails_sent").select("created_at").execute().data
    drip_q = supabase.table("drip_queue").select("status").execute().data
    total_sent = len(all_emails)
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    sent_today = sum(1 for e in all_emails if e["created_at"] and e["created_at"][:10] == today_str)
    this_week = sum(1 for e in all_emails if e["created_at"] and e["created_at"][:10] >= (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"))
    drip_pending = sum(1 for d in drip_q if d["status"] == "pending")
    drip_sent = sum(1 for d in drip_q if d["status"] == "sent")
    drip_failed = sum(1 for d in drip_q if d["status"] not in ("pending", "sent", "cancelled", "skipped"))
    return {
        "total_sent": total_sent, "sent_today": sent_today, "sent_this_week": this_week,
        "drip_pending": drip_pending, "drip_sent": drip_sent, "drip_failed": drip_failed
    }


# ══════════════════════════════════════════
# ACTIVITY LOG (POST for OpenClaw)
# ══════════════════════════════════════════

@router.post("/api/activity")
def log_activity(data: dict):
    supabase.table("activity_log").insert({
        "type": data.get("type", "system"),
        "message": data.get("message", ""),
        "meta": data.get("meta", {}),
        "actor": data.get("actor", "openclaw"),
        "action": data.get("action", ""),
        "target_type": data.get("target_type"),
        "target_id": data.get("target_id"),
        "description": data.get("description")
    }).execute()
    return {"success": True}


# ══════════════════════════════════════════
# AI ACTIONS (Lead Scoring + OpenClaw-powered)
# ══════════════════════════════════════════

# Source intent scoring weights
SOURCE_SCORES = {
    "Commission Calculator": 85, "calculator": 85,
    "Fee Plans": 70, "fee_plans": 70,
    "27K Worksheet": 80, "worksheet": 80,
    "Resource Download": 40, "resource": 40,
    "comparison": 75,
    "direct": 50, "Web": 30, "": 20
}

# High-value target brokerages
HIGH_VALUE_BROKERAGES = {"keller williams", "kw", "exp", "exp realty", "remax", "re/max", "coldwell banker", "compass", "century 21", "real brokerage"}


def calculate_lead_score(lead: dict) -> tuple:
    """Calculate lead score (0-100) and temperature. Returns (score, temperature)."""
    score = 0

    # Source intent (0-85)
    source = lead.get("source", "")
    for key, val in SOURCE_SCORES.items():
        if key.lower() in source.lower():
            score = max(score, val)
            break
    if score == 0:
        score = 20  # baseline

    # Brokerage value boost (+10 for high-value targets)
    brokerage = (lead.get("current_brokerage") or lead.get("brokerage") or "").lower()
    if any(hv in brokerage for hv in HIGH_VALUE_BROKERAGES):
        score = min(100, score + 10)

    # Recency decay (-1 per day old, max -20)
    created = lead.get("created_at", "")
    if created:
        try:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00").replace("+00:00", ""))
            days_old = (datetime.utcnow() - created_dt).days
            score = max(0, score - min(days_old, 20))
        except (ValueError, TypeError):
            pass

    # Has production data boost (+5)
    if lead.get("deals_per_year") or lead.get("gci"):
        score = min(100, score + 5)

    score = max(0, min(100, score))
    if score >= 70:
        temp = "hot"
    elif score >= 40:
        temp = "warming"
    else:
        temp = "cold"

    return score, temp


@router.post("/api/ai/score-leads")
def score_all_leads():
    """Recalculate scores for all leads not in signed/onboarding."""
    leads = supabase.table("leads").select("id, source, current_brokerage, brokerage, created_at, deals_per_year, gci, stage").execute().data
    updated = 0
    for lead in leads:
        if lead.get("stage") in ("signed", "onboarding"):
            continue
        score, temp = calculate_lead_score(lead)
        supabase.table("leads").update({
            "lead_score": score, "lead_temperature": temp
        }).eq("id", lead["id"]).execute()
        updated += 1
    supabase.table("activity_log").insert({
        "type": "system", "message": f"Lead scores recalculated: {updated} leads updated",
        "meta": {"updated": updated}, "actor": "openclaw", "action": "lead_scored"
    }).execute()
    return {"success": True, "updated": updated}


@router.post("/api/ai/who-to-call")
def who_to_call():
    """Analyze pipeline and return prioritized call list with reasoning."""
    leads = supabase.table("leads").select("*").not_.in_("stage", ["signed", "onboarding"]).order("lead_score", desc=True).limit(50).execute().data
    now = datetime.utcnow()
    call_list = []

    for lead in leads:
        reasons = []
        priority = 0

        # Overdue follow-up
        fu = lead.get("follow_up_date")
        if fu:
            try:
                fu_dt = datetime.fromisoformat(str(fu).replace("Z", "+00:00").replace("+00:00", ""))
                if fu_dt <= now:
                    days_overdue = (now - fu_dt).days
                    reasons.append(f"Follow-up overdue by {days_overdue}d")
                    priority += 30 + min(days_overdue * 2, 20)
            except (ValueError, TypeError):
                pass

        # Hot lead not yet contacted
        if lead.get("lead_temperature") == "hot" and lead.get("stage") == "new":
            reasons.append("Hot lead, not yet contacted")
            priority += 40

        # Stale lead (no update in 3+ days)
        updated = lead.get("updated_at") or lead.get("created_at", "")
        if updated:
            try:
                up_dt = datetime.fromisoformat(updated.replace("Z", "+00:00").replace("+00:00", ""))
                days_stale = (now - up_dt).days
                if days_stale >= 3 and lead.get("stage") not in ("new",):
                    reasons.append(f"No activity for {days_stale}d")
                    priority += 15
            except (ValueError, TypeError):
                pass

        # High score
        score = lead.get("lead_score", 0)
        priority += score // 5

        if reasons or score >= 60:
            if not reasons:
                reasons.append(f"High intent lead (score: {score})")
            call_list.append({
                "lead_id": lead["id"], "name": lead["name"],
                "brokerage": lead.get("current_brokerage") or lead.get("brokerage", ""),
                "stage": lead.get("stage", "new"), "score": score,
                "temperature": lead.get("lead_temperature", "warming"),
                "reasons": reasons, "priority": priority,
                "suggested_action": _suggest_action(lead)
            })

    call_list.sort(key=lambda x: x["priority"], reverse=True)
    return {"call_list": call_list[:10], "total_actionable": len(call_list)}


def _suggest_action(lead: dict) -> str:
    stage = lead.get("stage", "new")
    if stage == "new":
        return "Research and make first contact"
    elif stage == "contacted":
        return "Schedule discovery call"
    elif stage == "discovery_call":
        return "Prep presentation materials"
    elif stage == "presentation":
        return "Follow up on presentation"
    elif stage == "considering":
        return "Address objections, close"
    return "Follow up"


@router.post("/api/ai/draft-dm")
def draft_dm(req: DraftDmRequest):
    """Draft a personalized outreach message for a lead."""
    lead = supabase.table("leads").select("*").eq("id", req.lead_id).execute()
    if not lead.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead = lead.data[0]

    name = lead["name"].split()[0] if lead.get("name") else "there"
    brokerage = lead.get("current_brokerage") or lead.get("brokerage", "")
    source = lead.get("source", "")
    stage = lead.get("stage", "new")
    deals = lead.get("deals_per_year", "")

    if stage == "new":
        if "calculator" in source.lower() or "Calculator" in source:
            draft = f"Hey {name}, I saw you ran the numbers on the commission calculator. What stood out to you? Most agents from {brokerage or 'traditional brokerages'} are surprised by the gap. Happy to walk through your specific situation if you want - takes about 15 minutes, no pitch. Would that be useful?"
        elif "comparison" in source.lower():
            draft = f"Hey {name}, noticed you were checking out the comparison page. I made the switch myself and the math was eye-opening. Would love to share what I found - especially the stuff that is not on the website. Got 15 minutes this week?"
        else:
            draft = f"Hey {name}, thanks for checking out TPL Collective. I am not a recruiter - I am an active agent who made the switch and built a system around it. If you are curious about the math, I can run your numbers in about 15 minutes. No pressure either way. Interested?"
    elif stage == "contacted":
        draft = f"Hey {name}, just following up from our last conversation. I know switching brokerages is a big decision. Any questions I can answer? I can also run a side-by-side comparison with your {brokerage} numbers if that would help."
    elif stage in ("discovery_call", "presentation"):
        prod = f" With {deals} deals/year," if deals else ""
        draft = f"Hey {name}, wanted to circle back after our call.{prod} the numbers really do speak for themselves. What is the main thing holding you back? Happy to address any concerns directly."
    else:
        draft = f"Hey {name}, just checking in. Any new questions about making the move? I am here whenever you are ready to talk next steps."

    # Save draft to lead
    supabase.table("leads").update({"ai_draft": draft}).eq("id", req.lead_id).execute()

    supabase.table("activity_log").insert({
        "type": "system", "message": f"AI draft created for {lead['name']}",
        "meta": {"lead_id": req.lead_id}, "actor": "openclaw", "action": "outreach_drafted",
        "target_type": "lead", "target_id": req.lead_id
    }).execute()

    return {"success": True, "draft": draft, "lead_id": req.lead_id}


@router.post("/api/ai/weekly-plan")
def weekly_plan():
    """Generate a weekly recruiting action plan based on pipeline state."""
    leads = supabase.table("leads").select("id, name, stage, lead_score, lead_temperature, follow_up_date, last_contacted_at, created_at, current_brokerage, brokerage").not_.in_("stage", ["signed", "onboarding"]).execute().data
    agents = supabase.table("agents").select("id, engagement_score, status").execute().data
    now = datetime.utcnow()

    plan = {"priorities": [], "daily_actions": {}, "metrics_to_watch": []}

    # Categorize leads
    hot_uncontacted = [l for l in leads if l.get("lead_temperature") == "hot" and l.get("stage") == "new"]
    overdue = []
    for l in leads:
        fu = l.get("follow_up_date")
        if fu:
            try:
                fu_dt = datetime.fromisoformat(str(fu).replace("Z", "+00:00").replace("+00:00", ""))
                if fu_dt <= now:
                    overdue.append(l)
            except (ValueError, TypeError):
                pass
    stale_3d = [l for l in leads if l.get("stage") not in ("new",) and _days_since(l.get("updated_at") or l.get("created_at", "")) >= 3]
    in_pipeline = [l for l in leads if l.get("stage") not in ("new",)]
    at_risk_agents = [a for a in agents if a.get("engagement_score", 100) < 30 and a.get("status") == "active"]

    # Priorities
    if hot_uncontacted:
        plan["priorities"].append(f"Contact {len(hot_uncontacted)} hot leads ASAP: {', '.join(l['name'] for l in hot_uncontacted[:3])}")
    if overdue:
        plan["priorities"].append(f"Clear {len(overdue)} overdue follow-ups")
    if stale_3d:
        plan["priorities"].append(f"Re-engage {len(stale_3d)} stale pipeline leads")
    if at_risk_agents:
        plan["priorities"].append(f"Check in with {len(at_risk_agents)} at-risk agents")

    # Daily breakdown
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    all_actions = []
    for l in hot_uncontacted:
        all_actions.append(f"First contact: {l['name']} ({l.get('current_brokerage') or l.get('brokerage', 'Unknown')})")
    for l in overdue:
        all_actions.append(f"Follow up (overdue): {l['name']}")
    for l in stale_3d[:5]:
        all_actions.append(f"Re-engage: {l['name']}")
    for a in at_risk_agents:
        all_actions.append(f"Agent check-in: agent #{a['id']}")

    for i, day in enumerate(days):
        day_actions = all_actions[i::5]  # distribute across days
        plan["daily_actions"][day] = day_actions if day_actions else ["Prospect for new leads", "Create social content"]

    # Metrics
    plan["metrics_to_watch"] = [
        f"Pipeline: {len(in_pipeline)} active leads",
        f"Hot leads: {len(hot_uncontacted)} uncontacted",
        f"Overdue: {len(overdue)} follow-ups",
        f"Active agents: {sum(1 for a in agents if a.get('status') == 'active')}"
    ]

    return plan


def _days_since(date_str: str) -> int:
    if not date_str:
        return 999
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00").replace("+00:00", ""))
        return (datetime.utcnow() - dt).days
    except (ValueError, TypeError):
        return 999


@router.post("/api/ai/generate-tasks")
def auto_generate_tasks():
    """OpenClaw auto-task generation: scan pipeline and create actionable tasks."""
    leads = supabase.table("leads").select("id, name, stage, lead_score, follow_up_date, last_contacted_at, created_at, updated_at").not_.in_("stage", ["signed", "onboarding"]).execute().data
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")
    created = 0

    # Get existing pending tasks to avoid duplicates
    existing = supabase.table("tasks").select("lead_id, task_type").eq("status", "pending").execute().data
    existing_set = {(t["lead_id"], t["task_type"]) for t in existing}

    for lead in leads:
        lid = lead["id"]
        name = lead["name"]

        # Overdue follow-up
        fu = lead.get("follow_up_date")
        if fu and (lid, "follow_up") not in existing_set:
            try:
                fu_dt = datetime.fromisoformat(str(fu).replace("Z", "+00:00").replace("+00:00", ""))
                if fu_dt <= now:
                    days = (now - fu_dt).days
                    supabase.table("tasks").insert({
                        "task_type": "follow_up", "title": f"Follow up with {name}",
                        "description": f"{days}d overdue", "lead_id": lid,
                        "priority": "urgent" if days > 3 else "normal",
                        "due_date": today, "created_by": "openclaw"
                    }).execute()
                    created += 1
            except (ValueError, TypeError):
                pass

        # Hot lead not contacted
        if lead.get("lead_score", 0) >= 70 and lead.get("stage") == "new" and (lid, "send_outreach") not in existing_set:
            supabase.table("tasks").insert({
                "task_type": "send_outreach", "title": f"Contact hot lead: {name}",
                "description": f"Score: {lead.get('lead_score', 0)}, not yet contacted",
                "lead_id": lid, "priority": "urgent", "due_date": today, "created_by": "openclaw"
            }).execute()
            created += 1

        # Stale pipeline lead (no update 5+ days, not new)
        updated = lead.get("updated_at") or lead.get("created_at", "")
        days_stale = _days_since(updated)
        if days_stale >= 5 and lead.get("stage") not in ("new",) and (lid, "follow_up") not in existing_set:
            supabase.table("tasks").insert({
                "task_type": "follow_up", "title": f"Re-engage {name}",
                "description": f"No activity for {days_stale}d, stage: {lead.get('stage')}",
                "lead_id": lid, "priority": "normal", "due_date": today, "created_by": "openclaw"
            }).execute()
            created += 1

    if created:
        supabase.table("activity_log").insert({
            "type": "system", "message": f"Auto-generated {created} tasks from pipeline scan",
            "meta": {"created": created}, "actor": "openclaw", "action": "tasks_generated"
        }).execute()

    return {"success": True, "tasks_created": created}


# ══════════════════════════════════════════
# FEATURE #4: FUNNEL ANALYTICS
# ══════════════════════════════════════════

PIPELINE_STAGES = ["new", "contacted", "discovery_call", "presentation", "considering", "signed", "onboarding"]

@router.get("/api/analytics/funnel")
def funnel_analytics():
    leads = supabase.table("leads").select("stage").execute().data
    counts = {s: 0 for s in PIPELINE_STAGES}
    for l in leads:
        s = l.get("stage") or "new"
        counts[s] = counts.get(s, 0) + 1
    # Conversion rates between adjacent stages
    conversions = []
    for i in range(len(PIPELINE_STAGES) - 1):
        curr = PIPELINE_STAGES[i]
        nxt = PIPELINE_STAGES[i + 1]
        # Count leads that are at this stage or beyond
        at_or_past_curr = sum(counts[PIPELINE_STAGES[j]] for j in range(i, len(PIPELINE_STAGES)))
        at_or_past_next = sum(counts[PIPELINE_STAGES[j]] for j in range(i + 1, len(PIPELINE_STAGES)))
        rate = round((at_or_past_next / at_or_past_curr * 100), 1) if at_or_past_curr > 0 else 0
        conversions.append({"from": curr, "to": nxt, "rate": rate, "from_count": at_or_past_curr, "to_count": at_or_past_next})
    return {"stage_counts": counts, "conversions": conversions, "total_leads": len(leads)}


@router.get("/api/analytics/sources")
def source_analytics():
    leads = supabase.table("leads").select("source, stage").execute().data
    sources = {}
    for l in leads:
        src = l.get("source") or "Unknown"
        if src not in sources:
            sources[src] = {"total": 0, "stages": {}, "converted": 0}
        sources[src]["total"] += 1
        stage = l.get("stage") or "new"
        sources[src]["stages"][stage] = sources[src]["stages"].get(stage, 0) + 1
        if stage in ("signed", "onboarding"):
            sources[src]["converted"] += 1
    # Add conversion rate
    result = []
    for src, data in sources.items():
        data["source"] = src
        data["conversion_rate"] = round((data["converted"] / data["total"] * 100), 1) if data["total"] > 0 else 0
        result.append(data)
    result.sort(key=lambda x: x["total"], reverse=True)
    return result


@router.get("/api/analytics/time-in-stage")
def time_in_stage():
    history = supabase.table("lead_stage_history").select("lead_id, from_stage, to_stage, changed_at").order("changed_at").execute().data
    if not history:
        return {"stages": {s: {"avg_days": 0, "count": 0} for s in PIPELINE_STAGES}}
    # Group by lead
    by_lead = {}
    for h in history:
        lid = h["lead_id"]
        if lid not in by_lead:
            by_lead[lid] = []
        by_lead[lid].append(h)
    # Calculate time in each stage
    stage_times = {s: [] for s in PIPELINE_STAGES}
    for lid, events in by_lead.items():
        events.sort(key=lambda x: x["changed_at"])
        for i in range(len(events)):
            from_s = events[i].get("from_stage")
            if from_s and from_s in stage_times:
                start_t = datetime.fromisoformat(events[i]["changed_at"].replace("Z", "+00:00").replace("+00:00", ""))
                if i + 1 < len(events):
                    end_t = datetime.fromisoformat(events[i + 1]["changed_at"].replace("Z", "+00:00").replace("+00:00", ""))
                else:
                    end_t = datetime.utcnow()
                days = (end_t - start_t).total_seconds() / 86400
                stage_times[from_s].append(days)
    result = {}
    for s in PIPELINE_STAGES:
        times = stage_times[s]
        result[s] = {
            "avg_days": round(sum(times) / len(times), 1) if times else 0,
            "count": len(times)
        }
    return {"stages": result}


@router.get("/api/analytics/funnel-roi")
def funnel_roi():
    leads = supabase.table("leads").select("source, stage").execute().data
    sources = {}
    for l in leads:
        src = l.get("source") or "Unknown"
        if src not in sources:
            sources[src] = {"total": 0, "signed": 0}
        sources[src]["total"] += 1
        if l.get("stage") in ("signed", "onboarding"):
            sources[src]["signed"] += 1
    result = []
    for src, data in sources.items():
        result.append({
            "source": src, "leads": data["total"], "conversions": data["signed"],
            "conversion_rate": round((data["signed"] / data["total"] * 100), 1) if data["total"] > 0 else 0
        })
    result.sort(key=lambda x: x["conversions"], reverse=True)
    return result


# ══════════════════════════════════════════
# FEATURE #5: REVENUE SHARE
# ══════════════════════════════════════════

@router.get("/api/revshare")
def list_revshare(year: int = 2026, agent_id: Optional[int] = None):
    query = supabase.table("revshare_entries").select("*, agents(name)").gte("month", f"{year}-01-01").lte("month", f"{year}-12-31").order("month", desc=True)
    if agent_id:
        query = query.eq("agent_id", agent_id)
    return query.execute().data


@router.post("/api/revshare")
def create_revshare(data: dict):
    result = supabase.table("revshare_entries").insert({
        "agent_id": data["agent_id"], "month": data["month"],
        "amount": data["amount"], "tier": data.get("tier", "tier_1"),
        "notes": data.get("notes", "")
    }).execute()
    return {"success": True, "id": result.data[0]["id"]}


@router.put("/api/revshare/{entry_id}")
def update_revshare(entry_id: int, data: dict):
    updates = {"updated_at": datetime.utcnow().isoformat()}
    for field in ["amount", "tier", "notes"]:
        if field in data:
            updates[field] = data[field]
    supabase.table("revshare_entries").update(updates).eq("id", entry_id).execute()
    return {"success": True}


@router.delete("/api/revshare/{entry_id}")
def delete_revshare(entry_id: int):
    supabase.table("revshare_entries").delete().eq("id", entry_id).execute()
    return {"success": True}


@router.get("/api/revshare/summary")
def revshare_summary(year: int = 2026):
    entries = supabase.table("revshare_entries").select("agent_id, amount, month, agents(name)").gte("month", f"{year}-01-01").lte("month", f"{year}-12-31").execute().data
    # Per agent
    by_agent = {}
    monthly_totals = {}
    for e in entries:
        aid = e["agent_id"]
        aname = e.get("agents", {}).get("name", f"Agent #{aid}") if e.get("agents") else f"Agent #{aid}"
        if aid not in by_agent:
            by_agent[aid] = {"name": aname, "total": 0, "months": 0}
        by_agent[aid]["total"] += float(e["amount"])
        by_agent[aid]["months"] += 1
        m = e["month"][:7]
        monthly_totals[m] = monthly_totals.get(m, 0) + float(e["amount"])
    # Projections
    now = datetime.utcnow()
    months_elapsed = now.month
    ytd = sum(v["total"] for v in by_agent.values())
    projected = round(ytd / months_elapsed * 12, 2) if months_elapsed > 0 else 0
    agents_list = sorted(by_agent.values(), key=lambda x: x["total"], reverse=True)
    return {
        "ytd_total": round(ytd, 2), "projected_annual": projected,
        "agents": agents_list, "monthly_totals": monthly_totals,
        "agent_count": len(by_agent),
        "avg_per_agent": round(ytd / len(by_agent), 2) if by_agent else 0
    }


@router.get("/api/revshare/calculator")
def revshare_calculator(network_size: int = 10):
    # LPT HybridShare tiers (Brokerage Partner plan)
    # Tier 1: 5% of agent's broker fee (direct recruits)
    # Tier 2: 3%, Tier 3: 2%, Tier 4: 1%, Tier 5-7: 0.5%
    # Assume avg agent pays $12,000/yr in broker fees (80/20 capped at $15K, most hit ~$12K)
    avg_annual_broker_fee = 12000
    tiers = [
        {"tier": 1, "pct": 0.05, "label": "Direct Recruits (5%)"},
        {"tier": 2, "pct": 0.03, "label": "Tier 2 (3%)"},
        {"tier": 3, "pct": 0.02, "label": "Tier 3 (2%)"},
        {"tier": 4, "pct": 0.01, "label": "Tier 4 (1%)"},
        {"tier": 5, "pct": 0.005, "label": "Tier 5 (0.5%)"},
        {"tier": 6, "pct": 0.005, "label": "Tier 6 (0.5%)"},
        {"tier": 7, "pct": 0.005, "label": "Tier 7 (0.5%)"},
    ]
    # Simple model: all agents at tier 1 for this calculator
    tier1_per_agent = avg_annual_broker_fee * tiers[0]["pct"]
    estimated_annual = round(network_size * tier1_per_agent, 2)
    estimated_monthly = round(estimated_annual / 12, 2)
    breakdown = []
    for t in tiers:
        per_agent = round(avg_annual_broker_fee * t["pct"], 2)
        breakdown.append({"tier": t["tier"], "label": t["label"], "per_agent_annual": per_agent, "per_agent_monthly": round(per_agent / 12, 2)})
    return {
        "network_size": network_size,
        "estimated_monthly": estimated_monthly,
        "estimated_annual": estimated_annual,
        "per_agent_monthly": round(tier1_per_agent / 12, 2),
        "per_agent_annual": tier1_per_agent,
        "tier_breakdown": breakdown,
        "note": "Based on avg $12K annual broker fee. Actual varies by agent production. Brokerage Partner plan required."
    }


# ══════════════════════════════════════════
# AUTOMATION STATUS & CONTROLS
# ══════════════════════════════════════════

@router.get("/api/automations/status")
def automation_status():
    settings = supabase.table("automation_settings").select("*").order("workflow").execute().data
    # Last 20 runs
    recent = supabase.table("automation_runs").select("*").order("created_at", desc=True).limit(20).execute().data
    return {"workflows": settings, "recent_runs": recent}


@router.put("/api/automations/{workflow}/toggle")
def toggle_automation(workflow: str):
    current = supabase.table("automation_settings").select("enabled").eq("workflow", workflow).execute()
    if not current.data:
        raise HTTPException(status_code=404, detail="Workflow not found")
    new_state = not current.data[0]["enabled"]
    supabase.table("automation_settings").update({
        "enabled": new_state, "updated_at": datetime.utcnow().isoformat()
    }).eq("workflow", workflow).execute()
    return {"success": True, "workflow": workflow, "enabled": new_state}


@router.post("/api/automations/{workflow}/run")
def run_automation_now(workflow: str):
    """Manually trigger a specific workflow."""
    import subprocess
    result = subprocess.run(
        ["python3", "-c", f"from automations import WORKFLOWS; WORKFLOWS['{workflow}']()"],
        capture_output=True, text=True, timeout=30, cwd="/app"
    )
    if result.returncode != 0:
        return {"success": False, "error": result.stderr[:500]}
    return {"success": True, "output": result.stdout[:500]}


@router.get("/api/automations/runs")
def automation_runs(workflow: Optional[str] = None, limit: int = 50):
    query = supabase.table("automation_runs").select("*").order("created_at", desc=True).limit(limit)
    if workflow:
        query = query.eq("workflow", workflow)
    return query.execute().data
