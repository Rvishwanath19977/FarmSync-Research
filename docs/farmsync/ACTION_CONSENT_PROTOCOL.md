# FarmSync — Farmer-Action & Renewed-Consent Protocol

**Status:** action-consent-protocol-v1-FROZEN-IMPLEMENTED (2026-08-24)

All methodological decisions are frozen (see §16). NO code, tests, datasets, solver settings,
epsilon/lambda/alpha, frozen artifacts, RNG seeds, or Phase 1–7 results are changed by this document.
Implementation is gated on this frozen design. One factual finding was surfaced by inspecting the
existing preference representation and is resolved in §9 with the smallest defensible deterministic
substitute (no unresolved methodological decision remains).

---

## 1. Purpose

FarmSync's optimisation layer (B1/B2/B3, Phases 3–5 reoptimisation) produces recommendations and
revised plans; Phases 1–2 model initial participation and a commitment ladder. This protocol freezes
the **behavioural action layer**: the deterministic, publication-safe semantics of how a synthetic
farmer acts on an offer or a revised recommendation, and how **consent** gates whether any
recommendation becomes a **realised** allocation. It preserves the core authority rule: the LLM never
decides allocation or feasibility; deterministic rules and the MILP hold allocation authority; the
action layer records only *what the (synthetic) farmer did* and *what consent exists*.

---

## 2. Terminology

- **Offer** — a specific (farmer, plot, crop) recommendation presented in a round.
- **Consent** — a farmer authorisation attached to a *specific* (plot, crop). Crop-specific; never
  generalises to a different crop. Carries `consent_kind ∈ {INITIAL, RENEWED}`.
- **Realised allocation** — an allocation that is (a) feasible/optimal under the deterministic layer
  and (b) covered by valid consent for its exact crop. Only realised allocations are delivered.
- **Recommendation / revised recommendation** — optimiser output carrying no consent; realised only
  after renewed consent (or the existing-consent exception).
- **Commitment lifecycle** (Phase 2, unchanged): `VIEWED → TENTATIVE_ACCEPT → CONFIRMED →
  INPUTS_PURCHASED → LAND_PREPARED → PLANTED`.
- **Lock level** (derived, unchanged): `VIEWED → FLEXIBLE`;
  `TENTATIVE_ACCEPT/CONFIRMED/INPUTS_PURCHASED/LAND_PREPARED → SOFT_LOCK`; `PLANTED → HARD_LOCK`.
- **Action event** — a behavioural event: `ACCEPT / REJECT / MODIFY / NO_RESPONSE / WITHDRAW`. These
  five remain the ONLY behavioural action values (§7). Renewed responses reuse ACCEPT/REJECT/
  NO_RESPONSE with `decision_round=RENEWED`.
- **DecisionRound** — `{INITIAL, RENEWED}` (new status type, not a behavioural action).
- **OfferStatus** — includes `PENDING_LAPSED` (a no-response offer/result status, not an action).
- **Action events are a SEPARATE stream from commitment lifecycle transitions.**
- **SYNTHETIC_EXPERIMENTAL** — provenance tag on every behavioural probability/policy; NOT an
  empirical Indian-farmer prevalence estimate.

### 2.1 Separation of concerns (invariant)
```
LLM / parser        -> classifies a request into an action + fields   (no authority)
Action layer        -> records the farmer action event + consent      (this protocol)
Deterministic layer -> feasibility, locks, MILP reoptimisation        (allocation authority)
Consent gate        -> converts recommendation -> realised iff consent (this protocol)
```

---

## 3. Action semantics

Deterministic validation (identity, ownership, feasibility, locks) always precedes any effect; a
failed validation yields a blocked action with a reason code and no state change.

### 3.1 ACCEPT
Farmer accepts the currently offered crop. Creates consent for that specific crop only
(`consent_kind` = INITIAL or RENEWED per round). May enter/advance the lifecycle. Not a
reoptimisation trigger. Accepted crop may be realised. Renewed consent not required when accepting
the already-consented crop (matches `requires_renewed_consent = (acc is None) or (acc != offered)`).

### 3.2 REJECT
Farmer rejects that specific offer. No consent created; **the farmer remains a participant** and the
same plot may later receive a NEW recommendation (which needs fresh consent). A reject on a `VIEWED`
offer is terminal for that offer (`REJECTED_TERMINAL`). REJECT may free a plot for a later
deterministic pass. On a `SOFT_LOCK` crop, REJECT is an explicit revocation of the currently
consented soft-lock crop: incurred/sunk commitment information is preserved, constrained
reoptimisation may follow, and **the rejected crop's active consent is invalidated** for subsequent
FINAL_REALIZED accounting. Rejected offers are never realised.

