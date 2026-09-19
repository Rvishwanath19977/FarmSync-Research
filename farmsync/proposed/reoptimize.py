"""
Proposed Phase 3 — stability-aware reoptimisation (REVISED PLAN, not realised).

First phase where the optimiser responds to Phase-1 rejections and Phase-2 commitment
states. Same CBC MILP backbone, dataset/gate/costs/prices/budgets/labour/market caps and
fairness-v2 framework. Output is a REVISED PLAN / recommendations — NOT realised farmer
adoption (no behavioural acceptance round runs here).

Lock rules (from the mixed commitment scenario):
  HARD_LOCK / PLANTED   : x(plot, original_crop) = 1, immutable.
  SOFT_LOCK / CONFIRMED : crop may change; deviating from the committed crop is DISRUPTION.
  FLEXIBLE / VIEWED      : crop may change freely; deviations counted as churn, NOT penalised.
  REJECTED_TERMINAL      : the rejected crop is excluded; another feasible crop may be a
                           NEW/REVISED OFFER (recovery), or the plot stays fallow.

Stability objective (normalised so lambda is interpretable; raw rupees never dominate):

    maximise   E / E*   −   lambda · ( disruption_area / soft_lock_area )

  E              = total cash net return of the revised plan (incl. fixed hard-lock cash)
  E*             = max attainable E under Phase-3 lock/rejection constraints (lambda=0, no
                   fairness floor) — the economic normaliser
  disruption_area= Σ over SOFT_LOCK plots of area·(1 − x[plot, committed_crop])
                   (a soft-lock plot deviating from its committed crop OR going fallow)
  soft_lock_area = total area of soft-lock plots (penalty denominator; 0 ⇒ no penalty term)

Flexible deviations are reported as churn but excluded from the penalty (they carry no
commitment). lambda is thus the economic fraction one would forgo to avoid full soft-lock
disruption.

Fairness carry-in: the B3 fairness floor is carried in as a CONSTRAINT — per capable
farmer, normalised return (cash / total area) ≥ t_floor, where t_floor is RECOMPUTED
under Phase-3 constraints (the min-normalised return attainable at the canonical ε=0.95),
not blindly forced to the baseline B3 value which may be infeasible under locks.
"""

from __future__ import annotations
import time
import pulp

from ..feasibility import FeasibilityConfig
from ..solver import cbc_solver
from ..ilp_reference import _eligible
from ..baselines import Allocation, B1Result, _b1_metrics
from ..ingest import operational as opdata
from ..config import CANONICAL_B3_EPSILON, FORMULATION_VERSION, FAIRNESS_FLOOR_NUMERIC_TOL
from .commitment import LOCK_HARD, LOCK_SOFT, LOCK_FLEXIBLE


def _phase3_options(farmers, plots, crops, scenario, config):
    """Per-plot eligible (crop, cash, a2fl, labour, area) under Phase-3 lock/rejection
    rules. Only plots in the B3 plan (present in `scenario`) are decision plots."""
    farmer_by_id = {f.farmer_id: f for f in farmers}
    crop_by_name = {c.crop_name: c for c in crops}
    elig = _eligible(plots, farmer_by_id, crop_by_name, config)   # feasible cash-positive
    plot_by_id = {p.plot_id: p for p in plots}
    opts = {}
    for (fid, pid), info in scenario.items():
        lock, orig = info["lock"], info["crop"]
        avail = elig.get(pid, [])
        if lock == LOCK_HARD:
            opts[pid] = [o for o in avail if o[0] == orig]            # fixed to committed crop
        elif lock == "REJECTED_TERMINAL":
            opts[pid] = [o for o in avail if o[0] != orig]            # exclude rejected crop
        else:                                                        # SOFT / FLEXIBLE
            opts[pid] = list(avail)
    return opts, plot_by_id


def _solver(seconds=120):
    return cbc_solver(time_limit=seconds)


