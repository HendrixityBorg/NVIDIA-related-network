from fastapi.testclient import TestClient

from arti.api import create_app


def test_health_and_filtered_relationships() -> None:
    with TestClient(create_app()) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["relationship_count"] >= 15

        response = client.get(
            "/v1/relationships",
            params={"company": "NVDA", "relation_type": "supplier", "limit": 3},
        )
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["data"]) == 3
        expected = sum(
            item.relation_type.value == "supplier"
            for item in client.app.state.service.repo.relationships.values()
        )
        assert payload["pagination"]["total"] == expected


def test_api_validation_and_not_found_errors_are_explicit() -> None:
    with TestClient(create_app()) as client:
        invalid = client.get("/v1/relationships", params={"min_confidence": 101})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "validation_error"

        missing = client.get("/v1/companies/not-a-company")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "not_found"

        bad_cursor = client.get("/v1/companies", params={"cursor": "not-a-cursor"})
        assert bad_cursor.status_code == 400
        assert bad_cursor.json()["error"]["code"] == "invalid_cursor"

        missing_evidence = client.get("/v1/evidence/not-evidence")
        assert missing_evidence.status_code == 404
        assert missing_evidence.json()["error"]["code"] == "not_found"


def test_api_filters_commercial_directness() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/v1/relationships",
            params={
                "relation_type": "supplier",
                "commercial_directness": "direct",
                "limit": 100,
            },
        )
        assert response.status_code == 200
        assert all(
            row["commercial_directness"] == "direct"
            for row in response.json()["data"]
        )


def test_evidence_can_be_queried_by_relationship() -> None:
    with TestClient(create_app()) as client:
        relationship = next(
            item
            for item in client.app.state.service.repo.relationships.values()
            if item.evidence_ids
        )
        response = client.get(
            "/v1/evidence",
            params={"relationship_id": relationship.id, "limit": 100},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["pagination"]["total"] == len(relationship.evidence_ids)
        assert {item["evidence"]["id"] for item in payload["data"]} == set(
            relationship.evidence_ids
        )
        assert all(item["source"]["url"] for item in payload["data"])


def test_graph_supports_cursor_pagination_and_explicit_cursor_errors() -> None:
    with TestClient(create_app()) as client:
        first = client.get(
            "/v1/graph", params={"company": "NVDA", "limit": 2}
        )
        assert first.status_code == 200
        first_data = first.json()["data"]
        assert first_data["truncated"] is True
        assert first_data["next_cursor"] is not None

        second = client.get(
            "/v1/graph",
            params={
                "company": "NVDA",
                "limit": 2,
                "cursor": first_data["next_cursor"],
            },
        )
        assert second.status_code == 200
        first_ids = {edge["id"] for edge in first_data["edges"]}
        second_ids = {edge["id"] for edge in second.json()["data"]["edges"]}
        assert first_ids.isdisjoint(second_ids)

        bad_cursor = client.get(
            "/v1/graph",
            params={"company": "NVDA", "cursor": "not-a-cursor"},
        )
        assert bad_cursor.status_code == 400
        assert bad_cursor.json()["error"]["code"] == "invalid_cursor"
