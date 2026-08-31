#!/usr/bin/env python3
"""Refresh only the public Yahoo chart metadata required by reviewed_mappings.json."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = "NPN-listed-parent-research/1.0 public-research contact=research@example.invalid"


def main() -> int:
    catalog = json.loads((ROOT / "reviewed_mappings.json").read_text(encoding="utf-8"))
    symbols = sorted({r["issuer"]["yahoo_symbol"] for r in catalog["mappings"] if r["issuer"].get("yahoo_symbol") and not r["issuer"].get("upstream_entity_id")})
    existing_path = ROOT / "yahoo_chart_fixture.jsonl"
    existing = {}
    if existing_path.exists():
        existing = {r["symbol"]: r for r in (json.loads(line) for line in existing_path.read_text(encoding="utf-8").splitlines() if line.strip())}
    rows = []
    failures = []
    for index, symbol in enumerate(symbols):
        if symbol in existing:
            rows.append(existing[symbol])
            continue
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol, safe="") + "?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read()
            payload = json.loads(body)
            meta = payload["chart"]["result"][0]["meta"]
            if meta.get("instrumentType") != "EQUITY":
                raise ValueError(f"not EQUITY: {meta.get('instrumentType')}")
        except Exception as exc:
            failures.append({"symbol": symbol, "source_url": url, "error": type(exc).__name__ + ": " + str(exc), "terminal": True})
            continue
        rows.append({
            "symbol": symbol, "long_name": meta.get("longName") or meta.get("shortName"),
            "short_name": meta.get("shortName"), "exchange_name": meta.get("fullExchangeName") or meta.get("exchangeName"),
            "instrument_type": meta.get("instrumentType"), "currency": meta.get("currency"),
            "regular_market_time": meta.get("regularMarketTime"), "regular_market_price": meta.get("regularMarketPrice"),
            "source_url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "source_content_sha256": hashlib.sha256(body).hexdigest(),
            "access_constraints": "Public JSON chart endpoint; no login, key, CAPTCHA, paywall, robots, limit, or other access control bypass.",
        })
        if index + 1 < len(symbols):
            time.sleep(0.35)
    (ROOT / "yahoo_chart_fixture.jsonl").write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8")
    (ROOT / "failed_yahoo_symbols.jsonl").write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in failures), encoding="utf-8")
    print(f"wrote {len(rows)} frozen listing metadata rows; {len(failures)} terminal failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
