#!/usr/bin/env python3
"""Build the frozen Data Center + HPC v2 taxonomy fragment.

This script performs no network access.  It serializes the manually reviewed
official-page observations made on 2026-08-25 into deterministic JSON/JSONL.
"""

from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[3]
V1_INDEX = HERE.parents[2] / "2026-08-25-run-002" / "agents" / "product_tree" / "canonical_index.jsonl"
ACCESSED = "2026-08-25T20:00:00+08:00"
ACCESS_NOTE = (
    "Public HTTPS official NVIDIA page; no login, paywall, CAPTCHA, rate-limit, "
    "or access-control bypass. Only short structured observations and locators retained."
)


def write_jsonl(name: str, rows: list[dict]) -> None:
    with (HERE / name).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")


def source(source_id, url, title, discovered_from, locator, status="processed", final_url=None, role="closure_page"):
    return {
        "source_id": source_id,
        "url": url,
        "canonical_url": final_url or url,
        "title": title,
        "publisher": "NVIDIA",
        "seed_id": "DC-SEED" if source_id.startswith("DC") else "HPC-SEED",
        "discovered_from": discovered_from,
        "discovery_locator": locator,
        "scope_role": role,
        "access_status": status,
        "accessed_at": ACCESSED,
        "access_or_license_note": ACCESS_NOTE,
        "pending": False,
    }


SOURCES = [
    source("DC001", "https://www.nvidia.com/en-us/data-center/", "Data Centers for the Era of AI Reasoning", None, "seed", role="seed"),
    source("DC002", "https://www.nvidia.com/en-us/data-center/solutions/accelerated-computing/", "Accelerated Computing for Modern Applications", "DC001", "Overview > NVIDIA accelerated computing; Solutions link"),
    source("DC003", "https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/", "NVIDIA Blackwell Architecture", "DC001", "Full-Stack Data Center Infrastructure > Blackwell"),
    source("DC004", "https://www.nvidia.com/en-us/data-center/grace-cpu/", "NVIDIA Grace CPU and Arm Architecture", "DC001", "Full-Stack Data Center Infrastructure > Grace CPU"),
    source("DC005", "https://www.nvidia.com/en-us/networking/products/data-processing-unit/", "BlueField Networking Platform", "DC001", "Full-Stack Data Center Infrastructure > BlueField DPU"),
    source("DC006", "https://www.nvidia.com/en-us/networking/spectrumx/", "NVIDIA Spectrum-X Ethernet Platform", "DC001", "Full-Stack Data Center Infrastructure > Spectrum-X"),
    source("DC007", "https://www.nvidia.com/en-us/deep-learning-ai/solutions/data-science/", "CUDA-X Data Science Libraries", "DC001", "Workloads > Data Science", "redirected", "https://developer.nvidia.com/topics/ai/data-science/cuda-x-for-data-science"),
    source("DC008", "https://www.nvidia.com/en-us/solutions/ai/inference/", "NVIDIA AI Inference", "DC001", "Workloads > AI Inference"),
    source("DC009", "https://www.nvidia.com/en-us/solutions/ai/generative-ai/", "Agentic AI Solutions", "DC001", "Workloads > Generative AI", "redirected", "https://www.nvidia.com/en-us/solutions/ai/agentic-ai/"),
    source("DC010", "https://www.nvidia.com/en-us/solutions/rendering/", "GPU Rendering Solutions", "DC001", "Workloads > Rendering", "redirected", "https://www.nvidia.com/en-us/products/workstations/rendering/"),
    source("DC011", "https://www.nvidia.com/en-us/data-center/virtualization/it-management/", "Virtual GPU Solutions", "DC001", "Workloads > Virtualization", "redirected", "https://www.nvidia.com/en-us/data-center/virtual-solutions/"),
    source("DC012", "https://www.nvidia.com/en-us/data-center/gpu-cloud-computing/", "Cloud Computing Solutions", "DC001", "Use Cases > From the Cloud"),
    source("DC013", "https://www.nvidia.com/en-us/products/workstations/", "NVIDIA RTX PRO Workstations", "DC001", "Use Cases > To the Office"),
    source("DC014", "https://www.nvidia.com/en-us/edge-computing/", "Edge Computing", "DC001", "Use Cases > To the Edge"),
    source("DC015", "https://resources.nvidia.com/l/en-us-gpu", "NVIDIA Data Center GPU Resource Center", "DC001", "Products > Data Center GPUs", "no_candidate", role="product_index"),
    source("DC016", "https://www.nvidia.com/en-us/data-center/dgx-platform/", "DGX Platform", "DC001", "Products > NVIDIA DGX Platform"),
    source("DC017", "https://www.nvidia.com/en-us/data-center/hgx/", "HGX Platform", "DC001", "Products > NVIDIA HGX Platform"),
    source("DC018", "https://www.nvidia.com/en-us/networking/products/", "NVIDIA Networking Products", "DC001", "Products > Networking Products"),
    source("DC019", "https://www.nvidia.com/en-us/data-center/virtual-solutions/", "NVIDIA Virtual GPUs", "DC001", "Products > Virtual GPUs"),
    source("DC020", "https://www.nvidia.com/en-us/data-center/technologies/hopper-architecture/", "Hopper GPU Architecture", "DC001", "Technologies > Hopper"),
    source("DC021", "https://www.nvidia.com/en-us/data-center/products/mgx/", "NVIDIA MGX", "DC001", "Technologies > MGX"),
    source("DC022", "https://www.nvidia.com/en-us/data-center/solutions/confidential-computing/", "Confidential Computing", "DC001", "Technologies > Confidential Computing"),
    source("DC023", "https://www.nvidia.com/en-us/technologies/multi-instance-gpu/", "Multi-Instance GPU", "DC001", "Technologies > Multi-Instance GPU"),
    source("DC024", "https://www.nvidia.com/en-us/data-center/nvlink-c2c/", "NVLink-C2C", "DC001", "Technologies > NVLink-C2C"),
    source("DC025", "https://www.nvidia.com/en-us/data-center/nvlink/", "NVLink and NVLink Switch", "DC001", "Technologies > NVLink/NVSwitch"),
    source("DC026", "https://www.nvidia.com/en-us/data-center/tensor-cores/", "NVIDIA Tensor Cores", "DC001", "Technologies > Tensor Cores"),
    source("HPC001", "https://www.nvidia.com/en-us/high-performance-computing/", "High-Performance Computing", None, "seed and DC001 Workloads > HPC", role="seed"),
    source("HPC002", "https://www.nvidia.com/en-us/high-performance-computing/hpc-and-ai/", "AI for Science", "HPC001", "Solutions navigation > HPC and AI"),
    source("HPC003", "https://www.nvidia.com/en-us/high-performance-computing/simulation-and-modeling/", "Simulation and Modeling", "HPC001", "Solutions navigation > Simulation and Modeling"),
    source("HPC004", "https://www.nvidia.com/en-us/high-performance-computing/scientific-visualization/", "Scientific Visualization", "HPC001", "Solutions navigation > Scientific Visualization"),
    source("HPC005", "https://www.nvidia.com/en-us/data-center/sustainable-computing/", "Sustainable Computing (legacy link)", "HPC001", "Solutions navigation > Sustainable Computing", "redirected", "https://www.nvidia.com/en-us/sustainability/"),
    source("HPC006", "https://developer.nvidia.com/cuda-toolkit", "CUDA Toolkit", "HPC001", "For Developers > CUDA", "redirected", "https://developer.nvidia.com/cuda/toolkit"),
    source("HPC007", "https://www.nvidia.com/en-us/technologies/cuda-x/", "CUDA-X", "HPC001", "For Developers > CUDA-X"),
    source("HPC008", "https://developer.nvidia.com/hpc-sdk", "NVIDIA HPC SDK", "HPC001", "For Developers > HPC SDK"),
    source("HPC009", "https://www.nvidia.com/en-us/data-center/index-paraview-plugin/", "NVIDIA IndeX for ParaView Plug-in", "HPC001", "For Developers > IndeX ParaView Plugin"),
    source("HPC010", "https://www.nvidia.com/en-us/high-performance-computing/earth-2/", "NVIDIA Earth-2", "HPC001", "Get Started With HPC Solutions > Climate and Weather"),
    source("HPC011", "https://www.nvidia.com/en-us/solutions/cae/", "Computer-Aided Engineering Solutions", "HPC001", "Get Started With HPC Solutions > Computer-Aided Engineering"),
    source("HPC012", "https://developer.nvidia.com/modulus", "NVIDIA PhysicsNeMo", "HPC001", "Get Started With HPC Solutions > Physics-Informed Machine Learning", "redirected", "https://developer.nvidia.com/physicsnemo"),
    source("HPC013", "https://www.nvidia.com/en-us/solutions/quantum-computing/", "NVIDIA Quantum", "HPC001", "Get Started With HPC Solutions > Quantum Computing"),
    source("HPC014", "https://www.nvidia.com/en-us/solutions/quantum-computing/accelerated-quantum-center/", "NVIDIA Accelerated Quantum Research Center", "HPC013", "NVIDIA Quantum > NVAQC"),
    source("HPC015", "https://www.nvidia.com/en-us/solutions/quantum-computing/nvqlink/", "NVIDIA NVQLink", "HPC013", "Solutions > NVIDIA NVQLink"),
    source("HPC016", "https://developer.nvidia.com/cuda-qx", "NVIDIA CUDA-QX", "HPC013", "Solutions > NVIDIA CUDA-QX"),
    source("HPC017", "https://developer.nvidia.com/cuda-q", "NVIDIA CUDA-Q", "HPC013", "Solutions > NVIDIA CUDA-Q"),
    source("HPC018", "https://developer.nvidia.com/cuquantum-sdk", "NVIDIA cuQuantum", "HPC013", "Solutions > NVIDIA cuQuantum"),
]


