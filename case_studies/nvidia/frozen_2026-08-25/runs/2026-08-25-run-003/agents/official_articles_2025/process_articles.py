#!/usr/bin/env python3
"""Fetch and deterministically process every 2025 NVIDIA official article.

Only public, no-login article URLs from the already frozen official archive
manifest are requested.  Raw HTML is stored compressed for audit; derived text
is used for conservative entity/relation observations.  A mention is never a
relationship by itself.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import subprocess
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


USER_AGENT = "listed-company-network-research/1.0 (public research; contact: repository README)"
CUTOFF = date(2026, 8, 25)
START = date(2025, 1, 1)
END = date(2025, 12, 31)
FINAL_STATES = {
    "processed_with_candidates",
    "processed_no_candidate",
    "access_blocked",
    "excluded_with_reason",
}
RELATION_CUES = {
    "investee": re.compile(r"\b(?:invest(?:ed|s|ment)?|equity stake|common stock|funding round)\b", re.I),
    "acquisition": re.compile(r"\b(?:acquir(?:e|es|ed|ing|ition)|purchase(?:d)?\s+(?:the|all)|buy(?:ing|s)?\s+(?:the|all))\b", re.I),
    "supplier": re.compile(r"\b(?:supplier(?:s)?(?:\s+(?:to|of|for)\s+NVIDIA)?|suppl(?:y|ies|ied)\s+[^.]{0,80}\s+to NVIDIA|provid(?:e|es|ed)\s+[^.]{0,80}\s+to NVIDIA|manufactur(?:e|es|ed)\s+[^.]{0,80}\s+for NVIDIA|supply collaboration)\b", re.I),
    "customer": re.compile(r"\b(?:adopt(?:s|ed|ing)?|deploy(?:s|ed|ing)?|select(?:s|ed|ing)?|cho(?:ose|oses|se)|purchas(?:e|es|ed)|customer|uses?|using|powered by|built on|runs? on)\b", re.I),
    "partner": re.compile(r"\b(?:partner(?:s|ed|ship)?|collaborat(?:e|es|ed|ion)|team(?:s|ed)? up|joint(?:ly)?|work(?:s|ed|ing)? with|integrat(?:e|es|ed|ion)|ecosystem)\b", re.I),
    "peer": re.compile(r"\b(?:compet(?:e|es|ed|itor|ing)|alternative to|rival)\b", re.I),
}
PRODUCT_FALLBACK = [
    "Blackwell", "Grace Blackwell", "GeForce", "RTX", "CUDA", "CUDA-X", "DGX",
    "DGX Cloud", "DGX Spark", "DGX Station", "Spectrum-X", "Spectrum-XGS",
    "NVLink", "NVLink Fusion", "NVQLink", "InfiniBand", "BlueField", "DPU",
    "NIM", "NeMo", "Nemotron", "Omniverse", "Cosmos", "Isaac", "Isaac GR00T",
    "Jetson", "Jetson Thor", "DRIVE", "DRIVE Hyperion", "Earth-2", "BioNeMo",
    "Clara", "cuQuantum", "AI Enterprise", "RTX PRO", "GeForce NOW",
]
NON_ENTITY_TEXT = re.compile(
    r"^(?:learn more|read more|click here|here|download|watch|listen|register|source|"
    r"blog|website|report|paper|video|image|photo|press release|newsroom|nvidia|"
    r"nvidia corporation|partners?|customers?|computex|gtc|nvidia gtc keynote|"
    r"artificial intelligence|ai|gpu|gpus|cpu|cpus|dpu|dpus)$",
    re.I,
)
EXCLUDED_HOST_BITS = (
    "nvidia.com", "youtube.com", "youtu.be", "twitter.com", "x.com",
    "linkedin.com", "facebook.com", "instagram.com", "tiktok.com",
)
TICKER_RE = re.compile(
    r"(?P<name>[A-Z][A-Za-z0-9&\u2019'.-]*(?:\s+[A-Z][A-Za-z0-9&\u2019'.-]*){0,6}"
    r"(?:,?\s+(?:Inc\.?|Corporation|Corp\.?|Company|Co\.?|Group|plc|Ltd\.?|Limited))?)"
    r"\s*\((?P<exchange>NASDAQ|Nasdaq|"
    r"NYSE|LSE|HKEX|TSE|TYO|KRX|SIX|Euronext)\s*:\s*(?P<ticker>[A-Z0-9.-]{1,12})\)",
    re.I,
)


def jsonl_read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def jsonl_write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


class BodyParser(HTMLParser):
    """Extract target container blocks and their anchors without dependencies."""

    def __init__(self, target_class: str):
        super().__init__(convert_charrefs=True)
        self.target_class = target_class
        self.capture_depth: int | None = None
        self.depth = 0
        self.in_block_depth: int | None = None
        self.block_tag = ""
        self.block_parts: list[str] = []
        self.blocks: list[dict] = []
        self.current_anchors: list[dict] = []
        self.anchor_depth: int | None = None
        self.anchor_href = ""
        self.anchor_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        if self.capture_depth is None and self.target_class in classes:
            self.capture_depth = self.depth
            return
        if self.capture_depth is None:
            return
        if tag in {"p", "li", "h2", "h3", "h4", "blockquote"} and self.in_block_depth is None:
            self.in_block_depth = self.depth
            self.block_tag = tag
            self.block_parts = []
            self.current_anchors = []
        if tag == "a" and self.in_block_depth is not None and self.anchor_depth is None:
            self.anchor_depth = self.depth
            self.anchor_href = attr.get("href") or ""
            self.anchor_parts = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return

    def handle_data(self, data: str) -> None:
        if self.capture_depth is None or self.in_block_depth is None:
            return
        self.block_parts.append(data)
        if self.anchor_depth is not None:
            self.anchor_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.capture_depth is not None:
            if self.anchor_depth == self.depth and tag == "a":
                text = clean_text(" ".join(self.anchor_parts))
                if text:
                    self.current_anchors.append({"text": text, "href": html.unescape(self.anchor_href)})
                self.anchor_depth = None
                self.anchor_href = ""
                self.anchor_parts = []
            if self.in_block_depth == self.depth and tag == self.block_tag:
                text = clean_text(" ".join(self.block_parts))
                if text:
                    self.blocks.append({"tag": self.block_tag, "text": text, "anchors": self.current_anchors[:]})
                self.in_block_depth = None
                self.block_tag = ""
                self.block_parts = []
                self.current_anchors = []
            if self.capture_depth == self.depth:
                self.capture_depth = None
        self.depth = max(0, self.depth - 1)


def title_from_html(text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    return clean_text(re.sub(r"<[^>]+>", " ", match.group(1))) if match else ""


def title_matches(expected: str, actual: str) -> bool:
    def tokens(value: str) -> set[str]:
        return {x.lower() for x in re.findall(r"[A-Za-z0-9]+", value) if len(x) > 2 and x.lower() not in {"the", "and", "nvidia", "newsroom", "blog"}}
    want, got = tokens(expected), tokens(actual)
    return bool(want) and len(want & got) / max(1, len(want)) >= 0.55


def parse_body(raw: bytes, publisher: str, expected_title: str) -> tuple[list[dict], str, str]:
    text = raw.decode("utf-8", errors="replace")
    actual_title = title_from_html(text)
    if not title_matches(expected_title, actual_title):
        raise ValueError(f"title mismatch: expected={expected_title!r}, actual={actual_title!r}")
    target = "entry-content" if publisher == "NVIDIA Blog" else "article-body"
    parser = BodyParser(target)
    parser.feed(text)
    body_text = "\n".join(block["text"] for block in parser.blocks)
    if len(body_text) < 120:
        raise ValueError(f"missing/short {target} body ({len(body_text)} characters)")
    return parser.blocks, body_text, actual_title


def fetch(url: str, expected_title: str, publisher: str, attempts: int = 5) -> tuple[bytes, str, int, str]:
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            marker = b"\n__LCN_HTTP_META__"
            result = subprocess.run(
                [
                    "curl", "--http1.1", "--location", "--silent", "--show-error",
                    "--max-time", "50", "--connect-timeout", "15",
                    "--user-agent", USER_AGENT,
                    "--header", "Accept: text/html,application/xhtml+xml",
                    "--write-out", "\n__LCN_HTTP_META__%{http_code}\t%{url_effective}",
                    url,
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
            if result.returncode != 0:
                raise ConnectionError(f"curl exit {result.returncode}: {result.stderr.decode(errors='replace')[:500]}")
            if marker not in result.stdout:
                raise ConnectionError("curl response missing HTTP metadata marker")
            raw, metadata = result.stdout.rsplit(marker, 1)
            status_raw, final_url_raw = metadata.decode("utf-8", errors="replace").split("\t", 1)
            status = int(status_raw)
            final_url = final_url_raw.strip()
            if status < 200 or status >= 400:
                raise ConnectionError(f"HTTP {status}")
            parse_body(raw, publisher, expected_title)
            return raw, final_url, status, "; ".join(errors)
        except (subprocess.TimeoutExpired, TimeoutError, ValueError, ConnectionError) as exc:
            errors.append(f"attempt {attempt}: {type(exc).__name__}: {str(exc)[:300]}")
            if attempt < attempts:
                time.sleep(min(15, 1.5 * (2 ** (attempt - 1))))
    raise RuntimeError(" | ".join(errors))


def normalize_entity(name: str) -> str:
    value = clean_text(re.sub(r"[\u00ae\u2122]", "", name)).strip(" ,.;:()[]{}\"'")
    value = re.sub(r"^(?:the|and|with)\s+", "", value, flags=re.I)
    return value


def plausible_entity(text: str, href: str = "") -> bool:
    value = normalize_entity(text)
    if len(value) < 2 or len(value) > 100 or NON_ENTITY_TEXT.match(value):
        return False
    if value.lower().startswith("nvidia") or value.lower().startswith("about nvidia"):
        return False
    if value.lower() in {x.lower() for x in PRODUCT_FALLBACK}:
        return False
    if len(value.split()) > 12 or re.match(r"^(?:how|why|what|when|where|see|find|explore)\b", value, re.I):
        return False
    # An organization-like anchor normally has a name-like token or acronym.
    name_like = bool(re.search(r"\b[A-Z][A-Za-z0-9&.-]*", value))
    if not name_like:
        return False
    if href:
        host = urlsplit(href).netloc.lower()
        if any(bit in host for bit in EXCLUDED_HOST_BITS) and not re.search(r"\b(?:Inc|Corp|Company|Group|Systems|Technologies)\b", value):
            # Internal links with a succinct proper-name anchor remain useful.
            return len(value.split()) <= 4 and value[0].isupper() and value.lower() not in {x.lower() for x in PRODUCT_FALLBACK}
    return True


def title_entities(title: str) -> list[str]:
    patterns = [
        r"^NVIDIA and (.+?) (?:Announce|Collaborate|Expand|Open|Build|Advance|Partner|Team|to\b|Unveil)",
        r"^(.+?) and NVIDIA (?:Announce|Collaborate|Expand|Open|Build|Advance|Partner|Team|to\b|Unveil)",
        r"^NVIDIA Partners With (.+?) to\b",
        r"^NVIDIA,? (.+?) (?:Collaborate|Partner|Team|Announce)",
        r"^(.+?) (?:Adopts|Selects|Deploys|Uses|Builds With) NVIDIA\b",
    ]
    out = []
    for pattern in patterns:
        match = re.search(pattern, title, re.I)
        if match:
            candidate = normalize_entity(match.group(1))
            if plausible_entity(candidate):
                out.append(candidate)
    return list(dict.fromkeys(out))


def load_products(paths: list[Path]) -> list[dict]:
    items: dict[str, dict] = {}
    for path in paths:
        if not path.exists():
            continue
        for row in jsonl_read(path):
            name = clean_text(str(row.get("name", "")))
            if len(name) < 4 or name.lower() in {"platform", "software", "solutions", "products", "industries", "networking", "robotics", "automotive"}:
                continue
            node_id = row.get("node_id") or row.get("id") or row.get("canonical_key")
            items.setdefault(name.lower(), {"name": name, "source_node_id": node_id, "mapping_origin": str(path)})
    for name in PRODUCT_FALLBACK:
        items.setdefault(name.lower(), {"name": name, "source_node_id": None, "mapping_origin": "fallback_lexicon"})
    return sorted(items.values(), key=lambda x: (-len(x["name"]), x["name"].lower()))


def product_matches(text: str, products: list[dict]) -> list[dict]:
    found = []
    for product in products:
        name = product["name"]
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", text, re.I):
            found.append(product)
        if len(found) >= 12:
            break
    return found


def ticker_evidence(blocks: list[dict]) -> dict[str, dict]:
    out = {}
    for index, block in enumerate(blocks, 1):
        for match in TICKER_RE.finditer(block["text"]):
            name = normalize_entity(match.group("name"))
            # Avoid a regex capture beginning in the middle of a long sentence.
            name = re.split(r"[.;:]|\b(?:and|today|announced)\b", name, flags=re.I)[-1].strip()
            if name and not name.lower().startswith("nvidia") and not name.lower().startswith("about nvidia") and name.lower() not in {"inc", "corp", "corporation", "company", "group"}:
                out[name.lower()] = {
                    "entity_name": name,
                    "exchange": match.group("exchange").upper(),
                    "ticker": match.group("ticker").upper(),
                    "listing_evidence_locator": f"body.block[{index}]",
                    "listing_evidence_excerpt": block["text"][max(0, match.start()-30):match.end()+30],
                }
    return out


def classify_relation(text: str, entity: str) -> tuple[str, str, str, str]:
    lower = text.lower()
    nvidia_pos = lower.find("nvidia")
    entity_pos = lower.find(entity.lower())
    nvidia_invests = re.search(
        r"(?:NVIDIA[^.]{0,100}\binvest(?:ed|s|ing|ment)?\b|\binvestment\s+(?:by|from)\s+NVIDIA\b)",
        text,
        re.I,
    )
    nvidia_acquires = re.search(
        r"(?:NVIDIA[^.]{0,100}\bacquir(?:e|es|ed|ing|ition)\b|\bacquir(?:e|ed|ition)\s+(?:by|from)\s+NVIDIA\b)",
        text,
        re.I,
    )
    if nvidia_invests and entity.lower() in lower:
        return (
            "unknown",
            "investment event mentioned; investee direction not claimable from article",
            "unknown",
            "non-authoritative investment mention; latest NVIDIA 13F is the sole allowed source for final investee claims",
        )
    if nvidia_acquires and entity.lower() in lower:
        return "acquisition", "NVIDIA acquires entity", "fact", "explicit acquisition wording"
    if RELATION_CUES["supplier"].search(text) and "nvidia" in lower:
        return "supplier", "entity supplies_to NVIDIA", "fact", "explicit supply/manufacturing wording"
    if RELATION_CUES["partner"].search(text) and "nvidia" in lower:
        return "partner", "NVIDIA partners_with entity", "fact", "explicit partnership/collaboration/integration wording"
    if RELATION_CUES["customer"].search(text) and "nvidia" in lower:
        explicit = bool(re.search(r"\b(?:adopt(?:s|ed)?|deploy(?:s|ed)?|select(?:s|ed)?|purchas(?:e|ed)|customer|uses?)\b", text, re.I))
        status = "fact" if explicit else "inferred"
        return "customer", "NVIDIA sells_to entity", status, "product adoption/use wording" if explicit else "powered-by/built-on wording; commercial role not explicit"
    if RELATION_CUES["peer"].search(text) and "nvidia" in lower:
        return "peer", "NVIDIA competes_with entity", "unknown", "competitive wording requires category-level corroboration"
    if nvidia_pos >= 0 and entity_pos >= 0:
        return "unknown", "direction unknown", "unknown", "co-mention only; no qualifying relationship verb"
    return "unknown", "direction unknown", "unknown", "entity mention without NVIDIA relation wording"


def age_info(published: date) -> tuple[int, str, float]:
    age = (CUTOFF - published).days
    if age <= 90:
        return age, "0_90_days", 1.0
    if age <= 180:
        return age, "91_180_days", 0.9
    if age <= 365:
        return age, "181_365_days", 0.75
    return age, "over_365_days_within_research_window", 0.55


def process_one(article: dict, blocks: list[dict], body_text: str, products: list[dict], snapshot_rel: str, raw_sha: str, fetched_at: str, final_url: str) -> tuple[dict, list[dict], list[dict]]:
    article_id = article["article_id"]
    published = date.fromisoformat(article["published_date"])
    age_days, bucket, factor = age_info(published)
    tickers = ticker_evidence(blocks)
    title_names = title_entities(article["title"])
    mentions: list[dict] = []
    observations: list[dict] = []
    seen_mentions: set[tuple[str, str]] = set()
    seen_obs: set[tuple[str, str, str]] = set()

    # Title-derived named counterparties are useful even when unlinked in body.
    for name in title_names:
        key = (name.lower(), "title")
        if key not in seen_mentions:
            mentions.append({
                "article_id": article_id, "source_url": article["canonical_url"],
                "publisher": article["publisher"], "published_date": article["published_date"],
                "entity_name_raw": name, "entity_name_normalized_hint": name,
                "mention_source": "title_pattern", "evidence_locator": "article.title",
                "context_excerpt": article["title"], "listing_status": "unresolved",
            })
            seen_mentions.add(key)

    for index, block in enumerate(blocks, 1):
        locator = f"body.block[{index}]"
        block_names: list[tuple[str, str, str]] = []
        for anchor in block["anchors"]:
            if plausible_entity(anchor["text"], anchor["href"]):
                block_names.append((normalize_entity(anchor["text"]), "anchor", anchor["href"]))
        for match in TICKER_RE.finditer(block["text"]):
            candidate = normalize_entity(match.group("name"))
            candidate = re.split(r"[.;:]|\b(?:and|today|announced)\b", candidate, flags=re.I)[-1].strip()
            if candidate and not candidate.lower().startswith("nvidia") and candidate.lower() not in {"inc", "corp", "corporation", "company", "group"}:
                block_names.append((candidate, "ticker_expression", ""))
        for name in title_names:
            if name.lower() in block["text"].lower():
                block_names.append((name, "title_entity_in_body", ""))

        # Dedupe names within a block, retaining the strongest mention source.
        unique = {}
        for name, source, href in block_names:
            unique.setdefault(name.lower(), (name, source, href))
        for _, (name, source, href) in unique.items():
            if not plausible_entity(name, href):
                continue
            listing = tickers.get(name.lower())
            mention_key = (name.lower(), locator)
            if mention_key not in seen_mentions:
                mentions.append({
                    "article_id": article_id,
                    "source_url": article["canonical_url"],
                    "publisher": article["publisher"],
                    "published_date": article["published_date"],
                    "entity_name_raw": name,
                    "entity_name_normalized_hint": name,
                    "mention_source": source,
                    "linked_url": href or None,
                    "evidence_locator": locator,
                    "context_excerpt": block["text"][:700],
                    "listing_status": "confirmed_in_article" if listing else "unresolved",
                    "exchange": listing["exchange"] if listing else None,
                    "ticker": listing["ticker"] if listing else None,
                    "listing_evidence_locator": listing["listing_evidence_locator"] if listing else None,
                })
                seen_mentions.add(mention_key)

            rel_type, direction, semantic_status, rationale = classify_relation(block["text"], name)
            # Unknown observations are retained only for title counterparties or
            # actual NVIDIA co-mentions; standalone external links stay mentions.
            if rel_type == "unknown" and "nvidia" not in block["text"].lower() and name not in title_names:
                continue
            matches = product_matches(block["text"], products)
            mapping_status = "explicit_in_same_block" if matches else "corporate_general"
            product_context = [
                {"product_name": x["name"], "source_node_id": x["source_node_id"], "mapping_origin": x["mapping_origin"]}
                for x in matches
            ] or [{"product_name": "corporate_general", "source_node_id": "corporate_general", "mapping_origin": "no_explicit_product_in_block"}]
            obs_key = (name.lower(), locator, rel_type)
            if obs_key in seen_obs:
                continue
            observations.append({
                "observation_id": "obs_" + hashlib.sha256(f"{article_id}|{locator}|{name}|{rel_type}".encode()).hexdigest()[:18],
                "article_id": article_id,
                "source_url": article["canonical_url"],
                "publisher": article["publisher"],
                "published_date": article["published_date"],
                "fetched_at": fetched_at,
                "snapshot_path": snapshot_rel,
                "body_sha256": raw_sha,
                "entity_name_raw": name,
                "entity_name_normalized_hint": name,
                "relationship_hint": rel_type,
                "direction_hint": direction,
                "semantic_status": semantic_status,
                "classification_rationale": rationale,
                "evidence_locator": locator,
                "evidence_excerpt": block["text"][:900],
                "product_mapping_status": mapping_status,
                "product_context": product_context,
                "listing_status": "confirmed_in_article" if listing else "unresolved_requires_entity_resolution",
                "exchange": listing["exchange"] if listing else None,
                "ticker": listing["ticker"] if listing else None,
                "listing_evidence_locator": listing["listing_evidence_locator"] if listing else None,
                "age_days_at_cutoff": age_days,
                "freshness_bucket": bucket,
                "freshness_factor_for_root_scoring": factor,
                "access_constraints": "public_no_login; publisher copyright retained; research snapshot only",
                "content_fingerprint": hashlib.sha256(block["text"].encode()).hexdigest(),
                "news_cooccurrence_warning": rel_type == "unknown",
            })
            seen_obs.add(obs_key)

    processing = {
        "article_id": article_id,
        "canonical_url": article["canonical_url"],
        "publisher": article["publisher"],
        "published_date": article["published_date"],
        "title": article["title"],
        "processing_status": "processed_with_candidates" if observations else "processed_no_candidate",
        "processing_reason": f"body parsed; {len(mentions)} entity mentions; {len(observations)} conservative relationship observations",
        "body_snapshot_path": snapshot_rel,
        "body_sha256": raw_sha,
        "extracted_text_sha256": hashlib.sha256(body_text.encode()).hexdigest(),
        "extracted_character_count": len(body_text),
        "block_count": len(blocks),
        "entity_mention_count": len(mentions),
        "observation_count": len(observations),
        "fetched_at": fetched_at,
        "final_url": final_url,
        "evidence_locator_scheme": "body.block[N] in deterministic article-body/entry-content parse",
        "age_days_at_cutoff": age_days,
        "freshness_bucket": bucket,
        "freshness_factor_for_root_scoring": factor,
        "access_constraints": "public_no_login; no access control bypass; publisher copyright retained",
    }
    return processing, mentions, observations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--product-files", nargs="*", type=Path, default=[])
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offline", action="store_true", help="Reuse existing body snapshots; do not make network requests")
    args = parser.parse_args()
    output = args.output.resolve()
    snapshots = output / "body_snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    products = load_products(args.product_files)
    all_manifest = jsonl_read(args.manifest)
    selected = [r for r in all_manifest if START <= date.fromisoformat(r["published_date"]) <= END]
    if args.limit:
        selected = selected[:args.limit]
    if len({r["article_id"] for r in selected}) != len(selected) or len({r["canonical_url"] for r in selected}) != len(selected):
        raise ValueError("selected manifest has duplicate article_id or canonical_url")

    processing_rows: list[dict] = []
    fetch_rows: list[dict] = []
    mention_rows: list[dict] = []
    observation_rows: list[dict] = []
    fetched_at_run = datetime.now(timezone.utc).isoformat()
    for position, article in enumerate(selected, 1):
        article_id = article["article_id"]
        snapshot = snapshots / f"{article_id}.html.gz"
        reused = snapshot.exists()
        fetch_error = ""
        try:
            if reused:
                with gzip.open(snapshot, "rb") as handle:
                    raw = handle.read()
                blocks, body_text, actual_title = parse_body(raw, article["publisher"], article["title"])
                final_url, http_status = article["canonical_url"], 200
            elif args.offline:
                raise FileNotFoundError("offline rebuild: no frozen body snapshot for this article")
            else:
                attempts = 1 if article["publisher"] == "NVIDIA Blog" else 5
                raw, final_url, http_status, retry_notes = fetch(
                    article["canonical_url"], article["title"], article["publisher"], attempts=attempts
                )
                blocks, body_text, actual_title = parse_body(raw, article["publisher"], article["title"])
                with gzip.open(snapshot, "wb", compresslevel=9) as handle:
                    handle.write(raw)
                fetch_error = retry_notes
            digest = hashlib.sha256(raw).hexdigest()
            snapshot_rel = str(snapshot.relative_to(output))
            processing, mentions, observations = process_one(
                article, blocks, body_text, products, snapshot_rel, digest,
                fetched_at_run, final_url,
            )
            processing_rows.append(processing)
            mention_rows.extend(mentions)
            observation_rows.extend(observations)
            fetch_rows.append({
                "article_id": article_id, "source_url": article["canonical_url"],
                "final_url": final_url, "publisher": article["publisher"],
                "published_date": article["published_date"], "fetched_at": fetched_at_run,
                "http_status": http_status, "fetch_status": "success",
                "snapshot_path": snapshot_rel, "sha256": digest, "byte_count": len(raw),
                "actual_html_title": actual_title, "reused_snapshot": reused,
                "retry_notes": fetch_error or None,
                "access_class": "public_no_login",
                "license_note": "Copyright remains with NVIDIA; stored for research/audit, no republication grant inferred.",
            })
        except Exception as exc:
            error = f"{type(exc).__name__}: {str(exc)[:2000]}"
            archive = article.get("archive_observation", {})
            fallback_text = clean_text(" ".join([article.get("title", ""), archive.get("description", "")]))
            fallback_mentions: list[dict] = []
            fallback_observations: list[dict] = []
            if fallback_text:
                _, fallback_mentions, fallback_observations = process_one(
                    article,
                    [{"tag": "archive", "text": fallback_text, "anchors": []}],
                    fallback_text,
                    products,
                    "",
                    hashlib.sha256(fallback_text.encode()).hexdigest(),
                    fetched_at_run,
                    article["canonical_url"],
                )
                fallback_locator = archive.get("evidence_locator") or "archive_observation.description"
                for row in fallback_mentions:
                    row["evidence_locator"] = fallback_locator
                    row["mention_source"] = "official_archive_fallback_" + row["mention_source"]
                    row["context_excerpt"] = fallback_text[:700]
                    row["archive_url"] = archive.get("archive_url")
                    row["body_access_status"] = "access_blocked"
                for row in fallback_observations:
                    row["evidence_locator"] = fallback_locator
                    row["evidence_excerpt"] = fallback_text[:900]
                    row["snapshot_path"] = None
                    row["body_sha256"] = None
                    row["archive_url"] = archive.get("archive_url")
                    row["evidence_basis"] = "official_newsroom_archive_title_and_description_only"
                    row["body_access_status"] = "access_blocked"
                    row["classification_rationale"] += "; body unavailable, do not promote without corroboration"
                mention_rows.extend(fallback_mentions)
                observation_rows.extend(fallback_observations)
            processing_rows.append({
                "article_id": article_id, "canonical_url": article["canonical_url"],
                "publisher": article["publisher"], "published_date": article["published_date"],
                "title": article["title"], "processing_status": "access_blocked",
                "processing_reason": error,
                "body_snapshot_path": None, "body_sha256": None,
                "archive_fallback_locator": archive.get("evidence_locator"),
                "archive_fallback_excerpt": archive.get("description"),
                "archive_fallback_entity_mention_count": len(fallback_mentions),
                "archive_fallback_observation_count": len(fallback_observations),
                "fetched_at": fetched_at_run,
                "access_constraints": "public route failed after bounded retries; no bypass attempted",
                "alternative_route": "use frozen official archive description and retry public canonical URL in a later refresh",
            })
            fetch_rows.append({
                "article_id": article_id, "source_url": article["canonical_url"],
                "publisher": article["publisher"], "published_date": article["published_date"],
                "fetched_at": fetched_at_run, "http_status": None,
                "fetch_status": "access_blocked", "error": error,
                "snapshot_path": None, "sha256": None, "byte_count": None,
                "reused_snapshot": reused, "access_class": "public_no_login_attempted",
                "license_note": "No body stored because public access did not complete.",
            })
        if position < len(selected) and not reused and not args.offline:
            time.sleep(args.delay)
        if position % 25 == 0 or position == len(selected):
            print(f"processed {position}/{len(selected)}; bodies={sum(r['fetch_status']=='success' for r in fetch_rows)}; blocked={sum(r['fetch_status']=='access_blocked' for r in fetch_rows)}", flush=True)

    jsonl_write(output / "article_processing.jsonl", processing_rows)
    jsonl_write(output / "fetch_manifest.jsonl", fetch_rows)
    jsonl_write(output / "entity_mentions.jsonl", mention_rows)
    jsonl_write(output / "observations.jsonl", observation_rows)
    status_counts = Counter(r["processing_status"] for r in processing_rows)
    publisher_counts = Counter(r["publisher"] for r in processing_rows)
    relation_counts = Counter(r["relationship_hint"] for r in observation_rows)
    ledger_closure_pass = (
        len(selected) == len(processing_rows) == len(fetch_rows)
        and len({r["article_id"] for r in processing_rows}) == len(selected)
        and len({r["canonical_url"] for r in processing_rows}) == len(selected)
        and all(r["processing_status"] in FINAL_STATES for r in processing_rows)
        and all(r.get("article_id") and r.get("source_url") and r.get("evidence_locator") and r.get("product_mapping_status") for r in observation_rows)
    )
    successful_bodies = sum(r["fetch_status"] == "success" for r in fetch_rows)
    body_coverage_complete = successful_bodies == len(selected)
    validation = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "research_window": {"start": START.isoformat(), "end": END.isoformat(), "scoring_cutoff": CUTOFF.isoformat()},
        "input_manifest_2025_count": len(selected),
        "processing_ledger_count": len(processing_rows),
        "fetch_manifest_count": len(fetch_rows),
        "unique_article_ids": len({r["article_id"] for r in processing_rows}),
        "unique_canonical_urls": len({r["canonical_url"] for r in processing_rows}),
        "status_counts": dict(status_counts),
        "publisher_counts": dict(publisher_counts),
        "entity_mentions": len(mention_rows),
        "observations": len(observation_rows),
        "relationship_hint_counts": dict(relation_counts),
        "access_blocked_article_ids": [r["article_id"] for r in processing_rows if r["processing_status"] == "access_blocked"],
        "pending_count": sum(r["processing_status"] not in FINAL_STATES for r in processing_rows),
        "all_rows_final": all(r["processing_status"] in FINAL_STATES for r in processing_rows),
        "manifest_ledger_exact_match": {r["article_id"] for r in processing_rows} == {r["article_id"] for r in selected},
        "all_observations_traceable": all(r.get("article_id") and r.get("source_url") and r.get("evidence_locator") and r.get("product_mapping_status") for r in observation_rows),
        "ledger_closure_pass": ledger_closure_pass,
        "successful_body_count": successful_bodies,
        "body_coverage_complete": body_coverage_complete,
        "body_coverage_ratio": f"{successful_bodies}/{len(selected)}",
        "body_coverage_fraction": successful_bodies / len(selected) if selected else 1.0,
        "pass": ledger_closure_pass and body_coverage_complete,
        "notes": [
            "Observations are conservative research candidates, not merged relationship claims.",
            "Unresolved listing status requires root entity resolution before a listed-company final claim.",
            "Unknown means co-mention or ambiguous wording, never an asserted relationship.",
            "Final investee claims may only come from the latest NVIDIA 13F; article investment wording is retained as unknown/non-authoritative context.",
            "Overall pass requires both ledger closure and complete body coverage; a terminal access_blocked ledger row does not satisfy body coverage.",
        ],
    }
    (output / "validation_report.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if validation["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
