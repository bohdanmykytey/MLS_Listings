"""Geographic distance helpers.

Every listing carries latitude/longitude, but no stated requirement uses them.
This module implements the part that is easy to get subtly wrong (great-circle
distance) so that adding a radius search later is a wiring change, not a
research task:

  1. add `lat`, `lng`, `radiusMiles` to `SearchParams` (validated as a group —
     all three or none),
  2. add `within_radius(...)` to the conjunction in `filters.apply_filters`.

Intentionally not exposed as a query parameter yet: the handout doesn't ask
for it, and shipping an untested public parameter is worse than shipping none.
"""

from __future__ import annotations

import math

EARTH_RADIUS_MILES = 3958.7613


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def within_radius(
    listing_lat: float,
    listing_lng: float,
    center_lat: float,
    center_lng: float,
    radius_miles: float,
) -> bool:
    return (
        haversine_miles(listing_lat, listing_lng, center_lat, center_lng) <= radius_miles
    )
