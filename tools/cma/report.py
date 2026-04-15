"""
CMA Report Generator.

Produces a clean HTML report that can be printed to PDF from the browser.
Designed for seller presentations — professional, data-driven, persuasive.
"""

from datetime import datetime
from models import CMAReport, Comp, BuyerReaction


def generate_html_report(report: CMAReport) -> str:
    """Generate a full HTML CMA report."""
    s = report.subject
    p = report.patterns

    comps_html = ""
    for i, comp in enumerate(report.comps, 1):
        comps_html += _comp_section(comp, i)

    active_html = ""
    if report.active_competition:
        rows = ""
        for a in report.active_competition:
            rows += f"""
            <tr>
                <td>{a.address}</td>
                <td>${a.list_price:,.0f}</td>
                <td>{a.dom}</td>
                <td>{a.beds}/{a.baths}</td>
                <td>{a.sqft:,}</td>
                <td>${a.price_per_sqft:,.2f}</td>
                <td>{a.price_changes}</td>
            </tr>"""
        active_html = f"""
        <div class="section">
            <h2>Active Competition</h2>
            <table>
                <tr>
                    <th>Address</th><th>List Price</th><th>DOM</th>
                    <th>Beds/Baths</th><th>Sqft</th><th>$/Sqft</th><th>Price Changes</th>
                </tr>
                {rows}
            </table>
        </div>"""

    pending_html = ""
    if report.pending_insights:
        rows = ""
        for pi in report.pending_insights:
            rows += f"""
            <tr>
                <td>{pi.address}</td>
                <td>${pi.list_price:,.0f}</td>
                <td>{pi.dom_before_contract}</td>
                <td>{pi.price_changes_before_contract}</td>
                <td>${pi.price_per_sqft:,.2f}</td>
                <td>{pi.notes}</td>
            </tr>"""
        pending_html = f"""
        <div class="section">
            <h2>Pending / Under Contract Insights</h2>
            <table>
                <tr>
                    <th>Address</th><th>List Price</th><th>DOM to Contract</th>
                    <th>Price Changes</th><th>$/Sqft</th><th>Notes</th>
                </tr>
                {rows}
            </table>
        </div>"""

    pattern_notes_html = ""
    for note in p.pattern_notes:
        pattern_notes_html += f"<li>{note}</li>"

    strategy_notes_html = ""
    for note in report.strategy_notes:
        strategy_notes_html += f"<li>{note}</li>"

    price_display = ""
    if report.recommended_list_price:
        price_display = f"""
        <div class="price-recommendation">
            <div class="price-label">Recommended List Price</div>
            <div class="price-value">${report.recommended_list_price:,.0f}</div>
            <div class="price-range">
                Range: ${report.price_range_low:,.0f} &ndash; ${report.price_range_high:,.0f}
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CMA — {s.address}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        color: #1a1a2e; background: #f8f9fa; line-height: 1.5;
    }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 24px; }}

    /* Header */
    .header {{
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        color: white; padding: 40px; border-radius: 12px; margin-bottom: 24px;
    }}
    .header h1 {{ font-size: 28px; margin-bottom: 4px; }}
    .header .subtitle {{ opacity: 0.8; font-size: 14px; }}
    .header .agent {{ margin-top: 16px; font-size: 13px; opacity: 0.7; }}

    /* Subject property summary */
    .subject-summary {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 12px; margin-bottom: 24px;
    }}
    .stat-card {{
        background: white; border-radius: 8px; padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center;
    }}
    .stat-card .label {{ font-size: 11px; text-transform: uppercase; color: #666; }}
    .stat-card .value {{ font-size: 22px; font-weight: 700; color: #1a1a2e; }}

    /* Sections */
    .section {{
        background: white; border-radius: 8px; padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px;
    }}
    .section h2 {{
        font-size: 18px; margin-bottom: 16px; padding-bottom: 8px;
        border-bottom: 2px solid #e8e8e8;
    }}

    /* Comp cards */
    .comp-card {{
        border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px;
        margin-bottom: 16px;
    }}
    .comp-card h3 {{ font-size: 16px; margin-bottom: 12px; color: #1a1a2e; }}
    .comp-details {{
        display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 8px; margin-bottom: 16px; font-size: 13px;
    }}
    .comp-details .item {{ }}
    .comp-details .item .label {{ color: #888; font-size: 11px; text-transform: uppercase; }}
    .comp-details .item .val {{ font-weight: 600; }}

    /* Price timeline */
    .timeline {{ padding: 12px 0; }}
    .timeline-event {{
        display: flex; align-items: flex-start; margin-bottom: 10px;
        padding-left: 20px; border-left: 3px solid #e0e0e0;
        position: relative;
    }}
    .timeline-event::before {{
        content: ''; width: 10px; height: 10px; border-radius: 50%;
        background: #666; position: absolute; left: -7px; top: 4px;
    }}
    .timeline-event.rejected::before {{ background: #e74c3c; }}
    .timeline-event.accepted::before {{ background: #27ae60; }}
    .timeline-event.sold::before {{ background: #2980b9; }}
    .timeline-event .date {{ min-width: 90px; font-size: 12px; color: #888; }}
    .timeline-event .detail {{ font-size: 13px; }}
    .timeline-event .price {{ font-weight: 700; }}

    /* Adjustments table */
    table {{
        width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px;
    }}
    th {{ text-align: left; padding: 8px 10px; background: #f0f0f0; font-weight: 600; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #eee; }}
    .positive {{ color: #27ae60; }}
    .negative {{ color: #e74c3c; }}

    /* Price recommendation */
    .price-recommendation {{
        text-align: center; padding: 32px; background: linear-gradient(135deg, #1a1a2e, #16213e);
        color: white; border-radius: 12px; margin: 24px 0;
    }}
    .price-label {{ font-size: 14px; text-transform: uppercase; opacity: 0.8; }}
    .price-value {{ font-size: 42px; font-weight: 800; margin: 8px 0; }}
    .price-range {{ font-size: 14px; opacity: 0.7; }}

    /* Insights */
    .insight-box {{
        background: #f0f7ff; border-left: 4px solid #2980b9;
        padding: 16px; border-radius: 0 8px 8px 0; margin: 12px 0;
    }}
    .insight-box.warning {{
        background: #fef9e7; border-left-color: #f39c12;
    }}
    .insight-box.success {{
        background: #eafaf1; border-left-color: #27ae60;
    }}
    ul {{ padding-left: 20px; }}
    li {{ margin-bottom: 6px; font-size: 14px; }}

    .demand-badge {{
        display: inline-block; padding: 4px 12px; border-radius: 20px;
        font-size: 12px; font-weight: 700; text-transform: uppercase;
    }}
    .demand-strong {{ background: #eafaf1; color: #27ae60; }}
    .demand-moderate {{ background: #fef9e7; color: #f39c12; }}
    .demand-weak {{ background: #fdedec; color: #e74c3c; }}

    @media print {{
        body {{ background: white; }}
        .container {{ padding: 0; }}
        .section, .comp-card {{ break-inside: avoid; }}
        .no-print {{ display: none; }}
    }}
</style>
</head>
<body>
<div class="container">

    <!-- Header -->
    <div class="header">
        <h1>Comparative Market Analysis</h1>
        <div class="subtitle">{s.address}, {s.city}, {s.state} {s.zip_code}</div>
        <div class="agent">
            Prepared by {report.agent_name} &middot; {report.brokerage}
            &middot; {report.created_at.strftime('%B %d, %Y')}
        </div>
    </div>

    <!-- Subject Property Summary -->
    <div class="subject-summary">
        <div class="stat-card">
            <div class="label">Beds / Baths</div>
            <div class="value">{s.beds} / {s.baths}</div>
        </div>
        <div class="stat-card">
            <div class="label">Sqft</div>
            <div class="value">{s.sqft:,}</div>
        </div>
        <div class="stat-card">
            <div class="label">Year Built</div>
            <div class="value">{s.year_built}</div>
        </div>
        <div class="stat-card">
            <div class="label">Lot Sqft</div>
            <div class="value">{s.lot_sqft:,}</div>
        </div>
        <div class="stat-card">
            <div class="label">Pool</div>
            <div class="value">{'Yes' if s.pool else 'No'}</div>
        </div>
        <div class="stat-card">
            <div class="label">Garage</div>
            <div class="value">{s.garage_spaces}</div>
        </div>
    </div>

    {price_display}

    <!-- Market Pattern Analysis -->
    <div class="section">
        <h2>Market Pattern Analysis</h2>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:16px;">
            <div class="stat-card">
                <div class="label">Avg Sale Price</div>
                <div class="value">${p.avg_sale_price:,.0f}</div>
            </div>
            <div class="stat-card">
                <div class="label">Avg DOM</div>
                <div class="value">{p.avg_dom:.0f}</div>
            </div>
            <div class="stat-card">
                <div class="label">Avg $/Sqft</div>
                <div class="value">${p.avg_price_per_sqft:,.0f}</div>
            </div>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; margin-bottom:16px;">
            <div class="stat-card">
                <div class="label">Avg Reductions</div>
                <div class="value">{p.avg_reductions:.1f}</div>
            </div>
            <div class="stat-card">
                <div class="label">Demand</div>
                <div class="value">
                    <span class="demand-badge demand-{p.demand_strength.value}">{p.demand_strength.value}</span>
                </div>
            </div>
            <div class="stat-card">
                <div class="label">Acceptance Zone</div>
                <div class="value" style="font-size:16px;">${p.acceptance_zone_low:,.0f}–${p.acceptance_zone_high:,.0f}</div>
            </div>
        </div>

        <div class="insight-box">
            <strong>Key Insight:</strong> {p.pricing_insight}
        </div>

        {'<h3 style="margin-top:20px;">Pattern Details</h3><ul>' + pattern_notes_html + '</ul>' if pattern_notes_html else ''}
    </div>

    <!-- Comparable Sales with Pricing History -->
    <div class="section">
        <h2>Comparable Sales &amp; Pricing History</h2>
        {comps_html}
    </div>

    {active_html}

    {pending_html}

    <!-- Pricing Strategy -->
    <div class="section">
        <h2>Pricing Strategy</h2>
        <ul>
            {strategy_notes_html}
        </ul>
    </div>

    <div style="text-align:center; padding:24px; font-size:12px; color:#999;">
        Prepared by {report.agent_name} &middot; {report.brokerage}<br>
        This analysis is based on MLS data and is intended for informational purposes.
        Market conditions may change. All data should be independently verified.
    </div>

</div>
</body>
</html>"""


