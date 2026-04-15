"""
Flexmls Public Link Parser.

Parses HTML from Flexmls public links — handles both the comparison table
format (properties in columns, attributes in rows) and the full-report
text format.

Workflow:
1. User runs a wide search in Flexmls (sold properties in an area)
2. User selects all results → generates a public link
3. This module fetches that link and parses every property
4. Returns structured data ready for the CMA analysis engine
"""

import re
from datetime import date, datetime, timedelta
from typing import Any

import requests
from bs4 import BeautifulSoup

from models import (
    Comp, SubjectProperty, ActiveListing, PricingHistory, PriceChange,
    PropertyType,
)


# ── Field label mapping ───────────────────────────────────────────────
# Maps lowercase Flexmls table labels → our property dict keys.
FIELD_MAP = {
    # Prices
    "list price": "list_price",
    "listprice": "list_price",
    "original list price": "original_list_price",
    "orig list price": "original_list_price",
    "original lp": "original_list_price",
    "sold price": "sale_price",
    "close price": "sale_price",
    "selling price": "sale_price",
    "sold/close price": "sale_price",
    "price": "list_price",  # bottom-row "Price" usually = current list

    # Status
    "status": "status",
    "status date": "status_date",

    # DOM
    "days on market": "dom",
    "cumulative days on market": "cdom",
    "dom": "dom",
    "cdom": "cdom",
    "dom/cdom": "dom",

    # Beds / baths
    "bedrooms total": "beds",
    "beds total": "beds",
    "beds": "beds",
    "br": "beds",
    "bathrooms total": "baths",
    "baths total": "baths",
    "baths": "baths",
    "bathrooms full": "baths_full",
    "bathrooms half": "baths_half",

    # Sqft
    "building area main": "sqft",
    "bldg area main": "sqft",
    "living area": "sqft",
    "approx living area": "sqft",
    "approx sqft": "sqft",
    "sq ft": "sqft",
    "sqft": "sqft",
    "heated sqft": "sqft",
    "total area": "sqft",

    # Lot
    "lot size dimensions": "lot_dimensions",
    "lot size area": "lot_sqft",
    "lot size acres": "lot_acres",
    "lot size": "lot_sqft",
    "lot sqft": "lot_sqft",
    "lot acres": "lot_acres",

    # Property details
    "year built": "year_built",
    "yr built": "year_built",
    "garage spaces": "garage_spaces",
    "garage cap": "garage_spaces",
    "pool private yn": "pool_yn",
    "pool yn": "pool_yn",
    "pool": "pool_yn",
    "waterfront yn": "waterfront_yn",
    "waterfront": "waterfront_yn",
    "stories": "stories",
    "membership fee amount": "hoa_monthly",
    "hoa fee": "hoa_monthly",
    "hoa": "hoa_monthly",
    "direction faces": "direction",
    "subdivision name": "subdivision",
    "subdivision": "subdivision",
    "property sub type": "property_type_raw",
    "property type": "property_type_raw",
    "prop type": "property_type_raw",
    "sub type": "property_type_raw",
}