### 3.3 MODIFY
Farmer requests a specific permitted change. **Deterministic validation is mandatory and unchanged:**
identity/ownership, agronomic feasibility, budget, labour, market cap, fairness-v2, concentration,
and locks. MODIFY never bypasses any of these. A `HARD_LOCK`/`PLANTED` crop cannot be changed. On
`SOFT_LOCK`, MODIFY is allowed subject to validation, a **soft-lock disruption penalty** applies in
the constrained reoptimisation, and incurred commitment costs/state are recorded. A validated MODIFY
is a *request*; if deterministic reoptimisation accepts it the result is a **REVISED RECOMMENDATION**,
**not realised until renewed consent** (required whenever the revised crop differs from the consented
crop; matches `requires_renewed_consent = (acc != crop)`). MODIFY-target selection is frozen in §9.

### 3.4 NO_RESPONSE
The farmer does not respond within the decision window. **First-class behavioural event; never
silently converted to ACCEPT; never creates consent.** Represented as `action = NO_RESPONSE` with
`offer_status = PENDING_LAPSED` (PENDING_LAPSED is an offer/result status, NOT a FarmerEvent). A
lapsed offer is not consented and not realised; it does not advance the lifecycle and does not free a
`SOFT_LOCK`/`HARD_LOCK` crop. Distinct from REJECT (no explicit decline; may be re-offered later
without prejudice) and WITHDRAW (farmer remains a participant). See §10 for the fresh-offer vs
prior-consent distinction.

### 3.5 WITHDRAW
Farmer exits participation for the **current planning cycle** — administrative, not a permanent
real-world exit and not a physical un-planting. Drawn once per farmer per cycle (§6). Behaviour by
lock state (§4). WITHDRAW ≠ REJECT: a rejected plot stays available to the farmer for a later new
recommendation, whereas a withdrawn farmer's flexible land is **removed from the optimiser decision
set for the remainder of the cycle and is NOT available for collective reassignment**. Phase-7
currently parses WITHDRAW as `NOT_IMPLEMENTED` (`WITHDRAW_REQUIRES_POLICY`); this protocol supplies
the policy.

### 3.6 Renewed responses (reuse of ACCEPT / REJECT / NO_RESPONSE)
There are **no** `RENEWED_ACCEPT`/`RENEWED_REJECT` action values. A renewed response is the existing
behavioural event with `decision_round = RENEWED`:
- Renewed ACCEPT (`action=ACCEPT, consent_kind=RENEWED, decision_round=RENEWED`): grants consent for
  the revised crop; **the only way** (besides the existing-consent exception) a revised recommendation
  becomes FINAL_REALIZED.
- Renewed REJECT (`action=REJECT, decision_round=RENEWED`): revised recommendation stays non-realised;
  plot retains any prior realised state (e.g., hard-locked planted crop) else fallow.
- Renewed NO_RESPONSE (`action=NO_RESPONSE, decision_round=RENEWED, offer_status=PENDING_LAPSED`):
  non-realised (a lapsed renewed offer is not recovery).
- **Existing-consent exception:** if the revised crop equals the already-consented crop, no renewed
  prompt is issued; it is already realised.

---

## 4. State / lock matrix

Columns are lock levels; rows are the five behavioural actions. RRC = renewed consent required;
Reopt = deterministic reoptimisation may occur.

### ACCEPT
| Lock | Permitted | Action state | Crop effect | Commitment effect | Reopt | RRC | Realised | Reason if blocked |
|---|---|---|---|---|---|---|---|---|
| FLEXIBLE/VIEWED | Yes | ACCEPTED | offered crop consented | may enter/advance lifecycle | No | No (grants consent) | Yes | — |
| SOFT_LOCK | Yes | ACCEPTED | confirms current crop | may advance lifecycle | No | No | Yes | — |
| HARD_LOCK/PLANTED | Yes (confirm) | ACCEPTED | confirms planted crop | none (terminal) | No | No | Yes (already realised) | — |

### REJECT
| Lock | Permitted | Action state | Crop effect | Commitment effect | Reopt | RRC | Realised | Reason if blocked |
|---|---|---|---|---|---|---|---|---|
| FLEXIBLE/VIEWED | Yes | REJECTED | offer declined; plot freeable; farmer stays participant | REJECTED_TERMINAL | Yes | N/A (fresh offer later needs consent) | No | — |
| SOFT_LOCK | Yes | REJECTED | revokes consented soft-lock crop; **consent invalidated**; sunk cost recorded | administrative | Yes (constrained) | N/A | No | — |
| HARD_LOCK/PLANTED | No | BLOCKED | none | none | No | N/A | planted stays realised | `REJECTED_HARD_LOCK` |

### MODIFY
| Lock | Permitted | Action state | Crop effect | Commitment effect | Reopt | RRC | Realised | Reason if blocked |
|---|---|---|---|---|---|---|---|---|
| FLEXIBLE/VIEWED | Yes (if valid) | MODIFY_VALIDATED | revised crop proposed (§9) | none | Yes | Yes (if revised ≠ consented) | Only after renewed ACCEPT | validation fail → `VALIDATION_REJECTED` (+ specific feasibility/budget/labour/market/fairness/concentration code); no alt → `MODIFY_NO_FEASIBLE_ALTERNATIVE` |
| SOFT_LOCK | Yes (if valid) | MODIFY_VALIDATED | revised crop proposed; soft-lock disruption penalty; sunk cost recorded | none | Yes (constrained) | Yes | Only after renewed ACCEPT | as above; if soft-change disallowed by validation → `VALIDATION_REJECTED` |
| HARD_LOCK/PLANTED | No | BLOCKED | none | none | No | N/A | planted stays realised | `MODIFY_HARD_LOCK` |