SECTION_SPECS = {
    "DC001": [
        ("Overview", "lines 51-60", "processed_with_nodes_and_candidates"),
        ("Full-Stack Data Center Infrastructure", "lines 64-97", "processed_with_nodes"),
        ("Workloads", "lines 99-154", "processed_with_nodes"),
        ("Use Cases", "lines 156-186", "processed_with_nodes"),
        ("Resources", "lines 188-206", "processed_no_taxonomy; downstream article agents own article bodies"),
        ("Next Steps", "lines 208-218", "processed_no_taxonomy"),
        ("Products and Technologies navigation", "lines 220-237", "processed_with_links"),
    ],
    "DC002": [("Accelerated system", "H1 through Anatomy", "processed_with_nodes"), ("NVIDIA Accelerated Computing Platforms", "EGX/HGX/DGX/OVX/AGX/IGX cards", "processed_with_nodes_and_candidates"), ("Enterprise use cases", "Get Started cards", "processed_with_edges")],
    "DC003": [("Technological Breakthroughs", "lines 40-85", "processed_with_nodes_and_candidates"), ("NVIDIA Blackwell Products", "lines 88-154", "processed_with_nodes")],
    "DC004": [("CPU architecture and lineup", "H1; Explore the CPU Lineup", "processed_with_nodes")],
    "DC005": [("BlueField portfolio", "H1; product/platform cards", "processed_with_nodes")],
    "DC006": [("Spectrum-X platform", "H1; platform components and use cases", "processed_with_nodes")],
    "DC007": [("CUDA-X data science", "redirect target H1 and library categories", "processed_with_nodes")],
    "DC008": [("Inference platform", "H1; software and infrastructure sections", "processed_with_nodes_and_candidates")],
    "DC009": [("Agentic AI", "redirect target H1; platform/software/use cases", "processed_with_nodes_and_candidates")],
    "DC010": [("Rendering", "redirect target H1; products and workloads", "processed_with_nodes_and_candidates")],
    "DC011": [("Virtualization", "redirect target; product family and workloads", "processed_with_nodes")],
    "DC012": [("Cloud infrastructure", "H1; deployment choices", "processed_with_nodes_and_candidates"), ("Cloud workloads", "AI, data science, industrial digitalization, HPC", "processed_with_edges")],
    "DC013": [("Professional workstations", "H1; product families and use cases", "processed_with_nodes_and_candidates")],
    "DC014": [("Overview and benefits", "lines 41-71", "processed_with_use_cases"), ("Products", "lines 73 onward", "processed_with_nodes")],
    "DC015": [("GPU resource index", "public resource hub; no named current item list in accessible body", "processed_no_candidate")],
    "DC016": [("DGX benefits", "lines 110-126", "processed_with_nodes"), ("Comprehensive AI Platform", "lines 127-150", "processed_with_nodes"), ("AI Across Enterprises", "lines 151 onward", "processed_with_candidates")],
    "DC017": [("HGX platform", "H1 and benefits", "processed_with_nodes"), ("Vera CPU and Networking", "lines 71-79", "processed_with_edges"), ("HGX Specifications", "lines 80 onward", "processed_with_nodes")],
    "DC018": [("Ethernet", "lines 26-31", "processed_with_nodes"), ("InfiniBand", "lines 32-38", "processed_with_nodes")],
    "DC019": [("vGPU products", "product cards", "processed_with_nodes"), ("Workloads", "lines 110-140", "processed_with_nodes")],
    "DC020": [("Hopper architecture", "H1; technology and products", "processed_with_nodes")],
    "DC021": [("MGX reference architecture", "H1; components and systems", "processed_with_nodes_and_candidates")],
    "DC022": [("Confidential Computing", "H1; hardware/software capability sections", "processed_with_nodes")],
    "DC023": [("Multi-Instance GPU", "H1; capabilities and supported workloads", "processed_with_nodes")],
    "DC024": [("NVLink-C2C", "H1; chip interconnect applications", "processed_with_nodes")],
    "DC025": [("NVLink and NVLink Switch", "H1; generations and scale-up", "processed_with_nodes")],
    "DC026": [("Tensor Core workloads", "lines 37-51", "processed_with_nodes"), ("Rubin Tensor Cores", "lines 52-66", "processed_with_nodes"), ("Blackwell Tensor Cores", "lines 67-95", "processed_with_nodes")],
    "HPC001": [("Overview", "lines 148-162", "processed_with_nodes"), ("Get Started With HPC Solutions", "lines 164-198", "processed_with_nodes"), ("Resources and stories", "lines 199-260", "processed_with_candidates; article bodies excluded"), ("Next Steps", "lines 262-269", "processed_no_taxonomy"), ("Products/Solutions/Developer navigation", "lines 20-53 and 335-350", "processed_with_links")],
    "HPC002": [("AI for Science overview", "lines 146-161", "processed_with_nodes"), ("Scientific domains", "lines 163-203", "processed_with_nodes"), ("Industry leaders", "lines 205-208", "processed_no_named_candidate_in_accessible_body")],
    "HPC003": [("Overview and users", "lines 127-147", "processed_with_nodes"), ("Simulation workloads", "lines 148-176", "processed_with_nodes_and_candidates"), ("Blueprint and CAE ecosystem", "lines 177-186", "processed_with_nodes_and_candidates"), ("Simulation in action", "lines 188-216", "processed_with_use_cases")],
    "HPC004": [("Overview and users", "lines 127-147", "processed_with_nodes"), ("Visualization workloads and software", "lines 148-183", "processed_with_nodes"), ("Visualization in action", "lines 184-195", "processed_with_candidates_and_use_cases")],
    "HPC005": [("Redirect decision", "legacy HPC solution URL redirects to Corporate Sustainability", "redirected; alias retained, no separate current solution page")],
    "HPC006": [("CUDA Toolkit", "redirect target H1; toolkit and developer tools", "processed_with_nodes")],
    "HPC007": [("CUDA-X library families", "AI, data processing, math, image/video, communication sections", "processed_with_nodes")],
    "HPC008": [("HPC SDK", "H1; compilers, libraries and tools", "processed_with_nodes")],
    "HPC009": [("IndeX for ParaView", "H1; workstation and cluster editions", "processed_with_nodes")],
    "HPC010": [("Overview", "lines 148-162", "processed_with_nodes"), ("Earth-2 Model Family", "lines 176-203", "processed_with_nodes"), ("Earth2Studio", "lines 205-210", "processed_with_nodes"), ("Partner Ecosystem", "lines 212-252", "processed_with_candidates"), ("Demos/use cases", "lines 254-276", "processed_with_use_cases")],
    "HPC011": [("Overview", "lines 46-59", "processed_with_candidates"), ("Technology", "lines 61-84", "processed_with_nodes"), ("Products/deployment", "lines 86-110", "processed_with_edges"), ("Industries", "lines 112-157", "processed_with_use_cases_and_candidates"), ("Adopters", "lines 159-223", "processed_with_candidates"), ("Resources", "lines 224 onward", "processed_with_candidates; article bodies excluded")],
    "HPC012": [("PhysicsNeMo methods and pipelines", "lines 35-50", "processed_with_nodes"), ("Benefits", "lines 48-99", "processed_with_nodes"), ("Customer Adoption Stories", "lines 100-170", "processed_with_candidates"), ("Use cases and get started", "lines 174-214", "processed_with_use_cases")],
    "HPC013": [("Overview", "lines 50-74", "processed_with_nodes"), ("Solutions", "lines 76-128", "processed_with_nodes"), ("Resources/workloads", "lines 130-151", "processed_with_use_cases"), ("CUDA-Q Academic", "lines 152-205", "processed_with_candidates"), ("Quantum Ecosystem", "lines 206-210", "processed_with_candidate_image_unresolved")],
    "HPC014": [("Overview", "lines 39-57", "processed_with_nodes"), ("Benefits", "lines 59-83", "processed_with_use_cases"), ("Components", "lines 85-112", "processed_with_nodes_and_edges"), ("Partners", "lines 114-124", "processed_with_candidates")],
    "HPC015": [("Overview and CUDA-Q integration", "lines 58-80", "processed_with_nodes_and_candidates"), ("Workloads", "lines 100-117", "processed_with_nodes"), ("Providers/Ecosystem", "lines 146-204", "processed_with_candidates")],
    "HPC016": [("CUDA-QX", "H1; libraries and tools", "processed_with_nodes")],
    "HPC017": [("CUDA-Q", "H1; hybrid quantum-classical platform", "processed_with_nodes")],
    "HPC018": [("cuQuantum SDK", "H1; libraries and appliance", "processed_with_nodes")],
}


