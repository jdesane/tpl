"""
Seller net sheet PDF.

This is the deliverable. Everything else in the Listing Dashboard exists so that this
document is correct, and it is the artifact a seller actually uses to decide whether
to accept an offer.

THREE RULES

1. THE AGENT'S BRAND, NOT OURS.
   A seller should see their agent's name on this, not the name of the software.
   Agents pay for tools that make THEM look good; a vendor logo on a client document
   is the fastest way to make the tool feel cheap. RETechbox branding stays on the app
   and on agent-facing surfaces only.

2. IT REFUSES TO RENDER UNCONFIRMED NUMBERS.
   Calls net_sheet.assert_sendable() before drawing a single line. If the agent has
   not confirmed their closing costs, no PDF exists to hand anyone. Enforced here as
   well as at the API because this is the last gate before a seller sees a number.

3. ASCII ONLY.
   The Helvetica that ships with reportlab cannot render en/em dashes, the delta
   glyph, or checkmarks. They come out as black boxes on the seller's copy. Every
   string passes through _ascii() on the way in.

Side-by-side is the point of the layout. The workbook had "Option 1 / Option 2" and
"Current List Price / Offer" columns because the conversation an agent actually has is
comparative: what do I net here versus there. Up to three scenarios per page.
"""
import io
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import net_sheet as _ns

# Matches the palette used by the coaching intake PDFs.
INK = "#1a1a2e"
ACCENT = "#6c63ff"
MUTED = "#6b7280"
LIGHT = "#f5f5fa"
BORDER = "#e5e7eb"
POSITIVE = "#0f766e"
WARN = "#b45309"

MAX_SCENARIOS = 3


_ASCII_MAP = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", " ": " ",
    "−": "-", "×": "x", "✓": "*", "Δ": "vs ",
}


def _ascii(value) -> str:
    """
    Bundled Helvetica has no glyphs for smart quotes, dashes, or symbols - they render
    as black boxes on a document a client sees. Normalize, then drop anything left.
    """
    if value is None:
        return ""
    text = str(value)
    for bad, good in _ASCII_MAP.items():
        text = text.replace(bad, good)
    return re.sub(r"[^\x20-\x7E]", "", text)


def _usd(amount, blank_zero: bool = False) -> str:
    if amount is None:
        return ""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return ""
    if blank_zero and abs(value) < 0.005:
        return ""
    return f"({abs(value):,.2f})" if value < 0 else f"{value:,.2f}"


def _ordered_line_keys(scenarios: List[dict], section_key: str) -> List[tuple]:
    """
    Union of line keys across scenarios for one section, preserving first-seen order.

    Scenarios legitimately differ - one offer carries an estoppel fee, another does not -
    so the rows are the union, and a scenario missing a line simply shows blank rather
    than being silently dropped or misaligned against the wrong label.
    """
    seen: Dict[str, str] = {}
    for sc in scenarios:
        for section in (sc.get("sections") or []):
            if section.get("key") != section_key:
                continue
            for line in (section.get("lines") or []):
                seen.setdefault(line["key"], line.get("label") or line["key"])
    return list(seen.items())


def _amount_for(scenario: dict, section_key: str, line_key: str):
    for section in (scenario.get("sections") or []):
        if section.get("key") != section_key:
            continue
        for line in (section.get("lines") or []):
            if line["key"] == line_key:
                return line.get("amount")
    return None


