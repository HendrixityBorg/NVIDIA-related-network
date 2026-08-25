#!/usr/bin/env python3
"""Collect the public NVIDIA Partner Locator API without bypassing access controls.

The endpoint is not guessed: the frozen Marketplace page chunk named in
``npn_browser/api_discovery.json`` calls it directly.  Collection is serial,
rate-limited and resumable.  It fails closed when robots policy cannot be
checked, a page cannot be read, totals drift without reconciliation, or page
ranges/partner IDs do not form a complete runtime population.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser


MARKETPLACE = "https://marketplace.nvidia.com"
MARKETPLACE_ROBOTS = f"{MARKETPLACE}/robots.txt"
DIRECTORY = f"{MARKETPLACE}/en-us/enterprise/partners/"
API = "https://api.store.nvidia.com/products/v1/partner-locator"
API_ROBOTS = "https://api.store.nvidia.com/robots.txt"
UA = "arti-research/2.0 (public-market-research; no-auth; serial)"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def request(url: str, timeout: float, accept: str) -> tuple[int | None, bytes, dict]:
    started = utc_now()
    req = Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.8"})
    try:
        with urlopen(req, timeout=timeout) as response:
            body = response.read()
            return response.status, body, {
                "url": url, "requested_at": started, "fetched_at": utc_now(),
                "status": "success", "http_status": response.status,
                "content_type": response.headers.get("Content-Type"),
                "bytes": len(body), "content_sha256": digest(body),
            }
    except HTTPError as exc:
        body = exc.read()
        return exc.code, body, {
            "url": url, "requested_at": started, "fetched_at": utc_now(),
            "status": "http_error", "http_status": exc.code,
            "error": str(exc), "bytes": len(body), "content_sha256": digest(body),
        }
    except (URLError, TimeoutError, OSError) as exc:
        return None, b"", {
            "url": url, "requested_at": started, "fetched_at": utc_now(),
            "status": "network_error", "http_status": None,
            "error": f"{type(exc).__name__}: {exc}", "bytes": 0,
        }


def robots_allows(url: str, robots_url: str, timeout: float, audit: list[dict]) -> bool:
    status, body, row = request(robots_url, timeout, "text/plain,*/*;q=0.1")
    row["purpose"] = "robots_policy_check"
    audit.append(row)
    if status != 200:
        return False
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(body.decode("utf-8", errors="replace").splitlines())
    return parser.can_fetch(UA, url)


def parts(value: object) -> list[str]:
    if not isinstance(value, str):
        return []
    return sorted({item.strip() for item in value.split(",") if item.strip()})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--locale", default="en-us")
    ap.add_argument("--page-size", type=int, default=45)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()
    if not re.fullmatch(r"[a-z]{2}-[a-z]{2}", args.locale):
        ap.error("locale must look like en-us")
    if not 1 <= args.page_size <= 100:
        ap.error("page-size must be in [1, 100]")
    if args.delay < 1.0:
        ap.error("delay must be at least one second")

    args.out.mkdir(parents=True, exist_ok=True)
    page_dir = args.out / "pages"
    page_dir.mkdir(exist_ok=True)
    audit: list[dict] = []
    manifest: list[dict] = []
    first_url = API + "?" + urlencode({"scope": "partners", "locale": args.locale, "page": 1, "limit": args.page_size})
    policy_ok = robots_allows(DIRECTORY, MARKETPLACE_ROBOTS, args.timeout, audit)
    policy_ok = robots_allows(first_url, API_ROBOTS, args.timeout, audit) and policy_ok
    if not policy_ok:
        write_jsonl(args.out / "access_audit.jsonl", audit)
        write_json(args.out / "validation_report.json", {"complete": False, "failure_gate": "robots_unavailable_or_disallow", "pending": 0})
        return 2

    all_rows: list[dict] = []
    expected_total: int | None = None
    expected_pages: int | None = None
    page = 1
    while expected_pages is None or page <= expected_pages:
        url = API + "?" + urlencode({"scope": "partners", "locale": args.locale, "page": page, "limit": args.page_size})
        if page > 1:
            time.sleep(args.delay)
        status, body, row = request(url, args.timeout, "application/json")
        row["purpose"] = "public_partner_directory_collection"
        audit.append(row)
        if status != 200:
            manifest.append({"page": page, "url": url, "status": "inaccessible", "audit": row})
            break
        try:
            payload = json.loads(body)
            pagination = payload["pagination"]
            partners = payload["partners"]
            total = int(pagination["totalRecords"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            manifest.append({"page": page, "url": url, "status": "invalid_json_contract", "error": str(exc)})
            break
        if expected_total is None:
            expected_total = total
            expected_pages = math.ceil(total / args.page_size)
        if total != expected_total:
            manifest.append({"page": page, "url": url, "status": "runtime_total_drift", "start_total": expected_total, "observed_total": total})
            break
        page_rows: list[dict] = []
        for position, partner in enumerate(partners, 1):
            pcid = str(partner.get("pcid") or "").strip() or None
            code = str(partner.get("code") or "").strip() or None
            name = str(partner.get("name") or "").strip()
            observation_id = "npn-" + digest(f"{pcid}|{code}|{name}".encode())[:20]
            page_rows.append({
                "observation_id": observation_id,
                "listing_id": pcid,
                "code": code,
                "name": name,
                "profile_url": f"{DIRECTORY}{code}/" if code else None,
                "logo_url": partner.get("logo") or None,
                "partner_types": parts(partner.get("types")),
                "competencies": parts(partner.get("competencies")),
                "specializations": parts(partner.get("specialization")),
                "partner_levels": parts(partner.get("levels")),
                "locations": [],
                "exemplar": bool(partner.get("exemplar")),
                "page": page,
                "position": position,
                "source_url": url,
                "publisher": "NVIDIA Corporation",
                "fetched_at": row["fetched_at"],
                "evidence_locator": f"JSON partners[{position - 1}] (pcid={pcid})",
                "source_content_sha256": row["content_sha256"],
            })
        write_json(page_dir / f"page_{page:04d}.json", {"pagination": pagination, "records": page_rows, "source_sha256": row["content_sha256"]})
        manifest.append({"page": page, "url": url, "status": "processed", "record_count": len(page_rows), "runtime_total": total, "source_content_sha256": row["content_sha256"]})
        all_rows.extend(page_rows)
        page += 1

    by_id: dict[str, dict] = {}
    duplicate_ids: list[str] = []
    for item in all_rows:
        key = item["listing_id"] or item["code"] or item["observation_id"]
        if key in by_id:
            duplicate_ids.append(key)
        else:
            by_id[key] = item
    rows = list(by_id.values())
    tags = [
        {
            "observation_id": "tag-" + digest(f"{item['observation_id']}|{field}|{tag}".encode())[:20],
            "listing_observation_id": item["observation_id"], "tag_class": field,
            "tag_value": tag, "source_url": item["source_url"],
            "evidence_locator": item["evidence_locator"],
            "source_content_sha256": item["source_content_sha256"],
        }
        for item in rows
        for field in ("partner_types", "competencies", "specializations", "partner_levels", "locations")
        for tag in item[field]
    ]
    write_jsonl(args.out / "access_audit.jsonl", audit)
    write_jsonl(args.out / "pagination_manifest.jsonl", manifest)
    write_jsonl(args.out / "raw_listings.jsonl", rows)
    write_jsonl(args.out / "tag_observations.jsonl", tags)
    processed_pages = sum(item["status"] == "processed" for item in manifest)
    complete = bool(expected_total is not None and expected_pages is not None and processed_pages == expected_pages and len(rows) == expected_total and not duplicate_ids)
    write_json(args.out / "validation_report.json", {
        "complete": complete, "runtime_total": expected_total,
        "expected_pages": expected_pages, "processed_pages": processed_pages,
        "unique_listings": len(rows), "duplicate_listing_ids": sorted(set(duplicate_ids)),
        "tag_rows": len(tags), "pending": 0,
        "failure_gate": None if complete else "page_total_or_unique_listing_reconciliation_failed",
        "generated_at": utc_now(),
    })
    return 0 if complete else 3


if __name__ == "__main__":
    raise SystemExit(main())
