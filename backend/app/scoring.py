"""Relevance scoring.

    relevance = 100 * (BUDGET_WEIGHT * budget_fit + NEGOTIABILITY_WEIGHT * negotiability)

budget_fit: 0.5 ** (deviation / BUDGET_HALF_DEVIATION) — halves every 5% off
target, symmetric, no plateau, so any price difference is comparable.

negotiability: min(1, days_on_market / NEGOTIABILITY_WINDOW_DAYS) — time on
market as buyer leverage, not staleness. Deliberately inverted from "newest
first": this is a buyer's search, and leverage caps out around four months.

Weighted 60/40 toward budget, since price is the constraint the user actually
stated. Without a targetBudget, negotiability carries the full weight.
Reference date is injected, not read from the clock, so scores stay stable.
"""

from __future__ import annotations

from datetime import date

from .models import Listing, ScoreBreakdown, ScoredListing

BUDGET_WEIGHT = 0.6
NEGOTIABILITY_WEIGHT = 0.4

# Every 5% away from the target budget halves the budget score.
BUDGET_HALF_DEVIATION = 0.05

# Days on market at which negotiating leverage maxes out.
NEGOTIABILITY_WINDOW_DAYS = 120.0


def budget_fit(price: float, target_budget: float | None) -> float:
    """1.0 on target, halving every 5% off; asymptotic, never clamped to 0."""
    if target_budget is None or target_budget <= 0:
        return 0.0
    deviation = abs(price - target_budget) / target_budget
    return 0.5 ** (deviation / BUDGET_HALF_DEVIATION)


def negotiability(listed_date: date, reference_date: date) -> float:
    """Buyer leverage from time on market: 0.0 fresh, 1.0 once capped."""
    days_on_market = (reference_date - listed_date).days
    if days_on_market <= 0:
        return 0.0
    return min(1.0, days_on_market / NEGOTIABILITY_WINDOW_DAYS)


def score_listing(
    listing: Listing, target_budget: float | None, reference_date: date
) -> ScoredListing:
    """Attach a 0-100 relevance score plus the breakdown that explains it."""
    fit = budget_fit(listing.price, target_budget)
    leverage = negotiability(listing.listed_date, reference_date)

    if target_budget is None:
        budget_w, negotiability_w = 0.0, 1.0  # nothing to fit against
    else:
        budget_w, negotiability_w = BUDGET_WEIGHT, NEGOTIABILITY_WEIGHT

    score = 100.0 * (budget_w * fit + negotiability_w * leverage)

    return ScoredListing(
        # `key` is computed, so excluded here rather than round-tripped.
        **listing.model_dump(by_alias=True, exclude={"key"}),
        relevanceScore=round(score, 2),
        scoreBreakdown=ScoreBreakdown(
            budgetFit=round(fit, 4),
            negotiability=round(leverage, 4),
            budgetWeight=budget_w,
            negotiabilityWeight=negotiability_w,
        ),
    )


def sort_key_relevance(item: ScoredListing) -> tuple:
    """Total ordering so ties never depend on input order: score desc, then
    longest on market, cheapest, then key."""
    return (
        -item.relevance_score,
        item.listed_date.toordinal(),
        item.price,
        item.key,
    )
