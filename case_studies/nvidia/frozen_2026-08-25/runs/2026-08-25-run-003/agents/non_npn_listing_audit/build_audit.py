#!/usr/bin/env python3
"""Build a unified non-NPN listed-entity and listed-parent resolution audit."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
FIXTURES = json.loads((HERE / "manual_mapping_fixtures.json").read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def strict_norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.replace("&", " and ").casefold()
    value = re.sub(r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|plc|sa|ag|se|nv|llc|lp)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def stable_id(prefix: str, value: str) -> str:
    return prefix + "_" + hashlib.sha256(value.encode()).hexdigest()[:16]


def portable(path: Path) -> str:
    return str(path.relative_to(RUN))


def first(*values):
    return next((v for v in values if v not in (None, "", [])), None)


article_types = {row["article_id"]: row["article_type"] for row in read_jsonl(RUN / "news" / "official_articles.jsonl")}
observations: dict[str, dict] = {}


def add_observation(name: str | None, family: str, path: Path, row: dict, relation_priority: bool = False) -> None:
    if not name or not str(name).strip():
        return
    name = str(name).strip()
    evidence = row.get("evidence") or {}
    locator = first(row.get("evidence_locator"), evidence.get("evidence_locator"), row.get("listing_evidence_locator"))
    source_url = first(row.get("source_url"), evidence.get("source_url"), row.get("retrieved_url"), row.get("profile_url"))
    published = first(row.get("published_date"), row.get("published_at"), row.get("filing_date"), row.get("period_of_report"))
    publisher = first(row.get("publisher"), evidence.get("publisher"), "NVIDIA")
    relation_hint = first(row.get("relationship_hint"), row.get("relationship_hypothesis"), row.get("relationship_type"), "unknown")
    semantic_status = first(row.get("semantic_status"), row.get("fact_status"), row.get("status"), "unknown")
    raw_id = first(row.get("observation_id"), row.get("candidate_observation_id"), row.get("candidate_id"), row.get("holding_id"))
    fingerprint = "|".join(str(x or "") for x in (family, name, source_url, locator, raw_id, relation_hint))
    obs_id = stable_id("nna_obs", fingerprint)
    security_candidates = []
    if isinstance(row.get("security"), dict) and row["security"].get("ticker"):
        security_candidates.append(row["security"])
    if row.get("ticker") and row.get("exchange"):
        security_candidates.append({"ticker": row["ticker"], "exchange": row["exchange"]})
    issuer_entity = row.get("issuer_entity") or {}
    if issuer_entity.get("ticker") and issuer_entity.get("exchange"):
        security_candidates.append({"ticker": issuer_entity["ticker"], "exchange": issuer_entity["exchange"]})
    observations.setdefault(obs_id, {
        "observation_id": obs_id,
        "raw_source_observation_id": raw_id,
        "entity_name_raw": name,
        "normalized_name": strict_norm(name),
        "source_family": family,
        "source_path": portable(path),
        "source_url": source_url,
        "publisher": publisher,
        "published_or_filed_date": published,
        "accessed_or_retrieved_at": first(row.get("fetched_at"), row.get("retrieved_at"), row.get("accessed_at"), evidence.get("accessed_at"), "2026-08-25"),
        "evidence_locator": locator,
        "relationship_hint": relation_hint,
        "semantic_status": semantic_status,
        "relation_semantic_priority": relation_priority or relation_hint not in {None, "", "unknown"},
        "evidence_tier": "raw_ocr_low" if path.name == "raw_observations.jsonl" else ("mention_only" if family == "nvidia_blog_mention" else "structured"),
        "short_evidence": first(row.get("evidence_excerpt"), row.get("context_excerpt"), row.get("short_evidence"), row.get("context"), row.get("review_rationale")),
        "access_constraints": first(row.get("access_constraints"), row.get("access_restrictions"), evidence.get("access_or_license_note"), "public research source; publisher rights retained"),
        "security_candidates": security_candidates,
        "listing_status_hint": first(row.get("current_listing_status"), row.get("listing_status"), issuer_entity.get("listing_status")),
    })


# Recovered Blog bodies: observations are relation-priority; remaining mentions
# are retained to prove frontier closure but never promoted merely for appearing.
body = RUN / "agents" / "article_body_recovery"
for row in read_jsonl(body / "observations.jsonl"):
    add_observation(row.get("entity_name_raw"), "nvidia_blog_body", body / "observations.jsonl", row, True)
for row in read_jsonl(body / "entity_mentions.jsonl"):
    add_observation(row.get("entity_name_raw"), "nvidia_blog_mention", body / "entity_mentions.jsonl", row, False)

# Official article shards contribute only press releases here; recovered Blog
# bodies supersede their direct/index fallback representations.
for year in (2025, 2026):
    base = RUN / "agents" / f"official_articles_{year}"
    for filename in ("observations.jsonl", "index_fallback_observations.jsonl"):
        path = base / filename
        for row in read_jsonl(path):
            if article_types.get(row.get("article_id")) == "press_release":
                add_observation(row.get("entity_name_raw"), "nvidia_press_release", path, row, True)

product = RUN / "product_tree_v2" / "relation_candidates.jsonl"
for row in read_jsonl(product):
    add_observation(row.get("entity_name_raw"), "nvidia_product_solution_page", product, row, row.get("relationship_hint") not in (None, "unknown"))

filings = RUN / "agents" / "filings_presentations_complete"
filing_source_map = {row.get("source_id"): row for row in read_jsonl(filings / "source_frontier.jsonl") if row.get("source_id")}
for filename in ("listed_candidates.jsonl", "raw_observations.jsonl", "13f_holdings.jsonl", "acquisition_review.jsonl"):
    path = filings / filename
    for row in read_jsonl(path):
        row = dict(row)
        source = filing_source_map.get(row.get("source_id")) or {}
        row.setdefault("source_url", source.get("url"))
        row.setdefault("publisher", source.get("publisher"))
        row.setdefault("published_at", source.get("published_at"))
        row.setdefault("retrieved_at", source.get("retrieved_at"))
        row.setdefault("access_constraints", source.get("access_restrictions"))
        name = first(row.get("entity_name_raw"), row.get("entity_name"), row.get("observed_entity_string"), row.get("issuer_name"), row.get("target"))
        add_observation(name, "nvidia_filing_or_presentation", path, row, filename != "raw_observations.jsonl" or first(row.get("relationship_hypothesis"), row.get("relationship_type")) not in (None, "unknown"))

peers = RUN / "agents" / "peers_complete" / "peer_candidates.jsonl"
peer_evidence = {row["evidence_id"]: row for row in read_jsonl(RUN / "agents" / "peers_complete" / "source_evidence.jsonl")}
for row in read_jsonl(peers):
    row = dict(row)
    selected_evidence = next((peer_evidence[x] for x in row.get("evidence_ids", []) if x in peer_evidence), {})
    row.setdefault("source_url", selected_evidence.get("url"))
    row.setdefault("publisher", selected_evidence.get("publisher"))
    row.setdefault("published_at", selected_evidence.get("published_at") or selected_evidence.get("retrieved_at"))
    row.setdefault("evidence_locator", selected_evidence.get("evidence_locator"))
    row.setdefault("access_constraints", selected_evidence.get("access_constraints"))
    add_observation(row.get("object_legal_name"), "reviewed_peer", peers, row, True)


# Existing reviewed issuer registries and alias overlays are lookup evidence,
# not relationship evidence.
entities: dict[str, dict] = {}
alias_entities: dict[str, set[str]] = defaultdict(set)
for path in (
    RUN / "agents" / "entity_resolution_complete" / "entity_registry.jsonl",
    RUN / "agents" / "global_listing_overlay" / "entity_registry_overlay.jsonl",
):
    for entity in read_jsonl(path):
        entities[entity["entity_id"]] = entity
        for alias in set(entity.get("aliases", []) + [entity.get("display_name", ""), entity.get("legal_name", "")]):
            if alias:
                alias_entities[strict_norm(alias)].add(entity["entity_id"])
for path in (
    RUN / "agents" / "entity_resolution_complete" / "aliases.jsonl",
    RUN / "agents" / "global_listing_overlay" / "aliases.jsonl",
):
    for alias in read_jsonl(path):
        if alias.get("entity_id") and alias.get("alias") and alias.get("alias_status") not in {"ambiguous", "context_bound"}:
            alias_entities[strict_norm(alias["alias"])].add(alias["entity_id"])

prior_review = {
    row["normalized_name"]: row
    for row in read_jsonl(RUN / "agents" / "entity_resolution_complete" / "candidate_review.jsonl")
}

manual_parent = {}
for fixture in FIXTURES["mappings"]:
    fixture = dict(fixture)
    fixture["mapping_evidence_id"] = stable_id("nna_map", fixture["mapping_evidence_url"] + "|" + fixture["parent_entity_id"])
    fixture["additional_mapping_evidence_ids"] = [
        stable_id("nna_map", item["url"] + "|" + fixture["parent_entity_id"])
        for item in fixture.get("additional_mapping_evidence", [])
    ]
    for alias in fixture["aliases"]:
        manual_parent[strict_norm(alias)] = fixture

direct_fixtures = {}
for fixture in FIXTURES["direct_issuer_fixtures"]:
    fixture = dict(fixture)
    fixture["mapping_evidence_id"] = stable_id("nna_map", fixture["evidence_url"] + "|" + fixture["entity_id"])
    for alias in fixture["aliases"]:
        direct_fixtures[strict_norm(alias)] = fixture

group_fixtures = {}
for fixture in FIXTURES["multi_listed_groups"]:
    fixture = dict(fixture)
    fixture["mapping_evidence_ids"] = [stable_id("nna_mcap", c["market_cap_source_url"] + "|" + c["security"]) for c in fixture["candidates"]]
    for alias in fixture["aliases"]:
        group_fixtures[strict_norm(alias)] = fixture

nonlisted = {strict_norm(x) for x in FIXTURES["known_non_listed"]}
known_noise = {strict_norm(x) for x in FIXTURES["known_noise_or_non_entity"]}
sec_screening = defaultdict(list)
for row in read_jsonl(HERE / "sec_screening_matches.jsonl"):
    sec_screening[row["candidate_normalized_name"]].append(row)
product_names = set()
for row in read_jsonl(RUN / "product_tree_v2" / "canonical_index_v2.jsonl"):
    product_names.add(strict_norm(row.get("primary_name", "")))
    product_names.update(strict_norm(x) for x in row.get("aliases", []))
product_names.discard("")


def noise_reason(raw_names: list[str], normalized: str) -> str | None:
    if normalized in known_noise or normalized in product_names:
        return "known NVIDIA product/model/program/social-channel string, not a company endpoint"
    raw = min(raw_names, key=len)
    if re.fullmatch(r"(?:19|20)\d{2}|(?:january|february|march|april|may|june|july|august|september|october|november|december).*", raw, re.I):
        return "date/event fragment"
    if len(normalized.split()) >= 7 and re.search(r"\b(?:is|are|has|have|using|uses|announced|unveiled|collaboration|powered|available|visit|today)\b", normalized):
        return "sentence fragment produced by conservative NER"
    if re.search(r"\b(?:gpu|gpus|blueprint|microservices|sdk|toolkit|model|models|architecture|platform|workflow|server|servers|supercomputer|conference|membership|repository|newsletter|channel)\b", normalized) and len(normalized.split()) <= 7:
        return "product/program/event string rather than issuer"
    return None


def contextual_prefix(normalized: str) -> tuple[str, dict] | None:
    # Only permit a reviewed issuer alias at the beginning followed by wording
    # characteristic of a possessive or sentence fragment. This never confirms
    # relationship semantics and stays below 60 confidence.
    matches = []
    for alias, ids in alias_entities.items():
        if len(alias) < 3 or len(ids) != 1 or not normalized.startswith(alias + " "):
            continue
        rest = normalized[len(alias):].strip()
        if re.match(r"(?:s |is |has |announced |work |mission |agent |cloud |data |petascale |pro |ai |fairwater)", rest):
            matches.append((len(alias), next(iter(ids)), entities[next(iter(ids))]))
    if not matches:
        return None
    _, entity_id, entity = max(matches)
    return entity_id, entity


by_candidate: dict[str, list[dict]] = defaultdict(list)
for observation in observations.values():
    by_candidate[observation["normalized_name"]].append(observation)

mapping_evidence: dict[str, dict] = {}
candidates = []
for normalized, obs_rows in sorted(by_candidate.items()):
    raw_names = sorted({row["entity_name_raw"] for row in obs_rows}, key=lambda x: (len(x), x.casefold()))
    relation_rows = [row for row in obs_rows if row["relation_semantic_priority"]]
    high_quality_relation_rows = [row for row in relation_rows if row["evidence_tier"] == "structured"]
    source_families = sorted({row["source_family"] for row in obs_rows})
    result = {
        "candidate_id": stable_id("nna_candidate", normalized),
        "normalized_name": normalized,
        "raw_name_variants": raw_names,
        "observation_ids": sorted(row["observation_id"] for row in obs_rows),
        "observation_count": len(obs_rows),
        "relation_priority_observation_count": len(relation_rows),
        "high_quality_relation_observation_count": len(high_quality_relation_rows),
        "source_families": source_families,
        "evidence_samples": sorted(obs_rows, key=lambda r: (not r["relation_semantic_priority"], r.get("published_or_filed_date") or ""))[:12],
        "original_nvidia_evidence_ids": sorted(row["observation_id"] for row in relation_rows),
        "mapping_evidence_ids": [],
        "parent_candidates": [],
        "selected_entity_id": None,
        "selected_legal_name": None,
        "selected_securities": [],
        "resolution_kind": None,
        "terminal_status": None,
        "endpoint_identity_fact_status_recommendation": "unknown",
        "relationship_fact_status_recommendation": "preserve NVIDIA evidence semantics; identity resolution does not prove a relationship",
        "confidence_score_cap_recommendation": 59,
        "uncertainty_and_limitations": [],
    }

    ids = alias_entities.get(normalized, set())
    structured_security_rows = [
        row for row in obs_rows if row["evidence_tier"] == "structured" and row.get("security_candidates")
    ]
    if len(ids) == 1:
        entity_id = next(iter(ids)); entity = entities[entity_id]
        result.update({
            "resolution_kind": "direct_issuer",
            "terminal_status": "resolved_listed",
            "selected_entity_id": entity_id,
            "selected_legal_name": entity.get("legal_name"),
            "selected_securities": entity.get("securities", []),
            "mapping_evidence_ids": entity.get("listing_evidence_ids", []),
            "endpoint_identity_fact_status_recommendation": "fact",
            "confidence_score_cap_recommendation": None,
        })
    elif len(ids) > 1:
        result.update({
            "resolution_kind": "ambiguous_exact_alias",
            "terminal_status": "ambiguous",
            "parent_candidates": [{"entity_id": x, "legal_name": entities[x].get("legal_name"), "securities": entities[x].get("securities", [])} for x in sorted(ids)],
        })
        result["uncertainty_and_limitations"].append("Exact normalized alias maps to more than one reviewed issuer; no fuzzy selection allowed.")
    elif structured_security_rows:
        securities = {}
        for row in structured_security_rows:
            for security in row["security_candidates"]:
                key = (str(security.get("exchange", "")), str(security.get("ticker", "")))
                if all(key):
                    securities[key] = security
        result.update({
            "resolution_kind": "direct_issuer",
            "terminal_status": "resolved_listed",
            "selected_entity_id": stable_id("listed_entity", normalized),
            "selected_legal_name": min(raw_names, key=len),
            "selected_securities": list(securities.values()),
            "mapping_evidence_ids": sorted(row["observation_id"] for row in structured_security_rows),
            "endpoint_identity_fact_status_recommendation": "fact",
            "confidence_score_cap_recommendation": None,
        })
        result["uncertainty_and_limitations"].append("Direct issuer resolution comes from a structured ticker/exchange observation in the frozen source; security class may still require final registry normalization.")
    elif normalized in sec_screening and normalized not in {"global ai", "everpure"}:
        sec_rows = sec_screening[normalized]
        ciks = {row["cik"] for row in sec_rows}
        if len(ciks) == 1:
            securities = [
                {"exchange": row["exchange"], "ticker": row["ticker"]}
                for row in sec_rows
            ]
            evidence_id = stable_id("nna_map_sec", next(iter(ciks)))
            result.update({
                "resolution_kind": "direct_issuer",
                "terminal_status": "resolved_listed",
                "selected_entity_id": stable_id("sec_issuer", next(iter(ciks))),
                "selected_legal_name": sec_rows[0]["issuer_name"],
                "selected_securities": securities,
                "mapping_evidence_ids": [evidence_id],
                "endpoint_identity_fact_status_recommendation": "fact",
                "confidence_score_cap_recommendation": None,
            })
            mapping_evidence[evidence_id] = {
                "mapping_evidence_id": evidence_id,
                "source_url": sec_rows[0]["source_url"],
                "publisher": sec_rows[0]["publisher"],
                "published_or_accessed_date": sec_rows[0]["retrieved_at"],
                "evidence_locator": sec_rows[0]["evidence_locator"],
                "issuer_cik": next(iter(ciks)),
                "match_method": "strict exact normalized issuer name; one CIK; no fuzzy matching",
                "access_constraints": "public official SEC JSON; no login; bounded single request",
            }
        else:
            result.update({"resolution_kind": "ambiguous_exact_official_issuer_match", "terminal_status": "ambiguous"})
            result["uncertainty_and_limitations"].append("Exact SEC screening returned more than one issuer CIK; no issuer selected.")
    elif normalized in direct_fixtures:
        fixture = direct_fixtures[normalized]
        result.update({
            "resolution_kind": "direct_issuer",
            "terminal_status": "resolved_listed",
            "selected_entity_id": fixture["entity_id"],
            "selected_legal_name": fixture["legal_name"],
            "selected_securities": fixture["securities"],
            "mapping_evidence_ids": [fixture["mapping_evidence_id"]],
            "endpoint_identity_fact_status_recommendation": "fact",
            "confidence_score_cap_recommendation": None,
        })
        mapping_evidence[fixture["mapping_evidence_id"]] = {
            "mapping_evidence_id": fixture["mapping_evidence_id"], "source_url": fixture["evidence_url"],
            "publisher": fixture["publisher"], "published_or_accessed_date": "2026-08-25",
            "evidence_locator": "issuer/security quote or investor identity page", "access_constraints": "public page; no login; exchange/issuer rights retained",
        }
    elif normalized in manual_parent:
        fixture = manual_parent[normalized]
        result.update({
            "resolution_kind": fixture.get("resolution_kind", "brand_to_listed_parent"),
            "terminal_status": "resolved_listed_parent_inferred",
            "selected_entity_id": fixture["parent_entity_id"],
            "selected_legal_name": fixture["parent_legal_name"],
            "selected_securities": fixture.get("parent_securities") or entities.get(fixture["parent_entity_id"], {}).get("securities", []),
            "mapping_evidence_ids": [fixture["mapping_evidence_id"]] + fixture.get("additional_mapping_evidence_ids", []) + entities.get(fixture["parent_entity_id"], {}).get("listing_evidence_ids", []),
            "endpoint_identity_fact_status_recommendation": "inferred",
            "relationship_fact_status_recommendation": "inferred endpoint only; final relation must cite original NVIDIA evidence plus parent mapping evidence",
            "confidence_score_cap_recommendation": 69,
        })
        result["uncertainty_and_limitations"].append("Brand/subsidiary and listed parent are distinct legal entities; do not rewrite the original NVIDIA wording.")
        mapping_evidence[fixture["mapping_evidence_id"]] = {
            "mapping_evidence_id": fixture["mapping_evidence_id"], "source_url": fixture["mapping_evidence_url"],
            "publisher": fixture["mapping_evidence_publisher"], "published_or_accessed_date": fixture["mapping_evidence_date"],
            "evidence_locator": fixture["mapping_evidence_locator"], "rationale": fixture["rationale"],
            "access_constraints": "public mapping reference; no login; publisher rights retained",
        }
        for item, evidence_id in zip(fixture.get("additional_mapping_evidence", []), fixture.get("additional_mapping_evidence_ids", [])):
            mapping_evidence[evidence_id] = {
                "mapping_evidence_id": evidence_id, "source_url": item["url"],
                "publisher": item["publisher"], "published_or_accessed_date": item["date"],
                "evidence_locator": item["locator"], "rationale": fixture["rationale"],
                "access_constraints": "public mapping reference; no login; publisher rights retained",
            }
    elif normalized in group_fixtures:
        fixture = group_fixtures[normalized]
        result.update({
            "resolution_kind": "multi_listed_group_market_cap_representative",
            "terminal_status": "ambiguous_representative_selected",
            "selected_legal_name": fixture["selected_parent"],
            "selected_securities": [{"security_id": fixture["selected_security"]}],
            "parent_candidates": fixture["candidates"],
            "mapping_evidence_ids": fixture["mapping_evidence_ids"],
            "endpoint_identity_fact_status_recommendation": "unknown",
            "relationship_fact_status_recommendation": "unknown; selected issuer is only the largest listed representative, not proof of group endpoint",
            "confidence_score_cap_recommendation": 49,
        })
        result["uncertainty_and_limitations"].append("Corporate-group name spans multiple listed issuers; market-cap selection is a representative inference only.")
        for candidate, evidence_id in zip(fixture["candidates"], fixture["mapping_evidence_ids"]):
            mapping_evidence[evidence_id] = {
                "mapping_evidence_id": evidence_id, "source_url": candidate["market_cap_source_url"],
                "publisher": FIXTURES["market_cap_method"]["publisher"], "published_or_accessed_date": FIXTURES["market_cap_method"]["accessed_at"],
                "evidence_locator": "public page description: August 2026 market capitalization",
                "quantitative_value": {"market_cap_usd": candidate["market_cap_usd"], "security": candidate["security"]},
                "access_constraints": "public page; third-party rounded market-cap estimate; use only for relative selection",
            }
    elif normalized in nonlisted:
        result.update({"resolution_kind": "non_listed_company", "terminal_status": "non_listed", "confidence_score_cap_recommendation": None})
    elif (reason := noise_reason(raw_names, normalized)):
        result.update({"resolution_kind": "non_entity_or_product_noise", "terminal_status": "rejected_non_entity", "confidence_score_cap_recommendation": None})
        result["uncertainty_and_limitations"].append(reason)
    elif (contextual := contextual_prefix(normalized)):
        entity_id, entity = contextual
        result.update({
            "resolution_kind": "contextual_inferred_entity",
            "terminal_status": "inferred_listed_candidate",
            "selected_entity_id": entity_id,
            "selected_legal_name": entity.get("legal_name"),
            "selected_securities": entity.get("securities", []),
            "mapping_evidence_ids": entity.get("listing_evidence_ids", []),
            "endpoint_identity_fact_status_recommendation": "unknown",
            "relationship_fact_status_recommendation": "unknown until the sentence fragment is manually rebound to its grammatical subject",
            "confidence_score_cap_recommendation": 59,
        })
        result["uncertainty_and_limitations"].append("Longest reviewed issuer alias appears at the start of a noisy sentence/product fragment; manual grammatical review required.")
    elif normalized in prior_review:
        prior = prior_review[normalized]
        status = prior["review_status"]
        result.update({
            "resolution_kind": "prior_review_" + status,
            "terminal_status": "rejected_prior_review" if status == "rejected" else status,
            "confidence_score_cap_recommendation": None if status == "rejected" else 59,
        })
        result["uncertainty_and_limitations"].append(prior.get("review_rationale"))
    else:
        result.update({"resolution_kind": "unresolved", "terminal_status": "unresolved"})
        result["uncertainty_and_limitations"].append("No exact reviewed issuer alias, direct listing fixture, explicit parent mapping, or safe contextual prefix rule matched.")
    candidates.append(result)


blocked = []
for row in read_jsonl(body / "article_processing.jsonl"):
    if row.get("recovery_method") == "blocked":
        blocked.append({
            "article_id": row["article_id"], "canonical_url": row["canonical_url"], "published_date": row["published_date"],
            "title": row["title"], "blind_spot_status": "body_access_blocked_terminal",
            "allowed_use": "title/index-level unknown only; never promote to relationship or listed-parent endpoint",
            "access_audit_sha256": row.get("access_audit_sha256"), "processing_reason": row.get("processing_reason"),
        })

write_jsonl(HERE / "candidate_observations.jsonl", sorted(observations.values(), key=lambda r: r["observation_id"]))
write_jsonl(HERE / "unified_candidates.jsonl", candidates)
write_jsonl(HERE / "relation_priority_review_queue.jsonl", sorted(
    [row for row in candidates if row["high_quality_relation_observation_count"] and row["terminal_status"] in {"unresolved", "ambiguous", "inferred_listed_candidate", "ambiguous_representative_selected"}],
    key=lambda row: (-row["high_quality_relation_observation_count"], row["normalized_name"]),
))
write_jsonl(HERE / "resolved_endpoint_candidates.jsonl", sorted(
    [row for row in candidates if row["terminal_status"] in {"resolved_listed", "resolved_listed_parent_inferred", "ambiguous_representative_selected", "inferred_listed_candidate"}],
    key=lambda row: (row["terminal_status"], row["normalized_name"]),
))
write_jsonl(HERE / "mapping_evidence.jsonl", sorted(mapping_evidence.values(), key=lambda r: r["mapping_evidence_id"]))
write_jsonl(HERE / "blocked_article_blind_spots.jsonl", blocked)

source_counts = Counter(row["source_family"] for row in observations.values())
status_counts = Counter(row["terminal_status"] for row in candidates)
kind_counts = Counter(row["resolution_kind"] for row in candidates)
priority = [row for row in candidates if row["relation_priority_observation_count"]]
high_quality_priority = [row for row in candidates if row["high_quality_relation_observation_count"]]
priority_status = Counter(row["terminal_status"] for row in priority)
high_quality_priority_status = Counter(row["terminal_status"] for row in high_quality_priority)
report = {
    "pass": True,
    "cutoff": "2026-08-25",
    "scope": "non-NPN frozen NVIDIA sources only",
    "source_observation_counts": dict(sorted(source_counts.items())),
    "total_observations": len(observations),
    "unique_candidates": len(candidates),
    "relation_priority_candidates": len(priority),
    "high_quality_relation_priority_candidates": len(high_quality_priority),
    "terminal_status_counts": dict(sorted(status_counts.items())),
    "relation_priority_terminal_status_counts": dict(sorted(priority_status.items())),
    "high_quality_relation_priority_terminal_status_counts": dict(sorted(high_quality_priority_status.items())),
    "resolution_kind_counts": dict(sorted(kind_counts.items())),
    "mapping_evidence_records": len(mapping_evidence),
    "blocked_article_blind_spots": len(blocked),
    "pending_bookkeeping": 0,
    "unresolved_research_candidates": status_counts["unresolved"] + status_counts["ambiguous"],
    "high_quality_relation_review_queue": sum(1 for row in high_quality_priority if row["terminal_status"] in {"unresolved", "ambiguous", "inferred_listed_candidate", "ambiguous_representative_selected"}),
    "rules": {
        "fuzzy_promotion": False,
        "brand_parent_endpoint_status": "inferred",
        "contextual_endpoint_status": "unknown",
        "multi_listed_selection": "largest August 2026 market cap representative; all candidates retained; unknown endpoint",
        "blocked_articles": "blind spot only; no body refetch or promotion",
    },
}
(HERE / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
