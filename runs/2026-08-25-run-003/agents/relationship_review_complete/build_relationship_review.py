#!/usr/bin/env python3
"""Review non-peer NVIDIA relationship observations and build auditable claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from listed_company_network.research_policy import (
    LOW_CONFIDENCE_PARTNER_CAPS,
    ResearchedEntityResolution,
    low_confidence_partner_profile,
    low_confidence_partner_score_is_valid,
)


HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
REPOSITORY_ROOT = RUN.parents[1]
CUTOFF = date(2026, 8, 25)
TERMINAL = {"approve_unknown", "reject", "needs_more_evidence", "approved"}


def repository_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPOSITORY_ROOT))
    except ValueError:
        return f"external_input/{path.name}"


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, values: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sid(prefix: str, raw: str) -> str:
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:18]}"


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("&", " and ").casefold()
    value = re.sub(r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|plc|sa|ag|se|nv|llc|lp)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path.rstrip("/") or "/", parts.query, ""))


def freshness_factor(published: str | None, family: str, provided: float | None = None) -> float:
    if family in {"official_product_page", "10k", "13f"}:
        return 1.0
    if provided is not None:
        return float(provided)
    if not published:
        return 0.55
    try:
        published_date = date.fromisoformat(published[:10])
    except ValueError:
        return 0.55
    age = (CUTOFF - published_date).days
    if age <= 90:
        return 1.0
    if age <= 180:
        return 0.9
    if age <= 365:
        return 0.75
    return 0.55


def product_lookup() -> tuple[dict[str, str], set[str]]:
    lookup: dict[str, str] = {}
    keys = set()
    for item in rows(RUN / "product_tree_v2" / "canonical_index_v2.jsonl"):
        key = item["canonical_key"]
        keys.add(key)
        for name in [item.get("primary_name"), *item.get("observed_names", []), *item.get("aliases", [])]:
            if name:
                lookup.setdefault(norm(name), key)
    lookup[norm("corporate_general")] = "corporate_general"
    keys.add("corporate_general")
    return lookup, keys


PRODUCT_LOOKUP, PRODUCT_KEYS = product_lookup()


def canonical_product(name: str | None, source_node_id: str | None = None) -> str:
    if name == "corporate_general" or source_node_id == "corporate_general":
        return "corporate_general"
    if name and norm(name) in PRODUCT_LOOKUP:
        return PRODUCT_LOOKUP[norm(name)]
    generic_overrides = {
        "dgx": "dgx-platform",
        "grace blackwell": "blackwell",
        "jetson thor": "jetson-thor-series",
        "nim": "nim-microservices",
        "rtx pro": "v2-design-rendering-rtx-pro",
    }
    if name and norm(name) in generic_overrides:
        return generic_overrides[norm(name)]
    if source_node_id:
        tail = source_node_id.rsplit(".", 1)[-1]
        if tail in PRODUCT_KEYS:
            return tail
    if not name:
        return "corporate_general"
    slug = re.sub(r"[^a-z0-9]+", "-", norm(name)).strip("-")
    return slug or "corporate_general"


REGISTRY = rows(RUN / "agents" / "entity_resolution_complete" / "entity_registry.jsonl")
REGISTRY_BY_ID = {r["entity_id"]: r for r in REGISTRY}
ALIAS_TO_IDS: dict[str, set[str]] = defaultdict(set)
SECURITY_TO_IDS: dict[str, set[str]] = defaultdict(set)
OVERLAY_ALIAS_TO_IDS: dict[str, set[str]] = defaultdict(set)
OVERLAY_PARENT_MAP: dict[str, str] = {}
OVERLAY_CONTEXT_ALIASES: dict[str, list[dict]] = defaultdict(list)
for entity in REGISTRY:
    for alias in [entity["legal_name"], entity.get("display_name"), *entity.get("aliases", [])]:
        if alias:
            ALIAS_TO_IDS[norm(alias)].add(entity["entity_id"])
    for security in entity.get("securities", []):
        SECURITY_TO_IDS[f"{str(security['exchange']).casefold()}:{str(security['ticker']).casefold()}"].add(entity["entity_id"])

ENTITY_REVIEW = {r["candidate_name"]: r for r in rows(RUN / "agents" / "entity_resolution_complete" / "candidate_review.jsonl")}
RESEARCHED_RESOLUTION_BY_OBSERVATION: dict[str, ResearchedEntityResolution] = {}
RESEARCHED_RESOLUTION_BY_NAME: dict[str, ResearchedEntityResolution] = {}


def load_researched_entity_resolutions(path: Path | None, *, required: bool) -> dict:
    if not path or not path.exists():
        if required:
            raise SystemExit("Required researched entity-resolution ledger is missing")
        return {"rows": 0, "inferred": 0, "largest_market_cap": 0}
    parsed = [ResearchedEntityResolution.model_validate(row) for row in rows(path)]
    for item in parsed:
        if item.selected_entity_id and item.selected_entity_id not in REGISTRY_BY_ID:
            raise SystemExit(
                f"Researched entity resolution selects unknown listed entity: {item.selected_entity_id}"
            )
        normalized_name = norm(item.candidate_name)
        if normalized_name in RESEARCHED_RESOLUTION_BY_NAME:
            raise SystemExit(f"Duplicate researched candidate name: {item.candidate_name}")
        RESEARCHED_RESOLUTION_BY_NAME[normalized_name] = item
        for observation_id in item.observation_ids:
            if observation_id in RESEARCHED_RESOLUTION_BY_OBSERVATION:
                raise SystemExit(f"Duplicate researched observation resolution: {observation_id}")
            RESEARCHED_RESOLUTION_BY_OBSERVATION[observation_id] = item
    return {
        "rows": len(parsed),
        "inferred": sum(item.inferred_entity_resolution for item in parsed),
        "largest_market_cap": sum(
            item.terminal_category.value == "resolved_largest_listed_parent"
            for item in parsed
        ),
    }


def researched_resolution(
    name: str | None, observation_id: str | None
) -> ResearchedEntityResolution | None:
    return (
        RESEARCHED_RESOLUTION_BY_OBSERVATION.get(observation_id or "")
        or RESEARCHED_RESOLUTION_BY_NAME.get(norm(name or ""))
    )


def load_listing_overlay(path: Path | None) -> dict:
    """Merge the validated three-table global listing overlay conservatively."""
    if not path or not path.exists():
        return {"entities": 0, "safe_exact_aliases": 0, "context_bound_aliases": 0, "listing_evidence": 0}
    if not path.is_dir():
        raise SystemExit("Global listing overlay must be the validated overlay directory")
    required = {
        "entities": path / "entity_registry_overlay.jsonl",
        "aliases": path / "aliases.jsonl",
        "evidence": path / "listing_evidence.jsonl",
        "validation": path / "validation_report.json",
    }
    missing = [name for name, item in required.items() if not item.exists()]
    if missing:
        raise SystemExit(f"Global listing overlay missing files: {', '.join(missing)}")
    report = json.loads(required["validation"].read_text(encoding="utf-8"))
    if report.get("status") != "pass":
        raise SystemExit("Global listing overlay validation status is not pass")
    evidence_rows = rows(required["evidence"])
    evidence_by_id = {row.get("listing_evidence_id"): row for row in evidence_rows}
    valid_evidence_ids = {
        evidence_id for evidence_id, row in evidence_by_id.items()
        if evidence_id and row.get("source_url") and row.get("publisher") and row.get("evidence_locator") and row.get("access_constraints")
    }
    active_entities = 0
    for row in rows(required["entities"]):
        if row.get("listing_status") != "listed_confirmed":
            continue
        listing_ids = row.get("listing_evidence_ids") or []
        if not listing_ids or not set(listing_ids).issubset(valid_evidence_ids):
            raise SystemExit(f"Overlay entity lacks complete official listing evidence: {row.get('entity_id')}")
        entity_id = row["merge_target_entity_id"] if row.get("merge_action") == "augment_existing" else row["entity_id"]
        security_rows = []
        for security in row.get("securities") or []:
            if security.get("status_at_cutoff") != "active_at_cutoff":
                continue
            security = dict(security)
            security["security_id"] = security.get("security_id") or f"{security['exchange']}:{security['ticker']}"
            security_rows.append(security)
        if not security_rows:
            raise SystemExit(f"Overlay active entity lacks an active exchange:ticker security: {entity_id}")
        if entity_id not in REGISTRY_BY_ID:
            entity = {
                "entity_id": entity_id,
                "legal_name": row["legal_name"],
                "display_name": row.get("display_name") or row["legal_name"],
                "aliases": [],
                "listing_status": "listed_confirmed",
                "securities": [],
                "listing_evidence_ids": [],
            }
            REGISTRY.append(entity)
            REGISTRY_BY_ID[entity_id] = entity
        entity = REGISTRY_BY_ID[entity_id]
        existing_security_ids = {security.get("security_id") for security in entity.get("securities", [])}
        for security in security_rows:
            if security["security_id"] not in existing_security_ids:
                entity.setdefault("securities", []).append(security)
                existing_security_ids.add(security["security_id"])
            SECURITY_TO_IDS[security["security_id"].casefold()].add(entity_id)
        entity["listing_evidence_ids"] = sorted(set(entity.get("listing_evidence_ids", [])) | set(listing_ids))
        # Legal/display names are issuer identity fields. All additional brand,
        # product and subsidiary mappings are admitted only from aliases.jsonl.
        for alias in [row.get("legal_name"), row.get("display_name")]:
            if alias:
                OVERLAY_ALIAS_TO_IDS[norm(alias)].add(entity_id)
                ALIAS_TO_IDS[norm(alias)].add(entity_id)
        active_entities += 1
    safe_exact = 0
    context_bound = 0
    for row in rows(required["aliases"]):
        entity_id = row.get("entity_id")
        if entity_id not in REGISTRY_BY_ID or not set(row.get("listing_evidence_ids") or []).issubset(valid_evidence_ids):
            continue
        if row.get("fuzzy_matching_allowed") is not False or row.get("match_policy") not in {"exact_only", "candidate_id_only"}:
            continue
        if row.get("alias_status") == "safe_exact":
            OVERLAY_ALIAS_TO_IDS[norm(row["alias"])].add(entity_id)
            ALIAS_TO_IDS[norm(row["alias"])].add(entity_id)
            safe_exact += 1
        elif row.get("alias_status") == "context_bound" and row.get("match_policy") == "candidate_id_only":
            OVERLAY_CONTEXT_ALIASES[norm(row["alias"])].append(row)
            context_bound += 1
    return {
        "entities": active_entities,
        "safe_exact_aliases": safe_exact,
        "context_bound_aliases": context_bound,
        "listing_evidence": len(evidence_rows),
    }


def load_researched_entity_registry_overlays(paths: list[Path]) -> dict:
    """Load additive, evidence-backed listed issuers produced by research shards.

    These files add endpoint identities only.  They do not create relationship
    claims and they never provide relationship-score credit.
    """
    loaded_rows = 0
    loaded_files = []
    for path in paths:
        resolved_path = path.resolve()
        if not resolved_path.is_file():
            raise SystemExit(f"Researched entity registry overlay is missing: {resolved_path}")
        loaded_files.append(
            {
                "path": repository_path(resolved_path),
                "sha256": hashlib.sha256(resolved_path.read_bytes()).hexdigest(),
            }
        )
        for row in rows(resolved_path):
            if row.get("listing_status") != "listed_confirmed":
                continue
            entity_id = row.get("entity_id")
            securities = [
                dict(item)
                for item in row.get("securities") or []
                if item.get("ticker") and item.get("exchange")
            ]
            if not entity_id or not securities or not row.get("listing_evidence_ids"):
                raise SystemExit(
                    f"Researched listed entity lacks id/security/evidence: {resolved_path}"
                )
            entity = REGISTRY_BY_ID.get(entity_id)
            if entity is None:
                entity = {
                    "entity_id": entity_id,
                    "legal_name": row["legal_name"],
                    "display_name": row.get("display_name") or row["legal_name"],
                    "aliases": [],
                    "listing_status": "listed_confirmed",
                    "securities": [],
                    "listing_evidence_ids": [],
                }
                REGISTRY.append(entity)
                REGISTRY_BY_ID[entity_id] = entity
            existing = {
                (str(item.get("exchange")), str(item.get("ticker")))
                for item in entity.get("securities") or []
            }
            for security in securities:
                security["security_id"] = security.get("security_id") or (
                    f"{security['exchange']}:{security['ticker']}"
                )
                key = (str(security["exchange"]), str(security["ticker"]))
                if key not in existing:
                    entity.setdefault("securities", []).append(security)
                    existing.add(key)
                SECURITY_TO_IDS[security["security_id"].casefold()].add(entity_id)
            aliases = {
                item
                for item in [
                    row.get("legal_name"),
                    row.get("display_name"),
                    *(row.get("aliases") or []),
                ]
                if item
            }
            entity["aliases"] = sorted(set(entity.get("aliases") or []) | aliases)
            entity["listing_evidence_ids"] = sorted(
                set(entity.get("listing_evidence_ids") or [])
                | set(row.get("listing_evidence_ids") or [])
            )
            for alias in aliases:
                ALIAS_TO_IDS[norm(alias)].add(entity_id)
            loaded_rows += 1
    return {"files": loaded_files, "listed_rows": loaded_rows}


def resolve_entity(name: str | None, exchange: str | None = None, ticker: str | None = None, allow_security_override: bool = False, observation_id: str | None = None) -> tuple[str | None, str, str]:
    if not name:
        return None, "missing_name", "No entity name."
    overlay_ids = OVERLAY_ALIAS_TO_IDS.get(norm(name), set())
    if len(overlay_ids) == 1:
        return next(iter(overlay_ids)), "official_global_listing_overlay", "Exact overlay alias is supported by official listing evidence."
    if norm(name) in OVERLAY_PARENT_MAP:
        return OVERLAY_PARENT_MAP[norm(name)], "official_overlay_parent_mapping", "Exact observed subsidiary/brand was mapped to its listed parent by the reviewed overlay."
    for context_alias in OVERLAY_CONTEXT_ALIASES.get(norm(name), []):
        reviewed_candidate = ENTITY_REVIEW.get(name) or {}
        reviewed_observations = {item.get("observation_id") for item in reviewed_candidate.get("observations", [])}
        if reviewed_candidate.get("candidate_id") in set(context_alias.get("candidate_review_ids") or []) and observation_id in reviewed_observations:
            return context_alias["entity_id"], "official_context_bound_listing_overlay", "Exact acronym mapping is limited to the reviewed candidate and source observation."
    reviewed = ENTITY_REVIEW.get(name)
    if reviewed:
        if reviewed["review_status"] == "resolved":
            return reviewed["entity_id"], "entity_resolution_registry", "Exact candidate was resolved as a listed issuer by the reviewed registry."
        if not allow_security_override:
            researched = researched_resolution(name, observation_id)
            if researched and researched.selected_entity_id:
                return (
                    researched.selected_entity_id,
                    f"researched_{researched.terminal_category.value}",
                    researched.rationale,
                )
            return None, reviewed["resolution_status"], reviewed.get("review_rationale", "Candidate is not resolved-listed.")
    if exchange and ticker:
        ids = SECURITY_TO_IDS.get(f"{exchange.casefold()}:{ticker.casefold()}", set())
        if len(ids) == 1:
            return next(iter(ids)), "exchange_ticker_registry_match", "Exact exchange:ticker maps uniquely to a confirmed registry entity."
    ids = ALIAS_TO_IDS.get(norm(name), set())
    if len(ids) == 1 and not reviewed:
        return next(iter(ids)), "reviewed_registry_alias", "Name is an exact conservative alias in the confirmed entity registry."
    if len(ids) > 1:
        researched = researched_resolution(name, observation_id)
        if researched and researched.selected_entity_id:
            return (
                researched.selected_entity_id,
                f"researched_{researched.terminal_category.value}",
                researched.rationale,
            )
        return None, "ambiguous_registry_alias", "Alias maps to more than one registry entity."
    researched = researched_resolution(name, observation_id)
    if researched and researched.selected_entity_id:
        return (
            researched.selected_entity_id,
            f"researched_{researched.terminal_category.value}",
            researched.rationale,
        )
    return None, "unresolved_entity", "No reviewed resolved-listed entity match."


SOURCE_FRONTIER = {r["source_id"]: r for r in rows(RUN / "agents" / "filings_presentations_complete" / "source_frontier.jsonl")}
PRODUCT_SOURCES = {}
for source in rows(RUN / "product_tree_v2" / "source_frontier.jsonl"):
    for key in (source.get("source_id"), source.get("source_id_raw")):
        if key:
            PRODUCT_SOURCES[key] = source
FILING_RAW_BY_OBS = {r["observation_id"]: r for r in rows(RUN / "agents" / "filings_presentations_complete" / "raw_observations.jsonl")}


def evidence_fingerprint(observation: dict) -> str:
    raw = "|".join([
        canonical_url(observation.get("source_url")) or "",
        observation.get("publisher") or "",
        observation.get("published_at") or "",
        observation.get("evidence_locator") or "",
        observation.get("content_fingerprint") or observation.get("body_sha256") or "",
        observation.get("evidence_excerpt") or "",
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def materialize_entity_resolution_evidence(
    researched: ResearchedEntityResolution | None,
    decision_id: str,
    evidence_by_fp: dict[str, dict],
) -> list[str]:
    """Persist identity evidence without treating it as relationship evidence."""
    if not researched:
        return []
    result: list[str] = []
    for item in researched.research_evidence:
        observation = {
            "source_url": str(item.url),
            "publisher": item.publisher,
            "published_at": None,
            "evidence_locator": item.locator,
            "content_fingerprint": item.evidence_id,
            "evidence_excerpt": item.supports,
        }
        fp = evidence_fingerprint(observation)
        evidence_id = sid("evidence", fp)
        record = evidence_by_fp.setdefault(
            fp,
            {
                "evidence_id": evidence_id,
                "fingerprint_sha256": fp,
                "source_family": "entity_resolution",
                "source_url": str(item.url),
                "publisher": item.publisher,
                "published_at": None,
                "retrieved_at": item.retrieved_at.isoformat(),
                "evidence_locator": item.locator,
                "evidence_excerpt": item.supports,
                "access_constraints": "Public issuer/exchange research; no access-control bypass.",
                "freshness_factor": None,
                "input_decision_ids": [],
                "content_fingerprint": item.evidence_id,
                "upstream_research_evidence_ids": [],
                "evidence_purpose": "entity_resolution_only_no_relationship_score_credit",
            },
        )
        record["input_decision_ids"].append(decision_id)
        record["upstream_research_evidence_ids"] = sorted(
            set(record.get("upstream_research_evidence_ids", [])) | {item.evidence_id}
        )
        result.append(evidence_id)
    return sorted(set(result))


def relation_key(entity_id: str, relation_type: str, product_scope_id: str) -> tuple[str, str, str, str, str]:
    if relation_type == "supplier":
        return entity_id, "nvidia", "supplies_to", relation_type, product_scope_id
    if relation_type == "customer":
        return "nvidia", entity_id, "sells_to", relation_type, product_scope_id
    if relation_type == "partner":
        return "nvidia", entity_id, "partners_with", relation_type, product_scope_id
    if relation_type == "investee":
        return "nvidia", entity_id, "invests_in", relation_type, product_scope_id
    raise ValueError(relation_type)


def decision_base(source_path: str, line_no: int, observation_id: str | None, entity_name: str | None) -> dict:
    raw = f"{source_path}:{line_no}:{observation_id or ''}:{entity_name or ''}"
    return {
        "decision_id": sid("decision", raw),
        "input_source_path": source_path,
        "input_line_number": line_no,
        "upstream_observation_id": observation_id,
        "entity_name_raw": entity_name,
        "terminal_status": None,
        "decision_reason": None,
        "generated_claim_keys": [],
    }


def product_observations() -> list[tuple[dict, dict, list[tuple]]]:
    path = RUN / "product_tree_v2" / "relation_candidates.jsonl"
    out = []
    partner_like = {"partner", "technology_collaborator", "intended_collaborator", "adopter_or_partner", "customer_or_partner", "certifier_or_partner", "inspection_lab_member_or_partner", "accreditor", "certifier", "inspection_report_recognizer"}
    customer_like = {"customer", "customer_story", "adopter"}
    for line_no, row in enumerate(rows(path), 1):
        name = row.get("entity_name_raw")
        decision = decision_base(str(path.relative_to(RUN)), line_no, row.get("candidate_observation_id"), name)
        entity_id, resolution, resolution_note = resolve_entity(name, observation_id=row.get("candidate_observation_id"))
        evidence = row.get("evidence") or {}
        source = PRODUCT_SOURCES.get(evidence.get("source_id")) or PRODUCT_SOURCES.get(evidence.get("source_id_raw")) or {}
        observation = {
            "source_family": "official_product_page",
            "source_url": evidence.get("source_url") or source.get("url") or source.get("canonical_url"),
            "publisher": evidence.get("publisher") or source.get("publisher") or "NVIDIA",
            "published_at": None,
            "retrieved_at": evidence.get("accessed_at") or source.get("accessed_at"),
            "evidence_locator": evidence.get("evidence_locator"),
            "evidence_excerpt": row.get("context") or row.get("uncertainty") or (row.get("raw_record") or {}).get("rationale"),
            "access_constraints": source.get("access_or_license_note") or "Public NVIDIA page; no access-control bypass.",
            "content_fingerprint": None,
            "semantic_status": "fact" if row.get("fact_status") == "confirmed" else row.get("fact_status", "unknown"),
            "freshness_factor": 1.0,
            "entity_id": entity_id,
            "entity_resolution_method": resolution,
            "entity_resolution_note": resolution_note,
            "original_relationship_hint": row.get("relationship_hint"),
            "product_scope_ids": sorted(set(row.get("nvidia_scope_canonical_keys") or ["corporate_general"])),
            "article_investment_boundary_applied": False,
        }
        hint = row.get("relationship_hint")
        fact = row.get("fact_status")
        proposed: list[tuple] = []
        if hint == "unknown" or fact in {"unknown", "unclassified_candidate"}:
            decision.update({"terminal_status": "approve_unknown", "decision_reason": "Logo/co-mention/architecture placement does not establish a classified commercial relationship."})
        elif not entity_id:
            decision.update({"terminal_status": "needs_more_evidence", "decision_reason": f"Relationship candidate retained, but entity is not resolved-listed: {resolution_note}"})
        elif hint in partner_like and (fact == "confirmed" or re.search(r"\b(partner|ecosystem|collaborator|adopter)\b", evidence.get("evidence_locator") or "", re.I)):
            proposed = [relation_key(entity_id, "partner", p) for p in observation["product_scope_ids"]]
            decision.update({"terminal_status": "approved", "decision_reason": "Official product page places the resolved issuer in an explicit partner/collaborator/ecosystem role; partner does not imply procurement direction."})
        elif hint in partner_like:
            decision.update({"terminal_status": "needs_more_evidence", "decision_reason": "The product-page candidate is inferred from example/logo/support-provider placement without an explicit partner/ecosystem heading; it remains unclassified."})
        elif hint in customer_like and fact == "confirmed":
            proposed = [relation_key(entity_id, "customer", p) for p in observation["product_scope_ids"]]
            decision.update({"terminal_status": "approved", "decision_reason": "Official page explicitly identifies a customer/adopter/use case and the resolved issuer; direction is NVIDIA to customer."})
        elif hint in customer_like:
            decision.update({"terminal_status": "needs_more_evidence", "decision_reason": "Customer direction is inferred from use/example text. The required two independent source families and business-alignment check are not established by this observation alone."})
        else:
            decision.update({"terminal_status": "approve_unknown", "decision_reason": "Specialized ecosystem placement is retained, but it is not safely reducible to supplier/customer/partner."})
        out.append((decision, observation, proposed))
    return out


PARTNER_VERBS = re.compile(r"\b(partner(?:ship|ed|ing)?|collaborat(?:e|es|ed|ion|ing)|co-?develop|work(?:ing)? (?:closely )?with|joint(?:ly)?|agreement|integrat(?:e|es|ed|ing|ion))\b", re.I)
CUSTOMER_VERBS = re.compile(r"\b(deploy(?:s|ed|ing)?|uses?|using|adopt(?:s|ed|ing)?|purchas(?:e|es|ed|ing)|buys?|built on|powered by|runs? on|select(?:s|ed)|integrat(?:e|es|ed|ing))\b", re.I)
SUPPLIER_TO_NVIDIA = re.compile(r"\b(suppl(?:y|ies|ied|ying) (?:collaboration|agreement|to nvidia)|suppl(?:ier|ies) (?:to|for) nvidia|nvidia (?:will )?purchase|purchase commitment|provid(?:e|es|ed|ing) .{0,80} to nvidia)\b", re.I)
INVESTMENT_WORDS = re.compile(r"\b(invest(?:s|ed|ing|ment|ments)?|equity|stake|subscription price)\b", re.I)

# Human review of article-customer false positives caused by multi-entity blocks.
# A corrected partner role is used only where the excerpt explicitly establishes
# integration/collaboration; otherwise the observation remains non-claiming.
ARTICLE_OVERRIDES = {
    "obs_0b1d2b7a04c766376d": ("approved_partner", "OCI deployment integration supports partner, not Oracle as an NVIDIA end customer."),
    "obs_1dbd7791a52e80b911": ("approved_partner", "The excerpt explicitly calls Dell a global system maker collaborating with NVIDIA; customer direction is not established."),
    "obs_4a967e7558e5414bde": ("approve_unknown", "Article title/summary co-mentions NVIDIA and Oracle but does not itself establish customer direction."),
    "obs_b867061c7b93e39903": ("needs_more_evidence", "The excerpt concerns possible use of Nokia optical technology by NVIDIA infrastructure, the reverse of the extracted customer direction."),
    "obs_7dfb7720c95a9d71aa": ("needs_more_evidence", "Dell is listed as an OEM/system maker offering NVIDIA-powered systems; the excerpt does not prove Dell is the customer."),
    "obs_8be83f31ee9c40457c": ("needs_more_evidence", "HP is listed as an OEM/system maker offering NVIDIA-powered systems; the excerpt does not prove HP is the customer."),
    "obs_aa98aefd94dfee1d1a": ("needs_more_evidence", "Supermicro is listed as an OEM/system maker offering NVIDIA-powered systems; the excerpt does not prove Supermicro is the customer."),
    "obs_1eaae32d95cdfed056": ("needs_more_evidence", "Corning supplies optical connectivity used by hyperscalers; this block does not establish Corning as NVIDIA's customer."),
    "obs_index_d074aa6b6596cd3b20": ("reject", "The adoption verb applies to Snap; Google Cloud is only the hosting context, so Alphabet is a news co-occurrence false positive."),
    "obs_index_6d9dbc70ebebfa6282": ("needs_more_evidence", "HPE and NVIDIA jointly contribute to LANL systems; the excerpt does not establish HPE as NVIDIA's customer."),
    "obs_098cef33117b01ffb8": ("needs_more_evidence", "Lenovo appears in an OEM system-availability list; the block does not establish Lenovo as NVIDIA's customer."),
    "obs_ed5e06c0a50709b179": ("approve_unknown", "GitHub is the download/distribution venue in this block, not a customer using or buying NVIDIA technology."),
    "obs_4f9c8e695be4599d48": ("needs_more_evidence", "ASUS appears in an OEM system-availability list; the block does not establish ASUS as NVIDIA's customer."),
    "obs_036878d3b50453092b": ("needs_more_evidence", "GIGABYTE appears in an OEM system-availability list; the block does not establish GIGABYTE as NVIDIA's customer."),
    "obs_e65b08eeac4b7ad6bc": ("needs_more_evidence", "MSI appears in an OEM system-availability list; the block does not establish MSI as NVIDIA's customer."),
    "obs_97545404ef6703b7ea": ("approved_partner", "ASUS is one of the system makers jointly building DSX-ready systems and contributing simulation-ready assets; this supports partner, not customer."),
    "obs_b1a22c75f643d50373": ("needs_more_evidence", "The block states NVIDIA is Cadence's first customer, so it does not support the requested NVIDIA-to-Cadence customer direction."),
    "obs_535b8c6824e7ef05d6": ("approve_unknown", "GitHub is a model/resource distribution venue in this block, not a customer using or buying NVIDIA technology."),
    "obs_3803cd1d0f53d0d222": ("approve_unknown", "GitHub is the public availability venue for tools in this block, not a customer relationship."),
    "obs_157712a64f68cd51b4": ("approve_unknown", "The quoted partner relation is Lucid-Dassault; NVIDIA technology is a separate tool reference, so this block is not independent NVIDIA-Dassault partner evidence."),
    "obs_480bcb48ebda6cdcbc": ("needs_more_evidence", "AWS provides a deployment/distribution route for NVIDIA software; this block does not establish AWS as NVIDIA's customer."),
    "obs_df30381d9eeefbce8f": ("needs_more_evidence", "Google Cloud provides a deployment/distribution route for NVIDIA software; this block does not establish Google Cloud as NVIDIA's customer."),
    "obs_961fab94176dd38a8a": ("needs_more_evidence", "Dell is collaborating with named media-software vendors at its booth; the block does not independently state a Dell-NVIDIA partnership."),
    "obs_1745da5d600db5d134": ("needs_more_evidence", "The relationship wording in this multi-entity block applies to other named companies; IQVIA is only described as building AI agents."),
    "obs_01b3245ffe23210551": ("needs_more_evidence", "CrowdStrike is an early user of the AWS-hosted service; the block does not independently establish a CrowdStrike-NVIDIA partnership."),
    "obs_a80df9a2badbb54127": ("needs_more_evidence", "Robotics companies use NVIDIA Isaac with AWS; this block does not establish AWS as NVIDIA's customer for Isaac."),
    "obs_eaedaef04b6ad5d543": ("needs_more_evidence", "KION is explicitly working with Accenture and Siemens while using NVIDIA technology; this block alone does not establish KION-NVIDIA partner direction."),
    "obs_b6cdb4eae3bea3c275": ("approved_partner", "NVIDIA and AWS jointly commit to deploy and provide sovereign AI clouds; this supports collaboration, not a unilateral customer direction."),
    "obs_7b8c752065dde9c9f3": ("approved_partner", "NVIDIA and AWS are jointly integrating NVLink Fusion with Trainium4 to build accelerated platforms; this supports collaboration, not a unilateral customer direction."),
}


def article_observations(recovery_dir: Path | None = None) -> list[tuple[dict, dict, list[tuple]]]:
    specs: list[Path] = [
        RUN / "agents" / "official_articles_2025" / "observations.jsonl",
        RUN / "agents" / "official_articles_2025" / "raw_relation_observations.jsonl",
        RUN / "agents" / "official_articles_2026" / "observations.jsonl",
        RUN / "agents" / "official_articles_2026" / "raw_relation_observations.jsonl",
    ]
    if recovery_dir and (recovery_dir / "observations.jsonl").exists():
        specs.append(recovery_dir / "observations.jsonl")
    recovery_processing = {
        row.get("article_id"): row
        for row in rows(recovery_dir / "article_processing.jsonl")
    } if recovery_dir and (recovery_dir / "article_processing.jsonl").exists() else {}
    out = []
    for path in specs:
        for line_no, row in enumerate(rows(path), 1):
            name = row.get("entity_name_raw")
            decision = decision_base(str(path.relative_to(RUN)), line_no, row.get("observation_id"), name)
            entity_id, resolution, resolution_note = resolve_entity(name, row.get("exchange"), row.get("ticker"), observation_id=row.get("observation_id"))
            product_scopes = []
            for product in row.get("product_context") or []:
                product_scopes.append(canonical_product(product.get("product_name"), product.get("source_node_id")))
            product_scopes = sorted(set(product_scopes or ["corporate_general"]))
            excerpt = row.get("evidence_excerpt") or ""
            investment_boundary = bool(row.get("article_investment_boundary_applied") or INVESTMENT_WORDS.search(excerpt))
            observation = {
                "source_family": "official_article",
                "source_url": row.get("source_url"), "publisher": row.get("publisher") or "NVIDIA",
                "published_at": row.get("published_date"), "retrieved_at": row.get("fetched_at"),
                "evidence_locator": row.get("evidence_locator"), "evidence_excerpt": excerpt,
                "access_constraints": row.get("access_constraints"),
                "content_fingerprint": row.get("content_fingerprint") or row.get("body_sha256"),
                "semantic_status": row.get("semantic_status", "unknown"),
                "freshness_factor": freshness_factor(row.get("published_date"), "official_article", row.get("freshness_factor_for_root_scoring")),
                "entity_id": entity_id, "entity_resolution_method": resolution, "entity_resolution_note": resolution_note,
                "original_relationship_hint": row.get("relationship_hint"), "product_scope_ids": product_scopes,
                "article_investment_boundary_applied": investment_boundary,
                "source_article_id": row.get("article_id"),
                "source_article_body_status": (recovery_processing.get(row.get("article_id")) or {}).get("body_coverage_status"),
            }
            hint = row.get("relationship_hint")
            semantic = row.get("semantic_status")
            proposed = []
            override = ARTICLE_OVERRIDES.get(row.get("observation_id"))
            recovery_row = recovery_processing.get(row.get("article_id"))
            recovery_blocked = bool(recovery_row and (
                recovery_row.get("processing_status") == "access_blocked"
                or recovery_row.get("body_coverage_status") != "complete"
            ))
            if recovery_blocked:
                decision.update({"terminal_status": "approve_unknown", "decision_reason": "The recovery ledger marks this article body blocked/uncovered; title/index-level material may be retained only as unknown and cannot create a claim."})
            elif norm(name or "") == "github":
                decision.update({"terminal_status": "approve_unknown", "decision_reason": "GitHub is used here as an open-source download, publication or distribution venue; venue availability is not a Microsoft/NVIDIA customer or partner claim."})
            elif override and entity_id:
                override_status, override_reason = override
                if override_status == "approved_partner":
                    proposed = [relation_key(entity_id, "partner", p) for p in product_scopes]
                    decision.update({"terminal_status": "approved", "decision_reason": f"Human role correction: {override_reason}"})
                else:
                    decision.update({"terminal_status": override_status, "decision_reason": f"Human role correction: {override_reason}"})
            elif hint == "unknown" or semantic == "unknown":
                reason = "Article observation is a co-mention or explicitly unknown; no commercial role is asserted."
                if investment_boundary:
                    reason += " Investment wording is quarantined: only the latest 13F may create an investee claim."
                decision.update({"terminal_status": "approve_unknown", "decision_reason": reason})
            elif not entity_id:
                decision.update({"terminal_status": "needs_more_evidence", "decision_reason": f"Article suggests {hint}, but entity is not resolved-listed: {resolution_note}"})
            elif hint == "partner" and semantic == "fact" and PARTNER_VERBS.search(excerpt):
                proposed = [relation_key(entity_id, "partner", p) for p in product_scopes]
                decision.update({"terminal_status": "approved", "decision_reason": "Official article contains explicit partnership/collaboration/integration wording for a resolved listed issuer."})
            elif hint == "customer" and semantic == "fact" and CUSTOMER_VERBS.search(excerpt):
                proposed = [relation_key(entity_id, "customer", p) for p in product_scopes]
                decision.update({"terminal_status": "approved", "decision_reason": "Official article explicitly describes deployment, use, purchase, selection or integration of NVIDIA technology by the issuer."})
            elif hint == "supplier" and semantic == "fact" and SUPPLIER_TO_NVIDIA.search(excerpt):
                proposed = [relation_key(entity_id, "supplier", p) for p in product_scopes]
                decision.update({"terminal_status": "approved", "decision_reason": "Official article explicitly states supply/purchase wording with the issuer supplying to NVIDIA."})
            elif hint in {"supplier", "customer"}:
                decision.update({"terminal_status": "needs_more_evidence", "decision_reason": "Supplier/customer classification is inferred or lacks direction-specific transaction wording; the two-source-family/business-alignment gate is not met."})
            elif hint == "partner":
                decision.update({"terminal_status": "needs_more_evidence", "decision_reason": "Partnership was inferred by extraction but the evidence excerpt lacks sufficiently explicit collaboration wording."})
            else:
                decision.update({"terminal_status": "approve_unknown", "decision_reason": "Observation cannot be safely mapped to an in-scope relationship type."})
            out.append((decision, observation, proposed))
    return out


ORDINARY_LINK = re.compile(
    r"(?:store\.steampowered\.com|store\.epicgames\.com|playstation\.com/.*/games|xbox\.com/.*/games|"
    r"github\.com|/games?/|/geforce-now/|/download/|/tools?/|marketplace)", re.I
)


def recovery_mention_observations(recovery_dir: Path | None) -> list[tuple[dict, dict, list[tuple]]]:
    """Close every recovered anchor mention without creating relations.

    Relationship observations from the same recovery shard are handled by
    article_observations(). A link/anchor alone is never partner evidence.
    """
    if not recovery_dir or not (recovery_dir / "entity_mentions.jsonl").exists():
        return []
    observation_keys = {
        (r.get("article_id"), norm(r.get("entity_name_raw", "")), r.get("evidence_locator"))
        for r in rows(recovery_dir / "observations.jsonl")
    }
    path = recovery_dir / "entity_mentions.jsonl"
    out = []
    for line_no, row in enumerate(rows(path), 1):
        name = row.get("entity_name_raw")
        decision = decision_base(str(path.relative_to(RUN)), line_no, f"mention:{row.get('article_id')}:{line_no}", name)
        entity_id, resolution, resolution_note = resolve_entity(name, row.get("exchange"), row.get("ticker"), observation_id=row.get("observation_id"))
        linked_url = row.get("linked_url") or ""
        ordinary_link = bool(ORDINARY_LINK.search(linked_url))
        has_relation_observation = (row.get("article_id"), norm(name or ""), row.get("evidence_locator")) in observation_keys
        observation = {
            "source_family": "official_article_anchor_mention",
            "source_url": row.get("source_url"), "publisher": row.get("publisher") or "NVIDIA Blog",
            "published_at": row.get("published_date"), "retrieved_at": row.get("fetched_at") or "2026-08-25",
            "evidence_locator": row.get("evidence_locator"), "evidence_excerpt": row.get("context_excerpt"),
            "access_constraints": row.get("access_constraints"),
            "content_fingerprint": row.get("body_sha256") or row.get("archive_timestamp"),
            "semantic_status": "mention_only", "freshness_factor": freshness_factor(row.get("published_date"), "official_article"),
            "entity_id": entity_id, "entity_resolution_method": resolution, "entity_resolution_note": resolution_note,
            "original_relationship_hint": "mention_only", "product_scope_ids": ["corporate_general"],
            "article_investment_boundary_applied": bool(INVESTMENT_WORDS.search(row.get("context_excerpt") or "")),
            "linked_url": linked_url, "ordinary_store_game_tool_link": ordinary_link,
            "source_article_id": row.get("article_id"),
            "source_article_body_status": row.get("body_coverage_status"),
        }
        if has_relation_observation:
            decision.update({"terminal_status": "reject", "decision_reason": "Anchor mention duplicates a body relationship observation; only the semantic observation can create a claim."})
        elif ordinary_link:
            decision.update({"terminal_status": "approve_unknown", "decision_reason": "Store/game/tool/marketplace link is mention-only. Catalog availability or a game list is not a partner relationship."})
        elif entity_id:
            decision.update({"terminal_status": "approve_unknown", "decision_reason": "Exact listed alias/parent mapping succeeded, but an anchor link without body relationship semantics remains unknown."})
        else:
            decision.update({"terminal_status": "approve_unknown", "decision_reason": f"Anchor mention has no resolved listed identity and no relationship semantics: {resolution_note}"})
        out.append((decision, observation, []))
    return out


def filing_observations() -> list[tuple[dict, dict, list[tuple]]]:
    out = []
    listed_path = RUN / "agents" / "filings_presentations_complete" / "listed_candidates.jsonl"
    for line_no, row in enumerate(rows(listed_path), 1):
        name = row.get("entity_name")
        decision = decision_base(str(listed_path.relative_to(RUN)), line_no, row.get("candidate_id"), name)
        entity_id, resolution, resolution_note = resolve_entity(name, row.get("exchange"), row.get("ticker"), observation_id=row.get("observation_id"))
        source = SOURCE_FRONTIER.get(row.get("source_id"), {})
        raw = FILING_RAW_BY_OBS.get(row.get("observation_id"), {})
        family = "10k" if source.get("kind") == "10-k" else "13f" if str(source.get("kind", "")).startswith("13f") else "presentation"
        observation = {
            "source_family": family, "source_url": source.get("url"),
            "publisher": source.get("publisher"), "published_at": source.get("published_at"), "retrieved_at": source.get("retrieved_at"),
            "evidence_locator": row.get("evidence_locator"), "evidence_excerpt": raw.get("short_evidence"),
            "access_constraints": source.get("access_restrictions"), "content_fingerprint": raw.get("content_fingerprint") or source.get("sha256"),
            "semantic_status": row.get("semantic_status"), "freshness_factor": freshness_factor(source.get("published_at"), family),
            "entity_id": entity_id, "entity_resolution_method": resolution, "entity_resolution_note": resolution_note,
            "original_relationship_hint": row.get("relationship_type"), "product_scope_ids": [row.get("product_canonical_key") or "corporate_general"],
            "article_investment_boundary_applied": False,
        }
        typ = row.get("relationship_type")
        proposed = []
        if typ == "peer":
            decision.update({"terminal_status": "reject", "decision_reason": "Peer review is explicitly out of scope for this shard."})
        elif typ == "investor_or_investee":
            decision.update({"terminal_status": "reject", "decision_reason": "Derived listed-candidate row duplicates the 13F table; investee claims are generated only from the authoritative 13f_holdings row."})
        elif typ == "unknown" or row.get("semantic_status") == "unknown":
            decision.update({"terminal_status": "approve_unknown", "decision_reason": "Presentation logo/cover/co-mention lacks a classified relationship title or direction."})
        elif not entity_id:
            decision.update({"terminal_status": "needs_more_evidence", "decision_reason": f"Upstream classified a relationship, but the issuer is not in the confirmed resolved-listed registry: {resolution_note}"})
        elif family == "presentation" and typ in {"supplier", "customer", "partner"} and raw.get("placement") == "titled_product_or_architecture_page":
            decision.update({"terminal_status": "needs_more_evidence", "decision_reason": "A visually reviewed logo/name on a titled product or architecture slide establishes product co-context only; without relationship wording it cannot be auto-promoted to a final claim."})
        elif typ in {"supplier", "customer", "partner"} and row.get("semantic_status") == "fact":
            proposed = [relation_key(entity_id, typ, row.get("product_canonical_key") or "corporate_general")]
            decision.update({"terminal_status": "approved", "decision_reason": f"Reviewed filing/presentation candidate explicitly classifies {typ} with direction and a single product scope."})
        else:
            decision.update({"terminal_status": "needs_more_evidence", "decision_reason": "Relationship is not an explicit reviewed fact."})
        out.append((decision, observation, proposed))

    holdings_path = RUN / "agents" / "filings_presentations_complete" / "13f_holdings.jsonl"
    listed_holdings = [r for r in rows(holdings_path) if r.get("listing_status") in {"listed", "listed_adr"}]
    total_value = sum(int(r["value_usd"]) for r in listed_holdings)
    for line_no, row in enumerate(rows(holdings_path), 1):
        name = row.get("entity_name")
        decision = decision_base(str(holdings_path.relative_to(RUN)), line_no, f"13f-row-{row.get('row_number')}", name)
        entity_id, resolution, resolution_note = resolve_entity(name, row.get("exchange"), row.get("ticker"), allow_security_override=True, observation_id=f"13f-row-{row.get('row_number')}")
        source = SOURCE_FRONTIER.get(row.get("source_id"), {})
        observation = {
            "source_family": "13f", "source_url": source.get("url"), "publisher": source.get("publisher"),
            "published_at": row.get("filing_date"), "retrieved_at": source.get("retrieved_at"),
            "evidence_locator": row.get("evidence_locator"),
            "evidence_excerpt": f"Issuer {row.get('issuer_raw')}; value USD {row.get('value_usd')}; shares {row.get('shares')}; CUSIP {row.get('cusip')}.",
            "access_constraints": source.get("access_restrictions"), "content_fingerprint": source.get("sha256"),
            "semantic_status": "fact", "freshness_factor": 1.0,
            "entity_id": entity_id, "entity_resolution_method": resolution, "entity_resolution_note": resolution_note,
            "original_relationship_hint": "investor_or_investee", "product_scope_ids": ["corporate_general"],
            "article_investment_boundary_applied": False,
            "quantitative": {
                "value_usd": row.get("value_usd"), "shares": row.get("shares"), "cusip": row.get("cusip"),
                "reported_listed_holdings_weight_pct": round(100 * int(row["value_usd"]) / total_value, 4) if row in listed_holdings and total_value else None,
                "period_of_report": row.get("period_of_report"),
            },
        }
        proposed = []
        if row.get("listing_status") not in {"listed", "listed_adr"}:
            decision.update({"terminal_status": "reject", "decision_reason": "Latest 13F row is explicitly private_excluded_from_listed_graph."})
        elif not entity_id:
            decision.update({"terminal_status": "needs_more_evidence", "decision_reason": f"13F row is listed but exact issuer/security resolution failed: {resolution_note}"})
        else:
            proposed = [relation_key(entity_id, "investee", "corporate_general")]
            decision.update({"terminal_status": "approved", "decision_reason": "Latest NVIDIA 13F for 2026-06-30 reports this resolved listed issuer; no strategic intent is inferred."})
        out.append((decision, observation, proposed))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--global-listing-overlay", type=Path, default=None)
    parser.add_argument("--article-recovery-dir", type=Path, default=RUN / "agents" / "article_body_recovery")
    parser.add_argument("--researched-entity-ledger", type=Path, default=None)
    parser.add_argument(
        "--researched-entity-registry-overlay",
        type=Path,
        action="append",
        default=[],
        help="additive JSONL registry produced by a reviewed entity-research shard",
    )
    parser.add_argument("--require-global-listing-overlay", action="store_true")
    parser.add_argument("--require-complete-article-recovery", action="store_true")
    parser.add_argument("--require-researched-entity-ledger", action="store_true")
    args = parser.parse_args()
    overlay_path = args.global_listing_overlay.resolve() if args.global_listing_overlay else None
    recovery_dir = args.article_recovery_dir.resolve() if args.article_recovery_dir else None
    if args.require_global_listing_overlay and (not overlay_path or not overlay_path.exists()):
        raise SystemExit("Required global listing overlay is missing")
    overlay_rows_accepted = load_listing_overlay(overlay_path)
    researched_registry_summary = load_researched_entity_registry_overlays(
        args.researched_entity_registry_overlay
    )
    researched_path = (
        args.researched_entity_ledger.resolve()
        if args.researched_entity_ledger
        else None
    )
    researched_resolution_summary = load_researched_entity_resolutions(
        researched_path, required=args.require_researched_entity_ledger
    )
    if args.require_complete_article_recovery:
        report_path = recovery_dir / "validation_report.json" if recovery_dir else None
        if not report_path or not report_path.exists():
            raise SystemExit("Required article recovery validation report is missing")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not (report.get("pass") or report.get("passed")):
            raise SystemExit("Article recovery validation has not passed")
        required_files = ["article_processing.jsonl", "observations.jsonl", "entity_mentions.jsonl"]
        missing = [name for name in required_files if not (recovery_dir / name).exists()]
        if missing:
            raise SystemExit(f"Required article recovery outputs are missing: {', '.join(missing)}")
        ledger_rows = len(rows(recovery_dir / "article_processing.jsonl"))
        if report.get("manifest_expected") != 597 or report.get("ledger_rows") != 597 or ledger_rows != 597:
            raise SystemExit(
                "Article recovery is not the frozen 597-article population: "
                f"manifest_expected={report.get('manifest_expected')}, "
                f"report_ledger_rows={report.get('ledger_rows')}, file_ledger_rows={ledger_rows}"
            )
        if report.get("pending") != 0 or report.get("terminal_ledger_complete") is not True:
            raise SystemExit(
                "Article recovery ledger is not terminal: "
                f"pending={report.get('pending')}, terminal_ledger_complete={report.get('terminal_ledger_complete')}"
            )

    reviewed = product_observations() + article_observations(recovery_dir) + recovery_mention_observations(recovery_dir) + filing_observations()
    evidence_by_fp: dict[str, dict] = {}
    claim_inputs: dict[tuple, list[tuple[dict, dict, str]]] = defaultdict(list)
    decisions = []
    for decision, observation, proposed_keys in reviewed:
        assert decision["terminal_status"] in TERMINAL
        fp = evidence_fingerprint(observation)
        evidence_id = sid("evidence", fp)
        evidence = evidence_by_fp.setdefault(fp, {
            "evidence_id": evidence_id, "fingerprint_sha256": fp,
            "source_family": observation["source_family"], "source_url": observation.get("source_url"),
            "publisher": observation.get("publisher"), "published_at": observation.get("published_at"),
            "retrieved_at": observation.get("retrieved_at"), "evidence_locator": observation.get("evidence_locator"),
            "evidence_excerpt": observation.get("evidence_excerpt"), "access_constraints": observation.get("access_constraints"),
            "freshness_factor": observation.get("freshness_factor"), "input_decision_ids": [],
            "content_fingerprint": observation.get("content_fingerprint"),
        })
        evidence["input_decision_ids"].append(decision["decision_id"])
        decision.update({
            "entity_id": observation.get("entity_id"),
            "entity_resolution_method": observation.get("entity_resolution_method"),
            "original_relationship_hint": observation.get("original_relationship_hint"),
            "product_scope_ids": observation.get("product_scope_ids"),
            "evidence_id": evidence_id,
            "evidence_fingerprint_sha256": fp,
            "article_investment_boundary_applied": observation.get("article_investment_boundary_applied", False),
            "source_article_id": observation.get("source_article_id"),
            "source_article_body_status": observation.get("source_article_body_status"),
        })
        researched = researched_resolution(
            decision.get("entity_name_raw"), decision.get("upstream_observation_id")
        )
        entity_resolution_evidence_ids = materialize_entity_resolution_evidence(
            researched, decision["decision_id"], evidence_by_fp
        )
        decision.update({
            "researched_entity_resolution_id": researched.resolution_id if researched else None,
            "researched_terminal_category": (
                researched.terminal_category.value if researched else None
            ),
            "entity_resolution_inferred": (
                researched.inferred_entity_resolution if researched else False
            ),
            "entity_resolution_research_evidence_ids": (
                entity_resolution_evidence_ids
            ),
            "entity_resolution_upstream_evidence_ids": (
                [item.evidence_id for item in researched.research_evidence]
                if researched
                else []
            ),
            "claim_inclusion_policy": None,
            "inference_explanation": None,
        })
        if decision["terminal_status"] == "approved":
            decision["claim_inclusion_policy"] = "approved_role_claim"
            for key in proposed_keys:
                key_str = "|".join(key)
                decision["generated_claim_keys"].append(key_str)
                claim_inputs[key].append((decision, observation, evidence_id))
        elif (
            decision["terminal_status"] in LOW_CONFIDENCE_PARTNER_CAPS
            and observation.get("entity_id")
        ):
            profile = low_confidence_partner_profile(decision["terminal_status"])
            decision["claim_inclusion_policy"] = "low_confidence_partner_from_terminal_review"
            decision["inference_explanation"] = (
                f"Original terminal status {decision['terminal_status']} is retained. "
                "The observation is included only as a low-confidence partner edge; "
                "it does not establish supplier/customer direction or a transaction. "
                f"Original review: {decision['decision_reason']}"
            )
            for product_scope in observation.get("product_scope_ids") or ["corporate_general"]:
                key = relation_key(
                    observation["entity_id"],
                    str(profile["relationship_type"]),
                    product_scope,
                )
                key_str = "|".join(key)
                decision["generated_claim_keys"].append(key_str)
                claim_inputs[key].append((decision, observation, evidence_id))
        decisions.append(decision)

    # Current v1 is a reviewed reference, not fresh evidence. It can flag prior
    # role coverage but cannot create a claim missing from run-003 evidence.
    snapshot = json.loads((REPOSITORY_ROOT / "data" / "snapshot_2026-08-25.json").read_text(encoding="utf-8"))
    prior_by_entity_type: dict[tuple[str, str], list[str]] = defaultdict(list)
    for rel in snapshot.get("relationships", []):
        typ = rel.get("relation_type")
        if typ not in {"supplier", "customer", "partner", "investor_or_investee"}:
            continue
        other = rel.get("source_entity_id") if rel.get("target_entity_id") == "nvidia" else rel.get("target_entity_id")
        prior_by_entity_type[(other, typ)].append(rel["id"])

    claims = []
    scoring_inputs = []
    conflicts = []
    for key in sorted(claim_inputs):
        source_id, target_id, direction, typ, product_scope = key
        inputs = claim_inputs[key]
        unique_evidence = {}
        for decision, observation, evidence_id in inputs:
            unique_evidence[evidence_id] = observation
        observations = list(unique_evidence.values())
        origin_terminal_statuses = sorted({item[0]["terminal_status"] for item in inputs})
        has_approved_input = "approved" in origin_terminal_statuses
        low_confidence_only = not has_approved_input and bool(
            set(origin_terminal_statuses) & set(LOW_CONFIDENCE_PARTNER_CAPS)
        )
        families = sorted({o["source_family"] for o in observations})
        publishers = sorted({o.get("publisher") for o in observations if o.get("publisher")})
        semantic_fact = any(o.get("semantic_status") == "fact" for o in observations)
        if low_confidence_only:
            fact_status = (
                "unknown"
                if "approve_unknown" in origin_terminal_statuses
                else "inferred"
            )
        else:
            fact_status = "confirmed" if semantic_fact else "inferred"
        authority = max({"13f": 25, "10k": 25, "official_product_page": 22, "presentation": 20, "official_article": 20}.get(o["source_family"], 10) for o in observations)
        explicitness = 5 if low_confidence_only else (25 if semantic_fact else 12)
        inferred_entity_resolution = any(
            decision.get("entity_resolution_inferred") for decision, _, _ in inputs
        )
        if inferred_entity_resolution and fact_status == "confirmed":
            fact_status = "inferred"
        entity_resolution = 10 if inferred_entity_resolution else 15
        methodological_independence = min(10, max(0, len(families) - 1) * 5)
        publisher_independence = min(5, max(0, len(publishers) - 1) * 5)
        independence = min(10, methodological_independence + publisher_independence)
        timeliness = round(10 * max(float(o.get("freshness_factor") or 0.55) for o in observations), 2)
        quantitative = next((o.get("quantitative") for o in observations if o.get("quantitative")), None)
        quantification = 10 if quantitative else 0
        relationship_specificity = 2 if low_confidence_only else 5
        conflict_penalty = 0
        raw_score = authority + explicitness + entity_resolution + independence + timeliness + quantification + relationship_specificity + conflict_penalty
        score_cap = 100
        inference_gate = None
        if fact_status == "inferred":
            score_cap = 69
        if low_confidence_only:
            score_cap = min(
                LOW_CONFIDENCE_PARTNER_CAPS[status]
                for status in origin_terminal_statuses
                if status in LOW_CONFIDENCE_PARTNER_CAPS
            )
        if typ in {"supplier", "customer"} and fact_status == "inferred":
            inference_gate = {
                "independent_source_families": len(families),
                "two_family_minimum_met": len(families) >= 2,
                "main_business_alignment_established": False,
                "product_consistency_established": True,
                "transaction_use_supply_wording_established": True,
                "strong_counterevidence": False,
                "result": "not_eligible_without_main_business_alignment",
                "alternative_explanation": "The entity may be an ecosystem integrator, technology collaborator or adopter rather than a direct supplier/customer.",
            }
            score_cap = 59
        confidence = min(score_cap, int(round(raw_score)))
        other_entity = source_id if target_id == "nvidia" else target_id
        prior_type = "investor_or_investee" if typ == "investee" else typ
        prior_refs = sorted(prior_by_entity_type.get((other_entity, prior_type), []))
        relationship_evidence_ids = sorted(unique_evidence)
        entity_resolution_evidence_ids = sorted(
            {
                evidence_id
                for decision, _, _ in inputs
                for evidence_id in decision.get(
                    "entity_resolution_research_evidence_ids", []
                )
            }
        )
        evidence_ids = sorted(
            set(relationship_evidence_ids) | set(entity_resolution_evidence_ids)
        )
        claim_id = sid("claim", "|".join(key))
        if typ == "supplier":
            explanation = f"{REGISTRY_BY_ID[other_entity]['legal_name']} supplies the indicated product/component/service scope to NVIDIA."
            limitations = ["Supply scope is limited to cited evidence; no exclusivity or revenue amount is inferred."]
        elif typ == "customer":
            explanation = f"NVIDIA sells to, or its indicated technology is explicitly deployed/used by, {REGISTRY_BY_ID[other_entity]['legal_name']}."
            limitations = ["Use/deployment does not necessarily disclose direct procurement value or contracting entity."]
        elif typ == "partner":
            if low_confidence_only:
                explanation = (
                    f"NVIDIA and {REGISTRY_BY_ID[other_entity]['legal_name']} are connected by retained "
                    "unknown or needs-more-evidence observations in the indicated scope. The edge is "
                    "modeled as a low-confidence partner hypothesis, not a confirmed collaboration."
                )
            else:
                explanation = f"NVIDIA and {REGISTRY_BY_ID[other_entity]['legal_name']} collaborate in the indicated scope; partner is modeled from NVIDIA to entity for canonicalization but is semantically symmetric."
            limitations = [
                "Partner placement does not by itself establish supplier/customer direction.",
                *( ["Original review did not establish an explicit partnership or transaction."] if low_confidence_only else [] ),
            ]
        else:
            explanation = f"NVIDIA's latest 13F reports a position in {REGISTRY_BY_ID[other_entity]['legal_name']} as of 2026-06-30."
            limitations = ["Point-in-time 13F holding; not real-time and does not establish strategic intent."]
        claim = {
            "claim_id": claim_id,
            "subject_entity_id": source_id, "object_entity_id": target_id,
            "direction": direction, "relationship_type": typ,
            "product_scope_id": product_scope,
            "dedup_key": "|".join(key),
            "fact_status": fact_status,
            "temporal_status": "point_in_time" if typ == "investee" else "current_or_recent_evidence",
            "as_of": "2026-06-30" if typ == "investee" else "2026-08-25",
            "confidence_score": confidence,
            "confidence_breakdown": {
                "source_authority": authority, "explicitness": explicitness,
                "entity_resolution": entity_resolution, "independence": independence,
                "timeliness": timeliness, "quantification": quantification,
                "relationship_type_specificity": relationship_specificity,
                "conflict_penalty": conflict_penalty,
            },
            "direction_explanation": explanation,
            "subject_entity": ({"entity_id": "nvidia", "legal_name": "NVIDIA Corporation", "security_identifiers": ["Nasdaq:NVDA"]} if source_id == "nvidia" else {
                "entity_id": source_id,
                "legal_name": REGISTRY_BY_ID[source_id]["legal_name"],
                "security_identifiers": [s["security_id"] for s in REGISTRY_BY_ID[source_id].get("securities", [])],
                "listing_evidence_ids": REGISTRY_BY_ID[source_id].get("listing_evidence_ids", []),
            }),
            "object_entity": ({"entity_id": "nvidia", "legal_name": "NVIDIA Corporation", "security_identifiers": ["Nasdaq:NVDA"]} if target_id == "nvidia" else {
                "entity_id": target_id,
                "legal_name": REGISTRY_BY_ID[target_id]["legal_name"],
                "security_identifiers": [s["security_id"] for s in REGISTRY_BY_ID[target_id].get("securities", [])],
                "listing_evidence_ids": REGISTRY_BY_ID[target_id].get("listing_evidence_ids", []),
            }),
            "evidence_ids": evidence_ids,
            "relationship_evidence_ids": relationship_evidence_ids,
            "entity_resolution_evidence_ids": entity_resolution_evidence_ids,
            "source_families": families,
            "independent_publisher_count": len(publishers),
            "prior_v1_reference_relationship_ids": prior_refs,
            "quantitative": quantitative,
            "inferred_supplier_customer_gate": inference_gate,
            "origin_terminal_statuses": origin_terminal_statuses,
            "low_confidence_partner_inclusion": low_confidence_only,
            "inference_explanations": sorted(
                {
                    decision["inference_explanation"]
                    for decision, _, _ in inputs
                    if decision.get("inference_explanation")
                }
            ),
            "entity_resolution_inferred": inferred_entity_resolution,
            "entity_resolution_research_ids": sorted(
                {
                    decision["researched_entity_resolution_id"]
                    for decision, _, _ in inputs
                    if decision.get("researched_entity_resolution_id")
                }
            ),
            "entity_resolution_research_evidence_ids": entity_resolution_evidence_ids,
            "limitations": limitations,
        }
        claims.append(claim)
        scoring_inputs.append({
            "claim_id": claim_id, "dedup_key": claim["dedup_key"],
            "evidence_count_after_fingerprint_dedup": len(relationship_evidence_ids),
            "entity_resolution_evidence_count": len(entity_resolution_evidence_ids),
            "entity_resolution_evidence_excluded_from_relationship_scoring": True,
            "source_families": families, "publishers": publishers,
            "freshness_factors": sorted({o.get("freshness_factor") for o in observations}),
            "semantic_statuses": sorted({o.get("semantic_status") for o in observations}),
            "quantitative_present": bool(quantitative),
            "score_cap": score_cap, "raw_score_before_cap": raw_score,
            "final_confidence_score": confidence,
            "origin_terminal_statuses": origin_terminal_statuses,
            "low_confidence_partner_inclusion": low_confidence_only,
            "entity_resolution_inferred": inferred_entity_resolution,
        })

    # Material review conflicts/boundaries retained even when they do not create claims.
    for name, conflict_type, resolution in [
        ("Spire", "entity_homonym", "No claim: Earth-2 context may mean former Spire Global rather than NYSE:SR utility issuer."),
        ("Everpure", "entity_homonym", "No claim: storage-logo context was not independently tied to the same-name SEC issuer."),
        ("Space Exploration Technologies Corp.", "listed_status_conflict", "No claim: 13F reviewer marked private_excluded_from_listed_graph."),
        ("article investment wording", "source_boundary", "No investee claim from articles/presentations; only latest 13F rows are eligible."),
    ]:
        conflicts.append({"conflict_id": sid("conflict", name), "type": conflict_type, "subject": name, "resolution": resolution, "status": "resolved"})

    evidence = sorted(evidence_by_fp.values(), key=lambda r: r["evidence_id"])
    decisions.sort(key=lambda r: (r["input_source_path"], r["input_line_number"]))
    write_jsonl(HERE / "decision_ledger.jsonl", decisions)
    write_jsonl(HERE / "evidence_fingerprints.jsonl", evidence)
    write_jsonl(HERE / "claims.jsonl", claims)
    write_jsonl(HERE / "scoring_inputs.jsonl", scoring_inputs)
    write_jsonl(HERE / "conflicts.jsonl", conflicts)

    input_paths = [
        RUN / "product_tree_v2" / "relation_candidates.jsonl",
        RUN / "agents" / "official_articles_2025" / "observations.jsonl",
        RUN / "agents" / "official_articles_2025" / "raw_relation_observations.jsonl",
        RUN / "agents" / "official_articles_2026" / "observations.jsonl",
        RUN / "agents" / "official_articles_2026" / "raw_relation_observations.jsonl",
        RUN / "agents" / "filings_presentations_complete" / "listed_candidates.jsonl",
        RUN / "agents" / "filings_presentations_complete" / "13f_holdings.jsonl",
    ]
    if recovery_dir and (recovery_dir / "observations.jsonl").exists():
        input_paths.append(recovery_dir / "observations.jsonl")
    if recovery_dir and (recovery_dir / "entity_mentions.jsonl").exists():
        input_paths.append(recovery_dir / "entity_mentions.jsonl")
    expected = 0
    input_manifest = []
    for path in input_paths:
        expected += len(rows(path))
        input_manifest.append({
            "path": str(path.relative_to(RUN)), "rows": len(rows(path)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None,
        })
    overlay_input_files = []
    if overlay_path:
        for name in ["entity_registry_overlay.jsonl", "aliases.jsonl", "listing_evidence.jsonl", "validation_report.json"]:
            path = overlay_path / name
            overlay_input_files.append({
                "path": repository_path(path),
                "rows": len(rows(path)) if path.suffix == ".jsonl" else None,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            })
    recovery_control_files = []
    if recovery_dir:
        for name in ["article_processing.jsonl", "validation_report.json", "independent_validation_report.json"]:
            path = recovery_dir / name
            if path.exists():
                recovery_control_files.append({
                    "path": repository_path(path),
                    "rows": len(rows(path)) if path.suffix == ".jsonl" else None,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                })
    write_json(HERE / "input_manifest.json", {
        "input_files": input_manifest,
        "global_listing_overlay": repository_path(overlay_path) if overlay_path else None,
        "global_listing_overlay_files": overlay_input_files,
        "global_listing_overlay_rows_accepted": overlay_rows_accepted,
        "article_recovery_dir": repository_path(recovery_dir) if recovery_dir else None,
        "article_recovery_required": args.require_complete_article_recovery,
        "article_recovery_control_files": recovery_control_files,
        "researched_entity_resolution_required": args.require_researched_entity_ledger,
        "researched_entity_resolution_ledger": (
            repository_path(researched_path) if researched_path else None
        ),
        "researched_entity_resolution_sha256": (
            hashlib.sha256(researched_path.read_bytes()).hexdigest()
            if researched_path and researched_path.exists()
            else None
        ),
        "researched_entity_resolution_summary": researched_resolution_summary,
        "researched_entity_registry_overlays": researched_registry_summary,
    })
    investee_claims = [c for c in claims if c["relationship_type"] == "investee"]
    investee_evidence_families = {fam for c in investee_claims for fam in c["source_families"]}
    blocked_article_ids = {
        row.get("article_id")
        for row in rows(recovery_dir / "article_processing.jsonl")
        if row.get("processing_status") == "access_blocked" or row.get("body_coverage_status") != "complete"
    } if recovery_dir and (recovery_dir / "article_processing.jsonl").exists() else set()
    validation = {
        "pass": True, "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_observations_expected": expected, "decision_rows": len(decisions),
        "global_listing_overlay_rows_accepted": overlay_rows_accepted,
        "article_recovery_observations_included": len(rows(recovery_dir / "observations.jsonl")) if recovery_dir and (recovery_dir / "observations.jsonl").exists() else 0,
        "article_recovery_mentions_included": len(rows(recovery_dir / "entity_mentions.jsonl")) if recovery_dir and (recovery_dir / "entity_mentions.jsonl").exists() else 0,
        "decision_status_counts": dict(sorted(Counter(d["terminal_status"] for d in decisions).items())),
        "pending": sum(d["terminal_status"] not in TERMINAL for d in decisions),
        "evidence_fingerprints": len(evidence), "claims": len(claims),
        "claim_type_counts": dict(sorted(Counter(c["relationship_type"] for c in claims).items())),
        "investee_claims": len(investee_claims),
        "checks": {
            "one_decision_per_input_observation": len(decisions) == expected,
            "all_decisions_terminal": all(d["terminal_status"] in TERMINAL for d in decisions),
            "zero_pending": all(d["terminal_status"] in TERMINAL for d in decisions),
            "dedup_keys_unique": len(claims) == len({c["dedup_key"] for c in claims}),
            "single_product_scope_per_claim": all(isinstance(c["product_scope_id"], str) and c["product_scope_id"] for c in claims),
            "product_scopes_resolve_frozen_tree": all(c["product_scope_id"] in PRODUCT_KEYS for c in claims),
            "claim_types_in_scope": all(c["relationship_type"] in {"supplier", "customer", "partner", "investee"} for c in claims),
            "claims_only_resolved_registry_entities": all((c["subject_entity_id"] == "nvidia" or c["subject_entity_id"] in REGISTRY_BY_ID) and (c["object_entity_id"] == "nvidia" or c["object_entity_id"] in REGISTRY_BY_ID) for c in claims),
            "directions_canonical": all((c["relationship_type"], c["direction"]) in {("supplier", "supplies_to"), ("customer", "sells_to"), ("partner", "partners_with"), ("investee", "invests_in")} for c in claims),
            "investee_exactly_seven_latest_13f_listed_issuers": len(investee_claims) == 7,
            "investee_evidence_only_13f": investee_evidence_families == {"13f"},
            "article_investment_never_creates_investee": all(not any("official_article" == fam for fam in c["source_families"]) for c in investee_claims),
            "inferred_supplier_customer_cap_59": all(c["confidence_score"] <= 59 for c in claims if c["relationship_type"] in {"supplier", "customer"} and c["fact_status"] == "inferred"),
            "approved_decisions_have_claim_key": all(d["generated_claim_keys"] for d in decisions if d["terminal_status"] == "approved"),
            "low_terminal_decisions_included_or_researched_nonlisted": all(
                d["generated_claim_keys"]
                or (
                    d.get("researched_entity_resolution_id")
                    and not d.get("entity_id")
                )
                for d in decisions
                if d["terminal_status"] in LOW_CONFIDENCE_PARTNER_CAPS
            ),
            "reject_decisions_have_no_claim_key": all(
                not d["generated_claim_keys"]
                for d in decisions
                if d["terminal_status"] == "reject"
            ),
            "low_confidence_claims_are_partner_and_capped": all(
                c["relationship_type"] == "partner"
                and c["direction"] == "partners_with"
                and c["confidence_score"]
                <= min(
                    LOW_CONFIDENCE_PARTNER_CAPS[status]
                    for status in c["origin_terminal_statuses"]
                    if status in LOW_CONFIDENCE_PARTNER_CAPS
                )
                for c in claims
                if c.get("low_confidence_partner_inclusion")
            ),
            "low_confidence_score_breakdown_and_fact_status_contract": all(
                low_confidence_partner_score_is_valid(c)
                for c in claims
                if c.get("low_confidence_partner_inclusion")
            ),
            "origin_terminal_status_and_inference_retained": all(
                c.get("origin_terminal_statuses")
                and (
                    not c.get("low_confidence_partner_inclusion")
                    or c.get("inference_explanations")
                )
                for c in claims
            ),
            "all_claim_input_evidence_retained": all(
                set(c["evidence_ids"])
                == (
                    {
                        d["evidence_id"]
                        for d in decisions
                        if c["dedup_key"] in d["generated_claim_keys"]
                    }
                    | {
                        evidence_id
                        for d in decisions
                        if c["dedup_key"] in d["generated_claim_keys"]
                        for evidence_id in d.get(
                            "entity_resolution_research_evidence_ids", []
                        )
                    }
                )
                for c in claims
            ),
            "entity_resolution_evidence_not_counted_as_relationship_independence": all(
                s.get("entity_resolution_evidence_excluded_from_relationship_scoring")
                is True
                and s.get("evidence_count_after_fingerprint_dedup")
                == len(c.get("relationship_evidence_ids", []))
                for c in claims
                for s in scoring_inputs
                if s["claim_id"] == c["claim_id"]
            ),
            "researched_entity_resolution_required_for_release": bool(
                args.require_researched_entity_ledger
                and researched_path
                and researched_path.exists()
            ),
            "claim_evidence_resolves": all(set(c["evidence_ids"]).issubset({e["evidence_id"] for e in evidence}) for c in claims),
            "source_urls_and_locators_retained": all(e.get("source_url") and e.get("evidence_locator") for e in evidence),
            "anchor_mentions_never_exceed_unknown_partner": all(
                not d["generated_claim_keys"]
                or d["terminal_status"] == "approve_unknown"
                for d in decisions
                if d["original_relationship_hint"] == "mention_only"
            ),
            "presentation_logo_architecture_never_exceed_low_partner": all(
                not d["generated_claim_keys"]
                or d["terminal_status"] in LOW_CONFIDENCE_PARTNER_CAPS
                for d in decisions
                if d["input_source_path"].endswith("filings_presentations_complete/listed_candidates.jsonl")
                and d["evidence_id"] in {
                    e["evidence_id"] for e in evidence
                    if e.get("source_family") == "presentation"
                }
            ),
            "blocked_recovery_articles_never_exceed_unknown_partner": all(
                not d["generated_claim_keys"]
                or d["terminal_status"] == "approve_unknown"
                for d in decisions
                if d.get("source_article_id") in blocked_article_ids
            ),
        },
    }
    validation["pass"] = all(validation["checks"].values())
    write_json(HERE / "validation_report.json", validation)
    write_json(HERE / "summary.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if validation["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
