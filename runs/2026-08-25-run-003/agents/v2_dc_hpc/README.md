# NVIDIA product/solution tree v2 — Data Center + HPC fragment

Frozen research fragment for the public NVIDIA secondary sites:

- <https://www.nvidia.com/en-us/data-center/>
- <https://www.nvidia.com/en-us/high-performance-computing/>

Research cutoff and access snapshot: **2026-08-25**. This directory is an
incremental input to the root product/solution-tree v2 merger; it does not
modify or replace the v1 files.

## Result

The two seeds and the in-scope Product, Solution, Technology, Workload, and
Use Case family/item link closure contain no pending records in this fragment.

| Artifact | Records | Purpose |
| --- | ---: | --- |
| `source_frontier.jsonl` | 44 | URL, redirect, discovery, access, and completion decisions |
| `page_sections.jsonl` | 95 | Major page-section processing ledger |
| `taxonomy_nodes.jsonl` | 101 | Normalized nodes with v1 add/augment decisions |
| `solution_product_edges.jsonl` | 94 | Traceable solution-to-product/software/technology/workload mappings |
| `relation_candidates.jsonl` | 150 | Unclassified names/logos/customer stories with adjacent product context |
| `merge_patch.json` | 1 | v1 additions, evidence augmentations, aliases, and conflict decisions |
| `validation_report.json` | 1 | Counts, error lists, and zero-pending gates |

The fragment adds 63 canonical keys and augments 38 v1 keys. Candidate
observations are deliberately **not** final supplier, customer, or partner
classifications. They preserve the page wording and product context for the
later relationship agent.

## Important normalization decisions

- The current `/hpc-and-ai/` H1 is **AI for Science**; `HPC and AI` remains a
  navigation alias.
- The old Sustainable Computing URL redirects to Corporate Sustainability.
  It is retained as a redirected alias, not a current standalone solution.
- CAE is modeled as a solution in this context. The v1 `software` observation
  remains in the conflict log for the root merger.
- The NVAQC page component heading/link and overview identify `GB200 NVL72`,
  while one body sentence says `GB200 NVL2`; this is preserved as a source
  conflict and normalized to the named/linked NVL72 product.
- Earth-2's public DOM flattens the `Collaborators`, `Customers`, and
  `Inception Partners` tabs. Every logo is retained, but no per-logo tab role
  is invented.
- NVIDIA Quantum's ecosystem is partly delivered as a composite image. Only
  individually addressable names from the CUDA-Q Academic, NVAQC, and NVQLink
  sections are enumerated; the composite-image observation is recorded in the
  page ledger without OCR-based role claims.

## Boundary

In scope:

- The two named secondary-site seeds.
- Current family/item pages explicitly linked from their Product, Solution,
  Technology, Workload, and Use Case sections.
- Named NVIDIA products, platforms, software, services, architectures,
  technologies, solutions, workloads, and use cases.
- Company, organization, logo, adopter, customer-story, and ecosystem
  observations on reviewed pages.

Out of scope for this fragment:

- Header/footer repetition, forms, event pages, training, where-to-buy and
  catalog inventory, generic corporate navigation, and gated documents.
- Newsroom, NVIDIA Blog, and technical-blog article bodies; their links are
  context only because other agents own the time-bounded article corpora.
- Third-party application packages such as GROMACS, LAMMPS, NAMD, and VMD as
  NVIDIA products. Their workload context is retained without misattribution.
- Final listed-company resolution or relationship classification.

## Legal and access notes

Only public HTTPS pages were reviewed. NVIDIA `robots.txt` was checked on the
snapshot date; the canonical, parameter-free seed paths were permitted. No
login, paywall, CAPTCHA, rate-limit, or other access control was bypassed. No
credentials or restricted source material are present. The repository retains
structured facts, short locators, and URLs rather than page copies, images, or
licensed raw content.

## Reproduce and validate

The builder performs no network requests. It deterministically regenerates the
frozen observations from the reviewed literals in `build_fragment.py`:

```bash
cd runs/2026-08-25-run-003/agents/v2_dc_hpc
python3 build_fragment.py
jq . validation_report.json
```

Expected final value:

```json
{"overall_status":"pass"}
```

All gates must remain true, including zero pending frontier records, unique
identifiers, valid provenance, processed page sections, and no dangling
solution/product edges.
