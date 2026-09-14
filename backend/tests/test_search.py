"""The search pipeline.

These tests are about *composition* — that filter, score, dedupe, sort and
paginate are applied in the right order with the right data flowing between
them. The individual steps have their own suites.
"""

from __future__ import annotations

from datetime import date

from app.search import search

TODAY = date(2026, 9, 11)


def run(listings, params_factory, **overrides):
    return search(listings, params_factory(**overrides), TODAY)


class TestPipelineOrder:
    def test_total_counts_matches_not_the_page_size(self, sample_listings, params) -> None:
        """Pagination must come last, or `total` would describe one page."""
        result = run(sample_listings, params, pageSize=5)
        assert result.page_info.total == 12
        assert len(result.items) == 5

    def test_filters_narrow_the_total(self, sample_listings, params) -> None:
        result = run(sample_listings, params, city="Springfield", pageSize=50)
        assert result.page_info.total == 4

    def test_scoring_happens_after_filtering(self, sample_listings, params) -> None:
        """Only surviving listings are scored, and all of them are."""
        result = run(sample_listings, params, city="Reston", pageSize=50)
        assert len(result.items) == 2
        assert all(i.relevance_score > 0 for i in result.items)

    def test_dedupe_runs_before_pagination(self, sample_listings, params) -> None:
        """Otherwise `total` would count duplicates the user never sees."""
        result = run(sample_listings, params, dedupe=True, pageSize=50)
        assert result.page_info.total == 8

    def test_dedupe_applies_after_filtering(self, sample_listings, params) -> None:
        # Springfield holds 4 records = 2 duplicate pairs.
        result = run(sample_listings, params, city="Springfield", dedupe=True, pageSize=50)
        assert result.page_info.total == 2

    def test_dedupe_off_by_default(self, sample_listings, params) -> None:
        assert run(sample_listings, params, pageSize=50).page_info.total == 12


class TestRanking:
    def test_results_are_ordered_by_score_descending(self, sample_listings, params) -> None:
        items = run(sample_listings, params, targetBudget=450_000, pageSize=50).items
        scores = [i.relevance_score for i in items]
        assert scores == sorted(scores, reverse=True)

    def test_target_budget_changes_the_ranking(self, sample_listings, params) -> None:
        cheap = run(sample_listings, params, targetBudget=400_000, pageSize=1).items[0]
        dear = run(sample_listings, params, targetBudget=600_000, pageSize=1).items[0]
        assert cheap.key != dear.key
        assert cheap.price < dear.price

    def test_without_a_budget_the_most_negotiable_listing_ranks_first(
        self, sample_listings, params
    ) -> None:
        """With no budget to match against, longest on market wins outright."""
        top = run(sample_listings, params, pageSize=1).items[0]
        assert top.listed_date == min(l.listed_date for l in sample_listings)

    def test_ranking_is_stable_across_identical_calls(self, sample_listings, params) -> None:
        first = [i.key for i in run(sample_listings, params, targetBudget=450_000, pageSize=50).items]
        second = [i.key for i in run(sample_listings, params, targetBudget=450_000, pageSize=50).items]
        assert first == second


class TestPagingThroughResults:
    def test_walking_every_page_visits_each_listing_exactly_once(
        self, sample_listings, params
    ) -> None:
        """End-to-end guard against the drifting-sort bug: with an unstable
        order, a listing can appear on two pages and another on none."""
        seen: list[str] = []
        total_pages = run(sample_listings, params, targetBudget=450_000, pageSize=5).page_info.total_pages
        for page in range(1, total_pages + 1):
            result = run(sample_listings, params, targetBudget=450_000, pageSize=5, page=page)
            seen.extend(i.key for i in result.items)
        assert len(seen) == 12
        assert len(set(seen)) == 12

    def test_page_past_the_end_returns_an_empty_page_with_real_totals(
        self, sample_listings, params
    ) -> None:
        result = run(sample_listings, params, page=99, pageSize=5)
        assert result.items == []
        assert result.page_info.total == 12
        assert result.page_info.total_pages == 3


class TestEmptyResults:
    def test_unmatched_city_is_an_empty_result_not_an_error(self, sample_listings, params) -> None:
        result = run(sample_listings, params, city="Atlantis")
        assert result.items == []
        assert result.page_info.total == 0
        assert result.page_info.total_pages == 0

    def test_impossible_price_window_returns_nothing(self, sample_listings, params) -> None:
        assert run(sample_listings, params, minPrice=10_000_000, maxPrice=20_000_000).items == []

    def test_searching_an_empty_dataset_does_not_crash(self, params) -> None:
        result = search([], params(), TODAY)
        assert result.items == []
        assert result.page_info.total == 0


class TestAppliedEcho:
    def test_applied_reports_what_the_server_actually_used(self, sample_listings, params) -> None:
        """Echoing the effective filters makes a surprising result set
        self-diagnosing rather than a guessing game."""
        result = run(sample_listings, params, city="  Reston  ", keyword="  pool  ", minPrice=1)
        assert result.applied["city"] == "Reston"      # trimmed
        assert result.applied["keyword"] == "pool"
        assert result.applied["referenceDate"] == TODAY.isoformat()

    def test_blank_filters_echo_as_absent(self, sample_listings, params) -> None:
        result = run(sample_listings, params, city="   ")
        assert result.applied["city"] is None
