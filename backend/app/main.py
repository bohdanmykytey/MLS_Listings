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

# Vite's dev server (3000) and its preview server for built output (4173).
# Both normally reach the API through Vite's proxy, so these only matter for a
# direct browser call — but listing them turns a confusing CORS failure into a
# working request. Narrow rather than "*" so the allowed origins stay explicit.
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


def create_app() -> FastAPI:
    """Build and wire the application.

    A factory rather than a module-level singleton so tests can construct an
    isolated app with their own repository instead of sharing one global.
    """
    app = FastAPI(
        title="Listing Search Service",
        version="1.0.0",
        description="Filter, rank, and page property listings ingested from multiple MLS feeds.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        # The API is read-only, so GET is the only method that exists to allow.
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
    )

    register_error_handlers(app)
    app.include_router(router, prefix="/api")

    # The single place the concrete data source is chosen.
    repository = InMemoryListingRepository.from_json_file()
    app.dependency_overrides[get_repository] = lambda: repository

    return app


app = create_app()
