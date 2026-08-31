#!/usr/bin/env python3
"""Convert collected contexts into fail-closed candidates/evidence/decisions."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
CANONICAL = HERE.parent / "partner_regulatory_entity_normalization/canonical_partner_universe.jsonl"
START, END = "2025-01-01", "2026-08-25"

# confirmed=True only where the filing expresses actual supply/procurement flow.
SPECS = {
    "compal": ("Primary Supply Sources", True, "direct", "gpu_and_ai_compute_hardware",
               "The annual report's key-material table names NVIDIA as the primary GPU supply source."),
    "quanta": ("Main Suppliers", True, "direct", "gpu_and_ai_compute_hardware",
               "The annual report's key-material table names NVIDIA among the main CPU/GPU suppliers."),
    "tatung_system": ("Primary suppliers include", True, "unclear", "ict_distribution",
               "The annual report identifies NVIDIA as a primary supplier, but the adjacent agency/distribution wording does not establish the immediate invoicing path."),
    "leadtek": ("continuous supply of NVIDIA workstation graphics cards", True, "unclear", "gpu_and_ai_compute_hardware",
               "The annual report explicitly records continuing NVIDIA-card supply to Leadtek; the immediate invoicing channel is not stated."),
    "samsung_electronics": ("공급받고 있습니다", True, "direct", "automotive_soc_and_communications_modules",
               "The DART filing states Harman receives SoCs/communications modules from NVIDIA and WNC."),
    "snet_systems": ("주요 구매처로 NVIDIA", True, "unclear", "ict_infrastructure_hardware_and_solutions",
               "The DART filing names NVIDIA as a main purchase source but also describes purchases through domestic distributors, so the immediate invoicing path is unresolved."),
    "unisplendour": ("厂商授信额度提供连带责任保证", True, "indirect", "ict_distribution",
               "The CNINFO filing records NVIDIA vendor-credit obligations of named Unisplendour subsidiaries; flow is through subsidiaries."),
    "edom": ("Distribution of all product lines of Nvidia", False, "unclear", "ict_distribution",
               "A distribution agreement is disclosed, but this passage does not state a purchase/order or an NVIDIA customer."),
    "mds_tech": ("International Distributor Agreement", False, "unclear", "ict_distribution",
               "A distributor/partner agreement alone does not establish actual procurement in the research window."),
    "zero_one_technology": ("Authorized distributor of NVIDIA products", False, "unclear", "ict_distribution",
               "Authorized-distributor status is explicit, but actual purchase/order flow is not."),
    "xiilab": ("판매ㆍ공급계약 내용 NVIDIA", False, "unclear", "gpu_and_ai_compute_hardware",
               "XIILAB sells NVIDIA-labelled products to Algorix; the filing does not identify NVIDIA as seller to XIILAB or customer of XIILAB."),
    "orbbec": ("稳定的生态合作", False, "unclear", "robotics_3d_vision_ecosystem",
               "Compatibility/ecosystem cooperation is explicit but does not establish purchase, order, revenue, or NVIDIA-as-customer direction."),
    "tztek": ("英伟达 Jetson 官方合作伙伴", False, "unclear", "edge_ai_controller",
               "Official-partner/platform-use language and sales to other customers do not establish a NVIDIA transaction direction."),
}


def rows(path: Path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(path: Path, values):
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in values), encoding="utf-8")


def hid(prefix, *parts):
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:20]}"


def excerpt_around(text: str, needle: str, radius=430):
    text = re.sub(r"\s+", " ", text).strip()
    at = text.lower().find(needle.lower())
    if at < 0:
        at = min((text.lower().find(term.lower()) for term in ("NVIDIA", "英伟达", "英偉達", "輝達", "엔비디아") if text.lower().find(term.lower()) >= 0), default=0)
    return text[max(0, at-radius):min(len(text), at+len(needle)+radius)]


canonical = {x["canonical_entity_id"]: x for x in rows(CANONICAL)}
frontier = rows(HERE / "source_frontier.jsonl")
raw = rows(HERE / "raw_contexts.jsonl")
frontier_by_id = {x["issuer_id"]: x for x in frontier}

candidates, evidence = [], []
candidate_by_issuer = {}
for iid, (needle, confirmed, directness, product, rationale) in SPECS.items():
    matches = [x for x in raw if x["issuer_id"] == iid and needle.lower() in x["excerpt"].lower()]
    if not matches:
        raise SystemExit(f"missing selected context: {iid}: {needle}")
    # Prefer latest and, for Unisplendour, the current 2026 filing.
    source = sorted(matches, key=lambda x: (x["published_at"], x["locator"]), reverse=True)[0]
    excerpt = excerpt_around(source["excerpt"], needle)
    cid = hid("apac_candidate", iid, source["url"], source["locator"])
    eid = hid("apac_evidence", cid)
    signal = "partner_purchases_nvidia" if confirmed else "unclear"
    source_obj = {
        "source_kind": source["source_kind"], "form_type": source["form_type"],
        "url": source["url"], "publisher": source["publisher"],
        "published_at": source["published_at"], "evidence_locator": source["locator"],
        "evidence_excerpt": excerpt, "access_mode": "public_no_login",
        "access_control_bypassed": False, "origin_publication_id": source["origin_publication_id"],
        "origin_content_fingerprint": hashlib.sha256(excerpt.encode()).hexdigest(),
    }
    proposed_claim = None
    if confirmed:
        proposed_claim = {
            "claim_id": hid("apac_claim", cid, "partner_purchases_nvidia"),
            "subject_entity_id": "nvidia", "object_entity_id": iid,
            "direction": "sells_to", "relationship_type": "customer",
            "fact_status": "confirmed", "directness": directness,
            "confidence_score": 90 if directness == "direct" else 86,
            "product_scope_id": product, "source_kind": source["source_kind"],
            "source_url": source["url"], "publisher": source["publisher"],
            "published_at": source["published_at"],
            "evidence_locator": source["locator"], "evidence_excerpt": excerpt,
            "evidence_ids": [eid],
            "source_cap_applied": "regulatory_explicit_direction_confirmed",
            "direction_rationale": rationale,
        }
    candidate = {
        "candidate_id": cid, "partner_entity_id": iid,
        "partner_legal_name": canonical[iid]["legal_name"], "existing_roles": ["partner"],
        "signals": [signal], "directness": directness, "product_scope_id": product,
        "direction_review": "explicit_procurement_or_supply" if confirmed else "insufficient_direction",
        "source": source_obj, "source_evidence_ids": [eid],
    }
    if proposed_claim:
        candidate["proposed_claim"] = proposed_claim
    candidates.append(candidate)
    evidence.append({
        "evidence_id": eid, "candidate_id": cid, "partner_entity_id": iid,
        "signal_assessment": signal, "fact_status_cap": "confirmed" if source["source_kind"] == "regulatory_filing" else "inferred",
        "selected_for_claim": confirmed, "directness": directness,
        "direction_rationale": rationale, **source_obj,
    })
    candidate_by_issuer[iid] = candidates[-1]

decisions = []
for item in frontier:
    iid = item["issuer_id"]
    cand = candidate_by_issuer.get(iid)
    claims = []
    if cand and cand["direction_review"] == "explicit_procurement_or_supply":
        claims.append(cand["proposed_claim"])
    if claims:
        status, reason = "approved_direction_claims", None
    elif item["terminal_status"] in {"access_blocked", "public_search_unavailable"}:
        status, reason = "access_incomplete_no_direction_claim", item["note"]
    elif cand:
        status, reason = "unknown_no_direction_claim", next(x["direction_rationale"] for x in evidence if x["candidate_id"] == cand["candidate_id"])
    else:
        status, reason = "unknown_no_direction_claim", "No explicit NVIDIA-as-customer or Partner-purchases-NVIDIA direction in the searched corpus."
    decisions.append({
        "decision_id": hid("apac_decision", iid), "candidate_id": cand["candidate_id"] if cand else None,
        "partner_entity_id": iid, "partner_legal_name": item["legal_name"],
        "review_status": status, "frontier_terminal_status": item["terminal_status"],
        "existing_roles_retained": ["partner"], "new_claims": claims,
        "unknown_reason": reason,
        "multi_role_policy": "Partner is retained; supplier/customer claims are additive; directness remains orthogonal to fact status.",
    })

write_jsonl(HERE / "candidates.jsonl", sorted(candidates, key=lambda x: x["partner_entity_id"]))
write_jsonl(HERE / "evidence.jsonl", sorted(evidence, key=lambda x: x["partner_entity_id"]))
write_jsonl(HERE / "decision_ledger.jsonl", sorted(decisions, key=lambda x: x["partner_entity_id"]))

summary = {
    "status": "pass", "research_window": {"start": START, "end": END},
    "canonical_apac_issuers": len(frontier), "frontier_rows": len(frontier),
    "frontier_terminal_counts": dict(Counter(x["terminal_status"] for x in frontier)),
    "frontier_by_region": {reg: dict(Counter(x["terminal_status"] for x in frontier if x["region_code"] == reg)) for reg in sorted({x["region_code"] for x in frontier})},
    "raw_nvidia_contexts": len(raw), "direction_candidates": len(candidates),
    "confirmed_direction_claims": sum(len(x["new_claims"]) for x in decisions),
    "unknown_direction_candidates": sum(1 for x in candidates if x["direction_review"] == "insufficient_direction"),
    "confirmed_claim_partner_ids": sorted(x["partner_entity_id"] for x in decisions if x["new_claims"]),
    "pending_count": 0,
    "scope_note": "searched_no_hit is bounded to searched_scope in source_frontier; it is not a claim that every document in every portal was machine-searchable.",
    "snapshot_modified": False,
}
(HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
