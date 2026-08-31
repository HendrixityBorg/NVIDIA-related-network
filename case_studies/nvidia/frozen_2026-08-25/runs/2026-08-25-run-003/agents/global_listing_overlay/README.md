# Global listing identity overlay

This directory supplements `agents/entity_resolution_complete/` with reviewed non-U.S. issuer identities and exact brand/subsidiary-to-listed-parent mappings as of **2026-08-25**. It does not edit the main registry or relationship snapshot.

## Scope and decision rules

- Primary evidence is an official issuer investor-relations page, issuer filing/press release, or an official exchange page. The Ansys cutoff decision additionally uses the Nasdaq-filed SEC Form 25-NSE.
- Only exact reviewed names are mapped. Fuzzy matching is disabled throughout.
- `Geely`, `Samsung`, and `Volvo` remain terminally ambiguous. Their precise listed forms (`Geely Auto`, `Samsung Electronics`, `Volvo Cars`) are separately resolved.
- `AIC` is acronym-ambiguous and is resolved only for its specific candidate ID(s) in the NVIDIA server/storage context. It is not a global alias.
- A subsidiary or product name maps to a listed parent only where an official source explicitly establishes the relationship: Google Cloud→Alphabet, Azure/GitHub→Microsoft, Red Hat→IBM, Hitachi Vantara→Hitachi, Giga Computing→GIGABYTE, NAVER Cloud→NAVER, ASRock Rack→ASRock, and MiTAC Computing→MiTAC Holdings.
- Ansys is retained only as a historical issuer. Synopsys completed the acquisition and Nasdaq filed Form 25-NSE on 2025-07-17, so ANSS is not an active listed endpoint at the cutoff.

## Files

- `entity_registry_overlay.jsonl`: 30 active reviewed issuers plus historical Ansys. Hitachi is an `augment_existing` record targeting the existing registry entity.
- `aliases.jsonl`: exact, context-bound, ambiguous-not-promoted, and historical-only alias decisions.
- `listing_evidence.jsonl`: source URL, publisher, publication/retrieval time, locator, short fact extract, and access/reuse constraints.
- `decision_ledger.jsonl`: terminal decisions for every requested name and exact candidate-review hits; OCR-decorated lookalikes are rejected rather than normalized.
- `validation_report.json`: deterministic validation result.
- `build_outputs.py`, `validate_outputs.py`: reproducible builder and validator.

## Reproduce

No credentials or environment variables are required. The builder does not fetch the web; it materializes the human-verified source decisions and joins exact normalized names to the frozen `candidate_review.jsonl` fixture.

```bash
python3 agents/global_listing_overlay/build_outputs.py
python3 agents/global_listing_overlay/validate_outputs.py
```

Run those commands from `runs/2026-08-25-run-003/`.

## Merge guidance

Apply only aliases with `alias_status=safe_exact` as unrestricted exact aliases. Apply `context_bound` only to the listed `candidate_review_ids`. Never auto-promote `ambiguous_not_promoted`. Keep `historical_only` entities out of active listed-company relationship endpoints. When augmenting Hitachi, merge its TSE security into `entity_43cff1458d4aab47` rather than creating a second issuer.

## Limits

- This overlay verifies issuer/security identity, not the underlying NVIDIA relationship claim.
- Live IR pages may change after the cutoff; `retrieved_at` fixes the review time and `published_at` is null where the page is continuously maintained.
- Vendor-formatted tickers such as `SU.PA` and `DSY.PA` are retained as vendor codes while exchange tickers use `SU` and `DSY`.
- Volvo Cars' original Nasdaq listing notice supplies the ISIN, while the live Nasdaq instrument page establishes continued trading at the cutoff.
- ASRock Rack is mapped as a controlled/consolidated subsidiary, not as a wholly owned company; the official 2025 statements disclose 46.22% ownership at year-end.
- This research artifact is not investment advice.
