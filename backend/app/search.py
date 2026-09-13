"""The search pipeline: filter -> score -> dedupe -> sort -> paginate.

Order matters and is deliberate:

  filter before score    scoring is the expensive step; no point ranking rows
                         the user excluded.
  dedupe after score     the survivor keeps its own already-correct score, and
                         `mergedFrom` can be reported on the row the user sees.
  sort before paginate   pagination must slice a totally-ordered list, or rows
                         drift between pages.
  paginate last          `total` must count matches, not the page.

This function is pure: it takes the listings and the params and returns a
response. No I/O, no framework types — so it is testable without a server.
"""

from __future__ import annotations

from datetime import date

from . import dedupe as dedupe_mod
from .filters import apply_filters
from .models import Listing, ScoredListing, SearchParams, SearchResponse
from .pagination import paginate
from .scoring import score_listing, sort_key_relevance


def _sort(items: list[ScoredListing], sort: str) -> list[ScoredListing]:
    if sort == "priceAsc":
        return sorted(items, key=lambda i: (i.price, i.key))
    if sort == "priceDesc":
        return sorted(items, key=lambda i: (-i.price, i.key))
    if sort == "newest":
        return sorted(items, key=lambda i: (-i.listed_date.toordinal(), i.key))
    return sorted(items, key=sort_key_relevance)


def search(
    listings: list[Listing], params: SearchParams, reference_date: date
) -> SearchResponse:
    matched = apply_filters(listings, params)
    scored = [score_listing(l, params.target_budget, reference_date) for l in matched]
    ranked = _sort(scored, params.sort)

    if params.dedupe:
        ranked = dedupe_mod.collapse_duplicates(ranked)

    page_items, page_info = paginate(ranked, params.page, params.page_size)

    return SearchResponse(
        items=page_items,
        pageInfo=page_info,
        applied={
            "minPrice": params.min_price,
            "maxPrice": params.max_price,
            "minBedrooms": params.min_bedrooms,
            "city": params.normalized_city,
            "keyword": params.normalized_keyword,
            "targetBudget": params.target_budget,
            "status": [s.value for s in params.status] if params.status else None,
            "dedupe": params.dedupe,
            "sort": params.sort,
            "referenceDate": reference_date.isoformat(),
        },
    )
