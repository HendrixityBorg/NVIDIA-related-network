#!/usr/bin/env python3
"""Conservative SEC-context direction review for normalized Partner entities."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def cj(v: Any) -> str: return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
def hid(prefix: str, v: Any) -> str: return prefix + hashlib.sha256(cj(v).encode()).hexdigest()[:18]
def write_jsonl(path: Path, rows): path.write_text("".join(cj(r) + "\n" for r in rows), encoding="utf-8")


def matches(text: str, rule: dict[str, Any], canonical_id: str, form: str) -> bool:
    low = text.casefold()
    allowed_entities = rule.get("canonical_entity_ids", [])
    allowed_forms = rule.get("forms", [])
    if allowed_entities and canonical_id not in allowed_entities:
        return False
    if allowed_forms and form not in allowed_forms:
        return False
    required = rule.get("required_patterns", [])
    any_patterns = rule.get("any_patterns", [])
    return all(x.casefold() in low for x in required) and (not any_patterns or any(x.casefold() in low for x in any_patterns))


def quantitative_mentions(text: str) -> list[str]:
    """Retain disclosed money, GPU counts and percentages without interpreting them."""
    patterns = [
        r"\$\s?\d+(?:\.\d+)?\s?(?:million|billion|m|bn)?",
        r"\b\d{1,3}(?:,\d{3})+\s+NVIDIA\s+[A-Z0-9]+\s+GPUs",
        r"\b\d+(?:\.\d+)?\s?%",
    ]
    return sorted({m.group(0) for p in patterns for m in re.finditer(p, text, re.I)})


def main() -> int:
    ap = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    run = here.parents[1]
    ap.add_argument("--input-dir", type=Path, default=run / "agents/partner_regulatory_review")
    ap.add_argument("--normalization-dir", type=Path, default=run / "agents/partner_regulatory_entity_normalization")
    ap.add_argument("--output-dir", type=Path, default=here)
    args = ap.parse_args()
    summary_in = json.loads((args.input_dir / "collection_summary.json").read_text(encoding="utf-8"))
    if int(summary_in.get("retrieved_documents", 0)) <= 0:
        raise RuntimeError("collection gate failed: collection_summary.retrieved_documents must be > 0")
    contexts = load_jsonl(args.input_dir / "mention_contexts.jsonl")
    documents = {r["document_id"]: r for r in load_jsonl(args.input_dir / "filing_documents.jsonl")}
    frontier_in = load_jsonl(args.input_dir / "source_frontier.jsonl")
    merge = {r["original_entity_id"]: r["canonical_entity_id"] for r in load_jsonl(args.normalization_dir / "entity_merge_map.jsonl")}
    rules = json.loads((args.output_dir / "rules_fixture.json").read_text(encoding="utf-8"))

    evidence_rows, decisions, candidates = [], [], []
    for ctx in contexts:
        doc = documents[ctx["document_id"]]
        canonical_ids = sorted({merge.get(eid, eid) for eid in ctx["entity_ids"]})
        if len(canonical_ids) != 1:
            raise ValueError(f"context {ctx['mention_id']} maps to {canonical_ids}")
        canonical_id = canonical_ids[0]
        eid = hid("sec-direction-evidence-", ctx["mention_id"])
        evidence_rows.append({
            "evidence_id": eid, "mention_id": ctx["mention_id"], "document_id": ctx["document_id"],
            "canonical_entity_id": canonical_id, "original_entity_ids": ctx["entity_ids"],
            "source_url": ctx["source_url"], "publisher": doc["publisher"], "form": ctx["form"],
            "file_date": ctx["file_date"], "accession": doc["accession"],
            "evidence_locator": ctx["evidence_locator"], "excerpt": ctx["excerpt"],
            "retrieved_at": doc["retrieved_at"], "source_content_sha256": doc["content_sha256"],
            "access": doc["access"], "redistribution": doc["redistribution"],
        })
        hit = next((r for r in rules["rules"] if matches(ctx["excerpt"], r, canonical_id, ctx["form"])), None)
        if hit:
            cls = hit["classification"]
            status = "approved"
            fact = "confirmed" if cls.endswith("confirmed") else "inferred"
            if cls.startswith("supplier"):
                rel, direction, subject, obj = "supplier", "supplies_to", canonical_id, "nvidia"
            else:
                rel, direction, subject, obj = "customer", "sells_to", "nvidia", canonical_id
            candidate = {
                "candidate_id": hid("sec-direction-candidate-", ctx["mention_id"] + cls),
                "canonical_entity_id": canonical_id, "original_entity_ids": ctx["entity_ids"],
                "subject_entity_id": subject, "object_entity_id": obj,
                "relationship_type": rel, "direction": direction, "fact_status": fact,
                "product_scope_id": hit["product_scope_id"], "directness": "explicit" if fact == "confirmed" else "unclear",
                "evidence_id": eid, "mention_id": ctx["mention_id"], "rule_id": hit["rule_id"],
                "reason": hit["reason"], "quantitative_mentions": quantitative_mentions(ctx["excerpt"]),
                "status": "terminal", "pending": False,
            }
            candidates.append(candidate)
            decision_reason = hit["reason"]
        else:
            status, fact = "rejected_non_directional", "unknown"
            low = ctx["excerpt"].casefold()
            reason_code = "no_explicit_commercial_direction"
            for code, patterns in rules["non_directional_patterns"].items():
                if any(x.casefold() in low for x in patterns):
                    reason_code = code; break
            decision_reason = {
                "compatibility_only": "Compatibility/interoperability does not establish purchase, sale, supplier, or customer direction.",
                "risk_or_competition": "Risk, competition, or upstream supply-chain discussion does not establish a direct NVIDIA transaction with this filer.",
                "partner_only": "Partnership/collaboration wording alone does not establish supplier/customer direction.",
                "reference_or_product_description_only": "A product/reference mention without explicit use, deployment, purchase, sale, or counterparty role is non-directional.",
                "no_explicit_commercial_direction": "The retained context does not establish NVIDIA as purchaser, revenue source, direct supplier, or a deployed product used by the filer.",
            }[reason_code]
        decisions.append({
            "decision_id": hid("sec-direction-decision-", ctx["mention_id"]), "mention_id": ctx["mention_id"],
            "canonical_entity_id": canonical_id, "original_entity_ids": ctx["entity_ids"],
            "decision": status, "fact_status": fact, "reason": decision_reason,
            "rule_id": hit["rule_id"] if hit else None, "evidence_id": eid,
            "status": "terminal", "pending": False,
        })

    # Aggregate approved contexts by canonical endpoint, role and one product scope.
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in candidates: grouped[(c["canonical_entity_id"], c["relationship_type"], c["product_scope_id"])].append(c)
    claims = []
    for (entity, rel, scope), rows in sorted(grouped.items()):
        confirmed = any(r["fact_status"] == "confirmed" for r in rows)
        subject, obj, direction = (entity, "nvidia", "supplies_to") if rel == "supplier" else ("nvidia", entity, "sells_to")
        claims.append({
            "claim_id": hid("sec-direction-claim-", [entity, rel, scope]),
            "dedup_key": f"{subject}|{obj}|{direction}|{rel}|{scope}",
            "subject_entity_id": subject, "object_entity_id": obj, "relationship_type": rel,
            "direction": direction, "product_scope_id": scope,
            "fact_status": "confirmed" if confirmed else "inferred",
            "confidence_score": 90 if confirmed else 56,
            "directness": "explicit" if confirmed else "unclear",
            "evidence_ids": sorted({r["evidence_id"] for r in rows}),
            "candidate_ids": sorted(r["candidate_id"] for r in rows),
            "original_entity_ids": sorted({x for r in rows for x in r["original_entity_ids"]}),
            "quantitative_mentions": sorted({x for r in rows for x in r["quantitative_mentions"]}),
            "source_family": "sec_regulatory_filing", "as_of": max(e["file_date"] for e in evidence_rows if e["evidence_id"] in {r["evidence_id"] for r in rows}),
            "direction_explanation": ("The filer explicitly identifies NVIDIA as purchaser/revenue source for services it supplies." if rel == "supplier" and confirmed else
                                      "The filer explicitly identifies NVIDIA as its seller/supplier." if confirmed else
                                      "The filing establishes use, deployment, ownership or purchase of NVIDIA-branded products, but not that NVIDIA was the direct seller."),
            "limitations": [] if confirmed else ["Direct seller/procurement counterparty is not identified in the retained context; customer direction is inferred and capped below 60."],
        })

    # Canonicalize and merge the 329-row collection frontier without erasing routes.
    frontier_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in frontier_in: frontier_groups[merge.get(row["entity_id"], row["entity_id"])].append(row)
    frontier_out = []
    for canonical, rows in sorted(frontier_groups.items()):
        statuses = sorted({r["terminal_status"] for r in rows})
        reviewed = any(s == "regulatory_hit_pending_review" for s in statuses)
        frontier_out.append({
            "canonical_entity_id": canonical, "original_entity_ids": sorted(r["entity_id"] for r in rows),
            "input_terminal_statuses": statuses,
            "terminal_status": "regulatory_hit_reviewed_terminal" if reviewed else (statuses[0] if len(statuses) == 1 else "merged_routes_terminal"),
            "ciks": sorted({c for r in rows for c in r.get("ciks", [])}),
            "listing_regions": sorted({x for r in rows for x in r.get("listing_regions", [])}),
            "queries": sorted({r["query"] for r in rows}), "date_from": min(r["date_from"] for r in rows), "date_to": max(r["date_to"] for r in rows),
            "status": "terminal", "pending": False,
        })

    out = args.output_dir; out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "relationship_candidates.jsonl", sorted(candidates, key=lambda r: r["candidate_id"]))
    write_jsonl(out / "relationship_claims.jsonl", claims)
    # Generic aliases match the hand-off contract; descriptive names remain for
    # consistency with the rest of the research pipeline.
    write_jsonl(out / "candidates.jsonl", sorted(candidates, key=lambda r: r["candidate_id"]))
    write_jsonl(out / "claims.jsonl", claims)
    write_jsonl(out / "evidence.jsonl", sorted(evidence_rows, key=lambda r: r["evidence_id"]))
    write_jsonl(out / "decision_ledger.jsonl", sorted(decisions, key=lambda r: r["mention_id"]))
    write_jsonl(out / "source_frontier.jsonl", frontier_out)
    out_summary = {
        "collection_gate_retrieved_documents": summary_in["retrieved_documents"],
        "collection_partner_entities": summary_in.get("partner_entity_ids"),
        "collection_partner_entities_with_cik": summary_in.get("partner_entities_with_cik"),
        "collection_partner_entities_with_hits": summary_in.get("partner_entities_with_hits"),
        "collection_frontier_status_counts": summary_in.get("frontier_status_counts"),
        "collection_access_control_bypass": summary_in.get("access_control_bypass"),
        "input_contexts": len(contexts), "terminal_decisions": len(decisions),
        "pending_decisions": sum(r["pending"] for r in decisions),
        "approved_candidates": len(candidates), "claims": len(claims),
        "decision_counts": dict(Counter(r["decision"] for r in decisions)),
        "claim_counts": dict(Counter(f"{r['relationship_type']}:{r['fact_status']}" for r in claims)),
        "claim_directness_counts": dict(Counter(r["directness"] for r in claims)),
        "claim_type_fact_directness_counts": dict(Counter(f"{r['relationship_type']}:{r['fact_status']}:{r['directness']}" for r in claims)),
        "claim_unique_endpoint_counts": dict(Counter(f"{rel}:{fact}" for rel, fact, entity in {
            (r["relationship_type"], r["fact_status"], r["subject_entity_id"] if r["relationship_type"] == "supplier" else r["object_entity_id"])
            for r in claims
        })),
        "canonical_frontier_rows": len(frontier_out),
    }
    (out / "summary.json").write_text(json.dumps(out_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
