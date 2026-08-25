#!/usr/bin/env python3
"""Conservative NVIDIA Partner Network collector.

The collector is fail-closed: it will not request the directory unless
robots.txt is successfully retrieved and permits the directory URL. It uses
only ordinary public GET requests, no authentication, browser fingerprinting,
CAPTCHA handling, proxying, or retry loops intended to defeat access controls.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
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


PUBLISHER = "NVIDIA Corporation"
BASE = "https://marketplace.nvidia.com"
ROBOTS_URL = f"{BASE}/robots.txt"
DIRECTORY_PATH = "/en-us/enterprise/partners/"
USER_AGENT = "arti-research/1.0 (public-market-research; no-auth)"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def fetch(url: str, timeout: float) -> tuple[bytes, dict]:
    requested_at = now()
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.5",
            "Accept-Language": "en-US,en;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            return body, {
                "url": url,
                "requested_at": requested_at,
                "fetched_at": now(),
                "status": "success",
                "http_status": response.status,
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type"),
                "content_sha256": sha256(body),
                "bytes": len(body),
            }
    except HTTPError as exc:
        body = exc.read()
        return body, {
            "url": url,
            "requested_at": requested_at,
            "fetched_at": now(),
            "status": "http_error",
            "http_status": exc.code,
            "error": str(exc),
            "content_sha256": sha256(body),
            "bytes": len(body),
        }
    except (URLError, TimeoutError, OSError) as exc:
        return b"", {
            "url": url,
            "requested_at": requested_at,
            "fetched_at": now(),
            "status": "network_error",
            "http_status": None,
            "error": f"{type(exc).__name__}: {exc}",
            "content_sha256": sha256(b""),
            "bytes": 0,
        }


def visible_text(document: str) -> str:
    document = re.sub(r"(?is)<script\b.*?</script>", " ", document)
    document = re.sub(r"(?is)<style\b.*?</style>", " ", document)
    document = re.sub(r"(?s)<[^>]+>", " ", document)
    return re.sub(r"\s+", " ", html.unescape(document)).strip()


def discover_total(document: str) -> int | None:
    text = visible_text(document)
    match = re.search(r"\bof\s+([0-9][0-9,]*)\s+items\b", text, flags=re.I)
    if match:
        return int(match.group(1).replace(",", ""))
    for pattern in (r'"total(?:Items|Count)?"\s*:\s*(\d+)', r'"count"\s*:\s*(\d+)'):
        values = [int(value) for value in re.findall(pattern, document, flags=re.I)]
        if values:
            return max(values)
    return None


def script_json_values(document: str) -> list[object]:
    values: list[object] = []
    pattern = re.compile(r"(?is)<script\b[^>]*type=[\"']application/(?:ld\+)?json[\"'][^>]*>(.*?)</script>")
    for payload in pattern.findall(document):
        try:
            values.append(json.loads(html.unescape(payload).strip()))
        except (json.JSONDecodeError, TypeError):
            continue
    return values


def listify(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("label") or item.get("value")
                if isinstance(name, str) and name.strip():
                    result.append(name.strip())
        return result
    return []


def pick(obj: dict, *keys: str) -> object:
    lower = {str(key).lower(): value for key, value in obj.items()}
    for key in keys:
        if key.lower() in lower:
            return lower[key.lower()]
    return None


def extract_partner_objects(value: object, page_url: str, page_sha: str, page_no: int) -> list[dict]:
    rows: list[dict] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            name = pick(node, "partnerName", "companyName", "name", "title")
            partner_types = listify(pick(node, "partnerTypes", "partnerType", "partner_type"))
            competencies = listify(pick(node, "competencies", "partnerCompetencies", "partner_competencies"))
            specializations = listify(pick(node, "specializations", "specialization"))
            if isinstance(name, str) and name.strip() and (partner_types or competencies or specializations):
                listing_id = pick(node, "listingId", "partnerId", "id", "uuid")
                profile_url = pick(node, "profileUrl", "url", "link", "href")
                row = {
                    "observation_id": f"npn-json-{page_no}-{sha256((str(listing_id) + name).encode())[:16]}",
                    "listing_id": str(listing_id) if listing_id is not None else None,
                    "name": name.strip(),
                    "profile_url": profile_url if isinstance(profile_url, str) else None,
                    "partner_types": partner_types,
                    "competencies": competencies,
                    "specializations": specializations,
                    "partner_level": pick(node, "partnerLevel", "level", "tier"),
                    "locations": listify(pick(node, "locations", "location", "countries", "regions")),
                    "product_service_tags": listify(pick(node, "products", "services", "productServiceTags")),
                    "source_url": page_url,
                    "publisher": PUBLISHER,
                    "fetched_at": now(),
                    "evidence_locator": f"embedded application/json object, directory page {page_no}",
                    "source_content_sha256": page_sha,
                    "collection_method": "public_directory_embedded_json",
                }
                rows.append(row)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return rows


def build_tags(rows: list[dict]) -> list[dict]:
    output: list[dict] = []
    tag_fields = ("partner_types", "competencies", "specializations", "locations", "product_service_tags")
    for row in rows:
        for field in tag_fields:
            for tag in row.get(field, []):
                output.append({
                    "observation_id": f"tag-{sha256((row['observation_id'] + field + tag).encode())[:20]}",
                    "listing_observation_id": row["observation_id"],
                    "tag_class": field,
                    "tag_value": tag,
                    "source_url": row["source_url"],
                    "evidence_locator": row["evidence_locator"],
                    "source_content_sha256": row["source_content_sha256"],
                    "provenance_status": "direct",
                })
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--locale", default="en-us")
    parser.add_argument("--page-size", type=int, default=15)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z]{2}-[a-z]{2}", args.locale):
        parser.error("locale must look like en-us")
    if not 1 <= args.page_size <= 100:
        parser.error("page-size must be between 1 and 100")
    if args.delay_seconds < 1.0:
        parser.error("delay-seconds must be at least 1.0")

    args.out.mkdir(parents=True, exist_ok=True)
    snapshots = args.out / "snapshots"
    snapshots.mkdir(exist_ok=True)
    access: list[dict] = []
    pages: list[dict] = []

    robots_body, robots_audit = fetch(ROBOTS_URL, args.timeout_seconds)
    robots_audit["access_purpose"] = "robots_policy_check"
    access.append(robots_audit)
    write_jsonl(args.out / "access_audit.jsonl", access)
    if robots_audit["status"] != "success" or robots_audit["http_status"] != 200:
        write_json(args.out / "validation_report.json", {
            "complete": False,
            "failure_gate": "robots_unavailable_fail_closed",
            "runtime_total": None,
            "unique_listings": 0,
            "pending": 0,
            "generated_at": now(),
        })
        return 2

    robots_text = robots_body.decode("utf-8", errors="replace")
    (snapshots / "robots.txt").write_text(robots_text, encoding="utf-8")
    parser_robots = RobotFileParser()
    parser_robots.set_url(ROBOTS_URL)
    parser_robots.parse(robots_text.splitlines())
    first_url = f"{BASE}{DIRECTORY_PATH}?{urlencode({'locale': args.locale, 'page': 1, 'limit': args.page_size})}"
    if not parser_robots.can_fetch(USER_AGENT, first_url):
        access.append({"url": first_url, "fetched_at": now(), "status": "blocked_by_robots", "access_purpose": "directory_collection"})
        write_jsonl(args.out / "access_audit.jsonl", access)
        write_json(args.out / "validation_report.json", {
            "complete": False,
            "failure_gate": "robots_disallow",
            "runtime_total": None,
            "unique_listings": 0,
            "pending": 0,
            "generated_at": now(),
        })
        return 3

    first_body, first_audit = fetch(first_url, args.timeout_seconds)
    first_audit["access_purpose"] = "directory_collection"
    access.append(first_audit)
    if first_audit["status"] != "success" or first_audit["http_status"] != 200:
        write_jsonl(args.out / "access_audit.jsonl", access)
        write_json(args.out / "validation_report.json", {
            "complete": False,
            "failure_gate": "entrypoint_unavailable",
            "runtime_total": None,
            "unique_listings": 0,
            "pending": 0,
            "generated_at": now(),
        })
        return 4

    first_doc = first_body.decode("utf-8", errors="replace")
    runtime_total = discover_total(first_doc)
    if runtime_total is None:
        write_jsonl(args.out / "access_audit.jsonl", access)
        write_json(args.out / "validation_report.json", {
            "complete": False,
            "failure_gate": "runtime_total_not_discoverable",
            "runtime_total": None,
            "unique_listings": 0,
            "pending": 0,
            "generated_at": now(),
        })
        return 5

    total_pages = math.ceil(runtime_total / args.page_size)
    extracted: list[dict] = []
    seen_page_hashes: set[str] = set()
    for page_no in range(1, total_pages + 1):
        page_url = f"{BASE}{DIRECTORY_PATH}?{urlencode({'locale': args.locale, 'page': page_no, 'limit': args.page_size})}"
        if not parser_robots.can_fetch(USER_AGENT, page_url):
            pages.append({"page": page_no, "url": page_url, "status": "blocked_by_robots"})
            continue
        if page_no == 1:
            body, audit = first_body, first_audit
        else:
            time.sleep(args.delay_seconds)
            body, audit = fetch(page_url, args.timeout_seconds)
            audit["access_purpose"] = "directory_collection"
            access.append(audit)
        if audit["status"] != "success" or audit["http_status"] != 200:
            pages.append({"page": page_no, "url": page_url, "status": "inaccessible", "audit": audit})
            continue
        digest = sha256(body)
        with gzip.open(snapshots / f"page_{page_no:04d}.html.gz", "wb") as handle:
            handle.write(body)
        document = body.decode("utf-8", errors="replace")
        page_rows: list[dict] = []
        for value in script_json_values(document):
            page_rows.extend(extract_partner_objects(value, page_url, digest, page_no))
        pages.append({
            "page": page_no,
            "url": page_url,
            "status": "processed",
            "content_sha256": digest,
            "duplicate_page_hash": digest in seen_page_hashes,
            "extracted_observations": len(page_rows),
        })
        seen_page_hashes.add(digest)
        extracted.extend(page_rows)

    dedup: dict[str, dict] = {}
    for row in extracted:
        key = row.get("listing_id") or f"{row['name']}|{row.get('profile_url')}"
        dedup.setdefault(key, row)
    rows = list(dedup.values())
    tags = build_tags(rows)
    groups = []
    edges = []
    for row in rows:
        group_id = f"unresolved-{sha256(row['name'].casefold().encode())[:16]}"
        groups.append({
            "group_id": group_id,
            "canonical_name": row["name"],
            "resolution_status": "unresolved_requires_human_counterparty_research",
            "listed_entity_status": "unknown",
            "listing_observation_ids": [row["observation_id"]],
        })
        edges.append({
            "listing_observation_id": row["observation_id"],
            "group_id": group_id,
            "mapping_status": "unresolved",
            "reason": "Collector does not infer corporate groups from name similarity alone.",
        })

    write_jsonl(args.out / "access_audit.jsonl", access)
    write_jsonl(args.out / "pagination_manifest.jsonl", pages)
    write_jsonl(args.out / "raw_listings.jsonl", rows)
    write_jsonl(args.out / "tag_observations.jsonl", tags)
    write_jsonl(args.out / "entity_groups.jsonl", groups)
    write_jsonl(args.out / "listing_group_edges.jsonl", edges)
    processed_pages = sum(page["status"] == "processed" for page in pages)
    complete = (
        processed_pages == total_pages
        and len(rows) == runtime_total
        and len(pages) == total_pages
        and all(page["status"] == "processed" for page in pages)
        and all(row.get("source_content_sha256") for row in rows)
    )
    write_json(args.out / "validation_report.json", {
        "complete": complete,
        "runtime_total": runtime_total,
        "unique_listings": len(rows),
        "expected_pages": total_pages,
        "processed_pages": processed_pages,
        "all_raw_listings_grouped_or_unresolved": len(edges) == len(rows),
        "tag_provenance_complete": all(tag.get("source_content_sha256") for tag in tags),
        "pending": 0,
        "failure_gate": None if complete else "runtime_total_or_page_reconciliation_failed",
        "generated_at": now(),
    })
    return 0 if complete else 6


if __name__ == "__main__":
    raise SystemExit(main())
