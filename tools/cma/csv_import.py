"""
Flexmls CSV/Excel import.

Parses listing data exported from Flexmls into Comp models.
Flexmls export columns vary by what fields you select, but
common columns are mapped here. Unmapped columns are skipped.

Usage:
    from csv_import import parse_flexmls_csv
    comps = parse_flexmls_csv("exported_listings.csv")
"""

import csv
import io
import re
from datetime import date, datetime
from typing import Any

import pandas as pd

from models import Comp, PricingHistory, PriceChange, ActiveListing, PropertyType


# ── Column name mapping ─────────────────────────────────────────────
# Flexmls uses various column names depending on export config.
# We normalize them to our internal field names.
COLUMN_MAP = {
    # MLS number
    "mls #": "mls_number",
    "mls#": "mls_number",
    "mls number": "mls_number",
    "listing id": "mls_number",
    "listingid": "mls_number",
    "ml #": "mls_number",
    "ml#": "mls_number",
    "list number": "mls_number",

    # Address
    "address": "address",
    "full address": "address",
    "street address": "address",
    "unparsed address": "address",
    "property address": "address",

    # City / State / ZIP
    "city": "city",
    "state": "state",
    "zip": "zip_code",
    "zip code": "zip_code",
    "postal code": "zip_code",

    # Property details
    "beds": "beds",
    "bedrooms": "beds",
    "br": "beds",
    "beds total": "beds",
    "bedrooms total": "beds",
    "total bedrooms": "beds",
    "baths": "baths",
    "bathrooms": "baths",
    "ba": "baths",
    "baths total": "baths",
    "total baths": "baths",
    "bathrooms total": "baths",
    "bath(s) full": "baths_full",
    "full baths": "baths_full",
    "bath(s) half": "baths_half",
    "half baths": "baths_half",

    "sqft": "sqft",
    "sq ft": "sqft",
    "square feet": "sqft",
    "living area": "sqft",
    "total sqft": "sqft",
    "approx sqft": "sqft",
    "area (living)": "sqft",

    "lot size": "lot_sqft",
    "lot sqft": "lot_sqft",
    "lot size (sqft)": "lot_sqft",
    "lot sq ft": "lot_sqft",
    "lot area": "lot_sqft",

    "year built": "year_built",
    "yr built": "year_built",
    "year": "year_built",

    "garage": "garage_spaces",
    "garage spaces": "garage_spaces",
    "# garage spaces": "garage_spaces",
    "garage cap": "garage_spaces",

    "pool": "pool",
    "pool y/n": "pool",
    "pool private": "pool",

    "subdivision": "subdivision",
    "subdivision name": "subdivision",

    # Pricing
    "list price": "list_price",
    "listing price": "list_price",
    "current price": "list_price",
    "price": "list_price",

    "original list price": "original_list_price",
    "orig list price": "original_list_price",
    "original price": "original_list_price",
    "orig price": "original_list_price",

    "sold price": "sale_price",
    "close price": "sale_price",
    "sale price": "sale_price",
    "selling price": "sale_price",
    "closed price": "sale_price",
    "sp": "sale_price",

    # Dates
    "list date": "list_date",
    "listing date": "list_date",
    "date listed": "list_date",
    "on market date": "list_date",

    "close date": "close_date",
    "sold date": "close_date",
    "closing date": "close_date",
    "date sold": "close_date",
    "date closed": "close_date",

    "contract date": "contract_date",
    "pending date": "contract_date",
    "under contract date": "contract_date",

    # DOM
    "dom": "dom",
    "days on market": "dom",
    "cdom": "dom",
    "cumulative dom": "dom",

    # Status
    "status": "status",
    "listing status": "status",
    "standard status": "status",

    # Property type
    "property type": "property_type",
    "type": "property_type",
    "prop type": "property_type",
}


def _normalize_col(name: str) -> str:
    """Normalize a column name for matching."""
    return re.sub(r"[^a-z0-9 /()#]", "", name.lower().strip())


def _parse_number(val: Any) -> float:
    """Parse a number from various formats ($500,000 → 500000)."""
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return 0
    s = str(val).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0


def _parse_int(val: Any) -> int:
    return int(_parse_number(val))


def _parse_bool(val: Any) -> bool:
    if val is None:
        return False
    s = str(val).lower().strip()
    return s in ("yes", "y", "true", "1", "private", "community", "both")


