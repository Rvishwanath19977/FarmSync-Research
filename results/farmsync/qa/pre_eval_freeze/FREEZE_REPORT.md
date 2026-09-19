# FarmSync Phase-3 — Pre-Evaluation Freeze Report

Generated: 2026-09-09T18:33:20Z

## Verdict

**PRE-EVALUATION FREEZE STATUS: PASS**
**READY FOR LIVE LLM INTEGRATION: YES**

## Checks

| Check | Result |
|---|---|
| authority | PASS |
| regressions | PASS |
| config_seed | PASS |
| repeatability | PASS |
| reconciliation_911 | PASS |
| solver_free_read | PASS |
| pre_post_zero_drift | PASS |
| browser_authority_still_valid | PASS |
| manifest_verify | PASS |

## Scope (discovered, not hard-coded)

| Category | Files | Rollup SHA-256 |
|---|---|---|
| scientific_source | 43 | 0ca93c4edf71ff5d |
| routes_templates_static | 4 | 767158ddaad05175 |
| scientific_tests | 22 | 00da208f3e82f97c |
| datasets | 20 | f3ea22aadf19b250 |
| qa_authority | 7 | 81e9908af52a06cc |
| authoritative_reports | 3 | 3d21f67352f3b3e5 |
| seed_rng_manifest | 2 | d62c4c32d45f8423 |
| frozen_artifacts | 52 | 2e299f061a46a49b |

manifest_core_sha256: `5365968196407f5983401c92a7636548ecbae6151f24220b8eb8837329805576`

## Frozen constants

- epsilon = 0.95
- lambda = 0.05
- alpha = 0.4
- fairness_version = fairness-v2
- action_policy_version = action-consent-v1
- uncertainty_version = uncertainty-v1
- instance_hash = 5ea24037c2d9cb6a
- replication_seeds_sha256 = 7224b558c8afc0071152f0b9d3bcc4d9972452f52a480ef333233facc981bf40

## Freeze philosophy

- The dataset is synthetic.
- The current working-plan mechanism is deterministic action-consent + canonical feasibility, NOT the collective MILP.
- Uncertainty/resilience are unavailable for the current edited working plan unless explicitly evaluated later.
- LLM functionality is NOT yet integrated into the frozen baseline.
- This is a pre-evaluation software/reproducibility checkpoint, not final research evidence.

## Non-goals (not performed by this freeze)
- No final30, no >=300 LLM benchmark, no live LLM, no publication Results.
- No PuLP/CBC on GET/page-load (verified in a fresh process).
- No dataset / B1-B2-B3 / allocation / feasibility / replanning change; no artifact regeneration.
- ε/λ/α, seeds and instance_hash unchanged.
