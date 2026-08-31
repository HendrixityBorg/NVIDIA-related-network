# product_tree agent output

This directory contains the NVIDIA official product-tree snapshot at 2026-08-25.

- `product_tree.md`: human-readable tree and scope/limitations.
- `product_tree.json`: nested machine-readable tree.
- `product_taxonomy.jsonl`: flat one-node-per-line form with `parent_id`, `path`, `canonical_key`, and evidence locator.
- `canonical_index.jsonl`: canonical objects with `primary_type`, aliases, all observed paths, and conflict resolution.
- `source_frontier.jsonl`: 59 reviewed public official pages.
- `build_taxonomy.py`: deterministic generator.
- `validate_taxonomy.py`: provenance, canonical, type, and GPU-state checks.

Reproduce and validate with:

```bash
python3 build_taxonomy.py
python3 -m json.tool product_tree.json >/dev/null
python3 validate_taxonomy.py
```

The build performs no network requests. It reproduces the frozen, manually verified snapshot. Refreshing the evidence requires a new dated run because NVIDIA pages are dynamic. No credentials or restricted content are used.

Current data-center GPU portfolio is defined by the official NVIDIA Marketplace GPU category at the cutoff and corroborated by the August 2025 line card. H100/H100 NVL and A40/A10/A16 are retained separately as `supported_not_current_marketplace_portfolio`; support evidence is not treated as current-portfolio evidence.
