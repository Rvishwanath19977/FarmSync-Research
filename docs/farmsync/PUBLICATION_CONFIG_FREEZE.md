# FarmSync — Publication Configuration Freeze

## 1. Status / version / date
**Status:** PUBLICATION-CONFIG-FROZEN. **Version:** `farmsync-publication-config-v1`. **Date:** 2026-08-24.
Frozen BEFORE final30. Single source of truth: `farmsync/config.py` (`PUBLICATION_*` constants).

## 2. Scope
Freezes the PRIMARY publication configuration (ε, λ, α, action profile, protocol versions) and records
the pre-final30 development-calibration evidence and selection rules for λ and α. Also records the
final action-consent traceability closure (consent provenance) and the MODIFY tie-break audit. No
methodology, dataset, seed, RNG, solver, or frozen-artifact change. No final30, no ≥300 LLM benchmark,
no live LLM, no UI, no manuscript Results.

## 3. Primary publication configuration
```
epsilon               = 0.95        (canonical B3 fairness-efficiency floor)
lambda                = 0.05        (Phase-3 stability penalty weight)
alpha                 = 0.40        (Phase-4 within-crop concentration cap)
action_profile        = PRIMARY
action_protocol       = action-consent-v1
uncertainty_protocol  = uncertainty-v1
fairness              = fairness-v2
formulation           = current ILP reference formulation (B1/B2/B3 + Phase-3/4)
solver                = centralized CBC 2.10.3 via PuLP 3.3.2 (OS-conditional threads; unchanged)
config_version        = farmsync-publication-config-v1
```

## 4. ε history and rationale
ε = 0.95 was frozen previously as the canonical B3 fairness-efficiency parameter (CANONICAL_B3_EPSILON),
with the B3 ε-frontier retained as audit evidence (`results/farmsync/audit/b3_epsilon_frontier.json`).
`PUBLICATION_EPSILON` is asserted equal to `CANONICAL_B3_EPSILON` in config. Unchanged this turn.

## 5. λ formulation
Phase-3 reoptimisation objective (UNCHANGED):
`maximize  E / E*  −  λ · (soft_disruption_area / soft_lock_area)`.
λ weights the soft-lock disruption penalty against normalised economic performance.

## 6. λ development evidence
From `results/farmsync/proposed/p3_lambda_frontier.csv` (development grid, all Optimal, hard_lock_ok True):
| λ | revised_cash | soft_disruption_rate | changed_soft |
|----|----|----|----|
| 0    | 12,359,219 | 0.0575 | 17 |
| 0.05 | 12,340,519 | 0.0313 | 13 |
| 0.10 | 12,340,519 | 0.0313 | 13 |
| 0.25 | 12,269,254 | 0.0157 | 9 |
| 0.50 | 12,269,254 | 0.0157 | 9 |
| 1.00 | 12,097,429 | 0.0000 | 0 |
λ=0.05 cuts soft-lock disruption 0.0575 → 0.0313 (~46%) while retaining 99.85% of the λ=0 economics
(12,340,519 vs 12,359,219). Provenance note: this frontier was generated under an earlier pipeline; the
Phase-3 λ FORMULATION is unchanged, so the qualitative λ→(disruption, economics) tradeoff it evidences
remains valid for selection. It is development-calibration evidence only — not a final30 result.

## 7. λ selection rule (development-calibrated, frozen before final evaluation/final30)
Interpretive rule applied to the development frontier: "choose the smallest strictly positive λ that
produces a meaningful reduction in soft-lock disruption relative to λ=0 while retaining near-maximal
economic performance." λ=0.05 is the smallest positive grid value; it delivers the meaningful
disruption cut at ~99.85% economic retention. **λ = 0.05 frozen.** This is a development-calibration
decision made from development evidence and frozen before final evaluation/final30 — not a threshold
defined in advance of seeing the frontier, not chosen for prettiness, not from final30, with no invented
statistical significance.

## 8. λ retained sensitivity values
λ ∈ {0, 0.05, 0.10, 0.25, 0.50, 1.00} retained as DESCRIPTIVE development/stability sensitivity evidence
only (separate from the PRIMARY analysis).

## 9. α formulation
Phase-4 concentration constraint (UNCHANGED): `q_fc ≤ α · Q_c` — a single farmer f's expected production
of active crop c may not exceed α of that crop's total expected production Q_c. Reported with max
largest-producer share (max_LPS), HHI (mean/median), and top-share where available.

