"""Pagination boundaries.

The cases that actually break in production: the exact-multiple boundary, the
short final page, and a page past the end. Structurally invalid input (page 0,
negative page size) never reaches this module — it is rejected at the edge by
`SearchParams` — so it is covered in the validation suite instead.
"""

from __future__ import annotations

import pytest

from app.pagination import paginate

ITEMS = list(range(1, 13))  # 12 items, matching the sample dataset size


class TestPageSlicing:
    def test_first_page(self) -> None:
        items, info = paginate(ITEMS, page=1, page_size=5)
        assert items == [1, 2, 3, 4, 5]
        assert (info.page, info.total, info.total_pages) == (1, 12, 3)

    def test_middle_page(self) -> None:
        items, _ = paginate(ITEMS, page=2, page_size=5)
        assert items == [6, 7, 8, 9, 10]

    def test_final_page_is_short_not_padded(self) -> None:
        items, info = paginate(ITEMS, page=3, page_size=5)
        assert items == [11, 12]
        assert info.total == 12  # total counts matches, not the page length

    def test_page_size_larger_than_the_result_set(self) -> None:
        items, info = paginate(ITEMS, page=1, page_size=100)
        assert items == ITEMS
        assert info.total_pages == 1

    def test_page_size_of_one(self) -> None:
        items, info = paginate(ITEMS, page=7, page_size=1)
        assert items == [7]
        assert info.total_pages == 12


class TestBoundaries:
    def test_exact_multiple_produces_no_trailing_empty_page(self) -> None:
        """12 items at 4 per page is exactly 3 pages, not 4."""
        _, info = paginate(ITEMS, page=1, page_size=4)
        assert info.total_pages == 3

    def test_one_over_a_multiple_adds_a_page(self) -> None:
        _, info = paginate(ITEMS + [13], page=1, page_size=4)
        assert info.total_pages == 4

    def test_page_past_the_end_is_empty_not_an_error(self) -> None:
        """Returning accurate totals lets the UI clamp and recover."""
        items, info = paginate(ITEMS, page=99, page_size=5)
        assert items == []
        assert info.total == 12
        assert info.total_pages == 3

    def test_empty_result_set_reports_zero_pages(self) -> None:
        items, info = paginate([], page=1, page_size=10)
        assert items == []
        assert (info.total, info.total_pages) == (0, 0)


class TestPageWalkIsLossless:
    @pytest.mark.parametrize("page_size", [1, 2, 3, 4, 5, 7, 12, 13])
    def test_walking_every_page_yields_each_item_exactly_once(self, page_size: int) -> None:
        """The property that matters most: no item lost, none duplicated.

        A drifting sort or an off-by-one in the slice shows up here as a
        missing or repeated row across the walk.
        """
        _, info = paginate(ITEMS, page=1, page_size=page_size)
        seen: list[int] = []
        for page in range(1, info.total_pages + 1):
            page_items, _ = paginate(ITEMS, page=page, page_size=page_size)
            seen.extend(page_items)
        assert seen == ITEMS
