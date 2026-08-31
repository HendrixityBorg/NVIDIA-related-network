#!/usr/bin/env python3
"""Build the NVIDIA product-tree research artifacts from reviewed official indexes.

The lists below are deliberately explicit: reviewers can diff them across snapshots,
and every generated node inherits a source URL plus a human-readable locator.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


OUT = Path(__file__).resolve().parent
ACCESSED_AT = "2026-08-25T16:30:00+08:00"
CUTOFF = "2026-08-25"


SOURCES = [
    ("S001", "https://www.nvidia.com/en-us/products/", "NVIDIA Products", "NVIDIA / Products", None, "reviewed", "Official current product index; rendered content available, page notes JavaScript for full functionality."),
    ("S002", "https://www.nvidia.com/en-us/software/", "NVIDIA Software and Applications", "NVIDIA / Software", "S001", "reviewed", "Official software index; rendered content available."),
    ("S003", "https://www.nvidia.com/en-us/solutions/", "NVIDIA Solutions", "NVIDIA / Solutions", None, "reviewed", "Official current solutions index."),
    ("S004", "https://www.nvidia.com/en-us/industries/", "AI Solutions for Industries", "NVIDIA / Industries", "S003", "reviewed", "Official current industries index."),
    ("S005", "https://www.nvidia.com/en-us/data-center/products/", "Data Center Products", "Products / Data Center / Current portfolio", "S001", "reviewed", "Canonical current data-center portfolio; query-string variant resolved to this path."),
    ("S006", "https://www.nvidia.com/en-us/data-center/dgx-platform/", "NVIDIA DGX Platform", "Products / Data Center / DGX", "S001", "reviewed", "Official family page."),
    ("S007", "https://www.nvidia.com/en-us/data-center/hgx/", "NVIDIA HGX Platform", "Products / Data Center / HGX", "S001", "reviewed", "Official family page."),
    ("S008", "https://www.nvidia.com/en-us/data-center/products/mgx/", "NVIDIA MGX", "Products / Data Center / MGX", "S001", "reviewed", "Official reference-architecture page."),
    ("S009", "https://www.nvidia.com/en-us/data-center/grace-cpu/", "NVIDIA CPU Platforms", "Products / Data Center / CPU", "S001", "reviewed", "Page title retains Grace URL but current content covers Vera and Grace CPUs."),
    ("S010", "https://www.nvidia.com/en-us/data-center/products/ovx/", "NVIDIA OVX Systems", "Products / Data Center / OVX", "S001", "reviewed", "Official systems page."),
    ("S011", "https://www.nvidia.com/en-us/edge-computing/products/igx/", "NVIDIA IGX", "Products / Edge / IGX", "S001", "reviewed", "Official family page."),
    ("S012", "https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/", "NVIDIA Jetson Embedded Systems", "Products / Embedded / Jetson", "S001", "reviewed", "Official family and SKU comparison page."),
    ("S013", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/in-vehicle-computing/", "NVIDIA DRIVE In-Vehicle Computing", "Products / Embedded / DRIVE", "S001", "reviewed", "Old self-driving-cars URL redirects to this canonical page."),
    ("S014", "https://www.nvidia.com/en-us/industries/robotics/", "AI for Robotics", "Solutions / Robotics", "S003", "reviewed", "Two legacy solution URLs redirect to this canonical industry page."),
    ("S015", "https://developer.nvidia.com/isaac", "NVIDIA Isaac", "Products / Robotics / Isaac", "S014", "reviewed", "Official NVIDIA Developer product page."),
    ("S016", "https://www.nvidia.com/en-us/networking/", "NVIDIA Networking", "Products / Networking", "S001", "reviewed", "Official networking overview."),
    ("S017", "https://www.nvidia.com/en-us/networking/products/data-processing-unit/", "NVIDIA BlueField Platform", "Products / Networking / BlueField", "S001", "reviewed", "Official portfolio page."),
    ("S018", "https://www.nvidia.com/en-us/networking/products/ethernet/", "NVIDIA Spectrum Ethernet Platform", "Products / Networking / Ethernet", "S001", "reviewed", "Official portfolio page."),
    ("S019", "https://www.nvidia.com/en-us/networking/products/infiniband/", "NVIDIA Quantum InfiniBand Platform", "Products / Networking / InfiniBand", "S001", "reviewed", "Official portfolio page."),
    ("S020", "https://www.nvidia.com/en-us/networking/products/software/", "NVIDIA Networking Software", "Products / Networking / Software", "S001", "reviewed", "Official networking software portfolio."),
    ("S021", "https://www.nvidia.com/en-us/data-center/magnum-io/", "NVIDIA Magnum IO", "Products / Networking / Network Acceleration", "S001", "reviewed", "Official optimization-stack page."),
    ("S022", "https://www.nvidia.com/en-us/geforce/graphics-cards/", "GeForce Graphics Cards", "Products / Gaming / Graphics Cards", "S001", "reviewed", "Official GeForce product navigation and current series page."),
    ("S023", "https://www.nvidia.com/en-us/products/workstations/professional-desktop-gpus/", "NVIDIA RTX PRO Desktop GPUs", "Products / Workstations / Desktop GPUs", "S001", "reviewed", "Official current and prior professional desktop lineup."),
    ("S024", "https://www.nvidia.com/en-us/products/workstations/professional-laptops/", "NVIDIA RTX PRO Laptops", "Products / Workstations / Laptop GPUs", "S001", "reviewed", "Official professional mobile lineup."),
    ("S025", "https://www.nvidia.com/en-us/ai-data-science/products/nim-microservices/", "NVIDIA NIM", "Software / AI / Inference", "S002", "reviewed", "Official product page."),
    ("S026", "https://www.nvidia.com/en-us/ai-data-science/products/nemo/", "NVIDIA NeMo", "Software / AI / Agent lifecycle", "S002", "reviewed", "Legacy NeMo LLM URL redirects here."),
    ("S027", "https://www.nvidia.com/en-us/ai/dynamo/", "NVIDIA Dynamo", "Software / AI / Inference", "S002", "reviewed", "Official current product page."),
    ("S028", "https://www.nvidia.com/en-us/ai/", "NVIDIA AI", "Solutions / Artificial Intelligence", "S003", "reviewed", "Official AI overview."),
    ("S029", "https://www.nvidia.com/en-us/data-center/dgx-cloud/", "NVIDIA DGX Cloud", "Products / Cloud Services / DGX Cloud", "S001", "reviewed", "Current page describes NVIDIA's internal cloud and DSX OS externalization."),
    ("S030", "https://www.nvidia.com/en-us/gpu-cloud/", "NVIDIA NGC", "Products / Cloud Services / NGC", "S001", "reviewed", "Official NGC landing page."),
    ("S031", "https://www.nvidia.com/en-us/technologies/", "NVIDIA Technologies", "Technologies", "S001", "reviewed", "Official technologies index; includes current and historical technologies."),
    ("S032", "https://www.nvidia.com/en-us/data-center/technologies/blackwell-architecture/", "NVIDIA Blackwell Architecture", "Architectures / Blackwell", "S031", "reviewed", "Official architecture and product list."),
    ("S033", "https://www.nvidia.com/en-us/data-center/technologies/hopper-architecture/", "NVIDIA Hopper Architecture", "Architectures / Hopper", "S031", "reviewed", "Official architecture page."),
    ("S034", "https://www.nvidia.com/en-us/technologies/ada-architecture/", "NVIDIA Ada Lovelace Architecture", "Architectures / Ada Lovelace", "S031", "reviewed", "Official architecture page."),
    ("S035", "https://www.nvidia.com/en-us/edge-computing/", "NVIDIA Edge Computing", "Solutions / Robotics and Edge AI / Edge AI", "S003", "reviewed", "Official solution page."),
    ("S036", "https://www.nvidia.com/en-us/autonomous-machines/intelligent-video-analytics-platform/", "NVIDIA Metropolis", "Products / Edge / Vision AI", "S003", "reviewed", "Official platform page."),
    ("S037", "https://www.nvidia.com/en-us/products/workstations/", "NVIDIA RTX PRO Workstations", "Products / Professional Workstations", "S001", "reviewed", "Canonical page also receives redirects from AI-workstations and design-visualization URLs."),
    ("S038", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/", "NVIDIA Autonomous Vehicles", "Solutions / Autonomous Vehicles", "S003", "reviewed", "Canonical page receives redirect from /self-driving-cars/."),
    ("S039", "https://www.nvidia.com/en-us/ai-trust-center/halos/autonomous-vehicles/", "NVIDIA Halos for Autonomous Vehicles", "Solutions / Autonomous Vehicles / Safety", "S003", "reviewed", "Legacy /trust-center/ path redirects here."),
    ("S040", "https://www.nvidia.com/en-us/data-center/enterprise-software/", "NVIDIA Data Center Enterprise Software", "Software / Infrastructure", "S002", "reviewed", "Official enterprise-software index."),
    ("S041", "https://www.nvidia.com/en-us/geforce/", "NVIDIA GeForce", "Products / Gaming", "S001", "reviewed", "Official GeForce landing page."),
    ("S042", "https://www.nvidia.com/en-us/software/nvidia-app/", "NVIDIA App", "Products / Apps and Tools", "S001", "reviewed", "Official application page."),
    ("S043", "https://www.nvidia.com/en-us/shield/", "NVIDIA SHIELD", "Products / Gaming / SHIELD", "S001", "reviewed", "Official product page."),
    ("S044", "https://www.nvidia.com/en-us/data-center/virtual-solutions/", "NVIDIA Virtual GPU", "Products / Data Center / Virtualization", "S001", "reviewed", "Official virtualization portfolio page."),
    ("S045", "https://www.nvidia.com/en-us/products/workstations/dgx-spark/", "NVIDIA DGX Spark", "Products / Professional Workstations", "S001", "reviewed", "Official product page."),
    ("S046", "https://www.nvidia.com/en-us/products/workstations/dgx-station/", "NVIDIA DGX Station", "Products / Professional Workstations", "S001", "reviewed", "Official product page."),
    ("S047", "https://docs.nvidia.com/ngc/latest/ngc-private-registry-user-guide.html", "NGC Private Registry User Guide", "Products / Cloud Services / Private Registry", "S001", "reviewed", "Public NVIDIA documentation; product-index link redirects here."),
    ("S048", "https://www.nvidia.com/en-us/industries/healthcare-life-sciences/", "AI for Healthcare and Life Sciences", "Industries / Healthcare", "S004", "reviewed", "BioNeMo and Clara legacy product-index links redirect to this industry page; the page contains current healthcare platforms."),
    ("S049", "https://build.nvidia.com/", "NVIDIA Build", "Software / API Catalog and Blueprints", "S002", "reviewed", "Public catalog landing; individual model catalog is intentionally not enumerated."),
    ("S050", "https://developer.nvidia.com/tools-overview", "NVIDIA Nsight Developer Tools", "Products / Apps and Tools / Nsight", "S001", "reviewed", "Official developer tools index."),
    ("S051", "https://www.nvidia.com/en-us/clara/biopharma/", "BioNeMo product-index target (legacy path)", "Products / Cloud Services / BioNeMo", "S001", "redirected", "Redirected to /en-us/industries/healthcare-life-sciences/; original and canonical URLs both retained."),
    ("S052", "https://www.nvidia.com/en-us/omniverse/cloud/", "Omniverse Cloud product-index target (legacy path)", "Products / Cloud Services / Omniverse Cloud", "S001", "redirect_mismatch", "Redirected to DGX Cloud at access time; does not independently confirm a current Omniverse Cloud service."),
    ("S053", "https://www.nvidia.com/en-us/clara/medical-devices/", "Clara AGX product-index target (legacy path)", "Products / Embedded Systems / Clara AGX", "S001", "redirect_mismatch", "Redirected to Healthcare and Life Sciences; does not independently confirm a current Clara AGX SKU."),
    ("S054", "https://www.nvidia.com/en-us/geforce-now/", "GeForce NOW US target", "Products / Gaming and Creating / GeForce NOW", "S001", "regional_redirect", "Redirected to the en-AU regional page in the access environment; no regional plans or prices collected."),
    ("S055", "https://www.nvidia.com/en-us/self-driving-cars/", "Self-Driving Cars legacy path", "Solutions / Autonomous Vehicles", "S003", "redirected", "Redirected to /en-us/solutions/autonomous-vehicles/."),
    ("S056", "https://www.nvidia.com/en-us/solutions/robotics-and-edge-computing/", "Robotics and Edge Computing legacy path", "Solutions / Robotics and Edge AI", "S003", "redirected", "Redirected to /en-us/industries/robotics/."),
    ("S057", "https://marketplace.nvidia.com/en-us/enterprise/data-center/?category=gpu&limit=15&locale=en-us&page=1", "NVIDIA Marketplace Data Center GPUs", "Products / Data Center / GPU portfolio", "S005", "reviewed", "Public official NVIDIA Marketplace page 1, 15 rows requested; seven GPU products were rendered. No pagination bypass or restricted access."),
    ("S058", "https://docs.nvidia.com/data-center-gpu/line-card.pdf", "NVIDIA Data Center Platform Line Card", "Products / Data Center / GPU portfolio", "S005", "reviewed", "Public official August 2025 line card; corroborates RTX PRO 6000 Blackwell Server Edition, L40S, and L4 as the universal graphics and compute portfolio."),
    ("S059", "https://www.nvidia.com/en-us/data-center/graphics-cards-for-virtualization/", "NVIDIA GPUs for Virtualization", "Products / Data Center / supported GPU comparison", "S044", "reviewed", "Public official comparison includes H100/A-series support examples; treated as supported, not evidence of inclusion in the current Marketplace GPU portfolio."),
]


SOURCE_MAP = {row[0]: row for row in SOURCES}


def ev(source_id: str, locator: str) -> dict:
    row = SOURCE_MAP[source_id]
    return {
        "source_id": source_id,
        "url": row[1],
        "publisher": "NVIDIA",
        "accessed_at": ACCESSED_AT,
        "evidence_locator": locator,
    }


def n(node_id: str, name: str, node_type: str, source_id: str, locator: str,
      children: list[dict] | None = None, *, state: str = "current",
      also: list[str] | None = None, notes: str | None = None) -> dict:
    result = {
        "id": node_id,
        "name": name,
        "node_type": node_type,
        "availability_state": state,
        "evidence": ev(source_id, locator),
    }
    if also:
        result["also_listed_under"] = also
    if notes:
        result["notes"] = notes
    if children:
        result["children"] = children
    return result


def leaves(prefix: str, names: list[str], node_type: str, source_id: str,
           locator: str, *, state: str = "current") -> list[dict]:
    return [n(f"{prefix}.{i:02d}", name, node_type, source_id, locator, state=state)
            for i, name in enumerate(names, 1)]


PRODUCTS = n("products", "Products", "category", "S001", "H1 Products; section headings and links, lines 38-129", [
    n("products.cloud", "Cloud Services", "category", "S001", "Cloud Services, lines 42-49", [
        n("products.cloud.bionemo", "BioNeMo", "platform", "S048", "Platforms > BioNeMo, lines 53-69", notes="The Products index label remains, but its link redirects to the healthcare industry page."),
        n("products.cloud.dgx_cloud", "DGX Cloud", "service", "S029", "H1 NVIDIA DGX Cloud and Overview, lines 18-49", [
            n("products.cloud.dgx_cloud.dsx_os", "DSX OS", "software", "S029", "NVIDIA DSX OS, lines 50-54"),
            n("products.cloud.dgx_cloud.exemplar", "Exemplar Cloud", "service", "S029", "NVIDIA Exemplar Cloud, lines 56-60"),
        ]),
        n("products.cloud.nemo", "NeMo", "platform", "S026", "H1 NVIDIA NeMo and What Is NVIDIA NeMo", [
            *leaves("products.cloud.nemo.build", ["NeMo Curator", "NeMo Data Designer", "NeMo Anonymizer", "NeMo Safe Synthesizer"], "software", "S026", "Features > Build tools"),
            *leaves("products.cloud.nemo.govern", ["NeMo Evaluator", "NeMo Guardrails", "NeMo Auditor"], "software", "S026", "Features > Evaluate, govern, and validate tools"),
        ]),
        n("products.cloud.omniverse_cloud", "Omniverse Cloud", "service", "S001", "Cloud Services, lines 42-49", state="index_listed_redirect_mismatch", notes="Current Products-index link resolves to DGX Cloud; retained as an index-listed name, not asserted as a distinct current service."),
        n("products.cloud.private_registry", "NGC Private Registry", "service", "S047", "Document title and user-guide scope"),
        n("products.cloud.ngc", "NVIDIA NGC", "service", "S030", "H1 NVIDIA NGC and catalog/service sections"),
    ]),
    n("products.data_center", "Data Center", "category", "S005", "H1 Data Center Products; Products/Architectures/Platforms", [
        n("products.data_center.current", "Current Data Center Product Portfolio", "category", "S005", "Products, lines 201-269", [
            *leaves("products.data_center.current", ["Vera Rubin NVL72", "Groq 3 LPX", "DGX Vera Rubin NVL72", "HGX Rubin NVL8", "DGX Rubin NVL8", "Vera CPU", "GB300 NVL72", "GB200 NVL72", "RTX PRO 4500 Blackwell Server Edition", "RTX PRO 6000 Blackwell Server Edition"], "product", "S005", "Products, lines 201-269"),
        ]),
        n("products.data_center.gpus_current", "Current Marketplace Data Center GPU Portfolio", "category", "S057", "Rendered GPU category page 1, seven listed products", [
            *leaves("products.data_center.gpus_current.item", ["RTX PRO 6000 Blackwell Server Edition", "RTX PRO 4500 Blackwell Server Edition", "H200", "H200 NVL", "L4", "L40", "L40S"], "product", "S057", "GPU category page 1 product cards"),
        ], notes="Current means displayed on the official NVIDIA Marketplace GPU category at cutoff; it is not a claim that older supported GPUs are discontinued."),
        n("products.data_center.gpus_supported", "Supported but Not in Current Marketplace GPU Page", "category", "S059", "Compare GPUs for Virtualization table", [
            *leaves("products.data_center.gpus_supported.item", ["H100", "H100 NVL", "A40", "A10", "A16"], "product", "S059", "Official virtualization GPU comparison", state="supported_not_current_marketplace_portfolio"),
        ], state="supported_not_current_marketplace_portfolio", notes="Retained to distinguish support evidence from current-portfolio evidence. Other driver-supported legacy GPUs are outside this product-tree boundary."),
        n("products.data_center.dgx", "DGX Platform", "platform", "S006", "H1 and Comprehensive AI Platform, lines 18-20 and 127-150", [
            *leaves("products.data_center.dgx.system", ["DGX SuperPOD", "DGX BasePOD", "DGX Spark", "DGX Station", "DGX Quantum"], "product", "S006", "Comprehensive AI Platform and Do More with DGX, lines 127-150 and 271-301"),
            n("products.data_center.dgx.cloud", "DGX Cloud", "service", "S006", "Do More with DGX > DGX Cloud, lines 279-306"),
            n("products.data_center.dgx.mission_control", "Mission Control", "software", "S006", "Comprehensive AI Platform > NVIDIA Mission Control, lines 144-150"),
        ]),
        n("products.data_center.hgx", "HGX Platform", "platform", "S007", "H1 and Overview, lines 18-46", [
            *leaves("products.data_center.hgx.system", ["HGX Vera Rubin NVL8", "HGX Rubin NVL8", "HGX B300", "HGX B200"], "product", "S007", "HGX Specifications, lines 80-147"),
        ]),
        n("products.data_center.mgx", "MGX", "reference_architecture", "S008", "Overview calls MGX an open modular reference architecture, lines 52-54"),
        n("products.data_center.stx", "STX", "reference_architecture", "S005", "Architectures > NVIDIA STX, lines 294-299"),
        n("products.data_center.ovx", "OVX Systems", "product", "S010", "H1 and overview, lines 20-22 and 52-55"),
        n("products.data_center.cpu", "CPU Platforms", "platform", "S009", "H1 NVIDIA CPU Platforms; Introduction, lines 20-22 and 46-53", [
            *leaves("products.data_center.cpu.item", ["Vera CPU", "Grace CPU Superchip", "Grace CPU C1", "GH200 Grace Hopper Superchip", "GB200 NVL4"], "product", "S009", "Explore the CPU Lineup, lines 78-117"),
        ]),
        n("products.data_center.virtual_gpu", "Virtual GPU", "software", "S044", "H1 and solution portfolio"),
        n("products.data_center.rtx_pro_server", "RTX PRO Servers", "platform", "S005", "Platforms > NVIDIA RTX PRO, lines 324-329"),
    ]),
    n("products.edge", "Embedded, Robotics, and Edge", "category", "S001", "Embedded Systems, lines 61-65", [
        n("products.edge.jetson", "Jetson Platform", "platform", "S012", "Jetson family introduction, lines 44-73", [
            *leaves("products.edge.jetson.series", ["Jetson Thor series", "Jetson AGX Orin series", "Jetson Orin NX series", "Jetson Orin Nano series", "Jetson AGX Xavier series", "Jetson Xavier NX series", "Jetson TX2 series", "Jetson Nano"], "product", "S012", "Discover the NVIDIA Jetson Family, lines 70-136"),
            n("products.edge.jetson.jetpack", "JetPack SDK", "sdk", "S012", "Jetson software and JetPack 7, lines 63-68"),
        ]),
        n("products.edge.igx", "IGX Platform", "platform", "S011", "Overview, lines 41-42", [
            n("products.edge.igx.thor", "IGX Thor", "product", "S011", "Introducing NVIDIA IGX Thor, lines 58-60 and 88-93"),
            n("products.edge.igx.halos_os", "Halos OS for IGX", "software", "S011", "Functional and AI Safety with Halos OS, lines 72-76"),
        ]),
        n("products.edge.drive", "DRIVE Platform", "platform", "S013", "Platform stack, lines 58-59", [
            *leaves("products.edge.drive.hardware", ["DRIVE Hyperion", "DRIVE AGX Thor", "DRIVE AGX Orin"], "product", "S013", "Hardware, lines 97-134"),
            *leaves("products.edge.drive.software", ["DRIVE AV", "DriveOS", "Alpamayo", "Halos"], "software", "S013", "Software and platform stack, lines 58-59 and 136-157"),
        ]),
        n("products.edge.isaac", "Isaac", "platform", "S015", "NVIDIA Isaac developer platform page", [
            *leaves("products.edge.isaac.item", ["Isaac GR00T", "Isaac Sim", "Isaac Lab", "Isaac ROS", "OSMO", "Newton"], "software", "S015", "Isaac platform, simulation, GR00T, and accelerated systems sections"),
        ]),
        n("products.edge.metropolis", "Metropolis", "platform", "S036", "H1 Metropolis and platform overview"),
        n("products.edge.clara_agx", "Clara AGX", "product", "S001", "Embedded Systems, lines 61-65", state="index_listed_redirect_mismatch", notes="The Products-index link redirects to Healthcare and Life Sciences rather than a distinct Clara AGX product page."),
    ]),
    n("products.networking", "Networking", "category", "S016", "Networking overview, lines 42-49 and Technology, lines 78-102", [
        n("products.networking.ethernet", "Spectrum Ethernet Platform", "platform", "S018", "H1 and platform definition, lines 18-20 and 44-47", [
            *leaves("products.networking.ethernet.item", ["Spectrum-X", "Spectrum-XGS", "Spectrum Ethernet Switch Systems", "ConnectX Ethernet SuperNICs", "BlueField DPUs", "LinkX Cables and Transceivers"], "product", "S018", "Complete Ethernet Solutions and Products, lines 44-78"),
        ]),
        n("products.networking.infiniband", "Quantum InfiniBand Platform", "platform", "S019", "H1 and Products, lines 18-20 and 60-90", [
            *leaves("products.networking.infiniband.item", ["Quantum-X800", "ConnectX InfiniBand Adapters", "BlueField DPUs", "Quantum InfiniBand Switches", "InfiniBand Routers and Gateways", "Long-Haul Systems"], "product", "S019", "Products, lines 54-94"),
        ]),
        n("products.networking.bluefield", "BlueField Platform", "platform", "S017", "H1 and portfolio, lines 18-20 and 70-88", [
            *leaves("products.networking.bluefield.item", ["BlueField-4 DPU", "BlueField-4 STX Storage Processor", "BlueField-3 DPU"], "product", "S017", "Portfolio, lines 70-88"),
        ]),
        n("products.networking.software", "Networking Software", "category", "S020", "Key Networking Software Offerings, lines 54-70", [
            *leaves("products.networking.software.item", ["DOCA", "DSX Air", "NetQ", "UFM", "Cumulus Linux", "Pure SONiC"], "software", "S020", "Key Networking Software Offerings, lines 54-88"),
        ]),
        n("products.networking.magnum", "Magnum IO", "software", "S021", "Magnum IO Optimization Stack, lines 27-29", [
            *leaves("products.networking.magnum.item", ["GPUDirect Storage", "NVMe SNAP", "GPUDirect RDMA", "HPC-X", "NCCL", "UCX", "SHARP", "NetQ", "UFM"], "technology", "S021", "Technologies Included, lines 32-78"),
        ]),
    ]),
    n("products.gaming", "Gaming and Creating", "category", "S001", "Gaming and Creating, lines 66-77", [
        n("products.gaming.geforce", "GeForce", "platform", "S041", "Official GeForce landing page", [
            n("products.gaming.geforce.cards", "Graphics Cards and Desktops", "category", "S022", "Products navigation, lines 22-30", [
                *leaves("products.gaming.geforce.cards.item", ["GeForce RTX 50 Series", "GeForce RTX 5090", "GeForce RTX 5080", "GeForce RTX 5070 Family", "GeForce RTX 5060 Family", "GeForce RTX 5050"], "product", "S022", "Graphics Cards & Desktops navigation, lines 22-30"),
            ]),
            *leaves("products.gaming.geforce.mobile", ["GeForce RTX 50 Series Laptops", "GeForce RTX 40 Series Laptops"], "product", "S022", "Laptops navigation, lines 31-35"),
            *leaves("products.gaming.geforce.tech", ["DLSS", "Reflex", "G-SYNC", "Max-Q", "RTX Remix"], "technology", "S022", "Games & Tech navigation, lines 39-59"),
        ]),
        n("products.gaming.geforce_now", "GeForce NOW", "service", "S001", "Gaming and Creating, lines 66-77"),
        n("products.gaming.studio", "NVIDIA Studio", "platform", "S001", "Gaming and Creating, lines 66-77"),
        n("products.gaming.nvidia_app", "NVIDIA App", "software", "S042", "H1 NVIDIA App for Gamers and Creators"),
        n("products.gaming.broadcast", "NVIDIA Broadcast", "software", "S001", "Gaming and Creating, lines 66-77"),
        n("products.gaming.shield", "SHIELD TV", "product", "S043", "H1 NVIDIA SHIELD"),
        n("products.gaming.rtx_ai_pc", "RTX AI PCs", "solution", "S001", "Gaming and Creating > RTX PCs, lines 66-77"),
    ]),
    n("products.proviz", "Professional Visualization and Workstations", "category", "S037", "NVIDIA RTX PRO Workstations page", [
        n("products.proviz.rtx_desktop", "RTX PRO Desktop GPUs", "category", "S023", "Compare > NVIDIA RTX PRO Desktop Solutions, lines 108-138", [
            *leaves("products.proviz.rtx_desktop.blackwell", ["RTX PRO 6000 Blackwell Workstation Edition", "RTX PRO 6000 Blackwell Max-Q Workstation Edition", "RTX PRO 5000 Blackwell", "RTX PRO 4500 Blackwell Workstation Edition", "RTX PRO 4000 Blackwell", "RTX PRO 4000 Blackwell SFF Edition", "RTX PRO 2000 Blackwell"], "product", "S023", "Blackwell desktop comparison, lines 108-138"),
            *leaves("products.proviz.rtx_desktop.ada", ["RTX 6000 Ada", "RTX 5000 Ada", "RTX 4500 Ada", "RTX 4000 Ada", "RTX 4000 SFF Ada", "RTX 2000 Ada"], "product", "S023", "Ada Lovelace desktop comparison beginning lines 139-158", state="current_or_legacy_listed"),
        ]),
        n("products.proviz.rtx_laptop", "RTX PRO Laptop GPUs", "product", "S024", "Official professional laptop lineup"),
        n("products.proviz.dgx_spark", "DGX Spark", "product", "S045", "H1 Personal AI Supercomputer Powered by Blackwell"),
        n("products.proviz.dgx_station", "DGX Station", "product", "S046", "H1 Personal AI Supercomputer"),
    ]),
])


SOFTWARE_GROUPS = [
    ("ai.training", "AI Training and Inference Frameworks", ["Dynamo", "NeMo Framework", "Nemotron", "NIM Microservices"], "software"),
    ("ai.physical", "Physical AI", ["Autonomous Vehicles Dataset", "CAE", "Omniverse", "Isaac", "Isaac Sim", "DRIVE", "Cosmos"], "software"),
    ("ai.interactivity", "Interactivity Systems", ["Riva"], "software"),
    ("sdk", "SDKs and Application-Specific Frameworks", ["Maxine", "cuLitho", "Morpheus", "RAPIDS", "HPC SDK", "Merlin", "Aerial", "Metropolis"], "sdk"),
    ("tools", "Productivity Apps and Tools", ["Omniverse", "AI Workbench", "DCGM / GPU Monitoring", "NVIDIA App", "NVIDIA App for Enterprise", "RTX Desktop Manager", "Maxine Video Conferencing"], "software"),
    ("cloud", "Cloud Services", ["Base Command Manager", "BioNeMo", "Fleet Command", "NeMo", "NGC Catalog", "Omniverse"], "service"),
    ("developer", "Developer Software", ["CUDA Toolkit", "NVIDIA FLARE", "Texture Tools Exporter", "Nsight Developer Tools"], "sdk"),
    ("gaming", "Gaming and Creating Software", ["NVIDIA Studio", "GeForce NOW", "RTX Remix", "NVIDIA App", "NVIDIA Broadcast", "SHIELD Software"], "software"),
    ("health", "Healthcare and Life Sciences", ["BioNeMo", "Clara", "Holoscan SDK", "MONAI", "Parabricks", "NVIDIA FLARE"], "software"),
    ("infra", "Infrastructure", ["Cloud Native Support", "Base Command Manager", "Slinky", "Fleet Command", "Magnum IO", "Networking Software", "NVIDIA AI Enterprise", "Slurm", "Virtual GPU", "Mission Control", "Run:ai"], "software"),
    ("drivers", "Drivers", ["NVIDIA Drivers", "Ethernet Drivers", "GeForce Game Ready Drivers", "NVIDIA Studio Drivers", "InfiniBand Drivers", "NVIDIA Control Panel", "RTX Enterprise Drivers"], "software"),
]


SOFTWARE = n("software", "Software and Services", "category", "S002", "H1 NVIDIA Software; sections lines 21-187", [
    n(f"software.{slug}", title, "category", "S002", f"{title} section", leaves(f"software.{slug}.item", names, typ, "S002", f"{title} section"))
    for slug, title, names, typ in SOFTWARE_GROUPS
] + [
    n("software.ai_models", "AI Models by Use Case", "category", "S002", "AI Models By Use Case, lines 42-62", [
        *leaves("software.ai_models.item", ["Code Generation", "Digital Twins", "Drug Discovery", "Image Generation", "Image-to-Embedding", "Image-to-Text", "Medical Imaging", "Object Detection", "Optical Character Recognition", "Retrieval-Augmented Generation", "Route Optimization", "Speech-to-Animation", "Speech-to-Text", "Synthetic Data Generation", "Text Translation", "Text-to-Embedding", "Text-to-Image", "Text-to-Speech", "Weather Simulation"], "solution", "S002", "AI Models By Use Case, lines 42-62"),
    ]),
    n("software.ai_enterprise", "NVIDIA AI Enterprise", "platform", "S040", "Enterprise software index and NVIDIA AI Enterprise listing"),
    n("software.build", "NVIDIA Build", "service", "S049", "Public API catalog and Blueprints landing", [
        n("software.build.nim_api", "NIM APIs", "service", "S049", "API catalog"),
        n("software.build.blueprints", "NVIDIA Blueprints", "reference_architecture", "S049", "Blueprints catalog"),
    ]),
])


SOLUTION_SECTIONS = [
    ("ai", "Artificial Intelligence", ["AI Overview", "AI Platform", "Conversational AI", "Cybersecurity", "Data Analytics", "Generative / Agentic AI", "Inference", "Machine Learning", "Predictions and Forecasting", "AI Workflows"]),
    ("cloud_dc", "Cloud and Data Center", ["Cloud and Data Center Overview", "Accelerated Computing", "Cloud Computing", "Colocation", "MLOps", "Networking", "Virtualization"]),
    ("design", "Design and Simulation", ["Design and Simulation Overview", "Computer-Aided Engineering", "Digital Twin Development", "Rendering", "Robotic Simulation", "Scientific Visualization", "Vehicle Simulation"]),
    ("robotics", "Robotics and Edge AI", ["Robotics and Edge AI Overview", "Robotics", "Edge AI", "Vision AI"]),
    ("hpc", "High-Performance Computing", ["HPC Overview", "HPC and AI", "Scientific Visualization", "Simulation and Modeling", "Quantum Computing"]),
    ("av", "Autonomous Vehicles", ["Autonomous Vehicles Overview", "In-Vehicle Computing", "AI Training", "AV Simulation", "Safety"]),
    ("industry", "Industry Solutions (Solutions Index)", ["Architecture, Engineering, Construction", "Automotive", "Consumer Internet", "Cybersecurity", "Energy", "Financial Services", "Healthcare and Life Sciences", "Higher Education", "Game Development", "Industrial Sector", "Manufacturing", "Media and Entertainment", "Government", "Restaurants", "Retail and CPG"]),
]


SOLUTIONS = n("solutions", "Solutions", "category", "S003", "H1 Solutions; sections lines 21-94", [
    n(f"solutions.{slug}", title, "category", "S003", f"{title} section", leaves(f"solutions.{slug}.item", names, "solution", "S003", f"{title} section"))
    for slug, title, names in SOLUTION_SECTIONS
])


INDUSTRY_NAMES = [
    "Architecture, Engineering, Construction, and Operations", "Automotive", "Energy", "Financial Services",
    "Government", "Healthcare and Life Sciences", "Higher Education and Research", "Industrial Sector",
    "Media and Entertainment", "Restaurants and Quick-Service", "Retail and Consumer Packaged Goods",
    "Robotics", "Semiconductor", "Telecommunications",
]


INDUSTRIES = n("industries", "Industries", "category", "S004", "Our Industries, lines 42-67",
               leaves("industries.item", INDUSTRY_NAMES, "industry", "S004", "Our Industries, lines 42-67"))


ARCHITECTURES = n("architectures", "Architectures and Core Technologies", "category", "S031", "NVIDIA Technologies categories, lines 20-28", [
    *leaves("architectures.current", ["Vera Rubin", "Blackwell", "Hopper", "Ada Lovelace"], "architecture", "S005", "Architectures, lines 270-299"),
    n("architectures.mgx", "MGX", "reference_architecture", "S005", "Architectures > NVIDIA MGX, lines 287-292"),
    n("architectures.stx", "STX", "reference_architecture", "S005", "Architectures > NVIDIA STX, lines 294-299"),
    *leaves("architectures.tech", ["CUDA", "CUDA-X", "NVLink", "NVLink Switch", "NVLink-C2C", "NVLink Fusion", "Tensor Cores", "Multi-Instance GPU", "Confidential Computing", "RTX", "DLSS", "G-SYNC", "OpenUSD"], "technology", "S031", "Enterprise & Developer, Gaming, and Industry Technologies"),
])


TREE = {
    "metadata": {
        "research_subject": "NVIDIA official product, platform, service, solution, and industry taxonomy",
        "company_entity": "NVIDIA Corporation",
        "security_identifier": "NASDAQ: NVDA",
        "cutoff_date": CUTOFF,
        "accessed_at": ACCESSED_AT,
        "scope": "Current public official NVIDIA index and portfolio pages reachable without authentication; normalized at named product-family/portfolio level.",
        "not_in_scope": "Partner entities, relationships, filings, individual NGC/build model artifacts, documentation leaf pages, regional store SKUs, accessories, discontinued products absent from current indexes, and an unbounded crawl of every nvidia.com URL.",
        "node_type_definitions": {
            "product": "Named sellable/deployable hardware or system family/SKU shown in an official portfolio.",
            "platform": "Integrated hardware/software or development/operating platform.",
            "service": "Cloud-hosted, catalog, API, subscription, or managed access offering.",
            "software": "Named application, framework, library suite, driver, or infrastructure software.",
            "sdk": "Developer kit or application-specific framework primarily exposed as developer software.",
            "solution": "Use-case or workload-oriented NVIDIA solution page, not necessarily a separately sold SKU.",
            "industry": "Vertical-market solution entry from the current Industries index.",
            "reference_architecture": "Blueprint/design specification intended for partners or implementers rather than a single NVIDIA-built product.",
            "architecture": "Named compute/GPU platform generation or system architecture.",
            "technology": "Enabling technology that can appear across multiple products.",
            "category": "Navigation/normalization container; not itself a product conclusion.",
        },
        "completeness_basis": "All names exposed by the current Products, Software, Solutions, and Industries index pages were processed; key portfolio pages were expanded to named families/items. Completeness is not claimed below the stated family/portfolio boundary.",
    },
    "roots": [PRODUCTS, SOFTWARE, SOLUTIONS, INDUSTRIES, ARCHITECTURES],
}


def flatten(node: dict, parent_id: str | None = None, path: list[str] | None = None):
    path = (path or []) + [node["name"]]
    item = {k: v for k, v in node.items() if k != "children"}
    item["parent_id"] = parent_id
    item["path"] = path
    # A stable grouping key keeps official cross-listings auditable without
    # pretending that every navigation occurrence is a distinct product.
    canonical = re.sub(r"[^a-z0-9]+", "-", node["name"].lower()).strip("-")
    item["canonical_key"] = canonical
    yield item
    for child in node.get("children", []):
        yield from flatten(child, node["id"], path)


def render(node: dict, depth: int = 0) -> list[str]:
    marker = "  " * depth + "- "
    line = f"{marker}{node['name']}  _[{node['node_type']}; {node['availability_state']}]_"
    lines = [line]
    for child in node.get("children", []):
        lines.extend(render(child, depth + 1))
    return lines


PRIMARY_TYPE_OVERRIDES = {
    "dgx-cloud": "service", "shield-tv": "product",
    "nvidia-app": "software", "nvidia-broadcast": "software",
    "nvidia-studio": "platform", "rtx-ai-pcs": "solution",
    "nemo": "platform", "bionemo": "platform", "isaac": "platform",
    "metropolis": "platform", "omniverse": "platform",
    "virtual-gpu": "software",
}

TYPE_PRIORITY = [
    "product", "service", "platform", "reference_architecture", "software",
    "sdk", "solution", "architecture", "technology", "industry",
]

ALIASES = {
    "dgx-cloud": ["NVIDIA DGX Cloud"],
    "shield-tv": ["NVIDIA SHIELD TV", "NVIDIA SHIELD"],
    "nvidia-app": ["NVIDIA app"],
    "nvidia-broadcast": ["NVIDIA Broadcast App"],
    "nvidia-studio": ["Studio"],
    "rtx-ai-pcs": ["RTX PCs", "GeForce RTX AI PCs"],
    "nemo": ["NVIDIA NeMo", "NeMo LLM"],
    "bionemo": ["NVIDIA BioNeMo"],
    "isaac": ["NVIDIA Isaac"],
    "metropolis": ["NVIDIA Metropolis"],
    "omniverse": ["NVIDIA Omniverse"],
    "h200": ["NVIDIA H200", "H200 SXM"],
    "h200-nvl": ["NVIDIA H200 NVL"],
    "l40s": ["NVIDIA L40S"], "l40": ["NVIDIA L40"], "l4": ["NVIDIA L4"],
}


def build_canonical_index(flat: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for item in flat:
        if item["node_type"] != "category":
            grouped.setdefault(item["canonical_key"], []).append(item)
    result = []
    for key, rows in sorted(grouped.items()):
        observed_types = sorted({row["node_type"] for row in rows})
        primary_type = PRIMARY_TYPE_OVERRIDES.get(key)
        if primary_type is None:
            primary_type = next((kind for kind in TYPE_PRIORITY if kind in observed_types), observed_types[0])
        result.append({
            "canonical_key": key,
            "primary_name": rows[0]["name"],
            "primary_type": primary_type,
            "aliases": sorted(set(ALIASES.get(key, [])) - {rows[0]["name"]}),
            "observed_types": observed_types,
            "type_conflict": len(observed_types) > 1,
            "type_resolution": "manual_override" if key in PRIMARY_TYPE_OVERRIDES else "type_priority",
            "availability_states": sorted({row["availability_state"] for row in rows}),
            "node_ids": [row["id"] for row in rows],
            "paths": [row["path"] for row in rows],
            "evidence": [row["evidence"] for row in rows],
        })
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    flat = [item for root in TREE["roots"] for item in flatten(root)]
    canonical_index = build_canonical_index(flat)
    counts = Counter(item["node_type"] for item in flat)
    canonical_count = len(canonical_index)
    TREE["metadata"]["node_count"] = len(flat)
    TREE["metadata"]["canonical_non_category_name_count"] = canonical_count
    TREE["metadata"]["node_type_counts"] = dict(sorted(counts.items()))

    (OUT / "product_taxonomy.json").write_text(json.dumps(TREE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "product_tree.json").write_text(json.dumps(TREE, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (OUT / "product_taxonomy.jsonl").open("w", encoding="utf-8") as fh:
        for item in flat:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    with (OUT / "canonical_index.jsonl").open("w", encoding="utf-8") as fh:
        for item in canonical_index:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    with (OUT / "source_frontier.jsonl").open("w", encoding="utf-8") as fh:
        for source_id, url, title, parent_path, discovered_from, status, note in SOURCES:
            fh.write(json.dumps({
                "source_id": source_id,
                "url": url,
                "title": title,
                "publisher": "NVIDIA",
                "parent_path": parent_path,
                "discovered_from": discovered_from,
                "accessed_at": ACCESSED_AT,
                "access_status": status,
                "access_or_license_note": "Public HTTPS; no login/paywall/captcha bypass; no restricted content retained. " + note,
            }, ensure_ascii=False) + "\n")

    md = [
        "# NVIDIA 官方产品树（研究截点 2026-08-25）",
        "",
        f"树中导航节点：**{len(flat)}**；去除 category 后按规范名合并为 **{canonical_count}** 个 canonical 名称；官方 frontier 页面：**{len(SOURCES)}**。节点类型统计：" +
        "，".join(f"{k}={v}" for k, v in sorted(counts.items())) + "。",
        "",
        "本树以 NVIDIA 当前官方 Products、Software、Solutions、Industries 四个索引为封闭入口，并展开关键组合页到命名产品族/产品项。树保留官方交叉列示，因此导航节点数不是独立产品数；机器文件用 `canonical_key` 将同名对象合并，防止把跨栏目出现误算成多个独立产品。",
        "",
        "## 树",
        "",
    ]
    for root in TREE["roots"]:
        md.extend(render(root))
        md.append("")
    md += [
        "## 完整性判据",
        "",
        "本轮 `frontier complete` 的含义是：四个当前官方总索引的所有栏目和列名均已形成节点或明确的交叉/异常记录；Data Center、DGX/HGX/MGX/CPU、Jetson/IGX/DRIVE/Isaac、Networking、GeForce/RTX PRO、NeMo/NIM/Dynamo 等组合页已展开到页面明确列示的产品族或产品项；每个节点均有官方 URL、访问时间和 locator；frontier 中没有 `pending` 状态。",
        "",
        "它不表示对整个 nvidia.com 做无限深度抓取，也不表示枚举 Build/NGC 中持续变化的每个模型、容器、API、驱动版本、地区商店 SKU、配件或历史停产型号。那些边界若要纳入，应单独建立有版本/分页上限的子 frontier。",
        "",
        "## 已知盲区和异常",
        "",
        "- NVIDIA 网站高度动态且依赖 JavaScript；本轮使用公开可渲染内容，不绕过任何访问控制。直接 `robots.txt` 请求曾被对端 reset，因此没有据此扩张自动抓取；改用公开搜索索引和 NVIDIA 页面内链接。",
        "- Products 索引存在导航陈旧或目标合并：`BioNeMo` 与 `Clara AGX` 链接落到 Healthcare and Life Sciences；`Omniverse Cloud` 落到 DGX Cloud。三者保留 `index_listed_redirect_mismatch`/说明，不把重定向当作独立产品存续的强证据。",
        "- GeForce NOW 的 en-US 链接在访问环境中重定向到 en-AU，产品名仍由美国 Products 索引确认；未采集地区价格/套餐。",
        "- RTX PRO、Jetson 页面同时展示当代与旧代仍列示产品；旧代项标注 `current_or_legacy_listed`，不能仅凭在页面出现断言仍在产。",
        "- 数据中心 GPU 的 `current` 口径取自截点时 NVIDIA Marketplace GPU 分类页，并由 2025-08 官方 line card 交叉验证；H100/H100 NVL 与 A40/A10/A16 在官方支持/虚拟化比较页仍出现，但不在该 current Marketplace 页，因此单列为 `supported_not_current_marketplace_portfolio`。这不是停产判断。",
        "- 2026 年页面已出现 Vera Rubin、Rubin、Groq 3 LPX 等新组合；它们是截点时当前页面事实，不应回填为 2025 年历史事实。",
        "- 产品与平台边界是研究规范化判断。例如 DGX 是平台，具体 DGX 系统是产品；MGX/STX 是参考架构；CUDA/NVLink 是技术；NIM/NeMo/Dynamo 是软件或平台。原始官方措辞与 locator 均保留，便于 reviewer 调整分类。",
        "",
        "## 文件",
        "",
        "- `product_taxonomy.json`：嵌套产品树、类型定义和范围元数据。",
        "- `product_taxonomy.jsonl`：每行一个规范化节点，含父节点、路径和证据。",
        "- `canonical_index.jsonl`：每行一个 canonical 对象，含主类型、别名、全部路径、冲突处理和证据。",
        "- `source_frontier.jsonl`：每行一个已处理官方入口/组合页。",
        "- `build_taxonomy.py`：可复现生成脚本。",
        "- `validate_taxonomy.py`：ID、provenance、canonical、关键类型与 GPU 状态校验。",
    ]
    (OUT / "PRODUCT_TREE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (OUT / "product_tree.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    readme = f"""# product_tree agent output\n\nThis directory contains the NVIDIA official product-tree snapshot at {CUTOFF}.\n\n- `product_tree.md`: human-readable tree and scope/limitations.\n- `product_tree.json`: nested machine-readable tree.\n- `product_taxonomy.jsonl`: flat one-node-per-line form with `parent_id`, `path`, `canonical_key`, and evidence locator.\n- `canonical_index.jsonl`: canonical objects with `primary_type`, aliases, all observed paths, and conflict resolution.\n- `source_frontier.jsonl`: {len(SOURCES)} reviewed public official pages.\n- `build_taxonomy.py`: deterministic generator.\n- `validate_taxonomy.py`: provenance, canonical, type, and GPU-state checks.\n\nReproduce and validate with:\n\n```bash\npython3 build_taxonomy.py\npython3 -m json.tool product_tree.json >/dev/null\npython3 validate_taxonomy.py\n```\n\nThe build performs no network requests. It reproduces the frozen, manually verified snapshot. Refreshing the evidence requires a new dated run because NVIDIA pages are dynamic. No credentials or restricted content are used.\n\nCurrent data-center GPU portfolio is defined by the official NVIDIA Marketplace GPU category at the cutoff and corroborated by the August 2025 line card. H100/H100 NVL and A40/A10/A16 are retained separately as `supported_not_current_marketplace_portfolio`; support evidence is not treated as current-portfolio evidence.\n"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()