### NO_RESPONSE (offer_status = PENDING_LAPSED)
| Lock | Permitted | Action state | Crop effect | Commitment effect | Reopt | RRC | Realised | Reason if blocked |
|---|---|---|---|---|---|---|---|---|
| FLEXIBLE/VIEWED | Yes (passive) | NO_RESPONSE / PENDING_LAPSED | fresh offer lapses; no consent | none | No (may be re-offered) | N/A | No | — |
| SOFT_LOCK | Yes (passive) | NO_RESPONSE / PENDING_LAPSED | **prior valid consent (same crop) NOT erased**; new offer lapses | none | No | N/A | prior consented state only | — |
| HARD_LOCK/PLANTED | Yes (passive) | NO_RESPONSE / PENDING_LAPSED | planted crop retained | none | No | N/A | planted stays realised | — |

### WITHDRAW (drawn once per farmer per cycle; applies to all owned plots)
| Lock | Permitted | Action state | Crop effect | Commitment effect | Reopt | RRC | Realised | Reason if blocked |
|---|---|---|---|---|---|---|---|---|
| FLEXIBLE/VIEWED | Yes | WITHDRAWN_CYCLE | plot **removed from optimiser decision set**; NOT reassigned; no new offers | participation flag = withdrawn | No (plot not pooled) | N/A | No | — |
| SOFT_LOCK | Yes (admin) | WITHDRAWN_CYCLE | sunk commitment recorded, not undone; no future offers | participation flag = withdrawn | No | N/A | prior state only | — |
| HARD_LOCK/PLANTED | Partial | WITHDRAWN_ADMIN_ONLY | **planted crop NOT removed** (physical immutability); no future offers | participation flag = withdrawn; physical state immutable | No | N/A | planted stays realised | `WITHDRAW_HARDLOCK_PHYSICAL_IMMUTABLE` |

---

## 5. Deterministic synthetic behavioural policy (FROZEN)

**Provenance: SYNTHETIC_EXPERIMENTAL** — experimental design parameters, NOT empirical prevalence.
All values are predefined here, frozen before final30, never tuned from any final result, and use the
frozen `farmer_response` substream with paired seeds.

### 5.1 Farmer acceptance propensity (retains the existing Phase-1 model)
```
p_accept(farmer) = clip(0.85 + 0.20 * (risk_tolerance - 0.5), 0, 1)
```
`risk_tolerance ∈ [0,1]` is the existing farmer field. This replaces NO fixed acceptance constant;
the existing validated Phase-1 acceptance model is preserved.

### 5.2 Per-eligible-offered-plot workflow (initial round)
```
A. WITHDRAW (farmer-level, §6): if the farmer's once-per-cycle withdraw draw fired, apply WITHDRAW
   to all their plots per the matrix; skip B–D.
B. ACCEPT draw: keyed uniform u_accept < p_accept(farmer) -> ACCEPT.
C. else NON-ACCEPTANCE: a separate keyed draw splits the non-acceptance mass (conditional shares,
   NOT unconditional population probabilities):
        REJECT      = 0.45
        MODIFY      = 0.35
        NO_RESPONSE = 0.20
```

### 5.3 Renewed-consent round (per revised offer requiring renewed consent)
```
Renewed ACCEPT draw: keyed uniform < p_accept(farmer) -> ACCEPT (consent_kind=RENEWED,
                                                                  decision_round=RENEWED).
else renewed NON-ACCEPTANCE split (conditional shares):
        REJECT      = 0.70
        NO_RESPONSE = 0.30
```
Single renewed-consent pass only; no iterative bargaining. FINAL_REALIZED via valid existing consent
or renewed ACCEPT only.

### 5.4 WITHDRAW rate
`p_withdraw = 0.02` per participating farmer per planning cycle (§6). Constant across profiles.

### 5.5 Sensitivity profiles (shifts of acceptance propensity only; frozen)
```
PRIMARY:        p_accept(f)
S1 reluctant:   clip(p_accept(f) - 0.15, 0, 1)
S2 high-uptake: clip(p_accept(f) + 0.10, 0, 1)
```
Conditional non-acceptance split (0.45/0.35/0.20) and renewed split (0.70/0.30) are UNCHANGED across
profiles; `p_withdraw = 0.02` is UNCHANGED — so sensitivity isolates acceptance propensity. All
profiles frozen before final30, paired seeds/substreams.

---

## 6. RNG design (keyed, order-independent)

