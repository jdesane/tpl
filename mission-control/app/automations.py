"""TPL Mission Control — Autonomous Automation Engine
Runs on cron every 15 minutes. Checks which workflows are due and executes them.

This engine ONLY operates on Joe's platform workspace (workspace_id=1). Other tenants
get their own automations later (out of scope for Phase 13). All queries and inserts
explicitly scope to workspace_id=1 to avoid touching other tenants' data."""
import os
import json
import time
import urllib.request
from datetime import datetime, timedelta
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zyonidiybzrgklrmalbt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
API_BASE = "http://127.0.0.1:8000"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def log_run(workflow, status, details, duration_ms):
    supabase.table("automation_runs").insert({
        "workspace_id": 1,
        "workflow": workflow, "status": status,
        "details": details, "duration_ms": duration_ms
    }).execute()
    supabase.table("automation_settings").update({
        "last_run_at": datetime.utcnow().isoformat()
    }).eq("workflow", workflow).eq("workspace_id", 1).execute()


def api_post(path):
    try:
        req = urllib.request.Request(
            API_BASE + path,
            data=b"",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def should_run(workflow, interval_minutes, last_run_at):
    if not last_run_at:
        return True
    try:
        last = datetime.fromisoformat(str(last_run_at).replace("Z", "+00:00").replace("+00:00", ""))
        return (datetime.utcnow() - last).total_seconds() >= interval_minutes * 60
    except (ValueError, TypeError):
        return True


def run_score_leads():
    start = time.time()
    result = api_post("/api/ai/score-leads")
    ms = int((time.time() - start) * 1000)
    if "error" in result:
        log_run("score_leads", "error", result, ms)
        return
    log_run("score_leads", "success", {"updated": result.get("updated", 0)}, ms)
    supabase.table("activity_log").insert({
        "workspace_id": 1,
        "type": "system", "message": f"Auto-scored {result.get('updated', 0)} leads",
        "meta": result, "actor": "openclaw", "action": "auto_score"
    }).execute()


def run_generate_tasks():
    start = time.time()
    result = api_post("/api/ai/generate-tasks")
    ms = int((time.time() - start) * 1000)
    if "error" in result:
        log_run("generate_tasks", "error", result, ms)
        return
    log_run("generate_tasks", "success", {"created": result.get("tasks_created", 0)}, ms)


def run_process_drips():
    start = time.time()
    result = api_post("/api/drip/process")
    ms = int((time.time() - start) * 1000)
    if "error" in result:
        log_run("process_drips", "error", result, ms)
        return
    log_run("process_drips", "success", {
        "processed": result.get("processed", 0),
        "errors": result.get("errors", [])
    }, ms)


def run_flag_stale_leads():
    start = time.time()
    now = datetime.utcnow()
    stale_cutoff = (now - timedelta(days=3)).isoformat()

    leads = supabase.table("leads").select("id, name, stage, updated_at, created_at").eq("workspace_id", 1).not_.in_("stage", ["signed", "onboarding"]).execute().data
    stale = []
    for l in leads:
        updated = l.get("updated_at") or l.get("created_at", "")
        if updated and updated < stale_cutoff:
            stale.append(l)

    # Log stale leads as alerts
    if stale:
        supabase.table("activity_log").insert({
            "workspace_id": 1,
            "type": "system",
            "message": f"Alert: {len(stale)} stale leads (no activity 3+ days)",
            "meta": {"stale_count": len(stale), "lead_ids": [l["id"] for l in stale[:10]]},
            "actor": "openclaw", "action": "stale_alert"
        }).execute()

    ms = int((time.time() - start) * 1000)
    log_run("flag_stale_leads", "success", {"stale_count": len(stale)}, ms)


def run_check_engagement():
    start = time.time()
    agents = supabase.table("agents").select("id, name, engagement_score, status").eq("status", "active").execute().data
    at_risk = [a for a in agents if (a.get("engagement_score") or 100) < 30]

    if at_risk:
        supabase.table("activity_log").insert({
            "workspace_id": 1,
            "type": "system",
            "message": f"Alert: {len(at_risk)} agents at risk (engagement < 30)",
            "meta": {"at_risk": [{"id": a["id"], "name": a["name"], "score": a.get("engagement_score")} for a in at_risk]},
            "actor": "openclaw", "action": "engagement_alert"
        }).execute()

        # Create tasks for at-risk agents (Joe's workspace)
        existing = supabase.table("tasks").select("agent_id").eq("workspace_id", 1).eq("status", "pending").eq("task_type", "follow_up").execute().data
        existing_ids = {t["agent_id"] for t in existing}
        for a in at_risk:
            if a["id"] not in existing_ids:
                supabase.table("tasks").insert({
                    "workspace_id": 1,
                    "task_type": "follow_up",
                    "title": f"Check in with {a['name']}",
                    "description": f"Engagement score: {a.get('engagement_score', 0)} - at risk",
                    "agent_id": a["id"], "priority": "normal",
                    "due_date": datetime.utcnow().strftime("%Y-%m-%d"),
                    "created_by": "openclaw"
                }).execute()

    ms = int((time.time() - start) * 1000)
    log_run("check_engagement", "success", {"at_risk": len(at_risk), "total_agents": len(agents)}, ms)


WORKFLOWS = {
    "score_leads": run_score_leads,
    "generate_tasks": run_generate_tasks,
    "process_drips": run_process_drips,
    "flag_stale_leads": run_flag_stale_leads,
    "check_engagement": run_check_engagement,
}


def main():
    print(f"[{datetime.utcnow().isoformat()}] Automation engine starting...")
    settings = supabase.table("automation_settings").select("*").eq("workspace_id", 1).execute().data

    ran = 0
    for s in settings:
        workflow = s["workflow"]
        if not s.get("enabled", True):
            continue
        if not should_run(workflow, s.get("interval_minutes", 15), s.get("last_run_at")):
            continue
        if workflow in WORKFLOWS:
            print(f"  Running: {workflow}")
            try:
                WORKFLOWS[workflow]()
                ran += 1
            except Exception as e:
                log_run(workflow, "error", {"exception": str(e)}, 0)
                print(f"  Error in {workflow}: {e}")

    print(f"[{datetime.utcnow().isoformat()}] Done. Ran {ran} workflows.")


if __name__ == "__main__":
    main()
