"""The data-access seam and the injectable clock.

The repository is the boundary that keeps the search pipeline ignorant of
where listings come from. These tests hold that boundary honest, so swapping
the in-memory store for a database stays a one-class change.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.clock import REFERENCE_DATE_ENV, today
from app.repository import InMemoryListingRepository


class TestLoading:
    def test_loads_every_sample_listing(self, repository) -> None:
        assert len(repository.list_all()) == 12

    def test_parses_typed_fields_not_raw_strings(self, repository) -> None:
        listing = repository.get("MLS_A", "A1")
        assert isinstance(listing.listed_date, date)
        assert isinstance(listing.price, float)
        assert isinstance(listing.bedrooms, int)

    def test_rejects_a_file_that_is_not_a_json_array(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"id": "A1"}))
        with pytest.raises(ValueError, match="JSON array"):
            InMemoryListingRepository.from_json_file(bad)

    def test_rejects_listings_missing_required_fields(self, tmp_path: Path) -> None:
        """A malformed feed must fail loudly at startup, not silently serve
        half a dataset."""
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps([{"id": "A1", "source": "MLS_A"}]))
        with pytest.raises(Exception):
            InMemoryListingRepository.from_json_file(bad)


class TestCompositeKeying:
    def test_listings_are_addressed_by_source_and_id(self, repository) -> None:
        assert repository.get("MLS_A", "A1") is not None
        assert repository.get("MLS_B", "A1") is None

    def test_missing_listing_returns_none_rather_than_raising(self, repository) -> None:
        assert repository.get("MLS_Z", "nope") is None

    def test_same_id_from_two_sources_coexist(self, make_listing) -> None:
        """The reason a composite key exists at all."""
        repo = InMemoryListingRepository([
            make_listing("A1", source="MLS_A"),
            make_listing("A1", source="MLS_B"),
        ])
        assert len(repo.list_all()) == 2
        assert repo.get("MLS_A", "A1") != repo.get("MLS_B", "A1")


class TestDerivedData:
    def test_cities_are_deduplicated_and_sorted(self, repository) -> None:
        cities = repository.cities()
        assert cities == sorted(set(cities))

    def test_cities_cover_every_listing(self, repository) -> None:
        assert set(repository.cities()) == {l.city for l in repository.list_all()}

    def test_list_all_returns_a_copy_callers_cannot_corrupt_the_store(
        self, repository
    ) -> None:
        repository.list_all().clear()
        assert len(repository.list_all()) == 12


class TestClock:
    def test_environment_override_pins_the_reference_date(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(REFERENCE_DATE_ENV, "2026-01-15")
        assert today() == date(2026, 1, 15)

    def test_falls_back_to_the_real_date_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(REFERENCE_DATE_ENV, raising=False)
        assert today() == date.today()

    def test_blank_override_is_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(REFERENCE_DATE_ENV, "")
        assert today() == date.today()
