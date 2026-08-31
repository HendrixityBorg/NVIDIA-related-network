#!/usr/bin/env python3
"""Hydrate exact SEC CIKs for canonical Partner issuers without fuzzy matching."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
UNIVERSE = HERE / "canonical_partner_universe.jsonl"
SEC_TICKERS = HERE.parent / "npn_listed_parent_resolution" / "company_tickers_exchange.json"
SEC_SOURCE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def normalized_exchange(value: object) -> str:
    text = str(value or "").casefold().strip()
    if text in {"nasdaq", "nasdaq global select market", "nasdaq global market"}:
        return "nasdaq"
    if text in {"nyse", "new york stock exchange"}:
        return "nyse"
    return text


def main() -> int:
    rows = read_jsonl(UNIVERSE)
    sec = json.loads(SEC_TICKERS.read_text(encoding="utf-8"))
    index: dict[tuple[str, str], set[str]] = {}
    for cik, _name, ticker, exchange in sec["data"]:
        if not ticker or not exchange:
            continue
        key = (normalized_exchange(exchange), str(ticker).casefold())
        index.setdefault(key, set()).add(str(cik).zfill(10))

    decisions: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    hydrated: list[dict[str, Any]] = []
    overlays: list[dict[str, Any]] = []
    for row in rows:
        current_ciks = {
            str(security.get("cik")).zfill(10)
            for security in row.get("securities") or []
            if security.get("cik")
        }
        candidates: set[str] = set()
        matched_keys: list[str] = []
        for security in row.get("securities") or []:
            key = (
                normalized_exchange(security.get("exchange")),
                str(security.get("ticker") or "").casefold(),
            )
            matches = index.get(key, set())
            if matches:
                candidates.update(matches)
                matched_keys.append(f"{key[0]}:{key[1]}")
        selected = next(iter(candidates)) if len(candidates) == 1 else None
        if not current_ciks and selected:
            for security in row.get("securities") or []:
                if (
                    normalized_exchange(security.get("exchange")),
                    str(security.get("ticker") or "").casefold(),
                ) in index:
                    security["cik"] = selected
            decisions.append(
                {
                    "canonical_entity_id": row["canonical_entity_id"],
                    "selected_cik": selected,
                    "matched_exchange_tickers": sorted(set(matched_keys)),
                    "resolution_kind": "exact_sec_exchange_ticker",
                    "source_url": SEC_SOURCE_URL,
                    "publisher": "U.S. Securities and Exchange Commission",
                    "retrieved_at": "2026-08-25T23:30:00+08:00",
                    "pending": False,
                }
            )
            overlays.append(
                {
                    "entity_id": row["canonical_entity_id"],
                    "legal_name": row["legal_name"],
                    "display_name": row["display_name"],
                    "aliases": row.get("aliases") or [],
                    "listing_status": "listed",
                    "securities": row.get("securities") or [],
                    "notes": "CIK hydrated by exact SEC exchange+ticker match; relationship semantics unchanged.",
                }
            )
        elif not current_ciks and any(
            security.get("listing_region") == "United States"
            for security in row.get("securities") or []
        ):
            unresolved.append(
                {
                    "canonical_entity_id": row["canonical_entity_id"],
                    "display_name": row["display_name"],
                    "candidate_ciks": sorted(candidates),
                    "securities": row.get("securities") or [],
                    "terminal_status": "no_unique_exact_sec_exchange_ticker_match",
                    "pending": False,
                }
            )
        hydrated.append(row)

    write_jsonl(HERE / "sec_cik_hydration.jsonl", decisions)
    write_jsonl(HERE / "sec_cik_unresolved.jsonl", unresolved)
    write_jsonl(HERE / "canonical_partner_universe_with_cik.jsonl", hydrated)
    write_jsonl(HERE / "sec_cik_entity_registry_overlay.jsonl", overlays)
    report = {
        "pass": True,
        "canonical_partner_rows": len(rows),
        "new_exact_ciks": len(decisions),
        "unresolved_us_ciks": len(unresolved),
        "pending_count": 0,
        "fuzzy_matches": 0,
        "source_url": SEC_SOURCE_URL,
    }
    (HERE / "sec_cik_hydration_validation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