def _build(farmers, plots, crops, scenario, config):
    opts, plot_by_id = _phase3_options(farmers, plots, crops, scenario, config)
    total_area = sum(p.area_ha for p in plots)
    cap = {c.crop_name: ((opdata.op_absorption(c.crop_name) or 1.0) if opdata.is_loaded() else 1.0)
           * total_area for c in crops}
    x, cash_terms = {}, []
    fb = {f.farmer_id: [] for f in farmers}; fl = {f.farmer_id: [] for f in farmers}
    fcash = {f.farmer_id: [] for f in farmers}
    ca = {c.crop_name: [] for c in crops}; pt = {}
    keep_orig = {}           # x[plot, committed_crop] for soft/flex/hard
    owner = {pid: fid for (fid, pid) in scenario}
    for pid, lst in opts.items():
        for (name, cash, a2fl, labour, area) in lst:
            v = pulp.LpVariable(f"x_{pid}_{name}", cat="Binary"); x[(pid, name)] = v
            cash_terms.append(cash*v); fb[owner[pid]].append(a2fl*v); fl[owner[pid]].append(labour*v)
            fcash[owner[pid]].append(cash*v); ca[name].append(area*v); pt.setdefault(pid, []).append(v)
            if name == scenario[(owner[pid], pid)]["crop"]:
                keep_orig[pid] = v
    return dict(x=x, cash_terms=cash_terms, fb=fb, fl=fl, fcash=fcash, ca=ca, pt=pt,
                cap=cap, keep_orig=keep_orig, opts=opts, plot_by_id=plot_by_id, owner=owner)


def _add_constraints(prob, m, farmers, scenario):
    for f in farmers:
        if m["fb"][f.farmer_id]:
            prob += pulp.lpSum(m["fb"][f.farmer_id]) <= f.cultivation_budget
            prob += pulp.lpSum(m["fl"][f.farmer_id]) <= f.labour_capacity
    for cn, terms in m["ca"].items():
        if terms:
            prob += pulp.lpSum(terms) <= m["cap"][cn]
    for pid, vs in m["pt"].items():
        info = scenario[(m["owner"][pid], pid)]
        if info["lock"] == LOCK_HARD:
            prob += pulp.lpSum(vs) == 1                 # hard lock: must plant committed crop
        else:
            prob += pulp.lpSum(vs) <= 1


def _disruption_terms(m, scenario):
    """Σ soft-lock area·(1 − keep_orig).  Returns (expr, soft_area, flex_expr, flex_area)."""
    soft, soft_area, flex, flex_area = [], 0.0, [], 0.0
    for (fid, pid), info in scenario.items():
        if pid not in m["pt"]:
            continue
        area = m["plot_by_id"][pid].area_ha
        keep = m["keep_orig"].get(pid)
        dev = (1 - keep) if keep is not None else 1     # if committed crop unavailable, always deviated
        if info["lock"] == LOCK_SOFT:
            soft.append(area*dev); soft_area += area
        elif info["lock"] == LOCK_FLEXIBLE:
            flex.append(area*dev); flex_area += area
    return pulp.lpSum(soft), soft_area, pulp.lpSum(flex), flex_area


def _extract(m, farmers, plots, scenario, status, runtime, lam, e_star, t_floor):
    from ..planning import projected_return
    chosen = [(pid, name) for (pid, name), v in m["x"].items() if v.value() and v.value() > 0.5]
    r = B1Result()
    changed_soft = changed_flex = rejected_recovered = 0
    changed_soft_area = changed_flex_area = rejected_recovered_area = 0.0
    crop_change = {}
    for pid, name in chosen:
        p = m["plot_by_id"][pid]; pr = projected_return(name, p.region_id, p.active_season.value, p.area_ha)
        r.allocations.append(Allocation(p.farmer_id, pid, name, p.area_ha, pr["net_return"],
                                        pr["cost"], pr["labour_pd"], pr["cash_cost"], pr["cash_net_return"]))
        info = scenario[(p.farmer_id, pid)]; orig = info["crop"]
        if info["lock"] == LOCK_SOFT and name != orig:
            changed_soft += 1; changed_soft_area += p.area_ha; crop_change[(orig, name)] = crop_change.get((orig, name), 0)+1
        elif info["lock"] == LOCK_FLEXIBLE and name != orig:
            changed_flex += 1; changed_flex_area += p.area_ha; crop_change[(orig, name)] = crop_change.get((orig, name), 0)+1
        elif info["lock"] == "REJECTED_TERMINAL":
            rejected_recovered += 1; rejected_recovered_area += p.area_ha
    assigned = {pid for pid, _ in chosen}
    r.total_return = round(sum(a.net_return for a in r.allocations), 0)
    r.metrics = _b1_metrics(r, farmers, plots)
    # hard-lock verification: every hard-lock plot keeps its committed crop
    hard_ok = all((pid in assigned) and any(nm == scenario[(m["owner"][pid], pid)]["crop"]
                  for (pp, nm) in chosen if pp == pid)
                  for (fid, pid), info in scenario.items() if info["lock"] == LOCK_HARD)
    r.phase3 = {
        "lambda": lam, "status": status, "runtime_s": round(runtime, 2),
        "formulation_version": FORMULATION_VERSION, "e_star": e_star, "t_floor": t_floor,
        "changed_soft": changed_soft, "changed_soft_area": round(changed_soft_area, 1),
        "changed_flex": changed_flex, "changed_flex_area": round(changed_flex_area, 1),
        "rejected_recovered": rejected_recovered, "rejected_recovered_area": round(rejected_recovered_area, 1),
        "hard_lock_changes": 0 if hard_ok else -1, "hard_lock_ok": hard_ok,
        "crop_change_counts": {f"{a}->{b}": n for (a, b), n in sorted(crop_change.items())},
    }
    return r


