"""Input validation.

The brief asks for invalid input to be handled deliberately rather than
incidentally, so this suite is the contract for what counts as a bad request.
The distinction it enforces throughout: a *malformed* query is a 400 the user
must fix, while a *valid query that matches nothing* is an ordinary 200 with
an empty page. Conflating the two is the failure mode being guarded against.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

SEARCH = "/api/listings/search"


def error(response) -> dict:
    return response.json()["error"]


def fields(response) -> set[str | None]:
    return {d["field"] for d in error(response)["details"]}


class TestRejectedRequests:
    @pytest.mark.parametrize(
        "params,expected_field",
        [
            ({"minPrice": 900_000, "maxPrice": 100_000}, None),   # cross-field
            ({"pageSize": 0}, "pageSize"),
            ({"pageSize": -5}, "pageSize"),
            ({"pageSize": 101}, "pageSize"),                      # above the cap
            ({"page": 0}, "page"),
            ({"page": -1}, "page"),
            ({"minPrice": -1}, "minPrice"),
            ({"maxPrice": -1}, "maxPrice"),
            ({"minBedrooms": -1}, "minBedrooms"),
            ({"targetBudget": 0}, "targetBudget"),                # must be > 0
            ({"targetBudget": -100}, "targetBudget"),
            ({"minPrice": "cheap"}, "minPrice"),                  # unparseable
            ({"page": "two"}, "page"),
            ({"status": "bogus"}, "status.0"),
            ({"colour": "blue"}, "colour"),                       # unknown param
        ],
    )
    def test_invalid_input_is_a_400_naming_the_offending_field(
        self, client: TestClient, params: dict, expected_field: str | None
    ) -> None:
        response = client.get(SEARCH, params=params)
        assert response.status_code == 400
        assert error(response)["code"] == "INVALID_REQUEST"
        assert expected_field in fields(response)

    def test_min_price_equal_to_max_price_is_allowed(self, client: TestClient) -> None:
        """The boundary is valid: an exact-price search is legitimate."""
        response = client.get(SEARCH, params={"minPrice": 450_000, "maxPrice": 450_000})
        assert response.status_code == 200

    def test_the_cross_field_message_explains_the_problem(self, client: TestClient) -> None:
        response = client.get(SEARCH, params={"minPrice": 900_000, "maxPrice": 100_000})
        issues = [d["issue"] for d in error(response)["details"]]
        assert any("minPrice" in i and "maxPrice" in i for i in issues)

    def test_multiple_invalid_fields_are_all_reported(self, client: TestClient) -> None:
        """One round trip should reveal every problem, not just the first."""
        response = client.get(SEARCH, params={"pageSize": 0, "page": 0, "minBedrooms": -3})
        assert {"pageSize", "page", "minBedrooms"} <= fields(response)

    def test_errors_are_reported_using_the_alias_the_client_sent(
        self, client: TestClient
    ) -> None:
        """`pageSize`, never the internal `page_size` — the UI keys its inputs
        by the alias and needs to map the error back to a control."""
        response = client.get(SEARCH, params={"pageSize": 0})
        assert "pageSize" in fields(response)
        assert "page_size" not in fields(response)


class TestAcceptedRequests:
    @pytest.mark.parametrize(
        "params",
        [
            {},                                        # no filters at all
            {"minPrice": 0},                           # zero is a valid floor
            {"minBedrooms": 0},
            {"pageSize": 1},                           # lower bound
            {"pageSize": 100},                         # upper bound
            {"page": 99999},                           # past the end, still valid
            {"city": ""},                              # blank means "no filter"
            {"keyword": ""},
            {"city": "   "},
            {"dedupe": "true"},
            {"dedupe": "false"},
            {"status": "active"},
        ],
    )
    def test_valid_input_is_accepted(self, client: TestClient, params: dict) -> None:
        assert client.get(SEARCH, params=params).status_code == 200

    def test_a_city_with_no_matches_is_not_an_error(self, client: TestClient) -> None:
        """The brief calls this out specifically: an empty result is not a
        failure, and must not be reported as one."""
        response = client.get(SEARCH, params={"city": "Atlantis"})
        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["pageInfo"]["total"] == 0
        assert "error" not in body

    def test_a_page_past_the_end_is_not_an_error(self, client: TestClient) -> None:
        response = client.get(SEARCH, params={"page": 99})
        assert response.status_code == 200
        assert response.json()["pageInfo"]["totalPages"] == 2


class TestErrorEnvelope:
    def test_every_error_uses_the_same_shape(self, client: TestClient) -> None:
        """One shape means the frontend needs exactly one error parser."""
        for response in (
            client.get(SEARCH, params={"pageSize": 0}),
            client.get("/api/listings/MLS_A/nope"),
            client.get("/api/does-not-exist"),
        ):
            body = response.json()
            assert set(body) == {"error"}
            assert set(body["error"]) == {"code", "message", "details"}

    def test_validation_failures_are_400_not_fastapis_default_422(
        self, client: TestClient
    ) -> None:
        assert client.get(SEARCH, params={"pageSize": 0}).status_code == 400

    def test_missing_listing_is_a_404_with_a_useful_code(self, client: TestClient) -> None:
        response = client.get("/api/listings/MLS_A/nope")
        assert response.status_code == 404
        assert error(response)["code"] == "NOT_FOUND"

    def test_internals_are_never_leaked_in_error_messages(self, client: TestClient) -> None:
        response = client.get(SEARCH, params={"pageSize": 0})
        blob = response.text.lower()
        for leak in ("traceback", "file \"", "/users/", "site-packages"):
            assert leak not in blob
