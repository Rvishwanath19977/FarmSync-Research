## Scientific provenance correction ? 18 September 2026

**SUPERSEDES the crop-economic recommendation values in Cases 2, 5 and 6 below.**

A post-smoke scientific audit found that the interactive canonical eligibility
path could execute while `farmsync.ingest.operational` was not loaded. In that
state, planning fell back to legacy/static economic parameters rather than the
processed operational DES / AGMARKNET / Cost-of-Cultivation parameter layer.

The defect was reproduced directly on built-in plot `F0001-P03`:

- before operational loading: Groundnut, expected cash `?1,74,535`;
- after loading `data/farmsync/processed`: Soybean, expected cash `?19,996`.

The interactive eligibility boundary was corrected so it now loads the existing
processed operational tables before canonical `_eligible()` evaluation and fails
loudly if those tables are unavailable.

Accordingly:

- the previously displayed Groundnut `?1,74,535` recommendation is **superseded**;
- the previously displayed Maize `?90,646` selectable-recommendation result is
  **superseded**;
- the current cash-positive alternative for `F0001-P03`, excluding Onion, is
  **Soybean at ?19,996** under the processed operational data;
- the Rice water-feasibility evidence remains valid: required water approximately
  `18,241.6 m?` versus approximately `13,700.3 m?` available;
- the parser / LLM boundary was not the source of this defect. No new live LLM
  evaluation or 322-case benchmark rerun is required for this deterministic
  data-initialisation correction.

The original observations below are retained as historical QA evidence and must
not be interpreted as current scientific economic results.

---

# FarmSync Targeted Live UI Regression Addendum — 2026-09-18

## Scope

This addendum records a targeted live UI regression check performed after a semantic inconsistency was found in the FarmSync farmer-facing explanation path.

It is **not**:
- the frozen 322-case parser benchmark,
- Final30 evaluation,
- a real-farmer deployment study,
- or a replacement for the existing 2026-09-17 10-call live smoke report.

The frozen 322-case benchmark and its artifacts were not rerun or modified.

## Environment

- FarmSync working-plan UI
- Built-in research dataset
- Farmer: `F0001`
- Plot: `F0001-P03`
- Original stored FarmSync recommendation: `Onion`
- Stored expected value: `₹2,58,775`
- Live parser mode: `gpt-5.6-terra`
- Parser schema: `farmsync-farmer-request-v1`
- Live prompt: `p7-parse-live-v3`
- LLM role: natural-language parsing only
- Deterministic FarmSync role: feasibility, evidence, selection, recommendation and state authority

## Triggering defect

The first targeted live call used:

`Why this crop?`

The live parser correctly produced a `QUERY` for the current crop, but the farmer-facing result incorrectly described the stored Onion recommendation as infeasible.

The defect was traced to an overloaded interpretation of `_eligible`: absence from the stricter selection set was being treated as agronomic infeasibility.

Deterministic diagnostic evidence showed that Onion had no blocking agronomic constraint for the current plot, while the later alternative-selection layer did not reproduce a rankable cash-positive entry for Onion.

The repair therefore separated:

- `agronomic_feasible`
- `eligible_for_selection`
- current-plan provenance
- stored expected-value provenance
- rank reproducibility

The UI was also changed so case-specific values are dynamically rendered from deterministic FarmSync evidence rather than hardcoded.

## Post-fix targeted live cases

### 1. Current recommendation explanation

Prompt: `Why this crop?`

Result: **PASS**

Observed behavior:
- Parser action: `QUERY`
- UI intent: `EXPLAIN_CURRENT`
- Crop: Onion
- Current-plan provenance preserved
- Current deterministic agronomic checks reported no blocking issue
- Stored expected value shown as `₹2,58,775`
- FarmSync did not claim that Onion was simply the highest-ranked standalone alternative
- No working-plan mutation occurred

### 2. Explicit infeasible crop modification

Prompt: `Can I grow rice instead?`

Result: **PASS**

