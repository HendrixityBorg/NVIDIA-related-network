#!/usr/bin/env python3
"""Validate IDs, provenance links, canonical groups, and key type decisions."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
tree = json.loads((HERE / "product_tree.json").read_text(encoding="utf-8"))
nodes = [json.loads(line) for line in (HERE / "product_taxonomy.jsonl").read_text(encoding="utf-8").splitlines()]
canonical = [json.loads(line) for line in (HERE / "canonical_index.jsonl").read_text(encoding="utf-8").splitlines()]
sources = [json.loads(line) for line in (HERE / "source_frontier.jsonl").read_text(encoding="utf-8").splitlines()]

assert len(nodes) == len({row["id"] for row in nodes}) == tree["metadata"]["node_count"]
assert len(canonical) == len({row["canonical_key"] for row in canonical}) == tree["metadata"]["canonical_non_category_name_count"]
source_ids = {row["source_id"] for row in sources}
assert all(row["evidence"]["source_id"] in source_ids for row in nodes)
assert all(row["evidence"]["evidence_locator"] for row in nodes)
assert not any(row["access_status"] == "pending" for row in sources)

by_id = {row["id"]: row for row in nodes}
expected_types = {
    "products.data_center.dgx.cloud": "service",
    "products.gaming.shield": "product",
    "products.gaming.nvidia_app": "software",
    "products.gaming.broadcast": "software",
    "products.gaming.studio": "platform",
    "products.gaming.rtx_ai_pc": "solution",
}
assert all(by_id[node_id]["node_type"] == expected for node_id, expected in expected_types.items())

for name in ["H200", "H200 NVL", "L4", "L40", "L40S"]:
    row = next(row for row in nodes if row["name"] == name and "gpus_current" in row["id"])
    assert row["availability_state"] == "current"
for name in ["H100", "H100 NVL", "A40", "A10", "A16"]:
    row = next(row for row in nodes if row["name"] == name)
    assert row["availability_state"] == "supported_not_current_marketplace_portfolio"

print(f"OK: {len(nodes)} nodes, {len(canonical)} canonical objects, {len(sources)} frontier records")
