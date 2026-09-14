"""Wire contract for the API. Single source of truth for request/response
shapes; `frontend/src/api/types.ts` mirrors these fields by hand."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

# `id` is only unique per source, so listings are addressed by "SOURCE:ID"
# everywhere: API, UI, React list keys.
ListingKey = str


def make_key(source: str, listing_id: str) -> ListingKey:
    """Build the composite key used to address a listing everywhere."""
    return f"{source}:{listing_id}"


class ListingStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    SOLD = "sold"


class Listing(BaseModel):
    """A listing exactly as it arrives from a feed, plus its composite key."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    source: str
    address: str
    city: str
    state: str
    zip: str
    price: float
    bedrooms: int
    bathrooms: float
    sqft: int
    latitude: float
    longitude: float
    listed_date: date = Field(alias="listedDate", serialization_alias="listedDate")
    status: ListingStatus
    description: str

    # Set only when dedupe collapses a cluster: the keys this record absorbed.
    merged_from: list[ListingKey] = Field(
        default_factory=list, alias="mergedFrom", serialization_alias="mergedFrom"
    )

    @computed_field
    @property
    def key(self) -> ListingKey:
        """Computed, not stored, so it can never disagree with source/id."""
        return make_key(self.source, self.id)


class ScoreBreakdown(BaseModel):
    """Score components kept separate, not one opaque number, so a rank is
    auditable and testable."""

    model_config = ConfigDict(populate_by_name=True)

    budget_fit: float = Field(alias="budgetFit", serialization_alias="budgetFit")
    negotiability: float
    budget_weight: float = Field(alias="budgetWeight", serialization_alias="budgetWeight")
    negotiability_weight: float = Field(
        alias="negotiabilityWeight", serialization_alias="negotiabilityWeight"
    )


class ScoredListing(Listing):
    """A listing with its relevance score, as returned by /search."""

    model_config = ConfigDict(populate_by_name=True)

    relevance_score: float = Field(
        alias="relevanceScore", serialization_alias="relevanceScore"
    )
    score_breakdown: ScoreBreakdown = Field(
        alias="scoreBreakdown", serialization_alias="scoreBreakdown"
    )


MAX_PAGE_SIZE = 100


class SearchParams(BaseModel):
    """Query parameters for /api/listings/search. Per-field bounds reject bad
    input at the edge with a 400; cross-field rules live in `check_ranges`."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    min_price: Annotated[float | None, Field(default=None, ge=0, alias="minPrice")]
    max_price: Annotated[float | None, Field(default=None, ge=0, alias="maxPrice")]
    min_bedrooms: Annotated[int | None, Field(default=None, ge=0, alias="minBedrooms")]
    city: Annotated[str | None, Field(default=None, max_length=120)]
    keyword: Annotated[str | None, Field(default=None, max_length=200)]
    target_budget: Annotated[
        float | None, Field(default=None, gt=0, alias="targetBudget")
    ]

    # Unfiltered by default — the handout never asks to hide `pending`.
    status: Annotated[list[ListingStatus] | None, Field(default=None)]

    dedupe: Annotated[bool, Field(default=False)]

    page: Annotated[int, Field(default=1, ge=1)]
    page_size: Annotated[
        int, Field(default=10, ge=1, le=MAX_PAGE_SIZE, alias="pageSize")
    ]

    @model_validator(mode="after")
    def check_ranges(self) -> SearchParams:
        """The one cross-field rule the brief calls out by name."""
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("minPrice must be less than or equal to maxPrice")
        return self

    @property
    def normalized_keyword(self) -> str | None:
        """Blank/whitespace-only means unfiltered, not "match nothing"."""
        kw = (self.keyword or "").strip()
        return kw or None

    @property
    def normalized_city(self) -> str | None:
        """Blank/whitespace-only means unfiltered, not "match nothing"."""
        city = (self.city or "").strip()
        return city or None


class PageInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    page: int
    page_size: int = Field(alias="pageSize", serialization_alias="pageSize")
    total: int
    total_pages: int = Field(alias="totalPages", serialization_alias="totalPages")


class SearchResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: list[ScoredListing]
    page_info: PageInfo = Field(alias="pageInfo", serialization_alias="pageInfo")
    # What the server actually applied, so a surprising result is self-diagnosing.
    applied: dict[str, object]


class ErrorDetail(BaseModel):
    field: str | None = None
    issue: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorEnvelope(BaseModel):
    """Every non-2xx response from this API has exactly this shape."""

    error: ErrorBody


def query_alias(field_name: str) -> str:
    """Map an internal field name back to the alias clients sent, so error
    responses speak the client's vocabulary (`page_size` -> `pageSize`)."""
    field = SearchParams.model_fields.get(field_name)
    if field is not None and isinstance(field.alias, str):
        return field.alias
    return field_name
