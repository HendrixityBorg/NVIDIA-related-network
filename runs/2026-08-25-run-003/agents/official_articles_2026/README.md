# NVIDIA official articles — 2026 shard

This directory processes every row in the frozen official article manifest
whose `published_date` is from 2026-01-01 through the research cutoff
2026-08-25, inclusive. The dynamically derived population is **283 unique
articles**: 77 NVIDIA Newsroom press releases and 206 NVIDIA Blog posts.

## Outcome at this run

The manifest and processing ledger close exactly: 283 input IDs, 283 unique
ledger rows, 283 fetch records and zero pending states. All 77 Newsroom bodies
were fetched from public, no-login canonical URLs and processed with SHA-256;
the full HTML was a local transient cache and is not distributed. The Blog host reset every canonical connection from this runtime,
including a browser-path diagnostic, so all 206 Blog rows are correctly marked
`access_blocked`.

This distinction is deliberate:

- `ledger_closure_pass = true`
- `body_coverage_complete = false` (77/283, 27.2085%)
- `overall/pass = false` until the 206 bodies are lawfully accessible

For each blocked Blog row, the already frozen official NVIDIA Newsroom archive
title and description were still scanned deterministically. Those 206 fallback
scan records are separately tagged `official_archive_index_fallback`; they are
not presented as body evidence and should receive lower weight or independent
corroboration before a final relationship merge.

## Files

- `article_processing.jsonl`: one terminal row per manifest article.
- `fetch_manifest.jsonl`: URL, publisher/date, fetch outcome, final URL,
  snapshot path, SHA-256, byte count, time and access/license notes.
- `body_snapshots/*.html.gz`: optional local processing cache, explicitly
  excluded from the repository; manifests retain hashes, sizes and locators.
- `entity_mentions.jsonl`: raw body-derived mentions; unresolved or non-listed
  names remain available for later entity resolution.
- `raw_relation_observations.jsonl`: append-only conservative body observations.
- `index_fallback_processing.jsonl`: exactly one scan ledger row for each of
  the 206 blocked Blog articles, including no-candidate outcomes.
- `index_fallback_entity_mentions.jsonl`: raw mentions found in archive
  title/description fallback text.
- `index_fallback_observations.jsonl`: listed-company fallback candidates,
  explicitly labeled as index-only evidence.
- `observations.jsonl`: final candidate export for this shard. Every row has a
  confirmed listed identity and at least one `exchange:ticker` identifier;
  body and fallback evidence tiers remain explicit.
- `access_audit.json`: robots/access/request policy and the safe alternative.
- `validation_report.json`: closure, body coverage, candidate and traceability
  statistics. `pass` is intentionally false while body coverage is incomplete.
- `process_articles.py`: reproducible processor and listing/fallback filter.
- `validate_outputs.py`: independent invariant and snapshot-hash validator.

## Relationship semantics

The parser only creates a relationship hint when a company-like name occurs in
a local text block with a relation cue. A co-mention is retained as
`relationship_hint=unknown` and never asserted as a relationship. Candidate
rows carry the direction hint, fact/inferred/unknown state, rationale, excerpt,
block or archive locator, product mapping, content fingerprint, access note,
published date, cutoff age and freshness bucket.

Article investment wording is deliberately demoted to `unknown`: investee
classification belongs exclusively to NVIDIA's latest 13F shard. News or blog
language can support later corroboration but cannot create an investee claim.

Products are matched against the frozen `product_tree_v2/canonical_index_v2.jsonl`
and `taxonomy_observations.jsonl`. If no product is explicit in the evidence
unit, the scope is `corporate_general`; the processor does not force a mapping.

Final listed-company filtering uses the frozen `arti/data/snapshot_2026-08-25.json`
entity registry or an exchange/ticker expression printed in the article.
Unresolved names are intentionally excluded from `observations.jsonl`, not
discarded. Because the frozen registry contains only 53 currently resolved
entities, root-level entity resolution can lawfully promote additional raw
mentions later when authoritative listing evidence is added.

## Reproduce

From this directory:

```bash
python3 process_articles.py \
  --manifest ../../news/official_articles.jsonl \
  --output . \
  --product-files ../../product_tree_v2/canonical_index_v2.jsonl \
                  ../../product_tree_v2/taxonomy_observations.jsonl \
  --delay 0.35

python3 validate_outputs.py
```

When the operator has the local processing cache, successful captures are
reused and rehashed. The processor uses no credentials. A refresh should use a meaningful cooldown; it must not circumvent
robots, authentication, CAPTCHA, paywall, throttling or connection controls.
If Blog access remains blocked, keep those rows blocked and regenerate only the
clearly marked archive-index fallback. Do not substitute the short description
for the article body.

## Known limitations

- 206 Blog bodies are unavailable in this runtime; relationship recall from
  those posts is therefore incomplete even though their ledger is closed.
- Deterministic anchors/title patterns favor precision and miss unlinked names.
- A public-company identity registry is incomplete, so many raw observations
  remain unresolved until authoritative exchange or issuer evidence is added.
- Keyword relation hints are research candidates, not final claims. Quotations,
  lists of game titles and ecosystem roundups can create co-mentions; the root
  merge must apply entity, direction, independence and corroboration review.
- NVIDIA retains source copyright. Snapshots are for audit/research only and do
  not imply permission to republish the articles.

No output is investment advice.