class FlexmlsParser:
    """Parse Flexmls public link reports into property models."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def fetch_and_parse(self, url: str) -> list[dict]:
        """Fetch a Flexmls public link and parse all properties."""
        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()
        return self.parse_html(resp.text)

    def parse_html(self, html: str) -> list[dict]:
        """Parse Flexmls HTML into property data dicts.
        Tries table-based parsing first, falls back to text-based."""
        soup = BeautifulSoup(html, "html.parser")

        # Primary: HTML table parsing (comparison format)
        properties = self._parse_comparison_tables(soup)
        if properties:
            return [p for p in properties if p.get("mls_number")]

        # Fallback: text-based parsing (full report format)
        text = soup.get_text(separator="\n")
        sections = self._split_into_properties(text)
        results = []
        for section in sections:
            prop = self._parse_property_section(section)
            if prop and prop.get("mls_number"):
                results.append(prop)
        return results

    # ══════════════════════════════════════════════════════════════════
    # TABLE-BASED PARSER (comparison format)
    # ══════════════════════════════════════════════════════════════════

    def _parse_comparison_tables(self, soup: BeautifulSoup) -> list[dict]:
        """Parse Flexmls comparison tables where columns = properties."""
        all_properties: list[dict] = []

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 3:
                continue

            # Step 1: find the MLS-number row
            mls_numbers = []
            mls_row_idx = -1
            for idx, row in enumerate(rows):
                cells = row.find_all(["td", "th"])
                candidates = []
                for cell in cells:
                    txt = cell.get_text(strip=True)
                    if re.match(r"^[A-Z]{0,2}\d{6,}$", txt):
                        candidates.append(txt)
                if candidates:
                    mls_numbers = candidates
                    mls_row_idx = idx
                    break

            if not mls_numbers:
                continue

            num_props = len(mls_numbers)
            prop_dicts: list[dict] = [{"mls_number": m} for m in mls_numbers]

            # Step 2: walk remaining rows
            for row in rows[mls_row_idx + 1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                label = cells[0].get_text(strip=True)
                label_lower = label.lower().strip()

                # Recognised data field?
                field_key = _match_field(label_lower)
                if field_key:
                    for j in range(num_props):
                        ci = j + 1
                        if ci < len(cells):
                            val = cells[ci].get_text(strip=True)
                            if val:
                                _set_field(prop_dicts[j], field_key, val)
                elif not label:
                    # Unlabelled row — might be address/photo
                    for j in range(num_props):
                        ci = j + 1
                        if ci < len(cells):
                            self._try_parse_address(
                                prop_dicts[j], cells[ci]
                            )

            all_properties.extend(prop_dicts)

        # Post-process: infer price changes, compute baths
        for p in all_properties:
            _postprocess(p)

        return all_properties

    @staticmethod
    def _try_parse_address(prop: dict, cell) -> None:
        """Try to extract an address from an unlabelled table cell."""
        if prop.get("address"):
            return
        text = cell.get_text(separator="\n", strip=True)
        if not text or len(text) < 5:
            return
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        if not lines:
            return
        # Address line: starts with digits
        for i, line in enumerate(lines):
            if re.match(r"\d{1,6}\s+\w", line):
                prop["address"] = line.rstrip(",.")
                # Next line might be "City FL ZIP"
                if i + 1 < len(lines):
                    m = re.match(
                        r"(.+?),?\s+FL\s*(\d{5})?",
                        lines[i + 1], re.I,
                    )
                    if m:
                        prop["city"] = m.group(1).strip().rstrip(",.")
                        if m.group(2):
                            prop["zip_code"] = m.group(2)
                return

    # ══════════════════════════════════════════════════════════════════
    # TEXT-BASED PARSER (full-report fallback)
    # ══════════════════════════════════════════════════════════════════

    def _split_into_properties(self, text: str) -> list[str]:
        """Split full report text into per-property sections."""
        for pattern in [
            r"(?=Residential\s+(?:Full\s+)?Report)",
            r"(?=MLS\s*#?\s*:?\s*[A-Z]{0,2}\d{5,})",
            r"(?=Listing\s+by\s+MLS)",
        ]:
            sections = re.split(pattern, text, flags=re.I)
            sections = [s.strip() for s in sections if s.strip()]
            if len(sections) > 1:
                return sections
        return [text]

    def _parse_property_section(self, text: str) -> dict:
        """Parse a single property section (text format)."""
        prop: dict[str, Any] = {}

        # MLS Number
        m = re.search(r"MLS\s*#?\s*:?\s*([A-Z]{0,2}\d{5,})", text, re.I)
        if m:
            prop["mls_number"] = m.group(1)

        # Status
        m = re.search(
            r"Status\s*:?\s*(Active|Closed|Pending|Sold|Expired|Withdrawn|Cancelled)",
            text, re.I,
        )
        if m:
            prop["status"] = m.group(1).strip()

        # Prices
        for label, key in [
            (r"List\s*Price", "list_price"),
            (r"(?:Original\s*L(?:ist\s*)?P(?:rice)?|Orig\.?\s*(?:List\s*)?Price)", "original_list_price"),
            (r"(?:Sold|Close|Selling)\s*Price", "sale_price"),
        ]:
            m = re.search(rf"{label}\s*:?\s*\$?([\d,]+)", text, re.I)
            if m:
                prop[key] = _clean_number(m.group(1))

        # Address
        for pat in [
            r"(?:^|\n)\s*(\d{1,6}\s+[A-Za-z0-9][\w\s.]{3,45}?(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Rd|Road|Ln|Lane|Way|Ct|Court|Cir|Circle|Ter|Terrace|Pl|Place|Trl|Trail)[\s.,]*(?:[NSEW])?)\s*[,.]?\s*([A-Za-z\s]+?)\s*,\s*FL\s*(\d{5})",
            r"(?:^|\n)\s*(\d{1,6}\s+[^,\n]{4,50}?)\s*,\s*([A-Za-z\s]+?)\s*,\s*FL\s*(\d{5})",
        ]:
            m = re.search(pat, text, re.I | re.MULTILINE)
            if m:
                prop["address"] = m.group(1).strip().rstrip(",.")
                prop["city"] = m.group(2).strip().rstrip(",.")
                prop["zip_code"] = m.group(3).strip()
                break

        # Beds / Baths
        m = re.search(r"(?:Beds?|Bedrooms?\s*(?:Total)?)\s*:?\s*(\d+)", text, re.I)
        if m:
            prop["beds"] = int(m.group(1))
        m = re.search(r"(?:Baths?\s*(?:Total)?|Bathrooms?\s*(?:Total)?)\s*:?\s*(\d+)", text, re.I)
        if m:
            prop["baths"] = float(m.group(1))
        m = re.search(r"(?:Full\s*Baths?|Baths?\s*Full)\s*:?\s*(\d+)", text, re.I)
        if m:
            prop["baths_full"] = int(m.group(1))
        m = re.search(r"(?:Half\s*Baths?|Baths?\s*Half)\s*:?\s*(\d+)", text, re.I)
        if m:
            prop["baths_half"] = int(m.group(1))

        # Square footage — expanded patterns
        for pat in [
            r"Building\s*Area\s*Main\s*:?\s*([\d,]+)",
            r"Bldg\.?\s*Area\s*(?:Main)?\s*:?\s*([\d,]+)",
            r"(?:Living\s*Area|Liv\s*Area)\s*:?\s*([\d,]+)",
            r"(?:Approx\.?\s*(?:Liv(?:ing)?\s*)?(?:Sq\.?\s*Ft|SqFt|SF))\s*:?\s*([\d,]+)",
            r"(?:Sq\.?\s*Ft|SqFt|Square\s*Feet)\s*:?\s*([\d,]+)",
            r"(?:Heated\s*Sqft)\s*:?\s*([\d,]+)",
        ]:
            m = re.search(pat, text, re.I)
            if m:
                val = _clean_number(m.group(1))
                if val > 100:
                    prop["sqft"] = int(val)
                    break

        # Lot size
        m = re.search(r"Lot\s*(?:Size\s*)?(?:Area|Sqft)\s*:?\s*([\d,]+)", text, re.I)
        if m:
            prop["lot_sqft"] = int(_clean_number(m.group(1)))
        m = re.search(r"Lot\s*(?:Size\s*)?Acres?\s*:?\s*([\d,.]+)", text, re.I)
        if m:
            acres = float(m.group(1).replace(",", ""))
            if "lot_sqft" not in prop or prop["lot_sqft"] == 0:
                prop["lot_sqft"] = int(acres * 43560)
            prop["lot_acres"] = acres

        # Year built
        m = re.search(r"(?:Year\s*Built|Yr\s*Built|Built)\s*:?\s*(\d{4})", text, re.I)
        if m:
            prop["year_built"] = int(m.group(1))

        # Garage
        m = re.search(r"(?:Garage\s*(?:Spaces?|Cap)?|Gar\s*Cap)\s*:?\s*(\d+)", text, re.I)
        if m:
            prop["garage_spaces"] = int(m.group(1))

        # Pool
        m = re.search(r"Pool\s*(?:Priv(?:ate)?|Y/?N)?\s*:?\s*(Yes|No|Private|Community|None)", text, re.I)
        if m:
            prop["pool"] = m.group(1).lower() in ("yes", "private", "community")

        # Waterfront
        m = re.search(r"(?:Waterfront|Water\s*Front)\s*(?:YN|Y/N)?\s*:?\s*(Yes|No)", text, re.I)
        if m:
            prop["waterfront"] = m.group(1).lower() == "yes"

        # DOM
        m = re.search(r"(?:DOMS?|DOM/?S|Days?\s*(?:on\s*)?(?:Market|MLS)|CDOM)\s*(?:/\s*DOMI?)?\s*:?\s*(\d+)", text, re.I)
        if m:
            prop["dom"] = int(m.group(1))

        # Dates
        m = re.search(r"(?:List(?:ing)?\s*Date|Date\s*Listed)\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
        if m:
            prop["list_date"] = _parse_date(m.group(1))
        m = re.search(r"(?:Close|Sold|Closing)\s*Date\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
        if m:
            prop["close_date"] = _parse_date(m.group(1))
        m = re.search(r"(?:Contract|Pending|Cntg)\s*Date\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
        if m:
            prop["contract_date"] = _parse_date(m.group(1))
        m = re.search(r"Status\s*Date\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
        if m:
            prop["status_date"] = m.group(1)

        # Subdivision
        m = re.search(r"(?:Subdiv(?:ision)?|Subdv)\s*(?:Name)?\s*:?\s*([A-Za-z0-9\s]+?)(?:\n|$)", text, re.I)
        if m:
            prop["subdivision"] = m.group(1).strip()

        # Property type
        m = re.search(r"(?:Sub\s*Type|Property\s*(?:Sub\s*)?Type|Prop\s*Type)\s*:?\s*([^\n]+)", text, re.I)
        if m:
            raw_type = m.group(1).strip()
            prop["property_type_raw"] = raw_type

        # Stories
        m = re.search(r"Stories?\s*:?\s*(\d+)", text, re.I)
        if m:
            prop["stories"] = int(m.group(1))

        # HOA
        m = re.search(r"(?:Membership\s*Fee\s*Amount|HOA\s*(?:Fee)?|Maint(?:enance)?\s*Fee)\s*:?\s*\$?([\d,]+)", text, re.I)
        if m:
            prop["hoa_monthly"] = _clean_number(m.group(1))

        # Price history (text-based events)
        prop["price_history"] = self._extract_price_history(text)

        # Post-process
        _postprocess(prop)

        return prop

    def _extract_price_history(self, text: str) -> list[dict]:
        """Extract date-based price history events from text."""
        events = []

        history_pattern = re.compile(
            r"(\d{1,2}/\d{1,2}/\d{2,4})\s+"
            r"(Listed|Price\s*Chang\w*|Reduced|Pending|Sold|Closed|Under\s*Contract|"
            r"Active|Back\s*on\s*Market|Withdrawn|Cancelled|Expired|New|"
            r"(?:Price\s*)?(?:Increase|Decrease|Reduction))\s*"
            r"(?:to\s*)?\$?([\d,]+)?",
            re.I,
        )
        for m in history_pattern.finditer(text):
            evt_date = _parse_date(m.group(1))
            if evt_date:
                events.append({
                    "date": evt_date,
                    "event": m.group(2).strip(),
                    "price": _clean_number(m.group(3)) if m.group(3) else 0,
                })

        if not events:
            status_pattern = re.compile(
                r"(\d{1,2}/\d{1,2}/\d{2,4})\s+\$?([\d,]+)\s+"
                r"(Active|Pending|Closed|Sold)", re.I,
            )
            for m in status_pattern.finditer(text):
                evt_date = _parse_date(m.group(1))
                if evt_date:
                    events.append({
                        "date": evt_date,
                        "event": m.group(3).strip(),
                        "price": _clean_number(m.group(2)),
                    })

        events.sort(key=lambda e: e.get("date", date.today()))
        return events


# ══════════════════════════════════════════════════════════════════════
# Cross-reference: merge data from a second link
# ══════════════════════════════════════════════════════════════════════

def cross_reference(
    primary: list[dict],
    secondary: list[dict],
) -> list[dict]:
    """Merge secondary property data into primary by MLS number.
    Secondary values fill in blanks but never overwrite existing data."""
    sec_map = {p["mls_number"]: p for p in secondary if p.get("mls_number")}
    for prop in primary:
        mls = prop.get("mls_number", "")
        if mls not in sec_map:
            continue
        sec = sec_map[mls]
        for key, val in sec.items():
            if key == "mls_number":
                continue
            # Fill blanks only
            existing = prop.get(key)
            if existing is None or existing == 0 or existing == "" or existing == []:
                prop[key] = val
    return primary


# ══════════════════════════════════════════════════════════════════════
# Public convenience functions
# ══════════════════════════════════════════════════════════════════════

def parse_flexmls_link(url: str) -> list[dict]:
    """Fetch + parse a Flexmls public link."""
    parser = FlexmlsParser()
    return parser.fetch_and_parse(url)


def parse_flexmls_html_file(file_content: str | bytes) -> list[dict]:
    """Parse saved Flexmls HTML file content."""
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8", errors="replace")
    parser = FlexmlsParser()
    return parser.parse_html(file_content)


def flexmls_to_comps(raw_properties: list[dict]) -> list[Comp]:
    """Convert parsed property dicts into Comp models."""
    comps = []
    for raw in raw_properties:
        status = (raw.get("status", "") or "").lower()

        sale_price = raw.get("sale_price", 0)
        list_price = raw.get("list_price", 0)
        orig_price = raw.get("original_list_price", 0) or list_price

        if "close" in status or "sold" in status:
            if not sale_price:
                continue
        else:
            sale_price = sale_price or list_price

        # Build PriceChange objects
        price_changes = _build_price_changes(raw, orig_price, list_price)

        # Baths
        baths = raw.get("baths", 0) or 0
        if baths == 0:
            baths = (raw.get("baths_full", 0) or 0) + (raw.get("baths_half", 0) or 0) * 0.5

        # Property type
        prop_type = PropertyType.SINGLE_FAMILY
        raw_type = raw.get("property_type", "single_family")
        try:
            prop_type = PropertyType(raw_type)
        except ValueError:
            pass

        comp = Comp(
            mls_number=raw.get("mls_number", ""),
            address=raw.get("address", ""),
            city=raw.get("city", ""),
            state="FL",
            zip_code=raw.get("zip_code", ""),
            subdivision=raw.get("subdivision", ""),
            property_type=prop_type,
            beds=raw.get("beds", 0) or 0,
            baths=baths,
            sqft=raw.get("sqft", 0) or 0,
            lot_sqft=raw.get("lot_sqft", 0) or 0,
            year_built=raw.get("year_built", 0) or 0,
            garage_spaces=raw.get("garage_spaces", 0) or 0,
            pool=raw.get("pool", False),
            waterfront=raw.get("waterfront", False),
            stories=raw.get("stories", 1) or 1,
        )

        list_date = raw.get("list_date") or date.today()
        close_date = raw.get("close_date")
        contract_date = raw.get("contract_date")
        dom = raw.get("dom", 0) or raw.get("cdom", 0) or 0

        if not list_date and close_date and dom:
            list_date = close_date - timedelta(days=dom)

        final_list = list_price
        if price_changes:
            final_list = price_changes[-1].new_price

        if sale_price > 0 or list_price > 0:
            comp.pricing_history = PricingHistory(
                original_list_price=orig_price or list_price,
                final_list_price=final_list or orig_price or list_price,
                sale_price=sale_price or list_price,
                list_date=list_date,
                contract_date=contract_date,
                close_date=close_date,
                total_dom=dom,
                price_changes=price_changes,
            )

        comps.append(comp)

    return comps


def flexmls_to_active(raw_properties: list[dict]) -> list[ActiveListing]:
    """Convert parsed property dicts into ActiveListing models."""
    listings = []
    for raw in raw_properties:
        status = (raw.get("status", "") or "").lower()
        if "active" not in status:
            continue

        baths = raw.get("baths", 0) or 0
        if baths == 0:
            baths = (raw.get("baths_full", 0) or 0) + (raw.get("baths_half", 0) or 0) * 0.5

        listings.append(ActiveListing(
            mls_number=raw.get("mls_number", ""),
            address=raw.get("address", ""),
            city=raw.get("city", ""),
            zip_code=raw.get("zip_code", ""),
            beds=raw.get("beds", 0) or 0,
            baths=baths,
            sqft=raw.get("sqft", 0) or 0,
            year_built=raw.get("year_built", 0) or 0,
            list_price=raw.get("list_price", 0) or 0,
            original_list_price=raw.get("original_list_price", 0) or raw.get("list_price", 0) or 0,
            dom=raw.get("dom", 0) or 0,
        ))

    return listings


# ══════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════

def _match_field(label: str) -> str | None:
    """Match a table label to a known field key."""
    label = label.strip().lower()
    if label in FIELD_MAP:
        return FIELD_MAP[label]
    # Fuzzy: check if any known key is contained in the label
    for key, val in FIELD_MAP.items():
        if key in label:
            return val
    return None


def _set_field(prop: dict, field_key: str, value_str: str) -> None:
    """Set a property dict field from a raw string value."""
    value_str = value_str.strip()
    if not value_str or value_str == "--" or value_str == "N/A":
        return

    # Price fields
    if field_key in (
        "list_price", "original_list_price", "sale_price", "hoa_monthly",
    ):
        num = _clean_number(value_str)
        if num > 0:
            prop[field_key] = num

    # Integer fields
    elif field_key in ("beds", "sqft", "lot_sqft", "dom", "cdom", "year_built", "garage_spaces", "stories"):
        num = _clean_number(value_str)
        if num > 0:
            prop[field_key] = int(num)

    # Float fields
    elif field_key in ("baths", "baths_full", "baths_half", "lot_acres"):
        num = _clean_number(value_str)
        if num > 0:
            prop[field_key] = float(num)

    # Boolean-ish fields
    elif field_key in ("pool_yn", "waterfront_yn"):
        yn = value_str.lower()
        actual_key = "pool" if "pool" in field_key else "waterfront"
        prop[actual_key] = yn in ("yes", "y", "true", "1", "private", "community")

    # String fields
    elif field_key in ("status", "status_date", "subdivision", "property_type_raw", "direction", "lot_dimensions"):
        prop[field_key] = value_str


def _postprocess(prop: dict) -> None:
    """Post-process a property dict: infer baths, price changes, property type."""
    # Compute baths from full + half
    if not prop.get("baths") and prop.get("baths_full"):
        prop["baths"] = (prop.get("baths_full", 0) or 0) + (prop.get("baths_half", 0) or 0) * 0.5

    # Infer property type from raw
    raw_type = (prop.get("property_type_raw", "") or "").lower()
    if "condo" in raw_type:
        prop["property_type"] = "condo"
    elif "town" in raw_type:
        prop["property_type"] = "townhouse"
    elif "villa" in raw_type:
        prop["property_type"] = "villa"
    elif "multi" in raw_type:
        prop["property_type"] = "multi_family"
    else:
        prop["property_type"] = "single_family"

    # Parse status_date into close_date / list_date if applicable
    status = (prop.get("status", "") or "").lower()
    sd = prop.get("status_date")
    if sd and not prop.get("close_date") and ("sold" in status or "close" in status):
        prop["close_date"] = _parse_date(sd)
    if sd and not prop.get("list_date") and "active" in status:
        prop["list_date"] = _parse_date(sd)

    # Infer price change from original vs current list price
    orig = prop.get("original_list_price", 0) or 0
    current = prop.get("list_price", 0) or 0
    if orig > 0 and current > 0 and orig != current:
        if "price_changes_inferred" not in prop:
            prop["price_changes_inferred"] = True
            prop.setdefault("price_history", [])
            # We don't have the exact date, but we know a change happened
            prop["price_history"].append({
                "date": None,
                "event": "Price Changed",
                "price": current,
                "previous_price": orig,
            })


def _build_price_changes(
    raw: dict, orig_price: float, list_price: float,
) -> list[PriceChange]:
    """Build PriceChange objects from raw history + inferred changes."""
    price_changes = []
    raw_history = raw.get("price_history", [])

    if raw_history:
        prev_price = orig_price
        prev_date = raw.get("list_date") or date.today()

        for evt in raw_history:
            evt_type = (evt.get("event", "") or "").lower()
            evt_price = evt.get("price", 0)
            evt_date = evt.get("date")

            if not evt_price:
                continue

            is_change = (
                "chang" in evt_type
                or "reduc" in evt_type
                or "decrease" in evt_type
                or "increase" in evt_type
            )
            if is_change and prev_price and evt_price != prev_price:
                pc = PriceChange(
                    date=evt_date or date.today(),
                    new_price=evt_price,
                    previous_price=prev_price,
                    days_at_previous_price=(
                        (evt_date - prev_date).days if evt_date and prev_date else 0
                    ),
                )
                price_changes.append(pc)
                prev_price = evt_price
                prev_date = evt_date

    # If no explicit history but prices differ, infer a change
    if not price_changes and orig_price > 0 and list_price > 0 and orig_price != list_price:
        list_date = raw.get("list_date") or date.today()
        dom = raw.get("dom", 0) or raw.get("cdom", 0) or 0
        # Estimate change happened halfway through DOM
        change_date = list_date + timedelta(days=max(dom // 2, 1)) if dom else list_date
        price_changes.append(PriceChange(
            date=change_date,
            new_price=list_price,
            previous_price=orig_price,
            days_at_previous_price=max(dom // 2, 1) if dom else 0,
        ))

    return price_changes


def _clean_number(val: str | None) -> float:
    if not val:
        return 0
    return float(str(val).replace(",", "").replace("$", "").strip() or 0)


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
