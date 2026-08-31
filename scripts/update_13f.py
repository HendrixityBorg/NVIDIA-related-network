#!/usr/bin/env python3
"""Fetch and normalize one NVIDIA 13F information table.

The script is deliberately narrow: one public SEC filing, one request, declared
User-Agent, no concurrency, and no attempt to mutate the reviewed snapshot.
It prints a review candidate that a human must reconcile to listed entities.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

DEFAULT_URL = (
    "https://www.sec.gov/Archives/edgar/data/1045810/"
    "000104581026000065/xslForm13F_X02/information_table.xml"
)


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "tr":
            self.in_row = True
            self.row = []
        elif tag == "td" and self.in_row:
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            self.row.append(" ".join(" ".join(self.cell_parts).split()))
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if len(self.row) >= 13 and self.row[0] not in {"", "NAME OF ISSUER"}:
                self.rows.append(self.row)
            self.in_row = False


def fetch(url: str, user_agent: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def normalize(raw: str) -> list[dict]:
    parser = TableParser()
    parser.feed(raw)
    results = []
    for row in parser.rows:
        results.append(
            {
                "issuer": row[0],
                "title_of_class": row[1],
                "cusip": row[2],
                "figi": row[3] or None,
                "value_usd": int(row[4].replace(",", "")),
                "shares_or_principal": int(row[5].replace(",", "")),
                "amount_type": row[6],
                "put_call": row[7] or None,
                "investment_discretion": row[8],
                "other_manager": row[9] or None,
                "voting_sole": int(row[10].replace(",", "")),
                "voting_shared": int(row[11].replace(",", "")),
                "voting_none": int(row[12].replace(",", "")),
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--input", type=Path, help="parse a previously saved response")
    parser.add_argument("--output", type=Path, help="write candidate JSON instead of stdout")
    args = parser.parse_args(argv)

    if args.input:
        raw = args.input.read_text(encoding="utf-8")
    else:
        user_agent = os.getenv("LCN_SEC_USER_AGENT", "").strip()
        if not user_agent or "example.invalid" in user_agent:
            print(
                "Set LCN_SEC_USER_AGENT to a descriptive application/contact value.",
                file=sys.stderr,
            )
            return 2
        raw = fetch(args.url, user_agent)

    rows = normalize(raw)
    payload = {
        "source_url": args.url,
        "row_count": len(rows),
        "review_required": True,
        "notes": [
            "Verify listed status and issuer identity at the research cutoff.",
            "Exclude options and non-company instruments according to the research charter.",
            "Do not infer strategic intent from a Form 13F row alone.",
        ],
        "rows": rows,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
