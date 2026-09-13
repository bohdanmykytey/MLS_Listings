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
        assert set(breakdown) == {"budgetFit", "recency", "budgetWeight", "recencyWeight"}

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


class TestCrud:
    def test_list_returns_the_whole_dataset(self, client: TestClient) -> None:
        assert len(client.get("/api/listings").json()) == 12

    def test_get_one_by_composite_key(self, client: TestClient) -> None:
        listing = client.get("/api/listings/MLS_A/A1").json()
        assert (listing["source"], listing["id"]) == ("MLS_A", "A1")

    def test_get_missing_is_404(self, client: TestClient) -> None:
        assert client.get("/api/listings/MLS_A/nope").status_code == 404

    def test_create_then_read_back(self, client: TestClient, make_listing) -> None:
        payload = make_listing("NEW", source="MLS_C").model_dump(by_alias=True, mode="json")
        assert client.post("/api/listings", json=payload).status_code == 201
        assert client.get("/api/listings/MLS_C/NEW").status_code == 200

    def test_creating_a_duplicate_key_is_a_409(self, client: TestClient) -> None:
        existing = client.get("/api/listings/MLS_A/A1").json()
        response = client.post("/api/listings", json=existing)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CONFLICT"

    def test_same_id_from_a_different_source_is_not_a_conflict(
        self, client: TestClient, make_listing
    ) -> None:
        """The crux of the composite key: A1 from MLS_C is a different listing."""
        payload = make_listing("A1", source="MLS_C").model_dump(by_alias=True, mode="json")
        assert client.post("/api/listings", json=payload).status_code == 201
        assert client.get("/api/listings/MLS_A/A1").status_code == 200

    def test_replace_updates_the_record(self, client: TestClient) -> None:
        listing = client.get("/api/listings/MLS_A/A1").json()
        listing["price"] = 123_456
        assert client.put("/api/listings/MLS_A/A1", json=listing).status_code == 200
        assert client.get("/api/listings/MLS_A/A1").json()["price"] == 123_456

    def test_replace_rejects_a_body_that_contradicts_the_url(self, client: TestClient) -> None:
        listing = client.get("/api/listings/MLS_A/A1").json()
        assert client.put("/api/listings/MLS_A/A2", json=listing).status_code == 409

    def test_replace_missing_is_404(self, client: TestClient, make_listing) -> None:
        payload = make_listing("GONE", source="MLS_Z").model_dump(by_alias=True, mode="json")
        assert client.put("/api/listings/MLS_Z/GONE", json=payload).status_code == 404

    def test_delete_removes_it(self, client: TestClient) -> None:
        assert client.delete("/api/listings/MLS_A/A1").status_code == 204
        assert client.get("/api/listings/MLS_A/A1").status_code == 404

    def test_delete_is_not_idempotent_second_call_is_404(self, client: TestClient) -> None:
        client.delete("/api/listings/MLS_A/A1")
        assert client.delete("/api/listings/MLS_A/A1").status_code == 404

    def test_create_with_an_invalid_body_is_a_400(self, client: TestClient) -> None:
        assert client.post("/api/listings", json={"id": "X"}).status_code == 400


class TestWritesAreVisibleToSearch:
    """Search and CRUD share one repository; a write must change search."""

    def test_deleting_a_listing_removes_it_from_results(self, client: TestClient) -> None:
        before = client.get(SEARCH, params={"pageSize": 50}).json()["pageInfo"]["total"]
        client.delete("/api/listings/MLS_A/A1")
        after = client.get(SEARCH, params={"pageSize": 50}).json()["pageInfo"]["total"]
        assert after == before - 1

    def test_deleting_a_duplicate_changes_the_dedupe_count(self, client: TestClient) -> None:
        client.delete("/api/listings/MLS_B/B7")  # A1's counterpart
        body = client.get(SEARCH, params={"dedupe": "true", "pageSize": 50}).json()
        assert body["pageInfo"]["total"] == 8  # still 8 properties, A1 now alone
        a1 = next(i for i in body["items"] if i["key"] == "MLS_A:A1")
        assert a1["mergedFrom"] == []

    def test_repository_is_isolated_between_tests(self, client: TestClient) -> None:
        """Proves the fixture resets state — otherwise the deletions above
        would leak and later tests would fail mysteriously."""
        assert len(client.get("/api/listings").json()) == 12
