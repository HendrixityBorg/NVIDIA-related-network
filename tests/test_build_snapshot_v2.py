import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.build_snapshot_v2 import (
    EXCHANGE_LISTING_REGION,
    PEER_CATEGORY_TO_SCOPE,
    annotate_listing_regions,
    build_coverage_frontier,
    merge_same_key_relationships,
    normalized_datetime,
    normalized_retrieval_datetime,
    source_access_policy,
    terminal_gate_checks,
    validate_source_retrieval_times,
)
from scripts.validate_snapshot import parse_args as parse_validate_args


def test_final_builder_fails_closed_when_required_gates_are_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        terminal_gate_checks(tmp_path)


def test_final_builder_accepts_current_report_schema_names(tmp_path: Path):
    reports = {
        "news/enumeration_validation_report.json": {
            "status": "pass",
            "counts": {"canonical_articles": 765},
        },
        "agents/filings_presentations_complete/validation_report.json": {
            "passed": True,
            "counts": {"sources": 9},
        },
        "product_tree_v2/validation_report.json": {"overall_status": "pass"},
        "agents/article_body_recovery/validation_report.json": {
            "pass": True,
            "manifest_total": 597,
            "terminal_rows": 597,
            "pending": 0,
        },
        "agents/npn_runtime_complete/validation_report.json": {
            "complete": True,
            "observed_raw_observations": 997,
            "unique_raw_observation_ids": 997,
            "pending_count": 0,
        },
        "agents/npn_listed_parent_resolution/validation_report.json": {
            "status": "pass",
            "pending_count": 0,
        },
        "agents/entity_resolution_complete/validation_report.json": {"pass": True, "pending": 0},
        "agents/global_listing_overlay/validation_report.json": {"status": "pass", "pending_count": 0},
        "agents/non_npn_listing_audit/researched_resolution_validation_report.json": {
            "pass": True,
            "pending_count": 0,
        },
        "agents/listing_temporal_audit/validation_report.json": {
            "status": "pass",
            "pending_count": 0,
        },
        "agents/relationship_review_complete/validation_report.json": {"pass": True, "pending": 0},
        "agents/peers_complete/validation_report.json": {"pass": True, "pending_count": 0},
        "agents/npn_runtime_complete/group_validation_report.json": {"complete": True, "pending_count": 0},
        "agents/partner_regulatory_entity_normalization/validation_report.json": {"pass": True, "pending": 0},
        "agents/partner_regulatory_entity_normalization/sec_cik_hydration_validation.json": {"pass": True, "pending": 0},
        "agents/partner_regulatory_source_registry/validation_report.json": {"pass": True, "pending": 0},
        "agents/partner_regulatory_sec_review/validation_report.json": {"pass": True, "pending": 0},
        "agents/partner_regulatory_apac_review/validation_report.json": {"pass": True, "pending": 0},
        "agents/partner_regulatory_emea_review/validation_report.json": {"pass": True, "pending": 0},
        "agents/partner_regulatory_integration/validation_report.json": {"pass": True, "pending": 0},
    }
    for relative, payload in reports.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    terminal_gate_checks(tmp_path)

    frontier = build_coverage_frontier(tmp_path)
    assert frontier["release_ready"] is True
    assert len(frontier["artifacts"]) == 20
    assert all("source_id" not in item for item in frontier["artifacts"])
    assert all(not item["validation_report"].startswith("/") for item in frontier["artifacts"])


def test_same_key_observations_merge_but_different_products_do_not():
    base = {
        "id": "claim-a",
        "source_entity_id": "nvidia",
        "target_entity_id": "counterparty",
        "direction": "partners_with",
        "relation_type": "partner",
        "product_scope_id": "scope-a",
        "fact_status": "confirmed",
        "confidence_score": 80,
        "relevance_score": 80,
        "evidence_ids": ["ev-a"],
        "channels": ["official_page"],
        "asserted_by": ["NVIDIA Corporation"],
        "counterevidence": [],
        "limitations": [],
        "observation_count": 1,
        "independent_source_count": 1,
        "quantitative": {},
        "direction_explanation": "Official partner observation.",
    }
    repeated = {
        **base,
        "id": "claim-b",
        "evidence_ids": ["ev-b"],
        "channels": ["npn_runtime_directory"],
    }
    other_product = {
        **base,
        "id": "claim-c",
        "product_scope_id": "scope-b",
        "evidence_ids": ["ev-c"],
    }
    result = merge_same_key_relationships([base, repeated, other_product])
    assert len(result) == 2
    merged = next(item for item in result if item["product_scope_id"] == "scope-a")
    assert merged["evidence_ids"] == ["ev-a", "ev-b"]
    assert merged["observation_count"] == 2


