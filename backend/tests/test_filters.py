"""Filtering.

Each predicate is tested in isolation, then in combination. Bounds are checked
for inclusivity explicitly: "min" and "max" that quietly exclude the boundary
value are a classic source of wrong-but-plausible results.
"""

from __future__ import annotations

import pytest

from app.filters import (
    apply_filters,
    matches_bedrooms,
    matches_city,
    matches_keyword,
    matches_price,
)
from app.models import ListingStatus


class TestPriceFilter:
    @pytest.mark.parametrize(
        "price,lo,hi,expected",
        [
            (500_000, 400_000, 600_000, True),
            (400_000, 400_000, 600_000, True),   # lower bound inclusive
            (600_000, 400_000, 600_000, True),   # upper bound inclusive
            (399_999, 400_000, 600_000, False),
            (600_001, 400_000, 600_000, False),
            (500_000, None, None, True),         # no bounds -> no filtering
            (500_000, 400_000, None, True),      # min only
            (300_000, 400_000, None, False),
            (500_000, None, 400_000, False),     # max only
        ],
    )
    def test_price_bounds(self, make_listing, price, lo, hi, expected) -> None:
        assert matches_price(make_listing(price=price), lo, hi) is expected


class TestBedroomsFilter:
    @pytest.mark.parametrize(
        "bedrooms,minimum,expected",
        [(3, 3, True), (4, 3, True), (2, 3, False), (3, None, True), (0, 0, True)],
    )
    def test_bedrooms_is_an_inclusive_minimum(self, make_listing, bedrooms, minimum, expected) -> None:
        assert matches_bedrooms(make_listing(bedrooms=bedrooms), minimum) is expected


class TestCityFilter:
    @pytest.mark.parametrize("query", ["Reston", "reston", "RESTON", "  Reston  "])
    def test_city_match_ignores_case_and_surrounding_whitespace(self, make_listing, query) -> None:
        assert matches_city(make_listing(city="Reston"), query) is True

    def test_city_is_exact_not_substring(self, make_listing) -> None:
        """Deliberate: "Fair" must not return Fairfax results nobody asked for."""
        assert matches_city(make_listing(city="Fairfax"), "Fair") is False

    def test_no_city_means_no_filtering(self, make_listing) -> None:
        assert matches_city(make_listing(city="Vienna"), None) is True


class TestKeywordFilter:
    @pytest.mark.parametrize("query", ["garage", "GARAGE", "Garage"])
    def test_keyword_match_is_case_insensitive(self, make_listing, query) -> None:
        listing = make_listing(description="Townhome with 2-car garage.")
        assert matches_keyword(listing, query) is True

    def test_keyword_matches_partial_words(self, make_listing) -> None:
        assert matches_keyword(make_listing(description="Renovated kitchen"), "renov") is True

    def test_absent_keyword_does_not_match(self, make_listing) -> None:
        assert matches_keyword(make_listing(description="Cozy starter home"), "pool") is False

    def test_no_keyword_means_no_filtering(self, make_listing) -> None:
        assert matches_keyword(make_listing(description="anything"), None) is True

    def test_known_limitation_lexical_match_ignores_negation(self, make_listing) -> None:
        """Pinned deliberately: searching "pets" also returns "no pets".

        This is documented behaviour, not an accident. Five sample descriptions
        mention pets and three do so negatively. Fixing it properly needs
        negation-aware matching, which is out of scope; this test exists so the
        limitation is visible and any future fix has to change it on purpose.
        """
        assert matches_keyword(make_listing(description="Cozy home, no pets."), "pets") is True


class TestApplyFilters:
    def test_no_filters_returns_everything(self, sample_listings, params) -> None:
        assert len(apply_filters(sample_listings, params())) == len(sample_listings)

    def test_filters_combine_as_and_not_or(self, sample_listings, params) -> None:
        both = apply_filters(sample_listings, params(city="Springfield", minBedrooms=3))
        assert {l.city for l in both} == {"Springfield"}
        assert all(l.bedrooms >= 3 for l in both)

    def test_impossible_combination_returns_empty_not_an_error(self, sample_listings, params) -> None:
        result = apply_filters(sample_listings, params(city="Reston", minBedrooms=99))
        assert result == []

    def test_unknown_city_returns_empty(self, sample_listings, params) -> None:
        assert apply_filters(sample_listings, params(city="Atlantis")) == []

    def test_blank_strings_are_treated_as_absent_filters(self, sample_listings, params) -> None:
        """An empty input box must mean "no filter", never "match nothing"."""
        blank = apply_filters(sample_listings, params(city="   ", keyword="  "))
        assert len(blank) == len(sample_listings)

    def test_status_is_unfiltered_by_default(self, sample_listings, params) -> None:
        # The brief never asks to hide the single `pending` listing.
        result = apply_filters(sample_listings, params())
        assert any(l.status == ListingStatus.PENDING for l in result)

    def test_status_filter_narrows_when_supplied(self, sample_listings, params) -> None:
        active = apply_filters(sample_listings, params(status=["active"]))
        assert len(active) == 11
        assert all(l.status == ListingStatus.ACTIVE for l in active)

    def test_status_filter_accepts_multiple_values(self, sample_listings, params) -> None:
        both = apply_filters(sample_listings, params(status=["active", "pending"]))
        assert len(both) == 12

    def test_filtering_does_not_mutate_the_source_list(self, sample_listings, params) -> None:
        before = len(sample_listings)
        apply_filters(sample_listings, params(city="Reston"))
        assert len(sample_listings) == before
