"""
AUDIT TOOLING — exact ILP reference solvers to measure the greedy optimality gap.
Not part of the FarmSync model; does not modify baselines or frozen results.

B1-ILP: per-farmer multiple-choice knapsack.
  maximise  Σ_{p,c} cash_np[p,c] · x[p,c]
  s.t.      Σ_c x[p,c] ≤ 1                      (one crop per plot, or fallow)
            Σ_{p,c} a2fl[p,c] · x[p,c] ≤ budget_f
            Σ_{p,c} labour[p,c] · x[p,c] ≤ labour_f
            x ∈ {0,1}, only feasible & cash-positive (p,c) eligible

B2-ILP: centralised, same per-farmer budget/labour + global market-absorption caps
  add       Σ_{p∈crop c} area[p] · x[p,c] ≤ cap_c
"""

from __future__ import annotations

import pulp

from .feasibility import assess_plot_crop, FeasibilityConfig
from .solver import cbc_solver, cbc_threads
from .planning import is_admitted, projected_return
from .ingest import operational as opdata


def _eligible(plots, farmer_by_id, crop_by_name, config):
    """Return {plot_id: [(crop, cash_np, a2fl, labour, area)]} of feasible cash-positive options."""
    opts = {}
    for p in plots:
        season = p.active_season.value
        fmr = farmer_by_id[p.farmer_id]
        lst = []
        for name, crop in crop_by_name.items():
            if season not in crop.seasons:
                continue
            if not is_admitted(name, p.region_id, season)[0]:
                continue
            if not assess_plot_crop(p, crop, farmer=fmr, config=config).feasible:
                continue
            pr = projected_return(name, p.region_id, season, p.area_ha)
            if pr["cash_net_return"] > 0:
                lst.append((name, pr["cash_net_return"], pr["cash_cost"], pr["labour_pd"], p.area_ha))
        if lst:
            opts[p.plot_id] = lst
    return opts


def b1_ilp_total(farmers, plots, crops, config=None) -> dict:
    config = config or FeasibilityConfig()
    crop_by_name = {c.crop_name: c for c in crops}
    farmer_by_id = {f.farmer_id: f for f in farmers}
    plots_by_farmer = {}
    for p in plots:
        plots_by_farmer.setdefault(p.farmer_id, []).append(p)
    opts = _eligible(plots, farmer_by_id, crop_by_name, config)

    total = 0.0
    for f in farmers:
        prob = pulp.LpProblem("b1", pulp.LpMaximize)
        x = {}
        obj = []
        bud, lab = [], []
        plot_terms = {}
        for p in plots_by_farmer.get(f.farmer_id, []):
            for (name, cash, a2fl, labour, area) in opts.get(p.plot_id, []):
                v = pulp.LpVariable(f"x_{p.plot_id}_{name}", cat="Binary")
                x[(p.plot_id, name)] = v
                obj.append(cash * v); bud.append(a2fl * v); lab.append(labour * v)
                plot_terms.setdefault(p.plot_id, []).append(v)
        if not x:
            continue
        prob += pulp.lpSum(obj)
        prob += pulp.lpSum(bud) <= f.cultivation_budget
        prob += pulp.lpSum(lab) <= f.labour_capacity
        for pid, vs in plot_terms.items():
            prob += pulp.lpSum(vs) <= 1
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
        total += pulp.value(prob.objective) or 0.0
    return {"b1_ilp_cash_total": round(total, 0)}


