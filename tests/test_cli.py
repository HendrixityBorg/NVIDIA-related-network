import json
from pathlib import Path

from arti.cli import main
from arti.models import RelationType
from arti.repository import SnapshotRepository


def test_cli_relationship_query(capsys) -> None:
    exit_code = main(
        ["relationships", "--company", "NVDA", "--type", "supplier", "--limit", "2"]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert len(payload["data"]) == 2
    expected = sum(
        item.relation_type == RelationType.SUPPLIER
        for item in SnapshotRepository().relationships.values()
    )
    assert payload["pagination"]["total"] == expected


def test_cli_not_found_is_structured_error(capsys) -> None:
    exit_code = main(["company", "does-not-exist"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["error"]["code"] == "not_found"


def test_cli_parser_and_range_failures_are_structured_json(capsys) -> None:
    exit_code = main(["relationships", "--limit", "0"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["error"]["code"] == "invalid_input"
    assert "between 1 and 100" in payload["error"]["message"]

    exit_code = main(["relationships", "--type", "not-a-relation"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["error"]["code"] == "invalid_input"


def test_cli_missing_snapshot_is_structured_json(capsys, tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    exit_code = main(["--data", str(missing), "company", "NVDA"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["error"]["code"] == "file_not_found"
    assert str(missing) in payload["error"]["message"]


def test_cli_commercial_directness_filter(capsys) -> None:
    exit_code = main(
        [
            "relationships",
            "--type",
            "supplier",
            "--commercial-directness",
            "direct",
            "--limit",
            "100",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert all(row["commercial_directness"] == "direct" for row in payload["data"])


def test_cli_graph_supports_cursor_pagination_and_bad_cursor(capsys) -> None:
    first_exit = main(["graph", "--company", "NVDA", "--limit", "2"])
    first = json.loads(capsys.readouterr().out)["data"]
    assert first_exit == 0
    assert first["truncated"] is True
    assert first["next_cursor"] is not None

    second_exit = main(
        [
            "graph",
            "--company",
            "NVDA",
            "--limit",
            "2",
            "--cursor",
            first["next_cursor"],
        ]
    )
    second = json.loads(capsys.readouterr().out)["data"]
    assert second_exit == 0
    assert {edge["id"] for edge in first["edges"]}.isdisjoint(
        {edge["id"] for edge in second["edges"]}
    )

    bad_exit = main(
        ["graph", "--company", "NVDA", "--cursor", "not-a-cursor"]
    )
    error = json.loads(capsys.readouterr().out)["error"]
    assert bad_exit == 2
    assert error["code"] == "invalid_cursor"
