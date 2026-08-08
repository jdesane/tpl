"""
Pricing History Analysis Engine — the competitive edge.

This module implements the pricing behavior analysis that most agents skip:
- For every comp, trace the full price change timeline
- Identify where the market REJECTED a price (sat, reduced)
- Identify where the market ACCEPTED a price (went under contract quickly)
- Stack patterns across all comps to find the true market value zone
"""

from datetime import date
from statistics import mean, median
from models import (
    Comp, PricingHistory, PriceChange, MarketPatterns, CompPattern,
    BuyerReaction, DemandStrength,
)


def classify_reaction(days: int | None) -> BuyerReaction | None:
    """Classify buyer reaction speed based on days to contract."""
    if days is None:
        return None
    if days <= 7:
        return BuyerReaction.FAST
    if days <= 20:
        return BuyerReaction.MODERATE
    return BuyerReaction.SLOW


def analyze_pricing_history(history: PricingHistory) -> PricingHistory:
    """
    Analyze a single comp's pricing behavior.

    Computes: reduction counts, market-rejected prices, the market acceptance
    price (the price at which buyers actually moved), buyer reaction speed,
    and sale-to-list ratios.
    """
    if not history.final_list_price:
        history.final_list_price = history.original_list_price

    # --- Sale-to-list ratios ---
    if history.final_list_price:
        history.sale_to_list_ratio = round(
            history.sale_price / history.final_list_price * 100, 2
        )
    if history.original_list_price:
        history.sale_to_original_ratio = round(
            history.sale_price / history.original_list_price * 100, 2
        )

    # --- Total DOM fallback ---
    if history.total_dom == 0 and history.contract_date and history.list_date:
        history.total_dom = (history.contract_date - history.list_date).days

    # --- Price reductions ---
    reductions = [pc for pc in history.price_changes if pc.change_amount < 0]
    history.num_reductions = len(reductions)
    history.total_reduction_amount = sum(pc.change_amount for pc in reductions)
    if history.original_list_price:
        history.total_reduction_pct = round(
            history.total_reduction_amount / history.original_list_price * 100, 2
        )

    # --- Market-rejected prices ---
    # Every price the property sat at before the final acceptance is a "rejection"
    rejected = []
    if history.price_changes:
        # Original list was rejected if there were any reductions
        if history.num_reductions > 0:
            rejected.append(history.original_list_price)
        # Each intermediate price that led to another reduction was rejected
        for pc in history.price_changes:
            if pc.change_amount < 0 and pc.previous_price not in rejected:
                rejected.append(pc.previous_price)
    history.market_rejected_prices = rejected

    # --- Market acceptance price ---
    # This is THE key insight: the price at which buyers engaged.
    if history.price_changes:
        # The acceptance price is the last price before going under contract
        last_change = history.price_changes[-1]
        history.market_acceptance_price = last_change.new_price

        # Days from last price change to under contract
        if history.contract_date:
            history.days_from_last_change_to_contract = (
                history.contract_date - last_change.date
            ).days
    else:
        # No price changes — original list was accepted
        history.market_acceptance_price = history.original_list_price
        if history.contract_date and history.list_date:
            history.days_from_last_change_to_contract = (
                history.contract_date - history.list_date
            ).days

    # --- Buyer reaction speed ---
    history.buyer_reaction = classify_reaction(
        history.days_from_last_change_to_contract
    )

    return history


def build_price_changes(
    original_price: float,
    list_date: date,
    change_prices: list[float],
    change_dates: list[date],
) -> list[PriceChange]:
    """
    Build PriceChange list from raw price/date sequences.

    Args:
        original_price: Original list price
        list_date: Date the property was listed
        change_prices: List of new prices after each change (in order)
        change_dates: Corresponding dates of each change
    """
    changes = []
    prev_price = original_price
    prev_date = list_date

    for new_price, change_date in zip(change_prices, change_dates):
        days_at_prev = (change_date - prev_date).days
        cumulative_dom = (change_date - list_date).days
        change = PriceChange(
            date=change_date,
            new_price=new_price,
            previous_price=prev_price,
            change_amount=new_price - prev_price,
            change_pct=round((new_price - prev_price) / prev_price * 100, 2) if prev_price else 0,
            days_at_previous_price=days_at_prev,
            cumulative_dom=cumulative_dom,
        )
        changes.append(change)
        prev_price = new_price
        prev_date = change_date

    return changes