def b2_ilp_total(farmers, plots, crops, config=None, cap_scale=1.0) -> dict:
    config = config or FeasibilityConfig()
    crop_by_name = {c.crop_name: c for c in crops}
    farmer_by_id = {f.farmer_id: f for f in farmers}
    opts = _eligible(plots, farmer_by_id, crop_by_name, config)
    total_area = sum(p.area_ha for p in plots)
    cap = {c.crop_name: ((opdata.op_absorption(c.crop_name) or 1.0) if opdata.is_loaded() else 1.0)
           * total_area * cap_scale for c in crops}

    prob = pulp.LpProblem("b2", pulp.LpMaximize)
    x = {}
    obj = []
    by_farmer_bud = {f.farmer_id: [] for f in farmers}
    by_farmer_lab = {f.farmer_id: [] for f in farmers}
    by_crop_area = {c.crop_name: [] for c in crops}
    plot_terms = {}
    plot_owner = {p.plot_id: p.farmer_id for p in plots}
    for pid, lst in opts.items():
        fid = plot_owner[pid]
        for (name, cash, a2fl, labour, area) in lst:
            v = pulp.LpVariable(f"x_{pid}_{name}", cat="Binary")
            x[(pid, name)] = v
            obj.append(cash * v)
            by_farmer_bud[fid].append(a2fl * v)
            by_farmer_lab[fid].append(labour * v)
            by_crop_area[name].append(area * v)
            plot_terms.setdefault(pid, []).append(v)
    prob += pulp.lpSum(obj)
    for f in farmers:
        if by_farmer_bud[f.farmer_id]:
            prob += pulp.lpSum(by_farmer_bud[f.farmer_id]) <= f.cultivation_budget
            prob += pulp.lpSum(by_farmer_lab[f.farmer_id]) <= f.labour_capacity
    for cn, terms in by_crop_area.items():
        if terms:
            prob += pulp.lpSum(terms) <= cap[cn]
    for pid, vs in plot_terms.items():
        prob += pulp.lpSum(vs) <= 1
    prob.solve(cbc_solver(time_limit=120))
    return {"b2_ilp_cash_total": round(pulp.value(prob.objective) or 0.0, 0),
            "status": pulp.LpStatus[prob.status]}


# --------------------------------------------------------------------------- #
# SHADOW B3 fairness ILP solvers (audit only; do not replace b3_final).
# Normalized outcome = farmer cash net return / farmer total area (holding-size
# invariant). "Capable" farmers = those with >=1 feasible cash-positive option;
# pure max-min over ALL farmers is degenerate (t pinned to 0 by structurally
# non-participating farmers), so max-min is taken over capable farmers and that
# restriction is reported explicitly.
# --------------------------------------------------------------------------- #

def _build_central(farmers, plots, crops, config, cap_scale=1.0):
    crop_by_name = {c.crop_name: c for c in crops}
    farmer_by_id = {f.farmer_id: f for f in farmers}
    opts = _eligible(plots, farmer_by_id, crop_by_name, config)
    total_area = sum(p.area_ha for p in plots)
    cap = {c.crop_name: ((opdata.op_absorption(c.crop_name) or 1.0) if opdata.is_loaded() else 1.0)
           * total_area * cap_scale for c in crops}
    plot_owner = {p.plot_id: p.farmer_id for p in plots}
    x, cash_terms = {}, []
    fb = {f.farmer_id: [] for f in farmers}; fl = {f.farmer_id: [] for f in farmers}
    fcash = {f.farmer_id: [] for f in farmers}
    ca = {c.crop_name: [] for c in crops}; pt = {}
    for pid, lst in opts.items():
        fid = plot_owner[pid]
        for (name, cash, a2fl, labour, area) in lst:
            v = pulp.LpVariable(f"x_{pid}_{name}", cat="Binary"); x[(pid, name)] = v
            cash_terms.append(cash*v); fb[fid].append(a2fl*v); fl[fid].append(labour*v)
            fcash[fid].append(cash*v); ca[name].append(area*v); pt.setdefault(pid, []).append(v)
    capable = [f for f in farmers if fcash[f.farmer_id]]
    return dict(x=x, cash_terms=cash_terms, fb=fb, fl=fl, fcash=fcash, ca=ca, pt=pt,
                cap=cap, capable=capable, farmer_by_id=farmer_by_id)


def _add_hard(prob, m, farmers):
    for f in farmers:
        if m["fb"][f.farmer_id]:
            prob += pulp.lpSum(m["fb"][f.farmer_id]) <= f.cultivation_budget
            prob += pulp.lpSum(m["fl"][f.farmer_id]) <= f.labour_capacity
    for cn, terms in m["ca"].items():
        if terms: prob += pulp.lpSum(terms) <= m["cap"][cn]
    for pid, vs in m["pt"].items():
        prob += pulp.lpSum(vs) <= 1


def _solve(prob, seconds=120):
    s = cbc_solver(time_limit=seconds)
    prob.solve(s)
    return pulp.LpStatus[prob.status]


