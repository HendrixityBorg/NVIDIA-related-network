from __future__ import annotations

from fastapi.testclient import TestClient

from listed_company_network.api import create_app
from listed_company_network.cli import main
from listed_company_network.research.build import build_snapshot

from conftest import NOW, write_valid_run


def snapshot_path(tmp_path, profile):
    run = tmp_path / "run"
    write_valid_run(run, profile)
    path = tmp_path / "snapshot.json"
    build_snapshot(profile, run, path, generated_at=NOW)
    return path


def test_http_filters_pagination_and_errors(tmp_path, profile):
    path = snapshot_path(tmp_path, profile)
    client = TestClient(create_app(str(path)))
    response = client.get(
        "/v1/relationships",
        params={"company": "TEST", "relation_type": "customer", "limit": 1},
    )
    assert response.status_code == 200
    assert response.json()["pagination"]["total"] == 1
    invalid = client.get("/v1/relationships", params={"min_confidence": 101})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    missing = client.get("/v1/companies/DOES-NOT-EXIST")
    assert missing.status_code == 404


def test_cli_query_and_invalid_input(tmp_path, profile, capsys):
    path = snapshot_path(tmp_path, profile)
    assert main(["--data", str(path), "relationships", "--company", "TEST"]) == 0
    payload = capsys.readouterr().out
    assert '"total": 1' in payload
    assert main(["--data", str(path), "relationships", "--min-confidence", "101"]) == 2
    assert '"code": "invalid_input"' in capsys.readouterr().out