PAGE_SECTIONS = []
for src in SOURCES:
    specs = SECTION_SPECS[src["source_id"]]
    for i, (section, locator, outcome) in enumerate(specs, 1):
        PAGE_SECTIONS.append({
            "section_id": f'{src["source_id"]}-SEC-{i:02d}',
            "source_id": src["source_id"],
            "url": src["canonical_url"],
            "section_title": section,
            "evidence_locator": locator,
            "processing_outcome": outcome,
            "accessed_at": ACCESSED,
            "status": "processed",
        })


def node(key, name, node_type, parent, source_id, locator, state="current", aliases=None):
    path = [] if parent is None else parent.split("/")
    return {
        "canonical_key": key,
        "name": name,
        "node_type": node_type,
        "parent_key": path[-1] if path else None,
        "taxonomy_path": path + [key],
        "availability_state": state,
        "aliases": aliases or [],
        "source_id": source_id,
        "source_url": next(s["canonical_url"] for s in SOURCES if s["source_id"] == source_id),
        "evidence_locator": locator,
        "accessed_at": ACCESSED,
        "status": "confirmed" if state != "redirected_alias" else "redirected",
    }


NODES = [
    node("data-center-solutions", "Data Center Solutions", "solution", "solutions", "DC001", "H1 and introduction, lines 20-23"),
    node("accelerated-computing", "Accelerated Computing", "solution", "solutions/data-center-solutions", "DC001", "Unified Platform, lines 51-54"),
    node("blackwell", "Blackwell", "architecture", "architectures", "DC001", "Full-Stack Infrastructure > Blackwell, lines 71-76"),
    node("grace-cpu-architecture", "Grace CPU Architecture", "architecture", "architectures", "DC001", "Full-Stack Infrastructure > Grace CPU, lines 78-83", aliases=["Grace Architecture"]),
    node("bluefield-platform", "BlueField Platform", "platform", "products/networking", "DC001", "Full-Stack Infrastructure > BlueField DPU, lines 85-90"),
    node("spectrum-x", "Spectrum-X", "platform", "products/networking", "DC001", "Full-Stack Infrastructure > Spectrum-X, lines 92-97"),
    node("data-science", "Data Science", "workload", "solutions/data-center-solutions", "DC001", "Workloads > Data Science, lines 102-111"),
    node("inference", "AI Inference", "workload", "solutions/data-center-solutions", "DC001", "Workloads > AI Inference, lines 113-121"),
    node("generative-agentic-ai", "Generative AI", "workload", "solutions/data-center-solutions", "DC001", "Workloads > Generative AI, lines 123-130", aliases=["Generative / Agentic AI"]),
    node("hpc-overview", "High-Performance Computing", "workload", "solutions/data-center-solutions", "DC001", "Workloads > High-Performance Computing, lines 131-138"),
    node("rendering", "Rendering", "workload", "solutions/data-center-solutions", "DC001", "Workloads > Rendering, lines 139-146"),
    node("virtualization", "Virtualization", "workload", "solutions/data-center-solutions", "DC001", "Workloads > Virtualization, lines 147-154"),
    node("cloud-access", "Cloud Access", "use_case", "solutions/data-center-solutions", "DC001", "Use Cases > From the Cloud, lines 159-165"),
    node("office-access", "Office and Professional Desktop Access", "use_case", "solutions/data-center-solutions", "DC001", "Use Cases > To the Office, lines 167-173"),
    node("on-prem-data-center", "On-Premises Data Center", "use_case", "solutions/data-center-solutions", "DC001", "Use Cases > To the Data Center, lines 174-179"),
    node("edge-deployment", "Edge Deployment", "use_case", "solutions/data-center-solutions", "DC001", "Use Cases > To the Edge, lines 181-186"),
    node("space-computing", "Space Computing", "use_case", "solutions/data-center-solutions", "DC001", "Overview > Space Computing announcement, lines 55-57"),
    node("space-1-vera-rubin-module", "Space-1 Vera Rubin Module", "product", "products/edge", "DC001", "Overview > Space Computing announcement, lines 55-57"),
    node("egx-platform", "EGX Platform", "platform", "products/data-center", "DC002", "NVIDIA Accelerated Computing Platforms > EGX"),
    node("hgx-platform", "HGX Platform", "platform", "products/data-center", "DC002", "NVIDIA Accelerated Computing Platforms > HGX"),
    node("dgx-platform", "DGX Platform", "platform", "products/data-center", "DC002", "NVIDIA Accelerated Computing Platforms > DGX"),
    node("ovx-systems", "OVX Systems", "product", "products/data-center", "DC002", "NVIDIA Accelerated Computing Platforms > OVX"),
    node("agx-platform", "AGX Platform", "platform", "products/edge", "DC002", "NVIDIA Accelerated Computing Platforms > AGX"),
    node("igx-platform", "IGX Platform", "platform", "products/edge", "DC002", "NVIDIA Accelerated Computing Platforms > IGX"),
    node("gb300-nvl72", "GB300 NVL72", "product", "products/data-center", "DC003", "Blackwell Products, lines 90-96"),
    node("gb200-nvl72", "GB200 NVL72", "product", "products/data-center", "DC003", "Blackwell Products, lines 141-147"),
    node("gb200-nvl4", "GB200 NVL4", "product", "products/data-center", "DC003", "Blackwell Products, lines 149-154"),
    node("dgx-superpod", "DGX SuperPOD", "product", "products/data-center/dgx-platform", "DC003", "Blackwell Products, lines 98-103"),
    node("dgx-station", "DGX Station", "product", "products/data-center/dgx-platform", "DC003", "Blackwell Products, lines 119-124"),
    node("dgx-spark", "DGX Spark", "product", "products/data-center/dgx-platform", "DC003", "Blackwell Products, lines 126-132"),
    node("hgx-b300", "HGX B300", "product", "products/data-center/hgx-platform", "DC003", "Blackwell Products, lines 134-139"),
    node("cuda-x-data-science", "CUDA-X Data Science", "software", "software/cuda-x", "DC007", "Redirect target H1 and library portfolio"),
    node("cloud-computing", "GPU Cloud Computing", "solution", "solutions/data-center-solutions", "DC012", "H1 and cloud deployment overview"),
    node("rapids", "RAPIDS", "sdk", "software/cuda-x", "DC012", "Accelerated Data Science, lines 118-124"),
    node("omniverse-cloud", "Omniverse Cloud", "service", "services/cloud", "DC012", "Industrial Digitalization, lines 126-130"),
    node("rtx-virtual-workstation", "RTX Virtual Workstation", "software", "software/virtual-gpu", "DC019", "vGPU product card, lines 98-102", aliases=["RTX vWS"]),
    node("virtual-pc", "Virtual PC", "software", "software/virtual-gpu", "DC019", "vGPU product card, lines 104-108", aliases=["vPC"]),
    node("virtual-applications", "Virtual Applications", "software", "software/virtual-gpu", "DC019", "vGPU product card, lines 104-108", aliases=["vApps"]),
    node("virtual-ai-development", "Virtual AI Development", "workload", "solutions/virtualization", "DC019", "Workloads > AI Development, lines 115-124"),
    node("virtual-design-engineering", "Virtual Design and Engineering", "workload", "solutions/virtualization", "DC019", "Workloads > Design and Engineering, lines 127-131"),
    node("virtual-productivity-apps", "Virtual Productivity Applications", "workload", "solutions/virtualization", "DC019", "Workloads > Productivity Apps, lines 134-138"),
    node("confidential-computing", "Confidential Computing", "technology", "technologies/data-center", "DC022", "H1 and capability overview"),
    node("multi-instance-gpu", "Multi-Instance GPU", "technology", "technologies/data-center", "DC023", "H1 and capabilities"),
    node("nvlink-c2c", "NVLink-C2C", "technology", "technologies/data-center", "DC024", "H1 and chip-interconnect overview"),
    node("nvlink", "NVLink", "technology", "technologies/data-center", "DC025", "H1 and scale-up overview"),
    node("nvlink-switch", "NVLink Switch", "technology", "technologies/data-center", "DC025", "H1 and scale-up overview"),
    node("tensor-cores", "Tensor Cores", "technology", "technologies/data-center", "DC026", "H1 and introduction, lines 18-21"),
    node("rubin-tensor-cores", "Rubin Tensor Cores", "technology", "technologies/tensor-cores", "DC026", "Rubin Tensor Cores, lines 52-66"),
    node("blackwell-tensor-cores", "Blackwell Tensor Cores", "technology", "technologies/tensor-cores", "DC026", "Blackwell Tensor Cores, lines 67-85"),
    node("hpc-and-ai", "AI for Science", "solution", "solutions/high-performance-computing", "HPC002", "H1 and Overview, lines 127-151", aliases=["HPC and AI"]),
    node("life-sciences-domain", "Life Sciences", "use_case", "solutions/high-performance-computing/ai-for-science", "HPC002", "Scientific Domains > Life Sciences, lines 169-174"),
    node("atmospheric-science-domain", "Atmospheric Science", "use_case", "solutions/high-performance-computing/ai-for-science", "HPC002", "Scientific Domains > Atmospheric Science, lines 176-182"),
    node("computational-engineering-domain", "Computational Engineering", "use_case", "solutions/high-performance-computing/ai-for-science", "HPC002", "Scientific Domains > Computational Engineering, lines 184-189"),
    node("chemistry-materials-domain", "Chemistry and Materials Science", "use_case", "solutions/high-performance-computing/ai-for-science", "HPC002", "Scientific Domains > Chemistry and Materials Science, lines 191-196"),
    node("ai-physics-domain", "AI Physics", "use_case", "solutions/high-performance-computing/ai-for-science", "HPC002", "Scientific Domains > AI Physics, lines 198-203"),
    node("simulation-and-modeling", "Simulation and Modeling", "solution", "solutions/high-performance-computing", "HPC003", "H1 and overview, lines 127-131"),
    node("molecular-dynamics-simulation", "Molecular Dynamics Simulation", "workload", "solutions/high-performance-computing/simulation-and-modeling", "HPC003", "GROMACS/LAMMPS/NAMD cards, lines 151-166"),
    node("weather-climate-simulation", "Weather and Climate Simulation", "workload", "solutions/high-performance-computing/simulation-and-modeling", "HPC003", "Simulation in Action > Predict Weather Patterns"),
    node("financial-modeling", "Financial Modeling", "workload", "solutions/high-performance-computing/simulation-and-modeling", "HPC003", "Simulation in Action > Accelerate Financial Models"),
    node("engineering-simulation", "Engineering Simulation", "workload", "solutions/high-performance-computing/simulation-and-modeling", "HPC003", "Simulation in Action > Speed Up Engineering Simulations"),
    node("earth-2-weather-analytics-blueprint", "Omniverse Blueprint for Earth-2 Weather Analytics", "reference_architecture", "solutions/high-performance-computing/simulation-and-modeling", "HPC003", "Develop AI-Powered Weather Analysis, lines 177-180"),
    node("scientific-visualization", "Scientific Visualization", "solution", "solutions/high-performance-computing", "HPC004", "H1 and overview, lines 127-131"),
    node("index", "NVIDIA IndeX", "software", "software/visualization", "HPC004", "Visualization workloads > NVIDIA IndeX, lines 151-155"),
    node("neuralvdb", "NeuralVDB", "software", "software/visualization", "HPC004", "Visualization workloads > NeuralVDB, lines 167-170"),
    node("sustainable-computing", "Sustainable Computing", "solution", "solutions/high-performance-computing", "HPC005", "Legacy navigation link redirects to Corporate Sustainability", "redirected_alias"),
    node("cuda-toolkit", "CUDA Toolkit", "sdk", "software/cuda", "HPC006", "Redirect target H1 and toolkit sections"),
    node("cuda-x", "CUDA-X", "technology", "software/cuda", "HPC007", "H1 and library-family sections"),
    node("nccl", "NCCL", "software", "software/cuda-x", "HPC007", "Communication Libraries, lines 109-115"),
    node("nvshmem", "NVSHMEM", "software", "software/cuda-x", "HPC007", "Communication Libraries, lines 110-114"),
    node("nixl", "NIXL", "software", "software/cuda-x", "HPC007", "Communication Libraries, lines 110-115", aliases=["NVIDIA Inference Transfer Library"]),
    node("hpc-sdk", "HPC SDK", "sdk", "software/hpc", "HPC008", "H1; compilers, libraries, tools"),
    node("index-paraview-plugin", "IndeX for ParaView Plug-in", "software", "software/visualization", "HPC009", "Workstation and Cluster editions, lines 96-110"),
    node("earth-2", "Earth-2", "platform", "solutions/high-performance-computing", "HPC010", "H1 and Overview, lines 125-152"),
    node("earth-2-medium-range", "Earth-2 Medium Range", "software", "software/earth-2", "HPC010", "Earth-2 Model Family, lines 180-184", aliases=["Atlas architecture"]),
    node("earth-2-nowcasting", "Earth-2 Nowcasting", "software", "software/earth-2", "HPC010", "Earth-2 Model Family, lines 185-188", aliases=["StormScope"]),
    node("earth-2-global-data-assimilation", "Earth-2 Global Data Assimilation", "software", "software/earth-2", "HPC010", "Earth-2 Model Family, lines 190-193", aliases=["HealDA"]),
    node("earth-2-corrdiff", "Earth-2 CorrDiff", "software", "software/earth-2", "HPC010", "Earth-2 Model Family, lines 195-198"),
    node("earth-2-fourcastnet-3", "Earth-2 FourCastNet 3", "software", "software/earth-2", "HPC010", "Earth-2 Model Family, lines 200-203"),
    node("earth2studio", "Earth2Studio", "software", "software/earth-2", "HPC010", "Get Started, lines 205-210"),
    node("earth-2-visualization-service", "Earth-2 Visualization Service", "service", "services/earth-2", "HPC010", "Earth-2 Goes Down to Street Level, lines 259-264"),
    node("weather-forecasting", "Weather Forecasting", "use_case", "solutions/high-performance-computing/earth-2", "HPC010", "Earth-2 Model Family, lines 176-203"),
    node("urban-weather-digital-twin", "Urban Weather Digital Twin", "use_case", "solutions/high-performance-computing/earth-2", "HPC010", "Earth-2 Goes Down to Street Level, lines 259-264"),
    node("carbon-capture-storage-modeling", "Carbon Capture and Storage Modeling", "use_case", "solutions/high-performance-computing/earth-2", "HPC010", "Earth-2 demo, lines 273-276"),
    node("computer-aided-engineering", "Computer-Aided Engineering", "solution", "solutions/high-performance-computing", "HPC011", "H1 and Overview, lines 46-49", aliases=["CAE"]),
    node("warp", "Warp", "sdk", "software/cae", "HPC011", "Technology > Accelerate, lines 67-70"),
    node("nemoclaw-blueprint", "NemoClaw Blueprint", "reference_architecture", "solutions/computer-aided-engineering", "HPC011", "Technology > AI Engineering, lines 73-76"),
    node("physicsnemo", "PhysicsNeMo", "framework", "software/ai-physics", "HPC012", "H1; methods and reference pipelines, lines 35-50"),
    node("physics-ai-reference-pipelines", "Physics AI Reference Pipelines", "reference_architecture", "software/physicsnemo", "HPC012", "Reference Pipelines, lines 43-45"),
    node("quantum-computing", "Quantum Computing", "solution", "solutions/high-performance-computing", "HPC013", "H1 and overview, lines 20-53", aliases=["NVIDIA Quantum"]),
    node("nvqlink", "NVQLink", "architecture", "technologies/quantum", "HPC015", "H1 and reference platform overview, lines 20-60"),
    node("cuda-qx", "CUDA-QX", "sdk", "software/quantum", "HPC016", "H1 and library/tool overview"),
    node("cuda-q", "CUDA-Q", "platform", "software/quantum", "HPC017", "H1 and hybrid quantum-classical platform overview"),
    node("cuquantum", "cuQuantum", "sdk", "software/quantum", "HPC018", "H1 and SDK library portfolio"),
    node("cuquantum-appliance", "cuQuantum Appliance", "software", "software/quantum", "HPC013", "Solutions > cuQuantum Appliance, lines 106-108"),
    node("cupqc", "cuPQC", "software", "software/quantum", "HPC013", "Solutions > NVIDIA cuPQC, lines 114-121"),
    node("quantum-cloud", "NVIDIA Quantum Cloud", "service", "services/quantum", "HPC013", "Solutions > NVIDIA Quantum Cloud, lines 122-128"),
    node("nvaqc", "NVIDIA Accelerated Quantum Research Center", "platform", "solutions/quantum-computing", "HPC014", "H1 and Overview, lines 20-42", aliases=["NVAQC"]),
    node("ising", "NVIDIA Ising", "software", "software/quantum", "HPC013", "Overview and FAQ portfolio, lines 56-60 and 255-263"),
    node("qpu-calibration", "QPU Calibration", "workload", "solutions/quantum-computing/nvqlink", "HPC015", "Workloads > QPU Calibration, lines 100-107"),
    node("qec-decoding", "QEC Decoding", "workload", "solutions/quantum-computing/nvqlink", "HPC015", "Workloads > QEC Decoding, lines 109-113"),
    node("logical-orchestration", "Logical Orchestration", "workload", "solutions/quantum-computing/nvqlink", "HPC015", "Workloads > Logical Orchestration, lines 114-117"),
]


