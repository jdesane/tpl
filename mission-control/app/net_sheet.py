"""
Seller net sheet calculation engine.

Pure computation - no FastAPI, no Supabase, no I/O. That makes it fully testable and
reusable by the API, the PDF generator, and any future export.

DESIGN RULES

1. All fee math comes from a fee_profile config (see the migration), never from
   constants in this file. The original workbook hardcoded Florida law - title
   insurance at $5.75/K, doc stamps at $0.70/$100, 365-day proration from Jan 1 -
   and this product is sold to agents in other states. Wrong numbers on a seller-facing
   document are worse than no document.

2. Every line carries its `formula` string. An agent handing this to a seller has to
   be able to explain any line out loud. Same audit-popover pattern as the coaching
   computed values.

3. Money is Decimal, quantized to cents at the boundary. Never float.

4. Agent overrides always win over profile defaults, and the line records which it was.


DEFECTS IN THE ORIGINAL WORKBOOK, CORRECTED HERE (each flagged in the output)

  a) Miscellaneous Credits were SUBTRACTED. The Expense Sheet computes
     `=F9-F33-F37-F39` where F39 is labelled "Miscellaneous Credits (Additions)".
     An addition that reduces proceeds is a sign error. Added here.
     Set inputs["misc_credits_are_deductions"]=True to reproduce the old behaviour.

  b) Title insurance was charged as a flat $575 on the first $100k even when the
     sale price was below $100k (`=100000*5.75/1000` is unconditional). That
     overcharges every sub-$100k sale. Tiers are applied against the actual price here.

  c) Only two title tiers existed, correct to $1M and wrong above it. Florida's
     schedule steps down again at $1M, $5M and $10M. The full ladder lives in the
     profile.

  d) Doc stamps were `price * 0.007`. Florida charges per $100 "or fraction thereof",
     so the taxable base rounds UP to the next $100. Equivalent only when the price is
     already a round hundred.
"""
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from datetime import date, datetime
from typing import Optional, Any, Dict, List

CENTS = Decimal("0.01")


# ════════════════════════════════════════════════════════════
# Helpers

