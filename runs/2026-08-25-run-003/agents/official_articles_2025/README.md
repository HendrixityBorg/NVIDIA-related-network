# NVIDIA official articles — 2025 shard

## Scope and outcome

This shard accounts for every row in the frozen official article master whose
`published_date` is from 2025-01-01 through 2025-12-31, inclusive. The input is
`../../../news/official_articles.jsonl`.

- Master rows: **482** (391 NVIDIA Blog, 91 NVIDIA Newsroom).
- Processing ledger rows: **482**, with unique `article_id` and canonical URL.
- Body captures processed during the run: **98** (all 91 Newsroom releases and
  7 Blog posts); full HTML is a local transient input and is not distributed.
- Explicit body access failures: **384**, all NVIDIA Blog pages.
- Ledger pending rows: **0**.
- Ledger closure: **pass**.
- Body coverage: **98/482 (20.33%)**, incomplete.
- Overall validation: **fail**, because a terminal `access_blocked` row closes
  the accounting ledger but does not equal successful body review.

The count is 98 rather than the earlier 92 checkpoint because six Blog bodies
became publicly reachable before the bounded retry run was stopped. Those
legally obtained snapshots are preserved rather than discarded. No further
  high-frequency retry was performed. Structured observations, hashes and
  locators are preserved; the publisher pages themselves are not republished.

## Files

- `article_processing.jsonl`: exactly one terminal processing row per 2025
  master article.
- `fetch_manifest.jsonl`: one access result per article, including timestamp,
  SHA-256, byte count, final URL and snapshot path where successful.
- `body_snapshots/*.html.gz`: optional local processing cache, explicitly
  excluded from the repository; manifests retain hashes, sizes and locators.
- `entity_mentions.jsonl`: raw organization-like mentions. These are not
  necessarily listed companies and are not relationship claims.
- `observations.jsonl`: conservative relationship candidates with article ID,
  source, body/archive locator, excerpt, direction hint, semantic status,
  product mapping, access note, age bucket and content fingerprint.
- `access_audit.json`: host/path access policy and restrictions.
- `validation_report.json`: separate ledger-closure and body-coverage gates.
- `process_articles.py`: dependency-free fetch, parse, derive and validate
  script.

## Interpretation boundaries

An entity co-mentioned with NVIDIA is recorded as `unknown`, not promoted to a
relationship. `customer`, `partner` and `supplier` are only hints for root-level
entity resolution and human review. Unresolved names can include products,
events, private companies, public institutions or subsidiaries; the root merge
must reject anything that is not a verified listed parent.

Article investment wording is deliberately retained as `unknown` and marked
non-authoritative. A final NVIDIA `invests_in`/investee claim may only come from
the latest allowed NVIDIA 13F source, never from this article shard. The script
therefore emits zero `investee` relationship hints.

The time-decay inputs are recorded, not scored here. At the 2026-08-25 cutoff,
the project buckets are 0–90 days (1.00), 91–180 (0.90), 181–365 (0.75), and
over 365 days within the research window (0.55).

## Access failures and alternative route

The Blog host intermittently reset direct public connections. The process used
one bounded request per Blog page, made no attempt to bypass robots, login,
paywall, CAPTCHA, rate limiting or other access controls, and then stopped.
Every failure is terminally accounted for as `access_blocked`. Its frozen
NVIDIA Newsroom archive title and description are retained as explicitly
lower-grade fallback evidence, with an archive locator and a warning not to
promote the result without body/counterparty corroboration.

The legitimate refresh route is to rerun the same public canonical URLs during
a later, separately documented update window. Reviewer understanding does not
depend on doing so: the ledger, access errors, archive fallback, hashes and
derived rows are all included here. A later successful refresh
must preserve old fetch observations rather than silently rewriting historical
access status in the final merged provenance layer.

## Reproduce

This is an intermediate shard superseded by `../article_body_recovery/` for the
release gate. The checked-in structured ledgers can be audited without page
refetch. Re-running the extractor itself requires either an authorized public
refresh or the operator's local, non-distributed processing cache; it is not a
reviewer prerequisite.

```bash
.venv/bin/python runs/2026-08-25-run-003/agents/official_articles_2025/process_articles.py \
  --manifest runs/2026-08-25-run-003/news/official_articles.jsonl \
  --output runs/2026-08-25-run-003/agents/official_articles_2025 \
  --product-files \
    runs/2026-08-25-run-002/agents/product_tree/product_taxonomy.jsonl \
    runs/2026-08-25-run-003/agents/v2_dc_hpc/taxonomy_nodes.jsonl \
    runs/2026-08-25-run-003/agents/v2_robotics_av/taxonomy_nodes.jsonl \
    runs/2026-08-25-run-003/agents/v2_network_ai_design/taxonomy_nodes.jsonl \
  --offline
```

For a future authorized public refresh, omit `--offline` and specify a polite
delay. Any local body cache remains excluded from publication.

## Human verification required at merge

The root researcher must verify legal/listed parent identity and ticker,
relation direction, product mapping, and whether apparently explicit wording
describes an actual transaction/use/supply relationship. Product names and
event names that survive the deliberately broad raw mention stage must be
removed. Multiple evidence rows must be content-fingerprint deduplicated before
independence or confidence is increased. This shard makes no investment
recommendation.