def _comp_section(comp: Comp, index: int) -> str:
    """Generate HTML for a single comp card with pricing history timeline."""
    h = comp.pricing_history
    if not h:
        return ""

    # Property details grid
    details = f"""
    <div class="comp-details">
        <div class="item"><div class="label">MLS#</div><div class="val">{comp.mls_number}</div></div>
        <div class="item"><div class="label">Beds/Baths</div><div class="val">{comp.beds}/{comp.baths}</div></div>
        <div class="item"><div class="label">Sqft</div><div class="val">{comp.sqft:,}</div></div>
        <div class="item"><div class="label">Year Built</div><div class="val">{comp.year_built}</div></div>
        <div class="item"><div class="label">Lot</div><div class="val">{comp.lot_sqft:,}</div></div>
        <div class="item"><div class="label">Pool</div><div class="val">{'Yes' if comp.pool else 'No'}</div></div>
        <div class="item"><div class="label">Garage</div><div class="val">{comp.garage_spaces}</div></div>
        <div class="item"><div class="label">$/Sqft</div><div class="val">${comp.price_per_sqft:,.2f}</div></div>
    </div>"""

    # Price timeline
    timeline = '<div class="timeline">'

    # Original listing
    rejected_class = "rejected" if h.num_reductions > 0 else ""
    timeline += f"""
    <div class="timeline-event {rejected_class}">
        <div class="date">{h.list_date.strftime('%m/%d/%Y')}</div>
        <div class="detail">Listed at <span class="price">${h.original_list_price:,.0f}</span></div>
    </div>"""

    # Each price change
    for pc in h.price_changes:
        direction = "reduced" if pc.change_amount < 0 else "increased"
        css_class = "rejected" if pc.change_amount < 0 else ""
        timeline += f"""
    <div class="timeline-event {css_class}">
        <div class="date">{pc.date.strftime('%m/%d/%Y')}</div>
        <div class="detail">
            Price {direction} to <span class="price">${pc.new_price:,.0f}</span>
            ({pc.change_pct:+.1f}%) &mdash; {pc.days_at_previous_price} days at previous price
        </div>
    </div>"""

    # Under contract
    if h.contract_date:
        timeline += f"""
    <div class="timeline-event accepted">
        <div class="date">{h.contract_date.strftime('%m/%d/%Y')}</div>
        <div class="detail">
            Under contract at <span class="price">${h.market_acceptance_price:,.0f}</span>
            {f'&mdash; {h.days_from_last_change_to_contract} days after last change' if h.days_from_last_change_to_contract is not None else ''}
        </div>
    </div>"""

    # Sold
    if h.close_date:
        timeline += f"""
    <div class="timeline-event sold">
        <div class="date">{h.close_date.strftime('%m/%d/%Y')}</div>
        <div class="detail">
            Sold at <span class="price">${h.sale_price:,.0f}</span>
            ({h.sale_to_original_ratio:.1f}% of original list)
        </div>
    </div>"""

    timeline += "</div>"

    # Key insight for this comp
    insight = ""
    if h.num_reductions > 0:
        rejected_str = ", ".join(f"${p:,.0f}" for p in h.market_rejected_prices)
        reaction_label = ""
        if h.buyer_reaction == BuyerReaction.FAST:
            reaction_label = "buyers moved quickly"
        elif h.buyer_reaction == BuyerReaction.MODERATE:
            reaction_label = "moderate buyer interest"
        elif h.buyer_reaction == BuyerReaction.SLOW:
            reaction_label = "slow buyer response even at final price"

        insight = f"""
        <div class="insight-box warning">
            <strong>Key Insight:</strong>
            Market rejected {rejected_str}.
            Accepted ~${h.market_acceptance_price:,.0f}
            ({reaction_label}, DOM: {h.total_dom}).
        </div>"""
    else:
        reaction_note = ""
        if h.buyer_reaction == BuyerReaction.FAST:
            reaction_note = "Strong demand — priced at or below market."
        insight = f"""
        <div class="insight-box success">
            <strong>Key Insight:</strong>
            No price reductions needed. Sold at ${h.sale_price:,.0f}
            ({h.sale_to_list_ratio:.1f}% of list) in {h.total_dom} days.
            {reaction_note}
        </div>"""

    # Adjustments table
    adj_html = ""
    if comp.adjustments:
        adj_rows = ""
        for field, amount in comp.adjustments.items():
            css = "positive" if amount > 0 else "negative" if amount < 0 else ""
            adj_rows += f"""
            <tr>
                <td>{field.replace('_', ' ').title()}</td>
                <td class="{css}">${amount:+,.0f}</td>
            </tr>"""
        adj_html = f"""
        <h4 style="margin-top:12px;">Adjustments</h4>
        <table>
            <tr><th>Feature</th><th>Adjustment</th></tr>
            {adj_rows}
            <tr style="font-weight:700; border-top:2px solid #333;">
                <td>Adjusted Sale Price</td>
                <td>${comp.adjusted_price:,.0f}</td>
            </tr>
        </table>"""

    return f"""
    <div class="comp-card">
        <h3>Comp {index}: {comp.address}</h3>
        {details}
        <h4>Pricing History</h4>
        {timeline}
        {insight}
        {adj_html}
    </div>"""
