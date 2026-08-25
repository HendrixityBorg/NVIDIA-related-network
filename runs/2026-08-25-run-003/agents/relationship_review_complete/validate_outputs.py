#!/usr/bin/env python3
"""Independent validator for relationship-review outputs."""

from __future__ import annotations

import json
import hashlib
from collections import Counter
from pathlib import Path

from arti.research_policy import (
    LOW_CONFIDENCE_PARTNER_CAPS,
    ResearchedEntityResolution,
    low_confidence_partner_score_is_valid,
)


HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
ARTI = RUN.parents[1]


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def manifest_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ARTI / path


def overlay_registry_ids(manifest: dict) -> set[str]:
    """Mirror the builder's conservative overlay eligibility for independent QA."""
    raw_path = manifest.get("global_listing_overlay")
    if not raw_path:
        return set()
    path = manifest_path(raw_path)
    if not path.is_dir():
        return set()
    result = set()
    evidence = {row.get("listing_evidence_id"): row for row in rows(path / "listing_evidence.jsonl")}
    valid_evidence = {
        evidence_id for evidence_id, row in evidence.items()
        if evidence_id and row.get("source_url") and row.get("publisher") and row.get("evidence_locator") and row.get("access_constraints")
    }
    for row in rows(path / "entity_registry_overlay.jsonl"):
        evidence_ids = set(row.get("listing_evidence_ids") or [])
        if row.get("listing_status") == "listed_confirmed" and evidence_ids and evidence_ids.issubset(valid_evidence):
            result.add(row.get("merge_target_entity_id") if row.get("merge_action") == "augment_existing" else row.get("entity_id"))
    return result


