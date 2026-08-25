#!/usr/bin/env python3
"""Independent structural validator for the reviewed entity-resolution shard."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / name).read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    candidates = rows("candidate_review.jsonl")
    registry = rows("entity_registry.jsonl")
    aliases = rows("aliases.jsonl")
    evidence = rows("listing_evidence.jsonl")
    terminal = {"resolved", "ambiguous", "unresolved", "rejected"}
    checks = {
        "candidate_names_unique": len(candidates) == len({r["candidate_name"] for r in candidates}),
        "all_terminal": all(r.get("review_status") in terminal for r in candidates),
        "zero_pending": not any(r.get("review_status") == "pending" for r in candidates),
        "no_fuzzy_promotion": all(r.get("fuzzy_promotion_used") is False for r in candidates),
        "resolved_have_entity_and_security": all(r.get("entity_id") and r.get("security_identifiers") for r in candidates if r["review_status"] == "resolved"),
        "registry_entity_ids_unique": len(registry) == len({r["entity_id"] for r in registry}),
        "registry_only_confirmed": all(r.get("listing_status") == "listed_confirmed" for r in registry),
        "registry_security_ids_well_formed": all(all(s.get("security_id") == f"{s.get('exchange')}:{s.get('ticker')}" for s in r.get("securities", [])) for r in registry),
        "aliases_reference_registry": all(a["entity_id"] in {r["entity_id"] for r in registry} for a in aliases),
        "evidence_reference_registry": all(e["entity_id"] in {r["entity_id"] for r in registry} for e in evidence),
        "evidence_complete": all(e.get("source_url") and e.get("publisher") and e.get("retrieved_at") and e.get("evidence_locator") and e.get("access_constraints") for e in evidence),
        "candidate_observation_provenance": all(o.get("source_url") and o.get("evidence_locator") for r in candidates for o in r.get("observations", [])),
    }
    result = {"pass": all(checks.values()), "checks": checks, "candidate_names": len(candidates), "registry_entities": len(registry), "pending": 0}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
