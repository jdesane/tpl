"""Data models for the CMA tool."""

from pydantic import BaseModel, Field, computed_field
from typing import Optional
from datetime import date, datetime
from enum import Enum


class PropertyType(str, Enum):
    SINGLE_FAMILY = "single_family"
    CONDO = "condo"
    TOWNHOUSE = "townhouse"
    MULTI_FAMILY = "multi_family"
    VILLA = "villa"


class BuyerReaction(str, Enum):
    """How quickly buyers responded after the acceptance price was hit."""
    FAST = "fast"          # <7 days to contract
    MODERATE = "moderate"  # 7-20 days
    SLOW = "slow"          # 20+ days


class DemandStrength(str, Enum):
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


# ---------------------------------------------------------------------------
# Pricing History Models (the "edge")
# ---------------------------------------------------------------------------

class PriceChange(BaseModel):
    """A single price change event on a listing."""
    date: date
    new_price: float
    previous_price: float
    change_amount: float = 0          # negative = reduction
    change_pct: float = 0             # negative = reduction
    days_at_previous_price: int = 0
    cumulative_dom: int = 0           # total DOM at this point

    def model_post_init(self, __context):
        if self.change_amount == 0 and self.previous_price:
            self.change_amount = self.new_price - self.previous_price
        if self.change_pct == 0 and self.previous_price:
            self.change_pct = round(
                (self.new_price - self.previous_price) / self.previous_price * 100, 2
            )


class PricingHistory(BaseModel):
    """Complete pricing behavior for a sold property."""
    original_list_price: float
    final_list_price: float = 0
    sale_price: float
    list_date: date
    contract_date: Optional[date] = None
    close_date: Optional[date] = None
    total_dom: int = 0
    price_changes: list[PriceChange] = []

    # --- Computed after analysis ---
    num_reductions: int = 0
    total_reduction_amount: float = 0
    total_reduction_pct: float = 0
    days_from_last_change_to_contract: Optional[int] = None
    market_acceptance_price: float = 0
    buyer_reaction: Optional[BuyerReaction] = None
    sale_to_list_ratio: float = 0       # sale / final list
    sale_to_original_ratio: float = 0   # sale / original list
    market_rejected_prices: list[float] = []


# ---------------------------------------------------------------------------
# Property Models
# ---------------------------------------------------------------------------

class Property(BaseModel):
    """Base property details."""
    mls_number: str = ""
    address: str = ""
    city: str = ""
    state: str = "FL"
    zip_code: str = ""
    subdivision: str = ""
    property_type: PropertyType = PropertyType.SINGLE_FAMILY
    beds: int = 0
    baths: float = 0
    sqft: int = 0
    lot_sqft: int = 0
    year_built: int = 0
    garage_spaces: int = 0
    pool: bool = False
    stories: int = 1
    waterfront: bool = False
    hoa_monthly: float = 0
    condition: str = ""  # excellent / good / average / fair / poor
    notes: str = ""


class SubjectProperty(Property):
    """The property being priced."""
    pass


class Comp(Property):
    """A comparable sold property with pricing history."""
    pricing_history: Optional[PricingHistory] = None
    distance_miles: Optional[float] = None

    # Adjustments (field name -> dollar amount, positive = comp inferior)
    adjustments: dict[str, float] = {}
    adjusted_price: Optional[float] = None

    @computed_field
    @property
    def price_per_sqft(self) -> float:
        if self.pricing_history and self.sqft:
            return round(self.pricing_history.sale_price / self.sqft, 2)
        return 0.0


class ActiveListing(Property):
    """A currently active listing (competition)."""
    list_price: float = 0
    original_list_price: float = 0
    dom: int = 0
    price_changes: int = 0

    @computed_field
    @property
    def price_per_sqft(self) -> float:
        if self.list_price and self.sqft:
            return round(self.list_price / self.sqft, 2)
        return 0.0


# ---------------------------------------------------------------------------
# Analysis Output Models
# ---------------------------------------------------------------------------

class CompPattern(BaseModel):
    """Pattern observed for a single comp."""
    address: str
    original_list: float
    sale_price: float
    dom: int
    reductions: int
    market_rejected_prices: list[float] = []
    market_accepted_price: float = 0
    reaction_days: Optional[int] = None
    buyer_reaction: Optional[BuyerReaction] = None
    price_per_sqft: float = 0


class MarketPatterns(BaseModel):
    """Cross-comp pattern analysis — this is the gold."""
    total_comps: int = 0
    comp_patterns: list[CompPattern] = []

    # Averages
    avg_original_list: float = 0
    avg_sale_price: float = 0
    avg_dom: float = 0
    avg_reductions: float = 0
    avg_total_reduction_pct: float = 0
    avg_sale_to_list: float = 0
    avg_price_per_sqft: float = 0
    median_price_per_sqft: float = 0

    # The market acceptance zone
    acceptance_zone_low: float = 0
    acceptance_zone_high: float = 0
    avg_reaction_days: float = 0
    demand_strength: DemandStrength = DemandStrength.MODERATE

    # Strategy output
    pattern_notes: list[str] = []
    pricing_insight: str = ""


class PendingInsight(BaseModel):
    """Insight from pending/under-contract listings."""
    address: str = ""
    list_price: float = 0
    dom_before_contract: int = 0
    price_changes_before_contract: int = 0
    original_list: float = 0
    price_per_sqft: float = 0
    notes: str = ""


class CMAReport(BaseModel):
    """The complete CMA package."""
    created_at: datetime = Field(default_factory=datetime.now)
    subject: SubjectProperty = Field(default_factory=SubjectProperty)
    comps: list[Comp] = []
    patterns: MarketPatterns = Field(default_factory=MarketPatterns)
    active_competition: list[ActiveListing] = []
    pending_insights: list[PendingInsight] = []

    # Final pricing strategy
    recommended_list_price: Optional[float] = None
    price_range_low: Optional[float] = None
    price_range_high: Optional[float] = None
    strategy_notes: list[str] = []

    # Agent
    agent_name: str = "Joe Desane"
    brokerage: str = "LPT Realty"
