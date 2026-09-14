"""Data access. Small read-only dataset, so it lives in memory behind a
`ListingRepository` protocol — swapping in a real DB later is one new class."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Protocol

from .models import Listing, ListingKey, make_key

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_listings.json"


class ListingRepository(Protocol):
    """The only surface the search pipeline depends on."""

    def list_all(self) -> list[Listing]:
        ...

    def get(self, source: str, listing_id: str) -> Listing | None:
        ...

    def cities(self) -> list[str]:
        ...


class InMemoryListingRepository:
    """Keyed by composite "SOURCE:ID" since `id` collides across sources."""

    def __init__(self, listings: Iterable[Listing]) -> None:
        self._by_key: dict[ListingKey, Listing] = {l.key: l for l in listings}

    @classmethod
    def from_json_file(cls, path: Path = DEFAULT_DATA_PATH) -> InMemoryListingRepository:
        """Validate at load time so bad data fails loudly on boot, not as a
        confusing 500 later."""
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{path} must contain a JSON array of listings")
        return cls(Listing.model_validate(item) for item in raw)

    def list_all(self) -> list[Listing]:
        """A copy, so callers can't mutate the store."""
        return list(self._by_key.values())

    def get(self, source: str, listing_id: str) -> Listing | None:
        return self._by_key.get(make_key(source, listing_id))

    def cities(self) -> list[str]:
        """Sorted for a stable dropdown."""
        return sorted({l.city for l in self._by_key.values()})
