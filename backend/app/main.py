"""Application entry point.

    uvicorn app.main:app --reload --port 8000

Docs at http://localhost:8000/docs once running.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import get_repository, router
from .errors import register_error_handlers
from .repository import InMemoryListingRepository

# Vite dev (3000) and preview (4173). Requests normally go through Vite's
# proxy; these only matter for a direct browser call.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def create_app() -> FastAPI:
    """Factory, not a module-level singleton, so tests get an isolated app."""
    app = FastAPI(
        title="Listing Search Service",
        version="1.0.0",
        description="Filter, rank, and page property listings ingested from multiple MLS feeds.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["GET"],  # read-only API
        allow_headers=["Content-Type"],
    )

    register_error_handlers(app)
    app.include_router(router, prefix="/api")

    # The one place the concrete data source is chosen.
    repository = InMemoryListingRepository.from_json_file()
    app.dependency_overrides[get_repository] = lambda: repository

    return app


app = create_app()