def test_stronger_same_key_partner_absorbs_low_confidence_hypothesis():
    low = {
        "id": "low",
        "source_entity_id": "nvidia",
        "target_entity_id": "issuer",
        "direction": "partners_with",
        "relation_type": "partner",
        "product_scope_id": "corporate_general",
        "fact_status": "unknown",
        "confidence_score": 30,
        "relevance_score": 30,
        "evidence_ids": ["low-ev"],
        "evidence_roles": {"low-ev": "primary"},
        "channels": [],
        "asserted_by": [],
        "counterevidence": [],
        "limitations": [],
        "origin_terminal_statuses": ["approve_unknown"],
        "inference_explanations": ["Insufficient evidence."],
        "low_confidence_partner_inclusion": True,
        "observation_count": 1,
        "independent_source_count": 1,
        "quantitative": {},
        "direction_explanation": "Low-confidence hypothesis.",
    }
    strong = {
        **low,
        "id": "strong",
        "fact_status": "confirmed",
        "confidence_score": 80,
        "relevance_score": 80,
        "evidence_ids": ["strong-ev"],
        "evidence_roles": {"strong-ev": "primary"},
        "origin_terminal_statuses": ["approved"],
        "inference_explanations": [],
        "low_confidence_partner_inclusion": False,
        "direction_explanation": "Explicit Partner evidence.",
    }
    merged = merge_same_key_relationships([low, strong])[0]
    assert merged["fact_status"] == "confirmed"
    assert merged["low_confidence_partner_inclusion"] is False
    assert merged["evidence_ids"] == ["low-ev", "strong-ev"]


def test_peer_categories_map_to_frozen_canonical_scope_ids():
    assert PEER_CATEGORY_TO_SCOPE == {
        "Data Center Compute": "accelerated-computing",
        "Networking": "networking",
        "AI Software & Cloud": "artificial-intelligence",
        "Gaming/Consumer": "gaming-and-creating",
        "Pro Viz/Design/Simulation": "professional-visualization-and-workstations",
        "Robotics/Edge/Embedded": "embedded-robotics-and-edge",
        "Automotive": "automotive",
        "Healthcare/Life Sciences": "healthcare-and-life-sciences",
    }


def test_missing_or_future_retrieval_time_is_clamped_to_build_start():
    build_start = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    assert normalized_retrieval_datetime(
        None, build_started_at=build_start
    ) == ("2026-08-25T12:00:00+00:00", True)
    assert normalized_retrieval_datetime(
        "2026-08-25T23:59:59+08:00", build_started_at=build_start
    ) == ("2026-08-25T12:00:00+00:00", True)
    assert normalized_retrieval_datetime(
        "2026-08-25T11:00:00+00:00", build_started_at=build_start
    ) == ("2026-08-25T11:00:00+00:00", False)
    assert normalized_datetime(None) != "None"


def test_npn_access_restriction_string_is_preserved_in_source_policy():
    note = "Public NPN directory; no access-control bypass."
    assert source_access_policy(note)["notes"] == note


def test_access_policy_explains_retrieval_timestamp_normalization():
    policy = source_access_policy(
        "Public source.", retrieval_timestamp_normalized=True
    )
    assert "missing/future" in policy["notes"]


def test_listing_regions_are_derived_from_each_security_market():
    entities = {
        "dual-listed": {
            "id": "dual-listed",
            "listing_status": "listed",
            "securities": [
                {"ticker": "AAA", "exchange": "NYSE", "primary": False},
                {"ticker": "0001", "exchange": "Hong Kong Stock Exchange", "primary": True},
            ],
        }
    }
    annotate_listing_regions(entities)
    assert entities["dual-listed"]["listing_regions"] == ["Hong Kong", "United States"]
    assert entities["dual-listed"]["securities"][0]["listing_region_code"] == "US"
    assert entities["dual-listed"]["securities"][1]["listing_region_code"] == "HK"
    assert len(EXCHANGE_LISTING_REGION) >= 42
    assert EXCHANGE_LISTING_REGION["National Stock Exchange of India"] == ("India", "IN")


def test_final_source_times_cannot_exceed_snapshot_generation_time():
    snapshot = {
        "meta": {"generated_at": "2026-08-25T12:00:00+00:00"},
        "sources": [{"id": "source-a", "retrieved_at": "2026-08-25T12:00:01+00:00"}],
    }
    with pytest.raises(ValueError, match="retrieval time exceeds"):
        validate_source_retrieval_times(snapshot)
    snapshot["sources"][0]["retrieved_at"] = "2026-08-25T12:00:00+00:00"
    validate_source_retrieval_times(snapshot)


def test_snapshot_validator_accepts_option_or_positional_path_not_both():
    assert parse_validate_args([]).snapshot is None
    assert str(parse_validate_args(["--snapshot", "one.json"]).snapshot) == "one.json"
    assert str(parse_validate_args(["two.json"]).snapshot) == "two.json"
    with pytest.raises(SystemExit):
        parse_validate_args(["one.json", "--snapshot", "two.json"])
