# NVIDIA product/solution tree v2 — Networking, AI, Design and Simulation

This directory is the independent merge patch produced for three official NVIDIA
secondary sites at the **2026-08-25** research cutoff:

1. <https://www.nvidia.com/en-us/networking/>
2. <https://www.nvidia.com/en-us/solutions/ai/>
3. <https://www.nvidia.com/en-us/solutions/design-and-simulation/>

It supplements the run-002 taxonomy; it does not modify or overwrite the shared
v1 artifacts. The output is research data, not investment advice.

## Result

The frozen patch contains:

- 3 seed pages;
- 38 source-frontier decisions, including 37 processed public pages and one
  robots-excluded parameterized listing;
- 229 individually decided page sections;
- 220 taxonomy nodes;
- 119 explicit solution/product/use-case mapping edges;
- 331 company or organization relation-candidate observations;
- zero pending sources, sections, unmapped product candidates, or broken
  provenance links within this shard.

The patch specifically adds current items absent or underdeveloped in v1,
including Spectrum-XGS, Spectrum-X Multiplane, Spectrum-X and Quantum-X
Photonics, BlueField-4 and BlueField-4 STX, DOCA components, DSX Air,
Quantum-X800 components, Agent Toolkit, AI-Q, NemoClaw, OpenShell, current
inference and conversational-AI components, current Design/Simulation
workflows, CAE, rendering, XR, and linked use-case product mappings.

## Operational closure boundary

For each seed, every titled page section was decided. The link closure includes
the seed's explicit links to current NVIDIA Product, Solution, Technology,
Workload, and Use Case pages, then stops at the named family/item boundary on
those pages. It does not recursively traverse:

- news, blog, press-release, customer-story, webinar, video, training, support,
  documentation, download, purchase, or contact links;
- arbitrary footer navigation;
- individual NGC/Build models, containers, endpoints, versions, or regional
  SKUs;
- gated resources or parameterized pages disallowed by robots.txt.

The linked Robotics and Autonomous-Vehicle Simulation pages overlap the other
v2 product-tree shards. They were processed here at the direct family boundary
and are explicitly identified in `merge_patch.json` so the root merge can
canonicalize by URL rather than duplicate them.

The filtered Use Cases URL reached from the AI seed contains a `page` query
parameter. NVIDIA's robots.txt disallows such parameter URLs, so it was not
fetched or used. This decision is retained as source `NAD038`; the seed's
unparameterized individual use-case links were processed instead.

## Relation-candidate semantics

`relation_candidates.jsonl` is an observation ledger, not a final company
relationship table. It deliberately includes private companies, nonprofits,
open-source projects, brands, and unresolved names. Listed-company resolution
belongs to the later entity-resolution stage.

- `confirmed` means the page text explicitly calls the entity a customer,
  adopter, partner, or user in the cited context. It is still only a candidate
  until entity and direction review.
- `inferred` is usually a logo/name under an explicit Partner, Ecosystem,
  Adopter, or named product section. The product context is retained, but the
  economic direction is not asserted.
- `unknown` covers unheaded hero labels, stray captions, and resource-video
  participants where the page does not state a relationship.

No logo-only observation is promoted to a final relationship. A company can
appear in multiple sources and product contexts; those observations are kept so
the downstream process can deduplicate only identical
`entity + role + product/category` conclusions while preserving different roles
and products.

## Files

- `source_frontier.jsonl` — canonical URL, discovery parent, access status,
  redirects, section list, and access/legal note.
- `page_sections.jsonl` — one decision per reviewed page section.
- `taxonomy_nodes.jsonl` — flat, typed v2 nodes with parent and evidence.
- `solution_product_edges.jsonl` — explicit `contains`, `uses_product`, or
  `simulates` mappings.
- `relation_candidates.jsonl` — company/project observations tied to adjacent
  NVIDIA products or solutions.
- `merge_patch.json` — canonical merge instructions, cross-shard overlaps, and
  zero-pending lists.
- `validation_report.json` — counts and integrity checks.
- `build_outputs.py` — deterministic offline serializer for this frozen patch.

## Reproduce and validate

The generator makes no network requests and needs only Python 3:

```bash
cd arti/runs/2026-08-25-run-003/agents/v2_network_ai_design
python3 build_outputs.py
python3 -m json.tool merge_patch.json >/dev/null
python3 -m json.tool validation_report.json >/dev/null
test "$(rg -c '\"closure_decision\": \"pending\"' source_frontier.jsonl || true)" = ""
```

Expected final generator summary:

```text
frontier_records=38 page_sections=229 taxonomy_nodes=220
solution_product_edges=119 relation_candidates=331
pending_sources=0 pending_sections=0 unmapped_product_candidates=0
broken_provenance_links=0
```

## Evidence and limitations

All research used public official NVIDIA HTTPS pages. No login, paywall,
captcha, rate limit, robots rule, or other access control was bypassed. No
credentials, personal data, restricted raw data, or gated content is retained.

NVIDIA pages are dynamic and many do not display a publication date. Evidence
locators therefore combine the stable page heading/section name with the line
location in the public text view captured during review. The files preserve
URLs and access time so later refreshes can compare the current page with this
frozen observation, but they do not copy full page bodies.

Some pages contain malformed or ambiguous alt text (for example a stray
“Katana” label). These are retained as `unknown`, not silently discarded or
treated as evidence. Partner/adopter logo walls establish a candidate and
product context only; they do not by themselves prove supplier/customer
direction, listing status, contract size, exclusivity, or current revenue.
