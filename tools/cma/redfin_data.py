"""
Redfin automated data source.

Pulls property details, comparable sold listings, and full price change
history from Redfin's internal API endpoints. No API key required.

This is the automation layer — enter an address, get everything:
- Subject property details (beds, baths, sqft, year, lot, etc.)
- Nearby sold comps with full pricing history
- Active competition listings
- Price change timelines for every comp
"""

import json
import re
import time
from datetime import date, datetime, timedelta
from urllib.parse import quote, urlencode

import requests

from models import (
    Comp, SubjectProperty, ActiveListing, PricingHistory, PriceChange,
    PropertyType,
)

# Optional: homeharvest for Realtor.com fallback
try:
    from homeharvest import scrape_property as hh_scrape
    HAS_HOMEHARVEST = True
except ImportError:
    HAS_HOMEHARVEST = False


class RedfinAPI:
    """Client for Redfin's internal stingray API."""

    BASE_URL = "https://www.redfin.com"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.redfin.com/",
    }

    def __init__(self, delay: float = 1.0):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.delay = delay  # seconds between requests to be polite

    def _wait(self):
        time.sleep(self.delay)

    def _clean_response(self, text: str) -> dict:
        """
        Redfin responses are prefixed with '{}&&' to prevent JSONP hijacking.
        Strip that prefix and parse the JSON.
        """
        cleaned = text.strip()
        if cleaned.startswith("{}&&"):
            cleaned = cleaned[4:]
        return json.loads(cleaned)

    # ── Search / Autocomplete ───────────────────────────────────────

    def search_address(self, address: str) -> list[dict]:
        """
        Search Redfin for a property by address.
        Returns a list of matching results with property IDs and URLs.
        """
        url = f"{self.BASE_URL}/stingray/do/location-autocomplete"
        params = {"location": address, "v": 2}
        resp = self.session.get(url, params=params, timeout=15)
        if resp.status_code == 403:
            raise ConnectionError(
                "Redfin returned 403 Forbidden. This usually means your IP is blocked "
                "(common on cloud/VPN IPs). Try running from your home network."
            )
        resp.raise_for_status()

        data = self._clean_response(resp.text)
        results = []

        # Parse the autocomplete payload
        payload = data.get("payload", {})
        sections = payload.get("sections", [])
        for section in sections:
            rows = section.get("rows", [])
            for row in rows:
                result = {
                    "name": row.get("name", ""),
                    "subName": row.get("subName", ""),
                    "url": row.get("url", ""),
                    "type": row.get("type", ""),
                    "id": row.get("id", ""),
                    "propertyId": row.get("propertyId", ""),
                }
                # Accept any result that has a URL (property pages, addresses)
                # Filter out cities/neighborhoods/zip-only results
                row_url = row.get("url", "")
                if row_url and "/home/" in row_url:
                    results.append(result)

        # If strict filtering returned nothing, accept any result with a URL
        if not results:
            for section in sections:
                for row in section.get("rows", []):
                    if row.get("url"):
                        results.append({
                            "name": row.get("name", ""),
                            "subName": row.get("subName", ""),
                            "url": row.get("url", ""),
                            "type": row.get("type", ""),
                            "id": row.get("id", ""),
                            "propertyId": row.get("propertyId", ""),
                        })

        return results

    # ── Property Details ────────────────────────────────────────────

    def get_property_details(self, property_url: str) -> dict:
        """
        Fetch full property details from a Redfin property page.
        Returns raw data dict with all available fields.
        """
        self._wait()
        url = f"{self.BASE_URL}{property_url}"
        resp = self.session.get(url)
        resp.raise_for_status()

        html = resp.text
        details = {}

        # Extract initial data from the page's embedded JSON
        # Redfin embeds property data in a script tag
        pattern = r'root\.__reactServerState\.InitialContext\s*=\s*(\{.*?\});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                details["_raw"] = data
            except json.JSONDecodeError:
                pass

        # Also try the redfinApi prefetch data
        pattern2 = r'"propertyId"\s*:\s*(\d+)'
        match2 = re.search(pattern2, html)
        if match2:
            details["property_id"] = int(match2.group(1))

        # Extract key facts from the page
        details.update(self._extract_basic_details(html))
        details["url"] = property_url

        return details

    def _extract_basic_details(self, html: str) -> dict:
        """Extract property details from Redfin HTML."""
        details = {}

        # Address
        match = re.search(r'<title>([^|<]+)', html)
        if match:
            details["full_title"] = match.group(1).strip()

        # Beds
        match = re.search(r'(\d+)\s*(?:bed|br|bedroom)', html, re.I)
        if match:
            details["beds"] = int(match.group(1))

        # Baths
        match = re.search(r'([\d.]+)\s*(?:bath|ba)', html, re.I)
        if match:
            details["baths"] = float(match.group(1))

        # Sqft
        match = re.search(r'([\d,]+)\s*(?:sq\s*ft|sqft)', html, re.I)
        if match:
            details["sqft"] = int(match.group(1).replace(",", ""))

        # Year built
        match = re.search(r'(?:year\s*built|built\s*in)[:\s]*(\d{4})', html, re.I)
        if match:
            details["year_built"] = int(match.group(1))

        # Lot size
        match = re.search(r'(?:lot\s*size)[:\s]*([\d,.]+)\s*(?:sq\s*ft|sqft|acres)', html, re.I)
        if match:
            val = float(match.group(1).replace(",", ""))
            if "acres" in html[match.start():match.end() + 10].lower():
                val = int(val * 43560)
            details["lot_sqft"] = int(val)

        # Price
        match = re.search(r'\$\s*([\d,]+)\s*(?:,\d{3})*', html)
        if match:
            price_str = match.group(0).replace("$", "").replace(",", "").strip()
            try:
                details["price"] = int(float(price_str))
            except ValueError:
                pass

        return details

    # ── Below the Fold (price history, tax history, etc.) ───────────

    def get_below_the_fold(self, property_id: int) -> dict:
        """
        Fetch the 'below the fold' data which includes price history.
        """
        self._wait()
        url = f"{self.BASE_URL}/stingray/api/home/details/belowTheFold"
        params = {
            "propertyId": property_id,
            "accessLevel": 1,
        }
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return self._clean_response(resp.text)

    def get_price_history(self, property_id: int) -> list[dict]:
        """
        Extract the full price change history for a property.

        Returns list of events like:
        [
            {"date": "2026-01-15", "event": "Listed", "price": 650000},
            {"date": "2026-02-14", "event": "Price Changed", "price": 625000},
            {"date": "2026-03-01", "event": "Pending", "price": 625000},
            {"date": "2026-03-15", "event": "Sold", "price": 620000},
        ]
        """
        data = self.get_below_the_fold(property_id)
        payload = data.get("payload", {})

        events = []

        # Price history is in the propertyHistoryInfo
        history_info = payload.get("propertyHistoryInfo", {})
        history_events = history_info.get("events", [])

        for evt in history_events:
            event_date = None
            if evt.get("eventDate"):
                try:
                    # Redfin dates can be epoch ms or string
                    if isinstance(evt["eventDate"], (int, float)):
                        event_date = datetime.fromtimestamp(
                            evt["eventDate"] / 1000
                        ).strftime("%Y-%m-%d")
                    else:
                        event_date = str(evt["eventDate"])[:10]
                except (ValueError, OSError):
                    pass

            price = evt.get("price", 0)
            event_type = evt.get("eventDescription", "Unknown")

            if event_date and price:
                events.append({
                    "date": event_date,
                    "event": event_type,
                    "price": int(price),
                    "source": evt.get("sourceDescription", ""),
                })

        return events

    # ── Comp Search ─────────────────────────────────────────────────

    def search_comps(
        self,
        address: str,
        radius_miles: float = 1.0,
        min_beds: int = 0,
        max_beds: int = 99,
        min_sqft: int = 0,
        max_sqft: int = 99999,
        min_price: int = 0,
        max_price: int = 99999999,
        sold_within_days: int = 180,
        status: str = "sold",  # "sold" or "active"
        limit: int = 20,
    ) -> list[dict]:
        """
        Search for comparable properties near an address using Redfin's
        GIS search. Returns raw search result dicts.
        """
        # First, geocode the address
        results = self.search_address(address)
        if not results:
            return []

        # Get the property URL to find coordinates
        prop_url = results[0].get("url", "")
        if not prop_url:
            return []

        self._wait()

        # Use Redfin's map-based search with filters
        # Build the search URL with filters
        search_params = {
            "al": 1,
            "market": "florida",
            "num_homes": limit,
            "ord": "redfin-recommended-asc",
            "page_number": 1,
            "sf": "1,2,3,5,6,7",  # property type filters
            "status": 9 if status == "sold" else 1,
            "uipt": "1,2,3",  # single family, condo, townhouse
            "v": 8,
        }

        if min_price:
            search_params["min_price"] = min_price
        if max_price < 99999999:
            search_params["max_price"] = max_price
        if min_beds:
            search_params["min_beds"] = min_beds
        if max_beds < 99:
            search_params["max_beds"] = max_beds
        if min_sqft:
            search_params["min_sqft"] = min_sqft
        if max_sqft < 99999:
            search_params["max_sqft"] = max_sqft
        if status == "sold" and sold_within_days:
            search_params["sold_within_days"] = sold_within_days

        # Try the GIS CSV endpoint for clean data
        csv_url = f"{self.BASE_URL}/stingray/api/gis-csv"
        resp = self.session.get(csv_url, params=search_params)

        if resp.status_code == 200 and "," in resp.text:
            return self._parse_gis_csv(resp.text)

        return []

    def _parse_gis_csv(self, csv_text: str) -> list[dict]:
        """Parse Redfin's GIS CSV response into property dicts."""
        import csv
        import io

        reader = csv.DictReader(io.StringIO(csv_text))
        results = []
        for row in reader:
            results.append({
                "address": row.get("ADDRESS", ""),
                "city": row.get("CITY", ""),
                "state": row.get("STATE OR PROVINCE", ""),
                "zip": row.get("ZIP OR POSTAL CODE", ""),
                "price": _safe_int(row.get("PRICE", 0)),
                "beds": _safe_int(row.get("BEDS", 0)),
                "baths": _safe_float(row.get("BATHS", 0)),
                "sqft": _safe_int(row.get("SQUARE FEET", 0)),
                "lot_sqft": _safe_int(row.get("LOT SIZE", 0)),
                "year_built": _safe_int(row.get("YEAR BUILT", 0)),
                "dom": _safe_int(row.get("DAYS ON MARKET", 0)),
                "hoa": _safe_int(row.get("HOA/MONTH", 0)),
                "status": row.get("STATUS", ""),
                "url": row.get("URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)", ""),
                "property_type": row.get("PROPERTY TYPE", ""),
                "sold_date": row.get("SOLD DATE", ""),
                "latitude": _safe_float(row.get("LATITUDE", 0)),
                "longitude": _safe_float(row.get("LONGITUDE", 0)),
                "original_list_price": _safe_int(row.get("ORIGINAL LIST PRICE", 0)),
            })
        return results

    # ── High-Level: Full CMA Data Pull ──────────────────────────────

    def pull_subject(self, address: str) -> SubjectProperty | None:
        """
        Pull subject property details from Redfin.
        Returns a SubjectProperty model or None.
        """
        results = self.search_address(address)
        if not results:
            return None

        top = results[0]
        details = self.get_property_details(top["url"])

        return SubjectProperty(
            address=top.get("name", address),
            city=top.get("subName", "").split(",")[0].strip() if top.get("subName") else "",
            state="FL",
            beds=details.get("beds", 0),
            baths=details.get("baths", 0),
            sqft=details.get("sqft", 0),
            lot_sqft=details.get("lot_sqft", 0),
            year_built=details.get("year_built", 0),
        )

    def pull_comps(
        self,
        address: str,
        beds_range: int = 1,
        sqft_range_pct: float = 0.20,
        price_range_pct: float = 0.30,
        sold_within_days: int = 180,
        limit: int = 15,
        subject: SubjectProperty | None = None,
    ) -> list[Comp]:
        """
        Pull comparable sold properties with full pricing history.

        This is the full automated pipeline:
        1. Search for sold homes near the address
        2. For each result, fetch the price change history
        3. Build Comp models with PricingHistory

        Args:
            address: Subject property address
            beds_range: +/- bedroom range (1 = same +/- 1 bed)
            sqft_range_pct: sqft tolerance (0.20 = +/- 20%)
            price_range_pct: price tolerance (0.30 = +/- 30%)
            sold_within_days: how far back to search
            limit: max comps to return
            subject: optional SubjectProperty for filtering
        """
        # Build search filters from subject if available
        min_beds = max(0, (subject.beds - beds_range)) if subject and subject.beds else 0
        max_beds = (subject.beds + beds_range) if subject and subject.beds else 99
        min_sqft = int(subject.sqft * (1 - sqft_range_pct)) if subject and subject.sqft else 0
        max_sqft = int(subject.sqft * (1 + sqft_range_pct)) if subject and subject.sqft else 99999

        # Search for sold homes
        raw_results = self.search_comps(
            address=address,
            min_beds=min_beds,
            max_beds=max_beds,
            min_sqft=min_sqft,
            max_sqft=max_sqft,
            sold_within_days=sold_within_days,
            status="sold",
            limit=limit,
        )

        comps = []
        for raw in raw_results:
            comp = Comp(
                address=raw.get("address", ""),
                city=raw.get("city", ""),
                state=raw.get("state", "FL"),
                zip_code=str(raw.get("zip", "")),
                beds=raw.get("beds", 0),
                baths=raw.get("baths", 0),
                sqft=raw.get("sqft", 0),
                lot_sqft=raw.get("lot_sqft", 0),
                year_built=raw.get("year_built", 0),
                property_type=self._map_property_type(raw.get("property_type", "")),
            )

            # Build pricing history
            sale_price = raw.get("price", 0)
            original_list = raw.get("original_list_price", 0) or sale_price
            sold_date_str = raw.get("sold_date", "")
            dom = raw.get("dom", 0)

            sold_dt = _parse_date(sold_date_str)
            list_dt = None
            if sold_dt and dom:
                list_dt = sold_dt - timedelta(days=dom)

            if sale_price > 0:
                comp.pricing_history = PricingHistory(
                    original_list_price=original_list,
                    final_list_price=original_list,  # updated from price history below
                    sale_price=sale_price,
                    list_date=list_dt or date.today(),
                    close_date=sold_dt,
                    total_dom=dom,
                )

            # Try to get full price change history from property page
            prop_url = raw.get("url", "")
            if prop_url and comp.pricing_history:
                self._enrich_with_price_history(comp, prop_url)

            comps.append(comp)

        return comps

    def _enrich_with_price_history(self, comp: Comp, prop_url: str):
        """
        Fetch the full price history from a property page and
        enrich the comp's PricingHistory with price changes.
        """
        try:
            details = self.get_property_details(prop_url)
            property_id = details.get("property_id")

            if not property_id:
                return

            events = self.get_price_history(property_id)
            if not events:
                return

            h = comp.pricing_history

            # Parse events into our price change model
            listed_price = None
            listed_date = None
            last_price = None
            last_date = None
            contract_date = None
            price_changes = []

            for evt in events:
                evt_type = evt.get("event", "").lower()
                evt_price = evt.get("price", 0)
                evt_date = _parse_date(evt.get("date", ""))

                if not evt_date or not evt_price:
                    continue

                if "listed" in evt_type and not listed_price:
                    listed_price = evt_price
                    listed_date = evt_date
                    last_price = evt_price
                    last_date = evt_date

                elif "price changed" in evt_type or "price reduced" in evt_type:
                    if last_price and last_date:
                        pc = PriceChange(
                            date=evt_date,
                            new_price=evt_price,
                            previous_price=last_price,
                            days_at_previous_price=(evt_date - last_date).days,
                            cumulative_dom=(evt_date - (listed_date or last_date)).days,
                        )
                        price_changes.append(pc)
                    last_price = evt_price
                    last_date = evt_date

                elif "pending" in evt_type or "contingent" in evt_type:
                    contract_date = evt_date

                elif "sold" in evt_type:
                    h.sale_price = evt_price
                    h.close_date = evt_date

            # Update the pricing history
            if listed_price:
                h.original_list_price = listed_price
            if listed_date:
                h.list_date = listed_date
            if contract_date:
                h.contract_date = contract_date
            if price_changes:
                h.price_changes = price_changes
                h.final_list_price = price_changes[-1].new_price
            elif listed_price:
                h.final_list_price = listed_price

            # Recalculate DOM if we have better data
            if listed_date and (contract_date or h.close_date):
                end = contract_date or h.close_date
                h.total_dom = (end - listed_date).days

        except Exception:
            # If price history fetch fails, we still have the basic data
            pass

    def pull_active_listings(
        self,
        address: str,
        min_beds: int = 0,
        max_beds: int = 99,
        min_sqft: int = 0,
        max_sqft: int = 99999,
        limit: int = 15,
    ) -> list[ActiveListing]:
        """Pull currently active listings near the address."""
        raw_results = self.search_comps(
            address=address,
            min_beds=min_beds,
            max_beds=max_beds,
            min_sqft=min_sqft,
            max_sqft=max_sqft,
            status="active",
            limit=limit,
        )

        listings = []
        for raw in raw_results:
            listings.append(ActiveListing(
                address=raw.get("address", ""),
                city=raw.get("city", ""),
                zip_code=str(raw.get("zip", "")),
                beds=raw.get("beds", 0),
                baths=raw.get("baths", 0),
                sqft=raw.get("sqft", 0),
                year_built=raw.get("year_built", 0),
                list_price=raw.get("price", 0),
                original_list_price=raw.get("original_list_price", 0) or raw.get("price", 0),
                dom=raw.get("dom", 0),
            ))

        return listings

    def _map_property_type(self, raw: str) -> PropertyType:
        raw_lower = (raw or "").lower()
        if "condo" in raw_lower:
            return PropertyType.CONDO
        if "town" in raw_lower:
            return PropertyType.TOWNHOUSE
        if "multi" in raw_lower:
            return PropertyType.MULTI_FAMILY
        return PropertyType.SINGLE_FAMILY