def analyze_comp(comp: Comp) -> Comp:
    """Run pricing history analysis on a comp and return it enriched."""
    if comp.pricing_history:
        comp.pricing_history = analyze_pricing_history(comp.pricing_history)
    return comp


def _comp_to_pattern(comp: Comp) -> CompPattern | None:
    """Extract the pattern from an analyzed comp."""
    h = comp.pricing_history
    if not h:
        return None
    return CompPattern(
        address=comp.address,
        original_list=h.original_list_price,
        sale_price=h.sale_price,
        dom=h.total_dom,
        reductions=h.num_reductions,
        market_rejected_prices=h.market_rejected_prices,
        market_accepted_price=h.market_acceptance_price,
        reaction_days=h.days_from_last_change_to_contract,
        buyer_reaction=h.buyer_reaction,
        price_per_sqft=comp.price_per_sqft,
    )


def analyze_market_patterns(comps: list[Comp]) -> MarketPatterns:
    """
    Stack patterns across all comps to find the true market value zone.

    This is where individual comp analysis becomes a pricing strategy:
    - Are multiple homes needing 2-3 price drops?
    - Are they all landing in the same price band?
    - Are buyers reacting quickly at a certain price point?
    That number becomes your pricing target.
    """
    analyzed = [analyze_comp(c) for c in comps]
    patterns = [_comp_to_pattern(c) for c in analyzed if c.pricing_history]
    patterns = [p for p in patterns if p is not None]

    if not patterns:
        return MarketPatterns()

    mp = MarketPatterns(
        total_comps=len(patterns),
        comp_patterns=patterns,
    )

    # --- Averages ---
    mp.avg_original_list = round(mean(p.original_list for p in patterns), 0)
    mp.avg_sale_price = round(mean(p.sale_price for p in patterns), 0)
    mp.avg_dom = round(mean(p.dom for p in patterns), 1)
    mp.avg_reductions = round(mean(p.reductions for p in patterns), 1)

    histories = [c.pricing_history for c in analyzed if c.pricing_history]
    if histories:
        mp.avg_total_reduction_pct = round(
            mean(h.total_reduction_pct for h in histories), 1
        )
        ratios = [h.sale_to_list_ratio for h in histories if h.sale_to_list_ratio]
        if ratios:
            mp.avg_sale_to_list = round(mean(ratios), 2)

    # --- Price per sqft ---
    ppsf = [p.price_per_sqft for p in patterns if p.price_per_sqft > 0]
    if ppsf:
        mp.avg_price_per_sqft = round(mean(ppsf), 2)
        mp.median_price_per_sqft = round(median(ppsf), 2)

    # --- Market acceptance zone ---
    acceptance_prices = [p.market_accepted_price for p in patterns if p.market_accepted_price > 0]
    if acceptance_prices:
        mp.acceptance_zone_low = round(min(acceptance_prices), 0)
        mp.acceptance_zone_high = round(max(acceptance_prices), 0)

    # --- Buyer reaction speed ---
    reaction_days = [p.reaction_days for p in patterns if p.reaction_days is not None]
    if reaction_days:
        mp.avg_reaction_days = round(mean(reaction_days), 1)

    # --- Demand strength ---
    if reaction_days:
        avg_react = mean(reaction_days)
        avg_reductions = mean(p.reductions for p in patterns)
        if avg_react <= 7 and avg_reductions < 1:
            mp.demand_strength = DemandStrength.STRONG
        elif avg_react <= 14 and avg_reductions <= 2:
            mp.demand_strength = DemandStrength.MODERATE
        else:
            mp.demand_strength = DemandStrength.WEAK

    # --- Pattern notes (auto-generated insights) ---
    notes = _generate_pattern_notes(mp, patterns)
    mp.pattern_notes = notes
    mp.pricing_insight = _generate_pricing_insight(mp)

    return mp


