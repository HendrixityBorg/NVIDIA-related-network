# Non-NPN listed-entity / listed-parent research audit

Cutoff: 2026-08-25. Scope: frozen NVIDIA Blog, Newsroom, product/solution,
10-K/13F/presentation, acquisition-review and reviewed-peer inputs. NVIDIA
Partner Network (NPN) is deliberately excluded because it has a separate 800+
partner normalization pipeline. No frozen NVIDIA page was refetched, no access
control was bypassed, and no third-party full text is retained.

## Outcome

The canonical arti.research_policy.ResearchedEntityResolution ledger has 5,009
unique, terminal rows:

| Terminal category | Rows |
|---|---:|
| resolved_exact | 269 |
| resolved_inferred_parent | 29 |
| resolved_largest_listed_parent | 5 |
| private_or_delisted | 76 |
| non_entity | 839 |
| ambiguous_after_research | 3,791 |

The first 4,913 rows close the unified frozen frontier. An additional 96
source-native candidates close every previously unmatched row in the 2026
official-article raw-relation shard. The relation-priority subset contains
1,546 candidates: 251 exact listed issuers, 29 inferred listed parents, 5
largest-listed-parent representatives, 76 private/delisted, 645 non-entities
and 540 genuinely ambiguous-after-research.

The audit enumerated 13,616 observations before candidate normalization:

| Frozen source family | Observations |
|---|---:|
| Recovered NVIDIA Blog body observations | 2,050 |
| NVIDIA Blog anchor/entity mentions | 5,005 |
| NVIDIA filing / presentation / acquisition review | 5,438 |
| NVIDIA Newsroom press releases | 516 |
| NVIDIA product / solution pages | 594 |
| Reviewed peer candidates | 13 |

The 39 legally blocked Blog bodies remain explicit blind spots. Their
title/index material cannot promote a relationship or listed endpoint.

## Important endpoint decisions

- Geely is resolved_inferred_parent to Geely Automobile Holdings Limited
  (HKEX:0175), confidence 69 or lower. Both source-native observations
  robotics_av:RAV-C0052 and robotics_av:RAV-C0089 are in the canonical ledger.
- NTT DATA / NTT DATA Group / NTT Data Japan maps as an inferred
  acquired/wholly-owned subsidiary endpoint to active listed parent NTT
  (TSE:9432). NTT DATA Group code 9613 was delisted on 2025-09-26. The mapping
  cites the JPX delisting notice and NTT transaction announcement.
- Samsung, Hyundai Motor Group, SK Group, LG Group and Doosan Group retain
  every listed candidate and use the largest evidenced 2026-08-25 market-cap
  candidate only as an inferred representative. Selected representatives are
  Samsung Electronics, Hyundai Motor, SK hynix, LG Energy Solution and Doosan
  Enerbility. Each option has a common USD/as-of basis and its own evidence ID.
- Brand/subsidiary mappings are inferred endpoints; direct issuers are exact.
  Entity-resolution evidence never proves or scores the NVIDIA relationship.

## Integration policy

approve_unknown and needs_more_evidence observations may enter Partner review
only when the resolution selects a confirmed listed issuer or parent.
Non-entity, private/delisted and ambiguous terminal rows select no entity and
cannot create graph edges. Article investment language never creates an
investee claim; investees remain restricted to the latest NVIDIA 13F.

The additive registry contains 75 evidence-backed issuer endpoints needed by
this shard. The relationship-builder dry run loaded all 5,009 resolutions and
left zero low-status decisions without a researched-resolution ID. Its
entity-resolution gates passed; the isolated run's remaining product-scope
gate belongs to the separate relationship-builder integration, not this entity
research ledger.

## Main files

- researched_resolution_ledger.jsonl — canonical 5,009-row schema ledger.
- canonical_candidate_review.jsonl — exact 5,009-row validation population.
- researched_entity_registry_overlay.jsonl — additive listed endpoint registry.
- mapping_evidence_researched.jsonl — mapping/listing evidence.
- researched_resolution_audit_detail.jsonl — 1,546 relation-priority details.
- full_frontier_terminal_ledger.jsonl — 4,913 frontier closure rows.
- blocked_article_blind_spots.jsonl — 39 blocked Blog bodies.
- researched_resolution_validation_report.json — canonical validation PASS.
- relationship_builder_dry_run_summary.json — isolated integration run.

## Reproduce and validate

Run, from the repository root:

    python3 arti/runs/2026-08-25-run-003/agents/non_npn_listing_audit/build_audit.py
    python3 arti/runs/2026-08-25-run-003/agents/non_npn_listing_audit/build_researched_resolution.py
    python3 arti/runs/2026-08-25-run-003/agents/non_npn_listing_audit/build_canonical_research_ledger.py
    PYTHONPATH=arti/src python3 arti/runs/2026-08-25-run-003/agents/entity_resolution_complete/validate_researched_resolutions.py --candidate-review arti/runs/2026-08-25-run-003/agents/non_npn_listing_audit/canonical_candidate_review.jsonl --ledger arti/runs/2026-08-25-run-003/agents/non_npn_listing_audit/researched_resolution_ledger.jsonl --global-overlay arti/runs/2026-08-25-run-003/agents/non_npn_listing_audit/validator_combined_overlay --report arti/runs/2026-08-25-run-003/agents/non_npn_listing_audit/researched_resolution_validation_report.json

The SEC screen is a separate bounded network step and need not be rerun to
understand or validate the frozen delivery. If deliberately refreshed, it
makes one fair-access request and retains only filtered matches plus source
hash/audit metadata.

## Limitations

An exact SEC-name miss is not proof of global non-listing. The 3,791 ambiguous
rows are deliberately fail-closed; many are mention-only names, OCR fragments
or private-company-like strings for which frozen evidence cannot safely
establish an issuer or parent. Market caps are third-party rounded figures used
only for relative selection. Ownership mappings remain inferred relationship
endpoints even when the ownership fact is explicit.
