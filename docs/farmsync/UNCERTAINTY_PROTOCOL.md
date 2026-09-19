# FarmSync — Uncertainty Protocol

**Status:** uncertainty-protocol-v1-FROZEN-IMPLEMENTED (2026-08-24)

All uncertainty-v1 methodological parameters are frozen (see §24). NO code, datasets, solver settings,
epsilon/lambda/alpha, action-consent policy, master seeds, frozen artifacts, or existing scientific
results are changed by this document. Implementation is gated on this frozen design.

**Framing.** FarmSync performs **paired scenario-based uncertainty evaluation** using **synthetic
exogenous uncertainty realisations**. For each seed, uncertainty inputs are drawn reproducibly and the
EXISTING deterministic optimisation is solved under that realised scenario. This is **not** stochastic
programming / stochastic optimisation. Phase-5 resilience remains a separate deterministic
counterfactual stress test (§11). Every severity and frequency below is **SYNTHETIC_EXPERIMENTAL — NOT
an empirical Indian agricultural frequency or probability.**

---

## 1. Purpose

Provide a deterministic, reproducible, paired framework so B1/B2/B3/Proposed can be evaluated under the
same synthetic weather, market, resource, and participation realisations across the 30 frozen seeds,
without conflating this exogenous uncertainty with the deterministic Phase-5 resilience tests, and
without the uncertainty draw depending on any experiment outcome.

---

## 2. Factual current-state audit (read-only)

- **RNG substreams (frozen, 30 seeds):** `farmer_response` (in use by the frozen action-consent
  protocol — untouched here), plus `participation_scenario`, `weather_hazard`, `market_shock`,
  `resource_shock` — the latter four currently **UNUSED** by any runtime code (clean 1:1 mapping).
- **`climate_scenarios` — POPULATED (40 rows = 8 scenarios × 5 regions):** baseline ET0 per
  region/season is present and **sourced**; ET0 is currently identical across scenario labels (shock
  magnitudes were left as experimental parameters). uncertainty-v1 supplies ET0 **multipliers** and
  does not modify the sourced baseline ET0 values.
- **`participation_scenarios` — POPULATED (5 rows):** `participation_rate` {1.0, 0.9, 0.75, 0.6, 0.4};
  the `non_response_rate`/`withdrawal_rate` columns are empty by design (those are `farmer_response`),
  supporting participation = pre-offer membership.
- **`market_scenarios` — SCHEMA-ONLY (0 rows):** columns `price_change, absorption_change,
  cost_change`. uncertainty-v1 freezes price and absorption multipliers (below) and does **not**
  activate `cost_change`.
- **Operational price basis:** `op_price(region_id, crop)` returns the **AGMARKNET market**
  (median monthly modal) price, basis `AGMARKNET_MARKET(...)`. **MSP is demoted to a REFERENCE** and is
  NOT applied as a floor in the operational price.
- **Absorption cap:** `op_absorption(crop)` is a **GLOBAL crop-level** cap (no region argument).
- **Constraints:** per-farmer `cultivation_budget` + `labour_capacity`; global crop absorption caps;
  ET0/NIR/CWR water-feasibility pathway; plot `available_water_m3`; FAO-33 `Ky` available.
- **Phase-5 resilience:** ZERO RNG references — fully deterministic counterfactual (N-1 +
  hazard-zone), never realised; categorically separate from this layer.

---

## 3. Terminology

- **Uncertainty realisation** — the per-seed draw of weather/market/resource/participation states
  applied to planning inputs for a cycle.
- **Channel** — one of four independent sources (W/M/R/P), each perturbing only its own variable.
- **Paired realisation** — the identical realisation reused across B1/B2/B3/Proposed for a seed.
- **SYNTHETIC_EXPERIMENTAL** — provenance tag on every unsourced severity/frequency.
- **CONDITIONAL-ON-OPTIMAL** — continuous metrics summarised only over Optimal runs, with n shown.

---

## 4. Causal timeline (frozen; compatible with current code)

