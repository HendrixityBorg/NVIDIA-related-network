#!/usr/bin/env python3
"""Collect public SEC filing documents that mention NVIDIA for listed partners.

The collector uses SEC's public full-text search endpoint and archive documents.
It never attempts login, CAPTCHA, paywall, robots, or rate-limit bypass.  The
result is a frozen candidate corpus, not a relationship classifier.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import html
import json
import re
import time
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = (
    "listed-company-network-research/1.0 contact-not-provided@example.invalid "
    "public research no credentials"
)
SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
# SEC EFTS treats base form names as families that include amendments.  Adding
# explicit ``/A`` tokens changes its filter semantics and can silently select
# amendments only, so the frozen query deliberately uses base names.
FORMS = "10-K,20-F,40-F,10-Q,8-K,6-K,S-1,F-1,424B4,UPLOAD,CORRESP"
START_DATE = "2025-01-01"
CUTOFF_DATE = "2026-08-25"
NVIDIA_RE = re.compile(r"\bNVIDIA(?:\s+Corporation)?\b", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


def pace_requests(minimum_interval: float = 0.38) -> None:
    """Keep aggregate SEC request starts well below the published 10/sec cap."""
    global _LAST_REQUEST_AT
    with _REQUEST_LOCK:
        remaining = minimum_interval - (time.monotonic() - _LAST_REQUEST_AT)
        if remaining > 0:
            time.sleep(remaining)
        _LAST_REQUEST_AT = time.monotonic()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def stable_id(prefix: str, *values: object) -> str:
    raw = "|".join(str(value) for value in values)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:20]}"


def fetch(url: str, *, retries: int = 3, delay: float = 0.14) -> bytes:
    error: Exception | None = None
    for attempt in range(retries):
        try:
            pace_requests()
            request = Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
            )
            with urlopen(request, timeout=40) as response:
                body = response.read()
            time.sleep(delay)
            return body
        except (HTTPError, URLError, TimeoutError) as exc:
            error = exc
            time.sleep(0.8 * (attempt + 1))
    raise RuntimeError(f"public SEC retrieval failed after {retries} attempts: {url}: {error}")


def normalize_cik(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits.zfill(10) if digits else None


def partner_universe(snapshot: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    partner_ids = {
        row["target_entity_id"] if row["source_entity_id"] == "nvidia" else row["source_entity_id"]
        for row in snapshot["relationships"]
        if row["relation_type"] == "partner"
    }
    rows: list[dict[str, Any]] = []
    cik_to_entities: dict[str, list[str]] = defaultdict(list)
    for entity in snapshot["entities"]:
        if entity["id"] not in partner_ids:
            continue
        ciks = sorted(
            {
                cik
                for security in entity.get("securities") or []
                if (cik := normalize_cik(security.get("cik")))
            }
        )
        row = {
            "entity_id": entity["id"],
            "legal_name": entity["legal_name"],
            "display_name": entity["display_name"],
            "listing_regions": entity.get("listing_regions") or [],
            "securities": entity.get("securities") or [],
            "ciks": ciks,
        }
        rows.append(row)
        for cik in ciks:
            cik_to_entities[cik].append(entity["id"])
    return sorted(rows, key=lambda item: item["entity_id"]), dict(cik_to_entities)


def canonical_partner_universe(path: Path) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    rows: list[dict[str, Any]] = []
    cik_to_entities: dict[str, list[str]] = defaultdict(list)
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        item = json.loads(raw)
        ciks = sorted(
            {
                cik
                for security in item.get("securities") or []
                if (cik := normalize_cik(security.get("cik")))
            }
        )
        entity_id = item.get("canonical_entity_id") or item["entity_id"]
        row = {
            "entity_id": entity_id,
            "legal_name": item["legal_name"],
            "display_name": item["display_name"],
            "listing_regions": sorted(
                {
                    security.get("listing_region")
                    for security in item.get("securities") or []
                    if security.get("listing_region")
                }
            ),
            "securities": item.get("securities") or [],
            "ciks": ciks,
        }
        rows.append(row)
        for cik in ciks:
            cik_to_entities[cik].append(entity_id)
    return sorted(rows, key=lambda item: item["entity_id"]), dict(cik_to_entities)


def search_hits(ciks: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    hits: dict[str, dict[str, Any]] = {}
    access: list[dict[str, Any]] = []
    for cik_index, cik in enumerate(ciks, 1):
        offset = 0
        total = None
        while total is None or offset < total:
            query = urlencode(
                {
                    "q": "NVIDIA",
                    "dateRange": "custom",
                    "startdt": START_DATE,
                    "enddt": CUTOFF_DATE,
                    "forms": FORMS,
                    "ciks": cik,
                    "from": offset,
                    "size": 100,
                }
            )
            url = f"{SEARCH_URL}?{query}"
            retrieved_at = datetime.now(timezone.utc).isoformat()
            try:
                payload = json.loads(fetch(url))
            except RuntimeError as exc:
                access.append(
                    {
                        "url": url,
                        "cik": cik,
                        "retrieved_at": retrieved_at,
                        "status": "failed",
                        "reason": str(exc),
                        "result_count": 0,
                        "reported_total": None,
                        "access": "public_no_login",
                        "robots_or_access_bypass": False,
                    }
                )
                break
            page_hits = payload.get("hits", {}).get("hits") or []
            total_value = payload.get("hits", {}).get("total", {})
            total = int(total_value.get("value") or 0)
            access.append(
                {
                    "url": url,
                    "cik": cik,
                    "retrieved_at": retrieved_at,
                    "status": "processed",
                    "result_count": len(page_hits),
                    "reported_total": total,
                    "access": "public_no_login",
                    "robots_or_access_bypass": False,
                }
            )
            for hit in page_hits:
                hits[hit["_id"]] = hit
            if not page_hits:
                break
            offset += len(page_hits)
        if cik_index % 25 == 0:
            print(f"searched_ciks={cik_index}/{len(ciks)}", flush=True)
    return sorted(hits.values(), key=lambda item: item["_id"]), access


def document_url(cik: str, accession: str, filename: str) -> str:
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession.replace('-', '')}/{filename}"
    )


def visible_text(raw: bytes) -> str:
    decoded = raw.decode("utf-8", errors="replace")
    decoded = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", decoded)
    return SPACE_RE.sub(" ", html.unescape(TAG_RE.sub(" ", decoded))).strip()


def contexts(text: str, *, radius: int = 700) -> list[str]:
    values: list[str] = []
    for match in NVIDIA_RE.finditer(text):
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        excerpt = text[start:end].strip()
        if excerpt not in values:
            values.append(excerpt)
    return values


def collect(
    snapshot_path: Path,
    output_dir: Path,
    partner_universe_path: Path | None = None,
) -> dict[str, Any]:
    snapshot = read_json(snapshot_path)
    universe, cik_to_entities = (
        canonical_partner_universe(partner_universe_path)
        if partner_universe_path
        else partner_universe(snapshot)
    )
    hits, search_access = search_hits(sorted(cik_to_entities))
    selected_hits: list[dict[str, Any]] = []
    failed_search_ciks = {
        row["cik"]
        for row in search_access
        if row.get("status") == "failed" and row.get("cik")
    }
    for hit in hits:
        source = hit.get("_source") or {}
        matching_ciks = sorted(set(source.get("ciks") or []) & set(cik_to_entities))
        if matching_ciks and "0001045810" not in matching_ciks:
            selected_hits.append({**hit, "matching_partner_ciks": matching_ciks})

    documents: list[dict[str, Any]] = []
    mention_rows: list[dict[str, Any]] = []
    access_rows = list(search_access)
    hit_entities: set[str] = set()
    cached_documents = {
        row["document_id"]: row
        for row in (
            read_jsonl(output_dir / "filing_documents.jsonl")
            if (output_dir / "filing_documents.jsonl").is_file()
            else []
        )
    }
    cached_mentions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if (output_dir / "mention_contexts.jsonl").is_file():
        for row in read_jsonl(output_dir / "mention_contexts.jsonl"):
            cached_mentions[row["document_id"]].append(row)
    reused_documents = 0

    def retrieve_hit(hit: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]], dict[str, Any]]:
        source = hit["_source"]
        accession = source["adsh"]
        filename = hit["_id"].split(":", 1)[1]
        doc_id = stable_id("regdoc", accession, filename)
        entity_ids = sorted(
            {
                entity_id
                for cik in hit["matching_partner_ciks"]
                for entity_id in cik_to_entities[cik]
            }
        )
        if doc_id in cached_documents:
            document = dict(cached_documents[doc_id])
            document["entity_ids"] = entity_ids
            mentions = []
            for cached in cached_mentions.get(doc_id, []):
                mention = dict(cached)
                mention["entity_ids"] = entity_ids
                mentions.append(mention)
            return document, mentions, {
                "url": document["source_url"],
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "status": "reused_frozen_document_context",
                "access": "public_no_login",
                "robots_or_access_bypass": False,
            }
        raw: bytes | None = None
        url = ""
        used_cik = ""
        retrieval_error = None
        for cik in hit["matching_partner_ciks"]:
            candidate = document_url(cik, accession, filename)
            try:
                raw = fetch(candidate)
                url = candidate
                used_cik = cik
                break
            except RuntimeError as exc:
                retrieval_error = str(exc)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        if raw is None:
            return None, [], {
                "url": url or f"SEC accession {accession}/{filename}",
                "retrieved_at": retrieved_at,
                "status": "failed",
                "reason": retrieval_error,
                "access": "public_no_login",
                "robots_or_access_bypass": False,
            }
        text = visible_text(raw)
        excerpts = contexts(text)
        document = {
                "document_id": doc_id,
                "entity_ids": entity_ids,
                "cik": used_cik,
                "accession": accession,
                "filename": filename,
                "form": source.get("form"),
                "file_type": source.get("file_type"),
                "file_description": source.get("file_description"),
                "file_date": source.get("file_date"),
                "period_ending": source.get("period_ending"),
                "source_url": url,
                "publisher": "U.S. Securities and Exchange Commission",
                "retrieved_at": retrieved_at,
                "content_sha256": hashlib.sha256(raw).hexdigest(),
                "mention_count": len(excerpts),
                "access": "public_no_login",
                "redistribution": "structured facts and short excerpts only",
            }
        mentions = []
        for ordinal, excerpt in enumerate(excerpts, 1):
            mentions.append(
                {
                    "mention_id": stable_id("regmention", doc_id, ordinal, excerpt),
                    "document_id": doc_id,
                    "entity_ids": entity_ids,
                    "form": source.get("form"),
                    "file_date": source.get("file_date"),
                    "source_url": url,
                    "evidence_locator": f"NVIDIA occurrence {ordinal} of {len(excerpts)}",
                    "excerpt": excerpt,
                    "review_status": "pending_direction_review",
                }
            )
        access = {
                "url": url,
                "retrieved_at": retrieved_at,
                "status": "processed",
                "bytes": len(raw),
                "access": "public_no_login",
                "robots_or_access_bypass": False,
            }
        return document, mentions, access

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(retrieve_hit, hit) for hit in selected_hits]
        for index, future in enumerate(as_completed(futures), 1):
            document, mentions, access = future.result()
            access_rows.append(access)
            if document is not None:
                if access["status"] == "reused_frozen_document_context":
                    reused_documents += 1
                documents.append(document)
                mention_rows.extend(mentions)
                hit_entities.update(document["entity_ids"])
            if index % 50 == 0:
                print(f"downloaded={index}/{len(selected_hits)}", flush=True)

    documents.sort(key=lambda item: item["document_id"])
    mention_rows.sort(key=lambda item: item["mention_id"])
    access_rows.sort(key=lambda item: (str(item.get("url")), str(item.get("retrieved_at"))))

    frontier: list[dict[str, Any]] = []
    for row in universe:
        ciks = row["ciks"]
        if row["entity_id"] in hit_entities:
            status = "regulatory_hit_pending_review"
        elif set(ciks) & failed_search_ciks:
            status = "public_regulator_search_failed"
        elif ciks:
            status = "searched_no_nvidia_hit"
        else:
            status = "non_sec_route_required"
        frontier.append(
            {
                "entity_id": row["entity_id"],
                "display_name": row["display_name"],
                "ciks": ciks,
                "listing_regions": row["listing_regions"],
                "terminal_status": status,
                "query": 'exact full-text term "NVIDIA"; forms=' + FORMS,
                "date_from": START_DATE,
                "date_to": CUTOFF_DATE,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "sec_search_hits.jsonl", selected_hits)
    write_jsonl(output_dir / "filing_documents.jsonl", documents)
    write_jsonl(output_dir / "mention_contexts.jsonl", mention_rows)
    write_jsonl(output_dir / "source_frontier.jsonl", frontier)
    write_jsonl(output_dir / "access_audit.jsonl", access_rows)
    summary = {
        "pass": True,
        "snapshot": str(snapshot_path),
        "partner_entity_ids": len(universe),
        "partner_entities_with_cik": sum(bool(row["ciks"]) for row in universe),
        "efts_matching_documents": len(selected_hits),
        "retrieved_documents": len(documents),
        "mention_contexts": len(mention_rows),
        "partner_entities_with_hits": len(hit_entities),
        "frontier_status_counts": {
            status: sum(row["terminal_status"] == status for row in frontier)
            for status in sorted({row["terminal_status"] for row in frontier})
        },
        "pending_direction_review": len(mention_rows),
        "reused_frozen_documents": reused_documents,
        "access_control_bypass": False,
    }
    write_json(output_dir / "collection_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--snapshot", type=Path, default=Path("data/snapshot_2026-08-25.json")
    )
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument(
        "--partner-universe",
        type=Path,
        default=Path(
            "runs/2026-08-25-run-003/agents/partner_regulatory_entity_normalization/"
            "canonical_partner_universe_with_cik.jsonl"
        ),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            collect(args.snapshot, args.output_dir, args.partner_universe), indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
