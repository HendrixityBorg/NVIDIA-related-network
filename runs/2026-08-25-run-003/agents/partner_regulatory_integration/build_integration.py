#!/usr/bin/env python3
"""Integrate SEC, APAC and EMEA Partner regulatory reviews.

The program is deliberately offline.  It refuses to write integration outputs
unless all three upstream review validation reports pass.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
AGENTS = RUN / "agents"
SEC = AGENTS / "partner_regulatory_sec_review"
APAC = AGENTS / "partner_regulatory_apac_review"
EMEA = AGENTS / "partner_regulatory_emea_review"
ENTITY_DIR = AGENTS / "partner_regulatory_entity_normalization"
UNIVERSE_PATH = ENTITY_DIR / "canonical_partner_universe.jsonl"
MERGE_MAP_PATH = ENTITY_DIR / "entity_merge_map.jsonl"
PRODUCT_PATH = RUN / "product_tree_v2/canonical_index_v2.jsonl"
WINDOW = {"start": "2025-01-01", "end": "2026-08-25"}
ALLOWED_DIRECTNESS = {"direct", "indirect", "both", "unclear"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path, required: bool = True) -> list[dict]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, values: list[dict]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in values), encoding="utf-8")


def sid(prefix: str, *parts: object) -> str:
    raw = "|".join(str(x) for x in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:20]}"


def validation_pass(report: dict) -> bool:
    return report.get("pass") is True or report.get("status") == "pass" or report.get("overall_pass") is True


def normalize_directness(value: object) -> str:
    text = str(value or "unclear").strip().casefold()
    aliases = {
        "explicit": "direct", "direct": "direct", "indirect": "indirect",
        "both": "both", "direct_and_indirect": "both", "mixed": "both",
        "unknown": "unclear", "unclear": "unclear", "not_disclosed": "unclear",
    }
    return aliases.get(text, "unclear")


def combine_directness(values: list[str]) -> str:
    known = {normalize_directness(x) for x in values}
    if "both" in known or {"direct", "indirect"} <= known:
        return "both"
    if "direct" in known:
        return "direct"
    if "indirect" in known:
        return "indirect"
    return "unclear"


def source_kind(value: object, workstream: str) -> str:
    text = str(value or "").casefold()
    if workstream == "sec" or any(x in text for x in ("regulatory", "filing", "exchange", "sec_")):
        return "regulatory_filing"
    if "third" in text or "media" in text:
        return "third_party_news"
    if "news" in text or "issuer" in text or "company" in text or "press" in text:
        return "company_news"
    return "regulatory_filing" if workstream == "apac" else "company_news"


def sec_source_kind(raw: dict) -> str:
    """Distinguish filing text from company-news exhibits hosted by EDGAR."""
    form = str(raw.get("form") or "").upper().replace("/A", "")
    url = str(raw.get("source_url") or raw.get("url") or "").casefold()
    filename = url.rsplit("/", 1)[-1]
    news_exhibit_markers = (
        "ex99", "ex-99", "dex991", "transcript", "results", "presentation",
        "pressrelease", "press-release", "newsrelease", "businessupdate",
    )
    if form == "6-K":
        # A 6-K commonly furnishes an issuer announcement. Without a distinct
        # annual/interim-report classification, conservatively apply the
        # company-news ceiling required by this project's source policy.
        return "company_news"
    if form == "8-K" and any(marker in filename for marker in news_exhibit_markers):
        return "company_news"
    return "regulatory_filing"


def compact_excerpt(value: object, limit: int = 700) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    # SEC mention contexts can be wider than the redistribution excerpt. Keep
    # the named relationship term in view instead of blindly retaining the
    # beginning of the surrounding paragraph.
    marker = text.casefold().find("nvidia")
    if marker < 0:
        return text[: limit - 1].rstrip() + "…"
    before = min(240, marker)
    start = marker - before
    end = min(len(text), start + limit - 2)
    start = max(0, end - (limit - 2))
    prefix = "…" if start else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix


def evidence_strength(relationship_type: str, row: dict) -> int:
    text = str(row.get("evidence_excerpt") or "").casefold()
    score = 0
    if "nvidia" in text:
        score += 10
    if relationship_type == "supplier":
        patterns = (
            (r"provide(?:s|d|ing)? nvidia", 60),
            (r"nvidia.{0,100}purchase commitment", 60),
            (r"sale by the company.{0,160}nvidia", 55),
            (r"nvidia corporation\s+\d+(?:\.\d+)?\s*%", 55),
            (r"supply of.{0,100}nvidia|nvidia.{0,100}supply", 45),
            (r"customer.{0,120}nvidia|nvidia.{0,120}customer", 40),
        )
    else:
        patterns = (
            (r"purchase(?:s|d|ing)?.{0,120}nvidia|nvidia.{0,120}purchase", 60),
            (r"supplier(?:s)?.{0,120}nvidia|nvidia.{0,120}supplier", 55),
            (r"receiv(?:e|es|ed|ing).{0,120}nvidia", 50),
            (r"deploy(?:s|ed|ing)?.{0,120}nvidia|nvidia.{0,120}deploy", 35),
            (r"use(?:s|d|ing)?.{0,120}nvidia|nvidia.{0,120}use", 30),
        )
    for pattern, points in patterns:
        if re.search(pattern, text):
            score += points
    if any(term in text for term in ("agreement", "contract", "revenue", "$", "%")):
        score += 8
    return score


def entity_maps() -> tuple[list[dict], dict[str, str]]:
    universe = read_jsonl(UNIVERSE_PATH)
    mapping = {"nvidia": "nvidia"}
    for row in read_jsonl(MERGE_MAP_PATH):
        mapping[row["original_entity_id"]] = row["canonical_entity_id"]
        mapping[row["canonical_entity_id"]] = row["canonical_entity_id"]
    for row in universe:
        mapping[row["canonical_entity_id"]] = row["canonical_entity_id"]
        for member in row.get("member_entity_ids", []):
            mapping[member] = row["canonical_entity_id"]
    return universe, mapping


PRODUCT_ALIASES = {
    "data_center": "data-center",
    "data_center_ai_infrastructure": "data-center",
    "data_center_gpu_servers": "data-center",
    "data_center_gpu_cloud": "cloud-computing",
    "data_center_ai_factory": "v2-ai-enterprise-factory",
    "automotive": "drive",
    "automotive_drive": "drive",
    "automotive_drive_and_dgx": "corporate_general",
    "ai_enterprise_accelerated_computing": "nvidia-ai-enterprise",
    "dgx_superpod": "dgx-superpod",
    "industrial_ai": "corporate_general",
    "mixed": "corporate_general",
    "unknown": "corporate_general",
    "unspecified": "corporate_general",
    "company_wide": "corporate_general",
}


class ProductMapper:
    def __init__(self) -> None:
        self.rows = read_jsonl(PRODUCT_PATH)
        self.keys = {x["canonical_key"] for x in self.rows}
        self.search = {}
        for row in self.rows:
            labels = [row["canonical_key"], row.get("primary_name", ""), *row.get("aliases", [])]
            self.search[row["canonical_key"]] = " ".join(labels).casefold().replace("_", "-")

    @staticmethod
    def norm(value: object) -> str:
        return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold())).strip("-")

    def map(self, value: object) -> tuple[str, str, float | None]:
        original = str(value or "corporate_general")
        norm = self.norm(original)
        if norm in {"", "corporate-general"}:
            return "corporate_general", "unknown_or_corporate_scope", None
        if original in self.keys:
            return original, "exact_canonical_key", 1.0
        if norm in self.keys:
            return norm, "normalized_exact_canonical_key", 1.0
        alias_key = original.casefold().replace("-", "_").replace(" ", "_")
        if alias_key in PRODUCT_ALIASES:
            return PRODUCT_ALIASES[alias_key], "curated_scope_alias", 1.0
        if any(token in norm for token in ("-and-", "mixed", "multi-product", "multiple-products")):
            return "corporate_general", "mixed_product_scope", None
        source_tokens = set(norm.split("-")) - {"nvidia", "platform", "solution", "products"}
        best_key, best_score = None, 0.0
        for key, label in self.search.items():
            candidate = self.norm(label)
            target_tokens = set(candidate.split("-")) - {"nvidia", "platform", "solution", "products"}
            jaccard = len(source_tokens & target_tokens) / max(1, len(source_tokens | target_tokens))
            ratio = difflib.SequenceMatcher(None, norm, key).ratio()
            score = max(jaccard, ratio * 0.82)
            if score > best_score or (score == best_score and key < (best_key or "~")):
                best_key, best_score = key, score
        if best_key and best_score >= 0.55:
            return best_key, "deterministic_closest_canonical_key", round(best_score, 4)
        return "corporate_general", "no_reliable_product_match", round(best_score, 4)


def evidence_record(workstream: str, upstream_id: str, raw: dict, embedded: dict | None = None) -> tuple[str, dict]:
    embedded = embedded or {}
    url = raw.get("url") or raw.get("source_url") or embedded.get("source_url") or embedded.get("url")
    publisher = raw.get("publisher") or embedded.get("publisher")
    published = raw.get("published_at") or raw.get("file_date") or embedded.get("published_at")
    locator = raw.get("evidence_locator") or raw.get("locator") or embedded.get("evidence_locator")
    excerpt = compact_excerpt(raw.get("evidence_excerpt") or raw.get("excerpt") or embedded.get("evidence_excerpt"))
    kind = (
        sec_source_kind(raw)
        if workstream == "sec"
        else source_kind(
            raw.get("source_kind")
            or raw.get("source_family")
            or embedded.get("source_kind"),
            workstream,
        )
    )
    origin = raw.get("origin_publication_id") or raw.get("accession") or raw.get("document_id") or url
    fingerprint_raw = "|".join(str(x or "") for x in (url, publisher, published, locator, excerpt))
    fingerprint = raw.get("origin_content_fingerprint") or hashlib.sha256(fingerprint_raw.encode()).hexdigest()
    integrated_id = sid("partner_reg_evidence", url, publisher, published, locator, hashlib.sha256(excerpt.encode()).hexdigest())
    return integrated_id, {
        "evidence_id": integrated_id,
        "upstream_evidence_ids": [upstream_id],
        "workstreams": [workstream],
        "source_kind": kind,
        "source_document_type": raw.get("form") or embedded.get("form_type"),
        "regulatory_accession": raw.get("accession"),
        "source_family": raw.get("source_family") or embedded.get("source_family") or kind,
        "url": url,
        "publisher": publisher,
        "published_at": published,
        "retrieved_at": raw.get("retrieved_at"),
        "evidence_locator": locator,
        "evidence_excerpt": excerpt,
        "access_mode": raw.get("access_mode") or raw.get("access") or "public_no_login",
        "access_control_bypassed": bool(raw.get("access_control_bypassed", False)),
        "origin_publication_id": origin,
        "origin_content_fingerprint": fingerprint,
        "source_content_sha256": raw.get("source_content_sha256"),
        "redistribution": raw.get("redistribution") or "structured facts and necessary short excerpt only",
        "full_text_retained": False,
    }


def merge_evidence(target: dict[str, dict], record: dict) -> None:
    eid = record["evidence_id"]
    if eid not in target:
        target[eid] = record
        return
    existing = target[eid]
    existing["upstream_evidence_ids"] = sorted(set(existing["upstream_evidence_ids"] + record["upstream_evidence_ids"]))
    existing["workstreams"] = sorted(set(existing["workstreams"] + record["workstreams"]))


def upstream_claims(entity_map: dict[str, str], mapper: ProductMapper) -> tuple[list[dict], dict[str, dict]]:
    normalized: list[dict] = []
    integrated_evidence: dict[str, dict] = {}

    sec_evidence = {x["evidence_id"]: x for x in read_jsonl(SEC / "evidence.jsonl")}
    for claim in read_jsonl(SEC / "claims.jsonl"):
        evidence_ids = []
        for upstream_id in claim.get("evidence_ids", []):
            raw = sec_evidence[upstream_id]
            eid, rec = evidence_record("sec", upstream_id, raw)
            merge_evidence(integrated_evidence, rec)
            evidence_ids.append(eid)
        product, method, score = mapper.map(claim.get("product_scope_id"))
        normalized.append({
            "workstream": "sec", "upstream_claim_id": claim["claim_id"],
            "subject": entity_map.get(claim["subject_entity_id"], claim["subject_entity_id"]),
            "object": entity_map.get(claim["object_entity_id"], claim["object_entity_id"]),
            "direction": claim["direction"], "relationship_type": claim["relationship_type"],
            "original_product_scope": claim.get("product_scope_id"), "product_scope": product,
            "product_mapping_method": method, "product_mapping_score": score,
            "fact_status": claim.get("fact_status", "unknown"),
            "directness": normalize_directness(claim.get("directness")),
            "confidence_score": claim.get("confidence_score"),
            "evidence_ids": sorted(set(evidence_ids)),
            "source_kinds": sorted({integrated_evidence[x]["source_kind"] for x in evidence_ids}),
            "quantitative_mentions": claim.get("quantitative_mentions", []),
            "limitations": claim.get("limitations", []),
        })

    for workstream, directory in (("apac", APAC), ("emea", EMEA)):
        raw_evidence_rows = read_jsonl(directory / "evidence.jsonl", required=False)
        evidence_by_id = {x.get("evidence_id"): x for x in raw_evidence_rows if x.get("evidence_id")}
        for candidate in read_jsonl(directory / "candidates.jsonl"):
            claim = candidate.get("proposed_claim") or candidate.get("claim")
            if not claim:
                continue
            evidence_ids = []
            upstream_refs = candidate.get("source_evidence_ids") or claim.get("evidence_ids") or []
            if not upstream_refs:
                upstream_refs = [sid("embedded", workstream, candidate.get("candidate_id"), claim.get("source_url"))]
            for upstream_id in upstream_refs:
                raw = evidence_by_id.get(upstream_id, {})
                eid, rec = evidence_record(workstream, upstream_id, raw, claim)
                merge_evidence(integrated_evidence, rec)
                evidence_ids.append(eid)
            original_scope = claim.get("product_scope_id") or candidate.get("product_scope_id") or "corporate_general"
            product, method, score = mapper.map(original_scope)
            kind_values = sorted({integrated_evidence[x]["source_kind"] for x in evidence_ids})
            fact = claim.get("fact_status", "unknown")
            if fact == "confirmed" and not any(x == "regulatory_filing" for x in kind_values):
                fact = "inferred"
            normalized.append({
                "workstream": workstream,
                "upstream_claim_id": claim.get("claim_id") or candidate.get("candidate_id"),
                "subject": entity_map.get(claim.get("subject_entity_id"), claim.get("subject_entity_id")),
                "object": entity_map.get(claim.get("object_entity_id"), claim.get("object_entity_id")),
                "direction": claim.get("direction"), "relationship_type": claim.get("relationship_type"),
                "original_product_scope": original_scope, "product_scope": product,
                "product_mapping_method": method, "product_mapping_score": score,
                "fact_status": fact, "directness": normalize_directness(claim.get("directness") or candidate.get("directness")),
                "confidence_score": claim.get("confidence_score") or candidate.get("confidence_score"),
                "evidence_ids": sorted(set(evidence_ids)), "source_kinds": kind_values,
                "quantitative_mentions": claim.get("quantitative_mentions", []),
                "limitations": [x for x in [claim.get("source_cap_applied"), claim.get("direction_rationale")] if x],
            })
    return normalized, integrated_evidence


def freshness_points(evidence_ids: list[str], evidence: dict[str, dict]) -> float:
    cutoff = date.fromisoformat(WINDOW["end"])
    ages = []
    for evidence_id in evidence_ids:
        value = evidence[evidence_id].get("published_at")
        if not value:
            continue
        try:
            ages.append((cutoff - date.fromisoformat(str(value)[:10])).days)
        except ValueError:
            continue
    if not ages:
        return 5.5
    age = max(0, min(ages))
    if age <= 90:
        return 10.0
    if age <= 180:
        return 9.0
    if age <= 365:
        return 7.5
    return 5.5


def relationship_score(
    fact_status: str,
    evidence_ids: list[str],
    evidence: dict[str, dict],
    quantitative_mentions: list[str],
) -> tuple[int, dict, dict]:
    kinds = {evidence[eid]["source_kind"] for eid in evidence_ids}
    publishers = {
        str(evidence[eid].get("publisher") or "").strip().casefold()
        for eid in evidence_ids
        if str(evidence[eid].get("publisher") or "").strip()
    }
    origins = {
        str(evidence[eid].get("origin_publication_id") or evidence[eid].get("url"))
        for eid in evidence_ids
    }
    if fact_status == "confirmed":
        source_authority = 25.0
        explicitness = 25.0
    else:
        source_authority = (
            25.0 if "regulatory_filing" in kinds
            else 20.0 if "company_news" in kinds
            else 18.0
        )
        explicitness = 8.0
    independence = float(min(15, max(0, len(publishers) - 1) * 5))
    quantification = 10.0 if quantitative_mentions and fact_status == "confirmed" else (
        5.0 if quantitative_mentions else 0.0
    )
    breakdown = {
        "source_authority": source_authority,
        "explicitness": explicitness,
        "entity_resolution": 15.0,
        "independence": independence,
        "timeliness": freshness_points(evidence_ids, evidence),
        "quantification": quantification,
        "relationship_type_specificity": 5.0,
        "conflict_penalty": 0.0,
    }
    raw = round(
        sum(value for key, value in breakdown.items() if key != "conflict_penalty")
        - breakdown["conflict_penalty"]
    )
    cap = 100 if fact_status == "confirmed" else 59
    score = min(cap, max(0, raw))
    stats = {
        "unique_publishers": len(publishers),
        "unique_origin_publications": len(origins),
        "evidence_contexts": len(evidence_ids),
        "independence_rule": "five points per additional independent publisher; repeated contexts and same-publisher filings add zero independence",
    }
    return score, breakdown, stats


def integrate_claims(source_claims: list[dict], evidence: dict[str, dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for claim in source_claims:
        key = (claim["subject"], claim["object"], claim["direction"], claim["relationship_type"], claim["product_scope"])
        groups[key].append(claim)
    out = []
    for key, items in sorted(groups.items()):
        all_evidence = sorted({eid for x in items for eid in x["evidence_ids"]})
        confirmed_support = sorted({eid for x in items if x["fact_status"] == "confirmed" for eid in x["evidence_ids"] if evidence[eid]["source_kind"] == "regulatory_filing"})
        fact = "confirmed" if confirmed_support else "inferred"
        directness = combine_directness([x["directness"] for x in items])
        product_scope = key[4]
        quantitative_mentions = sorted(
            {str(q) for x in items for q in x.get("quantitative_mentions", [])}
        )
        confidence, breakdown, evidence_stats = relationship_score(
            fact, all_evidence, evidence, quantitative_mentions
        )
        evidence_by_origin: dict[str, list[str]] = defaultdict(list)
        for evidence_id in all_evidence:
            evidence_by_origin[
                str(
                    evidence[evidence_id].get("origin_publication_id")
                    or evidence[evidence_id].get("url")
                    or evidence_id
                )
            ].append(evidence_id)
        primary_evidence_ids = sorted(
            max(
                evidence_ids,
                key=lambda evidence_id: (
                    evidence_strength(key[3], evidence[evidence_id]),
                    len(evidence[evidence_id].get("evidence_excerpt") or ""),
                    evidence_id,
                ),
            )
            for evidence_ids in evidence_by_origin.values()
        )
        out.append({
            "claim_id": sid("partner_reg_claim", *key),
            "subject_entity_id": key[0], "object_entity_id": key[1],
            "direction": key[2], "relationship_type": key[3],
            "product_scope_id": product_scope,
            "original_product_scopes": sorted({str(x["original_product_scope"]) for x in items}),
            "product_scope_mappings": sorted({f'{x["original_product_scope"]}->{product_scope}:{x["product_mapping_method"]}' for x in items}),
            "fact_status": fact, "directness": directness, "confidence_score": confidence,
            "confidence_breakdown": breakdown,
            "evidence_independence_stats": evidence_stats,
            "evidence_ids": all_evidence,
            "primary_evidence_ids": primary_evidence_ids,
            "confirmed_support_evidence_ids": confirmed_support,
            "source_workstreams": sorted({x["workstream"] for x in items}),
            "source_kinds": sorted({evidence[eid]["source_kind"] for eid in all_evidence}),
            "upstream_claim_ids": sorted({x["upstream_claim_id"] for x in items}),
            "quantitative_mentions": quantitative_mentions,
            "upstream_confidence_scores": sorted(
                {x["confidence_score"] for x in items if isinstance(x.get("confidence_score"), (int, float))}
            ),
            "limitations": sorted({str(q) for x in items for q in x.get("limitations", []) if q}),
            "dedup_key": "|".join(key),
            "research_window": WINDOW,
        })
    return out


def load_frontiers(entity_map: dict[str, str]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for workstream, directory in (("sec", SEC), ("apac", APAC), ("emea", EMEA)):
        for row in read_jsonl(directory / "source_frontier.jsonl"):
            raw_id = row.get("canonical_entity_id") or row.get("partner_entity_id") or row.get("issuer_id")
            canonical_id = entity_map.get(raw_id, raw_id)
            out[canonical_id].append({
                "workstream": workstream,
                "upstream_frontier_id": row.get("frontier_id"),
                "terminal_status": row.get("terminal_status"),
                "status": row.get("status", "terminal"),
                "pending": bool(row.get("pending", False)),
                "region_code": row.get("region_code"),
                "source_id": row.get("source_id"),
                "actual_search_performed": row.get("actual_search_performed"),
                "route_only": row.get("route_only"),
            })
    return out


def overall_terminal(entries: list[dict], has_claim: bool) -> str:
    if has_claim:
        return "direction_claims_found"
    statuses = {str(x.get("terminal_status")) for x in entries}
    if statuses & {"regulatory_hit", "regulatory_hit_reviewed_terminal"}:
        return "regulatory_hit_no_approved_direction_claim"
    if statuses & {"searched_no_hit", "searched_no_nvidia_hit"}:
        return "searched_no_direction_claim"
    if "public_search_unavailable" in statuses:
        return "public_search_unavailable"
    if "access_blocked" in statuses:
        return "access_blocked"
    if statuses <= {"non_sec_route_required", "merged_routes_terminal"}:
        return "route_or_identifier_terminal_no_direction_claim"
    return "reviewed_terminal_no_direction_claim"


def build_frontier_and_decisions(universe: list[dict], entity_map: dict[str, str], claims: list[dict]) -> tuple[list[dict], list[dict]]:
    source_frontiers = load_frontiers(entity_map)
    claims_by_entity: dict[str, list[dict]] = defaultdict(list)
    for claim in claims:
        partner_id = claim["object_entity_id"] if claim["subject_entity_id"] == "nvidia" else claim["subject_entity_id"]
        claims_by_entity[partner_id].append(claim)

    upstream_decisions: dict[str, list[dict]] = defaultdict(list)
    for workstream, directory in (("sec", SEC), ("apac", APAC), ("emea", EMEA)):
        for row in read_jsonl(directory / "decision_ledger.jsonl", required=False):
            raw_id = row.get("canonical_entity_id") or row.get("partner_entity_id") or row.get("issuer_id")
            if not raw_id:
                continue
            cid = entity_map.get(raw_id, raw_id)
            upstream_decisions[cid].append({
                "workstream": workstream,
                "decision_id": row.get("decision_id"),
                "decision": row.get("decision") or row.get("review_status"),
                "terminal_status": row.get("terminal_status"),
            })

    frontier, decisions = [], []
    for entity in sorted(universe, key=lambda x: x["canonical_entity_id"]):
        cid = entity["canonical_entity_id"]
        entries = source_frontiers.get(cid, [])
        entity_claims = claims_by_entity.get(cid, [])
        terminal = overall_terminal(entries, bool(entity_claims))
        frontier_id = sid("partner_reg_frontier", cid, WINDOW["end"])
        frontier.append({
            "frontier_id": frontier_id, "canonical_entity_id": cid,
            "display_name": entity["display_name"], "legal_name": entity["legal_name"],
            "listing_status": entity["listing_status"], "securities": entity.get("securities", []),
            "research_window": WINDOW, "status": "terminal", "pending": False,
            "terminal_status": terminal,
            "workstream_terminals": sorted(entries, key=lambda x: (x["workstream"], str(x.get("region_code")), str(x.get("source_id")))),
            "claim_ids": sorted(x["claim_id"] for x in entity_claims),
        })
        evidence_ids = sorted({e for x in entity_claims for e in x["evidence_ids"]})
        decisions.append({
            "decision_id": sid("partner_reg_decision", cid, WINDOW["end"]),
            "frontier_id": frontier_id, "canonical_entity_id": cid,
            "status": "terminal", "pending": False, "terminal_status": terminal,
            "review_status": "approved_direction_claims" if entity_claims else "unknown_no_direction_claim",
            "existing_roles_retained": ["partner"],
            "claim_ids": sorted(x["claim_id"] for x in entity_claims), "evidence_ids": evidence_ids,
            "unknown_reason": None if entity_claims else "No integrated upstream claim passed direction and source-policy gates.",
            "upstream_decisions": sorted(upstream_decisions.get(cid, []), key=lambda x: (x["workstream"], str(x.get("decision_id")))),
            "multi_role_policy": "Partner remains; supplier/customer claims are additive and may coexist in both directions and with other roles.",
        })
    return frontier, decisions


def render_readme(summary: dict) -> str:
    tc = summary["frontier_terminal_counts"]
    return f"""# Partner 监管反向关系统一集成

