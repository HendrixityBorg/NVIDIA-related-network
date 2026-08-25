# NVIDIA Partner Network complete shard

Research cutoff: `2026-08-25` (`Asia/Shanghai`). Publisher: NVIDIA
Corporation. Directory scope: the global `locale=en-us` NVIDIA Enterprise
Partner directory, preserving regional/legal-entity listings before grouping.

## Outcome

This environment could **not** complete a direct full-directory collection.
Both `robots.txt` and the directory were unreachable from the shell (HTTP/2
stream error, then IPv4 HTTP/1.1 connection reset). The public API host
identified by public Marketplace material timed out before any response, and
the available in-app browser had no connected browser instance. No login,
CAPTCHA, paywall, rate-limit bypass, proxy, alternate-IP evasion, or hidden
credential was used.

A public search index of the official NVIDIA page, crawled roughly three weeks
before the cutoff, reported `1 - 15 of 985 items` for the explicit global
locale and exposed nine listing cards. Those nine are retained as a transparent
fallback sample. `985` is **not** hard-coded as a completion target and is not
claimed as the live direct runtime total. The direct 66-page frontier is closed
as inaccessible, not processed; `validation_report.json` therefore sets
`complete=false`.

## Files

- `source_frontier.jsonl`: source/access states, including resolution sources.
- `access_audit.jsonl`: each access diagnostic and its failure semantics.
- `pagination_manifest.jsonl`: all 66 pages implied by the fallback count;
  none is marked pending or successfully fetched directly.
- `snapshots/search_index_fallback_2026-08-25.json`: redistributable structured
  notes from the official-page search snippet, not a copy of NVIDIA HTML.
- `raw_listings.jsonl`: nine append-only listing observations. Missing fields
  remain empty and explicitly marked unavailable; they are not inferred.
- `tag_observations.jsonl`: one row per observed NPN partner type or competency.
- `entity_groups.jsonl` and `listing_group_edges.jsonl`: group-level resolution
  that preserves every listing. AMAX Ireland and AMAX Suzhou map to one AMAX
  group because AMAX's official organization page identifies both as 100%
  group entities; 2CRSi and 2CRSi USA similarly remain two listings under one
  listed parent.
- `validation_report.json`: reconciliation and completion gates.
- `collect_npn.py`: fail-closed direct collector for a network where the public
  first-party page and robots policy can be reached.

## Reproduction

Run from this directory. The script uses the Python standard library only and
does not require credentials:

```bash
python3 collect_npn.py \
  --out reproduced \
  --locale en-us \
  --page-size 15 \
  --delay-seconds 2 \
  --timeout-seconds 20
```

The collector stops without requesting the directory if `robots.txt` cannot be
retrieved or disallows the directory. If access is allowed, it obtains the
runtime total from page 1, calculates the page frontier, performs low-frequency
ordinary GETs, saves gzipped HTML snapshots with SHA-256 hashes, and searches
only embedded public JSON for listing objects. It never equates a page count or
old search-index count with successful collection. If embedded data cannot be
parsed or listing count does not reconcile, it exits non-zero and records the
failure rather than claiming completeness.

## Interpretation limits

The fallback snippet does not expose listing IDs, profile URLs, partner levels,
specializations, locations, or profile-level product/service tags. Those fields
are null/empty. `competencies` are NPN program competency labels and describe
program participation/content; they are not treated as proof that a partner
supplies or buys a particular NVIDIA product. Corporate grouping and listed
status are separate research decisions with their own sources and uncertainty.
This artifact is research infrastructure only and is not investment advice.
