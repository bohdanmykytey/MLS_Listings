"""Relevance scoring.

    relevance = 100 * (BUDGET_WEIGHT * budget_fit + RECENCY_WEIGHT * recency)

Two components, both normalized to [0, 1] so the final score is always 0-100
and comparable across queries:

budget_fit  Full credit inside a tolerance band around targetBudget, then a
            linear decay to zero at the cutoff. The penalty is *symmetric*: a
            $200k home does not "fit" a $500k budget any better than an $800k
            one does. Buyers shop a band, not a ceiling. (Asymmetric — reward
            anything under budget — is the obvious alternative; rejected
            because it ranks a studio above the house you actually want.)

recency     Exponential decay with a 30-day half-life. Monotone, never
            negative, and degrades smoothly: a listing 30 days old is worth
            half a listing posted today. A linear decay over the corpus's date
            range was the alternative, but it makes every score depend on the
            dataset's oldest record, so adding one stale listing silently
            reshuffles every other rank.

When targetBudget is absent there is nothing to fit, so the budget term is
dropped and recency is renormalized to carry the full weight. Scores stay on
the same 0-100 scale either way.

The reference date is injected rather than read from the clock inside the
formula, so tests are deterministic and a demo doesn't drift day to day.
"""

from __future__ import annotations

from datetime import date

from .models import Listing, ScoreBreakdown, ScoredListing

BUDGET_WEIGHT = 0.6
RECENCY_WEIGHT = 0.4

# Within +/-5% of target counts as a perfect fit; fit reaches 0 at +/-50%.
BUDGET_TOLERANCE = 0.05
BUDGET_CUTOFF = 0.50

RECENCY_HALF_LIFE_DAYS = 30.0


def budget_fit(price: float, target_budget: float | None) -> float:
    """1.0 for a price at/near target, decaying linearly to 0.0 at the cutoff."""
    if target_budget is None or target_budget <= 0:
        return 0.0
    deviation = abs(price - target_budget) / target_budget
    if deviation <= BUDGET_TOLERANCE:
        return 1.0
    if deviation >= BUDGET_CUTOFF:
        return 0.0
    # Linear ramp from 1.0 at the tolerance edge to 0.0 at the cutoff.
    return 1.0 - (deviation - BUDGET_TOLERANCE) / (BUDGET_CUTOFF - BUDGET_TOLERANCE)


def recency(listed_date: date, reference_date: date) -> float:
    """0.5 ** (age_days / half_life), clamped to [0, 1].

    A listing dated in the future (feed clock skew, or seed data ahead of
    today) is treated as brand new rather than scoring above 1.0.
    """
    age_days = (reference_date - listed_date).days
    if age_days <= 0:
        return 1.0
    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


def score_listing(
    listing: Listing, target_budget: float | None, reference_date: date
) -> ScoredListing:
    fit = budget_fit(listing.price, target_budget)
    rec = recency(listing.listed_date, reference_date)

    if target_budget is None:
        # Nothing to fit against: recency carries the whole score.
        budget_w, recency_w = 0.0, 1.0
    else:
        budget_w, recency_w = BUDGET_WEIGHT, RECENCY_WEIGHT

    score = 100.0 * (budget_w * fit + recency_w * rec)

    return ScoredListing(
        # `key` is computed from source+id, so it is excluded here rather
        # than round-tripped through the constructor.
        **listing.model_dump(by_alias=True, exclude={"key"}),
        relevanceScore=round(score, 2),
        scoreBreakdown=ScoreBreakdown(
            budgetFit=round(fit, 4),
            recency=round(rec, 4),
            budgetWeight=budget_w,
            recencyWeight=recency_w,
        ),
    )


def sort_key_relevance(item: ScoredListing) -> tuple:
    """Total ordering, so ties never depend on input order.

    Without a deterministic tie-break, two listings with equal scores can swap
    places between requests and the same row shows up on two different pages.
    Tie-break chain: score desc, then newest, then cheapest, then key.
    """
    return (
        -item.relevance_score,
        -item.listed_date.toordinal(),
        item.price,
        item.key,
    )