def _generate_pattern_notes(mp: MarketPatterns, patterns: list[CompPattern]) -> list[str]:
    """Generate human-readable pattern observations."""
    notes: list[str] = []

    # Multiple reductions pattern
    multi_reduce = [p for p in patterns if p.reductions >= 2]
    if len(multi_reduce) >= 2:
        notes.append(
            f"{len(multi_reduce)} of {len(patterns)} comps needed 2+ price reductions "
            f"before finding a buyer — sellers consistently overpriced initially."
        )

    # All landing in same band
    if mp.acceptance_zone_high and mp.acceptance_zone_low:
        spread = mp.acceptance_zone_high - mp.acceptance_zone_low
        midpoint = (mp.acceptance_zone_high + mp.acceptance_zone_low) / 2
        if midpoint > 0 and (spread / midpoint) < 0.10:
            notes.append(
                f"Market acceptance prices clustered tightly between "
                f"${mp.acceptance_zone_low:,.0f}–${mp.acceptance_zone_high:,.0f} "
                f"(only {spread / midpoint * 100:.1f}% spread) — strong consensus on value."
            )

    # Fast reactions
    fast = [p for p in patterns if p.buyer_reaction == BuyerReaction.FAST]
    if fast:
        prices = [p.market_accepted_price for p in fast]
        notes.append(
            f"{len(fast)} comp(s) went under contract within 7 days of reaching their "
            f"acceptance price (${min(prices):,.0f}–${max(prices):,.0f} range) — "
            f"strong buyer demand at that level."
        )

    # Slow reactions
    slow = [p for p in patterns if p.buyer_reaction == BuyerReaction.SLOW]
    if len(slow) > len(patterns) / 2:
        notes.append(
            "Majority of comps took 20+ days even after their final price reduction — "
            "demand is soft; aggressive pricing recommended."
        )

    # Sale-to-original ratio
    if mp.avg_sale_to_list and mp.avg_sale_to_list < 95:
        notes.append(
            f"Average sale-to-list ratio is {mp.avg_sale_to_list:.1f}% — "
            f"homes are selling well below asking; price expectations need to be set early."
        )

    # DOM pattern
    if mp.avg_dom > 60:
        notes.append(
            f"Average days on market is {mp.avg_dom:.0f} — this is a slow-moving "
            f"market segment; pricing right on day one is critical."
        )
    elif mp.avg_dom < 14:
        notes.append(
            f"Average days on market is only {mp.avg_dom:.0f} — strong demand; "
            f"there may be room to price at the higher end of the range."
        )

    # No reductions = strong market
    no_reduce = [p for p in patterns if p.reductions == 0]
    if len(no_reduce) == len(patterns):
        notes.append(
            "None of the comps needed a price reduction — the market is absorbing "
            "inventory at list price. Well-priced listings should sell quickly."
        )

    return notes


def _generate_pricing_insight(mp: MarketPatterns) -> str:
    """Generate the top-level pricing insight summary."""
    if mp.demand_strength == DemandStrength.STRONG:
        return (
            f"Strong buyer demand in this segment. Homes priced at or near market "
            f"(${mp.acceptance_zone_low:,.0f}–${mp.acceptance_zone_high:,.0f}) are "
            f"attracting offers within {mp.avg_reaction_days:.0f} days. "
            f"Price competitively to capture the strongest buyer activity upfront."
        )
    elif mp.demand_strength == DemandStrength.MODERATE:
        return (
            f"Moderate demand. Comps needed an average of {mp.avg_reductions:.1f} "
            f"price reduction(s) before selling. The market acceptance zone is "
            f"${mp.acceptance_zone_low:,.0f}–${mp.acceptance_zone_high:,.0f}. "
            f"Pricing at or slightly below this zone will minimize days on market."
        )
    else:
        return (
            f"Weak buyer demand in this segment. Average DOM is {mp.avg_dom:.0f} "
            f"days with {mp.avg_reductions:.1f} reductions needed on average. "
            f"The market only responded when prices reached "
            f"${mp.acceptance_zone_low:,.0f}–${mp.acceptance_zone_high:,.0f}. "
            f"Recommend pricing aggressively from day one to avoid chasing the market."
        )


