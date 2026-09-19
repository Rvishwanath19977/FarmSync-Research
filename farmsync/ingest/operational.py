"""
Operational data layer — serves the FINAL, ingested state-level parameters to the
optimiser (spec items 16, 19). Loads processed tables produced by run_ingest.

Cost-basis policy (documented):
  * return_cost  = C2 (single primary, consistent cross-crop)
  * budget_cost  = A2+FL (operational/cash requirement)
  * sensitivity  = A2+FL vs C2 (both retained)

Fallbacks are explicit and labelled: DES/NHB national yield only where a state
value is unavailable. No cost/price fallback across states — a missing cost or a
sparse price means the crop×region is NOT admitted to the final gate.
"""

from __future__ import annotations

import os
import pandas as pd

from .commodity_map import CROP_PRIMARY_SEASON

# national yield fallback (kg/ha) from earlier DES/NHB sourcing, labelled ALL_INDIA.
from ..crop_yield import CROP_YIELD as _NATIONAL_YIELD

_DATA = {"loaded": False, "yield": {}, "price": {}, "cost": {}, "labour": {},
         "absorption": {}, "sparse": set(), "primary_year": "2022-23"}


def load(processed_dir: str):
    """Load processed ingested tables into region-keyed lookups."""
    yld = pd.read_csv(os.path.join(processed_dir, "yield_state.csv"))
    cost = pd.read_csv(os.path.join(processed_dir, "cost_state.csv"))
    price = pd.read_csv(os.path.join(processed_dir, "market_price_state.csv"))
    absorp = pd.read_csv(os.path.join(processed_dir, "absorption_proxy.csv"))

    # yield: prefer primary year, keep both
    yv = {}
    for _, r in yld.iterrows():
        yv.setdefault((r["region_id"], r["crop"]), {})[r["year"]] = r["yield_kg_ha"]
    _DATA["yield"] = yv

    pv, sparse = {}, set()
    for _, r in price.iterrows():
        pv[(r["region_id"], r["crop"])] = {"price_per_kg": r["price_rs_per_kg"],
                                           "coverage": r["coverage_pct"],
                                           "commodity": r["agmarknet_commodity"]}
        if bool(r["sparse_flag"]):
            sparse.add((r["region_id"], r["crop"]))
    _DATA["price"] = pv
    _DATA["sparse"] = sparse

    cv, lv = {}, {}
    for _, r in cost.iterrows():
        cv[(r["region_id"], r["crop"])] = {"c2": r["cost_c2_per_ha"], "a2fl": r["cost_a2fl_per_ha"]}
        if pd.notna(r["labour_person_days_ha"]):
            lv[(r["region_id"], r["crop"])] = r["labour_person_days_ha"]
    _DATA["cost"] = cv
    _DATA["labour"] = lv
    _DATA["absorption"] = {r["crop"]: r["absorption_proxy"] for _, r in absorp.iterrows()}
    _DATA["loaded"] = True
    return _DATA


def is_loaded():
    return _DATA["loaded"]


def op_yield(region_id, crop):
    """(value_kg_ha, scope). State primary year, else state alt year, else national."""
    y = _DATA["yield"].get((region_id, crop))
    if y:
        py = _DATA["primary_year"]
        if py in y:
            return y[py], f"STATE:{region_id}:{py}"
        k = sorted(y)[-1]
        return y[k], f"STATE:{region_id}:{k}"
    nat = _NATIONAL_YIELD.get(crop)
    if nat:
        season = CROP_PRIMARY_SEASON[crop]
        v = nat.yield_for(season) or nat.yield_for("kharif") or nat.yield_for("rabi")
        if v is not None:
            return v, "ALL_INDIA_FALLBACK"
    return None, None


def op_price(region_id, crop):
    """(price_rs_kg, basis). None if missing or sparse (excluded from final).
    uncertainty-v1: a scoped price multiplier keyed (region_id, crop) is applied at read time to the
    AGMARKNET operational price. NO MSP floor (MSP is a reference only). Baseline is never mutated."""
    p = _DATA["price"].get((region_id, crop))
    if not p:
        return None, None
    if (region_id, crop) in _DATA["sparse"]:
        return None, f"SPARSE({p['coverage']}%)"      # not admitted for final
    m = _PRICE_MULT.get((region_id, crop), 1.0)
    price = p["price_per_kg"] * m
    if price < 0:
        price = 0.0                                    # non-negativity only
    return price, f"AGMARKNET_MARKET({p['commodity']})"


def op_cost(region_id, crop, basis="C2"):
    """(cost_per_ha, basis_label). basis in {C2, A2FL}."""
    c = _DATA["cost"].get((region_id, crop))
    if not c:
        return None, None
    val = c["c2"] if basis == "C2" else c["a2fl"]
    if val is None or pd.isna(val):
        return None, None
    return round(float(val), 0), f"DES_CoC_{basis}"


def op_labour(region_id, crop):
    return _DATA["labour"].get((region_id, crop))


def op_absorption(crop):
    """Global crop-level absorption cap. uncertainty-v1: a scoped crop-GLOBAL absorption multiplier
    is applied at read time (keyed by crop only, never region). Baseline is never mutated."""
    base = _DATA["absorption"].get(crop)
    if base is None:
        return None
    m = _ABS_MULT.get(crop, 1.0)
    val = base * m
    return val if val >= 0 else 0.0                     # non-negativity


# --- scoped market override for uncertainty-v1 -------------------------------------------------
# Read-time multipliers: price keyed (region_id, crop); absorption keyed crop (GLOBAL). Default empty
# => 1.0. Baseline _DATA is never mutated; cleared by the uncertainty context (try/finally).
_PRICE_MULT = {}
_ABS_MULT = {}


def set_market_mult(price_mult_by_region_crop, absorption_mult_by_crop):
    _PRICE_MULT.clear(); _PRICE_MULT.update(price_mult_by_region_crop)
    _ABS_MULT.clear(); _ABS_MULT.update(absorption_mult_by_crop)


def clear_market_mult():
    _PRICE_MULT.clear(); _ABS_MULT.clear()
