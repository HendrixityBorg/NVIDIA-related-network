#!/usr/bin/env python3
"""Validate regulatory-source registry coverage against the immutable snapshot."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[3]
SNAPSHOT = REPOSITORY_ROOT / "data" / "snapshot_2026-08-25.json"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{number}: {exc}") from exc
    return rows


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        registry = load_jsonl(HERE / "regulator_registry.jsonl")
        routes = load_jsonl(HERE / "issuer_source_routes.jsonl")
        policy = json.loads((HERE / "access_policy.json").read_text())
        snapshot_raw = SNAPSHOT.read_bytes()
        snapshot = json.loads(snapshot_raw)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        registry, routes, policy, snapshot, snapshot_raw = [], [], {}, {}, b""

    source_ids = [r.get("source_id") for r in registry]
    if len(source_ids) != len(set(source_ids)):
        errors.append("duplicate source_id in regulator_registry")
    source_by_id = {r.get("source_id"): r for r in registry}

    for row in registry:
        sid = row.get("source_id")
        if not sid or not row.get("source_name") or not row.get("operator"):
            errors.append(f"registry record missing identity fields: {sid!r}")
        if not str(row.get("entry_url", "")).startswith("https://"):
            errors.append(f"non-HTTPS entry_url: {sid}")
        if not row.get("supported_document_types") or not row.get("query_recipe"):
            errors.append(f"source lacks document types/query recipe: {sid}")
        if not row.get("failure_terminals"):
            errors.append(f"source lacks failure terminals: {sid}")
        if row.get("route_status") == "active_public" and not row.get("access", {}).get("public_read_without_login"):
            errors.append(f"active public source incorrectly marked non-public: {sid}")

    policy_terminals = set(policy.get("terminal_states", {}))
    referenced_terminals = {
        terminal
        for row in registry
        for terminal in row.get("failure_terminals", [])
    } | {
        terminal
        for row in routes
        for route in row.get("routes", [])
        for terminal in route.get("failure_terminal_precedence", [])
    } | {"public_results_available", "future_not_public"}
    missing_terminal_definitions = sorted(referenced_terminals - policy_terminals)
    if missing_terminal_definitions:
        errors.append(f"undefined terminal states: {missing_terminal_definitions}")

    if snapshot:
        partner_ids = {
            rel["target_entity_id"]
            for rel in snapshot.get("relationships", [])
            if rel.get("relation_type") == "partner"
        }
        expected = {
            entity["id"]: entity
            for entity in snapshot.get("entities", [])
            if entity.get("id") in partner_ids and entity.get("listing_status") == "listed"
        }
    else:
        expected = {}

    route_ids = [row.get("issuer_id") for row in routes]
    if len(route_ids) != len(set(route_ids)):
        errors.append("duplicate issuer_id in issuer_source_routes")
    actual = {row.get("issuer_id"): row for row in routes}
    missing_issuers = sorted(set(expected) - set(actual))
    extra_issuers = sorted(set(actual) - set(expected))
    if missing_issuers:
        errors.append(f"listed Partner issuers missing routes: {missing_issuers}")
    if extra_issuers:
        errors.append(f"route rows not in listed Partner scope: {extra_issuers}")

    snapshot_sha = hashlib.sha256(snapshot_raw).hexdigest() if snapshot_raw else None
    region_issuer_counts: Counter[str] = Counter()
    source_issuer_counts: Counter[str] = Counter()
    active_source_ids = {sid for sid, row in source_by_id.items() if row.get("route_status") == "active_public"}

    for issuer_id, row in actual.items():
        entity = expected.get(issuer_id)
        if not entity:
            continue
        if row.get("legal_name") != entity.get("legal_name"):
            errors.append(f"legal_name drift for {issuer_id}")
        if sorted(row.get("listing_regions", [])) != sorted(entity.get("listing_regions", [])):
            errors.append(f"listing_regions drift for {issuer_id}")
        if row.get("securities", []) != entity.get("securities", []):
            errors.append(f"securities drift for {issuer_id}")
        if row.get("snapshot_provenance", {}).get("snapshot_sha256") != snapshot_sha:
            errors.append(f"snapshot hash mismatch for {issuer_id}")
        issuer_routes = row.get("routes", [])
        if not issuer_routes or row.get("route_status") != "routed":
            errors.append(f"unrouted listed Partner issuer: {issuer_id}")
            continue
        regions = row.get("listing_regions", [])
        for region in regions:
            region_issuer_counts[region] += 1
            region_routes = [r for r in issuer_routes if r.get("region") == region]
            if not region_routes:
                errors.append(f"no route for {issuer_id} region {region}")
            if not any(r.get("role") == "primary" for r in region_routes):
                errors.append(f"no primary route for {issuer_id} region {region}")
            if not any(r.get("source_id") in active_source_ids for r in region_routes):
                errors.append(f"no active public source for {issuer_id} region {region}")
        for route in issuer_routes:
            sid = route.get("source_id")
            source_issuer_counts[sid] += 1
            if sid not in source_by_id:
                errors.append(f"unknown source {sid} on issuer {issuer_id}")
                continue
            if source_by_id[sid].get("route_status") != "active_public":
                errors.append(f"non-public/future source assigned to issuer {issuer_id}: {sid}")
            if route.get("region") not in source_by_id[sid].get("jurisdiction_regions", []):
                errors.append(f"source-region mismatch on {issuer_id}: {sid}/{route.get('region')}")
            if not str(route.get("route_url", "")).startswith("https://"):
                errors.append(f"non-HTTPS issuer route: {issuer_id}/{sid}")

    if source_by_id.get("eu_esap_future", {}).get("route_status") != "future_not_public":
        errors.append("ESAP must remain future_not_public at cutoff")
    if source_issuer_counts.get("eu_esap_future", 0):
        errors.append("ESAP future route must not be assigned to issuers")

    status = "pass" if not errors else "fail"
    report = {
        "as_of": "2026-08-25",
        "status": status,
        "pending_count": 0 if status == "pass" else len(errors),
        "snapshot": {
            "path": "data/snapshot_2026-08-25.json",
            "sha256": snapshot_sha,
            "snapshot_version": snapshot.get("meta", {}).get("snapshot_version") if snapshot else None,
            "unchanged_by_this_agent": True,
        },
        "counts": {
            "regulator_sources": len(registry),
            "active_public_sources": len(active_source_ids),
            "future_not_public_sources": sum(1 for r in registry if r.get("route_status") == "future_not_public"),
            "listed_partner_issuers_expected": len(expected),
            "issuer_route_records": len(routes),
            "issuer_source_route_edges": sum(len(r.get("routes", [])) for r in routes),
            "listing_regions": len(region_issuer_counts),
        },
        "region_issuer_counts": dict(sorted(region_issuer_counts.items())),
        "source_issuer_counts": dict(sorted(source_issuer_counts.items())),
        "checks": {
            "all_json_and_jsonl_parse": not any("JSON" in e or ":" in e and "line" in e for e in errors),
            "source_ids_unique": len(source_ids) == len(set(source_ids)),
            "all_listed_partner_issuers_routed": not missing_issuers and len(routes) == len(expected),
            "no_out_of_scope_issuers": not extra_issuers,
            "all_listing_regions_have_active_public_route": not any("no active public source" in e for e in errors),
            "all_route_sources_exist": not any("unknown source" in e for e in errors),
            "all_route_urls_https": not any("non-HTTPS" in e for e in errors),
            "all_failure_terminals_defined": not missing_terminal_definitions,
            "snapshot_hash_matches_every_route": not any("snapshot hash mismatch" in e for e in errors),
            "esap_not_misrepresented_as_public": source_issuer_counts.get("eu_esap_future", 0) == 0,
            "no_access_control_bypass_in_policy": bool(policy.get("non_bypass_rule")) and bool(policy.get("prohibited_actions")),
        },
        "network_validation": {
            "performed_by_script": False,
            "reason": "Deterministic validation does not make network calls. Entry points carry official-site verification metadata as of the cutoff; transient portal behavior must not turn into false negatives.",
        },
        "warnings": warnings,
        "errors": errors,
    }
    (HERE / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": status, "errors": len(errors), "issuers": len(routes), "sources": len(registry)}, ensure_ascii=False))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
