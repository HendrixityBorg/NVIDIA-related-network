#!/usr/bin/env python3
"""Build a conservative listed-entity resolution queue from all run-003 shards.

Exact aliases from the frozen v1 registry and exact normalized issuer names from
the SEC list can auto-resolve.  Fuzzy similarity never promotes a company.
Unmatched names remain an explicit human-review queue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
DEFAULT_UA = "listed-company-network-research/1.0 contact=research@example.invalid"
LEGAL_SUFFIXES = re.compile(
    r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|plc|holdings?|group|"
    r"technologies|technology|systems|international|sa|ag|se|nv|llc|lp)\b",
    re.I,
)


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("&", " and ").casefold()
    value = LEGAL_SUFFIXES.sub(" ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def add_observation(bucket: dict[str, list[dict]], name: str | None, item: dict) -> None:
    if not name or not name.strip():
        return
    bucket[name.strip()].append(item)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sec-user-agent", default=DEFAULT_UA)
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    run = repository_root / "runs" / "2026-08-25-run-003"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    observations: dict[str, list[dict]] = defaultdict(list)
    for row in rows(run / "product_tree_v2" / "relation_candidates.jsonl"):
        add_observation(observations, row.get("entity_name_raw"), {
            "family": "official_product_solution_page",
            "observation_id": row.get("candidate_observation_id"),
            "source_url": (row.get("evidence") or {}).get("source_url"),
            "relationship_hint": row.get("relationship_hint"),
        })
    for year in (2025, 2026):
        base = run / "agents" / f"official_articles_{year}"
        for row in rows(base / "observations.jsonl"):
            add_observation(observations, row.get("entity_name_raw"), {
                "family": f"official_article_{year}",
                "observation_id": row.get("observation_id"),
                "article_id": row.get("article_id"),
                "source_url": row.get("source_url"),
                "relationship_hint": row.get("relationship_hint"),
                "existing_resolution": row.get("resolved_entity_id"),
                "security_identifiers": row.get("security_identifiers", []),
            })
    filings = run / "agents" / "filings_presentations_complete"
    for filename in ("listed_candidates.jsonl", "raw_observations.jsonl"):
        for row in rows(filings / filename):
            add_observation(observations, row.get("entity_name_raw") or row.get("issuer_name"), {
                "family": "filing_or_presentation",
                "observation_id": row.get("observation_id") or row.get("holding_id"),
                "source_url": row.get("source_url"),
                "relationship_hint": row.get("relationship_hint"),
            })
    for row in rows(run / "npn_browser" / "raw_listings.jsonl"):
        add_observation(observations, row.get("name"), {
            "family": "npn",
            "observation_id": row.get("observation_id"),
            "source_url": row.get("source_url"),
            "relationship_hint": "partner",
        })

    snapshot = json.loads((repository_root / "data" / "snapshot_2026-08-25.json").read_text(encoding="utf-8"))
    existing_aliases: dict[str, set[str]] = defaultdict(set)
    existing_by_id = {}
    for entity in snapshot["entities"]:
        existing_by_id[entity["id"]] = entity
        for alias in [entity["legal_name"], entity["display_name"], *entity.get("aliases", [])]:
            if norm(alias):
                existing_aliases[norm(alias)].add(entity["id"])

    request = Request(SEC_URL, headers={"User-Agent": args.sec_user_agent, "Accept": "application/json"})
    with urlopen(request, timeout=45) as response:
        sec_raw = response.read()
    sec_payload = json.loads(sec_raw)
    fields = sec_payload["fields"]
    sec_rows = [dict(zip(fields, values)) for values in sec_payload["data"]]
    sec_by_name: dict[str, list[dict]] = defaultdict(list)
    for issuer in sec_rows:
        key = norm(str(issuer["name"]))
        if key:
            sec_by_name[key].append(issuer)

    resolved: list[dict] = []
    unresolved: list[dict] = []
    ambiguous: list[dict] = []
    sec_filtered: dict[tuple, dict] = {}
    for name in sorted(observations, key=str.casefold):
        key = norm(name)
        obs = observations[name]
        existing_ids = sorted(existing_aliases.get(key, set()))
        sec_matches = sec_by_name.get(key, [])
        record = {
            "candidate_name": name,
            "normalized_name": key,
            "observation_count": len(obs),
            "source_families": sorted({item["family"] for item in obs}),
            "observations": obs,
        }
        if len(existing_ids) == 1:
            entity = existing_by_id[existing_ids[0]]
            record.update({
                "resolution_status": "resolved_existing_exact_alias",
                "entity_id": entity["id"],
                "legal_name": entity["legal_name"],
                "securities": entity.get("securities", []),
            })
            resolved.append(record)
        elif len(existing_ids) > 1:
            record.update({"resolution_status": "ambiguous_existing_alias", "candidate_entity_ids": existing_ids})
            ambiguous.append(record)
        elif sec_matches:
            tickers = sorted({(item["cik"], item["name"], item["ticker"], item["exchange"]) for item in sec_matches})
            record.update({
                "resolution_status": "resolved_sec_exact_issuer_name",
                "sec_securities": [
                    {"cik": str(cik).zfill(10), "issuer_name": issuer, "ticker": ticker, "exchange": exchange}
                    for cik, issuer, ticker, exchange in tickers
                ],
            })
            resolved.append(record)
            for item in sec_matches:
                sec_filtered[(item["cik"], item["ticker"], item["exchange"])] = item
        else:
            record.update({"resolution_status": "unresolved_no_exact_match", "fuzzy_promotion_allowed": False})
            unresolved.append(record)

    write_jsonl(output / "resolved_exact.jsonl", resolved)
    write_jsonl(output / "ambiguous.jsonl", ambiguous)
    write_jsonl(output / "unresolved_review_queue.jsonl", unresolved)
    write_jsonl(output / "sec_company_tickers_exchange_filtered.jsonl", sorted(sec_filtered.values(), key=lambda x: (x["name"], x["ticker"])))
    source = {
        "url": SEC_URL,
        "publisher": "U.S. Securities and Exchange Commission",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": hashlib.sha256(sec_raw).hexdigest(),
        "access": "public_no_login",
        "license_note": "Public SEC company ticker/exchange dataset; filtered rows retained for audit.",
    }
    (output / "sec_source.json").write_text(json.dumps(source, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "candidate_names": len(observations),
        "resolved_exact": len(resolved),
        "ambiguous": len(ambiguous),
        "unresolved": len(unresolved),
        "fuzzy_promotions": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
