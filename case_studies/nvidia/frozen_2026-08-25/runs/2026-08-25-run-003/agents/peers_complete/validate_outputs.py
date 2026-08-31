#!/usr/bin/env python3
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "Data Center Compute", "Networking", "AI Software & Cloud", "Gaming/Consumer",
    "Pro Viz/Design/Simulation", "Robotics/Edge/Embedded", "Automotive",
    "Healthcare/Life Sciences",
}


def load(name):
    return [json.loads(x) for x in (HERE / name).read_text(encoding="utf-8").splitlines() if x.strip()]


peers = load("peer_candidates.jsonl")
reviews = load("category_review_ledger.jsonl")
evidence = load("source_evidence.jsonl")
eids = {e["evidence_id"] for e in evidence}
errors = []

if {r["category"] for r in reviews} != EXPECTED:
    errors.append("category ledger does not cover exactly the eight required categories")
if len(reviews) != 8:
    errors.append("category ledger must contain exactly eight rows")
if any(r["review_status"] != "complete" or r["pending_count"] != 0 for r in reviews):
    errors.append("all categories must be complete with zero pending")

review_counts = {r["category"]: r["accepted_count"] for r in reviews}
actual_counts = {c: sum(p["product_category_id"] == c for p in peers) for c in EXPECTED}
if review_counts != actual_counts:
    errors.append(f"ledger counts do not match peer records: {review_counts} != {actual_counts}")

keys = []
for p in peers:
    keys.append((p["subject_entity_id"], p["object_legal_name"], p["direction"], p["relationship_type"], p["product_category_id"]))
    if p["review_status"] != "accepted": errors.append(f"non-accepted row in candidates: {p['peer_candidate_id']}")
    if p["security"]["status_at_cutoff"] != "listed_confirmed": errors.append(f"listing not confirmed: {p['peer_candidate_id']}")
    if p["self_developed"] is not True: errors.append(f"self-developed gate failed: {p['peer_candidate_id']}")
    if p["fact_status"] not in {"confirmed", "inferred"}: errors.append(f"bad fact status: {p['peer_candidate_id']}")
    if not (0 <= p["confidence_score"] <= 100): errors.append(f"score out of range: {p['peer_candidate_id']}")
    if p["fact_status"] == "inferred" and p["confidence_score"] > 69: errors.append(f"inferred score exceeds 69 contract cap: {p['peer_candidate_id']}")
    if p["fact_status"] == "inferred" and p["confidence_factors"].get("fact_status_score_cap") != 69: errors.append(f"inferred cap not documented: {p['peer_candidate_id']}")
    if p["fact_status"] == "inferred" and "cannot exceed 69/100" not in p["review_rationale"]: errors.append(f"inferred rationale omits cap: {p['peer_candidate_id']}")
    if not p["evidence_ids"] or any(e not in eids for e in p["evidence_ids"]): errors.append(f"missing evidence ref: {p['peer_candidate_id']}")
    if p["product_category_id"] not in EXPECTED: errors.append(f"unexpected category: {p['peer_candidate_id']}")
if len(keys) != len(set(keys)):
    errors.append("duplicate category-level peer relationship key")

for e in evidence:
    for field in ("url", "publisher", "retrieved_at", "evidence_locator", "short_excerpt", "access_constraints"):
        if not e.get(field): errors.append(f"evidence {e['evidence_id']} missing {field}")
    if e["access_constraints"].get("robots_or_access_control_bypassed") is not False:
        errors.append(f"access policy violation: {e['evidence_id']}")

report = {
    "pass": not errors,
    "errors": errors,
    "categories_reviewed": len(reviews),
    "peer_relationship_records": len(peers),
    "unique_peer_issuers": len({p["security"]["ticker"] for p in peers}),
    "source_evidence_records": len(evidence),
    "pending_count": sum(r["pending_count"] for r in reviews),
}
(HERE / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2))
raise SystemExit(0 if not errors else 1)
