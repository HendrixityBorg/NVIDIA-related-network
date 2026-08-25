#!/usr/bin/env python3
"""Screen high-quality relation candidates against the official SEC ticker file."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
URL = "https://www.sec.gov/files/company_tickers_exchange.json"
UA = "arti-nvidia-research/1.0 contact=research@example.invalid"


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c)).replace("&", " and ").casefold()
    value = re.sub(r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|plc|sa|ag|se|nv|llc|lp|oyj|de)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


queue = [json.loads(line) for line in (HERE / "relation_priority_review_queue.jsonl").open(encoding="utf-8") if line.strip()]
wanted = {}
for row in queue:
    # Apply the same jurisdiction-suffix stripping to both sides while retaining
    # the audit candidate's own stable normalized key in the result.
    for raw_name in row.get("raw_name_variants", []) or [row["normalized_name"]]:
        wanted.setdefault(norm(raw_name), set()).add(row["normalized_name"])
request = Request(URL, headers={"User-Agent": UA, "Accept": "application/json"})
with urlopen(request, timeout=45) as response:
    raw = response.read()
payload = json.loads(raw)
fields = payload["fields"]
matches = []
for values in payload["data"]:
    row = dict(zip(fields, values))
    normalized = norm(str(row.get("name") or ""))
    if normalized in wanted:
      for candidate_key in sorted(wanted[normalized]):
        matches.append({
            "candidate_normalized_name": candidate_key,
            "issuer_name": row.get("name"),
            "cik": str(row.get("cik")).zfill(10),
            "ticker": row.get("ticker"),
            "exchange": row.get("exchange"),
            "source_url": URL,
            "publisher": "U.S. Securities and Exchange Commission",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "evidence_locator": f"data row matching CIK {str(row.get('cik')).zfill(10)}",
            "match_method": "strict_exact_normalized_issuer_name",
        })
with (HERE / "sec_screening_matches.jsonl").open("w", encoding="utf-8") as handle:
    for row in sorted(matches, key=lambda r: (r["candidate_normalized_name"], r["ticker"] or "")):
        handle.write(json.dumps(row, sort_keys=True) + "\n")
(HERE / "sec_screening_source.json").write_text(json.dumps({
    "source_url": URL,
    "publisher": "U.S. Securities and Exchange Commission",
    "retrieved_at": datetime.now(timezone.utc).isoformat(),
    "sha256": hashlib.sha256(raw).hexdigest(),
    "byte_count": len(raw),
    "raw_full_file_retained": False,
    "filtered_match_rows": len(matches),
    "access_constraints": "public no-login official JSON; bounded single request; SEC fair-access user agent",
    "license_note": "structured issuer facts retained for research; no redistribution right beyond public government data inferred",
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"queue_candidates": len(queue), "filtered_matches": len(matches)}, sort_keys=True))
