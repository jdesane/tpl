"""
Flexmls / Spark API client for Beaches MLS.

Connects to the Spark API to pull:
- Property details by MLS# or address
- Comparable sold listings
- Listing price change history

Requires API credentials from https://sparkplatform.com
When credentials aren't configured, the app falls back to manual entry.
"""

import hashlib
import hmac
import json
import time
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

import requests

from config import Config
from models import (
    Comp, PricingHistory, PriceChange, Property, ActiveListing,
    PropertyType,
)


class SparkAPIError(Exception):
    pass


class SparkClient:
    """Client for the Spark / Flexmls API."""

    def __init__(self):
        self.base_url = Config.SPARK_API_BASE_URL.rstrip("/")
        self.api_key = Config.SPARK_API_KEY
        self.api_secret = Config.SPARK_API_SECRET
        self.access_token = Config.SPARK_ACCESS_TOKEN
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "X-SparkApi-User-Agent": "TPLAgentTools/1.0",
        })
        if self.access_token:
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token or (self.api_key and self.api_secret))

    def authenticate(self) -> str:
        """
        Authenticate with Spark API using API key + secret.
        Returns an access token and stores it on the session.

        NOTE: If you already have an access token (from OAuth flow or
        sparkplatform.com developer portal), set SPARK_ACCESS_TOKEN in .env
        and skip this step.
        """
        if self.access_token:
            return self.access_token

        if not self.api_key or not self.api_secret:
            raise SparkAPIError(
                "No Spark API credentials configured. "
                "Set SPARK_ACCESS_TOKEN or SPARK_API_KEY + SPARK_API_SECRET in .env"
            )

        # Spark API session auth
        url = f"{self.base_url}/session"
        headers = {"Content-Type": "application/json"}
        body = {"D": {"ApiKey": self.api_key}}

        # Compute API signature
        sig_data = f"{self.api_secret}/v1/session"
        api_sig = hashlib.sha256(sig_data.encode()).hexdigest()
        body["D"]["ApiSig"] = api_sig

        resp = self.session.post(url, json=body, headers=headers)
        if resp.status_code != 200:
            raise SparkAPIError(f"Auth failed: {resp.status_code} — {resp.text}")

        data = resp.json()
        self.access_token = data.get("D", {}).get("AuthToken", "")
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        return self.access_token

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a GET request to the Spark API."""
        url = f"{self.base_url}{endpoint}"
        resp = self.session.get(url, params=params)
        if resp.status_code == 401:
            # Try re-auth
            self.authenticate()
            resp = self.session.get(url, params=params)
        if resp.status_code != 200:
            raise SparkAPIError(f"API error {resp.status_code}: {resp.text}")
        return resp.json()

    def get_listing(self, mls_number: str) -> dict | None:
        """Fetch a single listing by MLS number."""
        data = self._get("/listings", params={
            "_filter": f"ListingId Eq '{mls_number}'",
            "_limit": 1,
        })
        results = data.get("D", {}).get("Results", [])
        return results[0] if results else None

    def search_listings(
        self,
        status: str = "Closed",
        city: str = "",
        zip_code: str = "",
        min_beds: int = 0,
        max_beds: int = 99,
        min_sqft: int = 0,
        max_sqft: int = 99999,
        min_price: float = 0,
        max_price: float = 99999999,
        sold_within_days: int = 180,
        property_type: str = "A",  # A = residential
        limit: int = 25,
    ) -> list[dict]:
        """
        Search for listings matching criteria.

        Args:
            status: "Closed", "Active", "Pending", etc.
            city: Filter by city name
            zip_code: Filter by zip
            min_beds/max_beds: Bedroom range
            min_sqft/max_sqft: Square footage range
            min_price/max_price: Price range
            sold_within_days: For Closed, how far back to look
            limit: Max results
        """
        filters = [f"StandardStatus Eq '{status}'"]

        if city:
            filters.append(f"City Eq '{city}'")
        if zip_code:
            filters.append(f"PostalCode Eq '{zip_code}'")
        if min_beds:
            filters.append(f"BedroomsTotal Ge {min_beds}")
        if max_beds < 99:
            filters.append(f"BedroomsTotal Le {max_beds}")
        if min_sqft:
            filters.append(f"LivingArea Ge {min_sqft}")
        if max_sqft < 99999:
            filters.append(f"LivingArea Le {max_sqft}")
        if min_price:
            filters.append(f"ListPrice Ge {min_price}")
        if max_price < 99999999:
            filters.append(f"ListPrice Le {max_price}")

        if status == "Closed" and sold_within_days:
            cutoff = (date.today() - timedelta(days=sold_within_days)).isoformat()
            filters.append(f"CloseDate Ge {cutoff}")

        filter_str = " And ".join(filters)
        data = self._get("/listings", params={
            "_filter": filter_str,
            "_limit": limit,
            "_orderby": "-CloseDate" if status == "Closed" else "-ListPrice",
        })
        return data.get("D", {}).get("Results", [])

    def get_listing_history(self, listing_key: str) -> list[dict]:
        """
        Fetch price change history for a listing.
        Returns list of history events with price and date.
        """
        try:
            data = self._get(f"/listings/{listing_key}/history")
            return data.get("D", {}).get("Results", [])
        except SparkAPIError:
            return []

    # -------------------------------------------------------------------
    # Conversion helpers: Spark API JSON → our models
    # -------------------------------------------------------------------

    def _parse_property_type(self, raw: str) -> PropertyType:
        raw_lower = (raw or "").lower()
        if "condo" in raw_lower:
            return PropertyType.CONDO
        if "town" in raw_lower:
            return PropertyType.TOWNHOUSE
        if "villa" in raw_lower:
            return PropertyType.VILLA
        if "multi" in raw_lower or "duplex" in raw_lower:
            return PropertyType.MULTI_FAMILY
        return PropertyType.SINGLE_FAMILY

    def listing_to_comp(self, listing: dict) -> Comp:
        """Convert a Spark API listing dict to a Comp model."""
        standard = listing.get("StandardFields", listing)

        # Basic property details
        comp = Comp(
            mls_number=standard.get("ListingId", ""),
            address=standard.get("UnparsedAddress", "")
                or f"{standard.get('StreetNumber', '')} {standard.get('StreetName', '')} {standard.get('StreetSuffix', '')}".strip(),
            city=standard.get("City", ""),
            state=standard.get("StateOrProvince", "FL"),
            zip_code=standard.get("PostalCode", ""),
            property_type=self._parse_property_type(standard.get("PropertyType", "")),
            beds=int(standard.get("BedroomsTotal", 0) or 0),
            baths=float(standard.get("BathroomsFull", 0) or 0)
                + float(standard.get("BathroomsHalf", 0) or 0) * 0.5,
            sqft=int(standard.get("LivingArea", 0) or 0),
            lot_sqft=int(standard.get("LotSizeSquareFeet", 0) or 0),
            year_built=int(standard.get("YearBuilt", 0) or 0),
            garage_spaces=int(standard.get("GarageSpaces", 0) or 0),
            pool="pool" in (standard.get("PoolFeatures", "") or "").lower()
                or bool(standard.get("PoolPrivateYN")),
        )

        # Build pricing history
        list_price = float(standard.get("OriginalListPrice", 0)
                          or standard.get("ListPrice", 0) or 0)
        close_price = float(standard.get("ClosePrice", 0) or 0)
        final_list = float(standard.get("ListPrice", 0) or 0)

        list_date_str = standard.get("ListingContractDate", "") or standard.get("OnMarketDate", "")
        close_date_str = standard.get("CloseDate", "")
        contract_date_str = standard.get("PurchaseContractDate", "") or standard.get("PendingTimestamp", "")

        list_dt = _parse_date(list_date_str)
        close_dt = _parse_date(close_date_str)
        contract_dt = _parse_date(contract_date_str)
        dom = int(standard.get("DaysOnMarket", 0) or 0)

        if list_price and close_price:
            comp.pricing_history = PricingHistory(
                original_list_price=list_price,
                final_list_price=final_list,
                sale_price=close_price,
                list_date=list_dt or date.today(),
                contract_date=contract_dt,
                close_date=close_dt,
                total_dom=dom,
            )

        return comp

    def listing_to_active(self, listing: dict) -> ActiveListing:
        """Convert a Spark API listing dict to an ActiveListing model."""
        standard = listing.get("StandardFields", listing)
        return ActiveListing(
            mls_number=standard.get("ListingId", ""),
            address=standard.get("UnparsedAddress", "")
                or f"{standard.get('StreetNumber', '')} {standard.get('StreetName', '')} {standard.get('StreetSuffix', '')}".strip(),
            city=standard.get("City", ""),
            zip_code=standard.get("PostalCode", ""),
            beds=int(standard.get("BedroomsTotal", 0) or 0),
            baths=float(standard.get("BathroomsFull", 0) or 0),
            sqft=int(standard.get("LivingArea", 0) or 0),
            year_built=int(standard.get("YearBuilt", 0) or 0),
            list_price=float(standard.get("ListPrice", 0) or 0),
            original_list_price=float(standard.get("OriginalListPrice", 0)
                                     or standard.get("ListPrice", 0) or 0),
            dom=int(standard.get("DaysOnMarket", 0) or 0),
        )


def _parse_date(val: str | None) -> date | None:
    """Parse a date string from the Spark API."""
    if not val:
        return None
    try:
        # Handle ISO format and common variants
        clean = val[:10]  # take YYYY-MM-DD portion
        return date.fromisoformat(clean)
    except (ValueError, IndexError):
        return None