EDGE_PAIRS = {
    "data-center-solutions": ["accelerated-computing", "blackwell", "grace-cpu-architecture", "bluefield-platform", "spectrum-x", "dgx-platform", "hgx-platform", "virtualization"],
    "space-computing": ["space-1-vera-rubin-module", "igx-thor", "jetson-agx-orin-series"],
    "accelerated-computing": ["egx-platform", "hgx-platform", "dgx-platform", "ovx-systems", "agx-platform", "igx-platform", "cuda-x", "virtual-gpu"],
    "data-science": ["cuda-x-data-science", "rapids", "dgx-platform"],
    "inference": ["blackwell", "dgx-platform", "nixl"],
    "generative-agentic-ai": ["blackwell", "dgx-platform", "cuda-x"],
    "rendering": ["rtx-virtual-workstation", "omniverse-cloud"],
    "virtualization": ["rtx-virtual-workstation", "virtual-pc", "virtual-applications"],
    "cloud-computing": ["dgx-platform", "cuda-x", "rapids", "omniverse-cloud"],
    "hpc-and-ai": ["blackwell", "grace-cpu-architecture", "dgx-platform", "hgx-platform", "cuda-x", "hpc-sdk", "physicsnemo", "earth-2"],
    "simulation-and-modeling": ["hpc-sdk", "cuda-x", "physicsnemo", "earth-2-weather-analytics-blueprint", "blackwell"],
    "scientific-visualization": ["index", "index-paraview-plugin", "neuralvdb", "omniverse-cloud", "physicsnemo", "hpc-sdk"],
    "earth-2": ["earth-2-medium-range", "earth-2-nowcasting", "earth-2-global-data-assimilation", "earth-2-corrdiff", "earth-2-fourcastnet-3", "earth2studio", "earth-2-visualization-service", "physicsnemo", "omniverse-cloud"],
    "computer-aided-engineering": ["blackwell", "gh200-grace-hopper-superchip", "cuda-x", "warp", "nemoclaw-blueprint", "physicsnemo", "omniverse-cloud"],
    "physicsnemo": ["dgx-platform", "ngc-catalog", "nim-microservices", "omniverse-cloud"],
    "quantum-computing": ["nvqlink", "cuda-qx", "cuda-q", "cuquantum", "cuquantum-appliance", "cupqc", "quantum-cloud", "nvaqc", "ising", "dgx-quantum", "gb200-nvl72"],
    "nvaqc": ["dgx-quantum", "gb200-nvl72", "cuda-q"],
    "nvqlink": ["cuda-q", "qpu-calibration", "qec-decoding", "logical-orchestration"],
}


