# NVIDIA Blog Body Recovery

This shard attempts body-level closure for the 597 NVIDIA Blog URLs in the
frozen `news/official_articles.jsonl` manifest, from 2025-01-01 through the
2026-08-25 cutoff.

## Retrieval order and legal boundary

1. Reuse an existing body captured directly from the public, no-login NVIDIA
   canonical URL by the 2025/2026 official-article shards.
2. Match the exact canonical URL in NVIDIA's official FeedBurner feed,
   `https://feeds.feedburner.com/nvidiablog`. NVIDIA's
   `https://www.nvidia.com/en-us/about-nvidia/rss/` page says this free RSS
   service is for information purposes only and restricts it to non-commercial
   uses. This research run follows that restriction.
3. For remaining URLs, request the public Internet Archive Availability API
   once for the exact canonical URL and publication date. Accept only an exact
   canonical URL match whose replay timestamp is on/after publication and
   on/before the cutoff, then request that public replay serially. The checked
   `https://archive.org/robots.txt` disallowed only `/control/` and `/report/`;
   neither the Availability API nor replay path was disallowed. The CDX endpoint
   returned service/rate-limit errors and was not bypassed.

No login, CAPTCHA, paywall, robots restriction, token, proxy rotation, browser
fingerprinting, or other access-control bypass is used. Requests are serial and
delayed. Third-party replay HTML is parsed in memory and never retained. The
repository retains URLs, timestamps, hashes, byte counts, short evidence
excerpts, locators, structured mentions/observations, and a terminal per-article
ledger. Copyright remains with the original publisher; no republication grant
is inferred.

The official Newsroom archive title/description is not counted as body
coverage. A terminal `blocked` row closes bookkeeping and can satisfy the legal
source-closure gate when its audit/reason is complete, but it does not make the
separately reported `body_coverage_complete` field true. Blocked articles may
contribute only title/index-level `unknown` evidence elsewhere; they must not be
promoted to a relationship claim.

## Run and validate

```bash
python3 agents/article_body_recovery/recover_blog_bodies.py \
  --run-root runs/2026-08-25-run-003 \
  --output runs/2026-08-25-run-003/agents/article_body_recovery \
  --delay 0.8

python3 agents/article_body_recovery/finalize_ledger.py \
  runs/2026-08-25-run-003/agents/article_body_recovery \
  runs/2026-08-25-run-003

python3 agents/article_body_recovery/validate_recovery.py \
  --run-root runs/2026-08-25-run-003 \
  --output runs/2026-08-25-run-003/agents/article_body_recovery
```

Per-article `partials/*.json` make the run resumable without refetching already
terminal articles. Delete or move a specific partial only when deliberately
re-attempting that article in a later refresh.

## Outputs

- `article_processing.jsonl`: exact 597-row body/recovery ledger.
- `access_audit.jsonl`: exact URL, public route, timestamp, response hash/size,
  and failure reason.
- `entity_mentions.jsonl`: structured candidates; a mention is not a relation.
- `observations.jsonl`: conservative body-block relation observations with
  locators and short excerpts.
- `validation_report.json`: run-generated coverage statistics.
- `independent_validation_report.json`: independent closure tests.

Article investment wording is always retained as `unknown`. Under the project
policy, only NVIDIA's latest 13F can establish a final investee relationship.

## Frozen cutoff result

The 2026-08-25 run has 597 unique terminal ledger rows and zero pending rows:
7 direct NVIDIA bodies, 16 official RSS bodies, 535 public Wayback replay
bodies, and 39 fully audited access-blocked rows. Body coverage is 558/597, so
`body_coverage_complete` is false while the legal source-closure validation is
true. The 39 blocked records must not be promoted from index/title evidence to
a relationship claim.