# ── Helpers ─────────────────────────────────────────────────────────

def _safe_int(val) -> int:
    try:
        return int(float(str(val).replace(",", "").replace("$", "").strip() or 0))
    except (ValueError, TypeError):
        return 0


def _safe_float(val) -> float:
    try:
        return float(str(val).replace(",", "").replace("$", "").strip() or 0)
    except (ValueError, TypeError):
        return 0.0


def _parse_date(val) -> date | None:
    if not val:
        return None
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


# ═══════════════════════════════════════════════════════════════════
# Realtor.com fallback via homeharvest
# ═══════════════════════════════════════════════════════════════════

def pull_comps_homeharvest(
    location: str,
    listing_type: str = "sold",
    past_days: int = 180,
    subject: SubjectProperty | None = None,
    beds_range: int = 1,
    sqft_range_pct: float = 0.20,
) -> list[Comp]:
    """
    Fallback comp search using homeharvest (Realtor.com scraper).
    Provides basic comp data (no individual price change history,
    but includes list price, sold price, and DOM).
    """
    if not HAS_HOMEHARVEST:
        raise ImportError("homeharvest not installed. Run: pip install homeharvest")

    import pandas as pd

    df = hh_scrape(
        location=location,
        listing_type=listing_type,
        past_days=past_days,
    )

    if df is None or df.empty:
        return []

    # Filter by subject property criteria if available
    if subject and subject.beds:
        min_beds = max(0, subject.beds - beds_range)
        max_beds = subject.beds + beds_range
        if "beds" in df.columns:
            df = df[(df["beds"] >= min_beds) & (df["beds"] <= max_beds)]

    if subject and subject.sqft:
        min_sqft = int(subject.sqft * (1 - sqft_range_pct))
        max_sqft = int(subject.sqft * (1 + sqft_range_pct))
        if "sqft" in df.columns:
            df = df[(df["sqft"] >= min_sqft) & (df["sqft"] <= max_sqft)]

    comps = []
    for _, row in df.iterrows():
        address = str(row.get("full_street_line", "") or row.get("street", ""))
        if not address:
            continue

        sale_price = _safe_int(row.get("sold_price", 0) or row.get("last_sold_date", 0))
        list_price = _safe_int(row.get("list_price", 0))
        if sale_price == 0:
            sale_price = _safe_int(row.get("price", 0))

        beds = _safe_int(row.get("beds", 0))
        baths = _safe_float(row.get("full_baths", 0)) + _safe_float(row.get("half_baths", 0)) * 0.5
        if baths == 0:
            baths = _safe_float(row.get("baths", 0))
        sqft = _safe_int(row.get("sqft", 0))
        lot_sqft = _safe_int(row.get("lot_sqft", 0))
        year_built = _safe_int(row.get("year_built", 0))
        dom = _safe_int(row.get("days_on_mls", 0))

        sold_date = None
        if "sold_date" in row and row["sold_date"] is not None:
            sold_date = _parse_date(str(row["sold_date"]))
        elif "last_sold_date" in row and row["last_sold_date"] is not None:
            sold_date = _parse_date(str(row["last_sold_date"]))

        list_date = None
        if "list_date" in row and row["list_date"] is not None:
            list_date = _parse_date(str(row["list_date"]))
        elif sold_date and dom:
            list_date = sold_date - timedelta(days=dom)

        comp = Comp(
            address=address,
            city=str(row.get("city", "")),
            state=str(row.get("state", "FL")),
            zip_code=str(row.get("zip_code", "")),
            beds=beds,
            baths=baths,
            sqft=sqft,
            lot_sqft=lot_sqft,
            year_built=year_built,
        )

        if sale_price > 0:
            comp.pricing_history = PricingHistory(
                original_list_price=list_price or sale_price,
                final_list_price=list_price or sale_price,
                sale_price=sale_price,
                list_date=list_date or date.today(),
                close_date=sold_date,
                total_dom=dom,
            )

        comps.append(comp)

    return comps


