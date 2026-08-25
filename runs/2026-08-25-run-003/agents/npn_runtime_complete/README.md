# NVIDIA Partner Network runtime postprocessor

This directory contains the deterministic, offline postprocessor for the 2026-08-25 NVIDIA Partner Network (NPN) browser capture. It does not collect pages and performs no network requests.

## Completion boundary

`build_outputs.py` accepts only the final complete runtime capture: exactly 23 `page_*.json` files, page numbers 1 through 23, and exactly 997 visible card observations (pages 1–22 contain 45 cards each; page 23 contains 7). Listing/profile duplication is allowed and retained. Each source card becomes a unique raw observation identified by page, within-page ordinal, and a deterministic digest.

The directory reported 996 cards in the initial same-day runtime observation and 997 in the final frozen browser capture. Every frozen page records both `initial_runtime_observation_total=996` and `runtime_total=997`; the one-card drift is explicitly reconciled in the page manifest and validation reports. The final 997-card freeze is authoritative for this snapshot and is not treated as an error.

The builder is fail-closed. Missing pages, a non-997 final card count, a page-card distribution other than 22×45 plus 7, malformed tag fields, an unrecognized NPN competency, an unavailable registry, or a competency mapping outside the frozen product tree causes a non-zero exit. In this state it writes a failure `validation_report.json` and `group_validation_report.json`, preserves the pagination audit, and emits no downstream groups, matches, or claims. A failure report is not a partial completion claim.

## Inputs

- `../npn_runtime_browser/pages/page_*.json`: public, visible NPN directory card snapshots produced by the browser collection agent.
- `../../product_tree_v2/canonical_index_v2.jsonl`: frozen NVIDIA product tree; every emitted `product_scope_id` must exist here.
- `../entity_resolution_complete/entity_registry.jsonl` and `aliases.jsonl`: base listed-company registry and reviewed exact aliases.
- `../global_listing_overlay/entity_registry_overlay.jsonl` and `aliases.jsonl`: non-US listing overlay; only `alias_status=safe_exact` aliases are eligible.

No login, credential, API key, personal data, paid content, or access-control bypass is used. Public directory facts are redistributed in structured form; NVIDIA retains copyright in the source pages and logos.

## Run

From this directory:

```bash
python3 build_outputs.py
```

The program uses only the Python 3 standard library. Paths can be overridden for isolated QA:

```bash
python3 build_outputs.py --input-dir /path/to/pages --output-dir /path/to/output
```

Exit codes:

- `0`: all input, grouping, entity-resolution, tag-losslessness, product-scope, and terminal-decision gates passed.
- `2`: input/schema/reference gate failed closed; no downstream completion claim.
- `3`: a final grouping or claim invariant failed.

## Outputs

- `raw_listings.jsonl`: all 997 regional/division card observations, without deduplication loss.
- `tag_observations.jsonl`: one provenance-bearing observation for every visible Partner Type, Competency, and optional tag value.
- `entity_groups.jsonl`: deterministic corporate/listing groups and unioned source tags.
- `listing_group_edges.jsonl`: exactly one group edge per raw observation, with the grouping rule.
- `group_decision_ledger.jsonl`: terminal grouping and listed-entity resolution decisions, including unresolved/conflict outcomes.
- `listed_group_matches.jsonl`: active listed parents resolved by reviewed/safe exact aliases only.
- `relationship_claims.jsonl`: one `partner` claim per resolved listed parent and individual NPN competency; when multiple exact NPN groups resolve to the same parent, all contributing `npn_group_ids` and source observations are retained on the consolidated claim.
- `evidence.jsonl`: page-level source URL, publisher, retrieval value, locator, content hash, snapshot path, and access/permission note.
- `pagination_manifest.jsonl`: page, declared total/range, record count, and content hash.
- `validation_report.json`: input, tag-losslessness, competency, product-scope, and completion gates.
- `group_validation_report.json`: grouping, listed matching, terminality, role-boundary, and claim gates.

## Grouping policy

Raw observations are never removed. Grouping uses only four deterministic rules:

1. identical normalized NPN profile URL;
2. names differing only by an enumerated trailing legal suffix;
3. names differing only by an enumerated trailing region suffix, and only when the unsuffixed base is also observed;
4. explicitly reviewed anchored corporate-family rules for AMAX, Accenture, ASUS/ASUSTeK, and 2CRSi.

Each merge retains its reason and member observations. Logo similarity, edit distance, token similarity, substring matching, and other fuzzy matching are prohibited. An unmatched group is a terminal unresolved decision, not pending work. Conflicting safe aliases are also terminal and do not generate a listed-company match.

## Tag and relationship semantics

Partner Type and Competency arrays are copied losslessly and represented again as atomic tag observations with card-level locators. Optional card fields may be empty; the raw record names the empty fields and states that the visible card did not expose them.

In the final frozen capture, 34 cards expose a nonempty Specialization: 28 `AI Factory` and 6 `Reference Platform NCP`. These two visible labels are allowlisted by the validator. Company names or any other text in the Specialization field fail the build rather than being retained as tags.

The nine observed NPN competencies are mapped one-to-one to frozen canonical scopes:

| NPN competency | `product_scope_id` |
| --- | --- |
| Compute | `accelerated-computing` |
| Visualization | `professional-visualization-and-workstations` |
| NVIDIA Enterprise Software | `nvidia-ai-enterprise` |
| NVIDIA Technologies | `architectures-and-core-technologies` |
| Embedded Compute | `embedded-robotics-and-edge` |
| NVIDIA Virtual Desktops | `virtual-gpu` |
| Networking | `networking` |
| DGX AI Compute Systems | `dgx-platform` |
| DGX Cloud | `dgx-cloud` |

An unseen competency stops the build for human taxonomy review. It is never guessed.

Official NPN directory membership confirms only a partner-program relationship. It does not establish supplier/customer status, purchases, sales direction, revenue, spend, exclusivity, product adoption, or contract terms. Accordingly, this processor emits only `relationship_type=partner`; supplier/customer inference is explicitly out of scope.

## Reproduction and review

The page snapshots are the frozen fixture. Re-running the builder does not require the reviewer to revisit NVIDIA's website. Compare `source_content_sha256` values in the page manifest and evidence file, then confirm `validation_report.json` reports 23 pages, 997 raw observations, 997 unique observation IDs, the reconciled +1 same-day runtime drift, zero unmapped competencies, and zero pending decisions.

Human judgment remains responsible for the explicit corporate-family rules, safe alias registry, listing status at the cutoff, and competency-to-product mapping. AI/coding agents assisted with schema design, deterministic transformation code, and validation checks; they were not given credentials, personal data, customer secrets, or unauthorized material.

This research artifact is not investment advice.
