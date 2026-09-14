"""Relevance scoring.

    relevance = 100 * (BUDGET_WEIGHT * budget_fit + NEGOTIABILITY_WEIGHT * negotiability)

Two components, both normalized to [0, 1] so the score is always 0-100 and
comparable across queries.

budget_fit      0.5 ** (deviation / BUDGET_HALF_DEVIATION). Halves for every 5%
                the price drifts from targetBudget. Steepest right around the
                target, so a listing $5k closer to budget genuinely outranks
                one $5k further away. An earlier version gave full credit
                anywhere inside a +/-5% band; that plateau made price
                differences *invisible* between two listings that both fell
                inside it, which is precisely the comparison a buyer cares
                about.

                The penalty is symmetric: a $200k home does not fit a $500k
                budget any better than an $800k one. Buyers shop a band, not a
                ceiling.

negotiability   min(1, days_on_market / NEGOTIABILITY_WINDOW_DAYS). Time on
                market is treated as an *asset*, not decay: the longer a
                listing sits, the more room a buyer has to negotiate, so a
                stale listing is a better prospect at the same price.

                This deliberately inverts the usual "newest first" ordering.
                Freshness is the seller's interest; leverage is the buyer's,
                and this is a buyer's search.

                The value is capped rather than unbounded because leverage
                stops accumulating. Beyond roughly four months, additional
                days on market say more about a problem with the property —
                overpricing, condition, title — than about a motivated seller,
                so a two-year-old listing earns no more credit than a
                four-month-old one.

Weights favour budget 60/40. Price is the constraint the user actually stated;
negotiability ranks the opportunities *within* the prices they can afford.

When targetBudget is absent there is nothing to fit, so the budget term is
dropped and negotiability is renormalized to carry the full weight. Scores stay
on the same 0-100 scale either way.

The reference date is injected rather than read from the clock inside the
formula, so tests are deterministic and a demo doesn't drift day to day.
"""

from __future__ import annotations

from datetime import date

from .models import Listing, ScoreBreakdown, ScoredListing

BUDGET_WEIGHT = 0.6
NEGOTIABILITY_WEIGHT = 0.4

# Every 5% away from the target budget halves the budget score.
BUDGET_HALF_DEVIATION = 0.05

# Days on market at which negotiating leverage is considered maxed out.
NEGOTIABILITY_WINDOW_DAYS = 120.0


def budget_fit(price: float, target_budget: float | None) -> float:
    """How well a price matches the target: 1.0 on the nose, halving every 5% off.

    Continuous with no plateau, so any price difference changes the score. That
    is the point — two listings either side of the target must be separable,
    however close they are. Asymptotic rather than clamped to zero, so listings
    far outside budget still rank sensibly against each other instead of all
    collapsing to the same 0.0.
    """
    if target_budget is None or target_budget <= 0:
        return 0.0
    deviation = abs(price - target_budget) / target_budget
    return 0.5 ** (deviation / BUDGET_HALF_DEVIATION)


def negotiability(listed_date: date, reference_date: date) -> float:
    """Buyer leverage from time on market: 0.0 when fresh, 1.0 once capped.

    Rises linearly over the negotiating window then plateaus, so a listing that
    has sat for a year earns no more credit than one at four months — past that
    point, extra days signal a problem with the property rather than a seller
    who will move on price.

    A listing dated in the future (feed clock skew, or seed data ahead of the
    reference date) has no leverage yet rather than a negative score.
    """
    days_on_market = (reference_date - listed_date).days
    if days_on_market <= 0:
        return 0.0
    return min(1.0, days_on_market / NEGOTIABILITY_WINDOW_DAYS)


def score_listing(
    listing: Listing, target_budget: float | None, reference_date: date
) -> ScoredListing:
    """Attach a 0-100 relevance score, and the breakdown that explains it.

    The brief asks for the scoring approach to be clearly explained, so the two
    components and their weights travel with the result instead of collapsing
    into one opaque number. That makes a rank auditable in the UI and exact in
    tests. `reference_date` is passed in rather than read from the clock so
    scores are reproducible.
    """
    fit = budget_fit(listing.price, target_budget)
    leverage = negotiability(listing.listed_date, reference_date)

    if target_budget is None:
        # Nothing to fit against: negotiability carries the whole score.
        budget_w, negotiability_w = 0.0, 1.0
    else:
        budget_w, negotiability_w = BUDGET_WEIGHT, NEGOTIABILITY_WEIGHT

    score = 100.0 * (budget_w * fit + negotiability_w * leverage)

    return ScoredListing(
        # `key` is computed from source+id, so it is excluded here rather
        # than round-tripped through the constructor. Everything else carries
        # over verbatim, including any `mergedFrom` that dedupe attached.
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
    """Total ordering, so ties never depend on input order.

    Without a deterministic tie-break, two listings with equal scores can swap
    places between requests and the same row shows up on two different pages.

    Chain: score desc, then longest on market, then cheapest, then key. The
    date direction mirrors the negotiability term — once scores tie, the more
    negotiable listing is the better prospect — so the secondary ordering can't
    contradict the primary one.
    """
    return (
        -item.relevance_score,
        item.listed_date.toordinal(),
        item.price,
        item.key,
    )
