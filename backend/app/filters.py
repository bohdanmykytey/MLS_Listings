"""Filtering — pure functions over a list of listings.

Each predicate is separate and independently testable; `apply_filters` is just
their conjunction. Filters narrow the candidate set only — they never influence
rank, which is `scoring.py`'s job.
"""

from __future__ import annotations

from .models import Listing, SearchParams


def matches_price(listing: Listing, min_price: float | None, max_price: float | None) -> bool:
    """Is the price inside the requested window?

    Both bounds are inclusive and independently optional, so a user can set a
    floor, a ceiling, both, or neither. `None` means unbounded rather than
    zero — otherwise an empty input box would silently exclude everything.
    """
    if min_price is not None and listing.price < min_price:
        return False
    if max_price is not None and listing.price > max_price:
        return False
    return True


def matches_bedrooms(listing: Listing, min_bedrooms: int | None) -> bool:
    """Does the listing meet the bedroom minimum?

    Inclusive: asking for 3 bedrooms returns 3-bedroom homes. Separate from the
    price predicate so each filter can be tested and changed in isolation.
    """
    return min_bedrooms is None or listing.bedrooms >= min_bedrooms


def matches_city(listing: Listing, city: str | None) -> bool:
    """Case- and whitespace-insensitive exact match.

    Deliberately not a substring match: "Fair" should not return "Fairfax"
    results the user didn't ask for. Feed inconsistencies in city spelling are
    a known limitation, documented in the README.
    """
    if city is None:
        return True
    return listing.city.strip().casefold() == city.strip().casefold()


def matches_keyword(listing: Listing, keyword: str | None) -> bool:
    """Case-insensitive substring match against the description.

    Known limitation: this is lexical, not semantic, so a search for "pets"
    also matches "no pets". Called out in the README rather than papered over.
    """
    if keyword is None:
        return True
    return keyword.casefold() in listing.description.casefold()


def apply_filters(listings: list[Listing], params: SearchParams) -> list[Listing]:
    """Narrow the corpus to the listings matching every active filter.

    The conjunction of the predicates above — filters are ANDed, since a user
    adding a filter expects fewer results, not more. This stage only decides
    *membership*; how results are ordered is `scoring.py`'s concern, and keeping
    the two apart is why either can change without touching the other.
    """
    statuses = set(params.status) if params.status else None
    return [
        l
        for l in listings
        if matches_price(l, params.min_price, params.max_price)
        and matches_bedrooms(l, params.min_bedrooms)
        and matches_city(l, params.normalized_city)
        and matches_keyword(l, params.normalized_keyword)
        and (statuses is None or l.status in statuses)
    ]
