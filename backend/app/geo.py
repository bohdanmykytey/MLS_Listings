"""Geographic distance helpers. Unwired: no requirement asks for radius
search, but great-circle distance is easy to get subtly wrong, so it's ready
here — wiring it up later is a `SearchParams` field plus one filter, not new
logic."""

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
    """Is a listing inside the search radius? Boundary inclusive."""
    return (
        haversine_miles(listing_lat, listing_lng, center_lat, center_lng) <= radius_miles
    )