# ═══════════════════════════════════════════════════════════════════
# Unified data pull — tries sources in order
# ═══════════════════════════════════════════════════════════════════

def auto_pull_comps(
    address: str,
    subject: SubjectProperty | None = None,
    sold_within_days: int = 180,
    limit: int = 15,
    beds_range: int = 1,
    sqft_range_pct: float = 0.20,
) -> tuple[list[Comp], str]:
    """
    Try multiple data sources to pull comps automatically.

    Returns (comps, source_name) tuple.
    Tries in order:
    1. Redfin (best — includes price change history)
    2. Realtor.com via homeharvest (fallback — basic data only)
    """
    # Try Redfin first (has price change history)
    try:
        rf = RedfinAPI(delay=1.5)
        comps = rf.pull_comps(
            address=address,
            beds_range=beds_range,
            sqft_range_pct=sqft_range_pct,
            sold_within_days=sold_within_days,
            limit=limit,
            subject=subject,
        )
        if comps:
            return comps, "Redfin"
    except (ConnectionError, requests.exceptions.HTTPError) as e:
        pass  # Fall through to next source

    # Try Realtor.com via homeharvest
    if HAS_HOMEHARVEST:
        try:
            # Build a location string from the address
            location = address
            if subject and subject.city:
                location = f"{subject.city}, {subject.state} {subject.zip_code}".strip()

            comps = pull_comps_homeharvest(
                location=location,
                listing_type="sold",
                past_days=sold_within_days,
                subject=subject,
                beds_range=beds_range,
                sqft_range_pct=sqft_range_pct,
            )
            if comps:
                return comps[:limit], "Realtor.com"
        except Exception:
            pass

    return [], "none"


