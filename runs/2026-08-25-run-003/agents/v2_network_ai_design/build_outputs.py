#!/usr/bin/env python3
"""Build the frozen v2 taxonomy patch for Networking, AI, and Design/Simulation.

This script performs no network requests.  It serializes the manually reviewed
official-page observations captured at the 2026-08-25 research cutoff.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


OUT = Path(__file__).resolve().parent
ACCESSED = "2026-08-25T20:30:00+08:00"
PUBLISHER = "NVIDIA"
ACCESS_NOTE = (
    "Public HTTPS; no login, paywall, captcha, access-control, or rate-limit bypass. "
    "Page is dynamic and JavaScript-enhanced; only publicly rendered content was reviewed."
)


def src(source_id, url, title, branch, discovered_from, sections, *, status="reviewed", note=None, redirect_from=None):
    return {
        "source_id": source_id,
        "url": url,
        "title": title,
        "publisher": PUBLISHER,
        "branch": branch,
        "discovered_from": discovered_from,
        "is_seed": discovered_from is None,
        "accessed_at": ACCESSED,
        "access_status": status,
        "closure_decision": "excluded_robots" if status == "excluded_robots" else "processed",
        "redirect_from": redirect_from,
        "sections": sections,
        "access_or_license_note": note or ACCESS_NOTE,
    }


SOURCES = [
    src("NAD001", "https://www.nvidia.com/en-us/networking/", "Networking Solutions for the Era of AI", "networking", None,
        ["Introduction", "Technology", "Benefits", "News", "Resources"]),
    src("NAD002", "https://www.nvidia.com/en-us/solutions/ai/", "AI Solutions for Enterprises", "ai", None,
        ["Overview", "Solutions", "Resources: use cases", "Resources: customer stories", "By Role", "Next Steps"]),
    src("NAD003", "https://www.nvidia.com/en-us/solutions/design-and-simulation/", "Design and Simulation Solutions", "design_simulation", None,
        ["Overview", "Solutions", "Use Cases", "Resources: customer stories", "Resources: training", "Next Steps"]),
    src("NAD004", "https://www.nvidia.com/en-us/data-center/nvlink/", "NVIDIA NVLink and NVLink Switch", "networking", "NAD001",
        ["Introduction", "NVLink", "NVLink Switch", "NVLink Fusion", "Specifications"]),
    src("NAD005", "https://www.nvidia.com/en-us/networking/spectrumx/", "NVIDIA Spectrum-X Ethernet Networking Platform", "networking", "NAD001",
        ["Introduction", "Benefits", "Products", "Applications", "Partners", "Resources"]),
    src("NAD006", "https://www.nvidia.com/en-us/networking/products/data-processing-unit/", "NVIDIA BlueField Platform", "networking", "NAD001",
        ["Overview", "Portfolio", "Benefits", "Use Cases", "Technology", "Partner Ecosystem", "Next Step"]),
    src("NAD007", "https://developer.nvidia.com/networking/doca", "DOCA Software Framework", "networking", "NAD001",
        ["Platform and Host Deployments", "BlueField Software Bundle", "SDK Key Components", "Developer Resources"]),
    src("NAD008", "https://www.nvidia.com/en-us/networking/products/silicon-photonics/", "NVIDIA Silicon Photonics", "networking", "NAD001",
        ["Introduction", "Offerings", "Benefits", "Products", "Technology Partners", "Resources", "Next Steps"]),
    src("NAD009", "https://www.nvidia.com/en-us/networking/products/ethernet/", "NVIDIA Spectrum Ethernet Platform", "networking", "NAD001",
        ["Introduction", "Products", "Capabilities", "Partners", "Resources", "Next Steps"]),
    src("NAD010", "https://www.nvidia.com/en-us/networking/ethernet-switching/air/", "NVIDIA DSX Air Platform", "networking", "NAD001",
        ["Overview", "Video", "Technology", "Benefits", "Use Cases", "Ecosystem", "Resources", "Next Steps"]),
    src("NAD011", "https://www.nvidia.com/en-us/networking/products/infiniband/", "NVIDIA Quantum InfiniBand Platform", "networking", "NAD001",
        ["Introduction", "Products", "Capabilities", "Software", "Resources", "Next Steps"]),
    src("NAD012", "https://www.nvidia.com/en-us/networking/products/infiniband/quantum-x800/", "NVIDIA Quantum-X800 InfiniBand Platform", "networking", "NAD001",
        ["Introduction", "Key Benefits", "Platform Components", "Resources", "Next Steps"]),
    src("NAD013", "https://www.nvidia.com/en-us/networking/infiniband-switching/", "NVIDIA Quantum InfiniBand Switches and Appliances", "networking", "NAD001",
        ["Overview", "Benefits", "Products", "Innovations", "Resources", "FAQs", "Next Steps"]),
    src("NAD014", "https://www.nvidia.com/en-us/networking/products/software/", "NVIDIA Networking Software", "networking", "NAD001",
        ["Overview", "Products", "Release Versions", "Validated Configurations", "Next Steps"]),
    src("NAD015", "https://www.nvidia.com/en-us/solutions/ai/agentic-ai/", "Agentic AI Solutions", "ai", "NAD002",
        ["Overview", "Demos", "Benefits", "Technology", "Use Cases", "Customer Stories", "Resources", "Next Steps"]),
    src("NAD016", "https://www.nvidia.com/en-us/deep-learning-ai/solutions/data-science/", "NVIDIA-Accelerated Data Science", "ai", "NAD002",
        ["Features", "Solutions", "RAPIDS", "Partner Ecosystem", "Webinars"]),
    src("NAD017", "https://www.nvidia.com/en-us/solutions/ai/inference/", "NVIDIA AI Inference", "ai", "NAD002",
        ["Overview", "Performance", "TCO", "Benefits", "Platform", "Customer Stories", "Resources", "Next Steps"]),
    src("NAD018", "https://www.nvidia.com/en-us/solutions/ai/conversational-ai/", "Conversational AI Applications", "ai", "NAD002",
        ["Overview", "Benefits", "Software", "Use Cases", "Customer Stories", "Adopters", "Resources", "Next Steps"]),
    src("NAD019", "https://www.nvidia.com/en-us/autonomous-machines/intelligent-video-analytics-platform/", "NVIDIA Metropolis", "ai", "NAD002",
        ["Overview", "Benefits", "Use Cases", "Starting Options", "Success Stories", "Partners", "Supported Platforms", "Next Steps"]),
    src("NAD020", "https://www.nvidia.com/en-us/solutions/ai/cybersecurity/", "AI Cybersecurity Solutions", "ai", "NAD002",
        ["Overview", "Benefits", "Technology", "Use Cases", "Adopters", "Next Steps"]),
    src("NAD021", "https://www.nvidia.com/en-us/use-cases/synthetic-data-generation-for-agentic-ai/", "Synthetic Data Generation for Agentic AI", "ai", "NAD002",
        ["Metadata", "Overview", "Technical Implementation", "Get Started", "Related Use Cases"]),
    src("NAD022", "https://www.nvidia.com/en-us/use-cases/content-creation-using-generative-ai/", "Accelerating Content Generation", "ai_design", "NAD002",
        ["Metadata", "Overview", "Technical Implementation", "FAQs", "Get Started", "Related Use Cases"],
        redirect_from="https://www.nvidia.com/en-us/use-cases/3d-product-configurator/"),
    src("NAD023", "https://www.nvidia.com/en-us/use-cases/biomolecular-foundation-models-for-discovery-in-life-science/", "Biomolecular Foundation Models for Discovery in Life Science", "ai", "NAD002",
        ["Metadata", "Biomolecular AI Model Training", "Protein Foundation Models", "Molecular Generation"],
        redirect_from="https://www.nvidia.com/en-us/use-cases/generative-ai-for-virtual-screening/"),
    src("NAD024", "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/", "NVIDIA AI Enterprise", "ai", "NAD002",
        ["Overview", "Benefits", "Reference Architectures", "Production-Ready AI", "Use Cases", "Customer Stories", "Starting Options", "Resources", "Next Steps"]),
    src("NAD025", "https://www.nvidia.com/en-us/glossary/digital-twin/", "What Is a Digital Twin?", "design_simulation", "NAD003",
        ["How It Works", "Evolution", "Benefits", "Necessary Skills", "Use Cases", "Next Steps"],
        redirect_from="https://www.nvidia.com/en-us/omniverse/solutions/digital-twins/"),
    src("NAD026", "https://www.nvidia.com/en-us/solutions/cae/", "Computer-Aided Engineering Solutions", "design_simulation", "NAD003",
        ["Overview", "Technology", "Products", "Industries", "Adopters", "Resources", "Next Steps"]),
    src("NAD027", "https://www.nvidia.com/en-us/products/workstations/rendering/", "Advanced Rendering Solutions", "design_simulation", "NAD003",
        ["Overview", "RTX Technology", "RTX Solutions", "Resources", "Applications", "Tools", "Find a Partner"],
        redirect_from="https://www.nvidia.com/en-us/design-visualization/solutions/rendering/"),
    src("NAD028", "https://www.nvidia.com/en-us/industries/robotics/", "Robotics Industry Solutions", "design_simulation", "NAD003",
        ["Overview", "Use Cases", "Technology", "Products", "Ecosystem"],
        redirect_from="https://www.nvidia.com/en-us/solutions/robotics-and-edge-computing/"),
    src("NAD029", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/simulation/", "Simulation and Validation for Robotaxis and Autonomous Vehicles", "design_simulation", "NAD003",
        ["Overview", "Benefits", "Technology", "Use Cases", "Partners", "Resources", "Next Steps"],
        redirect_from="https://www.nvidia.com/en-us/use-cases/autonomous-vehicle-simulation/"),
    src("NAD030", "https://www.nvidia.com/en-us/design-visualization/solutions/virtual-reality/", "Extended Reality Solutions", "design_simulation", "NAD003",
        ["Overview", "Technologies", "News", "Resources"]),
    src("NAD031", "https://www.nvidia.com/en-us/use-cases/industrial-facility-digital-twins/", "Industrial Facility Digital Twins", "design_simulation", "NAD003",
        ["Metadata", "Overview", "Technical Implementation", "Partner Ecosystem", "FAQs", "Get Started", "Resources"],
        redirect_from="https://www.nvidia.com/en-us/use-cases/ai-for-virtual-factory-solutions/"),
    src("NAD032", "https://www.nvidia.com/en-us/use-cases/robot-learning/", "Robot Learning", "design_simulation", "NAD003",
        ["Metadata", "Overview", "Technical Implementation", "Get Started", "Related Use Cases"],
        redirect_from="https://www.nvidia.com/en-us/use-cases/reinforcement-learning/"),
    src("NAD033", "https://www.nvidia.com/en-us/use-cases/synthetic-data-physical-ai/", "Synthetic Data Generation for Physical AI", "design_simulation", "NAD003",
        ["Metadata", "Overview", "Technical Implementation", "Get Started", "Related Use Cases"],
        redirect_from="https://www.nvidia.com/en-us/use-cases/synthetic-data/"),
    src("NAD034", "https://www.nvidia.com/en-us/use-cases/robotics-simulation/", "Robotics Simulation", "design_simulation", "NAD003",
        ["Metadata", "Overview", "Technical Implementation", "Get Started", "FAQs", "News", "Related Use Cases"]),
    src("NAD035", "https://www.nvidia.com/en-us/use-cases/humanoid-robots/", "Humanoid Robots", "design_simulation", "NAD003",
        ["Metadata", "Overview", "Technical Implementation", "Ecosystem", "Get Started", "News", "Resources"]),
    src("NAD036", "https://www.nvidia.com/en-us/use-cases/video-analytics-ai-agents/", "Video Analytics AI Agents", "design_simulation", "NAD003",
        ["Metadata", "Overview", "Technical Implementation", "FAQs", "Get Started", "Resources", "Deploy AI Agents", "Customer Stories"],
        redirect_from="https://www.nvidia.com/en-us/use-cases/visual-ai-agents/"),
    src("NAD037", "https://developer.nvidia.com/industries/telecommunications/ai-aerial", "NVIDIA AI Aerial", "design_simulation", "NAD003",
        ["AI Aerial Software", "Hardware Platforms", "Ecosystem", "Resources"],
        redirect_from="https://developer.nvidia.com/aerial-omniverse-digital-twin"),
    src("NAD038", "https://www.nvidia.com/en-us/use-cases/?page=1&products=NeMo,NIM,DGX", "Filtered Use Cases Listing", "ai", "NAD002", [],
        status="excluded_robots",
        note="Not fetched or used: NVIDIA robots.txt disallows URLs containing the page parameter. The unparameterized individual use-case pages explicitly linked by the seed were processed instead."),
]


def node(node_id, name, node_type, parent_id, source_id, locator, branch, *, notes=None):
    row = {
        "node_id": node_id,
        "canonical_key": node_id.replace(".", "-"),
        "name": name,
        "node_type": node_type,
        "parent_id": parent_id,
        "branch": branch,
        "availability_state": "current_at_cutoff",
        "evidence": {
            "source_id": source_id,
            "evidence_locator": locator,
            "accessed_at": ACCESSED,
        },
    }
    if notes:
        row["notes"] = notes
    return row


NODES = []


def add_group(parent, source_id, branch, locator, items):
    for item in items:
        if len(item) == 3:
            nid, name, typ = item
            notes = None
        else:
            nid, name, typ, notes = item
        NODES.append(node(nid, name, typ, parent, source_id, locator, branch, notes=notes))


# Roots and page-level solution families.
NODES.extend([
    node("v2.networking", "Networking", "solution", None, "NAD001", "H1 and Introduction, lines 18-46", "networking"),
    node("v2.ai", "AI Solutions", "solution", None, "NAD002", "H2 The Most Advanced AI and Solutions, lines 20-115", "ai"),
    node("v2.design", "Design and Simulation", "solution", None, "NAD003", "H1 and Solutions, lines 20-112", "design_simulation"),
])

add_group("v2.networking", "NAD001", "networking", "Introduction and Technology, lines 43-102", [
    ("v2.networking.scale_up", "Scale-Up Networking", "solution"),
    ("v2.networking.scale_out", "Scale-Out Networking", "solution"),
    ("v2.networking.scale_across", "Scale-Across Networking", "solution"),
    ("v2.networking.nvlink", "NVLink", "technology"),
    ("v2.networking.quantum", "Quantum InfiniBand", "platform"),
    ("v2.networking.spectrum_x", "Spectrum-X Ethernet", "platform"),
    ("v2.networking.spectrum_xgs", "Spectrum-XGS Ethernet", "technology"),
    ("v2.networking.bluefield", "BlueField", "platform"),
    ("v2.networking.doca", "DOCA", "software"),
    ("v2.networking.silicon_photonics", "Silicon Photonics", "technology"),
    ("v2.networking.dsx_air", "DSX Air", "platform"),
])
add_group("v2.networking.nvlink", "NAD004", "networking", "NVLink sections and specifications, lines 38-99", [
    ("v2.networking.nvlink.gen6", "Sixth-Generation NVLink", "technology"),
    ("v2.networking.nvlink.switch", "NVLink Switch", "product"),
    ("v2.networking.nvlink.fusion", "NVLink Fusion", "technology"),
    ("v2.networking.nvlink.sharp", "SHARP", "technology"),
])
add_group("v2.networking.spectrum_x", "NAD005", "networking", "Products and Applications, lines 47-163", [
    ("v2.networking.spectrum_x.multiplane", "Spectrum-X Multiplane", "technology"),
    ("v2.networking.spectrum_x.switch", "Spectrum-X Ethernet Switch", "product"),
    ("v2.networking.spectrum_x.supernic", "Spectrum-X Ethernet SuperNIC", "product"),
    ("v2.networking.spectrum_x.sn5000", "Spectrum SN5000", "product"),
    ("v2.networking.spectrum_x.sn6000", "Spectrum SN6000", "product"),
    ("v2.networking.spectrum_x.ai_compute_fabric", "AI Compute Fabrics", "workload"),
    ("v2.networking.spectrum_x.ai_storage", "AI Storage", "workload"),
])
add_group("v2.networking.bluefield", "NAD006", "networking", "Portfolio, lines 70-89", [
    ("v2.networking.bluefield.4_dpu", "BlueField-4 DPU", "product"),
    ("v2.networking.bluefield.4_stx", "BlueField-4 STX Storage Processor", "product"),
    ("v2.networking.bluefield.3_dpu", "BlueField-3 DPU", "product"),
])
add_group("v2.networking.bluefield", "NAD006", "networking", "Use Cases, lines 115-158", [
    ("v2.networking.bluefield.cloud_scale_ai", "Cloud-Scale AI", "use_case"),
    ("v2.networking.bluefield.enterprise_ai_factory", "Enterprise AI Factory", "use_case"),
    ("v2.networking.bluefield.ai_storage", "Accelerated AI Storage", "use_case"),
    ("v2.networking.bluefield.cybersecurity", "Cybersecurity Infrastructure", "use_case"),
    ("v2.networking.bluefield.elastic_infrastructure", "Elastic AI Infrastructure", "use_case"),
    ("v2.networking.bluefield.edge_security", "Edge and OT Security", "use_case"),
])
add_group("v2.networking.doca", "NAD007", "networking", "Page sections, lines 7-87", [
    ("v2.networking.doca.runtime", "DOCA Runtime", "software"),
    ("v2.networking.doca.sdk", "DOCA SDK", "software"),
    ("v2.networking.doca.host", "DOCA-Host", "software"),
    ("v2.networking.doca.rdma_sdk", "DOCA RDMA SDK", "software"),
    ("v2.networking.doca.network_sdk", "DOCA Network Acceleration SDK", "software"),
    ("v2.networking.doca.security_sdk", "DOCA Security Acceleration SDK", "software"),
    ("v2.networking.doca.storage_sdk", "DOCA Storage Acceleration SDK", "software"),
    ("v2.networking.doca.dpa_sdk", "DOCA DPA SDK", "software"),
    ("v2.networking.doca.management_sdk", "DOCA Management SDK", "software"),
])
add_group("v2.networking.silicon_photonics", "NAD008", "networking", "Offerings and Products, lines 79-144", [
    ("v2.networking.silicon_photonics.quantum_x", "Quantum-X InfiniBand Photonics", "architecture"),
    ("v2.networking.silicon_photonics.spectrum_x", "Spectrum-X Ethernet Photonics", "architecture"),
    ("v2.networking.silicon_photonics.q3450_ld", "Quantum-X Q3450-LD Photonics Switch", "product"),
    ("v2.networking.silicon_photonics.spectrum_switches", "Spectrum-X Ethernet Photonics Switches", "product"),
])
add_group("v2.networking", "NAD009", "networking", "Products, lines 65-107", [
    ("v2.networking.spectrum_ethernet", "Spectrum Ethernet Platform", "platform"),
    ("v2.networking.spectrum_ethernet.switches", "Spectrum Ethernet Switch Systems", "product"),
    ("v2.networking.ethernet_supernic", "Ethernet SuperNICs", "product"),
    ("v2.networking.connectx_nic", "ConnectX NICs", "product"),
    ("v2.networking.linkx", "LinkX Cables and Transceivers", "product"),
])
add_group("v2.networking.dsx_air", "NAD010", "networking", "Technology, Benefits and Use Cases, lines 86-159", [
    ("v2.networking.dsx_air.simulate", "AI Factory Infrastructure Simulation", "use_case"),
    ("v2.networking.dsx_air.day_zero", "Day-Zero Development", "use_case"),
    ("v2.networking.dsx_air.integration", "Software Integration", "use_case"),
    ("v2.networking.dsx_air.training", "Training and Skills Transfer", "use_case"),
    ("v2.networking.dsx_air.cicd", "CI/CD Validation and Automation", "use_case"),
])
add_group("v2.networking.quantum", "NAD011", "networking", "Products, Capabilities and Software, lines 60-145", [
    ("v2.networking.quantum.adapters", "InfiniBand Adapters", "product"),
    ("v2.networking.quantum.switches", "InfiniBand Switches", "product"),
    ("v2.networking.quantum.routers", "Routers and Gateway Systems", "product"),
    ("v2.networking.quantum.long_haul", "MetroX Long-Haul Systems", "product"),
    ("v2.networking.quantum.mlnx_ofed", "MLNX_OFED", "software"),
    ("v2.networking.quantum.hpc_x", "HPC-X", "software"),
])
add_group("v2.networking.quantum", "NAD012", "networking", "Platform Components, lines 63-90", [
    ("v2.networking.quantum.x800", "Quantum-X800", "platform"),
    ("v2.networking.quantum.x800_switch", "Quantum-X800 InfiniBand Switch", "product"),
    ("v2.networking.quantum.connectx8", "ConnectX-8 SuperNIC", "product"),
    ("v2.networking.quantum.connectx9", "ConnectX-9 SuperNIC", "product"),
])
add_group("v2.networking.quantum.switches", "NAD013", "networking", "Products and Innovations, lines 86-140", [
    ("v2.networking.quantum.quantum2", "Quantum-2 InfiniBand", "platform"),
    ("v2.networking.quantum.qm9700", "Quantum-2 QM9700", "product"),
    ("v2.networking.quantum.skyway", "Skyway InfiniBand-to-Ethernet Gateway", "product"),
    ("v2.networking.quantum.metrox3", "MetroX-3 XC", "product"),
    ("v2.networking.quantum.nvos", "NVOS", "software"),
    ("v2.networking.quantum.ufm", "Unified Fabric Manager", "platform"),
])
add_group("v2.networking", "NAD014", "networking", "Key Networking Software Offerings, lines 54-109", [
    ("v2.networking.software", "Networking Software", "software"),
    ("v2.networking.netq", "NetQ", "software"),
    ("v2.networking.cumulus", "Cumulus Linux", "software"),
    ("v2.networking.pure_sonic", "Pure SONiC", "software"),
    ("v2.networking.infiniband_drivers", "InfiniBand Software and Drivers", "software"),
    ("v2.networking.ethernet_drivers", "Ethernet Software and Drivers", "software"),
])

# AI solutions and named family/item boundary.
add_group("v2.ai", "NAD002", "ai", "Solutions, lines 58-115", [
    ("v2.ai.agentic", "Agentic AI", "solution"),
    ("v2.ai.data_science", "Data Science", "solution"),
    ("v2.ai.inference", "Inference", "solution"),
    ("v2.ai.conversational", "Conversational AI", "solution"),
    ("v2.ai.vision", "Vision AI", "solution"),
    ("v2.ai.cybersecurity", "Cybersecurity AI", "solution"),
])
add_group("v2.ai", "NAD002", "ai", "Resources > Use Cases, lines 121-154", [
    ("v2.ai.uc.sdg_agentic", "Synthetic Data Generation for Agentic AI", "use_case"),
    ("v2.ai.uc.content_generation", "Content Generation", "use_case"),
    ("v2.ai.uc.biomolecular_generation", "Biomolecular Generation", "use_case"),
])
add_group("v2.ai.agentic", "NAD015", "ai", "Technology, lines 146-181", [
    ("v2.ai.agentic.agent_toolkit", "NVIDIA Agent Toolkit", "platform"),
    ("v2.ai.nemotron", "Nemotron", "model_family"),
    ("v2.ai.cosmos", "Cosmos", "model_family"),
    ("v2.ai.nim", "NIM Microservices", "software"),
    ("v2.ai.agentic.ai_q", "AI-Q", "software"),
    ("v2.ai.nemo_agent_tools", "NeMo Agent Tools", "software"),
    ("v2.ai.nemoclaw", "NemoClaw", "reference_architecture"),
    ("v2.ai.agentic.openshell", "OpenShell", "software"),
    ("v2.ai.agentic.metropolis_vss", "Metropolis VSS Blueprint", "reference_architecture"),
])
add_group("v2.ai.agentic", "NAD015", "ai", "Use Cases, lines 183-237", [
    ("v2.ai.agentic.uc.eda", "Autonomous EDA Engineer", "use_case"),
    ("v2.ai.agentic.uc.video", "Video Analytics Agents", "use_case"),
    ("v2.ai.agentic.uc.it_desk", "IT Service Desk Agent", "use_case"),
    ("v2.ai.agentic.uc.health", "Health and Life Science Agents", "use_case"),
    ("v2.ai.agentic.uc.cyber", "Cyber Defense Agent", "use_case"),
])
add_group("v2.ai.data_science", "NAD016", "ai", "Features and RAPIDS, lines 37-165", [
    ("v2.ai.rapids", "RAPIDS", "software"),
    ("v2.ai.rapids.cudf", "cuDF", "software"),
    ("v2.ai.rapids.cugraph", "cuGraph", "software"),
    ("v2.ai.rapids.spark", "RAPIDS Accelerator for Apache Spark", "software"),
    ("v2.ai.rapids.xgboost", "GPU-Accelerated XGBoost", "software"),
])
add_group("v2.ai.inference", "NAD017", "ai", "Platform, lines 120-152", [
    ("v2.ai.inference.vera_rubin_nvl72", "Vera Rubin NVL72", "platform"),
    ("v2.ai.inference.gb300_nvl72", "Grace Blackwell Ultra GB300 NVL72", "platform"),
    ("v2.ai.inference.dynamo", "Dynamo", "software"),
    ("v2.ai.inference.tensorrt_llm", "TensorRT-LLM", "software"),
    ("v2.ai.inference.triton", "Triton Inference Server", "software"),
    ("v2.ai.inference.tensorrt", "TensorRT", "software"),
])
add_group("v2.ai.conversational", "NAD018", "ai", "Software and Use Cases, lines 85-169", [
    ("v2.ai.conversational.riva", "Riva", "software"),
    ("v2.ai.conversational.riva_magpie", "Riva Magpie TTS NIM", "software"),
    ("v2.ai.conversational.canary", "Canary Speech Model", "model"),
    ("v2.ai.conversational.parakeet", "Parakeet Speech Model", "model"),
    ("v2.ai.conversational.blueprints", "Conversational AI Blueprints", "reference_architecture"),
    ("v2.ai.conversational.uc.health", "Healthcare Agents", "use_case"),
    ("v2.ai.conversational.uc.assistant", "AI Virtual Assistant", "use_case"),
    ("v2.ai.conversational.uc.agent_assist", "Agent Assist", "use_case"),
    ("v2.ai.conversational.uc.translation", "AI Translation", "use_case"),
    ("v2.ai.conversational.uc.physical", "Physical AI Voice Interfaces", "use_case"),
])
add_group("v2.ai.vision", "NAD019", "ai", "Overview, Use Cases and Supported Platforms, lines 50-140 and 283-307", [
    ("v2.ai.metropolis", "Metropolis", "platform"),
    ("v2.ai.tao", "TAO Toolkit", "software"),
    ("v2.ai.deepstream", "DeepStream", "software"),
    ("v2.ai.vision.uc.video_agents", "Video Analytics AI Agents", "use_case"),
    ("v2.ai.vision.uc.visual_inspection", "Automated Visual Inspection", "use_case"),
    ("v2.ai.vision.uc.transport", "Intelligent Transportation Systems", "use_case"),
    ("v2.ai.vision.uc.industrial", "Industrial Automation", "use_case"),
    ("v2.ai.vision.uc.retail", "Intelligent Retail Stores", "use_case"),
    ("v2.ai.vision.uc.robot_safety", "Robot Safety", "use_case"),
])
add_group("v2.ai.cybersecurity", "NAD020", "ai", "Technology and Use Cases, lines 83-186", [
    ("v2.ai.confidential_computing", "Confidential Computing", "solution"),
    ("v2.ai.morpheus", "Morpheus", "software"),
    ("v2.ai.cybersecurity.uc.vulnerability", "Vulnerability Analysis", "use_case"),
    ("v2.ai.cybersecurity.uc.anomaly", "Anomaly Detection", "use_case"),
    ("v2.ai.cybersecurity.uc.leakage", "Data Leakage Prevention", "use_case"),
    ("v2.ai.cybersecurity.uc.phishing", "Spear Phishing Detection", "use_case"),
    ("v2.ai.cybersecurity.uc.zero_trust", "Zero-Trust Architecture", "use_case"),
    ("v2.ai.cybersecurity.uc.secure_agents", "Securing Enterprise AI Agents", "use_case"),
])
add_group("v2.ai", "NAD024", "ai", "Overview through Use Cases, lines 57-198", [
    ("v2.ai.ai_enterprise", "AI Enterprise", "software"),
    ("v2.ai.enterprise_factory", "Enterprise AI Factory", "reference_architecture"),
    ("v2.ai.data_platform", "AI Data Platform for Enterprise", "reference_architecture"),
    ("v2.ai.nemo", "NeMo", "platform"),
    ("v2.ai.omniverse", "Omniverse", "platform"),
    ("v2.ai.run_ai", "Run:ai", "software"),
    ("v2.ai.blueprints", "NVIDIA Blueprints", "reference_architecture"),
    ("v2.ai.blueprints.rag", "Enterprise RAG Blueprint", "reference_architecture"),
    ("v2.ai.blueprints.research", "Enterprise Research AI Agent Blueprint", "reference_architecture"),
    ("v2.ai.blueprints.vss", "Video Analytics AI Agent Blueprint", "reference_architecture"),
    ("v2.ai.blueprints.multi_robot", "Multi-Robot Fleet Blueprint", "reference_architecture"),
    ("v2.ai.blueprints.realtime_sim", "Real-Time Simulation Blueprint", "reference_architecture"),
])
add_group("v2.ai.uc.sdg_agentic", "NAD021", "ai", "Metadata, lines 38-54", [
    ("v2.ai.workload.generative_llm", "Generative AI and LLMs", "workload"),
    ("v2.ai.workload.conversational_nlp", "Conversational AI and NLP", "workload"),
])
add_group("v2.ai.uc.biomolecular_generation", "NAD023", "ai", "Metadata, lines 21-45", [
    ("v2.ai.workload.structural_biology", "Structural Biology", "workload"),
    ("v2.ai.workload.molecular_design", "Molecular Design", "workload"),
    ("v2.ai.workload.molecular_simulation", "Molecular Simulation", "workload"),
    ("v2.ai.workload.biomedical_imaging", "Biomedical Imaging", "workload"),
    ("v2.ai.bionemo", "BioNeMo", "platform"),
    ("v2.ai.monai", "MONAI", "software"),
])

# Design and simulation workflows, use cases, technologies, and direct child pages.
add_group("v2.design", "NAD003", "design_simulation", "Solutions, lines 62-112", [
    ("v2.design.cae", "Computer-Aided Engineering", "solution"),
    ("v2.design.digital_twin", "Digital Twin Development", "solution"),
    ("v2.design.rendering", "Rendering and Visualization", "solution"),
    ("v2.design.robotics_edge", "Robotics and Edge Computing", "solution"),
    ("v2.design.vehicle_sim", "Vehicle Simulation", "solution"),
    ("v2.design.xr", "Virtual and Augmented Reality", "solution"),
])
add_group("v2.design", "NAD003", "design_simulation", "Use Cases, lines 114-207", [
    ("v2.design.uc.facility_twin", "Industrial Facility Digital Twin", "use_case"),
    ("v2.design.uc.configurator", "Product Configurators", "use_case"),
    ("v2.design.uc.robot_learning", "Robot Learning", "use_case"),
    ("v2.design.uc.synthetic_data", "Synthetic Data Generation for Physical AI", "use_case"),
    ("v2.design.uc.robot_sim", "Robotics Simulation", "use_case"),
    ("v2.design.uc.humanoid", "Humanoid Development", "use_case"),
    ("v2.design.uc.av_sim", "Autonomous Vehicle Simulation", "use_case"),
    ("v2.design.uc.video_agents", "Intelligent Video Analytics", "use_case"),
    ("v2.design.uc.network_sim", "Wireless Network Simulation", "use_case"),
])
add_group("v2.design.digital_twin", "NAD025", "design_simulation", "Use Cases, lines 119-233", [
    ("v2.design.digital_twin.product_development", "Product Development", "use_case"),
    ("v2.design.digital_twin.architecture", "Architectural Design and Simulation", "use_case"),
    ("v2.design.digital_twin.remote_ops", "Remote Monitoring of Industrial Operations", "use_case"),
    ("v2.design.digital_twin.autonomous_testing", "Autonomous System Testing and Validation", "use_case"),
    ("v2.design.digital_twin.inspection", "Optical Inspection and Defect Detection", "use_case"),
    ("v2.design.digital_twin.ai_factory", "Data Center and AI Factory Optimization", "use_case"),
    ("v2.design.digital_twin.surgery", "Digital Surgery", "use_case"),
    ("v2.design.digital_twin.smart_city", "Smart City Planning and Operations", "use_case"),
    ("v2.design.digital_twin.wireless", "Wireless Network Simulation", "use_case"),
    ("v2.design.digital_twin.climate", "Climate Simulation and Energy Efficiency", "use_case"),
])
add_group("v2.design.cae", "NAD026", "design_simulation", "Technology and Products, lines 61-110", [
    ("v2.design.cae.accelerate", "GPU-Accelerated Engineering", "technology"),
    ("v2.design.cae.ai_engineering", "AI Engineering", "technology"),
    ("v2.design.cae.visualization", "Interactive Visualization", "technology"),
    ("v2.design.cae.cuda_x", "CUDA-X", "software"),
    ("v2.design.cae.warp", "Warp", "software"),
    ("v2.design.cae.physicsnemo", "PhysicsNeMo", "platform"),
    ("v2.design.cae.workstation", "Engineering Simulation on Workstations", "solution"),
    ("v2.design.cae.data_center", "Engineering Simulation in the Data Center", "solution"),
    ("v2.design.cae.cloud", "Engineering Simulation in the Cloud", "solution"),
])
add_group("v2.design.rendering", "NAD027", "design_simulation", "RTX Solutions and Tools, lines 69-200", [
    ("v2.design.rendering.rtx_pro", "RTX PRO Platform", "platform"),
    ("v2.design.rendering.laptop", "RTX PRO Laptop", "product_family"),
    ("v2.design.rendering.desktop", "RTX PRO Desktop Workstation", "product_family"),
    ("v2.design.rendering.data_center", "RTX PRO Data Center Rendering", "solution"),
    ("v2.design.rendering.vws", "RTX Virtual Workstation", "software"),
    ("v2.design.rendering.rtx_kit", "RTX Kit", "software"),
    ("v2.design.rendering.optix", "OptiX", "software"),
    ("v2.design.rendering.denoiser", "AI-Accelerated Denoiser", "software"),
])
add_group("v2.design.xr", "NAD030", "design_simulation", "Technologies, lines 38-63", [
    ("v2.design.xr.cloudxr", "CloudXR", "software"),
    ("v2.design.xr.vrworks", "VRWorks", "software"),
    ("v2.design.xr.vr_ready", "VR Ready", "program"),
    ("v2.design.xr.vcr", "Virtual Reality Capture and Replay", "software"),
])
add_group("v2.design.uc.facility_twin", "NAD031", "design_simulation", "Metadata and Products, lines 39-66", [
    ("v2.design.cuopt", "cuOpt", "software"),
    ("v2.design.isaac", "Isaac", "platform"),
])
add_group("v2.design.uc.robot_learning", "NAD032", "design_simulation", "Metadata and Products, lines 17-47", [
    ("v2.design.isaac_lab", "Isaac Lab", "software"),
    ("v2.design.isaac_groot", "Isaac GR00T", "platform"),
    ("v2.design.jetson", "Jetson", "platform"),
])
add_group("v2.design.uc.robot_sim", "NAD034", "design_simulation", "Metadata and Products, lines 17-67", [
    ("v2.design.isaac_sim", "Isaac Sim", "software"),
])
add_group("v2.design.uc.video_agents", "NAD036", "design_simulation", "Metadata and Products, lines 17-70", [
    ("v2.design.video.deepstream", "DeepStream", "software"),
    ("v2.design.video.cosmos", "Cosmos", "model_family"),
])
add_group("v2.design.uc.network_sim", "NAD037", "design_simulation", "AI Aerial Software and Hardware, lines 5-60", [
    ("v2.design.aerial", "AI Aerial", "platform"),
    ("v2.design.aerial.sionna", "Sionna", "software"),
    ("v2.design.aerial.framework", "Aerial Framework", "software"),
    ("v2.design.aerial.acar", "Aerial CUDA-Accelerated RAN", "software"),
    ("v2.design.aerial.aodt", "Aerial Omniverse Digital Twin", "platform"),
    ("v2.design.aerial.sionna_kit", "Sionna Research Kit", "product"),
])


def edge(edge_id, source, target, relation, source_id, locator, status="confirmed"):
    return {
        "edge_id": edge_id,
        "source_node_id": source,
        "target_node_id": target,
        "edge_type": relation,
        "status": status,
        "evidence": {"source_id": source_id, "evidence_locator": locator, "accessed_at": ACCESSED},
    }


EDGES = []
def link(parent, children, relation, sid, locator):
    for i, child in enumerate(children, 1):
        EDGES.append(edge(f"E{len(EDGES)+1:04d}", parent, child, relation, sid, locator))

link("v2.networking.scale_up", ["v2.networking.nvlink", "v2.networking.nvlink.switch"], "uses_product", "NAD001", "Introduction, lines 43-49")
link("v2.networking.scale_out", ["v2.networking.quantum", "v2.networking.spectrum_x"], "uses_product", "NAD001", "Introduction, lines 43-49")
link("v2.networking.scale_across", ["v2.networking.spectrum_xgs"], "uses_product", "NAD001", "Introduction, lines 43-49")
link("v2.networking.spectrum_x", ["v2.networking.spectrum_x.switch", "v2.networking.spectrum_x.supernic", "v2.networking.spectrum_xgs", "v2.networking.silicon_photonics.spectrum_x"], "contains", "NAD005", "Introduction and Products, lines 47-149")
link("v2.networking.bluefield", ["v2.networking.bluefield.4_dpu", "v2.networking.bluefield.4_stx", "v2.networking.bluefield.3_dpu", "v2.networking.doca"], "contains", "NAD006", "Portfolio and FAQ, lines 70-190")
link("v2.networking.dsx_air", ["v2.networking.spectrum_x", "v2.networking.connectx_nic", "v2.networking.bluefield", "v2.networking.netq"], "simulates", "NAD010", "Benefits, lines 115-124")
link("v2.networking.quantum.x800", ["v2.networking.quantum.x800_switch", "v2.networking.quantum.connectx8", "v2.networking.quantum.connectx9", "v2.networking.linkx"], "contains", "NAD012", "Platform Components, lines 63-90")
link("v2.networking.software", ["v2.networking.doca", "v2.networking.dsx_air", "v2.networking.netq", "v2.networking.quantum.ufm", "v2.networking.cumulus", "v2.networking.pure_sonic"], "contains", "NAD014", "Key Networking Software Offerings, lines 54-109")

link("v2.ai.agentic", ["v2.ai.agentic.agent_toolkit", "v2.ai.nemotron", "v2.ai.cosmos", "v2.ai.nim", "v2.ai.agentic.ai_q", "v2.ai.nemo_agent_tools", "v2.ai.nemoclaw", "v2.ai.agentic.openshell"], "uses_product", "NAD015", "Technology, lines 146-181")
link("v2.ai.data_science", ["v2.ai.rapids", "v2.ai.rapids.cudf", "v2.ai.rapids.cugraph", "v2.ai.rapids.spark", "v2.ai.rapids.xgboost"], "uses_product", "NAD016", "Features and RAPIDS, lines 37-165")
link("v2.ai.inference", ["v2.ai.inference.vera_rubin_nvl72", "v2.ai.inference.gb300_nvl72", "v2.ai.inference.dynamo", "v2.ai.inference.tensorrt_llm", "v2.ai.inference.triton", "v2.ai.inference.tensorrt"], "uses_product", "NAD017", "Platform and customer stories, lines 120-206")
link("v2.ai.conversational", ["v2.ai.nemotron", "v2.ai.conversational.riva", "v2.ai.nim", "v2.ai.conversational.blueprints"], "uses_product", "NAD018", "Software, lines 85-120")
link("v2.ai.vision", ["v2.ai.metropolis", "v2.ai.tao", "v2.ai.deepstream", "v2.ai.nim"], "uses_product", "NAD019", "Overview and Starting Options, lines 50-157")
link("v2.ai.cybersecurity", ["v2.ai.agentic.openshell", "v2.ai.confidential_computing", "v2.networking.bluefield", "v2.ai.nemotron", "v2.ai.blueprints", "v2.ai.nemo", "v2.ai.morpheus", "v2.networking.doca"], "uses_product", "NAD020", "Technology and Use Cases, lines 83-180")
link("v2.ai.uc.sdg_agentic", ["v2.ai.nemo"], "uses_product", "NAD021", "Products, lines 51-54")
link("v2.ai.uc.content_generation", ["v2.ai.ai_enterprise", "v2.ai.nemo", "v2.ai.omniverse", "v2.design.rendering.rtx_pro"], "uses_product", "NAD022", "Products, lines 58-64")
link("v2.ai.uc.biomolecular_generation", ["v2.ai.nim", "v2.ai.bionemo", "v2.ai.ai_enterprise", "v2.ai.monai"], "uses_product", "NAD023", "Products, lines 40-45")
link("v2.ai.ai_enterprise", ["v2.ai.nemo", "v2.ai.omniverse", "v2.ai.run_ai", "v2.ai.nim", "v2.ai.blueprints"], "contains", "NAD024", "Production-Ready AI and Use Cases, lines 123-198")

link("v2.design.cae", ["v2.design.cae.cuda_x", "v2.design.cae.warp", "v2.design.cae.physicsnemo", "v2.ai.omniverse", "v2.ai.nemoclaw"], "uses_product", "NAD026", "Technology, lines 61-84")
link("v2.design.rendering", ["v2.design.rendering.rtx_pro", "v2.design.rendering.rtx_kit", "v2.design.rendering.optix", "v2.design.rendering.denoiser", "v2.ai.omniverse"], "uses_product", "NAD027", "RTX Solutions and Tools, lines 69-200")
link("v2.design.xr", ["v2.design.xr.cloudxr", "v2.design.xr.vrworks", "v2.design.xr.vr_ready", "v2.ai.omniverse", "v2.design.xr.vcr"], "uses_product", "NAD030", "Technologies, lines 41-63")
link("v2.design.uc.facility_twin", ["v2.ai.ai_enterprise", "v2.design.cuopt", "v2.design.isaac", "v2.ai.metropolis", "v2.ai.omniverse"], "uses_product", "NAD031", "Products, lines 52-66")
link("v2.design.uc.robot_learning", ["v2.ai.omniverse", "v2.design.isaac", "v2.design.jetson", "v2.design.isaac_lab", "v2.design.isaac_groot"], "uses_product", "NAD032", "Products and Overview, lines 42-57")
link("v2.design.uc.synthetic_data", ["v2.ai.omniverse", "v2.design.isaac", "v2.ai.cosmos"], "uses_product", "NAD033", "Products and Overview, lines 53-64")
link("v2.design.uc.robot_sim", ["v2.design.isaac_sim", "v2.ai.omniverse"], "uses_product", "NAD034", "Products, lines 63-67")
link("v2.design.uc.humanoid", ["v2.ai.omniverse", "v2.design.isaac", "v2.design.jetson", "v2.design.isaac_groot"], "uses_product", "NAD035", "Products and Overview, lines 61-84")
link("v2.design.uc.video_agents", ["v2.ai.metropolis", "v2.design.video.deepstream", "v2.ai.ai_enterprise", "v2.design.video.cosmos"], "uses_product", "NAD036", "Products, lines 64-70")
link("v2.design.uc.network_sim", ["v2.design.aerial", "v2.design.aerial.sionna", "v2.design.aerial.framework", "v2.design.aerial.acar", "v2.design.aerial.aodt"], "uses_product", "NAD037", "AI Aerial Software, lines 5-46")


RELATIONS = []


def rel_group(source_id, context, names, hint, scopes, *, obs="logo", status="inferred", rationale=None):
    for name in names:
        RELATIONS.append({
            "candidate_id": f"RC{len(RELATIONS)+1:04d}",
            "entity_name_raw": name,
            "source_id": source_id,
            "evidence_locator": context,
            "observation_type": obs,
            "relationship_hint": hint,
            "candidate_fact_status": status,
            "nvidia_scope_ids": scopes,
            "product_mapping_status": "confirmed" if status == "confirmed" else "inferred",
            "rationale": rationale or (
                "Logo/name appears under an explicit partner, ecosystem, adopter, or customer heading; "
                "this is a relation candidate, not a final classified relationship."
            ),
            "accessed_at": ACCESSED,
        })


# Networking candidates.
rel_group("NAD001", "News: Spectrum-X Ethernet adoption, lines 158-163", ["Meta", "Microsoft", "Oracle"], "customer", ["v2.networking.spectrum_x"], obs="explicit_text", status="confirmed")
rel_group("NAD005", "Partners > Server, lines 165-182", ["Cisco", "Dell Technologies", "Hewlett Packard Enterprise", "Lenovo", "Supermicro"], "partner", ["v2.networking.spectrum_x"])
rel_group("NAD005", "Partners > Storage, lines 165-194", ["DDN", "Everpure", "IBM", "Supermicro", "VAST Data", "WEKA"], "partner", ["v2.networking.spectrum_x", "v2.networking.spectrum_x.ai_storage"])
rel_group("NAD005", "Partners > Orchestration, lines 165-206", ["Armada", "Aviz", "BE Networks", "Hedgehog", "Netris", "OpenNebula"], "partner", ["v2.networking.spectrum_x"])
rel_group("NAD005", "Introduction: xAI 100,000-GPU system, lines 55-59", ["xAI"], "customer", ["v2.networking.spectrum_x"], obs="explicit_text", status="confirmed")

bluefield_groups = {
    "Cloud": ["Akamai", "CoreWeave", "Crusoe", "Lambda", "Nebius", "Oracle Cloud Infrastructure", "Together AI"],
    "Storage": ["Cloudian", "DDN", "Dell", "Everpure", "Hitachi Vantara", "IBM", "MinIO", "NetApp", "Nutanix", "VAST Data", "WEKA"],
    "Cybersecurity": ["Akamai", "Armis", "Check Point", "Cisco", "CrowdStrike", "EQTY Lab", "F5", "Forescout", "Fortinet", "Palo Alto Networks", "TrendAI", "Xage Security", "Zscaler"],
    "Infrastructure": ["Aviz", "Canonical", "Mirantis", "Netris", "Nutanix", "Rafay", "Red Hat", "Spectro Cloud", "SUSE"],
    "Systems": ["AIC", "ASRock Rack", "ASUS", "Cisco", "Dell", "Foxconn", "GIGABYTE", "Hewlett Packard Enterprise", "Lenovo", "Pegatron", "QCT", "Supermicro", "Wistron", "Wiwynn"],
    "Services": ["Accenture", "Bechtle", "Computacenter", "Deloitte", "World Wide Technology"],
}
for group, names in bluefield_groups.items():
    rel_group("NAD006", f"Partner Ecosystem > {group}, lines 257-385", names, "partner", ["v2.networking.bluefield"])

rel_group("NAD008", "Technology Partners, lines 148-171", ["Browave", "Coherent", "Corning", "Fabrinet", "Foxconn", "Lumentum", "Senko", "SPIL", "Sumitomo Electric", "TSMC"], "partner", ["v2.networking.silicon_photonics"])
rel_group("NAD008", "Introduction: first adopters, lines 52-56", ["CoreWeave", "Lambda", "Meta", "Microsoft", "Oracle Cloud Infrastructure"], "customer", ["v2.networking.silicon_photonics.spectrum_x"], obs="explicit_text", status="confirmed")
rel_group("NAD009", "Partners, lines 135-146", ["Cisco", "Dell Technologies", "Hewlett Packard Enterprise", "Lenovo", "Supermicro"], "partner", ["v2.networking.spectrum_x"])
rel_group("NAD010", "Ecosystem, lines 161-184", ["Armada", "Aviz", "BE Networks", "Check Point", "Hedgehog", "Keysight", "Netris", "OpenNebula", "Rafay", "TrendAI", "VAST Data"], "partner", ["v2.networking.dsx_air"])

# AI candidates.
rel_group("NAD002", "Resources > video: ServiceNow document intelligence, lines 165-174", ["ServiceNow"], "partner", ["v2.ai"], obs="explicit_text", status="unknown", rationale="Company expert appears in a resource video; relationship and product adoption are not stated on the seed page.")
rel_group("NAD016", "Partner Ecosystem, lines 180-217", ["Anaconda", "BlazingDB", "Chainer", "Datalogue", "Databricks", "Dell EMC", "FastData", "Graphistry", "H2O.ai", "Hewlett Packard Enterprise", "OmniSci", "Oracle", "Pure Storage", "PyTorch", "SAP", "SAS", "SQream", "Zilliz"], "partner", ["v2.ai.rapids"])
rel_group("NAD017", "Inference providers on Blackwell, lines 60-64", ["Baseten", "DeepInfra", "Fireworks AI", "Together AI"], "customer", ["v2.ai.inference", "v2.ai.inference.gb300_nvl72"], obs="explicit_text", status="confirmed")
rel_group("NAD017", "Customer Stories, lines 176-206", ["Amdocs", "Snap", "Amazon"], "customer", ["v2.ai.inference"], obs="customer_story", status="confirmed")
rel_group("NAD018", "Customer Stories, lines 176-215", ["Caterpillar", "Personal AI", "Yum! Brands"], "customer", ["v2.ai.conversational"], obs="customer_story", status="confirmed")
rel_group("NAD018", "Adopters > Ecosystem Partners, lines 217-298", [
    "Artisight", "Botpress", "Computacenter", "Data Monsters", "Exigent AI", "Infosys", "InstaDeep", "Intelligent Voice", "Interactions", "Kensho", "Kore.ai", "Latitude", "Lexistem", "Malamute", "MeetKai", "Minerva CQ", "Moneypenny", "Morningstar", "MTS", "NetApp", "Pendulum", "Playbook", "Quantiphi", "Read AI", "Samespace", "SimInsights", "SliceX AI", "SmartCow", "SoftServe", "SVA", "Talkwalker", "Tarteel AI", "TextCortex", "Vector Ventures", "Verneek", "Voca.ai", "WASP", "Writer"
], "partner", ["v2.ai.conversational"])
rel_group("NAD018", "Adopters > Developer Libraries, lines 300-314", ["DeepPavlov", "ESPnet", "Hugging Face", "Ludwig", "PerceptiLabs", "spaCy", "Rasa"], "partner", ["v2.ai.conversational"])
rel_group("NAD019", "Metropolis Ecosystem > Global System Integrators, lines 164-187", ["Deloitte", "Accenture", "EY", "HCLTech", "Infosys", "Tata Consultancy Services"], "partner", ["v2.ai.metropolis"])
rel_group("NAD019", "Metropolis Ecosystem > Application Providers, lines 164-212", ["DeepHow", "InOrbit", "Vaidio", "K2K", "Linker Vision", "ITMax", "MetAI", "Plato", "Solomon", "Spingence", "ST Engineering", "Telit Cinterion", "VAST Data"], "partner", ["v2.ai.metropolis"])
rel_group("NAD019", "Metropolis Ecosystem > System Builders, lines 164-222", ["Advantech", "Dell", "Hewlett Packard Enterprise", "Lenovo", "Siemens"], "partner", ["v2.ai.metropolis"])
rel_group("NAD019", "Metropolis Ecosystem > Solution Providers, lines 164-239", ["FTP Software", "Genetec", "Kenmec", "Milestone Systems", "Quantiphi", "Rockwell Automation", "Siemens", "SoftServe", "World Wide Technology"], "partner", ["v2.ai.metropolis"])
rel_group("NAD020", "Leading Adopters, lines 197-222", ["Accenture", "Check Point", "Cisco", "Cloudflare", "CrowdStrike", "Deloitte", "F5", "Fortinet", "Palo Alto Networks", "TrendAI", "Zscaler"], "partner", ["v2.ai.cybersecurity"])
rel_group("NAD024", "Customer Stories, lines 200-226", ["Amgen", "ServiceNow", "Amdocs"], "customer", ["v2.ai.ai_enterprise"], obs="customer_story", status="confirmed")
rel_group("NAD024", "Marketplace deployment training, lines 298-317", ["Oracle", "Microsoft", "Google", "Amazon Web Services"], "partner", ["v2.ai.ai_enterprise"], obs="explicit_text", status="inferred", rationale="Page documents AI Enterprise deployment/onboarding through each cloud marketplace; commercial role requires later corroboration.")

# Design and simulation candidates.
rel_group("NAD003", "Overview: strategic partnership, lines 50-54", ["Synopsys"], "partner", ["v2.design"], obs="explicit_text", status="confirmed")
rel_group("NAD003", "Solutions: CAE image label, lines 65-73", ["Cadence"], "unknown", ["v2.design.cae"], obs="image_caption", status="unknown", rationale="Cadence Fidelity appears as an image/product caption adjacent to CAE; the seed alone does not classify the economic relationship.")
rel_group("NAD003", "Use Cases, lines 118-207", ["Pegatron", "Katana", "Amazon Robotics", "Fourier"], "customer", ["v2.design"], obs="use_case_card", status="confirmed")
rel_group("NAD003", "Resources > Customer Stories, lines 230-255", ["Foxconn", "Katana Studio", "BMW Group"], "customer", ["v2.design.digital_twin"], obs="customer_story", status="confirmed")
rel_group("NAD025", "Digital twin examples and support providers, lines 72-148", ["Siemens", "BMW Group", "Wistron", "Pegatron", "Accenture", "SoftServe", "T-Systems", "Continental", "Rockwell Automation", "Foxconn", "Sight Machine", "Ansys", "Cadence", "Luminary Cloud", "Rescale"], "partner", ["v2.design.digital_twin"], obs="explicit_text", status="inferred", rationale="Official glossary describes use, development, or supporting services with named NVIDIA technologies; final role and direction require entity-level review.")
rel_group("NAD025", "Product configurator and autonomous-system examples, lines 149-180", ["Unilever", "Moet Hennessy", "Nissan", "Apple", "WPP", "Coca-Cola", "Zaha Hadid Architects", "Microsoft", "Amazon Robotics", "MathWorks", "Foretellix", "KION Group", "Accenture", "Delta Electronics"], "customer", ["v2.design.digital_twin"], obs="explicit_text", status="inferred", rationale="Named company is described using or developing with NVIDIA/OpenUSD technology; exact procurement direction is not always stated.")
rel_group("NAD025", "Smart city and AI-factory examples, lines 182-231", ["Digital Realty", "Linker Vision"], "partner", ["v2.design.digital_twin"], obs="explicit_text", status="inferred")
rel_group("NAD026", "Overview: industrial software integration, lines 55-59", ["Cadence", "Dassault Systemes", "PTC", "Siemens", "Synopsys"], "partner", ["v2.design.cae"], obs="explicit_text", status="confirmed")
rel_group("NAD026", "Leading Adopters > Industry Software Providers, lines 159-201", ["Autodesk", "Beyond Math", "Cadence", "COMSOL", "Dassault Systemes", "ENGYS", "Flexcompute", "Keysight", "Luminary Cloud", "Neural Concept", "nTop", "PhysicsX", "PTC", "Siemens", "SimScale", "Synopsys", "Trane Technologies", "Volcano Platforms"], "partner", ["v2.design.cae"])
rel_group("NAD026", "Leading Adopters > Cloud Service Providers, lines 159-211", ["Amazon Web Services", "Google Cloud", "Microsoft", "Oracle Cloud", "Rescale"], "partner", ["v2.design.cae"])
rel_group("NAD026", "Leading Adopters > Hardware Partners, lines 159-223", ["BOXX", "Dell Technologies", "Hewlett Packard Enterprise", "Lenovo", "Supermicro", "HP"], "partner", ["v2.design.cae"])
rel_group("NAD027", "Resources and application examples, lines 151-187", ["KeyShot", "Digital Domain"], "partner", ["v2.design.rendering"], obs="explicit_text", status="inferred")
rel_group("NAD030", "XR page stray Katana label, lines 41-59", ["Katana"], "unknown", ["v2.design.xr"], obs="unheaded_label", status="unknown", rationale="Company-like label appears without a titled relationship or explanatory text; retained as unknown to prevent logo/co-occurrence overclaim.")
rel_group("NAD031", "Industrial facility page company examples", ["Foxconn", "BMW Group", "Pegatron", "Siemens", "Rockwell Automation", "KION Group"], "customer", ["v2.design.uc.facility_twin"], obs="explicit_text", status="inferred")
rel_group("NAD032", "Hero/company label, lines 17-24", ["Boston Dynamics"], "unknown", ["v2.design.uc.robot_learning"], obs="unheaded_label", status="unknown", rationale="Company name appears in hero context without a relationship sentence in the reviewed locator.")
rel_group("NAD034", "Hero/company label and resource mentions, lines 17-85", ["Fraunhofer IML", "Skild AI", "Lightwheel"], "unknown", ["v2.design.uc.robot_sim"], obs="unheaded_label", status="unknown", rationale="Names are adjacent to use-case/resource content; later source-level corroboration is required.")
rel_group("NAD035", "Hero/company label, lines 17-24", ["Apptronik"], "unknown", ["v2.design.uc.humanoid"], obs="unheaded_label", status="unknown", rationale="Company appears in hero context without an explicit relationship sentence in the reviewed locator.")
rel_group("NAD029", "AV simulation ecosystem examples", ["CARLA", "MathWorks", "Foretellix"], "partner", ["v2.design.uc.av_sim"], obs="explicit_text", status="inferred")
rel_group("NAD036", "Video analytics customer/partner examples", ["Milestone Systems", "K2K", "Akila", "Foxconn"], "partner", ["v2.design.uc.video_agents"], obs="explicit_text", status="inferred")


def write_jsonl(name, rows):
    path = OUT / name
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


SECTIONS = []
for s in SOURCES:
    for ordinal, section in enumerate(s["sections"], 1):
        SECTIONS.append({
            "section_id": f"{s['source_id']}.SEC{ordinal:02d}",
            "source_id": s["source_id"],
            "section_title": section,
            "processing_status": "processed_no_taxonomy_or_relation_candidate" if section in {"Next Steps", "Resources", "Webinars", "News"} else "processed",
            "evidence_locator": f"Page section heading: {section}",
            "accessed_at": ACCESSED,
        })


source_ids = {s["source_id"] for s in SOURCES}
node_ids = {n["node_id"] for n in NODES}
errors = []
if len([s for s in SOURCES if s["is_seed"]]) != 3:
    errors.append("seed_count_not_3")
if any(s["closure_decision"] == "pending" or s["access_status"] == "pending" for s in SOURCES):
    errors.append("pending_source")
if any(sec["processing_status"] == "pending" for sec in SECTIONS):
    errors.append("pending_section")
if any(n["evidence"]["source_id"] not in source_ids or not n["evidence"]["evidence_locator"] for n in NODES):
    errors.append("node_provenance_error")
if any(e["source_node_id"] not in node_ids or e["target_node_id"] not in node_ids or e["evidence"]["source_id"] not in source_ids for e in EDGES):
    errors.append("edge_integrity_error")
if any(r["source_id"] not in source_ids or not r["evidence_locator"] or not r["nvidia_scope_ids"] for r in RELATIONS):
    errors.append("relation_provenance_error")
if len(node_ids) != len(NODES):
    errors.append("duplicate_node_id")

write_jsonl("source_frontier.jsonl", SOURCES)
write_jsonl("page_sections.jsonl", SECTIONS)
write_jsonl("taxonomy_nodes.jsonl", NODES)
write_jsonl("solution_product_edges.jsonl", EDGES)
write_jsonl("relation_candidates.jsonl", RELATIONS)

merge_patch = {
    "patch_id": "v2-network-ai-design-2026-08-25",
    "research_cutoff": "2026-08-25",
    "supersedes": "run-002 product_tree coverage for these three branches; does not overwrite v1 artifacts",
    "roots": ["v2.networking", "v2.ai", "v2.design"],
    "source_ids": sorted(source_ids),
    "taxonomy_node_ids": sorted(node_ids),
    "edge_ids": [e["edge_id"] for e in EDGES],
    "relation_candidate_ids": [r["candidate_id"] for r in RELATIONS],
    "merge_rules": {
        "canonicalize_by": ["normalized_name", "official_family_page", "existing_v1_canonical_key"],
        "preserve_multi_parent_paths": True,
        "do_not_promote_relation_candidates": True,
        "redirect_aliases_are_evidence_not_separate_nodes": True,
        "logo_only_requires_later_human_review": True,
    },
    "known_cross_shard_overlaps": [
        {"source_id": "NAD028", "owner_hint": "robotics shard", "decision": "processed here at direct-family boundary; merge by canonical URL"},
        {"source_id": "NAD029", "owner_hint": "autonomous-vehicles shard", "decision": "processed here at direct-family boundary; merge by canonical URL"},
        {"node_id": "v2.ai.omniverse", "decision": "shared AI/Design platform; one canonical object with multiple observed paths"},
        {"node_id": "v2.ai.metropolis", "decision": "shared Vision AI/Design use-case platform; one canonical object"},
    ],
    "unmapped_product_candidates": [],
    "pending_sources": [],
    "pending_sections": [],
}
(OUT / "merge_patch.json").write_text(json.dumps(merge_patch, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

validation = {
    "status": "pass" if not errors else "fail",
    "research_cutoff": "2026-08-25",
    "generated_at": ACCESSED,
    "counts": {
        "seed_pages": len([s for s in SOURCES if s["is_seed"]]),
        "frontier_records": len(SOURCES),
        "reviewed_or_decided_frontier_records": len([s for s in SOURCES if s["closure_decision"] != "pending"]),
        "excluded_by_robots": len([s for s in SOURCES if s["access_status"] == "excluded_robots"]),
        "page_sections": len(SECTIONS),
        "taxonomy_nodes": len(NODES),
        "solution_product_edges": len(EDGES),
        "relation_candidates": len(RELATIONS),
        "candidate_statuses": dict(Counter(r["candidate_fact_status"] for r in RELATIONS)),
        "pending_sources": 0,
        "pending_sections": 0,
        "unmapped_product_candidates": 0,
        "broken_provenance_links": len(errors),
    },
    "checks": {
        "three_seeds_present": len([s for s in SOURCES if s["is_seed"]]) == 3,
        "frontier_zero_pending": not any(s["closure_decision"] == "pending" for s in SOURCES),
        "sections_zero_pending": not any(sec["processing_status"] == "pending" for sec in SECTIONS),
        "taxonomy_provenance_valid": "node_provenance_error" not in errors,
        "edge_integrity_valid": "edge_integrity_error" not in errors,
        "relation_candidate_provenance_valid": "relation_provenance_error" not in errors,
        "robots_parameter_exclusion_recorded": any(s["source_id"] == "NAD038" and s["access_status"] == "excluded_robots" for s in SOURCES),
        "logo_only_not_final_relationship": all(r["relationship_hint"] in {"partner", "customer", "unknown"} and r["candidate_fact_status"] in {"confirmed", "inferred", "unknown"} for r in RELATIONS),
    },
    "errors": errors,
}
(OUT / "validation_report.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

if errors:
    raise SystemExit("validation failed: " + ", ".join(errors))
print(json.dumps(validation["counts"], ensure_ascii=False, sort_keys=True))
