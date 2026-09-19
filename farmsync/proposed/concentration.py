"""
Proposed Phase 4 — production concentration / market resilience.

Measures and controls dependence on individual PRODUCERS within each crop
(pre-failure exposure). This is DISTINCT from the market-absorption cap (an
arrivals-derived throughput proxy, NOT demand, already in the backbone). Actual
producer failure / N-1 resilience is Phase 5 and is NOT implemented here.

Concentration is measured by FARMER within each crop using expected production:
    q_fc = expected_yield_kg_per_ha(crop, region) * allocated_area_ha
(expected yield from FarmSync's validated resolver `planning.op_yield_value`).

Concentration constraint (added on top of Phase-3 stability + full B3 fairness):
    q_fc <= alpha * Q_c      for every farmer f and active crop c
where Q_c = total expected production of crop c. alpha=1 imposes no extra restriction.

Hard locks (PLANTED) are absolute: never changed to satisfy alpha. If an alpha cannot
be met given hard locks / too few feasible producers, the solve is reported INFEASIBLE
honestly (no pseudo-solution, no silent weakening).

All outputs are REVISED PLANS / recommendations, never realised. LPS/HHI are pre-failure
EXPOSURE measures only — not demonstrated disaster resilience.
"""

from __future__ import annotations
import time
import pulp

from ..feasibility import FeasibilityConfig
from ..planning import op_yield_value
from ..config import CANONICAL_B3_EPSILON, FAIRNESS_FLOOR_NUMERIC_TOL
from .reoptimize import (_build, _add_constraints, _disruption_terms, _extract, _solver)
from .commitment import LOCK_HARD


# --------------------------------------------------------------------------- #
# expected-production coefficients
# --------------------------------------------------------------------------- #
def prod_coeffs(m, plots):
    """{(plot_id, crop): expected_yield_kg_ha * area_ha} for every decision variable."""
    pby = {p.plot_id: p for p in plots}
    q = {}
    for (pid, name) in m["x"]:
        p = pby[pid]
        y, _ = op_yield_value(name, p.region_id, p.active_season.value)
        q[(pid, name)] = (y or 0.0) * p.area_ha
    return q


def _add_concentration(prob, m, qcoef, alpha):
    """q_fc <= alpha * Q_c for each (farmer, crop) with an eligible plot."""
    if alpha >= 1.0:
        return
    # group variables by crop, and by (farmer, crop)
    by_crop, by_fc = {}, {}
    for (pid, name), v in m["x"].items():
        fid = m["owner"][pid]
        by_crop.setdefault(name, []).append(qcoef[(pid, name)] * v)
        by_fc.setdefault((fid, name), []).append(qcoef[(pid, name)] * v)
    for (fid, name), fterms in by_fc.items():
        Qc = pulp.lpSum(by_crop[name])
        prob += pulp.lpSum(fterms) <= alpha * Qc          # q_fc - alpha*Q_c <= 0 (linear)


def max_economic_alpha(farmers, plots, crops, scenario, alpha, config=None):
    config = config or FeasibilityConfig()
    m = _build(farmers, plots, crops, scenario, config)
    q = prod_coeffs(m, plots)
    prob = pulp.LpProblem("p4_estar", pulp.LpMaximize)
    prob += pulp.lpSum(m["cash_terms"])
    _add_constraints(prob, m, farmers, scenario)
    _add_concentration(prob, m, q, alpha)
    prob.solve(_solver())
    st = pulp.LpStatus[prob.status]
    return (round(pulp.value(prob.objective) or 0.0, 0) if st == "Optimal" else None), st


def fairness_floor_alpha(farmers, plots, crops, scenario, alpha, e_star_alpha,
                         epsilon=None, config=None):
    config = config or FeasibilityConfig()
    epsilon = CANONICAL_B3_EPSILON if epsilon is None else epsilon
    m = _build(farmers, plots, crops, scenario, config)
    q = prod_coeffs(m, plots)
    prob = pulp.LpProblem("p4_floor", pulp.LpMaximize)
    t = pulp.LpVariable("t", lowBound=0); prob += t
    _add_constraints(prob, m, farmers, scenario)
    _add_concentration(prob, m, q, alpha)
    prob += pulp.lpSum(m["cash_terms"]) >= epsilon * e_star_alpha
    fmap = {f.farmer_id: f for f in farmers}
    for fid, terms in m["fcash"].items():
        if terms:
            prob += pulp.lpSum(terms) >= t * fmap[fid].total_area_ha
    prob.solve(_solver())
    st = pulp.LpStatus[prob.status]
    return ((pulp.value(t) or 0.0) if st == "Optimal" else None), st