## 结果

本目录统一合并 SEC、APAC 与 EMEA/英国/加拿大三组 Partner 对手方监管材料复查结果，研究窗口为 **2025-01-01 至 2026-08-25**。上游三组验证均通过后，合并器才会写出最终文件。

- 规范 Partner frontier：{summary['canonical_partner_total']} / 316，全部 terminal，pending 0。
- 上游来源 claim：{summary['upstream_claim_total']}；按关系五元键合并后：{summary['canonical_claim_total']}。
- canonical evidence：{summary['canonical_evidence_total']}。
- confirmed：{summary['fact_status_counts'].get('confirmed', 0)}；inferred：{summary['fact_status_counts'].get('inferred', 0)}。
- customer：{summary['relationship_type_counts'].get('customer', 0)}；supplier：{summary['relationship_type_counts'].get('supplier', 0)}。
- frontier 终态分布：`{json.dumps(tc, ensure_ascii=False, sort_keys=True)}`。

## 规范化规则

关系按以下五元键合并，重复关系合并证据而不删除 Partner：

```text
subject_entity_id | object_entity_id | direction | relationship_type | product_scope_id
```

- 实体端点通过 `partner_regulatory_entity_normalization/entity_merge_map.jsonl` 统一为 canonical entity ID。
- SEC 读取 `claims.jsonl`；APAC 与 EMEA 读取 `candidates.jsonl` 的 `proposed_claim`。
- directness 的 `explicit` 规范为 `direct`；最终只允许 `direct / indirect / both / unclear`。同时存在直接和间接证据时为 `both`。
- 产品 scope 必须是冻结 `product_tree_v2/canonical_index_v2.jsonl` 中的 key；自由文本映射保留在 `original_product_scopes` 和 `product_scope_mappings`。混合或无法可靠匹配时为 `corporate_general`。
- 新闻、公司公告或第三方材料不能生成 confirmed。只有通过上游验证、且有监管材料支持的 confirmed 才保留。
- inferred supplier/customer 的置信分严格小于 60。
- 转载或相同 URL/日期/locator/短摘录按证据指纹合并，不增加独立来源。
- 独立性按不同 publisher 计算；同一申报中的重复 NVIDIA 上下文、同一 publisher 的多份
  文件或同一新闻转载均不增加 independence 分。重复上下文仍保留为 corroborating 证据。

