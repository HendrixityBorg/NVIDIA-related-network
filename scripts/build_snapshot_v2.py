#!/usr/bin/env python3
"""Build the final v2 snapshot from frozen, validated research artifacts.

The builder intentionally fails closed.  It cannot emit the final snapshot
unless the product tree, official-article body ledger, runtime NPN population,
entity resolution, reviewed relationship claims and category peer review all
pass their own completion gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from arti.models import Snapshot


PEER_CATEGORY_TO_SCOPE = {
    "Data Center Compute": "accelerated-computing",
    "Networking": "networking",
    "AI Software & Cloud": "artificial-intelligence",
    "Gaming/Consumer": "gaming-and-creating",
    "Pro Viz/Design/Simulation": "professional-visualization-and-workstations",
    "Robotics/Edge/Embedded": "embedded-robotics-and-edge",
    "Automotive": "automotive",
    "Healthcare/Life Sciences": "healthcare-and-life-sciences",
}

BUILD_STARTED_AT = datetime.now(timezone.utc).replace(microsecond=0)
RETRIEVAL_NORMALIZATION_NOTE = (
    "retrieval timestamp normalized to final build time because upstream value was missing/future"
)

COVERAGE_REPORTS = (
    ("product_tree", "product_tree_v2/validation_report.json"),
    ("official_article_enumeration", "news/enumeration_validation_report.json"),
    ("article_body_recovery", "agents/article_body_recovery/validation_report.json"),
    ("filings_and_presentations", "agents/filings_presentations_complete/validation_report.json"),
    ("npn_runtime", "agents/npn_runtime_complete/validation_report.json"),
    ("npn_group_review", "agents/npn_runtime_complete/group_validation_report.json"),
    ("npn_listed_parent_resolution", "agents/npn_listed_parent_resolution/validation_report.json"),
    ("partner_regulatory_entity_normalization", "agents/partner_regulatory_entity_normalization/validation_report.json"),
    ("partner_regulatory_sec_cik_hydration", "agents/partner_regulatory_entity_normalization/sec_cik_hydration_validation.json"),
    ("partner_regulatory_source_registry", "agents/partner_regulatory_source_registry/validation_report.json"),
    ("partner_regulatory_sec_review", "agents/partner_regulatory_sec_review/validation_report.json"),
    ("partner_regulatory_apac_review", "agents/partner_regulatory_apac_review/validation_report.json"),
    ("partner_regulatory_emea_review", "agents/partner_regulatory_emea_review/validation_report.json"),
    ("partner_regulatory_integration", "agents/partner_regulatory_integration/validation_report.json"),
    ("base_entity_resolution", "agents/entity_resolution_complete/validation_report.json"),
    ("global_listing_overlay", "agents/global_listing_overlay/validation_report.json"),
    ("non_npn_listing_resolution", "agents/non_npn_listing_audit/researched_resolution_validation_report.json"),
    ("listing_temporal_audit", "agents/listing_temporal_audit/validation_report.json"),
    ("relationship_review", "agents/relationship_review_complete/validation_report.json"),
    ("peer_review", "agents/peers_complete/validation_report.json"),
)


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path, *, required: bool = True) -> list[dict[str, Any]]:
    if not path.is_file():
        if required:
            raise FileNotFoundError(path)
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
    return rows


def stable_id(prefix: str, *values: object) -> str:
    joined = "|".join(str(value) for value in values)
    return f"{prefix}_{hashlib.sha256(joined.encode()).hexdigest()[:20]}"


def normalized_retrieval_datetime(
    value: object,
    *,
    build_started_at: datetime = BUILD_STARTED_AT,
) -> tuple[str, bool]:
    """Return a valid non-future retrieval time and whether it was clamped."""
    if build_started_at.tzinfo is None:
        raise ValueError("build_started_at must be timezone-aware")
    if value is None or str(value).strip() in {"", "None", "null"}:
        return build_started_at.isoformat(), True
    text = str(value)
    if len(text) == 10:
        text += "T00:00:00+00:00"
    text = text.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError(f"retrieval timestamp must be timezone-aware: {value}")
    if parsed > build_started_at:
        return build_started_at.isoformat(), True
    return text, False


def normalized_datetime(value: object) -> str:
    return normalized_retrieval_datetime(value)[0]


def normalize_listing_status(value: str | None) -> str:
    return {
        "listed": "listed",
        "listed_confirmed": "listed",
        "private": "private",
        "delisted": "delisted",
    }.get(value or "", "unknown")


EXCHANGE_LISTING_REGION: dict[str, tuple[str, str]] = {
    "Australian Securities Exchange": ("Australia", "AU"),
    "Borsa Italiana": ("Italy", "IT"),
    "Bursa Malaysia": ("Malaysia", "MY"),
    "Euronext Amsterdam": ("Netherlands", "NL"),
    "Euronext Growth Paris": ("France", "FR"),
    "Euronext Paris": ("France", "FR"),
    "Frankfurt / Munich": ("Germany", "DE"),
    "Frankfurt / Xetra": ("Germany", "DE"),
    "Hong Kong Stock Exchange": ("Hong Kong", "HK"),
    "Hong Kong Stock Exchange RMB Counter": ("Hong Kong", "HK"),
    "HKEX": ("Hong Kong", "HK"),
    "Ho Chi Minh Stock Exchange": ("Vietnam", "VN"),
    "KOSDAQ": ("South Korea", "KR"),
    "Korea Exchange": ("South Korea", "KR"),
    "Korea Exchange / KOSPI": ("South Korea", "KR"),
    "London Stock Exchange": ("United Kingdom", "GB"),
    "Luxembourg Stock Exchange": ("Luxembourg", "LU"),
    "Nagoya Stock Exchange": ("Japan", "JP"),
    "Nasdaq": ("United States", "US"),
    "NASDAQ": ("United States", "US"),
    "Nasdaq Global Select Market": ("United States", "US"),
    "Nasdaq Helsinki": ("Finland", "FI"),
    "Nasdaq Stockholm": ("Sweden", "SE"),
    "NASDAQ_STOCKHOLM": ("Sweden", "SE"),
    "National Stock Exchange of India": ("India", "IN"),
    "NYSE": ("United States", "US"),
    "Oslo Bors": ("Norway", "NO"),
    "Oslo Børs": ("Norway", "NO"),
    "OTC": ("United States", "US"),
    "Shanghai Stock Exchange": ("China", "CN"),
    "Shanghai Stock Exchange STAR Market": ("China", "CN"),
    "Shenzhen Stock Exchange": ("China", "CN"),
    "Singapore Exchange": ("Singapore", "SG"),
    "SIX Swiss Exchange": ("Switzerland", "CH"),
    "Taipei Exchange": ("Taiwan", "TW"),
    "Taiwan Stock Exchange": ("Taiwan", "TW"),
    "Tokyo Stock Exchange": ("Japan", "JP"),
    "TSE": ("Japan", "JP"),
    "Toronto Stock Exchange": ("Canada", "CA"),
    "Warsaw Stock Exchange": ("Poland", "PL"),
    "Xetra": ("Germany", "DE"),
    "Xetra / Frankfurt": ("Germany", "DE"),
}


def listing_region_for_exchange(exchange: str) -> tuple[str, str]:
    try:
        return EXCHANGE_LISTING_REGION[exchange]
    except KeyError as exc:
        raise ValueError(f"unmapped listing exchange: {exchange}") from exc


def annotate_listing_regions(entities: dict[str, dict[str, Any]]) -> None:
    """Add market location independently from issuer domicile/country."""
    for entity in entities.values():
        securities = entity.get("securities") or []
        if entity.get("listing_status") == "listed" and not securities:
            raise ValueError(f"listed entity has no security: {entity['id']}")
        for security in securities:
            region, code = listing_region_for_exchange(security["exchange"])
            security["listing_region"] = region
            security["listing_region_code"] = code

        ordered = sorted(
            enumerate(securities),
            key=lambda pair: (not bool(pair[1].get("primary")), pair[0]),
        )
        regions: list[str] = []
        for _, security in ordered:
            region = security["listing_region"]
            if region not in regions:
                regions.append(region)
        entity["listing_regions"] = regions


def security_from_registry(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "ticker": str(row.get("ticker") or "UNKNOWN"),
        "exchange": str(row.get("exchange") or "UNKNOWN"),
        "cik": row.get("cik"),
        "cusip": row.get("cusip"),
        "isin": row.get("isin"),
        "mic": row.get("mic"),
        "primary": row.get("primary"),
        "status_at_cutoff": row.get("status_at_cutoff"),
        "security_type": row.get("security_type") or row.get("security_class") or "common_equity",
    }


def entity_from_registry(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["entity_id"],
        "legal_name": row["legal_name"],
        "display_name": row.get("display_name") or row["legal_name"],
        "aliases": sorted(set(row.get("aliases") or [])),
        "country": row.get("country") or row.get("jurisdiction"),
        "listing_status": normalize_listing_status(row.get("listing_status")),
        "securities": [security_from_registry(item) for item in row.get("securities") or []],
        "ultimate_parent_id": row.get("ultimate_parent_id"),
        "notes": row.get("notes")
        or "; ".join((row.get("conflict_notes") or []) + (row.get("temporal_notes") or []))
        or None,
    }


def source_access_policy(
    access_constraints: object,
    *,
    retrieval_timestamp_normalized: bool = False,
) -> dict[str, Any]:
    if isinstance(access_constraints, dict):
        policy = {
            "access": access_constraints.get("access") or "public_no_login",
            "login_required": bool(access_constraints.get("login_required", False)),
            "paywall": bool(access_constraints.get("paywall", False)),
            "robots_checked_at": None,
            "redistribution": access_constraints.get("redistribution")
            or "structured facts and short excerpts only",
            "notes": access_constraints.get("notes")
            or "No robots, login, paywall, CAPTCHA, rate-limit or access-control bypass used.",
        }
    else:
        policy = {
            "access": "public_no_login",
            "login_required": False,
            "paywall": False,
            "robots_checked_at": None,
            "redistribution": "structured facts and short excerpts only",
            "notes": str(access_constraints or "No access-control bypass used."),
        }
    if retrieval_timestamp_normalized:
        policy["notes"] = "; ".join(
            item for item in (policy.get("notes"), RETRIEVAL_NORMALIZATION_NOTE) if item
        )
    return policy


def ensure_gate(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def report_passed(report: dict[str, Any]) -> bool:
    return bool(
        report.get("pass")
        or report.get("passed")
        or report.get("complete")
        or report.get("status") in {"pass", "passed"}
        or report.get("overall_status") == "pass"
    )


def report_pending(report: dict[str, Any]) -> int:
    return int(report.get("pending", report.get("pending_count", 0)))


def build_coverage_frontier(run_root: Path) -> dict[str, Any]:
    """Summarize frozen closure reports without inventing final source IDs."""
    artifacts: list[dict[str, Any]] = []
    portable_run_root = Path("runs") / run_root.name
    for family, relative in COVERAGE_REPORTS:
        report = read_json(run_root / relative)
        selected_counts = report.get("counts") or {}
        for field in (
            "manifest_total",
            "manifest_expected",
            "terminal_rows",
            "ledger_rows",
            "body_covered",
            "access_blocked",
            "observed_raw_observations",
            "unique_raw_observation_ids",
            "entity_group_count",
            "listed_group_match_count",
            "relationship_claim_count",
            "candidate_names",
            "registry_entities",
            "claims",
            "decision_rows",
            "peer_relationship_records",
            "unique_peer_issuers",
        ):
            if field in report:
                selected_counts[field] = report[field]
        artifacts.append(
            {
                "family": family,
                "validation_report": str(portable_run_root / relative),
                "status": "pass" if report_passed(report) else "not_passed",
                "pending": report_pending(report),
                "reported_counts": selected_counts,
            }
        )
    return {
        "schema_version": "2.0",
        "cutoff_at": "2026-08-25T23:59:59+08:00",
        "evidence_start_date": "2025-01-01",
        "definition": (
            "Deterministic v2 closure summary over frozen run validation reports. "
            "It does not enumerate or invent final snapshot source IDs."
        ),
        "release_ready": all(
            item["status"] == "pass" and item["pending"] == 0 for item in artifacts
        ),
        "artifacts": artifacts,
    }


def terminal_gate_checks(run_root: Path) -> None:
    failures: list[str] = []
    enumeration = read_json(run_root / "news" / "enumeration_validation_report.json")
    ensure_gate(report_passed(enumeration), "official article enumeration did not pass", failures)
    ensure_gate(
        enumeration.get("counts", {}).get("canonical_articles") == 765,
        "official article enumeration is not the frozen 765-item frontier",
        failures,
    )

    filings = read_json(
        run_root / "agents" / "filings_presentations_complete" / "validation_report.json"
    )
    ensure_gate(report_passed(filings), "filings/presentations validation did not pass", failures)
    ensure_gate(
        filings.get("counts", {}).get("sources") == 9,
        "filings/presentations frontier is not 10-K + 13F cover/table + six presentations",
        failures,
    )

    product = read_json(run_root / "product_tree_v2" / "validation_report.json")
    ensure_gate(
        bool(
            product.get("pass")
            or product.get("complete")
            or product.get("status") == "pass"
            or product.get("overall_status") == "pass"
        ),
        "product tree validation did not pass",
        failures,
    )
    ensure_gate(
        product.get("pending", product.get("pending_count", 0)) == 0,
        "product tree has pending rows",
        failures,
    )

    recovery = read_json(run_root / "agents" / "article_body_recovery" / "validation_report.json")
    ensure_gate(bool(recovery.get("pass") or recovery.get("complete")), "article body recovery did not pass", failures)
    manifest_total = recovery.get("manifest_total", recovery.get("manifest_expected"))
    terminal_rows = recovery.get("terminal_rows", recovery.get("ledger_rows"))
    ensure_gate(manifest_total == 597, "article recovery total is not 597", failures)
    ensure_gate(terminal_rows == 597, "not all 597 Blog articles are terminal", failures)
    ensure_gate(recovery.get("pending", 1) == 0, "article recovery has pending rows", failures)

    npn = read_json(run_root / "agents" / "npn_runtime_complete" / "validation_report.json")
    ensure_gate(bool(npn.get("complete") or npn.get("pass")), "runtime NPN validation did not pass", failures)
    npn_total = npn.get("runtime_total", npn.get("observed_raw_observations"))
    npn_unique = npn.get("unique_listings", npn.get("unique_raw_observation_ids"))
    npn_pending = npn.get("pending", npn.get("pending_count", 1))
    ensure_gate(npn_total == 997, "runtime NPN total is not the final frozen 997", failures)
    ensure_gate(npn_unique == 997, "runtime NPN does not contain 997 unique raw observations", failures)
    ensure_gate(npn_pending == 0, "runtime NPN has pending rows", failures)

    for relative, label in (
        ("agents/entity_resolution_complete/validation_report.json", "base entity resolution"),
        ("agents/global_listing_overlay/validation_report.json", "global listing overlay"),
        ("agents/non_npn_listing_audit/researched_resolution_validation_report.json", "non-NPN listing resolution"),
        ("agents/listing_temporal_audit/validation_report.json", "listing temporal audit"),
        ("agents/relationship_review_complete/validation_report.json", "relationship review"),
        ("agents/peers_complete/validation_report.json", "peer review"),
        ("agents/npn_runtime_complete/group_validation_report.json", "NPN group review"),
        ("agents/npn_listed_parent_resolution/validation_report.json", "NPN listed-parent resolution"),
        ("agents/partner_regulatory_entity_normalization/validation_report.json", "Partner regulatory entity normalization"),
        ("agents/partner_regulatory_entity_normalization/sec_cik_hydration_validation.json", "Partner SEC CIK hydration"),
        ("agents/partner_regulatory_source_registry/validation_report.json", "Partner regulatory source registry"),
        ("agents/partner_regulatory_sec_review/validation_report.json", "Partner SEC regulatory review"),
        ("agents/partner_regulatory_apac_review/validation_report.json", "Partner APAC regulatory review"),
        ("agents/partner_regulatory_emea_review/validation_report.json", "Partner EMEA regulatory review"),
        ("agents/partner_regulatory_integration/validation_report.json", "Partner regulatory integration"),
    ):
        report = read_json(run_root / relative)
        ensure_gate(
            bool(report.get("pass") or report.get("complete") or report.get("status") == "pass"),
            f"{label} did not pass",
            failures,
        )
        pending = report.get("pending", report.get("pending_count", 0))
        ensure_gate(pending == 0, f"{label} has pending rows", failures)

    if failures:
        raise RuntimeError("final snapshot gates remain open:\n- " + "\n- ".join(failures))


def add_relation_evidence(
    fingerprints: Iterable[dict[str, Any]],
    evidence_to_claims: dict[str, list[str]],
    sources: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
) -> None:
    for row in fingerprints:
        url = row["source_url"]
        source_id = stable_id("source", url, row.get("content_fingerprint"))
        retrieved_at, retrieval_normalized = normalized_retrieval_datetime(
            row.get("retrieved_at")
        )
        sources.setdefault(
            source_id,
            {
                "id": source_id,
                "url": url,
                "publisher": row["publisher"],
                "title": f"{row['publisher']} evidence ({row.get('published_at') or 'retrieved source'})",
                "source_type": row["source_family"],
                "published_at": row.get("published_at"),
                "retrieved_at": retrieved_at,
                "access_policy": source_access_policy(
                    row.get("access_constraints") or row.get("access_or_license_restrictions"),
                    retrieval_timestamp_normalized=retrieval_normalized,
                ),
                "content_sha256": row.get("content_fingerprint"),
                "source_family": row["source_family"],
            },
        )
        evidence[row["evidence_id"]] = {
            "id": row["evidence_id"],
            "source_id": source_id,
            "locator": row["evidence_locator"],
            "excerpt": row.get("evidence_excerpt"),
            "visual_description": None,
            "supports": ", ".join(sorted(evidence_to_claims[row["evidence_id"]])),
            "inference_basis": [],
            "human_verified": False,
            "notes": f"fingerprint_sha256={row.get('fingerprint_sha256')}; freshness_factor={row.get('freshness_factor')}",
        }


def relation_from_claim(
    claim: dict[str, Any],
    evidence_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    evidence_ids = claim["evidence_ids"]
    publishers = sorted({evidence_rows[item]["publisher"] for item in evidence_ids})
    observation_count = sum(len(evidence_rows[item].get("input_decision_ids") or []) for item in evidence_ids)
    relation_type = claim["relationship_type"]
    api_type = "investor_or_investee" if relation_type == "investee" else relation_type
    temporal = {
        "point_in_time": "point_in_time",
        "historical": "historical",
        "planned": "planned",
        "unknown": "unknown",
    }.get(claim.get("temporal_status"), "current")
    score = int(claim["confidence_score"])
    quantitative = claim.get("quantitative") or {}
    quant_note = " Quantitative filing fields increase the quantification component." if quantitative else " No quantitative amount was inferred."
    relationship_evidence_ids = claim.get("relationship_evidence_ids") or evidence_ids
    entity_resolution_evidence_ids = claim.get("entity_resolution_evidence_ids") or []
    if api_type == "supplier":
        default_directness = "direct" if claim["fact_status"] == "confirmed" else "unclear"
    elif api_type == "customer":
        default_directness = "unclear"
    else:
        default_directness = "not_applicable"
    evidence_roles = dict(claim.get("evidence_roles") or {})
    for evidence_id in relationship_evidence_ids:
        evidence_roles.setdefault(evidence_id, "primary")
    for evidence_id in entity_resolution_evidence_ids:
        evidence_roles.setdefault(evidence_id, "corroborating")
    return {
        "id": claim["claim_id"],
        "source_entity_id": claim["subject_entity_id"],
        "target_entity_id": claim["object_entity_id"],
        "relation_type": api_type,
        "direction": claim["direction"],
        "direction_explanation": claim["direction_explanation"],
        "commercial_directness": claim.get("commercial_directness") or default_directness,
        "relation_subtype": relation_type if relation_type == "investee" else None,
        "product_scope_id": claim["product_scope_id"],
        "product_scopes": [],
        "channels": sorted(set(claim.get("source_families") or [])),
        "fact_status": claim["fact_status"],
        "temporal_status": temporal,
        "as_of": claim["as_of"],
        "valid_from": None,
        "valid_to": None,
        "confidence_score": score,
        "relevance_score": score,
        "confidence_breakdown": claim["confidence_breakdown"],
        "relevance_explanation": (
            "The 0-100 relationship score uses source authority, explicitness, exact entity resolution, "
            "independent publishers, cutoff-relative timeliness, relationship-type specificity, quantitative "
            f"fields and conflict penalties; status caps are then applied.{quant_note}"
        ),
        "evidence_ids": evidence_ids,
        "evidence_roles": evidence_roles,
        "relationship_evidence_ids": relationship_evidence_ids,
        "entity_resolution_evidence_ids": entity_resolution_evidence_ids,
        "origin_terminal_statuses": claim.get("origin_terminal_statuses") or ["approved"],
        "inference_explanations": claim.get("inference_explanations") or [],
        "low_confidence_partner_inclusion": bool(claim.get("low_confidence_partner_inclusion")),
        "entity_resolution_inferred": bool(claim.get("entity_resolution_inferred")),
        "entity_resolution_research_ids": claim.get("entity_resolution_research_ids") or [],
        "observation_count": max(1, observation_count),
        "independent_source_count": int(claim.get("independent_publisher_count") or len(publishers)),
        "quantitative": quantitative,
        "asserted_by": publishers,
        "counterevidence": claim.get("counterevidence") or [],
        "limitations": claim.get("limitations") or [],
    }


def exact_breakdown(score: int, status: str) -> dict[str, float]:
    """Create a transparent peer/NPN component allocation summing to score."""
    if status == "confirmed":
        values = {
            "source_authority": 25.0,
            "explicitness": 25.0,
            "entity_resolution": 15.0,
            "independence": 0.0,
            "timeliness": 10.0,
            "relationship_type_specificity": 5.0,
            "quantification": 0.0,
            "conflict_penalty": 0.0,
        }
    else:
        values = {
            "source_authority": 20.0,
            "explicitness": 15.0,
            "entity_resolution": 15.0,
            "independence": 5.0,
            "timeliness": 9.0,
            "relationship_type_specificity": 5.0,
            "quantification": 0.0,
            "conflict_penalty": 0.0,
        }
    current = round(sum(values.values()))
    delta = score - current
    if delta > 0:
        add = min(delta, 15 - values["independence"])
        values["independence"] += add
        delta -= round(add)
    if delta > 0:
        add = min(delta, 10 - values["quantification"])
        values["quantification"] += add
        delta -= round(add)
    if delta < 0:
        for field in ("independence", "timeliness", "explicitness", "source_authority"):
            remove = min(-delta, values[field])
            values[field] -= remove
            delta += round(remove)
            if delta == 0:
                break
    if delta:
        raise ValueError(f"cannot allocate score {score}")
    return values


def add_peer_data(
    run_root: Path,
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> None:
    source_rows = read_jsonl(run_root / "agents" / "peers_complete" / "source_evidence.jsonl")
    peer_rows = [
        item
        for item in read_jsonl(run_root / "agents" / "peers_complete" / "peer_candidates.jsonl")
        if item.get("review_status") == "accepted"
    ]
    security_to_entity = {
        f"{security['exchange'].casefold()}:{security['ticker'].casefold()}": entity_id
        for entity_id, entity in entities.items()
        for security in entity["securities"]
    }
    ev_to_peer: dict[str, list[str]] = defaultdict(list)
    for peer in peer_rows:
        for evidence_id in peer["evidence_ids"]:
            ev_to_peer[evidence_id].append(peer["peer_candidate_id"])
    for row in source_rows:
        source_id = stable_id("source", row["url"], row.get("content_fingerprint"))
        retrieved_at, retrieval_normalized = normalized_retrieval_datetime(
            row.get("retrieved_at")
        )
        sources.setdefault(
            source_id,
            {
                "id": source_id,
                "url": row["url"],
                "publisher": row["publisher"],
                "title": row["title"],
                "source_type": row["source_type"],
                "published_at": row.get("published_at"),
                "retrieved_at": retrieved_at,
                "access_policy": source_access_policy(
                    row.get("access_constraints") or row.get("access_or_license_restrictions"),
                    retrieval_timestamp_normalized=retrieval_normalized,
                ),
                "content_sha256": row.get("content_fingerprint"),
                "source_family": row["source_type"],
            },
        )
        evidence[row["evidence_id"]] = {
            "id": row["evidence_id"],
            "source_id": source_id,
            "locator": row["evidence_locator"],
            "excerpt": row.get("short_excerpt"),
            "visual_description": None,
            "supports": ", ".join(sorted(ev_to_peer.get(row["evidence_id"], []))),
            "inference_basis": [],
            "human_verified": True,
            "notes": row.get("notes"),
        }
    for peer in peer_rows:
        security = peer["security"]
        security_key = f"{security['exchange'].casefold()}:{security['ticker'].casefold()}"
        target_id = security_to_entity.get(security_key)
        if target_id is None:
            target_id = stable_id("entity", security["exchange"], security["ticker"])
            entities[target_id] = {
                "id": target_id,
                "legal_name": peer["object_legal_name"],
                "display_name": peer["object_legal_name"],
                "aliases": [security["ticker"]],
                "country": None,
                "listing_status": "listed",
                "securities": [security_from_registry(security)],
                "ultimate_parent_id": None,
                "notes": "Added from validated product-category peer review.",
            }
        score = int(peer["confidence_score"])
        category = peer["product_category_id"]
        if category not in PEER_CATEGORY_TO_SCOPE:
            raise ValueError(f"unmapped peer product category: {category}")
        relationships.append(
            {
                "id": peer["peer_candidate_id"],
                "source_entity_id": "nvidia",
                "target_entity_id": target_id,
                "relation_type": "peer",
                "direction": "competes_with",
                "direction_explanation": peer["review_rationale"],
                "commercial_directness": "not_applicable",
                "relation_subtype": "product_category_peer",
                "product_scope_id": PEER_CATEGORY_TO_SCOPE[category],
                "product_scopes": [],
                "channels": ["product_category_peer_review"],
                "fact_status": peer["fact_status"],
                "temporal_status": "current",
                "as_of": peer["as_of"],
                "valid_from": None,
                "valid_to": None,
                "confidence_score": score,
                "relevance_score": score,
                "confidence_breakdown": exact_breakdown(score, peer["fact_status"]),
                "relevance_explanation": (
                    "Score reflects direct category substitution, NVIDIA competitor disclosure, "
                    "counterparty official self-developed product evidence, independent source families, "
                    "current listing and cutoff timeliness; inferred status is capped at 69."
                ),
                "evidence_ids": peer["evidence_ids"],
                "evidence_roles": {
                    evidence_id: "primary" for evidence_id in peer["evidence_ids"]
                },
                "observation_count": len(peer["evidence_ids"]),
                "independent_source_count": int(peer["confidence_factors"]["independent_source_families"]),
                "quantitative": {"competing_product": peer["counterparty_competing_product_or_platform"]},
                "asserted_by": sorted(
                    {
                        sources[evidence[item]["source_id"]]["publisher"]
                        for item in peer["evidence_ids"]
                    }
                ),
                "counterevidence": peer.get("uncertainty_or_conflict") or [],
                "limitations": ["Peer scope is the named top-level product category, not the issuer's entire business."],
            }
        )


def add_npn_data(
    run_root: Path,
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> None:
    base = run_root / "agents" / "npn_runtime_complete"
    resolution_base = run_root / "agents" / "npn_listed_parent_resolution"
    complete_claims = resolution_base / "relationship_claims_complete.jsonl"
    claims = read_jsonl(
        complete_claims if complete_claims.is_file() else base / "relationship_claims.jsonl"
    )
    combined_evidence_rows = read_jsonl(base / "evidence.jsonl")
    if complete_claims.is_file():
        combined_evidence_rows.extend(read_jsonl(resolution_base / "mapping_evidence.jsonl"))
    npn_evidence = list(
        {row["evidence_id"]: row for row in combined_evidence_rows}.values()
    )
    ev_to_claims: dict[str, list[str]] = defaultdict(list)
    for claim in claims:
        for evidence_id in claim["evidence_ids"]:
            ev_to_claims[evidence_id].append(claim["claim_id"])
    for row in npn_evidence:
        source_family = (
            "npn_runtime_directory"
            if str(row.get("evidence_id") or "").startswith("npn-evidence-")
            or str(row.get("evidence_type") or "").startswith("npn_")
            or row.get("source_family") == "npn_runtime_directory"
            else "entity_resolution"
        )
        source_id = stable_id("source", row["source_url"], row.get("source_content_sha256"))
        retrieved_at, retrieval_normalized = normalized_retrieval_datetime(
            row.get("retrieved_at")
        )
        sources.setdefault(
            source_id,
            {
                "id": source_id,
                "url": row["source_url"],
                "publisher": row.get("publisher") or "NVIDIA Corporation",
                "title": row.get("title") or "NVIDIA Partner Network Locator runtime page",
                "source_type": source_family,
                "published_at": None,
                "retrieved_at": retrieved_at,
                "access_policy": source_access_policy(
                    row.get("access_constraints") or row.get("access_or_license_restrictions"),
                    retrieval_timestamp_normalized=retrieval_normalized,
                ),
                "content_sha256": row.get("source_content_sha256"),
                "source_family": source_family,
            },
        )
        evidence[row["evidence_id"]] = {
            "id": row["evidence_id"],
            "source_id": source_id,
            "locator": row["evidence_locator"],
            "excerpt": row.get("excerpt") or row.get("supports"),
            "visual_description": None,
            "supports": ", ".join(sorted(ev_to_claims[row["evidence_id"]])),
            "inference_basis": [],
            "human_verified": False,
            "notes": row.get("notes") or row.get("upstream_path"),
        }
    for claim in claims:
        if claim["object_entity_id"] not in entities:
            raise ValueError(f"NPN claim references unknown listed entity {claim['object_entity_id']}")
        fact_status = claim.get("fact_status") or "confirmed"
        score = min(int(claim["confidence_score"]), 69) if fact_status == "inferred" else int(claim["confidence_score"])
        relationship_evidence_ids = claim.get("npn_evidence_ids") or [
            item for item in claim["evidence_ids"] if item.startswith("npn-evidence-")
        ]
        entity_resolution_evidence_ids = claim.get("mapping_evidence_ids") or sorted(
            set(claim["evidence_ids"]) - set(relationship_evidence_ids)
        )
        resolution_kinds = claim.get("resolution_kinds") or []
        endpoint_inferred = bool(
            claim.get("entity_resolution_inferred")
            or fact_status == "inferred"
            or set(resolution_kinds) & {"brand_to_parent", "subsidiary_to_parent"}
        )
        inference_explanations = claim.get("inference_explanations") or (
            [
                "NPN names the observed card entity; the graph endpoint is its evidenced "
                "listed parent, so the endpoint substitution and relationship are retained as inferred."
            ]
            if endpoint_inferred
            else []
        )
        relationships.append(
            {
                "id": claim["claim_id"],
                "source_entity_id": "nvidia",
                "target_entity_id": claim["object_entity_id"],
                "relation_type": "partner",
                "direction": "partners_with",
                "direction_explanation": claim["direction_explanation"],
                "commercial_directness": "not_applicable",
                "relation_subtype": "nvidia_partner_network_member",
                "product_scope_id": claim["product_scope_id"],
                "product_scopes": [],
                "channels": claim.get("partner_types") or [],
                "fact_status": fact_status,
                "temporal_status": "current",
                "as_of": "2026-08-25",
                "valid_from": None,
                "valid_to": None,
                "confidence_score": score,
                "relevance_score": score,
                "confidence_breakdown": exact_breakdown(score, fact_status),
                "relevance_explanation": (
                    "Official runtime NPN membership, exact listed-company/group resolution, repeated regional "
                    "listings and product competency tags drive the score; directory membership alone does not "
                    "establish supplier or customer direction."
                ),
                "evidence_ids": claim["evidence_ids"],
                "evidence_roles": {
                    **{item: "primary" for item in relationship_evidence_ids},
                    **{item: "corroborating" for item in entity_resolution_evidence_ids},
                },
                "relationship_evidence_ids": relationship_evidence_ids,
                "entity_resolution_evidence_ids": entity_resolution_evidence_ids,
                "origin_terminal_statuses": ["approved"],
                "inference_explanations": inference_explanations,
                "low_confidence_partner_inclusion": False,
                "entity_resolution_inferred": endpoint_inferred,
                "entity_resolution_research_ids": claim.get("entity_resolution_research_ids") or [],
                "observation_count": int(
                    claim.get("observation_count")
                    or len(claim.get("source_observation_ids") or [])
                    or 1
                ),
                "independent_source_count": 1,
                "quantitative": {
                    "partner_types": claim.get("partner_types") or [],
                    "competencies": claim.get("competencies") or [claim.get("competency")],
                    "specializations": claim.get("specializations") or [],
                    "partner_levels": claim.get("partner_levels") or [],
                    "locations": claim.get("locations") or [],
                    "raw_listing_ids": claim.get("raw_listing_ids")
                    or claim.get("source_observation_ids")
                    or [],
                },
                "asserted_by": ["NVIDIA Corporation"],
                "counterevidence": [],
                "limitations": ["NPN membership does not by itself prove a commercial transaction or revenue materiality."],
            }
        )


def add_partner_regulatory_data(
    run_root: Path,
    entities: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> None:
    """Add validated reverse-direction Partner filing review conclusions."""
    base = run_root / "agents" / "partner_regulatory_integration"
    claims = read_jsonl(base / "claims.jsonl")
    evidence_rows = read_jsonl(base / "evidence.jsonl")
    evidence_to_claims: dict[str, list[str]] = defaultdict(list)
    for claim in claims:
        for evidence_id in claim["evidence_ids"]:
            evidence_to_claims[evidence_id].append(claim["claim_id"])

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for row in evidence_rows:
        evidence_id = row["evidence_id"]
        evidence_by_id[evidence_id] = row
        source_url = row.get("url")
        if not source_url:
            raise ValueError(f"Partner regulatory evidence {evidence_id} has no public URL")
        content_sha = row.get("source_content_sha256") or row.get(
            "origin_content_fingerprint"
        )
        source_id = stable_id(
            "source", source_url, row.get("origin_publication_id"), content_sha
        )
        retrieved_at, retrieval_normalized = normalized_retrieval_datetime(
            row.get("retrieved_at")
        )
        sources.setdefault(
            source_id,
            {
                "id": source_id,
                "url": source_url,
                "publisher": row.get("publisher") or "Public regulatory publisher",
                "title": (
                    f"{row.get('publisher') or 'Issuer'} Partner counterparty evidence "
                    f"({row.get('published_at') or 'retrieved source'})"
                ),
                "source_type": row.get("source_kind") or "regulatory_filing",
                "published_at": row.get("published_at"),
                "retrieved_at": retrieved_at,
                "access_policy": source_access_policy(
                    {
                        "access": row.get("access_mode") or "public_no_login",
                        "redistribution": row.get("redistribution")
                        or "structured facts and necessary short excerpt only",
                        "notes": (
                            "Partner counterparty reverse-direction review; no robots, login, "
                            "paywall, CAPTCHA, rate-limit or access-control bypass used."
                        ),
                    },
                    retrieval_timestamp_normalized=retrieval_normalized,
                ),
                "content_sha256": content_sha,
                "source_family": row.get("source_family")
                or row.get("source_kind")
                or "regulatory_filing",
            },
        )
        evidence[evidence_id] = {
            "id": evidence_id,
            "source_id": source_id,
            "locator": row.get("evidence_locator") or "NVIDIA mention context",
            "excerpt": row.get("evidence_excerpt"),
            "visual_description": None,
            "supports": ", ".join(sorted(evidence_to_claims[evidence_id])),
            "inference_basis": [],
            "human_verified": False,
            "notes": (
                f"workstreams={','.join(row.get('workstreams') or [])}; "
                f"origin_publication_id={row.get('origin_publication_id')}; "
                "only a necessary short excerpt is retained"
            ),
        }

    for claim in claims:
        missing_entities = sorted(
            {claim["subject_entity_id"], claim["object_entity_id"]} - set(entities)
        )
        if missing_entities:
            raise ValueError(
                f"Partner regulatory claim {claim['claim_id']} references missing entities "
                f"{missing_entities}"
            )
        score = int(claim["confidence_score"])
        fact_status = claim["fact_status"]
        primary_ids = set(claim.get("primary_evidence_ids") or [])
        if not primary_ids:
            primary_by_origin: dict[str, str] = {}
            for evidence_id in claim["evidence_ids"]:
                evidence_row = evidence_by_id[evidence_id]
                origin = str(
                    evidence_row.get("origin_publication_id")
                    or evidence_row.get("url")
                    or evidence_id
                )
                primary_by_origin.setdefault(origin, evidence_id)
            primary_ids = set(primary_by_origin.values())
        evidence_roles = {
            evidence_id: "primary" if evidence_id in primary_ids else "corroborating"
            for evidence_id in claim["evidence_ids"]
        }
        publishers = sorted(
            {
                evidence_by_id[evidence_id].get("publisher")
                or "Public regulatory publisher"
                for evidence_id in claim["evidence_ids"]
            }
        )
        relationship_type = claim["relationship_type"]
        if relationship_type == "supplier":
            explanation = (
                "Counterparty-side public evidence identifies NVIDIA as a customer or "
                "otherwise states a supply flow from the counterparty toward NVIDIA."
            )
        elif relationship_type == "customer":
            explanation = (
                "Counterparty-side public evidence states that the counterparty purchases, "
                "licenses, deploys or depends on NVIDIA products; NVIDIA sells to the counterparty."
            )
        else:
            raise ValueError(
                f"Partner regulatory claim has unsupported type {relationship_type}"
            )
        relationships.append(
            {
                "id": claim["claim_id"],
                "source_entity_id": claim["subject_entity_id"],
                "target_entity_id": claim["object_entity_id"],
                "relation_type": relationship_type,
                "direction": claim["direction"],
                "direction_explanation": explanation,
                "commercial_directness": claim.get("directness") or "unclear",
                "relation_subtype": "partner_counterparty_reverse_review",
                "product_scope_id": claim["product_scope_id"],
                "product_scopes": [],
                "channels": sorted(
                    set(
                        (claim.get("source_workstreams") or [])
                        + (claim.get("source_kinds") or [])
                    )
                ),
                "fact_status": fact_status,
                "temporal_status": "current",
                "as_of": "2026-08-25",
                "valid_from": None,
                "valid_to": None,
                "confidence_score": score,
                "relevance_score": score,
                "confidence_breakdown": claim.get("confidence_breakdown")
                or exact_breakdown(score, fact_status),
                "relevance_explanation": (
                    "The score reflects counterparty filing authority, explicit commercial-flow "
                    "language, exact issuer resolution, source independence, timeliness, product "
                    "specificity and quantitative details. Inferred supplier/customer claims are "
                    "capped below 60."
                ),
                "evidence_ids": claim["evidence_ids"],
                "evidence_roles": evidence_roles,
                "relationship_evidence_ids": claim["evidence_ids"],
                "entity_resolution_evidence_ids": [],
                "origin_terminal_statuses": ["partner_regulatory_review_approved"],
                "inference_explanations": (
                    claim.get("limitations") or [] if fact_status == "inferred" else []
                ),
                "low_confidence_partner_inclusion": False,
                "entity_resolution_inferred": False,
                "entity_resolution_research_ids": claim.get("upstream_claim_ids") or [],
                "observation_count": max(1, len(claim["evidence_ids"])),
                "independent_source_count": max(1, len(publishers)),
                "quantitative": {
                    "commercial_directness": claim.get("directness") or "unclear",
                    "original_product_scopes": claim.get("original_product_scopes") or [],
                    "product_scope_mappings": claim.get("product_scope_mappings") or [],
                    "quantitative_mentions": claim.get("quantitative_mentions") or [],
                    "evidence_independence_stats": claim.get("evidence_independence_stats") or {},
                    "upstream_confidence_scores": claim.get("upstream_confidence_scores") or [],
                },
                "asserted_by": publishers,
                "counterevidence": [],
                "limitations": sorted(
                    set(
                        (claim.get("limitations") or [])
                        + [
                            "No-hit for another Partner does not prove that no commercial relationship exists.",
                            "The original Partner edge is retained; this commercial role is additive.",
                        ]
                    )
                ),
            }
        )


def validate_source_retrieval_times(snapshot: dict[str, Any]) -> None:
    generated_at = datetime.fromisoformat(
        str(snapshot["meta"]["generated_at"]).replace("Z", "+00:00")
    )
    for row in snapshot["sources"]:
        retrieved_at = datetime.fromisoformat(
            str(row["retrieved_at"]).replace("Z", "+00:00")
        )
        if retrieved_at > generated_at:
            raise ValueError(
                f"source {row['id']} retrieval time exceeds snapshot generation time"
            )


def validate_final_invariants(snapshot: dict[str, Any], valid_product_scope_ids: set[str]) -> None:
    entity_ids = [row["id"] for row in snapshot["entities"]]
    source_ids = [row["id"] for row in snapshot["sources"]]
    evidence_ids = [row["id"] for row in snapshot["evidence"]]
    relationship_ids = [row["id"] for row in snapshot["relationships"]]
    for label, values in (
        ("entity", entity_ids),
        ("source", source_ids),
        ("evidence", evidence_ids),
        ("relationship", relationship_ids),
    ):
        if len(values) != len(set(values)):
            raise ValueError(f"duplicate {label} id in v2 snapshot")
    entity_id_set = set(entity_ids)
    source_id_set = set(source_ids)
    evidence_id_set = set(evidence_ids)
    validate_source_retrieval_times(snapshot)
    security_owner: dict[tuple[str, str], str] = {}
    for entity in snapshot["entities"]:
        securities = entity.get("securities") or []
        if entity.get("listing_status") == "listed" and not securities:
            raise ValueError(f"listed entity has no security: {entity['id']}")
        expected_regions: list[str] = []
        ordered = sorted(
            enumerate(securities),
            key=lambda pair: (not bool(pair[1].get("primary")), pair[0]),
        )
        for _, security in ordered:
            security_key = (
                str(security["exchange"]).casefold(),
                str(security["ticker"]).casefold(),
            )
            previous_owner = security_owner.get(security_key)
            if previous_owner and previous_owner != entity["id"]:
                raise ValueError(
                    "same exchange+ticker belongs to multiple entity endpoints: "
                    f"{security_key} -> {previous_owner}, {entity['id']}"
                )
            security_owner[security_key] = entity["id"]
            region, code = listing_region_for_exchange(security["exchange"])
            if security.get("listing_region") != region:
                raise ValueError(
                    f"security {security['exchange']}:{security['ticker']} has invalid listing_region"
                )
            if security.get("listing_region_code") != code:
                raise ValueError(
                    f"security {security['exchange']}:{security['ticker']} has invalid listing_region_code"
                )
            if region not in expected_regions:
                expected_regions.append(region)
        if entity.get("listing_regions") != expected_regions:
            raise ValueError(f"entity {entity['id']} has inconsistent listing_regions")
    for row in snapshot["evidence"]:
        if row["source_id"] not in source_id_set:
            raise ValueError(f"evidence {row['id']} references missing source {row['source_id']}")

    relationships = snapshot["relationships"]
    keys: set[tuple[str, str, str, str, str]] = set()
    allowed_directions = {
        "supplier": {"supplies_to"},
        "customer": {"sells_to", "uses_or_buys_from", "buys_from"},
        "partner": {"partners_with"},
        "investor_or_investee": {"invests_in"},
        "peer": {"competes_with"},
    }
    for row in relationships:
        key = (
            row["source_entity_id"],
            row["target_entity_id"],
            row["direction"],
            row["relation_type"],
            row["product_scope_id"],
        )
        if key in keys:
            raise ValueError(f"duplicate v2 relationship key: {key}")
        keys.add(key)
        for entity_field in ("source_entity_id", "target_entity_id"):
            if row[entity_field] not in entity_id_set:
                raise ValueError(
                    f"relationship {row['id']} references missing entity {row[entity_field]}"
                )
        missing_evidence = sorted(set(row["evidence_ids"]) - evidence_id_set)
        if missing_evidence:
            raise ValueError(
                f"relationship {row['id']} references missing evidence {missing_evidence}"
            )
        if row["product_scope_id"] not in valid_product_scope_ids | {"corporate_general"}:
            raise ValueError(
                f"relationship {row['id']} has unknown product_scope_id {row['product_scope_id']}"
            )
        if row["direction"] not in allowed_directions[row["relation_type"]]:
            raise ValueError(
                f"relationship {row['id']} has incompatible type/direction "
                f"{row['relation_type']}/{row['direction']}"
            )
        if row.get("product_scopes"):
            raise ValueError(f"v2 relationship {row['id']} retains legacy multi-product scopes")
        directness = row.get("commercial_directness", "not_applicable")
        if row["relation_type"] in {"supplier", "customer"}:
            if directness not in {"direct", "indirect", "both", "unclear"}:
                raise ValueError(
                    f"commercial relationship {row['id']} has invalid directness {directness}"
                )
        elif directness != "not_applicable":
            raise ValueError(
                f"non-commercial relationship {row['id']} has directness {directness}"
            )
        if not set(row.get("evidence_roles") or {}).issubset(row["evidence_ids"]):
            raise ValueError(f"relationship {row['id']} has detached evidence_roles")
        if row["relation_type"] in {"supplier", "customer"} and row["fact_status"] == "inferred" and row["confidence_score"] >= 60:
            raise ValueError(f"inferred supplier/customer score must be below 60: {row['id']}")
        if row["fact_status"] == "inferred" and row["confidence_score"] > 69:
            raise ValueError(f"inferred score exceeds 69: {row['id']}")
        if row["fact_status"] == "unknown" and row["confidence_score"] > 39:
            raise ValueError(f"unknown score exceeds 39: {row['id']}")
    investees = [row for row in relationships if row.get("relation_subtype") == "investee"]
    if len(investees) != 7:
        raise ValueError(f"expected exactly 7 latest-13F listed investees, got {len(investees)}")


def merge_same_key_relationships(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge repeated observations without collapsing distinct role/product keys."""
    grouped: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    status_rank = {"unknown": 0, "inferred": 1, "confirmed": 2}
    for row in rows:
        key = (
            row["source_entity_id"],
            row["target_entity_id"],
            row["direction"],
            row["relation_type"],
            row["product_scope_id"],
        )
        if key not in grouped:
            grouped[key] = row
            continue
        current = grouped[key]
        preferred = max(
            (current, row),
            key=lambda item: (status_rank[item["fact_status"]], item["confidence_score"]),
        )
        other = row if preferred is current else current
        merged = dict(preferred)
        for field in (
            "evidence_ids",
            "relationship_evidence_ids",
            "entity_resolution_evidence_ids",
            "origin_terminal_statuses",
            "inference_explanations",
            "entity_resolution_research_ids",
            "channels",
            "asserted_by",
            "counterevidence",
            "limitations",
        ):
            merged[field] = sorted(set((current.get(field) or []) + (row.get(field) or [])))
        role_rank = {"lead_only": 0, "corroborating": 1, "primary": 2}
        evidence_roles = dict(current.get("evidence_roles") or {})
        for evidence_id, role in (row.get("evidence_roles") or {}).items():
            previous = evidence_roles.get(evidence_id)
            if previous is None or role_rank[role] > role_rank[previous]:
                evidence_roles[evidence_id] = role
        merged["evidence_roles"] = evidence_roles
        directness_values = {
            value
            for value in (
                current.get("commercial_directness"),
                row.get("commercial_directness"),
            )
            if value not in {None, "not_applicable", "unclear"}
        }
        if directness_values == {"direct", "indirect"} or "both" in directness_values:
            merged["commercial_directness"] = "both"
        elif directness_values:
            merged["commercial_directness"] = next(iter(directness_values))
        else:
            merged["commercial_directness"] = preferred.get(
                "commercial_directness", "not_applicable"
            )
        merged["entity_resolution_inferred"] = bool(
            current.get("entity_resolution_inferred")
            or row.get("entity_resolution_inferred")
        )
        # A retained needs-more-evidence/unknown Partner hypothesis can collide
        # with a stronger NPN or reviewed Partner edge after exact issuer
        # canonicalization.  The evidence and origin statuses remain attached,
        # but the merged edge is no longer *only* a low-confidence inclusion.
        merged["low_confidence_partner_inclusion"] = bool(
            current.get("low_confidence_partner_inclusion")
            and row.get("low_confidence_partner_inclusion")
        )
        merged["observation_count"] = current.get("observation_count", 1) + row.get("observation_count", 1)
        merged["independent_source_count"] = max(
            current.get("independent_source_count", 1), row.get("independent_source_count", 1)
        )
        quantitative = dict(other.get("quantitative") or {})
        for name, value in (preferred.get("quantitative") or {}).items():
            if isinstance(value, list) and isinstance(quantitative.get(name), list):
                quantitative[name] = sorted(set(quantitative[name] + value))
            else:
                quantitative[name] = value
        merged["quantitative"] = quantitative
        merged["direction_explanation"] = (
            preferred["direction_explanation"]
            + " Repeated same-key observations were merged; see every attached evidence record."
        )
        grouped[key] = merged
    return list(grouped.values())


