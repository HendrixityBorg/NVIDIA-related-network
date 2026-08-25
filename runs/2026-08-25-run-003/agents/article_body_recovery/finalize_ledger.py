#!/usr/bin/env python3
"""Add portable provenance fields and rebuild aggregates without network I/O."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


root = Path(sys.argv[1]).resolve()
run_root = Path(sys.argv[2]).resolve()
manifest = [row for row in read_jsonl(run_root / "news" / "official_articles.jsonl") if row["article_type"] == "blog"]
manifest.sort(key=lambda row: (row["published_date"], row["article_id"]))
families = {
    "direct": "nvidia_blog_canonical",
    "rss": "nvidia_official_feedburner_rss",
    "wayback": "internet_archive_wayback_replay",
    "blocked": "internet_archive_wayback_availability_audit",
}
processing_rows, access_rows, mention_rows, observation_rows = [], [], [], []
for article in manifest:
    path = root / "partials" / f"{article['article_id']}.json"
    partial = json.loads(path.read_text(encoding="utf-8"))
    processing = partial["processing"]
    access = partial["access"]
    method = processing["recovery_method"]
    source_family = families[method]
    audit_sha = digest(access)
    locator = (
        "body.block[N] in deterministic entry-content parse"
        if method != "blocked"
        else "access_audit.availability_attempts[*] (exact canonical path and trailing-slash equivalent)"
    )
    processing.update({
        "source_family": source_family,
        "evidence_locator": locator,
        "access_audit_sha256": audit_sha,
        "content_or_audit_sha256": processing.get("body_sha256") or audit_sha,
    })
    access.update({
        "source_family": source_family,
        "evidence_locator": locator,
        "audit_record_sha256": audit_sha,
        "access_constraints": processing["access_constraints"],
    })
    for row in partial["mentions"]:
        row["source_family"] = source_family
    for row in partial["observations"]:
        row["source_family"] = source_family
    partial = {
        "processing": processing,
        "mentions": partial["mentions"],
        "observations": partial["observations"],
        "access": access,
    }
    path.write_text(json.dumps(partial, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    processing_rows.append(processing)
    access_rows.append(access)
    mention_rows.extend(partial["mentions"])
    observation_rows.extend(partial["observations"])

write_jsonl(root / "article_processing.jsonl", processing_rows)
write_jsonl(root / "access_audit.jsonl", access_rows)
write_jsonl(root / "entity_mentions.jsonl", mention_rows)
write_jsonl(root / "observations.jsonl", observation_rows)
print(json.dumps({
    "ledger_rows": len(processing_rows),
    "access_rows": len(access_rows),
    "mentions": len(mention_rows),
    "observations": len(observation_rows),
    "rows_with_source_family_locator_hash_constraints": sum(
        bool(row.get("source_family") and row.get("evidence_locator") and row.get("content_or_audit_sha256") and row.get("access_constraints"))
        for row in processing_rows
    ),
}, sort_keys=True))