## 10. α development evidence
From `results/farmsync/proposed/p4_alpha_frontier.csv` (λ=0.05, all Optimal, target_violations 0):
| α | revised_cash | economic_retention_pct | max_LPS | mean_HHI |
|----|----|----|----|----|
| 1.00 | 12,340,519 | 100.0 | 0.529 | 0.1178 |
| 0.60 | 12,340,519 | 100.0 | 0.529 | 0.1178 |
| 0.50 | 12,328,480 | 99.9  | 0.4954 | 0.1127 |
| 0.40 | 12,285,254 | 99.55 | 0.3988 | 0.1067 |
| 0.33 | 12,235,846 | 99.15 | 0.3297 | 0.0981 |
At α=0.40 the cap binds (max_LPS 0.3988 ≈ 0.40) while retaining 99.55% economics and mean HHI 0.1067.
Same provenance note as §6 (earlier pipeline; concentration FORMULATION unchanged; qualitative
α→(concentration, economics) tradeoff valid for selection). Development evidence only.

## 11. α selection rationale (pre-final30)
Interpretable design rule: "No single farmer may account for more than ~40% of expected production of an
active crop." α=0.40 enforces that ~40% cap (max_LPS 0.3988) at ~99.5% economic retention with zero
target violations. **α = 0.40 frozen** as the PRIMARY design threshold.

## 12. α retained sensitivity values
α ∈ {1.00, 0.60, 0.50, 0.40, 0.33} retained as DESCRIPTIVE concentration sensitivity evidence only.

## 13. Action profile
PRIMARY behavioural profile (frozen action-consent-v1 probabilities). Sensitivity profiles S1 (−0.15)
and S2 (+0.10) retained as separate behavioural-robustness evaluation, not part of PRIMARY.

## 14. Uncertainty protocol
uncertainty-v1 (FROZEN-IMPLEMENTED): paired scenario-based SYNTHETIC EXOGENOUS realisations, four
channels (W/M/R/P), conditions U0/UW/UM/UR/UP/UJ. Separate uncertainty evaluation family, not crossed
with ε/λ/α in PRIMARY.

## 15. Solver configuration
CBC 2.10.3 via PuLP 3.3.2, Optimal-only extraction, OS-conditional threads (Windows threads=0 /
non-Windows threads=1), timeLimit=120.

The original pre-publication configuration used gapRel=1e-4. Before any Final30 publication cell was
executed, DEV-only reproducibility diagnostics showed that CBC could return different near-optimal
incumbents while reporting Optimal, with downstream effects under the joint-uncertainty UJ condition.
The numerical stopping tolerance was therefore prospectively tightened to gapRel=1e-6 before Final30.
The scientific design, dataset, frozen 30 seeds, RNG streams, epsilon, lambda, alpha, action protocol,
uncertainty protocol, fairness formulation, and experiment matrix are unchanged. The historical
gapRel=1e-4 artifacts are preserved and are not rewritten.

Authoritative amendment:
`results/farmsync/audit/solver_amendment_pre_final30_v1.json`.

## 16. Fairness / formulation versions
fairness-v2; current ILP reference formulation (B1 unconstrained ILP; B2 total-cash reference; B3
ε-fairness floor; Phase-3 λ stability reopt; Phase-4 α concentration). Unchanged.

## 17. No-post-hoc-tuning rule
No parameter (ε/λ/α/action/uncertainty/seeds/solver) may be silently changed after observing final30.
Any later change to ε/λ/α requires: (1) explicit protocol amendment; (2) written justification;
(3) config version increment; (4) documentation of the original value; (5) disclosure that the
publication configuration changed.

## 18. Primary vs sensitivity analyses
PRIMARY: fixed ε=0.95 / λ=0.05 / α=0.40 / action PRIMARY. Separate sensitivity/evaluation families:
ε fairness-efficiency; λ stability; α concentration; action S1/S2 behavioural robustness; uncertainty
U0/UW/UM/UR/UP/UJ. Explicitly NOT a giant ε×λ×α×action×uncertainty Cartesian.

## 19. Provenance classification
ε: approved canonical fairness parameter. λ, α: development-calibrated EXPERIMENTAL DESIGN parameters
(SYNTHETIC_EXPERIMENTAL), selected pre-final30 by the documented rules above. action-consent-v1,
uncertainty-v1: frozen synthetic behavioural/uncertainty policies. All frozen before final30.

## 20. Limitations
λ and α are design parameters, NOT empirical Indian-agriculture constants and NOT regulatory
thresholds. The λ/α frontiers were generated under an earlier pipeline (formulation unchanged); they
justify the qualitative selection, not exact post-correction cash. Concentration control (α) does NOT
by itself guarantee hazard resilience — Phase-5 hazard protection is a separate empirical/result
question. Development checkpoint is a single seed (20260812), not final30.

