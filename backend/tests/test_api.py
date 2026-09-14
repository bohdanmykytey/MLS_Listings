"""HTTP surface: response shape, CRUD lifecycle, and the repository seam.

The search *logic* is covered elsewhere; this suite is about the wire — that
responses carry the fields the UI renders, that aliases are camelCase, and
that writes and reads agree with each other.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

SEARCH = "/api/listings/search"


class TestResponseShape:
    def test_search_response_has_the_documented_top_level_keys(self, client: TestClient) -> None:
        body = client.get(SEARCH).json()
        assert set(body) == {"items", "pageInfo", "applied"}

    def test_page_info_shape(self, client: TestClient) -> None:
        info = client.get(SEARCH).json()["pageInfo"]
        assert set(info) == {"page", "pageSize", "total", "totalPages"}

    def test_items_carry_every_field_the_ui_renders(self, client: TestClient) -> None:
        item = client.get(SEARCH).json()["items"][0]
        # The four the brief requires, plus what the UI adds.
        for field in (
            "address", "price", "bedrooms", "relevanceScore",
            "key", "city", "state", "zip", "listedDate", "status",
            "scoreBreakdown", "mergedFrom",
        ):
            assert field in item, field

    def test_field_names_are_camel_case_on_the_wire(self, client: TestClient) -> None:
        """Python is snake_case internally; the JSON contract is not."""
        item = client.get(SEARCH).json()["items"][0]
        assert "listedDate" in item and "listed_date" not in item
        assert "relevanceScore" in item and "relevance_score" not in item

    def test_score_breakdown_shape(self, client: TestClient) -> None:
        breakdown = client.get(SEARCH).json()["items"][0]["scoreBreakdown"]
        assert set(breakdown) == {
            "budgetFit",
            "negotiability",
            "budgetWeight",
            "negotiabilityWeight",
        }

    def test_key_is_the_composite_source_and_id(self, client: TestClient) -> None:
        """`id` is only unique per source, so the composite is the real key."""
        for item in client.get(SEARCH, params={"pageSize": 50}).json()["items"]:
            assert item["key"] == f"{item['source']}:{item['id']}"

    def test_keys_are_unique_across_the_whole_result_set(self, client: TestClient) -> None:
        items = client.get(SEARCH, params={"pageSize": 50}).json()["items"]
        assert len({i["key"] for i in items}) == len(items)


class TestSupportingEndpoints:
    def test_health_reports_the_active_reference_date(self, client: TestClient) -> None:
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["referenceDate"] == "2026-09-11"  # pinned by the fixture

    def test_cities_are_distinct_and_sorted(self, client: TestClient) -> None:
        cities = client.get("/api/cities").json()
        assert cities == sorted(set(cities))

    def test_cities_match_the_dataset(self, client: TestClient) -> None:
        assert client.get("/api/cities").json() == [
            "Chantilly", "Fairfax", "Manassas", "Reston", "Springfield", "Vienna",
        ]

    def test_every_city_returns_at_least_one_listing(self, client: TestClient) -> None:
        """The dropdown must never offer a choice that yields nothing."""
        for city in client.get("/api/cities").json():
            body = client.get(SEARCH, params={"city": city}).json()
            assert body["pageInfo"]["total"] > 0, city


class TestRawDataEndpoints:
    """Read-only inspection of what search is working from."""

    def test_list_returns_the_whole_dataset(self, client: TestClient) -> None:
        assert len(client.get("/api/listings").json()) == 12

    def test_get_one_by_composite_key(self, client: TestClient) -> None:
        listing = client.get("/api/listings/MLS_A/A1").json()
        assert (listing["source"], listing["id"]) == ("MLS_A", "A1")

    def test_get_missing_is_404(self, client: TestClient) -> None:
        assert client.get("/api/listings/MLS_A/nope").status_code == 404

    def test_same_id_from_a_different_source_is_a_different_listing(
        self, client: TestClient
    ) -> None:
        """The crux of the composite key: MLS_A:A1 and MLS_B:A1 are not the
        same record, so `id` alone cannot address a listing."""
        assert client.get("/api/listings/MLS_A/A1").status_code == 200
        assert client.get("/api/listings/MLS_B/A1").status_code == 404

    def test_raw_listings_are_not_deduplicated(self, client: TestClient) -> None:
        """This endpoint shows the feed union; collapsing is search's job."""
        raw = client.get("/api/listings").json()
        deduped = client.get(
            "/api/listings/search", params={"dedupe": "true", "pageSize": 50}
        ).json()
        assert len(raw) == 12
        assert deduped["pageInfo"]["total"] == 8

    def test_the_api_exposes_no_write_endpoints(self, client: TestClient) -> None:
        """The application is read-only. A write reaching the API would mean
        surface nothing in the product uses."""
        for method in (client.post, client.put, client.delete):
            assert method("/api/listings/MLS_A/A1").status_code == 405
