"""
Proposed Phase 6 — full deterministic Proposed pipeline (end-to-end integration).

Pure ORCHESTRATION: this module CALLS the already-validated Phase 1-5 modules and never
duplicates their optimisation formulations or adds new behavioural assumptions. It runs
the canonical deterministic workflow once and returns a structured, traceable result:

  Stage 0 instance/provenance
  Stage 1 STATIC PLAN            (B3 ILP-v2, canonical ε=0.95)              -> PLANNED
  Stage 2 initial response       (Phase-1 ACCEPT/REJECT)                   -> REALIZED_INITIAL
  Stage 3 commitment snapshot    (existing P3_MIXED_V1 mixed scenario)
  Stage 4 stability-aware reopt  (Phase-3, λ dev-ref, full B3 ε-structure) -> REVISED
  Stage 5 concentration control  (Phase-4, α dev-ref)                      -> REVISED (conc-controlled)
  Stage 6 resilience demo        (Phase-5, tiny representative set)         -> COUNTERFACTUAL_BACKUP

State labels are kept strictly separate; revised/backup recommendations are NEVER realised
and carry revised_requires_renewed_consent=True. The pipeline fails loudly if a stage that
must be Optimal is not (no silent continuation from invalid optimisation output).
"""

from __future__ import annotations

from .. import experiment as exp, fairness as fair, config
from ..generate import CROPS
from ..ilp_reference import run_b1_ilp, run_b3_ilp, b2_ilp_total
from ..baselines import verify_hard_constraints
from .participation import AcceptanceConfig, apply_participation
from . import commitment as cm, reoptimize as ro, concentration as co, resilience as rz

# Development-reference configuration (NOT publication-selected).
DEV_SEED = 20260812
DEV_LAMBDA = 0.05
DEV_ALPHA = 0.40
SCENARIO_ID = "P3_MIXED_V1"

# Explicit state labels
PLANNED = "PLANNED"
REALIZED_INITIAL = "REALIZED_INITIAL"
REVISED = "REVISED"
REVISED_CONC = "CONCENTRATION_CONTROLLED_REVISED_PLAN"
COUNTERFACTUAL_BACKUP = "COUNTERFACTUAL_POST_SHOCK_BACKUP_PLAN"

STAGE_ORDER = ["stage0_instance", "stage1_static_plan", "stage2_initial_response",
               "stage3_commitment", "stage4_stability_reopt", "stage5_concentration",
               "stage6_resilience_demo"]


class PipelineError(RuntimeError):
    pass


def _require_optimal(where, status):
    if status != "Optimal":
        raise PipelineError(f"{where}: required Optimal, got {status!r} — refusing to continue")


def _cash(res):
    return round(sum(a.cash_net for a in res.allocations))


def _consent(fid, pid, current_crop, accepted_crop_map):
    """Allocation-specific consent. Existing consent iff the farmer accepted the original
    Phase-1 crop for this plot AND the current recommended crop is still that accepted crop.
    Renewed consent required for recovered offers (no prior accept) or any crop change."""
    acc = accepted_crop_map.get((fid, pid))
    if acc is None:
        return {"consent_exists": False, "requires_renewed_consent": True,
                "consent_basis": "recovered_or_no_prior_accept"}
    if current_crop == acc:
        return {"consent_exists": True, "requires_renewed_consent": False,
                "consent_basis": "unchanged_accepted_crop"}
    return {"consent_exists": False, "requires_renewed_consent": True,
            "consent_basis": "crop_changed_from_accepted"}