Observed behavior:
- Parser action: `MODIFY`
- Requested crop: `rice`
- FarmSync deterministic validation rejected Rice
- Grounded reason: insufficient water
- Required water: approximately `18,241.6 m³`
- Available water: approximately `13,700.3 m³`
- Deterministic feasible alternative returned: Groundnut
- Expected value for Groundnut: `₹1,74,535`
- Working-plan response remained unchanged until explicit user action

### 3. Named-crop explanation

Prompt: `Why can't I grow rice on this plot?`

Result: **PASS**

Observed behavior:
- Parser action: `QUERY`
- UI intent: `EXPLAIN_CROP`
- Requested crop: `rice`
- Deterministic check: `Water = INSUFFICIENT`
- Agronomic feasibility: blocking constraint detected
- Explanation used the same deterministic water evidence
- No mutation occurred

### 4. Unsupported certainty / disease-outbreak question

Prompt: `Will this crop definitely survive a disease outbreak next year?`

Result: **PASS**

Observed behavior:
- Parser action: `QUERY`
- UI intent: `UNSUPPORTED_QUERY`
- FarmSync declined to make a disease-survival prediction
- Recommendation source: not applicable
- No unsupported certainty was invented
- No mutation occurred

### 5. Explicit feasible crop modification

Prompt: `Can I grow maize instead?`

Result: **PASS**

Observed behavior:
- Parser action: `MODIFY`
- Requested crop: `maize`
- Deterministic FarmSync validation found Maize feasible
- Expected value shown as `₹90,646`
- Recommendation source: deterministic FarmSync
- Crop was not applied automatically
- Explicit `Use this recommendation` action remained required

### 6. Alternative-seeking request

Prompt: `What else can I grow?`

Result: **PASS**

Observed behavior:
- Parser action: `QUERY`
- UI intent: `REQUEST_ALTERNATIVE`
- FarmSync deterministically selected Groundnut
- Expected value shown as `₹1,74,535`
- Selection authority remained with deterministic FarmSync
- No automatic plan mutation occurred

`REQUEST_ALTERNATIVE` is a UI intent, not a new frozen parser action.

### 7. Ambiguous modification request

Prompt: `I want to change my crop.`

Result: **PASS**

Observed behavior:
- Parser action: `MODIFY`
- UI intent: `CLARIFY`
- No crop was guessed
- No recommendation was generated
- Recommendation source: not applicable
- Farmer was asked to name a crop or request feasible alternatives
- Nothing was changed

## UI/provenance corrections validated

The post-fix UI also validated:
- duplicate explanation removed,
- crop names rendered with readable capitalization,
- expected values formatted consistently,
- long Technical Details values wrapped without widening the page,
- response provenance changed to `LLM PARSED · FARMSYNC GROUNDED`,
- the separate Ask control retained `LIVE · GPT-5.6-TERRA`.

This distinction reflects the implemented architecture:
- the live LLM parses farmer language,
- deterministic FarmSync supplies the grounded evidence and decision authority.

The provenance badge was implemented with wrapping behavior intended to remain usable on smaller screens.

## Final offline regression

After the live targeted checks and UI/provenance changes, the final combined offline regression was run:

```text
python -m pytest tests/test_farmsync_llm_ui_integration.py tests/test_farmsync_ui.py tests/test_farmsync_browser.py -q
```

Final result:

```text
275 passed in 67.50s
```

## Conclusion

The targeted live regression addendum closed the semantic inconsistency discovered in the current-crop explanation path.

All seven post-fix targeted live cases passed:
- current recommendation explanation,
- infeasible explicit modification,
- named-crop explanation,
- unsupported certainty handling,
- feasible explicit modification,
- alternative seeking,
- ambiguous modification / clarification.

No frozen 322-case benchmark artifacts were modified or rerun.

The final implementation preserves the intended boundary:

**The LLM parses farmer language; deterministic FarmSync validates, selects, grounds explanations, and remains authoritative for planning state and scientific outputs.**
