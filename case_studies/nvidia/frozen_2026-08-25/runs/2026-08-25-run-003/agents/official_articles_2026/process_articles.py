#!/usr/bin/env python3
"""Reproducibly process the 2026 shard of the frozen NVIDIA article manifest.

The conservative HTML parser/fetcher is shared with the adjacent 2025 shard.
This wrapper fixes the date window and separates append-only raw observations
from final listed-company candidates.  It deliberately performs no search-
engine discovery and never treats a mere news co-mention as a relationship.
"""

from __future__ import annotations

import importlib.util
import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
BASE_SCRIPT = HERE.parent / "official_articles_2025" / "process_articles.py"
SNAPSHOT = HERE.parents[3] / "data" / "snapshot_2026-08-25.json"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_base():
    spec = importlib.util.spec_from_file_location("official_articles_shared", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load shared processor: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.START = date(2026, 1, 1)
    module.END = date(2026, 8, 25)
    return module


def aliases(entity: dict) -> set[str]:
    values = {
        str(entity.get("legal_name", "")),
        str(entity.get("display_name", "")),
        *[str(x) for x in entity.get("aliases", [])],
    }
    # Add slash-separated display-name components while avoiding one-letter keys.
    values |= {part.strip() for value in list(values) for part in value.split("/")}
    return {value.casefold().strip(" .,") for value in values if len(value.strip()) >= 2}


def load_listing_registry() -> tuple[dict[str, dict], list[dict]]:
    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    entities = [row for row in payload.get("entities", []) if row.get("listing_status") == "listed" and row.get("securities")]
    index: dict[str, dict] = {}
    for entity in entities:
        for alias in aliases(entity):
            # Ambiguous ticker-like aliases (LI, GM, AI) are not safe as prose names.
            if len(alias) <= 2 and alias.isalpha():
                continue
            index.setdefault(alias, entity)
    return index, entities


def resolve_listing(name: str, direct_exchange: str | None, direct_ticker: str | None, index: dict[str, dict]) -> tuple[dict | None, str]:
    key = name.casefold().strip(" .,")
    entity = index.get(key)
    if entity:
        return entity, "exact_alias_match_to_frozen_entity_registry"
    # Corporate suffix differences are common in linked article anchors.
    stripped = key
    for suffix in (" corporation", " corp", " corp.", " incorporated", " inc", " inc.", " company", " co.", " limited", " ltd.", " plc"):
        if stripped.endswith(suffix):
            stripped = stripped[: -len(suffix)].strip()
    entity = index.get(stripped)
    if entity:
        return entity, "corporate_suffix_normalized_match_to_frozen_entity_registry"
    if direct_exchange and direct_ticker:
        synthetic = {
            "id": None,
            "legal_name": name,
            "display_name": name,
            "listing_status": "listed",
            "securities": [{"exchange": direct_exchange, "ticker": direct_ticker}],
        }
        return synthetic, "explicit_exchange_ticker_expression_in_article"
    return None, "unresolved"


def registry_mentions(text: str, index: dict[str, dict]) -> list[tuple[str, dict]]:
    """Return longest deterministic registry-alias matches without NER guessing."""
    matches: list[tuple[str, dict]] = []
    seen_entities: set[str] = set()
    for alias, entity in sorted(index.items(), key=lambda item: (-len(item[0]), item[0])):
        entity_id = str(entity.get("id"))
        if entity_id == "nvidia":
            continue
        if entity_id in seen_entities:
            continue
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", text, re.I):
            matches.append((alias, entity))
            seen_entities.add(entity_id)
    return matches


def enforce_article_role_boundary(row: dict) -> dict:
    """Investee claims are owned by the latest 13F shard, never articles."""
    if row.get("relationship_hint") != "investee":
        return row
    result = dict(row)
    result.update({
        "relationship_hint": "unknown",
        "direction_hint": "direction unknown; requires latest 13F verification",
        "semantic_status": "unknown",
        "classification_rationale": "Investment wording retained as an article observation, but investee classification is exclusively sourced from NVIDIA's latest 13F.",
        "news_cooccurrence_warning": True,
        "article_investment_boundary_applied": True,
    })
    return result


def build_index_fallback(output: Path, processing: list[dict], index: dict[str, dict], base) -> tuple[list[dict], list[dict], list[dict]]:
    manifest = {row["article_id"]: row for row in read_jsonl(HERE.parents[1] / "news" / "official_articles.jsonl")}
    products = base.load_products([
        HERE.parents[1] / "product_tree_v2" / "canonical_index_v2.jsonl",
        HERE.parents[1] / "product_tree_v2" / "taxonomy_observations.jsonl",
    ])
    fallback_mentions: list[dict] = []
    fallback_observations: list[dict] = []
    fallback_processing: list[dict] = []
    for ledger in processing:
        if ledger["processing_status"] != "access_blocked":
            continue
        article = manifest[ledger["article_id"]]
        archive = article.get("archive_observation", {})
        title = article.get("title", "")
        description = archive.get("description") or ""
        text = f"{title}. {description}".strip()
        locator = f"{archive.get('evidence_locator', 'article.index-item')} title+description"
        observed: dict[str, tuple[str, dict | None, str]] = {}
        for alias, entity in registry_mentions(text, index):
            observed[str(entity.get("id"))] = (entity.get("display_name") or entity.get("legal_name"), entity, "registry_alias_in_archive_text")
        for name in base.title_entities(title):
            entity, basis = resolve_listing(name, None, None, index)
            key = str(entity.get("id")) if entity else f"raw:{name.casefold()}"
            observed.setdefault(key, (name, entity, "title_counterparty_pattern" if not entity else basis))
        article_mention_start = len(fallback_mentions)
        article_observation_start = len(fallback_observations)
        for key, (name, entity, mention_basis) in observed.items():
            securities = entity.get("securities", []) if entity else []
            identifiers = [f"{sec.get('exchange')}:{sec.get('ticker')}" for sec in securities if sec.get("exchange") and sec.get("ticker")]
            fallback_mentions.append({
                "article_id": article["article_id"],
                "source_url": article["canonical_url"],
                "publisher": article["publisher"],
                "published_date": article["published_date"],
                "entity_name_raw": name,
                "resolved_entity_id": entity.get("id") if entity else None,
                "security_identifiers": identifiers,
                "listing_status": "confirmed_from_frozen_registry" if identifiers else "unresolved",
                "mention_source": "official_archive_index_fallback",
                "mention_basis": mention_basis,
                "evidence_locator": locator,
                "context_excerpt": text[:1200],
                "body_access_status": "access_blocked",
                "fallback_warning": "Official archive title/description only; not article body evidence.",
            })
            if not entity or not identifiers:
                continue
            relationship_hint, direction, semantic_status, rationale = base.classify_relation(text, name)
            product_hits = base.product_matches(text, products)
            product_context = [
                {"product_name": item["name"], "source_node_id": item["source_node_id"], "mapping_origin": item["mapping_origin"]}
                for item in product_hits
            ] or [{"product_name": "corporate_general", "source_node_id": "corporate_general", "mapping_origin": "no_explicit_product_in_archive_text"}]
            published = date.fromisoformat(article["published_date"])
            age_days, bucket, factor = base.age_info(published)
            fallback_observations.append(enforce_article_role_boundary({
                "observation_id": "obs_index_" + hashlib.sha256(f"{article['article_id']}|{key}|{relationship_hint}".encode()).hexdigest()[:18],
                "article_id": article["article_id"],
                "source_url": article["canonical_url"],
                "publisher": article["publisher"],
                "published_date": article["published_date"],
                "entity_name_raw": name,
                "resolved_entity_id": entity.get("id"),
                "resolved_legal_name": entity.get("legal_name"),
                "security_identifiers": identifiers,
                "listing_identity_status": "confirmed",
                "listing_resolution_basis": mention_basis,
                "listing_evidence_source": str(SNAPSHOT.relative_to(HERE.parents[4])),
                "listing_evidence_locator": f"entities[id={entity.get('id')}]",
                "relationship_hint": relationship_hint,
                "direction_hint": direction,
                "semantic_status": semantic_status,
                "classification_rationale": rationale,
                "evidence_source_tier": "official_archive_index_fallback",
                "evidence_locator": locator,
                "evidence_excerpt": text[:1200],
                "product_mapping_status": "explicit_in_archive_text" if product_hits else "corporate_general",
                "product_context": product_context,
                "body_access_status": "access_blocked",
                "fallback_warning": "Not a body-derived claim; retain lower evidence weight and corroborate before final merge.",
                "age_days_at_cutoff": age_days,
                "freshness_bucket": bucket,
                "freshness_factor_for_root_scoring": factor,
                "access_constraints": "public official archive index available; canonical Blog body connection reset; no bypass attempted",
                "content_fingerprint": hashlib.sha256(text.encode()).hexdigest(),
                "news_cooccurrence_warning": relationship_hint == "unknown",
            }))
        article_mentions = len(fallback_mentions) - article_mention_start
        article_observations = len(fallback_observations) - article_observation_start
        fallback_processing.append({
            "article_id": article["article_id"],
            "canonical_url": article["canonical_url"],
            "publisher": article["publisher"],
            "published_date": article["published_date"],
            "fallback_processing_status": "scanned_with_listed_candidates" if article_observations else "scanned_no_listed_candidate",
            "fallback_source": archive.get("archive_url"),
            "evidence_locator": locator,
            "title_description_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "entity_mention_count": article_mentions,
            "listed_observation_count": article_observations,
            "body_access_status": "access_blocked",
            "warning": "Deterministic official archive title+description scan; not a substitute for body review.",
        })
    write_jsonl(output / "index_fallback_entity_mentions.jsonl", fallback_mentions)
    write_jsonl(output / "index_fallback_observations.jsonl", fallback_observations)
    write_jsonl(output / "index_fallback_processing.jsonl", fallback_processing)
    return fallback_mentions, fallback_observations, fallback_processing


def rebuild_body_data(output: Path, processing: list[dict], fetches: list[dict], base) -> list[dict]:
    """Rebuild body ledgers/mentions/observations from frozen snapshots, no network."""
    manifest = {row["article_id"]: row for row in read_jsonl(HERE.parents[1] / "news" / "official_articles.jsonl")}
    fetch_index = {row["article_id"]: row for row in fetches if row.get("fetch_status") == "success"}
    products = base.load_products([
        HERE.parents[1] / "product_tree_v2" / "canonical_index_v2.jsonl",
        HERE.parents[1] / "product_tree_v2" / "taxonomy_observations.jsonl",
    ])
    observations: list[dict] = []
    mentions: list[dict] = []
    for position, ledger in enumerate(processing):
        article_id = ledger["article_id"]
        fetch_row = fetch_index.get(article_id)
        if not fetch_row:
            continue
        snapshot = output / fetch_row["snapshot_path"]
        with gzip.open(snapshot, "rb") as handle:
            raw_html = handle.read()
        blocks, body_text, _ = base.parse_body(raw_html, ledger["publisher"], ledger["title"])
        rebuilt_ledger, rebuilt_mentions, rows = base.process_one(
            manifest[article_id], blocks, body_text, products,
            fetch_row["snapshot_path"], fetch_row["sha256"], fetch_row["fetched_at"], fetch_row["final_url"],
        )
        processing[position] = rebuilt_ledger
        mentions.extend(rebuilt_mentions)
        observations.extend(enforce_article_role_boundary(row) for row in rows)
    write_jsonl(output / "article_processing.jsonl", processing)
    write_jsonl(output / "entity_mentions.jsonl", mentions)
    write_jsonl(output / "raw_relation_observations.jsonl", observations)
    return observations


def postprocess(output: Path) -> None:
    base = load_base()
    processing = read_jsonl(output / "article_processing.jsonl")
    fetches = read_jsonl(output / "fetch_manifest.jsonl")
    raw = rebuild_body_data(output, processing, fetches, base)
    index, registry = load_listing_registry()
    listed: list[dict] = []
    unresolved: list[dict] = []
    for row in raw:
        entity, basis = resolve_listing(row["entity_name_raw"], row.get("exchange"), row.get("ticker"), index)
        if not entity:
            unresolved.append(row)
            continue
        securities = entity.get("securities", [])
        identifiers = [f"{sec.get('exchange')}:{sec.get('ticker')}" for sec in securities if sec.get("exchange") and sec.get("ticker")]
        if not identifiers:
            unresolved.append(row)
            continue
        resolved = dict(row)
        resolved.update({
            "resolved_entity_id": entity.get("id"),
            "resolved_legal_name": entity.get("legal_name"),
            "security_identifiers": identifiers,
            "listing_resolution_basis": basis,
            "listing_evidence_source": str(SNAPSHOT.relative_to(HERE.parents[4])),
            "listing_evidence_locator": f"entities[id={entity.get('id')}]" if entity.get("id") else row.get("listing_evidence_locator"),
            "listing_identity_status": "confirmed",
        })
        listed.append(resolved)
    fallback_mentions, fallback_observations, fallback_processing = build_index_fallback(output, processing, index, base)
    # Final candidates may use either body evidence or clearly marked archive-index
    # fallback evidence.  Their different evidence tiers are never conflated.
    listed.extend(fallback_observations)
    write_jsonl(output / "observations.jsonl", listed)

    original_report = json.loads((output / "validation_report.json").read_text(encoding="utf-8"))
    selected_count = sum(1 for row in read_jsonl(HERE.parents[1] / "news" / "official_articles.jsonl") if "2026-01-01" <= row["published_date"] <= "2026-08-25")
    statuses = Counter(row["processing_status"] for row in processing)
    validation = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "research_window": {"start": "2026-01-01", "end": "2026-08-25", "scoring_cutoff": "2026-08-25"},
        "input_manifest_2026_count": selected_count,
        "processing_ledger_count": len(processing),
        "fetch_manifest_count": len(fetches),
        "unique_article_ids": len({row["article_id"] for row in processing}),
        "unique_canonical_urls": len({row["canonical_url"] for row in processing}),
        "status_counts": dict(statuses),
        "successful_body_snapshots": sum(row.get("fetch_status") == "success" for row in fetches),
        "body_coverage_complete": all(row.get("fetch_status") == "success" for row in fetches),
        "body_coverage_ratio": round(sum(row.get("fetch_status") == "success" for row in fetches) / max(1, len(fetches)), 6),
        "access_blocked_count": statuses.get("access_blocked", 0),
        "access_blocked_article_ids": [row["article_id"] for row in processing if row["processing_status"] == "access_blocked"],
        "raw_relation_observations": len(raw),
        "listed_company_observations": len(listed),
        "index_fallback_entity_mentions": len(fallback_mentions),
        "index_fallback_listed_observations": len(fallback_observations),
        "blocked_articles_scanned_with_index_fallback": len(fallback_processing),
        "index_fallback_processing_exact_blocked_match": (
            {row["article_id"] for row in fallback_processing}
            == {row["article_id"] for row in processing if row["processing_status"] == "access_blocked"}
        ),
        "unresolved_raw_observations": len(unresolved),
        "listed_relationship_hint_counts": dict(Counter(row["relationship_hint"] for row in listed)),
        "pending_count": sum(row["processing_status"] not in {"processed_with_candidates", "processed_no_candidate", "access_blocked", "excluded_with_reason"} for row in processing),
        "ledger_closure_pass": (
            selected_count == len(processing) == len(fetches)
            and len({row["article_id"] for row in processing}) == selected_count
            and len({row["canonical_url"] for row in processing}) == selected_count
            and all(row["processing_status"] in {"processed_with_candidates", "processed_no_candidate", "access_blocked", "excluded_with_reason"} for row in processing)
        ),
        "all_rows_final": all(row["processing_status"] in {"processed_with_candidates", "processed_no_candidate", "access_blocked", "excluded_with_reason"} for row in processing),
        "manifest_ledger_exact_match": selected_count == len(processing),
        "article_id_unique": len({row["article_id"] for row in processing}) == len(processing),
        "canonical_url_unique": len({row["canonical_url"] for row in processing}) == len(processing),
        "all_final_candidates_listed": all(row.get("listing_identity_status") == "confirmed" and row.get("security_identifiers") for row in listed),
        "all_final_candidates_traceable": all(row.get("article_id") and row.get("source_url") and row.get("evidence_locator") and row.get("product_mapping_status") for row in listed),
        "shared_processor_validation_pass_before_listing_filter": original_report.get("pass"),
        "registry_entity_count": len(registry),
        "pass": (
            selected_count == len(processing) == len(fetches)
            and len({row["article_id"] for row in processing}) == selected_count
            and len({row["canonical_url"] for row in processing}) == selected_count
            and all(row["processing_status"] in {"processed_with_candidates", "processed_no_candidate", "access_blocked", "excluded_with_reason"} for row in processing)
            and all(row.get("listing_identity_status") == "confirmed" and row.get("security_identifiers") for row in listed)
            and all(row.get("article_id") and row.get("source_url") and row.get("evidence_locator") and row.get("product_mapping_status") for row in listed)
            and all(row.get("fetch_status") == "success" for row in fetches)
            and {row["article_id"] for row in fallback_processing} == {row["article_id"] for row in processing if row["processing_status"] == "access_blocked"}
        ),
        "notes": [
            "Every 2026 manifest article has one terminal ledger row; access_blocked is terminal bookkeeping, not completed body coverage.",
            "pass is intentionally false until body_coverage_complete is true; ledger_closure_pass reports the separate bookkeeping gate.",
            "raw_relation_observations.jsonl is append-only and can contain unresolved/non-listed mentions.",
            "observations.jsonl contains only listed-company candidates with exchange:ticker identifiers.",
            "A co-mention remains semantic_status=unknown and is never promoted by listing resolution.",
        ],
    }
    (output / "validation_report.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    base = load_base()
    result = base.main()
    output_arg = Path(sys.argv[sys.argv.index("--output") + 1]).resolve()
    postprocess(output_arg)
    report = json.loads((output_arg / "validation_report.json").read_text(encoding="utf-8"))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result == 0 and report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
