# Filings and presentations shard

Frozen cutoff: `2026-08-25` (`Asia/Shanghai`). Research subject: NVIDIA
Corporation (`NASDAQ: NVDA`, CIK `0001045810`). This shard is research data,
not investment advice.

## Boundary

Included sources only:

- NVIDIA FY2026 Form 10-K, filed 2026-02-25, accession
  `0001045810-26-000021`;
- NVIDIA Form 13F-HR for the period ended 2026-06-30, filed 2026-08-14,
  accession `0001045810-26-000065`, including its cover and complete
  information table;
- the six user-specified official PDFs: GTC 2025 Keynote, GTC Taipei / COMPUTEX
  2025, GTC Paris 2025, GTC Washington D.C. 2025, COMPUTEX 2026 and July 2026
  NDR.

Excluded: 10-Q, 8-K, SEC submissions as a relationship source, the rest of the
NVIDIA IR archive, institutions holding NVDA, paid/logged-in sources and any
non-public material. SEC recent-submission metadata was queried only to verify
the latest accession and absence of a later amendment through the cutoff.

## Outputs

- `source_frontier.jsonl`: URL, publisher, publication/retrieval time, access
  terms, byte count, SHA-256 and PDF page total. Full source files are not
  redistributed.
- `page_processing.jsonl`: one record for every physical PDF page. The six page
  totals are 73, 72, 70, 66, 73 and 25, totaling 379.
- `raw_observations.jsonl`: append-only page audit, every OCR line from every
  visually selected candidate page (including OCR errors/non-entities), plus
  resolved observations. This prevents silent deletion of logo candidates.
- `listed_candidates.jsonl`: occurrence-level listed-company candidates with
  direction, semantic status, product key, exchange/ticker candidate and
  provenance. It is not deduplicated across pages. Security identifiers remain
  marked for human review before final graph merge.
- `13f_holdings.jsonl`: all eight filed rows. Issuer entity and security class
  are separate objects. `value_usd` is the filed integer dollar value, not
  thousands; `put_call` is null for every row and amount type is `SH`.
- `acquisition_review.jsonl`: completed acquisitions of formerly public
  companies are separated from current listed-company candidates; the failed
  Arm proposal is explicitly excluded.
- `conflicts.jsonl` and `validation_report.json`: resolved edge cases and hard
  completion gates.

Reviewer comprehension does not require re-fetching any source: short evidence,
page locators, source metadata and fingerprints are stored here. Re-fetch is
only needed to independently reproduce extraction or visually inspect original
layout.

## Evidence rules

- A name/logo under an explicit NVIDIA product, adoption, collaboration or
  customer architecture heading is a factual *placement*. This establishes a
  partner candidate unless the language explicitly establishes customer or
  supplier direction. It does not by itself prove commercial materiality.
- A logo on a cover, general event wall, sponsor-like wall, architecture page
  without a relationship title or no-title page is `unknown`, product scope
  `corporate_general` unless a nearby product is unambiguous.
- The photonics ecosystem page explicitly calls the shown entities ecosystem
  partners/co-inventors; the 10-K expressly names foundry, memory and contract
  manufacturing suppliers.
- The 10-K competitor list is an explicit peer fact. NVIDIA states that these
  companies or their internal teams develop the competing hardware/software;
  therefore it satisfies the self-developed-product peer rule.
- The 10-K's 22% and 14% direct customers and the meaningful unnamed AI research
  and deployment company remain `unknown`. No company identity is guessed.
- Repeated appearances remain separate evidence observations for downstream
  confidence aggregation.

## 13F result

The 2026-06-30 filing is `13F-HR`, `isAmendment=false`, reports zero other
included managers, eight rows and no confidential omission. Filed value totals
exactly `$63,439,974,569`.

Seven issuers are current-listed candidates: Coherent (`COHR`), CoreWeave
(`CRWV`), Generate Biomedicines (`GENB`), Intel (`INTC`), Nebius (`NBIS`),
Nokia ADR (`NOK`) and Synopsys (`SNPS`). Space Exploration Technologies is
private and is retained in the raw 13F result but excluded from the listed graph.
CUSIP and security class come directly from the filing. Exchange and ticker are
candidate mappings requiring a final human check; Generate's CUSIP/ticker is
also corroborated by its official investor FAQ at the cutoff.

13F is evidence that NVIDIA reported investment discretion over a security; it
does not establish a strategic operating partnership, beneficial-owner control,
purchase date or economic intent.

## Reproduction

Requires Python 3 and `pypdf`; PDF visual processing uses Poppler
`pdftoppm`. On macOS, `ocr_pages.swift` uses Apple's local Vision framework.
No credentials or environment variables are used.

```bash
python3 collect_sources.py
pdftoppm -jpeg -r 72 source_files/gtc_2025_keynote.pdf source_files/rendered/gtc_2025_keynote/page
# Repeat the render command for all six PDFs, then:
swift ocr_pages.swift source_files/rendered source_files/page_ocr.jsonl
python3 build_outputs.py
python3 finalize_public_outputs.py
python3 validate_outputs.py
```

`collect_sources.py` contains the frozen URLs and polite SEC user-agent logic.
It fetches only the nine scoped documents. `finalize_public_outputs.py` first
removes local paths from the public provenance ledger and then deletes only the
script-created `source_files/` cache. Repository policy forbids redistributing
full third-party PDF/HTML/XML or rendered pages. The final
`validation_report.json` asserts that this cache is absent.

## Human verification and limitations

The Agent downloaded public sources, extracted text, rendered all pages, ran
local OCR, created contact sheets and enlarged selected pages. A human reviewer
should verify exchange/ticker mappings, visually ambiguous OCR strings and any
relationship promoted beyond placement evidence. The researcher remains
responsible for source selection, relation direction, product mapping and final
investment-research judgment.

OCR is deliberately recall-oriented: private companies, public institutions,
product names, garbled text and unresolved marks stay in raw observations.
`listed_candidates.jsonl` is a high-precision but not infallible resolver layer.
Logo presence can be branding, example, event participation or ecosystem
co-occurrence rather than a transaction. The selected PDFs do not prove the
absence of a relationship, revenue amount or exclusivity. Historical acquisition
review is designed to keep obvious formerly listed targets out of the current
graph; historical ticker records with no first-party exchange page are marked
for manual verification.

Access was limited to public HTTP resources without robots, login, paywall,
CAPTCHA, rate-limit or other access-control bypass. Source copyright remains
with each publisher. Only short excerpts and structured facts are retained.
