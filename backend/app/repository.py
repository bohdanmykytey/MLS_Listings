"""Data access.

The dataset is small and read-mostly, so it lives in memory: the JSON feed is
parsed once at startup into a list of `Listing`. Everything above this module
talks to `ListingRepository`, so swapping in Postgres (or a live MLS client)
means writing one new class and changing one line in `main.py`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Protocol

from .models import Listing, ListingKey, make_key

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_listings.json"


class ListingRepository(Protocol):
    """The only surface the search pipeline depends on."""

    def list_all(self) -> list[Listing]: ...
    def get(self, source: str, listing_id: str) -> Listing | None: ...
    def upsert(self, listing: Listing) -> Listing: ...
    def delete(self, source: str, listing_id: str) -> bool: ...
    def cities(self) -> list[str]: ...


class InMemoryListingRepository:
    """Keyed by the composite "SOURCE:ID" because `id` collides across sources."""

    def __init__(self, listings: Iterable[Listing]) -> None:
        self._by_key: dict[ListingKey, Listing] = {l.key: l for l in listings}

    @classmethod
    def from_json_file(cls, path: Path = DEFAULT_DATA_PATH) -> InMemoryListingRepository:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{path} must contain a JSON array of listings")
        return cls(Listing.model_validate(item) for item in raw)

    def list_all(self) -> list[Listing]:
        return list(self._by_key.values())

    def get(self, source: str, listing_id: str) -> Listing | None:
        return self._by_key.get(make_key(source, listing_id))

    def upsert(self, listing: Listing) -> Listing:
        self._by_key[listing.key] = listing
        return listing

    def delete(self, source: str, listing_id: str) -> bool:
        return self._by_key.pop(make_key(source, listing_id), None) is not None

    def cities(self) -> list[str]:
        return sorted({l.city for l in self._by_key.values()})
