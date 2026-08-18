"""
Net sheet engine tests.

Two jobs:
  1. Prove parity with Joe's workbook wherever the workbook was RIGHT.
  2. Prove the four documented defects are actually corrected.

Run: <venv>/bin/python test_net_sheet.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from decimal import Decimal
from net_sheet import compute_net_sheet, title_insurance, doc_stamps, prorated_taxes, _d

# Mirrors the FL profile seeded in 2026-08-18-listing-dashboard-foundation.sql
FL = {
    "title_insurance": {
        "basis": "sale_price",
        "tiers": [
            {"up_to": 100000,   "rate_per_1000": 5.75},
            {"up_to": 1000000,  "rate_per_1000": 5.00},
            {"up_to": 5000000,  "rate_per_1000": 2.50},
            {"up_to": 10000000, "rate_per_1000": 2.25},
            {"up_to": None,     "rate_per_1000": 2.00},
        ],
        "minimum": 100.00,
        "paid_by_default": "seller",
        "paid_by_county_overrides": {"Miami-Dade": "buyer", "Broward": "buyer"},
    },
    "doc_stamps": {
        "rate_per_100": 0.70,
        "rounding": "up_to_next_100",
        "paid_by_default": "seller",
        "county_overrides": {
            "Miami-Dade": {"rate_per_100": 0.60, "surtax_per_100": 0.45,
                           "surtax_applies_to": "non_single_family"},
        },
    },
    "tax_proration": {"day_count": 365, "start": "jan_1",
                      "seller_pays_through": "day_before_closing",
                      "escrow_refund_estimate_pct": 0.75},
    "defaults": {
        "settlement_fee": 525.00, "municipal_lien_search": 85.00,
        "title_search": 100.00, "deed_recording": 50.00,
        "release_of_mortgage": 100.00, "estoppel_fee": 0.00,
    },
}

P = F = 0
def check(label, got, want, tol=0.01):
    global P, F
    ok = abs(float(got) - float(want)) <= tol
    P, F = P + (1 if ok else 0), F + (0 if ok else 1)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:52} got {got:>14,.2f}  want {want:>14,.2f}")

def check_bool(label, got, want=True):
    global P, F
    ok = (got == want)
    P, F = P + (1 if ok else 0), F + (0 if ok else 1)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:52} {got}")

def lines_of(res):
    return {l["key"]: l for s in res["sections"] for l in s["lines"]}


print("\n=== 1. PARITY with the workbook at $500,000 ===")
print("    Workbook: comm 4.5%=22,500 | settle 525 | title 575+2,000=2,575")
print("              lien 85 | search 100 | recording 50 | stamps 3,500")
r = compute_net_sheet(500_000, FL, {"commission_pct": "0.045"}, county="Palm Beach",
                      property_type="single_family")
L = lines_of(r)
check("commission 4.5%",            L["commission"]["amount"],               22_500.00)
check("settlement fee",             L["settlement_fee"]["amount"],              525.00)
check("owner's title insurance",    L["owners_title_insurance"]["amount"],    2_575.00)
check("municipal lien search",      L["municipal_lien_search"]["amount"],        85.00)
check("abstract / title search",    L["title_search"]["amount"],                100.00)
check("deed recording",             L["deed_recording"]["amount"],               50.00)
check("doc stamps @ 0.70/100",      L["doc_stamps"]["amount"],                3_500.00)
# 22,500 + 525 + 2,575 + 85 + 100 + 50 + 3,500 + release 100 = 29,435
check("total closing costs",        r["totals"]["total_closing_costs"],      29_435.00)
check("proceeds to seller",         r["totals"]["proceeds_to_seller"],      470_565.00)


print("\n=== 2. DEFECT (b): sub-$100k no longer overcharged ===")
print("    Workbook charged a flat $575 on the first 100k regardless of price.")
ti, formula = title_insurance(Decimal("80000"), FL["title_insurance"])
check("title on $80k = 80,000/1000 x 5.75", ti, 460.00)
check_bool("...not the workbook's flat 575", abs(float(ti) - 575.00) > 1)


print("\n=== 3. DEFECT (c): tiers above $1M ===")
print("    Workbook had only two tiers, correct to $1M and wrong above it.")
# 100k@5.75=575 | 900k@5.00=4,500 | 1M@2.50=2,500  => 7,575
ti, _ = title_insurance(Decimal("2000000"), FL["title_insurance"])
check("title on $2M (3 bands)", ti, 7_575.00)
# workbook's 2-tier math would have been 575 + (2M-100k)*5/1000 = 10,075
check_bool("...lower than the 2-tier result (10,075)", float(ti) < 10_075)
# 100k@5.75 + 900k@5.00 + 4M@2.50 + 5M@2.25 + 2M@2.00 = 575+4500+10000+11250+4000
ti, _ = title_insurance(Decimal("12000000"), FL["title_insurance"])
check("title on $12M (all 5 bands)", ti, 30_325.00)


print("\n=== 4. DEFECT (d): doc stamps round up per $100 ===")
st, _ = doc_stamps(Decimal("450050"), FL["doc_stamps"], "Palm Beach", "single_family")
check("$450,050 -> ceil to 4,501 hundreds x .70", st, 3_150.70)
check_bool("...higher than price*0.007 (3,150.35)", float(st) > 3_150.35)
st, _ = doc_stamps(Decimal("450000"), FL["doc_stamps"], "Palm Beach", "single_family")
check("round price matches price*0.007", st, 3_150.00)


print("\n=== 5. DEFECT (a): misc credits ADD to proceeds ===")
base = compute_net_sheet(400_000, FL, {"commission_pct": "0.05"})
with_credit = compute_net_sheet(400_000, FL, {"commission_pct": "0.05", "misc_credits": "5000"})
check("proceeds rise by the credit",
      with_credit["totals"]["proceeds_to_seller"] - base["totals"]["proceeds_to_seller"], 5_000.00)
check_bool("correction is disclosed to the agent",
           any("subtracted" in c for c in with_credit["meta"]["corrections_applied"]))
legacy = compute_net_sheet(400_000, FL, {"commission_pct": "0.05", "misc_credits": "5000",
                                         "misc_credits_are_deductions": True})
check("legacy workbook behaviour still reachable",
      base["totals"]["proceeds_to_seller"] - legacy["totals"]["proceeds_to_seller"], 5_000.00)


print("\n=== 6. County rules (the portability payoff) ===")
mia = compute_net_sheet(600_000, FL, {"commission_pct": "0.05"},
                        county="Miami-Dade", property_type="single_family")
Lm = lines_of(mia)
check("Miami-Dade: buyer pays owner's title", Lm["owners_title_insurance"]["amount"], 0.00)
check_bool("...and the line explains why",
           "buyer pays" in Lm["owners_title_insurance"]["formula"])
# single family -> surtax does NOT apply: 6,000 hundreds x 0.60
check("Miami-Dade stamps, single family", Lm["doc_stamps"]["amount"], 3_600.00)
mia_condo = compute_net_sheet(600_000, FL, {"commission_pct": "0.05"},
                              county="Miami-Dade", property_type="condo")
# non single family -> 6,000 x (0.60 + 0.45)
check("Miami-Dade stamps, condo (+surtax)",
      lines_of(mia_condo)["doc_stamps"]["amount"], 6_300.00)
pb = compute_net_sheet(600_000, FL, {"commission_pct": "0.05"}, county="Palm Beach")
check("Palm Beach: seller pays title", lines_of(pb)["owners_title_insurance"]["amount"], 3_075.00)


print("\n=== 7. Tax proration ===")
from datetime import date
tax, formula = prorated_taxes(Decimal("3650"), date(2026, 7, 1), FL["tax_proration"])
# Jan 1 -> Jul 1 = 181 days; 3650/365 = 10/day
check("$3,650/yr, closing Jul 1 = 181 days x $10", tax, 1_810.00)
check_bool("formula is human-auditable", "days" in formula and "Jan 1" in formula)


print("\n=== 8. Payoffs, escrow refund, and the full stack ===")
full = compute_net_sheet(
    750_000, FL,
    {"commission_pct": "0.055", "transaction_fee": "395",
     "annual_property_taxes": "9125", "home_warranty": "600", "estoppel_fee": "350"},
    county="Palm Beach", property_type="single_family",
    closing_date="2026-09-15",
    mortgage_payoffs=[{"lender_name": "Chase", "position": "first", "estimated_payoff": "282000"},
                      {"lender_name": "Citi HELOC", "position": "heloc", "estimated_payoff": "45000"}],
)
Lf = lines_of(full)
check("commission 5.5% of 750k",     Lf["commission"]["amount"],            41_250.00)
check("transaction fee override",    Lf["transaction_fee"]["amount"],          395.00)
check("title 575 + 650k@5.00",       Lf["owners_title_insurance"]["amount"],  3_825.00)
check("both payoffs present",        len([k for k in Lf if k.startswith("payoff_")]), 2)
check("payoff total in reductions",
      Lf["payoff_0"]["amount"] + Lf["payoff_1"]["amount"],                  327_000.00)
# Jan 1 -> Sep 15 2026 = 257 days; 9125/365 = 25/day -> 6,425
check("prorated taxes",              Lf["prorated_taxes"]["amount"],          6_425.00)
check("escrow refund = 75% of taxes",
      full["totals"]["escrow_refund_post_closing"],                           4_818.75)
check("amount realized = proceeds + refund",
      full["totals"]["amount_realized"],
      full["totals"]["proceeds_to_seller"] + 4_818.75)
check_bool("net % of price reported", 0 < full["totals"]["net_pct_of_price"] < 100)


print("\n=== 9. Every line is auditable and attributed ===")
all_lines = [l for s in full["sections"] for l in s["lines"]]
check_bool("every line carries a formula", all(l.get("formula") for l in all_lines))
check_bool("every line declares its source",
           all(l["source"] in ("profile", "input", "computed") for l in all_lines))
check_bool("agent override attributed to input", Lf["transaction_fee"]["source"] == "input")
check_bool("profile default attributed to profile", Lf["settlement_fee"]["source"] == "profile")
check_bool("disclaimer present", "estimates" in full["meta"]["disclaimer"])


print("\n=== 10. Edge cases ===")
zero = compute_net_sheet(0, FL, {"commission_pct": "0.05"})
check_bool("zero price does not divide by zero", zero["totals"]["net_pct_of_price"] == 0)
empty = compute_net_sheet(300_000, {}, {"commission_pct": "0.05"})
check("empty profile still returns commission",
      lines_of(empty)["commission"]["amount"], 15_000.00)
check_bool("empty profile flags missing title config",
           "no title tiers" in lines_of(empty)["owners_title_insurance"]["formula"])
no_close = compute_net_sheet(300_000, FL, {"commission_pct": "0.05",
                                           "annual_property_taxes": "3000"})
check("no closing date -> no proration", lines_of(no_close)["prorated_taxes"]["amount"], 0.00)

print(f"\n{'='*78}\n{P} passed, {F} failed\n{'='*78}")
sys.exit(1 if F else 0)
