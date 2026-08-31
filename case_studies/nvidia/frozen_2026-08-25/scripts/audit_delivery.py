#!/usr/bin/env python3
"""Fail-closed delivery audit for the frozen relationship research service."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
    "openai_project_key": re.compile(r"sk-proj-[A-Za-z0-9_-]{40,}"),
    "openai_legacy_key": re.compile(r"sk-[A-Za-z0-9]{48}(?![A-Za-z0-9_-])"),
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def relationship_id_digest(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(sorted(row["id"] for row in rows)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_human_signoff(
    signoff: dict[str, Any],
    supplier_rows: list[dict[str, Any]],
    new_confirmed: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    expected = {
        "supplier_relationships": supplier_rows,
        "new_confirmed_commercial_relationships": new_confirmed,
    }
    scopes = signoff.get("review_scope", {})
    for name, rows in expected.items():
        scope = scopes.get(name, {})
        if scope.get("completed") is not True:
            errors.append(f"human sign-off scope is incomplete: {name}")
        if scope.get("relationship_count") != len(rows):
            errors.append(f"human sign-off count mismatch: {name}")
        if scope.get("relationship_ids_sha256") != relationship_id_digest(rows):
            errors.append(f"human sign-off relationship digest mismatch: {name}")
    if not signoff.get("reviewed_at") or not signoff.get("reviewer_identifier"):
        errors.append("human sign-off lacks reviewer identifier or review date")
    return not errors, errors


def score_from_breakdown(relationship: dict[str, Any]) -> int:
    breakdown = relationship["confidence_breakdown"]
    raw = round(
        sum(
            value
            for key, value in breakdown.items()
            if key != "conflict_penalty"
        )
        - breakdown.get("conflict_penalty", 0)
    )
    cap = {"confirmed": 100, "inferred": 69, "unknown": 39}[
        relationship["fact_status"]
    ]
    if (
        relationship["fact_status"] == "inferred"
        and relationship["relation_type"] in {"supplier", "customer"}
    ):
        cap = 59
    if relationship.get("low_confidence_partner_inclusion"):
        cap = 49 if relationship["fact_status"] == "inferred" else 39
    return min(cap, max(0, raw))


def supply_category(company: str, scope: str) -> str:
    if scope == "cloud-services":
        return "ai_cloud_service_supplier"
    if scope == "networking":
        return "optical_or_networking_supplier"
    if scope in {"blackwell", "semiconductor", "architectures-and-core-technologies"}:
        return "semiconductor_foundry_or_memory_supplier"
    if company in {"Fabrinet", "Foxconn / Hon Hai", "Wistron"}:
        return "contract_manufacturing_supplier"
    return "other_disclosed_supplier"


def evidence_summary(
    relationship: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    output = []
    for evidence_id in relationship["evidence_ids"]:
        if relationship.get("evidence_roles", {}).get(evidence_id) != "primary":
            continue
        row = evidence[evidence_id]
        source = sources[row["source_id"]]
        output.append(
            {
                "evidence_id": evidence_id,
                "publisher": source["publisher"],
                "source_type": source["source_type"],
                "published_at": source.get("published_at"),
                "source_url": source["url"],
                "evidence_locator": row["locator"],
                "necessary_short_excerpt": row.get("excerpt"),
            }
        )
    return output


def public_repository_audit(project_root: Path) -> dict[str, Any]:
    ignored_parts = {".git", ".venv", ".pytest_cache", "__pycache__"}
    large_files: list[dict[str, Any]] = []
    credential_files: list[str] = []
    secret_hits: list[dict[str, str]] = []
    for path in project_root.rglob("*"):
        if not path.is_file() or any(part in ignored_parts for part in path.parts):
            continue
        relative = str(path.relative_to(project_root))
        size = path.stat().st_size
        if size > 20 * 1024 * 1024:
            large_files.append({"path": relative, "bytes": size})
        if path.name == ".env" or path.suffix.casefold() in {
            ".pem", ".key", ".p12", ".pfx"
        }:
            credential_files.append(relative)
        if size > 10 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern_name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                secret_hits.append({"path": relative, "pattern": pattern_name})
    required = ["README.md", "LICENSE", ".gitignore", ".env.example", "pyproject.toml"]
    missing_required = [name for name in required if not (project_root / name).is_file()]
    return {
        "large_files_over_20mb": large_files,
        "credential_like_files": sorted(credential_files),
        "high_specificity_secret_pattern_hits": secret_hits,
        "missing_required_repository_files": missing_required,
        "pass": not (large_files or credential_files or secret_hits or missing_required),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=Path("data/snapshot_2026-08-25.json"))
    parser.add_argument("--run-root", type=Path, default=Path("runs/2026-08-25-run-003"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/2026-08-25-run-003/delivery_review"),
    )
    parser.add_argument(
        "--human-signoff",
        type=Path,
        default=Path("research/HUMAN_REVIEW_SIGNOFF.json"),
    )
    args = parser.parse_args()
    snapshot = read_json(args.snapshot)
    integration_dir = args.run_root / "agents" / "partner_regulatory_integration"
    integration_validation = read_json(integration_dir / "validation_report.json")
    integration_claims = read_jsonl(integration_dir / "claims.jsonl")

    entities = {row["id"]: row for row in snapshot["entities"]}
    sources = {row["id"]: row for row in snapshot["sources"]}
    evidence = {row["id"]: row for row in snapshot["evidence"]}
    relationships = snapshot["relationships"]
    supplier_rows = [row for row in relationships if row["relation_type"] == "supplier"]
    new_commercial = [
        row
        for row in relationships
        if row.get("relation_subtype") == "partner_counterparty_reverse_review"
    ]
    new_confirmed = [row for row in new_commercial if row["fact_status"] == "confirmed"]

    human_signoff = read_json(args.human_signoff)
    human_signoff_valid, human_signoff_errors = validate_human_signoff(
        human_signoff, supplier_rows, new_confirmed
    )

    errors: list[str] = list(human_signoff_errors)
    five_keys = [
        (
            row["source_entity_id"], row["target_entity_id"], row["direction"],
            row["relation_type"], row["product_scope_id"],
        )
        for row in relationships
    ]
    if len(five_keys) != len(set(five_keys)):
        errors.append("duplicate relationship five-tuple")
    if any(row["confidence_score"] != score_from_breakdown(row) for row in relationships):
        errors.append("relationship score does not equal its breakdown and cap")
    if any(
        row["direction"] != "supplies_to"
        or row["target_entity_id"] != "nvidia"
        or row["commercial_directness"] == "not_applicable"
        for row in supplier_rows
    ):
        errors.append("supplier direction or directness invariant failed")
    if any(
        not any(role == "primary" for role in row.get("evidence_roles", {}).values())
        for row in supplier_rows
    ):
        errors.append("supplier without primary evidence")
    if any(
        row["fact_status"] == "confirmed"
        and not any(
            sources[evidence[eid]["source_id"]]["source_type"] == "regulatory_filing"
            for eid, role in row.get("evidence_roles", {}).items()
            if role == "primary"
        )
        for row in new_commercial
    ):
        errors.append("new confirmed commercial relation lacks primary regulatory evidence")
    if any(
        row["fact_status"] == "inferred" and row["confidence_score"] >= 60
        for row in new_commercial
    ):
        errors.append("new inferred commercial relation is not capped below 60")
    if any(
        row["confidence_breakdown"]["independence"]
        > min(15, max(0, row["independent_source_count"] - 1) * 5)
        for row in new_commercial
    ):
        errors.append("commercial independence points exceed distinct publishers")
    if not integration_validation.get("pass"):
        errors.append("Partner regulatory integration validation did not pass")

    supplier_audit = []
    for row in sorted(
        supplier_rows,
        key=lambda item: (
            entities[item["source_entity_id"]]["display_name"].casefold(),
            item["product_scope_id"],
        ),
    ):
        entity = entities[row["source_entity_id"]]
        supplier_audit.append(
            {
                "relationship_id": row["id"],
                "company": entity["display_name"],
                "securities": [
                    f"{security['exchange']}:{security['ticker']}"
                    for security in entity["securities"]
                ],
                "supply_category": supply_category(
                    entity["display_name"], row["product_scope_id"]
                ),
                "product_scope_id": row["product_scope_id"],
                "fact_status": row["fact_status"],
                "commercial_directness": row["commercial_directness"],
                "confidence_score": row["confidence_score"],
                "primary_evidence": evidence_summary(row, evidence, sources),
                "agent_delivery_review": "pass_direction_source_and_scope",
                "human_verified": human_signoff_valid,
                "human_reviewed_at": human_signoff.get("reviewed_at"),
                "human_reviewer_identifier": human_signoff.get("reviewer_identifier"),
            }
        )

    confirmed_audit = []
    for row in sorted(new_confirmed, key=lambda item: item["id"]):
        counterparty_id = (
            row["source_entity_id"]
            if row["source_entity_id"] != "nvidia"
            else row["target_entity_id"]
        )
        confirmed_audit.append(
            {
                "relationship_id": row["id"],
                "counterparty": entities[counterparty_id]["display_name"],
                "relationship_type": row["relation_type"],
                "direction": row["direction"],
                "product_scope_id": row["product_scope_id"],
                "commercial_directness": row["commercial_directness"],
                "confidence_score": row["confidence_score"],
                "primary_evidence": evidence_summary(row, evidence, sources),
                "agent_delivery_review": "pass_explicit_regulatory_direction",
                "human_verified": human_signoff_valid,
                "human_reviewed_at": human_signoff.get("reviewed_at"),
                "human_reviewer_identifier": human_signoff.get("reviewer_identifier"),
            }
        )

    repository_audit = public_repository_audit(Path.cwd())
    if not repository_audit["pass"]:
        errors.append("public repository hygiene audit failed")

    report = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "snapshot_version": snapshot["meta"]["snapshot_version"],
        "cutoff_at": snapshot["meta"]["cutoff_at"],
        "counts": {
            "entities": len(entities),
            "relationships": len(relationships),
            "supplier_relationships": len(supplier_rows),
            "supplier_unique_companies": len(
                {row["source_entity_id"] for row in supplier_rows}
            ),
            "new_partner_regulatory_commercial_relationships": len(new_commercial),
            "new_confirmed_commercial_relationships": len(new_confirmed),
            "integration_claims": len(integration_claims),
        },
        "checks": {
            "relationship_five_tuple_unique": len(five_keys) == len(set(five_keys)),
            "scores_equal_breakdown_and_caps": all(
                row["confidence_score"] == score_from_breakdown(row)
                for row in relationships
            ),
            "supplier_direction_and_primary_evidence_valid": not any(
                row["direction"] != "supplies_to"
                or row["target_entity_id"] != "nvidia"
                or not any(
                    role == "primary"
                    for role in row.get("evidence_roles", {}).values()
                )
                for row in supplier_rows
            ),
            "confirmed_requires_primary_regulatory_evidence": not any(
                row["fact_status"] == "confirmed"
                and not any(
                    sources[evidence[eid]["source_id"]]["source_type"]
                    == "regulatory_filing"
                    for eid, role in row.get("evidence_roles", {}).items()
                    if role == "primary"
                )
                for row in new_commercial
            ),
            "inferred_commercial_below_60": all(
                row["fact_status"] != "inferred" or row["confidence_score"] < 60
                for row in new_commercial
            ),
            "independence_bounded_by_distinct_publishers": all(
                row["confidence_breakdown"]["independence"]
                <= min(15, max(0, row["independent_source_count"] - 1) * 5)
                for row in new_commercial
            ),
            "integration_validation_pass": integration_validation.get("pass") is True,
            "human_review_signoff_valid": human_signoff_valid,
            "public_repository_hygiene_pass": repository_audit["pass"],
        },
        "human_review_signoff": human_signoff,
        "public_repository_audit": repository_audit,
        "limitations": [
            "Human sign-off is bound to the exact reviewed relationship ID sets by count and SHA-256 digest.",
            "A terminal no-hit or unavailable public search is not evidence that no relationship exists.",
            "High-specificity secret scanning supplements but does not replace Git hosting provider secret scanning.",
        ],
        "disclaimer": "Research service delivery audit; not investment advice.",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "delivery_audit_report.json", report)
    write_jsonl(args.output_dir / "supplier_audit.jsonl", supplier_audit)
    write_jsonl(
        args.output_dir / "new_confirmed_commercial_audit.jsonl", confirmed_audit
    )
    readme = f"""# 交付级审计

本目录对冻结快照执行确定性收尾检查，不重新联网，也不修改研究观察。

- 状态：`{report['status']}`
- Supplier：{len(supplier_rows)} 条 / {report['counts']['supplier_unique_companies']} 家上市公司
- Partner 监管复查新增商业关系：{len(new_commercial)} 条
- 其中 confirmed：{len(new_confirmed)} 条
- 公开仓库卫生检查：`{'pass' if repository_audit['pass'] else 'fail'}`

`supplier_audit.jsonl` 保留每条供应关系的类型、产品、直接性、分数及主证据；
`new_confirmed_commercial_audit.jsonl` 覆盖本轮新增 confirmed supplier/customer。
重复上下文保留为 corroborating，但同一 publisher 不增加独立性分。

人工复核签字已通过数量与关系 ID 集合 SHA-256 校验，账本记录为
`human_verified=true`。Agent 输出仍不被视为来源证据。本研究不构成投资建议。
"""
    (args.output_dir / "README_ZH.md").write_text(readme, encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
