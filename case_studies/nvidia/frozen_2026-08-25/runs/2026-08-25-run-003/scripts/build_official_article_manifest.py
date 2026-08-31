#!/usr/bin/env python3
"""Freeze NVIDIA Newsroom's public archive into reproducible article manifests.

The archive intentionally contains both Newsroom press releases and links to the
NVIDIA Blog.  We enumerate by publication year, retain the archive observation,
and write one canonical row per URL.  Source HTML is stored gzip-compressed so a
reviewer can audit the enumeration without hitting the live site again.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


BASE = "https://nvidianews.nvidia.com/news"
USER_AGENT = "listed-company-network-research/1.0 (public research; contact: repository README)"
ARTICLE_RE = re.compile(r'<article class="index-item[^>]*>(.*?)</article>', re.S | re.I)
DATE_RE = re.compile(r'index-item-text-info-date[^>]*>(.*?)</span>', re.S | re.I)
TITLE_RE = re.compile(
    r'index-item-text-title[^>]*>\s*<a\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.S | re.I,
)
DESCRIPTION_RE = re.compile(r'index-item-text-description[^>]*>(.*?)</div>', re.S | re.I)
READ_RE = re.compile(r'index-item-text-link[^>]*>\s*<a\s+[^>]*>(.*?)</a>', re.S | re.I)
PAGING_RE = re.compile(
    r'href="\?page=(\d+)&amp;year=\d+"[^>]*title="(?:View results for page \d+|Last page of results)"',
    re.I,
)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def clean(fragment: str) -> str:
    return SPACE_RE.sub(" ", html.unescape(TAG_RE.sub(" ", fragment))).strip()


def canonicalize(raw_url: str) -> str:
    absolute = urljoin(BASE, html.unescape(raw_url))
    parts = urlsplit(absolute)
    host = parts.netloc.lower()
    path = re.sub(r"/{2,}", "/", parts.path)
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(("https", host, path, "", ""))


def fetch(url: str, attempts: int = 6) -> tuple[bytes, str]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
            with urlopen(request, timeout=45) as response:
                return response.read(), response.headers.get_content_charset() or "utf-8"
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def parse_page(raw: bytes, charset: str, archive_url: str, page: int, year: int) -> tuple[list[dict], int]:
    text = raw.decode(charset, errors="replace")
    last_pages = [int(value) for value in PAGING_RE.findall(text)]
    last_page = max(last_pages, default=1)
    rows: list[dict] = []
    for position, block in enumerate(ARTICLE_RE.findall(text), start=1):
        date_match = DATE_RE.search(block)
        title_match = TITLE_RE.search(block)
        if not date_match or not title_match:
            raise ValueError(f"unparseable article at {archive_url} position {position}")
        published = datetime.strptime(clean(date_match.group(1)), "%B %d, %Y").date()
        url = canonicalize(title_match.group(1))
        description_match = DESCRIPTION_RE.search(block)
        read_match = READ_RE.search(block)
        read_label = clean(read_match.group(1)) if read_match else ""
        host = urlsplit(url).netloc
        if host == "blogs.nvidia.com" or "Blog" in read_label:
            article_type = "blog"
            publisher = "NVIDIA Blog"
        elif host == "nvidianews.nvidia.com" or "Press Release" in read_label:
            article_type = "press_release"
            publisher = "NVIDIA Newsroom"
        else:
            article_type = "unknown"
            publisher = "NVIDIA"
        rows.append(
            {
                "article_id": "article_" + hashlib.sha256(url.encode()).hexdigest()[:16],
                "canonical_url": url,
                "title": clean(title_match.group(2)),
                "published_date": published.isoformat(),
                "publisher": publisher,
                "article_type": article_type,
                "archive_observation": {
                    "archive_url": archive_url,
                    "archive_year": year,
                    "archive_page": page,
                    "position": position,
                    "read_label": read_label,
                    "description": clean(description_match.group(1)) if description_match else "",
                    "evidence_locator": f"article.index-item[{position}]",
                },
                "access": {
                    "access_class": "public_no_login",
                    "robots_checked_url": "https://nvidianews.nvidia.com/robots.txt",
                    "robots_result": "archive path not disallowed as of cutoff run",
                    "license_note": "Copyright remains with publisher; stored for research/audit, no republication grant inferred.",
                },
                "processing_status": "pending_body_review",
            }
        )
    return rows, last_page


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--years", type=int, nargs="+", default=[2025, 2026])
    parser.add_argument("--cutoff", default="2026-08-25")
    parser.add_argument("--delay", type=float, default=0.75)
    args = parser.parse_args()

    output = args.output.resolve()
    snapshots = output / "source_pages"
    snapshots.mkdir(parents=True, exist_ok=True)
    cutoff = date.fromisoformat(args.cutoff)
    fetched_at = datetime.now(timezone.utc).isoformat()
    observations: list[dict] = []
    page_rows: list[dict] = []

    for year in args.years:
        page = 1
        expected_last = None
        while expected_last is None or page <= expected_last:
            archive_url = f"{BASE}?page={page}&year={year}"
            snapshot_name = f"news_{year}_{page:03d}.html.gz"
            snapshot_path = snapshots / snapshot_name
            reused_snapshot = snapshot_path.exists()
            if reused_snapshot:
                with gzip.open(snapshot_path, "rb") as handle:
                    raw = handle.read()
                charset = "utf-8"
                parsed, found_last = parse_page(raw, charset, archive_url, page, year)
            else:
                for content_attempt in range(5):
                    raw, charset = fetch(archive_url)
                    parsed, found_last = parse_page(raw, charset, archive_url, page, year)
                    # Some overload responses are HTTP 200 but contain no archive.
                    if parsed and found_last >= page:
                        break
                    if content_attempt == 4:
                        raise RuntimeError(
                            f"archive content unavailable after retries: {archive_url}; "
                            f"items={len(parsed)}, max_visible_page={found_last}"
                        )
                    time.sleep(min(20, 5 * (content_attempt + 1)))
            if expected_last is None:
                expected_last = found_last
            elif found_last != expected_last:
                raise ValueError(f"pagination drift for {year}: {expected_last} -> {found_last}")
            if not reused_snapshot:
                with gzip.open(snapshot_path, "wb", compresslevel=9) as handle:
                    handle.write(raw)
            digest = hashlib.sha256(raw).hexdigest()
            page_rows.append(
                {
                    "archive_url": archive_url,
                    "year": year,
                    "page": page,
                    "expected_last_page": expected_last,
                    "item_count": len(parsed),
                    "fetched_at": fetched_at,
                    "sha256": digest,
                    "snapshot_path": f"source_pages/{snapshot_name}",
                    "http_content_charset": charset,
                    "reused_snapshot_from_interrupted_same_cutoff_run": reused_snapshot,
                }
            )
            observations.extend(parsed)
            page += 1
            if page <= expected_last:
                time.sleep(args.delay)

    by_url: dict[str, dict] = {}
    duplicate_observations: list[dict] = []
    for row in observations:
        url = row["canonical_url"]
        if url in by_url:
            duplicate_observations.append(row)
            existing = by_url[url]
            existing.setdefault("additional_archive_observations", []).append(row["archive_observation"])
            if row["published_date"] != existing["published_date"]:
                existing.setdefault("date_conflicts", []).append(row["published_date"])
        else:
            by_url[url] = row

    rows = sorted(by_url.values(), key=lambda item: (item["published_date"], item["canonical_url"]))
    included = [row for row in rows if date.fromisoformat(row["published_date"]) <= cutoff]
    future_excluded = [row for row in rows if date.fromisoformat(row["published_date"]) > cutoff]
    lower = date(min(args.years), 1, 1)
    if any(date.fromisoformat(row["published_date"]) < lower for row in rows):
        raise ValueError("archive returned a row before requested year range")

    write_jsonl(output / "official_articles.jsonl", included)
    write_jsonl(output / "newsroom_press_releases.jsonl", [r for r in included if r["article_type"] == "press_release"])
    write_jsonl(output / "nvidia_blog_articles.jsonl", [r for r in included if r["article_type"] == "blog"])
    write_jsonl(output / "unknown_type_articles.jsonl", [r for r in included if r["article_type"] == "unknown"])
    write_jsonl(output / "archive_pages.jsonl", page_rows)
    write_jsonl(output / "duplicate_archive_observations.jsonl", duplicate_observations)
    write_jsonl(output / "after_cutoff_exclusions.jsonl", future_excluded)

    counts = {
        "generated_at": fetched_at,
        "cutoff_date_inclusive": cutoff.isoformat(),
        "years": args.years,
        "archive_pages": len(page_rows),
        "raw_archive_observations": len(observations),
        "canonical_articles_before_cutoff_filter": len(rows),
        "included_articles": len(included),
        "newsroom_press_releases": sum(r["article_type"] == "press_release" for r in included),
        "nvidia_blog_articles": sum(r["article_type"] == "blog" for r in included),
        "unknown_type_articles": sum(r["article_type"] == "unknown" for r in included),
        "duplicate_archive_observations": len(duplicate_observations),
        "after_cutoff_exclusions": len(future_excluded),
        "pages_with_zero_items": [r["archive_url"] for r in page_rows if r["item_count"] == 0],
        "pending_body_review": len(included),
    }
    (output / "manifest_summary.json").write_text(
        json.dumps(counts, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(counts, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
