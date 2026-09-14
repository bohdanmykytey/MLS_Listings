"""Pagination over an already-sorted result set. A page past the end is an
empty page with accurate totals, not an error."""

from __future__ import annotations

import math
from typing import TypeVar

from .models import PageInfo

T = TypeVar("T")


def paginate(items: list[T], page: int, page_size: int) -> tuple[list[T], PageInfo]:
    """Slice one page out of an ordered list, with totals to navigate by."""
    total = len(items)
    total_pages = math.ceil(total / page_size) if total else 0
    start = (page - 1) * page_size
    return items[start : start + page_size], PageInfo(
        page=page, pageSize=page_size, total=total, totalPages=total_pages
    )
