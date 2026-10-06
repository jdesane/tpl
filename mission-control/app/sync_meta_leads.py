#!/usr/bin/env python3
"""
Meta Leads backfill. Cron (VPS, every 6 hours):
  docker exec mission-control-mission-control-1 python3 /app/sync_meta_leads.py

All the logic lives in meta_leads.py so the webhook and the backfill share one
code path. This script asks the running app (loopback, so no login needed) to
list recent leads on EVERY active form on the Page, store any leadgen ID it
hasn't seen, and retry failed ones. Pass --token-check to run the daily token
health check instead.
"""
import json
import sys
import urllib.request

path = "/api/meta-leads/token-check" if "--token-check" in sys.argv else "/api/meta-leads/sync"
req = urllib.request.Request("http://127.0.0.1:8000" + path, data=b"", method="POST")
try:
    with urllib.request.urlopen(req, timeout=600) as r:
        print(json.dumps(json.loads(r.read().decode())))
except Exception as e:
    print(f"meta {path} failed: {e}")
    sys.exit(1)
