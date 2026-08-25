#!/usr/bin/env python3
"""Re-run only the DART slice and merge it into an existing collection."""
import json
from pathlib import Path

from collect_apac_review import Collector, OUT, write_jsonl


def rows(name):
    path = OUT / name
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


c = Collector()
c.load()
for issuer in c.universe:
    if any(s.get("listing_region_code") == "KR" for s in issuer["securities"]):
        c.dart(issuer)

frontier = [x for x in rows("source_frontier.jsonl") if x["region_code"] != "KR"] + c.frontier
access = [x for x in rows("access_audit.jsonl") if x["source_id"] not in {"kr_dart", "kr_dart_document"}] + c.access
raw = [x for x in rows("raw_contexts.jsonl") if x["region_code"] != "KR"] + c.raw_hits
write_jsonl(OUT / "source_frontier.jsonl", sorted(frontier, key=lambda x: (x["issuer_id"], x["region_code"])))
write_jsonl(OUT / "access_audit.jsonl", access)
write_jsonl(OUT / "raw_contexts.jsonl", raw)
print(json.dumps({"dart_frontier": len(c.frontier), "dart_contexts": len(c.raw_hits)}, ensure_ascii=False))