NODE_BY_KEY = {n["canonical_key"]: n for n in NODES}
EDGES = []
for solution_key, targets in EDGE_PAIRS.items():
    src = NODE_BY_KEY[solution_key]
    for target in targets:
        target_node = NODE_BY_KEY.get(target)
        if target_node:
            target_type = target_node["node_type"]
            evidence_source = target_node["source_id"]
            locator = target_node["evidence_locator"]
        else:
            target_type = "v1_canonical_reference"
            evidence_source = src["source_id"]
            locator = f"{src['evidence_locator']}; target retained from v1 canonical index"
        if target_type in {"software", "sdk", "framework"}:
            edge_type = "uses_software"
        elif target_type in {"workload", "use_case"}:
            edge_type = "supports_workload"
        elif target_type in {"architecture", "technology", "reference_architecture"}:
            edge_type = "uses_technology"
        else:
            edge_type = "uses_product_or_platform"
        EDGES.append({
            "from_key": solution_key,
            "to_key": target,
            "edge_type": edge_type,
            "mapping_status": "confirmed",
            "source_id": evidence_source,
            "evidence_locator": locator,
            "accessed_at": ACCESSED,
            "status": "current",
        })


def candidate(name, kind, source_id, locator, products, method="text", context="relationship candidate only; classification deferred"):
    return {
        "candidate_name_raw": name,
        "entity_kind_hint": kind,
        "source_id": source_id,
        "source_url": next(s["canonical_url"] for s in SOURCES if s["source_id"] == source_id),
        "evidence_locator": locator,
        "observation_method": method,
        "product_context_keys": products,
        "relationship_status": "unclassified_candidate",
        "context_note": context,
        "accessed_at": ACCESSED,
    }


