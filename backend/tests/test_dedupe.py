"""Cross-source duplicate collapsing.

Verified against the real sample data, which contains exactly four duplicate
pairs, because that is the dataset a reviewer will run against. The pairs
differ in address formatting, price, listing date, and in one case zip code —
which is precisely why the cluster key uses geometry rather than text.
"""

from __future__ import annotations

from datetime import date

from app.dedupe import cluster_key, collapse_duplicates
from app.scoring import score_listing

TODAY = date(2026, 9, 11)

# The pairs planted in sample_listings.json: (survivor, absorbed).
KNOWN_PAIRS = [
    ("MLS_A:A1", "MLS_B:B7"),   # "123 Main St, Apt 4B" / "123 Main Street, Unit 4B"
    ("MLS_A:A2", "MLS_B:B8"),   # zip 22150 vs 22151
    ("MLS_A:A3", "MLS_B:B9"),   # same address, $500 apart
    ("MLS_A:A5", "MLS_B:B11"),  # "55 Elm Ct" / "55 Elm Court"
]


def _score_all(listings, target=None):
    return [score_listing(l, target, TODAY) for l in listings]


class TestClusterKey:
    def test_known_duplicates_share_a_cluster_key(self, sample_listings) -> None:
        scored = {s.key: s for s in _score_all(sample_listings)}
        for survivor, absorbed in KNOWN_PAIRS:
            assert cluster_key(scored[survivor]) == cluster_key(scored[absorbed])

    def test_distinct_properties_do_not_share_a_cluster_key(self, sample_listings) -> None:
        scored = _score_all(sample_listings)
        keys = [cluster_key(s) for s in scored]
        assert len(set(keys)) == 8  # 12 records, 4 duplicate pairs

    def test_key_ignores_price_and_date(self, make_listing) -> None:
        """The fields feeds disagree on must not affect clustering."""
        a = score_listing(make_listing("A", price=450_000, listed_date="2026-08-01"), None, TODAY)
        b = score_listing(make_listing("B", price=452_000, listed_date="2026-09-01"), None, TODAY)
        assert cluster_key(a) == cluster_key(b)

    def test_key_separates_different_bedroom_counts_at_the_same_address(self, make_listing) -> None:
        """Two units in one building share coordinates but are not the same home."""
        a = score_listing(make_listing("A", bedrooms=2), None, TODAY)
        b = score_listing(make_listing("B", bedrooms=3), None, TODAY)
        assert cluster_key(a) != cluster_key(b)

    def test_tiny_coordinate_jitter_still_clusters(self, make_listing) -> None:
        # ~1m apart: feed-level rounding noise, not a different building.
        a = score_listing(make_listing("A", latitude=38.90120), None, TODAY)
        b = score_listing(make_listing("B", latitude=38.901203), None, TODAY)
        assert cluster_key(a) == cluster_key(b)


class TestCollapse:
    def test_twelve_records_collapse_to_eight_properties(self, sample_listings) -> None:
        assert len(collapse_duplicates(_score_all(sample_listings))) == 8

    def test_the_newest_record_survives_each_pair(self, sample_listings) -> None:
        survivors = {s.key for s in collapse_duplicates(_score_all(sample_listings))}
        for survivor, absorbed in KNOWN_PAIRS:
            assert survivor in survivors
            assert absorbed not in survivors

    def test_merged_from_reports_what_was_absorbed(self, sample_listings) -> None:
        by_key = {s.key: s for s in collapse_duplicates(_score_all(sample_listings))}
        for survivor, absorbed in KNOWN_PAIRS:
            assert by_key[survivor].merged_from == [absorbed]

    def test_unique_listings_report_nothing_merged(self, sample_listings) -> None:
        collapsed = {s.key: s for s in collapse_duplicates(_score_all(sample_listings))}
        # A4, A6 and A7 have no counterpart in the other feed.
        for key in ("MLS_A:A4", "MLS_A:A6", "MLS_A:A7"):
            assert collapsed[key].merged_from == []

    def test_nothing_is_lost_every_input_is_kept_or_reported(self, sample_listings) -> None:
        """Dedupe must never silently drop a record."""
        scored = _score_all(sample_listings)
        collapsed = collapse_duplicates(scored)
        accounted = {s.key for s in collapsed} | {
            k for s in collapsed for k in s.merged_from
        }
        assert accounted == {s.key for s in scored}

    def test_input_ordering_is_preserved(self, sample_listings) -> None:
        """Dedupe runs after sorting, so it must not reshuffle the ranking."""
        scored = sorted(_score_all(sample_listings, 450_000), key=lambda s: -s.relevance_score)
        collapsed = collapse_duplicates(scored)
        order = [s.relevance_score for s in collapsed]
        assert order == sorted(order, reverse=True)

    def test_survivor_keeps_its_own_score(self, sample_listings) -> None:
        """Scores are not recomputed or blended: the survivor's score is
        already correct for its own price and date."""
        scored = {s.key: s for s in _score_all(sample_listings, 450_000)}
        collapsed = {s.key: s for s in collapse_duplicates(list(scored.values()))}
        for survivor, _ in KNOWN_PAIRS:
            assert collapsed[survivor].relevance_score == scored[survivor].relevance_score

    def test_empty_input_is_handled(self) -> None:
        assert collapse_duplicates([]) == []

    def test_collapsing_is_idempotent(self, sample_listings) -> None:
        once = collapse_duplicates(_score_all(sample_listings))
        twice = collapse_duplicates(once)
        assert [s.key for s in once] == [s.key for s in twice]

    def test_three_way_duplicate_collapses_to_one(self, make_listing) -> None:
        """A property appearing in three feeds, not just two."""
        scored = _score_all([
            make_listing("A", source="MLS_A", listed_date="2026-09-01"),
            make_listing("B", source="MLS_B", listed_date="2026-09-03"),
            make_listing("C", source="MLS_C", listed_date="2026-09-02"),
        ])
        collapsed = collapse_duplicates(scored)
        assert len(collapsed) == 1
        assert collapsed[0].key == "MLS_B:B"  # newest wins
        assert collapsed[0].merged_from == ["MLS_A:A", "MLS_C:C"]
