#!/usr/bin/env python3
import argparse
from collections import Counter
import json
from pathlib import Path

from listed_company_network.repository import SnapshotRepository


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a frozen relationship v2 snapshot")
    parser.add_argument("snapshot_path", nargs="?", type=Path, help="snapshot JSON path")
    parser.add_argument("--snapshot", dest="snapshot_option", type=Path, help="snapshot JSON path")
    parser.add_argument(
        "--product-index",
        type=Path,
        default=Path("runs/2026-08-25-run-003/product_tree_v2/canonical_index_v2.jsonl"),
        help="frozen canonical product index used to validate product_scope_id",
    )
    args = parser.parse_args(argv)
    if args.snapshot_path and args.snapshot_option:
        parser.error("provide a positional snapshot path or --snapshot, not both")
    args.snapshot = args.snapshot_option or args.snapshot_path
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    repo = SnapshotRepository(args.snapshot)
    if not repo.snapshot.meta.snapshot_version.endswith(".v2"):
        raise SystemExit(
            f"expected final v2 snapshot, got {repo.snapshot.meta.snapshot_version}"
        )
    keys: set[tuple[str, str, str, str, str]] = set()
    product_scope_ids = {
        json.loads(line)["canonical_key"]
        for line in args.product_index.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    for source in repo.sources.values():
        if source.retrieved_at > repo.snapshot.meta.generated_at:
            raise SystemExit(
                f"source {source.id} retrieved_at exceeds snapshot generated_at"
            )
    security_owner: dict[tuple[str, str], str] = {}
    for entity in repo.entities.values():
        security_regions = {item.listing_region for item in entity.securities}
        if not entity.listing_regions:
            raise SystemExit(f"entity {entity.id} has no listing region")
        if set(entity.listing_regions) != security_regions:
            raise SystemExit(f"entity {entity.id} has inconsistent listing regions")
        for security in entity.securities:
            key = (security.exchange.casefold(), security.ticker.casefold())
            previous = security_owner.get(key)
            if previous and previous != entity.id:
                raise SystemExit(
                    f"duplicate exchange+ticker endpoint {key}: {previous}, {entity.id}"
                )
            security_owner[key] = entity.id
    for relation in repo.relationships.values():
        key = (
            relation.source_entity_id,
            relation.target_entity_id,
            relation.direction.value,
            relation.relation_type.value,
            relation.product_scope_id,
        )
        if key in keys:
            raise SystemExit(f"duplicate relationship key: {key}")
        keys.add(key)
        if relation.product_scope_id not in product_scope_ids | {"corporate_general"}:
            raise SystemExit(
                f"relationship {relation.id} has unknown product_scope_id: "
                f"{relation.product_scope_id}"
            )
        if relation.product_scopes:
            raise SystemExit(
                f"relationship {relation.id} retains legacy multi-product scopes"
            )
        if (
            relation.fact_status.value == "inferred"
            and relation.relation_type.value in {"supplier", "customer"}
            and relation.confidence_score >= 60
        ):
            raise SystemExit(
                f"inferred supplier/customer {relation.id} is not capped below 60"
            )
        if relation.low_confidence_partner_inclusion:
            if relation.relation_type.value != "partner":
                raise SystemExit(
                    f"low-confidence relation {relation.id} is not a partner"
                )
            statuses = set(relation.origin_terminal_statuses)
            if relation.fact_status.value == "inferred":
                if "needs_more_evidence" not in statuses:
                    raise SystemExit(
                        f"inferred low-confidence partner {relation.id} lacks needs_more_evidence"
                    )
                expected_cap = 49
            elif relation.fact_status.value == "unknown":
                if "approve_unknown" not in statuses:
                    raise SystemExit(
                        f"unknown low-confidence partner {relation.id} lacks approve_unknown"
                    )
                expected_cap = 39
            else:
                raise SystemExit(
                    f"low-confidence partner {relation.id} has wrong fact status"
                )
            if relation.confidence_score > expected_cap:
                raise SystemExit(
                    f"low-confidence partner {relation.id} exceeds cap {expected_cap}"
                )
            if not relation.inference_explanations:
                raise SystemExit(
                    f"low-confidence partner {relation.id} lacks inference explanation"
                )
        if not set(relation.relationship_evidence_ids).issubset(relation.evidence_ids):
            raise SystemExit(
                f"relationship {relation.id} has detached relationship evidence"
            )
        if not set(relation.entity_resolution_evidence_ids).issubset(relation.evidence_ids):
            raise SystemExit(
                f"relationship {relation.id} has detached entity-resolution evidence"
            )
    investees = [
        item
        for item in repo.relationships.values()
        if item.relation_type.value == "investor_or_investee"
        and item.relation_subtype == "investee"
    ]
    if len(investees) != 7:
        raise SystemExit(f"expected 7 latest-13F listed investees, got {len(investees)}")
    print(f"snapshot_path={repo.path}")
    print(f"snapshot={repo.snapshot.meta.snapshot_version}")
    print(f"entities={len(repo.entities)}")
    print(f"sources={len(repo.sources)}")
    print(f"evidence={len(repo.evidence)}")
    print(f"relationships={len(repo.relationships)}")
    for key, value in sorted(
        Counter(item.relation_type.value for item in repo.relationships.values()).items()
    ):
        print(f"relation.{key}={value}")
    for key, value in sorted(
        Counter(item.fact_status.value for item in repo.relationships.values()).items()
    ):
        print(f"status.{key}={value}")


if __name__ == "__main__":
    main()