```
STAGE A  frozen synthetic instance (instance_hash 5ea24037c2d9cb6a)
STAGE B  baseline planning inputs (ET0/price/absorption/budget/labour, unperturbed)
STAGE C  UNCERTAINTY REALISATION (drawn from frozen substreams; depends only on seed + frozen params):
           C1 participation_scenario -> eligible collective membership (BEFORE any offer)
           C2 weather_hazard        -> ET0 multiplier (region × season)
           C3 market_shock          -> price (crop × region) and absorption (crop global) multipliers
           C4 resource_shock        -> shared budget+labour multiplier (per farmer)
STAGE D  B1/B2/B3/Proposed receive the SAME paired realisation + population (§10)
STAGE E  initial plan / offer generation on perturbed inputs (B3 planned for Proposed)
STAGE F  farmer actions + commitments (farmer_response; frozen action-consent, unchanged)
STAGE G  action-adjusted deterministic reoptimisation (existing ro/co machinery)
STAGE H  renewed consent (existing action-consent layer)
STAGE I  FINAL_REALIZED (consented-only)
STAGE J  OPTIONAL, SEPARATE Phase-5 deterministic resilience stress test — reported separately.
```

Stage C is a NEW pre-optimisation input-perturbation layer feeding the EXISTING optimisation + action
stages; it requires no optimiser change and never sees Stage I outcomes.

---

## 5. Participation uncertainty (channel P) — FROZEN

- **Definition:** pre-offer availability to enter collective planning. Distinct from `farmer_response`
  (post-offer ACCEPT/REJECT/MODIFY/NO_RESPONSE/WITHDRAW) — no double counting.
- **Mechanism:** per-farmer Bernoulli from `participation_scenario`,
  `u = uniform01(sha256(substream:farmer_id:cycle_id:participation))`; include iff
  `u < participation_rate`. A non-participating farmer and their plots are absent from the decision set
  for the cycle; land is not reassigned; no offer is generated; therefore no farmer_response action.
- **PRIMARY / core UP:** `participation_rate = 0.90`.
- **Descriptive sensitivity (separate, NOT in the inferential family):** the ladder
  {1.00, 0.90, 0.75, 0.60, 0.40} is retained as a descriptive participation sensitivity only; it is
  NOT expanded into extra core uncertainty conditions.

---

## 6. Weather uncertainty (channel W) — FROZEN

- **Perturbed variable:** reference evapotranspiration **ET0** (region × season), flowing through the
  EXISTING CWR/NIR/water-requirement pathway into deterministic plot/crop feasibility.
- **Three discrete ET0 states** (labels chosen to reflect an ET0-only mechanism, NOT the full climate
  taxonomy):
  - `LOW_EVAPORATIVE_DEMAND`: multiplier 0.90, probability 0.20
  - `NORMAL`: multiplier 1.00, probability 0.60
  - `HIGH_EVAPORATIVE_DEMAND`: multiplier 1.15, probability 0.20
- **Granularity:** once per region × season × cycle, from `weather_hazard`
  `u = uniform01(sha256(substream:region_id:season:cycle_id:weather))` — shared regional/seasonal
  exposure (correlated), not independent per-farmer noise.
- **PRIMARY effect is ET0-only.** `ET0' = ET0_base × m_W` → existing CWR/NIR/water-requirement →
  deterministic feasibility. **No additional Ky yield penalty is applied in uncertainty-v1 PRIMARY**,
  because the hard water-feasibility pathway already represents water sufficiency; adding a second
  Ky yield-loss without a separately validated partial-water formulation could double-count the same
  stress. `Ky` remains available for a separately approved future weather-yield sensitivity but is NOT
  part of uncertainty-v1 PRIMARY or core final30.
- Baseline ET0 values are not modified. Multipliers/probabilities are SYNTHETIC_EXPERIMENTAL, not
  empirical climate frequencies. Non-negativity preserved.

---

## 7. Market uncertainty (channel M) — FROZEN

Two SEPARATE factors; **`cost_change` is NOT activated in uncertainty-v1** (cultivation cost is not
perturbed).

**Price.**
- Multipliers: `LOW 0.90 / NORMAL 1.00 / HIGH 1.10`; probabilities `0.25 / 0.50 / 0.25`.
- Granularity: crop × region, from `market_shock`
  `u = uniform01(sha256(substream:crop_id:region_id:cycle_id:price))`.
- **Equation:** `price' = price_AGMARKNET × m_price`, subject only to **non-negativity**.
- **MSP is NOT a floor.** The operational price basis is AGMARKNET market (median monthly modal) and
  MSP has been demoted to a REFERENCE. The shocked price is never clipped or replaced by MSP. MSP may
  be retained in metadata/reporting only as a reference comparison (e.g., whether a shocked price falls
  below the MSP reference); it must not alter the operational shocked price.

