#!/usr/bin/env python3
"""
Meta Leads Sync - Backup cron job that polls Meta Graph API for new leads
and imports any that aren't already in Supabase. Runs every 15 minutes.
This ensures leads are never lost even if the webhook fails.
"""
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from supabase import create_client

SETTINGS_PATH = "/data/settings.json"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zyonidiybzrgklrmalbt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
FORM_ID = "2446350272487229"  # KW Commission Comparison - 2026

def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

def fetch_meta_leads(token, form_id, limit=50):
    url = f"https://graph.facebook.com/v21.0/{form_id}/leads?access_token={token}&limit={limit}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())

def main():
    settings = load_settings()
    token = settings.get("meta_page_access_token", "")
    if not token:
        print("No meta_page_access_token configured")
        return

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Get existing Meta lead emails
    existing = supabase.table("leads").select("email").in_("source", ["Meta Ads", "Meta Ad"]).execute()
    existing_emails = {r["email"].lower() for r in existing.data}

    # Fetch leads from Meta
    try:
        data = fetch_meta_leads(token, FORM_ID)
    except Exception as e:
        print(f"Error fetching Meta leads: {e}")
        return

    new_count = 0
    for lead in data.get("data", []):
        fields = {}
        for f in lead.get("field_data", []):
            fname = f.get("name", "").lower()
            fvals = f.get("values", [])
            if fvals:
                fields[fname] = fvals[0]

        email = fields.get("email", "")
        if not email or email.lower() in existing_emails:
            continue

        name = fields.get("full_name", "") or fields.get("name", "Unknown")
        phone = fields.get("phone_number", "") or fields.get("phone", "")
        name_parts = name.strip().split(" ", 1)
        first_name = name_parts[0] if name_parts else "Unknown"
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Detect brokerage
        form_name = "KW Commission Comparison - 2026"
        current_brokerage = "Keller Williams"
        funnel_id = 20

        # Create lead
        result = supabase.table("leads").insert({
            "name": name,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "source": "Meta Ads",
            "source_page": f"Ad 1A - The 30% Reality - {form_name}",
            "stage": "new_fb_lead",
            "lead_temperature": "warm",
            "status": "new",
            "current_brokerage": current_brokerage,
            "notes": f"Meta Lead Ad submission via {form_name}. Imported by sync job."
        }).execute()

        lead_id = result.data[0]["id"]

        # Create opportunity
        try:
            supabase.table("opportunities").insert({
                "contact_id": lead_id,
                "pipeline_id": 1,
                "stage": "new_fb_lead",
                "source": f"Meta Ads - {form_name}",
                "status": "open",
                "notes": "Auto-created by Meta lead sync job."
            }).execute()
        except Exception:
            pass

        # Enroll in email funnel
        try:
            supabase.table("email_funnel_enrollments").insert({
                "lead_id": lead_id,
                "funnel_id": funnel_id,
                "current_step": 1,
                "status": "active",
                "enrolled_at": datetime.now(timezone.utc).isoformat()
            }).execute()
        except Exception:
            pass

        # Log activity
        supabase.table("activity_log").insert({
            "type": "meta_lead",
            "message": f"New lead via Meta sync: {name} ({email}) - {form_name}",
            "meta": {"lead_id": lead_id, "form": form_name, "funnel_id": funnel_id, "sync": True}
        }).execute()

        existing_emails.add(email.lower())
        new_count += 1
        print(f"Imported: {name} ({email})")

    print(f"Sync complete. {new_count} new leads imported.")

if __name__ == "__main__":
    main()
