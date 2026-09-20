# FarmSync Live Release Validation — 2026-09-21

## Scope

This document records a live validation of the already-published FarmSync
`v1.0.0-paper` release code using a disposable QA clone.

The validation covered:

- live GPT-5.6-Terra natural-language parsing;
- deterministic FarmSync validation and action-consent handling;
- interactive working-plan replanning;
- renewed consent;
- explicit finalisation;
- current final-plan analysis;
- a renewed-consent UI/backend defect discovered during validation;
- the post-release correction for that defect.

This validation did **not** rerun Final30, regenerate frozen scientific
artifacts, modify the frozen publication configuration, or constitute field
validation with real farmers.

The LLM remained non-authoritative throughout. It was used only for supported
natural-language parsing and explanation. Feasibility, crop selection,
allocation, optimisation, fairness, consent, locks, replanning, and execution
remained under deterministic FarmSync logic.

## Release provenance

Repository:

`https://github.com/Rvishwanath19977/FarmSync-Research`

Published release:

- tag: `v1.0.0-paper`
- target commit: `c88790de5236167e404ba6caa52de646e5de90fd`
- short commit: `c88790d`
- release title: `FarmSync v1.0.0 — Paper Release`

Validation date:

`2026-09-21`

Disposable validation clone:

`R:\FarmSync-Live-QA`

Runtime used for live validation:

- Python: `3.12.8`
- OpenAI SDK: `2.29.0`
- model: `gpt-5.6-terra`
- API: Responses API
- parser schema: `farmsync-farmer-request-v1`
- parser prompt: `p7-parse-live-v3`

Live LLM access was explicitly enabled for validation and the API key was
cleared from the PowerShell environment after live work completed.

## Scientific and interactive-system boundary

The publication experiments evaluate FarmSync's coupled collective
reoptimization, where a farmer response may alter recommendations for other
participants through shared market, resource, and fairness constraints. Any
subsequently changed recommendation requires renewed consent.

The interactive working-plan demonstrator is intentionally lighter. It uses
deterministic action-consent handling plus canonical per-plot feasibility for
responsive exploration and does **not** rerun the full collective MILP after
every UI edit.

The interactive demonstrator must therefore not be interpreted as executing
the publication-scale collective optimiser on every click.

## Historical persisted live evidence

Existing persisted live evidence predating this validation includes:

### 2026-09-17 bounded live UI smoke

- live GPT-5.6-Terra;
- 10 explicit live calls;
- bounded UI integration smoke rather than benchmark;
- not Final30;
- not field validation;
- covered natural-language queries, alternatives, MODIFY, authority override,
  clarification, identity/plot guards, and ACCEPT non-mutation.

Earlier Groundnut/Maize recommendation examples from this historical smoke were
superseded by corrected processed crop economics and must not be reused as
current selectable recommendation claims.

### 2026-09-18 targeted live addendum

Seven targeted live parser/interface cases passed:

1. current recommendation explanation;
2. explicit infeasible modification;
3. named crop explanation;
4. unsupported certainty;
5. explicit feasible modification;
6. alternative seeking;
7. ambiguous modification requiring clarification.

For the corrected `F0001-P03` example:

- initial/current crop: Onion;
- projected cash: `₹258,775`;
- feasible alternative: Soybean;
- projected cash: `₹19,996`;
- Rice is infeasible under the canonical water check.

### 322-case live parser benchmark

Persisted synthetic benchmark:

- API calls successful: `322/322`;
- schema valid: `322/322`;
- API errors: `0`;
- refusals: `0`;
- action accuracy: `301/322 = 93.48%`;
- clarification accuracy: `321/322 = 99.69%`;
- plot_id extraction: `322/322`;
- requested_crop extraction: `322/322`;
- requested_value extraction: `322/322`;
- unit extraction: `322/322`;
- deterministic execution equivalence where applicable: `104/104`;
- zero observed unsafe false-to-true `may_execute` escalation.

There were 21 action mismatches, primarily on difficult or vague MODIFY
phrasing. The persisted benchmark therefore has
`boundary_integrity_pass = false` and must not be described as perfect parser
or boundary performance.

## 2026-09-21 live release validation