**Absorption / market cap.**
- Multipliers: `LOW 0.85 / NORMAL 1.00 / HIGH 1.15`; probabilities `0.20 / 0.60 / 0.20`.
- Granularity: **crop GLOBAL** (matching `op_absorption(crop)`), once per crop × cycle, from
  `market_shock` `u = uniform01(sha256(substream:crop_id:cycle_id:absorption))`. NOT crop × region.
- **Equation:** `absorption' = absorption_base × m_abs` (non-negative). AGMARKNET arrivals remain an
  absorption proxy and are never called demand.

---

## 8. Resource uncertainty (channel R) — FROZEN

- **One shared resource-capacity state per farmer** (not independent budget/labour distributions):
  - `NORMAL`: multiplier 1.00, probability 0.70
  - `CONSTRAINED`: multiplier 0.85, probability 0.30
- **Draw:** once per farmer per cycle from `resource_shock`
  `u = uniform01(sha256(substream:farmer_id:cycle_id:resource_state))`.
- **Application:** the SAME drawn multiplier scales BOTH `cultivation_budget` and `labour_capacity`.
- **NOT perturbed in v1:** cultivation costs (avoids double-count with any market cost factor) and
  `available_water_m3` (weather already perturbs crop water requirement; water-supply uncertainty is
  intentionally left out of v1 to preserve channel separation and avoid an extra unfrozen parameter).
- **Locks / physical state:** applied at planning-input time; cannot un-plant a HARD_LOCK/PLANTED
  allocation. Non-negativity enforced. Values are SYNTHETIC_EXPERIMENTAL.

---

## 9. RNG / substream design — FROZEN

One channel ↔ one frozen substream (participation_scenario / weather_hazard / market_shock /
resource_shock); `farmer_response` untouched. Sub-seeds via existing `experiment.substream(seed,
stream)`; master 30-seed list unchanged. All draws deterministic, keyed, order-independent, and
platform-independent (no timestamp/UUID). cycle_id = master seed. The same realisation for a seed is
reused across methods (§10).

---

## 10. Draw granularity, equations & paired baseline rules — FROZEN

```
Weather      region × season   ET0'        = ET0_base × m_W       m_W ∈ {0.90(.20),1.00(.60),1.15(.20)}
Market price crop × region      price'      = price_AGMARKNET × m_price  {0.90(.25),1.00(.50),1.10(.25)}  (NO MSP floor)
Market abs.  crop GLOBAL        absorption' = absorption_base × m_abs    {0.85(.20),1.00(.60),1.15(.20)}
Resource     farmer             budget',labour' = base × m_R  (same m_R) {1.00(.70),0.85(.30)}
Participation farmer            include iff uniform01(key) < 0.90
Farmer response  existing farmer/plot mechanism — unchanged
```

**Paired baseline interpretation.** For each seed, B1/B2/B3/Proposed receive the identical exogenous
realisation and the identical participating population. Farmer-response + renewed-consent (Stages F–H)
are **Proposed-only**. Therefore method-level B1/B2/B3/Proposed comparisons use comparable
PLANNED/optimised tiers; Proposed-only INITIAL_REALIZED / RECOMMENDED_REVISED / FINAL_REALIZED are
deployment outcomes analysed separately. Baselines are never given synthetic farmer response for
symmetry; a tier a baseline lacks is reported N/A, not fabricated. A baseline's PLANNED output is never
compared directly against Proposed FINAL_REALIZED as if equivalent.

---

## 11. Joint scenario (UJ) & Phase-5 separation — FROZEN

UJ activates all four channels via their independent substreams. **No overall risk multiplier, no
interaction coefficient, no hidden cross-channel dependency.** Channels touch disjoint variables
(W→ET0/NIR/water feasibility; M→price + crop-global absorption cap; R→budget + labour; P→pre-offer
membership) and compose only through the existing deterministic planning constraints.

Phase-5 remains unchanged and separate: N-1 producer failure, hazard-zone outage, deterministic
counterfactual, no RNG, recommendation/recovery potential — not a probability. Phase-5 observations are
never merged into UJ or called realised weather events.

---

## 12. Optimisation / infeasibility semantics — FROZEN (no imputation)

