"""Cross-source duplicate collapsing.

The same property arrives from both feeds with cosmetic differences (address
text, zip), so matching is geometry-first: cluster on rounded lat/lng +
bedrooms + sqft, not text. Survivor = newest record's details, but the
EARLIEST listed_date in the cluster, since that feeds the negotiability score.
Off by default (`?dedupe=true`) since the brief describes the raw feed union.
"""

from __future__ import annotations

from collections import defaultdict

from .models import Listing

# ~11m of latitude — tight enough to keep neighbouring houses distinct, loose
# enough to absorb feed-level coordinate jitter.
COORD_PRECISION = 4


def cluster_key(listing: Listing) -> tuple:
    """Identity of the physical property: coordinates + building facts."""
    return (
        round(listing.latitude, COORD_PRECISION),
        round(listing.longitude, COORD_PRECISION),
        listing.bedrooms,
        listing.sqft,
    )


def _survivor_rank(listing: Listing) -> tuple:
    """Newest record wins (freshest price/status); source+key breaks ties."""
    return (-listing.listed_date.toordinal(), listing.source, listing.key)


def collapse_duplicates(listings: list[Listing]) -> list[Listing]:
    """Collapse same-property records into one composite per property.

    details/price from the newest record; listed_date is the EARLIEST in the
    cluster (else a relist would erase real time-on-market); mergedFrom lists
    what was absorbed. Runs before scoring since it changes a scoring input.
    """
    clusters: dict[tuple, list[Listing]] = defaultdict(list)
    for listing in listings:
        clusters[cluster_key(listing)].append(listing)

    survivors: dict[str, Listing] = {}
    for group in clusters.values():
        best, *absorbed = sorted(group, key=_survivor_rank)
        survivors[best.key] = best.model_copy(
            update={
                "merged_from": sorted(l.key for l in absorbed),
                "listed_date": min(l.listed_date for l in group),
            }
        )

    # Preserve the caller's ordering, not cluster iteration order.
    return [survivors[l.key] for l in listings if l.key in survivors]
