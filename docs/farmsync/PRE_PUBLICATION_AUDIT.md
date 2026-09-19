# FarmSync — Pre-Publication Methodology + Implementation Audit

## 1. Executive status
**PASS WITH REQUIRED FIXES.** The implemented model, configuration, provenance and publication claims are
internally consistent and sufficiently frozen. No correctness/traceability defect was found in code; the
one code-touching issue was a documentation-only stale test count (fixed this turn). The remaining
"required fixes" are deliverables to author/freeze BEFORE the ≥300 benchmark and final30 — not defects in
existing behaviour. **FarmSync is approved to proceed to UI/UX BUILD.**

Audit is inspection-only: no final30, no ≥300 benchmark, no live LLM, no UI, no manuscript Results, no
parameter tuning. U0/UJ checkpoints re-verified exact; frozen artifacts byte-identical.

## 2. Methodology consistency — PASS
Cross-checked intended methodology ↔ code ↔ docs. B1 = unconstrained max-total ILP; B2 = total-cash
reference T*; B3 = ε-constraint max-min of per-farmer normalized return (cash/operated-area) over CAPABLE
farmers s.t. total cash ≥ ε·T* (`ilp_reference.b3_epsilon_ilp`, ε default = CANONICAL_B3_EPSILON = 0.95).
Efficiency floor = ε·T*. Structurally-incapable / zero-option farmers are excluded from the max-min
(`capable = [f for f in farmers if fcash[f]]`) — correct Rawlsian-among-capable interpretation, matching
the documented Gini caveat. Phase-3 λ objective `E/E* − λ·(soft_disruption_area/soft_lock_area)` with E*
at λ=0 and soft_lock_area denominator (0 ⇒ no penalty) matches `reoptimize.solve_phase3` and
PUBLICATION_CONFIG_FREEZE §5. Phase-4 `q_fc ≤ α·Q_c` per (farmer, active crop), Q_c = total expected
production, hard locks absolute, LPS/HHI explicitly pre-failure and revised-plan-only
(`concentration.py`). Phase-5 separates immediate N−1 exposure (`immediate_nminus1`) from post-shock
recovery (`post_shock_reopt`); hazard-zone outage supported. Optimal-only extraction throughout.

## 3. Implementation consistency — PASS
Action-consent causal ordering: fresh VIEWED/FLEXIBLE offers → one initial action per offer → commit
P3_MIXED_V1 to ACCEPTs only → action-adjusted reopt → renewed consent → FINAL_REALIZED. Consent
provenance chain is closed and structurally linked (see §6). Auxiliary solver statuses all guarded
(phase3_e_star / phase3_fairness_floor / phase4_e_star_alpha / phase4_fairness_floor_alpha) with typed
`ProposedInfeasibleError`; `ConsentProvenanceError` is a distinct invariant failure that propagates.
Numeric tolerances are scoped and documented: TSTAR_TOLERANCE (₹1, B2 agreement), FAIRNESS_FLOOR_NUMERIC_
TOL (CBC feasibility-scale), RESILIENCE_FLOOR_NUMERIC_TOL (1e-7, resilience only). No cross-scope leakage.

## 4. Data / provenance — PASS (with documented limitations)
Provenance labels enforced by `provenance.py` (`OBSERVED`/`DERIVED` require a source; `SYNTHETIC_GROUNDED`
requires an assumption; `SYNTHETIC_EXPERIMENTAL`). 500-farmer / 10-collective synthetic population over 5
regions; 14 crops, 13 admitted via region×season gate. DES APY → yields; DES Cost of Cultivation (A2+FL vs
C2) → costs; AGMARKNET → operational prices; arrivals used ONLY as an absorption proxy (never demand);
cotton lint→kapas conversion; FAO-56 CWR/NIR with effective-rainfall handling. Raw-source manifest hash
cc271fdd594451b2, processed dataset hash 9984aa9948740c06, gate hash 9f81463dd4c127a5, generator hash
dbaa11e4a4684199, replication-seed-file hash 7224b558c8afc007 — all recorded in
`results/farmsync/audit/experiment_manifest.json`. Reproducible under the frozen dataset. Limitation:
absorption is a proxy, not demand; synthetic population is not claimed as an empirical Indian sample.