def run_proposed_pipeline(seed=DEV_SEED, lam=DEV_LAMBDA, alpha=DEV_ALPHA,
                          base=None, run_id="p6_dev", instance=None):
    ledger = []
    seq = [0]

    def log(**kw):
        seq[0] += 1
        rec = {"run_id": run_id, "master_seed": seed, "sequence": seq[0]}
        rec.update(kw)
        ledger.append(rec)
        return rec

    # ---- Stage 0: instance / provenance ----
    # uncertainty-v1: an externally perturbed instance (participation-filtered, resource-scaled) may
    # be injected so Proposed consumes the SAME realisation as the baselines; else build canonically.
    inst = instance if instance is not None else exp.build_instance(seed, tightness="base")
    f, plots = inst["farmers"], inst["plots"]
    ih = inst["record"]["instance_hash"]
    allf = [x.farmer_id for x in f]
    psub = exp.substream(seed, "farmer_response", base)
    stage0 = {
        "master_seed": seed, "instance_hash": ih,
        "dataset_version": inst["record"]["dataset_version"],
        "config": {"epsilon": config.CANONICAL_B3_EPSILON, "fairness_version": config.FAIRNESS_VERSION,
                   "formulation_version": config.FORMULATION_VERSION,
                   "fairness_floor_numeric_tol": config.FAIRNESS_FLOOR_NUMERIC_TOL,
                   "resilience_floor_numeric_tol": config.RESILIENCE_FLOOR_NUMERIC_TOL,
                   "lambda_dev_ref": lam, "alpha_dev_ref": alpha, "scenario_id": SCENARIO_ID},
        "rng_substream_farmer_response": psub,
    }
    log(stage="stage0_instance", event="instance_built", instance_hash=ih, counterfactual=False)

    # ---- Stage 1: STATIC PLAN (B3 ILP-v2, canonical ε) ----
    tstar = b2_ilp_total(f, plots, CROPS)["b2_ilp_cash_total"]
    b1 = run_b1_ilp(f, plots, CROPS); _require_optimal("stage1.B1", b1.solver["status"])
    b1cash = fair.farmer_cash(b1); cohorts = fair.bottom_cohorts(b1cash, allf)
    planned = run_b3_ilp(f, plots, CROPS, tstar=tstar)
    _require_optimal("stage1.B3", planned.solver["status"])
    planned_rep = fair.fairness_report(planned, f, b1_reference=b1cash, cohorts=cohorts)
    stage1 = {"state": PLANNED, "cash": _cash(planned),
              "area_ha": round(sum(a.area_ha for a in planned.allocations), 1),
              "n_farmers": planned_rep["primary"]["n_participating"],
              "per_ha_gini_all": planned_rep["primary"]["per_ha_gini_all"],
              "epsilon": planned.solver["epsilon"], "status": planned.solver["status"],
              "consent_exists": False, "counterfactual": False}
    for a in planned.allocations:
        log(stage="stage1_static_plan", event="planned_offer", farmer_id=a.farmer_id, plot_id=a.plot_id,
            crop_before=None, crop_after=a.crop, allocation_status=PLANNED, planned_cash=a.cash_net,
            current_cash=a.cash_net, source_phase="B3", consent_exists=False, counterfactual=False)

    # ---- Stage 2: initial farmer response (Phase-1) ----
    realised, offers = apply_participation(planned, f, psub, AcceptanceConfig(),
                                           run_id=run_id, master_seed=seed, instance_hash=ih)
    accepted = sum(1 for o in offers if o["status"] == "REALISED")
    rejected = len(offers) - accepted
    realised_rep = fair.fairness_report(realised, f, b1_reference=b1cash, cohorts=cohorts)
    p_cash, r_cash = _cash(planned), _cash(realised)
    stage2 = {"state": REALIZED_INITIAL, "offers": len(offers), "accepted": accepted, "rejected": rejected,
              "accept_rate": round(accepted/len(offers), 4), "cash": r_cash,
              "area_ha": round(sum(a.area_ha for a in realised.allocations), 1),
              "cash_realisation_ratio": round(r_cash/p_cash, 4),
              "per_ha_gini_all": realised_rep["primary"]["per_ha_gini_all"],
              "consent_exists": True, "counterfactual": False}
    for o in offers:
        log(stage="stage2_initial_response", event="farmer_response", farmer_id=o["farmer_id"],
            plot_id=o["plot_id"], crop_before=o["planned_crop"],
            crop_after=(o["planned_crop"] if o["status"] == "REALISED" else "FALLOW_UNALLOCATED"),
            participation_response=o["response"],
            allocation_status=(REALIZED_INITIAL if o["status"] == "REALISED" else "REJECTED_FALLOW"),
            planned_cash=o["planned_cash_return"], current_cash=o["realised_cash_return"],
            source_phase="phase1", consent_exists=(o["status"] == "REALISED"), counterfactual=False)

    # ---- Stage 3: commitment snapshot (existing P3_MIXED_V1) ----
    scen = cm.mixed_commitment_scenario(offers, SCENARIO_ID)
    from collections import Counter
    locks = dict(Counter(v["lock"] for v in scen.values()))
    stage3 = {"scenario_id": SCENARIO_ID, "provenance": "SYNTHETIC_EXPERIMENTAL commitment-timing (existing); NOT observed prevalence",
              "lock_counts": locks, "consent_exists": True, "counterfactual": False}
    for (fid, pid), info in scen.items():
        log(stage="stage3_commitment", event="commitment_state", farmer_id=fid, plot_id=pid,
            crop_after=info["crop"], commitment_state=info["state"].value, lock_level=info["lock"],
            allocation_status=REALIZED_INITIAL if info["accepted"] else "REJECTED_TERMINAL",
            source_phase="phase2", consent_exists=info["accepted"], counterfactual=False)

    # ---- Stage 4: stability-aware reoptimisation (Phase-3) ----
    e_star, es = ro.max_economic(f, plots, CROPS, scen); _require_optimal("stage4.E*", es)
    t_floor, tf = ro.fairness_floor(f, plots, CROPS, scen, e_star); _require_optimal("stage4.t_floor", tf)
    revised = ro.solve_phase3(f, plots, CROPS, scen, lam, e_star, t_floor)
    _require_optimal("stage4.reopt", revised.phase3["status"])
    rev_rep = fair.fairness_report(revised, f, b1_reference=b1cash, cohorts=cohorts)
    # accepted original Phase-1 crop per plot (None if rejected/no prior accept)
    accepted_crop_map = {(o["farmer_id"], o["plot_id"]): o["planned_crop"]
                         for o in offers if o["status"] == "REALISED"}
    revised_crop_map = {(a.farmer_id, a.plot_id): a.crop for a in revised.allocations}
    # per-allocation Stage-4 ledger records (gap 1 fix)
    s4_unconsented = 0
    for a in revised.allocations:
        info = scen.get((a.farmer_id, a.plot_id), {}); lock = info.get("lock", "?")
        orig = accepted_crop_map.get((a.farmer_id, a.plot_id))  # accepted crop, or None if recovered
        cons = _consent(a.farmer_id, a.plot_id, a.crop, accepted_crop_map)
        if cons["requires_renewed_consent"]:
            s4_unconsented += 1
        cls = ("recovered_offer" if lock == "REJECTED_TERMINAL" else
               ("changed" if orig is not None and a.crop != orig else "unchanged"))
        log(stage="stage4_stability_reopt", event="revised_offer", farmer_id=a.farmer_id, plot_id=a.plot_id,
            crop_before=(orig if orig is not None else "FALLOW_OR_REJECTED"), crop_after=a.crop,
            lock_level=lock, allocation_status=REVISED, reason=cls, planned_cash=None, current_cash=a.cash_net,
            consent_exists=cons["consent_exists"], requires_renewed_consent=cons["requires_renewed_consent"],
            consent_basis=cons["consent_basis"], source_phase="phase3", counterfactual=False)
    stage4 = {"state": REVISED, "lambda_dev_ref": lam, "revised_cash": _cash(revised),
              "recovery_potential_vs_realised": _cash(revised) - r_cash,
              "soft_changes": revised.phase3["changed_soft"], "flex_changes": revised.phase3["changed_flex"],
              "hard_lock_changes": revised.phase3["hard_lock_changes"],
              "per_ha_gini_all": rev_rep["primary"]["per_ha_gini_all"],
              "fairness_structure": revised.phase3["fairness_structure"], "status": revised.phase3["status"],
              "contains_unconsented_recommendations": s4_unconsented > 0,
              "unconsented_allocation_count": s4_unconsented,
              "revised_requires_renewed_consent": True, "counterfactual": False}

    # ---- Stage 5: concentration control (Phase-4) ----
    ea, esa = co.max_economic_alpha(f, plots, CROPS, scen, alpha); _require_optimal("stage5.E*_alpha", esa)
    ta, tfa = co.fairness_floor_alpha(f, plots, CROPS, scen, alpha, ea); _require_optimal("stage5.t_floor_alpha", tfa)
    conc = co.solve_phase4(f, plots, CROPS, scen, lam, alpha, ea, ta)
    if isinstance(conc, dict):
        raise PipelineError(f"stage5.concentration: required Optimal, got {conc['status']!r}")
    _require_optimal("stage5.concentration", conc.phase4["status"])
    cmap, csum = co.concentration_metrics(conc, plots, alpha=alpha)
    conc_rep = fair.fairness_report(conc, f, b1_reference=b1cash, cohorts=cohorts)
    chk5 = verify_hard_constraints(conc, f, plots, CROPS)
    s5_unconsented = 0
    for a in conc.allocations:
        cons = _consent(a.farmer_id, a.plot_id, a.crop, accepted_crop_map)
        if cons["requires_renewed_consent"]:
            s5_unconsented += 1
    stage5 = {"state": REVISED_CONC, "alpha_dev_ref": alpha, "cash": _cash(conc),
              "economic_retention_vs_revised_pct": round(100*_cash(conc)/_cash(revised), 2),
              "max_LPS": csum["max_LPS"], "mean_HHI": csum["mean_HHI"], "n_active_crops": csum["n_active_crops"],
              "concentration_violations": csum["target_violations"], "hard_lock_changes": conc.phase3["hard_lock_changes"],
              "hard_violations": len(chk5["violations"]), "per_ha_gini_all": conc_rep["primary"]["per_ha_gini_all"],
              "status": conc.phase4["status"],
              "contains_unconsented_recommendations": s5_unconsented > 0,
              "unconsented_allocation_count": s5_unconsented,
              "revised_requires_renewed_consent": True, "counterfactual": False}
    for a in conc.allocations:
        info = scen.get((a.farmer_id, a.plot_id), {}); lock = info.get("lock", "?")
        prev = revised_crop_map.get((a.farmer_id, a.plot_id))       # actual Stage-4 revised crop (gap 2 fix)
        cons = _consent(a.farmer_id, a.plot_id, a.crop, accepted_crop_map)  # gap 3 fix
        lbl = ("conc_shifted" if prev is not None and a.crop != prev else "unchanged_from_revised")
        log(stage="stage5_concentration", event="concentration_controlled_offer", farmer_id=a.farmer_id,
            plot_id=a.plot_id, crop_before=prev, crop_after=a.crop, lock_level=lock,
            allocation_status=REVISED_CONC, reason=lbl, planned_cash=None, current_cash=a.cash_net,
            consent_exists=cons["consent_exists"], requires_renewed_consent=cons["requires_renewed_consent"],
            consent_basis=cons["consent_basis"], source_phase="phase4", counterfactual=False)

    # ---- Stage 6: resilience demonstration (tiny representative set) ----
    stage6 = _resilience_demo(f, plots, scen, conc, alpha, lam, log)

    result = {
        "run_id": run_id, "status": "development/checkpoint (integrated)",
        "stage_order": STAGE_ORDER,
        "stage0_instance": stage0, "stage1_static_plan": stage1, "stage2_initial_response": stage2,
        "stage3_commitment": stage3, "stage4_stability_reopt": stage4, "stage5_concentration": stage5,
        "stage6_resilience_demo": stage6,
        "state_labels": [PLANNED, REALIZED_INITIAL, REVISED, REVISED_CONC, COUNTERFACTUAL_BACKUP],
        "revised_requires_renewed_consent": True,
        "note": "integration/orchestration only; calls validated Phase 1-5 modules; no methodology change, no new behaviour, no LLM, no final experiment",
    }
    return {"result": result, "ledger": ledger,
            "objects": {"planned": planned, "realised": realised, "scen": scen,
                        "revised": revised, "conc": conc, "b1cash": b1cash, "cohorts": cohorts,
                        "e_star": e_star, "t_floor": t_floor}}