## 21. Reproducibility fields
instance_hash 5ea24037c2d9cb6a (seed 20260812, base). Master analysis seed 20260812; 30 replication
seeds frozen. Substreams (seed 20260812): farmer_response 1120031581, participation_scenario
1267646869, weather_hazard 350915459, market_shock 150500057, resource_shock 30953779. Solver PuLP
3.3.2 / CBC 2.10.3. config_version farmsync-publication-config-v1.

## 22. Consent traceability audit result — CLOSED
Consent now carries `action_event_id` linking each consent to the exact ACCEPT ACTION ledger event that
authorised it. INITIAL ACCEPT logs the ACTION then creates the INITIAL consent with that event_id;
RENEWED ACCEPT logs a separate RENEWED ACCEPT ACTION row and a linked RENEWED CONSENT row; the
existing-consent exception reuses the original consent and its original action_event_id (no new
behavioural ACCEPT). The fabricated HARD_LOCK consent fallback was REMOVED — a HARD_LOCK/PLANTED without
a valid prior INITIAL ACCEPT consent now raises `ConsentProvenanceError`. Each CONSENT ledger row also
carries a structural `action_event_id` field pointing at its authorising ACCEPT ACTION (not parsed from
reason_code). FINAL_REALIZED is provenance-verified — every allocation must satisfy all of:
consent matches allocation (farmer, plot, exact crop, valid); consent_kind == decision_round; consent
cycle_id == current cycle; non-null action_event_id resolving to a real ledger ACTION with
behavioural_action == ACCEPT; referenced event farmer_id and plot_id match the allocation; referenced
event decision_round matches the consent's decision_round; referenced event cycle_id == current cycle;
and the referenced ACCEPT authorises the consent's crop (INITIAL → crop_before, RENEWED →
crop_recommended). `consent_coverage_final` = provenance-verified exact-crop ACCEPT consent /
FINAL_REALIZED count = 1.0. Provenance/invariant failures propagate and are NOT converted to solver
infeasibility (only genuine solver-stage `ProposedInfeasibleError` is recorded as optimal=False).

## 23. MODIFY tie-break audit result — FIXED
Frozen MODIFY-target policy: highest deterministic expected-net-return feasible admitted alternative,
tie-break by crop_id. Implementation previously tied by crop_name; crop_id and crop_name orderings are
not guaranteed identical, so the tie-break was corrected to crop_id. Ranking, feasibility, admission,
MODIFY probabilities, and optimiser authority are unchanged. Verified: no development allocation change
(U0/UJ scientific values identical), plus a controlled tie-case unit test.

## 24. Files changed
`farmsync/config.py` (PUBLICATION_* constants); `farmsync/proposed/actions.py` (action_event_id,
ConsentProvenanceError, removed HARD_LOCK fabrication, strengthened FINAL_REALIZED verification, MODIFY
crop_id tie-break); `tests/test_farmsync_actions.py` (traceability + tie-break tests; two prior tests
updated to provenance-accurate shape); `docs/farmsync/ACTION_CONSENT_PROTOCOL.md` (traceability note);
`docs/farmsync/PUBLICATION_CONFIG_FREEZE.md` (this file, NEW); `docs/farmsync/PROGRESS.md`.

## 25. Tests executed
Current state after the consent-provenance closures (2026-08-24): test_farmsync_actions.py 44 passed;
test_farmsync_uncertainty.py 22 passed; test_farmsync_proposed_p3.py 8 + p4 10 + ilp_v2 6 + portability
7 passed. U0 baselines B1 14,644,537 / B2 13,822,731 / B3 13,142,166;
Proposed U0 PLANNED 13,142,166 / INITIAL_REALIZED 11,953,688 / RECOMMENDED_REVISED 12,586,101 /
FINAL_REALIZED 12,362,577; UJ FINAL_REALIZED 11,208,457; coverage 1.0; reopt/conc Optimal. Frozen
artifacts + λ/α frontiers byte-identical; substreams unchanged. No experiment rerun. No tuning.
(This section supersedes the earlier "39 passed" figure recorded before the provenance closures added
the traceability/cycle/kind tests.)

## 26. Exact next step
PRE-PUBLICATION METHODOLOGY + IMPLEMENTATION AUDIT → UI/UX BUILD → live LLM smoke → ≥300 LLM benchmark →
final experiment readiness check → final30. (Do NOT begin in this turn.)
