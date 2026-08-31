#!/usr/bin/env python3
"""Write an atomic, reproducible progress summary from terminal partials."""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


root = Path(sys.argv[1]).resolve()
rows = []
for path in sorted((root / "partials").glob("article_*.json")):
    rows.append(json.loads(path.read_text(encoding="utf-8"))["processing"])
counts = Counter(row.get("recovery_method") for row in rows)
progress = {
    "manifest_total": 597,
    "terminal_rows": len(rows),
    "remaining": 597 - len(rows),
    "counts_by_recovery_method": dict(sorted(counts.items())),
    "body_covered_so_far": counts["direct"] + counts["rss"] + counts["wayback"],
    "blocked_so_far": counts["blocked"],
    "pending": 597 - len(rows),
    "third_party_full_html_retained": False,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}
temporary = root / "progress.json.tmp"
temporary.write_text(json.dumps(progress, indent=2, sort_keys=True) + "\n", encoding="utf-8")
temporary.replace(root / "progress.json")
print(json.dumps(progress, sort_keys=True))
