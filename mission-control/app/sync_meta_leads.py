#!/usr/bin/env python3
"""
Meta Leads Sync - Backup cron job that polls Meta Graph API for new leads
and imports any that aren't already in Supabase. Runs every 15 minutes.
This ensures leads are never lost even if the webhook fails.
"""
import json
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from supabase import create_client

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

def is_valid_email(value):
    if not value or not isinstance(value, str):
        return False
    return bool(EMAIL_REGEX.match(value.strip()))

SETTINGS_PATH = "/data/settings.json"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zyonidiybzrgklrmalbt.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
# Form ID -> (form_name, brokerage, funnel_id) mapping
FORM_CONFIGS = {
    "2446350272487229": ("KW Commission Comparison - 2026", "Keller Williams", 20),
    "956068570135306": ("RE/MAX Commission Comparison - 2026", "RE/MAX", 21),
}

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

    # Get ALL existing lead emails (not just Meta) to avoid re-importing deleted leads
    existing = supabase.table("leads").select("email").execute()
    existing_emails = {r["email"].lower() for r in existing.data}

    # Also check suppression list and deleted leads log
    try:
        suppressed = supabase.table("email_suppressions").select("email").execute()
        existing_emails.update({r["email"].lower() for r in suppressed.data})
    except Exception:
        pass

    # Check for previously synced-then-deleted leads (stored in settings)
    deleted_emails = set(settings.get("meta_deleted_emails", []))
    existing_emails.update(deleted_emails)

    # Fetch and process leads from all configured forms
    total_new = 0
    for form_id, (form_name, current_brokerage, funnel_id) in FORM_CONFIGS.items():
        try:
            data = fetch_meta_leads(token, form_id)
        except Exception as e:
            print(f"Error fetching Meta leads for {form_name}: {e}")
            continue

        new_count = 0
        for lead in data.get("data", []):
            fields = {}
            for f in lead.get("field_data", []):
                fname = f.get("name", "").lower()
                fvals = f.get("values", [])
                if fvals:
                    fields[fname] = fvals[0]

            email = (fields.get("email", "") or "").strip()
            if not email or email.lower() in existing_emails:
                continue
            if not is_valid_email(email):
                try:
                    supabase.table("activity_log").insert({
                        "type": "sync_validation_error",
                        "message": f"sync_meta_leads rejected malformed email: {email!r} (form={form_name!r})",
                        "meta": {"email": email, "form": form_name, "fields": fields}
                    }).execute()
                except Exception:
                    pass
                continue

            name = fields.get("full_name", "") or fields.get("name", "Unknown")
            phone = fields.get("phone_number", "") or fields.get("phone", "")
            name_parts = name.strip().split(" ", 1)
            first_name = name_parts[0] if name_parts else "Unknown"
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Create lead
            result = supabase.table("leads").insert({
                "name": name,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "source": "Meta Ads",
                "source_page": form_name,
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
                    "notes": f"Auto-created by Meta lead sync job ({current_brokerage})."
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
                "meta": {"lead_id": lead_id, "form": form_name, "funnel_id": funnel_id, "sync": True, "brokerage": current_brokerage}
            }).execute()

            existing_emails.add(email.lower())
            new_count += 1
            print(f"Imported ({current_brokerage}): {name} ({email})")

        print(f"  {form_name}: {new_count} new leads.")
        total_new += new_count

    print(f"Sync complete. {total_new} total new leads imported.")

if __name__ == "__main__":
    main()
