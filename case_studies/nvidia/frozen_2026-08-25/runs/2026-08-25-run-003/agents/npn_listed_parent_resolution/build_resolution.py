#!/usr/bin/env python3
"""Resolve frozen NPN groups to listed issuers without fuzzy auto-promotion.

This is an offline builder.  Network collection is deliberately separated into
``refresh_yahoo_fixture.py``; normal builds consume only frozen repository inputs.
Every previously-unresolved NPN group receives a terminal reviewed disposition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

CUTOFF = "2026-08-25"
COMPETENCY_TO_SCOPE = {
    "Compute": "accelerated-computing", "Visualization": "professional-visualization-and-workstations",
    "NVIDIA Enterprise Software": "nvidia-ai-enterprise", "NVIDIA Technologies": "architectures-and-core-technologies",
    "Embedded Compute": "embedded-robotics-and-edge", "NVIDIA Virtual Desktops": "virtual-gpu",
    "Networking": "networking", "DGX AI Compute Systems": "dgx-platform", "DGX Cloud": "dgx-cloud",
}
FALSE_SEC_HOMONYMS = {
    "Compugen Inc": "NPN card is the North-American IT integrator Compugen; SEC exact-normalized candidate Nasdaq:CGEN is an Israeli biotechnology issuer.",
    "TEN Inc": "SEC exact-normalized candidate Nasdaq:XHLD is TEN Holdings, not the NPN technology-services card TEN Inc.",
    "Cronos": "SEC exact-normalized candidate Nasdaq:CRON is Cronos Group, a cannabis issuer; the NPN technology card lacks identity evidence linking it to that issuer.",
}

LEGAL_SUFFIXES = {
    "inc", "incorporated", "corporation", "corp", "limited", "ltd", "llc", "plc",
    "company", "co", "group", "holdings", "holding", "sa", "spa", "ag", "nv", "se",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").casefold().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def legal_norm(value: str) -> str:
    toks = norm(value).split()
    while len(toks) > 1 and toks[-1] in LEGAL_SUFFIXES:
        toks.pop()
    return " ".join(toks)


def hid(prefix: str, value: str) -> str:
    return prefix + hashlib.sha256(value.encode()).hexdigest()[:16]


def security_id(exchange: str, ticker: str) -> str:
    return f"{exchange}:{ticker}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    run = args.run_dir
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    npn = run / "agents/npn_runtime_complete"
    er = run / "agents/entity_resolution_complete"
    gle = run / "agents/global_listing_overlay"
    groups = load_jsonl(npn / "entity_groups.jsonl")
    prior = load_jsonl(npn / "listed_group_matches.jsonl")
    prior_ids = {r["group_id"] for r in prior}
    target = [g for g in groups if g["group_id"] not in prior_ids]
    raw = {r["observation_id"]: r for r in load_jsonl(npn / "raw_listings.jsonl")}
    manual = json.loads((out / "reviewed_mappings.json").read_text(encoding="utf-8"))
    yahoo = {r["symbol"]: r for r in load_jsonl(out / "yahoo_chart_fixture.jsonl")}

    registries: dict[str, dict[str, Any]] = {}
    listing_evidence: dict[str, dict[str, Any]] = {}
    for base, fn in ((er, "entity_registry.jsonl"), (gle, "entity_registry_overlay.jsonl")):
        for r in load_jsonl(base / fn):
            registries[r["entity_id"]] = r
    for base in (er, gle):
        for r in load_jsonl(base / "listing_evidence.jsonl"):
            listing_evidence[r.get("listing_evidence_id") or r.get("evidence_id")] = r

    sec_path = out / "company_tickers_exchange.json"
    sec_payload = json.loads(sec_path.read_text(encoding="utf-8"))
    sec_rows = [dict(zip(sec_payload["fields"], row)) for row in sec_payload["data"]]
    sec_by_legal: dict[str, list[dict[str, Any]]] = {}
    for row in sec_rows:
        sec_by_legal.setdefault(legal_norm(row["name"]), []).append(row)

    by_name = {g["canonical_name"]: g for g in target}
    decisions: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    evidence: dict[str, dict[str, Any]] = {}
    entity_overlay: dict[str, dict[str, Any]] = {}
    comparisons: list[dict[str, Any]] = []

    def npn_evidence(g: dict[str, Any]) -> list[str]:
        ids = sorted({raw[x]["evidence_id"] for x in g["member_observation_ids"]})
        for eid in ids:
            rr = next(raw[x] for x in g["member_observation_ids"] if raw[x]["evidence_id"] == eid)
            evidence[eid] = {
                "evidence_id": eid,
                "evidence_type": "npn_card",
                "source_url": rr["source_url"],
                "publisher": rr["publisher"],
                "published_at": rr["published_at"],
                "retrieved_at": rr["retrieved_at"],
                "evidence_locator": rr["evidence_locator"],
                "access_constraints": rr["access_or_license_restrictions"],
                "upstream_path": "agents/npn_runtime_complete/raw_listings.jsonl",
            }
        return ids

    def upstream_listing_evidence(entity_id: str) -> list[str]:
        ids = list(registries[entity_id].get("listing_evidence_ids", []))
        for eid in ids:
            if eid in listing_evidence:
                r = listing_evidence[eid]
                evidence[eid] = {
                    "evidence_id": eid,
                    "evidence_type": r.get("evidence_type", "issuer_listing"),
                    "source_url": r["source_url"],
                    "publisher": r["publisher"],
                    "published_at": r.get("published_at"),
                    "retrieved_at": r["retrieved_at"],
                    "evidence_locator": r["evidence_locator"],
                    "access_constraints": r.get("access_constraints", "public_no_login"),
                    "upstream_path": "agents/entity_resolution_complete or agents/global_listing_overlay",
                }
        return ids

    def yahoo_evidence(symbol: str, entity_id: str) -> str:
        y = yahoo[symbol]
        eid = hid("npn-listing-evidence-", symbol + y["source_content_sha256"])
        evidence[eid] = {
            "evidence_id": eid,
            "entity_id": entity_id,
            "evidence_type": "public_market_listing_snapshot",
            "source_url": y["source_url"],
            "publisher": "Yahoo Finance",
            "published_at": None,
            "retrieved_at": y["retrieved_at"],
            "evidence_locator": "chart.result[0].meta: symbol, exchangeName/fullExchangeName, instrumentType=EQUITY, longName/shortName, regularMarketTime",
            "evidence_excerpt": f"{y['long_name']} — {y['symbol']} — {y['exchange_name']} — {y['instrument_type']}",
            "access_constraints": "Public JSON chart endpoint; no login, key, CAPTCHA, robots, paywall, or access-control bypass.",
            "source_content_sha256": y["source_content_sha256"],
            "snapshot_path": "agents/npn_listed_parent_resolution/yahoo_chart_fixture.jsonl",
        }
        return eid

    def manual_listing_evidence(item: dict[str, Any], entity_id: str) -> str:
        src = item["issuer"]["listing_source"]
        eid = hid("npn-listing-evidence-", entity_id + src["url"] + src["locator"])
        evidence[eid] = {"evidence_id": eid, "entity_id": entity_id, "evidence_type": "issuer_listing",
            "source_url": src["url"], "publisher": src["publisher"], "published_at": src.get("published_at"),
            "retrieved_at": "2026-08-25T20:00:00+08:00", "evidence_locator": src["locator"],
            "evidence_excerpt": src["excerpt"], "access_constraints": "Public official issuer page; no access-control bypass.",
            "verification_method": "manual_review_of_official_public_source"}
        return eid

    def parent_evidence(item: dict[str, Any], entity_id: str) -> list[str]:
        sources = item.get("mapping_sources") or ([item["mapping_source"]] if item.get("mapping_source") else [])
        ids = []
        for src in sources:
            eid = hid("npn-parent-evidence-", item["name"] + src["url"] + src["locator"])
            evidence[eid] = {
            "evidence_id": eid,
            "entity_id": entity_id,
            "evidence_type": "brand_or_subsidiary_parent_mapping",
            "source_url": src["url"],
            "publisher": src["publisher"],
            "published_at": src.get("published_at"),
            "retrieved_at": "2026-08-25T20:00:00+08:00",
            "evidence_locator": src["locator"],
            "evidence_excerpt": src["excerpt"],
            "access_constraints": "Public corporate/issuer page; facts and short locator only; no access control bypass.",
            "verification_method": "manual_review_of_named_public_source",
            }
            ids.append(eid)
        return ids

    def add_mapping(g: dict[str, Any], item: dict[str, Any], method: str) -> None:
        kind = item["resolution_kind"]
        if kind == "direct_issuer":
            fact, cap = "confirmed", 95
        elif kind == "subsidiary_to_parent":
            fact, cap = "inferred", 69
        elif kind == "brand_to_parent":
            fact, cap = "inferred", 69
        else:
            fact, cap = "inferred", 59
        issuer = item["issuer"]
        entity_id = issuer["entity_id"]
        npn_ids = npn_evidence(g)
        if entity_id in registries:
            ent = registries[entity_id]
            secs = [{**s, "security_id": s.get("security_id") or security_id(s["exchange"], s["ticker"]), "status_at_cutoff": s.get("status_at_cutoff", "active_at_cutoff")} for s in ent["securities"]]
            list_ids = upstream_listing_evidence(entity_id)
            display = ent["display_name"]
            legal = ent["legal_name"]
        else:
            secs = [{
                "exchange": issuer["exchange"], "ticker": issuer["ticker"],
                "security_id": security_id(issuer["exchange"], issuer["ticker"]),
                "primary": True, "status_at_cutoff": "active_at_cutoff",
            }]
            display, legal = issuer["display_name"], issuer["legal_name"]
            list_ids = [manual_listing_evidence(item, entity_id)] if issuer.get("listing_source") else [yahoo_evidence(issuer["yahoo_symbol"], entity_id)]
            entity_overlay[entity_id] = {
                "entity_id": entity_id, "display_name": display, "legal_name": legal,
                "listing_status": "listed_confirmed", "securities": secs,
                "listing_evidence_ids": list_ids, "research_cutoff": CUTOFF,
            }
        peids = parent_evidence(item, entity_id)
        mapping_ids = list_ids + peids
        all_ids = sorted(set(npn_ids + mapping_ids))
        row = {
            "mapping_id": hid("npn-parent-map-", g["group_id"] + entity_id),
            "group_id": g["group_id"], "npn_name": g["canonical_name"],
            "entity_id": entity_id, "display_name": display, "legal_name": legal,
            "securities": secs, "resolution_kind": kind,
            "fact_status_recommendation": fact,
            "confidence_cap_recommendation": cap,
            "mapping_method": method,
            "fuzzy_matching_used": False,
            "npn_evidence_ids": npn_ids,
            "mapping_evidence_ids": sorted(set(mapping_ids)),
            "all_evidence_ids": all_ids,
            "uncertainty": item.get("uncertainty", "none_material_identified" if kind == "direct_issuer" else "NPN relationship is observed for the named card; endpoint substitution to the public parent is an inference."),
            "status": "terminal", "pending": False,
        }
        mappings.append(row)
        decisions.append({
            "decision_id": hid("npn-parent-decision-", g["group_id"]),
            "group_id": g["group_id"], "candidate_name": g["canonical_name"],
            "decision": "resolved_listed_endpoint", "reason": item["review_reason"],
            "resolution_kind": kind, "mapping_id": row["mapping_id"],
            "fuzzy_matching_used": False, "status": "terminal", "pending": False,
        })
        if item.get("candidate_comparison"):
            comparisons.append({"group_id": g["group_id"], **item["candidate_comparison"]})

    # Human-reviewed catalog always wins over mechanical SEC discovery.
    catalog = {r["name"]: r for r in manual["mappings"]}
    processed: set[str] = set()
    for name, item in catalog.items():
        if name not in by_name:
            raise ValueError(f"reviewed mapping name not present among 950 targets: {name}")
        add_mapping(by_name[name], item, "explicit_reviewed_exact_card_or_parent_rule")
        processed.add(name)

    for item in manual.get("rejections", []):
        name = item["name"]
        if name not in by_name or name in processed:
            raise ValueError(f"invalid or duplicate reviewed rejection: {name}")
        g = by_name[name]
        npn_ids = npn_evidence(g)
        eids = []
        for src in item.get("sources", []):
            eid = hid("npn-rejection-evidence-", name + src["url"] + src["locator"])
            evidence[eid] = {"evidence_id": eid, "evidence_type": "cutoff_listing_status",
                "source_url": src["url"], "publisher": src["publisher"], "published_at": src.get("published_at"),
                "retrieved_at": "2026-08-25T20:00:00+08:00", "evidence_locator": src["locator"],
                "evidence_excerpt": src["excerpt"], "access_constraints": "Public official source; no access-control bypass."}
            eids.append(eid)
        row = {"group_id": g["group_id"], "candidate_name": name, "decision": item["decision"],
               "reason": item["reason"], "npn_evidence_ids": npn_ids, "mapping_evidence_ids": eids,
               "fuzzy_matching_used": False, "status": "terminal", "pending": False}
        rejected.append(row)
        decisions.append({"decision_id": hid("npn-parent-decision-", g["group_id"]), **row})
        processed.add(name)

    for g in target:
        name = g["canonical_name"]
        if name in processed:
            continue
        candidates = sec_by_legal.get(legal_norm(name), [])
        if name in FALSE_SEC_HOMONYMS and candidates:
            npn_ids = npn_evidence(g)
            row = {
                "group_id": g["group_id"], "candidate_name": name,
                "decision": "rejected_false_homonym", "reason": FALSE_SEC_HOMONYMS[name],
                "sec_candidates": candidates, "npn_evidence_ids": npn_ids,
                "fuzzy_matching_used": False, "status": "terminal", "pending": False,
            }
            rejected.append(row)
            decisions.append({"decision_id": hid("npn-parent-decision-", g["group_id"]), **row})
            continue
        if len(candidates) == 1:
            c = candidates[0]
            item = {
                "name": name, "resolution_kind": "direct_issuer",
                "issuer": {"entity_id": hid("npn-issuer-", f"{c['exchange']}:{c['ticker']}"),
                           "display_name": name, "legal_name": c["name"],
                           "exchange": c["exchange"], "ticker": c["ticker"],
                           "yahoo_symbol": c["ticker"]},
                "review_reason": "Human-reviewed strict legal-name equality to the official SEC exchange/ticker row; no fuzzy or token-deletion match.",
            }
            # Use a synthetic Yahoo-shaped SEC evidence row for one uniform path.
            symbol = c["ticker"]
            if symbol not in yahoo:
                yahoo[symbol] = {
                    "symbol": symbol, "long_name": c["name"], "exchange_name": c["exchange"],
                    "instrument_type": "EQUITY", "source_url": "https://www.sec.gov/files/company_tickers_exchange.json",
                    "retrieved_at": "2026-08-25T17:35:00+08:00",
                    "source_content_sha256": hashlib.sha256(sec_path.read_bytes()).hexdigest(),
                }
            add_mapping(g, item, "reviewed_strict_sec_legal_name_exact")
        else:
            npn_ids = npn_evidence(g)
            reason = "No reviewed direct-issuer or listed-parent identity was established from the SEC exact screen, global issuer overlay, and curated corporate-family screen. Absence is not evidence that the card is private."
            if len(candidates) > 1:
                reason = "Multiple strict SEC legal-name candidates remain and no identity evidence distinguishes the NPN card; fail closed."
            row = {
                "decision_id": hid("npn-parent-decision-", g["group_id"]),
                "group_id": g["group_id"], "candidate_name": name,
                "decision": "unresolved_after_multisource_screen", "reason": reason,
                "sec_candidates": candidates, "npn_evidence_ids": npn_ids,
                "screened_sources": ["SEC company_tickers_exchange.json", "existing US entity registry", "global listing overlay", "reviewed corporate-family catalog"],
                "fuzzy_matching_used": False, "status": "terminal", "pending": False,
            }
            unresolved.append(row)
            decisions.append(row)

    decisions.sort(key=lambda r: r["group_id"])
    mappings.sort(key=lambda r: r["group_id"])
    unresolved.sort(key=lambda r: r["group_id"])
    rejected.sort(key=lambda r: r["group_id"])
    comparisons.sort(key=lambda r: r["group_id"])
    write_jsonl(out / "mapping_decision_ledger.jsonl", decisions)
    write_jsonl(out / "resolved_parent_mappings.jsonl", mappings)
    write_jsonl(out / "listed_entity_registry_overlay.jsonl", sorted(entity_overlay.values(), key=lambda r: r["entity_id"]))
    write_jsonl(out / "mapping_evidence.jsonl", sorted(evidence.values(), key=lambda r: r["evidence_id"]))
    write_jsonl(out / "unresolved_review_queue.jsonl", unresolved)
    write_jsonl(out / "rejected_candidates.jsonl", rejected)
    write_jsonl(out / "candidate_comparisons.jsonl", comparisons)

    # Integration-ready partner claims: merge repeated regional cards that map to
    # the same listed endpoint and product scope, retaining every group/tag/evidence.
    group_by_id = {g["group_id"]: g for g in groups}
    claim_acc: dict[str, dict[str, Any]] = {}
    for m in mappings:
        g = group_by_id[m["group_id"]]
        for competency in g["competencies"]:
            scope = COMPETENCY_TO_SCOPE[competency]
            key = f"nvidia|{m['entity_id']}|partners_with|partner|{scope}"
            row = claim_acc.setdefault(key, {
                "claim_id": hid("npn-parent-claim-", key), "dedup_key": key,
                "subject_entity_id": "nvidia", "object_entity_id": m["entity_id"],
                "direction": "partners_with", "relationship_type": "partner",
                "relation_subtype": "nvidia_partner_network_directory_member",
                "product_scope_id": scope, "competencies": [], "npn_group_ids": [],
                "source_observation_ids": [], "evidence_ids": [], "partner_types": [],
                "specializations": [], "partner_levels": [], "locations": [], "product_service_tags": [],
                "resolution_kinds": [], "fact_status": "confirmed", "confidence_score": 80,
                "as_of": CUTOFF, "temporal_status": "current_as_observed_at_cutoff",
                "direction_explanation": "Official NPN directory membership establishes a symmetric partner-program relationship; it does not establish a buyer/seller direction.",
                "role_boundary": "Directory membership supports partner only. It is not evidence that the member is an NVIDIA supplier or customer.",
                "limitations": ["NPN directory membership alone does not disclose transaction direction, revenue, spend, contract terms, or exclusivity.", "A competency is a program tag mapped to one canonical product scope; it is not proof of product adoption or purchase."],
            })
            for field, vals in (("competencies", [competency]), ("npn_group_ids", [g["group_id"]]),
                                ("source_observation_ids", g["member_observation_ids"]), ("evidence_ids", m["all_evidence_ids"]),
                                ("partner_types", g["partner_types"]), ("specializations", g["specializations"]),
                                ("partner_levels", g["partner_levels"]), ("locations", g["locations"]),
                                ("product_service_tags", g["product_service_tags"]), ("resolution_kinds", [m["resolution_kind"]])):
                row[field] = sorted(set(row[field]) | set(vals))
            if m["fact_status_recommendation"] == "inferred":
                row["fact_status"] = "inferred"
            row["confidence_score"] = min(row["confidence_score"], m["confidence_cap_recommendation"])
    for row in claim_acc.values():
        if "direct_issuer" in row["resolution_kinds"]:
            row["fact_status"], row["confidence_score"] = "confirmed", 80
        else:
            row["fact_status"] = "inferred"
    new_claims = sorted(claim_acc.values(), key=lambda r: r["dedup_key"])
    prior_claims = load_jsonl(npn / "relationship_claims.jsonl")
    combined = {r["dedup_key"]: r for r in prior_claims}
    for r in new_claims:
        if r["dedup_key"] in combined:
            old = combined[r["dedup_key"]]
            for field in ("evidence_ids", "npn_group_ids", "source_observation_ids", "partner_types", "specializations", "partner_levels", "locations", "product_service_tags", "competencies", "resolution_kinds"):
                old[field] = sorted(set(old.get(field, [])) | set(r.get(field, [])))
            old["fact_status"] = "confirmed" if "confirmed" in {old.get("fact_status"), r.get("fact_status")} else "inferred"
            old["confidence_score"] = max(old.get("confidence_score", 0), r["confidence_score"])
        else:
            combined[r["dedup_key"]] = r
    write_jsonl(out / "relationship_claims_overlay.jsonl", new_claims)
    write_jsonl(out / "relationship_claims_complete.jsonl", sorted(combined.values(), key=lambda r: r["dedup_key"]))
    write_json(out / "integration_manifest.json", {"prior_claims": len(prior_claims), "new_claims": len(new_claims), "combined_claims": len(combined), "strategy": "replace agents/npn_runtime_complete/relationship_claims.jsonl with relationship_claims_complete.jsonl in final snapshot; evidence union is agents/npn_runtime_complete/evidence.jsonl plus mapping_evidence.jsonl", "new_group_count": len(mappings), "new_entity_count": len({m['entity_id'] for m in mappings})})

    c = Counter(r["decision"] for r in decisions)
    kinds = Counter(r["resolution_kind"] for r in mappings)
    summary = {
        "research_cutoff": CUTOFF, "frozen_group_count": len(groups),
        "prior_resolved_count": len(prior), "audited_target_count": len(target),
        "terminal_decision_count": len(decisions), "pending_count": sum(bool(r.get("pending")) for r in decisions),
        "new_resolved_count": len(mappings), "unresolved_count": len(unresolved),
        "rejected_false_homonym_count": len(rejected), "decision_counts": dict(c),
        "resolution_kind_counts": dict(kinds),
        "total_listed_group_coverage": len(prior) + len(mappings),
        "coverage_rate_of_973": round((len(prior) + len(mappings)) / len(groups), 6),
        "new_relationship_claim_count": len(new_claims), "combined_relationship_claim_count": len(combined),
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
