"""Relevance scoring.

The formula is the most contestable design decision in the project, so these
tests pin its *intent*, not just its arithmetic: the tolerance band, the
symmetric penalty, the decay rate, and the renormalization when no budget is
given. If someone changes a weight, a test should say which behaviour broke.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.scoring import (
    BUDGET_HALF_DEVIATION,
    BUDGET_WEIGHT,
    NEGOTIABILITY_WEIGHT,
    NEGOTIABILITY_WINDOW_DAYS,
    budget_fit,
    negotiability,
    score_listing,
    sort_key_relevance,
)

TODAY = date(2026, 9, 11)
TARGET = 500_000.0


class TestBudgetFit:
    def test_exact_target_is_a_perfect_fit(self) -> None:
        assert budget_fit(TARGET, TARGET) == 1.0

    def test_one_half_deviation_halves_the_fit(self) -> None:
        """The formula in one assertion: 5% off target costs half the score."""
        assert budget_fit(TARGET * (1 + BUDGET_HALF_DEVIATION), TARGET) == pytest.approx(0.5)

    def test_two_half_deviations_quarter_the_fit(self) -> None:
        assert budget_fit(TARGET * 1.10, TARGET) == pytest.approx(0.25)

    def test_small_price_differences_are_visible(self) -> None:
        """The reason the old tolerance band was removed.

        $465k and $470k against a $450k budget both sat inside the former
        +/-5% plateau and scored an identical 1.0, so the closer listing could
        not outrank the further one. Any price difference must now register.
        """
        closer = budget_fit(465_000, 450_000)
        further = budget_fit(470_000, 450_000)
        assert closer > further

    def test_penalty_is_symmetric_around_the_target(self) -> None:
        """A home 30% under budget fits exactly as well as one 30% over.

        Buyers shop a band, not a ceiling. Rewarding anything cheaper would
        rank a studio above the house the user actually wants.
        """
        under = budget_fit(TARGET * 0.70, TARGET)
        over = budget_fit(TARGET * 1.30, TARGET)
        assert under == pytest.approx(over)
        assert 0.0 < under < 1.0

    def test_fit_decays_monotonically_as_price_moves_away(self) -> None:
        fits = [budget_fit(TARGET * (1 + d), TARGET) for d in (0.02, 0.10, 0.25, 0.50)]
        assert fits == sorted(fits, reverse=True)

    def test_fit_stays_within_bounds_however_far_off(self) -> None:
        """Asymptotic, never clamped — so distant listings still order against
        each other rather than all collapsing to a shared 0.0."""
        far = budget_fit(50_000_000, TARGET)
        nearer = budget_fit(5_000_000, TARGET)
        assert 0.0 <= far < nearer < 1.0

    @pytest.mark.parametrize("target", [None, 0.0, -1.0])
    def test_missing_or_nonsensical_target_yields_no_fit(self, target: float | None) -> None:
        # Guards the formula against division by zero; the API rejects
        # non-positive budgets before they reach here.
        assert budget_fit(400_000, target) == 0.0


class TestNegotiability:
    """Time on market as buyer leverage, not as decay.

    Deliberately inverted relative to a conventional "newest first" ranking:
    freshness serves the seller, leverage serves the buyer, and this is a
    buyer's search.
    """

    def test_a_listing_posted_today_has_no_leverage_yet(self) -> None:
        assert negotiability(TODAY, TODAY) == 0.0

    def test_leverage_accrues_linearly_across_the_window(self) -> None:
        quarter = date.fromordinal(TODAY.toordinal() - int(NEGOTIABILITY_WINDOW_DAYS / 4))
        half = date.fromordinal(TODAY.toordinal() - int(NEGOTIABILITY_WINDOW_DAYS / 2))
        assert negotiability(quarter, TODAY) == pytest.approx(0.25)
        assert negotiability(half, TODAY) == pytest.approx(0.5)

    def test_leverage_maxes_out_at_the_window(self) -> None:
        full = date.fromordinal(TODAY.toordinal() - int(NEGOTIABILITY_WINDOW_DAYS))
        assert negotiability(full, TODAY) == 1.0

    def test_leverage_is_capped_not_unbounded(self) -> None:
        """Past the window, extra days say more about a problem with the
        property than about a motivated seller, so they earn no more credit."""
        capped = date.fromordinal(TODAY.toordinal() - int(NEGOTIABILITY_WINDOW_DAYS))
        ancient = date.fromordinal(TODAY.toordinal() - 3650)
        assert negotiability(ancient, TODAY) == negotiability(capped, TODAY) == 1.0

    def test_older_listings_always_score_at_least_as_well(self) -> None:
        scores = [
            negotiability(date.fromordinal(TODAY.toordinal() - age), TODAY)
            for age in (0, 30, 60, 120, 365)
        ]
        assert scores == sorted(scores)

    def test_future_dated_listing_has_no_leverage_rather_than_negative(self) -> None:
        """Feed clock skew must not produce a score below zero."""
        future = date.fromordinal(TODAY.toordinal() + 30)
        assert negotiability(future, TODAY) == 0.0

    def test_value_is_always_within_bounds(self) -> None:
        for age in (-30, 0, 1, 120, 10_000):
            value = negotiability(date.fromordinal(TODAY.toordinal() - age), TODAY)
            assert 0.0 <= value <= 1.0


class TestScoreListing:
    def test_perfect_listing_scores_one_hundred(self, make_listing) -> None:
        """On budget to the dollar, and on the market long enough to negotiate."""
        capped = date.fromordinal(TODAY.toordinal() - int(NEGOTIABILITY_WINDOW_DAYS))
        listing = make_listing(price=TARGET, listed_date=capped.isoformat())
        assert score_listing(listing, TARGET, TODAY).relevance_score == 100.0

    def test_worst_listing_scores_zero(self, make_listing) -> None:
        """Far outside budget and posted today: no price match, no leverage."""
        listing = make_listing(price=TARGET * 5, listed_date=TODAY.isoformat())
        assert score_listing(listing, TARGET, TODAY).relevance_score == 0.0

    def test_score_always_lands_between_zero_and_one_hundred(self, make_listing) -> None:
        for price in (1, 100_000, TARGET, 5_000_000):
            for age in (0, 45, 900):
                listing = make_listing(
                    price=price,
                    listed_date=date.fromordinal(TODAY.toordinal() - age).isoformat(),
                )
                assert 0.0 <= score_listing(listing, TARGET, TODAY).relevance_score <= 100.0

    def test_weights_are_applied_as_documented(self, make_listing) -> None:
        # Perfect fit, halfway through the negotiating window.
        halfway = date.fromordinal(TODAY.toordinal() - int(NEGOTIABILITY_WINDOW_DAYS / 2))
        listing = make_listing(price=TARGET, listed_date=halfway.isoformat())
        expected = 100 * (BUDGET_WEIGHT * 1.0 + NEGOTIABILITY_WEIGHT * 0.5)
        assert score_listing(listing, TARGET, TODAY).relevance_score == pytest.approx(expected)

    def test_breakdown_explains_the_score(self, make_listing) -> None:
        listing = make_listing(price=TARGET, listed_date=TODAY.isoformat())
        scored = score_listing(listing, TARGET, TODAY)
        b = scored.score_breakdown
        recomputed = 100 * (
            b.budget_weight * b.budget_fit + b.negotiability_weight * b.negotiability
        )
        assert recomputed == pytest.approx(scored.relevance_score, abs=0.01)


class TestNoTargetBudget:
    """Without a budget the score must stay on the same 0-100 scale."""

    def test_weights_renormalize_so_negotiability_carries_everything(
        self, make_listing
    ) -> None:
        listing = make_listing()
        scored = score_listing(listing, None, TODAY)
        assert scored.score_breakdown.budget_weight == 0.0
        assert scored.score_breakdown.negotiability_weight == 1.0

    def test_most_negotiable_listing_still_reaches_one_hundred(self, make_listing) -> None:
        # Without renormalization this would cap at 40 (the negotiability weight).
        capped = date.fromordinal(TODAY.toordinal() - int(NEGOTIABILITY_WINDOW_DAYS))
        listing = make_listing(listed_date=capped.isoformat())
        assert score_listing(listing, None, TODAY).relevance_score == 100.0

    def test_price_is_irrelevant_when_no_budget_is_given(self, make_listing) -> None:
        cheap = make_listing("C", price=100_000)
        dear = make_listing("D", price=9_000_000)
        a = score_listing(cheap, None, TODAY).relevance_score
        b = score_listing(dear, None, TODAY).relevance_score
        assert a == b


class TestTieBreaking:
    """Tied scores.

    Ties occur with real data: scores are rounded to 2dp before sorting, so two
    listings whose raw scores differ by less than half a cent compare equal.
    The tie-break chain then orders them — score desc -> newest -> cheapest ->
    key — so the result is a total order rather than one that depends on the
    order rows happened to arrive in.

    The real-data case is covered first; the constructed listings that follow
    isolate each individual link in the chain, which a single dataset cannot.
    """

    def test_real_query_on_sample_data_produces_a_tie(self, sample_listings) -> None:
        """No fixtures: this is a query a user could actually run."""
        scored = [score_listing(l, 398_100.0, TODAY) for l in sample_listings]
        by_key = {s.key: s for s in scored}
        assert by_key["MLS_A:A1"].relevance_score == by_key["MLS_B:B7"].relevance_score

    def test_a_real_tie_is_ordered_deterministically(self, sample_listings) -> None:
        """Both tied listings are returned and both keep their score; only
        their relative order is decided. B7 has sat longer, so it ranks first."""
        scored = sorted(
            (score_listing(l, 398_100.0, TODAY) for l in sample_listings),
            key=sort_key_relevance,
        )
        keys = [s.key for s in scored]
        assert keys.index("MLS_B:B7") < keys.index("MLS_A:A1")

    def test_a_real_tie_survives_input_reordering(self, sample_listings) -> None:
        """The property that matters: the output order must come from the data,
        not from the order the repository happened to return rows in."""
        forward = [
            s.key
            for s in sorted(
                (score_listing(l, 398_100.0, TODAY) for l in sample_listings),
                key=sort_key_relevance,
            )
        ]
        backward = [
            s.key
            for s in sorted(
                (score_listing(l, 398_100.0, TODAY) for l in reversed(sample_listings)),
                key=sort_key_relevance,
            )
        ]
        assert forward == backward

    def test_identical_listings_produce_identical_scores(self, make_listing) -> None:
        a = score_listing(make_listing("A", price=TARGET), TARGET, TODAY)
        b = score_listing(make_listing("B", price=TARGET), TARGET, TODAY)
        assert a.relevance_score == b.relevance_score

    def test_tie_breaks_on_time_on_market_first(self, make_listing) -> None:
        """Equal scores: the listing that has sat longer is the better prospect,
        matching the direction of the negotiability term itself.

        Both listings are past the negotiability cap (so leverage ties at 1.0)
        and equidistant from the target in opposite directions (so budget_fit
        ties by symmetry) — the only way to construct a genuine tie between two
        listings with different dates.
        """
        longer = score_listing(make_listing("L", price=490_000, listed_date="2026-01-01"), TARGET, TODAY)
        shorter = score_listing(make_listing("S", price=510_000, listed_date="2026-03-01"), TARGET, TODAY)
        assert longer.relevance_score == shorter.relevance_score
        assert sorted([longer, shorter], key=sort_key_relevance)[0].key == longer.key

    def test_fully_tied_scores_break_on_price_then_key(self, make_listing) -> None:
        # Same date and symmetric deviation -> identical scores.
        cheap = score_listing(make_listing("C", price=480_000, listed_date="2026-09-01"), TARGET, TODAY)
        dear = score_listing(make_listing("D", price=520_000, listed_date="2026-09-01"), TARGET, TODAY)
        assert cheap.relevance_score == dear.relevance_score
        assert sorted([dear, cheap], key=sort_key_relevance)[0].key == cheap.key

    def test_ordering_is_stable_regardless_of_input_order(self, make_listing) -> None:
        """The property that actually matters: without a total order, equal
        rows can swap between requests and appear on two different pages."""
        listings = [
            make_listing("A", source="MLS_A", price=TARGET, listed_date="2026-09-01"),
            make_listing("B", source="MLS_B", price=TARGET, listed_date="2026-09-01"),
            make_listing("C", source="MLS_C", price=TARGET, listed_date="2026-09-01"),
        ]
        scored = [score_listing(l, TARGET, TODAY) for l in listings]
        assert len({s.relevance_score for s in scored}) == 1  # all tied

        forward = [s.key for s in sorted(scored, key=sort_key_relevance)]
        backward = [s.key for s in sorted(reversed(scored), key=sort_key_relevance)]
        assert forward == backward