def calculate_adjustments(
    comp: Comp,
    subject_sqft: int,
    subject_beds: int,
    subject_baths: float,
    subject_garage: int,
    subject_pool: bool,
    subject_year: int,
    price_per_sqft: float = 0,
    bed_value: float = 10_000,
    bath_value: float = 8_000,
    garage_value: float = 15_000,
    pool_value: float = 20_000,
    age_value_per_year: float = 1_500,
) -> Comp:
    """
    Apply standard CMA adjustments to a comp.

    Adjustments are from the COMP's perspective:
    - Comp is INFERIOR to subject → positive adjustment (adds value to comp)
    - Comp is SUPERIOR to subject → negative adjustment (subtracts from comp)
    """
    if not comp.pricing_history:
        return comp

    adjustments: dict[str, float] = {}
    base_price = comp.pricing_history.sale_price

    # Sqft adjustment
    sqft_diff = subject_sqft - comp.sqft
    if sqft_diff != 0 and price_per_sqft > 0:
        adjustments["sqft"] = round(sqft_diff * price_per_sqft)

    # Beds
    bed_diff = subject_beds - comp.beds
    if bed_diff != 0:
        adjustments["beds"] = round(bed_diff * bed_value)

    # Baths
    bath_diff = subject_baths - comp.baths
    if bath_diff != 0:
        adjustments["baths"] = round(bath_diff * bath_value)

    # Garage
    garage_diff = subject_garage - comp.garage_spaces
    if garage_diff != 0:
        adjustments["garage"] = round(garage_diff * garage_value)

    # Pool
    if subject_pool and not comp.pool:
        adjustments["pool"] = pool_value
    elif not subject_pool and comp.pool:
        adjustments["pool"] = -pool_value

    # Age / condition (newer = more valuable)
    year_diff = subject_year - comp.year_built
    if abs(year_diff) >= 3:
        adjustments["age"] = round(year_diff * age_value_per_year)

    comp.adjustments = adjustments
    comp.adjusted_price = round(base_price + sum(adjustments.values()))
    return comp


def generate_pricing_strategy(
    mp: MarketPatterns,
    adjusted_prices: list[float],
    subject_sqft: int = 0,
) -> dict:
    """
    Combine pattern analysis + adjusted comps into a final pricing strategy.

    Returns a dict with:
    - recommended_price: single recommended list price
    - price_range: (low, high) range
    - strategy_notes: list of talking points
    - presentation_script: what to say to the seller
    """
    if not adjusted_prices:
        return {
            "recommended_price": None,
            "price_range": (None, None),
            "strategy_notes": [],
            "presentation_script": "",
        }

    avg_adjusted = mean(adjusted_prices)
    med_adjusted = median(adjusted_prices)

    # Use the tighter of adjusted values vs acceptance zone
    low = round(min(min(adjusted_prices), mp.acceptance_zone_low or min(adjusted_prices)), -3)
    high = round(max(max(adjusted_prices), mp.acceptance_zone_high or max(adjusted_prices)), -3)

    # Recommended price based on demand
    if mp.demand_strength == DemandStrength.STRONG:
        recommended = round(med_adjusted, -3)  # price at median
    elif mp.demand_strength == DemandStrength.MODERATE:
        recommended = round(avg_adjusted * 0.99, -3)  # slight discount
    else:
        recommended = round(avg_adjusted * 0.97, -3)  # price to move

    notes = []
    notes.append(
        f"Adjusted comp values range from ${min(adjusted_prices):,.0f} to "
        f"${max(adjusted_prices):,.0f}."
    )

    if mp.avg_reductions > 1:
        notes.append(
            f"Comps averaged {mp.avg_reductions:.1f} price reductions. "
            f"Pricing below the initial list range avoids the same trap."
        )

    if mp.avg_dom > 30:
        notes.append(
            f"Average DOM of {mp.avg_dom:.0f} days. Aggressive initial pricing "
            f"recommended to beat market fatigue."
        )

    if subject_sqft and mp.median_price_per_sqft:
        ppsf_value = round(subject_sqft * mp.median_price_per_sqft, -3)
        notes.append(
            f"At the median $/sqft of ${mp.median_price_per_sqft:,.2f}, "
            f"subject property values at ${ppsf_value:,.0f}."
        )

    # Seller presentation script
    script_parts = [
        '"Here\'s what most agents won\'t show you..."',
        "",
    ]
    for cp in mp.comp_patterns[:3]:
        if cp.reductions > 0:
            script_parts.append(
                f"• {cp.address}: Listed at ${cp.original_list:,.0f}, "
                f"needed {cp.reductions} reduction(s), finally sold at ${cp.sale_price:,.0f} "
                f"after {cp.dom} days."
            )
        else:
            script_parts.append(
                f"• {cp.address}: Listed and sold at ${cp.sale_price:,.0f} "
                f"in just {cp.dom} days — priced right from day one."
            )

    script_parts.append("")
    script_parts.append('"Here\'s the pattern across every comparable that sold..."')
    for note in mp.pattern_notes[:3]:
        script_parts.append(f"• {note}")

    script_parts.append("")
    script_parts.append(
        f'"If we price at ${recommended:,.0f} from day one, we skip the reductions '
        f'and capture the strongest buyer activity upfront."'
    )

    return {
        "recommended_price": recommended,
        "price_range": (low, high),
        "strategy_notes": notes,
        "presentation_script": "\n".join(script_parts),
    }