## 文件

- `claims.jsonl`：统一五元键后的关系 claim。
- `evidence.jsonl`：所有 claim 引用的规范证据；仅保留结构化字段和必要短摘录。
- `source_frontier.jsonl`：316 个 canonical Partner 的组合终态及各工作流终态。
- `decision_ledger.jsonl`：316 个 Partner 的增量关系决策；Partner 角色始终保留。
- `summary.json`：合并统计、上游验证和限制。
- `validation_report.json`：输入门禁与最终一致性检查。
- `build_integration.py`：离线、确定性重建脚本。

## 复现

从本目录执行：

```bash
python3 build_integration.py
jq -e '.pass == true' validation_report.json
jq -s 'length == 316 and (map(.canonical_entity_id) | unique | length == 316)' source_frontier.jsonl
jq -s 'all(.fact_status != "inferred" or .confidence_score < 60)' claims.jsonl
```

## 限制与合法边界

- 本集成器不联网，只读取冻结上游成果；未重新抓取或绕过 robots、登录、付费墙、验证码、限流等访问控制。
- `searched_no_direction_claim` 不证明现实中不存在交易关系。
- `route_or_identifier_terminal_no_direction_claim` 表示上游已给出终态，但没有可合并方向 claim；不应解释为完成了所有可能的当地语言全文检索。
- 本集成器本身不直接修改主 relationship builder 或最终 snapshot；root builder 只在本目录
  validation 通过后消费这些增量 claims。正式快照中的结论仍需提交者最终负责，不构成投资建议。