def _d(value, default="0") -> Decimal:
    """Coerce anything reasonable to Decimal. None/'' -> default."""
    if value is None or value == "":
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value) -> Decimal:
    return _d(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def _as_date(value) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (ValueError, TypeError):
        return None


def _line(key: str, label: str, amount, formula: str, source: str = "computed",
          editable: bool = True, note: Optional[str] = None) -> dict:
    out = {
        "key": key,
        "label": label,
        "amount": float(money(amount)),
        "formula": formula,
        "source": source,        # profile | input | computed
        "editable": editable,
    }
    if note:
        out["note"] = note
    return out


def _pick(inputs: dict, defaults: dict, key: str, fallback="0"):
    """
    Agent override wins over profile default. Returns (value, source) so the line
    can say where the number came from.
    """
    if inputs.get(key) not in (None, ""):
        return _d(inputs.get(key)), "input"
    if defaults.get(key) not in (None, ""):
        return _d(defaults.get(key)), "profile"
    return _d(fallback), "computed"


# ════════════════════════════════════════════════════════════
# Fee components

def title_insurance(sale_price: Decimal, cfg: dict) -> tuple:
    """
    Tiered owner's-policy premium. Tiers are [{up_to, rate_per_1000}, ...] with a
    final null `up_to` meaning "everything above". Each tier's rate applies only to
    the portion of the price within that band.

    Fixes workbook defect (b): the first band is applied to min(price, band), not
    unconditionally to the full band.
    """
    tiers = (cfg or {}).get("tiers") or []
    if not tiers:
        return Decimal("0"), "no title tiers configured in fee profile"

    total = Decimal("0")
    lower = Decimal("0")
    parts: List[str] = []

    for tier in tiers:
        up_to = tier.get("up_to")
        rate = _d(tier.get("rate_per_1000"))
        ceiling = sale_price if up_to is None else min(sale_price, _d(up_to))
        band = ceiling - lower
        if band > 0:
            amount = band / Decimal("1000") * rate
            total += amount
            parts.append(f"${band:,.0f} x ${rate}/1,000 = ${amount:,.2f}")
            lower = ceiling
        if up_to is not None and sale_price <= _d(up_to):
            break

    minimum = _d((cfg or {}).get("minimum", "0"))
    if minimum > 0 and total < minimum:
        parts.append(f"raised to profile minimum ${minimum:,.2f}")
        total = minimum

    return total, " + ".join(parts) if parts else "0"


def doc_stamps(sale_price: Decimal, cfg: dict, county: Optional[str],
               property_type: Optional[str]) -> tuple:
    """
    Documentary stamp tax on the deed.

    Fixes workbook defect (d): charged per $100 "or fraction thereof", so the base
    rounds UP to the next $100 when the profile says so.
    """
    cfg = cfg or {}
    rate = _d(cfg.get("rate_per_100", "0"))
    surtax = Decimal("0")
    override_note = ""

    overrides = cfg.get("county_overrides") or {}
    if county and county in overrides:
        ov = overrides[county]
        rate = _d(ov.get("rate_per_100", rate))
        applies = ov.get("surtax_applies_to")
        if ov.get("surtax_per_100") is not None:
            if applies != "non_single_family" or (property_type or "") != "single_family":
                surtax = _d(ov.get("surtax_per_100"))
        override_note = f" ({county} county rate)"

    if cfg.get("rounding") == "up_to_next_100":
        hundreds = (sale_price / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_CEILING)
        base_desc = f"ceil(${sale_price:,.2f} / 100) = {hundreds:,} hundreds"
    else:
        hundreds = sale_price / Decimal("100")
        base_desc = f"${sale_price:,.2f} / 100"

    total = hundreds * (rate + surtax)
    rate_desc = f"${rate}/100" + (f" + ${surtax}/100 surtax" if surtax else "")
    return total, f"{base_desc} x {rate_desc}{override_note} = ${total:,.2f}"


def prorated_taxes(annual_taxes: Decimal, closing: Optional[date], cfg: dict) -> tuple:
    """
    Seller's share of the year's property taxes.

    Mirrors the workbook: day one is January 1, daily rate is annual / day_count,
    and the seller is charged for the days elapsed. `seller_pays_through` selects
    whether closing day itself is the seller's.
    """
    cfg = cfg or {}
    if not closing or annual_taxes <= 0:
        return Decimal("0"), "no closing date or annual taxes set"

    day_count = int(cfg.get("day_count", 365))
    jan1 = date(closing.year, 1, 1)
    days = (closing - jan1).days
    if cfg.get("seller_pays_through") != "day_before_closing":
        days += 1

    daily = annual_taxes / Decimal(day_count)
    total = daily * Decimal(days)
    return total, (f"${annual_taxes:,.2f} / {day_count} days = ${daily:,.4f}/day "
                   f"x {days} days (Jan 1 to {closing.isoformat()}) = ${total:,.2f}")


# ════════════════════════════════════════════════════════════
# Main entry point

def compute_net_sheet(sale_price, profile_config: dict, inputs: Optional[dict] = None, *,
                      county: Optional[str] = None,
                      closing_date=None,
                      property_type: Optional[str] = None,
                      mortgage_payoffs: Optional[List[dict]] = None,
                      profile_meta: Optional[dict] = None) -> dict:
    """
    Produce a full seller net sheet.

    sale_price      the price this scenario is based on (list price, or an offer)
    profile_config  fee_profiles.config - the AGENT'S OWN numbers, not ours
    inputs          agent overrides, keyed to match the line keys below
    mortgage_payoffs  [{lender_name, estimated_payoff}] from listing_mortgages
    profile_meta    {is_template, confirmed_at, name} - drives the blocking check

    Returns sections of labelled lines each with its formula, totals, and a
    `blocking` flag. We supply arithmetic; the agent supplies and owns the rates.
    """
    inputs = dict(inputs or {})
    cfg = dict(profile_config or {})
    defaults = dict(cfg.get("defaults") or {})
    price = _d(sale_price)
    closing = _as_date(closing_date)
    corrections: List[str] = []

    # ── Is this profile safe to put in front of a seller? ───
    # A net sheet is what a seller uses to decide whether to accept an offer. It must
    # never be produced from a starter template or from numbers nobody confirmed.
    # The figures still compute (the agent needs to see their setup working) but the
    # result is marked blocking, and callers must refuse to render or send it.
    meta = dict(profile_meta or {})
    blockers: List[str] = []
    if not cfg:
        blockers.append("No fee profile is set for this listing. Add your closing costs first.")
    if meta.get("is_template"):
        blockers.append(
            "This is a starter template, not your rates. Copy it to your workspace and "
            "replace every number with your own title company quote or your last "
            "settlement statement."
        )
    if not meta.get("confirmed_at") and not meta.get("is_template"):
        blockers.append(
            "These closing costs have not been confirmed yet. Review each line against "
            "your last settlement statement and confirm before sending this to a seller."
        )

    # ── Brokerage ───────────────────────────────────────────
    commission_pct = _d(inputs.get("commission_pct", "0"))
    commission = price * commission_pct
    brokerage_lines = [
        _line("commission", "Commission",
              commission,
              f"${price:,.2f} x {commission_pct * 100:.2f}% = ${commission:,.2f}",
              source="input"),
    ]
    txn_fee, txn_src = _pick(inputs, defaults, "transaction_fee")
    if txn_fee > 0 or "transaction_fee" in inputs:
        brokerage_lines.append(
            _line("transaction_fee", "Transaction / brokerage fee", txn_fee,
                  f"flat ${txn_fee:,.2f}", source=txn_src))

    # ── Title ───────────────────────────────────────────────
    ti_cfg = cfg.get("title_insurance") or {}
    pays = ti_cfg.get("paid_by_default", "seller")
    county_pays = (ti_cfg.get("paid_by_county_overrides") or {}).get(county or "")
    if county_pays:
        pays = county_pays

    if "owners_title_insurance" in inputs:
        ti_amount, ti_formula, ti_src = _d(inputs["owners_title_insurance"]), "agent override", "input"
    elif pays != "seller":
        ti_amount, ti_formula, ti_src = Decimal("0"), f"buyer pays in {county} county", "profile"
    else:
        ti_amount, ti_formula = title_insurance(price, ti_cfg)
        ti_src = "profile"

    settlement_fee, settle_src = _pick(inputs, defaults, "settlement_fee")
    lien_search, lien_src = _pick(inputs, defaults, "municipal_lien_search")
    title_search, ts_src = _pick(inputs, defaults, "title_search")

    title_lines = [
        _line("settlement_fee", "Settlement / closing fee", settlement_fee,
              f"flat ${settlement_fee:,.2f}", source=settle_src),
        _line("owners_title_insurance", "Owner's title insurance", ti_amount,
              ti_formula, source=ti_src),
        _line("municipal_lien_search", "Municipal lien search", lien_search,
              f"flat ${lien_search:,.2f}", source=lien_src),
        _line("title_search", "Abstract / title search", title_search,
              f"flat ${title_search:,.2f}", source=ts_src),
    ]

    # ── Government ──────────────────────────────────────────
    if "doc_stamps" in inputs:
        stamps, stamps_formula, stamps_src = _d(inputs["doc_stamps"]), "agent override", "input"
    else:
        stamps, stamps_formula = doc_stamps(price, cfg.get("doc_stamps"), county, property_type)
        stamps_src = "profile"

    recording, rec_src = _pick(inputs, defaults, "deed_recording")
    release, rel_src = _pick(inputs, defaults, "release_of_mortgage")

    gov_lines = [
        _line("doc_stamps", "Documentary stamps on the deed", stamps, stamps_formula, source=stamps_src),
        _line("deed_recording", "Deed recording", recording, f"flat ${recording:,.2f}", source=rec_src),
        _line("release_of_mortgage", "Release of mortgage", release, f"flat ${release:,.2f}", source=rel_src),
    ]

    # ── Other, all agent-entered ────────────────────────────
    other_specs = [
        ("termite_inspection", "Termite inspection (VA)"),
        ("lender_required_repairs", "Lender-required repairs"),
        ("home_warranty", "Home warranty"),
        ("estoppel_fee", "HOA / condo estoppel fee"),
        ("seller_paid_closing_costs", "Seller-paid buyer closing costs"),
        ("repairs_credit", "Repair credit to buyer"),
        ("other_costs", "Other"),
    ]
    other_lines = []
    for key, label in other_specs:
        amount, src = _pick(inputs, defaults, key)
        if amount != 0 or key in inputs:
            other_lines.append(_line(key, label, amount, f"${amount:,.2f}", source=src))

    closing_costs = sum((_d(l["amount"]) for l in
                         brokerage_lines + title_lines + gov_lines + other_lines), Decimal("0"))

    # ── Reductions: payoffs + prorated taxes ────────────────
    payoff_lines = []
    for i, m in enumerate(mortgage_payoffs or []):
        amount = _d(m.get("estimated_payoff"))
        if amount == 0:
            continue
        lender = m.get("lender_name") or f"Mortgage {i + 1}"
        pos = (m.get("position") or "").replace("_", " ").title()
        payoff_lines.append(
            _line(f"payoff_{i}", f"Payoff - {lender}" + (f" ({pos})" if pos else ""),
                  amount, f"lender-quoted payoff ${amount:,.2f}", source="input"))
    if "mortgage_payoff" in inputs:
        amount = _d(inputs["mortgage_payoff"])
        payoff_lines.append(_line("mortgage_payoff", "Mortgage principal payoff",
                                  amount, f"${amount:,.2f}", source="input"))

    annual_taxes = _d(inputs.get("annual_property_taxes", "0"))
    if "prorated_taxes" in inputs:
        taxes, taxes_formula, taxes_src = _d(inputs["prorated_taxes"]), "agent override", "input"
    else:
        taxes, taxes_formula = prorated_taxes(annual_taxes, closing, cfg.get("tax_proration"))
        taxes_src = "computed"

    reduction_lines = payoff_lines + [
        _line("prorated_taxes", "Estimated pro-rated property taxes", taxes,
              taxes_formula, source=taxes_src)
    ]
    reductions = sum((_d(l["amount"]) for l in reduction_lines), Decimal("0"))

    # ── Credits ─────────────────────────────────────────────
    # Workbook defect (a): these were subtracted despite being labelled "Additions".
    credits = _d(inputs.get("misc_credits", "0"))
    credits_are_deductions = bool(inputs.get("misc_credits_are_deductions"))
    if credits and not credits_are_deductions:
        corrections.append(
            "Miscellaneous credits are ADDED to proceeds. The original workbook "
            "subtracted them (=F9-F33-F37-F39) despite labelling them 'Additions'."
        )
    signed_credits = -credits if credits_are_deductions else credits

    proceeds = price - closing_costs - reductions + signed_credits

    # ── Post-closing escrow refund (shown separately, as in the workbook) ──
    refund_pct = _d((cfg.get("tax_proration") or {}).get("escrow_refund_estimate_pct", "0"))
    escrow_refund = taxes * refund_pct if refund_pct else Decimal("0")
    amount_realized = proceeds + escrow_refund

    if price > 0:
        net_pct = (proceeds / price * Decimal("100")).quantize(Decimal("0.01"))
    else:
        net_pct = Decimal("0")

    return {
        "sale_price": float(money(price)),
        "sections": [
            {"key": "brokerage",  "label": "Real estate brokerage costs", "lines": brokerage_lines,
             "subtotal": float(money(sum((_d(l["amount"]) for l in brokerage_lines), Decimal("0"))))},
            {"key": "title",      "label": "Title costs (estimated)", "lines": title_lines,
             "subtotal": float(money(sum((_d(l["amount"]) for l in title_lines), Decimal("0"))))},
            {"key": "government", "label": "Government closing costs", "lines": gov_lines,
             "subtotal": float(money(sum((_d(l["amount"]) for l in gov_lines), Decimal("0"))))},
            {"key": "other",      "label": "Other costs (if applicable)", "lines": other_lines,
             "subtotal": float(money(sum((_d(l["amount"]) for l in other_lines), Decimal("0"))))},
            {"key": "reductions", "label": "Reductions and prorations", "lines": reduction_lines,
             "subtotal": float(money(reductions))},
        ],
        "totals": {
            "total_closing_costs": float(money(closing_costs)),
            "total_reductions": float(money(reductions)),
            "misc_credits": float(money(signed_credits)),
            "proceeds_to_seller": float(money(proceeds)),
            "escrow_refund_post_closing": float(money(escrow_refund)),
            "amount_realized": float(money(amount_realized)),
            "net_pct_of_price": float(net_pct),
        },
        "formulas": {
            "total_closing_costs": "sum of brokerage + title + government + other",
            "proceeds_to_seller": "sale price - closing costs - reductions + credits",
            "amount_realized": "proceeds + estimated post-closing escrow refund",
        },
        # Callers MUST check this before rendering a PDF, emailing, or printing.
        # True means the numbers came from a template or from an unconfirmed profile.
        "blocking": bool(blockers),
        "blockers": blockers,
        "meta": {
            "county": county,
            "property_type": property_type,
            "closing_date": closing.isoformat() if closing else None,
            "title_paid_by": pays,
            "corrections_applied": corrections,
            "fee_profile_name": meta.get("name"),
            "fee_profile_confirmed_at": meta.get("confirmed_at"),
            "rates_provided_by": "agent",
            "disclaimer": ("All amounts are estimates based on closing costs entered by the "
                           "listing agent and information provided by third parties. They are "
                           "not a guarantee of final figures."),
        },
    }


def assert_sendable(result: dict) -> None:
    """
    Guard for any seller-facing path - PDF, email, print, share link.

    Raises ValueError when the net sheet was computed from a template or from rates
    nobody confirmed. Call this at the boundary rather than trusting the caller to
    read `blocking`; a wrong net sheet is worse than no net sheet.
    """
    if result.get("blocking"):
        raise ValueError(
            "This net sheet cannot be sent to a seller yet: "
            + " ".join(result.get("blockers") or ["fee profile not confirmed"])
        )
