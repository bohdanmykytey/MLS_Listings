"""The search pipeline: filter -> dedupe -> score -> sort -> paginate.

Order is load-bearing: filter first (scoring is the expensive stage), dedupe
before score (it rewrites listed_date, a scoring input), sort before paginate
(pages must slice a stable order), paginate last (`total` counts matches).
"""

from __future__ import annotations

from datetime import date

from .dedupe import collapse_duplicates
from .filters import apply_filters
from .models import Listing, SearchParams, SearchResponse
from .pagination import paginate
from .scoring import score_listing, sort_key_relevance


def _describe(params: SearchParams, reference_date: date) -> dict[str, object]:
    """What the server actually applied, echoed back so a surprising result
    is self-diagnosing. Derived from the model so a new filter can't be
    forgotten here."""
    return {
        **params.model_dump(by_alias=True, mode="json"),
        "city": params.normalized_city,
        "keyword": params.normalized_keyword,
        "referenceDate": reference_date.isoformat(),
    }


def search(
    listings: list[Listing], params: SearchParams, reference_date: date
) -> SearchResponse:
    """Run a full search and return one page of ranked results. Pure — no
    I/O, no framework types — so it's testable without a server."""
    matched = apply_filters(listings, params)

    if params.dedupe:
        matched = collapse_duplicates(matched)

    scored = [score_listing(l, params.target_budget, reference_date) for l in matched]
    ranked = sorted(scored, key=sort_key_relevance)

    page_items, page_info = paginate(ranked, params.page, params.page_size)

    return SearchResponse(
        items=page_items,
        pageInfo=page_info,
        applied=_describe(params, reference_date),
    )