CANDIDATES = []
for name, kind in [("AetherFlux", "private_company"), ("Kepler Communications", "private_company"), ("Planet Labs", "public_company"), ("Sophia Space", "private_company"), ("Starcloud", "private_company")]:
    CANDIDATES.append(candidate(name, kind, "DC001", "Overview > Space Computing announcement, lines 55-57", ["accelerated-computing", "space-1-vera-rubin-module", "igx-thor", "jetson-agx-orin-series"], context="Page says these organizations are using NVIDIA accelerated-computing platforms for orbital and ground missions; downstream agent must verify entity and role."))
for name, kind in [("Microsoft", "public_company"), ("CoreWeave", "public_company"), ("Oracle", "public_company")]:
    CANDIDATES.append(candidate(name, kind, "DC002", "Blackwell Ultra deployment paragraph, lines 82-85", ["gb300-nvl72", "blackwell", "nvlink", "dynamo"], context="Page says cloud providers are deploying GB300 NVL72 systems; candidate customer/partner classification deferred."))
for name in ["Lockheed Martin", "Sony", "BMW", "Shell"]:
    CANDIDATES.append(candidate(name, "public_company", "DC016", "AI Across Enterprises customer tabs, lines 151 onward", ["dgx-platform", "dgx-superpod"], method="customer_story", context="Named DGX adoption/customer-story candidate; downstream relationship classification required."))
for name in ["Applied Materials", "Samsung", "Synopsys", "TSMC"]:
    CANDIDATES.append(candidate(name, "public_company", "HPC001", "HPC resource tile: cuEST / semiconductor design, lines 221-235", ["cuda-x", "hpc-overview"], context="Named in a dynamic resource tile; article body is owned by the News/Blog agents."))
for name, kind in [("Los Alamos National Laboratory", "government_research"), ("Jülich Supercomputing Centre", "public_research")]:
    CANDIDATES.append(candidate(name, kind, "HPC001", "HPC resource/customer tile, lines 221-255", ["hpc-overview", "grace-cpu-architecture"], context="Research-institution adoption candidate; not assumed to be a listed company."))
for name in ["Ansys", "Altair", "Cadence", "Siemens", "Synopsys"]:
    CANDIDATES.append(candidate(name, "public_company", "HPC003", "Blackwell Accelerates CAE Software Ecosystem, lines 181-186", ["simulation-and-modeling", "blackwell", "cuda-x"], context="Page says CAE vendors are accelerating tools on Blackwell; partner candidate only."))
for name, kind in [("NOAA", "government"), ("Lockheed Martin", "public_company"), ("University of Wisconsin", "university")]:
    CANDIDATES.append(candidate(name, kind, "HPC004", "Accelerated Scientific Visualization in Action, lines 184-195", ["scientific-visualization", "omniverse-cloud"], method="customer_story"))

