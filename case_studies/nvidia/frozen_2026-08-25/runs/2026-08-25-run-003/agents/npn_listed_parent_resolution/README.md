# NPN listed issuer / listed parent resolution overlay

Research cutoff: **2026-08-25**. This directory audits the 950 NPN groups that remained unresolved after safe-exact alias matching in `agents/npn_runtime_complete`. It does not fetch or alter the frozen 997 NPN cards or 973 entity groups and does not emit relationship claims.

## Policy

- A direct card-to-issuer identity may recommend `confirmed` with cap 95.
- A subsidiary, brand, or likely-parent endpoint is always `inferred`, capped at 79/69/59 respectively, and must cite both the frozen NPN card and separate parent/listing evidence.
- The SEC legal-name screen is strict and human-reviewed. No fuzzy result is auto-promoted; `Compugen`, `TEN Inc`, and `Cronos` are explicit false-homonym regression cases.
- Cutoff status wins over historical ticker identity. NTT DATA, SCSK, Nebius B.V., Okaya Electronics, Atea country companies, and EDF/EXAION have explicit temporal/entity corrections.
- Remaining unresolved rows are terminal research decisions, not assertions that the organization is private. Each records the four screens applied and preserves the NPN evidence reference.

## Inputs and reproducibility

- Frozen NPN inputs: `../npn_runtime_complete/{raw_listings,entity_groups,listed_group_matches}.jsonl`
- Existing validated issuer evidence: `../entity_resolution_complete/` and `../global_listing_overlay/`
- Official SEC fixture: `company_tickers_exchange.json`, SHA-256 `18ea4fbc84ee31d7320907ebf176df92013a28e4d304c95ef3f9674dfd373410`
- Reviewed public-market metadata fixture: `yahoo_chart_fixture.jsonl`; refresh is isolated in `refresh_yahoo_fixture.py` and is not required to reproduce outputs.
- Human-reviewed exact-card catalog: `reviewed_mappings.json`, generated from the auditable compact rules in `catalog_seed.py`.

Rebuild and validate without network:

```bash
python3 catalog_seed.py
python3 build_resolution.py
python3 validate_outputs.py
python3 -m unittest -v test_resolution.py
```

`refresh_yahoo_fixture.py` is optional and only uses Yahoo Finance's public chart JSON with a descriptive user agent and 350 ms spacing. It uses no login, API key, paywall, CAPTCHA, robots, rate-limit, or access-control bypass. `failed_yahoo_symbols.jsonl` must be empty for a passing build.

## Outputs

- `mapping_decision_ledger.jsonl`: exactly 950 terminal decisions, zero pending.
- `resolved_parent_mappings.jsonl`: group-to-listed-endpoint mappings with `resolution_kind`, status/cap recommendation, and NPN + mapping/listing evidence IDs.
- `listed_entity_registry_overlay.jsonl`: new issuer registry rows only; upstream registry rows are referenced, not duplicated.
- `mapping_evidence.jsonl`: source URL, publisher, publication/retrieval time, locator, access constraints, and upstream/snapshot pointers.
- `unresolved_review_queue.jsonl` / `rejected_candidates.jsonl`: terminal fail-closed outcomes.
- `candidate_comparisons.jsonl`: reserved for reviewed multiple-parent market-cap comparisons; empty because no ambiguous multi-parent card was promoted in this slice.
- `summary.json` and `validation_report.json`: coverage and independent QA.

Limitations: this is a high-recall improvement over exact aliases, not a claim that every NPN card has been exhaustively proved private or public. The 754 unresolved cards include local resellers, opaque legal entities, short/homonymous names, and entities for which no reviewed active listed-parent evidence was established by the cutoff. They remain available for further jurisdiction-specific registry and ownership research.