"""


def main() -> None:
    report_paths = {
        "sec": SEC / "validation_report.json",
        "apac": APAC / "validation_report.json",
        "emea": EMEA / "validation_report.json",
    }
    missing = [name for name, path in report_paths.items() if not path.exists()]
    if missing:
        raise SystemExit(f"Refusing integration: upstream validation report missing: {', '.join(missing)}")
    upstream_reports = {name: read_json(path) for name, path in report_paths.items()}
    failed = [name for name, report in upstream_reports.items() if not validation_pass(report)]
    if failed:
        raise SystemExit(f"Refusing integration: upstream validation not PASS: {', '.join(failed)}")

    universe, entity_map = entity_maps()
    mapper = ProductMapper()
    source_claims, evidence_map = upstream_claims(entity_map, mapper)
    claims = integrate_claims(source_claims, evidence_map)
    referenced = {eid for claim in claims for eid in claim["evidence_ids"]}
    evidence = sorted((evidence_map[eid] for eid in referenced), key=lambda x: x["evidence_id"])
    frontier, decisions = build_frontier_and_decisions(universe, entity_map, claims)

    summary = {
        "research_object": "NVIDIA canonical Partner regulatory reverse-direction integration",
        "research_window": WINDOW,
        "canonical_partner_total": len(universe),
        "upstream_validation": {name: {"pass": validation_pass(report), "status": report.get("status"), "counts": report.get("counts")} for name, report in upstream_reports.items()},
        "upstream_claim_counts": dict(Counter(x["workstream"] for x in source_claims)),
        "upstream_claim_total": len(source_claims),
        "canonical_claim_total": len(claims),
        "canonical_evidence_total": len(evidence),
        "fact_status_counts": dict(Counter(x["fact_status"] for x in claims)),
        "directness_counts": dict(Counter(x["directness"] for x in claims)),
        "relationship_type_counts": dict(Counter(x["relationship_type"] for x in claims)),
        "product_scope_counts": dict(Counter(x["product_scope_id"] for x in claims)),
        "frontier_terminal_counts": dict(Counter(x["terminal_status"] for x in frontier)),
        "pending": 0,
        "limitations": [
            "No-hit is not proof of no commercial relationship.",
            "News cannot support confirmed; inferred supplier/customer is capped below 60.",
            "corporate_general is used for mixed or unreliably matched product scopes.",
        ],
        "disclaimer": "Research service output; not investment advice.",
    }

    canonical_ids = {x["canonical_entity_id"] for x in universe}
    product_keys = mapper.keys | {"corporate_general"}
    errors = []
    five_keys = [(x["subject_entity_id"], x["object_entity_id"], x["direction"], x["relationship_type"], x["product_scope_id"]) for x in claims]
    if len(universe) != 316: errors.append(f"canonical universe expected 316, got {len(universe)}")
    if len(frontier) != 316 or len({x["canonical_entity_id"] for x in frontier}) != 316: errors.append("frontier is not exact 316 unique canonical entities")
    if {x["canonical_entity_id"] for x in frontier} != canonical_ids: errors.append("frontier does not exactly match canonical universe")
    if len(decisions) != 316 or len({x["canonical_entity_id"] for x in decisions}) != 316: errors.append("decision ledger is not exact 316 unique canonical entities")
    if any(x["status"] != "terminal" or x["pending"] for x in frontier + decisions): errors.append("non-terminal or pending rows")
    if len(five_keys) != len(set(five_keys)): errors.append("duplicate relationship five-tuple")
    if any(x["subject_entity_id"] not in canonical_ids | {"nvidia"} or x["object_entity_id"] not in canonical_ids | {"nvidia"} for x in claims): errors.append("non-canonical claim endpoint")
    if any(x["product_scope_id"] not in product_keys for x in claims): errors.append("non-canonical product scope")
    if any(x["directness"] not in ALLOWED_DIRECTNESS for x in claims): errors.append("invalid directness")
    if any(x["fact_status"] == "inferred" and x["confidence_score"] >= 60 for x in claims): errors.append("inferred confidence is not below 60")
    if any(
        x["confidence_score"] != min(
            100 if x["fact_status"] == "confirmed" else 59,
            round(
                sum(
                    value
                    for key, value in x["confidence_breakdown"].items()
                    if key != "conflict_penalty"
                )
                - x["confidence_breakdown"].get("conflict_penalty", 0)
            ),
        )
        for x in claims
    ): errors.append("confidence score does not equal explainable breakdown and status cap")
    if any(
        x["confidence_breakdown"]["independence"]
        > min(15, max(0, x["evidence_independence_stats"]["unique_publishers"] - 1) * 5)
        for x in claims
    ): errors.append("independence score exceeds distinct-publisher support")
    if any(x["fact_status"] == "confirmed" and not x["confirmed_support_evidence_ids"] for x in claims): errors.append("confirmed claim lacks regulatory support evidence")
    if any(eid not in {x["evidence_id"] for x in evidence} for claim in claims for eid in claim["evidence_ids"]): errors.append("claim evidence reference does not close")
    if any(
        not set(x["primary_evidence_ids"]).issubset(x["evidence_ids"])
        or len(x["primary_evidence_ids"])
        != x["evidence_independence_stats"]["unique_origin_publications"]
        for x in claims
    ): errors.append("primary evidence is not exactly one strongest context per origin publication")
    if any(x["access_control_bypassed"] or x["full_text_retained"] for x in evidence): errors.append("access/full-text policy violation")
    if any(not x["original_product_scopes"] for x in claims): errors.append("original product scope not retained")
    if any(validation_pass(x) is False for x in upstream_reports.values()): errors.append("upstream validation failed")
    serialized = json.dumps([claims, evidence, frontier, decisions, summary], ensure_ascii=False)
    if "/Users/" in serialized or "Graph Agent" in serialized or "file://" in serialized: errors.append("local absolute path leaked")

    report = {
        "pass": not errors, "errors": errors,
        "checks": {
            "all_upstream_validations_pass": all(validation_pass(x) for x in upstream_reports.values()),
            "canonical_frontier_exact_316": len(frontier) == 316 and {x["canonical_entity_id"] for x in frontier} == canonical_ids,
            "decision_ledger_exact_316": len(decisions) == 316 and len({x["canonical_entity_id"] for x in decisions}) == 316,
            "all_terminal_pending_zero": all(x["status"] == "terminal" and not x["pending"] for x in frontier + decisions),
            "relationship_five_tuple_unique": len(five_keys) == len(set(five_keys)),
            "entity_endpoints_canonical": all(x["subject_entity_id"] in canonical_ids | {"nvidia"} and x["object_entity_id"] in canonical_ids | {"nvidia"} for x in claims),
            "product_scopes_canonical_or_general": all(x["product_scope_id"] in product_keys for x in claims),
            "original_product_scope_retained": all(x["original_product_scopes"] for x in claims),
            "directness_enum_valid": all(x["directness"] in ALLOWED_DIRECTNESS for x in claims),
            "news_never_confirmed_without_regulatory_support": all(x["fact_status"] != "confirmed" or x["confirmed_support_evidence_ids"] for x in claims),
            "inferred_confidence_below_60": all(x["fact_status"] != "inferred" or x["confidence_score"] < 60 for x in claims),
            "scores_equal_breakdown_and_cap": all(
                x["confidence_score"] == min(
                    100 if x["fact_status"] == "confirmed" else 59,
                    round(
                        sum(
                            value
                            for key, value in x["confidence_breakdown"].items()
                            if key != "conflict_penalty"
                        )
                        - x["confidence_breakdown"].get("conflict_penalty", 0)
                    ),
                )
                for x in claims
            ),
            "independence_bounded_by_unique_publishers": all(
                x["confidence_breakdown"]["independence"]
                <= min(15, max(0, x["evidence_independence_stats"]["unique_publishers"] - 1) * 5)
                for x in claims
            ),
            "evidence_refs_close": all(eid in {x["evidence_id"] for x in evidence} for claim in claims for eid in claim["evidence_ids"]),
            "one_primary_context_per_origin_publication": all(
                set(x["primary_evidence_ids"]).issubset(x["evidence_ids"])
                and len(x["primary_evidence_ids"])
                == x["evidence_independence_stats"]["unique_origin_publications"]
                for x in claims
            ),
            "no_access_bypass_or_full_text": all(not x["access_control_bypassed"] and not x["full_text_retained"] for x in evidence),
            "no_local_absolute_paths": "/Users/" not in serialized and "Graph Agent" not in serialized and "file://" not in serialized,
        },
        "counts": {"claims": len(claims), "evidence": len(evidence), "frontier": len(frontier), "decisions": len(decisions), "pending": 0},
    }
    if errors:
        raise SystemExit("Integration validation failed: " + "; ".join(errors))

    write_jsonl(HERE / "claims.jsonl", claims)
    write_jsonl(HERE / "evidence.jsonl", evidence)
    write_jsonl(HERE / "source_frontier.jsonl", frontier)
    write_jsonl(HERE / "decision_ledger.jsonl", decisions)
    write_json(HERE / "summary.json", summary)
    write_json(HERE / "validation_report.json", report)
    (HERE / "README_ZH.md").write_text(render_readme(summary), encoding="utf-8")
    print(json.dumps({"summary": summary, "validation": report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
