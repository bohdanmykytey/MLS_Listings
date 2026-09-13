"""Pagination over an already-sorted result set.

Requesting a page past the end is not an error: it returns an empty page with
an accurate `total`/`totalPages` so the UI can clamp and recover. Only
structurally invalid input (page < 1, pageSize <= 0) is rejected, and that
happens at the edge in `SearchParams`.
"""

from __future__ import annotations

import math
from typing import TypeVar

from .models import PageInfo

T = TypeVar("T")


def paginate(items: list[T], page: int, page_size: int) -> tuple[list[T], PageInfo]:
    total = len(items)
    total_pages = math.ceil(total / page_size) if total else 0
    start = (page - 1) * page_size
    return items[start : start + page_size], PageInfo(
        page=page, pageSize=page_size, total=total, totalPages=total_pages
    )
