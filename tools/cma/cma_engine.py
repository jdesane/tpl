"""
CMA orchestration engine.

Ties together: subject property, comp search, pricing history analysis,
adjustments, and strategy generation into a complete CMA report.
"""

from models import (
    CMAReport, SubjectProperty, Comp, ActiveListing, PendingInsight,
)
from analysis import (
    analyze_comp, analyze_market_patterns, calculate_adjustments,
    generate_pricing_strategy,
)
from config import Config


def run_cma(
    subject: SubjectProperty,
    comps: list[Comp],
    active: list[ActiveListing] | None = None,
    pending: list[PendingInsight] | None = None,
    adjustment_overrides: dict | None = None,
) -> CMAReport:
    """
    Run the full CMA workflow:
    1. Analyze each comp's pricing history
    2. Apply adjustments
    3. Detect cross-comp market patterns
    4. Generate pricing strategy
    5. Package into report
    """
    # Step 1: Analyze each comp's pricing history
    analyzed_comps = [analyze_comp(c) for c in comps]

    # Step 2: Market pattern analysis (the gold)
    patterns = analyze_market_patterns(analyzed_comps)

    # Step 3: Apply adjustments
    # Use median price/sqft from patterns, or a default
    ppsf = patterns.median_price_per_sqft or patterns.avg_price_per_sqft or 200

    adj_defaults = {
        "price_per_sqft": ppsf,
        "bed_value": 10_000,
        "bath_value": 8_000,
        "garage_value": 15_000,
        "pool_value": 20_000,
        "age_value_per_year": 1_500,
    }
    if adjustment_overrides:
        adj_defaults.update(adjustment_overrides)

    adjusted_comps = []
    for comp in analyzed_comps:
        adj = calculate_adjustments(
            comp,
            subject_sqft=subject.sqft,
            subject_beds=subject.beds,
            subject_baths=subject.baths,
            subject_garage=subject.garage_spaces,
            subject_pool=subject.pool,
            subject_year=subject.year_built,
            **adj_defaults,
        )
        adjusted_comps.append(adj)

    # Step 4: Generate pricing strategy
    adjusted_prices = [c.adjusted_price for c in adjusted_comps if c.adjusted_price]
    strategy = generate_pricing_strategy(
        patterns,
        adjusted_prices,
        subject_sqft=subject.sqft,
    )

    # Step 5: Package report
    report = CMAReport(
        subject=subject,
        comps=adjusted_comps,
        patterns=patterns,
        active_competition=active or [],
        pending_insights=pending or [],
        recommended_list_price=strategy["recommended_price"],
        price_range_low=strategy["price_range"][0],
        price_range_high=strategy["price_range"][1],
        strategy_notes=strategy["strategy_notes"],
        agent_name=Config.AGENT_NAME,
        brokerage=Config.BROKERAGE,
    )

    return report
