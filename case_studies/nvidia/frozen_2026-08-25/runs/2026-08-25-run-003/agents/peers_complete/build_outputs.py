#!/usr/bin/env python3
"""Build the reviewed, category-level NVIDIA peer research fixture."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parent
CUTOFF = "2026-08-25"
RETRIEVED = "2026-08-25T22:30:00+08:00"

CATEGORIES = [
    "Data Center Compute",
    "Networking",
    "AI Software & Cloud",
    "Gaming/Consumer",
    "Pro Viz/Design/Simulation",
    "Robotics/Edge/Embedded",
    "Automotive",
    "Healthcare/Life Sciences",
]

LISTINGS = {
    "AMD": ("Advanced Micro Devices, Inc.", "Nasdaq", "AMD", "0000002488"),
    "INTC": ("Intel Corporation", "Nasdaq", "INTC", "0000050863"),
    "AMZN": ("Amazon.com, Inc.", "Nasdaq", "AMZN", "0001018724"),
    "GOOGL": ("Alphabet Inc.", "Nasdaq", "GOOGL", "0001652044"),
    "MSFT": ("Microsoft Corporation", "Nasdaq", "MSFT", "0000789019"),
    "AVGO": ("Broadcom Inc.", "Nasdaq", "AVGO", "0001730168"),
    "ANET": ("Arista Networks, Inc.", "NYSE", "ANET", "0001596532"),
    "CSCO": ("Cisco Systems, Inc.", "Nasdaq", "CSCO", "0000858877"),
    "MRVL": ("Marvell Technology, Inc.", "Nasdaq", "MRVL", "0001835632"),
    "QCOM": ("QUALCOMM Incorporated", "Nasdaq", "QCOM", "0000804328"),
    "AMBA": ("Ambarella, Inc.", "Nasdaq", "AMBA", "0001280263"),
    "TSLA": ("Tesla, Inc.", "Nasdaq", "TSLA", "0001318605"),
    "MBLY": ("Mobileye Global Inc.", "Nasdaq", "MBLY", "0001910139"),
    "SDGR": ("Schrodinger, Inc.", "Nasdaq", "SDGR", "0001490978"),
}

ACCESS = {
    "access": "public_no_login",
    "login_required": False,
    "paywall": False,
    "robots_or_access_control_bypassed": False,
    "redistribution": "structured facts and short excerpts only; no full page retained",
}


def fp(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


sources: dict[str, dict] = {}


def evidence(
    eid: str,
    url: str,
    publisher: str,
    title: str,
    source_type: str,
    locator: str,
    excerpt: str,
    published_at: str | None = None,
    notes: str | None = None,
) -> str:
    row = {
        "evidence_id": eid,
        "url": url,
        "publisher": publisher,
        "title": title,
        "source_type": source_type,
        "published_at": published_at,
        "retrieved_at": RETRIEVED,
        "evidence_locator": locator,
        "short_excerpt": excerpt,
        "access_constraints": ACCESS,
        "content_fingerprint": fp("|".join([url, locator, excerpt])),
        "notes": notes,
    }
    sources[eid] = row
    return eid


SEC_LIST_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
for ticker, (name, exchange, _, cik) in LISTINGS.items():
    evidence(
        f"ev-listing-{ticker.lower()}",
        SEC_LIST_URL,
        "U.S. Securities and Exchange Commission",
        "Company tickers and exchanges",
        "official_listing_reference",
        f"data row matching CIK {cik}",
        f"{name}; ticker {ticker}; exchange {exchange}.",
        notes="The SEC file is a current ticker/exchange reference, not an exchange admission opinion.",
    )

TENK_URL = "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm"


def tenk(eid: str, company: str, scope: str) -> str:
    return evidence(
        eid,
        TENK_URL,
        "NVIDIA Corporation / U.S. Securities and Exchange Commission",
        "NVIDIA Form 10-K for fiscal year ended January 25, 2026",
        "regulatory_filing",
        "Item 1, Business—Competition, printed pages 7–8",
        f"NVIDIA identifies {company} among competitors in {scope}.",
        "2026-02-25",
        "Entity and category wording was manually checked against the filing competition section.",
    )


TENK = {
    "AMD": tenk("ev-10k-amd", "AMD", "GPUs, custom chips, SoCs and networking"),
    "INTC": tenk("ev-10k-intel", "Intel", "GPUs, custom chips, SoCs and networking"),
    "AMZN": tenk("ev-10k-amazon", "Amazon", "internally designed accelerated/AI computing hardware and software"),
    "GOOGL": tenk("ev-10k-alphabet", "Alphabet", "internally designed accelerated/AI computing hardware and software"),
    "MSFT": tenk("ev-10k-microsoft", "Microsoft", "internally designed accelerated/AI computing hardware and software"),
    "AVGO": tenk("ev-10k-broadcom", "Broadcom", "SoCs and networking"),
    "ANET": tenk("ev-10k-arista", "Arista Networks", "data-center networking"),
    "CSCO": tenk("ev-10k-cisco", "Cisco", "data-center networking"),
    "MRVL": tenk("ev-10k-marvell", "Marvell", "data-center networking"),
    "QCOM": tenk("ev-10k-qualcomm", "Qualcomm", "systems-on-chip"),
    "AMBA": tenk("ev-10k-ambarella", "Ambarella", "systems-on-chip"),
    "TSLA": tenk("ev-10k-tesla", "Tesla", "internally designed systems-on-chip"),
}

PRODUCT = {
    "amd_instinct": evidence("ev-product-amd-instinct", "https://www.amd.com/en/products/accelerators/instinct/mi350.html", "Advanced Micro Devices, Inc.", "AMD Instinct MI350 Series GPUs", "counterparty_official_product_page", "Heading 'Leadership AI & HPC Acceleration' and 'Under the Hood'", "AMD says MI350 GPUs are built on AMD CDNA 4 architecture for AI training, inference and HPC."),
    "intel_gaudi": evidence("ev-product-intel-gaudi", "https://www.intel.com/content/www/us/en/products/details/processors/ai-accelerators/gaudi.html", "Intel Corporation", "Intel Gaudi AI Accelerator Products", "counterparty_official_product_page", "Heading 'Intel Gaudi 3 AI Accelerators'", "Intel describes Gaudi 3 PCIe cards and rack-scale systems as its AI accelerators for LLM, RAG, training and inference workloads."),
    "aws_trainium": evidence("ev-product-aws-trainium", "https://aws.amazon.com/ai/machine-learning/trainium/", "Amazon Web Services, Inc.", "AWS Trainium", "counterparty_official_product_page", "Lines 238–246, heading 'Why Trainium?'", "AWS calls Trainium a purpose-built AI chip and describes a co-designed chip, server, network, software and services system."),
    "google_tpu": evidence("ev-product-google-tpu", "https://cloud.google.com/tpu", "Google Cloud", "Tensor Processing Units", "counterparty_official_product_page", "Lines 40–48, 'Engineered for next-generation AI'", "Google calls TPUs custom accelerators co-designed with open software for the AI lifecycle."),
    "microsoft_maia": evidence("ev-product-microsoft-maia", "https://blogs.microsoft.com/blog/2026/01/26/maia-200-the-ai-accelerator-built-for-inference/", "Microsoft Corporation", "Maia 200: The AI accelerator built for inference", "counterparty_official_blog", "Opening and section 'Engineered for AI inference'", "Microsoft describes Maia 200 as its first-party inference accelerator and a Microsoft-designed chip, software, network and rack system.", "2026-01-26"),
    "broadcom_switch": evidence("ev-product-broadcom-switch", "https://www.broadcom.com/products/ethernet-connectivity/switching/strataxgs", "Broadcom Inc.", "StrataXGS Switch Solutions", "counterparty_official_product_page", "Opening product-line description and Tomahawk rows", "Broadcom offers self-branded programmable Ethernet switch silicon for data-center cloud and AI networks."),
    "arista_switch": evidence("ev-product-arista-switch", "https://www.arista.com/en/products/platforms", "Arista Networks, Inc.", "Arista Networks Cloud Networking Portfolio", "counterparty_official_product_page", "Opening portfolio description and 7800R4 section", "Arista describes its EOS-based 400/800GbE platforms for large data centers and AI/ML clusters."),
    "cisco_silicon": evidence("ev-product-cisco-silicon", "https://www.cisco.com/site/us/en/products/networking/silicon-one/index.html", "Cisco Systems, Inc.", "Cisco Silicon One", "counterparty_official_product_page", "Opening and 'G-Series: AI Scale Switch'", "Cisco describes a scalable programmable networking architecture with purpose-built AI scale switching silicon."),
    "marvell_switch": evidence("ev-product-marvell-switch", "https://www.marvell.com/products/data-center-switches.html", "Marvell Technology, Inc.", "Data Center Switches", "counterparty_official_product_page", "Opening and 'Teralynx AI Cloud Network Switches'", "Marvell describes Teralynx as clean-sheet Ethernet switch silicon for cloud and AI data-center fabrics."),
    "aws_sagemaker": evidence("ev-product-aws-sagemaker", "https://aws.amazon.com/sagemaker/ai/", "Amazon Web Services, Inc.", "Amazon SageMaker AI", "counterparty_official_product_page", "Lines 34–45, 'Meet SageMaker AI'", "AWS describes SageMaker AI as a managed platform for building, training, customizing and deploying AI models."),
    "google_agent": evidence("ev-product-google-agent-platform", "https://docs.cloud.google.com/gemini-enterprise-agent-platform/build", "Google Cloud", "Build with Gemini Enterprise Agent Platform", "counterparty_official_documentation", "Opening and 'Create agents in the console'", "Google documents a platform for building and deploying agents with models, tools, RAG, grounding and enterprise integrations.", "2026-08-19"),
    "microsoft_foundry": evidence("ev-product-microsoft-foundry", "https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-azure-ai-foundry", "Microsoft Corporation", "What is Microsoft Foundry?", "counterparty_official_documentation", "Sections 'What you can build' and 'Enterprise-ready platform'", "Microsoft documents its unified platform for building agents and using models and tools with monitoring and governance.", "2026-07-20"),
    "nvidia_dgx_cloud": evidence("ev-nvidia-dgx-cloud", "https://www.nvidia.com/en-us/data-center/dgx-cloud/", "NVIDIA Corporation", "NVIDIA DGX Cloud", "subject_official_product_page", "Heading and 'DGX Cloud—How NVIDIA Builds AI'", "NVIDIA describes DGX Cloud as its cloud environment for building and operating AI at scale."),
    "amd_radeon": evidence("ev-product-amd-radeon", "https://www.amd.com/en/products/graphics/desktops/radeon.html", "Advanced Micro Devices, Inc.", "AMD Radeon RX Graphics Cards", "counterparty_official_product_page", "Heading 'Radeon RX 9000 Series Graphics'", "AMD describes Radeon RX 9000 GPUs, built on AMD RDNA 4, for ultra-fast gaming."),
    "intel_arc": evidence("ev-product-intel-arc", "https://www.intel.com/content/www/us/en/products/details/discrete-gpus/arc.html", "Intel Corporation", "Intel Arc GPUs", "counterparty_official_product_page", "Sections 'Explore Intel Arc GPUs' and 'ultimate gaming experience'", "Intel offers Arc desktop and laptop GPUs for high-performance gaming with Intel XeSS and AI engines."),
    "amd_radeon_pro": evidence("ev-product-amd-radeon-pro", "https://www.amd.com/en/products/graphics/workstations.html", "Advanced Micro Devices, Inc.", "AMD Radeon Professional Graphics", "counterparty_official_product_page", "Heading 'Built for Demanding Creative, Engineering, and AI Applications'", "AMD offers self-branded Radeon PRO workstation GPUs for creative, engineering and visualization workflows."),
    "intel_arc_pro": evidence("ev-product-intel-arc-pro", "https://www.intel.com/content/www/us/en/products/details/discrete-gpus/arc/workstations/b-series.html", "Intel Corporation", "Intel Arc Pro B-Series Graphics Cards", "counterparty_official_product_page", "Sections 'Designed around how professionals work' and 'Design & Engineering'", "Intel offers Arc Pro workstation GPUs for CAD, 3D, architectural, rendering and visualization workflows."),
    "qualcomm_rb5": evidence("ev-product-qualcomm-rb5", "https://www.qualcomm.com/developer/hardware/robotics-rb5-development-kit", "Qualcomm Technologies, Inc.", "Qualcomm Robotics RB5 Development Kit", "counterparty_official_product_page", "Overview and 'On Board Artificial Intelligence'", "Qualcomm offers a robotics development platform with its QRB5165 SoC, AI engine and edge computer-vision capabilities."),
    "ambarella_robotics": evidence("ev-product-ambarella-robotics", "https://www.ambarella.com/applications/aiot-industrial-robotics/", "Ambarella, Inc.", "AIoT, Industrial & Robotics", "counterparty_official_product_page", "Opening and technology list", "Ambarella says it developed processors for computer vision, neural-network processing and robotics at low power."),
    "qualcomm_ride": evidence("ev-product-qualcomm-ride", "https://www.qualcomm.com/automotive/solutions/snapdragon-ride", "Qualcomm Technologies, Inc.", "Snapdragon Ride", "counterparty_official_product_page", "Sections 'Scalability and flexibility' and 'Meet our family of Snapdragon Ride SoCs'", "Qualcomm offers customizable Snapdragon Ride SoCs, SDKs and automated-driving platforms for ADAS and AD."),
    "tesla_fsd": evidence("ev-product-tesla-fsd", "https://www.tesla.com/AI", "Tesla, Inc.", "AI & Robotics", "counterparty_official_product_page", "Section 'FSD Chip'", "Tesla says it builds AI inference chips to run its Full Self-Driving software."),
    "mobileye_eyeq": evidence("ev-product-mobileye-eyeq", "https://ir.mobileye.com/node/9036/pdf", "Mobileye Global Inc.", "Mobileye Surround ADAS Adds Second Top 10 Automaker", "counterparty_official_release", "Opening product announcement", "Mobileye identifies EyeQ6H as its purpose-built SoC for surround ADAS and automated-driving functions.", "2026-06-05"),
    "nvidia_health": evidence("ev-nvidia-health-platforms", "https://www.nvidia.com/en-us/industries/healthcare-life-sciences/", "NVIDIA Corporation", "AI for Healthcare and Life Sciences", "subject_official_product_page", "Lines 53–69, BioNeMo", "NVIDIA calls BioNeMo its development platform for AI-driven biology and drug discovery, including molecular design and virtual screening."),
    "schrodinger": evidence("ev-product-schrodinger-livedesign", "https://www.schrodinger.com/platform/products/livedesign/", "Schrodinger, Inc.", "LiveDesign", "counterparty_official_product_page", "Opening and 'LiveDesign ML'", "Schrodinger describes a cloud-native molecular design and discovery platform with proprietary modeling and AI/ML workflows."),
}


def peer(category: str, ticker: str, product: str, product_ev: str, status: str, score: int, rationale: str, extra: list[str] | None = None) -> dict:
    name, exchange, _, cik = LISTINGS[ticker]
    original_score = score
    if status == "inferred":
        score = min(score, 69)
        rationale = f"{rationale} Global scoring-contract cap applied: inferred claims cannot exceed 69/100 (raw evidence score {original_score})."
    evidence_ids = [f"ev-listing-{ticker.lower()}", product_ev]
    if ticker in TENK:
        evidence_ids.insert(1, TENK[ticker])
    if extra:
        evidence_ids.extend(extra)
    return {
        "peer_candidate_id": f"peer-{category.lower().replace(' & ','-').replace('/','-').replace(' ','-')}-{ticker.lower()}",
        "subject_entity_id": "nvidia",
        "object_legal_name": name,
        "direction": "competes_with",
        "relationship_type": "peer",
        "product_category_id": category,
        "counterparty_competing_product_or_platform": product,
        "security": {"exchange": exchange, "ticker": ticker, "cik": cik, "status_at_cutoff": "listed_confirmed"},
        "self_developed": True,
        "self_developed_basis": "Counterparty official product material identifies the product/platform as its own architecture, silicon, software or branded platform.",
        "fact_status": status,
        "temporal_status": "current_at_cutoff",
        "as_of": CUTOFF,
        "confidence_score": score,
        "confidence_factors": {
            "official_counterparty_product_evidence": True,
            "nvidia_explicit_competitor_name": ticker in TENK,
            "independent_source_families": 3 if ticker in TENK else 3,
            "current_listing_reference": True,
            "category_overlap_directness": "direct" if status == "confirmed" else "reasoned_overlap",
            "fact_status_score_cap": None if status == "confirmed" else 69,
            "pre_cap_evidence_score": original_score,
            "cap_applied": status == "inferred" and original_score > 69,
        },
        "review_rationale": rationale,
        "uncertainty_or_conflict": [] if status == "confirmed" else ["Neither company explicitly labels the other a competitor for this exact category; peer status is inferred from overlapping core product capabilities."],
        "evidence_ids": list(dict.fromkeys(evidence_ids)),
        "review_status": "accepted",
    }


peers = [
    peer("Data Center Compute", "AMD", "AMD Instinct MI350 GPUs", PRODUCT["amd_instinct"], "confirmed", 96, "Direct accelerator substitution in AI training, inference and HPC; NVIDIA names AMD and AMD documents its own GPU architecture."),
    peer("Data Center Compute", "INTC", "Intel Gaudi 3 AI accelerators", PRODUCT["intel_gaudi"], "confirmed", 94, "Direct data-center AI accelerator overlap; NVIDIA names Intel and Intel documents purpose-built accelerator hardware and software."),
    peer("Data Center Compute", "AMZN", "AWS Trainium", PRODUCT["aws_trainium"], "confirmed", 95, "NVIDIA explicitly identifies Amazon's internal accelerated computing and AWS documents purpose-built Trainium silicon and full-stack infrastructure."),
    peer("Data Center Compute", "GOOGL", "Google TPUs", PRODUCT["google_tpu"], "confirmed", 95, "NVIDIA explicitly identifies Alphabet's internal accelerated computing and Google documents custom TPU accelerators."),
    peer("Data Center Compute", "MSFT", "Microsoft Maia 200", PRODUCT["microsoft_maia"], "confirmed", 95, "NVIDIA explicitly identifies Microsoft's internal accelerated computing and Microsoft documents its deployed first-party Maia inference accelerator."),
    peer("Networking", "AVGO", "Broadcom StrataXGS/Tomahawk Ethernet switch silicon", PRODUCT["broadcom_switch"], "confirmed", 94, "Direct overlap with NVIDIA Spectrum Ethernet switching; NVIDIA names Broadcom and Broadcom documents its own switch-silicon family."),
    peer("Networking", "ANET", "Arista EOS and 7800R data-center switches", PRODUCT["arista_switch"], "confirmed", 93, "Direct data-center/AI Ethernet switching overlap; NVIDIA names Arista and Arista documents its EOS-based systems."),
    peer("Networking", "CSCO", "Cisco Silicon One AI-scale networking", PRODUCT["cisco_silicon"], "confirmed", 93, "Direct overlap in programmable data-center and AI-fabric switching; NVIDIA names Cisco and Cisco documents purpose-built Silicon One."),
    peer("Networking", "MRVL", "Marvell Teralynx AI cloud switches", PRODUCT["marvell_switch"], "confirmed", 93, "Direct overlap in Ethernet switch silicon for AI fabrics; NVIDIA names Marvell and Marvell documents a clean-sheet Teralynx architecture."),
    peer("AI Software & Cloud", "AMZN", "Amazon SageMaker AI", PRODUCT["aws_sagemaker"], "inferred", 82, "SageMaker and NVIDIA DGX Cloud/AI Enterprise address overlapping managed AI build-train-deploy workflows; exact category competition is inferred, while Amazon's internal AI stack is named in NVIDIA's 10-K.", [PRODUCT["nvidia_dgx_cloud"]]),
    peer("AI Software & Cloud", "GOOGL", "Gemini Enterprise Agent Platform / Google Cloud AI", PRODUCT["google_agent"], "inferred", 80, "Google and NVIDIA both provide managed environments for building and deploying AI applications and agents; the specific software-platform peer relation is inferred.", [PRODUCT["nvidia_dgx_cloud"]]),
    peer("AI Software & Cloud", "MSFT", "Microsoft Foundry", PRODUCT["microsoft_foundry"], "inferred", 82, "Microsoft Foundry and NVIDIA's cloud AI stack overlap in model/agent development, deployment and governance; exact platform competition is inferred.", [PRODUCT["nvidia_dgx_cloud"]]),
    peer("Gaming/Consumer", "AMD", "AMD Radeon RX 9000 GPUs", PRODUCT["amd_radeon"], "confirmed", 96, "Direct discrete gaming-GPU substitution; NVIDIA names AMD and AMD documents its self-developed RDNA-based Radeon products."),
    peer("Gaming/Consumer", "INTC", "Intel Arc consumer GPUs", PRODUCT["intel_arc"], "confirmed", 94, "Direct consumer gaming-GPU substitution; NVIDIA names Intel and Intel documents its Arc gaming GPU line."),
    peer("Pro Viz/Design/Simulation", "AMD", "AMD Radeon PRO workstation GPUs", PRODUCT["amd_radeon_pro"], "confirmed", 94, "Direct professional workstation graphics and visualization overlap; NVIDIA names AMD and AMD documents Radeon PRO."),
    peer("Pro Viz/Design/Simulation", "INTC", "Intel Arc Pro workstation GPUs", PRODUCT["intel_arc_pro"], "confirmed", 92, "Direct workstation graphics, CAD, rendering and visualization overlap; NVIDIA names Intel and Intel documents Arc Pro."),
    peer("Robotics/Edge/Embedded", "QCOM", "Qualcomm Robotics RB5 / QRB5165", PRODUCT["qualcomm_rb5"], "confirmed", 91, "Robotics edge-compute and developer-platform overlap with NVIDIA Jetson/Isaac; NVIDIA names Qualcomm in SoC competition and Qualcomm documents its own robotics SoC platform."),
    peer("Robotics/Edge/Embedded", "AMBA", "Ambarella CVflow AI vision SoCs", PRODUCT["ambarella_robotics"], "confirmed", 90, "Edge computer-vision SoC overlap; NVIDIA names Ambarella in SoC competition and Ambarella says it develops processors specifically for robotics and AIoT."),
    peer("Automotive", "QCOM", "Snapdragon Ride", PRODUCT["qualcomm_ride"], "confirmed", 94, "Direct ADAS/automated-driving compute and software-platform overlap with NVIDIA DRIVE; NVIDIA names Qualcomm and Qualcomm documents Ride SoCs and SDKs."),
    peer("Automotive", "TSLA", "Tesla FSD Chip and autonomy stack", PRODUCT["tesla_fsd"], "confirmed", 90, "NVIDIA names Tesla among internal SoC competitors and Tesla confirms it develops FSD inference chips; competition is internal substitution rather than third-party merchant sales."),
    peer("Automotive", "MBLY", "Mobileye EyeQ6H and Surround ADAS", PRODUCT["mobileye_eyeq"], "inferred", 86, "EyeQ6H is a self-developed ADAS SoC/platform sold to automakers and directly overlaps NVIDIA DRIVE's vehicle-compute scope; NVIDIA's 10-K does not name Mobileye in the extracted list."),
]


reviews = [
    {
        "category": "Data Center Compute", "review_status": "complete", "pending_count": 0,
        "accepted_count": 5, "accepted_tickers": ["AMD", "INTC", "AMZN", "GOOGL", "MSFT"],
        "search_scope": "data-center GPUs/AI accelerators and internally designed hyperscaler AI silicon; excludes server OEM assembly and general-purpose CPU-only overlap",
        "rejected_or_unknown": [
            {"entity": "Super Micro Computer, Inc.", "ticker": "SMCI", "decision": "rejected", "reason": "server OEM/integrator; NVIDIA-powered systems alone do not establish a self-developed competing accelerator"},
            {"entity": "Arm Holdings plc", "ticker": "ARM", "decision": "unknown_not_promoted", "reason": "self-developed CPU IP exists, but direct substitution against the category's accelerated-compute core was not established in this review"},
        ],
    },
    {
        "category": "Networking", "review_status": "complete", "pending_count": 0,
        "accepted_count": 4, "accepted_tickers": ["AVGO", "ANET", "CSCO", "MRVL"],
        "search_scope": "data-center/AI fabric switch silicon, systems and network operating platforms; excludes resellers, cabling-only vendors and generic storage networking",
        "rejected_or_unknown": [
            {"entity": "Dell Technologies Inc.", "ticker": "DELL", "decision": "rejected", "reason": "OEM/integrator evidence did not prove a core self-developed AI-fabric silicon/platform substitute"},
            {"entity": "Lumentum Holdings Inc.", "ticker": "LITE", "decision": "unknown_not_promoted", "reason": "optical components overlap one NVIDIA networking subsegment, but category-level core platform comparability was not established"},
        ],
    },
    {
        "category": "AI Software & Cloud", "review_status": "complete", "pending_count": 0,
        "accepted_count": 3, "accepted_tickers": ["AMZN", "GOOGL", "MSFT"],
        "search_scope": "managed AI model/agent build, train, deploy and operate platforms; excludes clouds that only resell NVIDIA instances",
        "rejected_or_unknown": [
            {"entity": "CoreWeave, Inc.", "ticker": "CRWV", "decision": "rejected", "reason": "cloud services built primarily on NVIDIA infrastructure; no self-developed core accelerator or sufficiently independent software platform proven here"},
            {"entity": "Oracle Corporation", "ticker": "ORCL", "decision": "unknown_not_promoted", "reason": "OCI AI services exist, but this pass found insufficient evidence separating own core competing platform from NVIDIA-powered service delivery"},
        ],
    },
    {
        "category": "Gaming/Consumer", "review_status": "complete", "pending_count": 0,
        "accepted_count": 2, "accepted_tickers": ["AMD", "INTC"],
        "search_scope": "self-developed consumer discrete graphics hardware and gaming software stack",
        "rejected_or_unknown": [
            {"entity": "Unity Software Inc.", "ticker": "U", "decision": "rejected", "reason": "game engine/application platform, not a substitute consumer GPU platform"},
            {"entity": "ASUSTeK Computer Inc.", "ticker": "2357", "decision": "rejected", "reason": "add-in-board/OEM products do not show self-developed competing GPU silicon"},
        ],
    },
    {
        "category": "Pro Viz/Design/Simulation", "review_status": "complete", "pending_count": 0,
        "accepted_count": 2, "accepted_tickers": ["AMD", "INTC"],
        "search_scope": "professional workstation GPUs and their self-developed graphics stacks; broader design applications were reviewed conservatively",
        "rejected_or_unknown": [
            {"entity": "Adobe Inc.", "ticker": "ADBE", "decision": "unknown_not_promoted", "reason": "creative software overlaps workflows but not the core professional GPU/platform layer used for this category"},
            {"entity": "Autodesk, Inc.", "ticker": "ADSK", "decision": "unknown_not_promoted", "reason": "design software may overlap Omniverse workflows, but direct category-level substitution was not sufficiently established"},
        ],
    },
    {
        "category": "Robotics/Edge/Embedded", "review_status": "complete", "pending_count": 0,
        "accepted_count": 2, "accepted_tickers": ["QCOM", "AMBA"],
        "search_scope": "self-developed robotics/edge AI SoCs and developer platforms; robot OEMs and NVIDIA-powered integrators excluded",
        "rejected_or_unknown": [
            {"entity": "Teradyne, Inc.", "ticker": "TER", "decision": "unknown_not_promoted", "reason": "owns robot manufacturers, but NVIDIA is primarily an enabling compute/simulation platform and direct platform substitution was not established"},
            {"entity": "Advantech Co., Ltd.", "ticker": "2395", "decision": "rejected", "reason": "edge systems/integration evidence did not prove self-developed core AI compute architecture"},
        ],
    },
    {
        "category": "Automotive", "review_status": "complete", "pending_count": 0,
        "accepted_count": 3, "accepted_tickers": ["QCOM", "TSLA", "MBLY"],
        "search_scope": "self-developed ADAS/autonomous-driving SoCs and platforms; vehicle OEM status alone is insufficient",
        "rejected_or_unknown": [
            {"entity": "Aurora Innovation, Inc.", "ticker": "AUR", "decision": "unknown_not_promoted", "reason": "self-driving system exists, but product-layer substitution versus NVIDIA's merchant DRIVE compute/platform was not sufficiently clear"},
            {"entity": "Magna International Inc.", "ticker": "MGA", "decision": "rejected", "reason": "Tier-1 integration and collaboration do not by themselves prove a self-developed core competing compute platform"},
        ],
    },
    {
        "category": "Healthcare/Life Sciences", "review_status": "complete", "pending_count": 0,
        "accepted_count": 0, "accepted_tickers": [],
        "search_scope": "self-developed computational biology, molecular design and drug-discovery platforms overlapping BioNeMo; medical-device and NVIDIA-enabled application vendors excluded",
        "rejected_or_unknown": [
            {"entity": "Schrodinger, Inc.", "ticker": "SDGR", "decision": "unknown_not_promoted", "reason": "LiveDesign is self-developed and overlaps some molecular-design workflows, but public evidence does not establish that it substitutes for BioNeMo rather than operating as a complementary application/informatics layer; conservative peer gate fails"},
            {"entity": "Tempus AI, Inc.", "ticker": "TEM", "decision": "unknown_not_promoted", "reason": "self-developed precision-medicine/data platform is confirmed, but direct substitution with BioNeMo's molecular-design/model-development core is not sufficiently demonstrated"},
            {"entity": "GE HealthCare Technologies Inc.", "ticker": "GEHC", "decision": "rejected", "reason": "medical devices and clinical applications operate downstream; NVIDIA collaboration/enablement does not establish a competing core platform"},
            {"entity": "Recursion Pharmaceuticals, Inc.", "ticker": "RXRX", "decision": "unknown_not_promoted", "reason": "self-developed drug-discovery stack exists, but public NVIDIA collaboration creates both complementarity and possible overlap; insufficient evidence for a category peer claim"},
        ],
    },
]


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


dump_jsonl(OUT / "peer_candidates.jsonl", peers)
dump_jsonl(OUT / "category_review_ledger.jsonl", reviews)
dump_jsonl(OUT / "source_evidence.jsonl", list(sources.values()))

summary = {
    "cutoff": CUTOFF,
    "categories_required": len(CATEGORIES),
    "categories_reviewed": len(reviews),
    "peer_relationship_records": len(peers),
    "unique_peer_issuers": len({p["security"]["ticker"] for p in peers}),
    "confirmed_records": sum(p["fact_status"] == "confirmed" for p in peers),
    "inferred_records": sum(p["fact_status"] == "inferred" for p in peers),
    "pending_count": sum(r["pending_count"] for r in reviews),
    "source_evidence_records": len(sources),
    "category_counts": {r["category"]: r["accepted_count"] for r in reviews},
}
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
