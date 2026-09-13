"""Shared fixtures.

Every test runs against a pinned reference date so recency scores are stable
and assertions can use exact numbers instead of tolerances.

Two kinds of data are used deliberately:

  * the real `sample_listings.json`, for behaviour that should be verified
    against the dataset the reviewer will actually run against, and
  * synthetic listings from `make_listing`, for cases the sample data cannot
    express. All 12 sample listings have distinct `listedDate` values, so
    recency always differs and a true relevance tie is impossible with real
    data — tie-break behaviour can only be tested with constructed records.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

import pytest
from fastapi.testclient import TestClient

from app.api import get_repository
from app.main import create_app
from app.models import Listing, ListingStatus, SearchParams
from app.repository import InMemoryListingRepository

# One week after the newest listing in the sample data (2026-09-04).
REFERENCE_DATE = date(2026, 9, 11)


@pytest.fixture(autouse=True)
def pinned_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LISTING_SEARCH_REFERENCE_DATE", REFERENCE_DATE.isoformat())


@pytest.fixture
def repository() -> InMemoryListingRepository:
    """A fresh repository per test, so CRUD tests can't leak into each other."""
    return InMemoryListingRepository.from_json_file()


@pytest.fixture
def sample_listings(repository: InMemoryListingRepository) -> list[Listing]:
    return repository.list_all()


@pytest.fixture
def client(repository: InMemoryListingRepository) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: repository
    return TestClient(app)


ListingFactory = Callable[..., Listing]


@pytest.fixture
def make_listing() -> ListingFactory:
    """Build a listing with sensible defaults; override only what matters.

    Keeping the irrelevant fields out of each test makes the field under test
    obvious at a glance.
    """

    def _make(
        listing_id: str = "X1",
        source: str = "MLS_X",
        *,
        price: float = 500_000,
        bedrooms: int = 3,
        listed_date: str = "2026-09-01",
        city: str = "Springfield",
        description: str = "A house.",
        status: ListingStatus | str = ListingStatus.ACTIVE,
        address: str | None = None,
        latitude: float = 38.0,
        longitude: float = -77.0,
        sqft: int = 1500,
        bathrooms: float = 2.0,
        zip_code: str = "22150",
    ) -> Listing:
        return Listing.model_validate(
            {
                "id": listing_id,
                "source": source,
                "address": address or f"{listing_id} Test St",
                "city": city,
                "state": "VA",
                "zip": zip_code,
                "price": price,
                "bedrooms": bedrooms,
                "bathrooms": bathrooms,
                "sqft": sqft,
                "latitude": latitude,
                "longitude": longitude,
                "listedDate": listed_date,
                "status": status,
                "description": description,
            }
        )

    return _make


@pytest.fixture
def params() -> Callable[..., SearchParams]:
    """SearchParams with defaults, overridden by keyword (aliases accepted)."""

    def _params(**overrides: object) -> SearchParams:
        return SearchParams.model_validate(overrides)

    return _params
