"""
Canonical fairness metrics (fairness-v2). One implementation, used by every model.

Primary metrics (per approved decision):
  * normalized fairness = farmer cash net return / farmer TOTAL operated area,
    over ALL farmers including zero-return/non-participating farmers;
  * normalized-return Gini over all farmers;
  * participation rate;
  * fixed B1-reference bottom-tail cohort outcomes;
  * farmer benefit/loss relative to B1.
Supporting metrics:
  * absolute-return Gini (all farmers);
  * participant-only per-ha Gini.
Efficiency (NOT fairness):
  * return per ALLOCATED hectare.

Cash net return = revenue − A2+FL, non-negative (only cash-positive plantings admitted).
Reconstructed from an Allocation as (net_return_C2 + cost_C2) − budget_cost_A2FL.
"""

from __future__ import annotations
import statistics as _st

FAIRNESS_IMPL_VERSION = "fairness-v2"


def gini(values):
    xs = sorted(v for v in values)
    n = len(xs)
    if n == 0 or sum(xs) == 0:
        return 0.0
    cum = sum((i + 1) * v for i, v in enumerate(xs))
    return round((2 * cum) / (n * sum(xs)) - (n + 1) / n, 4)


def farmer_cash(result):
    """{farmer_id: cash net return} over participating farmers (others implicitly 0).
    Uses the canonical single-rounded Allocation.cash_net so totals match the ILP
    objective exactly (no triple-rounding drift)."""
    d = {}
    for a in result.allocations:
        d[a.farmer_id] = d.get(a.farmer_id, 0.0) + a.cash_net
    return d


def bottom_cohorts(b1_cash, all_farmer_ids, sizes=(50, 125)):
    """Frozen B1-reference cohorts: farmer IDs with lowest B1 cash. Returns {size: set(ids)}."""
    order = sorted(all_farmer_ids, key=lambda fid: b1_cash.get(fid, 0.0))
    return {s: set(order[:s]) for s in sizes}


def fairness_report(result, farmers, b1_reference=None, cohorts=None, tol=1.0):
    """Full canonical metric set. b1_reference = farmer_cash(B1) for benefit/loss +
    cohorts; if None, benefit/loss and cohort blocks are omitted."""
    area = {f.farmer_id: f.total_area_ha for f in farmers}
    allf = [f.farmer_id for f in farmers]
    cash = farmer_cash(result)
    per_ha_all = [cash.get(fid, 0.0) / area[fid] for fid in allf]
    per_ha_part = [cash[fid] / area[fid] for fid in cash]
    alloc_area = sum(a.area_ha for a in result.allocations)

    rep = {
        "impl_version": FAIRNESS_IMPL_VERSION,
        # PRIMARY
        "primary": {
            "per_ha_gini_all": gini(per_ha_all),          # /total area, all farmers
            "participation_rate_pct": round(100 * len(cash) / len(allf), 1),
            "n_participating": len(cash),
            "n_farmers": len(allf),
        },
        # SUPPORTING
        "supporting": {
            "abs_gini_all": gini([cash.get(fid, 0.0) for fid in allf]),
            "per_ha_gini_participants": gini(per_ha_part),
            "abs_gini_participant_only": gini([cash[fid] for fid in cash]),  # == old frozen basis
        },
        # EFFICIENCY (not fairness)
        "efficiency": {
            "return_per_allocated_ha": round(sum(cash.values()) / alloc_area, 1) if alloc_area else 0.0,
            "total_cash_return": round(sum(cash.values()), 0),
        },
        "denominators": {
            "per_ha_gini_all": "farmer cash / total operated area, all 500 incl zeros",
            "abs_gini_participant_only": "participating farmers only (== legacy frozen gini basis)",
        },
    }
    if b1_reference is not None:
        cohorts = cohorts or bottom_cohorts(b1_reference, allf)
        rep["primary"]["fixed_cohort_mean_cash"] = {
            f"bottom_{s}_B1ref": round(sum(cash.get(fid, 0.0) for fid in ids) / len(ids), 1)
            for s, ids in cohorts.items()}
        deltas = sorted(cash.get(fid, 0.0) - b1_reference.get(fid, 0.0) for fid in allf)
        better = sum(1 for x in deltas if x > tol)
        worse = sum(1 for x in deltas if x < -tol)
        rep["primary"]["benefit_loss_vs_b1"] = {
            "better": better, "worse": worse, "unchanged": len(deltas) - better - worse,
            "mean_delta": round(_st.mean(deltas)), "median_delta": round(_st.median(deltas)),
            "p10_delta": round(deltas[len(deltas)//10]), "p90_delta": round(deltas[9*len(deltas)//10]),
            "tolerance": tol,
        }
    return rep
