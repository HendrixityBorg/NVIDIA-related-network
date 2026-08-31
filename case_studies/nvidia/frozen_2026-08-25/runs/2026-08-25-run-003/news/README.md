# Official NVIDIA article enumeration

This directory freezes the public NVIDIA Newsroom archive for the inclusive
research window `2025-01-01` through `2026-08-25`. The Newsroom archive is an
official NVIDIA super-index: each card identifies either `Read Press Release`
or `Read Blog`, and Blog cards link directly to `blogs.nvidia.com`. Enumeration
therefore preserves the publisher split instead of treating all cards as
Newsroom articles.

## Frozen result

- 78 year-filtered archive pages
- 771 raw card observations
- 765 unique canonical article URLs after six duplicate observations were
  retained separately
- 168 NVIDIA Newsroom press releases
- 597 NVIDIA Blog articles
- zero unknown article types and zero empty archive pages

`official_articles.jsonl` is the immutable body-processing mother table.
`newsroom_press_releases.jsonl` and `nvidia_blog_articles.jsonl` are exact
partitions. `archive_pages.jsonl` links every fetched page to a gzip snapshot
and SHA-256. No reviewer re-fetch is required to audit the enumeration.
`access_audit.json` and the frozen Newsroom robots file record the legal-access
decision and failed Blog-host checks.

The Blog `recent-news` UI was also inspected as a secondary closure check. It
exposes a public `Load More` control and a WordPress REST base, but requests to
the REST route were reset during this run. We did not bypass or increase
concurrency. The UI is not used as the mother table because it also omits some
category-specific posts from the first visible batch; the official Newsroom
archive includes those Blog URLs and labels them explicitly.

## Reproduce and validate

```bash
python3 scripts/build_official_article_manifest.py \
  --output news --years 2025 2026 --cutoff 2026-08-25 --delay 2.5
python3 scripts/validate_official_article_manifest.py
```

The collector uses a descriptive user agent, sequential requests, delay,
bounded retry, and content-level validation. An interrupted first pass was
resumed from valid same-run snapshots; it did not refetch those pages. Source
copyright remains with NVIDIA. These snapshots support research/audit and do
not imply a republication license.

Enumeration completeness does not imply body-review completeness. The latter
gate remains open until every mother-table row has one terminal processing
status and all year shards reconcile exactly to 765.