def max_economic(farmers, plots, crops, scenario, config=None):
    """E* = max total cash under Phase-3 lock/rejection constraints (no fairness floor)."""
    config = config or FeasibilityConfig()
    m = _build(farmers, plots, crops, scenario, config)
    prob = pulp.LpProblem("p3_estar", pulp.LpMaximize)
    prob += pulp.lpSum(m["cash_terms"])
    _add_constraints(prob, m, farmers, scenario)
    prob.solve(_solver())
    return round(pulp.value(prob.objective) or 0.0, 0), pulp.LpStatus[prob.status]


def fairness_floor(farmers, plots, crops, scenario, e_star, epsilon=None, config=None):
    """t_floor = min normalised return attainable under Phase-3 constraints at epsilon."""
    config = config or FeasibilityConfig()
    epsilon = CANONICAL_B3_EPSILON if epsilon is None else epsilon
    m = _build(farmers, plots, crops, scenario, config)
    prob = pulp.LpProblem("p3_floor", pulp.LpMaximize)
    t = pulp.LpVariable("t", lowBound=0); prob += t
    _add_constraints(prob, m, farmers, scenario)
    prob += pulp.lpSum(m["cash_terms"]) >= epsilon * e_star
    fmap = {f.farmer_id: f for f in farmers}
    for fid, terms in m["fcash"].items():
        if terms:
            prob += pulp.lpSum(terms) >= t * fmap[fid].total_area_ha
    prob.solve(_solver())
    return (pulp.value(t) or 0.0), pulp.LpStatus[prob.status]      # full precision (do not round up)


def solve_phase3(farmers, plots, crops, scenario, lam, e_star, t_floor,
                 fairness=True, config=None, epsilon=None, floor_tol=None):
    """Maximise E/E* − lam·(disruption/soft_area) s.t. the FULL B3 ε-structure
    (E ≥ ε·E* AND per-capable-farmer normalised return ≥ t_floor) + all constraints."""
    config = config or FeasibilityConfig()
    epsilon = CANONICAL_B3_EPSILON if epsilon is None else epsilon
    floor_tol = FAIRNESS_FLOOR_NUMERIC_TOL if floor_tol is None else floor_tol
    m = _build(farmers, plots, crops, scenario, config)
    prob = pulp.LpProblem("p3", pulp.LpMaximize)
    disr, soft_area, flex, flex_area = _disruption_terms(m, scenario)
    econ = pulp.lpSum(m["cash_terms"])
    if soft_area > 0:
        prob += (1.0/e_star)*econ - (lam/soft_area)*disr
    else:
        prob += (1.0/e_star)*econ
    _add_constraints(prob, m, farmers, scenario)
    floor_applied = t_floor * (1.0 - floor_tol)
    if fairness and t_floor > 0:
        prob += econ >= epsilon * e_star                      # (i) B3 total-efficiency floor
        fmap = {f.farmer_id: f for f in farmers}
        for fid, terms in m["fcash"].items():
            if terms:
                prob += pulp.lpSum(terms) >= floor_applied * fmap[fid].total_area_ha  # (ii) min-norm floor
    t0 = time.time(); prob.solve(_solver()); rt = time.time()-t0
    r = _extract(m, farmers, plots, scenario, pulp.LpStatus[prob.status], rt, lam, e_star, t_floor)
    r.phase3["soft_lock_area"] = round(soft_area, 1)
    r.phase3["flex_area"] = round(flex_area, 1)
    r.phase3["objective_formula"] = "E/E* - lambda*(soft_disruption_area/soft_lock_area)"
    r.phase3["fairness_floor_applied"] = bool(fairness and t_floor > 0)
    r.phase3["fairness_structure"] = "BOTH: E>=eps*E* AND min_norm>=t_floor" if fairness else "none"
    r.phase3["epsilon"] = epsilon
    r.phase3["fairness_floor_tolerance"] = floor_tol
    r.phase3["fairness_floor_value"] = round(floor_applied, 4)
    return r
    return r
