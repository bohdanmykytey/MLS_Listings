"""Filtering — pure, independently-testable predicates. `apply_filters` is
their conjunction; they narrow the candidate set only, never affect rank."""

from __future__ import annotations

from .models import Listing, SearchParams


def matches_price(listing: Listing, min_price: float | None, max_price: float | None) -> bool:
    """Inclusive price window; either bound can be unset."""
    if min_price is not None and listing.price < min_price:
        return False
    if max_price is not None and listing.price > max_price:
        return False
    return True


def matches_bedrooms(listing: Listing, min_bedrooms: int | None) -> bool:
    """Inclusive bedroom minimum."""
    return min_bedrooms is None or listing.bedrooms >= min_bedrooms


def matches_city(listing: Listing, city: str | None) -> bool:
    """Case/whitespace-insensitive exact match, not substring — "Fair"
    should not also return "Fairfax"."""
    if city is None:
        return True
    return listing.city.strip().casefold() == city.strip().casefold()


def matches_keyword(listing: Listing, keyword: str | None) -> bool:
    """Case-insensitive substring match against the description. Lexical, not
    semantic — "pets" also matches "no pets"; a documented limitation."""
    if keyword is None:
        return True
    return keyword.casefold() in listing.description.casefold()


def apply_filters(listings: list[Listing], params: SearchParams) -> list[Listing]:
    """AND all active filters together."""
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
