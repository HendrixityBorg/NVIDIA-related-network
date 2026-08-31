# run-003: full-scope NVIDIA relationship research

Research cutoff: `2026-08-25` (`Asia/Shanghai`).

This run supersedes the pilot coverage claims from run-002. It is complete only
when every gate in `completion_gates.json` is satisfied. Company count is an
output, never a completion criterion.

Execution order:

1. close the seven official secondary product/solution sites and freeze product/solution tree v2;
2. enumerate and process every NVIDIA Newsroom and NVIDIA Blog article published from 2025-01-01 through the cutoff;
3. collect the runtime-reported complete NVIDIA Partner Network listing set, subject to robots and access review;
4. process the latest NVIDIA 10-K, latest 13F, and the explicitly scoped presentation set;
5. resolve listed entities, classify product-scoped multi-role relations, research category-level peers, score and review;
6. update the frozen snapshot, API, CLI, tests, README and reproducibility records.

Raw observations are append-only. Reviewed claims are deduplicated by resolved
entity pair, direction, relationship type and product/product-category scope.
