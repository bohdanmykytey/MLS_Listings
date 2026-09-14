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

from .models import Listing

# 4 decimal places of latitude is ~11m — tight enough that neighbouring houses
# stay distinct, loose enough to absorb feed-level coordinate jitter.
COORD_PRECISION = 4


def cluster_key(listing: Listing) -> tuple:
    """Identity of the physical property a record describes.

    Coordinates plus the building's physical facts, because those are the only
    fields the feeds agree on. Records sharing this key are the same home.
    """
    return (
        round(listing.latitude, COORD_PRECISION),
        round(listing.longitude, COORD_PRECISION),
        listing.bedrooms,
        listing.sqft,
    )


def _survivor_rank(listing: Listing) -> tuple:
    """Newest record first, then a stable tie-break.

    The newest record wins because it carries the freshest price and status —
    but only its *details* survive, not its date. See `collapse_duplicates`.
    """
    return (-listing.listed_date.toordinal(), listing.source, listing.key)


def collapse_duplicates(listings: list[Listing]) -> list[Listing]:
    """Collapse same-property records into one composite per property.

    The result is deliberately a *composite*, not simply the best record:

      details and price   from the newest record, which is the freshest data
      listed date         the EARLIEST across the cluster, because that is when
                          the property actually came to market
      mergedFrom          the keys absorbed, so nothing vanishes silently

    The date rule matters because time on market drives the negotiability term.
    Taking the survivor's own date would let a property that has sat for months
    look brand new the moment a second feed picked it up — and would hand any
    seller a way to reset their days-on-market by relisting elsewhere.

    Runs before scoring for exactly that reason: it changes an input to the
    score, so it cannot run after one has been computed.
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

    # Preserve the caller's ordering rather than the cluster iteration order.
    return [survivors[l.key] for l in listings if l.key in survivors]
