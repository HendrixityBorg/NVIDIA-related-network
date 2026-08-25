#!/usr/bin/env python3
"""Build a deterministic canonical universe for listed Partner endpoints.

This pre-normalization layer never edits the source snapshot.  It groups only
listed entities used by Partner relationships, using exact identifiers or exact
normalized legal names; it retains all original IDs, securities, tags and
relationship/evidence/source provenance for downstream regulatory review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


def norm_text(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def norm_exchange(value: str | None) -> str:
    aliases = {
        "nasdaq global select market": "nasdaq", "nasdaq global market": "nasdaq",
        "new york stock exchange": "nyse", "taiwan stock exchange corporation": "taiwan stock exchange",
    }
    n = norm_text(value)
    return aliases.get(n, n)


def security_key(s: dict[str, Any]) -> str | None:
    if not s.get("exchange") or not s.get("ticker"):
        return None
    return f"{norm_exchange(s['exchange'])}:{str(s['ticker']).strip().upper()}"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def hid(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(canonical_json(value).encode()).hexdigest()[:16]


def merge_unique(items: list[Any]) -> list[Any]:
    out, seen = [], set()
    for item in items:
        key = canonical_json(item)
        if key not in seen:
            seen.add(key); out.append(item)
    return out


class UF:
    def __init__(self, keys): self.p = {x: x for x in keys}
    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b: self.p[max(a, b)] = min(a, b)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=Path(__file__).resolve().parents[4] / "data/snapshot_2026-08-25.json")
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    snapshot_bytes = args.snapshot.read_bytes()
    snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
    data = json.loads(snapshot_bytes)
    entities = {e["id"]: e for e in data["entities"]}
    evidence = {e["id"]: e for e in data["evidence"]}
    sources = {s["id"]: s for s in data["sources"]}
    partner_rels = [r for r in data["relationships"] if r["relation_type"] == "partner"]
    partner_ids = set()
    for r in partner_rels:
        partner_ids.update((r["source_entity_id"], r["target_entity_id"]))
    partner_ids.discard("nvidia")
    partner_ids = {eid for eid in partner_ids if entities[eid].get("listing_status") == "listed"}
    uf = UF(partner_ids)
    bases: dict[tuple[str, str], list[str]] = defaultdict(list)
    for eid in sorted(partner_ids):
        e = entities[eid]
        for cik in sorted({str(s.get("cik") or "").lstrip("0").zfill(10) for s in e.get("securities", []) if s.get("cik")}):
            bases[("cik", cik)].append(eid)
        for s in e.get("securities", []):
            if security_key(s): bases[("exchange_ticker", security_key(s))].append(eid)
            if s.get("isin"): bases[("isin", str(s["isin"]).upper())].append(eid)
        if norm_text(e.get("legal_name")):
            bases[("legal_name_exact", norm_text(e["legal_name"]))].append(eid)
    for _, ids in sorted(bases.items()):
        for eid in ids[1:]: uf.union(ids[0], eid)

    members: dict[str, list[str]] = defaultdict(list)
    for eid in sorted(partner_ids): members[uf.find(eid)].append(eid)
    rels_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in partner_rels:
        for eid in (r["source_entity_id"], r["target_entity_id"]):
            if eid in partner_ids: rels_by_entity[eid].append(r)

    def rank(eid: str) -> tuple[Any, ...]:
        e = entities[eid]
        secs = e.get("securities", [])
        has_cik = any(s.get("cik") for s in secs)
        has_isin = any(s.get("isin") for s in secs)
        active = sum(s.get("status_at_cutoff") == "active_at_cutoff" for s in secs)
        # Prefer stable descriptive IDs only after stronger regulatory identifiers.
        synthetic = eid.startswith("npn-issuer-") or eid.startswith("entity_")
        return (-int(has_cik), -int(has_isin), -len(secs), -active, int(synthetic), len(eid), eid)

    canonical_rows, merge_rows, overlay_rows, ambiguity_rows = [], [], [], []
    for _, ids in sorted(members.items(), key=lambda kv: min(kv[1])):
        ids = sorted(ids)
        canonical_id = min(ids, key=rank)
        canon = entities[canonical_id]
        all_secs = merge_unique([s for eid in ids for s in entities[eid].get("securities", [])])
        all_aliases = sorted({a for eid in ids for a in (entities[eid].get("aliases") or [])} |
                             {entities[eid].get("display_name") for eid in ids} |
                             {entities[eid].get("legal_name") for eid in ids} - {None, ""})
        relationship_ids = sorted({r["id"] for eid in ids for r in rels_by_entity[eid]})
        rel_rows = [r for eid in ids for r in rels_by_entity[eid]]
        evidence_ids = sorted({x for r in rel_rows for x in r.get("evidence_ids", [])})
        source_ids = sorted({evidence[x]["source_id"] for x in evidence_ids if x in evidence})
        tag_fields = ["partner_types", "competencies", "specializations", "partner_levels", "locations", "product_service_tags", "npn_group_ids"]
        merged_tags = {field: sorted({v for r in rel_rows for v in r.get(field, [])}) for field in tag_fields}
        group_bases = []
        if len(ids) > 1:
            for (kind, value), hit_ids in sorted(bases.items()):
                overlap = sorted(set(hit_ids) & set(ids))
                if len(overlap) > 1:
                    group_bases.append({"identifier_type": kind, "identifier_value": value, "member_entity_ids": overlap})
        securities_by_identity: dict[str, dict[str, Any]] = {}
        for s in all_secs:
            key = security_key(s) or ("isin:" + str(s.get("isin")))
            if key not in securities_by_identity:
                securities_by_identity[key] = dict(s)
            else:
                securities_by_identity[key] = {k: securities_by_identity[key].get(k) or s.get(k) for k in set(securities_by_identity[key]) | set(s)}
        merged_secs = [securities_by_identity[k] for k in sorted(securities_by_identity)]
        row = {
            "canonical_entity_id": canonical_id, "display_name": canon.get("display_name"), "legal_name": canon.get("legal_name"),
            "listing_status": "listed", "member_entity_ids": ids, "member_count": len(ids),
            "aliases": all_aliases, "securities": merged_secs, "merge_bases": group_bases,
            "partner_relationship_ids": relationship_ids, "relationship_count": len(relationship_ids),
            "relationship_evidence_ids": evidence_ids, "relationship_source_ids": source_ids,
            "relationship_sources": [{k: sources[sid].get(k) for k in ("id", "url", "publisher", "published_at", "retrieved_at", "source_family")} for sid in source_ids],
            "merged_npn_tags": merged_tags, "source_snapshot": "data/snapshot_2026-08-25.json", "source_snapshot_sha256": snapshot_sha256,
            "research_cutoff": data["meta"].get("research_cutoff", "2026-08-25"),
        }
        canonical_rows.append(row)
        for eid in ids:
            merge_rows.append({
                "original_entity_id": eid, "canonical_entity_id": canonical_id,
                "is_canonical": eid == canonical_id, "merge_status": "merged_exact" if len(ids) > 1 else "singleton_retained",
                "merge_bases": group_bases if len(ids) > 1 else [], "original_entity": entities[eid],
                "partner_relationship_ids": sorted({r["id"] for r in rels_by_entity[eid]}),
                "status": "terminal", "pending": False,
            })
        if len(ids) > 1:
            overlay_rows.append({
                "entity_id": canonical_id, "member_entity_ids": ids, "legal_name": row["legal_name"], "display_name": row["display_name"],
                "aliases": all_aliases, "listing_status": "listed", "securities": merged_secs,
                "merge_bases": group_bases, "preservation_rule": "union securities/aliases; retain original entities in entity_merge_map; rewrite only downstream relationship endpoints using merge map",
            })
        active_keys = sorted({security_key(s) for s in merged_secs if security_key(s) and s.get("status_at_cutoff") != "historical_inactive"})
        if len(active_keys) > 1:
            ambiguity_rows.append({
                "canonical_entity_id": canonical_id, "member_entity_ids": ids, "active_exchange_ticker_candidates": active_keys,
                "status": "needs_manual_multilisting_classification", "reason": "Multiple active exchange+ticker identities are retained. They may be dual listings, multiple share classes, debt/preferred tickers, or stale status fields; no security was discarded.",
            })

    out = args.output_dir; out.mkdir(parents=True, exist_ok=True)
    def write(name, rows):
        (out / name).write_text("".join(canonical_json(r) + "\n" for r in rows), encoding="utf-8")
    write("canonical_partner_universe.jsonl", canonical_rows)
    write("entity_merge_map.jsonl", sorted(merge_rows, key=lambda r: r["original_entity_id"]))
    write("entity_registry_overlay.jsonl", sorted(overlay_rows, key=lambda r: r["entity_id"]))
    write("manual_multilisting_review.jsonl", sorted(ambiguity_rows, key=lambda r: r["canonical_entity_id"]))
    summary = {
        "snapshot_partner_listed_entity_count": len(partner_ids), "canonical_partner_entity_count": len(canonical_rows),
        "duplicate_group_count": sum(r["member_count"] > 1 for r in canonical_rows),
        "duplicate_original_entity_count": sum(r["member_count"] for r in canonical_rows if r["member_count"] > 1),
        "merged_away_entity_count": len(partner_ids) - len(canonical_rows),
        "manual_multilisting_review_count": len(ambiguity_rows),
    }
    (out / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