- Only solver status **Optimal** yields allocations; no pseudo-solution from a non-Optimal solve.
- Infeasibility is a valid outcome; **never** treated as zero cash; fairness/concentration/locks are
  never relaxed to force a solution.
- Report per method × condition: `n_total, n_optimal, n_infeasible, infeasibility_rate`, and
  `failed_stage` counts.
- Continuous metrics (cash/fairness/area) are summarised **over Optimal runs only**, with exact n and
  a CONDITIONAL-ON-OPTIMAL label.
- Paired continuous tests use only seeds where BOTH compared runs are Optimal; report `n_pairs`; never
  silently drop a seed (it still appears in reliability/infeasibility analysis).
- Paired binary feasibility comparison: exact **McNemar** where inferential testing is appropriate and
  discordant pairs exist; otherwise report paired counts / risk difference descriptively.
- The Phase-5 numeric-only fairness-floor tolerance is NOT generalised to uncertainty-v1.

---

## 13. Provenance

SYNTHETIC_EXPERIMENTAL: all weather/market/resource multipliers + probabilities, participation level,
ablation set. SOURCED_BASELINE: baseline ET0, AGMARKNET prices, baseline budget/labour. MSP is a
reference only. DETERMINISTIC_RULE: channel equations, pairing, infeasibility handling, Phase-5
separation. FROZEN_INPUT: five substreams + canonical instance. GENERATED_RESULT: per-seed realisations
and metrics (not yet produced). No unsourced value is labelled empirical.

---

## 14. Metrics

Economic: planned / initial-realised / recommended-revised / final-realised cash; cash retention vs the
U0 (no-shock) counterpart; downside/loss. Land/participation: utilised area, participation, realised
area, withdrawn/unavailable area. Fairness: fairness-v2 primary per-ha Gini (+ supporting absolute
Gini; capable worst-off / fairness floor where applicable) against the canonical B1 reference
(₹14,644,537). Stability: plots changed, area changed, soft-lock disruption, renewed-consent prompts,
churn/replanning burden. Concentration: max largest-producer share, mean HHI. Resilience: Phase-5
metrics kept SEPARATE but linkable by seed. Reliability: solver Optimal/infeasible counts, constraint
violations = 0, consent coverage = 1.0 for FINAL_REALIZED, recommendation-to-realisation ratio.
Uncertainty-specific: loss vs U0 counterpart, recovery after action-driven reoptimisation, variance
across paired replications, factor-specific sensitivity.

---

## 15. Core ablations — FROZEN (exactly six)

```
U0 = no uncertainty        UW = weather only       UM = market only
UR = resource only         UP = participation only UJ = joint (W + M + R + P)
```
No Cartesian severity grid. Action-layer sensitivity (S1/S2 from ACTION_CONSENT_PROTOCOL) is a SEPARATE
analysis and is **not** crossed with UJ in uncertainty-v1 core (no S×U factorial in v1).

---

## 16. Final-30 statistical design — FROZEN (design only; DO NOT RUN)

