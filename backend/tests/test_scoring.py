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
    BUDGET_CUTOFF,
    BUDGET_TOLERANCE,
    BUDGET_WEIGHT,
    RECENCY_HALF_LIFE_DAYS,
    RECENCY_WEIGHT,
    budget_fit,
    recency,
    score_listing,
    sort_key_relevance,
)

TODAY = date(2026, 9, 11)
TARGET = 500_000.0


class TestBudgetFit:
    def test_exact_target_is_a_perfect_fit(self) -> None:
        assert budget_fit(TARGET, TARGET) == 1.0

    @pytest.mark.parametrize("price", [475_000, 500_000, 525_000])
    def test_anything_inside_the_tolerance_band_is_a_perfect_fit(self, price: float) -> None:
        # +/-5% of 500k is 475k-525k.
        assert budget_fit(price, TARGET) == 1.0

    def test_tolerance_edge_is_inclusive(self) -> None:
        edge = TARGET * (1 + BUDGET_TOLERANCE)
        assert budget_fit(edge, TARGET) == 1.0

    @pytest.mark.parametrize("price", [250_000, 750_000])
    def test_fit_is_zero_at_and_beyond_the_cutoff(self, price: float) -> None:
        # +/-50% of 500k is 250k / 750k.
        assert budget_fit(price, TARGET) == 0.0

    def test_fit_never_goes_negative_however_far_off(self) -> None:
        assert budget_fit(50_000_000, TARGET) == 0.0

    def test_penalty_is_symmetric_around_the_target(self) -> None:
        """A home 30% under budget fits exactly as well as one 30% over.

        This is the deliberate design call: buyers shop a band, not a ceiling,
        so being far under target is also a poor match. Rewarding anything
        cheaper would rank a studio above the house the user actually wants.
        """
        under = budget_fit(TARGET * 0.70, TARGET)
        over = budget_fit(TARGET * 1.30, TARGET)
        assert under == pytest.approx(over)
        assert 0.0 < under < 1.0

    def test_fit_decays_monotonically_as_price_moves_away(self) -> None:
        deviations = [0.10, 0.20, 0.30, 0.40]
        fits = [budget_fit(TARGET * (1 + d), TARGET) for d in deviations]
        assert fits == sorted(fits, reverse=True)

    def test_decay_is_linear_between_tolerance_and_cutoff(self) -> None:
        midpoint = (BUDGET_TOLERANCE + BUDGET_CUTOFF) / 2
        assert budget_fit(TARGET * (1 + midpoint), TARGET) == pytest.approx(0.5)

    @pytest.mark.parametrize("target", [None, 0.0, -1.0])
    def test_missing_or_nonsensical_target_yields_no_fit(self, target: float | None) -> None:
        # Guards the formula against division by zero; the API rejects
        # non-positive budgets before they reach here.
        assert budget_fit(400_000, target) == 0.0


class TestRecency:
    def test_listed_today_scores_one(self) -> None:
        assert recency(TODAY, TODAY) == 1.0

    def test_one_half_life_scores_exactly_one_half(self) -> None:
        older = date.fromordinal(TODAY.toordinal() - int(RECENCY_HALF_LIFE_DAYS))
        assert recency(older, TODAY) == pytest.approx(0.5)

    def test_two_half_lives_score_one_quarter(self) -> None:
        older = date.fromordinal(TODAY.toordinal() - int(RECENCY_HALF_LIFE_DAYS * 2))
        assert recency(older, TODAY) == pytest.approx(0.25)

    def test_future_dated_listing_clamps_to_one_rather_than_exceeding_it(self) -> None:
        """Feed clock skew must not produce a score above 100."""
        future = date.fromordinal(TODAY.toordinal() + 30)
        assert recency(future, TODAY) == 1.0

    def test_recency_is_always_within_bounds(self) -> None:
        for age in (0, 1, 30, 365, 10_000):
            value = recency(date.fromordinal(TODAY.toordinal() - age), TODAY)
            assert 0.0 <= value <= 1.0

    def test_recency_decays_monotonically_with_age(self) -> None:
        scores = [recency(date.fromordinal(TODAY.toordinal() - a), TODAY) for a in (0, 10, 20, 30)]
        assert scores == sorted(scores, reverse=True)


