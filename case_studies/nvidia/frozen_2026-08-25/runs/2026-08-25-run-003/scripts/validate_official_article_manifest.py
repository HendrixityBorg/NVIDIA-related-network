#!/usr/bin/env python3
"""Validate the frozen official NVIDIA article enumeration."""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEWS = ROOT / "news"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    articles = load_jsonl(NEWS / "official_articles.jsonl")
    pages = load_jsonl(NEWS / "archive_pages.jsonl")
    summary = json.loads((NEWS / "manifest_summary.json").read_text(encoding="utf-8"))
    errors: list[str] = []

    ids = [row["article_id"] for row in articles]
    urls = [row["canonical_url"] for row in articles]
    if len(ids) != len(set(ids)):
        errors.append("duplicate article_id")
    if len(urls) != len(set(urls)):
        errors.append("duplicate canonical_url")
    if any(not date(2025, 1, 1) <= date.fromisoformat(r["published_date"]) <= date(2026, 8, 25) for r in articles):
        errors.append("article outside research date range")
    if any(r["article_type"] not in {"blog", "press_release"} for r in articles):
        errors.append("unknown article type")
    if len(pages) != 78 or len({(r["year"], r["page"]) for r in pages}) != len(pages):
        errors.append("archive page closure mismatch")
    if any(r["item_count"] <= 0 for r in pages):
        errors.append("zero-item archive page")

    for row in pages:
        snapshot = NEWS / row["snapshot_path"]
        if not snapshot.exists():
            errors.append(f"missing snapshot: {snapshot.name}")
            continue
        with gzip.open(snapshot, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        if digest != row["sha256"]:
            errors.append(f"snapshot hash mismatch: {snapshot.name}")

    type_counts = Counter(r["article_type"] for r in articles)
    checks = {
        "articles_match_summary": len(articles) == summary["included_articles"],
        "page_items_match_raw_observations": sum(r["item_count"] for r in pages) == summary["raw_archive_observations"],
        "blog_count_matches_summary": type_counts["blog"] == summary["nvidia_blog_articles"],
        "press_release_count_matches_summary": type_counts["press_release"] == summary["newsroom_press_releases"],
        "no_unknown_type": summary["unknown_type_articles"] == 0,
        "no_page_errors": not errors,
    }
    errors.extend(name for name, passed in checks.items() if not passed and name != "no_page_errors")
    report = {
        "status": "pass" if not errors else "fail",
        "counts": {
            "archive_pages": len(pages),
            "raw_archive_observations": sum(r["item_count"] for r in pages),
            "canonical_articles": len(articles),
            "blog": type_counts["blog"],
            "press_release": type_counts["press_release"],
        },
        "checks": checks,
        "errors": errors,
        "downstream_body_recovery": {
            "validation_report": "runs/2026-08-25-run-003/agents/article_body_recovery/validation_report.json",
            "status": "tracked by the separate fail-closed article recovery gate",
        },
    }
    (NEWS / "enumeration_validation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