## 5. Publication configuration — PASS
`config.py`: PUBLICATION_CONFIG_VERSION farmsync-publication-config-v1; PUBLICATION_EPSILON 0.95
(asserted == CANONICAL_B3_EPSILON); PUBLICATION_LAMBDA 0.05; PUBLICATION_ALPHA 0.40;
PUBLICATION_ACTION_PROFILE PRIMARY; action-consent-v1; uncertainty-v1; fairness-v2. Solver CBC 2.10.3 /
PuLP 3.3.2, OS-conditional threads, timeLimit 120, gapRel 1e-6 following the documented pre-Final30 numerical-reproducibility amendment. λ and α are correctly documented as
development-calibrated experimental DESIGN parameters, frozen before final evaluation/final30, from
development frontier evidence — not empirical/regulatory constants, not selected from final30. Sensitivity
families are kept separate; there is NO implicit ε×λ×α×action×uncertainty Cartesian. §25 stale test count
corrected this turn (39 → 44/22/31); no scientific change.

## 6. Action / consent — PASS
`Consent(farmer_id, plot_id, crop, consent_kind, decision_round, cyc, valid, action_event_id)`. INITIAL
ACCEPT emits the ACTION, captures its event_id, then links the INITIAL consent; RENEWED ACCEPT emits a
separate RENEWED ACCEPT ACTION row + a linked RENEWED CONSENT row; existing-consent exception reuses the
original consent + original action_event_id. No fabricated HARD_LOCK consent (fail-loud
`ConsentProvenanceError`). `verify_consent_provenance` checks: consent↔allocation exact match; consent_
kind == decision_round; consent.cyc == cycle; action_event_id resolves to a real ACCEPT ACTION with
matching farmer/plot/decision_round/cycle; and the ACCEPT authorises the crop (INITIAL → crop_before,
RENEWED → crop_recommended). CONSENT ledger rows carry a structural `action_event_id`. FINAL_REALIZED
coverage is provenance-verified = 1.0. ACCEPT/REJECT/MODIFY/NO_RESPONSE/WITHDRAW semantics conform to the
frozen protocol; MODIFY tie-break by crop_id.

## 7. Uncertainty — PASS
uncertainty-v1: four channels reaching real optimiser inputs — W (ET0 mult, region×season, no Ky), M
(AGMARKNET price mult crop×region + crop-global absorption mult, no MSP floor, no cost), R (one per-farmer
mult on budget AND labour), P (pre-offer Bernoulli membership, plots removed before planning). Conditions
U0/UW/UM/UR/UP/UJ. One paired Realisation per (seed, condition) with a deterministic realisation_hash
reused across B1/B2/B3/Proposed. Scoped apply()/clear() state isolation verified (UJ→U0 identical). Real
solver-status handling (non-Optimal → structured optimal=False, never zero-imputed). farmer_response
substream untouched.

## 8. Resilience — PASS
Phase-5 is deterministic and SEPARATE from the uncertainty path (not executed under uncertainty.apply()).
N−1 largest-producer failure and correlated hazard-zone outage; immediate exposure vs post-shock recovery
clearly distinguished; recovery uses the Phase-4 machinery under a scoped resilience floor tolerance.
Formulation and artifacts unchanged.

## 9. LLM boundary — PASS (dev-ready; benchmark dataset pending)
`llm_interaction.py`: NL → LLM structured parse → deterministic schema/semantic/farmer/plot/feasibility
validation → deterministic mechanism → validated result → grounded explanation. The LLM has NO allocation
authority (`FORBIDDEN_AUTHORITY_FIELDS`, `detect_authority_attempts`). Live client reads OPENAI_API_KEY
from env; NO keys in repo; MockLLMClient drives offline/dev; live evaluation marked NOT RUN.
`llm_eval.run_dev_benchmark` computes schema validity, action exact-match, field P/R/F1, clarification
P/R, explanation groundedness. `p7_dev_cases.jsonl` holds 41 development cases. The ≥300 labelled
publication benchmark dataset + gold spec is NOT yet authored (MUST FIX before the ≥300 run; not
final30-blocking).

