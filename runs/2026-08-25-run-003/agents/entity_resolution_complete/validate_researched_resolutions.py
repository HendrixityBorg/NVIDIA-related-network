#!/usr/bin/env python3
"""Fail-closed completeness validator for researched issuer-parent decisions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from listed_company_network.research_policy import (
    ResearchedEntityResolution,
    missing_researched_candidate_ids,
)


HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]


def rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidate-review",
        type=Path,
        default=HERE / "candidate_review.jsonl",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=HERE / "researched_resolution_ledger.jsonl",
    )
    parser.add_argument(
        "--global-overlay",
        type=Path,
        default=RUN / "agents" / "global_listing_overlay",
    )
    parser.add_argument(
        "--print-schema",
        action="store_true",
        help="print the researched-resolution JSON Schema and exit",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=HERE / "researched_resolution_validation_report.json",
        help="write the release-gate report after validation",
    )
    args = parser.parse_args()
    if args.print_schema:
        print(
            json.dumps(
                ResearchedEntityResolution.model_json_schema(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if not args.ledger.is_file():
        raise SystemExit(f"researched resolution ledger is missing: {args.ledger}")

    candidates = rows(args.candidate_review)
    researched = [
        ResearchedEntityResolution.model_validate(row) for row in rows(args.ledger)
    ]
    base_entity_ids = {
        row["entity_id"] for row in rows(HERE / "entity_registry.jsonl")
    }
    overlay_entity_ids = {
        (
            row.get("merge_target_entity_id")
            if row.get("merge_action") == "augment_existing"
            else row.get("entity_id")
        )
        for row in rows(args.global_overlay / "entity_registry_overlay.jsonl")
        if row.get("listing_status") == "listed_confirmed"
    }
    known_entity_ids = base_entity_ids | overlay_entity_ids
    selected_unknown = sorted(
        {
            row.selected_entity_id
            for row in researched
            if row.selected_entity_id and row.selected_entity_id not in known_entity_ids
        }
    )
    missing = missing_researched_candidate_ids(candidates, researched)
    duplicate_resolution_ids = len(researched) != len(
        {row.resolution_id for row in researched}
    )
    result = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "pass": not missing and not selected_unknown and not duplicate_resolution_ids,
        "candidate_rows": len(candidates),
        "researched_terminal_rows": len(researched),
        "missing_researched_candidate_ids": missing,
        "selected_unknown_entity_ids": selected_unknown,
        "duplicate_resolution_ids": duplicate_resolution_ids,
        "terminal_category_counts": {
            category: sum(row.terminal_category.value == category for row in researched)
            for category in sorted({row.terminal_category.value for row in researched})
        },
        "inferred_resolution_rows": sum(
            row.inferred_entity_resolution for row in researched
        ),
    }
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
