#!/usr/bin/env python3
"""Collect the strictly scoped NVIDIA filings and presentation sources.

The script intentionally does not enumerate 10-Q, 8-K or the general IR archive.
SEC submissions metadata is used only to verify the frozen accession numbers; the
research source records are the 10-K document and 13F filing/table themselves.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

from pypdf import PdfReader


CUTOFF = "2026-08-25"
ACCESSED_AT = "2026-08-25T00:00:00+08:00"
USER_AGENT = "listed-company-network-research/1.0 research@example.invalid"

SOURCES = [
    {
        "source_id": "FP-S001",
        "kind": "10-k",
        "title": "NVIDIA FY2026 Form 10-K",
        "publisher": "NVIDIA Corporation / U.S. SEC",
        "published_at": "2026-02-25",
        "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm",
        "filename": "nvda-20260125.htm",
    },
    {
        "source_id": "FP-S002",
        "kind": "13f-primary",
        "title": "NVIDIA 13F-HR cover for quarter ended 2026-06-30",
        "publisher": "NVIDIA Corporation / U.S. SEC",
        "published_at": "2026-08-14",
        "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000065/primary_doc.xml",
        "filename": "13f_2026q2_primary.xml",
    },
    {
        "source_id": "FP-S003",
        "kind": "13f-table",
        "title": "NVIDIA 13F information table for quarter ended 2026-06-30",
        "publisher": "NVIDIA Corporation / U.S. SEC",
        "published_at": "2026-08-14",
        "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000065/information_table.xml",
        "filename": "13f_2026q2_information_table.xml",
    },
    {
        "source_id": "FP-S004",
        "kind": "presentation-pdf",
        "title": "GTC 2025 Keynote",
        "publisher": "NVIDIA Corporation",
        "published_at": "2025-03-18",
        "url": "https://s201.q4cdn.com/141608511/files/doc_downloads/2025/03/GTC2025_Keynote.pdf",
        "filename": "gtc_2025_keynote.pdf",
    },
    {
        "source_id": "FP-S005",
        "kind": "presentation-pdf",
        "title": "GTC Taipei / COMPUTEX 2025 Keynote",
        "publisher": "NVIDIA Corporation",
        "published_at": "2025-05-19",
        "url": "https://s201.q4cdn.com/141608511/files/doc_events/2025/May/19/GTC-Taipei-Computex-25-Keynote.pdf",
        "filename": "gtc_taipei_computex_2025.pdf",
    },
    {
        "source_id": "FP-S006",
        "kind": "presentation-pdf",
        "title": "GTC Paris 2025 Keynote",
        "publisher": "NVIDIA Corporation",
        "published_at": "2025-06-11",
        "url": "https://s201.q4cdn.com/141608511/files/doc_events/2025/Jun/11/GTC-Paris-2025-Keynote.pdf",
        "filename": "gtc_paris_2025.pdf",
    },
    {
        "source_id": "FP-S007",
        "kind": "presentation-pdf",
        "title": "GTC Washington, D.C. 2025 Keynote",
        "publisher": "NVIDIA Corporation",
        "published_at": "2025-10-28",
        "url": "https://s201.q4cdn.com/141608511/files/doc_events/2025/Oct/28/gtc-dc-2025.pdf",
        "filename": "gtc_dc_2025.pdf",
    },
    {
        "source_id": "FP-S008",
        "kind": "presentation-pdf",
        "title": "COMPUTEX 2026 Keynote",
        "publisher": "NVIDIA Corporation",
        "published_at": "2026-06-01",
        "url": "https://s201.q4cdn.com/141608511/files/doc_events/2026/Jun/01/JHH-Computex-2026-Keynote.pdf",
        "filename": "computex_2026_keynote.pdf",
    },
    {
        "source_id": "FP-S009",
        "kind": "presentation-pdf",
        "title": "NVIDIA July 2026 NDR",
        "publisher": "NVIDIA Corporation",
        "published_at": "2026-07-07",
        "url": "https://s201.q4cdn.com/141608511/files/doc_presentations/2026/07/NDR_July2026_.pdf",
        "filename": "ndr_july_2026.pdf",
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fetch(url: str, path: Path) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read()
        status = response.status
        content_type = response.headers.get("Content-Type", "")
    path.write_bytes(body)
    return status, content_type


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    raw = root / "source_files"
    raw.mkdir(exist_ok=True)
    frontier = []
    for index, spec in enumerate(SOURCES):
        path = raw / spec["filename"]
        status = 200
        content_type = "application/pdf" if spec["filename"].endswith(".pdf") else "application/octet-stream"
        if args.refresh or not path.exists():
            status, content_type = fetch(spec["url"], path)
            time.sleep(0.12 if "sec.gov" in spec["url"] else 0.02)
        record = {
            **spec,
            "cutoff": CUTOFF,
            "retrieved_at": ACCESSED_AT,
            "access_state": "processed",
            "http_status": status,
            "content_type": content_type,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "access_restrictions": "Public URL; no login, paywall, CAPTCHA or access-control bypass used. SEC requests identify a research user agent.",
            "local_path": str(path.relative_to(root)),
        }
        if spec["kind"] == "presentation-pdf":
            reader = PdfReader(path)
            record["page_count"] = len(reader.pages)
            record["pdf_page_numbering"] = "1-based physical PDF page"
        frontier.append(record)
    with (root / "source_frontier.jsonl").open("w", encoding="utf-8") as fh:
        for record in frontier:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"sources": len(frontier), "bytes": sum(x["bytes"] for x in frontier)}, indent=2))


if __name__ == "__main__":
    main()
