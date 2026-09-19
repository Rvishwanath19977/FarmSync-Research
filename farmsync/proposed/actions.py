"""
Proposed — Farmer-action + renewed-consent layer (ACTION_CONSENT_PROTOCOL v1, FROZEN).

Deterministic, keyed, order-independent behavioural layer implemented EXACTLY per the frozen
protocol. It has NO solver/allocation authority: it records what the synthetic farmer did and what
consent exists, selects MODIFY targets from the CANONICAL optimiser eligibility (`_eligible`), and
gates recommendations into realised allocations via consent. The MILP/deterministic layer remains the
sole authority for feasibility/budget/labour/market/fairness/concentration.

All behavioural probabilities are SYNTHETIC_EXPERIMENTAL (see farmsync.config); not empirical
prevalence. Draws use the frozen `farmer_response` substream. WITHDRAW is drawn ONCE per farmer per
cycle, keyed WITHOUT plot_id. The cycle identifier is the stable master seed (recorded in metadata).
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from enum import Enum

from .. import config as C
from ..ilp_reference import _eligible
from ..feasibility import FeasibilityConfig


# --- status vocabularies (NOT behavioural actions; no new FarmerEvent) --------------------------
class ConsentKind(str, Enum):
    INITIAL = "INITIAL"
    RENEWED = "RENEWED"


class DecisionRound(str, Enum):
    INITIAL = "INITIAL"
    RENEWED = "RENEWED"


class OfferStatus(str, Enum):
    CONSENTED = "CONSENTED"
    DECLINED = "DECLINED"
    PENDING_LAPSED = "PENDING_LAPSED"          # produced by NO_RESPONSE
    WITHDRAWN = "WITHDRAWN"
    BLOCKED = "BLOCKED"
    NO_FEASIBLE_ALTERNATIVE = "NO_FEASIBLE_ALTERNATIVE"


# Behavioural actions remain exactly these five (reuse FarmerEvent names; no RENEWED_* values).
ACTIONS = ("ACCEPT", "REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW")

LOCK_FLEXIBLE = "FLEXIBLE"
LOCK_SOFT = "SOFT_LOCK"
LOCK_HARD = "HARD_LOCK"


# --- deterministic keyed RNG (order-independent) -----------------------------------------------
def _u01(*parts) -> float:
    """Uniform[0,1) from a sha256 of the stable key parts (order-independent by construction)."""
    key = ":".join(str(p) for p in parts)
    return int(hashlib.sha256(key.encode()).hexdigest(), 16) / (1 << 256)


def cycle_id(master_seed) -> str:
    """Stable, deterministic action-cycle identifier: the master seed. Independent of iteration
    order, timestamp, UUID, and platform; recorded in output metadata."""
    return str(master_seed)


def p_accept(risk_tolerance: float, profile: str = "PRIMARY") -> float:
    """Frozen acceptance propensity with a profile shift, clipped to [0,1]."""
    shift = C.ACTION_SENSITIVITY[profile]
    v = C.P_ACCEPT_BASE + C.P_ACCEPT_SLOPE * (risk_tolerance - 0.5) + shift
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def _split_pick(u: float, split: dict) -> str:
    """Map u in [0,1) onto a cumulative distribution given as an ordered {label: share} dict."""
    acc = 0.0
    for label, share in split.items():
        acc += share
        if u < acc:
            return label
    return list(split)[-1]          # numerical guard


# --- WITHDRAW: once per farmer per cycle, keyed WITHOUT plot_id ---------------------------------
def withdraw_draw(substream, farmer_id, cyc, profile="PRIMARY") -> bool:
    u = _u01(substream, farmer_id, cyc, "withdraw")
    return u < C.P_WITHDRAW


# --- initial-round action for one (farmer, plot) -----------------------------------------------
def initial_action(substream, farmer_id, plot_id, cyc, risk_tolerance, withdrawn, profile="PRIMARY"):
    if withdrawn:
        return "WITHDRAW"
    if _u01(substream, farmer_id, plot_id, cyc, "initial_accept") < p_accept(risk_tolerance, profile):
        return "ACCEPT"
    u = _u01(substream, farmer_id, plot_id, cyc, "initial_split")
    return _split_pick(u, C.INITIAL_NONACCEPT_SPLIT)


def renewed_action(substream, farmer_id, plot_id, cyc, risk_tolerance, profile="PRIMARY"):
    if _u01(substream, farmer_id, plot_id, cyc, "renewed_accept") < p_accept(risk_tolerance, profile):
        return "ACCEPT"
    u = _u01(substream, farmer_id, plot_id, cyc, "renewed_split")
    return _split_pick(u, C.RENEWED_NONACCEPT_SPLIT)


# --- lock/action matrix (permitted + reason) ---------------------------------------------------
def matrix_cell(action: str, lock: str):
    """Return (permitted, offer_status_hint, reason_code) for the (action, lock) cell.
    Effects on realisation are applied by the orchestrator; this encodes permission + reason."""
    if action == "ACCEPT":
        return True, OfferStatus.CONSENTED, None
    if action == "REJECT":
        if lock == LOCK_HARD:
            return False, OfferStatus.BLOCKED, "REJECTED_HARD_LOCK"
        return True, OfferStatus.DECLINED, None
    if action == "MODIFY":
        if lock == LOCK_HARD:
            return False, OfferStatus.BLOCKED, "MODIFY_HARD_LOCK"
        return True, None, None                # target/validation decided downstream
    if action == "NO_RESPONSE":
        return True, OfferStatus.PENDING_LAPSED, None
    if action == "WITHDRAW":
        if lock == LOCK_HARD:
            return True, OfferStatus.WITHDRAWN, "WITHDRAW_HARDLOCK_PHYSICAL_IMMUTABLE"
        return True, OfferStatus.WITHDRAWN, None
    return False, OfferStatus.BLOCKED, "UNKNOWN_ACTION"


# --- MODIFY target selection via CANONICAL eligibility (guardrail 1) ----------------------------
def modify_target(plot, farmer, crops, current_crop, config=None):
    """Choose the requested crop for a synthetic MODIFY using the canonical optimiser eligibility.

    Reuses `_eligible` (region + season + planning.is_admitted + deterministic feasibility +
    cash-positive projected return) — NO second eligibility definition. Excludes the current crop,
    ranks remaining eligible alternatives by canonical expected cash return (desc), deterministic
    tie-break by crop_id. Returns (crop_name, expected_cash) or (None, None) if none eligible.
    """
    config = config or FeasibilityConfig()
    crop_by_name = {c.crop_name: c for c in crops}
    opts = _eligible([plot], {farmer.farmer_id: farmer}, crop_by_name, config).get(plot.plot_id, [])
    cands = [(name, cash, crop_by_name[name].crop_id) for (name, cash, *_rest) in opts if name != current_crop]
    if not cands:
        return None, None
    cands.sort(key=lambda t: (-t[1], t[2]))    # expected cash desc, then crop_id asc (frozen tie-break)
    return cands[0][0], cands[0][1]


# --- consent record ----------------------------------------------------------------------------
@dataclass
class Consent:
    farmer_id: str
    plot_id: str
    crop: str
    consent_kind: str            # ConsentKind value
    decision_round: str          # DecisionRound value
    cyc: str
    valid: bool = True
    action_event_id: int = None  # the ACCEPT ACTION ledger event that authorised this consent


class ConsentProvenanceError(Exception):
    """Raised when a FINAL_REALIZED allocation's consent fails provenance verification (missing/
    invalid consent, missing or non-ACCEPT action_event_id, mismatched linkage, or a HARD_LOCK with no
    genuine prior ACCEPT). This is an invariant/provenance failure, NOT solver infeasibility — it must
    propagate and must NOT be recorded as optimal=False."""


@dataclass
class ActionOutcome:
    farmer_id: str
    plot_id: str
    action: str                  # behavioural action
    decision_round: str
    lock: str
    permitted: bool
    offer_status: str
    crop_before: str = None
    crop_requested: str = None   # for MODIFY
    reason_code: str = None
    realised: bool = False
    consent_kind: str = None


# --- lock lookup helper ------------------------------------------------------------------------
def lock_of(scen, farmer_id, plot_id):
    cell = scen.get((farmer_id, plot_id), {})
    lk = cell.get("lock")
    return lk or LOCK_FLEXIBLE


# --- lightweight allocation bundle for reuse with fairness_report ------------------------------
@dataclass
class _AllocSet:
    allocations: list = field(default_factory=list)


def _cash(allocs):
    return round(sum(a.cash_net for a in allocs), 0)


def _area(allocs):
    return round(sum(a.area_ha for a in allocs), 3)



# --- event ledger row --------------------------------------------------------------------------
def _ev(seq, seed, cyc, fid, pid, event_type, **kw):
    row = {"event_id": seq, "seed": seed, "cycle_id": cyc, "farmer_id": fid, "plot_id": pid,
           "event_type": event_type, "behavioural_action": None, "decision_round": None,
           "crop_before": None, "crop_requested": None, "crop_recommended": None,
           "consent_kind": None, "consent_valid": None, "offer_status": None, "lock": None,
           "reason_code": None, "realised": None, "action_event_id": None}
    row.update(kw)
    return row


class ProposedInfeasibleError(RuntimeError):
    """Raised when an action-adjusted Proposed reopt/concentration solve is non-Optimal. Carries the
    failed stage and solver status so callers can record a structured infeasible outcome WITHOUT
    catching unrelated programming errors."""
    def __init__(self, failed_stage, status):
        self.failed_stage = failed_stage; self.status = status
        super().__init__(f"{failed_stage}: non-Optimal ({status})")


def run_action_consent_layer(seed=None, profile="PRIMARY", base=None, instance=None,
                             uncertainty_condition=None, realisation_hash=None,
                             lam=None, alpha=None):
    """CAUSAL action + renewed-consent layer.

    Sequence (frozen protocol): PLANNED -> ONE initial farmer action per eligible B3 offer -> apply
    action/lock/consent consequences to the reoptimisation SCENARIO -> run the existing Phase-3/4
    reoptimisation machinery on that action-adjusted scenario -> RECOMMENDED_REVISED -> renewed consent
    (real Consent records) -> FINAL_REALIZED. The optimiser remains authoritative; actions never force a
    crop. Reuses ro.solve_phase3 / co.solve_phase4 (no new optimiser). B1 reference for fairness is the
    canonical B1 ILP (b1cash), never B3.

    Prerequisites come from `prepare_proposed_prerequisites` (NOT the full pipeline): there is NO legacy
    Phase-1 accept/reject gate and NO Stage-6 resilience — the single behavioural gate is this frozen
    action-v1 initial process, over every eligible planned offer.
    """
    import copy
    from .. import experiment as exp
    from . import pipeline as pl, reoptimize as ro, concentration as co
    from .. import fairness as fair
    from ..generate import CROPS

    seed = pl.DEV_SEED if seed is None else seed
    # Publication defaults remain authoritative for PRIMARY.
    # Explicit overrides are used only by the predeclared
    # lambda/alpha sensitivity families.
    lam = C.PUBLICATION_LAMBDA if lam is None else float(lam)
    alpha = C.PUBLICATION_ALPHA if alpha is None else float(alpha)
    # Prefix: B3 planned + fresh (uncommitted) offers + canonical B1 ref. No Phase-1 gate, no
    # resilience; commitment locks are assigned AFTER acceptance (commit_accepted), not here.
    # No Phase-1 gate; no resilience.
    prep = pl.prepare_proposed_prerequisites(seed=seed, base=base, instance=instance)
    planned = prep["planned"].allocations
    fresh_offers = prep["offers"]                    # every offer is fresh VIEWED/FLEXIBLE
    b1cash = prep["b1cash"]                           # CANONICAL B1 ILP reference (not B3)
    cohorts = prep["cohorts"]
    farmers = prep["farmers"]; plots = prep["plots"]
    farmer_by_id = {f.farmer_id: f for f in farmers}
    plot_by_id = {p.plot_id: p for p in plots}
    crops = CROPS
    substream = exp.substream(seed, "farmer_response", base)
    cyc = cycle_id(seed)
    _instance_hash = prep["instance_hash"]

    ledger = []
    seq = [0]
    def emit(fid, pid, etype, **kw):
        seq[0] += 1; row = _ev(seq[0], seed, cyc, fid, pid, etype, **kw); ledger.append(row); return row

    # ---- participating farmers = every farmer with a fresh B3 offer (pre-offer membership) --------
    participating = {o["farmer_id"] for o in fresh_offers}
    withdrawn = {fid: withdraw_draw(substream, fid, cyc, profile) for fid in participating}
    withdrawn_ids = {fid for fid, w in withdrawn.items() if w}

    # ---- initial round: ONE action per FRESH FLEXIBLE offer (never pre-committed) -----------------
    # A fresh offer is VIEWED/FLEXIBLE; it cannot be SOFT/HARD before acceptance. Commitment timing is
    # assigned AFTER acceptance (below), to ACCEPTed offers only.
    consents = {}                                    # (fid,pid) -> Consent  (INITIAL, ACCEPT only)
    counts = {a: 0 for a in ACTIONS}
    modify_requests = {}                             # (fid,pid) -> requested crop
    modify_no_alt = consent_invalidations = 0
    accepted_offers = []                             # -> P3_MIXED_V1 commitment ladder
    initial_realized = []
    reject_terminal = set()                          # (fid,pid) whose current crop is excluded in reopt
    pending_plots = set()                            # NO_RESPONSE / MODIFY-no-alt: decision plot, no consent
    removed_plots = set()                            # withdrawn (fresh flexible) plots exit the cycle
    lock = LOCK_FLEXIBLE                             # fresh-offer lock for the initial matrix
    for o in fresh_offers:
        fid, pid, crop0 = o["farmer_id"], o["plot_id"], o["crop"]
        withdrawn_here = withdrawn.get(fid, False)
        act = initial_action(substream, fid, pid, cyc, farmer_by_id[fid].risk_tolerance, withdrawn_here, profile)
        counts[act] += 1

        if act == "WITHDRAW":
            # fresh offer: nothing accepted/planted yet -> no commitment ladder, no consent.
            removed_plots.add((fid, pid))
            emit(fid, pid, "ACTION", behavioural_action="WITHDRAW", decision_round="INITIAL",
                 lock=lock, crop_before=crop0, offer_status=OfferStatus.WITHDRAWN.value,
                 reason_code="WITHDRAW_CYCLE_PARTICIPATION", realised=False)
        elif act == "ACCEPT":
            ev = emit(fid, pid, "ACTION", behavioural_action="ACCEPT", decision_round="INITIAL", lock=lock,
                      crop_before=crop0, offer_status=OfferStatus.CONSENTED.value,
                      consent_kind=ConsentKind.INITIAL.value, consent_valid=True, realised=True)
            consents[(fid, pid)] = Consent(fid, pid, crop0, ConsentKind.INITIAL.value,
                                           DecisionRound.INITIAL.value, cyc,
                                           action_event_id=ev["event_id"])
            initial_realized.append(_alloc_lookup(planned, fid, pid))
            accepted_offers.append(o)                # eligible for P3_MIXED_V1 commitment
        elif act == "REJECT":
            reject_terminal.add((fid, pid))          # current crop excluded in reopt; NO consent
            emit(fid, pid, "ACTION", behavioural_action="REJECT", decision_round="INITIAL", lock=lock,
                 crop_before=crop0, offer_status=OfferStatus.DECLINED.value, realised=False)
        elif act == "MODIFY":
            tgt, _tc = modify_target(plot_by_id[pid], farmer_by_id[fid], crops, crop0)
            if tgt is None:
                modify_no_alt += 1; pending_plots.add((fid, pid))     # retain plot; NO consent
                emit(fid, pid, "ACTION", behavioural_action="MODIFY", decision_round="INITIAL",
                     lock=lock, crop_before=crop0, offer_status=OfferStatus.NO_FEASIBLE_ALTERNATIVE.value,
                     reason_code="MODIFY_NO_FEASIBLE_ALTERNATIVE", realised=False)
            else:
                modify_requests[(fid, pid)] = tgt; reject_terminal.add((fid, pid))  # NO consent for current crop
                emit(fid, pid, "ACTION", behavioural_action="MODIFY", decision_round="INITIAL",
                     lock=lock, crop_before=crop0, crop_requested=tgt, realised=False)
        else:  # NO_RESPONSE
            pending_plots.add((fid, pid))            # PENDING_LAPSED; NO consent; VIEWED/FLEXIBLE
            emit(fid, pid, "ACTION", behavioural_action="NO_RESPONSE", decision_round="INITIAL",
                 lock=lock, crop_before=crop0, offer_status=OfferStatus.PENDING_LAPSED.value,
                 realised=False)
    modify_valid = len(modify_requests)

    # ---- assign P3_MIXED_V1 commitment timing to ACCEPTED offers ONLY (unchanged mechanism) -------
    committed = pl.commit_accepted(accepted_offers)  # {(fid,pid): {state, lock(FLEX/SOFT/HARD), crop, accepted}}

    # ---- build the action-adjusted reoptimisation scenario ---------------------------------------
    # Withdrawn farmers exit the cycle: none of their plots (accepted or not) enter reopt.
    scen2 = {}
    for (fid, pid), info in committed.items():
        if fid in withdrawn_ids:
            removed_plots.add((fid, pid)); continue
        scen2[(fid, pid)] = dict(info)               # accepted plot with its commitment lock
    crop_by_key = {(o["farmer_id"], o["plot_id"]): o["crop"] for o in fresh_offers}
    for (fid, pid) in reject_terminal | pending_plots:
        if fid in withdrawn_ids or (fid, pid) in removed_plots:
            continue
        lk = "REJECTED_TERMINAL" if (fid, pid) in reject_terminal else LOCK_FLEXIBLE
        scen2[(fid, pid)] = {"lock": lk, "crop": crop_by_key[(fid, pid)], "accepted": False}
    base_scen = committed                            # for downstream lock lookups (accepted plots only)

    # ---- run the EXISTING Phase-3/4 reoptimisation on the action-adjusted scenario --------------
    # Fail loudly on EVERY auxiliary solve, matching the validated P6 pipeline: never consume a
    # non-Optimal E*, t_floor, E*_alpha, or t_floor_alpha, and never call a downstream solve until its
    # prerequisites are Optimal. No fabrication / zero-imputation of any bound.
    plots2 = [p for p in plots if (p.farmer_id, p.plot_id) not in removed_plots]
    es, s_es = ro.max_economic(farmers, plots2, crops, scen2)
    if s_es != "Optimal":
        raise ProposedInfeasibleError("proposed.phase3_e_star", s_es)
    tfl, s_tf = ro.fairness_floor(farmers, plots2, crops, scen2, es)
    if s_tf != "Optimal":
        raise ProposedInfeasibleError("proposed.phase3_fairness_floor", s_tf)
    revised = ro.solve_phase3(farmers, plots2, crops, scen2, lam, es, tfl)
    if revised.phase3["status"] != "Optimal":
        raise ProposedInfeasibleError("proposed.reopt_phase3", revised.phase3["status"])
    ea, s_ea = co.max_economic_alpha(farmers, plots2, crops, scen2, alpha)
    if s_ea != "Optimal":
        raise ProposedInfeasibleError("proposed.phase4_e_star_alpha", s_ea)
    ta, s_ta = co.fairness_floor_alpha(farmers, plots2, crops, scen2, alpha, ea)
    if s_ta != "Optimal":
        raise ProposedInfeasibleError("proposed.phase4_fairness_floor_alpha", s_ta)
    conc = co.solve_phase4(farmers, plots2, crops, scen2, lam, alpha, ea, ta)
    conc_status = conc["status"] if isinstance(conc, dict) else conc.phase4["status"]
    if conc_status != "Optimal":
        raise ProposedInfeasibleError("proposed.concentration_phase4", conc_status)

    # ---- classify MODIFY outcomes against the actual revised recommendation ---------------------
    conc_by_key = {(a.farmer_id, a.plot_id): a for a in conc.allocations}
    modify_recommended = modify_not_recommended = 0
    for (fid, pid), tgt in modify_requests.items():
        rec = conc_by_key.get((fid, pid))
        rc = "REQUESTED_AND_RECOMMENDED" if (rec and rec.crop == tgt) else "REQUESTED_NOT_RECOMMENDED"
        if rec and rec.crop == tgt: modify_recommended += 1
        else: modify_not_recommended += 1
        emit(fid, pid, "MODIFY_RESULT", crop_requested=tgt,
             crop_recommended=(rec.crop if rec else None), reason_code=rc)

    # ---- RECOMMENDED_REVISED = the concentration-controlled revised plan (action-driven) --------
    for a in conc.allocations:
        emit(a.farmer_id, a.plot_id, "RECOMMENDATION", crop_recommended=a.crop,
             lock=lock_of(scen2, a.farmer_id, a.plot_id), decision_round="RENEWED")

    # ---- renewed consent (real records); NEVER prompt withdrawn farmers -------------------------
    renewed_prompts = 0
    renewed_counts = {"ACCEPT": 0, "REJECT": 0, "NO_RESPONSE": 0}
    existing_exception = 0
    final_realized = []
    for a in conc.allocations:
        fid, pid = a.farmer_id, a.plot_id
        if fid in withdrawn_ids:
            continue                                 # invariant: withdrawn never re-prompted
        lock = lock_of(base_scen, fid, pid)
        prior = consents.get((fid, pid))
        if lock == LOCK_HARD:
            # A HARD_LOCK/PLANTED allocation can only exist downstream of a genuine prior ACCEPT.
            # No fabrication: if the prior INITIAL consent is missing/invalid/mismatched, fail loudly.
            if prior is None or not prior.valid or prior.crop != a.crop \
                    or prior.consent_kind != ConsentKind.INITIAL.value or prior.action_event_id is None:
                raise ConsentProvenanceError(
                    f"HARD_LOCK ({fid},{pid},{a.crop}) without valid prior INITIAL ACCEPT consent")
            emit(fid, pid, "CONSENT", crop_recommended=a.crop, consent_kind=prior.consent_kind,
                 consent_valid=True, decision_round=prior.decision_round, action_event_id=prior.action_event_id,
                 offer_status=OfferStatus.CONSENTED.value, reason_code=f"AUTH_EVENT:{prior.action_event_id}")
            final_realized.append((a, prior)); continue
        if prior is not None and prior.valid and prior.crop == a.crop:
            existing_exception += 1
            # existing-consent exception: reuse the ORIGINAL consent + its ORIGINAL action_event_id;
            # do NOT generate another behavioural ACCEPT. The audit CONSENT row references the original.
            emit(fid, pid, "CONSENT", crop_recommended=a.crop, consent_kind=prior.consent_kind,
                 consent_valid=True, decision_round=prior.decision_round, action_event_id=prior.action_event_id,
                 offer_status=OfferStatus.CONSENTED.value, reason_code=f"AUTH_EVENT:{prior.action_event_id}")
            final_realized.append((a, prior)); continue
        renewed_prompts += 1
        ract = renewed_action(substream, fid, pid, cyc, farmer_by_id[fid].risk_tolerance, profile)
        renewed_counts[ract] += 1
        if ract == "ACCEPT":
            # separate ledger rows: the RENEWED ACCEPT behavioural ACTION, then the CONSENT it authorises
            ev = emit(fid, pid, "ACTION", behavioural_action="ACCEPT", decision_round="RENEWED",
                      crop_recommended=a.crop, offer_status=OfferStatus.CONSENTED.value,
                      consent_kind=ConsentKind.RENEWED.value, consent_valid=True, realised=True)
            c = Consent(fid, pid, a.crop, ConsentKind.RENEWED.value, DecisionRound.RENEWED.value, cyc,
                        action_event_id=ev["event_id"])
            consents[(fid, pid)] = c
            emit(fid, pid, "CONSENT", crop_recommended=a.crop, consent_kind=ConsentKind.RENEWED.value,
                 consent_valid=True, decision_round=DecisionRound.RENEWED.value, action_event_id=ev["event_id"],
                 offer_status=OfferStatus.CONSENTED.value, reason_code=f"AUTH_EVENT:{ev['event_id']}")
            final_realized.append((a, c))
        else:
            emit(fid, pid, "ACTION", behavioural_action=ract, decision_round="RENEWED",
                 crop_recommended=a.crop, realised=False,
                 offer_status=(OfferStatus.PENDING_LAPSED.value if ract == "NO_RESPONSE" else OfferStatus.DECLINED.value))

    # ---- FINAL_REALIZED provenance verification (against the ACCEPT action events in the ledger) --
    ledger_by_id = {row["event_id"]: row for row in ledger}
    verified = 0
    for a, c in final_realized:
        if verify_consent_provenance(a, c, ledger_by_id, cyc):
            verified += 1
    final_allocs = [a for (a, _c) in final_realized]
    coverage = (verified / len(final_allocs)) if final_allocs else 1.0
    if final_allocs and verified != len(final_allocs):
        # every FINAL_REALIZED is constructed with a genuine ACCEPT authorisation; a shortfall is a
        # provenance invariant violation, not solver infeasibility.
        raise ConsentProvenanceError(
            f"FINAL_REALIZED provenance verification failed: {len(final_allocs) - verified} of "
            f"{len(final_allocs)} allocations lack verified exact-crop ACCEPT consent")

    # ---- fairness with CORRECT B1 reference -----------------------------------------------------
    fr_i = fair.fairness_report(_AllocSet(initial_realized), farmers, b1_reference=b1cash, cohorts=cohorts) if initial_realized else None
    fr_f = fair.fairness_report(_AllocSet(final_allocs), farmers, b1_reference=b1cash, cohorts=cohorts) if final_allocs else None

    def tier(allocs):
        return {"cash": _cash(allocs), "area": _area(allocs), "n": len(allocs)}

    planned_cash = _cash(planned); rec_cash = _cash(conc.allocations); final_cash = _cash(final_allocs)

    # Publication-evaluation observability only.
    # These are measurements of already-computed solver outputs; they do NOT
    # alter optimisation, farmer actions, consent, or allocation authority.
    _rec_per_crop, rec_concentration = co.concentration_metrics(
        conc, plots, alpha=alpha
    )
    _final_per_crop, final_concentration = co.concentration_metrics(
        _AllocSet(final_allocs), plots, alpha=None
    )

    recommended_stability = dict(getattr(conc, "phase3", {}) or {})
    recommended_phase4 = dict(getattr(conc, "phase4", {}) or {})

    # invariant check surfaced in result: withdrawn ∩ renewed-prompted == empty
    renewed_prompt_farmers = {r["farmer_id"] for r in ledger if r["event_type"] == "CONSENT" and r["decision_round"] == "RENEWED"} \
        | {r["farmer_id"] for r in ledger if r["event_type"] == "ACTION" and r["decision_round"] == "RENEWED"}
    withdrawn_in_renewed = withdrawn_ids & renewed_prompt_farmers

    return {
        "meta": {"protocol": "action-consent-v1", "profile": profile,
                 "lambda": lam, "alpha": alpha, "provenance": C.ACTION_PROVENANCE,
                 "seed": seed, "cycle_id": cyc, "instance_hash": _instance_hash,
                 "uncertainty_condition": uncertainty_condition, "realisation_hash": realisation_hash,
                 "substream_farmer_response": substream, "b1_reference_source": "B1_ILP (run_b1_ilp)",
                 "b1_reference_total_cash": round(sum(b1cash.values()))},
        "participating_farmers": len(participating),
        "action_counts": counts, "withdrawn_farmers": len(withdrawn_ids),
        "modify_valid": modify_valid, "modify_no_alternative": modify_no_alt,
        "modify_requested_and_recommended": modify_recommended,
        "modify_requested_not_recommended": modify_not_recommended,
        "lock_blocked_actions": 0, "consent_invalidations": consent_invalidations,
        "renewed_prompts": renewed_prompts, "renewed_counts": renewed_counts,
        "existing_consent_exceptions": existing_exception,
        "reopt_status": revised.phase3["status"], "conc_status": conc_status,
        "tiers": {"PLANNED": tier(planned), "INITIAL_REALIZED": tier(initial_realized),
                  "RECOMMENDED_REVISED": tier(conc.allocations), "FINAL_REALIZED": tier(final_allocs)},
        "recommendation_realisation_ratio_vs_planned": round(final_cash / planned_cash, 4) if planned_cash else None,
        "recommendation_realisation_ratio_vs_recommended": round(final_cash / rec_cash, 4) if rec_cash else None,
        "unconsented_revised_recommendations": max(0, len(conc.allocations) - len(final_allocs)),
        "consent_coverage_final": round(coverage, 6),
        "consent_coverage_derivation": "provenance-verified exact-crop ACCEPT consent (farmer,plot,crop,valid,action_event_id->ACCEPT event,decision_round,cycle) / FINAL_REALIZED count",
        "withdrawn_in_renewed_prompts": sorted(withdrawn_in_renewed),   # MUST be empty
        "fairness_v2_initial": (fr_i or {}).get("primary") if fr_i else None,
        "fairness_v2_final": (fr_f or {}).get("primary") if fr_f else None,

        # Existing deterministic Phase-3/4 measurements surfaced for the
        # predeclared Final30 sensitivity/evaluation families.
        "recommended_revised_stability": recommended_stability,
        "recommended_revised_phase4": recommended_phase4,
        "recommended_revised_concentration": rec_concentration,
        "final_realized_concentration": final_concentration,
        "concentration_constraint_scope": "RECOMMENDED_REVISED only",

        "ledger": ledger,
        "ledger_event_types": sorted({r["event_type"] for r in ledger}),
    }


def _alloc_lookup(allocs, fid, pid):
    for a in allocs:
        if a.farmer_id == fid and a.plot_id == pid:
            return a
    return None


def consent_matches(alloc, consent) -> bool:
    """Exact-crop consent verification used for FINAL_REALIZED coverage. A mismatched or invalid
    consent must return False (used by tests to prove coverage is record-derived, not a counter)."""
    return (consent is not None and consent.valid and consent.farmer_id == alloc.farmer_id
            and consent.plot_id == alloc.plot_id and consent.crop == alloc.crop)


def verify_consent_provenance(alloc, consent, ledger_by_id, cyc) -> bool:
    """Full provenance chain for a FINAL_REALIZED allocation: the consent must exactly match the
    allocation (farmer/plot/exact-crop, valid), have consent_kind == decision_round, carry a non-null
    action_event_id whose referenced ledger event is a real ACTION with behavioural_action==ACCEPT,
    matching farmer/plot, a decision_round matching the consent, cycle_id matching the current cycle,
    the consent cycle_id matching the current cycle, AND the referenced ACCEPT ACTION must itself
    authorise the consent's crop (INITIAL -> crop_before; RENEWED -> crop_recommended)."""
    if not consent_matches(alloc, consent):
        return False
    # consent_kind and decision_round both range over INITIAL/RENEWED and denote the same
    # authorisation round; a mismatch is malformed provenance.
    if consent.consent_kind != consent.decision_round:
        return False
    if consent.cyc != cyc:
        return False
    if consent.action_event_id is None:
        return False
    ev = ledger_by_id.get(consent.action_event_id)
    if ev is None:
        return False
    if ev.get("event_type") != "ACTION" or ev.get("behavioural_action") != "ACCEPT":
        return False
    if ev.get("farmer_id") != alloc.farmer_id or ev.get("plot_id") != alloc.plot_id:
        return False
    if ev.get("decision_round") != consent.decision_round:
        return False
    if ev.get("cycle_id") != cyc:                       # referenced ACCEPT event must be this cycle
        return False
    # the referenced ACCEPT ACTION must itself authorise the consent's crop:
    #   INITIAL ACCEPT is drawn on the fresh offered crop  -> crop_before
    #   RENEWED ACCEPT is drawn on the revised recommended crop -> crop_recommended
    if consent.decision_round == DecisionRound.INITIAL.value:
        if ev.get("crop_before") != consent.crop:
            return False
    elif consent.decision_round == DecisionRound.RENEWED.value:
        if ev.get("crop_recommended") != consent.crop:
            return False
    else:
        return False
    return True
