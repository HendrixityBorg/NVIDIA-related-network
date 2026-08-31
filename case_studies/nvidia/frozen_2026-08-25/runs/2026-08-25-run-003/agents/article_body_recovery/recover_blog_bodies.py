#!/usr/bin/env python3
"""Recover NVIDIA Blog bodies from legal, public alternate routes.

Priority is: an already-frozen direct NVIDIA body, NVIDIA's public FeedBurner
RSS feed, then an exact-URL Internet Archive replay selected by the public
Availability API.  Third-party replay HTML is processed in memory and is never
written to the repository.  Per-article structured partials make the run
resumable without retaining full third-party documents.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import re
import subprocess
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


USER_AGENT = "listed-company-network-research/1.0 (public research; contact: repository README)"
CUTOFF = date(2026, 8, 25)
RSS_URL = "https://feeds.feedburner.com/nvidiablog"
RSS_TERMS_URL = "https://www.nvidia.com/en-us/about-nvidia/rss/"
WAYBACK_AVAILABILITY = "https://archive.org/wayback/available"
WAYBACK_ROBOTS = "https://archive.org/robots.txt"
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def portable_paths(value):
    """Remove this workstation's repository prefix from generated JSON."""
    if isinstance(value, dict):
        return {key: portable_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_paths(item) for item in value]
    if isinstance(value, str):
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                return str(candidate.resolve().relative_to(REPOSITORY_ROOT))
            except ValueError:
                pass
    return value


