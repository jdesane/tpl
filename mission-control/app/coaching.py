"""
Phase 15 — Coaching Platform module.

Surfaces:
  - Coaching client list / create / update / delete
  - Business Plan editor (Budget Model + Economic Model + Lead Gen Model)
  - Computed numbers endpoint (auditable: every value carries its formula + inputs)

The `db` callable is injected by main.py so we inherit the workspace-scoping wrapper
without circular imports. `supabase` is the raw client for child tables that scope
via FK chain (budget_models, economic_models, etc.) and don't carry workspace_id.
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Callable, Any
from datetime import date, datetime

router = APIRouter(prefix="/api/coaching", tags=["coaching"])

# Injected by main.py via setup() ─ avoids circular imports.
_db: Optional[Callable[[str], Any]] = None
_supabase: Any = None


def setup(db_callable, supabase_client):
    """Called from main.py after `db` and `supabase` are defined."""
    global _db, _supabase
    _db = db_callable
    _supabase = supabase_client


# ════════════════════════════════════════════════════════════
# Pydantic models
# ════════════════════════════════════════════════════════════

class CoachingClientIn(BaseModel):
    # Existing-contact path: just pass lead_id
    lead_id: Optional[int] = None
    # New-contact path: pass these to create the lead AND coaching_client in one call
    new_contact: Optional[dict] = None  # {first_name, last_name, email, phone, current_brokerage}
    # Coaching metadata (all optional at creation; can be filled in later)
    brokerage: Optional[str] = None
    lpt_comp_plan: Optional[str] = None
    license_date: Optional[str] = None
    market_city: Optional[str] = None
    market_state: Optional[str] = None
    avg_sale_price: Optional[float] = None
    avg_commission_rate: Optional[float] = None
    call_cadence: Optional[str] = "WEEKLY"
    coaching_start_date: Optional[str] = None
    notes: Optional[str] = None


class CoachingClientUpdate(BaseModel):
    brokerage: Optional[str] = None
    lpt_comp_plan: Optional[str] = None
    license_date: Optional[str] = None
    market_city: Optional[str] = None
    market_state: Optional[str] = None
    avg_sale_price: Optional[float] = None
    avg_commission_rate: Optional[float] = None
    call_cadence: Optional[str] = None
    coaching_start_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class BusinessPlanUpdate(BaseModel):
    gci_target: Optional[float] = None
    notes: Optional[str] = None


class BudgetModelUpdate(BaseModel):
    paid_to_brokerage: Optional[float] = None
    referrals_to_you_count: Optional[int] = None
    referrals_avg_commission: Optional[float] = None
    referrals_split_pct: Optional[float] = None
    seller_specialist_split_pct: Optional[float] = None
    buyer_specialist_split_pct: Optional[float] = None
    operating_expenses: Optional[dict] = None
    charity_pct: Optional[float] = None
    retirement_pct: Optional[float] = None
    income_tax_pct: Optional[float] = None
    personal_expenses: Optional[dict] = None
    avg_net_commission_per_close: Optional[float] = None
    surplus_allocation: Optional[list] = None


class EconomicModelUpdate(BaseModel):
    seller_pct: Optional[float] = None
    seller_avg_sale_price: Optional[float] = None
    buyer_avg_sale_price: Optional[float] = None
    commission_rate: Optional[float] = None
    listings_close_pct: Optional[float] = None
    buyers_close_pct: Optional[float] = None
    listing_appt_to_list_pct: Optional[float] = None
    buyer_appt_to_work_pct: Optional[float] = None
    avg_days_on_market: Optional[int] = None
    avg_buyer_working_days: Optional[int] = None


# ════════════════════════════════════════════════════════════
# Default operating-expense / personal-expense scaffolds
# ════════════════════════════════════════════════════════════
# These are line-item TEMPLATES — agents can add/remove rows from the UI.
# JSONB structure: { "Category > Line Item": amount }

DEFAULT_OPERATING_EXPENSES = {
    "Salaries > Admin": 0,
    "Salaries > Marketing": 0,
    "Lead Gen Marketing > Advertising in media": 0,
    "Lead Gen Marketing > Photography / staging": 0,
    "Lead Gen Marketing > Websites / internet leads / social clicks": 0,
    "Lead Gen Marketing > Direct mail postcards": 0,
    "Lead Gen Marketing > Signs / brochure boxes": 0,
    "Lead Gen Marketing > Name tags / shirts / car magnets": 0,
    "Lead Gen Marketing > Sponsoring festivals / teams": 0,
    "Lead Gen Prospecting > Open houses": 0,
    "Lead Gen Prospecting > Client parties": 0,
    "Lead Gen Prospecting > Networking events": 0,
    "Lead Gen Prospecting > Teaching / speaking": 0,
    "Lead Gen Prospecting > Builders / FSBOs direct": 0,
    "Lead Gen Prospecting > Door to door": 0,
    "Occupancy > Rent": 0,
    "Technology > Apps / software / subscriptions": 0,
    "Technology > Phone": 0,
    "Operations > Supplies": 0,
    "Operations > Education / Dues / Coaching / Travel": 0,
    "Operations > Equipment (long-term use)": 0,
    "Auto > Gas": 0,
    "Auto > Maintenance": 0,
    "Auto > Insurance": 0,
}

DEFAULT_PERSONAL_EXPENSES = {
    "House": 0,
    "Food": 0,
    "Recreation / Entertainment": 0,
    "Credit Cards": 0,
    "Car": 0,
    "Other Regular Payments": 0,
    "Miscellaneous": 0,
}

# Default LPT cap based on comp plan
LPT_CAP_BUSINESS_BUILDER = 5000
LPT_CAP_BROKERAGE_PARTNER = 15000


# ════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════

def _ws(req: Request) -> int:
    return getattr(req.state, "workspace_id", 1) or 1


def _normalize_pct(v):
    """Accept percentages as either 0.30 or 30 — snap to 0–1 range."""
    if v is None:
        return None
    f = float(v)
    return f / 100.0 if f > 1.0 else f


def _enrich_client(row: dict) -> dict:
    """Attach lead-name fields onto a coaching_client row."""
    if not row:
        return row
    lead_id = row.get("lead_id")
    if lead_id:
        try:
            r = _supabase.table("leads").select("first_name,last_name,name,email,phone,current_brokerage").eq("id", lead_id).single().execute()
            if r.data:
                row["lead"] = r.data
        except Exception:
            row["lead"] = None
    return row


def _ensure_business_plan(client_id: int, year: int, workspace_id: int) -> dict:
    """Find or create the business_plan + budget_model + economic_model + lead_gen_model rows."""
    bp_resp = _supabase.table("business_plans").select("*").eq("coaching_client_id", client_id).eq("year", year).execute()
    if bp_resp.data:
        plan = bp_resp.data[0]
    else:
        ins = _supabase.table("business_plans").insert({
            "workspace_id": workspace_id,
            "coaching_client_id": client_id,
            "year": year,
            "gci_target": 0,
        }).execute()
        plan = ins.data[0]

    plan_id = plan["id"]

    # Budget model — auto-create with seeded operating/personal expense scaffolds
    bm_resp = _supabase.table("budget_models").select("*").eq("business_plan_id", plan_id).execute()
    if bm_resp.data:
        budget = bm_resp.data[0]
    else:
        # Default paid_to_brokerage from the client's comp plan, if set
        client = _supabase.table("coaching_clients").select("lpt_comp_plan").eq("id", client_id).single().execute().data or {}
        cap = 0
        if client.get("lpt_comp_plan") == "BROKERAGE_PARTNER":
            cap = LPT_CAP_BROKERAGE_PARTNER
        elif client.get("lpt_comp_plan") == "BUSINESS_BUILDER":
            cap = LPT_CAP_BUSINESS_BUILDER
        ins = _supabase.table("budget_models").insert({
            "business_plan_id": plan_id,
            "paid_to_brokerage": cap,
            "operating_expenses": DEFAULT_OPERATING_EXPENSES,
            "personal_expenses": DEFAULT_PERSONAL_EXPENSES,
        }).execute()
        budget = ins.data[0]

    # Economic model
    em_resp = _supabase.table("economic_models").select("*").eq("business_plan_id", plan_id).execute()
    if em_resp.data:
        economic = em_resp.data[0]
    else:
        # Default sale prices from the client's avg_sale_price (same value for both sides until split)
        client = _supabase.table("coaching_clients").select("avg_sale_price,avg_commission_rate").eq("id", client_id).single().execute().data or {}
        asp = float(client.get("avg_sale_price") or 0)
        rate = float(client.get("avg_commission_rate") or 0.025)
        ins = _supabase.table("economic_models").insert({
            "business_plan_id": plan_id,
            "seller_avg_sale_price": asp,
            "buyer_avg_sale_price": asp,
            "commission_rate": rate,
        }).execute()
        economic = ins.data[0]

    # Lead Gen model
    lg_resp = _supabase.table("lead_gen_models").select("*").eq("business_plan_id", plan_id).execute()
    if lg_resp.data:
        leadgen = lg_resp.data[0]
    else:
        ins = _supabase.table("lead_gen_models").insert({
            "business_plan_id": plan_id,
        }).execute()
        leadgen = ins.data[0]

    return {
        "plan": plan,
        "budget_model": budget,
        "economic_model": economic,
        "lead_gen_model": leadgen,
    }


# ════════════════════════════════════════════════════════════
# Math: Economic Model derivations
# ════════════════════════════════════════════════════════════
# Mirrors the MREA workbook:
#   - Seller revenue = GCI × seller %
#   - Buyer revenue  = GCI − seller revenue
#   - Volume         = revenue / commission rate
#   - Houses sold    = volume / avg sale price
#   - Listings taken = houses sold (sellers) / % listings close
#   - Buyers shown   = houses sold (buyers) / % buyers close
#   - Listing appts  = listings taken / % appts that list
#   - Buyer consults = buyers shown / % buyer appts work
#   - Per week       = annual / 48  (NOT 52 — accounts for vacation/holidays per legacy spreadsheet)
#   - Active listings to carry = houses sold sellers / (365 / DOM)
#   - Ready buyers to work     = houses sold buyers  / (365 / buyer working time)

def _safe_div(a, b):
    if b is None or b == 0:
        return 0
    return a / b


def calc_economic(gci_target: float, em: dict) -> dict:
    seller_pct = float(em.get("seller_pct") or 0.5)
    sasp = float(em.get("seller_avg_sale_price") or 0)
    basp = float(em.get("buyer_avg_sale_price") or 0)
    rate = float(em.get("commission_rate") or 0.025)
    list_close = float(em.get("listings_close_pct") or 0.85)
    buyer_close = float(em.get("buyers_close_pct") or 0.80)
    list_appt_pct = float(em.get("listing_appt_to_list_pct") or 0.65)
    buyer_appt_pct = float(em.get("buyer_appt_to_work_pct") or 0.75)
    dom = float(em.get("avg_days_on_market") or 60)
    buyer_days = float(em.get("avg_buyer_working_days") or 60)

    seller_rev = gci_target * seller_pct
    buyer_rev = gci_target - seller_rev

    seller_volume = _safe_div(seller_rev, rate)
    buyer_volume = _safe_div(buyer_rev, rate)

    sellers_closed = _safe_div(seller_volume, sasp) if sasp > 0 else 0
    buyers_closed = _safe_div(buyer_volume, basp) if basp > 0 else 0

    listings_taken = _safe_div(sellers_closed, list_close)
    buyers_worked = _safe_div(buyers_closed, buyer_close)

    listing_appts_yr = _safe_div(listings_taken, list_appt_pct)
    buyer_consults_yr = _safe_div(buyers_worked, buyer_appt_pct)

    listings_per_wk = listing_appts_yr / 48.0
    buyers_per_wk = buyer_consults_yr / 48.0

    active_listings_carry = _safe_div(sellers_closed, _safe_div(365, dom)) if dom > 0 else 0
    ready_buyers = _safe_div(buyers_closed, _safe_div(365, buyer_days)) if buyer_days > 0 else 0

    return {
        "seller_revenue":          {"value": round(seller_rev, 2),       "formula": "GCI Target × Seller %"},
        "buyer_revenue":           {"value": round(buyer_rev, 2),        "formula": "GCI Target − Seller Revenue"},
        "seller_volume":           {"value": round(seller_volume, 2),    "formula": "Seller Revenue ÷ Commission Rate"},
        "buyer_volume":            {"value": round(buyer_volume, 2),     "formula": "Buyer Revenue ÷ Commission Rate"},
        "sellers_closed":          {"value": round(sellers_closed, 2),   "formula": "Seller Volume ÷ Seller Avg Sale Price"},
        "buyers_closed":           {"value": round(buyers_closed, 2),    "formula": "Buyer Volume ÷ Buyer Avg Sale Price"},
        "houses_sold_total":       {"value": round(sellers_closed + buyers_closed, 2), "formula": "Sellers Closed + Buyers Closed"},
        "listings_taken":          {"value": round(listings_taken, 2),   "formula": "Sellers Closed ÷ % Listings Close"},
        "buyers_shown":            {"value": round(buyers_worked, 2),    "formula": "Buyers Closed ÷ % Buyers Close"},
        "listing_appts_annual":    {"value": round(listing_appts_yr, 1), "formula": "Listings Taken ÷ % Appts that List"},
        "buyer_consults_annual":   {"value": round(buyer_consults_yr, 1),"formula": "Buyers Shown ÷ % Buyer Appts that Work"},
        "listing_appts_per_week":  {"value": round(listings_per_wk, 2),  "formula": "Listing Appts Annual ÷ 48"},
        "buyer_consults_per_week": {"value": round(buyers_per_wk, 2),    "formula": "Buyer Consults Annual ÷ 48"},
        "active_listings_to_carry":{"value": round(active_listings_carry, 1), "formula": "Sellers Closed ÷ (365 ÷ Avg DOM)"},
        "ready_buyers":            {"value": round(ready_buyers, 1),     "formula": "Buyers Closed ÷ (365 ÷ Avg Buyer Working Days)"},
    }


# ════════════════════════════════════════════════════════════
# Math: Budget Model derivations
# ════════════════════════════════════════════════════════════

def calc_budget(gci_target: float, bm: dict, econ_calc: dict) -> dict:
    paid_to_brokerage = float(bm.get("paid_to_brokerage") or 0)
    ref_count = float(bm.get("referrals_to_you_count") or 0)
    ref_avg = float(bm.get("referrals_avg_commission") or 0)
    ref_split = float(bm.get("referrals_split_pct") or 0.25)
    seller_split = float(bm.get("seller_specialist_split_pct") or 0)  # 0 means no team
    buyer_split = float(bm.get("buyer_specialist_split_pct") or 0)

    seller_rev = econ_calc["seller_revenue"]["value"]
    buyer_rev = econ_calc["buyer_revenue"]["value"]

    referral_fees = ref_count * ref_avg * ref_split
    seller_specialist_cost = seller_rev * seller_split
    buyer_specialist_cost = buyer_rev * buyer_split
    total_cost_of_sale = paid_to_brokerage + referral_fees + seller_specialist_cost + buyer_specialist_cost

    gross_profit = gci_target - total_cost_of_sale

    op_exp = bm.get("operating_expenses") or {}
    if isinstance(op_exp, str):
        try:
            import json as _j
            op_exp = _j.loads(op_exp)
        except Exception:
            op_exp = {}
    total_op_exp = sum(float(v or 0) for v in op_exp.values()) if isinstance(op_exp, dict) else 0

    net_income = gross_profit - total_op_exp

    charity_pct = float(bm.get("charity_pct") or 0)
    retirement_pct = float(bm.get("retirement_pct") or 0)
    income_tax_pct = float(bm.get("income_tax_pct") or 0)

    charity_amt = net_income * charity_pct
    retirement_amt = net_income * retirement_pct
    taxable_income = net_income - charity_amt - retirement_amt
    tax_amt = taxable_income * income_tax_pct
    take_home = taxable_income - tax_amt
    monthly_budget = take_home / 12.0

    # Personal expenses
    pers = bm.get("personal_expenses") or {}
    if isinstance(pers, str):
        try:
            import json as _j
            pers = _j.loads(pers)
        except Exception:
            pers = {}
    monthly_personal = sum(float(v or 0) for v in pers.values()) if isinstance(pers, dict) else 0
    annual_personal = monthly_personal * 12.0

    # Survival number — total annual need = personal annual + business op exp + (each × 30% for taxes)
    annual_need_pre_tax = annual_personal + total_op_exp
    annual_need_w_tax = annual_need_pre_tax * 1.30
    avg_net_close = float(bm.get("avg_net_commission_per_close") or 0)
    survival_closings = _safe_div(annual_need_w_tax, avg_net_close)
    closings_total = econ_calc["houses_sold_total"]["value"]
    closings_beyond_survival = closings_total - survival_closings
    surplus = closings_beyond_survival * avg_net_close * (1 - income_tax_pct)

    return {
        "referral_fees":           {"value": round(referral_fees, 2),         "formula": "# Referrals to You × Avg Referral Commission × Referral Split %"},
        "seller_specialist_cost":  {"value": round(seller_specialist_cost, 2),"formula": "Seller Revenue × Seller Specialist Split %"},
        "buyer_specialist_cost":   {"value": round(buyer_specialist_cost, 2), "formula": "Buyer Revenue × Buyer Specialist Split %"},
        "total_cost_of_sale":      {"value": round(total_cost_of_sale, 2),    "formula": "Paid to Brokerage + Referral Fees + Seller Specialist + Buyer Specialist"},
        "gross_profit":            {"value": round(gross_profit, 2),          "formula": "GCI Target − Total Cost of Sale"},
        "total_operating_expenses":{"value": round(total_op_exp, 2),          "formula": "Sum of all Operating Expense line items"},
        "net_income":              {"value": round(net_income, 2),            "formula": "Gross Profit − Total Operating Expenses"},
        "charity_amount":          {"value": round(charity_amt, 2),           "formula": "Net Income × Charity %"},
        "retirement_amount":       {"value": round(retirement_amt, 2),        "formula": "Net Income × Retirement %"},
        "taxable_income":          {"value": round(taxable_income, 2),        "formula": "Net Income − Charity − Retirement"},
        "tax_amount":              {"value": round(tax_amt, 2),               "formula": "Taxable Income × Income Tax %"},
        "take_home":               {"value": round(take_home, 2),             "formula": "Taxable Income − Tax Amount"},
        "monthly_life_budget":     {"value": round(monthly_budget, 2),        "formula": "Take Home ÷ 12"},
        "annual_personal_expenses":{"value": round(annual_personal, 2),       "formula": "Monthly Personal Subtotal × 12"},
        "annual_need_w_tax":       {"value": round(annual_need_w_tax, 2),     "formula": "(Annual Personal + Operating Expenses) × 1.30"},
        "survival_closings":       {"value": round(survival_closings, 2),     "formula": "Annual Need (incl. tax) ÷ Avg Net Commission per Close"},
        "closings_beyond_survival":{"value": round(closings_beyond_survival, 2), "formula": "Total Closings (planned) − Survival Closings"},
        "surplus":                 {"value": round(surplus, 2),               "formula": "Closings Beyond Survival × Avg Net Commission × (1 − Tax %)"},
    }


# ════════════════════════════════════════════════════════════
# Math: Lead Gen derivations
# ════════════════════════════════════════════════════════════

def calc_lead_gen(econ_calc: dict, lg: dict) -> dict:
    met_pct = float(lg.get("met_pct") or 0.8)
    cur_met = float(lg.get("current_met_db_size") or 0)
    cur_havent = float(lg.get("current_havent_met_db_size") or 0)

    total_sales = econ_calc["houses_sold_total"]["value"]
    sales_from_met = total_sales * met_pct
    sales_from_havent_met = total_sales - sales_from_met

    # MREA rule: 12 touches/yr × 2 contacts per sale → required Met DB = met sales × 12 / 2 = met sales × 6
    required_met_db = sales_from_met * 6
    # Haven't-Met rule: 50:1 ratio
    required_havent_met_db = sales_from_havent_met * 50

    return {
        "sales_from_met":          {"value": round(sales_from_met, 2),       "formula": "Total Sales × Met %"},
        "sales_from_havent_met":   {"value": round(sales_from_havent_met, 2),"formula": "Total Sales − Sales from Met"},
        "required_met_db":         {"value": round(required_met_db, 0),     "formula": "Met Sales × 12 ÷ 2  (12 touches/yr, 2 contacts per sale)"},
        "required_havent_met_db":  {"value": round(required_havent_met_db, 0), "formula": "Haven't-Met Sales × 50"},
        "met_gap":                 {"value": round(required_met_db - cur_met, 0), "formula": "Required Met DB − Current Met DB"},
        "havent_met_gap":          {"value": round(required_havent_met_db - cur_havent, 0), "formula": "Required Haven't-Met DB − Current Haven't-Met DB"},
    }


# ════════════════════════════════════════════════════════════
# Routes — Coaching Clients
# ════════════════════════════════════════════════════════════

@router.get("/clients")
def list_clients(request: Request):
    workspace_id = _ws(request)
    resp = _db("coaching_clients").select("*").order("created_at", desc=True).execute()
    rows = resp.data or []
    return [_enrich_client(r) for r in rows]


@router.get("/clients/{client_id}")
def get_client(client_id: int, request: Request):
    resp = _db("coaching_clients").select("*").eq("id", client_id).execute()
    if not resp.data:
        raise HTTPException(404, "Coaching client not found")
    return _enrich_client(resp.data[0])


@router.post("/clients")
def create_client(payload: CoachingClientIn, request: Request):
    workspace_id = _ws(request)
    lead_id = payload.lead_id

    # New-contact path — create the lead first
    if not lead_id and payload.new_contact:
        nc = payload.new_contact
        first = (nc.get("first_name") or "").strip()
        last = (nc.get("last_name") or "").strip()
        full_name = (nc.get("name") or f"{first} {last}").strip()
        email = (nc.get("email") or "").strip()
        if not full_name or not email:
            raise HTTPException(400, "New contact requires name and email")
        # Reuse if a lead with this email already exists in the workspace
        existing = _db("leads").select("id").eq("email", email).execute()
        if existing.data:
            lead_id = existing.data[0]["id"]
        else:
            lead_row = {
                "first_name": first or full_name.split(" ")[0],
                "last_name": last or " ".join(full_name.split(" ")[1:]),
                "name": full_name,
                "email": email,
                "phone": nc.get("phone"),
                "current_brokerage": nc.get("current_brokerage"),
                "stage": "coaching_client",
                "source": "Coaching",
            }
            ins = _db("leads").insert(lead_row).execute()
            lead_id = ins.data[0]["id"]

    if not lead_id:
        raise HTTPException(400, "Either lead_id or new_contact is required")

    # Refuse to duplicate
    existing_cc = _supabase.table("coaching_clients").select("id").eq("lead_id", lead_id).execute()
    if existing_cc.data:
        raise HTTPException(409, "This contact is already a coaching client")

    row = {
        "workspace_id": workspace_id,
        "lead_id": lead_id,
        "brokerage": payload.brokerage,
        "lpt_comp_plan": payload.lpt_comp_plan,
        "license_date": payload.license_date,
        "market_city": payload.market_city,
        "market_state": payload.market_state,
        "avg_sale_price": payload.avg_sale_price,
        "avg_commission_rate": _normalize_pct(payload.avg_commission_rate),
        "call_cadence": payload.call_cadence or "WEEKLY",
        "coaching_start_date": payload.coaching_start_date or date.today().isoformat(),
        "notes": payload.notes,
    }
    row = {k: v for k, v in row.items() if v is not None}
    ins = _supabase.table("coaching_clients").insert(row).execute()
    client = ins.data[0]

    # Auto-create the current-year business plan + child models so the editor has data to render
    _ensure_business_plan(client["id"], datetime.utcnow().year, workspace_id)

    return _enrich_client(client)


@router.patch("/clients/{client_id}")
def update_client(client_id: int, payload: CoachingClientUpdate, request: Request):
    data = {k: v for k, v in payload.dict().items() if v is not None}
    if "avg_commission_rate" in data:
        data["avg_commission_rate"] = _normalize_pct(data["avg_commission_rate"])
    if not data:
        raise HTTPException(400, "No fields to update")
    resp = _supabase.table("coaching_clients").update(data).eq("id", client_id).execute()
    if not resp.data:
        raise HTTPException(404, "Coaching client not found")
    return _enrich_client(resp.data[0])


@router.delete("/clients/{client_id}")
def delete_client(client_id: int, request: Request):
    _supabase.table("coaching_clients").delete().eq("id", client_id).execute()
    return {"ok": True}


# ════════════════════════════════════════════════════════════
# Routes — Business Plan + child models
# ════════════════════════════════════════════════════════════

@router.get("/clients/{client_id}/plan")
def get_plan(client_id: int, request: Request, year: Optional[int] = None):
    workspace_id = _ws(request)
    yr = year or datetime.utcnow().year
    bundle = _ensure_business_plan(client_id, yr, workspace_id)
    return bundle


@router.patch("/clients/{client_id}/plan")
def update_plan(client_id: int, payload: BusinessPlanUpdate, request: Request, year: Optional[int] = None):
    yr = year or datetime.utcnow().year
    plan_resp = _supabase.table("business_plans").select("id").eq("coaching_client_id", client_id).eq("year", yr).execute()
    if not plan_resp.data:
        raise HTTPException(404, f"No plan for year {yr}")
    plan_id = plan_resp.data[0]["id"]
    data = {k: v for k, v in payload.dict().items() if v is not None}
    if not data:
        raise HTTPException(400, "No fields to update")
    upd = _supabase.table("business_plans").update(data).eq("id", plan_id).execute()
    return upd.data[0]


@router.patch("/clients/{client_id}/budget-model")
def update_budget(client_id: int, payload: BudgetModelUpdate, request: Request, year: Optional[int] = None):
    yr = year or datetime.utcnow().year
    plan_resp = _supabase.table("business_plans").select("id").eq("coaching_client_id", client_id).eq("year", yr).execute()
    if not plan_resp.data:
        raise HTTPException(404, f"No plan for year {yr}")
    plan_id = plan_resp.data[0]["id"]
    data = payload.dict(exclude_unset=True)
    # Normalize percentages
    for k in ("referrals_split_pct", "seller_specialist_split_pct", "buyer_specialist_split_pct",
              "charity_pct", "retirement_pct", "income_tax_pct"):
        if k in data and data[k] is not None:
            data[k] = _normalize_pct(data[k])
    if not data:
        raise HTTPException(400, "No fields to update")
    upd = _supabase.table("budget_models").update(data).eq("business_plan_id", plan_id).execute()
    if not upd.data:
        raise HTTPException(404, "Budget model not found")
    return upd.data[0]


@router.patch("/clients/{client_id}/economic-model")
def update_economic(client_id: int, payload: EconomicModelUpdate, request: Request, year: Optional[int] = None):
    yr = year or datetime.utcnow().year
    plan_resp = _supabase.table("business_plans").select("id").eq("coaching_client_id", client_id).eq("year", yr).execute()
    if not plan_resp.data:
        raise HTTPException(404, f"No plan for year {yr}")
    plan_id = plan_resp.data[0]["id"]
    data = payload.dict(exclude_unset=True)
    for k in ("seller_pct", "commission_rate", "listings_close_pct", "buyers_close_pct",
              "listing_appt_to_list_pct", "buyer_appt_to_work_pct"):
        if k in data and data[k] is not None:
            data[k] = _normalize_pct(data[k])
    if not data:
        raise HTTPException(400, "No fields to update")
    upd = _supabase.table("economic_models").update(data).eq("business_plan_id", plan_id).execute()
    if not upd.data:
        raise HTTPException(404, "Economic model not found")
    return upd.data[0]


# ════════════════════════════════════════════════════════════
# Routes — Computed numbers (auditable)
# ════════════════════════════════════════════════════════════

@router.get("/clients/{client_id}/computed")
def get_computed(client_id: int, request: Request, year: Optional[int] = None):
    workspace_id = _ws(request)
    yr = year or datetime.utcnow().year
    bundle = _ensure_business_plan(client_id, yr, workspace_id)
    plan = bundle["plan"]
    bm = bundle["budget_model"]
    em = bundle["economic_model"]
    lg = bundle["lead_gen_model"]
    gci = float(plan.get("gci_target") or 0)

    economic = calc_economic(gci, em)
    budget = calc_budget(gci, bm, economic)
    leadgen = calc_lead_gen(economic, lg)

    return {
        "year": yr,
        "gci_target": gci,
        "economic": economic,
        "budget": budget,
        "lead_gen": leadgen,
    }


# ════════════════════════════════════════════════════════════
# Routes — Lead picker (for the Invite modal)
# ════════════════════════════════════════════════════════════

@router.get("/lead-search")
def search_leads(request: Request, q: Optional[str] = None, limit: int = 15):
    """Autocomplete for the Invite modal — returns candidate leads not yet flagged as coaching clients."""
    workspace_id = _ws(request)
    q_str = (q or "").strip()
    qb = _db("leads").select("id,first_name,last_name,name,email,phone,current_brokerage")
    if q_str:
        # Supabase OR filter syntax
        like = f"%{q_str}%"
        qb = qb.or_(f"name.ilike.{like},email.ilike.{like},first_name.ilike.{like},last_name.ilike.{like}")
    leads = qb.limit(limit).execute().data or []
    # Filter out leads already linked to a coaching_client
    if leads:
        ids = [l["id"] for l in leads]
        existing = _supabase.table("coaching_clients").select("lead_id").in_("lead_id", ids).execute().data or []
        existing_set = {r["lead_id"] for r in existing}
        leads = [l for l in leads if l["id"] not in existing_set]
    return leads
