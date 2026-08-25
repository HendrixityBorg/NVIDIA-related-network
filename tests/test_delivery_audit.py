import json
from pathlib import Path

from scripts.audit_delivery import score_from_breakdown


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/snapshot_2026-08-25.json"
INTEGRATION = (
    ROOT
    / "runs/2026-08-25-run-003/agents/partner_regulatory_integration"
)
DELIVERY = ROOT / "runs/2026-08-25-run-003/delivery_review"


def jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_delivery_audit_passes_and_covers_every_supplier():
    report = json.loads((DELIVERY / "delivery_audit_report.json").read_text())
    suppliers = jsonl(DELIVERY / "supplier_audit.jsonl")
    assert report["status"] == "pass"
    assert report["counts"]["supplier_relationships"] == 16
    assert report["counts"]["supplier_unique_companies"] == 11
    assert len(suppliers) == 16
    assert all(row["primary_evidence"] for row in suppliers)
    assert report["checks"]["human_review_signoff_valid"] is True
    assert all(row["human_verified"] is True for row in suppliers)
    assert all(row["human_reviewed_at"] == "2026-08-26" for row in suppliers)


def test_iren_repeated_contexts_do_not_increase_independence():
    claims = jsonl(INTEGRATION / "claims.jsonl")
    claim = next(
        row
        for row in claims
        if row["subject_entity_id"] == "entity_045454fe093dec63"
        and row["relationship_type"] == "supplier"
    )
    assert claim["confidence_score"] == 89
    assert claim["confidence_breakdown"]["independence"] == 0
    assert claim["evidence_independence_stats"] == {
        "evidence_contexts": 17,
        "independence_rule": "five points per additional independent publisher; repeated contexts and same-publisher filings add zero independence",
        "unique_origin_publications": 3,
        "unique_publishers": 1,
    }
    assert len(claim["primary_evidence_ids"]) == 3


def test_company_news_only_supplier_claims_are_inferred():
    claims = jsonl(INTEGRATION / "claims.jsonl")
    by_subject = {
        (row["subject_entity_id"], row["product_scope_id"]): row
        for row in claims
        if row["relationship_type"] == "supplier"
    }
    for key in (("lumentum", "networking"), ("tsmc", "architectures-and-core-technologies")):
        assert by_subject[key]["source_kinds"] == ["company_news"]
        assert by_subject[key]["fact_status"] == "inferred"
        assert by_subject[key]["confidence_score"] < 60


def test_ambiguous_apac_invoicing_paths_remain_unclear():
    claims = jsonl(INTEGRATION / "claims.jsonl")
    directness = {
        row["object_entity_id"]: row["directness"]
        for row in claims
        if row["relationship_type"] == "customer"
    }
    assert directness["snet_systems"] == "unclear"
    assert directness["tatung_system"] == "unclear"


def test_snapshot_scores_still_equal_breakdown_and_status_caps():
    snapshot = json.loads(SNAPSHOT.read_text())
    assert all(
        row["confidence_score"] == score_from_breakdown(row)
        for row in snapshot["relationships"]
    )
