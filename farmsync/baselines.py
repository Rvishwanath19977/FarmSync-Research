"""
B1 — Independent Farmer Planning (baseline).

Each farmer independently maximises their OWN projected net return across their own
plots, subject to their OWN budget and labour, ignoring all other farmers, collective
supply, market alignment, fairness, and production concentration (spec B1).

Deterministic. Uses only ADMITTED crops and grounded return inputs. After solving,
hard constraints (feasibility, farmer budget, farmer labour) are independently
re-verified (spec §28: verify hard constraints after every optimisation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .feasibility import assess_plot_crop, FeasibilityConfig
from .planning import projected_return, is_admitted, ADMITTED_CROPS
from .crop_agronomy import labour_pd_ha
from .crop_yield import resolve_yield
from .crop_economics import CROP_PRICE


@dataclass
class Allocation:
    farmer_id: str
    plot_id: str
    crop: str
    area_ha: float
    net_return: float
    cost: float                 # C2 economic cost (return accounting)
    labour_pd: float
    budget_cost: float = 0.0    # A2+FL cash cost (budget constraint)
    cash_net: float = 0.0       # CANONICAL cash net return = round(revenue − A2+FL), single-rounded


@dataclass
class B1Result:
    allocations: list = field(default_factory=list)
    fallow_plots: list = field(default_factory=list)
    total_return: float = 0.0
    metrics: dict = field(default_factory=dict)


def _plot_cost(crop, region_id, season, area):
    pr = CROP_PRICE[crop]
    y = resolve_yield(crop, season, region_id)["value"]
    return pr.cost_per_quintal * (y / 100.0) * area


def run_b1(farmers, plots, crops, config=None) -> B1Result:
    config = config or FeasibilityConfig()
    crop_by_name = {c.crop_name: c for c in crops}
    plots_by_farmer = {}
    for p in plots:
        plots_by_farmer.setdefault(p.farmer_id, []).append(p)

    result = B1Result()
    for farmer in farmers:
        fplots = plots_by_farmer.get(farmer.farmer_id, [])
        # best feasible admitted crop per plot (by net return)
        candidates = []
        for plot in fplots:
            season = plot.active_season.value
            best = None
            for name, crop in crop_by_name.items():
                if season not in crop.seasons:
                    continue
                ok, _ = is_admitted(name, plot.region_id, season)
                if not ok:
                    continue
                res = assess_plot_crop(plot, crop, farmer=farmer, config=config)
                if not res.feasible:
                    continue
                pr = projected_return(name, plot.region_id, season, plot.area_ha)
                if best is None or pr["cash_net_return"] > best["cash_net_return"]:
                    best = pr | {"plot_id": plot.plot_id,
                                 "budget_cost": pr["cash_cost"]}
            if best:
                candidates.append(best)

        # farmer maximises CASH net return (revenue − A2+FL); plants if cash-positive.
        # C2 economic net return is retained for reporting/comparison.
        candidates.sort(key=lambda c: c["cash_net_return"], reverse=True)
        budget_left = farmer.cultivation_budget
        labour_left = farmer.labour_capacity
        assigned_plots = set()
        for c in candidates:
            bc = c["budget_cost"]
            if c["cash_net_return"] > 0 and bc <= budget_left and c["labour_pd"] <= labour_left:
                result.allocations.append(Allocation(
                    farmer.farmer_id, c["plot_id"], c["crop"], c["area_ha"],
                    c["net_return"], c["cost"], c["labour_pd"], bc, c["cash_net_return"]))
                budget_left -= bc
                labour_left -= c["labour_pd"]
                assigned_plots.add(c["plot_id"])
        for plot in fplots:
            if plot.plot_id not in assigned_plots:
                result.fallow_plots.append(plot.plot_id)

    result.total_return = round(sum(a.net_return for a in result.allocations), 0)
    result.metrics = _b1_metrics(result, farmers, plots)
    return result


def _b1_metrics(result, farmers, plots) -> dict:
    n_farmers = len(farmers)
    farmer_return = {}
    for a in result.allocations:
        farmer_return[a.farmer_id] = farmer_return.get(a.farmer_id, 0.0) + a.cash_net
    returns = sorted(farmer_return.values())
    crop_area = {}
    for a in result.allocations:
        crop_area[a.crop] = crop_area.get(a.crop, 0.0) + a.area_ha
    total_area = sum(p.area_ha for p in plots)
    planted_area = sum(a.area_ha for a in result.allocations)
    med = returns[len(returns)//2] if returns else 0.0
    # Gini coefficient of farmer returns (equity metric)
    def _gini(xs):
        xs = sorted(x for x in xs if x is not None)
        n = len(xs)
        if n == 0 or sum(xs) == 0:
            return 0.0
        cum = sum((i+1)*v for i, v in enumerate(xs))
        return round((2*cum)/(n*sum(xs)) - (n+1)/n, 3)
    total_cash = sum(a.cash_net for a in result.allocations)
    return {
        "total_return": result.total_return,             # C2 economic net return
        "total_cash_return": round(total_cash, 0),       # A2+FL cash net return (B1 objective)
        "gini_farmer_return": _gini(returns),
        "mean_farmer_return": round(sum(returns)/n_farmers, 0) if n_farmers else 0,
        "median_farmer_return": round(med, 0),
        "min_farmer_return": round(min(returns), 0) if returns else 0,
        "plots_allocated": len(result.allocations),
        "plots_fallow": len(result.fallow_plots),
        "land_utilisation_pct": round(100*planted_area/total_area, 1) if total_area else 0,
        "crop_diversity": len(crop_area),
        "crop_area_ha": {k: round(v, 1) for k, v in sorted(crop_area.items(), key=lambda x: -x[1])},
    }


def verify_hard_constraints(result, farmers, plots, crops, config=None) -> dict:
    """Independently re-verify feasibility + farmer budget/labour after solving (spec §28)."""
    config = config or FeasibilityConfig()
    crop_by_name = {c.crop_name: c for c in crops}
    plot_by_id = {p.plot_id: p for p in plots}
    farmer_by_id = {f.farmer_id: f for f in farmers}
    violations = []
    # feasibility of each allocation
    for a in result.allocations:
        plot = plot_by_id[a.plot_id]
        res = assess_plot_crop(plot, crop_by_name[a.crop],
                               farmer=farmer_by_id[a.farmer_id], config=config)
        if not res.feasible:
            violations.append({"plot": a.plot_id, "crop": a.crop, "reasons": res.reasons})
    # farmer aggregate budget + labour
    by_farmer = {}
    for a in result.allocations:
        d = by_farmer.setdefault(a.farmer_id, {"cost": 0.0, "labour": 0.0})
        d["cost"] += a.budget_cost or a.cost      # A2+FL cash basis for the budget constraint
        d["labour"] += a.labour_pd
    for fid, tot in by_farmer.items():
        f = farmer_by_id[fid]
        if tot["cost"] > f.cultivation_budget + 1:
            violations.append({"farmer": fid, "budget_exceeded": round(tot["cost"] - f.cultivation_budget)})
        if tot["labour"] > f.labour_capacity + 1:
            violations.append({"farmer": fid, "labour_exceeded": round(tot["labour"] - f.labour_capacity)})
    return {"violations": violations, "hard_constraints_satisfied": len(violations) == 0}


# =========================================================================== #
# B2 — Centralised, market-aware profit maximisation
# =========================================================================== #
# A central planner maximises TOTAL collective cash net return across all plots,
# subject to the same hard constraints as B1 (feasibility, per-farmer A2+FL budget,
# labour) PLUS a collective market-absorption cap per crop: total planted area of a
# crop may not exceed absorption_proxy[crop] × total cultivable area. This prevents
# the collective from oversupplying low-throughput crops (which in reality collapses
# price) and is the key coordination B1 lacks. Greedy heuristic (fast, deterministic).

ABSORPTION_CAP_SCALE = 1.0     # documented scenario parameter (cap = proxy × total area × scale)


def run_b2(farmers, plots, crops, config=None) -> B1Result:
    from .ingest import operational as opdata
    config = config or FeasibilityConfig()
    crop_by_name = {c.crop_name: c for c in crops}
    farmer_by_id = {f.farmer_id: f for f in farmers}
    plots_by_farmer = {}
    for p in plots:
        plots_by_farmer.setdefault(p.farmer_id, []).append(p)

    total_area = sum(p.area_ha for p in plots)
    # per-crop area cap from the market-absorption proxy
    cap = {}
    for c in crops:
        ap = (opdata.op_absorption(c.crop_name) if opdata.is_loaded() else None)
        cap[c.crop_name] = (ap if ap is not None else 1.0) * total_area * ABSORPTION_CAP_SCALE

    # build all feasible (plot, crop) candidates with cash return
    candidates = []
    for p in plots:
        season = p.active_season.value
        fmr = farmer_by_id[p.farmer_id]
        for name, crop in crop_by_name.items():
            if season not in crop.seasons:
                continue
            ok, _ = is_admitted(name, p.region_id, season)
            if not ok:
                continue
            res = assess_plot_crop(p, crop, farmer=fmr, config=config)
            if not res.feasible:
                continue
            pr = projected_return(name, p.region_id, season, p.area_ha)
            if pr["cash_net_return"] > 0:
                candidates.append(pr | {"plot_id": p.plot_id, "farmer_id": p.farmer_id,
                                        "budget_cost": pr["cash_cost"]})

    # global greedy by cash return, respecting caps + per-farmer resources
    candidates.sort(key=lambda c: c["cash_net_return"], reverse=True)
    budget_left = {f.farmer_id: f.cultivation_budget for f in farmers}
    labour_left = {f.farmer_id: f.labour_capacity for f in farmers}
    cap_left = dict(cap)
    assigned = set()
    result = B1Result()
    for c in candidates:
        if c["plot_id"] in assigned:
            continue
        if c["area_ha"] > cap_left.get(c["crop"], 0):
            continue
        if c["budget_cost"] > budget_left[c["farmer_id"]] or c["labour_pd"] > labour_left[c["farmer_id"]]:
            continue
        result.allocations.append(Allocation(
            c["farmer_id"], c["plot_id"], c["crop"], c["area_ha"],
            c["net_return"], c["cost"], c["labour_pd"], c["budget_cost"], c["cash_net_return"]))
        assigned.add(c["plot_id"])
        cap_left[c["crop"]] -= c["area_ha"]
        budget_left[c["farmer_id"]] -= c["budget_cost"]
        labour_left[c["farmer_id"]] -= c["labour_pd"]
    result.fallow_plots = [p.plot_id for p in plots if p.plot_id not in assigned]
    result.total_return = round(sum(a.net_return for a in result.allocations), 0)
    result.metrics = _b1_metrics(result, farmers, plots)
    result.metrics["market_cap_binding_crops"] = sorted(
        [k for k, v in cap_left.items() if v < 0.01 and cap[k] > 0])
    return result


# =========================================================================== #
# B3 — Static fairness-aware allocation
# =========================================================================== #
# Centralised like B2 (feasibility + per-farmer budget/labour + market-absorption
# cap), but the allocation ORDER is fairness-weighted: at each step the worst-off
# farmer (lowest cumulative return so far) is served first, raising the minimum
# return and lowering inequality (Gini) at some cost to total return. Static =
# solved once, no farmer interaction/reoptimisation (that is the Proposed model).

def run_b3(farmers, plots, crops, config=None) -> B1Result:
    from .ingest import operational as opdata
    config = config or FeasibilityConfig()
    crop_by_name = {c.crop_name: c for c in crops}
    farmer_by_id = {f.farmer_id: f for f in farmers}

    total_area = sum(p.area_ha for p in plots)
    cap_left = {}
    for c in crops:
        ap = (opdata.op_absorption(c.crop_name) if opdata.is_loaded() else None)
        cap_left[c.crop_name] = (ap if ap is not None else 1.0) * total_area * ABSORPTION_CAP_SCALE

    # feasible candidates per plot, best cash first
    per_plot = {}
    for p in plots:
        season = p.active_season.value
        fmr = farmer_by_id[p.farmer_id]
        opts = []
        for name, crop in crop_by_name.items():
            if season not in crop.seasons:
                continue
            ok, _ = is_admitted(name, p.region_id, season)
            if not ok:
                continue
            if not assess_plot_crop(p, crop, farmer=fmr, config=config).feasible:
                continue
            pr = projected_return(name, p.region_id, season, p.area_ha)
            if pr["cash_net_return"] > 0:
                opts.append(pr | {"plot_id": p.plot_id, "farmer_id": p.farmer_id,
                                  "budget_cost": pr["cash_cost"]})
        opts.sort(key=lambda c: c["cash_net_return"], reverse=True)
        if opts:
            per_plot[p.plot_id] = opts

    budget_left = {f.farmer_id: f.cultivation_budget for f in farmers}
    labour_left = {f.farmer_id: f.labour_capacity for f in farmers}
    farmer_return = {f.farmer_id: 0.0 for f in farmers}
    plots_by_farmer = {}
    for p in plots:
        plots_by_farmer.setdefault(p.farmer_id, []).append(p.plot_id)
    assigned = set()
    result = B1Result()

    # fairness-ordered rounds: repeatedly serve the worst-off farmer with an
    # unassigned feasible plot, giving them their best still-available option.
    progress = True
    while progress:
        progress = False
        order = sorted(farmer_return, key=lambda fid: farmer_return[fid])   # worst-off first
        for fid in order:
            for pid in plots_by_farmer.get(fid, []):
                if pid in assigned or pid not in per_plot:
                    continue
                for c in per_plot[pid]:
                    if c["area_ha"] <= cap_left.get(c["crop"], 0) \
                            and c["budget_cost"] <= budget_left[fid] \
                            and c["labour_pd"] <= labour_left[fid]:
                        result.allocations.append(Allocation(
                            fid, pid, c["crop"], c["area_ha"], c["net_return"],
                            c["cost"], c["labour_pd"], c["budget_cost"], c["cash_net_return"]))
                        assigned.add(pid)
                        cap_left[c["crop"]] -= c["area_ha"]
                        budget_left[fid] -= c["budget_cost"]
                        labour_left[fid] -= c["labour_pd"]
                        farmer_return[fid] += (c["cash_net_return"])
                        progress = True
                        break
                break   # one plot per farmer per round (round-robin fairness)
    result.fallow_plots = [p.plot_id for p in plots if p.plot_id not in assigned]
    result.total_return = round(sum(a.net_return for a in result.allocations), 0)
    result.metrics = _b1_metrics(result, farmers, plots)
    return result