The current validation followed the published release workflow through the
interactive application.

Evidence captured included:

1. initial Farmer Response state for `F0001-P03`;
2. live explanation of the current Onion recommendation;
3. deterministic Soybean alternative;
4. evidence explanation for Soybean;
5. explanation of Rice infeasibility;
6. explicit Rice modification rejected by deterministic feasibility;
7. ambiguous change request routed to clarification;
8. attempted authority override blocked;
9. initial Farmer Response controls;
10. request-another-crop flow;
11. saved change request and editable response;
12. explicit replanning action;
13. renewed-consent controls;
14. renewed-consent explanation;
15. alternative browsing;
16. return to original plan;
17. Soybean reselection remaining pending;
18. renewed ACCEPT for Soybean;
19. renewed REJECT example;
20. renewed NO_RESPONSE example;
21. mixed renewed-consent accounting;
22. bulk acceptance of pending rows only;
23. Final Plan ready-to-finalise state;
24. explicit finalisation;
25. mixed final realised/non-realised outcomes;
26. current-plan fairness and concentration analysis;
27. current-plan uncertainty analysis;
28. current-plan resilience analysis.

## Renewed-consent defect discovered

During live validation, the Renewed Consent UI offered:

`Return to original plan -> Use this`

but the backend selection pathway unconditionally excluded the original crop
from eligible options.

As a result:

- the UI could display a valid original-return option;
- the `select-recommendation` endpoint returned HTTP 400 when that option was
  selected;
- the frontend silently ignored the non-success response because it returned
  early when `available` was false.

A direct POST selecting a normal alternative succeeded, helping isolate the
defect to the original-return branch.

## Post-release correction

Three files were corrected in the disposable QA clone and then ported
byte-identically to both real repositories:

- `farmsync/exploratory_run.py`
- `static/js/farmsync.js`
- `tests/test_farmsync_ui.py`

Backend correction:

- determine the original crop;
- determine the effective farmer action;
- preserve persistent rejected alternatives;
- reject an explicitly rejected crop;
- reject return to the original crop unless the effective action is MODIFY;
- allow a feasible original crop for a valid MODIFY return;
- keep persistent rejection semantics intact;
- selecting a crop does not itself grant renewed consent.

Frontend correction:

- inspect HTTP status and response payload;
- display a visible consent-card error on selection failure;
- remove the previous silent inert-button behaviour;
- refresh authoritative working-run state after successful selection.

Regression coverage was strengthened so that a valid MODIFY original-return
case must succeed and remain pending for renewed consent, while REJECT-origin
return remains blocked.

## Manual browser verification of the correction

After restarting the patched Flask application:

### F0001-P03 original return

The renewed recommendation was changed:

`Soybean -> Return to original plan -> Onion`

Result:

- Onion selected successfully;
- no HTTP 400;
- renewed consent remained `PENDING`;
- crop selection did not automatically grant consent.

### F0001-P03 revised crop reselection

The user then selected Soybean again.

Result:

- Soybean selected successfully;
- renewed consent remained `PENDING`.

The recommendation was then explicitly accepted.

Result:

- revised crop: Soybean;
- renewed response: `ACCEPT`.

### Explicit negative outcomes

`F0017-P03`:

- revised recommendation: Pigeon_pea;
- renewed response: `REJECT`.

`F0025-P01`:

- revised recommendation: Sorghum;
- renewed response: `NO_RESPONSE`.

After bulk accepting all remaining pending renewed-consent rows, these explicit
decisions remained unchanged.

## Renewed-consent API verification

The current working run was verified through the read-only API after
finalisation.

Verified workflow state:

- `consent_complete = True`
- `n_changed = 20`
- `n_consent_pending = 0`
- `n_requires_consent = 20`
- `n_unresolved = 0`
- `replan_current = True`
- `final_current = True`
- `final_stale = False`
- `finalisable = True`
- `stages.final = True`
- `stages.analyse = True`

Verified explicit rows:

### F0001-P03

- original crop: Onion;
- revised crop: Soybean;
- revised cash: `₹19,996`;
- renewed response: `ACCEPT`;
- consent crop: Soybean;
- changed: true;
- renewed consent required: true.