def auto_pull_subject(address: str) -> tuple[SubjectProperty | None, str]:
    """
    Try to pull subject property details automatically.
    Returns (subject, source_name) tuple.
    """
    # Try Redfin
    try:
        rf = RedfinAPI(delay=0.5)
        subject = rf.pull_subject(address)
        if subject and subject.beds > 0:
            return subject, "Redfin"
    except Exception:
        pass

    # Try homeharvest / Realtor.com
    if HAS_HOMEHARVEST:
        try:
            import pandas as pd
            df = hh_scrape(location=address, listing_type="sold", past_days=365)
            if df is not None and not df.empty:
                row = df.iloc[0]
                addr = str(row.get("full_street_line", "") or row.get("street", address))
                subject = SubjectProperty(
                    address=addr,
                    city=str(row.get("city", "")),
                    state=str(row.get("state", "FL")),
                    zip_code=str(row.get("zip_code", "")),
                    beds=_safe_int(row.get("beds", 0)),
                    baths=_safe_float(row.get("full_baths", 0)) or _safe_float(row.get("baths", 0)),
                    sqft=_safe_int(row.get("sqft", 0)),
                    lot_sqft=_safe_int(row.get("lot_sqft", 0)),
                    year_built=_safe_int(row.get("year_built", 0)),
                )
                if subject.beds > 0:
                    return subject, "Realtor.com"
        except Exception:
            pass

    return None, "none"