## 10. Experimental design (before final30)
The 30 replication seeds are the exact deterministic derivation `sorted(random.Random(20260812).sample
(range(10000,1000000),30))` (re-verified — not cherry-picked), frozen 2026-08-15. Paired comparisons use
common seeds and the five frozen RNG substreams. Proposed publication experiment matrix (to FREEZE as a
standalone manifest before final30):

| Family | Treatment vs baseline | Seeds | Paired key | Metrics | Test | Effect size | CI | Multiplicity | Table/Figure |
|---|---|---|---|---|---|---|---|---|---|
| PRIMARY | B1/B2/B3/Proposed @ pub config | 30 frozen | seed | cash, area, fairness-v2, LPS/HHI, coverage, disruption, infeasibility, runtime | Wilcoxon signed-rank (paired) | matched-pairs rank-biserial | bootstrap 95% CI (10k, seed 20260812) | Holm within family | T1 main results |
| ε sensitivity | B3 over ε grid | 30 frozen | seed | min-norm return, efficiency retained, gini(s) | descriptive + Wilcoxon vs 0.95 | rank-biserial | bootstrap 95% CI | Holm within family | F: ε frontier |
| λ stability | Proposed over λ grid | 30 frozen | seed | disruption rate, economic retention | descriptive | — | bootstrap 95% CI | n/a (descriptive) | F: λ frontier |
| α concentration | Proposed over α grid | 30 frozen | seed | max_LPS, HHI, retention, violations | descriptive | — | bootstrap 95% CI | n/a (descriptive) | F: α frontier |
| Action robustness | PRIMARY vs S1/S2 | 30 frozen | seed | tiers, coverage, disruption | Wilcoxon | rank-biserial | bootstrap 95% CI | Holm within family | T: behavioural robustness |
| Uncertainty | U0/UW/UM/UR/UP/UJ | 30 frozen | seed | tiers, infeasibility, coverage | Wilcoxon (vs U0) | rank-biserial | bootstrap 95% CI | Holm within family | T: uncertainty |
| Scalability | 25–500 farmers | 30 frozen | seed×size | runtime, status, cash/ha | descriptive | — | bootstrap 95% CI | n/a | F: scalability |

`build_instance(seed, n_farmers=…)` already parameterizes scalability. Missing-before-final30: the frozen
experiment manifest above committed as an artifact (currently only the provenance manifest exists).

