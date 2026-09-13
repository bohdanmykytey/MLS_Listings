"""Great-circle distance.

`geo.py` is not wired into any endpoint yet — it exists so that adding a radius
search is a wiring change rather than a research task. It is tested anyway,
because the value of a prepared seam is that it is already known to be correct.
"""

from __future__ import annotations

import pytest

from app.geo import haversine_miles, within_radius

# Two real sample listings, ~8.8 miles apart.
VIENNA = (38.9012, -77.2653)       # 55 Elm Ct
SPRINGFIELD = (38.7893, -77.1873)  # 123 Main St, Apt 4B


class TestHaversine:
    def test_zero_distance_to_itself(self) -> None:
        assert haversine_miles(*VIENNA, *VIENNA) == 0.0

    def test_known_distance_between_two_sample_listings(self) -> None:
        """8.80 miles, cross-checked against two independent formulas
        (spherical law of cosines and an equirectangular approximation),
        which agree to within 0.002 miles at this scale."""
        assert haversine_miles(*VIENNA, *SPRINGFIELD) == pytest.approx(8.80, abs=0.05)

    def test_one_degree_of_latitude_is_about_sixty_nine_miles(self) -> None:
        assert haversine_miles(38.0, -77.0, 39.0, -77.0) == pytest.approx(69.0, abs=0.5)

    def test_distance_is_symmetric(self) -> None:
        there = haversine_miles(*VIENNA, *SPRINGFIELD)
        back = haversine_miles(*SPRINGFIELD, *VIENNA)
        assert there == pytest.approx(back)

    def test_longitude_degrees_shrink_away_from_the_equator(self) -> None:
        """The reason naive euclidean distance on lat/lng is wrong."""
        at_equator = haversine_miles(0.0, 0.0, 0.0, 1.0)
        at_virginia = haversine_miles(38.0, -77.0, 38.0, -76.0)
        assert at_virginia < at_equator

    def test_antipodal_points_are_about_half_the_earths_circumference(self) -> None:
        assert haversine_miles(0.0, 0.0, 0.0, 180.0) == pytest.approx(12_437, abs=50)


class TestWithinRadius:
    def test_inside_the_radius(self) -> None:
        assert within_radius(*VIENNA, *SPRINGFIELD, 20.0) is True

    def test_outside_the_radius(self) -> None:
        assert within_radius(*VIENNA, *SPRINGFIELD, 5.0) is False

    def test_radius_boundary_is_inclusive(self) -> None:
        distance = haversine_miles(*VIENNA, *SPRINGFIELD)
        assert within_radius(*VIENNA, *SPRINGFIELD, distance) is True

    def test_zero_radius_matches_only_the_exact_point(self) -> None:
        assert within_radius(*VIENNA, *VIENNA, 0.0) is True
        assert within_radius(*VIENNA, *SPRINGFIELD, 0.0) is False
