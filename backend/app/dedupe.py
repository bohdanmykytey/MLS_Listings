"""Cross-source duplicate collapsing.

The same physical property arrives from multiple feeds with cosmetic
differences. In the sample data, four pairs are the same home:

    A1  "123 Main St, Apt 4B"     $450,000  <->  B7  "123 Main Street, Unit 4B"  $452,000
    A2  "456 Oak Ave"   zip 22150 <->  B8  "456 Oak Avenue"  zip 22151
    A3  "789 Pine Rd"   $399,000  <->  B9  "789 Pine Rd"     $399,500
    A5  "55 Elm Ct"     $470,000  <->  B11 "55 Elm Court"    $465,000

Matching strategy — geometry first, text second. Address strings are explicitly
not normalized ("St" vs "Street", "Apt" vs "Unit") and zip codes disagree
between feeds, so text alone is fragile. Coordinates plus the physical facts of
the building are the stable signal, so the cluster key is:

    (lat rounded to ~11m, lng rounded to ~11m, bedrooms, sqft)

Two records that agree on all four are the same building. Price and listedDate
are deliberately excluded from the key: those are exactly the fields feeds
disagree on.

Survivor choice: the most recently listed record wins, since it carries the
freshest price. Ties break on source then key so the result is deterministic.
The absorbed keys are reported in `mergedFrom` so the UI can show that a row
represents several feed records, and nothing is silently discarded.

Off by default (`?dedupe=true`), because the handout's stated requirements
describe searching the raw feed union; collapsing by default would change
result counts the spec implies.
"""

from __future__ import annotations

from collections import defaultdict

from .models import ScoredListing

# 4 decimal places of latitude is ~11m — tight enough that neighbouring houses
# stay distinct, loose enough to absorb feed-level coordinate jitter.
COORD_PRECISION = 4


def cluster_key(listing: ScoredListing) -> tuple:
    return (
        round(listing.latitude, COORD_PRECISION),
        round(listing.longitude, COORD_PRECISION),
        listing.bedrooms,
        listing.sqft,
    )


def _survivor_rank(listing: ScoredListing) -> tuple:
    """Newest first, then a stable tie-break."""
    return (-listing.listed_date.toordinal(), listing.source, listing.key)


def collapse_duplicates(listings: list[ScoredListing]) -> list[ScoredListing]:
    """Collapse same-property records, preserving the input ordering.

    Returns one record per cluster with `mergedFrom` listing the keys it
    absorbed. Scores are not recomputed: the survivor keeps its own score,
    which is already correct for its own price and date.
    """
    clusters: dict[tuple, list[ScoredListing]] = defaultdict(list)
    for listing in listings:
        clusters[cluster_key(listing)].append(listing)

    survivors: dict[str, ScoredListing] = {}
    for group in clusters.values():
        best, *absorbed = sorted(group, key=_survivor_rank)
        survivors[best.key] = best.model_copy(
            update={"merged_from": sorted(l.key for l in absorbed)}
        )

    # Preserve the caller's ordering rather than the cluster iteration order.
    return [survivors[l.key] for l in listings if l.key in survivors]