class TestScoreListing:
    def test_perfect_listing_scores_one_hundred(self, make_listing) -> None:
        listing = make_listing(price=TARGET, listed_date=TODAY.isoformat())
        assert score_listing(listing, TARGET, TODAY).relevance_score == 100.0

    def test_worst_listing_scores_zero(self, make_listing) -> None:
        """Beyond the budget cutoff and old enough for recency to vanish."""
        ancient = date.fromordinal(TODAY.toordinal() - 3650).isoformat()
        listing = make_listing(price=TARGET * 5, listed_date=ancient)
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
        # Perfect fit, exactly one half-life old -> 100*(0.6*1 + 0.4*0.5).
        older = date.fromordinal(TODAY.toordinal() - int(RECENCY_HALF_LIFE_DAYS))
        listing = make_listing(price=TARGET, listed_date=older.isoformat())
        expected = 100 * (BUDGET_WEIGHT * 1.0 + RECENCY_WEIGHT * 0.5)
        assert score_listing(listing, TARGET, TODAY).relevance_score == pytest.approx(expected)

    def test_breakdown_explains_the_score(self, make_listing) -> None:
        listing = make_listing(price=TARGET, listed_date=TODAY.isoformat())
        scored = score_listing(listing, TARGET, TODAY)
        b = scored.score_breakdown
        recomputed = 100 * (b.budget_weight * b.budget_fit + b.recency_weight * b.recency)
        assert recomputed == pytest.approx(scored.relevance_score, abs=0.01)


class TestNoTargetBudget:
    """Without a budget the score must stay on the same 0-100 scale."""

    def test_weights_renormalize_so_recency_carries_everything(self, make_listing) -> None:
        listing = make_listing(listed_date=TODAY.isoformat())
        scored = score_listing(listing, None, TODAY)
        assert scored.score_breakdown.budget_weight == 0.0
        assert scored.score_breakdown.recency_weight == 1.0

    def test_newest_listing_still_reaches_one_hundred(self, make_listing) -> None:
        # Without renormalization this would cap at 40 (the recency weight).
        listing = make_listing(listed_date=TODAY.isoformat())
        assert score_listing(listing, None, TODAY).relevance_score == 100.0

    def test_price_is_irrelevant_when_no_budget_is_given(self, make_listing) -> None:
        cheap = make_listing("C", price=100_000, listed_date=TODAY.isoformat())
        dear = make_listing("D", price=9_000_000, listed_date=TODAY.isoformat())
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
        scored = [score_listing(l, 418_000.0, TODAY) for l in sample_listings]
        by_key = {s.key: s for s in scored}
        assert by_key["MLS_B:B7"].relevance_score == by_key["MLS_A:A5"].relevance_score

    def test_a_real_tie_is_ordered_deterministically(self, sample_listings) -> None:
        """Both tied listings are returned and both keep their score; only
        their relative order is decided. A5 is newer, so it ranks first."""
        scored = sorted(
            (score_listing(l, 418_000.0, TODAY) for l in sample_listings),
            key=sort_key_relevance,
        )
        keys = [s.key for s in scored]
        assert keys.index("MLS_A:A5") < keys.index("MLS_B:B7")

    def test_a_real_tie_survives_input_reordering(self, sample_listings) -> None:
        """The property that matters: the output order must come from the data,
        not from the order the repository happened to return rows in."""
        forward = [
            s.key
            for s in sorted(
                (score_listing(l, 418_000.0, TODAY) for l in sample_listings),
                key=sort_key_relevance,
            )
        ]
        backward = [
            s.key
            for s in sorted(
                (score_listing(l, 418_000.0, TODAY) for l in reversed(sample_listings)),
                key=sort_key_relevance,
            )
        ]
        assert forward == backward

    def test_identical_listings_produce_identical_scores(self, make_listing) -> None:
        a = score_listing(make_listing("A", price=TARGET), TARGET, TODAY)
        b = score_listing(make_listing("B", price=TARGET), TARGET, TODAY)
        assert a.relevance_score == b.relevance_score

    def test_tie_breaks_on_recency_first(self, make_listing) -> None:
        # Both sit inside the tolerance band, so budget_fit ties at 1.0.
        older = score_listing(make_listing("O", price=490_000, listed_date="2026-09-01"), TARGET, TODAY)
        newer = score_listing(make_listing("N", price=510_000, listed_date="2026-09-05"), TARGET, TODAY)
        assert sorted([older, newer], key=sort_key_relevance)[0].key == newer.key

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
