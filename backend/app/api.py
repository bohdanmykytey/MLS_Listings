"""HTTP layer. Thin: routes validate, delegate to the pure pipeline, serialize."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from . import search as search_mod
from .clock import today
from .models import Listing, SearchParams, SearchResponse
from .repository import ListingRepository

router = APIRouter()


def get_repository() -> ListingRepository:
    """Unimplemented on purpose — `main.py`/tests override it. Raises loudly if not."""
    raise RuntimeError("repository dependency not configured")


RepoDep = Annotated[ListingRepository, Depends(get_repository)]


@router.get("/health")
def health() -> dict[str, object]:
    """Liveness, plus the reference date scores are measured against."""
    return {"status": "ok", "referenceDate": today().isoformat()}


@router.get("/cities", response_model=list[str])
def list_cities(repo: RepoDep) -> list[str]:
    """Distinct cities, so the UI offers real choices instead of free text."""
    return repo.cities()


@router.get("/listings/search", response_model=SearchResponse, response_model_by_alias=True)
def search_listings(
    repo: RepoDep,
    params: Annotated[SearchParams, Query()],
) -> SearchResponse:
    """Filter, rank, paginate — the endpoint the exercise is about."""
    return search_mod.search(repo.list_all(), params, today())


# --- Raw data ----------------------------------------------------------------
# Read-only, for inspecting what search is working from. Addressed by
# composite key since `id` alone isn't unique across sources.


@router.get("/listings", response_model=list[Listing], response_model_by_alias=True)
def list_listings(repo: RepoDep) -> list[Listing]:
    """Every listing, unranked and unfiltered — the raw feed union."""
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