### F0017-P03

- original crop: Onion;
- revised crop: Pigeon_pea;
- revised cash: `₹139,236`;
- renewed response: `REJECT`;
- consent crop: Pigeon_pea;
- changed: true;
- renewed consent required: true.

### F0025-P01

- original crop: Maize;
- revised crop: Sorghum;
- revised cash: `₹880`;
- renewed response: `NO_RESPONSE`;
- consent crop: Sorghum;
- changed: true;
- renewed consent required: true.

This confirms that the pending-only bulk action did not overwrite the explicit
ACCEPT, REJECT, or NO_RESPONSE decisions.

## Finalisation verification

The Final Plan page was first opened while the plan was ready to finalise.

Opening the page did not automatically finalise the plan.

The user then explicitly invoked:

`Finalise Consent-Verified Plan`

The resulting final plan reported:

- status: `FINAL_REALIZED`;
- total plots accounted for: `911`;
- initially allocated/offered: `381`;
- no initial allocation: `530`;
- finally realised: `348`;
- not realised: `563`;
- final realised projected cash: `₹1,17,10,382`.

The accounting reconciled:

- `381 + 530 = 911`;
- `348 + 563 = 911`.

Explicit final outcomes included:

- `F0001-P03`: Soybean, `RENEWED_ACCEPT`, realised;
- `F0017-P03`: renewed REJECT, not realised;
- `F0025-P01`: renewed NO_RESPONSE, not realised.

## Current-plan analysis

These analyses describe the exact current `FINAL_REALIZED` working plan.
They are separate from the frozen Final30 publication results.

### Fairness and concentration

Current-plan values displayed by the UI included:

- all-farmer per-ha Gini: `0.7425`;
- all-farmer absolute-cash Gini: `0.8627`;
- participant-only per-ha Gini: `0.5267`;
- participants: `272`;
- zero-realisation farmers: `228`;
- active realised crops: `8`;
- maximum crop share: `32.0%`;
- HHI: `0.1925`;
- concentration basis: area.

The UI explicitly states that the interactive plan did not run the
concentration-control MILP. The frozen publication parameter `alpha = 0.40`
is therefore descriptive context only for this interactive analysis and was
not enforced as an interactive optimisation constraint.

### Uncertainty

Protocol:

`interactive-stress-v1`

Current-plan provenance included:

- realised area: `291.878 ha`;
- baseline projected realised cash: `₹1,17,10,382`;
- selected dataset area: `779.220 ha`.

This is a fixed-plan sensitivity check: the final allocation remains unchanged
and no reoptimisation is performed.

Displayed stress summaries included:

- weather: ETo multiplier `1.15`, 59 exposed plots, `47.948 ha`;
- market: price multiplier `0.90`, stressed projected cash `₹87,80,885`,
  change `-₹29,29,497` / `-25.02%`;
- resource: capacity multiplier `0.85`, 69 farmers and 98 plots exposed;
- joint W+M+R: 144 plots and `129.298 ha` with weather/resource exposure.

Weather/resource exposure is not presented as an invented cash-loss model.

### Resilience

Protocol:

`interactive-resilience-v1`

Current-plan values included:

- realised plots: `348`;
- realised area: `291.878 ha`;
- projected realised cash: `₹1,17,10,382`;
- active crops: `8`;
- realised hazard zones: `14`.

Representative largest-producer exposure:

- target crop: Cotton;
- failed farmer: `F0178`;
- producer share: `51.3%`;
- affected plots: `2`;
- affected area: `2.296 ha`;
- immediate expected cash exposure: `₹1,10,952`;
- expected cash remaining: `₹1,15,99,430`.

Representative hazard zone `R1-HZ1`:

- affected plots: `36`;
- affected area: `27.028 ha`;
- exposure: `₹8,83,865`;
- expected cash remaining: `₹1,08,26,517`;
- exposure share: `7.5%`.

The UI explicitly states that post-shock recovery is not evaluated for this
interactive plan.

## Automated regression verification

Disposable QA clone:

`5 passed, 187 deselected in 3.36s`

Standalone research repository after porting the patch:

`5 passed, 187 deselected in 4.42s`

