"""
TPL Agent Tools — CMA Builder
Local Streamlit app for building Comparative Market Analyses
with pricing history analysis.

Run: streamlit run app.py
"""

import sys
import json
import streamlit as st
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from models import (
    SubjectProperty, Comp, PricingHistory, PriceChange,
    ActiveListing, PendingInsight, PropertyType, CMAReport,
)
from csv_import import parse_flexmls_csv, rows_to_comps, rows_to_active_listings
from analysis import (
    analyze_comp, analyze_market_patterns, build_price_changes,
    generate_pricing_strategy, calculate_adjustments,
)
from cma_engine import run_cma
from report import generate_html_report
from config import Config

st.set_page_config(page_title="CMA Builder", page_icon="🏠", layout="wide")


def _parse_safe(val) -> float:
    """Safely parse a number."""
    try:
        s = str(val).replace("$", "").replace(",", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return 0


# ── Session state init ──────────────────────────────────────────────
def _init_state():
    defaults = {
        "subject": SubjectProperty(),
        "comps": [],
        "active_listings": [],
        "pending_insights": [],
        "report": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


# ── Sidebar ─────────────────────────────────────────────────────────
with st.sidebar:
    st.title("CMA Builder")
    st.caption("TPL Agent Tools")
    st.divider()

    step = st.radio("Step", [
        "1. Subject Property",
        "2. Add Comps",
        "3. Pricing Analysis",
        "4. Active Competition",
        "5. Report",
    ])

    st.divider()
    st.caption(f"Agent: {Config.AGENT_NAME}")
    st.caption(f"Brokerage: {Config.BROKERAGE}")
    api_status = "Connected" if Config.has_spark_credentials() else "Manual Entry"
    st.caption(f"MLS API: {api_status}")

    st.divider()
    if st.button("Reset CMA", type="secondary"):
        for k in ["subject", "comps", "active_listings", "pending_insights", "report"]:
            del st.session_state[k]
        _init_state()
        st.rerun()


# ═══════════════════════════════════════════════════════════════════
# STEP 1: Subject Property
# ═══════════════════════════════════════════════════════════════════
if step.startswith("1"):
    st.header("Subject Property")
    st.caption("Enter the property you're pricing.")

    s = st.session_state.subject

    col1, col2 = st.columns(2)
    with col1:
        address = st.text_input("Address", value=s.address)
        city = st.text_input("City", value=s.city)
        zip_code = st.text_input("ZIP", value=s.zip_code)
        subdivision = st.text_input("Subdivision", value=s.subdivision)
        prop_type = st.selectbox("Property Type", [t.value for t in PropertyType],
                                 index=0)

    with col2:
        beds = st.number_input("Beds", min_value=0, max_value=20, value=s.beds)
        baths = st.number_input("Baths", min_value=0.0, max_value=20.0,
                                value=float(s.baths), step=0.5)
        sqft = st.number_input("Sqft", min_value=0, max_value=50000, value=s.sqft)
        lot_sqft = st.number_input("Lot Sqft", min_value=0, value=s.lot_sqft)
        year_built = st.number_input("Year Built", min_value=1900, max_value=2027,
                                     value=s.year_built or 2000)

    col3, col4, col5 = st.columns(3)
    with col3:
        garage = st.number_input("Garage Spaces", min_value=0, max_value=10,
                                 value=s.garage_spaces)
    with col4:
        pool = st.checkbox("Pool", value=s.pool)
    with col5:
        waterfront = st.checkbox("Waterfront", value=s.waterfront)

    notes = st.text_area("Notes", value=s.notes)

    if st.button("Save Subject Property", type="primary"):
        st.session_state.subject = SubjectProperty(
            address=address, city=city, state="FL", zip_code=zip_code,
            subdivision=subdivision, property_type=PropertyType(prop_type),
            beds=beds, baths=baths, sqft=sqft, lot_sqft=lot_sqft,
            year_built=year_built, garage_spaces=garage, pool=pool,
            waterfront=waterfront, notes=notes,
        )
        st.success(f"Saved: {address}")


# ═══════════════════════════════════════════════════════════════════
# STEP 2: Add Comps
# ═══════════════════════════════════════════════════════════════════
elif step.startswith("2"):
    st.header("Comparable Sales")
    st.caption("Add sold comps with their full pricing history.")

    # Show existing comps
    if st.session_state.comps:
        st.subheader(f"Current Comps ({len(st.session_state.comps)})")
        for i, c in enumerate(st.session_state.comps):
            h = c.pricing_history
            sale = f"${h.sale_price:,.0f}" if h else "N/A"
            with st.expander(f"Comp {i+1}: {c.address} — Sold {sale}"):
                if h:
                    st.write(f"**Original List:** ${h.original_list_price:,.0f} | "
                             f"**Sale:** ${h.sale_price:,.0f} | "
                             f"**DOM:** {h.total_dom} | "
                             f"**Reductions:** {len(h.price_changes)}")
                if st.button(f"Remove Comp {i+1}", key=f"rm_{i}"):
                    st.session_state.comps.pop(i)
                    st.rerun()

    st.divider()

    # ── CSV Import from Flexmls ──
    st.subheader("Import from Flexmls Export")
    st.caption("In Flexmls: run your comp search → export to CSV/Excel → upload here.")

    uploaded = st.file_uploader(
        "Upload Flexmls CSV or Excel export",
        type=["csv", "xlsx", "xls"],
        key="csv_upload",
    )
    if uploaded is not None:
        raw = uploaded.read()
        rows = parse_flexmls_csv(raw)
        if rows:
            imported = rows_to_comps(rows)
            st.success(f"Parsed {len(rows)} rows → {len(imported)} sold comps found.")

            if imported:
                # Preview
                for ic in imported:
                    h = ic.pricing_history
                    price_str = f"${h.sale_price:,.0f}" if h else "N/A"
                    orig_str = f"${h.original_list_price:,.0f}" if h else "N/A"
                    st.markdown(
                        f"- **{ic.address}** — {ic.beds}bd/{ic.baths}ba, "
                        f"{ic.sqft:,} sqft — Listed {orig_str}, Sold {price_str}"
                    )

                st.caption(
                    "Note: CSV imports include property details and list/sale prices. "
                    "Price change history must be added manually per comp in the form below "
                    "(Flexmls doesn't export price change history in CSV)."
                )

                if st.button("Add All Imported Comps", type="primary"):
                    st.session_state.comps.extend(imported)
                    st.success(f"Added {len(imported)} comps!")
                    st.rerun()
        else:
            st.error("Could not parse the file. Check that it's a Flexmls export.")

    st.divider()
    st.subheader("Add Comp Manually")

    with st.form("add_comp", clear_on_submit=True):
        st.markdown("**Property Details**")
        ac1, ac2 = st.columns(2)
        with ac1:
            c_mls = st.text_input("MLS #")
            c_address = st.text_input("Address")
            c_city = st.text_input("City")
            c_zip = st.text_input("ZIP")
        with ac2:
            c_beds = st.number_input("Beds", 0, 20, 3)
            c_baths = st.number_input("Baths", 0.0, 20.0, 2.0, step=0.5)
            c_sqft = st.number_input("Sqft", 0, 50000, 1500)
            c_year = st.number_input("Year Built", 1900, 2027, 2000)

        ac3, ac4, ac5 = st.columns(3)
        with ac3:
            c_lot = st.number_input("Lot Sqft", 0, value=5000)
        with ac4:
            c_garage = st.number_input("Garage", 0, 10, 2)
        with ac5:
            c_pool = st.checkbox("Pool")

        st.markdown("---")
        st.markdown("**Pricing History** (this is where the edge is)")

        p1, p2 = st.columns(2)
        with p1:
            c_orig_price = st.number_input("Original List Price", 0, value=0)
            c_sale_price = st.number_input("Sale Price", 0, value=0)
            c_dom = st.number_input("Total DOM", 0, value=0)
        with p2:
            c_list_date = st.date_input("List Date", value=date.today() - timedelta(days=90))
            c_contract_date = st.date_input("Contract Date", value=date.today() - timedelta(days=30))
            c_close_date = st.date_input("Close Date", value=date.today())

        st.markdown("**Price Changes** (enter each reduction/increase)")
        st.caption("Add up to 5 price changes. Leave price at 0 to skip.")

        changes_prices = []
        changes_dates = []
        pc_cols = st.columns(5)
        for j in range(5):
            with pc_cols[j]:
                p = st.number_input(f"Price {j+1}", 0, key=f"pc_p_{j}", value=0)
                d = st.date_input(f"Date {j+1}", key=f"pc_d_{j}",
                                  value=date.today() - timedelta(days=60 - j * 15))
                if p > 0:
                    changes_prices.append(p)
                    changes_dates.append(d)

        submitted = st.form_submit_button("Add Comp", type="primary")

        if submitted and c_address and c_sale_price > 0 and c_orig_price > 0:
            price_changes = build_price_changes(
                c_orig_price, c_list_date, changes_prices, changes_dates
            )

            pricing = PricingHistory(
                original_list_price=c_orig_price,
                final_list_price=changes_prices[-1] if changes_prices else c_orig_price,
                sale_price=c_sale_price,
                list_date=c_list_date,
                contract_date=c_contract_date,
                close_date=c_close_date,
                total_dom=c_dom,
                price_changes=price_changes,
            )

            comp = Comp(
                mls_number=c_mls, address=c_address, city=c_city,
                zip_code=c_zip, beds=c_beds, baths=c_baths, sqft=c_sqft,
                lot_sqft=c_lot, year_built=c_year, garage_spaces=c_garage,
                pool=c_pool, pricing_history=pricing,
            )
            st.session_state.comps.append(comp)
            st.success(f"Added: {c_address}")


# ═══════════════════════════════════════════════════════════════════
# STEP 3: Pricing History Analysis
# ═══════════════════════════════════════════════════════════════════
elif step.startswith("3"):
    st.header("Pricing History Analysis")

    if not st.session_state.comps:
        st.warning("Add comps first (Step 2).")
    else:
        analyzed = [analyze_comp(c.model_copy(deep=True)) for c in st.session_state.comps]
        patterns = analyze_market_patterns(st.session_state.comps)

        # Market summary
        st.subheader("Market Summary")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Avg Sale Price", f"${patterns.avg_sale_price:,.0f}")
        m2.metric("Avg DOM", f"{patterns.avg_dom:.0f}")
        m3.metric("Avg Reductions", f"{patterns.avg_reductions:.1f}")
        m4.metric("Demand", patterns.demand_strength.value.upper())

        a1, a2, a3 = st.columns(3)
        a1.metric("Avg $/Sqft", f"${patterns.avg_price_per_sqft:,.2f}")
        a2.metric("Acceptance Zone",
                   f"${patterns.acceptance_zone_low:,.0f}–${patterns.acceptance_zone_high:,.0f}")
        a3.metric("Avg Reaction Days", f"{patterns.avg_reaction_days:.0f}")

        # Pricing insight
        st.info(patterns.pricing_insight)

        # Pattern notes
        if patterns.pattern_notes:
            st.subheader("Pattern Details")
            for note in patterns.pattern_notes:
                st.markdown(f"- {note}")

        # Individual comp analysis
        st.divider()
        st.subheader("Individual Comp Breakdown")

        for i, comp in enumerate(analyzed):
            h = comp.pricing_history
            if not h:
                continue

            with st.expander(
                f"Comp {i+1}: {comp.address} — "
                f"${h.sale_price:,.0f} (DOM: {h.total_dom})",
                expanded=True,
            ):
                # Timeline
                st.markdown("**Pricing Timeline**")

                # Original list
                icon = "🔴" if h.num_reductions > 0 else "🟢"
                st.markdown(f"{icon} **{h.list_date}** — Listed at **${h.original_list_price:,.0f}**")

                # Price changes
                for pc in h.price_changes:
                    direction = "reduced" if pc.change_amount < 0 else "increased"
                    st.markdown(
                        f"🔴 **{pc.date}** — Price {direction} to **${pc.new_price:,.0f}** "
                        f"({pc.change_pct:+.1f}%) — {pc.days_at_previous_price} days at previous price"
                    )

                # Contract
                if h.contract_date:
                    st.markdown(
                        f"🟢 **{h.contract_date}** — Under contract "
                        f"({h.days_from_last_change_to_contract} days after last change)"
                    )

                # Sold
                if h.close_date:
                    st.markdown(
                        f"🔵 **{h.close_date}** — Sold at **${h.sale_price:,.0f}** "
                        f"({h.sale_to_original_ratio:.1f}% of original list)"
                    )

                # Key insight
                st.divider()
                if h.num_reductions > 0:
                    rejected = ", ".join(f"${p:,.0f}" for p in h.market_rejected_prices)
                    st.warning(
                        f"**Market rejected:** {rejected}\n\n"
                        f"**Market accepted:** ~${h.market_acceptance_price:,.0f} "
                        f"(buyer reaction: {h.buyer_reaction.value if h.buyer_reaction else 'N/A'})"
                    )
                else:
                    st.success(
                        f"No reductions needed. Sold at {h.sale_to_list_ratio:.1f}% of list "
                        f"in {h.total_dom} days."
                    )


# ═══════════════════════════════════════════════════════════════════
# STEP 4: Active Competition
# ═══════════════════════════════════════════════════════════════════
elif step.startswith("4"):
    st.header("Active Competition")
    st.caption("Current active listings competing with the subject property.")

    if st.session_state.active_listings:
        st.subheader(f"Active Listings ({len(st.session_state.active_listings)})")
        for i, a in enumerate(st.session_state.active_listings):
            with st.expander(f"{a.address} — ${a.list_price:,.0f} ({a.dom} DOM)"):
                st.write(f"{a.beds}bd / {a.baths}ba | {a.sqft:,} sqft | "
                         f"${a.price_per_sqft:,.2f}/sqft")
                if st.button(f"Remove", key=f"rm_active_{i}"):
                    st.session_state.active_listings.pop(i)
                    st.rerun()

    st.divider()

    # CSV import for active listings
    st.subheader("Import Active Listings from Flexmls")
    active_upload = st.file_uploader(
        "Upload Flexmls CSV/Excel (active listings search)",
        type=["csv", "xlsx", "xls"],
        key="csv_active_upload",
    )
    if active_upload is not None:
        raw = active_upload.read()
        rows = parse_flexmls_csv(raw)
        if rows:
            imported_active = rows_to_active_listings(rows)
            if not imported_active:
                imported_active = [
                    ActiveListing(
                        mls_number=str(r.get("mls_number", "")),
                        address=str(r.get("address", "")),
                        city=str(r.get("city", "")),
                        beds=int(_parse_safe(r.get("beds", 0))),
                        baths=float(_parse_safe(r.get("baths", 0))),
                        sqft=int(_parse_safe(r.get("sqft", 0))),
                        list_price=float(_parse_safe(r.get("list_price", 0))),
                        dom=int(_parse_safe(r.get("dom", 0))),
                    ) for r in rows if _parse_safe(r.get("list_price", 0)) > 0
                ]
            st.success(f"Found {len(imported_active)} active listings.")
            if imported_active and st.button("Add All Active Listings", type="primary"):
                st.session_state.active_listings.extend(imported_active)
                st.rerun()

    st.divider()
    with st.form("add_active", clear_on_submit=True):
        st.subheader("Add Active Listing")
        x1, x2 = st.columns(2)
        with x1:
            xa_addr = st.text_input("Address")
            xa_price = st.number_input("List Price", 0, value=0)
            xa_orig = st.number_input("Original List Price", 0, value=0)
            xa_dom = st.number_input("DOM", 0, value=0)
        with x2:
            xa_beds = st.number_input("Beds", 0, 20, 3)
            xa_baths = st.number_input("Baths", 0.0, 20.0, 2.0, step=0.5)
            xa_sqft = st.number_input("Sqft", 0, 50000, 1500)
            xa_changes = st.number_input("Price Changes", 0, value=0)

        if st.form_submit_button("Add Active Listing", type="primary"):
            if xa_addr and xa_price > 0:
                st.session_state.active_listings.append(ActiveListing(
                    address=xa_addr, list_price=xa_price,
                    original_list_price=xa_orig or xa_price,
                    dom=xa_dom, beds=xa_beds, baths=xa_baths,
                    sqft=xa_sqft, price_changes=xa_changes,
                ))
                st.success(f"Added: {xa_addr}")


# ═══════════════════════════════════════════════════════════════════
# STEP 5: Report
# ═══════════════════════════════════════════════════════════════════
elif step.startswith("5"):
    st.header("CMA Report")

    subj = st.session_state.subject
    comps = st.session_state.comps

    if not subj.address:
        st.warning("Enter a subject property first (Step 1).")
    elif not comps:
        st.warning("Add comps first (Step 2).")
    else:
        # Adjustment config
        with st.expander("Adjustment Values", expanded=False):
            st.caption("Customize per-unit adjustment values used in comp adjustments.")
            adj1, adj2, adj3 = st.columns(3)
            with adj1:
                bed_val = st.number_input("Per Bedroom ($)", value=10000)
                bath_val = st.number_input("Per Bathroom ($)", value=8000)
            with adj2:
                garage_val = st.number_input("Per Garage Space ($)", value=15000)
                pool_val = st.number_input("Pool ($)", value=20000)
            with adj3:
                age_val = st.number_input("Per Year Age Diff ($)", value=1500)

        if st.button("Generate CMA Report", type="primary"):
            report = run_cma(
                subject=subj,
                comps=comps,
                active=st.session_state.active_listings,
                pending=st.session_state.pending_insights,
                adjustment_overrides={
                    "bed_value": bed_val,
                    "bath_value": bath_val,
                    "garage_value": garage_val,
                    "pool_value": pool_val,
                    "age_value_per_year": age_val,
                },
            )
            st.session_state.report = report

        report = st.session_state.report
        if report:
            # Summary metrics
            st.subheader("Pricing Recommendation")
            r1, r2, r3 = st.columns(3)
            r1.metric("Recommended List Price",
                      f"${report.recommended_list_price:,.0f}" if report.recommended_list_price else "N/A")
            r2.metric("Range Low",
                      f"${report.price_range_low:,.0f}" if report.price_range_low else "N/A")
            r3.metric("Range High",
                      f"${report.price_range_high:,.0f}" if report.price_range_high else "N/A")

            # Strategy notes
            if report.strategy_notes:
                st.subheader("Strategy Notes")
                for note in report.strategy_notes:
                    st.markdown(f"- {note}")

            # Pattern insights
            if report.patterns.pricing_insight:
                st.info(report.patterns.pricing_insight)

            st.divider()

            # Generate HTML report
            html = generate_html_report(report)

            st.download_button(
                label="Download HTML Report",
                data=html,
                file_name=f"CMA_{report.subject.address.replace(' ', '_')}_{date.today()}.html",
                mime="text/html",
                type="primary",
            )

            # Preview
            with st.expander("Preview Report", expanded=False):
                st.components.v1.html(html, height=1200, scrolling=True)

            # Save as JSON
            report_json = report.model_dump_json(indent=2)
            st.download_button(
                label="Download JSON Data",
                data=report_json,
                file_name=f"CMA_{report.subject.address.replace(' ', '_')}_{date.today()}.json",
                mime="application/json",
            )
