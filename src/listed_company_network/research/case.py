from __future__ import annotations

import json
import hashlib
import subprocess
from collections import Counter
from pathlib import Path

from .contracts import CaseManifest
from .io import load_document, sha256_file


def verify_case(manifest_path: Path) -> dict:
    manifest = CaseManifest.model_validate(load_document(manifest_path))
    repo_root = manifest_path.resolve().parents[2]
    legacy_root = repo_root / manifest.legacy_root
    errors: list[str] = []
    tracked_files_checked = 0
    try:
        tree_id = subprocess.run(
            ["git", "rev-parse", f"{manifest.frozen_source_commit}^{{tree}}"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if tree_id != manifest.frozen_tree_id:
            errors.append(f"frozen tree mismatch: {tree_id} != {manifest.frozen_tree_id}")
        raw_tree = subprocess.run(
            ["git", "ls-tree", "-r", "-z", manifest.frozen_source_commit],
            cwd=repo_root,
            check=True,
            capture_output=True,
        ).stdout
        for entry in raw_tree.split(b"\0"):
            if not entry:
                continue
            metadata, relative_raw = entry.split(b"\t", 1)
            _, object_type, expected_blob = metadata.decode().split(" ", 2)
            if object_type != "blob":
                continue
            relative = relative_raw.decode("utf-8", errors="surrogateescape")
            path = legacy_root / relative
            if not path.is_file():
                errors.append(f"frozen tracked file missing: {relative}")
                continue
            content = path.read_bytes()
            actual_blob = hashlib.sha1(
                f"blob {len(content)}\0".encode() + content
            ).hexdigest()
            if actual_blob != expected_blob:
                errors.append(f"frozen tracked file changed: {relative}")
            tracked_files_checked += 1
        if tracked_files_checked != manifest.expected_tracked_files:
            errors.append(
                f"tracked file count mismatch: {tracked_files_checked} != {manifest.expected_tracked_files}"
            )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        errors.append(f"unable to verify frozen Git tree: {exc}")
    checked_hashes: dict[str, str] = {}
    for relative, expected in manifest.key_artifact_sha256.items():
        path = legacy_root / relative
        if not path.is_file():
            errors.append(f"missing artifact: {path}")
            continue
        actual = sha256_file(path)
        checked_hashes[relative] = actual
        if actual != expected:
            errors.append(f"hash mismatch: {relative}")
    snapshot_path = legacy_root / manifest.snapshot_path
    counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    if snapshot_path.is_file():
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        counts = {
            "entities": len(snapshot.get("entities", [])),
            "sources": len(snapshot.get("sources", [])),
            "evidence": len(snapshot.get("evidence", [])),
            "relationships": len(snapshot.get("relationships", [])),
        }
        relation_counts = dict(
            Counter(item["relation_type"] for item in snapshot.get("relationships", []))
        )
        for key, expected in manifest.expected_counts.items():
            if counts.get(key) != expected:
                errors.append(f"count mismatch {key}: {counts.get(key)} != {expected}")
        for key, expected in manifest.expected_relation_counts.items():
            if relation_counts.get(key, 0) != expected:
                errors.append(
                    f"relationship count mismatch {key}: {relation_counts.get(key, 0)} != {expected}"
                )
    else:
        errors.append(f"missing snapshot: {snapshot_path}")
    return {
        "pass": not errors,
        "case_id": manifest.case_id,
        "frozen_source_commit": manifest.frozen_source_commit,
        "frozen_tree_id": manifest.frozen_tree_id,
        "tracked_files_checked": tracked_files_checked,
        "counts": counts,
        "relation_counts": relation_counts,
        "checked_hashes": checked_hashes,
        "errors": errors,
    }
