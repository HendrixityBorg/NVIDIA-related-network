#!/usr/bin/env python3
"""Independent validation for Partner regulatory entity normalization."""

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT.parents[3] / "data/snapshot_2026-08-25.json"


def jl(name):
    return [json.loads(x) for x in (ROOT / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> int:
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    universe, merge, overlay, ambiguous = jl("canonical_partner_universe.jsonl"), jl("entity_merge_map.jsonl"), jl("entity_registry_overlay.jsonl"), jl("manual_multilisting_review.jsonl")
    rel_ids = {r["id"] for r in snap["relationships"]}
    ev_ids = {e["id"] for e in snap["evidence"]}
    src_ids = {s["id"] for s in snap["sources"]}
    by_original = {r["original_entity_id"]: r for r in merge}
    duplicate_groups = [r for r in universe if r["member_count"] > 1]
    required = [
        {"coreweave", "npn-issuer-0f21b8aa69ac3580"},
        {"entity_70b6644e2c2a916d", "npn-issuer-b77edd9e7010e111"},
        {"entity_e4b76123e847422c", "t_mobile_us"},
        {"alibaba", "entity_448ee47d0990d0c2"},
        {"entity_c13dcedb27ebe7f7", "npn-issuer-8603eeefab8517c7"},
        {"elastic", "entity_cff4787c0eeaf22e"},
        {"entity_1ba13f36f5792a1b", "npn-issuer-fc55b1f0a87affc6"},
        {"entity_30f6a80d17a88625", "entity_30f6d340bb3ce3f2"},
        {"entity_8a954030356bd7f0", "verizon"},
        {"quanta", "quanta_computer"},
    ]
    sets = [set(r["member_entity_ids"]) for r in duplicate_groups]
    checks = {
        "all_329_original_partner_entities_mapped_once": len(merge) == 329 == len(by_original),
        "canonical_partition_closes": sum(r["member_count"] for r in universe) == 329 and len(universe) == 316,
        "all_decisions_terminal_zero_pending": all(r["status"] == "terminal" and r["pending"] is False for r in merge),
        "required_ten_duplicate_groups_fixed": all(any(req <= got for got in sets) for req in required),
        "duplicate_groups_have_exact_basis": all(r["merge_bases"] and all(b["identifier_type"] in {"cik", "exchange_ticker", "isin", "legal_name_exact"} for b in r["merge_bases"]) for r in duplicate_groups),
        "no_fuzzy_or_suffix_stripping_basis": all(all(b["identifier_type"] != "fuzzy" for b in r["merge_bases"]) for r in duplicate_groups),
        "overlay_exactly_duplicate_groups": len(overlay) == len(duplicate_groups) == 13,
        "relationship_refs_close": all(set(r["partner_relationship_ids"]) <= rel_ids for r in universe),
        "evidence_refs_close": all(set(r["relationship_evidence_ids"]) <= ev_ids for r in universe),
        "source_refs_close": all(set(r["relationship_source_ids"]) <= src_ids for r in universe),
        "source_records_preserved": all({s["id"] for s in r["relationship_sources"]} == set(r["relationship_source_ids"]) for r in universe),
        "original_entities_preserved_in_merge_map": all(r.get("original_entity", {}).get("id") == r["original_entity_id"] for r in merge),
        "security_union_not_empty": all(r["securities"] for r in universe),
        "npn_tag_fields_present": all(set(r["merged_npn_tags"]) == {"partner_types", "competencies", "specializations", "partner_levels", "locations", "product_service_tags", "npn_group_ids"} for r in universe),
        "multilisting_review_terminal": all(r["status"] == "needs_manual_multilisting_classification" and len(r["active_exchange_ticker_candidates"]) > 1 for r in ambiguous),
        "source_snapshot_hash_pinned": all(r["source_snapshot_sha256"] == hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest() for r in universe),
    }
    report = {
        "status": "pass" if all(checks.values()) else "fail", "checks": checks,
        "counts": {"snapshot_partner_listed_entities": len(merge), "canonical_partner_entities": len(universe), "duplicate_groups": len(duplicate_groups), "merged_away_entities": len(merge)-len(universe), "manual_multilisting_review": len(ambiguous)},
        "required_duplicate_groups": [sorted(x) for x in required],
    }
    (ROOT / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
