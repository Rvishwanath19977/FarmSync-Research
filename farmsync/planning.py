"""
Planning inputs — the provenance/scientific-validity gate for optimisation.

Only crops whose REQUIRED optimisation fields are fully grounded may be ADMITTED
into B1/B2/B3/Proposed. Required fields: season-appropriate yield (state or national,
scope-labelled), a usable price (MSP policy-floor anchor, documented), a consistent
cultivation cost, and a defined crop-water requirement. No REQUIRES_SOURCING,
UNKNOWN, or unit-inconsistent value may enter a return calculation.

Excluded (documented): potato, onion, tomato — vegetables have no MSP price and
their AGMARKNET market prices are not yet sourced; onion/tomato also lack yield.
They are NOT admitted, so their open fields never enter the experiment.

Price basis: MSP floor is used as the price anchor, explicitly labelled — it is a
policy floor, not a silently-substituted market price. Region-specific AGMARKNET
prices remain an open obligation and would refine (not gate) the admitted set.
"""

from __future__ import annotations

from .crop_economics import CROP_PRICE
from .crop_yield import CROP_YIELD, resolve_yield
from .crop_agronomy import labour_pd_ha
from .climate import compute_crop_water_requirements
from .market import absorption_proxy
from .market_price import market_price as veg_market_price

# Ingested operational data (populated from data/farmsync/market/ when you provide
# exports; empty otherwise). When populated, these drive the FINAL experiment.
_INGESTED = {"prices": {}, "costs": {}, "active": False}


def load_operational_market(market_dir):
    """Load AGMARKNET/DES-CoC exports; when present, switch to the market-price basis."""
    from .market_ingest import load_market_dir
    data = load_market_dir(market_dir)
    _INGESTED["prices"] = data["prices"]
    _INGESTED["costs"] = data["costs"]
    _INGESTED["active"] = bool(data["present"])
    return data


def operational_price(crop_name, region_id, season):
    """Operational price (Rs/kg) + basis. Prefers ingested AGMARKNET state price;
    then legacy ingest; then vegetable representative; then MSP reference."""
    from .ingest import operational as opdata
    if opdata.is_loaded():
        p, basis = opdata.op_price(region_id, crop_name)
        if p is not None:
            return p, basis
        if basis and basis.startswith("SPARSE"):
            return None, basis                        # sparse -> not admitted for final
    ing = _INGESTED["prices"].get((crop_name, region_id))
    if ing:
        return ing["price_per_kg"], f"MARKET_AGMARKNET(region {region_id})"
    veg = veg_market_price(crop_name)
    if veg is not None:
        return veg, "MARKET_REPRESENTATIVE_PROVISIONAL"
    pr = CROP_PRICE.get(crop_name)
    if pr and pr.msp_floor_per_kg is not None:
        return pr.msp_floor_per_kg, "MSP_FLOOR_REFERENCE"
    return None, None


def operational_cost_per_ha(crop_name, region_id, season, basis="C2"):
    """Operational cost/ha + basis. Prefers ingested DES-CoC; then CACP cost×yield."""
    from .ingest import operational as opdata
    if opdata.is_loaded():
        c, cbasis = opdata.op_cost(region_id, crop_name, basis=basis)
        if c is not None:
            return c, cbasis
        return None, None                             # loaded but missing -> not admitted
    ing = _INGESTED["costs"].get((crop_name, region_id))
    if ing:
        return ing["cost_per_ha"], f"DES_CoC({ing['basis']})"
    pr = CROP_PRICE.get(crop_name)
    y = resolve_yield(crop_name, season, region_id)["value"]
    if pr and pr.cost_per_quintal is not None and y is not None \
            and CROP_YIELD[crop_name].unit_consistent_with_price:
        return round(pr.cost_per_quintal * (y/100.0), 0), f"CACP×yield({pr.cost_basis})"
    return None, None


def op_yield_value(crop_name, region_id, season):
    """Yield (kg/ha) + scope, preferring ingested DES state yield."""
    from .ingest import operational as opdata
    if opdata.is_loaded():
        v, scope = opdata.op_yield(region_id, crop_name)
        if v is not None:
            return v, scope
    y = resolve_yield(crop_name, season, region_id)
    return y["value"], y["scope"]

# Crops fully grounded for optimisation return (11 of 14).
ADMITTED_CROPS = [
    "rice", "wheat", "maize", "sorghum", "pearl_millet", "chickpea",
    "pigeon_pea", "groundnut", "soybean", "mustard", "cotton",
]
EXCLUDED_CROPS = {"potato": "no MSP price; AGMARKNET not yet sourced",
                  "onion": "no MSP price and no yield yet",
                  "tomato": "no MSP price and no yield yet"}


