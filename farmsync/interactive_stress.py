"""
FarmSync interactive-stress-v1.

Deterministic fixed-allocation sensitivity analysis for the exact FINAL_REALIZED
working plan.

This is intentionally separate from frozen uncertainty-v1.

Scientific contract
-------------------
* Fixed FINAL_REALIZED allocation only.
* No optimisation / reallocation / CBC / PuLP.
* No farmer-response simulation.
* No participation uncertainty after finalisation.
* Weather stress changes ET0 -> CWR/NIR/water exposure only.
  It does NOT invent a yield-loss response.
* Market stress changes AGMARKNET operational price; costs/yield remain fixed.
  Absorption is reported as capacity exposure only; it never reallocates crops.
* Resource stress scales farmer budget and labour capacity together and reports
  whether the fixed allocation exceeds those shocked capacities.
* Joint stress evaluates W + M + R simultaneously but does not convert water or
  resource exposure into an unsupported cash-loss estimate.

The adverse multipliers mirror the corresponding frozen uncertainty-v1 states,
but probabilities/RNG are NOT used by this interactive sensitivity protocol.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from . import climate
from . import config as C
from .crop_water import CROP_WATER
from .ingest import operational as opdata
from .planning import (
    labour_pd_ha,
    op_yield_value,
    operational_cost_per_ha,
    operational_price,
)


PROTOCOL_VERSION = "interactive-stress-v1"

WEATHER_ET0_MULT = C.WEATHER_ET0_STATES["HIGH_EVAPORATIVE_DEMAND"][0]
MARKET_PRICE_MULT = C.MARKET_PRICE_STATES["LOW"][0]
MARKET_ABSORPTION_MULT = C.MARKET_ABSORPTION_STATES["LOW"][0]
RESOURCE_MULT = C.RESOURCE_STATES["CONSTRAINED"][0]


def _season_value(v):
    return v.value if hasattr(v, "value") else str(v)


def final_plan_hash(allocations):
    """Stable order-independent hash of the exact realised-plan economic identity."""
    rows = []
    for a in allocations:
        rows.append({
            "farmer_id": str(a["farmer_id"]),
            "plot_id": str(a["plot_id"]),
            "final_crop": str(a["final_crop"]).lower(),
            "final_cash": round(float(a["final_cash"]), 6),
        })
    rows.sort(key=lambda x: (
        x["farmer_id"], x["plot_id"], x["final_crop"], x["final_cash"]
    ))
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _assert_clean_scoped_state():
    """
    interactive-stress-v1 must read baseline operational/climate values.

    Refuse to run inside a frozen uncertainty-v1 scoped override rather than
    clearing or mutating someone else's scientific context.
    """
    if not opdata.is_loaded():
        raise RuntimeError(
            "interactive-stress-v1 requires loaded processed operational data"
        )

    if getattr(climate, "_ET0_MULT", {}):
        raise RuntimeError(
            "interactive-stress-v1 cannot run while an ET0 uncertainty override is active"
        )

    if getattr(opdata, "_PRICE_MULT", {}) or getattr(opdata, "_ABS_MULT", {}):
        raise RuntimeError(
            "interactive-stress-v1 cannot run while a market uncertainty override is active"
        )


def _baseline_economics(plot, crop_name):
    """
    Formula-identical fixed-plan cash economics without installing shock globals.

    Mirrors projected_return():
      revenue = operational_price * operational_yield * area
      cash cost = A2+FL cost/ha * area (C2 only if A2+FL unavailable)
      cash net = revenue - cash cost
    """
    region = plot.region_id
    season = _season_value(plot.active_season)
    area = float(plot.area_ha)

    yld, y_scope = op_yield_value(crop_name, region, season)
    price, price_basis = operational_price(crop_name, region, season)

    c2_ha, c2_basis = operational_cost_per_ha(
        crop_name, region, season, basis="C2"
    )
    a2fl_ha, a2fl_basis = operational_cost_per_ha(
        crop_name, region, season, basis="A2FL"
    )

    lab_ha = opdata.op_labour(region, crop_name)
    if lab_ha is None:
        lab_ha = labour_pd_ha(crop_name)

    missing = []
    if yld is None:
        missing.append("yield")
    if price is None:
        missing.append("price")
    if c2_ha is None:
        missing.append("C2 cost")
    if lab_ha is None:
        missing.append("labour")

    if missing:
        return {
            "available": False,
            "reason": "Missing operational inputs: " + ", ".join(missing),
        }

    effective_a2fl_ha = a2fl_ha if a2fl_ha is not None else c2_ha

    revenue = float(price) * float(yld) * area
    economic_cost = float(c2_ha) * area
    cash_cost = float(effective_a2fl_ha) * area

    return {
        "available": True,
        "yield_kg_ha": float(yld),
        "yield_scope": y_scope,
        "price_per_kg": float(price),
        "price_basis": price_basis,
        "c2_cost_per_ha": float(c2_ha),
        "c2_cost_basis": c2_basis,
        "a2fl_cost_per_ha": float(effective_a2fl_ha),
        "a2fl_cost_basis": a2fl_basis or c2_basis,
        "revenue": round(revenue, 0),
        "economic_cost": round(economic_cost, 0),
        "cash_cost": round(cash_cost, 0),
        "cash_net_return": round(revenue - cash_cost, 0),
        "labour_pd": round(float(lab_ha) * area, 1),
    }


def _base_et0(region_id, season):
    row = climate.REGION_ET0.get(region_id)
    if row is None:
        return None
    return (
        row.kharif_mm_day
        if season == "kharif"
        else row.rabi_mm_day
    )


def _water_record(plot, crop_name, et0_mult):
    """
    Fixed-allocation weather sensitivity.

    FAO-56 CWR is recomputed with stressed ET0. Effective rainfall is held at
    the existing experimental rainfall assumption. No yield response is added.
    """
    region = plot.region_id
    season = _season_value(plot.active_season)
    area = float(plot.area_ha)

    et0 = _base_et0(region, season)
    cw = CROP_WATER.get(crop_name)
    eff_rain = climate.effective_rainfall_mm(region, season)

    if et0 is None or cw is None or eff_rain is None:
        return {
            "available": False,
            "plot_id": plot.plot_id,
            "reason": "Required ET0/CWR/effective-rainfall input unavailable",
        }

    base_stage = {
        k: float(et0)
        for k in ("init", "dev", "mid", "late")
    }
    stressed_stage = {
        k: float(et0) * float(et0_mult)
        for k in ("init", "dev", "mid", "late")
    }

    base_cwr = float(cw.crop_water_requirement_mm(base_stage))
    stressed_cwr = float(cw.crop_water_requirement_mm(stressed_stage))

    base_nir = max(0.0, base_cwr - float(eff_rain))
    stressed_nir = max(0.0, stressed_cwr - float(eff_rain))

    base_need = base_nir * area * 10.0
    stressed_need = stressed_nir * area * 10.0
    available = float(plot.available_water_m3)

    return {
        "available": True,
        "plot_id": plot.plot_id,
        "farmer_id": plot.farmer_id,
        "crop": crop_name,
        "region_id": region,
        "season": season,
        "area_ha": area,
        "et0_multiplier": float(et0_mult),
        "baseline_cwr_mm": round(base_cwr, 1),
        "stressed_cwr_mm": round(stressed_cwr, 1),
        "effective_rainfall_mm": round(float(eff_rain), 1),
        "baseline_nir_mm": round(base_nir, 1),
        "stressed_nir_mm": round(stressed_nir, 1),
        "baseline_required_water_m3": round(base_need, 1),
        "stressed_required_water_m3": round(stressed_need, 1),
        "available_water_m3": round(available, 1),
        "baseline_water_exposed": base_need > available + 1e-9,
        "stressed_water_exposed": stressed_need > available + 1e-9,
    }


def _weather_summary(records, et0_mult):
    details = []
    missing = []

    for r in records:
        w = _water_record(r["plot"], r["crop"], et0_mult)
        if not w["available"]:
            missing.append({
                "plot_id": r["plot"].plot_id,
                "reason": w["reason"],
            })
        else:
            details.append(w)

    exposed_ids = {
        d["plot_id"] for d in details
        if d["stressed_water_exposed"]
    }

    cash_by_plot = {
        r["plot"].plot_id: r["baseline"]["cash_net_return"]
        for r in records
    }

    return {
        "available": len(missing) == 0,
        "et0_multiplier": float(et0_mult),
        "n_evaluable_plots": len(details),
        "n_missing_plots": len(missing),
        "missing": missing,
        "n_water_exposed_plots": len(exposed_ids),
        "water_exposed_area_ha": round(sum(
            d["area_ha"] for d in details
            if d["plot_id"] in exposed_ids
        ), 3),
        # Value is "at exposure", not a claimed weather-induced cash loss.
        "baseline_cash_at_water_exposure": round(sum(
            cash_by_plot[pid] for pid in exposed_ids
        ), 0),
        "details": details,
        "interpretation": (
            "Water exposure only. interactive-stress-v1 does not apply a "
            "weather-driven yield or cash-loss function."
        ),
    }


def _market_summary(
    records,
    price_mult,
    absorption_mult,
    total_dataset_area_ha,
):
    """
    Fixed-allocation market sensitivity.

    Price:
      recompute cash on the unchanged realised allocation.

    Absorption:
      preserve FarmSync's established B2/B3 semantics:
          area_cap_c = absorption_proxy_c * total selected dataset area

      The absorption proxy is an arrivals-derived relative throughput proxy,
      NOT hectares and NOT empirical demand.
    """
    per_plot = []
    baseline_total = 0.0
    stressed_total = 0.0
    crop_area = defaultdict(float)

    for r in records:
        b = r["baseline"]
        plot = r["plot"]

        baseline_total += b["cash_net_return"]

        stressed_revenue = (
            b["price_per_kg"]
            * float(price_mult)
            * b["yield_kg_ha"]
            * float(plot.area_ha)
        )

        stressed_cash = round(
            stressed_revenue - b["cash_cost"],
            0,
        )

        stressed_total += stressed_cash
        crop_area[r["crop"]] += float(plot.area_ha)

        per_plot.append({
            "farmer_id": plot.farmer_id,
            "plot_id": plot.plot_id,
            "crop": r["crop"],
            "area_ha": float(plot.area_ha),
            "baseline_price_per_kg": b["price_per_kg"],
            "stressed_price_per_kg": round(
                b["price_per_kg"] * float(price_mult),
                6,
            ),
            "baseline_cash_net_return": b["cash_net_return"],
            "stressed_cash_net_return": stressed_cash,
        })

    absorption = {}
    missing_absorption = []

    for crop, area in sorted(crop_area.items()):
        proxy = opdata.op_absorption(crop)

        if proxy is None:
            missing_absorption.append(crop)
            absorption[crop] = {
                "available": False,
                "realised_area_ha": round(area, 3),
            }
            continue

        baseline_proxy = float(proxy)
        stressed_proxy = baseline_proxy * float(absorption_mult)

        baseline_cap_ha = (
            baseline_proxy * float(total_dataset_area_ha)
        )
        stressed_cap_ha = (
            stressed_proxy * float(total_dataset_area_ha)
        )

        excess = max(0.0, area - stressed_cap_ha)

        absorption[crop] = {
            "available": True,

            # Raw arrivals-derived relative proxy.
            "baseline_absorption_proxy": round(
                baseline_proxy, 6
            ),
            "stressed_absorption_proxy": round(
                stressed_proxy, 6
            ),

            # Comparable physical units.
            "selected_dataset_area_ha": round(
                float(total_dataset_area_ha), 3
            ),
            "realised_area_ha": round(area, 3),
            "baseline_area_cap_ha": round(
                baseline_cap_ha, 3
            ),
            "stressed_area_cap_ha": round(
                stressed_cap_ha, 3
            ),
            "excess_over_stressed_cap_ha": round(
                excess, 3
            ),
            "exposed": excess > 1e-9,
        }

    change = stressed_total - baseline_total

    return {
        "available": len(missing_absorption) == 0,
        "price_multiplier": float(price_mult),
        "absorption_multiplier": float(absorption_mult),
        "selected_dataset_area_ha": round(
            float(total_dataset_area_ha), 3
        ),

        "baseline_cash_net_return": round(
            baseline_total, 0
        ),
        "stressed_cash_net_return": round(
            stressed_total, 0
        ),
        "cash_change": round(change, 0),
        "cash_change_pct": (
            round(100.0 * change / baseline_total, 3)
            if baseline_total
            else None
        ),

        "n_absorption_exposed_crops": sum(
            1
            for x in absorption.values()
            if x.get("available") and x.get("exposed")
        ),

        "missing_absorption_crops": missing_absorption,
        "absorption": absorption,
        "per_plot": per_plot,

        "interpretation": (
            "Price stress changes fixed-plan projected cash. "
            "Absorption stress uses the established FarmSync area-cap "
            "definition: absorption proxy ? total selected dataset area. "
            "The proxy is an arrivals-derived throughput proxy, not demand. "
            "No crop is reallocated."
        ),
    }


def _resource_summary(records, farmer_by_id, resource_mult):
    req = defaultdict(lambda: {
        "cash_cost": 0.0,
        "labour_pd": 0.0,
        "area_ha": 0.0,
        "baseline_cash": 0.0,
        "plot_ids": [],
    })

    for r in records:
        fid = r["plot"].farmer_id
        req[fid]["cash_cost"] += r["baseline"]["cash_cost"]
        req[fid]["labour_pd"] += r["baseline"]["labour_pd"]
        req[fid]["area_ha"] += float(r["plot"].area_ha)
        req[fid]["baseline_cash"] += r["baseline"]["cash_net_return"]
        req[fid]["plot_ids"].append(r["plot"].plot_id)

    rows = []
    exposed_ids = set()
    exposed_plot_ids = set()

    for fid, v in sorted(req.items()):
        farmer = farmer_by_id.get(fid)
        if farmer is None:
            rows.append({
                "farmer_id": fid,
                "available": False,
                "reason": "Farmer resource record unavailable",
            })
            continue

        base_budget = float(farmer.cultivation_budget)
        base_labour = float(farmer.labour_capacity)

        shocked_budget = max(0.0, base_budget * float(resource_mult))
        shocked_labour = max(0.0, base_labour * float(resource_mult))

        budget_exposed = v["cash_cost"] > shocked_budget + 1e-9
        labour_exposed = v["labour_pd"] > shocked_labour + 1e-9
        exposed = budget_exposed or labour_exposed

        if exposed:
            exposed_ids.add(fid)
            exposed_plot_ids.update(v["plot_ids"])

        rows.append({
            "farmer_id": fid,
            "available": True,
            "resource_multiplier": float(resource_mult),
            "required_cash_cost": round(v["cash_cost"], 0),
            "baseline_budget": round(base_budget, 0),
            "stressed_budget": round(shocked_budget, 0),
            "required_labour_pd": round(v["labour_pd"], 1),
            "baseline_labour_capacity": round(base_labour, 1),
            "stressed_labour_capacity": round(shocked_labour, 1),
            "budget_exposed": budget_exposed,
            "labour_exposed": labour_exposed,
            "exposed": exposed,
            "n_realised_plots": len(v["plot_ids"]),
            "realised_area_ha": round(v["area_ha"], 3),
            "baseline_cash_at_exposure": round(v["baseline_cash"], 0),
        })

    missing = [x for x in rows if not x["available"]]
    exposed_rows = [
        x for x in rows
        if x.get("available") and x.get("exposed")
    ]

    return {
        "available": len(missing) == 0,
        "resource_multiplier": float(resource_mult),
        "n_evaluable_farmers": len(rows) - len(missing),
        "n_missing_farmers": len(missing),
        "n_exposed_farmers": len(exposed_ids),
        "n_exposed_plots": len(exposed_plot_ids),
        "exposed_area_ha": round(sum(
            x["realised_area_ha"] for x in exposed_rows
        ), 3),
        # Again: value at exposure, not assumed loss.
        "baseline_cash_at_resource_exposure": round(sum(
            x["baseline_cash_at_exposure"] for x in exposed_rows
        ), 0),
        "farmers": rows,
        "interpretation": (
            "Capacity exposure only. interactive-stress-v1 does not scale or "
            "erase crop cash because a budget/labour constraint is exceeded."
        ),
    }


def _joint_summary(
    records,
    farmer_by_id,
    total_dataset_area_ha,
):
    weather = _weather_summary(
        records,
        WEATHER_ET0_MULT,
    )

    market = _market_summary(
        records,
        MARKET_PRICE_MULT,
        MARKET_ABSORPTION_MULT,
        total_dataset_area_ha,
    )

    resources = _resource_summary(
        records,
        farmer_by_id,
        RESOURCE_MULT,
    )

    weather_ids = {
        d["plot_id"]
        for d in weather.get("details", [])
        if d.get("stressed_water_exposed")
    }

    resource_ids = set()

    for f in resources.get("farmers", []):
        if f.get("available") and f.get("exposed"):
            fid = f["farmer_id"]

            for r in records:
                if r["plot"].farmer_id == fid:
                    resource_ids.add(
                        r["plot"].plot_id
                    )

    union_ids = weather_ids | resource_ids

    rec_by_plot = {
        r["plot"].plot_id: r
        for r in records
    }

    return {
        "available": (
            weather["available"]
            and market["available"]
            and resources["available"]
        ),
        "channels": ["W", "M", "R"],
        "weather": weather,
        "market": market,
        "resources": resources,

        "n_plots_with_weather_or_resource_exposure":
            len(union_ids),

        "area_with_weather_or_resource_exposure":
            round(sum(
                float(
                    rec_by_plot[pid]["plot"].area_ha
                )
                for pid in union_ids
            ), 3),

        "baseline_cash_at_weather_or_resource_exposure":
            round(sum(
                rec_by_plot[pid]["baseline"][
                    "cash_net_return"
                ]
                for pid in union_ids
            ), 0),

        "interpretation": (
            "Joint W+M+R sensitivity on the same fixed allocation. "
            "Market cash is recomputed under the price shock; "
            "weather/resource exposure is not converted into "
            "unsupported additional cash loss."
        ),
    }


def analyse_fixed_final_plan(
    allocations,
    plots_by_id,
    farmer_by_id,
    *,
    dataset_hash=None,
    final_plan_revision=None,
):
    """
    Evaluate deterministic adverse stresses on an already FINAL_REALIZED plan.

    allocations entries require:
      farmer_id, plot_id, final_crop, final_cash

    No state is mutated.
    """
    _assert_clean_scoped_state()

    allocations = list(allocations or [])
    if not allocations:
        return {
            "available": False,
            "protocol_version": PROTOCOL_VERSION,
            "reason": "No realised allocations exist in the current final plan.",
        }

    seen = set()
    records = []
    missing = []
    mismatches = []

    for a in allocations:
        fid = str(a["farmer_id"])
        pid = str(a["plot_id"])
        crop = str(a["final_crop"]).lower()

        if pid in seen:
            return {
                "available": False,
                "protocol_version": PROTOCOL_VERSION,
                "reason": f"Duplicate realised plot in final plan: {pid}",
            }
        seen.add(pid)

        plot = plots_by_id.get(pid)
        farmer = farmer_by_id.get(fid)

        if plot is None or farmer is None:
            missing.append({
                "farmer_id": fid,
                "plot_id": pid,
                "missing": (
                    "plot" if plot is None else "farmer"
                ),
            })
            continue

        b = _baseline_economics(plot, crop)
        if not b["available"]:
            missing.append({
                "farmer_id": fid,
                "plot_id": pid,
                "missing": b["reason"],
            })
            continue

        stored_cash = float(a["final_cash"])

        if abs(stored_cash - b["cash_net_return"]) > 1.0:
            mismatches.append({
                "farmer_id": fid,
                "plot_id": pid,
                "crop": crop,
                "stored_final_cash": stored_cash,
                "recomputed_cash_net_return": b["cash_net_return"],
            })

        records.append({
            "allocation": dict(a),
            "plot": plot,
            "farmer": farmer,
            "crop": crop,
            "baseline": b,
        })

    if missing:
        return {
            "available": False,
            "protocol_version": PROTOCOL_VERSION,
            "reason": "Required inputs are missing for the current final plan.",
            "missing": missing,
        }

    if mismatches:
        return {
            "available": False,
            "protocol_version": PROTOCOL_VERSION,
            "reason": (
                "Current final-plan cash does not match the loaded operational "
                "economic layer; analysis is withheld rather than mixing provenance."
            ),
            "economic_mismatches": mismatches,
        }

    try:
        total_dataset_area_ha = sum(
            float(p.area_ha)
            for p in plots_by_id.values()
        )
    except (TypeError, ValueError, AttributeError):
        return {
            "available": False,
            "protocol_version": PROTOCOL_VERSION,
            "reason": (
                "Selected dataset area is unavailable; "
                "market-absorption exposure cannot be "
                "evaluated defensibly."
            ),
        }

    if total_dataset_area_ha <= 0:
        return {
            "available": False,
            "protocol_version": PROTOCOL_VERSION,
            "reason": (
                "Selected dataset area must be positive "
                "for interactive stress analysis."
            ),
        }

    plan_hash = final_plan_hash(allocations)

    baseline_cash = round(sum(
        r["baseline"]["cash_net_return"] for r in records
    ), 0)
    baseline_area = round(sum(
        float(r["plot"].area_ha) for r in records
    ), 3)

    uw = _weather_summary(records, WEATHER_ET0_MULT)
    um = _market_summary(
        records,
        MARKET_PRICE_MULT,
        MARKET_ABSORPTION_MULT,
        total_dataset_area_ha,
    )
    ur = _resource_summary(records, farmer_by_id, RESOURCE_MULT)
    uj = _joint_summary(
        records,
        farmer_by_id,
        total_dataset_area_ha,
    )

    return {
        "available": True,
        "protocol_version": PROTOCOL_VERSION,
        "method": "deterministic_fixed_final_realised_sensitivity",
        "deterministic": True,
        "allocation_policy": "fixed-final-realised",
        "reoptimization": False,
        "participation_uncertainty": False,
        "dataset_hash": dataset_hash,
        "final_plan_revision": final_plan_revision,
        "final_plan_hash": plan_hash,
        "n_realised_plots": len(records),
        "selected_dataset_area_ha": round(
            total_dataset_area_ha, 3
        ),
        "baseline": {
            "realised_area_ha": baseline_area,
            "cash_net_return": baseline_cash,
        },
        "stress_definition": {
            "UW": {
                "weather_et0_multiplier": WEATHER_ET0_MULT,
            },
            "UM": {
                "market_price_multiplier": MARKET_PRICE_MULT,
                "market_absorption_multiplier": MARKET_ABSORPTION_MULT,
            },
            "UR": {
                "resource_multiplier": RESOURCE_MULT,
            },
            "UJ": {
                "weather_et0_multiplier": WEATHER_ET0_MULT,
                "market_price_multiplier": MARKET_PRICE_MULT,
                "market_absorption_multiplier": MARKET_ABSORPTION_MULT,
                "resource_multiplier": RESOURCE_MULT,
            },
        },
        "scenarios": {
            "UW": {
                "available": uw["available"],
                "channels": ["W"],
                "weather": uw,
            },
            "UM": {
                "available": um["available"],
                "channels": ["M"],
                "market": um,
            },
            "UR": {
                "available": ur["available"],
                "channels": ["R"],
                "resources": ur,
            },
            "UJ": uj,
        },
        "excluded": {
            "UP_participation": (
                "Excluded because participation uncertainty is a pre-offer "
                "planning-pipeline mechanism and is not valid after finalisation."
            ),
            "weather_yield_loss": (
                "Not modelled: uncertainty-v1 defines ET0-only weather stress "
                "and provides no Ky/yield-response function."
            ),
            "post_stress_reoptimization": (
                "Not performed: this protocol measures sensitivity of the "
                "exact fixed FINAL_REALIZED plan."
            ),
        },
    }
