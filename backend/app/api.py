"""HTTP layer.

Thin on purpose: each route validates, delegates to the pure logic, and
serializes. No filtering, scoring, or pagination logic lives here.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from . import search as search_mod
from .clock import today
from .models import Listing, SearchParams, SearchResponse
from .repository import ListingRepository

router = APIRouter()


def get_repository() -> ListingRepository:
    """Overridden at startup in `main.py`, and per-test in the test suite."""
    raise RuntimeError("repository dependency not configured")


RepoDep = Annotated[ListingRepository, Depends(get_repository)]


@router.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "referenceDate": today().isoformat()}


@router.get("/cities", response_model=list[str])
def list_cities(repo: RepoDep) -> list[str]:
    """Distinct cities, so the UI can offer a real choice instead of free text."""
    return repo.cities()


@router.get("/listings/search", response_model=SearchResponse, response_model_by_alias=True)
def search_listings(
    repo: RepoDep,
    params: Annotated[SearchParams, Query()],
) -> SearchResponse:
    return search_mod.search(repo.list_all(), params, today())


# --- CRUD -------------------------------------------------------------------
# Not required by the handout. Included because it makes the repository seam
# real (the search path and the write path share one interface) and gives the
# in-memory store an honest lifecycle. Addressed by the composite key, since
# `id` alone is not unique across sources.


@router.get("/listings", response_model=list[Listing], response_model_by_alias=True)
def list_listings(repo: RepoDep) -> list[Listing]:
    return repo.list_all()


@router.get(
    "/listings/{source}/{listing_id}",
    response_model=Listing,
    response_model_by_alias=True,
)
def get_listing(source: str, listing_id: str, repo: RepoDep) -> Listing:
    listing = repo.get(source, listing_id)
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No listing {source}:{listing_id}")
    return listing


@router.post(
    "/listings",
    response_model=Listing,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
def create_listing(listing: Listing, repo: RepoDep) -> Listing:
    if repo.get(listing.source, listing.id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{listing.key} already exists")
    return repo.upsert(listing)


@router.put(
    "/listings/{source}/{listing_id}",
    response_model=Listing,
    response_model_by_alias=True,
)
def replace_listing(
    source: str, listing_id: str, listing: Listing, repo: RepoDep
) -> Listing:
    if repo.get(source, listing_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No listing {source}:{listing_id}")
    if (listing.source, listing.id) != (source, listing_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Body source/id must match the URL path"
        )
    return repo.upsert(listing)


@router.delete("/listings/{source}/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(source: str, listing_id: str, repo: RepoDep) -> Response:
    if not repo.delete(source, listing_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No listing {source}:{listing_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
