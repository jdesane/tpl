"""
Flexmls Public Link Parser.

Parses the HTML from Flexmls "Residential Full Report" public links
to extract all property data including price change history.

Workflow:
1. User runs a wide search in Flexmls (sold comps in an area)
2. User selects all results → generates a public link
3. This module fetches that link and parses every property
4. Returns structured data ready for the CMA analysis engine

The public link URL format:
https://www.flexmls.com/cgi-bin/mainmenu.cgi?cmd=url+other/run_public_link.html&public_link_tech_id=XXXXX&s=15&id=1&cid=1
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
        """
        Fetch a Flexmls public link and parse all properties.
        Returns a list of raw property dicts.
        """
        resp = requests.get(url, headers=self.HEADERS, timeout=30)
        resp.raise_for_status()
        return self.parse_html(resp.text)

    def parse_html(self, html: str) -> list[dict]:
        """
        Parse Flexmls report HTML into property data dicts.

        Handles the "Residential Full Report" format which includes:
        - Property header (MLS#, status, price, address)
        - Property details (beds, baths, sqft, lot, year, etc.)
        - Room details
        - Features
        - Listing history / price changes
        - Agent/broker info
        """
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator="\n")

        # Split into individual property sections
        # Each property starts with a header containing MLS # and address
        sections = self._split_into_properties(text)

        properties = []
        for section in sections:
            prop = self._parse_property_section(section)
            if prop and prop.get("mls_number"):
                properties.append(prop)

        return properties

    def _split_into_properties(self, text: str) -> list[str]:
        """Split the full report text into individual property sections."""
        # Flexmls reports separate properties with headers containing MLS #
        # Try splitting on "MLS #:" or "MLS#:" or "Listing by MLS" patterns
        # Also try "Residential Full Report" as separator

        # First try: split on "Residential Full Report" or similar report headers
        sections = re.split(
            r'(?=Residential\s+(?:Full\s+)?Report)',
            text,
            flags=re.IGNORECASE,
        )
        sections = [s.strip() for s in sections if s.strip()]

        if len(sections) > 1:
            return sections

        # Second try: split on MLS # pattern
        sections = re.split(
            r'(?=MLS\s*#?\s*:\s*[A-Z]?\d{5,})',
            text,
            flags=re.IGNORECASE,
        )
        sections = [s.strip() for s in sections if s.strip()]

        if len(sections) > 1:
            return sections

        # Third try: split on "Listing by" which appears between properties
        sections = re.split(
            r'(?=Listing\s+by\s+MLS)',
            text,
            flags=re.IGNORECASE,
        )

        if len(sections) <= 1:
            # If we can't split, treat the whole thing as one property
            return [text]

        return [s.strip() for s in sections if s.strip()]

    def _parse_property_section(self, text: str) -> dict:
        """Parse a single property section into a data dict."""
        prop: dict[str, Any] = {}

        # ── MLS Number ──
        m = re.search(r'MLS\s*#?\s*:?\s*([A-Z]?\d{5,})', text, re.I)
        if m:
            prop["mls_number"] = m.group(1)

        # ── Status ──
        m = re.search(r'Status\s*:?\s*(Active|Closed|Pending|Sold|Expired|Withdrawn|Cancelled)', text, re.I)
        if m:
            prop["status"] = m.group(1).strip()

        # ── Prices ──
        # List Price (current)
        m = re.search(r'List\s*Price\s*:?\s*\$?([\d,]+)', text, re.I)
        if m:
            prop["list_price"] = _clean_number(m.group(1))

        # Original List Price
        m = re.search(r'(?:Original\s*L(?:ist\s*)?P(?:rice)?|Orig\.?\s*(?:List\s*)?Price)\s*:?\s*\$?([\d,]+)', text, re.I)
        if m:
            prop["original_list_price"] = _clean_number(m.group(1))

        # Sold/Close Price
        m = re.search(r'(?:Sold|Close|Selling|Sold)\s*Price\s*:?\s*\$?([\d,]+)', text, re.I)
        if m:
            prop["sale_price"] = _clean_number(m.group(1))
        # Also try "SP:" (common Flexmls abbreviation)
        if "sale_price" not in prop:
            m = re.search(r'\bSP\s*:?\s*\$?([\d,]+)', text)
            if m:
                prop["sale_price"] = _clean_number(m.group(1))

        # ── Address ──
        # Flexmls format: typically "1234 Street Name, City, FL ZIP" on its own line
        # Use multiline to anchor and avoid matching digits from prices
        for addr_pattern in [
            # "14863 22nd Rd N, Loxahatchee Groves, FL 33470"
            r'(?:^|\n)\s*(\d{1,6}\s+[A-Za-z0-9][\w\s.]{3,45}?(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Rd|Road|Ln|Lane|Way|Ct|Court|Cir|Circle|Ter|Terrace|Pl|Place|Trl|Trail)[\s.,]*(?:[NSEW])?)\s*[,.]?\s*([A-Za-z\s]+?)\s*,\s*FL\s*(\d{5})',
            # broader: "1234 Something, City, FL 33470"
            r'(?:^|\n)\s*(\d{1,6}\s+[^,\n]{4,50}?)\s*,\s*([A-Za-z\s]+?)\s*,\s*FL\s*(\d{5})',
        ]:
            m = re.search(addr_pattern, text, re.I | re.MULTILINE)
            if m:
                prop["address"] = m.group(1).strip().rstrip(",.")
                prop["city"] = m.group(2).strip().rstrip(",.")
                prop["zip_code"] = m.group(3).strip()
                break

        # ── Beds / Baths ──
        m = re.search(r'(?:Beds?|Bedrooms?\s*(?:Total)?)\s*:?\s*(\d+)', text, re.I)
        if m:
            prop["beds"] = int(m.group(1))

        m = re.search(r'(?:Baths?\s*(?:Total)?|Bathrooms?\s*(?:Total)?)\s*:?\s*(\d+)', text, re.I)
        if m:
            prop["baths"] = float(m.group(1))

        # Full and half baths
        m = re.search(r'(?:Full\s*Baths?|Baths?\s*Full)\s*:?\s*(\d+)', text, re.I)
        if m:
            prop["baths_full"] = int(m.group(1))
        m = re.search(r'(?:Half\s*Baths?|Baths?\s*Half)\s*:?\s*(\d+)', text, re.I)
        if m:
            prop["baths_half"] = int(m.group(1))

        if "baths" not in prop and "baths_full" in prop:
            prop["baths"] = prop.get("baths_full", 0) + prop.get("baths_half", 0) * 0.5

        # MLS-specific: "Mstr Lvl Beds" and "Mstr Lvl Bths"
        if "beds" not in prop:
            m = re.search(r'(?:Total\s*Beds|Tot\s*Beds|Br)\s*:?\s*(\d+)', text, re.I)
            if m:
                prop["beds"] = int(m.group(1))

        # ── Square Footage ──
        # Try "Living Area", "Liv Area", "Leg Area Main", "Sq Ft", "Approx Sqft"
        for pattern in [
            r'(?:Living\s*Area\s*(?:Main)?|Liv\s*Area|Leg\s*Area\s*Main)\s*:?\s*([\d,]+)',
            r'(?:Approx\.?\s*(?:Liv(?:ing)?\s*)?(?:Sq\.?\s*Ft|SqFt|SF))\s*:?\s*([\d,]+)',
            r'(?:Sq\.?\s*Ft|SqFt|Square\s*Feet)\s*:?\s*([\d,]+)',
            r'(?:Bldg\.?\s*Area|Building\s*Area)\s*:?\s*([\d,]+)',
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                val = _clean_number(m.group(1))
                if val > 100:  # sanity check
                    prop["sqft"] = int(val)
                    break

        # ── Lot Size ──
        m = re.search(r'Lot\s*(?:Area|Size)\s*:?\s*([\d,]+)', text, re.I)
        if m:
            prop["lot_sqft"] = int(_clean_number(m.group(1)))
        m = re.search(r'Lot\s*Acres?\s*:?\s*([\d,.]+)', text, re.I)
        if m:
            acres = float(m.group(1).replace(",", ""))
            if "lot_sqft" not in prop or prop["lot_sqft"] == 0:
                prop["lot_sqft"] = int(acres * 43560)
            prop["lot_acres"] = acres

        # ── Year Built ──
        m = re.search(r'(?:Year\s*Built|Yr\s*Built|Built)\s*:?\s*(\d{4})', text, re.I)
        if m:
            prop["year_built"] = int(m.group(1))

        # ── Garage ──
        m = re.search(r'(?:Garage\s*(?:Spaces?|Cap)?|Gar(?:age)?\s*Cap)\s*:?\s*(\d+)', text, re.I)
        if m:
            prop["garage_spaces"] = int(m.group(1))
        # Also check "Attch Gar" or "Carport"
        if "garage_spaces" not in prop:
            m = re.search(r'(?:Attch?\s*Gar|Carport)\s*:?\s*(\d+)', text, re.I)
            if m:
                prop["garage_spaces"] = int(m.group(1))

        # ── Pool ──
        m = re.search(r'Pool\s*(?:Priv(?:ate)?|Y/?N)?\s*:?\s*(Yes|No|Private|Community|None)', text, re.I)
        if m:
            prop["pool"] = m.group(1).lower() in ("yes", "private", "community")
        else:
            prop["pool"] = bool(re.search(r'Pool|Swimming', text, re.I) and
                               not re.search(r'Pool\s*:\s*No', text, re.I))

        # ── Waterfront ──
        m = re.search(r'(?:Waterfront|Water\s*Front)\s*:?\s*(Yes|No)', text, re.I)
        if m:
            prop["waterfront"] = m.group(1).lower() == "yes"

        # ── DOM ──
        m = re.search(r'(?:DOMS?|DOM/?S|Days?\s*(?:on\s*)?(?:Market|MLS)|CDOM)\s*(?:/\s*DOMI?)?\s*:?\s*(\d+)', text, re.I)
        if m:
            prop["dom"] = int(m.group(1))

        # ── Dates ──
        m = re.search(r'(?:List(?:ing)?\s*Date|Date\s*Listed)\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})', text, re.I)
        if m:
            prop["list_date"] = _parse_date(m.group(1))

        m = re.search(r'(?:Close|Sold|Closing)\s*Date\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})', text, re.I)
        if m:
            prop["close_date"] = _parse_date(m.group(1))

        m = re.search(r'(?:Contract|Pending|Cntg)\s*Date\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})', text, re.I)
        if m:
            prop["contract_date"] = _parse_date(m.group(1))

        # ── Subdivision ──
        m = re.search(r'(?:Subdiv(?:ision)?|Subdv)\s*:?\s*([A-Za-z0-9\s]+?)(?:\n|$)', text, re.I)
        if m:
            prop["subdivision"] = m.group(1).strip()

        # ── Property Type ──
        m = re.search(r'(?:Sub\s*Type|Property\s*Type|Prop\s*Type)\s*:?\s*([^\n]+)', text, re.I)
        if m:
            raw_type = m.group(1).strip()
            prop["property_type_raw"] = raw_type
            if "condo" in raw_type.lower():
                prop["property_type"] = "condo"
            elif "town" in raw_type.lower():
                prop["property_type"] = "townhouse"
            elif "villa" in raw_type.lower():
                prop["property_type"] = "villa"
            else:
                prop["property_type"] = "single_family"

        # ── Stories ──
        m = re.search(r'Stories?\s*:?\s*(\d+)', text, re.I)
        if m:
            prop["stories"] = int(m.group(1))

        # ── HOA ──
        m = re.search(r'(?:Est\.?\s*Monthly\s*(?:Rent|Fee)|HOA\s*(?:Fee)?|Maint(?:enance)?\s*Fee)\s*:?\s*\$?([\d,]+)', text, re.I)
        if m:
            prop["hoa_monthly"] = _clean_number(m.group(1))

        # ── Listing History / Price Changes ──
        prop["price_history"] = self._extract_price_history(text)

        return prop

    def _extract_price_history(self, text: str) -> list[dict]:
        """
        Extract price change history from the property text.

        Flexmls reports may include a "History" or "Listing History" section
        showing status and price changes with dates.
        """
        events = []

        # Look for history section patterns
        # Pattern 1: "Date - Event - Price" rows
        # e.g., "04/01/2026  Listed  $650,000"
        #        "05/01/2026  Price Changed  $625,000"
        history_pattern = re.compile(
            r'(\d{1,2}/\d{1,2}/\d{2,4})\s+'
            r'(Listed|Price\s*Chang\w*|Reduced|Pending|Sold|Closed|Under\s*Contract|'
            r'Active|Back\s*on\s*Market|Withdrawn|Cancelled|Expired|New|'
            r'(?:Price\s*)?(?:Increase|Decrease|Reduction))\s*'
            r'(?:to\s*)?\$?([\d,]+)?',
            re.IGNORECASE,
        )
        for m in history_pattern.finditer(text):
            evt_date = _parse_date(m.group(1))
            evt_type = m.group(2).strip()
            evt_price = _clean_number(m.group(3)) if m.group(3) else 0

            if evt_date:
                events.append({
                    "date": evt_date,
                    "event": evt_type,
                    "price": evt_price,
                })

        # Pattern 2: "Status Change" table format
        # Some reports show: "Date | Status | Price | Agent"
        status_pattern = re.compile(
            r'(\d{1,2}/\d{1,2}/\d{2,4})\s+\$?([\d,]+)\s+'
            r'(Active|Pending|Closed|Sold)',
            re.IGNORECASE,
        )
        if not events:
            for m in status_pattern.finditer(text):
                evt_date = _parse_date(m.group(1))
                evt_price = _clean_number(m.group(2))
                evt_type = m.group(3).strip()
                if evt_date and evt_price:
                    events.append({
                        "date": evt_date,
                        "event": evt_type,
                        "price": evt_price,
                    })

        # Pattern 3: Look for price change amounts
        # "Price Change: -$25,000 on 05/01/2026"
        change_pattern = re.compile(
            r'(?:Price\s*(?:Change|Reduction|Decrease|Increase))\s*:?\s*'
            r'[-+]?\$?([\d,]+)\s+(?:on\s+)?(\d{1,2}/\d{1,2}/\d{2,4})',
            re.IGNORECASE,
        )
        for m in change_pattern.finditer(text):
            evt_date = _parse_date(m.group(2))
            if evt_date:
                events.append({
                    "date": evt_date,
                    "event": "Price Changed",
                    "price": _clean_number(m.group(1)),
                })

        # Sort by date
        events.sort(key=lambda e: e.get("date", date.today()))
        return events


def parse_flexmls_link(url: str) -> list[dict]:
    """Convenience function: fetch + parse a Flexmls public link."""
    parser = FlexmlsParser()
    return parser.fetch_and_parse(url)


def parse_flexmls_html_file(file_content: str | bytes) -> list[dict]:
    """Parse saved Flexmls HTML file content."""
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8", errors="replace")
    parser = FlexmlsParser()
    return parser.parse_html(file_content)


def flexmls_to_comps(raw_properties: list[dict]) -> list[Comp]:
    """Convert parsed Flexmls property dicts into Comp models."""
    comps = []
    for raw in raw_properties:
        status = (raw.get("status", "") or "").lower()

        # Build pricing history
        sale_price = raw.get("sale_price", 0)
        list_price = raw.get("list_price", 0)
        orig_price = raw.get("original_list_price", 0) or list_price

        # For closed listings, we need a sale price
        if "close" in status or "sold" in status:
            if not sale_price:
                continue  # skip if no sale price for a "sold" property
        else:
            # For active/pending, use list price as reference
            sale_price = sale_price or list_price

        # Parse price history into PriceChange objects
        price_changes = []
        raw_history = raw.get("price_history", [])
        if raw_history:
            prev_price = orig_price
            prev_date = raw.get("list_date") or date.today()

            for evt in raw_history:
                evt_type = (evt.get("event", "") or "").lower()
                evt_price = evt.get("price", 0)
                evt_date = evt.get("date")

                if not evt_date or not evt_price:
                    continue

                # Only track price changes (not "Listed", "Sold", etc.)
                if "chang" in evt_type or "reduc" in evt_type or "decrease" in evt_type or "increase" in evt_type:
                    if prev_price and evt_price != prev_price:
                        pc = PriceChange(
                            date=evt_date,
                            new_price=evt_price,
                            previous_price=prev_price,
                            days_at_previous_price=(evt_date - prev_date).days if prev_date else 0,
                        )
                        price_changes.append(pc)
                    prev_price = evt_price
                    prev_date = evt_date

        # Build the comp
        baths = raw.get("baths", 0) or 0
        if baths == 0:
            baths = (raw.get("baths_full", 0) or 0) + (raw.get("baths_half", 0) or 0) * 0.5

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

        # Build pricing history
        list_date = raw.get("list_date") or date.today()
        close_date = raw.get("close_date")
        contract_date = raw.get("contract_date")
        dom = raw.get("dom", 0) or 0

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
    """Convert parsed Flexmls property dicts into ActiveListing models (active only)."""
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


# ── Helpers ─────────────────────────────────────────────────────────

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
