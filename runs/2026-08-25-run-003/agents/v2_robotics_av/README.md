# Product/Solution Tree v2 — Robotics and Autonomous Vehicles shard

This directory is the frozen `2026-08-25` official-source shard for two NVIDIA
secondary sites:

- `https://www.nvidia.com/en-us/industries/robotics/`
- `https://www.nvidia.com/en-us/solutions/autonomous-vehicles/`

It supplements, but does not overwrite, the v1 tree in
`runs/2026-08-25-run-002/agents/product_tree/`. The root integrator must apply
`merge_patch.json`, deduplicate by `canonical_key`, preserve every evidence path,
and resolve the documented conflicts.

## Result

- 2/2 seed pages processed
- 27 source-frontier records, 0 pending
- 112 section decisions
- 103 taxonomy nodes
- 122 solution/product edges
- 113 company or organization candidate observations
- 0 unprocessed in-scope sections or links

The Robotics branch now represents:

```text
Robotics
├── three-computer architecture
│   ├── training: DGX
│   ├── simulation/validation: OVX, Omniverse, Isaac Sim, Isaac Lab
│   └── inference/control: Jetson AGX Thor
├── use cases
│   ├── Humanoid Robots
│   ├── Robot Learning
│   ├── Robotics Simulation
│   ├── Synthetic Data Generation for Physical AI
│   ├── Industrial Facility Digital Twins
│   └── Robot Safety
└── named technology families and Isaac items
    ├── Isaac GR00T, Isaac ROS, Isaac Sim, Isaac Lab, Isaac Lab-Arena
    ├── cuMotion, FoundationPose, FoundationStereo, SyntheticaDETR
    ├── nvblox, cuVSLAM, COMPASS, Newton, OSMO
    └── Metropolis, IGX, Cosmos, OpenUSD, NIM and Blueprints
```

The Autonomous Vehicles branch now represents:

```text
Autonomous Vehicles and Robotaxis
├── Model Development
│   ├── Physical AI Data Factory Blueprint
│   ├── DGX, Cosmos for Data Factory and AI Enterprise
│   └── data processing, training, synthetic data and safety-grade curation
├── Simulation and Validation
│   ├── Omniverse NuRec, Cosmos, Cosmos-Dreams and Cosmos Transfer
│   ├── Asset Harvester, Fixer and Harmonizer
│   └── neural reconstruction, world generation, scenario variation,
│       closed-loop simulation
├── In-Vehicle Computing
│   ├── DRIVE AGX Thor and Orin
│   ├── DriveOS and DRIVE AV
│   └── Automotive NIM microservices
├── DRIVE Hyperion
│   ├── Hyperion 10
│   └── Hyperion 8
├── Alpamayo portfolio
│   ├── Alpamayo 1 Nano, 1.5 Nano and 2 Super
│   ├── AlpaSim and AlpaGym
│   └── Physical AI Open Datasets and CoC auto-labeling pipeline
└── Halos full-stack safety system
    ├── Halos OS: Core, SDK, Applications and Workflow
    ├── Safety Evaluation Framework and Inspection Lab
    └── platform, algorithmic and ecosystem safety
```

## Files

- `source_frontier.jsonl`: every reviewed seed, in-scope linked page, reused-v1
  page, and cross-shard product-family reference; every row has a final access
  decision and `pending=false`.
- `page_sections.jsonl`: section-level processing ledger. Empty rendered partner
  sections are explicitly recorded as `processed_no_named_cards` or
  `processed_category_only`, not silently skipped.
- `taxonomy_nodes.jsonl`: additive product, platform, software, model, dataset,
  solution, workload, use-case, architecture and technology nodes.
- `solution_product_edges.jsonl`: explicit solution/product/stage mappings.
- `relation_candidates.jsonl`: observations only. It intentionally does not make
  final supplier/customer/partner classifications.
- `merge_patch.json`: v1 merge guidance, redirects, type upgrades and source
  conflicts.
- `validation_report.json`: mechanical closure/provenance verification.
- `build_outputs.py`: deterministic, offline materializer for this frozen shard.

## Evidence and candidate semantics

`confirmed` in `relation_candidates.jsonl` means that the name/logo or described
use is directly visible under the cited official-page heading. It does **not**
mean the final economic relationship has been confirmed. Final relationship
classification belongs to the later entity-resolution and relationship-review
pipeline.

- `confirmed`: explicit name/logo, partner/customer heading, quotation, adoption
  wording or named story.
- `inferred`: a name is adjacent to a use-case card or figure and the product
  context is inferable, but the role is not stated.
- `unknown`: co-occurrence such as a figure caption cannot establish a commercial
  role. The BMW factory figure is retained in this state rather than discarded.

Every candidate is bound to a local NVIDIA product/solution node or to `unknown`.
Logo-only ecosystems retain their exact section locator. Institutions and open
source projects such as CARLA and Mcity are retained with a non-company hint so
the later listed-company filter can exclude them transparently.

## Notable merge conflicts

1. v1 calls Alpamayo a single `software` item. The current dedicated page defines
   a portfolio of models, simulation frameworks and datasets, so this shard
   proposes `platform` as the canonical type.
2. v1 calls Halos `software`. The dedicated page calls it a full-stack system
   spanning architecture, models, chips, software, tools and services; this shard
   proposes `platform`.
3. DRIVE Hyperion is explicitly a development platform and reference
   architecture, not merely a product.
4. NVIDIA pages disagree on Alpamayo 2 Super size: the current Hyperion page says
   32B, while the AV landing and Alpamayo pages say 34B. Both observations are
   preserved; the root integrator must not silently erase the conflict.
5. The AV landing says Halos reflects 15,000+ engineering years, while the
   dedicated Halos page reports 18,600+. The dedicated page is more specific, but
   the older/rounded observation remains traceable.

## Reproduction and validation

The frozen outputs require no network access:

```bash
cd arti/runs/2026-08-25-run-003/agents/v2_robotics_av
python3 build_outputs.py
python3 -m json.tool merge_patch.json >/dev/null
python3 -m json.tool validation_report.json >/dev/null
```

Refreshing evidence is a new dated run. Do not overwrite this snapshot. NVIDIA
pages are dynamic and some partner cards or images may require browser rendering;
where the public text representation exposed only a heading/category and no name,
this shard records that limitation instead of guessing or bypassing access
controls.

## Scope boundary

This shard follows the two seeds through their named Product, Solution,
Technology, Workload and Use Case pages to the family/item names needed for the
v2 tree. It does not recurse into documentation articles, GitHub repositories,
model-card versions, NGC assets, videos, event recordings, contact forms or news
articles. News/Blog full-history processing and the full NVIDIA Partner Network
are separate required workstreams. Detailed Omniverse, Cosmos, data-center and AI
Enterprise sub-portfolios remain owned by their respective v2 shards; this shard
retains the explicit cross-reference and local solution mapping.

Only publicly accessible official NVIDIA pages were used. No credentials,
personal data, restricted content, or access-control bypass was used or stored.
