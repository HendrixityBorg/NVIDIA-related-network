#!/usr/bin/env python3
"""Validate ledger closure, frozen snapshots and fallback coverage."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE.parents[1] / "news" / "official_articles.jsonl"
FINAL = {"processed_with_candidates", "processed_no_candidate", "access_blocked", "excluded_with_reason"}


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (HERE / name).open(encoding="utf-8") if line.strip()]


def main() -> int:
    manifest = [row for row in [json.loads(line) for line in MANIFEST.open(encoding="utf-8") if line.strip()] if "2026-01-01" <= row["published_date"] <= "2026-08-25"]
    ledger = rows("article_processing.jsonl")
    fetches = rows("fetch_manifest.jsonl")
    fallback = rows("index_fallback_processing.jsonl")
    candidates = rows("observations.jsonl")
    expected = {row["article_id"] for row in manifest}
    blocked = {row["article_id"] for row in ledger if row["processing_status"] == "access_blocked"}
    snapshot_errors = []
    for row in fetches:
        if row.get("fetch_status") != "success":
            continue
        path = HERE / row["snapshot_path"]
        if not path.exists():
            snapshot_errors.append(f"missing:{row['article_id']}")
            continue
        with gzip.open(path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        if digest != row["sha256"]:
            snapshot_errors.append(f"sha256:{row['article_id']}")
    checks = {
        "manifest_count_283": len(manifest) == 283,
        "ledger_exact_manifest": len(ledger) == len(expected) and {row["article_id"] for row in ledger} == expected,
        "fetch_exact_manifest": len(fetches) == len(expected) and {row["article_id"] for row in fetches} == expected,
        "article_ids_unique": len({row["article_id"] for row in ledger}) == len(ledger),
        "urls_unique": len({row["canonical_url"] for row in ledger}) == len(ledger),
        "all_terminal": all(row["processing_status"] in FINAL for row in ledger),
        "fallback_exact_blocked": len(fallback) == len(blocked) and {row["article_id"] for row in fallback} == blocked,
        "snapshot_hashes_valid": not snapshot_errors,
        "all_candidates_listed": all(row.get("listing_identity_status") == "confirmed" and row.get("security_identifiers") for row in candidates),
        "all_candidates_traceable": all(row.get("article_id") and row.get("source_url") and row.get("evidence_locator") and row.get("product_mapping_status") for row in candidates),
    }
    body_complete = not blocked and all(row.get("fetch_status") == "success" for row in fetches)
    result = {
        "ledger_closure_pass": all(checks.values()),
        "body_coverage_complete": body_complete,
        "overall_pass": all(checks.values()) and body_complete,
        "counts": {"manifest": len(manifest), "ledger": len(ledger), "fetch": len(fetches), "blocked": len(blocked), "fallback_scans": len(fallback), "listed_candidates": len(candidates)},
        "checks": checks,
        "snapshot_errors": snapshot_errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ledger_closure_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