def main() -> int:
    decisions = rows(HERE / "decision_ledger.jsonl")
    claims = rows(HERE / "claims.jsonl")
    evidence = rows(HERE / "evidence_fingerprints.jsonl")
    scoring = rows(HERE / "scoring_inputs.jsonl")
    product_keys = {r["canonical_key"] for r in rows(RUN / "product_tree_v2" / "canonical_index_v2.jsonl")} | {"corporate_general"}
    manifest = json.loads((HERE / "input_manifest.json").read_text(encoding="utf-8"))
    registry = {r["entity_id"] for r in rows(RUN / "agents" / "entity_resolution_complete" / "entity_registry.jsonl")} | overlay_registry_ids(manifest)
    researched_registry_files = (
        manifest.get("researched_entity_registry_overlays", {}).get("files", [])
    )
    registry |= {
        row["entity_id"]
        for item in researched_registry_files
        for row in rows(manifest_path(item["path"]))
        if row.get("listing_status") in {"listed", "listed_confirmed"}
    }
    expected_paths = [RUN / item["path"] for item in manifest["input_files"]]
    expected = sum(len(rows(path)) for path in expected_paths)
    terminal = {"approve_unknown", "reject", "needs_more_evidence", "approved"}
    evidence_ids = {r["evidence_id"] for r in evidence}
    evidence_by_id = {r["evidence_id"]: r for r in evidence}
    claim_ids = {r["claim_id"] for r in claims}
    investees = [r for r in claims if r["relationship_type"] == "investee"]
    recovery_dir = manifest_path(manifest["article_recovery_dir"]) if manifest.get("article_recovery_dir") else None
    researched_path = (
        manifest_path(manifest["researched_entity_resolution_ledger"])
        if manifest.get("researched_entity_resolution_ledger")
        else None
    )
    researched_rows = (
        [ResearchedEntityResolution.model_validate(row) for row in rows(researched_path)]
        if researched_path and researched_path.exists()
        else []
    )
    researched_ids = {row.resolution_id for row in researched_rows}
    blocked_article_ids = {
        row.get("article_id")
        for row in rows(recovery_dir / "article_processing.jsonl")
        if row.get("processing_status") == "access_blocked" or row.get("body_coverage_status") != "complete"
    } if recovery_dir and (recovery_dir / "article_processing.jsonl").exists() else set()
    checks = {
        "decision_count_matches_inputs": len(decisions) == expected,
        "decision_ids_unique": len(decisions) == len({r["decision_id"] for r in decisions}),
        "all_terminal": all(r["terminal_status"] in terminal for r in decisions),
        "zero_pending": not any(r["terminal_status"] not in terminal for r in decisions),
        "claim_ids_unique": len(claims) == len(claim_ids),
        "dedup_keys_unique": len(claims) == len({r["dedup_key"] for r in claims}),
        "dedup_key_exact_fields": all(r["dedup_key"] == "|".join([r["subject_entity_id"], r["object_entity_id"], r["direction"], r["relationship_type"], r["product_scope_id"]]) for r in claims),
        "one_product_per_claim": all(r["product_scope_id"] in product_keys for r in claims),
        "roles_in_scope": all(r["relationship_type"] in {"supplier", "customer", "partner", "investee"} for r in claims),
        "entities_resolved": all((r["subject_entity_id"] == "nvidia" or r["subject_entity_id"] in registry) and (r["object_entity_id"] == "nvidia" or r["object_entity_id"] in registry) for r in claims),
        "evidence_ids_unique": len(evidence) == len(evidence_ids),
        "evidence_fingerprints_unique": len(evidence) == len({r["fingerprint_sha256"] for r in evidence}),
        "claim_evidence_valid": all(set(r["evidence_ids"]).issubset(evidence_ids) for r in claims),
        "source_provenance_complete": all(r.get("source_url") and r.get("publisher") and r.get("evidence_locator") and r.get("access_constraints") for r in evidence),
        "input_manifest_rows_match": all(len(rows(RUN / item["path"])) == item["rows"] for item in manifest["input_files"]),
        "approved_have_claims": all(r["generated_claim_keys"] for r in decisions if r["terminal_status"] == "approved"),
        "low_terminal_included_or_researched_nonlisted": all(
            row["generated_claim_keys"]
            or (
                row.get("researched_entity_resolution_id") in researched_ids
                and not row.get("entity_id")
            )
            for row in decisions
            if row["terminal_status"] in LOW_CONFIDENCE_PARTNER_CAPS
        ),
        "reject_has_no_claim": all(
            not row["generated_claim_keys"]
            for row in decisions
            if row["terminal_status"] == "reject"
        ),
        "low_claims_partner_only_and_capped": all(
            row["relationship_type"] == "partner"
            and row["direction"] == "partners_with"
            and row["confidence_score"]
            <= min(
                LOW_CONFIDENCE_PARTNER_CAPS[status]
                for status in row["origin_terminal_statuses"]
                if status in LOW_CONFIDENCE_PARTNER_CAPS
            )
            for row in claims
            if row.get("low_confidence_partner_inclusion")
        ),
        "low_claim_score_breakdown_and_fact_status_contract": all(
            low_confidence_partner_score_is_valid(row)
            for row in claims
            if row.get("low_confidence_partner_inclusion")
        ),
        "origin_status_and_inference_explanation_retained": all(
            row.get("origin_terminal_statuses")
            and (
                not row.get("low_confidence_partner_inclusion")
                or row.get("inference_explanations")
            )
            for row in claims
        ),
        "all_claim_input_evidence_retained": all(
            set(claim["evidence_ids"])
            == (
                {
                    decision["evidence_id"]
                    for decision in decisions
                    if claim["dedup_key"] in decision["generated_claim_keys"]
                }
                | {
                    evidence_id
                    for decision in decisions
                    if claim["dedup_key"] in decision["generated_claim_keys"]
                    for evidence_id in decision.get(
                        "entity_resolution_research_evidence_ids", []
                    )
                }
            )
            for claim in claims
        ),
        "entity_resolution_evidence_materialized": all(
            evidence_by_id.get(evidence_id, {}).get("source_family") == "entity_resolution"
            and evidence_by_id.get(evidence_id, {}).get("evidence_purpose")
            == "entity_resolution_only_no_relationship_score_credit"
            for claim in claims
            for evidence_id in claim.get("entity_resolution_evidence_ids", [])
        ),
        "entity_resolution_evidence_excluded_from_relationship_scoring": all(
            score.get("entity_resolution_evidence_excluded_from_relationship_scoring")
            is True
            and score.get("evidence_count_after_fingerprint_dedup")
            == len(claim.get("relationship_evidence_ids", []))
            for claim in claims
            for score in scoring
            if score["claim_id"] == claim["claim_id"]
        ),
        "researched_entity_resolution_required": bool(
            manifest.get("researched_entity_resolution_required")
            and researched_path
            and researched_path.exists()
            and researched_rows
        ),
        "researched_entity_resolution_hash_matches": bool(
            researched_path
            and researched_path.exists()
            and hashlib.sha256(researched_path.read_bytes()).hexdigest()
            == manifest.get("researched_entity_resolution_sha256")
        ),
        "seven_investees": len(investees) == 7,
        "investee_only_latest_13f": all(r["source_families"] == ["13f"] and r["as_of"] == "2026-06-30" for r in investees),
        "article_investment_boundary": not any("official_article" in r["source_families"] for r in investees),
        "anchor_mentions_never_exceed_unknown_partner": all(
            not row["generated_claim_keys"]
            or row["terminal_status"] == "approve_unknown"
            for row in decisions
            if row["original_relationship_hint"] == "mention_only"
        ),
        "presentation_logo_architecture_never_exceed_low_partner": all(
            not r["generated_claim_keys"]
            or r["terminal_status"] in LOW_CONFIDENCE_PARTNER_CAPS
            for r in decisions
            if r["input_source_path"].endswith("filings_presentations_complete/listed_candidates.jsonl")
            and evidence_by_id[r["evidence_id"]].get("source_family") == "presentation"
        ),
        "listed_entities_have_exchange_ticker": all(
            all(identifier and ":" in identifier for identifier in endpoint.get("security_identifiers", []))
            for claim in claims
            for endpoint in [claim["subject_entity"], claim["object_entity"]]
            if endpoint["entity_id"] != "nvidia"
        ),
        "overlay_manifest_hashes_match": all(
            manifest_path(item["path"]).exists() and hashlib.sha256(manifest_path(item["path"]).read_bytes()).hexdigest() == item["sha256"]
            for item in manifest.get("global_listing_overlay_files", [])
        ),
        "researched_registry_overlay_hashes_match": all(
            manifest_path(item["path"]).exists()
            and hashlib.sha256(manifest_path(item["path"]).read_bytes()).hexdigest()
            == item["sha256"]
            for item in researched_registry_files
        ),
        "recovery_control_hashes_match": all(
            manifest_path(item["path"]).exists() and hashlib.sha256(manifest_path(item["path"]).read_bytes()).hexdigest() == item["sha256"]
            for item in manifest.get("article_recovery_control_files", [])
        ),
        "blocked_recovery_articles_never_exceed_unknown_partner": all(
            not row["generated_claim_keys"]
            or row["terminal_status"] == "approve_unknown"
            for row in decisions
            if row.get("source_article_id") in blocked_article_ids
        ),
        "inferred_supplier_customer_cap": all(r["confidence_score"] <= 59 for r in claims if r["relationship_type"] in {"supplier", "customer"} and r["fact_status"] == "inferred"),
        "score_range": all(0 <= r["confidence_score"] <= 100 for r in claims),
        "one_scoring_row_per_claim": len(scoring) == len(claims) and {r["claim_id"] for r in scoring} == claim_ids,
    }
    result = {
        "pass": all(checks.values()), "checks": checks,
        "input_observations": expected, "decision_rows": len(decisions),
        "decision_status_counts": dict(sorted(Counter(r["terminal_status"] for r in decisions).items())),
        "claims": len(claims), "claim_type_counts": dict(sorted(Counter(r["relationship_type"] for r in claims).items())),
        "evidence_fingerprints": len(evidence), "pending": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
