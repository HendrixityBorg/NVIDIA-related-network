#!/usr/bin/env python3
"""Merge the v1 product tree and three independently validated v2 shards.

The output separates immutable observations from canonical decisions.  The build
is offline and deterministic: it never refetches a source or mutates its inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
REPO_ROOT = OUT.parents[2]
RUN2 = ROOT / "arti/runs/2026-08-25-run-002/agents/product_tree"
AGENTS = ROOT / "arti/runs/2026-08-25-run-003/agents"
CUTOFF = "2026-08-25"
GENERATED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

INPUTS = {
    "v1": RUN2,
    "dc_hpc": AGENTS / "v2_dc_hpc",
    "robotics_av": AGENTS / "v2_robotics_av",
    "network_ai_design": AGENTS / "v2_network_ai_design",
}


def repository_path(path: Path) -> str:
    """Serialize artifact paths relative to the repository, never a workstation."""
    return str(path.resolve().relative_to(REPO_ROOT))

SPECIAL_KEYS = {
    "architectures": "architectures-and-core-technologies",
    "edge": "embedded-robotics-and-edge",
    "cloud": "cloud-services",
    "visualization": "scientific-visualization",
    "hpc": "high-performance-computing",
    "ai-physics": "ai-physics-domain",
    "quantum": "quantum-computing",
    "hpc-overview": "high-performance-computing",
    "ai-for-science": "hpc-and-ai",
    "nvidia-robotics": "robotics",
    "jetson": "jetson-platform",
    "igx": "igx-platform",
    "ai-enterprise": "nvidia-ai-enterprise",
    "av-stage-vehicle": "in-vehicle-computing",
    "av-product-hyperion": "drive-hyperion",
    "av-product-agx-thor": "drive-agx-thor",
    "av-product-agx-orin": "drive-agx-orin",
    "av-product-driveos": "driveos",
    "av-product-drive-av": "drive-av",
    "av-product-alpamayo": "alpamayo",
    "av-product-halos": "halos",
    "av-safety-platform": "safety",
}

PRIMARY_OVERRIDES = {
    "alpamayo": ("NVIDIA Alpamayo", "platform", "Dedicated current Alpamayo page defines a portfolio spanning models, simulation frameworks, tools, and datasets."),
    "halos": ("NVIDIA Halos", "platform", "Dedicated current Halos page defines a full-stack safety system spanning hardware, software, tools, and services."),
    "drive-hyperion": ("NVIDIA DRIVE Hyperion", "reference_architecture", "Dedicated current page explicitly describes DRIVE Hyperion as a development platform and reference architecture."),
    "hpc-and-ai": ("AI for Science", "solution", "AI for Science is the current dedicated-page H1; HPC and AI is retained as a navigation alias."),
}

TYPE_PRIORITY = [
    "platform", "reference_architecture", "product", "service", "model",
    "software", "sdk", "framework", "blueprint", "solution", "workload",
    "use_case", "technology", "architecture", "industry", "category",
]


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def clean_key(value: str) -> str:
    value = value.replace("_", "-").lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def relaxed_name(value: str) -> str:
    value = re.sub(r"[™®]", "", value.lower())
    value = re.sub(r"\bnvidia\b", "", value)
    value = re.sub(r"\b(platform|portfolio|solution|solutions)\b", "", value)
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    path = re.sub(r"/+", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/") + "/"
    # Tracking and presentation-only parameters do not create a new source.
    ignored = {"ncid", "locale", "limit"}
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k not in ignored))
    return urlunsplit((parts.scheme.lower() or "https", parts.netloc.lower(), path, query, ""))


def evidence_from(raw: dict, shard: str, source_map: dict[tuple[str, str], str]) -> dict:
    nested = raw.get("evidence") if isinstance(raw.get("evidence"), dict) else {}
    raw_source_id = nested.get("source_id") or raw.get("source_id")
    source_id = source_map.get((shard, str(raw_source_id))) if raw_source_id is not None else None
    return {
        "source_id": source_id,
        "source_id_raw": raw_source_id,
        "source_url": nested.get("source_url") or nested.get("url") or raw.get("source_url"),
        "publisher": nested.get("publisher") or raw.get("publisher") or "NVIDIA",
        "evidence_locator": nested.get("evidence_locator") or raw.get("evidence_locator") or raw.get("locator"),
        "accessed_at": nested.get("accessed_at") or raw.get("accessed_at"),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # 1. Load and namespace every source observation.
    source_rows: list[dict] = []
    source_map: dict[tuple[str, str], str] = {}
    for shard, folder in INPUTS.items():
        for raw in load_jsonl(folder / "source_frontier.jsonl"):
            raw_id = str(raw["source_id"])
            source_id = f"{shard}:{raw_id}"
            source_map[(shard, raw_id)] = source_id
            url = raw["url"]
            status = raw.get("access_status", "processed")
            closure = raw.get("closure_decision") or ("excluded_robots" if status == "excluded_robots" else "processed_or_decided")
            source_rows.append({
                "source_id": source_id,
                "shard": shard,
                "source_id_raw": raw_id,
                "url": url,
                "canonical_url": canonical_url(raw.get("canonical_url") or url),
                "canonical_url_group": hashlib.sha256(canonical_url(raw.get("canonical_url") or url).encode()).hexdigest()[:16],
                "title": raw.get("title"),
                "publisher": raw.get("publisher", "NVIDIA"),
                "parent_path": raw.get("parent_path") or raw.get("branch"),
                "discovered_from_raw": raw.get("discovered_from"),
                "scope_role": raw.get("scope_role") or ("seed" if raw.get("is_seed") else "linked"),
                "is_seed": raw.get("scope_role") == "seed" or bool(raw.get("is_seed")),
                "accessed_at": raw.get("accessed_at"),
                "access_status": status,
                "closure_decision": closure,
                "pending": bool(raw.get("pending", False)) or "pending" in str(status).lower(),
                "access_or_license_note": raw.get("access_or_license_note"),
                "raw_record": raw,
            })
    for row in source_rows:
        raw_parent = row["discovered_from_raw"]
        row["discovered_from"] = source_map.get((row["shard"], str(raw_parent))) if raw_parent else None
    write_jsonl(OUT / "source_frontier.jsonl", source_rows)

    # 2. Normalize section-decision observations.
    section_rows: list[dict] = []
    for shard, folder in INPUTS.items():
        for idx, raw in enumerate(load_jsonl(folder / "page_sections.jsonl"), 1):
            raw_source = str(raw["source_id"])
            section_id_raw = str(raw.get("section_id") or f"section-{idx:04d}")
            status = raw.get("processing_status") or raw.get("processing_outcome") or raw.get("status") or "processed"
            section_rows.append({
                # Shard inputs may reuse semantic IDs such as ``overview`` on
                # multiple pages.  The merged observation identity therefore
                # includes the source while the exact raw ID remains below.
                "section_observation_id": f"{shard}:{raw_source}:{section_id_raw}",
                "shard": shard,
                "section_id_raw": section_id_raw,
                "source_id": source_map.get((shard, raw_source)),
                "section_title": raw.get("section_title") or raw.get("heading"),
                "evidence_locator": raw.get("evidence_locator"),
                "processing_status": status,
                "pending": "pending" in str(status).lower(),
                "notes": raw.get("notes"),
                "raw_record": raw,
            })
    write_jsonl(OUT / "page_sections.jsonl", section_rows)

    # 3. Load raw taxonomy records and construct canonical-key aliases.
    raw_nodes: list[tuple[str, dict]] = []
    raw_nodes.extend(("v1", row) for row in load_jsonl(INPUTS["v1"] / "product_taxonomy.jsonl"))
    for shard in ("dc_hpc", "robotics_av", "network_ai_design"):
        raw_nodes.extend((shard, row) for row in load_jsonl(INPUTS[shard] / "taxonomy_nodes.jsonl"))

    v1_relaxed: dict[str, set[str]] = defaultdict(set)
    for shard, raw in raw_nodes:
        if shard == "v1":
            v1_relaxed[relaxed_name(raw["name"])].add(clean_key(raw["canonical_key"]))

    def choose_key(shard: str, raw_key: str, name: str) -> str:
        key = clean_key(raw_key)
        if key in SPECIAL_KEYS:
            return SPECIAL_KEYS[key]
        if shard != "v1":
            matches = v1_relaxed.get(relaxed_name(name), set())
            if len(matches) == 1:
                return next(iter(matches))
        return key

    raw_id_map: dict[tuple[str, str], str] = {}
    raw_key_map: dict[tuple[str, str], str] = {}
    for shard, raw in raw_nodes:
        raw_key = str(raw["canonical_key"])
        canonical_key = choose_key(shard, raw_key, raw["name"])
        raw_id = str(raw.get("node_id") or raw.get("id") or raw_key)
        raw_id_map[(shard, raw_id)] = canonical_key
        raw_key_map[(shard, clean_key(raw_key))] = canonical_key

    observations: list[dict] = []
    for index, (shard, raw) in enumerate(raw_nodes, 1):
        raw_key = str(raw["canonical_key"])
        raw_id = str(raw.get("node_id") or raw.get("id") or raw_key)
        canonical_key = raw_id_map[(shard, raw_id)]
        parent_raw = raw.get("parent_key") or raw.get("parent_id")
        parent_key = None
        if parent_raw:
            parent_key = raw_id_map.get((shard, str(parent_raw)))
            if parent_key is None:
                parent_key = raw_key_map.get((shard, clean_key(str(parent_raw))))
            if parent_key is None:
                parent_key = SPECIAL_KEYS.get(clean_key(str(parent_raw)), clean_key(str(parent_raw)))
        raw_path = raw.get("taxonomy_path") or raw.get("path") or []
        canonical_path = []
        for part in raw_path:
            part_key = clean_key(str(part))
            canonical_path.append(raw_key_map.get((shard, part_key), SPECIAL_KEYS.get(part_key, part_key)))
        aliases = raw.get("aliases") if isinstance(raw.get("aliases"), list) else []
        observations.append({
            "observation_id": f"OBS-{index:05d}",
            "shard": shard,
            "raw_node_id": raw_id,
            "raw_canonical_key": raw_key,
            "canonical_key": canonical_key,
            "observed_name": raw["name"],
            "observed_type": raw["node_type"],
            "observed_aliases": aliases,
            "parent_ref_raw": parent_raw,
            "parent_canonical_key": parent_key,
            "raw_path": raw_path,
            "canonical_path": canonical_path,
            "availability_state": raw.get("availability_state", "unspecified"),
            "observation_status": raw.get("evidence_status") or raw.get("status") or "observed",
            "merge_action_raw": raw.get("merge_action"),
            "evidence": evidence_from(raw, shard, source_map),
            "raw_record": raw,
        })
    write_jsonl(OUT / "taxonomy_observations.jsonl", observations)

    # 4. Canonical objects: every observation remains linked, while primary fields are decisions.
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in observations:
        grouped[row["canonical_key"]].append(row)
    all_keys = set(grouped)
    canonical_rows: list[dict] = []
    conflicts: list[dict] = []
    decisions: list[dict] = []
    for key, rows in sorted(grouped.items()):
        names = sorted({row["observed_name"] for row in rows})
        types = sorted({row["observed_type"] for row in rows})
        parent_counts = Counter(row["parent_canonical_key"] for row in rows if row["parent_canonical_key"] and row["parent_canonical_key"] != key)
        valid_parents = [parent for parent, _ in parent_counts.most_common() if parent in all_keys]
        if key in PRIMARY_OVERRIDES:
            primary_name, primary_type, rule = PRIMARY_OVERRIDES[key]
            type_rule = "explicit_current_dedicated_page_override"
        else:
            name_scores = Counter()
            for row in rows:
                name_scores[row["observed_name"]] += 3 if row["shard"] != "v1" else 1
            primary_name = sorted(name_scores, key=lambda name: (-name_scores[name], len(name), name))[0]
            primary_type = next((kind for kind in TYPE_PRIORITY if kind in types), types[0])
            rule = "Prefer repeated v2 observation for name; choose the most entity-specific observed type by documented precedence."
            type_rule = "explanatory_type_precedence"
        aliases = set(names) - {primary_name}
        for row in rows:
            aliases.update(row["observed_aliases"])
        if key == "hpc-and-ai":
            aliases.add("HPC and AI")
        primary_parent = valid_parents[0] if valid_parents else None
        source_paths = []
        for row in rows:
            source_paths.append({
                "observation_id": row["observation_id"],
                "shard": row["shard"],
                "canonical_path": row["canonical_path"],
                "parent_canonical_key": row["parent_canonical_key"],
                "source_id": row["evidence"]["source_id"],
                "evidence_locator": row["evidence"]["evidence_locator"],
            })
        canonical_rows.append({
            "canonical_key": key,
            "primary_name": primary_name,
            "primary_type": primary_type,
            "aliases": sorted(alias for alias in aliases if alias and alias != primary_name),
            "observed_names": names,
            "observed_types": types,
            "availability_states": sorted({row["availability_state"] for row in rows}),
            "primary_parent_key": primary_parent,
            "all_parent_keys": valid_parents,
            "paths_and_evidence": source_paths,
            "observation_ids": [row["observation_id"] for row in rows],
            "observation_count": len(rows),
            "decision_rule": rule,
        })
        decisions.append({
            "decision_id": f"DEC-{len(decisions)+1:05d}",
            "canonical_key": key,
            "selected_primary_name": primary_name,
            "selected_primary_type": primary_type,
            "selected_primary_parent_key": primary_parent,
            "name_candidates": names,
            "type_candidates": types,
            "parent_candidates": valid_parents,
            "rule": rule,
            "type_rule": type_rule,
            "observation_ids": [row["observation_id"] for row in rows],
        })
        if len(names) > 1:
            conflicts.append({"conflict_id": f"CON-{len(conflicts)+1:05d}", "canonical_key": key, "field": "name", "observed_values": names, "resolution": primary_name, "status": "resolved_with_aliases", "observation_ids": [row["observation_id"] for row in rows]})
        if len(types) > 1:
            conflicts.append({"conflict_id": f"CON-{len(conflicts)+1:05d}", "canonical_key": key, "field": "node_type", "observed_values": types, "resolution": primary_type, "status": "resolved_primary_observations_preserved", "rule": rule, "observation_ids": [row["observation_id"] for row in rows]})
        if len(valid_parents) > 1:
            conflicts.append({"conflict_id": f"CON-{len(conflicts)+1:05d}", "canonical_key": key, "field": "parent", "observed_values": valid_parents, "resolution": primary_parent, "status": "primary_parent_selected_all_paths_preserved", "observation_ids": [row["observation_id"] for row in rows]})

    # Preserve shard-authored semantic/quantitative conflicts as additional raw observations.
    for shard in ("dc_hpc", "robotics_av"):
        patch = json.loads((INPUTS[shard] / "merge_patch.json").read_text(encoding="utf-8"))
        for raw in patch.get("conflicts", []):
            conflicts.append({
                "conflict_id": f"CON-{len(conflicts)+1:05d}",
                "canonical_key": SPECIAL_KEYS.get(clean_key(str(raw.get("canonical_key", ""))), clean_key(str(raw.get("canonical_key", "")))) or None,
                "field": raw.get("field") or "shard_authored_conflict",
                "observed_values": raw.get("observations") or {k: v for k, v in raw.items() if k not in {"resolution", "handling"}},
                "resolution": raw.get("resolution") or raw.get("handling"),
                "status": raw.get("status") or "shard_conflict_preserved",
                "shard": shard,
                "raw_record": raw,
            })
    write_jsonl(OUT / "canonical_index_v2.jsonl", canonical_rows)
    write_jsonl(OUT / "conflicts.jsonl", conflicts)
    write_jsonl(OUT / "merge_decisions.jsonl", decisions)

    canonical_keys = {row["canonical_key"] for row in canonical_rows}

    # 5. Normalize edge observations and resolve endpoints to canonical keys.
    edge_rows: list[dict] = []
    for shard in ("dc_hpc", "robotics_av", "network_ai_design"):
        for idx, raw in enumerate(load_jsonl(INPUTS[shard] / "solution_product_edges.jsonl"), 1):
            raw_from = str(raw.get("from_key") or raw.get("source_node_id"))
            raw_to = str(raw.get("to_key") or raw.get("target_node_id"))
            from_key = raw_id_map.get((shard, raw_from)) or raw_key_map.get((shard, clean_key(raw_from))) or SPECIAL_KEYS.get(clean_key(raw_from), clean_key(raw_from))
            to_key = raw_id_map.get((shard, raw_to)) or raw_key_map.get((shard, clean_key(raw_to))) or SPECIAL_KEYS.get(clean_key(raw_to), clean_key(raw_to))
            evidence = evidence_from(raw, shard, source_map)
            raw_edge_id = str(raw.get("edge_id") or f"edge-{idx:04d}")
            edge_rows.append({
                "edge_observation_id": f"{shard}:{raw_edge_id}",
                "shard": shard,
                "edge_id_raw": raw_edge_id,
                "from_canonical_key": from_key,
                "to_canonical_key": to_key,
                "edge_type": raw["edge_type"],
                "status": raw.get("mapping_status") or raw.get("evidence_status") or raw.get("status") or "observed",
                "evidence": evidence,
                "rationale": raw.get("rationale"),
                "raw_record": raw,
            })
    write_jsonl(OUT / "edges.jsonl", edge_rows)

    # 6. Normalize candidate observations.  They remain candidates, never final relationships.
    candidate_rows: list[dict] = []
    for shard in ("dc_hpc", "robotics_av", "network_ai_design"):
        for idx, raw in enumerate(load_jsonl(INPUTS[shard] / "relation_candidates.jsonl"), 1):
            raw_candidate_id = str(raw.get("candidate_id") or f"candidate-{idx:04d}")
            raw_scopes = raw.get("product_context_keys") or raw.get("nvidia_product_or_solution_ids") or raw.get("nvidia_scope_ids") or []
            scopes = []
            for ref in raw_scopes:
                ref = str(ref)
                key = raw_id_map.get((shard, ref)) or raw_key_map.get((shard, clean_key(ref))) or SPECIAL_KEYS.get(clean_key(ref), clean_key(ref))
                scopes.append(key)
            evidence = evidence_from(raw, shard, source_map)
            candidate_rows.append({
                "candidate_observation_id": f"{shard}:{raw_candidate_id}",
                "shard": shard,
                "candidate_id_raw": raw_candidate_id,
                "entity_name_raw": raw.get("candidate_name_raw") or raw.get("observed_entity_name") or raw.get("entity_name_raw"),
                "entity_kind_hint": raw.get("entity_kind_hint"),
                "fact_status": raw.get("relationship_status") or raw.get("observation_status") or raw.get("candidate_fact_status") or "unclassified_candidate",
                "relationship_hint": raw.get("page_relationship_label_or_hint") or raw.get("relationship_hint") or "unknown",
                "product_mapping_status": raw.get("product_mapping_status") or "observed",
                "nvidia_scope_canonical_keys": sorted(set(scopes)),
                "context": raw.get("context_note") or raw.get("context"),
                "uncertainty": raw.get("rationale_or_uncertainty") or raw.get("rationale"),
                "final_relationship_classification": raw.get("final_relationship_classification") or "not_performed_in_product_tree",
                "evidence": evidence,
                "raw_record": raw,
            })
    write_jsonl(OUT / "relation_candidates.jsonl", candidate_rows)

    # 7. Render a complete once-per-canonical tree using the chosen primary parent.
    canon_by_key = {row["canonical_key"]: row for row in canonical_rows}
    children: dict[str | None, list[str]] = defaultdict(list)
    for row in canonical_rows:
        parent = row["primary_parent_key"] if row["primary_parent_key"] in canon_by_key else None
        children[parent].append(row["canonical_key"])
    for values in children.values():
        values.sort(key=lambda key: (canon_by_key[key]["primary_name"].lower(), key))
    rendered: set[str] = set()

    def render_key(key: str, depth: int, ancestry: set[str]) -> list[str]:
        row = canon_by_key[key]
        line = "  " * depth + f"- {row['primary_name']} `[{row['primary_type']}]` (`{key}`; observations={row['observation_count']})"
        if key in ancestry:
            return [line + " — cycle suppressed"]
        rendered.add(key)
        lines = [line]
        for child in children.get(key, []):
            if child not in rendered:
                lines.extend(render_key(child, depth + 1, ancestry | {key}))
        return lines

    md = [
        "# NVIDIA Product Tree v2",
        "",
        f"Research cutoff: **{CUTOFF}**. Canonical objects: **{len(canonical_rows)}**; raw taxonomy observations: **{len(observations)}**.",
        "",
        "This tree shows each canonical object once under a selected primary parent. All alternative names, types, parents, paths, and evidence remain in `canonical_index_v2.jsonl` and `taxonomy_observations.jsonl`; the readable tree is therefore a view, not a destructive flattening.",
        "",
        "## Canonical tree",
        "",
    ]
    for root_key in children[None]:
        if root_key not in rendered:
            md.extend(render_key(root_key, 0, set()))
    for key in sorted(canonical_keys - rendered):
        md.extend(render_key(key, 0, set()))
    md += [
        "",
        "## Explicit conflict decisions",
        "",
        "- **NVIDIA Alpamayo**: primary type `platform`; all v1 software and v2 platform observations retained.",
        "- **NVIDIA Halos**: primary type `platform`; subordinate Halos OS/SDK/app/service observations remain separate.",
        "- **NVIDIA DRIVE Hyperion**: primary type `reference_architecture`; Hyperion 8/10 remain product observations.",
        "- **AI for Science**: current primary name for canonical key `hpc-and-ai`; `HPC and AI` is an alias.",
        "- Other conflicts use documented type precedence and retain `observed_types`, all paths, and the decision record; no observation is silently overwritten.",
        "",
        "## Scope boundary",
        "",
        "The seven seed pages and each shard's declared direct-family closure are complete at the shard-defined boundary. A robots-excluded parameterized use-case listing is retained as an explicit exclusion, not a pending source. This is not an unbounded crawl of NVIDIA documentation, model catalogs, stores, news, or every product SKU.",
    ]
    (OUT / "PRODUCT_TREE_V2.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    # 8. Validate gates and reconcile input/output counts.
    validation_inputs = {}
    shard_pass = {}
    for shard in ("dc_hpc", "robotics_av", "network_ai_design"):
        report = json.loads((INPUTS[shard] / "validation_report.json").read_text(encoding="utf-8"))
        status = report.get("overall_status") or report.get("status")
        if status is None and isinstance(report.get("checks"), dict):
            status = "pass" if all(report["checks"].values()) else "fail"
        shard_pass[shard] = status == "pass"
        validation_inputs[shard] = report

    source_ids = {row["source_id"] for row in source_rows}
    observation_ids = {row["observation_id"] for row in observations}
    errors = {
        "pending_sources": [row["source_id"] for row in source_rows if row["pending"]],
        "pending_sections": [row["section_observation_id"] for row in section_rows if row["pending"]],
        "duplicate_source_ids": [key for key, count in Counter(row["source_id"] for row in source_rows).items() if count > 1],
        "taxonomy_bad_source_refs": [row["observation_id"] for row in observations if row["evidence"]["source_id"] not in source_ids],
        "taxonomy_bad_parent_refs": [row["observation_id"] for row in observations if row["parent_canonical_key"] and row["parent_canonical_key"] not in canonical_keys],
        "canonical_bad_observation_refs": [row["canonical_key"] for row in canonical_rows if any(item not in observation_ids for item in row["observation_ids"])],
        "canonical_bad_source_refs": [row["canonical_key"] for row in canonical_rows if any(item["source_id"] not in source_ids for item in row["paths_and_evidence"])],
        "canonical_dangling_parent_refs": [row["canonical_key"] for row in canonical_rows if row["primary_parent_key"] and row["primary_parent_key"] not in canonical_keys],
        "edge_bad_source_refs": [row["edge_observation_id"] for row in edge_rows if row["evidence"]["source_id"] not in source_ids],
        "edge_dangling_refs": [row["edge_observation_id"] for row in edge_rows if row["from_canonical_key"] not in canonical_keys or row["to_canonical_key"] not in canonical_keys],
        "candidate_bad_source_refs": [row["candidate_observation_id"] for row in candidate_rows if row["evidence"]["source_id"] not in source_ids],
        "candidate_dangling_scope_refs": [row["candidate_observation_id"] for row in candidate_rows if any(key not in canonical_keys for key in row["nvidia_scope_canonical_keys"])],
        "duplicate_canonical_keys": [key for key, count in Counter(row["canonical_key"] for row in canonical_rows).items() if count > 1],
        "duplicate_observation_ids": [key for key, count in Counter(row["observation_id"] for row in observations).items() if count > 1],
        "duplicate_section_ids": [key for key, count in Counter(row["section_observation_id"] for row in section_rows).items() if count > 1],
        "duplicate_edge_ids": [key for key, count in Counter(row["edge_observation_id"] for row in edge_rows).items() if count > 1],
        "duplicate_candidate_ids": [key for key, count in Counter(row["candidate_observation_id"] for row in candidate_rows).items() if count > 1],
    }
    expected = {
        "taxonomy_observations": sum(len(load_jsonl(INPUTS[s] / ("product_taxonomy.jsonl" if s == "v1" else "taxonomy_nodes.jsonl"))) for s in INPUTS),
        "source_observations": sum(len(load_jsonl(INPUTS[s] / "source_frontier.jsonl")) for s in INPUTS),
        "page_section_observations": sum(len(load_jsonl(INPUTS[s] / "page_sections.jsonl")) for s in INPUTS),
        "edge_observations": sum(len(load_jsonl(INPUTS[s] / "solution_product_edges.jsonl")) for s in ("dc_hpc", "robotics_av", "network_ai_design")),
        "relation_candidate_observations": sum(len(load_jsonl(INPUTS[s] / "relation_candidates.jsonl")) for s in ("dc_hpc", "robotics_av", "network_ai_design")),
    }
    actual = {
        "taxonomy_observations": len(observations),
        "source_observations": len(source_rows),
        "page_section_observations": len(section_rows),
        "edge_observations": len(edge_rows),
        "relation_candidate_observations": len(candidate_rows),
    }
    seed_rows = [row for row in source_rows if row["shard"] != "v1" and row["is_seed"]]
    gates = {
        "seven_of_seven_seeds": len(seed_rows) == 7,
        "all_three_shards_pass": all(shard_pass.values()),
        "source_zero_pending": not errors["pending_sources"],
        "section_zero_pending": not errors["pending_sections"],
        "robots_exclusion_explicit": any(row["closure_decision"] == "excluded_robots" and not row["pending"] for row in source_rows),
        "all_taxonomy_provenance_resolves": not errors["taxonomy_bad_source_refs"] and not errors["taxonomy_bad_parent_refs"],
        "canonical_index_provenance_resolves": not errors["canonical_bad_observation_refs"] and not errors["canonical_bad_source_refs"] and not errors["canonical_dangling_parent_refs"],
        "all_edge_provenance_resolves": not errors["edge_bad_source_refs"] and not errors["edge_dangling_refs"],
        "all_candidate_provenance_resolves": not errors["candidate_bad_source_refs"] and not errors["candidate_dangling_scope_refs"],
        "canonical_keys_unique": not errors["duplicate_canonical_keys"],
        "source_ids_unique": not errors["duplicate_source_ids"],
        "observation_ids_unique": not errors["duplicate_observation_ids"] and not errors["duplicate_section_ids"] and not errors["duplicate_edge_ids"] and not errors["duplicate_candidate_ids"],
        "counts_reconcile": expected == actual,
    }
    validation = {
        "schema_version": "2.0",
        "research_cutoff": CUTOFF,
        "generated_at": GENERATED_AT,
        "inputs": {name: repository_path(path) for name, path in INPUTS.items()},
        "v1_status": "superseded_by_product_tree_v2_inputs_preserved",
        "shard_validation_status": shard_pass,
        "seed_count": len(seed_rows),
        "seed_source_ids": [row["source_id"] for row in seed_rows],
        "counts": {
            **actual,
            "canonical_objects": len(canonical_rows),
            "conflict_records": len(conflicts),
            "merge_decisions": len(decisions),
            "canonical_url_groups": len({row["canonical_url_group"] for row in source_rows}),
        },
        "expected_input_counts": expected,
        "gates": gates,
        "errors": errors,
        "overall_status": "pass" if all(gates.values()) and not any(errors.values()) else "fail",
    }
    (OUT / "validation_report.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "supersession.json").write_text(json.dumps({
        "superseded_artifact": repository_path(RUN2),
        "superseded_version": "product_tree_v1",
        "superseding_artifact": repository_path(OUT),
        "superseding_version": "product_tree_v2",
        "policy": "v1 files remain immutable and all v1 taxonomy/source observations are included in v2 provenance.",
        "research_cutoff": CUTOFF,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readme = f"""# NVIDIA Product Tree v2\n\nResearch cutoff: **{CUTOFF}**. This artifact supersedes v1 without modifying it. It merges v1 plus the independently validated Data Center/HPC, Robotics/AV, and Networking/AI/Design shards.\n\n## Outputs\n\n- `PRODUCT_TREE_V2.md`: readable once-per-canonical tree.\n- `canonical_index_v2.jsonl`: canonical decisions with every observed name, type, path, and evidence.\n- `taxonomy_observations.jsonl`: {len(observations)} immutable normalized raw taxonomy observations, each retaining its raw input record.\n- `edges.jsonl`: {len(edge_rows)} solution/product edge observations.\n- `relation_candidates.jsonl`: {len(candidate_rows)} research candidates; none are promoted to a final relationship here.\n- `source_frontier.jsonl`: {len(source_rows)} namespaced source observations; same canonical URL can retain multiple shard paths.\n- `page_sections.jsonl`: normalized section decisions.\n- `conflicts.jsonl`: generated and shard-authored conflicts.\n- `merge_decisions.jsonl`: one explainable primary-field decision per canonical object.\n- `validation_report.json`: all closure, provenance, uniqueness, and reconciliation gates.\n- `supersession.json`: explicit v1 supersession record.\n- `build_v2.py`: offline deterministic merger.\n\n`generated_at` is the actual UTC build time; it is provenance metadata and is not used in canonical IDs, merge decisions, counts, or validation hashes.\n\n## Reproduce\n\nRun these commands from the repository root (`arti/`):\n\n```bash\npython3 runs/2026-08-25-run-003/product_tree_v2/build_v2.py\npython3 runs/2026-08-25-run-003/product_tree_v2/validate_v2.py\n```\n\nThe source frontier uses only public observations already collected by the input shards. No credential, login, paywall, CAPTCHA, robots, rate-limit, or access-control bypass occurs. The parameterized use-case URL excluded by robots remains an explicit decided frontier row.\n\n## Canonical rules\n\nAll raw observations survive. Exact/safe normalized-name matches and documented aliases map observations to a canonical key. `Alpamayo=platform`, `Halos=platform`, `DRIVE Hyperion=reference_architecture`, and `hpc-and-ai` has current primary name `AI for Science` with `HPC and AI` as alias. Other type conflicts use a documented entity-specific precedence, while `observed_types`, paths, evidence, conflict records, and decisions remain visible.\n"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")

    if validation["overall_status"] != "pass":
        raise SystemExit("v2 validation gates failed; inspect validation_report.json")


if __name__ == "__main__":
    main()