## 11. Statistical plan — PASS (frozen)
Frozen in UNCERTAINTY_PROTOCOL: descriptive mean/median + SD/IQR; 95% CIs via deterministic bootstrap
(10,000 resamples, analysis seed 20260812); primary paired inference two-sided Wilcoxon signed-rank by
seed; matched-pairs rank-biserial effect size (not Cliff's delta); zero/tied handled deterministically
(Pratt where supported); Holm multiplicity within PREDEFINED metric families; infeasible runs included, no
seed dropped. SHOULD FIX: cross-reference this plan into the experiment manifest for the non-uncertainty
families (ε/λ/α/scalability) so every reported number has an assigned test/CI/multiplicity treatment.

## 12. Reproducibility / portability — PASS
project-root/_resolve path handling; portable test roots; Windows/Linux OS-conditional CBC threads with
honest empirical provenance (no claim about CBC's internal meaning of threads=0); PuLP 3.3.2 / CBC 2.10.3;
requirements minimal (pulp==3.3.2, xlrd==2.0.2, pytest>=7.4.0 added). No hardcoded local paths, no `/mnt/…`
production paths, no API keys in `farmsync/`. Deterministic seed/substream derivation. Frozen artifacts
byte-identical. `git_commit` is null in the manifest (SHOULD FIX: populate at final freeze).

## 13. Publication-claim matrix
| Claim | Supported? | Evidence | Allowed wording | Forbidden / overstated |
|---|---|---|---|---|
| Fairness | Yes | B3 ε-constraint max-min over capable | "improves worst-off normalized return among capable farmers subject to an efficiency floor" | "reduces inequality/Gini in general" |
| Worst-off protection | Yes | B3 max-min | "Rawlsian worst-off protection among capable farmers" | "protects all farmers" |
| Inequality (Gini) | Partial | fairness-v2 reports multiple gini denominators | "changes in normalized-return Gini are reported descriptively" | "B3 reduces global Gini" |
| Concentration | Yes | Phase-4 q_fc≤αQ_c, LPS/HHI | "limits within-crop production concentration to ≈α" | "prevents monopoly/market power" |
| Resilience | Partial | Phase-5 N−1 + hazard, recovery reopt | "evaluates N−1 and hazard-zone exposure and post-shock recovery" | "guarantees resilience" |
| Hazard protection | No (not from α) | α is within-crop, not spatial | "concentration control is distinct from spatial hazard protection" | "α provides hazard/spatial protection" |
| Farmer agency | Yes | action-consent-v1 causal layer | "models farmer accept/reject/modify/withdraw with consent-gated realisation" | "captures real farmer behaviour" |
| Realised recovery | Partial | post_shock_reopt | "post-shock recovery fraction under the backup reoptimisation" | "recovers losses" |
| Synthetic behaviour | Yes | SYNTHETIC_EXPERIMENTAL config | "synthetic behavioural model with stated probabilities" | "empirically estimated farmer behaviour" |
| Uncertainty | Yes | uncertainty-v1 four channels | "paired scenario-based synthetic exogenous uncertainty" | "stochastic optimisation / empirical risk frequencies" |
| Market demand/absorption | Partial | arrivals as absorption proxy | "absorption proxy from AGMARKNET arrivals" | "market demand / demand curve" |
| Indian representativeness | No | synthetic population | "parameterised from Indian public datasets (DES/AGMARKNET), synthetic population" | "representative sample of Indian farmers" |
| LLM reliability | Not yet | dev cases only, live NOT RUN | "LLM used only as a non-authoritative parse/explanation layer; benchmark pending" | "reliable/accurate LLM" (pre-benchmark) |

## 14. Required fixes before UI / live LLM / final30
- **MUST FIX BEFORE FINAL30:** freeze the publication experiment manifest (§10 matrix) as a committed
  artifact with per-experiment seeds/paired-key/metrics/test/effect-size/CI/multiplicity/table mapping.
- **MUST FIX BEFORE ≥300 BENCHMARK:** author the ≥300 labelled LLM benchmark dataset + gold spec and the
  scoring harness wiring (only 41 dev cases exist); run the live smoke first.
- **SHOULD FIX BEFORE SUBMISSION:** cross-reference the statistical plan into the experiment manifest for
  ε/λ/α/scalability families; populate `git_commit` at final freeze.

## 15. Non-blocking documented limitations
B3 does not necessarily reduce global Gini (claim = Rawlsian worst-off among capable subject to the
efficiency floor). α limits within-crop production concentration and does NOT imply strong spatial hazard
protection or large post-shock recovery. λ/α are synthetic experimental design parameters. Behavioural and
uncertainty severities are synthetic, not empirical frequencies. Absorption is a proxy, never demand. The
synthetic population is parameterised from Indian public data but is not an empirical sample. Development
checkpoint is a single seed; final30 not run.

## 16. Exact approved next step
UI/UX BUILD → live LLM smoke → ≥300 LLM benchmark → final experiment readiness check → final30. Approved to
begin UI/UX BUILD. The two MUST-FIX deliverables above are gated before the benchmark and final30
respectively, not before UI.
