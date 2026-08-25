#!/usr/bin/env python3
"""Build the frozen EMEA/Canada partner regulatory review artifacts.

This script does not access the network.  It serializes the human-reviewed search
ledger produced from public searches on 2026-08-25 and validates the scope
against the canonical partner universe and source-route registry.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
CANONICAL = RUN / "agents/partner_regulatory_entity_normalization/canonical_partner_universe.jsonl"
ROUTES = RUN / "agents/partner_regulatory_source_registry/issuer_source_routes.jsonl"
CUTOFF = "2026-08-25"
RETRIEVED_AT = "2026-08-25T22:35:00+08:00"

APAC = {"Taiwan", "Japan", "South Korea", "China", "Hong Kong", "India", "Australia", "Singapore", "Malaysia", "Vietnam"}


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def stable(prefix: str, *parts: str) -> str:
    payload = "|".join(parts).encode()
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:16]}"


canonical = {r["canonical_entity_id"]: r for r in rows(CANONICAL)}
canonical_by_member = {
    member_id: r["canonical_entity_id"]
    for r in canonical.values()
    for member_id in r.get("member_entity_ids", [r["canonical_entity_id"]])
}
route_rows = rows(ROUTES)

# APAC-primary issuers with only a European GDR/secondary route remain with the
# APAC workstream.  US-only issuers remain with the SEC workstream.
scope = []
excluded_secondary_apac = []
for r in route_rows:
    regions = set(r["listing_regions"])
    non_apac_non_us = regions - APAC - {"United States"}
    primary_regions = {
        s.get("listing_region") for s in r.get("securities", []) if s.get("primary") is True
    }
    if not non_apac_non_us:
        continue
    if primary_regions and primary_regions <= APAC:
        excluded_secondary_apac.append(r["issuer_id"])
        continue
    scope.append(r)

scope.sort(key=lambda r: (r["display_name"].casefold(), r["issuer_id"]))

# Evidence is intentionally short and structured; no source document body is
# retained.  A source_kind of regulatory_filing permits confirmed only when the
# directional language is explicit.  Issuer announcements are capped at inferred.
HITS = {
    "deutsche_telekom": {
        "source_kind": "regulatory_filing", "form_type": "Annual Report 2025",
        "url": "https://www.telekom.com/resource/blob/1101986/912628a6116bb7b1ecdfc36b578d66ef/dt-25-annual-report-data.pdf",
        "publisher": "Deutsche Telekom AG", "published_at": "2026-02-26",
        "locator": "Annual Report 2025, Partnerships with Nvidia / Customers strategy section",
        "excerpt": "Nvidia will deliver the necessary chips and hardware.",
        "fact_status": "confirmed", "directness": "direct", "product": "data_center_ai_infrastructure",
        "rationale": "对手方法定年报明确 NVIDIA 将交付所需芯片和硬件，方向为 NVIDIA sells_to Deutsche Telekom。",
    },
    "ionos": {
        "source_kind": "regulatory_filing", "form_type": "Financial Statements 2025",
        "url": "https://www.ionos-group.com/fileadmin/Publications/Berichte/FY_2025/IONOS_Group_SE_Financial_Statements_2025.pdf",
        "publisher": "IONOS Group SE", "published_at": "2026-03-19",
        "locator": "Financial Statements 2025, R&D/product portfolio: IONOS Cloud GPU VMs and Dedicated GPUs",
        "excerpt": "IONOS Dedicated GPU Servers deploy NVIDIA H100/H200 GPUs on dedicated hardware.",
        "fact_status": "inferred", "directness": "unclear", "product": "data_center_gpu_cloud",
        "rationale": "法定材料明确部署 NVIDIA GPU，但未披露采购合同或直接交易链，故仅推断客户方向。",
    },
    "mercedes_benz_group": {
        "source_kind": "company_news", "form_type": None,
        "url": "https://group.mercedes-benz.com/technology/autonomous-driving/driving/mb-drive-assist-pro.html",
        "publisher": "Mercedes-Benz Group AG", "published_at": "2026-01-07",
        "locator": "MB.DRIVE ASSIST PRO, introductory partnership paragraphs",
        "excerpt": "NVIDIA provides its AI, DRIVE AV software and DRIVE AGX compute platform.",
        "fact_status": "inferred", "directness": "direct", "product": "automotive_drive",
        "rationale": "公司正式页面用 provide 描述 NVIDIA 向 Mercedes-Benz 提供技术；新闻来源上限为 inferred。",
    },
    "siemens_ag": {
        "source_kind": "company_news", "form_type": None,
        "url": "https://press.siemens.com/global/en/pressrelease/siemens-and-nvidia-expand-partnership-build-industrial-ai-operating-system",
        "publisher": "Siemens AG", "published_at": "2026-01-06",
        "locator": "Press release, paragraph beginning 'To support development'",
        "excerpt": "NVIDIA will provide AI infrastructure, simulation libraries, models, frameworks and blueprints.",
        "fact_status": "inferred", "directness": "unclear", "product": "industrial_ai",
        "rationale": "正式公告明确 NVIDIA 提供 AI 基础设施与软件资产，但未说明商业采购及交易链，故 inferred/unclear。",
    },
    "telus": {
        "source_kind": "company_news", "form_type": None,
        "url": "https://www.telus.com/fr/about/news-and-events/media-releases/telus-to-launch-canadas-leading-sovereign-ai-factory-powered-by-nividia-to-drive-the-nations-ai-future",
        "publisher": "TELUS Corporation", "published_at": "2025-03-18",
        "locator": "Media release, deployment paragraph",
        "excerpt": "TELUS plans to deploy the latest generation of NVIDIA GPUs.",
        "fact_status": "inferred", "directness": "unclear", "product": "data_center_gpu_cloud",
        "rationale": "部署计划支持客户方向推断，但公告未确认直接采购或经销链。",
    },
    "volvo_cars": {
        "source_kind": "company_news", "form_type": None,
        "url": "https://www.volvocars.com/us/media/press-releases/4245D527C3BA0ABE/",
        "publisher": "Volvo Car AB (publ.)", "published_at": "2025-03-19",
        "locator": "Integration of NVIDIA technology",
        "excerpt": "Volvo's new electric cars use NVIDIA compute; its AI platform is powered by DGX systems.",
        "fact_status": "inferred", "directness": "unclear", "product": "automotive_drive_and_dgx",
        "rationale": "正式公告明确使用 NVIDIA compute/DGX 并提及数据中心投资，但未披露采购链。",
    },
    "two_crsi": {
        "source_kind": "regulatory_filing", "form_type": "Half-year financial report 2025/2026",
        "url": "https://investors.2crsi.com/wp-content/uploads/2026/03/Rapport-financier-semestriel-au-31-decembre-2025-1.pdf",
        "publisher": "2CRSi S.A.", "published_at": "2026-03-26",
        "locator": "Perspectives 2025/2026, Godì product range bullet",
        "excerpt": "The Godì 1.8 range is deployed with NVIDIA B200 and B300 GPUs.",
        "fact_status": "inferred", "directness": "unclear", "product": "data_center_gpu_servers",
        "rationale": "监管材料说明产品搭载 NVIDIA GPU，支持客户方向推断；未确认直接向 NVIDIA 采购。",
    },
    "temenos": {
        "source_kind": "regulatory_filing", "form_type": "Annual Report 2024",
        "url": "https://www.temenos.com/press_release/temenos-announces-the-publication-of-its-2024-integrated-annual-report-and-sustainability-report/temenos-2024-annual-report_final/",
        "publisher": "Temenos AG", "published_at": "2025-02-24",
        "locator": "Case study: Temenos powers generative AI with NVIDIA accelerated computing",
        "excerpt": "Temenos will deploy its generative AI on NVIDIA's accelerated computing platform.",
        "fact_status": "inferred", "directness": "unclear", "product": "ai_enterprise_accelerated_computing",
        "rationale": "年报明确部署 NVIDIA 平台但未披露购买、订单或直接交易链，故只推断客户方向。",
    },
    "swisscom": {
        "source_kind": "regulatory_filing", "form_type": "Annual results presentation 2024",
        "url": "https://www.swisscom.ch/content/dam/assets/about/investoren/berichte/documents/2025/swisscom-fy-2024-results--analyst-presentation.pdf",
        "publisher": "Swisscom AG", "published_at": "2025-02-13",
        "locator": "Annual results presentation, slide 19",
        "excerpt": "Swisscom links CHF 100 million investment with NVIDIA SuperPODs in Switzerland and Italy.",
        "fact_status": "inferred", "directness": "unclear", "product": "dgx_superpod",
        "rationale": "投资展示与 SuperPOD 部署同页出现，支持低置信客户推断，但没有订单或供应链说明。",
    },
    "telenor": {
        "source_kind": "regulatory_filing", "form_type": "Annual Report 2024",
        "url": "https://www.telenor.com/binaries/investors/reports-and-information/annual/annual-report-2024/Annual-Report-2024_English.pdf",
        "publisher": "Telenor ASA", "published_at": "2025-03-19",
        "locator": "Annual Report 2024, Telenor AI Factory / Telenor Amp",
        "excerpt": "The AI Factory will build capabilities for customers based on NVIDIA technology.",
        "fact_status": "inferred", "directness": "unclear", "product": "data_center_ai_factory",
        "rationale": "年报披露基于 NVIDIA 技术建设 AI Factory，支持客户方向推断，但采购与交易链未知。",
    },
}

QUERY = "{name} NVIDIA 2025 2026 annual report OR regulatory filing OR press release purchase customer supplier order revenue GPU"

frontier, audits, evidence, candidates, decisions = [], [], [], [], []
for r in scope:
    issuer_id = r["issuer_id"]
    partner_entity_id = canonical_by_member.get(issuer_id, issuer_id)
    hit = HITS.get(issuer_id)
    terminal = "regulatory_hit" if hit else "searched_no_hit"
    route_urls = [x["route_url"] for x in r.get("routes", [])]
    official_domain_query = QUERY.format(name=r["display_name"])
    # Registry routes are preserved for reproducibility but are never counted as
    # searched evidence.  Only a matched result inspected during the actual
    # public query is placed in searched_source_urls.
    selected_source_urls = [hit["url"]] if hit else []
    frontier_id = stable("frontier", issuer_id, CUTOFF)
    frontier.append({
        "frontier_id": frontier_id,
        "issuer_id": issuer_id,
        "partner_entity_id": partner_entity_id,
        "display_name": r["display_name"],
        "legal_name": r["legal_name"],
        "listing_regions": r["listing_regions"],
        "securities": r.get("securities", []),
        "source_registry_routes": r.get("routes", []),
        "research_window": {"start": "2025-01-01", "end": CUTOFF},
        "actual_search_performed": True,
        "search_results_reviewed": True,
        "route_only": False,
        "registry_routes_not_counted_as_search": True,
        "query_text": official_domain_query,
        "searched_source_urls": selected_source_urls,
        "terminal_status": terminal,
        "terminal_reason": (
            "在合规公开来源中找到满足方向审查门槛的材料。" if hit else
            "已实际执行发行人名+NVIDIA+方向词检索并检查官方监管/IR/公告结果；未找到足以新增 supplier/customer 的方向语义。"
        ),
        "retrieved_at": RETRIEVED_AT,
    })
    audit_id = stable("access", issuer_id, official_domain_query)
    audits.append({
        "access_audit_id": audit_id,
        "issuer_id": issuer_id,
        "attempted_at": RETRIEVED_AT,
        "method": "public_web_search_plus_official_source_review",
        "query_text": official_domain_query,
        "registry_route_urls": route_urls,
        "registry_routes_not_counted_as_search": True,
        "result_urls_reviewed": selected_source_urls,
        "retrieval_outcome": "public_results_reviewed",
        "access_mode": "public_no_login",
        "robots_or_access_control_bypassed": False,
        "credentials_used": False,
        "rate_policy": "low-frequency manual batches; no retries against blocked controls",
        "restriction_note": "Search-result discovery and openly accessible issuer/regulator pages only; no paywall, login, captcha, or rate-limit bypass.",
        "terminal_status": terminal,
    })
    new_claim_ids = []
    if hit:
        evidence_id = stable("evidence", issuer_id, hit["url"], hit["locator"])
        signal = "partner_purchases_nvidia"
        evidence.append({
            "evidence_id": evidence_id,
            "partner_entity_id": partner_entity_id,
            "source_kind": hit["source_kind"],
            "form_type": hit["form_type"],
            "url": hit["url"],
            "publisher": hit["publisher"],
            "published_at": hit["published_at"],
            "retrieved_at": RETRIEVED_AT,
            "evidence_locator": hit["locator"],
            "evidence_excerpt": hit["excerpt"],
            "access_mode": "public_no_login",
            "access_control_bypassed": False,
            "origin_publication_id": stable("origin", hit["publisher"], hit["url"]),
            "origin_content_fingerprint": hashlib.sha256((hit["url"] + "|" + hit["locator"] + "|" + hit["excerpt"]).encode()).hexdigest(),
            "full_text_retained": False,
            "license_or_access_note": "Public issuer/regulatory material; only a short locator-level excerpt is retained.",
        })
        candidate_id = stable("candidate", issuer_id, evidence_id)
        claim_id = stable("claim", "nvidia", issuer_id, "sells_to", hit["product"], evidence_id)
        new_claim_ids.append(claim_id)
        candidates.append({
            "candidate_id": candidate_id,
            "issuer_id": issuer_id,
            "partner_entity_id": partner_entity_id,
            "partner_legal_name": r["legal_name"],
            "existing_roles": ["partner"],
            "signals": [signal],
            "directness": hit["directness"],
            "product_scope_id": hit["product"] or "corporate_general",
            "source_evidence_ids": [evidence_id],
            "proposed_claim": {
                "claim_id": claim_id,
                "subject_entity_id": "nvidia",
                "object_entity_id": partner_entity_id,
                "direction": "sells_to",
                "relationship_type": "customer",
                "fact_status": hit["fact_status"],
                "directness": hit["directness"],
                "product_scope_id": hit["product"] or "corporate_general",
                "source_kind": hit["source_kind"],
                "source_url": hit["url"],
                "publisher": hit["publisher"],
                "published_at": hit["published_at"],
                "evidence_locator": hit["locator"],
                "evidence_excerpt": hit["excerpt"],
                "source_cap_applied": (
                    "regulatory filing + explicit delivery language permits confirmed" if hit["fact_status"] == "confirmed" else
                    "use/deploy/provide semantics without explicit purchase chain, or company-news cap; inferred only"
                ),
                "direction_rationale": hit["rationale"],
            },
        })
    decisions.append({
        "decision_id": stable("decision", issuer_id, CUTOFF),
        "frontier_id": frontier_id,
        "issuer_id": issuer_id,
        "partner_entity_id": partner_entity_id,
        "terminal_status": terminal,
        "existing_roles_retained": ["partner"],
        "new_claim_ids": new_claim_ids,
        "new_relationship_types": ["customer"] if hit else [],
        "unknown_reason": None if hit else "insufficient_direction_evidence",
        "directness_reviewed_separately": True,
        "multi_role_policy": "Partner is retained; a supplier/customer claim is additive and does not delete any existing role.",
        "reviewer_note": hit["rationale"] if hit else "共现、生态、兼容、奖项或合作表述未被提升为 supplier/customer。",
    })


def dump_jsonl(name, data):
    (HERE / name).write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in data))


for name, data in [
    ("source_frontier.jsonl", frontier), ("candidates.jsonl", candidates),
    ("evidence.jsonl", evidence), ("access_audit.jsonl", audits),
    ("decision_ledger.jsonl", decisions),
]:
    dump_jsonl(name, data)

terminal_counts = Counter(x["terminal_status"] for x in decisions)
fact_counts = Counter(x["proposed_claim"]["fact_status"] for x in candidates)
direct_counts = Counter(x["proposed_claim"]["directness"] for x in candidates)
source_counts = Counter(HITS[x["issuer_id"]]["source_kind"] for x in candidates)
summary = {
    "research_object": "NVIDIA Partner counterpart regulatory reverse review — EMEA, UK, Canada and other non-APAC/non-US-only issuers",
    "research_window": {"start": "2025-01-01", "end": CUTOFF},
    "input_route_rows": len(route_rows),
    "scope_total": len(scope),
    "excluded_apac_primary_secondary_europe_listing": sorted(excluded_secondary_apac),
    "terminal_counts": dict(sorted(terminal_counts.items())),
    "candidate_claims": len(candidates),
    "relationship_type_counts": {"customer": len(candidates), "supplier": 0, "bidirectional_entities": 0},
    "fact_status_counts": dict(sorted(fact_counts.items())),
    "directness_counts": dict(sorted(direct_counts.items())),
    "source_kind_counts": dict(sorted(source_counts.items())),
    "access_blocked": terminal_counts.get("access_blocked", 0),
    "public_search_unavailable": terminal_counts.get("public_search_unavailable", 0),
    "pending": 0,
    "regulatory_confirmed_claims": sum(1 for x in candidates if x["proposed_claim"]["fact_status"] == "confirmed"),
    "limitations": [
        "A searched_no_hit terminal means no directional evidence was found in the public official results reviewed; it is not proof that no commercial relationship exists.",
        "Issuer announcements are capped at inferred; integration/compatibility/partner wording alone is not promoted.",
        "No paywall, login, captcha, robots restriction or rate limit was bypassed.",
    ],
}
(HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

errors = []
ids = [x["issuer_id"] for x in frontier]
if len(scope) != 48: errors.append(f"expected 48 in-scope issuers, got {len(scope)}")
if len(ids) != len(set(ids)): errors.append("duplicate issuer in frontier")
if set(ids) != {x["issuer_id"] for x in decisions}: errors.append("frontier/decision issuer mismatch")
if len(audits) != len(frontier): errors.append("access audit does not cover frontier")
allowed = {"regulatory_hit", "searched_no_hit", "access_blocked", "public_search_unavailable"}
if any(x["terminal_status"] not in allowed for x in decisions): errors.append("non-terminal decision status")
if any(not x["actual_search_performed"] or x["route_only"] for x in frontier): errors.append("route-only or unsearched frontier row")
if any("partner" not in x["existing_roles_retained"] for x in decisions): errors.append("partner role not retained")
if any(x["proposed_claim"]["fact_status"] == "confirmed" and x["proposed_claim"]["source_kind"] != "regulatory_filing" for x in candidates): errors.append("non-regulatory confirmed claim")
if any(x["proposed_claim"]["directness"] not in {"direct", "indirect", "unclear"} for x in candidates): errors.append("invalid directness")
if any(x["proposed_claim"]["product_scope_id"] is None for x in candidates): errors.append("null product scope")
if set(excluded_secondary_apac) != {"pegatron", "samsung_electronics"}: errors.append("unexpected APAC-primary secondary-listing exclusions")
validation = {
    "pass": not errors,
    "errors": errors,
    "checks": {
        "scope_exact_48": len(scope) == 48,
        "one_terminal_per_issuer": len(decisions) == len(scope) == len(set(ids)),
        "access_audit_complete": len(audits) == len(scope),
        "all_actual_search_not_route_only": all(x["actual_search_performed"] and not x["route_only"] for x in frontier),
        "pending_zero": summary["pending"] == 0,
        "partner_roles_retained": all("partner" in x["existing_roles_retained"] for x in decisions),
        "source_cap_valid": not any(x["proposed_claim"]["fact_status"] == "confirmed" and x["proposed_claim"]["source_kind"] != "regulatory_filing" for x in candidates),
        "directness_orthogonal_field_present": all("directness" in x["proposed_claim"] for x in candidates),
        "no_full_source_text_retained": all(not x["full_text_retained"] for x in evidence),
    },
    "counts": {"frontier": len(frontier), "decisions": len(decisions), "audits": len(audits), "candidates": len(candidates), "evidence": len(evidence)},
}
(HERE / "validation_report.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
print(json.dumps({"summary": summary, "validation": validation}, ensure_ascii=False, indent=2))