def apply_entity_merge_map(
    entities: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> None:
    """Rewrite relationship endpoints and union exact duplicate issuer records."""
    mapping = {
        row["original_entity_id"]: row["canonical_entity_id"]
        for row in rows
    }
    mapping.setdefault("nvidia", "nvidia")
    for relationship in relationships:
        relationship["source_entity_id"] = mapping.get(
            relationship["source_entity_id"], relationship["source_entity_id"]
        )
        relationship["target_entity_id"] = mapping.get(
            relationship["target_entity_id"], relationship["target_entity_id"]
        )

    for original_id, canonical_id in sorted(mapping.items()):
        if original_id == canonical_id or original_id not in entities:
            continue
        if canonical_id not in entities:
            raise ValueError(
                f"entity merge map references missing canonical entity {canonical_id}"
            )
        original = entities[original_id]
        canonical = entities[canonical_id]
        canonical["aliases"] = sorted(
            set(
                (canonical.get("aliases") or [])
                + (original.get("aliases") or [])
                + [original.get("legal_name"), original.get("display_name"), original_id]
            )
            - {None}
        )
        securities = {
            (item["exchange"].casefold(), item["ticker"].casefold()): item
            for item in (canonical.get("securities") or [])
            + (original.get("securities") or [])
        }
        canonical["securities"] = list(securities.values())
        canonical["notes"] = "; ".join(
            item
            for item in (
                canonical.get("notes"),
                original.get("notes"),
                f"Exact duplicate issuer endpoint merged from {original_id}.",
            )
            if item
        )
        del entities[original_id]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=Path("runs/2026-08-25-run-003"))
    parser.add_argument("--output", type=Path, default=Path("data/snapshot_2026-08-25.json"))
    parser.add_argument(
        "--coverage-output",
        type=Path,
        help="closure-summary JSON path (defaults beside --output)",
    )
    parser.add_argument(
        "--entity-registry-overlay",
        type=Path,
        action="append",
        default=[],
        help="additional evidence-backed listed-entity registry JSONL",
    )
    parser.add_argument(
        "--entity-merge-map",
        type=Path,
        help="reviewed exact issuer merge map JSONL applied before relationship dedup",
    )
    parser.add_argument("--skip-gates", action="store_true", help="development only; final CI must not use this")
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    if not args.skip_gates:
        terminal_gate_checks(run_root)

    entities: dict[str, dict[str, Any]] = {}
    registry_paths = [
        run_root / "agents/entity_resolution_complete/entity_registry.jsonl",
        run_root / "agents/global_listing_overlay/entity_registry_overlay.jsonl",
        *(path.resolve() for path in args.entity_registry_overlay),
    ]
    for registry_path in registry_paths:
        for row in read_jsonl(registry_path):
            entity = entity_from_registry(row)
            if entity["listing_status"] == "listed":
                if entity["id"] in entities:
                    current = entities[entity["id"]]
                    entity["aliases"] = sorted(set(current["aliases"] + entity["aliases"]))
                    securities = {
                        (item["exchange"], item["ticker"]): item
                        for item in current["securities"] + entity["securities"]
                    }
                    entity["securities"] = list(securities.values())
                    entity["notes"] = "; ".join(
                        item for item in (current.get("notes"), entity.get("notes")) if item
                    ) or None
                    entity["country"] = entity.get("country") or current.get("country")
                    entity["ultimate_parent_id"] = (
                        entity.get("ultimate_parent_id") or current.get("ultimate_parent_id")
                    )
                entities[entity["id"]] = entity
    entities["nvidia"] = {
        "id": "nvidia",
        "legal_name": "NVIDIA Corporation",
        "display_name": "NVIDIA",
        "aliases": ["NVDA", "NVIDIA Corp."],
        "country": "United States",
        "listing_status": "listed",
        "securities": [{"ticker": "NVDA", "exchange": "Nasdaq", "cik": "0001045810", "cusip": "67066G104", "security_type": "common_equity"}],
        "ultimate_parent_id": None,
        "notes": "Research subject; NVIDIA Corporation, not unrelated entities using the same acronym.",
    }

    claims = read_jsonl(run_root / "agents" / "relationship_review_complete" / "claims.jsonl")
    fingerprints = read_jsonl(run_root / "agents" / "relationship_review_complete" / "evidence_fingerprints.jsonl")
    evidence_rows = {item["evidence_id"]: item for item in fingerprints}
    evidence_to_claims: dict[str, list[str]] = defaultdict(list)
    for claim in claims:
        for evidence_id in claim["evidence_ids"]:
            evidence_to_claims[evidence_id].append(claim["claim_id"])
        for entity_id in (claim["subject_entity_id"], claim["object_entity_id"]):
            if entity_id not in entities:
                embedded = claim.get("subject_entity") if entity_id == claim["subject_entity_id"] else claim.get("object_entity")
                if not embedded:
                    raise ValueError(f"claim {claim['claim_id']} references missing entity {entity_id}")
                identifiers = embedded.get("security_identifiers") or []
                securities = []
                for identifier in identifiers:
                    exchange, ticker = identifier.split(":", 1)
                    securities.append({"ticker": ticker, "exchange": exchange, "security_type": "common_equity"})
                entities[entity_id] = {
                    "id": entity_id,
                    "legal_name": embedded["legal_name"],
                    "display_name": embedded["legal_name"],
                    "aliases": [],
                    "country": None,
                    "listing_status": "listed",
                    "securities": securities,
                    "ultimate_parent_id": None,
                    "notes": "Added from terminal reviewed claim with exact security identifier.",
                }

    sources: dict[str, dict[str, Any]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    add_relation_evidence(fingerprints, evidence_to_claims, sources, evidence)
    relationships = [relation_from_claim(item, evidence_rows) for item in claims]
    add_peer_data(run_root, entities, sources, evidence, relationships)
    add_npn_data(run_root, entities, sources, evidence, relationships)
    add_partner_regulatory_data(run_root, entities, sources, evidence, relationships)
    if args.entity_merge_map:
        apply_entity_merge_map(
            entities,
            relationships,
            read_jsonl(args.entity_merge_map.resolve()),
        )
    relationships = merge_same_key_relationships(relationships)
    relationship_entity_ids = {
        entity_id
        for relationship in relationships
        for entity_id in (
            relationship["source_entity_id"],
            relationship["target_entity_id"],
        )
    }
    entities = {
        entity_id: entity
        for entity_id, entity in entities.items()
        if entity_id in relationship_entity_ids
    }
    annotate_listing_regions(entities)

    generated_at = BUILD_STARTED_AT.isoformat()
    snapshot = {
        "meta": {
            "subject_entity_id": "nvidia",
            "cutoff_at": "2026-08-25T23:59:59+08:00",
            "evidence_start_date": "2025-01-01",
            "snapshot_version": "2026-08-25.v2",
            "generated_at": generated_at,
            "disclaimer": "This research snapshot is for interview demonstration and informational purposes only. It is not investment advice or a recommendation.",
            "coverage": [
                "NVIDIA Corporation and listed-company supplier, customer, partner, latest-13F investee and top-level product-category peer relationships",
                "complete frozen NVIDIA product/solution tree v2",
                "all NVIDIA Newsroom and NVIDIA Blog items from 2025-01-01 through the 2026-08-25 cutoff, each with a terminal processing state",
                "all 997 final-runtime NVIDIA Partner Network listings, with raw regional records, reconciled 996-to-997 intraday drift, and reviewed group-level deduplication",
                "confirmed facts, reasonable inferences and unknown observations with direction, time, evidence and explainable 0-100 confidence",
                "reverse-direction regulatory review of every canonical listed Partner, retaining direct, indirect, both or unclear commercial-path labels",
            ],
            "exclusions": [
                "Institutional managers holding NVIDIA shares",
                "Private-company endpoints from the primary listed-company graph",
                "Restricted, paywalled, logged-in, CAPTCHA-protected or access-controlled material",
                "NVIDIA's own 10-Q, 8-K and complete investor-relations archive; counterparty filings of those form types are used only for Partner reverse verification",
                "An assertion that NPN membership proves supplier/customer direction or that Form 13F represents every NVIDIA investment",
            ],
        },
        "entities": sorted(entities.values(), key=lambda item: item["id"]),
        "sources": sorted(sources.values(), key=lambda item: item["id"]),
        "evidence": sorted(evidence.values(), key=lambda item: item["id"]),
        "relationships": sorted(relationships, key=lambda item: item["id"]),
    }
    product_scope_ids = {
        row["canonical_key"]
        for row in read_jsonl(run_root / "product_tree_v2" / "canonical_index_v2.jsonl")
    }
    validate_final_invariants(snapshot, product_scope_ids)
    validated = Snapshot.model_validate(snapshot)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(validated.model_dump_json(indent=2) + "\n", encoding="utf-8")
    coverage_output = args.coverage_output or args.output.with_name(
        "coverage_frontier_2026-08-25.json"
    )
    coverage_output.parent.mkdir(parents=True, exist_ok=True)
    coverage_output.write_text(
        json.dumps(build_coverage_frontier(run_root), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "snapshot": str(args.output),
        "coverage_frontier": str(coverage_output),
        "entities": len(snapshot["entities"]),
        "sources": len(snapshot["sources"]),
        "evidence": len(snapshot["evidence"]),
        "relationships": len(snapshot["relationships"]),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