def build_net_sheet_pdf(scenarios: List[dict], *,
                        branding: Optional[dict] = None,
                        listing: Optional[dict] = None,
                        sellers: Optional[List[dict]] = None,
                        show_formulas: bool = False,
                        prepared_on: Optional[str] = None) -> bytes:
    """
    scenarios  [{label, computed}] - up to MAX_SCENARIOS, rendered as columns
    branding   the AGENT's identity: {agent_name, brokerage, phone, email, license}
    show_formulas  agent's working copy; never enable for the seller's copy

    Raises ValueError when any scenario was computed from a template or from rates the
    agent has not confirmed.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                    TableStyle, KeepTogether)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    if not scenarios:
        raise ValueError("No scenarios to render")
    scenarios = scenarios[:MAX_SCENARIOS]

    # Rule 2: the last gate before a seller sees a number.
    for sc in scenarios:
        _ns.assert_sendable(sc.get("computed") or {})

    computed = [sc["computed"] for sc in scenarios]
    labels = [_ascii(sc.get("label") or f"Option {i+1}") for i, sc in enumerate(scenarios)]
    n = len(scenarios)

    brand = branding or {}
    listing = listing or {}
    sellers = sellers or []

    INKC, ACC = colors.HexColor(INK), colors.HexColor(ACCENT)
    MUT, LIT = colors.HexColor(MUTED), colors.HexColor(LIGHT)
    BRD, POS = colors.HexColor(BORDER), colors.HexColor(POSITIVE)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.55 * inch, rightMargin=0.55 * inch,
        topMargin=0.55 * inch, bottomMargin=0.7 * inch,
        title=_ascii("Seller's Estimated Net Proceeds"),
        author=_ascii(brand.get("agent_name") or ""),
    )

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                        fontSize=19, textColor=INKC, spaceAfter=2, leading=22)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                        fontSize=11, textColor=ACC, spaceBefore=12, spaceAfter=4)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica",
                          fontSize=9.5, textColor=INKC, leading=13)
    sub = ParagraphStyle("sub", parent=ss["BodyText"], fontName="Helvetica",
                         fontSize=8.5, textColor=MUT, leading=11)
    brandline = ParagraphStyle("brand", parent=ss["BodyText"], fontName="Helvetica-Bold",
                               fontSize=12, textColor=INKC, leading=15, spaceAfter=0)

    story: List[Any] = []

    # ── Header: the AGENT's identity (Rule 1) ───────────────
    agent_bits = [b for b in [brand.get("brokerage"), brand.get("phone"), brand.get("email")] if b]
    if brand.get("license"):
        agent_bits.append(f"License {brand['license']}")
    story.append(Paragraph(_ascii(brand.get("agent_name") or "Listing Agent"), brandline))
    if agent_bits:
        story.append(Paragraph(_ascii("  |  ".join(agent_bits)), sub))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Seller's Estimated Net Proceeds", h1))

    addr = ", ".join(_ascii(x) for x in [
        listing.get("address_line1"), listing.get("city"),
        f"{listing.get('state') or ''} {listing.get('zip') or ''}".strip()] if x)
    seller_names = ", ".join(
        _ascii(" ".join(filter(None, [s.get("first_name"), s.get("last_name")])))
        for s in sellers) or "-"
    prepared = prepared_on or datetime.now(timezone.utc).strftime("%B %d, %Y")

    meta_rows = [
        ["Prepared for:", seller_names],
        ["Property:", addr or "-"],
        ["Prepared on:", _ascii(prepared)],
    ]
    closing_dates = {c.get("meta", {}).get("closing_date") for c in computed}
    closing_dates.discard(None)
    if len(closing_dates) == 1:
        raw_close = list(closing_dates)[0]
        try:
            pretty = datetime.fromisoformat(str(raw_close)[:10]).strftime("%B %d, %Y")
        except (ValueError, TypeError):
            pretty = raw_close
        meta_rows.append(["Estimated closing:", _ascii(pretty)])

    meta = Table(meta_rows, colWidths=[1.3 * inch, 5.9 * inch])
    meta.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
        ("FONT", (1, 0), (1, -1), "Helvetica", 9),
        ("TEXTCOLOR", (0, 0), (0, -1), MUT),
        ("TEXTCOLOR", (1, 0), (1, -1), INKC),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(meta)
    story.append(Spacer(1, 14))

    # ── Column geometry ─────────────────────────────────────
    label_w = 7.4 * inch - (n * 1.25 * inch)
    col_w = [label_w] + [1.25 * inch] * n

    def money_row(label, values, blank_zero=True):
        return [_ascii(label)] + [_usd(v, blank_zero) for v in values]

    rows: List[List[str]] = []
    styles: List[tuple] = []

    def add_header():
        rows.append([""] + labels)
        r = len(rows) - 1
        styles.extend([
            ("BACKGROUND", (0, r), (-1, r), INKC),
            ("TEXTCOLOR", (0, r), (-1, r), colors.white),
            ("FONT", (0, r), (-1, r), "Helvetica-Bold", 9),
        ])

    def add_section(title):
        rows.append([_ascii(title)] + [""] * n)
        r = len(rows) - 1
        styles.extend([
            ("BACKGROUND", (0, r), (-1, r), LIT),
            ("FONT", (0, r), (-1, r), "Helvetica-Bold", 8.5),
            ("TEXTCOLOR", (0, r), (-1, r), ACC),
        ])

    def add_total(label, values, emphasize=False):
        rows.append(money_row(label, values, blank_zero=False))
        r = len(rows) - 1
        styles.extend([
            ("FONT", (0, r), (-1, r), "Helvetica-Bold", 10 if emphasize else 9),
            ("LINEABOVE", (0, r), (-1, r), 0.75, INKC),
        ])
        if emphasize:
            styles.extend([
                ("BACKGROUND", (0, r), (-1, r), colors.HexColor("#eef2ff")),
                ("TEXTCOLOR", (0, r), (-1, r), POS),
                ("TOPPADDING", (0, r), (-1, r), 6),
                ("BOTTOMPADDING", (0, r), (-1, r), 6),
            ])

    add_header()
    rows.append(money_row("Sale price", [c.get("sale_price") for c in computed], blank_zero=False))
    styles.append(("FONT", (0, len(rows) - 1), (-1, len(rows) - 1), "Helvetica-Bold", 9.5))

    COST_SECTIONS = [
        ("brokerage", "Real estate brokerage costs"),
        ("title", "Title costs (estimated)"),
        ("government", "Government closing costs"),
        ("other", "Other costs (if applicable)"),
    ]
    for key, title in COST_SECTIONS:
        line_keys = _ordered_line_keys(computed, key)
        if not line_keys:
            continue
        add_section(title)
        for line_key, line_label in line_keys:
            values = [_amount_for(c, key, line_key) for c in computed]
            if all(v in (None, 0) for v in values):
                continue
            rows.append(money_row(line_label, values))

    add_total("TOTAL CLOSING COSTS",
              [c["totals"]["total_closing_costs"] for c in computed])

    red_keys = _ordered_line_keys(computed, "reductions")
    if red_keys:
        add_section("Reductions and prorations")
        for line_key, line_label in red_keys:
            values = [_amount_for(c, "reductions", line_key) for c in computed]
            if all(v in (None, 0) for v in values):
                continue
            rows.append(money_row(line_label, values))
        add_total("TOTAL REDUCTIONS", [c["totals"]["total_reductions"] for c in computed])

    if any(c["totals"].get("misc_credits") for c in computed):
        rows.append(money_row("Miscellaneous credits",
                              [c["totals"].get("misc_credits") for c in computed]))

    add_total("ESTIMATED PROCEEDS TO SELLER",
              [c["totals"]["proceeds_to_seller"] for c in computed], emphasize=True)

    # The number a seller actually asks for. A comparison that makes someone do
    # subtraction in their head has not finished the job.
    if n > 1:
        base = computed[0]["totals"]["proceeds_to_seller"]
        deltas = [None] + [c["totals"]["proceeds_to_seller"] - base for c in computed[1:]]
        rows.append([_ascii(f"Difference vs {labels[0]}")] +
                    ["" if d is None else _usd(d, blank_zero=False) for d in deltas])
        r = len(rows) - 1
        styles.append(("FONT", (0, r), (-1, r), "Helvetica-Bold", 8.5))
        for i, d in enumerate(deltas):
            if d is None:
                continue
            styles.append(("TEXTCOLOR", (i + 1, r), (i + 1, r),
                           POS if d >= 0 else colors.HexColor(WARN)))

    if any(c["totals"].get("escrow_refund_post_closing") for c in computed):
        rows.append(money_row("Estimated escrow refund after closing",
                              [c["totals"].get("escrow_refund_post_closing") for c in computed]))
        add_total("TOTAL AMOUNT REALIZED",
                  [c["totals"]["amount_realized"] for c in computed])

    table = Table(rows, colWidths=col_w, repeatRows=1)
    styles.extend([
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
        ("TEXTCOLOR", (0, 1), (-1, -1), INKC),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -2), 0.25, BRD),
        ("BOX", (0, 0), (-1, -1), 0.75, BRD),
    ])
    table.setStyle(TableStyle(styles))
    story.append(table)

    # ── Agent's working copy only ───────────────────────────
    if show_formulas:
        story.append(Paragraph("How each line was calculated", h2))
        first = computed[0]
        for section in (first.get("sections") or []):
            for line in (section.get("lines") or []):
                if line.get("amount"):
                    story.append(Paragraph(
                        f"<b>{_ascii(line.get('label'))}</b>: {_ascii(line.get('formula'))}", sub))

    # ── Disclaimer + signatures ─────────────────────────────
    story.append(Spacer(1, 12))
    disclaimer = (computed[0].get("meta") or {}).get("disclaimer") or ""
    story.append(Paragraph(_ascii(disclaimer), sub))

    corrections = (computed[0].get("meta") or {}).get("corrections_applied") or []
    if corrections and show_formulas:
        for c in corrections:
            story.append(Paragraph(_ascii("Note: " + c), sub))

    # Compact on purpose. An earlier version used a taller block wrapped in
    # KeepTogether, which pushed the signatures onto a nearly empty second page -
    # orphaned signature lines look careless on a document a client signs.
    story.append(Spacer(1, 16))
    sig = Table(
        [["", ""], ["Seller", "Date"], ["", ""], ["Seller", "Date"]],
        colWidths=[4.2 * inch, 2.2 * inch], rowHeights=[20, 11, 20, 11])
    sig.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (0, 0), 0.75, INKC),
        ("LINEBELOW", (1, 0), (1, 0), 0.75, INKC),
        ("LINEBELOW", (0, 2), (0, 2), 0.75, INKC),
        ("LINEBELOW", (1, 2), (1, 2), 0.75, INKC),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), MUT),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(sig))

    # ── Footer: agent, page number, confirmation provenance ──
    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUT)
        left = _ascii(brand.get("agent_name") or "")
        if brand.get("brokerage"):
            left += _ascii(f"  |  {brand['brokerage']}")
        canvas.drawString(0.55 * inch, 0.42 * inch, left)
        canvas.drawRightString(letter[0] - 0.55 * inch, 0.42 * inch,
                               f"Page {canvas.getPageNumber()}")
        confirmed = (computed[0].get("meta") or {}).get("fee_profile_confirmed_at")
        if confirmed:
            canvas.drawCentredString(
                letter[0] / 2, 0.42 * inch,
                _ascii(f"Closing costs confirmed {str(confirmed)[:10]}"))
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
