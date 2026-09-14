"""The search pipeline: filter -> dedupe -> score -> sort -> paginate.

This module composes the pure stages into the one operation the API exposes.
It exists so the ordering of those stages lives in a single readable place
instead of being implied by the shape of an endpoint handler.

The order is load-bearing:

  filter first           scoring is the expensive stage; there is no point
                         ranking rows the user excluded.
  dedupe before score    merging rewrites a record's effective listing date to
                         the earliest in its cluster, and that date feeds the
                         negotiability term — so dedupe changes an *input* to
                         the score and cannot run after one exists.
  sort before paginate   pagination must slice a totally-ordered list, or rows
                         drift between pages across independent requests.
  paginate last          `total` must count matches, not the length of a page.
"""

from __future__ import annotations

from datetime import date

from .dedupe import collapse_duplicates
from .filters import apply_filters
from .models import Listing, SearchParams, SearchResponse
from .pagination import paginate
from .scoring import score_listing, sort_key_relevance


def _describe(params: SearchParams, reference_date: date) -> dict[str, object]:
    """Report the filters the server actually applied.

    Echoed back so a surprising result set is self-diagnosing: the caller can
    see that a stray space was trimmed, or which reference date the
    days-on-market figures were measured against.

    Derived from the model rather than listed by hand, so adding a filter
    cannot leave this silently out of date. `city` and `keyword` are
    overridden with their normalized values, since those — not the raw
    strings the client sent — are what was actually applied.
    """
    return {
        **params.model_dump(by_alias=True, mode="json"),
        "city": params.normalized_city,
        "keyword": params.normalized_keyword,
        "referenceDate": reference_date.isoformat(),
    }


def search(
    listings: list[Listing], params: SearchParams, reference_date: date
) -> SearchResponse:
    """Run a full search and return one page of ranked results.

    Pure by design — it takes data and parameters and returns a value, with no
    I/O and no framework types — so the whole behaviour of the endpoint is
    testable without starting a server.
    """
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
