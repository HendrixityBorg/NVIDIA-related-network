# NVIDIA Product Tree v2

Research cutoff: **2026-08-25**. This artifact supersedes v1 without modifying it. It merges v1 plus the independently validated Data Center/HPC, Robotics/AV, and Networking/AI/Design shards.

## Outputs

- `PRODUCT_TREE_V2.md`: readable once-per-canonical tree.
- `canonical_index_v2.jsonl`: canonical decisions with every observed name, type, path, and evidence.
- `taxonomy_observations.jsonl`: 797 immutable normalized raw taxonomy observations, each retaining its raw input record.
- `edges.jsonl`: 335 solution/product edge observations.
- `relation_candidates.jsonl`: 594 research candidates; none are promoted to a final relationship here.
- `source_frontier.jsonl`: 168 namespaced source observations; same canonical URL can retain multiple shard paths.
- `page_sections.jsonl`: normalized section decisions.
- `conflicts.jsonl`: generated and shard-authored conflicts.
- `merge_decisions.jsonl`: one explainable primary-field decision per canonical object.
- `validation_report.json`: all closure, provenance, uniqueness, and reconciliation gates.
- `supersession.json`: explicit v1 supersession record.
- `build_v2.py`: offline deterministic merger.

`generated_at` is the actual UTC build time; it is provenance metadata and is not used in canonical IDs, merge decisions, counts, or validation hashes.

## Reproduce

Run these commands from the repository root (`arti/`):

```bash
python3 runs/2026-08-25-run-003/product_tree_v2/build_v2.py
python3 runs/2026-08-25-run-003/product_tree_v2/validate_v2.py
```

The source frontier uses only public observations already collected by the input shards. No credential, login, paywall, CAPTCHA, robots, rate-limit, or access-control bypass occurs. The parameterized use-case URL excluded by robots remains an explicit decided frontier row.

## Canonical rules

All raw observations survive. Exact/safe normalized-name matches and documented aliases map observations to a canonical key. `Alpamayo=platform`, `Halos=platform`, `DRIVE Hyperion=reference_architecture`, and `hpc-and-ai` has current primary name `AI for Science` with `HPC and AI` as alias. Other type conflicts use a documented entity-specific precedence, while `observed_types`, paths, evidence, conflict records, and decisions remain visible.