earth_names = [
    ("Allen Institute for AI (Ai2)", "nonprofit_research"), ("Barcelona Supercomputing Center", "public_research"),
    ("Berkeley Lab", "government_research"), ("CSCS", "public_research"), ("Leap", "unresolved"),
    ("Max Planck Institute for Meteorology", "nonprofit_research"), ("UC Irvine", "university"),
    ("NOAA", "government"), ("University of Washington", "university"), ("Meteomatics", "private_company"),
    ("Spire", "public_company"), ("The Weather Company", "private_company"), ("ClimaSens", "private_company"),
    ("North.io", "private_company"), ("RSS-Hydro", "private_company"), ("Tomorrow.io", "private_company"),
]
for name, kind in earth_names:
    CANDIDATES.append(candidate(name, kind, "HPC010", "Partner Ecosystem logo grid, lines 212-252", ["earth-2"], method="logo", context="Logo is under a tabbed Collaborators/Customers/Inception Partners section; flattened public DOM does not preserve per-logo tab membership, so exact role remains unknown."))

cae_isv = ["Autodesk", "Beyond Math", "Cadence", "COMSOL", "Dassault Systèmes", "ENGYS", "Flexcompute", "Keysight Technologies", "Luminary Cloud", "Neural Concept", "nTop", "PhysicsX", "PTC", "Siemens", "SimScale", "Synopsys", "Trane Technologies", "Volcano Platforms"]
cae_cloud = ["Amazon Web Services", "Google Cloud", "Microsoft", "Oracle", "Rescale"]
cae_hardware = ["BOXX Technologies", "Dell Technologies", "Hewlett Packard Enterprise", "Lenovo", "Supermicro", "HP"]
for name in cae_isv:
    CANDIDATES.append(candidate(name, "company", "HPC011", "Adopters > Industry Software Providers logo grid, lines 159-201", ["computer-aided-engineering", "cuda-x", "physicsnemo", "omniverse-cloud"], method="logo", context="Industry Software Provider adopter; listing status and final role deferred."))
for name in cae_cloud:
    CANDIDATES.append(candidate(name, "company", "HPC011", "Adopters > Cloud Service Providers logo grid, lines 203-211", ["computer-aided-engineering", "cloud-computing"], method="logo", context="Cloud Service Provider adopter; final role deferred."))
for name in cae_hardware:
    CANDIDATES.append(candidate(name, "company", "HPC011", "Adopters > Hardware Partners logo grid, lines 213-223", ["computer-aided-engineering", "blackwell"], method="logo", context="Explicit Hardware Partner section; final listed-entity mapping deferred."))
for name in ["Ansys", "Rescale", "Siemens Gamesa", "TSMC", "KLA"]:
    CANDIDATES.append(candidate(name, "company", "HPC011", "Industry/use-case image caption or resource story, lines 123-157 and 234-248", ["computer-aided-engineering", "blackwell", "cuda-x"], method="caption", context="Named in page caption/story; article-body corroboration deferred."))

physics_customers = [
    ("Ansys", "public_company"), ("Luminary Cloud", "private_company"), ("nTop", "private_company"),
    ("Foxconn", "public_company"), ("TSMC", "public_company"), ("Wistron", "public_company"),
    ("SimScale", "private_company"), ("AXA", "public_company"), ("G42", "private_company"),
    ("Siemens Energy", "public_company"), ("Rescale", "private_company"), ("BRLi", "private_company"),
    ("Toulouse INP", "university"), ("Stone Ridge Technology", "private_company"),
    ("Amazon Web Services", "public_company_business_unit"), ("Shell", "public_company"),
]
for name, kind in physics_customers:
    CANDIDATES.append(candidate(name, kind, "HPC012", "Customer Adoption Stories, lines 100-170", ["physicsnemo", "earth-2", "omniverse-cloud"], method="customer_story", context="Named adoption/customer-story candidate; exact product subset is preserved in the story but final role remains for downstream classification."))

academic = ["Arizona State University", "Carnegie Mellon University", "Chung Yuan Christian University", "Dartmouth College", "ETH Zurich", "Fordham University", "IIT Madras", "KAUST", "Mälardalen University", "Northwestern University", "Pittsburgh Supercomputing Center", "Polytechnic University of Valencia", "Princeton University", "Purdue University", "Robert Morris University", "Technical University of Munich", "Technion", "UC Davis", "University of Cambridge", "University of Chicago", "University of Florida", "University of Illinois Urbana-Champaign", "University of Nevada Reno", "University of Pittsburgh", "UPC BarcelonaTech"]
for name in academic:
    CANDIDATES.append(candidate(name, "university_or_research", "HPC013", "CUDA-Q Academic logo grid, lines 152-205", ["cuda-q"], method="logo", context="Academic-program participant, retained as a non-company candidate for entity filtering."))
for name, kind in [("Engineering Quantum Systems at MIT (EQuS)", "university_research"), ("Quantinuum", "private_company"), ("Quantum Machines", "private_company"), ("QuEra", "private_company")]:
    CANDIDATES.append(candidate(name, kind, "HPC014", "NVAQC Partners and Ecosystem, lines 114-124", ["nvaqc", "dgx-quantum", "cuda-q"], method="logo", context="Explicit NVAQC partner/ecosystem candidate."))

nvqlink_ecosystem = ["Alice & Bob", "Anyon Technologies", "Atom Computing", "Dell Technologies", "Diraq", "Equal1", "IonQ", "IQM Quantum Computers", "Infleqtion", "Keysight Technologies", "ORCA Computing", "Pasqal", "Oxford Quantum Circuits", "Qblox", "QubiC", "Quantinuum", "Quandela", "Quantum Circuits", "Quantum Machines", "Quantum Motion", "QuEL", "QuEra", "Rigetti Computing", "SEEQC", "QICK", "SDT", "Silicon Quantum Computing", "Wistron", "Zurich Instruments"]
for name in nvqlink_ecosystem:
    CANDIDATES.append(candidate(name, "company_or_project", "HPC015", "NVQLink Ecosystem logo grid, lines 146-204", ["nvqlink", "cuda-q"], method="logo", context="Explicit NVQLink ecosystem candidate; listed-company and parent mapping deferred."))


