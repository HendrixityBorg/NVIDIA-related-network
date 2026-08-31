#!/usr/bin/env python3
"""Remove the script-created source cache after preserving public provenance."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTIER = ROOT / "source_frontier.jsonl"
CACHE = ROOT / "source_files"


def main() -> None:
    rows = [json.loads(line) for line in FRONTIER.read_text().splitlines() if line.strip()]
    for row in rows:
        row.pop("local_path", None)
        if "bytes" in row:
            row["byte_size"] = row.pop("bytes")
        row["local_cache_state"] = "removed_before_delivery"
        row["reproduction_note"] = "Re-fetch from frozen public URL; verify sha256 and byte_size before parsing."
    FRONTIER.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))

    expected = (ROOT / "source_files").resolve()
    if CACHE.exists():
        resolved = CACHE.resolve()
        if resolved != expected or resolved.parent != ROOT.resolve() or resolved.name != "source_files":
            raise RuntimeError(f"Refusing to delete unexpected path: {resolved}")
        shutil.rmtree(resolved)
    print(json.dumps({"source_rows": len(rows), "source_cache_present": CACHE.exists()}))


if __name__ == "__main__":
    main()
