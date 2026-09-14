"""HTTP layer.

Thin on purpose: each route validates, delegates to the pure logic, and
serializes. No filtering, scoring, or pagination logic lives here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from . import search as search_mod
from .clock import today
from .models import Listing, SearchParams, SearchResponse
from .repository import ListingRepository

router = APIRouter()


def get_repository() -> ListingRepository:
    """Dependency seam for the data source.

    Deliberately unimplemented: the concrete repository is injected by
    `main.py` at startup and by fixtures in tests, so no module here has to
    know where listings actually come from. Raising makes a missing override a
    loud failure rather than a mysterious empty result.
    """
    raise RuntimeError("repository dependency not configured")


RepoDep = Annotated[ListingRepository, Depends(get_repository)]


@router.get("/health")
def health() -> dict[str, object]:
    """Liveness, plus the reference date days-on-market is measured against.

    Surfacing the date makes a "why did the scores change?" question
    answerable without reading the server's environment.
    """
    return {"status": "ok", "referenceDate": today().isoformat()}


@router.get("/cities", response_model=list[str])
def list_cities(repo: RepoDep) -> list[str]:
    """Distinct cities, so the UI can offer a real choice instead of free text.

    Exists to stop the city filter being a guessing game: a typo returns an
    empty result that looks identical to a genuine no-match.
    """
    return repo.cities()


@router.get("/listings/search", response_model=SearchResponse, response_model_by_alias=True)
def search_listings(
    repo: RepoDep,
    params: Annotated[SearchParams, Query()],
) -> SearchResponse:
    """The endpoint the whole exercise is about: filter, rank, paginate.

    Deliberately thin — validation is done by `SearchParams` before this runs,
    and the work is done by the pure pipeline afterwards, so nothing that
    decides results lives in the HTTP layer.
    """
    return search_mod.search(repo.list_all(), params, today())


# --- Raw data ----------------------------------------------------------------
# Read-only. These exist to inspect what the search endpoint is working from —
# useful when a result set is surprising, and when demonstrating that dedupe
# really is collapsing distinct feed records. Addressed by the composite key,
# since `id` alone is not unique across sources.


@router.get("/listings", response_model=list[Listing], response_model_by_alias=True)
def list_listings(repo: RepoDep) -> list[Listing]:
    """Every listing, unranked and unfiltered — the raw feed union.

    Useful for inspecting what the search endpoint is working from.
    """
    return repo.list_all()


@router.get(
    "/listings/{source}/{listing_id}",
    response_model=Listing,
    response_model_by_alias=True,
)
def get_listing(source: str, listing_id: str, repo: RepoDep) -> Listing:
    """One listing, addressed by composite key. 404 when absent."""
    listing = repo.get(source, listing_id)
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No listing {source}:{listing_id}")
    return listing
