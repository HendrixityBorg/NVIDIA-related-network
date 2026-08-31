# Relationship review: supplier, customer, partner and investee

This shard reviews NVIDIA relationship observations and produces evidence-linked claims for resolved listed entities. Peer research and NPN are intentionally excluded.

## Input and closure

The builder processes every row from:

- `product_tree_v2/relation_candidates.jsonl`;
- the 2025 and 2026 official article `observations.jsonl` and available `raw_relation_observations.jsonl`;
- `filings_presentations_complete/listed_candidates.jsonl`;
- `filings_presentations_complete/13f_holdings.jsonl`.

The final frozen build additionally accepts two reviewed overlays:

- an official global-listing overlay for exact non-US issuer, alias and listed-parent resolution;
- `article_body_recovery/observations.jsonl` and `entity_mentions.jsonl` from the validated 597-article Blog recovery.

The listing overlay may resolve an exact alias or subsidiary/brand-to-listed-parent mapping only when the row carries an explicit confirmed-listed status and official listing provenance. It never authorizes fuzzy matching. Recovered anchor mentions enter the decision ledger, but an anchor alone cannot create a claim: ordinary store, game, tool and marketplace links, and GeForce NOW catalog/platform/publisher mentions without body relationship semantics, remain unknown.

A recovery ledger row may be terminal `access_blocked` after all permitted public routes are exhausted. Such an article counts toward ledger closure, not body coverage: any title/index-level material stays `approve_unknown` and is hard-blocked from generating confirmed or inferred claims.

Every input row receives exactly one terminal status in `decision_ledger.jsonl`:

- `approved`: creates one or more single-product claims;
- `approve_unknown`: if a listed endpoint is resolved, emits only an unknown Partner capped at 39; otherwise retains evidence and research terminal state;
- `needs_more_evidence`: if a listed endpoint is resolved, emits only an inferred Partner capped at 49; otherwise retains the researched terminal state;
- `reject`: duplicate derivative, out-of-scope peer, or explicitly non-listed/private observation.

No raw observation is deleted. `evidence_fingerprints.jsonl` merges repeated evidence only after hashing canonical URL, publisher, date, locator, source content fingerprint and excerpt. Multiple input decisions can point to one fingerprint.

## Direction and dedup contract

The exact dedup key is:

```text
subject_entity_id | object_entity_id | direction | relationship_type | product_scope_id
```

- supplier: `listed_entity -> NVIDIA`, direction `supplies_to`;
- customer: `NVIDIA -> listed_entity`, direction `sells_to`;
- partner: stored `NVIDIA -> listed_entity`, direction `partners_with`, semantically symmetric;
- investee: `NVIDIA -> listed_issuer`, direction `invests_in`.

Each claim has one `product_scope_id`. Different products and roles remain separate. Evidence with the same key is fingerprint-deduplicated and merged.

## Review boundaries

- Final claims require a resolved entity in `entity_resolution_complete/entity_registry.jsonl`. Exact `exchange:ticker` may resolve a latest-13F issuer such as Nokia to an existing registry entity.
- Generic logos, architecture diagrams, covers and co-mentions are unknown, not partner/customer facts.
- A logo/name on a titled presentation product or architecture slide remains `needs_more_evidence`; product co-context alone cannot create supplier, customer or partner claims. An explicit partner/ecosystem heading on a current NVIDIA product page is treated separately and may support a low-confidence inferred partner claim.
- Product-page placement under an explicit partner/ecosystem heading can support a partner claim, but never establishes supplier/customer direction by itself.
- Inferred supplier/customer claims require two independent evidence families after fingerprint dedup, business-model alignment, consistent product scope, direction-specific transaction/use/supply wording, and no strong counterevidence. Their score is capped at 59. Candidates that cannot prove business alignment remain `needs_more_evidence`.
- The only investee source is NVIDIA's latest 13F for 2026-06-30. Seven listed issuers are accepted. The private Space Exploration Technologies row is rejected. Investment wording in articles/presentations is quarantined and cannot create investee claims.
- The v1 snapshot is used only as a prior reviewed reference. It cannot create a run-003 claim without current evidence.

## Scoring

Confidence is 0–100 and records each component in `claims.jsonl` and `scoring_inputs.jsonl`:

- source authority: up to 25;
- explicitness: up to 25;
- resolved entity identity: 15;
- evidence-family/publisher independence: up to 10;
- timeliness: up to 10 using the frozen decay schedule;
- quantification: 10 for quantified 13F evidence;
- relationship-type/direction specificity: 5;
- conflict penalty where applicable.

Time decay is 100% for 0–90 days, 90% for 91–180 days, 75% for 181–365 days and 55% beyond 365 days. Current product pages use access time; the current 10-K and latest 13F remain current until superseded.

## Outputs

- `claims.jsonl`: final non-peer claims;
- `decision_ledger.jsonl`: one terminal decision per input observation;
- `evidence_fingerprints.jsonl`: source/evidence/provenance records;
- `scoring_inputs.jsonl`: explainable score inputs and caps;
- `conflicts.jsonl`: resolved source, identity and boundary conflicts;
- `validation_report.json`: build gates.
- `input_manifest.json`: exact input paths, row counts and SHA-256 hashes, plus overlay/recovery parameters.

## Reproduce

From the repository root:

```bash
python3 runs/2026-08-25-run-003/agents/relationship_review_complete/build_relationship_review.py
python3 runs/2026-08-25-run-003/agents/relationship_review_complete/validate_outputs.py
```

The final overlay-enabled invocation is:

```bash
python3 runs/2026-08-25-run-003/agents/relationship_review_complete/build_relationship_review.py \
  --global-listing-overlay runs/2026-08-25-run-003/agents/global_listing_overlay \
  --require-global-listing-overlay \
  --article-recovery-dir runs/2026-08-25-run-003/agents/article_body_recovery \
  --require-complete-article-recovery \
  --researched-entity-ledger runs/2026-08-25-run-003/agents/non_npn_listing_audit/researched_resolution_ledger.jsonl \
  --researched-entity-registry-overlay runs/2026-08-25-run-003/agents/non_npn_listing_audit/researched_entity_registry_overlay.jsonl \
  --require-researched-entity-ledger
python3 runs/2026-08-25-run-003/agents/relationship_review_complete/validate_outputs.py
```

No credentials are used. All source access notes are inherited from the upstream public-source shards. This research is not investment advice.
