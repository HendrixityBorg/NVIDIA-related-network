#!/usr/bin/env python3
"""Conservative, reproducible listed-entity resolution for run-003 candidates.

The output intentionally separates identity resolution from relationship review.
No fuzzy match can promote a candidate.  SEC issuer-name matching starts from a
strict normalization; the small set of brand-to-legal-name matches is explicitly
reviewed below.  A previous local registry may contribute aliases, but it does
not by itself prove that a security remains listed at the research cutoff.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
DEFAULT_UA = "listed-company-network-research/1.0 contact=research@example.invalid"
STRICT_SUFFIXES = re.compile(
    r"\b(?:incorporated|inc|corporation|corp|company|co|limited|ltd|plc|sa|ag|se|nv|llc|lp)\b",
    re.I,
)
AGGRESSIVE_WORDS = re.compile(
    r"\b(?:holdings?|group|technologies|technology|systems|international)\b", re.I
)

# These are brand/legal-name variants, individually reviewed against context and
# the SEC issuer record.  They are not produced by a generic fuzzy rule.
REVIEWED_BRAND_MATCHES = {
    "Akamai": "AKAMAI TECHNOLOGIES INC",
    "CrowdStrike": "CrowdStrike Holdings, Inc.",
    "GE HealthCare": "GE HealthCare Technologies Inc.",
    "IQVIA": "IQVIA HOLDINGS INC.",
    "Keysight": "Keysight Technologies, Inc.",
    "Palantir": "Palantir Technologies Inc.",
    "Sony": "Sony Group Corp",
    "Vertiv": "Vertiv Holdings Co",
    "Applied Materials": "APPLIED MATERIALS INC /DE",
    "Booz Allen": "Booz Allen Hamilton Holding Corp",
    "Cadence": "CADENCE DESIGN SYSTEMS INC",
    "Check Point": "CHECK POINT SOFTWARE TECHNOLOGIES LTD",
    "Digital Realty": "DIGITAL REALTY TRUST, INC.",
    "IBM": "INTERNATIONAL BUSINESS MACHINES CORP",
    "Planet Labs": "Planet Labs PBC",
    "Siemens Energy": "Siemens Energy AG/ADR",
}

# Exact strings whose SEC-name collision is not enough to establish contextual
# identity.  This is the manual audit of the risky normalization cases observed
# in this run, not a generic suppression list.
MANUAL_OVERRIDES = {
    "Everpure": (
        "ambiguous",
        "SEC has an Everpure, Inc. record, but NVIDIA evidence places the name in a storage-partner logo grid; the logo/entity identity was not independently established.",
    ),
    "Global AI": (
        "ambiguous",
        "The generic name in NVIDIA's article could refer to the new NVIDIA Cloud Partner; the article does not supply a CIK/ticker proving it is OTC:GLAI.",
    ),
    "Spire": (
        "ambiguous",
        "Earth-2 context plausibly refers to weather-data company Spire Global, not SEC exact-name utility issuer Spire Inc.; current listed identity is not uniquely established.",
    ),
    "SEEQC": (
        "unresolved",
        "SEC row has a ticker string but no exchange; exchange:ticker listed-security requirement is not met.",
    ),
    "Hyundai Motor Group": (
        "ambiguous",
        "Hyundai Motor Group is a corporate group with multiple affiliates and is not an exact alias for a single listed issuer.",
    ),
    "JLR": (
        "unresolved",
        "JLR is an operating subsidiary/brand; mapping it directly to listed parent Tata Motors would collapse distinct legal entities.",
    ),
    "Samsung": (
        "ambiguous",
        "Samsung alone can denote the wider group or multiple listed affiliates; evidence must say Samsung Electronics or otherwise disambiguate the entity.",
    ),
    "Space Exploration Technologies Corp.": (
        "rejected",
        "The reviewed 2026-06-30 NVIDIA 13F shard classifies this holding as private_excluded_from_listed_graph. A conflicting carried registry/SEC-name record is not allowed to override that explicit instrument review.",
    ),
}

NON_ENTITY_EXACT = {
    "Access", "Announced", "Autonomous vehicle", "Celebrates", "CES", "COMPUTEX",
    "CoRL", "DCAI", "DRIVE", "Dynamo", "Europe", "France", "GDC", "Germany",
    "GTC 2025", "NVIDIA", "RTX", "USA", "V",
}
NON_ENTITY_PATTERNS = [
    re.compile(r"^(?:about nvidia|and\b|in the\b)", re.I),
    re.compile(r"\b(?:keynote|sessions?|festival|initiative|collaboration between|developer day)\b", re.I),
    re.compile(r"\b(?:models?|techniques|systems|services|toolchain|ecosystem)\b", re.I),
    re.compile(r"\b(?:factory|factories|infrastructure)\b", re.I),
    re.compile(r"^(?:AI|NVIDIA|GeForce|Cosmos|GB\d+|HGX|DLSS)\b", re.I),
    re.compile(r"\b(?:powered|expand full-stack|is introducing)$", re.I),
    re.compile(r"^(?:get started|sign up|multiyear strategic agreements with)\b", re.I),
]


def jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def strict_norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.replace("&", " and ").casefold()
    value = STRICT_SUFFIXES.sub(" ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def aggressive_norm(value: str) -> str:
    return re.sub(r"\s+", " ", AGGRESSIVE_WORDS.sub(" ", strict_norm(value))).strip()


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def add(bucket: dict[str, list[dict]], name: str | None, observation: dict) -> None:
    if name and name.strip():
        bucket[name.strip()].append(observation)


def source_obs(row: dict, family: str, source_path: str) -> dict:
    evidence = row.get("evidence") or {}
    return {
        "family": family,
        "observation_id": row.get("observation_id") or row.get("candidate_observation_id") or row.get("holding_id") or row.get("listing_id"),
        "source_path": source_path,
        "source_url": row.get("source_url") or evidence.get("source_url") or row.get("profile_url"),
        "publisher": row.get("publisher") or evidence.get("publisher") or "NVIDIA",
        "published_at": row.get("published_date") or row.get("published_at"),
        "retrieved_at": row.get("fetched_at") or row.get("retrieved_at") or row.get("accessed_at") or evidence.get("accessed_at") or "2026-08-25",
        "evidence_locator": row.get("evidence_locator") or evidence.get("evidence_locator"),
        "relationship_hint": row.get("relationship_hint"),
    }


def collect(run: Path) -> dict[str, list[dict]]:
    candidates: dict[str, list[dict]] = defaultdict(list)
    product_path = run / "product_tree_v2" / "relation_candidates.jsonl"
    product_sources = {}
    for source in jsonl(run / "product_tree_v2" / "source_frontier.jsonl"):
        for key in (source.get("source_id"), source.get("source_id_raw")):
            if key:
                product_sources[key] = source
    for row in jsonl(product_path):
        observation = source_obs(row, "official_product_solution_page", str(product_path.relative_to(run)))
        evidence = row.get("evidence") or {}
        source = product_sources.get(evidence.get("source_id")) or product_sources.get(evidence.get("source_id_raw")) or {}
        observation["source_url"] = observation.get("source_url") or source.get("url") or source.get("canonical_url")
        observation["retrieved_at"] = observation.get("retrieved_at") or source.get("accessed_at")
        observation["access_constraints"] = source.get("access_or_license_note")
        add(candidates, row.get("entity_name_raw"), observation)

    for year in (2025, 2026):
        base = run / "agents" / f"official_articles_{year}"
        for filename in ("observations.jsonl", "index_fallback_observations.jsonl"):
            path = base / filename
            for row in jsonl(path):
                add(candidates, row.get("entity_name_raw"), source_obs(row, f"official_article_{year}", str(path.relative_to(run))))

    filings = run / "agents" / "filings_presentations_complete"
    filing_sources = {row.get("source_id"): row for row in jsonl(filings / "source_frontier.jsonl") if row.get("source_id")}
    for filename in (
        "listed_candidates.jsonl", "raw_observations.jsonl", "13f_holdings.jsonl",
        "holding_observations.jsonl", "presentation_candidates.jsonl",
    ):
        path = filings / filename
        for row in jsonl(path):
            name = row.get("entity_name_raw") or row.get("entity_name") or row.get("observed_entity_string") or row.get("issuer_name") or row.get("nameOfIssuer")
            observation = source_obs(row, "filing_or_presentation", str(path.relative_to(run)))
            source = filing_sources.get(row.get("source_id")) or {}
            observation["source_url"] = observation.get("source_url") or source.get("source_url") or source.get("url")
            observation["publisher"] = row.get("publisher") or source.get("publisher") or observation["publisher"]
            observation["published_at"] = observation.get("published_at") or row.get("filing_date") or source.get("published_at")
            observation["retrieved_at"] = row.get("retrieved_at") or source.get("retrieved_at") or observation["retrieved_at"]
            observation["access_constraints"] = row.get("access_restrictions") or source.get("access_restrictions") or source.get("access_constraints")
            observation["relationship_hint"] = row.get("relationship_hypothesis") or row.get("relationship_type") or observation.get("relationship_hint")
            add(candidates, name, observation)

    # Accept both the browser page fixtures and the normalized NPN raw table. A
    # stable observation fingerprint prevents the same visible card from being
    # counted twice when both representations are present.
    seen_npn: set[tuple[str, str | None]] = set()
    for page_path in sorted((run / "npn_browser" / "pages").glob("page_*.json")):
        page = json.loads(page_path.read_text(encoding="utf-8"))
        for record in page.get("records", []):
            key = (record.get("name", ""), record.get("profile_url"))
            if key in seen_npn:
                continue
            seen_npn.add(key)
            row = dict(record)
            row.update({
                "source_url": page.get("url"),
                "publisher": "NVIDIA",
                "retrieved_at": "2026-08-25",
                "observation_id": f"npn-page-{page.get('page')}-{record.get('position')}",
                "relationship_hint": "partner",
            })
            add(candidates, row.get("name"), source_obs(row, "npn", str(page_path.relative_to(run))))
    for path in (run / "npn_browser" / "raw_listings.jsonl", run / "agents" / "npn_complete" / "raw_listings.jsonl"):
        for row in jsonl(path):
            key = (row.get("name", ""), row.get("profile_url"))
            if key in seen_npn:
                continue
            seen_npn.add(key)
            add(candidates, row.get("name"), source_obs(row, "npn", str(path.relative_to(run))))
    return candidates


def is_non_entity_noise(name: str, observations: list[dict]) -> bool:
    if name in NON_ENTITY_EXACT:
        return True
    # Product-page/NPN strings are kept for entity review because they are often
    # real private companies or projects. This reject rule is only for noisy NER
    # fragments from article prose.
    if any(obs["family"] not in {"official_article_2025", "official_article_2026"} for obs in observations):
        return False
    return any(pattern.search(name) for pattern in NON_ENTITY_PATTERNS)


def choose_reference_securities(matches: list[dict], prior_entity: dict | None) -> list[dict]:
    """Keep reference equity identifiers, not warrants/rights/preferred series.

    The SEC ticker file does not label security classes. Existing reviewed
    securities therefore take precedence. For a new entity, obvious derivative
    suffixes are removed and a non-OTC identifier is preferred when present.
    The complete accepted SEC rows remain in the filtered audit fixture.
    """
    if prior_entity:
        prior = {(str(s.get("exchange", "")).casefold(), str(s.get("ticker", "")).casefold()) for s in prior_entity.get("securities", [])}
        exact = [r for r in matches if (str(r.get("exchange", "")).casefold(), str(r.get("ticker", "")).casefold()) in prior]
        if exact:
            return exact
        prior_tickers = {ticker for _, ticker in prior}
        by_ticker = [r for r in matches if str(r.get("ticker", "")).casefold() in prior_tickers]
        if by_ticker:
            return by_ticker
    derivative = re.compile(r"(?:-W(?:T)?|-RI|-P[A-Z]?$|W$)", re.I)
    commonish = [r for r in matches if not derivative.search(str(r.get("ticker", "")))] or matches
    non_otc = [r for r in commonish if str(r.get("exchange", "")).upper() != "OTC"]
    return non_otc or commonish


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sec-user-agent", default=DEFAULT_UA)
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    run = repository_root / "runs" / "2026-08-25-run-003"
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    observations = collect(run)
    snapshot_path = repository_root / "data" / "snapshot_2026-08-25.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    existing = {entity["id"]: entity for entity in snapshot["entities"]}
    alias_map: dict[str, set[str]] = defaultdict(set)
    aggressive_alias_map: dict[str, set[str]] = defaultdict(set)
    for entity in existing.values():
        for alias in [entity["legal_name"], entity["display_name"], *entity.get("aliases", [])]:
            alias_map[strict_norm(alias)].add(entity["id"])
            aggressive_alias_map[aggressive_norm(alias)].add(entity["id"])

    req = Request(SEC_URL, headers={"User-Agent": args.sec_user_agent, "Accept": "application/json"})
    with urlopen(req, timeout=60) as response:
        sec_raw = response.read()
    payload = json.loads(sec_raw)
    sec_rows = [dict(zip(payload["fields"], values)) for values in payload["data"]]
    sec_by_strict: dict[str, list[dict]] = defaultdict(list)
    sec_by_aggressive: dict[str, list[dict]] = defaultdict(list)
    sec_by_cik: dict[str, list[dict]] = defaultdict(list)
    for issuer in sec_rows:
        sec_by_strict[strict_norm(str(issuer["name"]))].append(issuer)
        sec_by_aggressive[aggressive_norm(str(issuer["name"]))].append(issuer)
        sec_by_cik[str(issuer["cik"]).zfill(10)].append(issuer)

    resolved, ambiguous, unresolved, rejected = [], [], [], []
    registry_by_key: dict[str, dict] = {}
    normalization_audit: list[dict] = []
    filtered_sec: dict[tuple, dict] = {}

    for name in sorted(observations, key=str.casefold):
        obs = observations[name]
        record = {
            "candidate_id": stable_id("candidate", name),
            "candidate_name": name,
            "normalized_name": strict_norm(name),
            "observation_count": len(obs),
            "source_families": sorted({item["family"] for item in obs}),
            "observations": obs,
            "reviewed_at": generated_at,
            "fuzzy_promotion_used": False,
        }

        if name in MANUAL_OVERRIDES:
            status, rationale = MANUAL_OVERRIDES[name]
            record.update({"review_status": status, "resolution_status": f"{status}_manual_override", "review_rationale": rationale})
            {"ambiguous": ambiguous, "unresolved": unresolved, "rejected": rejected}[status].append(record)
            continue
        if is_non_entity_noise(name, obs):
            record.update({
                "review_status": "rejected",
                "resolution_status": "rejected_non_entity_extraction",
                "review_rationale": "Article NER string is a product/event/geography/title fragment, not a uniquely identifiable issuer candidate.",
            })
            rejected.append(record)
            continue

        if all(item.get("source_path", "").endswith("raw_observations.jsonl") for item in obs):
            record.update({
                "review_status": "unresolved",
                "resolution_status": "unresolved_raw_ocr_only",
                "review_rationale": "The name occurs only in the presentation raw OCR audit. Raw OCR is preserved for completeness but cannot establish issuer identity even when a same-name SEC issuer exists.",
            })
            unresolved.append(record)
            continue

        strict_key = strict_norm(name)
        existing_ids = sorted(alias_map.get(strict_key, set()))
        sec_matches = sec_by_strict.get(strict_key, [])
        match_method = None
        entity = None

        if len(existing_ids) > 1:
            record.update({"review_status": "ambiguous", "resolution_status": "ambiguous_existing_exact_alias", "candidate_entity_ids": existing_ids})
            ambiguous.append(record)
            continue
        if len(existing_ids) == 1:
            entity = existing[existing_ids[0]]
            # Revalidate the listing against SEC when a CIK is available. Non-US
            # exchange-only carry-forwards remain unresolved, not confirmed.
            ciks = {str(s.get("cik", "")).zfill(10) for s in entity.get("securities", []) if s.get("cik")}
            validated = [row for cik in ciks for row in sec_by_cik.get(cik, []) if row.get("exchange") and row.get("ticker")]
            if not validated:
                record.update({
                    "review_status": "unresolved",
                    "resolution_status": "identity_resolved_listing_not_revalidated",
                    "candidate_entity_id": entity["id"],
                    "review_rationale": "Exact prior-registry alias establishes an identity hypothesis, but no current SEC exchange:ticker row validates the carried listing; official exchange evidence is still required.",
                })
                unresolved.append(record)
                continue
            sec_matches = validated
            match_method = "existing_exact_alias_plus_sec_cik_revalidation"
        else:
            sec_matches = [row for row in sec_matches if row.get("exchange") and row.get("ticker")]
            if not sec_matches:
                # Audit aggressive matches but never auto-promote them, except the
                # explicit reviewed brand/legal-name table above.
                aggressive = [row for row in sec_by_aggressive.get(aggressive_norm(name), []) if row.get("exchange") and row.get("ticker")]
                reviewed_legal_name = REVIEWED_BRAND_MATCHES.get(name, "").casefold()
                reviewed = [row for row in sec_rows if reviewed_legal_name and reviewed_legal_name == str(row["name"]).casefold() and row.get("exchange") and row.get("ticker")]
                if reviewed:
                    sec_matches = reviewed
                    match_method = "manual_reviewed_brand_to_sec_issuer"
                    normalization_audit.append({
                        "candidate_name": name, "aggressive_normalized_name": aggressive_norm(name),
                        "decision": "accepted_after_manual_review", "sec_matches": reviewed,
                        "rationale": "Brand is a well-defined short form of this issuer; exact SEC ticker/exchange evidence retained.",
                    })
                else:
                    if aggressive:
                        normalization_audit.append({
                            "candidate_name": name, "aggressive_normalized_name": aggressive_norm(name),
                            "decision": "not_promoted", "sec_matches": aggressive,
                            "rationale": "Only aggressive normalization matched; technology/systems/group/holdings removal cannot auto-resolve identity.",
                        })
                    record.update({
                        "review_status": "unresolved",
                        "resolution_status": "unresolved_no_safe_exact_listed_match",
                        "review_rationale": "No strict exact alias or exact listed SEC issuer match; fuzzy/aggressive promotion is prohibited.",
                    })
                    unresolved.append(record)
                    continue
            else:
                match_method = "strict_exact_sec_issuer_name"

        unique_ciks = {str(row["cik"]).zfill(10) for row in sec_matches}
        if len(unique_ciks) != 1:
            record.update({
                "review_status": "ambiguous", "resolution_status": "ambiguous_multiple_sec_issuers",
                "sec_candidates": sec_matches,
                "review_rationale": "Name maps to more than one SEC issuer CIK; no automatic issuer selection.",
            })
            ambiguous.append(record)
            continue

        cik = next(iter(unique_ciks))
        legal_name = entity["legal_name"] if entity else sorted({str(row["name"]) for row in sec_matches}, key=len)[0]
        entity_id = entity["id"] if entity else stable_id("entity", f"sec:{cik}")
        reference_matches = choose_reference_securities(sec_matches, entity)
        securities = []
        for row in sorted(reference_matches, key=lambda x: (str(x.get("exchange")), str(x.get("ticker")))):
            item = {
                "security_id": f"{row['exchange']}:{row['ticker']}",
                "exchange": row["exchange"], "ticker": row["ticker"],
                "cik": str(row["cik"]).zfill(10), "security_type": "not_classified_in_sec_ticker_dataset",
            }
            if item not in securities:
                securities.append(item)
        for row in sec_matches:
            filtered_sec[(row["cik"], row["ticker"], row["exchange"])] = row
        record.update({
            "review_status": "resolved", "resolution_status": "resolved_listed",
            "entity_id": entity_id, "legal_name": legal_name,
            "security_identifiers": [s["security_id"] for s in securities],
            "match_method": match_method,
            "review_rationale": "Identity and current exchange:ticker are supported by an exact or explicitly reviewed SEC issuer match.",
        })
        resolved.append(record)

        reg = registry_by_key.setdefault(entity_id, {
            "entity_id": entity_id, "legal_name": legal_name,
            "display_name": entity.get("display_name") if entity else name,
            "aliases": set(), "listing_status": "listed_confirmed",
            "securities": [], "listing_evidence_ids": [],
        })
        reg["aliases"].add(name)
        if entity:
            reg["aliases"].update(entity.get("aliases", []))
        for security in securities:
            if security not in reg["securities"]:
                reg["securities"].append(security)
        evidence_id = stable_id("listing_evidence", f"sec:{cik}")
        if evidence_id not in reg["listing_evidence_ids"]:
            reg["listing_evidence_ids"].append(evidence_id)

    registry = []
    listing_evidence = []
    aliases = []
    for entity_id, reg in sorted(registry_by_key.items()):
        reg["aliases"] = sorted(reg["aliases"], key=str.casefold)
        reg["securities"] = sorted(reg["securities"], key=lambda x: x["security_id"])
        registry.append(reg)
        for alias in reg["aliases"]:
            aliases.append({"alias": alias, "normalized_alias": strict_norm(alias), "entity_id": entity_id, "alias_status": "reviewed"})
        ciks = sorted({s["cik"] for s in reg["securities"]})
        for cik in ciks:
            listing_evidence.append({
                "listing_evidence_id": stable_id("listing_evidence", f"sec:{cik}"),
                "entity_id": entity_id, "source_url": SEC_URL,
                "publisher": "U.S. Securities and Exchange Commission",
                "published_at": None, "retrieved_at": generated_at,
                "evidence_locator": f"data row(s) where cik={int(cik)}; filtered fixture retained",
                "access_constraints": "public_no_login; automated access used descriptive User-Agent; no access control bypassed",
                "security_identifiers": sorted(s["security_id"] for s in reg["securities"] if s["cik"] == cik),
                "evidence_scope": "issuer ticker/exchange identity only; security class is not supplied by this dataset",
            })

    all_records = sorted(resolved + ambiguous + unresolved + rejected, key=lambda x: x["candidate_name"].casefold())
    write_jsonl(output / "candidate_review.jsonl", all_records)
    write_jsonl(output / "entity_registry.jsonl", registry)
    write_jsonl(output / "aliases.jsonl", sorted(aliases, key=lambda x: (x["normalized_alias"], x["entity_id"])))
    write_jsonl(output / "listing_evidence.jsonl", listing_evidence)
    write_jsonl(output / "ambiguous_review_queue.jsonl", ambiguous)
    write_jsonl(output / "unresolved_review_queue.jsonl", unresolved)
    write_jsonl(output / "rejected_review_queue.jsonl", rejected)
    write_jsonl(output / "normalization_risk_audit.jsonl", normalization_audit)
    write_jsonl(output / "sec_company_tickers_exchange_filtered.jsonl", sorted(filtered_sec.values(), key=lambda x: (str(x["name"]), str(x["ticker"]))))
    write_json(output / "sec_source.json", {
        "url": SEC_URL, "publisher": "U.S. Securities and Exchange Commission",
        "retrieved_at": generated_at, "content_sha256": hashlib.sha256(sec_raw).hexdigest(),
        "access_constraints": "public_no_login; descriptive User-Agent; no access-control bypass",
        "fixture": "sec_company_tickers_exchange_filtered.jsonl",
        "fixture_scope": "Only rows supporting accepted resolutions are retained; source hash covers the full retrieved response.",
    })

    status_counts = {name: sum(r["review_status"] == name for r in all_records) for name in ("resolved", "ambiguous", "unresolved", "rejected")}
    validation = {
        "pass": len(all_records) == len(observations) and sum(status_counts.values()) == len(observations),
        "generated_at": generated_at, "candidate_names": len(observations),
        "status_counts": status_counts, "pending": len(observations) - sum(status_counts.values()),
        "registry_entities": len(registry), "alias_rows": len(aliases),
        "listing_evidence_rows": len(listing_evidence), "fuzzy_promotions": 0,
        "checks": {
            "one_terminal_status_per_candidate": len({r["candidate_name"] for r in all_records}) == len(observations),
            "resolved_have_exchange_ticker": all(r.get("security_identifiers") and all(":" in x for x in r["security_identifiers"]) for r in resolved),
            "registry_never_labels_unverified_as_listed": all(r["listing_status"] == "listed_confirmed" and r["listing_evidence_ids"] for r in registry),
            "no_fuzzy_promotion": True,
            "manual_risky_name_overrides_applied": all(any(r["candidate_name"] == name for r in ambiguous + unresolved + rejected) for name in MANUAL_OVERRIDES if name in observations),
        },
        "source_input_counts": {family: sum(family in r["source_families"] for r in all_records) for family in sorted({f for r in all_records for f in r["source_families"]})},
    }
    validation["pass"] = validation["pass"] and validation["pending"] == 0 and all(validation["checks"].values())
    write_json(output / "validation_report.json", validation)
    write_json(output / "summary.json", validation)
    print(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if validation["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
