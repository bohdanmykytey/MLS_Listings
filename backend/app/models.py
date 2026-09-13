"""Wire contract for the listing search API.

These models are the single source of truth for request/response shapes; the
frontend's `src/api/types.ts` mirrors them by hand. Changing a field here means
changing it there.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

# A listing's `id` is only unique per source, so every listing is addressed by
# the composite "SOURCE:ID" throughout the API, the UI, and React list keys.
ListingKey = str


def make_key(source: str, listing_id: str) -> ListingKey:
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

    @computed_field  # serialized as part of the contract, not stored
    @property
    def key(self) -> ListingKey:
        return make_key(self.source, self.id)


class ScoreBreakdown(BaseModel):
    """Why a listing scored what it did — surfaced so the UI can explain a rank.

    Keeping the components separate (rather than returning one opaque number)
    makes the scoring defensible in review and debuggable in tests.
    """

    model_config = ConfigDict(populate_by_name=True)

    budget_fit: float = Field(alias="budgetFit", serialization_alias="budgetFit")
    recency: float
    budget_weight: float = Field(alias="budgetWeight", serialization_alias="budgetWeight")
    recency_weight: float = Field(alias="recencyWeight", serialization_alias="recencyWeight")


class ScoredListing(Listing):
    """A listing with its relevance score, as returned by /search."""

    model_config = ConfigDict(populate_by_name=True)

    relevance_score: float = Field(
        alias="relevanceScore", serialization_alias="relevanceScore"
    )
    score_breakdown: ScoreBreakdown = Field(
        alias="scoreBreakdown", serialization_alias="scoreBreakdown"
    )
    # Populated only when dedupe is on: the other keys this record absorbed.
    merged_from: list[ListingKey] = Field(
        default_factory=list, alias="mergedFrom", serialization_alias="mergedFrom"
    )


SortOption = Literal["relevance", "priceAsc", "priceDesc", "newest"]

MAX_PAGE_SIZE = 100


class SearchParams(BaseModel):
    """Query parameters for /api/listings/search.

    Bounds are declared on the fields so invalid input is rejected at the edge
    with a 400 instead of silently producing wrong data. Cross-field rules that
    Pydantic can't express per-field live in `check_ranges` below.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    min_price: Annotated[float | None, Field(default=None, ge=0, alias="minPrice")]
    max_price: Annotated[float | None, Field(default=None, ge=0, alias="maxPrice")]
    min_bedrooms: Annotated[int | None, Field(default=None, ge=0, alias="minBedrooms")]
    city: Annotated[str | None, Field(default=None, max_length=120)]
    keyword: Annotated[str | None, Field(default=None, max_length=200)]
    target_budget: Annotated[
        float | None, Field(default=None, gt=0, alias="targetBudget")
    ]

    # Status is filterable but unfiltered by default: the handout never asks to
    # hide the one `pending` listing, so the baseline matches the spec exactly.
    # Flipping the default to [ACTIVE] is a one-line change.
    status: Annotated[list[ListingStatus] | None, Field(default=None)]

    dedupe: Annotated[bool, Field(default=False)]
    sort: Annotated[SortOption, Field(default="relevance")]

    page: Annotated[int, Field(default=1, ge=1)]
    page_size: Annotated[
        int, Field(default=10, ge=1, le=MAX_PAGE_SIZE, alias="pageSize")
    ]

    @model_validator(mode="after")
    def check_ranges(self) -> SearchParams:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("minPrice must be less than or equal to maxPrice")
        return self

    @property
    def normalized_keyword(self) -> str | None:
        kw = (self.keyword or "").strip()
        return kw or None

    @property
    def normalized_city(self) -> str | None:
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
    # Echoed back so the UI can prove what the server actually applied, and so
    # a surprising result set is self-diagnosing.
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
    """Map an internal field name back to the alias clients actually send.

    Pydantic reports validation errors against the Python field name
    (`page_size`), but the client sent `pageSize` and its form controls are
    keyed by that. Translating here keeps the error envelope in the same
    vocabulary as the request, so the UI can highlight the offending input.
    """
    field = SearchParams.model_fields.get(field_name)
    if field is not None and isinstance(field.alias, str):
        return field.alias
    return field_name
