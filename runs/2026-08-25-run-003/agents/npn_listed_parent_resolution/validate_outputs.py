#!/usr/bin/env python3
"""Independent fail-closed validation for the NPN listed-parent overlay."""

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN = ROOT.parents[1]


def jl(name):
    return [json.loads(x) for x in (ROOT / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    checks = {}
    decisions = jl("mapping_decision_ledger.jsonl")
    maps = jl("resolved_parent_mappings.jsonl")
    unresolved = jl("unresolved_review_queue.jsonl")
    rejected = jl("rejected_candidates.jsonl")
    evidence = {r["evidence_id"]: r for r in jl("mapping_evidence.jsonl")}
    overlay_claims = jl("relationship_claims_overlay.jsonl")
    complete_claims = jl("relationship_claims_complete.jsonl")
    prior = [json.loads(x) for x in (RUN / "agents/npn_runtime_complete/listed_group_matches.jsonl").read_text().splitlines() if x]
    groups = [json.loads(x) for x in (RUN / "agents/npn_runtime_complete/entity_groups.jsonl").read_text().splitlines() if x]
    checks["exactly_950_target_decisions"] = len(decisions) == 950 == len({r["group_id"] for r in decisions})
    checks["all_973_groups_accounted_for"] = len(prior) + len(decisions) == len(groups) == 973 and not ({r["group_id"] for r in prior} & {r["group_id"] for r in decisions})
    checks["zero_pending_all_terminal"] = all(r.get("status") == "terminal" and r.get("pending") is False for r in decisions)
    checks["partition_closes"] = len(maps) + len(unresolved) + len(rejected) == 950
    checks["no_fuzzy_promotion"] = all(r.get("fuzzy_matching_used") is False for r in decisions + maps)
    checks["one_mapping_per_group"] = len(maps) == len({r["group_id"] for r in maps})
    checks["all_securities_exchange_ticker_active"] = all(m["securities"] and all(s.get("exchange") and s.get("ticker") and s.get("status_at_cutoff") == "active_at_cutoff" for s in m["securities"]) for m in maps)
    checks["all_evidence_refs_close"] = all(set(m["all_evidence_ids"]) <= evidence.keys() for m in maps)
    checks["direct_status_and_cap"] = all(m["fact_status_recommendation"] == "confirmed" and m["confidence_cap_recommendation"] == 95 for m in maps if m["resolution_kind"] == "direct_issuer")
    checks["parent_status_and_cap"] = all(m["fact_status_recommendation"] == "inferred" and m["confidence_cap_recommendation"] < 95 and any(evidence[e].get("evidence_type") == "brand_or_subsidiary_parent_mapping" for e in m["mapping_evidence_ids"]) for m in maps if m["resolution_kind"] != "direct_issuer")
    checks["each_mapping_has_npn_and_listing_evidence"] = all(m["npn_evidence_ids"] and m["mapping_evidence_ids"] for m in maps)
    byname = {m["npn_name"]: m for m in maps}
    reject_names = {r["candidate_name"] for r in rejected}
    checks["known_false_homonyms_rejected"] = {"Compugen Inc", "TEN Inc", "Cronos"} <= reject_names
    checks["edf_not_promoted"] = "EXAION (EDF GROUP)" in reject_names and "EXAION (EDF GROUP)" not in byname
    checks["temporal_parent_corrections"] = (
        byname["NTT Data Group Corporation"]["entity_id"] == "ntt" and
        byname["SCSK Corporation"]["entity_id"] == "sumitomo_corporation" and
        byname["Okaya Electronics Corp."]["entity_id"] == "okaya_co" and
        byname["Nebius B.V."]["resolution_kind"] == "subsidiary_to_parent" and
        byname["Atea A/S"]["resolution_kind"] == "subsidiary_to_parent"
    )
    checks["no_failed_market_metadata"] = not jl("failed_yahoo_symbols.jsonl")
    sec_hash = hashlib.sha256((ROOT / "company_tickers_exchange.json").read_bytes()).hexdigest()
    checks["sec_fixture_hash_pinned"] = sec_hash == "18ea4fbc84ee31d7320907ebf176df92013a28e4d304c95ef3f9674dfd373410"
    checks["claim_keys_unique"] = len(overlay_claims) == len({r["dedup_key"] for r in overlay_claims}) and len(complete_claims) == len({r["dedup_key"] for r in complete_claims})
    npn_evidence = {json.loads(x)["evidence_id"] for x in (RUN / "agents/npn_runtime_complete/evidence.jsonl").read_text().splitlines() if x}
    checks["claim_evidence_union_closes"] = all(set(r["evidence_ids"]) <= (evidence.keys() | npn_evidence) for r in complete_claims)
    checks["claim_tags_and_groups_retained"] = all(r.get("npn_group_ids") and r.get("partner_types") is not None and r.get("locations") is not None for r in overlay_claims)
    checks["claim_fact_status_matches_endpoint_resolution"] = all((r["fact_status"] == "confirmed") == ("direct_issuer" in r["resolution_kinds"]) for r in overlay_claims)
    report = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "counts": {"decisions": len(decisions), "resolved_groups": len(maps), "resolved_entities": len({m['entity_id'] for m in maps}), "unresolved": len(unresolved), "rejected": len(rejected), "resolution_kinds": dict(Counter(m["resolution_kind"] for m in maps)), "new_claims": len(overlay_claims), "complete_claims": len(complete_claims)},
    }
    (ROOT / "validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
