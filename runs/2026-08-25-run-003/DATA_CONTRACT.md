# Data contract

## Taxonomy nodes

Every node has `node_id`, `canonical_key`, `name`, `node_type`, `parent_id`,
`path`, `availability_state`, `source_id`, `source_url`, `accessed_at` and
`evidence_locator`. Allowed semantic node types are product, platform, software,
service, architecture, technology, reference_architecture, solution, workload,
use_case, industry, model, dataset, framework, SDK and library. Category is
navigation only. Product tree v2 is frozen in `product_tree_v2/`; v1 remains a
superseded input snapshot.

## Page sections and frontier

Every discovered in-boundary page ends in exactly one state: `processed`,
`processed_no_candidate`, `redirected`, `inaccessible`, `excluded`, or `failed`.
Every seed page section has a section record. `pending` is forbidden in a
frozen deliverable.

## Candidate observations

Observations are never deleted. Required fields include the source, publisher,
published/retrieved time, locator, observed entity string, page section,
nearby NVIDIA product/solution context, relationship hypotheses, semantic
status (`fact`, `inferred`, `unknown`), access note and content fingerprint.

## Entity and relationship claims

One listed parent can have multiple operating entities and multiple roles.
Each security identifier carries `listing_region` and the ISO alpha-2
`listing_region_code` derived from its actual exchange. Entity-level
`listing_regions` is the ordered union of those markets. Issuer `country` is a
separate domicile/headquarters attribute and is never inferred from an ADR,
GDR or OTC trading venue.
Claims deduplicate on:

`subject_entity_id + object_entity_id + direction + relationship_type + product_scope_id`.

Different roles or product scopes remain separate. Same-key observations attach
as evidence. Supplier direction is supplier `supplies_to` NVIDIA; customer
direction is NVIDIA `sells_to` customer; partner and peer are semantically
symmetric; investment direction is NVIDIA `invests_in` investee.

Commercial relationships also carry `commercial_directness`:
`direct`, `indirect`, `both`, or `unclear`. Non-commercial roles use
`not_applicable`. Directness is independent of `fact_status`: a filing may
explicitly confirm an indirect supplier, while a direct-looking transaction
may remain inferred if the source is only company news or third-party media.
Each evidence reference has an `evidence_role` of `primary`, `corroborating`,
or `lead_only`. Only primary/corroborating evidence can support a relationship;
lead-only news cannot by itself create a confirmed claim.

An ambiguous repeated partner may receive a low-confidence supplier/customer
inference only with at least two independent evidence families, main-business
alignment, consistent NVIDIA product context, a transaction/use signal and no
strong counterevidence. Such an inference records rationale, alternatives and
why it is not confirmed, and is capped below 60.

Partner counterparty filings are reviewed in the reverse direction. If a
counterparty filing states that NVIDIA is its customer, the counterparty is a
supplier to NVIDIA. If it states that it purchases, licenses, deploys or is
dependent on NVIDIA products, NVIDIA sells to that counterparty. Contract
manufacturers, distributors and component makers are not silently promoted to
direct suppliers: the claim must preserve `indirect` or `unclear` unless the
commercial path is explicit. NVIDIA's own 10-Q and 8-K are outside the NVIDIA
self-filing source boundary; those form types remain allowed when they are the
public regulatory filings of a Partner counterparty used for this reverse
verification.

Issuer-parent candidates that miss an exact alias or match multiple listed
issuers require a `researched_terminal` record conforming to
`listed_company_network.research_policy.ResearchedEntityResolution`. An alias miss alone is not a
terminal category. Inferred parent resolution is capped at 69 and retains its
research evidence. If multiple listed issuers remain plausible, every option
must have a comparable market cap on the same date and in the same currency;
the evidenced largest issuer is selected.

`approve_unknown` and `needs_more_evidence` decisions retain their original
terminal status and, where a listed endpoint is resolved, create respectively
unknown partner claims capped at 39 and inferred partner claims capped at 49.
Claims retain all relationship evidence plus materialized
`source_family=entity_resolution` evidence. Identity evidence is never counted
as relationship-source independence or relationship explicitness.

## NPN

Raw regional listings remain append-only. Group-level dedup never discards the
original listing. Capture raw partner types, competencies, specializations,
partner level, locations and any product/service tags. Group unions retain the
origin listing IDs for each tag.

## Peer

Peer claims use product-category scope, not SKU scope. The counterparty must be
listed and have a self-developed competing product/platform. Resellers,
integrators and NVIDIA-powered offerings alone do not qualify.