def _resilience_demo(f, plots, scen, pre_conc, alpha, lam, log):
    """Deterministic representative resilience integration (NOT the full 66-scenario study).
    Selection rules (documented, not cherry-picked):
      N-1  : active crop with MAXIMUM pre-shock LPS in the concentration-controlled plan.
      hazard: lexicographically FIRST non-empty hazard zone in that plan.
      infeasible-path: the known R5-HZ1 zone if present (explicit INFEASIBLE integration test)."""
    _, csum = co.concentration_metrics(pre_conc, plots, alpha=alpha)
    active = csum["active_crops"]
    pby = {p.plot_id: p for p in plots}
    # N-1 selection: crop with max LPS
    lps_by_crop = {c: rz.largest_producer(pre_conc, plots, c)[2] for c in active}
    n1_crop = max(lps_by_crop, key=lps_by_crop.get)
    ff, _, lps = rz.largest_producer(pre_conc, plots, n1_crop)
    imm = rz.immediate_nminus1(pre_conc, plots, ff, n1_crop)
    r_n1, es, ts, stg_n1 = rz.post_shock_reopt(f, plots, CROPS, rz.remove_farmer(scen, ff), alpha, lam)
    n1 = {"selection_rule": "active crop with max pre-shock LPS", "shock_type": "N-1_largest_producer",
          "target_crop": n1_crop, "failed_farmer": ff, "state": COUNTERFACTUAL_BACKUP,
          "immediate_target_loss_fraction": imm["target_loss_fraction"], "pre_shock_LPS": round(lps, 4),
          "immediate_cash_loss": imm["immediate_cash_loss"], "failed_stage": stg_n1["failed_stage"],
          "backup_status": stg_n1["cbc_status"], "backup_optimal": r_n1 is not None,
          "counterfactual": True, "consent_exists": False}
    if r_n1 is not None:
        integ = rz.verify_failure_integrity(r_n1, set(imm["failed_plot_ids"]), rz.remove_farmer(scen, ff), pre_conc)
        n1.update({"post_reopt_cash": _cash(r_n1),
                   "recovery_potential": _cash(r_n1) - imm["immediate_remaining_cash"],
                   "surviving_hard_lock_changes": 0 if integ["surviving_hard_locks_ok"] else -1,
                   "failed_plots_reused": integ["failed_plots_reused"]})
    log(stage="stage6_resilience_demo", event="N-1_shock", farmer_id=ff, crop_after=n1_crop,
        allocation_status=COUNTERFACTUAL_BACKUP, reason=f"N-1 max-LPS crop; backup {n1['backup_status']}",
        source_phase="phase5", consent_exists=False, counterfactual=True)

    # hazard selection: lexicographically first non-empty zone in the plan
    plan_zones = sorted({pby[a.plot_id].hazard_zone for a in pre_conc.allocations})
    hz_zone = plan_zones[0]
    post_hz, zplots = rz.remove_zone(scen, plots, hz_zone)
    affected = [a for a in pre_conc.allocations if a.plot_id in zplots]
    r_hz, esz, tsz, stg_hz = rz.post_shock_reopt(f, plots, CROPS, post_hz, alpha, lam)
    hz = {"selection_rule": "lexicographically first non-empty hazard zone", "shock_type": "hazard_zone_outage",
          "zone": hz_zone, "affected_plots": len(affected), "state": COUNTERFACTUAL_BACKUP,
          "immediate_cash_loss": round(sum(a.cash_net for a in affected)),
          "failed_stage": stg_hz["failed_stage"], "backup_status": stg_hz["cbc_status"],
          "backup_optimal": r_hz is not None, "counterfactual": True, "consent_exists": False}
    if r_hz is not None:
        integ = rz.verify_failure_integrity(r_hz, zplots, post_hz, pre_conc)
        hz.update({"post_reopt_cash": _cash(r_hz),
                   "surviving_hard_lock_changes": 0 if integ["surviving_hard_locks_ok"] else -1,
                   "failed_plots_reused": integ["failed_plots_reused"]})
    log(stage="stage6_resilience_demo", event="hazard_shock", crop_after=None, allocation_status=COUNTERFACTUAL_BACKUP,
        reason=f"hazard {hz_zone}; backup {hz['backup_status']}", source_phase="phase5",
        consent_exists=False, counterfactual=True)

    # explicit known-infeasible integration path: R5-HZ1 (if present in the plan)
    infeas = None
    if "R5-HZ1" in plan_zones:
        post_r5, r5plots = rz.remove_zone(scen, plots, "R5-HZ1")
        r_r5, esr, tsr, stg_r5 = rz.post_shock_reopt(f, plots, CROPS, post_r5, alpha, lam)
        infeas = {"selection_rule": "known R5-HZ1 (explicit INFEASIBLE-path integration test)",
                  "zone": "R5-HZ1", "failed_stage": stg_r5["failed_stage"], "backup_status": stg_r5["cbc_status"],
                  "backup_optimal": r_r5 is not None, "extracted_plan": r_r5 is not None,
                  "counterfactual": True}
        log(stage="stage6_resilience_demo", event="hazard_shock_infeasible_path", allocation_status=COUNTERFACTUAL_BACKUP,
            reason=f"R5-HZ1 expected infeasible; status {stg_r5['cbc_status']}", source_phase="phase5",
            consent_exists=False, counterfactual=True)
    return {"nminus1_representative": n1, "hazard_representative": hz,
            "infeasible_path": infeas, "note": "tiny representative set for integration validation only; full 66-scenario study remains the Phase-5 evidence"}