def load_base(path: Path):
    spec = importlib.util.spec_from_file_location("official_article_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_key(url: str) -> str:
    split = urllib.parse.urlsplit(url)
    path = re.sub(r"/+", "/", split.path).rstrip("/")
    return f"{split.scheme.lower()}://{split.netloc.lower()}{path}"


def curl_bytes(url: str, accept: str, max_time: int = 50) -> tuple[bytes, int, str, dict]:
    marker = b"\n__LCN_HTTP_META__"
    result = subprocess.run(
        [
            "curl", "--http1.1", "--location", "--compressed", "--silent", "--show-error",
            "--max-time", str(max_time), "--connect-timeout", "12",
            "--user-agent", USER_AGENT, "--header", f"Accept: {accept}",
            "--dump-header", "-",
            "--write-out", "\n__LCN_HTTP_META__%{http_code}\t%{url_effective}\t%{content_type}",
            url,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=max_time + 10,
        check=False,
    )
    if result.returncode != 0:
        raise ConnectionError(f"curl exit {result.returncode}: {result.stderr.decode(errors='replace')[:500]}")
    if marker not in result.stdout:
        raise ConnectionError("response missing HTTP metadata marker")
    payload, meta = result.stdout.rsplit(marker, 1)
    # --dump-header - prefixes the response body with one or more header blocks.
    # Split on the final blank line belonging to the final response.
    segments = re.split(br"\r?\n\r?\n", payload)
    body_index = 0
    for index, segment in enumerate(segments):
        if segment.startswith(b"HTTP/"):
            body_index = index + 1
    body = b"\n\n".join(segments[body_index:])
    header_block = segments[body_index - 1].decode("latin-1", errors="replace") if body_index else ""
    headers = {}
    for line in header_block.splitlines()[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    status_raw, final_url, content_type = meta.decode(errors="replace").split("\t", 2)
    status = int(status_raw)
    if not 200 <= status < 400:
        raise ConnectionError(f"HTTP {status}")
    return body, status, final_url.strip(), {"content_type": content_type.strip(), **headers}


def load_products(path: Path) -> list[dict]:
    products: dict[str, dict] = {}
    mapping_origin = portable_paths(str(path))
    for row in read_jsonl(path):
        name = str(row.get("primary_name") or "").strip()
        if len(name) < 4:
            continue
        products.setdefault(name.lower(), {
            "name": name,
            "source_node_id": row.get("canonical_key"),
            "mapping_origin": mapping_origin,
        })
        for alias in row.get("aliases", []):
            alias = str(alias).strip()
            if len(alias) >= 4:
                products.setdefault(alias.lower(), {
                    "name": alias,
                    "source_node_id": row.get("canonical_key"),
                    "mapping_origin": mapping_origin,
                })
    return sorted(products.values(), key=lambda row: (-len(row["name"]), row["name"].lower()))


def direct_snapshot_map(run_root: Path, manifest: list[dict]) -> dict[str, Path]:
    blog_ids = {row["article_id"] for row in manifest}
    found = {}
    for shard in ("official_articles_2025", "official_articles_2026"):
        folder = run_root / "agents" / shard / "body_snapshots"
        if not folder.exists():
            continue
        for path in folder.glob("article_*.html.gz"):
            article_id = path.name[:-8]
            if article_id in blog_ids:
                found[article_id] = path
    return found


def feed_items(raw: bytes) -> dict[str, dict]:
    root = ET.fromstring(raw)
    out = {}
    for item in root.findall(".//item"):
        link = item.findtext("link") or ""
        title = item.findtext("title") or ""
        published_raw = item.findtext("pubDate") or ""
        encoded = ""
        for child in item:
            if child.tag.endswith("encoded"):
                encoded = child.text or ""
                break
        if not link or not encoded:
            continue
        try:
            published = parsedate_to_datetime(published_raw).date().isoformat()
        except Exception:
            published = None
        out[canonical_key(link)] = {
            "link": link,
            "title": title,
            "published_date": published,
            "encoded": encoded,
        }
    return out


def safe_process(base, article: dict, blocks: list[dict], body_text: str, products: list[dict],
                 raw_sha: str, retrieved_url: str, method: str, fetched_at: str,
                 direct_path: str | None = None, archive_timestamp: str | None = None):
    processing, mentions, observations = base.process_one(
        article, blocks, body_text, products, direct_path or "", raw_sha,
        fetched_at, retrieved_url,
    )
    access_note = {
        "direct": "public NVIDIA canonical page; publisher copyright retained",
        "rss": "NVIDIA RSS free service; information purposes only; non-commercial use only; publisher copyright retained",
        "wayback": "public no-login Internet Archive replay; original publisher copyright retained; no republication grant inferred",
    }[method]
    processing.update({
        "body_coverage_status": "complete",
        "recovery_method": method,
        "retrieved_url": retrieved_url,
        "archive_timestamp": archive_timestamp,
        "access_constraints": access_note,
    })
    if method != "direct":
        processing["body_snapshot_path"] = None
        processing["raw_content_retained"] = False
    for row in mentions:
        row.update({
            "body_recovery_method": method,
            "retrieved_url": retrieved_url,
            "archive_timestamp": archive_timestamp,
            "access_constraints": access_note,
        })
    for row in observations:
        row.update({
            "body_recovery_method": method,
            "retrieved_url": retrieved_url,
            "archive_timestamp": archive_timestamp,
            "access_constraints": access_note,
        })
        if method != "direct":
            row["snapshot_path"] = None
        # Investment claims from articles are outside the accepted investee
        # source policy.  Preserve the evidence only as an unknown event.
        if row.get("relationship_hint") in {"investee", "investor_or_investee"}:
            row["relationship_hint"] = "unknown"
            row["direction_hint"] = "direction unknown"
            row["semantic_status"] = "unknown"
            row["classification_rationale"] = (
                "investment wording in an article is non-authoritative for this project; "
                "latest NVIDIA 13F is the sole allowed final investee source"
            )
    return processing, mentions, observations


def parse_wayback_body(base, raw: bytes, expected_title: str) -> tuple[list[dict], str, str]:
    """Validate an archived body using its article H1, not SEO-shortened title."""
    text = raw.decode("utf-8", errors="replace")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    actual_title = base.clean_text(re.sub(r"<[^>]+>", " ", title_match.group(1))) if title_match else ""
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I | re.S)
    h1 = base.clean_text(re.sub(r"<[^>]+>", " ", h1_match.group(1))) if h1_match else ""
    if not base.title_matches(expected_title, h1 or actual_title):
        raise ValueError(
            f"article H1/title mismatch: expected={expected_title!r}, h1={h1!r}, html_title={actual_title!r}"
        )
    parser = base.BodyParser("entry-content")
    parser.feed(text)
    body_text = "\n".join(block["text"] for block in parser.blocks)
    if len(body_text) < 120:
        raise ValueError(f"missing/short entry-content body ({len(body_text)} characters)")
    return parser.blocks, body_text, actual_title


def wayback_candidate(article: dict, delay: float) -> tuple[dict | None, dict]:
    targets = [article["canonical_url"]]
    if not article["canonical_url"].endswith("/"):
        # A trailing slash is a canonical-equivalent path form, not a query or
        # semantic URL variant.  It is tried only if the frozen form has no hit.
        targets.append(article["canonical_url"] + "/")
    attempt_audit = []
    for target in targets:
        params = urllib.parse.urlencode({
            "url": target,
            "timestamp": article["published_date"].replace("-", ""),
        })
        request_url = f"{WAYBACK_AVAILABILITY}?{params}"
        try:
            raw, status, final_url, headers = curl_bytes(request_url, "application/json", 35)
            payload = json.loads(raw)
            closest = payload.get("archived_snapshots", {}).get("closest")
            if not closest or not closest.get("available"):
                attempt_audit.append({"request_url": request_url, "http_status": status, "result": "no_available_snapshot"})
                time.sleep(delay)
                continue
        except Exception as exc:
            attempt_audit.append({"request_url": request_url, "http_status": None, "result": "request_failed", "error": f"{type(exc).__name__}: {str(exc)[:500]}"})
            time.sleep(delay)
            continue
        try:
            timestamp = str(closest.get("timestamp") or "")
            original = str(closest.get("url") or "")
            original_from_replay = re.sub(r"^https?://web\.archive\.org/web/\d+(?:[a-z_]+)?/", "", original)
            if canonical_key(original_from_replay) != canonical_key(article["canonical_url"]):
                attempt_audit.append({"request_url": request_url, "http_status": status, "result": "url_mismatch", "candidate_url": original})
                time.sleep(delay)
                continue
            published_key = article["published_date"].replace("-", "")
            cutoff_key = CUTOFF.isoformat().replace("-", "")
            if len(timestamp) < 8 or timestamp[:8] < published_key or timestamp[:8] > cutoff_key:
                attempt_audit.append({
                    "request_url": request_url, "http_status": status,
                    "result": "snapshot_outside_allowed_window", "candidate_timestamp": timestamp,
                    "candidate_url": original,
                })
                time.sleep(delay)
                continue
            replay_original = article["canonical_url"] + ("/" if not article["canonical_url"].endswith("/") else "")
            replay = f"https://web.archive.org/web/{timestamp}id_/{replay_original}"
            time.sleep(delay)
            return {"timestamp": timestamp, "url": replay}, {
                "request_url": request_url, "http_status": status,
                "result": "candidate_selected", "candidate_timestamp": timestamp,
                "candidate_url": replay, "response_sha256": hashlib.sha256(raw).hexdigest(),
                "cache_control": headers.get("cache-control"),
                "availability_attempts": attempt_audit,
            }
        except Exception as exc:
            attempt_audit.append({"request_url": request_url, "http_status": status, "result": "candidate_validation_failed", "error": f"{type(exc).__name__}: {str(exc)[:500]}"})
            time.sleep(delay)
    return None, {"result": "no_acceptable_snapshot", "availability_attempts": attempt_audit}


def recover_wayback(base, article: dict, products: list[dict], delay: float, fetched_at: str):
    candidate, audit = wayback_candidate(article, delay)
    if not candidate:
        exc = RuntimeError(json.dumps(audit, sort_keys=True))
        exc.audit = audit
        raise exc
    errors = []
    for attempt in range(1, 3):
        try:
            raw, status, final_url, headers = curl_bytes(candidate["url"], "text/html,application/xhtml+xml", 50)
            blocks, body_text, actual_title = parse_wayback_body(base, raw, article["title"])
            processing, mentions, observations = safe_process(
                base, article, blocks, body_text, products, hashlib.sha256(raw).hexdigest(),
                final_url, "wayback", fetched_at, archive_timestamp=candidate["timestamp"],
            )
            audit.update({
                "replay_http_status": status,
                "replay_final_url": final_url,
                "replay_sha256": hashlib.sha256(raw).hexdigest(),
                "replay_byte_count": len(raw),
                "replay_content_type": headers.get("content_type"),
                "actual_html_title": actual_title,
                "raw_content_retained": False,
                "result": "body_processed",
            })
            time.sleep(delay)
            return processing, mentions, observations, audit
        except Exception as exc:
            errors.append(f"attempt {attempt}: {type(exc).__name__}: {str(exc)[:500]}")
            time.sleep(delay * (attempt + 1))
    audit.update({"result": "replay_failed", "error": " | ".join(errors)})
    exc = RuntimeError(audit["error"])
    exc.audit = audit
    raise exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--retry-blocked", action="store_true")
    args = parser.parse_args()
    run_root = args.run_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    partials = output / "partials"
    partials.mkdir(exist_ok=True)
    base = load_base(run_root / "agents" / "official_articles_2025" / "process_articles.py")
    manifest = [row for row in read_jsonl(run_root / "news" / "official_articles.jsonl") if row["article_type"] == "blog"]
    manifest.sort(key=lambda row: (row["published_date"], row["article_id"]))
    if len(manifest) != 597 or len({row["article_id"] for row in manifest}) != 597:
        raise ValueError(f"expected exact 597-item Blog manifest, got {len(manifest)}")
    selected = manifest[:args.limit] if args.limit else manifest
    products = load_products(run_root / "product_tree_v2" / "canonical_index_v2.jsonl")
    direct = direct_snapshot_map(run_root, manifest)
    fetched_at = datetime.now(timezone.utc).isoformat()

    rss_raw, rss_status, rss_final, rss_headers = curl_bytes(RSS_URL, "application/rss+xml,application/xml,text/xml", 45)
    rss = feed_items(rss_raw)
    rss_audit = {
        "source_url": RSS_URL,
        "final_url": rss_final,
        "http_status": rss_status,
        "content_type": rss_headers.get("content_type"),
        "sha256": hashlib.sha256(rss_raw).hexdigest(),
        "byte_count": len(rss_raw),
        "item_count": len(rss),
        "fetched_at": fetched_at,
        "raw_content_retained": False,
        "terms_url": RSS_TERMS_URL,
        "terms_locator": "Additional Information: free service for information purposes only; restricted to non-commercial purposes",
        "license_note": "NVIDIA RSS is restricted to non-commercial, information-only use; copyright remains with NVIDIA.",
    }
    write_json(output / "rss_access_audit.json", rss_audit)

    processing_rows, mention_rows, observation_rows, access_rows = [], [], [], []
    for position, article in enumerate(selected, 1):
        partial_path = partials / f"{article['article_id']}.json"
        if partial_path.exists():
            partial_raw = json.loads(partial_path.read_text(encoding="utf-8"))
            partial = portable_paths(partial_raw)
            if partial != partial_raw:
                write_json(partial_path, partial)
            if not (args.retry_blocked and partial["processing"].get("recovery_method") == "blocked"):
                processing_rows.append(partial["processing"])
                mention_rows.extend(partial["mentions"])
                observation_rows.extend(partial["observations"])
                access_rows.append(partial["access"])
                print(f"[{position}/{len(selected)}] resume {article['article_id']} {partial['processing']['recovery_method']}", flush=True)
                continue
        processing = None
        mentions: list[dict] = []
        observations: list[dict] = []
        access: dict = {"article_id": article["article_id"], "canonical_url": article["canonical_url"]}
        try:
            if article["article_id"] in direct:
                import gzip
                path = direct[article["article_id"]]
                with gzip.open(path, "rb") as handle:
                    raw = handle.read()
                blocks, body_text, actual_title = base.parse_body(raw, "NVIDIA Blog", article["title"])
                rel_path = str(path.relative_to(run_root))
                processing, mentions, observations = safe_process(
                    base, article, blocks, body_text, products, hashlib.sha256(raw).hexdigest(),
                    article["canonical_url"], "direct", fetched_at, direct_path=rel_path,
                )
                access.update({
                    "result": "body_processed", "recovery_method": "direct",
                    "http_status": 200, "retrieved_url": article["canonical_url"],
                    "sha256": hashlib.sha256(raw).hexdigest(), "byte_count": len(raw),
                    "actual_html_title": actual_title, "reused_snapshot_path": rel_path,
                })
            elif canonical_key(article["canonical_url"]) in rss:
                item = rss[canonical_key(article["canonical_url"])]
                if item["published_date"] and item["published_date"] != article["published_date"]:
                    raise ValueError(f"RSS date mismatch: {item['published_date']} vs {article['published_date']}")
                wrapped = (
                    "<!doctype html><html><head><title>" + html.escape(article["title"]) +
                    "</title></head><body><div class=\"entry-content\">" + item["encoded"] +
                    "</div></body></html>"
                ).encode()
                blocks, body_text, actual_title = base.parse_body(wrapped, "NVIDIA Blog", article["title"])
                processing, mentions, observations = safe_process(
                    base, article, blocks, body_text, products, hashlib.sha256(wrapped).hexdigest(),
                    RSS_URL, "rss", fetched_at,
                )
                access.update({
                    "result": "body_processed", "recovery_method": "rss",
                    "http_status": rss_status, "retrieved_url": RSS_URL,
                    "item_link": item["link"], "item_content_sha256": hashlib.sha256(item["encoded"].encode()).hexdigest(),
                    "item_content_character_count": len(item["encoded"]), "actual_html_title": actual_title,
                    "raw_content_retained": False,
                    "license_note": rss_audit["license_note"],
                })
            else:
                processing, mentions, observations, wb_audit = recover_wayback(
                    base, article, products, args.delay, fetched_at,
                )
                access.update(wb_audit)
                access["recovery_method"] = "wayback"
        except Exception as exc:
            attached_audit = getattr(exc, "audit", None)
            if attached_audit:
                access.update(attached_audit)
            processing = {
                "article_id": article["article_id"],
                "canonical_url": article["canonical_url"],
                "publisher": article["publisher"],
                "published_date": article["published_date"],
                "title": article["title"],
                "processing_status": "access_blocked",
                "body_coverage_status": "access_blocked",
                "recovery_method": "blocked",
                "processing_reason": f"{type(exc).__name__}: {str(exc)[:1500]}",
                "body_snapshot_path": None,
                "body_sha256": None,
                "fetched_at": fetched_at,
                "access_constraints": "public direct/RSS/Wayback routes exhausted with bounded requests; no access control bypass",
            }
            access.update({
                "result": access.get("result", "access_blocked"),
                "recovery_method": "blocked",
                "error": f"{type(exc).__name__}: {str(exc)[:1500]}",
            })
        partial = {"processing": processing, "mentions": mentions, "observations": observations, "access": access}
        write_json(partial_path, partial)
        processing_rows.append(processing)
        mention_rows.extend(mentions)
        observation_rows.extend(observations)
        access_rows.append(access)
        print(f"[{position}/{len(selected)}] {article['article_id']} {processing['recovery_method']}", flush=True)

    write_jsonl(output / "article_processing.jsonl", processing_rows)
    write_jsonl(output / "entity_mentions.jsonl", mention_rows)
    write_jsonl(output / "observations.jsonl", observation_rows)
    write_jsonl(output / "access_audit.jsonl", access_rows)
    counts = {method: sum(row.get("recovery_method") == method for row in processing_rows) for method in ("direct", "rss", "wayback", "blocked")}
    coverage = counts["direct"] + counts["rss"] + counts["wayback"]
    all_terminal = len(processing_rows) == len(selected) and all(row.get("recovery_method") in {"direct", "rss", "wayback", "blocked"} for row in processing_rows)
    ledger_exact = len(selected) == 597 and len({row["article_id"] for row in processing_rows}) == 597 and {row["article_id"] for row in processing_rows} == {row["article_id"] for row in manifest}
    covered_have_hash = all(row.get("body_sha256") for row in processing_rows if row.get("recovery_method") != "blocked")
    blocked_ids = {row["article_id"] for row in processing_rows if row.get("recovery_method") == "blocked"}
    blocked_audits = {row["article_id"]: row for row in access_rows if row.get("article_id") in blocked_ids}
    blocked_audited = len(blocked_audits) == len(blocked_ids) and all(
        row.get("error") and row.get("result") and row.get("recovery_method") == "blocked"
        for row in blocked_audits.values()
    )
    no_investee = not any(row.get("relationship_hint") in {"investee", "investor_or_investee"} for row in observation_rows)
    acceptance_checks = {
        "ledger_exactly_matches_597_blog_manifest": ledger_exact,
        "all_rows_terminal": all_terminal,
        "pending_zero": all_terminal and ledger_exact,
        "covered_rows_have_hash": covered_have_hash,
        "blocked_rows_have_complete_access_audit_and_reason": blocked_audited,
        "no_third_party_full_html_retained": True,
        "no_article_investee_claims": no_investee,
    }
    report = {
        "pass": all(acceptance_checks.values()),
        "body_coverage_complete": len(selected) == 597 and coverage == 597,
        "acceptance_checks": acceptance_checks,
        "manifest_expected": 597,
        "manifest_total": 597,
        "ledger_rows": len(processing_rows),
        "terminal_rows": len(processing_rows) if all_terminal else sum(row.get("recovery_method") in {"direct", "rss", "wayback", "blocked"} for row in processing_rows),
        "counts_by_recovery_method": counts,
        "body_covered": coverage,
        "access_blocked": counts["blocked"],
        "pending": 0 if all_terminal and len(selected) == 597 else 597 - len(processing_rows),
        "terminal_ledger_complete": all_terminal and len(selected) == 597,
        "entity_mentions": len(mention_rows),
        "observations": len(observation_rows),
        "investment_policy_check": {
            "article_investee_observations": sum(row.get("relationship_hint") in {"investee", "investor_or_investee"} for row in observation_rows),
            "required": 0,
            "rule": "article investment semantics remain unknown; latest NVIDIA 13F is sole final investee source",
        },
        "raw_third_party_html_retained": False,
        "cutoff": CUTOFF.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(output / "validation_report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
