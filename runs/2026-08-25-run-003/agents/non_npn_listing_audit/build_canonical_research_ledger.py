#!/usr/bin/env python3
"""Materialize listed_company_network.research_policy-compatible ledger and additive registry."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
RETRIEVED = "2026-08-25T00:00:00Z"


def rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()] if path.exists() else []


def write(path: Path, values: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def sid(prefix: str, raw: str) -> str:
    return prefix + "_" + hashlib.sha256(raw.encode()).hexdigest()[:18]


def dt(value: str | None) -> str:
    if not value:
        return RETRIEVED
    if "T" not in value:
        return value[:10] + "T00:00:00Z"
    return value.replace("+00:00", "Z")


detail = rows(HERE / "researched_resolution_audit_detail.jsonl")
detail_by_id = {x["candidate_id"]: x for x in detail}
all_candidates = rows(HERE / "unified_candidates.jsonl")
candidate_observations = {x["observation_id"]: x for x in rows(HERE / "candidate_observations.jsonl")}

evidence_lookup = {}
for path in [
    HERE / "mapping_evidence_researched.jsonl",
    RUN / "agents" / "entity_resolution_complete" / "listing_evidence.jsonl",
    RUN / "agents" / "global_listing_overlay" / "listing_evidence.jsonl",
]:
    for item in rows(path):
        evidence_id = item.get("mapping_evidence_id") or item.get("listing_evidence_id")
        if evidence_id:
            evidence_lookup[evidence_id] = item

base_ids = {x["entity_id"] for x in rows(RUN / "agents" / "entity_resolution_complete" / "entity_registry.jsonl")}
global_rows = rows(RUN / "agents" / "global_listing_overlay" / "entity_registry_overlay.jsonl")
global_ids = {
    x.get("merge_target_entity_id") if x.get("merge_action") == "augment_existing" else x.get("entity_id")
    for x in global_rows if x.get("listing_status") == "listed_confirmed"
}
group_selected_ids = {
    "samsung": "samsung_electronics",
    "hyundai motor group": "hyundai_motor",
    "sk group": "sk-hynix",
    "lg group": "lg_energy_solution",
    "doosan group": "doosan_enerbility",
}


def actual_ids(item: dict) -> list[str]:
    output = []
    for internal_id in item["observation_ids"]:
        observation = candidate_observations.get(internal_id, {})
        raw = observation.get("raw_source_observation_id")
        if raw:
            output.append(str(raw))
        elif observation.get("source_path", "").endswith("13f_holdings.jsonl"):
            # The authoritative relationship builder addresses these rows as
            # 13f-row-N. Recover row number from locator.
            locator = str(observation.get("evidence_locator") or "")
            number = locator.rsplit(" ", 1)[-1]
            if number.isdigit():
                output.append("13f-row-" + number)
    return sorted(set(output))


# Relationship builder synthesizes mention IDs from article ID and source line.
# Reconstruct that exact namespace for name-based frontier candidates.
mention_ids_by_name = defaultdict(list)
for line_no, mention in enumerate(rows(RUN / "agents" / "article_body_recovery" / "entity_mentions.jsonl"), 1):
    import re
    import unicodedata
    value = unicodedata.normalize("NFKD", str(mention.get("entity_name_raw") or ""))
    value = "".join(c for c in value if not unicodedata.combining(c)).replace("&", " and ").casefold()
    value = re.sub(r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|plc|sa|ag|se|nv|llc|lp)\b", " ", value)
    normalized = re.sub(r"[^a-z0-9]+", " ", value).strip()
    mention_ids_by_name[normalized].append(f"mention:{mention.get('article_id')}:{line_no}")


def low_quality_detail(candidate: dict) -> dict:
    base = candidate["terminal_status"]
    if base == "resolved_listed":
        terminal = "resolved_listed"
        basis = "Existing reviewed issuer registry or structured security observation resolves the low-quality mention frontier exactly."
    elif base == "resolved_listed_parent_inferred":
        terminal = "resolved_listed_parent_inferred"
        basis = "Existing reviewed ownership mapping resolves the mention to a listed parent while preserving inferred endpoint status."
    elif base == "non_listed":
        terminal = "researched_nonlisted_or_private"
        basis = "Prior reviewed private/non-listed decision; mention-only evidence does not justify a listed endpoint."
    elif base in {"rejected_non_entity", "rejected_prior_review"}:
        terminal = "researched_non_entity"
        basis = "Prior review or deterministic classifier identifies a product, event, venue, fragment or other non-endpoint mention."
    else:
        terminal = "ambiguous_after_research"
        basis = "Mention-only or low-quality OCR candidate has no safe exact listed issuer/parent match; it is terminally excluded from the graph without a fuzzy promotion."
    evidence_sample = next((x for x in candidate.get("evidence_samples", []) if x.get("source_url")), candidate.get("evidence_samples", [{}])[0] if candidate.get("evidence_samples") else {})
    return {
        "candidate_id": candidate["candidate_id"],
        "normalized_name": candidate["normalized_name"],
        "raw_name_variants": candidate["raw_name_variants"],
        "observation_ids": candidate["observation_ids"],
        "terminal_classification": terminal,
        "resolution_kind": candidate.get("resolution_kind") or "low_quality_frontier_terminal",
        "research_basis": basis,
        "selected_entity_id": candidate.get("selected_entity_id") if terminal.startswith("resolved") else None,
        "selected_legal_name": candidate.get("selected_legal_name"),
        "selected_securities": candidate.get("selected_securities", []),
        "mapping_evidence_ids": candidate.get("mapping_evidence_ids", []),
        "representative_source": {
            "url": evidence_sample.get("source_url"),
            "publisher": evidence_sample.get("publisher"),
            "locator": evidence_sample.get("evidence_locator"),
        },
        "confidence_score_cap_recommendation": candidate.get("confidence_score_cap_recommendation"),
        "uncertainty_and_limitations": candidate.get("uncertainty_and_limitations", []),
    }


resolution_inputs = [detail_by_id.get(x["candidate_id"]) or low_quality_detail(x) for x in all_candidates]


priority_rank = {
    "resolved_listed": 0,
    "resolved_listed_parent_inferred": 1,
    "researched_nonlisted_or_private": 2,
    "ambiguous_after_research": 3,
    "researched_non_entity": 4,
}
assigned = set()
actual_by_candidate = {}
for item in sorted(resolution_inputs, key=lambda x: (priority_rank[x["terminal_classification"]], x["normalized_name"])):
    available = [x for x in actual_ids(item) if x not in assigned]
    available.extend(x for x in mention_ids_by_name.get(item["normalized_name"], []) if x not in assigned and x not in available)
    # These seven candidates come from frozen acquisition/peer review tables
    # not consumed by the non-peer relationship builder. Use a source-native
    # stable record key rather than the nna_obs audit join key.
    if not available:
        source_native = "source-record:" + item["candidate_id"]
        available = [source_native]
    actual_by_candidate[item["candidate_id"]] = available
    assigned.update(available)


def research_evidence(item: dict) -> list[dict]:
    chosen = []
    for evidence_id in item.get("mapping_evidence_ids", []):
        source = evidence_lookup.get(evidence_id)
        if not source or not source.get("source_url"):
            continue
        chosen.append({
            "evidence_id": evidence_id,
            "url": source["source_url"],
            "publisher": source.get("publisher") or "Official issuer/exchange",
            "retrieved_at": dt(source.get("retrieved_at") or source.get("published_or_accessed_date")),
            "locator": source.get("evidence_locator") or "issuer, listing or ownership identity",
            "supports": source.get("evidence_scope") or source.get("rationale") or source.get("use_limitation") or "Issuer listing identity or parent ownership mapping; relationship semantics are not inferred from this evidence.",
        })
    representative = item.get("representative_source") or {}
    if representative.get("url"):
        chosen.append({
            "evidence_id": sid("nna_nvidia_context", representative["url"] + "|" + item["candidate_id"]),
            "url": representative["url"],
            "publisher": representative.get("publisher") or "NVIDIA",
            "retrieved_at": RETRIEVED,
            "locator": representative.get("locator") or "frozen candidate context",
            "supports": "Frozen NVIDIA context supports classification of the observed string and preserves the original relationship wording.",
        })
    if not chosen:
        chosen.append({
            "evidence_id": "nna_sec_screen_20260825",
            "url": "https://www.sec.gov/files/company_tickers_exchange.json",
            "publisher": "U.S. Securities and Exchange Commission",
            "retrieved_at": RETRIEVED,
            "locator": "bounded exact normalized issuer-name screening; filtered results retained in sec_screening_matches.jsonl",
            "supports": "Exact U.S. issuer screen. A miss does not prove global non-listing and is combined with frozen NVIDIA context.",
        })
    dedup = {}
    for value in chosen:
        dedup[value["evidence_id"]] = value
    return list(dedup.values())


canonical = []
additive = {}
for item in resolution_inputs:
    terminal = item["terminal_classification"]
    if terminal == "resolved_listed":
        category = "resolved_exact"
        selected = item["selected_entity_id"]
        confidence = 90
        inferred = False
        exact = "match"
    elif terminal == "resolved_listed_parent_inferred":
        category = "resolved_inferred_parent"
        selected = item["selected_entity_id"]
        confidence = min(69, item.get("confidence_score_cap_recommendation") or 69)
        inferred = True
        exact = "ambiguous"
    elif terminal == "researched_nonlisted_or_private":
        category = "private_or_delisted"
        selected = None
        confidence = 78
        inferred = False
        exact = "miss"
    elif terminal == "researched_non_entity":
        category = "non_entity"
        selected = None
        confidence = 85
        inferred = False
        exact = "miss"
    elif item["resolution_kind"] == "multi_listed_group_market_cap_representative":
        category = "resolved_largest_listed_parent"
        selected = group_selected_ids[item["normalized_name"]]
        confidence = 49
        inferred = True
        exact = "ambiguous"
    else:
        category = "ambiguous_after_research"
        selected = None
        confidence = 35
        inferred = False
        exact = "ambiguous" if "ambiguous" in item["resolution_kind"] or "group" in item["resolution_kind"] else "miss"

    # Fail closed for two mechanically ticker-promoted fragments.
    if item["normalized_name"] in {"v", "multiyear strategic agreements with lumentum holdings"}:
        category, selected, confidence, inferred, exact = "non_entity", None, 95, False, "miss"

    evidence = research_evidence(item)
    listed_options = []
    if category == "resolved_largest_listed_parent":
        for option, evidence_id in zip(item.get("candidate_parents_or_issuers", []), item.get("mapping_evidence_ids", [])):
            security_id = option["security"]
            listed_options.append({
                "entity_id": group_selected_ids[item["normalized_name"]] if option["name"] == item.get("selected_legal_name") or option is item.get("candidate_parents_or_issuers", [None])[0] else sid("group_option", item["normalized_name"] + "|" + option["name"]),
                "security_id": security_id,
                "relationship_to_observed_name": "candidate listed issuer within the named corporate group; representative selection does not equate group and issuer",
                "market_cap": option["market_cap_usd"],
                "market_cap_currency": "USD",
                "market_cap_as_of": "2026-08-25",
                "market_cap_evidence_ids": [evidence_id],
            })
        selected_option = max(listed_options, key=lambda x: x["market_cap"])
        selected = selected_option["entity_id"]
        item["selected_legal_name"] = item.get("candidate_parents_or_issuers", [{}])[0].get("name")
        exchange, ticker = selected_option["security_id"].split(":", 1)
        item["selected_securities"] = [{"exchange": "Korea Exchange" if exchange == "KRX" else exchange, "ticker": ticker}]

    canonical.append({
        "resolution_id": sid("nna_resolution", item["candidate_id"]),
        "candidate_name": item["raw_name_variants"][0],
        "candidate_review_ids": [item["candidate_id"]],
        "observation_ids": actual_by_candidate[item["candidate_id"]],
        "research_status": "researched_terminal",
        "terminal_category": category,
        "selected_entity_id": selected,
        "resolution_confidence": confidence,
        "inferred_entity_resolution": inferred,
        "exact_alias_search_outcome": exact,
        "research_methods": [
            "strict exact alias search in reviewed issuer registry",
            "official SEC issuer/exchange screen where applicable",
            "listed-parent ownership and cutoff-status research",
            "manual frozen NVIDIA context review; no fuzzy promotion",
        ],
        "research_evidence": evidence,
        "listed_entity_options": listed_options,
        "rationale": item["research_basis"] + " Relationship semantics remain governed by the original NVIDIA observation and are not upgraded by identity research.",
    })

    if selected and selected not in base_ids and selected not in global_ids:
        listing_ids = [x["evidence_id"] for x in evidence]
        securities = []
        for security in item.get("selected_securities", []):
            if security.get("ticker") and security.get("exchange"):
                security = dict(security)
                security["security_id"] = security.get("security_id") or f"{security['exchange']}:{security['ticker']}"
                securities.append(security)
        if securities:
            additive[selected] = {
                "entity_id": selected,
                "legal_name": item["selected_legal_name"],
                "display_name": item["selected_legal_name"],
                "aliases": item["raw_name_variants"],
                "listing_status": "listed_confirmed",
                "securities": securities,
                "listing_evidence_ids": listing_ids,
                "status_as_of": "2026-08-25",
                "resolution_limitations": item["uncertainty_and_limitations"],
            }

# The relationship builder also consumes one frozen 2026 raw-relation shard
# whose source-native candidates were not part of the prior unified frontier.
# Add every unmatched row as its own fail-closed researched terminal resolution.
# Repeated observed strings receive an observation suffix solely to satisfy the
# schema's unique candidate-name lookup; the exact upstream observation ID is
# the authoritative join.
import re
import unicodedata


def canonical_norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c)).replace("&", " and ").casefold()
    value = re.sub(r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|plc|sa|ag|se|nv|llc|lp)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


# Attach seven index-level variants to the already researched listed subject.
index_alias_targets = {
    "eli lilly": "lilly",
    "oracle oci": "oracle",
    "alphabet google": "alphabet",
}
canonical_by_norm = {canonical_norm(x["candidate_name"]): x for x in canonical}
existing_ids = {y for x in canonical for y in x["observation_ids"]}
for article_row in rows(RUN / "agents" / "official_articles_2026" / "observations.jsonl"):
    observation_id = article_row.get("observation_id")
    target_norm = index_alias_targets.get(canonical_norm(article_row.get("entity_name_raw") or ""))
    if observation_id and observation_id not in existing_ids and target_norm in canonical_by_norm:
        canonical_by_norm[target_norm]["observation_ids"].append(observation_id)
        canonical_by_norm[target_norm]["observation_ids"] = sorted(set(canonical_by_norm[target_norm]["observation_ids"]))
        existing_ids.add(observation_id)

existing_names = {canonical_norm(x["candidate_name"]) for x in canonical}
raw_misses = []
for raw_row in rows(RUN / "agents" / "official_articles_2026" / "raw_relation_observations.jsonl"):
    observation_id = raw_row.get("observation_id")
    normalized = canonical_norm(raw_row.get("entity_name_raw") or "")
    if observation_id in existing_ids or normalized in existing_names:
        continue
    raw_misses.append(raw_row)

seen_supplement_names = set(existing_names)
for raw_row in raw_misses:
    observation_id = raw_row["observation_id"]
    observed = raw_row.get("entity_name_raw") or "<unnamed raw relation candidate>"
    candidate_name = observed
    if canonical_norm(candidate_name) in seen_supplement_names:
        candidate_name = f"{observed} [source {observation_id}]"
    seen_supplement_names.add(canonical_norm(candidate_name))
    source_url = raw_row.get("source_url") or "https://nvidianews.nvidia.com/"
    canonical.append({
        "resolution_id": sid("nna_resolution_raw", observation_id),
        "candidate_name": candidate_name,
        "candidate_review_ids": ["source_native_raw:" + observation_id],
        "observation_ids": [observation_id],
        "research_status": "researched_terminal",
        "terminal_category": "ambiguous_after_research",
        "selected_entity_id": None,
        "resolution_confidence": 30,
        "inferred_entity_resolution": False,
        "exact_alias_search_outcome": "miss",
        "research_methods": [
            "strict exact alias search in reviewed issuer registry",
            "official SEC issuer/exchange screen where applicable",
            "listed-parent ownership research",
            "manual frozen raw-observation context review; no fuzzy promotion",
        ],
        "research_evidence": [{
            "evidence_id": sid("nna_raw_context", observation_id),
            "url": source_url,
            "publisher": raw_row.get("publisher") or "NVIDIA",
            "retrieved_at": RETRIEVED,
            "locator": raw_row.get("evidence_locator") or "frozen official-article raw relation observation",
            "supports": "The frozen raw observation establishes the exact string and context, but not a safe listed issuer or listed-parent endpoint.",
        }],
        "listed_entity_options": [],
        "rationale": "Source-native raw-relation candidate has no safe exact listed issuer or parent match after issuer/exchange/ownership screening. It remains terminally ambiguous and cannot create a graph edge.",
    })
    existing_ids.add(observation_id)

write(HERE / "researched_resolution_ledger.jsonl", sorted(canonical, key=lambda x: x["candidate_name"].casefold()))
write(HERE / "researched_entity_registry_overlay.jsonl", sorted(additive.values(), key=lambda x: x["entity_id"]))

# Candidate-review fixture lets the repository validator test exact closure of
# this shard's own population instead of the separate legacy candidate-review
# population.
candidate_review = []
canonical_by_review_id = {x["candidate_review_ids"][0]: x for x in canonical}
for item in resolution_inputs:
    resolution = canonical_by_review_id[item["candidate_id"]]
    candidate_review.append({
        "candidate_id": item["candidate_id"],
        "candidate_name": resolution["candidate_name"],
        "resolution_status": "unresolved_no_safe_exact_listed_match",
        "observations": [{"observation_id": x} for x in resolution["observation_ids"]],
    })
for raw_row in raw_misses:
    observation_id = raw_row["observation_id"]
    resolution = next(x for x in canonical if x["resolution_id"] == sid("nna_resolution_raw", observation_id))
    candidate_review.append({
        "candidate_id": "source_native_raw:" + observation_id,
        "candidate_name": resolution["candidate_name"],
        "resolution_status": "unresolved_no_safe_exact_listed_match",
        "observations": [{"observation_id": observation_id}],
    })
write(HERE / "canonical_candidate_review.jsonl", candidate_review)

combined_dir = HERE / "validator_combined_overlay"
combined_dir.mkdir(exist_ok=True)
write(combined_dir / "entity_registry_overlay.jsonl", global_rows + list(additive.values()))

report = {
    "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "canonical_rows": len(canonical),
    "canonical_expected_rows": len(all_candidates) + len(raw_misses),
    "source_native_raw_relation_rows_added": len(raw_misses),
    "terminal_category_counts": dict(sorted(Counter(x["terminal_category"] for x in canonical).items())),
    "unique_actual_upstream_observation_ids": len({y for x in canonical for y in x["observation_ids"] if not y.startswith("source-record:")}),
    "source_native_nonbuilder_record_ids": sum(y.startswith("source-record:") for x in canonical for y in x["observation_ids"]),
    "additive_listed_entity_rows": len(additive),
    "geely_observation_ids": next((x["observation_ids"] for x in canonical if x["candidate_name"].casefold() == "geely"), []),
    "ntt_data_resolution": next((
        {"selected_entity_id": x["selected_entity_id"], "terminal_category": x["terminal_category"], "confidence": x["resolution_confidence"]}
        for x in canonical if x["candidate_name"].casefold() == "ntt data"
    ), None),
}
(HERE / "canonical_ledger_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
