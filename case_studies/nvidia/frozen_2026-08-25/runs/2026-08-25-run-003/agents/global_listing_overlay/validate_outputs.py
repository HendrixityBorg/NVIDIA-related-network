#!/usr/bin/env python3
"""Validate referential integrity and high-risk disambiguation gates."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["entity_registry_overlay.jsonl", "aliases.jsonl", "listing_evidence.jsonl", "decision_ledger.jsonl"]


def load(name: str) -> list[dict]:
    rows = []
    for no, line in enumerate((HERE / name).open(), 1):
        try:
            rows.append(json.loads(line))
        except Exception as exc:
            raise AssertionError(f"{name}:{no}: invalid JSON: {exc}") from exc
    return rows


entities, aliases, evidence, decisions = [load(name) for name in FILES]
errors: list[str] = []
warnings: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def unique(rows: list[dict], key: str, label: str) -> None:
    vals = [r[key] for r in rows]
    check(len(vals) == len(set(vals)), f"duplicate {label}")


unique(entities, "entity_id", "entity_id")
unique(aliases, "alias_id", "alias_id")
unique(evidence, "listing_evidence_id", "listing_evidence_id")
unique(decisions, "decision_id", "decision_id")

entity_ids = {e["entity_id"] for e in entities} | {"alphabet", "microsoft", "entity_7f4992b527dcdcb3", "synopsys"}
evidence_ids = {e["listing_evidence_id"] for e in evidence}

for row in entities:
    check(row["status_as_of"] == "2026-08-25", f"wrong cutoff: {row['entity_id']}")
    check(set(row["listing_evidence_ids"]) <= evidence_ids, f"missing entity evidence: {row['entity_id']}")
    if row["listing_status"] == "listed_confirmed":
        check(bool(row["securities"]), f"active issuer lacks securities: {row['entity_id']}")
        check(any(s["status_at_cutoff"] == "active_at_cutoff" for s in row["securities"]), f"active issuer lacks active security: {row['entity_id']}")

for row in aliases:
    if row["entity_id"] is not None:
        check(row["entity_id"] in entity_ids, f"alias target missing: {row['alias']}")
    check(set(row["listing_evidence_ids"]) <= evidence_ids, f"alias evidence missing: {row['alias']}")
    check(row["fuzzy_matching_allowed"] is False, f"fuzzy matching enabled: {row['alias']}")

safe_norms = [a["normalized_alias"] for a in aliases if a["alias_status"] == "safe_exact"]
check(len(safe_norms) == len(set(safe_norms)), "duplicate safe normalized alias")

alias_by_name = {a["alias"]: a for a in aliases}
check(alias_by_name["Geely"]["alias_status"] == "ambiguous_not_promoted", "bare Geely was promoted")
check(alias_by_name["Samsung"]["alias_status"] == "ambiguous_not_promoted", "bare Samsung was promoted")
check(alias_by_name["Volvo"]["alias_status"] == "ambiguous_not_promoted", "bare Volvo was promoted")
check(alias_by_name["AIC"]["alias_status"] == "context_bound" and alias_by_name["AIC"]["match_policy"] == "candidate_id_only", "bare AIC is not context-bound")
check(alias_by_name["Volvo Cars"]["entity_id"] == "volvo_cars", "Volvo Cars mapping wrong")
check(alias_by_name["Foxconn"]["entity_id"] == "hon_hai", "Foxconn mapping wrong")
check(alias_by_name["Google Cloud"]["entity_id"] == "alphabet", "Google Cloud parent mapping wrong")
check(alias_by_name["Azure"]["entity_id"] == "microsoft", "Azure parent mapping wrong")
check(alias_by_name["GitHub"]["entity_id"] == "microsoft", "GitHub parent mapping wrong")
check(alias_by_name["Red Hat"]["entity_id"] == "entity_7f4992b527dcdcb3", "Red Hat parent mapping wrong")
check(alias_by_name["Hitachi Vantara"]["entity_id"] == "entity_43cff1458d4aab47", "Hitachi Vantara parent mapping wrong")

ansys = next(e for e in entities if e["entity_id"] == "ansys_historical")
check(ansys["listing_status"] == "historical_delisted_acquired", "Ansys incorrectly active")
check(all(s["status_at_cutoff"] != "active_at_cutoff" for s in ansys["securities"]), "ANSS security incorrectly active")

required_targets = {
    "Lenovo", "Siemens", "ASUS", "ASUSTeK", "Foxconn", "Hon Hai", "Mercedes-Benz",
    "Pegatron", "GIGABYTE", "Wistron", "Inventec", "NAVER", "Wiwynn", "Schneider Electric",
    "Samsung Electronics", "Fujitsu", "Volvo Cars", "BMW", "Advantech", "MSI", "ASRock",
    "AIC", "MiTAC", "Geely", "Geely Auto", "Nissan", "DENSO", "Dassault Systèmes", "Hexagon",
    "KION", "Computacenter", "BNP Paribas", "Google Cloud", "Azure", "GitHub", "Red Hat",
    "Hitachi Vantara", "Ansys",
}
decision_names = {d["input_name"] for d in decisions}
check(required_targets <= decision_names, f"missing terminal target decisions: {sorted(required_targets - decision_names)}")
for row in decisions:
    check(row["terminal_status"].endswith("terminal") or row["terminal_status"].startswith("resolved_"), f"nonterminal decision: {row['decision_id']}")
    check(row["fuzzy_promotion_used"] is False, f"fuzzy promotion used: {row['decision_id']}")

for row in evidence:
    for field in ["source_url", "publisher", "retrieved_at", "evidence_locator", "access_constraints", "license_or_reuse_notes"]:
        check(bool(row.get(field)), f"evidence missing {field}: {row['listing_evidence_id']}")
    check(row["source_url"].startswith("https://"), f"non-HTTPS source: {row['listing_evidence_id']}")

report = {
    "status": "pass" if not errors else "fail",
    "validated_at": "2026-08-25T16:30:00+08:00",
    "cutoff": "2026-08-25",
    "counts": {
        "entities": len(entities),
        "active_listed_entities": sum(e["listing_status"] == "listed_confirmed" for e in entities),
        "historical_entities": sum(e["listing_status"] != "listed_confirmed" for e in entities),
        "aliases": len(aliases),
        "safe_exact_aliases": sum(a["alias_status"] == "safe_exact" for a in aliases),
        "context_bound_aliases": sum(a["alias_status"] == "context_bound" for a in aliases),
        "ambiguous_aliases": sum(a["alias_status"] == "ambiguous_not_promoted" for a in aliases),
        "evidence_records": len(evidence),
        "decision_records": len(decisions),
        "candidate_decisions_with_observations": sum(bool(d["candidate_review_ids"]) for d in decisions),
    },
    "gates": {
        "json_parse": "pass",
        "referential_integrity": "pass" if not [e for e in errors if "missing" in e] else "fail",
        "no_fuzzy_matching": "pass" if not [e for e in errors if "fuzzy" in e] else "fail",
        "high_risk_disambiguation": "pass" if not [e for e in errors if any(k in e for k in ["Geely", "Samsung", "Volvo", "AIC"])] else "fail",
        "ansys_cutoff_status": "pass" if not [e for e in errors if "Ansys" in e or "ANSS" in e] else "fail",
        "all_required_targets_terminal": "pass" if not [e for e in errors if "target" in e or "nonterminal" in e] else "fail",
    },
    "errors": errors,
    "warnings": warnings,
}
(HERE / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if not errors else 1)