def prepare_proposed_prerequisites(seed=DEV_SEED, base=None, instance=None):
    """Prefix helper for the action-consent layer: returns ONLY the prerequisite plan objects it
    needs — B3 planned + canonical B1 reference — WITHOUT the legacy Phase-1 ACCEPT/REJECT gate and
    WITHOUT Stage-6 resilience. It also does NOT assign any P3_MIXED_V1 commitment timing: a fresh B3
    offer is VIEWED/FLEXIBLE and must not be SOFT/HARD-locked before the farmer has accepted it. The
    commitment ladder is assigned by the action layer AFTER acceptance, on ACCEPTed offers only
    (see actions.run_action_consent_layer). Returns {planned, offers, b1cash, cohorts, farmers, plots,
    instance_hash}; `offers` is the list of fresh (all-FLEXIBLE) planned offers.
    """
    inst = instance if instance is not None else exp.build_instance(seed, tightness="base")
    f, plots = inst["farmers"], inst["plots"]
    allf = [x.farmer_id for x in f]
    ih = inst["record"]["instance_hash"]
    tstar = b2_ilp_total(f, plots, CROPS)["b2_ilp_cash_total"]
    b1 = run_b1_ilp(f, plots, CROPS); _require_optimal("prep.B1", b1.solver["status"])
    b1cash = fair.farmer_cash(b1); cohorts = fair.bottom_cohorts(b1cash, allf)
    planned = run_b3_ilp(f, plots, CROPS, tstar=tstar)
    _require_optimal("prep.B3", planned.solver["status"])
    # Fresh offers: every planned offer is VIEWED/FLEXIBLE, not yet accepted, not yet committed.
    offers = [{"farmer_id": a.farmer_id, "plot_id": a.plot_id, "crop": a.crop} for a in planned.allocations]
    return {"planned": planned, "offers": offers, "b1cash": b1cash, "cohorts": cohorts,
            "farmers": f, "plots": plots, "instance_hash": ih}


def commit_accepted(accepted_offers, scenario_id=SCENARIO_ID):
    """Assign P3_MIXED_V1 commitment timing to INITIALLY ACCEPTED offers only, using the UNCHANGED
    deterministic hash mechanism (accepted offers passed as status=REALISED, as originally designed).
    Returns {(farmer_id, plot_id): {state, lock, crop, accepted=True}}."""
    return cm.mixed_commitment_scenario(
        [{"farmer_id": o["farmer_id"], "plot_id": o["plot_id"],
          "planned_crop": o["crop"], "status": "REALISED"} for o in accepted_offers],
        scenario_id)