def solve_phase4(farmers, plots, crops, scenario, lam, alpha, e_star_alpha, t_floor_alpha,
                 epsilon=None, floor_tol=None, config=None):
    """Phase-3 stability objective + BOTH B3 fairness constraints + concentration cap.
    Returns a result with .phase3 (stability) and .phase4 (concentration/status) blocks,
    or a status-only dict if not Optimal (never extracts a pseudo-solution)."""
    config = config or FeasibilityConfig()
    epsilon = CANONICAL_B3_EPSILON if epsilon is None else epsilon
    floor_tol = FAIRNESS_FLOOR_NUMERIC_TOL if floor_tol is None else floor_tol
    m = _build(farmers, plots, crops, scenario, config)
    q = prod_coeffs(m, plots)
    prob = pulp.LpProblem("p4", pulp.LpMaximize)
    disr, soft_area, flex, flex_area = _disruption_terms(m, scenario)
    econ = pulp.lpSum(m["cash_terms"])
    prob += ((1.0/e_star_alpha)*econ - (lam/soft_area)*disr) if soft_area > 0 else (1.0/e_star_alpha)*econ
    _add_constraints(prob, m, farmers, scenario)
    _add_concentration(prob, m, q, alpha)
    floor_applied = t_floor_alpha * (1.0 - floor_tol)
    prob += econ >= epsilon * e_star_alpha
    fmap = {f.farmer_id: f for f in farmers}
    for fid, terms in m["fcash"].items():
        if terms:
            prob += pulp.lpSum(terms) >= floor_applied * fmap[fid].total_area_ha
    t0 = time.time(); prob.solve(_solver()); rt = time.time()-t0
    status = pulp.LpStatus[prob.status]
    if status != "Optimal":
        return {"status": status, "alpha": alpha, "lambda": lam, "runtime_s": round(rt, 2),
                "extracted": False}
    r = _extract(m, farmers, plots, scenario, status, rt, lam, e_star_alpha, t_floor_alpha)
    r.phase3["soft_lock_area"] = round(soft_area, 1); r.phase3["flex_area"] = round(flex_area, 1)
    r.phase3["fairness_structure"] = "BOTH: E>=eps*E*_alpha AND min_norm>=t_floor_alpha"
    r.phase3["epsilon"] = epsilon; r.phase3["fairness_floor_tolerance"] = floor_tol
    r.phase4 = {"alpha": alpha, "status": status, "e_star_alpha": e_star_alpha,
                "t_floor_alpha": round(t_floor_alpha, 4)}
    return r


# --------------------------------------------------------------------------- #
# concentration metrics + infeasibility diagnosis
# --------------------------------------------------------------------------- #
def concentration_metrics(result, plots, alpha=None):
    """Per-crop producer-concentration metrics from expected production (safe on zeros)."""
    pby = {p.plot_id: p for p in plots}
    per_crop = {}
    for a in result.allocations:
        p = pby[a.plot_id]
        y, _ = op_yield_value(a.crop, p.region_id, p.active_season.value)
        q = (y or 0.0) * a.area_ha
        per_crop.setdefault(a.crop, {}).setdefault(a.farmer_id, 0.0)
        per_crop[a.crop][a.farmer_id] += q
    out = {}
    max_lps = 0.0; hhis = []; violations = 0
    for crop, fmap in per_crop.items():
        Qc = sum(fmap.values())
        if Qc <= 0:
            out[crop] = {"Q_c": 0.0, "producers": len(fmap), "LPS": 0.0, "top3_share": 0.0,
                         "HHI": 0.0, "effective_producers": 0.0}
            continue
        shares = sorted((v / Qc for v in fmap.values()), reverse=True)
        hhi = sum(s * s for s in shares); lps = shares[0]; top3 = sum(shares[:3])
        out[crop] = {"Q_c": round(Qc, 1), "producers": len(fmap), "LPS": round(lps, 4),
                     "top3_share": round(top3, 4), "HHI": round(hhi, 4),
                     "effective_producers": round(1.0 / hhi, 2) if hhi > 0 else 0.0}
        max_lps = max(max_lps, lps); hhis.append(hhi)
        if alpha is not None and lps > alpha + 1e-6:
            violations += 1
    hhis_sorted = sorted(hhis)
    summary = {
        "active_crops": sorted(per_crop.keys()), "n_active_crops": len(per_crop),
        "max_LPS": round(max_lps, 4),
        "mean_HHI": round(sum(hhis) / len(hhis), 4) if hhis else 0.0,
        "median_HHI": round(hhis_sorted[len(hhis_sorted)//2], 4) if hhis_sorted else 0.0,
        "target_violations": violations,
    }
    return out, summary


def diagnose_infeasibility(farmers, plots, crops, scenario, alpha, config=None):
    """Best-effort honest diagnosis: crops where hard-locked production forces a single
    farmer's share above alpha, or crops with a single feasible producer."""
    config = config or FeasibilityConfig()
    m = _build(farmers, plots, crops, scenario, config)
    q = prod_coeffs(m, plots)
    # per-crop: total feasible Q (all eligible), and hard-locked production per farmer
    feas_Q = {}; hard_by_fc = {}; feasible_producers = {}
    for (pid, name), v in m["x"].items():
        fid = m["owner"][pid]
        feas_Q[name] = feas_Q.get(name, 0.0) + q[(pid, name)]
        feasible_producers.setdefault(name, set()).add(fid)
        if scenario[(fid, pid)]["lock"] == LOCK_HARD and scenario[(fid, pid)]["crop"] == name:
            hard_by_fc[(fid, name)] = hard_by_fc.get((fid, name), 0.0) + q[(pid, name)]
    causes = []
    for name, Qmax in feas_Q.items():
        if Qmax <= 0:
            continue
        # single feasible producer -> share 1 > alpha
        if len(feasible_producers.get(name, ())) <= 1 and alpha < 1.0:
            causes.append({"crop": name, "reason": "single feasible producer", "min_forced_LPS": 1.0})
            continue
        hard_farmers = {f for (f, c) in hard_by_fc if c == name}
        for hf in hard_farmers:
            forced = hard_by_fc[(hf, name)] / Qmax          # lower bound on this farmer's share
            if forced > alpha + 1e-9:
                causes.append({"crop": name, "reason": "hard-locked producer exceeds alpha",
                               "farmer": hf, "min_forced_LPS": round(forced, 4)})
    return causes
