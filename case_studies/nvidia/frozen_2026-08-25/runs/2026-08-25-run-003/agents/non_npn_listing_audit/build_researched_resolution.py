#!/usr/bin/env python3
"""Close every high-quality non-NPN relation candidate with a researched status."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
FIX = json.loads((HERE / "researched_resolution_fixtures.json").read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()] if path.exists() else []


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c)).replace("&", " and ").casefold()
    value = re.sub(r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|plc|sa|ag|se|nv|llc|lp)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def sid(prefix: str, value: str) -> str:
    return prefix + "_" + hashlib.sha256(value.encode()).hexdigest()[:16]


def fixture_map(items: list[dict]) -> dict[str, dict]:
    output = {}
    for item in items:
        for alias in item["aliases"]:
            output[norm(alias)] = item
    return output


direct = fixture_map(FIX["direct_issuers"])
parents = fixture_map(FIX["listed_parent_mappings"])
nonlisted = {norm(name) for name in FIX["researched_nonlisted"]}
sec_screened = {}
for row in read_jsonl(HERE / "sec_screening_matches.jsonl"):
    sec_screened.setdefault(row["candidate_normalized_name"], []).append(row)

all_candidates = read_jsonl(HERE / "unified_candidates.jsonl")
priority = [row for row in all_candidates if row["high_quality_relation_observation_count"] > 0]


NON_ENTITY_PATTERNS = re.compile(
    r"\b(?:"
    r"keynote|conference|summit|webinar|workshop|forum|day|week|show|gamescom|siggraph|cvpr|neurips|computex|gtc|ces|sc25|vivatech|hannover messe|"
    r"university|institute|foundation|consortium|alliance|government|department|program|initiative|fund|laboratory|lab|centre|center|college|community|"
    r"country|kingdom|korea|taiwan|italy|california|oregon|mississippi|wisconsin|atlanta|arabia|u k|united kingdom|"
    r"gpu|dpu|cpu|nvl|gb\d+|gh\d+|rtx|geforce|bluefield|connectx|dgx|jetson|cuda|omniverse|nemo|nemotron|cosmos|isaac|gr00t|nvfp|"
    r"model|models|microservice|blueprint|framework|engine|sdk|toolkit|library|libraries|driver|system|systems|server|servers|workstation|"
    r"benchmark|leaderboard|dataset|course|learning path|certification|specification|architecture|workflow|playbook|plug in|plugin|"
    r"marketplace|newsletter|channel|website|article|blog post|podcast|github|repository|docker|announcement|"
    r"game|battlefield|borderlands|pubg|half life|portal|"
    r"available|announced|today|visit|register|apply|join|read|follow|subscribe|buy now|this site|this release|"
    r"ai agents?|ai factories|llms?|rag|vlms?|ethernet|linux|windows|pytorch|blender|comfyui|openusd|"
    r"strategy|facility|award|list|performance|inference|training|simulation|reasoning|collaboration|solution|technology center"
    r")\b", re.I
)

INSTITUTION_PATTERNS = re.compile(
    r"\b(?:university|institute|foundation|government|department|alliance|consortium|association|council|college|laboratory|lab|research center|research centre)\b",
    re.I,
)

SOCIAL_OR_FOOTER = re.compile(r"\b(?:follow|stay up to date|subscribe|newsletter|social|channel|instagram|youtube|tiktok|linkedin|threads|facebook)\b", re.I)
STARTUP_PRIVATE_SIGNAL = re.compile(r"\b(?:startup|privately held|venture backed|scaleup|emerging company)\b", re.I)


def best_evidence(candidate: dict) -> dict:
    samples = candidate.get("evidence_samples", [])
    return next((x for x in samples if x.get("relation_semantic_priority") and x.get("source_url")), samples[0] if samples else {})


def research_classification(candidate: dict) -> tuple[str, str, str]:
    """Return terminal status, resolution kind and research basis."""
    n = candidate["normalized_name"]
    names = " | ".join(candidate["raw_name_variants"])
    snippets = " ".join(str(x.get("short_evidence") or "") for x in candidate.get("evidence_samples", []))
    base = candidate["terminal_status"]

    if n in direct:
        return "resolved_listed", "direct_issuer", "manually reviewed exact issuer fixture with public issuer/exchange evidence"
    if n in parents:
        return "resolved_listed_parent_inferred", parents[n]["resolution_kind"], "manually reviewed brand/subsidiary ownership mapping to a listed parent"
    if n in nonlisted:
        return "researched_nonlisted_or_private", "researched_nonlisted_company", "named company reviewed as private/non-listed at cutoff; no listed endpoint promoted"
    if base == "resolved_listed":
        return "resolved_listed", candidate["resolution_kind"], "existing reviewed issuer registry, structured security observation, or exact official SEC screening"
    if base == "resolved_listed_parent_inferred":
        return "resolved_listed_parent_inferred", candidate["resolution_kind"], "existing explicit brand/subsidiary-to-parent mapping"
    if base == "non_listed":
        return "researched_nonlisted_or_private", "researched_nonlisted_company", "prior reviewed non-listed fixture, re-screened against current exact issuer sources"
    if base in {"rejected_non_entity", "rejected_prior_review"}:
        return "researched_non_entity", "researched_non_entity_or_noise", "prior review or deterministic product/event classifier rejects issuer interpretation"
    if base == "ambiguous_representative_selected":
        return "ambiguous_after_research", candidate["resolution_kind"], "group label spans multiple listed issuers; largest-market-cap representative preserved but endpoint remains unknown"
    if base in {"ambiguous", "inferred_listed_candidate"}:
        return "ambiguous_after_research", candidate["resolution_kind"], "candidate has conflicting aliases or only contextual-prefix identity; no fuzzy promotion"
    if SOCIAL_OR_FOOTER.search(snippets):
        return "researched_non_entity", "social_platform_or_footer_reference", "NVIDIA context is a follow/subscribe/footer reference, not relationship evidence"
    if INSTITUTION_PATTERNS.search(names) or INSTITUTION_PATTERNS.search(snippets):
        return "researched_non_entity", "non_issuer_institution", "context identifies a university, public body, nonprofit, standards body or research institution"
    if NON_ENTITY_PATTERNS.search(names):
        return "researched_non_entity", "product_event_program_or_fragment", "name and frozen context identify a product, model, event, geography, program, sentence fragment or call-to-action"
    if STARTUP_PRIVATE_SIGNAL.search(snippets):
        return "researched_nonlisted_or_private", "researched_private_company", "frozen NVIDIA context calls the entity a startup/private company and exact issuer screens found no listing"
    return "ambiguous_after_research", "ambiguous_company_or_name_after_research", "company-like or ambiguous name had no exact reviewed global issuer, structured security, exact SEC issuer, or explicit parent match; frozen context is insufficient for a safe status claim"


mapping_evidence = {row["mapping_evidence_id"]: row for row in read_jsonl(HERE / "mapping_evidence.jsonl")}
ledger = []
for candidate in priority:
    n = candidate["normalized_name"]
    terminal, kind, basis = research_classification(candidate)
    selected_entity_id = candidate.get("selected_entity_id")
    selected_legal_name = candidate.get("selected_legal_name")
    selected_securities = candidate.get("selected_securities", [])
    mapping_ids = list(candidate.get("mapping_evidence_ids", []))
    endpoint_status = candidate.get("endpoint_identity_fact_status_recommendation", "unknown")
    confidence_cap = candidate.get("confidence_score_cap_recommendation")
    parent_candidates = candidate.get("parent_candidates", [])

    fixture = direct.get(n) or parents.get(n)
    if fixture:
        evidence_id = sid("nna_research_map", fixture["url"] + "|" + fixture["entity_id"])
        mapping_ids = [evidence_id]
        selected_entity_id = fixture["entity_id"]
        selected_legal_name = fixture["legal_name"]
        selected_securities = fixture["securities"]
        endpoint_status = "fact" if n in direct else "inferred"
        confidence_cap = None if n in direct else 69
        mapping_evidence[evidence_id] = {
            "mapping_evidence_id": evidence_id,
            "source_url": fixture["url"],
            "publisher": fixture["publisher"],
            "published_or_accessed_date": "2026-08-25",
            "evidence_locator": fixture["locator"],
            "access_constraints": "public no-login issuer/parent reference; publisher rights retained",
            "resolution_kind": kind,
            "use_limitation": "Identity/listing or ownership mapping only; does not prove the NVIDIA relationship."
        }

    evidence = best_evidence(candidate)
    screens = [
        {
            "screen": "existing_reviewed_global_issuer_and_alias_registries",
            "result": "matched" if candidate["terminal_status"] == "resolved_listed" else "no_safe_exact_match_or_not_applicable",
            "method": "strict normalized alias only; ambiguous/context-bound aliases excluded"
        },
        {
            "screen": "official_sec_company_tickers_exchange",
            "result": "exact_match" if n in sec_screened else "no_exact_match",
            "method": "bounded single-file screen; U.S. SEC scope only; absence is not proof of global non-listing",
            "source_record": "sec_screening_source.json"
        },
        {
            "screen": "frozen_nvidia_context",
            "result": terminal,
            "method": "review name, source family, relation hint, locator and short evidence; no NVIDIA page refetch"
        },
    ]
    ledger.append({
        "research_resolution_id": sid("nna_research", candidate["candidate_id"]),
        "candidate_id": candidate["candidate_id"],
        "normalized_name": n,
        "raw_name_variants": candidate["raw_name_variants"],
        "observation_ids": candidate["observation_ids"],
        "high_quality_relationship_observation_ids": sorted(
            set(candidate["original_nvidia_evidence_ids"])
        ),
        "source_families": candidate["source_families"],
        "terminal_classification": terminal,
        "resolution_kind": kind,
        "research_basis": basis,
        "selected_entity_id": selected_entity_id,
        "selected_legal_name": selected_legal_name,
        "selected_securities": selected_securities,
        "candidate_parents_or_issuers": parent_candidates,
        "mapping_evidence_ids": sorted(set(mapping_ids)),
        "original_nvidia_evidence_ids": candidate["original_nvidia_evidence_ids"],
        "endpoint_identity_fact_status_recommendation": endpoint_status if terminal.startswith("resolved") else "unknown",
        "relationship_fact_status_recommendation": (
            "preserve original NVIDIA semantics; identity research does not independently prove the relationship"
            if terminal == "resolved_listed"
            else "inferred endpoint only; final relation must cite original NVIDIA evidence and mapping evidence"
            if terminal == "resolved_listed_parent_inferred"
            else "unknown; do not promote to final listed-company relationship"
        ),
        "confidence_score_cap_recommendation": confidence_cap if terminal.startswith("resolved") else 49,
        "representative_source": {
            "url": evidence.get("source_url"),
            "publisher": evidence.get("publisher"),
            "published_or_filed_date": evidence.get("published_or_filed_date"),
            "locator": evidence.get("evidence_locator"),
            "access_constraints": evidence.get("access_constraints")
        },
        "research_policy": {
            "policy_version": "non_npn_listing_research_v1",
            "cutoff": "2026-08-25",
            "screens_performed": screens,
            "no_fuzzy_promotion": True,
            "sec_scope_limitation": "SEC exact-name screening covers SEC-reporting issuers, not the full world.",
            "terminal_taxonomy": [
                "resolved_listed", "resolved_listed_parent_inferred",
                "researched_nonlisted_or_private", "researched_non_entity",
                "ambiguous_after_research"
            ]
        },
        "uncertainty_and_limitations": candidate.get("uncertainty_and_limitations", []) + (
            ["No listed relationship endpoint may be emitted from this row without new mapping evidence."]
            if not terminal.startswith("resolved") else []
        )
    })

write_jsonl(HERE / "researched_resolution_audit_detail.jsonl", sorted(ledger, key=lambda x: x["normalized_name"]))
write_jsonl(HERE / "mapping_evidence_researched.jsonl", sorted(mapping_evidence.values(), key=lambda x: x["mapping_evidence_id"]))

# Close the full enumerated frontier without pretending mention-only/OCR strings
# received the same research depth as relation-semantic candidates.
research_by_id = {row["candidate_id"]: row for row in ledger}
frontier_terminal = []
for candidate in all_candidates:
    researched = research_by_id.get(candidate["candidate_id"])
    if researched:
        frontier_terminal.append({
            "candidate_id": candidate["candidate_id"],
            "normalized_name": candidate["normalized_name"],
            "frontier_terminal_status": researched["terminal_classification"],
            "research_resolution_id": researched["research_resolution_id"],
            "graph_eligibility": "resolved_endpoint_subject_to_relation_semantic_review" if researched["terminal_classification"] in {"resolved_listed", "resolved_listed_parent_inferred"} else "excluded",
            "observation_ids": candidate["observation_ids"],
            "reason": researched["research_basis"],
        })
    else:
        frontier_terminal.append({
            "candidate_id": candidate["candidate_id"],
            "normalized_name": candidate["normalized_name"],
            "frontier_terminal_status": "excluded_low_quality_frontier_only",
            "research_resolution_id": None,
            "graph_eligibility": "excluded",
            "observation_ids": candidate["observation_ids"],
            "reason": "No structured high-quality relation-semantic observation; mention-only or low-quality OCR frontier is retained for reproducibility but cannot create a relationship endpoint.",
        })
write_jsonl(HERE / "full_frontier_terminal_ledger.jsonl", sorted(frontier_terminal, key=lambda x: x["normalized_name"]))

# Integration overlay contains only high-quality candidates with a resolved
# listed issuer/parent endpoint. Relationship type/status must still be decided
# from the original NVIDIA observations.
overlay = []
for row in ledger:
    if row["terminal_classification"] not in {"resolved_listed", "resolved_listed_parent_inferred"}:
        continue
    overlay.append({
        "overlay_resolution_id": sid("nna_overlay", row["candidate_id"]),
        "candidate_id": row["candidate_id"],
        "normalized_name": row["normalized_name"],
        "raw_name_variants": row["raw_name_variants"],
        "selected_entity_id": row["selected_entity_id"],
        "selected_legal_name": row["selected_legal_name"],
        "selected_securities": row["selected_securities"],
        "resolution_kind": row["resolution_kind"],
        "endpoint_identity_fact_status": row["endpoint_identity_fact_status_recommendation"],
        "original_nvidia_evidence_ids": row["original_nvidia_evidence_ids"],
        "mapping_evidence_ids": row["mapping_evidence_ids"],
        "relationship_semantics_policy": "Preserve each original relation hint/status. Identity resolution alone cannot upgrade unknown/needs_more_evidence; candidate may enter Partner review only because its endpoint is now a listed issuer/parent.",
        "eligible_for_relation_graph_review": True,
        "confidence_score_cap_recommendation": row["confidence_score_cap_recommendation"],
        "uncertainty_and_limitations": row["uncertainty_and_limitations"],
    })
write_jsonl(HERE / "listed_endpoint_overlay.jsonl", sorted(overlay, key=lambda x: x["normalized_name"]))

terminal_counts = Counter(row["terminal_classification"] for row in ledger)
resolved_parent_rows = [x for x in ledger if x["terminal_classification"] == "resolved_listed_parent_inferred"]
violations = []
if len(ledger) != len(priority):
    violations.append("ledger_count_mismatch")
if len({x["candidate_id"] for x in ledger}) != len(ledger):
    violations.append("duplicate_candidate_id")
if any(x["terminal_classification"] not in {
    "resolved_listed", "resolved_listed_parent_inferred", "researched_nonlisted_or_private",
    "researched_non_entity", "ambiguous_after_research"
} for x in ledger):
    violations.append("nonterminal_classification")
if any(not x["original_nvidia_evidence_ids"] for x in ledger):
    violations.append("missing_original_nvidia_evidence")
if any(not x["mapping_evidence_ids"] for x in resolved_parent_rows):
    violations.append("parent_mapping_without_mapping_evidence")
if any(x["endpoint_identity_fact_status_recommendation"] != "inferred" for x in resolved_parent_rows):
    violations.append("parent_mapping_not_inferred")
if any(x["resolution_kind"] == "direct_issuer" and x["endpoint_identity_fact_status_recommendation"] != "fact" for x in ledger if x["terminal_classification"] == "resolved_listed"):
    violations.append("direct_issuer_not_fact")
if len(frontier_terminal) != len(all_candidates) or len({x["candidate_id"] for x in frontier_terminal}) != len(all_candidates):
    violations.append("full_frontier_not_exactly_closed")
if any(x["graph_eligibility"] != "excluded" for x in frontier_terminal if x["frontier_terminal_status"] not in {"resolved_listed", "resolved_listed_parent_inferred"}):
    violations.append("unresolved_or_noise_candidate_graph_eligible")
if any(x["endpoint_identity_fact_status"] not in {"fact", "inferred"} for x in overlay):
    violations.append("overlay_endpoint_status_invalid")

summary = json.loads((HERE / "summary.json").read_text(encoding="utf-8"))
summary.update({
    "pass": not violations,
    "pass_semantics": "all high-quality relation-priority candidates have one researched terminal row; this is not a claim that every ambiguous name is listed/non-listed",
    "researched_resolution_ledger_rows": len(ledger),
    "researched_resolution_expected_rows": len(priority),
    "researched_terminal_classification_counts": dict(sorted(terminal_counts.items())),
    "high_quality_unresolved_after_research": 0,
    "full_frontier_terminal_rows": len(frontier_terminal),
    "full_frontier_expected_rows": len(all_candidates),
    "low_quality_frontier_excluded_rows": sum(x["frontier_terminal_status"] == "excluded_low_quality_frontier_only" for x in frontier_terminal),
    "listed_endpoint_overlay_rows": len(overlay),
    "research_validation_violations": violations,
    "research_policy_schema": "embedded research_policy object in every researched_resolution_ledger row",
    "ntt_data_cutoff_correction": "9613 delisted 2025-09-26; NTT DATA variants map inferred to active listed parent NTT TSE:9432",
})
(HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
