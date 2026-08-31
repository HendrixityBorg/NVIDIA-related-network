#!/usr/bin/env python3
"""Independent validation for SEC Partner direction review."""

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN = ROOT.parents[1]


def jl(name): return [json.loads(x) for x in (ROOT / name).read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> int:
    collection = json.loads((RUN / "agents/partner_regulatory_review/collection_summary.json").read_text())
    contexts = [json.loads(x) for x in (RUN / "agents/partner_regulatory_review/mention_contexts.jsonl").read_text().splitlines() if x]
    documents = [json.loads(x) for x in (RUN / "agents/partner_regulatory_review/filing_documents.jsonl").read_text().splitlines() if x]
    product_keys = {r["canonical_key"] for r in (json.loads(x) for x in (RUN / "product_tree_v2/canonical_index_v2.jsonl").read_text().splitlines() if x)} | {"corporate_general"}
    universe = {r["canonical_entity_id"] for r in (json.loads(x) for x in (RUN / "agents/partner_regulatory_entity_normalization/canonical_partner_universe.jsonl").read_text().splitlines() if x)}
    candidates, claims, evidence, decisions, frontier = map(jl, ["relationship_candidates.jsonl", "relationship_claims.jsonl", "evidence.jsonl", "decision_ledger.jsonl", "source_frontier.jsonl"])
    evidence_ids = {r["evidence_id"] for r in evidence}
    candidate_ids = {r["candidate_id"] for r in candidates}
    claim_keys = {r["dedup_key"] for r in claims}
    by_entity_rel = {(r["subject_entity_id"], r["object_entity_id"], r["relationship_type"]) for r in claims}
    claim_counts = Counter(f"{r['relationship_type']}:{r['fact_status']}:{r['directness']}" for r in claims)
    frontier_counts = Counter(r["terminal_status"] for r in frontier)
    candidate_mentions = {r["mention_id"] for r in candidates}
    approved_mentions = {r["mention_id"] for r in decisions if r["decision"] == "approved"}
    decisions_by_mention = {r["mention_id"]: r for r in decisions}
    contexts_by_mention = {r["mention_id"]: r for r in contexts}
    fabrinet_claims = [r for r in claims if r["subject_entity_id"] == "fabrinet" and r["relationship_type"] == "supplier"]
    checks = {
        "collection_gate_retrieved_documents_positive": collection["retrieved_documents"] > 0,
        "frozen_collection_470_documents_1973_contexts": collection["retrieved_documents"] == len(documents) == 470 and collection["mention_contexts"] == len(contexts) == 1973,
        "collection_declares_no_access_bypass": collection["access_control_bypass"] is False,
        "collection_counts_match_files": collection["mention_contexts"] == len(contexts) and collection["retrieved_documents"] == len(documents),
        "all_contexts_terminal_once": len(contexts) == len(decisions) == len({r["mention_id"] for r in decisions}) == len(contexts_by_mention),
        "zero_pending": all(r["status"] == "terminal" and r["pending"] is False for r in decisions),
        "one_evidence_per_context": len(evidence) == len(contexts) == len(evidence_ids) and {r["mention_id"] for r in evidence} == {r["mention_id"] for r in contexts},
        "decision_evidence_refs_close": all(r["evidence_id"] in evidence_ids for r in decisions),
        "candidate_evidence_refs_close": all(r["evidence_id"] in evidence_ids for r in candidates),
        "claim_refs_close": all(set(r["evidence_ids"]) <= evidence_ids and set(r["candidate_ids"]) <= candidate_ids for r in claims),
        "claim_keys_unique": len(claim_keys) == len(claims),
        "generic_and_descriptive_output_aliases_match": (ROOT / "candidates.jsonl").read_bytes() == (ROOT / "relationship_candidates.jsonl").read_bytes() and (ROOT / "claims.jsonl").read_bytes() == (ROOT / "relationship_claims.jsonl").read_bytes(),
        "approved_context_candidate_bijection": approved_mentions == candidate_mentions and len(candidates) == len(candidate_mentions),
        "canonical_entity_ids_only": all(r["canonical_entity_id"] in universe for r in decisions + candidates) and all(({r["subject_entity_id"], r["object_entity_id"]} - {"nvidia"}) <= universe for r in claims),
        "product_scopes_are_canonical_or_corporate_general": all(r["product_scope_id"] in product_keys for r in candidates + claims),
        "supplier_confirmed_direction": all(r["fact_status"] == "confirmed" and r["direction"] == "supplies_to" and r["object_entity_id"] == "nvidia" for r in claims if r["relationship_type"] == "supplier"),
        "customer_confirmed_direction": all(r["direction"] == "sells_to" and r["subject_entity_id"] == "nvidia" for r in claims if r["relationship_type"] == "customer" and r["fact_status"] == "confirmed"),
        "inferred_customer_cap_and_directness": all(r["confidence_score"] <= 59 and r["directness"] == "unclear" and r["direction"] == "sells_to" for r in claims if r["relationship_type"] == "customer" and r["fact_status"] == "inferred"),
        "rejected_contexts_not_candidates": not ({r["mention_id"] for r in decisions if r["decision"] == "rejected_non_directional"} & {r["mention_id"] for r in candidates}),
        "quantinuum_compatibility_not_directional": all(r["decision"] == "rejected_non_directional" for r in decisions if r["canonical_entity_id"] == "entity_73ba1f6eff1a76fc"),
        "coreweave_dual_confirmed": ("coreweave", "nvidia", "supplier") in by_entity_rel and ("nvidia", "coreweave", "customer") in by_entity_rel and all(r["fact_status"] == "confirmed" for r in claims if {r["subject_entity_id"], r["object_entity_id"]} == {"coreweave", "nvidia"}),
        "known_coreweave_payment_retained": any("$320 million" in r["quantitative_mentions"] for r in claims if r["subject_entity_id"] == "coreweave" and r["relationship_type"] == "supplier"),
        "known_sk_hynix_supplier_confirmed": ("sk-hynix", "nvidia", "supplier") in by_entity_rel,
        "iren_dual_confirmed": ("entity_045454fe093dec63", "nvidia", "supplier") in by_entity_rel and ("nvidia", "entity_045454fe093dec63", "customer") in by_entity_rel and all(r["fact_status"] == "confirmed" for r in claims if {r["subject_entity_id"], r["object_entity_id"]} == {"entity_045454fe093dec63", "nvidia"}),
        "fabrinet_supplier_revenue_percentages_retained": len(fabrinet_claims) == 1 and {"16.3%", "27.6%", "35.1%"} <= {x.replace(" ", "") for x in fabrinet_claims[0]["quantitative_mentions"]},
        "bitdeer_direct_purchase_confirmed": any(r["object_entity_id"] == "npn-issuer-ad81309481717c2b" and r["relationship_type"] == "customer" and r["fact_status"] == "confirmed" and "$13.2 million" in r["quantitative_mentions"] for r in claims),
        "new_exact_use_cases_inferred_not_confirmed": all(any(r["object_entity_id"] == entity and r["relationship_type"] == "customer" and r["fact_status"] == "inferred" and r["directness"] == "unclear" for r in claims) for entity in ("npn-issuer-ea0992ccf8964407", "npn-issuer-707b51d1c6951b12", "weride", "aurora_innovation", "telus", "npn-issuer-61a6a741280baa3b", "cognizant", "npn-issuer-e4cd6add33e52e4e")),
        "media_partnership_risk_false_positives_rejected": all(decisions_by_mention[mid]["decision"] == "rejected_non_directional" for mid in ("regmention_46992801d23486e57b39", "regmention_25dbefebf9f8e3193cc7", "regmention_00cbf4e8053cceefc96b")),
        "arm_magna_applied_digital_not_promoted": not any(({r["subject_entity_id"], r["object_entity_id"]} & {"arm_holdings", "magna", "npn-issuer-f83a62c5a610a538"}) for r in claims),
        "direction_fact_directness_partition": set(claim_counts) <= {"supplier:confirmed:explicit", "customer:confirmed:explicit", "customer:inferred:unclear"} and sum(claim_counts.values()) == len(claims),
        "frontier_canonical_partition": len(frontier) == len(universe) == 316 and len({r["canonical_entity_id"] for r in frontier}) == 316,
        "frontier_frozen_status_partition": frontier_counts == Counter({"non_sec_route_required": 146, "regulatory_hit_reviewed_terminal": 89, "searched_no_nvidia_hit": 81}) and sum(bool(r["ciks"]) for r in frontier) == 170,
        "frontier_terminal_zero_pending": all(r["status"] == "terminal" and r["pending"] is False for r in frontier),
        "evidence_has_required_trace_fields": all(all(r.get(k) is not None for k in ("excerpt", "evidence_locator", "source_url", "form", "file_date", "publisher", "retrieved_at")) for r in evidence),
    }
    report = {
        "status": "pass" if all(checks.values()) else "fail", "checks": checks,
        "counts": {"contexts": len(contexts), "decisions": len(decisions), "candidates": len(candidates), "claims": len(claims), "evidence": len(evidence), "frontier": len(frontier), "pending": sum(r["pending"] for r in decisions)},
    }
    (ROOT / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