def is_admitted(crop_name: str, region_id: str, season: str) -> tuple:
    """(admitted, reason). Admitted only if every required field is grounded:
    yield, an operational price, a consistent cost/ha, consistent units, and CWR.
    With AGMARKNET/DES-CoC ingested, vegetables can qualify; otherwise they don't."""
    if crop_name in EXCLUDED_CROPS and not _INGESTED["active"]:
        # vegetables excluded only while no operational market/cost data is loaded
        pass
    y_val, y_scope = op_yield_value(crop_name, region_id, season)
    if y_val is None:
        return False, "no yield for this season"
    if not CROP_YIELD[crop_name].unit_consistent_with_price:
        return False, "unit inconsistency"
    price, pbasis = operational_price(crop_name, region_id, season)
    if price is None:
        return False, f"no usable price ({pbasis or 'missing'})"
    cost, cbasis = operational_cost_per_ha(crop_name, region_id, season)
    if cost is None:
        return False, "no cost/ha"
    from .ingest import operational as opdata
    if opdata.is_loaded() and opdata.op_labour(region_id, crop_name) is None:
        return False, "no labour data"
    cwr = compute_crop_water_requirements(region_id, season)
    if cwr.get("_status") != "OK" or crop_name not in cwr:
        return False, "no crop water requirement"
    return True, f"grounded (price:{pbasis}, cost:{cbasis}, yield:{y_scope})"


def admitted_crops_for(region_id, season):
    """Dynamic admitted set given current data (11 crops on provisional basis;
    up to 14 once vegetable price+cost are ingested)."""
    from .generate import CROPS
    out = []
    for c in CROPS:
        if season in c.seasons:
            ok, _ = is_admitted(c.crop_name, region_id, season)
            if ok:
                out.append(c.crop_name)
    return out


def projected_return(crop_name: str, region_id: str, season: str, area_ha: float) -> dict:
    """
    Net projected return for a plot allocation, on fully-grounded inputs only.
    revenue = price(MSP floor) x yield x area; cost = cost_per_quintal x yield/100 x area.
    Yield (state or national) is used consistently for BOTH revenue and cost.
    Raises if the crop is not admitted (no placeholder ever enters the calculation).
    """
    ok, reason = is_admitted(crop_name, region_id, season)
    if not ok:
        raise ValueError(f"{crop_name}/{region_id}/{season} not admitted: {reason}")
    y_val, y_scope = op_yield_value(crop_name, region_id, season)
    yld_kg_ha = y_val
    price, price_basis = operational_price(crop_name, region_id, season)
    cost_ha, cost_basis = operational_cost_per_ha(crop_name, region_id, season)
    a2fl_ha, _ = operational_cost_per_ha(crop_name, region_id, season, basis="A2FL")
    from .ingest import operational as opdata
    absorp = opdata.op_absorption(crop_name) if opdata.is_loaded() else absorption_proxy(crop_name)
    lab = opdata.op_labour(region_id, crop_name) if opdata.is_loaded() else labour_pd_ha(crop_name)
    lab = lab if lab is not None else labour_pd_ha(crop_name)
    revenue = price * yld_kg_ha * area_ha
    cost = cost_ha * area_ha
    a2fl_cost = (a2fl_ha if a2fl_ha is not None else cost_ha) * area_ha
    return {
        "crop": crop_name, "region": region_id, "season": season, "area_ha": area_ha,
        "yield_kg_ha": yld_kg_ha, "yield_scope": y_scope,
        "price_per_kg": price, "price_basis": price_basis,
        "cost_basis": cost_basis, "cost_per_ha": cost_ha,
        "revenue": round(revenue, 0), "cost": round(cost, 0),
        "net_return": round(revenue - cost, 0),               # C2 economic
        "cash_cost": round(a2fl_cost, 0),
        "cash_net_return": round(revenue - a2fl_cost, 0),     # A2+FL cash (farmer's objective)
        "absorption_proxy": absorp,
        "labour_pd": round(lab * area_ha, 1),
    }


def admitted_gate_report() -> dict:
    """Machine-readable final gate: classify every crop×region×season as admitted
    (all required fields valid) or excluded (with reason). Exclusion is expected and
    correct — 'valid' means no ADMITTED combo carries a placeholder/invalid value."""
    from .generate import REGIONS, CROPS
    seasons_by_crop = {c.crop_name: c.seasons for c in CROPS}
    admitted, excluded = [], []
    for c in CROPS:
        for r in REGIONS:
            for season in seasons_by_crop[c.crop_name]:
                ok, reason = is_admitted(c.crop_name, r.region_id, season)
                rec = {"crop": c.crop_name, "region": r.region_id, "season": season, "reason": reason}
                (admitted if ok else excluded).append(rec)
    return {
        "admitted_combinations": len(admitted),
        "admitted": admitted,
        "excluded_combinations": len(excluded),
        "excluded": excluded,
        "admitted_crops": sorted({a["crop"] for a in admitted}),
        "fully_excluded_crops": sorted(
            {c.crop_name for c in CROPS} - {a["crop"] for a in admitted}),
        "gate_valid": True,   # is_admitted guarantees admitted combos have no placeholder
    }