- **Source:** the frozen `farmer_response` substream (`experiment.substream(seed, "farmer_response")`),
  unchanged. No new master seeds; no change to derivation or files.
- **Per-plot decision draws** (initial ACCEPT, non-acceptance split, renewed):
  `u = uniform01( sha256(f"{substream}:{farmer_id}:{plot_id}:{cycle_id}:{decision_point}") )`,
  `decision_point ∈ {"initial_accept","initial_split","renewed_accept","renewed_split"}`.
- **WITHDRAW draw — once per farmer per cycle (RNG correction, keyed WITHOUT plot_id):**
  `u_w = uniform01( sha256(f"{substream}:{farmer_id}:{cycle_id}:withdraw") )`; if `u_w < p_withdraw`
  the farmer is withdrawn and the result applies consistently to ALL their plots. plot_id is NOT part
  of the withdraw key.
- **Order independence:** keys use stable identity tuples, so draws are independent of farmer/plot
  iteration order and of parallel execution — required for the 30 paired replications.
- **Pairing:** the paired design reuses the same `farmer_response` sub-seed for the shared behavioural
  mechanism across compared variants. No tuning; all mappings fixed before final30.

---

## 7. Behavioural vocabulary (no new action enums)

Behavioural action semantics remain exactly `ACCEPT / REJECT / MODIFY / NO_RESPONSE / WITHDRAW`. NO
`RENEWED_ACCEPT`/`RENEWED_REJECT` are added (no technical necessity; renewed responses are
distinguished by `decision_round`). New **status** types (not behavioural actions) that MAY be added
at implementation:
- `ConsentKind {INITIAL, RENEWED}`
- `DecisionRound {INITIAL, RENEWED}`
- `OfferStatus {..., PENDING_LAPSED}`
`PENDING_LAPSED` is NOT a FarmerEvent. `NO_RESPONSE` and `WITHDRAW` already exist in `FarmerEvent`;
no Phase-7 parser vocabulary change is required.

---

## 8. Renewed-consent workflow (deterministic)
```
Phase 3/4 reoptimisation -> revised/new recommendations (per plot)        [RECOMMENDED_REVISED]
  classify each revised offer:
    (a) revised crop == already-consented crop -> existing-consent exception -> already realised
    (b) revised crop != consented crop OR new offer -> requires renewed consent
  for (b) generate renewed response via §5.3/§6 keyed draw:
        ACCEPT(RENEWED)      -> consent granted -> REALISED (revised)      [FINAL_REALIZED]
        REJECT(RENEWED)      -> non-realised; plot keeps prior realised state or fallow
        NO_RESPONSE(RENEWED) -> PENDING_LAPSED; non-realised
  HARD_LOCK plots never enter renewed consent for a crop change (immutable); remain realised as-is.
FINAL realised plan = (initially-realised consented allocations still valid)
                    ∪ (revised allocations that received renewed ACCEPT).
```
Rows entering renewed consent: any plot with a revised/new recommendation whose crop differs from the
existing consent, excluding HARD_LOCK/PLANTED. Final realised cash/area/fairness-v2 are computed ONLY
over FINAL_REALIZED (consented) allocations; unconsented revised recommendations are reported
separately and are **never counted as realised recovery**. Consent provenance record:
`(farmer_id, plot_id, crop, consent_kind ∈ {INITIAL,RENEWED}, decision_round, cycle_id,
action_event_id)`, linked to the allocation it authorises. The event ledger records the
**recommendation event** and the **consent event** as SEPARATE rows, each with its own sequence id.

---

## 9. MODIFY-target selection (FROZEN — with a factual finding)

**Factual finding (from inspecting the existing representation).** The `Farmer` dataclass
intentionally carries NO preferred/excluded crops. A `farmer_preferences.csv` schema exists
(`farmer_id, preferred_crops, excluded_crops, preference_score, min_area, max_area`) but is written
**empty (0 data rows)** in both the builtin dataset and the frozen snapshot, and no runtime path
supplies a per-farmer preference ordering (only schema validation of `farmer_id`). Therefore the
draft's step "take the farmer's existing preference ordering" is **not supported by current data**.
The only farmer-level behavioural signal is `risk_tolerance`; the available per-(plot,crop)
deterministic signals are `plot_crop_suitability` (feasibility + reason code) and the **expected net
cash return per (plot,crop)** already computed for the optimiser objective (via `_eligible` /
`assess_plot_crop`).

**Smallest defensible deterministic substitute (FROZEN):** a synthetic MODIFY selects its requested
crop by:
1. candidate set = crops that are **feasible** for the plot (`assess_plot_crop(...).feasible`) and
   **admitted** (in the active crop set; not fully-excluded per `planning.fully_excluded_crops`);
