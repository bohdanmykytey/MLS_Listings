"""Data access.

The dataset is small and read-only, so it lives in memory: the JSON feed is
parsed once at startup into a list of `Listing`. Everything above this module
talks to `ListingRepository`, so swapping in Postgres (or a live MLS client)
means writing one new class and changing one line in `main.py`.

The interface exposes reads only, because that is all the application does.
Adding writes later means adding them here and nowhere else.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Protocol

from .models import Listing, ListingKey, make_key

DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_listings.json"


class ListingRepository(Protocol):
    """The only surface the search pipeline depends on."""

    def list_all(self) -> list[Listing]:
        """Every listing. The search pipeline filters in memory from here."""
        ...

    def get(self, source: str, listing_id: str) -> Listing | None:
        """One listing by composite key, or None — absence is not an error."""
        ...

    def cities(self) -> list[str]:
        """Distinct cities, so the UI dropdown reflects the data rather than a
        hardcoded list that silently rots."""
        ...


class InMemoryListingRepository:
    """Keyed by the composite "SOURCE:ID" because `id` collides across sources."""

    def __init__(self, listings: Iterable[Listing]) -> None:
        """Index the listings by composite key for O(1) lookup by id."""
        self._by_key: dict[ListingKey, Listing] = {l.key: l for l in listings}

    @classmethod
    def from_json_file(cls, path: Path = DEFAULT_DATA_PATH) -> InMemoryListingRepository:
        """Load and validate a feed file at startup.

        Validation happens here, once, so malformed data fails loudly on boot
        rather than surfacing as a confusing 500 on some later request.
        """
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{path} must contain a JSON array of listings")
        return cls(Listing.model_validate(item) for item in raw)

    def list_all(self) -> list[Listing]:
        """A copy, so callers cannot mutate the store by accident."""
        return list(self._by_key.values())

    def get(self, source: str, listing_id: str) -> Listing | None:
        """See `ListingRepository.get`."""
        return self._by_key.get(make_key(source, listing_id))

    def cities(self) -> list[str]:
        """See `ListingRepository.cities`. Sorted for a stable dropdown."""
        return sorted({l.city for l in self._by_key.values()})