Frozen 30 seeds only; no cherry-picking. Descriptive per method × condition: mean, median, SD, IQR, n,
95% CI. **95% CIs** via deterministic bootstrap, **10,000 resamples**, fixed **analysis-only bootstrap
seed = 20260812** (an analysis constant, NOT a FarmSync scientific substream; it does not alter the
five substreams). Primary paired continuous inference: two-sided **Wilcoxon signed-rank** paired by
seed, with **matched-pairs rank-biserial** effect size (NOT Cliff's delta); zero/tied differences
handled deterministically and documented (Pratt handling where supported). Multiplicity: **Holm**
within PREDEFINED metric families (below), not across every descriptive number. Deterministic
single-factor sensitivity sweeps are descriptive only (no significance tests). Infeasible runs are
included per §12; no seed excluded.

**Predefined metric families (fixed before final30):**
- **A. Planning / method comparison** (B1/B2/B3/Proposed at comparable PLANNED/optimised tiers only):
  total cash return; fairness-v2 per-ha Gini; land utilisation; concentration max-largest-producer
  share where available. Proposed FINAL_REALIZED is NOT compared to a baseline PLANNED as equivalent.
- **B. Proposed deployment** (within Proposed): FINAL_REALIZED cash retention vs Proposed PLANNED;
  FINAL_REALIZED cash vs U0 counterpart; recommendation-to-realisation ratio; replanning/churn burden.
- **C. Reliability:** Optimal vs infeasible; hard-constraint violations; consent coverage.
Secondary metrics remain descriptive/exploratory and are labelled as such.

---

## 17. Invariants

1. Uncertainty draws depend only on (seed, frozen params) — never on outcomes.
2. Same seed → identical paired realisation + population across B1/B2/B3/Proposed.
3. Each channel perturbs only its own variable; no cross-channel/overall multiplier.
4. All perturbed quantities non-negative; the shocked market price is NOT MSP-floored.
5. HARD_LOCK/PLANTED never un-planted by any shock.
6. Optimal-only extraction; infeasible recorded, never relaxed, never imputed.
7. Participation ≠ farmer_response (no double-counted dropout).
8. Phase-5 resilience never merged into or relabelled as general uncertainty.
9. `farmer_response` substream and all frozen artifacts unchanged.
10. Every severity/frequency tagged SYNTHETIC_EXPERIMENTAL.

---

## 18. Edge cases

- Weather HIGH_EVAPORATIVE_DEMAND makes a plot's only feasible crop infeasible → plot drops from the
  eligible set deterministically (feasibility), not via a cash hack.
- Shocked price below MSP reference → recorded in metadata only; operational price stays the shocked
  AGMARKNET value (no clipping).
- Resource CONSTRAINED below any feasible plan → infeasible outcome recorded (not relaxed/imputed).
- Joint infeasibility → first failing stage recorded; reported per method.
- Baseline lacking a tier under a shock → tier = N/A.
- Non-participating farmer with a would-be hard-lock → out of scope (participation is per-cycle
  pre-planning; hard-locks belong to an in-progress cycle, not re-drawn).

---

## 19. Limitations

Severities are experimental, not empirical; external validity not claimed. Single planning cycle per
seed; single renewed-consent pass. Weather is region/season correlated, not spatially autocorrelated
beyond region, and ET0-only in v1 (no Ky yield channel). Market cost and water-supply uncertainty are
excluded from v1 by design. Participation is a simple Bernoulli membership model. Phase-5 remains a
deterministic counterfactual.

---

## 20. Proposed implementation architecture (NOT executed)

1. `farmsync/config.py`: frozen SYNTHETIC_EXPERIMENTAL uncertainty block (version, the multipliers +
   probabilities above, participation 0.90, six-ablation set, analysis bootstrap seed 20260812).
2. `farmsync/proposed/uncertainty.py` (new): keyed per-channel draws returning a `Realisation`
   (per-region/season weather state, per-crop/region price mult, per-crop absorption mult, per-farmer
   resource mult, participating-farmer set); pure functions, NO solver authority.
3. Stage-C application shims: apply the realisation to ET0/price/absorption/budget/labour/membership,
   feeding the EXISTING optimisation + action-consent stages (no optimiser change).
4. Ablation runner U0/UW/UM/UR/UP/UJ over frozen seeds — build only; do not run final30.
5. Metrics/aggregation extending the action layer's four-tier output with uncertainty fields +
   reliability/infeasibility reporting.
6. Phase-5 kept separate (Stage J), linked by seed.

## 21. Proposed tests (NOT executed)

Determinism (same seed→same realisation); order-independence (shuffled entities→identical draws);
channel independence (perturbing one channel leaves others' variables unchanged); paired reuse across
methods; non-negativity; **shocked price NOT MSP-floored**; absorption is crop-global (one draw per
crop, identical across that crop's regions); weather is ET0-only (no Ky penalty applied); resource
multiplier identical for budget and labour; participation excludes farmers pre-offer and is disjoint
from farmer_response; infeasible outcome recorded (no imputation, no relaxation); Phase-5 unchanged and
separate; provenance tags SYNTHETIC_EXPERIMENTAL; frozen artifacts + `farmer_response` substream
byte-identical.

## 22. (reserved)

## 23. Scientific / manuscript audit (no edits made)

- **vs ACTION_CONSENT_PROTOCOL:** compatible; participation (pre-offer) and farmer_response
  (post-offer) disjoint; uncertainty feeds Stage C before the action layer.
- **vs Phase-5:** no conflict; Phase-5 stays a separate deterministic counterfactual (Stage J).
- **vs Methods 2.1–2.20:** sentences implying deterministic single-scenario evaluation, MSP-flooring of
  prices, crop×region absorption, or a Ky weather-yield effect in the core evaluation would become
  inaccurate once implemented and must be revised LATER (not now). MSP must be described as a reference,
  not a floor.
- **Data/schema:** `market_scenarios` empty → market multipliers frozen here (values in §7/§10);
  `climate_scenarios` ET0 shock magnitudes undifferentiated → weather multipliers frozen here;
  `participation_scenarios` usable as-is.
- **Dependencies:** Stage-C shims depend on op_price/op_absorption/ET0/budget/labour accessors, all of
  which exist.

## 24. Decisions — RESOLVED / FROZEN

1. **Weather:** ET0 states LOW 0.90 (0.20) / NORMAL 1.00 (0.60) / HIGH 1.15 (0.20), per region×season;
   ET0-only, **no Ky penalty** in v1. **FROZEN.**
2. **Market price:** 0.90/1.00/1.10 at 0.25/0.50/0.25, crop×region; `price'=AGMARKNET×m`,
   **no MSP floor** (MSP reference only). **FROZEN.**
3. **Market absorption:** 0.85/1.00/1.15 at 0.20/0.60/0.20, **crop GLOBAL**. **FROZEN.**
4. **Market cost:** `cost_change` NOT activated in v1. **FROZEN.**
5. **Resource:** shared per-farmer state NORMAL 1.00 (0.70) / CONSTRAINED 0.85 (0.30) applied to BOTH
   budget and labour; costs and water NOT perturbed. **FROZEN.**
6. **Participation:** PRIMARY/core 0.90; the {1.0…0.4} ladder is a separate descriptive sensitivity,
   not in the inferential family. **FROZEN.**
7. **Draw granularity:** weather region×season; price crop×region; absorption crop-global; resource
   farmer; participation farmer; farmer_response unchanged. **FROZEN.**
8. **Core ablations:** U0/UW/UM/UR/UP/UJ (six); no S×U cross in v1. **FROZEN.**
9. **Infeasibility:** no imputation; Optimal-only continuous summaries with n; paired tests on
   both-Optimal seeds; McNemar for paired feasibility; every seed retained in reliability analysis.
   **FROZEN.**
10. **Final-30 statistics:** descriptive + bootstrap 95% CI (10,000 resamples, analysis seed 20260812)
    + two-sided Wilcoxon signed-rank + matched-pairs rank-biserial + Holm within families A/B/C.
    **FROZEN.**

No unresolved uncertainty-v1 methodological parameter remains. All severities/frequencies are
SYNTHETIC_EXPERIMENTAL and are NOT empirical Indian agricultural frequencies or probabilities.

---

## 26. Implementation-correction note (2026-08-24)

Methodology unchanged. Corrections to the IMPLEMENTATION:
- **Infeasibility handling:** B1/B2/B3 (and Proposed) now read the ACTUAL solver status
  (`res.solver["status"]` / reopt status). Only Optimal exposes allocations/continuous metrics;
  non-Optimal yields a structured record `{status, optimal:False, failed_stage, cash:None, area:None}`.
  No pseudo-solution is extracted and zero is never imputed (helper `uncertainty.baseline_record`).
- **Realisation-hash provenance:** the Proposed/action layer now receives `uncertainty_condition` and
  `realisation_hash` from the SAME `Realisation` used by B1/B2/B3 and surfaces them in its meta; the
  hash is not recomputed inside Proposed. B1==B2==B3==Proposed share one realisation_hash.
- **Phase-5 separation:** the action-consent/uncertainty path uses `prepare_proposed_prerequisites`
  (no Stage-6). Phase-5 resilience is NOT executed under `uncertainty.apply()`. Standalone P6 retains
  Stage-6; Phase-5 artifacts/formulation unchanged.

---

## 27. Implementation-correction note (2026-08-24) — typed infeasibility only

Methodology unchanged. `run_uncertainty_condition` now catches ONLY the dedicated
`actions.ProposedInfeasibleError` (carrying `failed_stage`/`status`) for a non-Optimal Proposed
reopt/concentration; unexpected programming errors (KeyError/TypeError/etc.) PROPAGATE and fail the run
rather than being mislabelled as optimisation infeasibility. Baseline non-Optimal handling
(`baseline_record`) is unchanged. The action-layer commitment-after-acceptance correction (see
ACTION_CONSENT_PROTOCOL §23) supersedes the prior Proposed tier numbers; U0 baselines unchanged.
