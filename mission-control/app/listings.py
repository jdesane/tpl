"""
Listing Dashboard - API router.

A per-listing operating system: seller intake -> pricing -> offers -> closing.
Replaces Joe's 14-tab workbook. See migrations/2026-08-18-listing-dashboard-foundation.sql
for the schema rationale and the list of deliberate departures from it.

Wired from main.py like coaching.py / cma.py:
    import listings as _listings_mod
    _listings_mod.setup(db, supabase)
    app.include_router(_listings_mod.router,
        dependencies=[Depends(_ent_mod.require_entitlement("listing-dashboard"))])
    app.include_router(_listings_mod.net_sheet_router,
        dependencies=[Depends(_ent_mod.require_any_entitlement(["listing-dashboard","net-sheet"]))])

TWO RULES THIS MODULE ENFORCES

1. Rates belong to the agent. We never supply a number that reaches a seller.
   Fee profiles are copied from an inert template, edited, and confirmed by the
   agent. Anything computed from a template or an unconfirmed profile is marked
   blocking, and every seller-facing path calls net_sheet.assert_sendable().

2. Net sheets are snapshots. A net sheet handed to a seller is a point-in-time
   document; if the agent later edits their fee profile, the historical document
   must not silently change underneath it. Both inputs and computed output are
   stored on the row. Recomputing is explicit and creates a fresh snapshot.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Callable, Any, Dict, List
from datetime import datetime, date, timezone, timedelta

import net_sheet as _ns

router = APIRouter(prefix="/api/listings", tags=["listings"])
# Sibling routers so main.py can gate them differently. Fee profiles and net sheets
# are reachable by a standalone net-sheet subscriber who has no Listing Dashboard.
net_sheet_router = APIRouter(prefix="/api", tags=["net-sheets"])

_db: Optional[Callable[[str], Any]] = None
_supabase: Any = None
_entitlements: Any = None


def setup(db_callable, supabase_client, entitlements_module=None):
    global _db, _supabase, _entitlements
    _db = db_callable
    _supabase = supabase_client
    _entitlements = entitlements_module


# ════════════════════════════════════════════════════════════
# Helpers

def _ws(request: Request) -> int:
    ws = getattr(request.state, "workspace_id", None)
    if ws is None:
        raise HTTPException(401, "Authentication required")
    return int(ws)


def _actor(request: Request) -> Optional[int]:
    user = getattr(request.state, "user", None) or {}
    return user.get("sub") if isinstance(user, dict) else None


def _clean(payload: dict) -> dict:
    """Drop unset fields so a PATCH never nulls a column it did not mention."""
    return {k: v for k, v in payload.items() if v is not None}


def _listing_or_404(listing_id: int) -> dict:
    rows = _db("listings").select("*").eq("id", listing_id).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "Listing not found")
    return rows[0]


def _row_or_404(table: str, row_id: int, label: str) -> dict:
    rows = _db(table).select("*").eq("id", row_id).limit(1).execute().data
    if not rows:
        raise HTTPException(404, f"{label} not found")
    return rows[0]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════
# Fee profiles - the agent's own closing costs

class FeeProfileIn(BaseModel):
    state: Optional[str] = None
    county: Optional[str] = None
    name: Optional[str] = None
    config: Optional[dict] = None
    source_note: Optional[str] = None
    source_by_field: Optional[dict] = None
    is_default: Optional[bool] = None
    copy_from_template_id: Optional[int] = None


def _resolve_fee_profile(listing: dict, workspace_id: int) -> Optional[dict]:
    """
    The listing's explicit profile, else the workspace default for its state.
    Never falls back to a template: a template cannot produce a sendable document,
    and silently selecting one would be the exact failure this design prevents.
    """
    if listing.get("fee_profile_id"):
        rows = (_supabase.table("fee_profiles").select("*")
                .eq("id", listing["fee_profile_id"]).limit(1).execute().data)
        if rows:
            return rows[0]
    state = listing.get("state")
    if not state:
        return None
    rows = (_supabase.table("fee_profiles").select("*")
            .eq("workspace_id", workspace_id).eq("state", state)
            .eq("is_default", True).limit(1).execute().data)
    return rows[0] if rows else None


@net_sheet_router.get("/fee-profiles/templates")
def list_fee_templates(state: Optional[str] = None):
    """
    Starter templates. Structure only - they carry no usable numbers and cannot be
    attached to a listing. They exist to show a new agent which line items to expect
    and how the tiers nest, which is the genuinely hard part of the setup.
    """
    q = _supabase.table("fee_profiles").select("*").eq("is_template", True)
    if state:
        q = q.eq("state", state)
    return {"templates": q.order("state").execute().data or []}


@net_sheet_router.get("/fee-profiles")
def list_fee_profiles(request: Request):
    ws = _ws(request)
    rows = (_supabase.table("fee_profiles").select("*")
            .eq("workspace_id", ws).order("state").execute().data) or []
    return {
        "profiles": rows,
        "needs_setup": not any(r.get("confirmed_at") for r in rows),
    }


@net_sheet_router.post("/fee-profiles")
def create_fee_profile(body: FeeProfileIn, request: Request):
    """
    Create the agent's own profile, optionally seeded from a template's STRUCTURE.

    A copy is never confirmed on creation, even when copied - the whole point is that
    the agent reviews every number against their own settlement statement first.
    """
    ws = _ws(request)
    payload = _clean(body.dict(exclude={"copy_from_template_id"}))

    if body.copy_from_template_id:
        tmpl = (_supabase.table("fee_profiles").select("*")
                .eq("id", body.copy_from_template_id).eq("is_template", True)
                .limit(1).execute().data)
        if not tmpl:
            raise HTTPException(404, "Template not found")
        src = tmpl[0]
        payload.setdefault("state", src.get("state"))
        payload.setdefault("config", src.get("config") or {})
        payload.setdefault("name", f"My closing costs ({src.get('state')})")
        payload["copied_from_id"] = src["id"]
        payload["source_note"] = (
            "Copied from a starter template. Every number must be replaced with your own "
            "title company quote or last settlement statement before this is confirmed."
        )

    if not payload.get("state"):
        raise HTTPException(400, "state is required")

    payload.update({
        "workspace_id": ws,
        "is_template": False,
        "confirmed_at": None,
        "confirmed_by_user_id": None,
    })
    return (_supabase.table("fee_profiles").insert(payload).execute().data)[0]


@net_sheet_router.patch("/fee-profiles/{profile_id}")
def update_fee_profile(profile_id: int, body: FeeProfileIn, request: Request):
    """
    Editing a profile UNCONFIRMS it. If the agent changes a rate, whatever they
    confirmed previously no longer describes what the tool will produce, so it has
    to be reviewed again before anything else reaches a seller.
    """
    ws = _ws(request)
    existing = (_supabase.table("fee_profiles").select("*")
                .eq("id", profile_id).eq("workspace_id", ws).limit(1).execute().data)
    if not existing:
        raise HTTPException(404, "Fee profile not found")

    payload = _clean(body.dict(exclude={"copy_from_template_id"}))
    if not payload:
        raise HTTPException(400, "Nothing to update")

    substantive = {"config", "state", "county"} & set(payload.keys())
    if substantive and existing[0].get("confirmed_at"):
        payload["confirmed_at"] = None
        payload["confirmed_by_user_id"] = None

    rows = (_supabase.table("fee_profiles").update(payload)
            .eq("id", profile_id).eq("workspace_id", ws).execute().data)
    out = rows[0]
    out["_unconfirmed_by_edit"] = bool(substantive and existing[0].get("confirmed_at"))
    return out


@net_sheet_router.post("/fee-profiles/{profile_id}/confirm")
def confirm_fee_profile(profile_id: int, request: Request):
    """The agent asserts these are their real closing costs. Unblocks seller output."""
    ws = _ws(request)
    rows = (_supabase.table("fee_profiles").update({
                "confirmed_at": _now(),
                "confirmed_by_user_id": _actor(request),
            }).eq("id", profile_id).eq("workspace_id", ws).execute().data)
    if not rows:
        raise HTTPException(404, "Fee profile not found")
    return rows[0]


@net_sheet_router.delete("/fee-profiles/{profile_id}")
def delete_fee_profile(profile_id: int, request: Request):
    ws = _ws(request)
    _supabase.table("fee_profiles").delete().eq("id", profile_id).eq("workspace_id", ws).execute()
    return {"deleted": True}


# ════════════════════════════════════════════════════════════
# Listings

class ListingIn(BaseModel):
    status: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    county: Optional[str] = None
    parcel_id: Optional[str] = None
    mls_number: Optional[str] = None
    property_type: Optional[str] = None
    year_built: Optional[int] = None
    beds_tax: Optional[float] = None
    baths_tax: Optional[float] = None
    sqft_tax: Optional[int] = None
    beds_marketing: Optional[float] = None
    baths_marketing: Optional[float] = None
    sqft_marketing: Optional[int] = None
    stories: Optional[int] = None
    garage_spaces: Optional[float] = None
    lot_size_acres: Optional[float] = None
    has_pool: Optional[bool] = None
    list_price: Optional[float] = None
    list_date: Optional[str] = None
    expiration_date: Optional[str] = None
    commission_pct: Optional[float] = None
    coop_commission_pct: Optional[float] = None
    under_contract_date: Optional[str] = None
    closed_date: Optional[str] = None
    sold_price: Optional[float] = None
    lead_id: Optional[int] = None
    cma_id: Optional[int] = None
    fee_profile_id: Optional[int] = None
    interview: Optional[dict] = None
    property_notes: Optional[dict] = None
    hoa: Optional[dict] = None
    marketing: Optional[dict] = None
    notes: Optional[str] = None
    price_change_reason: Optional[str] = None   # captured when list_price moves


ACTIVE_STATUSES = ("pre_list", "coming_soon", "active", "pending")


@router.get("")
def list_listings(request: Request, status: Optional[str] = None, q: Optional[str] = None):
    query = _db("listings").select("*")
    if status:
        query = query.eq("status", status)
    rows = query.order("created_at", desc=True).execute().data or []

    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in " ".join(str(r.get(f) or "") for f in
                ("address_line1", "city", "mls_number", "zip")).lower()]

    counts: Dict[str, int] = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"listings": rows, "counts": counts, "total": len(rows)}


@router.post("")
def create_listing(body: ListingIn, request: Request):
    ws = _ws(request)

    # Free tier caps active listings. Enforced here, at the API - hiding the button
    # would not be gating.
    if _entitlements:
        active = _db("listings").select("id").in_("status", list(ACTIVE_STATUSES)).execute().data or []
        _entitlements.check_limit(ws, "listing-dashboard", "active_listings", len(active))

    payload = _clean(body.dict(exclude={"price_change_reason"}))
    payload["created_by_user_id"] = _actor(request)
    if payload.get("list_price") and not payload.get("original_list_price"):
        payload["original_list_price"] = payload["list_price"]

    row = (_db("listings").insert(payload).execute().data)[0]

    if row.get("list_price"):
        _db("listing_price_changes").insert({
            "listing_id": row["id"],
            "new_price": row["list_price"],
            "changed_by_user_id": _actor(request),
            "reason": "Initial list price",
        }).execute()
    return row


@router.get("/milestones/due")
def milestones_due(request: Request, days: int = 7, include_overdue: bool = True):
    """
    Everything due across ALL listings in the next N days.

    The workbook could never answer this: deadlines lived as columns on one sheet per
    property, so "what is due this week" meant opening every file. This is the single
    biggest reason to move it off a spreadsheet.

    Declared before /{listing_id} so the literal path is not captured as an id.
    """
    horizon = (date.today() + timedelta(days=days)).isoformat()
    q = (_db("transaction_milestones").select("*")
         .is_("completed_at", "null").lte("due_date", horizon))
    if not include_overdue:
        q = q.gte("due_date", date.today().isoformat())
    rows = q.order("due_date").execute().data or []

    listings = {l["id"]: l for l in (_db("listings").select(
        "id,address_line1,city,status,mls_number").execute().data or [])}
    today = date.today()
    overdue, upcoming = [], []
    for r in rows:
        r["listing"] = listings.get(r["listing_id"])
        due = _ns._as_date(r.get("due_date"))
        r["days_until"] = (due - today).days if due else None
        (overdue if (due and due < today) else upcoming).append(r)
    return {"overdue": overdue, "upcoming": upcoming,
            "total": len(rows), "horizon_days": days}


@router.get("/{listing_id}")
def get_listing(listing_id: int, request: Request):
    """The full bundle - one round trip powers the whole detail view."""
    listing = _listing_or_404(listing_id)
    ws = _ws(request)

    def child(table, order="id", desc=False):
        return (_db(table).select("*").eq("listing_id", listing_id)
                .order(order, desc=desc).execute().data) or []

    profile = _resolve_fee_profile(listing, ws)
    return {
        "listing": listing,
        "sellers": child("listing_sellers"),
        "mortgages": child("listing_mortgages"),
        "offers": child("offers", "received_at", True),
        "net_sheets": child("net_sheets", "created_at", True),
        "milestones": child("transaction_milestones", "sort_order"),
        "price_changes": child("listing_price_changes", "changed_at", True),
        "showings": child("listing_showings", "showed_at", True),
        "weekly_reports": child("listing_weekly_reports", "week_ending", True),
        "fee_profile": profile,
        "fee_profile_ready": bool(profile and profile.get("confirmed_at")
                                  and not profile.get("is_template")),
    }


@router.patch("/{listing_id}")
def update_listing(listing_id: int, body: ListingIn, request: Request):
    """A list price change is recorded automatically - sellers argue about reductions."""
    existing = _listing_or_404(listing_id)
    payload = _clean(body.dict(exclude={"price_change_reason"}))
    if not payload:
        raise HTTPException(400, "Nothing to update")

    old_price = existing.get("list_price")
    new_price = payload.get("list_price")
    price_moved = new_price is not None and float(new_price) != float(old_price or 0)

    row = (_db("listings").update(payload).eq("id", listing_id).execute().data)[0]

    if price_moved:
        _db("listing_price_changes").insert({
            "listing_id": listing_id,
            "old_price": old_price,
            "new_price": new_price,
            "changed_by_user_id": _actor(request),
            "reason": body.price_change_reason,
        }).execute()
    return row


@router.delete("/{listing_id}")
def delete_listing(listing_id: int, request: Request):
    _listing_or_404(listing_id)
    _db("listings").delete().eq("id", listing_id).execute()   # children cascade
    return {"deleted": True}


# ════════════════════════════════════════════════════════════
# Sellers and mortgages

class SellerIn(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_cell: Optional[str] = None
    phone_home: Optional[str] = None
    other_contact: Optional[str] = None
    is_primary: Optional[bool] = None
    marital_status: Optional[str] = None
    mailing_address: Optional[str] = None
    forwarding_address: Optional[str] = None
    trust_parties: Optional[str] = None
    lead_id: Optional[int] = None
    notes: Optional[str] = None
    # There is deliberately no SSN field. See the migration header.


class MortgageIn(BaseModel):
    position: Optional[str] = None
    lender_name: Optional[str] = None
    account_number_last4: Optional[str] = None
    estimated_payoff: Optional[float] = None
    payoff_good_through: Optional[str] = None
    has_escrow: Optional[bool] = None
    notes: Optional[str] = None


@router.post("/{listing_id}/sellers")
def add_seller(listing_id: int, body: SellerIn, request: Request):
    _listing_or_404(listing_id)
    payload = _clean(body.dict())
    payload["listing_id"] = listing_id
    return (_db("listing_sellers").insert(payload).execute().data)[0]


@router.patch("/sellers/{seller_id}")
def update_seller(seller_id: int, body: SellerIn, request: Request):
    _row_or_404("listing_sellers", seller_id, "Seller")
    payload = _clean(body.dict())
    if not payload:
        raise HTTPException(400, "Nothing to update")
    return (_db("listing_sellers").update(payload).eq("id", seller_id).execute().data)[0]


@router.delete("/sellers/{seller_id}")
def delete_seller(seller_id: int, request: Request):
    _row_or_404("listing_sellers", seller_id, "Seller")
    _db("listing_sellers").delete().eq("id", seller_id).execute()
    return {"deleted": True}


@router.post("/{listing_id}/mortgages")
def add_mortgage(listing_id: int, body: MortgageIn, request: Request):
    _listing_or_404(listing_id)
    payload = _clean(body.dict())
    last4 = payload.get("account_number_last4")
    if last4 and len(str(last4)) > 4:
        # The DB CHECK would catch this; a clear 400 explains WHY rather than
        # surfacing a constraint violation.
        raise HTTPException(400, "Store only the last four digits of the account number. "
                                 "Full account numbers are not kept in this system.")
    payload["listing_id"] = listing_id
    return (_db("listing_mortgages").insert(payload).execute().data)[0]


@router.patch("/mortgages/{mortgage_id}")
def update_mortgage(mortgage_id: int, body: MortgageIn, request: Request):
    _row_or_404("listing_mortgages", mortgage_id, "Mortgage")
    payload = _clean(body.dict())
    last4 = payload.get("account_number_last4")
    if last4 and len(str(last4)) > 4:
        raise HTTPException(400, "Store only the last four digits of the account number.")
    if not payload:
        raise HTTPException(400, "Nothing to update")
    return (_db("listing_mortgages").update(payload).eq("id", mortgage_id).execute().data)[0]


@router.delete("/mortgages/{mortgage_id}")
def delete_mortgage(mortgage_id: int, request: Request):
    _row_or_404("listing_mortgages", mortgage_id, "Mortgage")
    _db("listing_mortgages").delete().eq("id", mortgage_id).execute()
    return {"deleted": True}


# ════════════════════════════════════════════════════════════
# Net sheets

class NetSheetIn(BaseModel):
    label: Optional[str] = None
    kind: Optional[str] = None            # estimate | offer
    offer_id: Optional[int] = None
    sale_price: Optional[float] = None
    closing_date: Optional[str] = None
    fee_profile_id: Optional[int] = None
    inputs: Optional[dict] = None


def _compute_for_listing(listing: dict, workspace_id: int, sale_price, closing_date,
                         inputs: dict, fee_profile_id: Optional[int] = None) -> tuple:
    """Assemble everything the engine needs. Returns (result, profile)."""
    profile = None
    if fee_profile_id:
        rows = (_supabase.table("fee_profiles").select("*")
                .eq("id", fee_profile_id).limit(1).execute().data)
        profile = rows[0] if rows else None
    if profile is None:
        profile = _resolve_fee_profile(listing, workspace_id)

    payoffs = (_db("listing_mortgages").select("*")
               .eq("listing_id", listing["id"]).execute().data) or []

    merged = dict(inputs or {})
    # The listing's commission is the default; an explicit input still wins.
    if "commission_pct" not in merged and listing.get("commission_pct") is not None:
        merged["commission_pct"] = listing["commission_pct"]

    result = _ns.compute_net_sheet(
        sale_price,
        (profile or {}).get("config") or {},
        merged,
        county=listing.get("county"),
        closing_date=closing_date,
        property_type=listing.get("property_type"),
        mortgage_payoffs=payoffs,
        profile_meta={
            "is_template": bool(profile and profile.get("is_template")),
            "confirmed_at": profile.get("confirmed_at") if profile else None,
            "name": profile.get("name") if profile else None,
        },
    )
    return result, profile


@net_sheet_router.post("/listings/{listing_id}/net-sheets/preview")
def preview_net_sheet(listing_id: int, body: NetSheetIn, request: Request):
    """
    Compute without saving. Powers live editing - the agent drags a price and watches
    the proceeds move. Nothing is persisted, so no snapshot is created.
    """
    listing = _listing_or_404(listing_id)
    price = body.sale_price if body.sale_price is not None else listing.get("list_price")
    if price is None:
        raise HTTPException(400, "No sale price - set the listing's list price or pass one")
    result, profile = _compute_for_listing(
        listing, _ws(request), price, body.closing_date, body.inputs or {}, body.fee_profile_id)
    return {"preview": result, "fee_profile": profile}


@net_sheet_router.post("/listings/{listing_id}/net-sheets")
def create_net_sheet(listing_id: int, body: NetSheetIn, request: Request):
    """
    Persist a net sheet WITH its computed snapshot. The snapshot is the point: if the
    agent later edits their fee profile, this document must still say what it said
    when the seller saw it.
    """
    listing = _listing_or_404(listing_id)
    price = body.sale_price if body.sale_price is not None else listing.get("list_price")
    if price is None:
        raise HTTPException(400, "No sale price - set the listing's list price or pass one")

    result, profile = _compute_for_listing(
        listing, _ws(request), price, body.closing_date, body.inputs or {}, body.fee_profile_id)

    row = (_db("net_sheets").insert({
        "listing_id": listing_id,
        "created_by_user_id": _actor(request),
        "label": body.label or ("Offer" if body.kind == "offer" else "Estimate"),
        "kind": body.kind or "estimate",
        "offer_id": body.offer_id,
        "sale_price": price,
        "closing_date": body.closing_date,
        "fee_profile_id": (profile or {}).get("id"),
        "inputs": body.inputs or {},
        "computed": result,
    }).execute().data)[0]

    # Surfaced so the UI can show the banner without re-reading the snapshot.
    row["blocking"] = result.get("blocking")
    row["blockers"] = result.get("blockers")
    return row


@net_sheet_router.get("/net-sheets/{net_sheet_id}")
def get_net_sheet(net_sheet_id: int, request: Request):
    return _row_or_404("net_sheets", net_sheet_id, "Net sheet")


@net_sheet_router.post("/net-sheets/{net_sheet_id}/recompute")
def recompute_net_sheet(net_sheet_id: int, request: Request):
    """
    Deliberately explicit. Rates change and profiles get corrected, but a saved net
    sheet must never move on its own - the agent chooses to refresh it.
    """
    sheet = _row_or_404("net_sheets", net_sheet_id, "Net sheet")
    listing = _listing_or_404(sheet["listing_id"])
    result, profile = _compute_for_listing(
        listing, _ws(request), sheet["sale_price"], sheet.get("closing_date"),
        sheet.get("inputs") or {}, sheet.get("fee_profile_id"))
    row = (_db("net_sheets").update({
        "computed": result,
        "fee_profile_id": (profile or {}).get("id"),
        "prepared_at": _now(),
    }).eq("id", net_sheet_id).execute().data)[0]
    row["blocking"] = result.get("blocking")
    row["blockers"] = result.get("blockers")
    return row


@net_sheet_router.delete("/net-sheets/{net_sheet_id}")
def delete_net_sheet(net_sheet_id: int, request: Request):
    _row_or_404("net_sheets", net_sheet_id, "Net sheet")
    _db("net_sheets").delete().eq("id", net_sheet_id).execute()
    return {"deleted": True}


# ════════════════════════════════════════════════════════════
# Offers

class OfferIn(BaseModel):
    buyer_names: Optional[str] = None
    buyer_agent_name: Optional[str] = None
    buyer_agent_email: Optional[str] = None
    buyer_agent_phone: Optional[str] = None
    buyer_brokerage: Optional[str] = None
    lender_name: Optional[str] = None
    title_company: Optional[str] = None
    offer_price: Optional[float] = None
    earnest_money: Optional[float] = None
    additional_deposit: Optional[float] = None
    additional_deposit_due: Optional[str] = None
    financing_type: Optional[str] = None
    closing_date_requested: Optional[str] = None
    seller_concessions: Optional[float] = None
    home_warranty_amount: Optional[float] = None
    home_warranty_paid_by: Optional[str] = None
    repairs_credit: Optional[float] = None
    status: Optional[str] = None
    executed_date: Optional[str] = None
    contingencies: Optional[dict] = None
    notes: Optional[str] = None


# Default contract timeline, in days from the executed date. Editable per offer;
# these mirror a standard FL residential contract as a starting point only.
MILESTONE_TEMPLATE = [
    ("escrow_deposit",   "Escrow deposit due",           3,  True),
    ("loan_application", "Loan application deadline",    5,  False),
    ("inspection",       "Inspection period ends",      15,  True),
    ("appraisal",        "Appraisal deadline",          25,  False),
    ("loan_commitment",  "Loan commitment deadline",    30,  True),
    ("title_ordered",    "Title ordered",                7,  False),
    ("walkthrough",      "Final walkthrough",           -1,  False),   # relative to closing
    ("closing",          "Closing",                    None, True),
]


@router.post("/{listing_id}/offers")
def add_offer(listing_id: int, body: OfferIn, request: Request):
    _listing_or_404(listing_id)
    payload = _clean(body.dict())
    payload["listing_id"] = listing_id
    return (_db("offers").insert(payload).execute().data)[0]


@router.patch("/offers/{offer_id}")
def update_offer(offer_id: int, body: OfferIn, request: Request):
    _row_or_404("offers", offer_id, "Offer")
    payload = _clean(body.dict())
    if not payload:
        raise HTTPException(400, "Nothing to update")
    if payload.get("status") in ("accepted", "rejected", "withdrawn"):
        payload["decision_at"] = _now()
    return (_db("offers").update(payload).eq("id", offer_id).execute().data)[0]


@router.delete("/offers/{offer_id}")
def delete_offer(offer_id: int, request: Request):
    _row_or_404("offers", offer_id, "Offer")
    _db("offers").delete().eq("id", offer_id).execute()
    return {"deleted": True}


@router.post("/offers/{offer_id}/accept")
def accept_offer(offer_id: int, request: Request):
    """
    Accept an offer and set the transaction in motion: mark the listing pending,
    move every other live offer to backup, and seed the contract timeline.
    """
    offer = _row_or_404("offers", offer_id, "Offer")
    listing_id = offer["listing_id"]

    _db("offers").update({"status": "accepted", "decision_at": _now()}).eq("id", offer_id).execute()

    others = (_db("offers").select("id,status").eq("listing_id", listing_id)
              .neq("id", offer_id).execute().data) or []
    for o in others:
        if o["status"] in ("received", "countered"):
            _db("offers").update({"status": "backup"}).eq("id", o["id"]).execute()

    _db("listings").update({
        "status": "pending",
        "under_contract_date": offer.get("executed_date") or date.today().isoformat(),
    }).eq("id", listing_id).execute()

    milestones = _seed_milestones(listing_id, offer, _actor(request))
    return {"accepted": True, "offer_id": offer_id,
            "milestones_created": len(milestones), "milestones": milestones}


def _seed_milestones(listing_id: int, offer: dict, actor: Optional[int]) -> List[dict]:
    """
    Build the contract timeline from the executed date and closing date.
    Skips any milestone key already present, so re-accepting never duplicates.
    """
    executed = _ns._as_date(offer.get("executed_date")) or date.today()
    closing = _ns._as_date(offer.get("closing_date_requested"))

    existing = {m["key"] for m in ((_db("transaction_milestones").select("key")
                .eq("listing_id", listing_id).execute().data) or [])}

    created = []
    for order, (key, label, offset, critical) in enumerate(MILESTONE_TEMPLATE):
        if key in existing:
            continue
        if key == "closing":
            due = closing
        elif offset is not None and offset < 0:
            due = (closing + timedelta(days=offset)) if closing else None
        else:
            due = executed + timedelta(days=offset) if offset is not None else None

        created.append({
            "listing_id": listing_id,
            "offer_id": offer["id"],
            "key": key,
            "label": label,
            "due_date": due.isoformat() if due else None,
            "sort_order": order,
            "is_critical": critical,
        })

    if created:
        return (_db("transaction_milestones").insert(created).execute().data) or []
    return []


# ════════════════════════════════════════════════════════════
# Milestones

class MilestoneIn(BaseModel):
    key: Optional[str] = None
    label: Optional[str] = None
    due_date: Optional[str] = None
    sort_order: Optional[int] = None
    is_critical: Optional[bool] = None
    completed: Optional[bool] = None
    notes: Optional[str] = None


@router.post("/{listing_id}/milestones")
def add_milestone(listing_id: int, body: MilestoneIn, request: Request):
    _listing_or_404(listing_id)
    if not body.label:
        raise HTTPException(400, "label is required")
    payload = _clean(body.dict(exclude={"completed"}))
    payload.update({"listing_id": listing_id, "key": body.key or "other"})
    return (_db("transaction_milestones").insert(payload).execute().data)[0]


@router.patch("/milestones/{milestone_id}")
def update_milestone(milestone_id: int, body: MilestoneIn, request: Request):
    _row_or_404("transaction_milestones", milestone_id, "Milestone")
    payload = _clean(body.dict(exclude={"completed"}))
    if body.completed is not None:
        payload["completed_at"] = _now() if body.completed else None
        payload["completed_by_user_id"] = _actor(request) if body.completed else None
    if not payload:
        raise HTTPException(400, "Nothing to update")
    return (_db("transaction_milestones").update(payload)
            .eq("id", milestone_id).execute().data)[0]


@router.delete("/milestones/{milestone_id}")
def delete_milestone(milestone_id: int, request: Request):
    _row_or_404("transaction_milestones", milestone_id, "Milestone")
    _db("transaction_milestones").delete().eq("id", milestone_id).execute()
    return {"deleted": True}


# ════════════════════════════════════════════════════════════
# Showings and weekly seller reports

class ShowingIn(BaseModel):
    showed_at: Optional[str] = None
    agent_name: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    agent_brokerage: Optional[str] = None
    feedback: Optional[str] = None
    buyer_interest_level: Optional[int] = None
    price_opinion: Optional[str] = None
    source: Optional[str] = None


class WeeklyReportIn(BaseModel):
    week_ending: Optional[str] = None
    showings_count: Optional[int] = None
    mls_matches: Optional[int] = None
    buyer_views: Optional[int] = None
    buyer_favorites: Optional[int] = None
    agent_rejections: Optional[int] = None
    adjustments_made: Optional[str] = None
    notes_to_seller: Optional[str] = None
    notes_internal: Optional[str] = None


@router.post("/{listing_id}/showings")
def add_showing(listing_id: int, body: ShowingIn, request: Request):
    _listing_or_404(listing_id)
    payload = _clean(body.dict())
    payload["listing_id"] = listing_id
    return (_db("listing_showings").insert(payload).execute().data)[0]


@router.patch("/showings/{showing_id}")
def update_showing(showing_id: int, body: ShowingIn, request: Request):
    _row_or_404("listing_showings", showing_id, "Showing")
    payload = _clean(body.dict())
    if payload.get("feedback"):
        payload.setdefault("feedback_received_at", _now())
    if not payload:
        raise HTTPException(400, "Nothing to update")
    return (_db("listing_showings").update(payload).eq("id", showing_id).execute().data)[0]


@router.delete("/showings/{showing_id}")
def delete_showing(showing_id: int, request: Request):
    _row_or_404("listing_showings", showing_id, "Showing")
    _db("listing_showings").delete().eq("id", showing_id).execute()
    return {"deleted": True}


@router.post("/{listing_id}/weekly-reports")
def upsert_weekly_report(listing_id: int, body: WeeklyReportIn, request: Request):
    """
    Upsert on (listing_id, week_ending) so re-saving a week corrects it rather than
    creating a duplicate - same discipline as the coaching daily activity log.

    Showing counts are auto-filled from logged showings when not supplied, so the
    agent is not re-counting what the system already knows.
    """
    _listing_or_404(listing_id)
    week = body.week_ending or date.today().isoformat()
    payload = _clean(body.dict())
    payload.update({"listing_id": listing_id, "week_ending": week})

    if payload.get("showings_count") is None:
        week_end = _ns._as_date(week)
        if week_end:
            start = (week_end - timedelta(days=6)).isoformat()
            shown = (_db("listing_showings").select("id")
                     .eq("listing_id", listing_id)
                     .gte("showed_at", start).lte("showed_at", week + "T23:59:59")
                     .execute().data) or []
            payload["showings_count"] = len(shown)

    existing = (_db("listing_weekly_reports").select("id")
                .eq("listing_id", listing_id).eq("week_ending", week)
                .limit(1).execute().data)
    if existing:
        return (_db("listing_weekly_reports").update(payload)
                .eq("id", existing[0]["id"]).execute().data)[0]
    return (_db("listing_weekly_reports").insert(payload).execute().data)[0]


@router.delete("/weekly-reports/{report_id}")
def delete_weekly_report(report_id: int, request: Request):
    _row_or_404("listing_weekly_reports", report_id, "Weekly report")
    _db("listing_weekly_reports").delete().eq("id", report_id).execute()
    return {"deleted": True}
