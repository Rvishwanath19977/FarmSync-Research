"""
Proposed Phase 5 — disaster / N-1 resilience + post-shock backup reoptimisation.

COUNTERFACTUAL / experimental stress tests on a Phase-4 pre-shock revised plan. Not
observed disasters or probabilities. Two shock families:
  (A) N-1 largest-producer failure: for a target crop, the farmer with the largest
      expected production of that crop becomes unavailable (ALL their allocations, not
      just the target crop).
  (B) correlated hazard-zone outage: all plots in an existing `Plot.hazard_zone`
      (region + spatial cluster, synthetic correlated-failure unit) become unavailable.

Disaster semantics vs locks:
  A shock may physically remove a HARD_LOCK/PLANTED allocation — that is exogenous loss
  (FAILED_UNAVAILABLE), NOT a lock violation. Every SURVIVING hard lock stays immutable,
  and failed plots are never reused by the post-shock optimiser.

Post-shock backup reoptimisation reuses the Phase-4 machinery with the failed
farmer/plots removed from scope; concentration alpha stays the pre-shock alpha; E*_shock
and t_floor_shock are recomputed under E >= 0.95*E*_shock; both floors enforced; exact
fairness tolerance; non-Optimal is never extracted. Outputs are REVISED BACKUP
RECOMMENDATIONS (counterfactual), never realised adoption.
"""

from __future__ import annotations

from ..planning import op_yield_value
from . import concentration as co
from .commitment import LOCK_HARD


def _crop_production_by_farmer(result, plots, crop):
    pby = {p.plot_id: p for p in plots}
    out = {}
    for a in result.allocations:
        if a.crop != crop:
            continue
        p = pby[a.plot_id]; y, _ = op_yield_value(a.crop, p.region_id, p.active_season.value)
        out[a.farmer_id] = out.get(a.farmer_id, 0.0) + (y or 0.0) * a.area_ha
    return out


def largest_producer(result, plots, crop):
    prod = _crop_production_by_farmer(result, plots, crop)
    if not prod:
        return None, 0.0, 0.0
    Qc = sum(prod.values())
    fid = max(prod, key=prod.get)
    return fid, prod[fid], (prod[fid] / Qc if Qc > 0 else 0.0)


def farmer_expected_production(result, plots, farmer_id):
    pby = {p.plot_id: p for p in plots}
    q = 0.0; area = 0.0; n = 0; locks = {}
    for a in result.allocations:
        if a.farmer_id != farmer_id:
            continue
        p = pby[a.plot_id]; y, _ = op_yield_value(a.crop, p.region_id, p.active_season.value)
        q += (y or 0.0) * a.area_ha; area += a.area_ha; n += 1
    return q, round(area, 2), n


def remove_farmer(scenario, failed_farmer):
    """Post-shock scenario with all of the failed farmer's plots removed (unavailable)."""
    return {k: v for k, v in scenario.items() if k[0] != failed_farmer}


def remove_zone(scenario, plots, zone):
    zone_plots = {p.plot_id for p in plots if p.hazard_zone == zone}
    return ({k: v for k, v in scenario.items() if k[1] not in zone_plots}, zone_plots)


def failed_allocation_locks(pre_result, scenario, failed_ids_by_plot):
    """Lock composition of the removed allocations (for hard/soft/flex accounting)."""
    comp = {}
    for a in pre_result.allocations:
        if a.plot_id in failed_ids_by_plot:
            lock = scenario.get((a.farmer_id, a.plot_id), {}).get("lock", "?")
            comp[lock] = comp.get(lock, 0) + 1
    return comp


def immediate_nminus1(pre_result, plots, failed_farmer, target_crop):
    """Immediate post-shock state (before recovery reopt)."""
    pre_cash = round(sum(a.cash_net for a in pre_result.allocations))
    failed_cash = round(sum(a.cash_net for a in pre_result.allocations if a.farmer_id == failed_farmer))
    prod = _crop_production_by_farmer(pre_result, plots, target_crop)
    Qc_before = sum(prod.values()); failed_target = prod.get(failed_farmer, 0.0)
    Qc_after = Qc_before - failed_target
    q_all, area, n_alloc = farmer_expected_production(pre_result, plots, failed_farmer)
    failed_plots = {a.plot_id for a in pre_result.allocations if a.farmer_id == failed_farmer}
    return {
        "failed_farmer": failed_farmer, "target_crop": target_crop,
        "failed_area_ha": area, "failed_expected_production": round(q_all, 1),
        "affected_allocations": n_alloc, "failed_plot_ids": sorted(failed_plots),
        "target_prod_before": round(Qc_before, 1), "target_prod_after_immediate": round(Qc_after, 1),
        "target_loss_fraction": round(failed_target / Qc_before, 4) if Qc_before > 0 else 0.0,
        "total_cash_before": pre_cash, "immediate_remaining_cash": pre_cash - failed_cash,
        "immediate_cash_loss": failed_cash,
    }


def post_shock_reopt(farmers, plots, crops, post_scenario, alpha, lam, floor_tol=None):
    """Recompute E*_shock, t_floor_shock and solve the backup plan. Returns (result_or_None,
    e_star_shock, t_floor_shock, stage_status) where stage_status records the exact CBC
    status at each stage and the failure stage. Uses the documented post-shock numerical
    floor tolerance (config.RESILIENCE_FLOOR_NUMERIC_TOL) so the provably-feasible recovery
    plan can be extracted past the max-attained-floor knife-edge; genuine infeasibility
    (failing at E*_shock, before any fairness floor) is preserved, never masked."""
    from ..config import RESILIENCE_FLOOR_NUMERIC_TOL
    floor_tol = RESILIENCE_FLOOR_NUMERIC_TOL if floor_tol is None else floor_tol
    ea, est = co.max_economic_alpha(farmers, plots, crops, post_scenario, alpha)
    if est != "Optimal":
        return None, ea, None, {"failed_stage": "E*_shock", "cbc_status": est,
                                "e_star": est, "t_floor": None, "final": None}
    ta, tst = co.fairness_floor_alpha(farmers, plots, crops, post_scenario, alpha, ea)
    if tst != "Optimal":
        return None, ea, ta, {"failed_stage": "t_floor_shock", "cbc_status": tst,
                              "e_star": est, "t_floor": tst, "final": None}
    r = co.solve_phase4(farmers, plots, crops, post_scenario, lam, alpha, ea, ta, floor_tol=floor_tol)
    if isinstance(r, dict):
        return None, ea, ta, {"failed_stage": "final_backup", "cbc_status": r["status"],
                              "e_star": est, "t_floor": tst, "final": r["status"]}
    return r, ea, ta, {"failed_stage": None, "cbc_status": "Optimal",
                       "e_star": est, "t_floor": tst, "final": "Optimal",
                       "numerical_floor_tolerance": floor_tol}


def verify_failure_integrity(result, failed_plot_ids, scenario, pre_result):
    """failed plots never reused; surviving hard locks keep their crop."""
    used_failed = any(a.plot_id in failed_plot_ids for a in result.allocations)
    got = {(a.farmer_id, a.plot_id): a.crop for a in result.allocations}
    surviving_hard_ok = True
    for (fid, pid), info in scenario.items():
        if info["lock"] == LOCK_HARD and pid not in failed_plot_ids:
            if got.get((fid, pid)) != info["crop"]:
                surviving_hard_ok = False; break
    return {"failed_plots_reused": used_failed, "surviving_hard_locks_ok": surviving_hard_ok}
