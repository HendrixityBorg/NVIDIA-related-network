#!/usr/bin/env python3
"""Independent closure checks for NVIDIA Blog body recovery."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = [
        row for row in read_jsonl(args.run_root / "news" / "official_articles.jsonl")
        if row["article_type"] == "blog"
    ]
    ledger = read_jsonl(args.output / "article_processing.jsonl")
    observations = read_jsonl(args.output / "observations.jsonl")
    access = read_jsonl(args.output / "access_audit.jsonl")
    manifest_ids = {row["article_id"] for row in manifest}
    ledger_ids = [row["article_id"] for row in ledger]
    methods = Counter(row.get("recovery_method") for row in ledger)
    covered = methods["direct"] + methods["rss"] + methods["wayback"]
    blocked_ids = {row["article_id"] for row in ledger if row.get("recovery_method") == "blocked"}
    blocked_access = {row["article_id"]: row for row in access if row.get("article_id") in blocked_ids}
    checks = {
        "manifest_has_597_unique_blogs": len(manifest) == len(manifest_ids) == 597,
        "ledger_has_597_unique_rows": len(ledger) == len(set(ledger_ids)) == 597,
        "ledger_exactly_matches_manifest": set(ledger_ids) == manifest_ids,
        "access_audit_has_597_rows": len(access) == 597,
        "all_rows_terminal": all(row.get("recovery_method") in {"direct", "rss", "wayback", "blocked"} for row in ledger),
        "covered_rows_have_body_hash": all(row.get("body_sha256") for row in ledger if row.get("recovery_method") != "blocked"),
        "every_terminal_row_has_source_family_locator_hash_and_constraints": all(
            row.get("source_family") and row.get("evidence_locator") and
            row.get("content_or_audit_sha256") and row.get("access_constraints")
            for row in ledger
        ),
        "blocked_rows_have_complete_access_audit_and_reason": len(blocked_access) == len(blocked_ids) and all(
            row.get("error") and row.get("result") and row.get("recovery_method") == "blocked"
            for row in blocked_access.values()
        ),
        "no_article_investee_claims": not any(row.get("relationship_hint") in {"investee", "investor_or_investee"} for row in observations),
        "no_wayback_or_rss_full_html_retained": not any(
            path.suffix in {".html", ".gz"} for path in args.output.rglob("*")
            if "test_output" not in path.parts
        ),
    }
    report = {
        "pass": all(checks.values()),
        "body_coverage_complete": covered == 597 and methods["blocked"] == 0,
        "checks": checks,
        "counts_by_recovery_method": dict(sorted(methods.items())),
        "body_covered": covered,
        "blocked": methods["blocked"],
        "pending": 0 if checks["ledger_has_597_unique_rows"] and checks["all_rows_terminal"] else 597 - len(ledger),
        "manifest_total": 597,
        "ledger_rows": len(ledger),
        "terminal_rows": sum(row.get("recovery_method") in {"direct", "rss", "wayback", "blocked"} for row in ledger),
        "observations": len(observations),
    }
    (args.output / "independent_validation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