def b3_maxmin_ilp(farmers, plots, crops, config=None, cap_scale=1.0):
    """maximise t s.t. per-capable-farmer normalized return (cash/area) >= t."""
    config = config or FeasibilityConfig()
    m = _build_central(farmers, plots, crops, config, cap_scale)
    prob = pulp.LpProblem("b3_maxmin", pulp.LpMaximize)
    t = pulp.LpVariable("t", lowBound=0)
    prob += t
    _add_hard(prob, m, farmers)
    for f in m["capable"]:
        A = m["farmer_by_id"][f.farmer_id].total_area_ha
        prob += pulp.lpSum(m["fcash"][f.farmer_id]) >= t * A
    status = _solve(prob)
    tot = sum(c.value() if hasattr(c, "value") else 0 for c in [])  # placeholder
    total_cash = round(pulp.value(pulp.lpSum(m["cash_terms"])) or 0.0, 0)
    return {"status": status, "min_normalized_return": round(pulp.value(t) or 0.0, 1),
            "total_cash": total_cash, "n_capable": len(m["capable"])}


def b3_epsilon_ilp(farmers, plots, crops, config=None, cap_scale=1.0, epsilon=None, tstar=None):
    if epsilon is None:
        epsilon = CANONICAL_B3_EPSILON
    """Stage 2 of epsilon-constraint: maximise min normalized return (capable) s.t.
    total cash >= epsilon * T*. T* (max total) must be supplied or computed first."""
    config = config or FeasibilityConfig()
    if tstar is None:
        tstar = b2_ilp_total(farmers, plots, crops, config, cap_scale)["b2_ilp_cash_total"]
    m = _build_central(farmers, plots, crops, config, cap_scale)
    prob = pulp.LpProblem("b3_eps", pulp.LpMaximize)
    t = pulp.LpVariable("t", lowBound=0)
    prob += t
    _add_hard(prob, m, farmers)
    prob += pulp.lpSum(m["cash_terms"]) >= epsilon * tstar
    for f in m["capable"]:
        A = m["farmer_by_id"][f.farmer_id].total_area_ha
        prob += pulp.lpSum(m["fcash"][f.farmer_id]) >= t * A
    status = _solve(prob)
    return {"status": status, "epsilon": epsilon, "tstar": tstar,
            "min_normalized_return": round(pulp.value(t) or 0.0, 1),
            "total_cash": round(pulp.value(pulp.lpSum(m["cash_terms"])) or 0.0, 0),
            "efficiency_retained_pct": round(100*(pulp.value(pulp.lpSum(m["cash_terms"])) or 0)/tstar, 1)}


# =========================================================================== #
# Allocation-returning ILP solvers (versioned baseline family). Reuse Allocation
# and B1Result so results pass verify_hard_constraints and fairness-v2 unchanged.
# =========================================================================== #
import time as _time
from .baselines import Allocation, B1Result, _b1_metrics
from .config import CANONICAL_B3_EPSILON, FORMULATION_VERSION


def _extract(chosen, plots, farmer_by_id):
    """chosen = list of (plot_id, crop_name). Build Allocation list via projected_return."""
    pby = {p.plot_id: p for p in plots}
    allocs = []
    for pid, name in chosen:
        p = pby[pid]; season = p.active_season.value
        pr = projected_return(name, p.region_id, season, p.area_ha)
        allocs.append(Allocation(p.farmer_id, pid, name, p.area_ha,
                                 pr["net_return"], pr["cost"], pr["labour_pd"], pr["cash_cost"],
                                 pr["cash_net_return"]))
    return allocs


def _result_from(allocs, farmers, plots, status, runtime):
    r = B1Result()
    r.allocations = allocs
    assigned = {a.plot_id for a in allocs}
    r.fallow_plots = [p.plot_id for p in plots if p.plot_id not in assigned]
    r.total_return = round(sum(a.net_return for a in allocs), 0)
    r.metrics = _b1_metrics(r, farmers, plots)
    r.solver = {"status": status, "runtime_s": round(runtime, 2),
                "pulp": pulp.__version__, "engine": "CBC", "cbc": "2.10.3",
                "gapRel": 1e-6, "threads": cbc_threads(), "timeLimit_s": 120}
    return r


