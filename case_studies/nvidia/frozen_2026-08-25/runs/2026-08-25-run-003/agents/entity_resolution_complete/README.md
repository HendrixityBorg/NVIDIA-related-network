# Reviewed listed-entity resolution shard

This directory resolves raw company-name candidates to listed issuer identities. It does **not** create or classify NVIDIA relationships.

## Method

`build_reviewed_registry.py` combines the frozen product-tree relation candidates, 2025/2026 official article observations (including archive-index fallbacks), available filings/presentation candidates, and the available NPN browser/raw fixtures. It retrieves the public SEC `company_tickers_exchange.json` dataset with a descriptive User-Agent, retains a hash of the full response, and stores only supporting rows in `sec_company_tickers_exchange_filtered.jsonl`.

Resolution is conservative:

- strict normalized exact alias/issuer matches are the default;
- fuzzy matching never promotes a candidate;
- eight brand-to-legal-name variants and additional obvious issuer short names are explicitly enumerated and audited in code/output;
- `technology`, `technologies`, `systems`, `group`, `holdings`, and `international` are never silently stripped to auto-promote a match;
- known contextual collisions (`Spire`, `Everpure`, `Global AI`, `Samsung`, and `Hyundai Motor Group`) are ambiguous, not listed entities;
- the 13F-reviewed private Space Exploration Technologies holding is explicitly excluded despite a conflicting carried registry/SEC-name match;
- a ticker without an exchange (for example, the current SEC row for SEEQC) does not meet the `exchange:ticker` gate;
- previous snapshot aliases can establish an identity hypothesis, but a carried non-US listing without current SEC evidence remains unresolved here rather than masquerading as confirmed.

The SEC ticker dataset identifies issuer/ticker/exchange but not security class. The registry keeps a reference security and labels its type `not_classified_in_sec_ticker_dataset`; obvious warrants, rights, and preferred-series symbols are excluded from the reference identifiers, while supporting SEC rows remain auditable.

## Outputs

- `candidate_review.jsonl`: one terminal reviewed record for every unique raw candidate.
- `entity_registry.jsonl`: confirmed listed entities only.
- `aliases.jsonl`: reviewed aliases for registry entities.
- `listing_evidence.jsonl`: source URL, publisher, retrieval time, locator, access constraint, and `exchange:ticker` identifiers.
- `ambiguous_review_queue.jsonl`, `unresolved_review_queue.jsonl`, `rejected_review_queue.jsonl`: closed review outcomes, not pending work.
- `normalization_risk_audit.jsonl`: potentially dangerous normalization decisions.
- `validation_report.json`: build-time completion gates.

`unresolved` is a terminal research status for this cutoff: it means the available evidence cannot safely prove a unique currently listed issuer. It is deliberately retained for future source improvement and is not eligible for final listed-company relationships.

## Reproduce and validate

From the repository root:

```bash
python3 runs/2026-08-25-run-003/agents/entity_resolution_complete/build_reviewed_registry.py \
  --repository-root . \
  --output runs/2026-08-25-run-003/agents/entity_resolution_complete
python3 runs/2026-08-25-run-003/agents/entity_resolution_complete/validate_outputs.py
```

Rerun the builder after an upstream article, filings/presentation, or NPN shard changes. Input discovery is dynamic and the one-status-per-candidate gate will be recalculated.

## Boundaries

- No relationship claim is generated here.
- No issuer is promoted from fuzzy similarity.
- Non-US securities absent from the SEC dataset require separate official-exchange evidence; until then they remain unresolved in this shard even when a prior local snapshot carried a ticker.
- Regional NPN grouping/dedup belongs to the NPN shard. This resolver preserves each raw name candidate and only resolves issuer identity.
