#!/usr/bin/env python3
"""Independent integrity checks for the NVIDIA product-tree v2 merge artifact."""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_jsonl(name: str) -> list[dict]:
    rows: list[dict] = []
    with (HERE / name).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise AssertionError(f"{name}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def unique(rows: list[dict], field: str, label: str) -> set[str]:
    values = [row[field] for row in rows]
    assert len(values) == len(set(values)), f"duplicate {label}"
    return set(values)


def main() -> None:
    report = json.loads((HERE / "validation_report.json").read_text(encoding="utf-8"))
    supersession = json.loads((HERE / "supersession.json").read_text(encoding="utf-8"))
    sources = load_jsonl("source_frontier.jsonl")
    sections = load_jsonl("page_sections.jsonl")
    observations = load_jsonl("taxonomy_observations.jsonl")
    canonicals = load_jsonl("canonical_index_v2.jsonl")
    edges = load_jsonl("edges.jsonl")
    candidates = load_jsonl("relation_candidates.jsonl")
    conflicts = load_jsonl("conflicts.jsonl")
    decisions = load_jsonl("merge_decisions.jsonl")

    assert report["overall_status"] == "pass"
    assert all(report["gates"].values()), "one or more recorded validation gates failed"
    assert all(not values for values in report["errors"].values()), "recorded error list is nonempty"

    source_ids = unique(sources, "source_id", "source IDs")
    section_ids = unique(sections, "section_observation_id", "section observation IDs")
    observation_ids = unique(observations, "observation_id", "taxonomy observation IDs")
    canonical_keys = unique(canonicals, "canonical_key", "canonical keys")
    edge_ids = unique(edges, "edge_observation_id", "edge observation IDs")
    candidate_ids = unique(candidates, "candidate_observation_id", "candidate observation IDs")
    unique(conflicts, "conflict_id", "conflict IDs")
    unique(decisions, "decision_id", "merge decision IDs")

    assert all(not row["pending"] for row in sources), "pending source remains"
    assert all(not row["pending"] for row in sections), "pending page section remains"
    excluded = [row for row in sources if "robot" in str(row.get("access_status", "")).lower()]
    assert excluded and all(row["closure_decision"] for row in excluded), (
        "robots-excluded source must have an explicit closure decision"
    )

    for row in observations:
        assert row["evidence"]["source_id"] in source_ids, row["observation_id"]
        parent = row.get("parent_canonical_key")
        assert parent is None or parent in canonical_keys, row["observation_id"]

    for row in canonicals:
        assert row["observation_ids"], row["canonical_key"]
        assert set(row["observation_ids"]) <= observation_ids, row["canonical_key"]
        parent = row.get("primary_parent_key")
        assert parent is None or parent in canonical_keys, row["canonical_key"]
        for item in row["paths_and_evidence"]:
            assert item["observation_id"] in observation_ids, row["canonical_key"]
            assert item["source_id"] in source_ids, row["canonical_key"]

    for row in edges:
        assert row["evidence"]["source_id"] in source_ids, row["edge_observation_id"]
        assert row["from_canonical_key"] in canonical_keys, row["edge_observation_id"]
        assert row["to_canonical_key"] in canonical_keys, row["edge_observation_id"]

    for row in candidates:
        assert row["evidence"]["source_id"] in source_ids, row["candidate_observation_id"]
        assert set(row["nvidia_scope_canonical_keys"]) <= canonical_keys, row["candidate_observation_id"]

    count_map = {
        "taxonomy_observations": len(observations),
        "source_observations": len(sources),
        "page_section_observations": len(sections),
        "edge_observations": len(edges),
        "relation_candidate_observations": len(candidates),
        "canonical_objects": len(canonicals),
        "conflict_records": len(conflicts),
        "merge_decisions": len(decisions),
        "canonical_url_groups": len({row["canonical_url_group"] for row in sources}),
    }
    assert count_map == report["counts"], "artifact counts do not match validation report"

    by_key = {row["canonical_key"]: row for row in canonicals}
    assert by_key["alpamayo"]["primary_type"] == "platform"
    assert by_key["halos"]["primary_type"] == "platform"
    assert by_key["drive-hyperion"]["primary_type"] == "reference_architecture"
    assert by_key["hpc-and-ai"]["primary_name"] == "AI for Science"
    assert "HPC and AI" in by_key["hpc-and-ai"]["aliases"]

    assert report["seed_count"] == 7 and len(set(report["seed_source_ids"])) == 7
    assert all(report["shard_validation_status"].values())
    assert supersession["superseded_version"] == "product_tree_v1"
    assert supersession["superseding_version"] == "product_tree_v2"
    assert "run-002/agents/product_tree" in supersession["superseded_artifact"]

    print(
        "PASS: "
        f"{len(canonicals)} canonical objects; "
        f"{len(observations)} taxonomy observations; "
        f"{len(sources)} sources; {len(sections)} sections; "
        f"{len(edges)} edges; {len(candidates)} relation candidates; "
        f"{len(conflicts)} conflicts; {len(decisions)} decisions."
    )


if __name__ == "__main__":
    main()