def run_b1_ilp(farmers, plots, crops, config=None):
    config = config or FeasibilityConfig()
    crop_by_name = {c.crop_name: c for c in crops}
    farmer_by_id = {f.farmer_id: f for f in farmers}
    plots_by_farmer = {}
    for p in plots:
        plots_by_farmer.setdefault(p.farmer_id, []).append(p)
    opts = _eligible(plots, farmer_by_id, crop_by_name, config)
    t0 = _time.time(); chosen = []; statuses = set()
    for f in farmers:
        prob = pulp.LpProblem("b1", pulp.LpMaximize)
        x = {}; obj = []; bud = []; lab = []; pt = {}
        for p in plots_by_farmer.get(f.farmer_id, []):
            for (name, cash, a2fl, labour, area) in opts.get(p.plot_id, []):
                v = pulp.LpVariable(f"x_{p.plot_id}_{name}", cat="Binary")
                x[(p.plot_id, name)] = v; obj.append(cash*v); bud.append(a2fl*v); lab.append(labour*v)
                pt.setdefault(p.plot_id, []).append(v)
        if not x:
            continue
        prob += pulp.lpSum(obj)
        prob += pulp.lpSum(bud) <= f.cultivation_budget
        prob += pulp.lpSum(lab) <= f.labour_capacity
        for pid, vs in pt.items():
            prob += pulp.lpSum(vs) <= 1
        prob.solve(cbc_solver(time_limit=120))
        statuses.add(pulp.LpStatus[prob.status])
        for (pid, name), v in x.items():
            if v.value() and v.value() > 0.5:
                chosen.append((pid, name))
    status = "Optimal" if statuses <= {"Optimal"} else "/".join(sorted(statuses))
    return _result_from(_extract(chosen, plots, farmer_by_id), farmers, plots, status, _time.time()-t0)


def _central_solve(farmers, plots, crops, config, cap_scale, extra=None, objective=None):
    m = _build_central(farmers, plots, crops, config, cap_scale)
    prob = pulp.LpProblem("central", pulp.LpMaximize)
    aux = objective(prob, m) if objective else prob.__iadd__(pulp.lpSum(m["cash_terms"]))
    _add_hard(prob, m, farmers)
    if extra:
        extra(prob, m)
    t0 = _time.time()
    status = _solve(prob)
    runtime = _time.time() - t0
    chosen = [key for key, v in m["x"].items() if v.value() and v.value() > 0.5]
    return m, chosen, status, runtime, aux


def run_b2_ilp(farmers, plots, crops, config=None, cap_scale=1.0):
    config = config or FeasibilityConfig()
    farmer_by_id = {f.farmer_id: f for f in farmers}
    m, chosen, status, rt, _ = _central_solve(farmers, plots, crops, config, cap_scale)
    return _result_from(_extract(chosen, plots, farmer_by_id), farmers, plots, status, rt)


def run_b3_ilp(farmers, plots, crops, config=None, cap_scale=1.0, epsilon=None, tstar=None):
    if epsilon is None:
        epsilon = CANONICAL_B3_EPSILON
    config = config or FeasibilityConfig()
    farmer_by_id = {f.farmer_id: f for f in farmers}
    if tstar is None:
        tstar = b2_ilp_total(farmers, plots, crops, config, cap_scale)["b2_ilp_cash_total"]

    def obj(prob, m):
        t = pulp.LpVariable("t", lowBound=0); prob += t; return t
    def extra(prob, m):
        prob += pulp.lpSum(m["cash_terms"]) >= epsilon * tstar
        tvar = prob.variablesDict()["t"]
        for f in m["capable"]:
            A = m["farmer_by_id"][f.farmer_id].total_area_ha
            prob += pulp.lpSum(m["fcash"][f.farmer_id]) >= tvar * A
    m, chosen, status, rt, tvar = _central_solve(farmers, plots, crops, config, cap_scale, extra, obj)
    r = _result_from(_extract(chosen, plots, farmer_by_id), farmers, plots, status, rt)
    r.solver["epsilon"] = epsilon; r.solver["tstar"] = tstar
    r.solver["formulation_version"] = FORMULATION_VERSION
    r.solver["min_normalized_return"] = round(pulp.value(tvar) or 0.0, 1)
    return r