2. exclude the currently offered/consented crop;
3. rank remaining candidates by the **deterministic expected net cash return for that (plot,crop)**
   (the optimiser's own coefficient), descending;
4. deterministic tie-break by `crop_id` (lexicographic);
5. choose the top-ranked candidate as the requested crop;
6. pass that request to the deterministic reoptimisation layer for global budget/labour/market/
   fairness/concentration validation (unchanged authority).

No randomness; no invented preference model. If `farmer_preferences.csv` is later populated, a
preference-ordering rule may supersede steps 1–5 (approval-gated); until then this expected-return
proxy is the frozen rule.

**No eligible alternative:** retain `action = MODIFY`; record
`outcome/reason = MODIFY_NO_FEASIBLE_ALTERNATIVE`; do NOT invent a crop; do NOT reoptimise; any prior
consent remains valid unless the farmer separately REJECTs/WITHDRAWs.

---

## 10. NO_RESPONSE context (fresh offer vs prior consent)

- A fresh offer normally enters at `VIEWED`/`FLEXIBLE`. NO_RESPONSE to a **fresh unconsented offer**
  → `PENDING_LAPSED`, no consent, not realised (matrix FLEXIBLE row).
- NO_RESPONSE to a **later confirmation/revised interaction where a still-valid prior crop-specific
  consent exists**: the non-response creates no new consent, but it does **NOT erase** the still-valid
  prior consent for the same crop, and it does not change HARD_LOCK physical state (matrix SOFT_LOCK/
  HARD_LOCK rows).
- The matrix therefore distinguishes (a) fresh-offer lapse (no prior consent) from (b) no-response to
  a later interaction with an existing valid consent (prior consent retained).

---

## 11. Invariants
1. Consent-before-realisation: no FINAL_REALIZED allocation without a matching consent record for its
   exact crop.
2. No silent ACCEPT: NO_RESPONSE never becomes ACCEPT and never creates consent.
3. Hard-lock immutability: HARD_LOCK/PLANTED crop never changed/removed by MODIFY/REJECT/WITHDRAW;
   withdrawal on hard-lock is administrative-only.
4. Recommendation ≠ consent: revised recommendations excluded from realised recovery until renewed
   ACCEPT; ledger stores recommendation and consent as separate events.
5. Deterministic authority preserved: feasibility, budget, labour, market cap, fairness-v2,
   concentration, locks enforced by the deterministic layer for every MODIFY; the action layer/LLM
   never overrides them.
6. Action ≠ lifecycle: action events and commitment lifecycle transitions remain separate streams.
7. WITHDRAW land-agency: a withdrawn farmer's flexible land is removed from the decision set and is
   NOT reassigned to the collective.
8. Reproducibility: all draws keyed/order-independent from the frozen `farmer_response` substream;
   WITHDRAW keyed once per farmer per cycle (no plot_id).
9. Provenance: every behavioural probability tagged SYNTHETIC_EXPERIMENTAL; no empirical prevalence
   claimed.

---

## 12. Edge cases
- MODIFY to the same crop → existing-consent exception; no renewed consent; no change.
- REJECT then later re-offer of a different crop → new offer, fresh consent.
- SOFT_LOCK REJECT → consent invalidated, sunk cost recorded, constrained reopt may follow.
- NO_RESPONSE with a still-valid prior consent → prior consent retained (§10).
- NO_RESPONSE then WITHDRAW next cycle → lapse then administrative withdrawal; distinct events.
- WITHDRAW on SOFT_LOCK with inputs purchased → participation withdrawn; sunk cost recorded, not
  undone.
- Renewed REJECT on a previously hard-locked plot → prior planted crop stays realised; revised offer
  discarded.
- MODIFY with no eligible alternative → `MODIFY_NO_FEASIBLE_ALTERNATIVE`; prior consent retained.
- All-reject/all-accept degenerate draws → possible but improbable under PRIMARY; no artificial
  floor/cap (agency preserved).

---

## 13. Provenance classification
- SYNTHETIC_EXPERIMENTAL: `p_accept` model, conditional splits, `p_withdraw`, sensitivity profiles.
- DETERMINISTIC_RULE: matrix, validation, lock rules, consent gate, renewed-consent workflow,
  MODIFY-target rule (§9).
- FROZEN_INPUT: `farmer_response` substream and the canonical instance (unchanged).
- GENERATED_RESULT: action counts, realised tiers, metrics from a future run (not yet generated).
No behavioural probability is ever labelled an empirical/government source.

---

## 14. Metrics (publication)
Four separated tiers: **PLANNED** (optimiser plan, e.g. B3 planned 13,142,166) · **INITIAL_REALIZED**
(consented after initial round) · **RECOMMENDED_REVISED** (Phase-3/4 revised recs; not realised
alone) · **FINAL_REALIZED** (after renewed consent).
Action-layer metrics: action counts/rates by type (initial ACCEPT/REJECT/MODIFY/NO_RESPONSE/WITHDRAW);
renewed counts/rates (ACCEPT/REJECT/NO_RESPONSE at RENEWED); renewed acceptance rate;
recommendation-to-realisation ratio (FINAL_REALIZED / PLANNED and / RECOMMENDED, both reported);
revised-offer realisation ratio (renewed-accepted / revised-requiring-consent); cash and area
equivalents per tier; participation; fairness-v2 on INITIAL_REALIZED and FINAL_REALIZED (never on
unconsented recs); replanning burden (plots re-planned; renewed prompts); farmer-level churn;
consent coverage (= 1.0 by construction); unconsented recommendation count; lock-related blocked
actions by reason code; withdrawal and no-response counts and consequences.

---

## 15. Scientific audit (no edits made)
- Manuscript Methods 2.1–2.20: sentences stating behaviour is limited to ACCEPT/REJECT, or that
  revised recommendations realise without a renewed round, would become inaccurate once implemented
  and must be revised LATER (not now). Crop-specific-consent and recommendation-non-realised
  statements remain accurate.
- Phase 1–7 semantics: consistent; this protocol supplies NO_RESPONSE behaviour, WITHDRAW policy, and
  the renewed-consent round, and reuses existing renewed-consent logic.
- Vocabularies: `FarmerEvent` already has NO_RESPONSE and WITHDRAW. NO new behavioural enum is added.
  Optional NEW status types for later, approval-gated implementation: `ConsentKind`, `DecisionRound`,
  and an `OfferStatus` including `PENDING_LAPSED`. No enum changed this turn.

---

## 16. Decisions — RESOLVED / FROZEN
1. **Acceptance model:** RETAIN `p_accept(f) = clip(0.85 + 0.20*(risk_tolerance-0.5),0,1)`
   (SYNTHETIC_EXPERIMENTAL). No fixed 0.70. **FROZEN.**
2. **Initial non-acceptance split (conditional):** REJECT 0.45 / MODIFY 0.35 / NO_RESPONSE 0.20.
   **FROZEN.**
3. **Renewed round:** reuse `p_accept(f)`; renewed non-acceptance REJECT 0.70 / NO_RESPONSE 0.30;
   single pass; FINAL_REALIZED via existing or renewed ACCEPT only. **FROZEN.**
4. **WITHDRAW:** `p_withdraw = 0.02`, drawn once per farmer per cycle, keyed WITHOUT plot_id; applies
   to all owned plots. **FROZEN.**
5. **WITHDRAW land-agency:** withdrawn flexible land removed from the decision set, NOT reassigned;
   soft-lock sunk cost preserved; hard-lock physical crop immutable/administrative-only. **FROZEN.**
6. **SOFT_LOCK:** changeable (≠ hard-lock). MODIFY allowed with soft-lock disruption penalty +
   constrained reopt + renewed consent; REJECT revokes consent (invalidated), sunk cost recorded.
   **FROZEN.**
7. **NO_RESPONSE / PENDING_LAPSED:** `action=NO_RESPONSE`, `offer_status=PENDING_LAPSED`; no new
   FarmerEvent. **FROZEN.**
8. **Renewed vocabulary:** no RENEWED_ACCEPT/RENEWED_REJECT; use ACCEPT/REJECT/NO_RESPONSE +
   `decision_round=RENEWED`; optional new status types ConsentKind/DecisionRound/OfferStatus.
   **FROZEN.**
9. **Sensitivity:** PRIMARY `p_accept`; S1 `-0.15`; S2 `+0.10`; splits and `p_withdraw` unchanged;
   paired seeds. **FROZEN.**
10. **MODIFY-target (§9):** preference table is EMPTY in current data (factual finding) → frozen
    substitute = highest deterministic expected-net-return feasible admitted alternative, tie-break
    crop_id; else `MODIFY_NO_FEASIBLE_ALTERNATIVE`. **FROZEN, with the factual finding recorded.**
11. **NO_RESPONSE context (§10):** matrix distinguishes fresh-offer lapse from no-response with a
    still-valid prior consent. **FROZEN.**

No unresolved methodological decision remains. The only surfaced factual item (empty preference table)
is resolved by the §9 substitute; if the user later wants preference-ordering-based MODIFY targeting,
populating `farmer_preferences.csv` and swapping §9 steps 1–5 is an approval-gated follow-up.

---

## 17. Proposed implementation plan (NOT executed; approval-gated)
1. `farmsync/config.py`: add frozen SYNTHETIC_EXPERIMENTAL policy block (p_accept model, splits,
   p_withdraw, S1/S2).
2. `farmsync/proposed/actions.py` (new): keyed draws (§6), action selection, matrix table, MODIFY
   target (§9) — pure deterministic functions, no solver authority.
3. Consent gate: add `consent_kind`/`decision_round`; FINAL_REALIZED = consented-only.
4. Renewed-consent round (§8): revised recs + consent as SEPARATE ledger rows.
5. WITHDRAW policy (§3.5/§4): replace Phase-7 `NOT_IMPLEMENTED` with validated administrative payload.
6. Four-tier metrics (§14).
7. Status types (§7) `ConsentKind`/`DecisionRound`/`OfferStatus{PENDING_LAPSED}` — added only if
   needed; NO behavioural enum change.
Existing B1–B7/Phase 1–6 frozen artifacts untouched.

## 18. Proposed tests (NOT executed)
Matrix determinism + reason codes; consent-before-realisation; unconsented revised excluded from
FINAL_REALIZED; NO_RESPONSE never ACCEPT; hard-lock immutability under MODIFY/REJECT/WITHDRAW;
WITHDRAW admin-only on hard-lock; WITHDRAW once-per-farmer keyed without plot_id (all plots
consistent); RNG order-independence (shuffle iteration → identical actions); renewed workflow (ACCEPT
realises, REJECT/NO_RESPONSE do not); existing-consent exception; MODIFY-target = top feasible
expected-return alt; `MODIFY_NO_FEASIBLE_ALTERNATIVE` path; SOFT_LOCK REJECT invalidates consent;
NO_RESPONSE with prior consent retains it; provenance tags SYNTHETIC_EXPERIMENTAL.

---

## 19. Limitations
Behavioural rates experimental, not empirical; external validity not claimed. Single decision window
per round; no intra-round negotiation. WITHDRAW is cycle-level administrative only; no multi-season
persistence. Single renewed-consent pass. MODIFY target uses an expected-return proxy while the
preference table is empty.

---

## 20. Implementation clarification — SOFT_LOCK WITHDRAW final-realisation (2026-08-24)

This clarifies (does not redesign) the frozen SOFT_LOCK WITHDRAW semantics for FINAL_REALIZED
accounting, as applied by the implementation:

- **FLEXIBLE/VIEWED WITHDRAW:** farmer exits the current cycle; owned flexible plots are removed from
  the optimiser decision set and are NOT reassigned; no future offers; **no FINAL_REALIZED allocation
  for those plots.**
- **SOFT_LOCK WITHDRAW:** farmer exits the current cycle; commitment state and sunk/incurred cost
  HISTORY are preserved (not pretended away); no future offers; **active collective consent is
  invalidated for FINAL_REALIZED accounting** — a not-yet-planted soft-lock allocation must NOT remain
  FINAL_REALIZED merely because prior consent once existed; withdrawn land is not reassigned.
- **HARD_LOCK/PLANTED WITHDRAW:** administrative withdrawal only; the planted physical crop remains
  immutable and **remains realised**; no future offers.

The physical-irreversibility exception (allocation remains realised despite withdrawal) applies ONLY
to HARD_LOCK/PLANTED. For FLEXIBLE and SOFT_LOCK, withdrawal removes the allocation from
FINAL_REALIZED (flexible: removed from the decision set; soft-lock: consent invalidated), while
soft-lock sunk-cost history is retained for auditability.

---

## 21. Implementation-correction note (2026-08-24)

The frozen methodology is unchanged. This records a correction to the IMPLEMENTATION only:

- **Defect (first implementation):** actions were generated AFTER the precomputed Phase-3/4 revised
  plan and the renewed-consent step was overlaid on that action-independent `conc` plan. MODIFY
  targets were selected but never fed to reoptimisation; REJECT/WITHDRAW did not alter the
  reoptimisation input; renewed ACCEPT incremented a counter rather than creating a consent record;
  and the fairness B1 reference was mistakenly `farmer_cash(planned)` (B3), not B1. The revised plan
  was therefore NOT causally driven by farmer actions. That checkpoint's numbers are SUPERSEDED.
- **Corrected implementation:** the sequence is now PLANNED → initial farmer actions → apply
  action/lock/consent consequences to the reoptimisation SCENARIO (REJECT/MODIFY → the plot's crop is
  excluded via the existing `REJECTED_TERMINAL` option rule; WITHDRAW on flexible/soft → the plot is
  removed from the decision set; HARD_LOCK immutable) → run the EXISTING `ro.solve_phase3` /
  `co.solve_phase4` machinery on that action-adjusted scenario → RECOMMENDED_REVISED → renewed consent
  (real `Consent` records) → FINAL_REALIZED. The optimiser stays authoritative (a MODIFY request is
  recorded as REQUESTED_AND_RECOMMENDED / REQUESTED_NOT_RECOMMENDED / MODIFY_NO_FEASIBLE_ALTERNATIVE /
  BLOCKED_BY_LOCK, never forced). `consent_coverage_final` is derived from verified
  (farmer, plot, exact-crop, valid) records; the fairness B1 reference is the canonical B1 ILP
  (₹14,644,537). Withdrawn farmers are never issued renewed prompts. Recommendation and consent are
  separate ledger events.

---

## 22. Implementation-correction note (2026-08-24) — single initial-response gate

**SUPERSEDED BY §23:** the "commitment locks over ALL offers" prefix described below was corrected in
§23 (commitment is now assigned only AFTER acceptance; the prefix returns fresh uncommitted offers).
This note is retained for chronology; its lock-before-acceptance behaviour is no longer in effect.

Frozen methodology unchanged. Correction to the IMPLEMENTATION only:
- **Defect:** the action layer previously obtained its base commitment scenario from the FULL
  `run_proposed_pipeline`, whose Stage-2 already performs the legacy Phase-1 ACCEPT/REJECT gate. The
  frozen initial action process (`p_accept` etc.) was then applied on top of the already-accepted
  plots — a DUPLICATE stochastic initial-response gate, contrary to the protocol's "one initial
  behavioural process per eligible planned offer".
- **Correction:** the action layer now consumes `pipeline.prepare_proposed_prerequisites`, which builds
  the commitment locks over ALL B3 planned offers using the existing P3_MIXED_V1 machinery (every
  eligible offer receives a FLEXIBLE/SOFT/HARD lock via the same deterministic hash) WITHOUT the
  Phase-1 accept/reject gate and WITHOUT Stage-6 resilience. There is now exactly ONE frozen initial
  action (`WITHDRAW` first, else `p_accept`, else REJECT/MODIFY/NO_RESPONSE) per eligible B3 offer.
  P_ACCEPT_BASE/slope/splits/WITHDRAW/RNG keys/renewed-consent/MODIFY/lock semantics are unchanged;
  P3_MIXED_V1 commitment timing is preserved. Prior action + UJ Proposed dev checkpoint numbers are
  SUPERSEDED (they depended on the duplicate gate). B1/B2/B3 U0 canonical values are unchanged.

---

## 23. Implementation-correction note (2026-08-24) — commitment after acceptance

Frozen methodology unchanged. Ordering correction to the IMPLEMENTATION only:
- **Defect:** the single-gate prefix marked every B3 offer `status="REALISED"` and ran P3_MIXED_V1
  BEFORE the initial action, so unaccepted offers could be pre-assigned SOFT_LOCK/HARD_LOCK; the action
  layer then treated a pre-assigned HARD_LOCK as already realised and fabricated INITIAL consent even
  when the drawn action was REJECT/MODIFY/NO_RESPONSE/WITHDRAW — violating consent semantics.
- **Correction:** the causal order is now PLANNED → ONE initial action per FRESH VIEWED/FLEXIBLE offer
  → construct consent/action outcome → assign P3_MIXED_V1 commitment timing to INITIALLY ACCEPTED
  allocations ONLY (`pipeline.commit_accepted`, same deterministic hash) → action-adjusted scenario →
  Phase-3/4 reopt → RECOMMENDED_REVISED → renewed consent → FINAL_REALIZED. A fresh offer is
  FLEXIBLE and can never be SOFT/HARD before acceptance; REJECT/MODIFY/NO_RESPONSE/WITHDRAW create no
  INITIAL consent and no commitment ladder; every HARD_LOCK now traces to a prior ACCEPT. P3_MIXED_V1
  itself, all frozen probabilities, RNG keys, MODIFY/renewed/lock semantics are unchanged. Prior
  Proposed dev tiers are SUPERSEDED; B1/B2/B3 U0 canonical values unchanged.

---

## 24. Implementation-correction note (2026-08-24) — consent provenance closure

Frozen methodology unchanged; §8 provenance requirement now fully implemented.
- **action_event_id:** `Consent` carries `action_event_id`, the exact ACCEPT ACTION ledger event that
  authorised it. INITIAL ACCEPT logs the ACTION, captures its event_id, then creates the INITIAL
  consent linked to it. RENEWED ACCEPT logs a SEPARATE RENEWED ACCEPT ACTION row and a linked RENEWED
  CONSENT row (distinct ledger rows). The existing-consent exception reuses the ORIGINAL consent and its
  ORIGINAL action_event_id — no new behavioural ACCEPT — and any audit CONSENT row references that
  original event (`reason_code=AUTH_EVENT:<id>`).
- **No fabricated HARD_LOCK consent:** the prior "if missing, create INITIAL consent" fallback is
  REMOVED. A HARD_LOCK/PLANTED without a valid prior INITIAL ACCEPT consent (missing / invalid /
  mismatched crop / missing action_event_id) raises `ConsentProvenanceError`.
- **FINAL_REALIZED provenance verification:** every FINAL_REALIZED allocation is verified via
  `verify_consent_provenance` (farmer, plot, exact crop, valid, non-null action_event_id → a real ACTION
  with behavioural_action==ACCEPT, matching farmer/plot, matching decision_round, matching cycle).
  `consent_coverage_final` is 1.0 only if all pass; a shortfall raises `ConsentProvenanceError`.
- **Error classification:** `ConsentProvenanceError` is an invariant/provenance failure, NOT solver
  infeasibility; it propagates and is never recorded as optimal=False. Only genuine solver-stage
  `ProposedInfeasibleError` represents optimisation failure.
- **MODIFY tie-break:** corrected to crop_id (was crop_name; orderings not guaranteed identical);
  ranking/feasibility/admission/probabilities/optimiser authority unchanged; no development allocation
  change. Recommendation, behavioural action, and consent remain distinct ledger concepts.