Portfolio repository after porting the same patch:

`5 passed, 187 deselected in 2.57s`

`git diff --check` completed without errors in both real repositories.

No Final30 rerun, scientific-output regeneration, or 322-case live benchmark
rerun was performed.

## Screenshot evidence

The live release validation screenshot set is stored externally at:

`R:\FarmSync-Live-Captures`

A SHA-256 provenance manifest was generated:

`FarmSync_live_release_screenshot_manifest_2026-09-21.csv`

The manifest contains the captured PNG filenames, SHA-256 hashes, and byte
sizes.

Representative evidence includes:

- `02_F0001-P03_live_why_this_crop.png`
- `04_F0001-P03_askwhy_soybean_evidence.png`
- `06_F0001-P03_live_modify_rice_rejected.png`
- `08_F0001-P03_live_authority_override_blocked.png`
- `16_F0001-P03_renewed_consent_return_original_selected.png`
- `18_F0001-P03_renewed_consent_soybean_accepted.png`
- `21_renewed_consent_summary_mixed_outcomes.png`
- `22_renewed_consent_all_resolved_bulk_accept.png`
- `23_final_plan_ready_to_finalise.png`
- `24a_final_plan_finalised_summary.png`
- `25b_final_plan_mixed_consent_outcomes.png`
- `26b_current_final_plan_fairness_concentration.png`
- `27b_current_final_plan_uncertainty.png`
- `27d_current_final_plan_uncertainty.png`
- `28a_current_final_plan_resilience.png`
- `28b_current_final_plan_resilience_hazard_zones.png`

## Audit patch

The exact QA-clone code correction was preserved externally as:

`R:\FarmSync-Live-Captures\renewed_consent_original_return_fix_2026-09-21.patch`

SHA-256:

`D1CA88BE4DAC05193BB5027139E3333955E239B1EF956826C2FDEA53F5F6E70B`

## Scientific impact

The discovered issue was an interactive UI/backend selection defect.

The correction:

- does not alter Final30;
- does not alter the frozen dataset;
- does not alter frozen seeds;
- does not alter solver settings;
- does not alter `action-consent-v1`;
- does not alter `uncertainty-v1`;
- does not alter `fairness-v2`;
- does not alter the frozen publication configuration;
- does not regenerate frozen scientific outputs.

The tagged `v1.0.0-paper` release remains immutable. The correction currently
exists as a post-release main-branch fix pending normal documentation,
commit/push, DOI review, and any later explicit decision on whether to publish
a separate `v1.0.1`.

## Limitations

This validation must not be interpreted as real-farmer or field validation.

Important limitations remain:

- the evaluation data are synthetic/constructed;
- farmer responses are simulated;
- the frozen scientific protocol uses one bounded renewed-consent pass;
- it does not perform iterative negotiation to equilibrium or convergence;
- the interactive demonstrator does not run the full collective MILP after
  every UI action;
- the live parser benchmark is a synthetic language/interface evaluation;
- live model/API behaviour can depend on provider/model/version;
- hard browser refresh can lose the client-side run identifier even when
  server state persists;
- no field adoption, usability, or causal agricultural outcome is claimed.

## Release and DOI verification

The existing `v1.0.0-paper` tag must not be moved, deleted, rewritten, or
retargeted.

The Zenodo record was verified directly after release.

Verified software archive metadata:

- version: `v1.0.0-paper`;
- publication date: `2026-09-20`;
- creator: Vishwanath Rajasekaran;
- resource type: Software;
- licence: Apache License 2.0;
- exact version DOI: `10.5281/zenodo.22864429`;
- concept/all-versions DOI: `10.5281/zenodo.22864428`.

The version DOI identifies the exact archived `v1.0.0-paper` software release
and is the reproducibility DOI used in `CITATION.cff`.

The concept DOI represents all archived FarmSync software versions and resolves
to the latest archived version.

The GitHub `v1.0.0-paper` tag remains the immutable frozen release. The
renewed-consent correction documented here is a later main-branch correction
and is not retroactively part of that archive.

Any decision to publish a corrected `v1.0.1` must be made explicitly after the
main-branch correction and documentation are committed and reviewed.