def _parse_date_val(val: Any) -> date | None:
    """Parse a date from various formats."""
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (date, datetime)):
        return val if isinstance(val, date) else val.date()
    s = str(val).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def parse_flexmls_csv(file_content: str | bytes | io.BytesIO) -> list[dict]:
    """
    Parse a Flexmls CSV/Excel export into a list of normalized row dicts.

    Returns list of dicts with our standard field names.
    """
    # Read with pandas (handles CSV and Excel)
    if isinstance(file_content, bytes):
        try:
            df = pd.read_excel(io.BytesIO(file_content))
        except Exception:
            df = pd.read_csv(io.BytesIO(file_content))
    elif isinstance(file_content, io.BytesIO):
        try:
            df = pd.read_excel(file_content)
        except Exception:
            file_content.seek(0)
            df = pd.read_csv(file_content)
    else:
        df = pd.read_csv(io.StringIO(file_content))

    # Build column mapping for this specific file
    col_map = {}
    for col in df.columns:
        normalized = _normalize_col(col)
        if normalized in COLUMN_MAP:
            col_map[col] = COLUMN_MAP[normalized]

    # Parse rows
    rows = []
    for _, row in df.iterrows():
        parsed = {}
        for orig_col, field_name in col_map.items():
            parsed[field_name] = row[orig_col]
        rows.append(parsed)

    return rows


def rows_to_comps(rows: list[dict], status_filter: str = "closed") -> list[Comp]:
    """
    Convert parsed CSV rows into Comp models.

    Args:
        rows: Output from parse_flexmls_csv()
        status_filter: "closed" for sold comps, "active" for active listings, "all"
    """
    comps = []
    for row in rows:
        # Filter by status if present
        status = str(row.get("status", "")).lower()
        if status_filter == "closed" and status and "close" not in status and "sold" not in status:
            continue
        if status_filter == "active" and status and "active" not in status:
            continue

        # Handle baths (full + half or single value)
        baths = _parse_number(row.get("baths", 0))
        if baths == 0:
            baths = _parse_number(row.get("baths_full", 0)) + \
                    _parse_number(row.get("baths_half", 0)) * 0.5

        # Build address
        address = str(row.get("address", "")).strip()

        # Prices
        original_list = _parse_number(row.get("original_list_price", 0))
        list_price = _parse_number(row.get("list_price", 0))
        sale_price = _parse_number(row.get("sale_price", 0))

        if not original_list:
            original_list = list_price

        # Dates
        list_date = _parse_date_val(row.get("list_date"))
        close_date = _parse_date_val(row.get("close_date"))
        contract_date = _parse_date_val(row.get("contract_date"))
        dom = _parse_int(row.get("dom", 0))

        comp = Comp(
            mls_number=str(row.get("mls_number", "")).strip(),
            address=address,
            city=str(row.get("city", "")).strip(),
            state=str(row.get("state", "FL")).strip() or "FL",
            zip_code=str(row.get("zip_code", "")).strip(),
            subdivision=str(row.get("subdivision", "")).strip(),
            beds=_parse_int(row.get("beds", 0)),
            baths=baths,
            sqft=_parse_int(row.get("sqft", 0)),
            lot_sqft=_parse_int(row.get("lot_sqft", 0)),
            year_built=_parse_int(row.get("year_built", 0)),
            garage_spaces=_parse_int(row.get("garage_spaces", 0)),
            pool=_parse_bool(row.get("pool")),
        )

        # Build pricing history if we have price data
        if sale_price > 0 and original_list > 0:
            comp.pricing_history = PricingHistory(
                original_list_price=original_list,
                final_list_price=list_price or original_list,
                sale_price=sale_price,
                list_date=list_date or date.today(),
                contract_date=contract_date,
                close_date=close_date,
                total_dom=dom,
            )

        comps.append(comp)

    return comps


def rows_to_active_listings(rows: list[dict]) -> list[ActiveListing]:
    """Convert parsed CSV rows into ActiveListing models."""
    listings = []
    for row in rows:
        status = str(row.get("status", "")).lower()
        if status and "active" not in status:
            continue

        baths = _parse_number(row.get("baths", 0))
        if baths == 0:
            baths = _parse_number(row.get("baths_full", 0)) + \
                    _parse_number(row.get("baths_half", 0)) * 0.5

        list_price = _parse_number(row.get("list_price", 0))
        original_list = _parse_number(row.get("original_list_price", 0)) or list_price

        listings.append(ActiveListing(
            mls_number=str(row.get("mls_number", "")).strip(),
            address=str(row.get("address", "")).strip(),
            city=str(row.get("city", "")).strip(),
            zip_code=str(row.get("zip_code", "")).strip(),
            beds=_parse_int(row.get("beds", 0)),
            baths=baths,
            sqft=_parse_int(row.get("sqft", 0)),
            year_built=_parse_int(row.get("year_built", 0)),
            list_price=list_price,
            original_list_price=original_list,
            dom=_parse_int(row.get("dom", 0)),
        ))

    return listings