def main() -> None:
    v1 = {}
    if V1_INDEX.exists():
        with V1_INDEX.open(encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                v1[row["canonical_key"]] = row

    for row in NODES:
        old = v1.get(row["canonical_key"])
        row["merge_action"] = "augment_existing" if old else "add"
        if old:
            row["v1_primary_name"] = old["primary_name"]
            row["v1_primary_type"] = old["primary_type"]
            row["type_conflict_with_v1"] = old["primary_type"] != row["node_type"]
        else:
            row["type_conflict_with_v1"] = False

    conflicts = []
    for row in NODES:
        if row.get("type_conflict_with_v1"):
            conflicts.append({
                "canonical_key": row["canonical_key"],
                "v1_type": row["v1_primary_type"],
                "v2_observed_type": row["node_type"],
                "resolution": "preserve both observations; root merger applies global type precedence and context-specific path",
                "evidence_source_id": row["source_id"],
                "evidence_locator": row["evidence_locator"],
            })
    conflicts.extend([
        {
            "canonical_key": "hpc-and-ai",
            "v1_name": "HPC and AI",
            "v2_name": "AI for Science",
            "resolution": "AI for Science is current page H1; keep HPC and AI as navigation alias",
            "evidence_source_id": "HPC002",
            "evidence_locator": "H1 and navigation, lines 28-33 and 126-151",
        },
        {
            "canonical_key": "sustainable-computing",
            "issue": "legacy HPC solution link now redirects to corporate sustainability",
            "resolution": "retain redirected alias but do not model a current standalone product/solution page",
            "evidence_source_id": "HPC005",
            "evidence_locator": "HTTP redirect and target H1 Corporate Sustainability",
        },
        {
            "canonical_key": "gb200-nvl72",
            "issue": "NVAQC component body contains 'GB200 NVL2' while heading/link and quantum overview identify GB200 NVL72",
            "resolution": "treat NVL2 as page copy error; canonicalize to GB200 NVL72 and retain conflict note",
            "evidence_source_id": "HPC014",
            "evidence_locator": "Components, lines 99-104; compare Overview line 41 and linked product",
        },
    ])

    merge_patch = {
        "fragment": "v2_dc_hpc",
        "base_snapshot": str(V1_INDEX.relative_to(REPO_ROOT)),
        "research_cutoff": "2026-08-25",
        "generated_at": ACCESSED,
        "add_keys": sorted(n["canonical_key"] for n in NODES if n["merge_action"] == "add"),
        "augment_existing_keys": sorted(n["canonical_key"] for n in NODES if n["merge_action"] == "augment_existing"),
        "aliases_to_add": {n["canonical_key"]: n["aliases"] for n in NODES if n["aliases"]},
        "conflicts": conflicts,
        "merge_rules": [
            "Never overwrite v1 evidence; append v2 evidence observations.",
            "Canonical identity is by canonical_key, not by tree path.",
            "A node may appear under both product and solution contexts while remaining one canonical object.",
            "Redirected aliases remain provenance records but do not prove current standalone availability.",
        ],
    }

    required_source = {"source_id", "url", "canonical_url", "access_status", "accessed_at", "pending"}
    required_node = {"canonical_key", "name", "node_type", "source_id", "source_url", "evidence_locator", "accessed_at", "status"}
    required_edge = {"from_key", "to_key", "edge_type", "source_id", "evidence_locator", "accessed_at", "status"}
    required_candidate = {"candidate_name_raw", "source_id", "source_url", "evidence_locator", "product_context_keys", "relationship_status", "accessed_at"}
    pending = [s["source_id"] for s in SOURCES if s["pending"]]
    bad_sources = [s.get("source_id") for s in SOURCES if not required_source.issubset(s)]
    bad_nodes = [n.get("canonical_key") for n in NODES if not required_node.issubset(n) or any(n[k] in (None, "") for k in required_node)]
    bad_edges = [f'{e.get("from_key")}->{e.get("to_key")}' for e in EDGES if not required_edge.issubset(e) or any(e[k] in (None, "") for k in required_edge)]
    source_ids = {s["source_id"] for s in SOURCES}
    canonical_keys = set(v1) | {n["canonical_key"] for n in NODES}
    dangling_edges = [f'{e["from_key"]}->{e["to_key"]}' for e in EDGES if e["from_key"] not in canonical_keys or e["to_key"] not in canonical_keys]
    duplicate_source_ids = sorted({s["source_id"] for s in SOURCES if sum(x["source_id"] == s["source_id"] for x in SOURCES) > 1})
    duplicate_node_keys = sorted({n["canonical_key"] for n in NODES if sum(x["canonical_key"] == n["canonical_key"] for x in NODES) > 1})
    bad_section_refs = [p["section_id"] for p in PAGE_SECTIONS if p["source_id"] not in source_ids or p["status"] != "processed"]
    bad_candidate_refs = [c.get("candidate_name_raw") for c in CANDIDATES if c.get("source_id") not in source_ids or not required_candidate.issubset(c) or any(c[k] in (None, "") for k in required_candidate)]
    bad_candidate_product_refs = sorted({key for c in CANDIDATES for key in c["product_context_keys"] if key not in canonical_keys})

    report = {
        "fragment": "v2_dc_hpc",
        "research_cutoff": "2026-08-25",
        "generated_at": ACCESSED,
        "counts": {
            "seed_pages": 2,
            "frontier_records": len(SOURCES),
            "frontier_processed": sum(s["access_status"] == "processed" for s in SOURCES),
            "frontier_redirected": sum(s["access_status"] == "redirected" for s in SOURCES),
            "frontier_no_candidate": sum(s["access_status"] == "no_candidate" for s in SOURCES),
            "page_sections": len(PAGE_SECTIONS),
            "taxonomy_nodes": len(NODES),
            "nodes_added": sum(n["merge_action"] == "add" for n in NODES),
            "nodes_augmented": sum(n["merge_action"] == "augment_existing" for n in NODES),
            "solution_product_edges": len(EDGES),
            "relation_candidate_observations": len(CANDIDATES),
            "merge_conflicts_logged": len(conflicts),
        },
        "errors": {
            "pending_sources": pending,
            "sources_missing_required_fields": bad_sources,
            "nodes_missing_required_fields": bad_nodes,
            "edges_missing_required_fields": bad_edges,
            "dangling_edges": dangling_edges,
            "duplicate_source_ids": duplicate_source_ids,
            "duplicate_node_keys": duplicate_node_keys,
            "bad_page_section_refs": bad_section_refs,
            "bad_candidate_refs": bad_candidate_refs,
            "bad_candidate_product_refs": bad_candidate_product_refs,
        },
        "gates": {
            "two_seeds_processed": len([s for s in SOURCES if s["scope_role"] == "seed" and not s["pending"]]) == 2,
            "zero_pending_frontier": not pending,
            "all_frontier_records_valid": not bad_sources,
            "all_page_sections_processed": not bad_section_refs,
            "all_nodes_traceable": not bad_nodes,
            "all_edges_traceable": not bad_edges and not dangling_edges,
            "all_candidates_traceable": not bad_candidate_refs and not bad_candidate_product_refs,
            "identifiers_unique": not duplicate_source_ids and not duplicate_node_keys,
        },
        "scope_notes": [
            "Closure is limited to Product, Solution, Technology, Workload, and Use Case links explicitly presented by the two seeds and reviewed family/item pages.",
            "Header/footer repetition, forms, training, catalogs, events, news/blog article bodies, gated documents, and generic corporate/industry navigation are outside this fragment.",
            "Dynamic tab markup can flatten logo-to-tab membership; those observations remain unclassified rather than guessed.",
            "This is an incremental fragment for the root v2 merger, not a standalone claim that all seven secondary sites are complete.",
        ],
    }
    report["overall_status"] = "pass" if all(report["gates"].values()) else "fail"

    write_jsonl("source_frontier.jsonl", SOURCES)
    write_jsonl("page_sections.jsonl", PAGE_SECTIONS)
    write_jsonl("taxonomy_nodes.jsonl", NODES)
    write_jsonl("solution_product_edges.jsonl", EDGES)
    write_jsonl("relation_candidates.jsonl", CANDIDATES)
    (HERE / "merge_patch.json").write_text(json.dumps(merge_patch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["overall_status"] != "pass":
        raise SystemExit(json.dumps(report["errors"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
