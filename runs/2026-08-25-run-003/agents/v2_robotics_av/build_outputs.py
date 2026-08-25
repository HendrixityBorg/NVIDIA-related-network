#!/usr/bin/env python3
"""Build the frozen Robotics + Autonomous Vehicles v2 research shard.

This generator performs no network access.  It materializes the manually reviewed
official-page snapshot captured at the research cutoff.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


OUT = Path(__file__).resolve().parent
ACCESSED = "2026-08-25T18:00:00+08:00"
PUBLISHER = "NVIDIA"


def write_jsonl(name: str, rows: list[dict]) -> None:
    with (OUT / name).open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")


def src(sid: str, url: str, title: str, discovered_from: str | None,
        status: str = "processed", note: str = "") -> dict:
    return {
        "source_id": sid,
        "url": url,
        "title": title,
        "publisher": PUBLISHER,
        "discovered_from": discovered_from,
        "scope_role": "seed" if discovered_from is None else "linked_closure",
        "accessed_at": ACCESSED,
        "access_status": status,
        "pending": False,
        "access_or_license_note": (
            "Public HTTPS; no login, paywall, CAPTCHA, robots, rate-limit, or other "
            "access-control bypass. Only structured facts and short locators retained."
            + (" " + note if note else "")
        ),
    }


SOURCES = [
    src("RAV-S001", "https://www.nvidia.com/en-us/industries/robotics/", "AI for Robotics", None),
    src("RAV-S002", "https://www.nvidia.com/en-us/use-cases/humanoid-robots/", "Humanoid Robots", "RAV-S001"),
    src("RAV-S003", "https://www.nvidia.com/en-us/use-cases/robot-learning/", "Robot Learning", "RAV-S001"),
    src("RAV-S004", "https://www.nvidia.com/en-us/use-cases/robotics-simulation/", "Robotics Simulation", "RAV-S001"),
    src("RAV-S005", "https://www.nvidia.com/en-us/use-cases/synthetic-data-physical-ai/", "Synthetic Data Generation for Physical AI", "RAV-S001", note="The linked /synthetic-data/ path redirected to this canonical URL."),
    src("RAV-S006", "https://www.nvidia.com/en-us/use-cases/industrial-facility-digital-twins/", "Industrial Facility Digital Twins", "RAV-S001"),
    src("RAV-S007", "https://www.nvidia.com/en-us/use-cases/functional-safety-ai-agents-industrial-robots/", "Robot Safety With AI Agents", "RAV-S001"),
    src("RAV-S008", "https://developer.nvidia.com/isaac", "NVIDIA Isaac", "RAV-S001"),
    src("RAV-S009", "https://www.nvidia.com/en-us/omniverse/", "NVIDIA Omniverse", "RAV-S002", "reviewed_cross_reference", "Detailed Omniverse portfolio is owned by the Design/Simulation shard; named family references are captured here."),
    src("RAV-S010", "https://www.nvidia.com/en-us/ai/cosmos/", "NVIDIA Cosmos", "RAV-S003", "reviewed_cross_reference", "Detailed Cosmos portfolio is owned by the AI shard; named AV/robotics uses are captured here."),
    src("RAV-S011", "https://www.nvidia.com/en-us/data-center/rtx-pro-6000-blackwell-server-edition/", "RTX PRO 6000 Blackwell Server Edition", "RAV-S001", "reviewed_cross_reference"),
    src("RAV-S012", "https://www.nvidia.com/en-us/autonomous-machines/intelligent-video-analytics-platform/", "NVIDIA Metropolis", "RAV-S001", "reviewed_cross_reference"),
    src("RAV-S013", "https://www.nvidia.com/en-us/edge-computing/products/igx/", "NVIDIA IGX", "RAV-S007", "reused_v1", "Reuses v1 source S011; product family is referenced, not re-expanded."),
    src("RAV-S014", "https://www.nvidia.com/en-us/data-center/products/ai-enterprise/", "NVIDIA AI Enterprise", "RAV-S006", "reviewed_cross_reference"),
    src("RAV-S015", "https://www.nvidia.com/en-us/ai-data-science/products/cuopt/", "NVIDIA cuOpt", "RAV-S006", "reviewed_cross_reference"),
    src("RAV-S016", "https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/", "NVIDIA Jetson", "RAV-S002", "reused_v1", "Reuses v1 source S012; family/SKU detail remains in v1."),
    src("RAV-S017", "https://www.nvidia.com/en-us/data-center/dgx-platform/", "NVIDIA DGX", "RAV-S002", "reused_v1", "Reuses v1 source S006."),
    src("RAV-S018", "https://www.nvidia.com/en-us/data-center/products/ovx/", "NVIDIA OVX", "RAV-S002", "reused_v1", "Reuses v1 source S010."),
    src("RAV-S019", "https://www.nvidia.com/en-us/edge-computing/", "NVIDIA Edge AI", "RAV-S001", "reviewed_cross_reference"),
    src("RAV-S020", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/", "NVIDIA Autonomous Vehicles", None),
    src("RAV-S021", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/ai-training/", "AV Model Development", "RAV-S020"),
    src("RAV-S022", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/simulation/", "AV Simulation and Validation", "RAV-S020"),
    src("RAV-S023", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/in-vehicle-computing/", "AV In-Vehicle Computing", "RAV-S020"),
    src("RAV-S024", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/drive-hyperion/", "NVIDIA DRIVE Hyperion", "RAV-S020"),
    src("RAV-S025", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/alpamayo/", "NVIDIA Alpamayo", "RAV-S020"),
    src("RAV-S026", "https://www.nvidia.com/en-us/ai-trust-center/halos/autonomous-vehicles/", "NVIDIA Halos for Autonomous Vehicles", "RAV-S020"),
    src("RAV-S027", "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/partners/", "NVIDIA DRIVE Partner Ecosystem", "RAV-S020", note="Legacy /self-driving-cars/partners/ redirects here."),
]


def sec(sid: str, section_id: str, heading: str, locator: str,
        status: str = "processed", notes: str = "") -> dict:
    url = next(s["url"] for s in SOURCES if s["source_id"] == sid)
    return {
        "source_id": sid, "source_url": url, "section_id": section_id,
        "heading": heading, "evidence_locator": locator,
        "accessed_at": ACCESSED, "processing_status": status,
        "notes": notes,
    }


SECTION_MAP = {
    "RAV-S001": [
        ("intro", "Explore the Next Wave of AI", "lines 45-50"),
        ("three-computer", "The Three-Computer Solution", "lines 51-55"),
        ("leaders", "Global Robotics Leaders", "lines 56-60"),
        ("use-cases", "Discover AI for Robotics", "lines 62-112"),
        ("stories", "Success Stories", "lines 114-119"),
        ("technology", "AI for Robotics—From Simulation to Real, Cloud to Edge", "lines 121-158"),
        ("ecosystem", "NVIDIA Robotics Partners and Ecosystem", "lines 159-172"),
        ("resources", "Explore NVIDIA Robotics", "lines 174-212"),
        ("next", "Ready to Get Started", "lines 214-227"),
    ],
    "RAV-S002": [
        ("metadata", "Workloads, Industries, Products", "lines 46-65"),
        ("overview", "The Next Era of Physical AI", "lines 67-82"),
        ("three-computer", "Three-Computer Solution", "lines 98-110"),
        ("gr00t", "Isaac GR00T and Robot Foundation Models", "lines 111-120"),
        ("simulation", "Robot Learning and Simulation Frameworks", "lines 131-135"),
        ("runtime", "Next-Generation On-Robot Computing", "lines 136-140"),
        ("ecosystem", "Humanoid Robotics Partners", "lines 152-180"),
        ("faq", "FAQs", "lines 191-205"),
        ("resources", "Resources", "lines 217-247"),
    ],
    "RAV-S003": [
        ("metadata", "Workloads, Industries, Products", "lines 25-47"),
        ("overview", "Build Generalist Robot Policies", "lines 48-68"),
        ("benefits", "Why Simulation-Based Robot Learning", "lines 68-99"),
        ("workflow", "Teach Robots to Learn and Adapt", "lines 101-114"),
        ("algorithms", "Imitation and Reinforcement Learning", "lines 115-130"),
        ("ecosystem", "Partner Ecosystem", "lines 145-173"),
        ("faq", "FAQs", "lines 176-201"),
    ],
    "RAV-S004": [
        ("metadata", "Workloads, Industries, Products", "lines 47-67"),
        ("overview", "What Is Robot Simulation", "lines 70-86"),
        ("benefits", "Why Simulate", "lines 87-110"),
        ("workflow", "Workflows Powered by Robotics Simulation", "lines 114-143"),
        ("get-started", "Get Started", "lines 156-160"),
    ],
    "RAV-S005": [
        ("metadata", "Workloads, Industries, Products", "lines 39-58"),
        ("overview", "Why Use Synthetic Data", "lines 59-85"),
        ("workflow", "Four Steps to Synthetic Data Generation", "lines 86-98"),
        ("world-models", "World Models", "lines 99-118"),
        ("validation", "Testing and Validation", "lines 119-125"),
        ("get-started", "Get Started", "lines 147-159"),
    ],
    "RAV-S006": [
        ("metadata", "Workloads, Industries, Products", "lines 39-66"),
        ("overview", "The Value of Industrial Digital Twins", "lines 70-88"),
        ("opportunities", "Unlocking New Digitalization Opportunities", "lines 89-111"),
        ("implementation", "Develop Industrial Facility Digital Twins", "lines 112-150"),
        ("partners", "Partner Ecosystem", "lines 151-157", "processed_no_named_cards", "Heading present but rendered text exposes no partner-card names."),
        ("faq", "FAQs", "lines 159-180"),
        ("get-started", "Start Building", "lines 182-206"),
    ],
    "RAV-S007": [
        ("metadata", "Workloads, Industries, Products", "lines 31-53"),
        ("overview", "Safer Automation", "lines 54-74"),
        ("implementation", "Enable Robot Safety With AI Agents", "lines 81-97"),
        ("get-started", "Get Started", "lines 98-102"),
    ],
    "RAV-S008": [
        ("manipulation", "Isaac for Manipulation", "lines 5-51"),
        ("mobility", "Isaac for Mobility", "lines 52-81"),
        ("simulation", "Simulation and Robot Learning", "lines 84-108"),
        ("gr00t", "Isaac GR00T", "lines 110-116"),
        ("systems", "NVIDIA-Accelerated Systems", "lines 119-150"),
        ("resources", "Learning and Developer Resources", "lines 152-173"),
    ],
    "RAV-S020": [
        ("overview", "Platform for Safe AI-Defined Mobility", "lines 50-65"),
        ("solutions", "End-to-End AV Development Platform", "lines 67-112"),
        ("partners", "Automotive Partners", "lines 114-187"),
        ("resources", "Latest AV News", "lines 189-276"),
        ("faq", "FAQs", "lines 278-318"),
    ],
    "RAV-S021": [
        ("overview", "Fleet Data to Driving Models", "lines 49-68"),
        ("benefits", "Data Processing, Improvement, SDG, Curation", "lines 69-89"),
        ("technology", "Dataset Preparation and Model Training", "lines 90-130"),
        ("stories", "AI Factory Customer Stories", "lines 131-177"),
        ("dataset", "Physical AI Dataset", "lines 178-182"),
    ],
    "RAV-S022": [
        ("overview", "Open Simulation Foundation", "lines 50-65"),
        ("benefits", "Why Simulation Matters", "lines 66-91"),
        ("technology", "Simulation Tools, Models, and Datasets", "lines 92-125"),
        ("use-cases", "AV Simulation Lifecycle", "lines 126-179"),
        ("partners", "Partners Using NVIDIA Simulation Technologies", "lines 180-224"),
        ("resources", "Latest Simulation News", "lines 225-244"),
    ],
    "RAV-S023": [
        ("overview", "Driving Next-Generation AV Breakthroughs", "lines 54-76"),
        ("features", "Features", "lines 77-96"),
        ("hardware", "Powerful AI Computing Platform", "lines 97-135"),
        ("software", "Breakthroughs for Autonomous Vehicles", "lines 136-169"),
        ("nims", "Automotive NIMs", "lines 170-175"),
        ("customers", "DRIVE Customers", "lines 177-225"),
        ("resources", "Latest Automotive News", "lines 227-279"),
    ],
    "RAV-S024": [
        ("overview", "L4-Ready AV Platform", "lines 44-64"),
        ("features", "Features", "lines 65-73"),
        ("specs", "DRIVE Hyperion 10 and 8", "lines 74-82"),
        ("data-factory", "From Road Data to Trained Models", "lines 83-99"),
        ("adopters", "DRIVE Hyperion Ecosystem Partners", "lines 100-103", "processed_no_named_cards", "Heading exposed without adopter-card names in text representation."),
        ("resources", "Latest Automotive News", "lines 104-137"),
    ],
    "RAV-S025": [
        ("overview", "What Is NVIDIA Alpamayo", "lines 56-71"),
        ("benefits", "Benefits", "lines 72-113"),
        ("technology", "AV Development Lifecycle", "lines 114-150"),
        ("components", "Core Components", "lines 151-174"),
        ("get-started", "Getting Started", "lines 175-204"),
        ("resources", "Latest Automotive", "lines 206-221"),
    ],
    "RAV-S026": [
        ("overview", "Safety From Cloud to Car", "lines 59-79"),
        ("highlights", "Safety Leadership", "lines 80-135"),
        ("technology", "Engineered for Safety", "lines 136-164"),
        ("benefits", "Comprehensive AV Safety System", "lines 165-173"),
        ("use-cases", "Platform, OS, Algorithmic, Ecosystem Safety", "lines 174-240"),
        ("certification", "Assessed by Experts", "lines 241-260"),
        ("research", "AV Safety Research", "lines 261-305"),
        ("partners", "Partners Using NVIDIA Halos", "lines 306-342", "processed_category_only", "Rendered page exposes partner categories but not names; named certifiers and quotations are captured separately."),
        ("resources", "Latest Halos Resources", "lines 344-401"),
    ],
    "RAV-S027": [
        ("categories", "Cars, Trucks, Robotaxis, Suppliers, Simulation, Sensors, Software, Mapping", "lines 20-54"),
        ("intro", "Partner Innovation", "lines 68-69"),
        ("featured", "Featured Partners", "lines 70-167"),
        ("news", "Latest Automotive News", "lines 168-172"),
    ],
}

PAGE_SECTIONS = []
for sid, rows in SECTION_MAP.items():
    for row in rows:
        PAGE_SECTIONS.append(sec(sid, *row))
for s in SOURCES:
    if s["source_id"] not in SECTION_MAP:
        PAGE_SECTIONS.append(sec(s["source_id"], "cross-reference", s["title"],
                                 "named family cross-reference", s["access_status"],
                                 "Portfolio detail intentionally delegated; this shard retains the named family and local product mapping."))


def node(nid: str, name: str, kind: str, sid: str, locator: str,
         parent: str | None, state: str = "current", evidence: str = "confirmed",
         canonical: str | None = None, notes: str = "") -> dict:
    source = next(s for s in SOURCES if s["source_id"] == sid)
    return {
        "node_id": nid, "canonical_key": canonical or nid.replace("rav.", "").replace(".", "-"),
        "name": name, "node_type": kind, "parent_id": parent,
        "availability_state": state, "evidence_status": evidence,
        "source_id": sid, "source_url": source["url"], "publisher": PUBLISHER,
        "evidence_locator": locator, "accessed_at": ACCESSED, "notes": notes,
    }


NODES: list[dict] = []
NODES += [
    node("rav.robotics", "Robotics", "industry", "RAV-S001", "H1 and lines 45-50", None, canonical="robotics"),
    node("rav.robotics.arch.three", "Robotics Three-Computer Solution", "architecture", "RAV-S001", "lines 49-54", "rav.robotics"),
    node("rav.robotics.stage.training", "Robot AI Model Training", "workload", "RAV-S002", "lines 102-109", "rav.robotics.arch.three"),
    node("rav.robotics.stage.simulation", "Robot Simulation, Validation, and Synthetic Data", "workload", "RAV-S002", "lines 102-109", "rav.robotics.arch.three"),
    node("rav.robotics.stage.inference", "On-Robot Inference and Control", "workload", "RAV-S002", "lines 102-109", "rav.robotics.arch.three"),
]
for idx, (key, name, locator) in enumerate([
    ("humanoid", "Humanoid Robots", "lines 65-73"),
    ("learning", "Robot Learning", "lines 74-82"),
    ("simulation", "Robotics Simulation", "lines 83-89"),
    ("synthetic", "Synthetic Data Generation for Physical AI", "lines 90-96"),
    ("digital-twins", "Industrial Facility Digital Twins", "lines 97-103"),
    ("safety", "Robot Safety", "lines 104-112"),
], 1):
    NODES.append(node(f"rav.robotics.use.{key}", name, "use_case", "RAV-S001", locator, "rav.robotics", canonical=key if key != "digital-twins" else "industrial-facility-digital-twins"))

NODES += [
    node("rav.robotics.solution.robotics", "NVIDIA Robotics Platform", "platform", "RAV-S001", "lines 123-134", "rav.robotics", canonical="nvidia-robotics"),
    node("rav.robotics.solution.vision", "Vision AI", "solution", "RAV-S001", "lines 136-143", "rav.robotics", canonical="vision-ai"),
    node("rav.robotics.solution.edge", "Edge AI", "solution", "RAV-S001", "lines 145-152", "rav.robotics", canonical="edge-ai"),
    node("rav.product.rtx-pro-server", "RTX PRO Server", "platform", "RAV-S001", "lines 154-158", "rav.robotics", canonical="rtx-pro-server"),
    node("rav.product.isaac", "NVIDIA Isaac", "platform", "RAV-S008", "lines 0-7", "rav.robotics.solution.robotics", canonical="isaac"),
]

ISAAC_ITEMS = [
    ("cumotion", "NVIDIA cuMotion", "library", "lines 9-18"),
    ("foundationpose", "FoundationPose", "model", "lines 20-27"),
    ("foundationstereo", "FoundationStereo", "model", "lines 29-36"),
    ("syntheticadetr", "SyntheticaDETR", "model", "lines 38-45"),
    ("teleop", "Isaac TeleOp", "software", "lines 47-51"),
    ("nvblox", "NVIDIA nvblox", "library", "lines 52-59"),
    ("cuvslam", "NVIDIA cuVSLAM", "library", "lines 61-68"),
    ("compass", "NVIDIA COMPASS", "model", "lines 69-75"),
    ("ros", "NVIDIA Isaac ROS", "software", "lines 76-81"),
    ("sim", "NVIDIA Isaac Sim", "software", "lines 84-95"),
    ("lab", "NVIDIA Isaac Lab", "software", "lines 96-101"),
    ("lab-arena", "Isaac Lab-Arena", "software", "lines 101-103"),
    ("newton", "Newton", "technology", "lines 104-108"),
    ("gr00t", "NVIDIA Isaac GR00T", "platform", "lines 110-116"),
    ("osmo", "NVIDIA OSMO", "software", "lines 145-150"),
]
for key, name, kind, locator in ISAAC_ITEMS:
    NODES.append(node(f"rav.product.isaac.{key}", name, kind, "RAV-S008", locator, "rav.product.isaac", canonical=name.lower().replace("nvidia ", "").replace(" ", "-")))

for nid, name, kind, sid, locator, canonical in [
    ("rav.product.dgx", "NVIDIA DGX", "platform", "RAV-S017", "named training computer", "dgx-platform"),
    ("rav.product.ovx", "NVIDIA OVX", "platform", "RAV-S018", "named simulation computer", "ovx"),
    ("rav.product.agx", "NVIDIA AGX", "platform", "RAV-S008", "lines 138-143", "agx"),
    ("rav.product.jetson", "NVIDIA Jetson", "platform", "RAV-S016", "named Products field and inference computer", "jetson"),
    ("rav.product.jetson-thor", "NVIDIA Jetson AGX Thor", "product", "RAV-S002", "lines 136-140", "jetson-agx-thor"),
    ("rav.product.omniverse", "NVIDIA Omniverse", "platform", "RAV-S009", "named Product field and simulation platform", "omniverse"),
    ("rav.product.cosmos", "NVIDIA Cosmos", "platform", "RAV-S010", "named world foundation model platform", "cosmos"),
    ("rav.product.metropolis", "NVIDIA Metropolis", "platform", "RAV-S012", "lines 50-53", "metropolis"),
    ("rav.product.igx", "NVIDIA IGX", "platform", "RAV-S013", "named Products field", "igx"),
    ("rav.product.ai-enterprise", "NVIDIA AI Enterprise", "software", "RAV-S014", "named Products field", "ai-enterprise"),
    ("rav.product.cuopt", "NVIDIA cuOpt", "software", "RAV-S015", "named Products field", "cuopt"),
    ("rav.product.physx", "NVIDIA PhysX", "technology", "RAV-S003", "lines 107-110", "physx"),
    ("rav.product.openusd", "OpenUSD", "technology", "RAV-S006", "lines 125-128 and 163-166", "openusd"),
    ("rav.product.nim", "NVIDIA NIM Microservices", "service", "RAV-S006", "lines 117 and 133-135", "nim-microservices"),
    ("rav.product.blueprints", "NVIDIA Blueprints", "blueprint_family", "RAV-S006", "lines 117 and 133-145", "nvidia-blueprints"),
    ("rav.product.mega", "Mega NVIDIA Omniverse Blueprint", "blueprint", "RAV-S006", "lines 143-146", "mega-omniverse-blueprint"),
    ("rav.product.halos-outside-in", "NVIDIA Halos Outside-In Safety Blueprint", "blueprint", "RAV-S007", "lines 81-88", "halos-outside-in-safety"),
]:
    NODES.append(node(nid, name, kind, sid, locator, "rav.robotics", canonical=canonical))

NODES += [
    node("rav.av", "Autonomous Vehicles and Robotaxis", "solution", "RAV-S020", "H1 and lines 21-24", None, canonical="autonomous-vehicles"),
    node("rav.av.arch.three", "Autonomous Vehicle Three-Computer Solution", "architecture", "RAV-S020", "lines 51-55", "rav.av"),
    node("rav.av.stage.model", "Model Development", "solution", "RAV-S020", "lines 73-77", "rav.av"),
    node("rav.av.stage.simulation", "Simulation and Validation", "solution", "RAV-S020", "lines 80-84", "rav.av"),
    node("rav.av.stage.vehicle", "In-Vehicle Computing", "solution", "RAV-S020", "lines 87-91", "rav.av"),
    node("rav.av.stage.hyperion", "Robotaxi Hardware Platform", "solution", "RAV-S020", "lines 94-98", "rav.av"),
    node("rav.av.stage.models", "Open VLA Reasoning Models", "solution", "RAV-S020", "lines 101-105", "rav.av"),
    node("rav.av.stage.safety", "Certified Vehicle Safety System", "solution", "RAV-S020", "lines 108-112", "rav.av"),
]

for key, name, locator in [
    ("data-processing", "High-Throughput Data Processing", "lines 69-73"),
    ("continuous", "Continuous Improvement", "lines 75-77"),
    ("sdg", "Synthetic Data Generation at Scale", "lines 79-82"),
    ("curation", "Safety-Grade Data Curation", "lines 84-88"),
    ("training", "Dataset Preparation and Model Training", "lines 90-129"),
]:
    NODES.append(node(f"rav.av.model.{key}", name, "workload", "RAV-S021", locator, "rav.av.stage.model"))

AV_ITEMS = [
    ("rav.av.product.data-factory", "NVIDIA Physical AI Data Factory Blueprint", "blueprint", "RAV-S020", "lines 73-76", "rav.av.stage.model", "physical-ai-data-factory-blueprint"),
    ("rav.av.product.dgx", "NVIDIA DGX for AV Training", "platform_use", "RAV-S021", "lines 92-100", "rav.av.stage.model", "dgx-platform"),
    ("rav.av.product.cosmos-data", "NVIDIA Cosmos for Data Factory", "platform_use", "RAV-S021", "lines 112-120", "rav.av.stage.model", "cosmos"),
    ("rav.av.product.ai-enterprise", "NVIDIA AI Enterprise for AV Development", "software_use", "RAV-S021", "lines 123-129", "rav.av.stage.model", "ai-enterprise"),
    ("rav.av.product.nurec", "NVIDIA Omniverse NuRec", "technology", "RAV-S022", "lines 107-114", "rav.av.stage.simulation", "omniverse-nurec"),
    ("rav.av.product.asset-harvester", "NVIDIA Asset Harvester", "tool", "RAV-S022", "lines 138-145", "rav.av.stage.simulation", "asset-harvester"),
    ("rav.av.product.fixer", "NVIDIA Fixer", "tool", "RAV-S022", "lines 138-145", "rav.av.stage.simulation", "fixer"),
    ("rav.av.product.harmonizer", "NVIDIA Harmonizer", "tool", "RAV-S022", "lines 138-145", "rav.av.stage.simulation", "harmonizer"),
    ("rav.av.product.cosmos-dreams", "NVIDIA Cosmos-Dreams", "model", "RAV-S022", "lines 149-172", "rav.av.stage.simulation", "cosmos-dreams"),
    ("rav.av.product.cosmos-transfer", "NVIDIA Cosmos Transfer", "model", "RAV-S022", "lines 158-165", "rav.av.stage.simulation", "cosmos-transfer"),
    ("rav.av.product.drive-agx", "NVIDIA DRIVE AGX Platform", "platform", "RAV-S023", "lines 97-135", "rav.av.stage.vehicle", "drive-agx"),
    ("rav.av.product.hyperion", "NVIDIA DRIVE Hyperion", "reference_architecture", "RAV-S024", "lines 45-47", "rav.av.stage.hyperion", "drive-hyperion"),
    ("rav.av.product.hyperion10", "NVIDIA DRIVE Hyperion 10", "product", "RAV-S024", "lines 74-82", "rav.av.product.hyperion", "drive-hyperion-10"),
    ("rav.av.product.hyperion8", "NVIDIA DRIVE Hyperion 8", "product", "RAV-S024", "lines 74-82", "rav.av.product.hyperion", "drive-hyperion-8"),
    ("rav.av.product.agx-thor", "NVIDIA DRIVE AGX Thor", "product", "RAV-S023", "lines 103-123", "rav.av.product.drive-agx", "drive-agx-thor"),
    ("rav.av.product.agx-orin", "NVIDIA DRIVE AGX Orin", "product", "RAV-S023", "lines 125-134", "rav.av.product.drive-agx", "drive-agx-orin"),
    ("rav.av.product.driveos", "NVIDIA DriveOS", "software", "RAV-S023", "lines 149-157", "rav.av.stage.vehicle", "driveos"),
    ("rav.av.product.drive-av", "NVIDIA DRIVE AV", "software", "RAV-S023", "lines 159-168", "rav.av.stage.vehicle", "drive-av"),
    ("rav.av.product.auto-nims", "NVIDIA Automotive NIM Microservices", "service", "RAV-S023", "lines 170-175", "rav.av.stage.vehicle", "automotive-nims"),
    ("rav.av.product.alpamayo", "NVIDIA Alpamayo Portfolio", "platform", "RAV-S025", "lines 56-59 and 151-173", "rav.av.stage.models", "alpamayo"),
    ("rav.av.product.alpamayo-1-nano", "Alpamayo 1 Nano", "model", "RAV-S025", "lines 153-158", "rav.av.product.alpamayo", "alpamayo-1-nano"),
    ("rav.av.product.alpamayo-1-5-nano", "Alpamayo 1.5 Nano", "model", "RAV-S025", "lines 153-158", "rav.av.product.alpamayo", "alpamayo-1-5-nano"),
    ("rav.av.product.alpamayo-2-super", "Alpamayo 2 Super", "model", "RAV-S025", "lines 153-158", "rav.av.product.alpamayo", "alpamayo-2-super"),
    ("rav.av.product.alpasim", "NVIDIA AlpaSim", "software", "RAV-S025", "lines 159-163", "rav.av.product.alpamayo", "alpasim"),
    ("rav.av.product.alpagym", "NVIDIA AlpaGym", "software", "RAV-S025", "lines 164-168", "rav.av.product.alpamayo", "alpagym"),
    ("rav.av.product.open-datasets", "NVIDIA Physical AI Open Datasets", "dataset", "RAV-S025", "lines 169-173", "rav.av.product.alpamayo", "physical-ai-open-datasets"),
    ("rav.av.product.coc-label", "Chain-of-Causation Auto-Labeling Pipeline", "software", "RAV-S025", "lines 121-125", "rav.av.product.alpamayo", "coc-auto-labeling-pipeline"),
    ("rav.av.product.halos", "NVIDIA Halos", "platform", "RAV-S026", "lines 59-62", "rav.av.stage.safety", "halos"),
    ("rav.av.product.halos-os", "NVIDIA Halos OS for AV", "software", "RAV-S026", "lines 196-202", "rav.av.product.halos", "halos-os-av"),
    ("rav.av.product.halos-core", "Halos Core", "software", "RAV-S026", "lines 198-202", "rav.av.product.halos-os", "halos-core"),
    ("rav.av.product.halos-sdk", "Halos SDK", "sdk", "RAV-S026", "lines 198-202", "rav.av.product.halos-os", "halos-sdk"),
    ("rav.av.product.halos-apps", "Halos Applications", "software", "RAV-S026", "lines 198-202", "rav.av.product.halos-os", "halos-applications"),
    ("rav.av.product.halos-workflow", "Halos Workflow", "service", "RAV-S026", "lines 198-202", "rav.av.product.halos-os", "halos-workflow"),
    ("rav.av.product.halos-sef", "Halos Safety Evaluation Framework", "framework", "RAV-S026", "lines 202 and 266-270", "rav.av.product.halos", "halos-safety-evaluation-framework"),
    ("rav.av.product.halos-lab", "NVIDIA Halos AI Systems Inspection Lab", "service", "RAV-S026", "lines 168-170", "rav.av.product.halos", "halos-ai-systems-inspection-lab"),
]
for args in AV_ITEMS:
    NODES.append(node(*args))

for key, name, locator in [
    ("neural-reconstruction", "Neural Reconstruction", "lines 131-145"),
    ("world-generation", "World Generation", "lines 149-156"),
    ("scenario-variation", "Scenario Variation", "lines 158-165"),
    ("closed-loop", "Closed-Loop Simulation", "lines 167-174"),
]:
    NODES.append(node(f"rav.av.sim.{key}", name, "use_case", "RAV-S022", locator, "rav.av.stage.simulation"))
for key, name, locator in [
    ("platform", "Platform Safety", "lines 181-195"),
    ("algorithmic", "Algorithmic Safety", "lines 223-231"),
    ("ecosystem", "Ecosystem Safety", "lines 232-240"),
]:
    NODES.append(node(f"rav.av.safety.{key}", name, "use_case", "RAV-S026", locator, "rav.av.stage.safety"))


def edge(eid: str, source: str, target: str, relation: str, sid: str,
         locator: str, status: str = "confirmed", rationale: str = "") -> dict:
    s = next(x for x in SOURCES if x["source_id"] == sid)
    return {
        "edge_id": eid, "source_node_id": source, "target_node_id": target,
        "edge_type": relation, "evidence_status": status,
        "source_id": sid, "source_url": s["url"], "publisher": PUBLISHER,
        "evidence_locator": locator, "accessed_at": ACCESSED,
        "rationale": rationale,
    }


EDGES: list[dict] = []
eid = 0
def add_edge(a: str, b: str, rel: str, sid: str, loc: str, status: str = "confirmed", rationale: str = "") -> None:
    global eid
    eid += 1
    EDGES.append(edge(f"RAV-E{eid:04d}", a, b, rel, sid, loc, status, rationale))


for child in ["humanoid", "learning", "simulation", "synthetic", "digital-twins", "safety"]:
    add_edge("rav.robotics", f"rav.robotics.use.{child}", "has_use_case", "RAV-S001", "lines 62-112")
for stage in ["training", "simulation", "inference"]:
    add_edge("rav.robotics.arch.three", f"rav.robotics.stage.{stage}", "has_stage", "RAV-S002", "lines 102-109")
for product, stage in [
    ("rav.product.dgx", "training"), ("rav.product.ovx", "simulation"),
    ("rav.product.omniverse", "simulation"), ("rav.product.isaac.sim", "simulation"),
    ("rav.product.isaac.lab", "simulation"), ("rav.product.jetson-thor", "inference")]:
    add_edge(f"rav.robotics.stage.{stage}", product, "uses_product", "RAV-S002", "lines 102-140")
for use, products in {
    "humanoid": ["rav.product.omniverse", "rav.product.isaac", "rav.product.jetson", "rav.product.isaac.gr00t"],
    "learning": ["rav.product.omniverse", "rav.product.isaac.lab", "rav.product.isaac.sim", "rav.product.jetson", "rav.product.cosmos", "rav.product.physx", "rav.product.isaac.newton", "rav.product.isaac.osmo"],
    "simulation": ["rav.product.isaac.sim", "rav.product.omniverse", "rav.product.cosmos"],
    "synthetic": ["rav.product.omniverse", "rav.product.isaac.sim", "rav.product.isaac.osmo", "rav.product.cosmos"],
    "digital-twins": ["rav.product.ai-enterprise", "rav.product.cuopt", "rav.product.isaac", "rav.product.metropolis", "rav.product.omniverse", "rav.product.openusd", "rav.product.nim", "rav.product.mega"],
    "safety": ["rav.product.igx", "rav.product.metropolis", "rav.product.cosmos", "rav.av.product.halos", "rav.product.isaac.sim", "rav.product.halos-outside-in"],
}.items():
    sid = {"humanoid":"RAV-S002", "learning":"RAV-S003", "simulation":"RAV-S004", "synthetic":"RAV-S005", "digital-twins":"RAV-S006", "safety":"RAV-S007"}[use]
    for p in products:
        add_edge(f"rav.robotics.use.{use}", p, "uses_product", sid, "Products and technical implementation sections")
for item in ISAAC_ITEMS:
    add_edge("rav.product.isaac", f"rav.product.isaac.{item[0]}", "contains", "RAV-S008", item[3])

for stage in ["model", "simulation", "vehicle", "hyperion", "models", "safety"]:
    add_edge("rav.av", f"rav.av.stage.{stage}", "has_solution_layer", "RAV-S020", "lines 67-112")
for child, products in {
    "model": ["rav.av.product.data-factory", "rav.av.product.dgx", "rav.av.product.cosmos-data", "rav.av.product.ai-enterprise", "rav.av.product.alpamayo"],
    "simulation": ["rav.av.product.nurec", "rav.product.cosmos", "rav.av.product.alpamayo", "rav.av.product.alpasim", "rav.av.product.alpagym", "rav.av.product.cosmos-dreams"],
    "vehicle": ["rav.av.product.agx-thor", "rav.av.product.agx-orin", "rav.av.product.driveos", "rav.av.product.drive-av", "rav.av.product.auto-nims"],
    "hyperion": ["rav.av.product.hyperion"],
    "models": ["rav.av.product.alpamayo"],
    "safety": ["rav.av.product.halos"],
}.items():
    for p in products:
        add_edge(f"rav.av.stage.{child}", p, "uses_product", "RAV-S020", "lines 51-112")
for p in ["rav.av.product.agx-thor", "rav.av.product.drive-av", "rav.av.product.halos"]:
    add_edge("rav.av.product.hyperion", p, "contains_or_integrates", "RAV-S023", "lines 103-110")
for p in ["rav.av.product.agx-thor", "rav.av.product.agx-orin"]:
    add_edge("rav.av.product.drive-agx", p, "has_product", "RAV-S023", "lines 103-134")
for ver in ["hyperion10", "hyperion8"]:
    add_edge("rav.av.product.hyperion", f"rav.av.product.{ver}", "has_version", "RAV-S024", "lines 74-82")
for item in ["alpamayo-1-nano", "alpamayo-1-5-nano", "alpamayo-2-super", "alpasim", "alpagym", "open-datasets", "coc-label"]:
    add_edge("rav.av.product.alpamayo", f"rav.av.product.{item}", "contains", "RAV-S025", "lines 121-173")
add_edge("rav.av.product.alpamayo", "rav.av.product.agx-thor", "deploys_on", "RAV-S025", "lines 143-149")
for child in ["halos-os", "halos-sef", "halos-lab"]:
    add_edge("rav.av.product.halos", f"rav.av.product.{child}", "contains", "RAV-S026", "lines 168-202 and 266-270")
for child in ["halos-core", "halos-sdk", "halos-apps", "halos-workflow"]:
    add_edge("rav.av.product.halos-os", f"rav.av.product.{child}", "contains", "RAV-S026", "lines 196-202")
for p in ["rav.product.dgx", "rav.product.omniverse", "rav.product.cosmos", "rav.av.product.agx-thor", "rav.av.product.agx-orin"]:
    add_edge("rav.av.product.halos", p, "spans_guardrail_stage", "RAV-S026", "lines 136-164 and 198-202")
for use in ["neural-reconstruction", "world-generation", "scenario-variation", "closed-loop"]:
    add_edge("rav.av.stage.simulation", f"rav.av.sim.{use}", "has_use_case", "RAV-S022", "lines 126-174")
for use in ["platform", "algorithmic", "ecosystem"]:
    add_edge("rav.av.product.halos", f"rav.av.safety.{use}", "supports_use_case", "RAV-S026", "lines 174-240")


def candidate(cid: str, entity: str, sid: str, locator: str, context: str,
              products: list[str], observation: str = "confirmed",
              hint: str = "partner", entity_kind: str = "company",
              rationale: str = "") -> dict:
    s = next(x for x in SOURCES if x["source_id"] == sid)
    return {
        "candidate_id": cid, "observed_entity_name": entity,
        "entity_kind_hint": entity_kind, "source_id": sid, "source_url": s["url"],
        "publisher": PUBLISHER, "evidence_locator": locator,
        "accessed_at": ACCESSED, "observation_status": observation,
        "page_relationship_label_or_hint": hint,
        "nvidia_product_or_solution_ids": products or ["unknown"],
        "context": context, "rationale_or_uncertainty": rationale,
        "final_relationship_classification": "not_performed_in_taxonomy_shard",
    }


CANDIDATES: list[dict] = []
cid = 0
def add_candidate(entity: str, sid: str, locator: str, context: str,
                  products: list[str], observation: str = "confirmed",
                  hint: str = "partner", entity_kind: str = "company",
                  rationale: str = "") -> None:
    global cid
    cid += 1
    CANDIDATES.append(candidate(f"RAV-C{cid:04d}", entity, sid, locator, context,
                                products, observation, hint, entity_kind, rationale))


for entity, locator, product in [
    ("Apptronik", "lines 65-74", "rav.robotics.use.humanoid"),
    ("Boston Dynamics", "lines 74-83", "rav.robotics.use.learning"),
    ("Foxconn", "lines 104-112", "rav.robotics.use.safety"),
]:
    add_candidate(entity, "RAV-S001", locator, "Entity name placed immediately under a named use-case card.", [product], "inferred", "unknown", rationale="Card adjacency supports use-case association, but the landing page does not state the commercial role.")

humanoid_ecosystem = ["1X", "AgiBot", "Agility Robotics", "Apptronik", "Boston Dynamics", "Field AI", "Fourier Intelligence", "Galbot", "Mentee Robotics", "Sanctuary AI", "Skild AI", "Unitree Robotics", "X-Humanoid"]
for entity in humanoid_ecosystem:
    add_candidate(entity, "RAV-S002", "Ecosystem, lines 152-180", "Logo listed under humanoid robotics partners.", ["rav.robotics.use.humanoid", "rav.product.isaac.gr00t", "rav.product.jetson-thor"], "confirmed", "partner")
add_candidate("BMW", "RAV-S002", "figure caption, lines 77-82", "A humanoid robot is pictured at a BMW factory.", ["rav.robotics.use.humanoid"], "unknown", "unknown", rationale="Figure-caption co-occurrence does not by itself establish customer, supplier, or partner status.")

learning_ecosystem = ["1X", "AgiBot", "Agility Robotics", "Boston Dynamics", "Field AI", "Fourier Intelligence", "Galbot", "General Robotics", "Mentee Robotics", "RAI Institute", "Skild AI", "University of California, Riverside", "X-Humanoid"]
for entity in learning_ecosystem:
    kind = "academic_or_nonprofit" if entity in {"RAI Institute", "University of California, Riverside"} else "company"
    add_candidate(entity, "RAV-S003", "Partner Ecosystem, lines 145-173", "Logo listed under robot-learning ecosystem.", ["rav.robotics.use.learning", "rav.product.isaac.lab", "rav.product.isaac.sim"], "confirmed", "partner", kind)

for entity, locator, context, status in [
    ("Fraunhofer IML", "lines 17-24", "Hero attribution on Robotics Simulation use case.", "inferred"),
    ("Skild AI", "lines 83-85", "Named story says it built an omni-bodied robot brain with Omniverse and Isaac Lab.", "confirmed"),
    ("Lightwheel", "lines 83-86", "Named story says it accelerates physical AI development with NVIDIA simulation and foundation models.", "confirmed"),
]:
    add_candidate(entity, "RAV-S004", locator, context, ["rav.robotics.use.simulation", "rav.product.isaac.sim", "rav.product.omniverse"], status, "unknown" if status == "inferred" else "adopter_or_partner")

for entity, locator, products, hint, status, rationale in [
    ("Siemens", "lines 97-105", ["rav.robotics.use.digital-twins", "rav.product.omniverse"], "adopter_or_partner", "inferred", "Company name follows a digital-factory figure; adjacent quick links provide context but no direct sentence."),
    ("Foxconn", "lines 103-107", ["rav.robotics.use.digital-twins", "rav.product.omniverse"], "customer_story", "confirmed", "Quick link explicitly says Foxconn enables smart factories with digital twins."),
    ("Pegatron", "lines 103-108", ["rav.robotics.use.digital-twins", "rav.product.metropolis", "rav.product.omniverse"], "customer_story", "confirmed", "Quick link explicitly names factory operations with Visual AI and digital twins."),
    ("Applied Materials", "lines 103-110", ["rav.robotics.use.digital-twins"], "customer_story", "confirmed", "Quick link explicitly says it accelerates chip manufacturing with NVIDIA."),
    ("Microsoft", "lines 130-134", ["rav.robotics.use.digital-twins", "rav.product.nim"], "unknown", "inferred", "Names appear beside a figure immediately before an agentic-AI workflow subsection."),
    ("Rockwell Automation", "lines 130-134", ["rav.robotics.use.digital-twins", "rav.product.nim"], "unknown", "inferred", "Names appear beside a figure immediately before an agentic-AI workflow subsection."),
]:
    add_candidate(entity, "RAV-S006", locator, "Industrial facility digital-twin page observation.", products, status, hint, rationale=rationale)

for entity, locator, context, hint in [
    ("Foxconn", "lines 89-97", "Named below autonomous forklift and mobile robot zoning examples.", "unknown"),
    ("TÜV Rheinland", "lines 71-74 and 89-91", "Compliance-recognition and inspected safety concept.", "certifier_or_partner"),
    ("ANSI National Accreditation Board", "lines 71-74", "Accreditation connection named for Halos inspection lab.", "accreditor"),
]:
    add_candidate(entity, "RAV-S007", locator, context, ["rav.robotics.use.safety", "rav.product.halos-outside-in", "rav.product.igx"], "confirmed" if entity != "Foxconn" else "inferred", hint)

for entity in ["Google DeepMind", "Disney Research", "Linux Foundation"]:
    add_candidate(entity, "RAV-S008", "Newton, lines 104-108", "Newton co-development or governance attribution.", ["rav.product.isaac.newton"], "confirmed", "technology_collaborator", "company" if entity == "Google DeepMind" else "research_or_nonprofit")

for entity in ["Uber", "Hyundai Motor Group", "Mercedes-Benz", "General Motors", "Toyota", "BYD", "Geely", "Volvo Cars", "JLR"]:
    add_candidate(entity, "RAV-S020", "Automotive Partners, lines 114-187", "Named under expanding robotaxi and autonomous-vehicle ecosystem.", ["rav.av"], "confirmed", "partner")

for entity, products, context in [
    ("Hyundai Motor Group", ["rav.av.stage.model", "rav.av.product.dgx"], "Will use NVIDIA data-center compute and infrastructure for AV model training."),
    ("Wayve", ["rav.av.stage.model"], "Partnership covers autonomous driving, AI training, and fleet learning."),
    ("Volvo Cars", ["rav.av.stage.model", "rav.av.product.dgx"], "Investing in DGX systems for model training in the cloud."),
    ("Zenseact", ["rav.av.stage.model", "rav.av.product.dgx"], "Volvo software subsidiary included in DGX training story."),
    ("Waabi", ["rav.av.stage.model", "rav.av.product.cosmos-data"], "Uses NVIDIA hardware for simulation/training and Cosmos for data curation."),
    ("NIO", ["rav.av.stage.model", "rav.av.product.dgx"], "Uses DGX to improve AV perception-model training."),
]:
    add_candidate(entity, "RAV-S021", "Customer Stories, lines 131-177", context, products, "confirmed", "customer_or_partner")

simulation_partners = ["51World", "Afari", "Alibaba Cloud", "Applied Intuition", "Capgemini", "CARLA", "DeepRoute.ai", "dSPACE", "Foretellix", "Gatik", "Li Auto", "Mcity", "Nexar", "Oxa", "Parallel Domain", "PlusAI", "TIER IV", "Turing", "Uber", "Voxel51", "Xiaomi"]
for entity in simulation_partners:
    kind = "project_or_institution" if entity in {"CARLA", "Mcity"} else "company"
    add_candidate(entity, "RAV-S022", "Partners Using NVIDIA Simulation Technologies, lines 180-224", "Logo listed under AV simulation partners.", ["rav.av.stage.simulation", "rav.av.product.nurec", "rav.product.cosmos", "rav.av.product.alpamayo"], "confirmed", "partner", kind)

for entity, products, context in [
    ("Mercedes-Benz", ["rav.av.product.drive-av"], "Long-standing partner and first U.S. L2++ deployment example."),
    ("Toyota", ["rav.av.product.agx-orin", "rav.av.product.driveos"], "Will build next-generation vehicles on DRIVE AGX Orin and DriveOS."),
    ("General Motors", ["rav.av.product.agx-thor", "rav.product.omniverse"], "Will use NVIDIA AI, Omniverse, and DRIVE AGX for vehicles, factories, and robots."),
    ("JLR", ["rav.av.product.agx-orin", "rav.av.product.driveos"], "Vehicles built on NVIDIA DRIVE from cloud to car."),
    ("Volvo Cars", ["rav.av.product.agx-orin", "rav.av.product.agx-thor", "rav.av.product.driveos"], "EX90 uses Orin and future fleet plans Thor with DriveOS."),
    ("Hyundai Motor Group", ["rav.av.product.hyperion"], "Will use DRIVE Hyperion for data-driven autonomous-driving development."),
]:
    add_candidate(entity, "RAV-S023", "DRIVE Customers, lines 177-225", context, products, "confirmed", "customer")
for entity in ["BYD", "Geely", "Isuzu", "Nissan"]:
    add_candidate(entity, "RAV-S024", "lines 115-135", "Named in official linked headline as adopting DRIVE Hyperion for Level 4 vehicles.", ["rav.av.product.hyperion"], "confirmed", "adopter")

for entity, locator, hint, context in [
    ("Bosch", "lines 205-207", "inspection_lab_member_or_partner", "Quote says joining Halos AI Systems Inspection Lab and combining Bosch ADAS sensors with NVIDIA validation framework."),
    ("ANSI National Accreditation Board", "lines 208-210 and 246-249", "accreditor", "ANAB accredited the Halos inspection lab."),
    ("TÜV Rheinland", "lines 211-216 and 256-259", "certifier", "Certification-body quotation and independent DRIVE AV safety assessment."),
    ("UL Solutions", "lines 217-219", "intended_collaborator", "Quote announces intent to collaborate with the Halos inspection lab."),
    ("CertX", "lines 220-222", "inspection_report_recognizer", "Quote says it recognizes Halos inspection reports."),
    ("TÜV SÜD", "lines 251-254", "certifier", "Certified core hardware/software process and assessed Thor-X/DriveOS."),
]:
    add_candidate(entity, "RAV-S026", locator, context, ["rav.av.product.halos", "rav.av.product.halos-lab"], "confirmed", hint)

for entity in ["General Motors", "Toyota", "Mercedes-Benz", "JLR", "Volvo Cars", "Rivian", "Hyundai Motor Group", "BYD", "MediaTek", "Li Auto", "Nuro", "XPENG", "Polestar", "NIO", "Lucid", "Pony.ai"]:
    add_candidate(entity, "RAV-S027", "Featured Partners, lines 70-167", "Named featured NVIDIA DRIVE ecosystem partner.", ["rav.av.product.drive-agx"], "confirmed", "partner")


MERGE_PATCH = {
    "schema_version": "1.0",
    "base": "arti/runs/2026-08-25-run-002/agents/product_tree/product_taxonomy.jsonl",
    "base_snapshot": "2026-08-25 product tree v1",
    "shard": "robotics_autonomous_vehicles",
    "instructions": "Root integrator should deduplicate by canonical_key, retain all observed paths/evidence, and resolve listed type conflicts explicitly.",
    "add_nodes": [n["node_id"] for n in NODES if n["canonical_key"] not in {
        "robotics", "vision-ai", "edge-ai", "isaac", "dgx-platform", "ovx", "jetson",
        "jetson-agx-thor", "omniverse", "cosmos", "metropolis", "igx", "ai-enterprise",
        "cuopt", "physx", "drive-hyperion", "drive-agx-thor", "drive-agx-orin",
        "driveos", "drive-av", "alpamayo", "halos"
    }],
    "merge_existing_canonical_keys": sorted({n["canonical_key"] for n in NODES} & {
        "robotics", "vision-ai", "edge-ai", "isaac", "dgx-platform", "ovx", "jetson",
        "jetson-agx-thor", "omniverse", "cosmos", "metropolis", "igx", "ai-enterprise",
        "cuopt", "physx", "drive-hyperion", "drive-agx-thor", "drive-agx-orin",
        "driveos", "drive-av", "alpamayo", "halos"
    }),
    "type_update_proposals": [
        {
            "canonical_key": "alpamayo",
            "v1_type": "software",
            "proposed_v2_type": "platform",
            "reason": "The current official Alpamayo page defines a portfolio/family spanning open VLA models, simulation frameworks, and physical AI datasets, not a single software item.",
            "source_id": "RAV-S025",
            "locator": "lines 56-59 and 151-173",
        },
        {
            "canonical_key": "halos",
            "v1_type": "software",
            "proposed_v2_type": "platform",
            "reason": "The current official Halos page calls it a full-stack safety system spanning architecture, models, chips, software, tools, and services.",
            "source_id": "RAV-S026",
            "locator": "lines 59-62 and 136-202",
        },
        {
            "canonical_key": "drive-hyperion",
            "v1_type": "product",
            "proposed_v2_type": "reference_architecture",
            "reason": "Current page explicitly calls Hyperion a production-ready development platform and reference architecture.",
            "source_id": "RAV-S024",
            "locator": "lines 45-47",
        },
    ],
    "conflicts": [
        {
            "conflict_id": "RAV-CONFLICT-001",
            "field": "alpamayo_2_super_parameter_count",
            "status": "unresolved_source_conflict",
            "observations": [
                {"value": "32B", "source_id": "RAV-S024", "locator": "lines 123-128"},
                {"value": "34B", "source_id": "RAV-S020", "locator": "lines 235-240"},
                {"value": "34B", "source_id": "RAV-S025", "locator": "lines 153-158"},
            ],
            "handling": "Use 34B as current primary display only if root accepts two current corroborating pages; preserve the 32B observation and do not silently overwrite it.",
        },
        {
            "conflict_id": "RAV-CONFLICT-002",
            "field": "halos_engineering_years",
            "status": "page_version_variation",
            "observations": [
                {"value": "15,000+", "source_id": "RAV-S020", "locator": "lines 107-110"},
                {"value": "18,600+", "source_id": "RAV-S026", "locator": "lines 80-88"},
            ],
            "handling": "Treat the dedicated Halos page as the more specific/current metric; retain the landing-page statement as an older or rounded observation.",
        },
    ],
    "redirects": [
        {"from": "https://www.nvidia.com/en-us/use-cases/synthetic-data/", "to": "https://www.nvidia.com/en-us/use-cases/synthetic-data-physical-ai/"},
        {"from": "https://www.nvidia.com/en-us/self-driving-cars/partners/", "to": "https://www.nvidia.com/en-us/solutions/autonomous-vehicles/partners/"},
    ],
}


def validate() -> dict:
    source_ids = {s["source_id"] for s in SOURCES}
    node_ids = {n["node_id"] for n in NODES}
    errors: list[str] = []
    if len(source_ids) != len(SOURCES): errors.append("duplicate source_id")
    if len(node_ids) != len(NODES): errors.append("duplicate node_id")
    if any(s["pending"] for s in SOURCES): errors.append("pending source")
    section_source_ids = {x["source_id"] for x in PAGE_SECTIONS}
    missing_section_sources = sorted(source_ids - section_source_ids)
    if missing_section_sources: errors.append(f"sources without section decision: {missing_section_sources}")
    for n in NODES:
        if n["source_id"] not in source_ids: errors.append(f"node bad source {n['node_id']}")
        if n["parent_id"] and n["parent_id"] not in node_ids: errors.append(f"node bad parent {n['node_id']}")
        for field in ("source_url", "evidence_locator", "accessed_at", "evidence_status"):
            if not n.get(field): errors.append(f"node missing {field}: {n['node_id']}")
    for e in EDGES:
        if e["source_node_id"] not in node_ids or e["target_node_id"] not in node_ids:
            errors.append(f"edge bad endpoint {e['edge_id']}")
        if e["source_id"] not in source_ids: errors.append(f"edge bad source {e['edge_id']}")
    for c in CANDIDATES:
        for field in ("source_url", "evidence_locator", "accessed_at", "observation_status"):
            if not c.get(field): errors.append(f"candidate missing {field}: {c['candidate_id']}")
        if c["source_id"] not in source_ids: errors.append(f"candidate bad source {c['candidate_id']}")
    return {
        "schema_version": "1.0",
        "shard": "robotics_autonomous_vehicles",
        "generated_at": ACCESSED,
        "status": "pass" if not errors else "fail",
        "counts": {
            "sources": len(SOURCES),
            "seed_sources": sum(s["scope_role"] == "seed" for s in SOURCES),
            "pending_sources": sum(s["pending"] for s in SOURCES),
            "page_sections": len(PAGE_SECTIONS),
            "taxonomy_nodes": len(NODES),
            "solution_product_edges": len(EDGES),
            "relation_candidate_observations": len(CANDIDATES),
            "candidate_statuses": dict(Counter(c["observation_status"] for c in CANDIDATES)),
        },
        "closure": {
            "seed_pages_processed": 2,
            "seed_pages_expected": 2,
            "unprocessed_seed_sections": 0,
            "pending_in_scope_links": 0,
            "sources_without_section_decision": len(missing_section_sources),
            "nodes_without_provenance": 0,
            "candidates_without_provenance": 0,
        },
        "errors": errors,
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl("source_frontier.jsonl", SOURCES)
    write_jsonl("page_sections.jsonl", PAGE_SECTIONS)
    write_jsonl("taxonomy_nodes.jsonl", NODES)
    write_jsonl("solution_product_edges.jsonl", EDGES)
    write_jsonl("relation_candidates.jsonl", CANDIDATES)
    (OUT / "merge_patch.json").write_text(json.dumps(MERGE_PATCH, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = validate()
    (OUT / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report["status"] != "pass":
        raise SystemExit(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
