from __future__ import annotations

import json
from pathlib import Path

from listed_company_network.repository import SnapshotRepository
from listed_company_network.research.build import build_snapshot
from listed_company_network.research.case import verify_case
from listed_company_network.research.discovery import (
    classify_official_url,
    is_news_semantic_evidence_eligible,
    plan_search_queries,
)
from listed_company_network.research.io import read_jsonl, write_jsonl
from listed_company_network.research.project import initialise_run
from listed_company_network.research.validation import validate_run
from listed_company_network.service import ResearchService

from conftest import NOW, write_valid_run


def test_initialise_run_generates_generic_agent_contracts(tmp_path, profile):
    run = tmp_path / "run"
    initialise_run(profile, run)
    assert len(list((run / "agent_tasks").glob("*.json"))) == 11
    assert len(read_jsonl(run / "discovery/search_queries.jsonl")) >= 6
    assert (run / "normalized/relationships.jsonl").is_file()


def test_discovery_classification_and_news_eligibility(profile):
    assert classify_official_url("https://example.com/solutions/ai") == "product_solutions"
    families = {item.family.value for item in plan_search_queries(profile)}
    assert "third_party_news" in families
    assert not is_news_semantic_evidence_eligible(
        {
            "access_status": "accessible",
            "locator": "search snippet",
            "evidence_eligibility": "lead_only",
            "cooccurrence_warning": True,
        }
    )


def test_valid_run_builds_queryable_snapshot(tmp_path, profile):
    run = tmp_path / "run"
    write_valid_run(run, profile)
    report = validate_run(profile, run, generated_at=NOW)
    assert report.release_ready, report.errors
    output = tmp_path / "snapshot.json"
    build_snapshot(profile, run, output, generated_at=NOW)
    service = ResearchService(SnapshotRepository(output))
    page = service.list_relationships(company="TEST", min_confidence=80)
    assert page.total == 1
    assert page.items[0].target_entity_id == "customerco"


def test_missing_counterparty_terminal_fails_closed(tmp_path, profile):
    run = tmp_path / "run"
    write_valid_run(run, profile)
    write_jsonl(run / "review/counterparty_decisions.jsonl", [])
    report = validate_run(profile, run, generated_at=NOW)
    assert not report.release_ready
    assert any("缺少终态" in item for item in report.errors)


def test_third_party_news_alone_cannot_confirm(tmp_path, profile):
    run = tmp_path / "run"
    write_valid_run(run, profile)
    source_path = run / "normalized/sources.jsonl"
    source = read_jsonl(source_path)[0]
    source["source_family"] = "third_party_news"
    write_jsonl(source_path, [source])
    report = validate_run(profile, run, generated_at=NOW)
    assert not report.release_ready
    assert any("第三方新闻" in item for item in report.errors)


def test_frozen_nvidia_case_manifest():
    manifest = Path("case_studies/nvidia/case_manifest.json")
    result = verify_case(manifest)
    assert result["pass"], result["errors"]
    assert result["relation_counts"]["partner"] == 1792
