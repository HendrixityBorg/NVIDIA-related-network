# Category-level peer research

Cutoff: 2026-08-25. This output reviews exactly the eight product categories
specified in the run contract. A peer is accepted only when the issuer was
listed at the cutoff and an official source shows a self-developed competing
product or platform. Resellers, OEM assembly, systems integration and an
NVIDIA-powered offering alone do not pass the gate.

`peer_candidates.jsonl` contains accepted category-scoped relationship
candidates. The same issuer can appear in more than one category. `confirmed`
means NVIDIA names the issuer as a competitor and the counterparty documents
its own overlapping product. `inferred` means both official product
descriptions show material category overlap, but neither party explicitly
labels the exact category relationship.

`category_review_ledger.jsonl` contains one terminal row for every required
category, including rejected and unknown-not-promoted examples. These records
are review decisions, not claims that the candidate is unrelated in every
context. `source_evidence.jsonl` preserves URL, publisher, publication or
retrieval time, locator, short excerpt, access constraints and a content
fingerprint. Full third-party pages are not redistributed.

Healthcare/Life Sciences has zero accepted peers. Schrodinger, Tempus, GE
HealthCare and Recursion were reviewed, but the evidence did not cleanly prove
category-level substitution rather than a downstream or complementary layer.
This conservative zero is intentional and is not a claim that those firms
never compete with NVIDIA in a narrower workflow.

Reproduce and validate:

```bash
python3 build_outputs.py
python3 validate_outputs.py
```

The research is deliberately category-level rather than SKU-exhaustive. It
does not compute market shares or assert that product peers are pure-play
financial comparables. Internal hyperscaler silicon is a product competitor
even when the issuer is also an NVIDIA customer or partner. No login, paywall,
CAPTCHA, rate limit, robots rule or other access control was bypassed.

AI-assisted search helped enumerate official pages and draft structured
fields. A human reviewed the eight category boundaries, listing identifiers,
self-development test, product overlap, evidence locators and all promotions
or exclusions. The author remains responsible for the research judgment. This
dataset is research infrastructure and does not constitute investment advice.
