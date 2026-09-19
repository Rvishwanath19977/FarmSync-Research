"""
Materialize the built-in FarmSync research dataset as CSV files.

Writes the frozen built-in dataset from the existing generator + FAO-56 water
block + regional ET0 + provenance. Files for which authoritative values are not
yet sourced (full economics, suitability, preferences, market scenarios) are
written with correct headers and REQUIRES_SOURCING / empty markers — never with
invented numbers. The dataset the user provides later can drop into the same
directory and replace this placeholder.
"""

from __future__ import annotations

import csv
import os

from .generate import generate_dataset, REGIONS, CROPS
from .schemas import Season
from .crop_water import CROP_WATER
from .climate import REGION_ET0, compute_crop_water_requirements
from .crop_economics import CROP_PRICE
from .crop_yield import CROP_YIELD, derive_cost_per_ha, resolve_yield
from .sourcing_report import build_phase5_registry


def _write(path, headers, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in headers})


def build_builtin_dataset(out_dir: str, master_seed: int = 20260812,
                          n_farmers: int = 500, n_collectives: int = 10,
                          season: Season = Season.KHARIF):
    os.makedirs(out_dir, exist_ok=True)
    farmers, plots, crops, regions, manifest, prov, collectives = generate_dataset(
        master_seed=master_seed, n_farmers=n_farmers,
        n_collectives=n_collectives, season=season)

    # farmers / plots / collectives / crops / regions
    _write(os.path.join(out_dir, "farmers.csv"),
           list(farmers[0].to_row().keys()), [f.to_row() for f in farmers])
    _write(os.path.join(out_dir, "plots.csv"),
           list(plots[0].to_row().keys()), [p.to_row() for p in plots])
    _write(os.path.join(out_dir, "collectives.csv"),
           ["collective_id", "collective_name", "region_id", "season",
            "description", "active", "synthetic"],
           [c.to_row() for c in collectives])
    _write(os.path.join(out_dir, "crops.csv"),
           ["crop_id", "crop_name", "crop_group", "seasons", "duration_days",
            "rotation_group", "perishability", "synthetic"],
           [{**c.__dict__, "seasons": "|".join(c.seasons)} for c in crops])
    _write(os.path.join(out_dir, "regions.csv"),
           ["region_id", "name", "dominant_soil", "rainfall_regime",
            "irrigation_propensity", "synthetic"],
           [{**r.__dict__, "dominant_soil": r.dominant_soil.value} for r in regions])

    # crop_region_season_params — water grounded; economics REQUIRES_SOURCING
    param_rows = []
    for c in crops:
        for r in regions:
            for season_v in c.seasons:
                cw = CROP_WATER[c.crop_name]
                cwr = compute_crop_water_requirements(r.region_id, season_v)
                cwr_val = cwr.get(c.crop_name, "") if cwr.get("_status") == "OK" else ""
                pr = CROP_PRICE.get(c.crop_name)
                msp = pr.msp_floor_per_kg if pr else None
                yobj = CROP_YIELD.get(c.crop_name)
                yres = resolve_yield(c.crop_name, season_v, r.region_id)
                yld = yres["value"]
                cost = derive_cost_per_ha(c.crop_name, season_v)
                cost_ha = cost.get("cost_per_ha") if cost else None
                param_rows.append({
                    "crop_id": c.crop_id, "region_id": r.region_id, "season": season_v,
                    "duration_days": cw.duration_days,
                    "crop_water_requirement_mm": cwr_val,
                    "expected_yield_kg_ha": yld if yld is not None else "REQUIRES_SOURCING",
                    "yield_scope": (yres["scope"] if yld is not None else ""),
                    "msp_floor_per_kg": msp if msp is not None else "",
                    "cost_per_quintal": (pr.cost_per_quintal if pr and pr.cost_per_quintal else ""),
                    "cost_basis": (pr.cost_basis if pr and pr.cost_basis else ""),
                    "cultivation_cost_per_ha": cost_ha if cost_ha is not None else "REQUIRES_SOURCING",
                    "price_per_kg": "REQUIRES_SOURCING (AGMARKNET market price)",
                    "labour_pd_per_ha": "REQUIRES_SOURCING",
                    "market_absorption_proxy": "REQUIRES_SOURCING",
                    "drought_sensitivity": "REQUIRES_SOURCING",
                    "heat_sensitivity": "REQUIRES_SOURCING",
                    "waterlogging_sensitivity": "REQUIRES_SOURCING",
                })
    _write(os.path.join(out_dir, "crop_region_season_params.csv"),
           list(param_rows[0].keys()), param_rows)

    # climate_scenarios — ET0 sourced per region + named scenario templates
    climate_rows = []
    scenarios = ["baseline", "drought", "water_shortage", "heat",
                 "excessive_rainfall", "unseasonal_rainfall", "delayed_rainfall",
                 "combined_heat_drought"]
    for r in regions:
        et0 = REGION_ET0.get(r.region_id)
        for sc in scenarios:
            climate_rows.append({
                "region_id": r.region_id, "scenario": sc,
                "kharif_et0_mm_day": et0.kharif_mm_day if et0 else "",
                "rabi_et0_mm_day": et0.rabi_mm_day if et0 else "",
                "et0_confidence": et0.confidence if et0 else "REQUIRES_SOURCING",
                "severity_note": "baseline sourced; shock magnitudes are experimental parameters",
            })
    _write(os.path.join(out_dir, "climate_scenarios.csv"),
           list(climate_rows[0].keys()), climate_rows)

    # hazard_zones — from plots
    zones = sorted({p.hazard_zone for p in plots})
    _write(os.path.join(out_dir, "hazard_zones.csv"),
           ["hazard_zone", "region_id", "plot_count"],
           [{"hazard_zone": z, "region_id": z.split("-")[0],
             "plot_count": sum(1 for p in plots if p.hazard_zone == z)} for z in zones])

    # participation_scenarios — the commitment/event vocabulary as templates
    _write(os.path.join(out_dir, "participation_scenarios.csv"),
           ["scenario", "participation_rate", "non_response_rate", "withdrawal_rate", "note"],
           [{"scenario": s, "participation_rate": pr, "non_response_rate": "",
             "withdrawal_rate": "", "note": "experimental level"}
            for s, pr in [("full", 1.0), ("high", 0.9), ("moderate", 0.75),
                          ("low", 0.6), ("very_low", 0.4)]])

    # plot_crop_suitability — computed by the Phase 6 agronomic feasibility engine
    from .feasibility import assess_plot_crop, FeasibilityConfig
    cfg = FeasibilityConfig()
    farmer_by_id = {f.farmer_id: f for f in farmers}
    suit_rows = []
    for p in plots:
        fmr = farmer_by_id.get(p.farmer_id)
        for c in crops:
            res = assess_plot_crop(p, c, farmer=fmr, config=cfg)
            row = res.to_row()
            row["crop_id"] = c.crop_id          # map crop_name -> crop_id for referential integrity
            suit_rows.append(row)
    _write(os.path.join(out_dir, "plot_crop_suitability.csv"),
           ["plot_id", "crop_id", "feasible", "reason_code", "binding"], suit_rows)
    _write(os.path.join(out_dir, "farmer_preferences.csv"),
           ["farmer_id", "preferred_crops", "excluded_crops", "preference_score",
            "min_area", "max_area"], [])                            # after feasibility
    _write(os.path.join(out_dir, "market_scenarios.csv"),
           ["crop_id", "region_id", "scenario", "price_change", "absorption_change",
            "cost_change"], [])                                     # after price sourcing

    # provenance
    reg = build_phase5_registry([c.crop_name for c in crops])
    for r in prov.records:
        reg.add(r)
    _write(os.path.join(out_dir, "parameter_provenance.csv"),
           ["parameter", "provenance_type", "value", "unit", "crop", "region",
            "season", "source", "source_url", "source_year", "transformation",
            "assumption", "confidence", "notes"],
           reg.rows())

    # data dictionary
    _write(os.path.join(out_dir, "dataset_dictionary.csv"),
           ["file", "field", "description"], _data_dictionary())

    return manifest


def _data_dictionary():
    return [
        {"file": "farmers.csv", "field": "farmer_id", "description": "Synthetic farmer identifier"},
        {"file": "farmers.csv", "field": "collective_id", "description": "Collective the farmer belongs to"},
        {"file": "farmers.csv", "field": "total_area_ha", "description": "Aggregate landholding (ha), sums plot areas"},
        {"file": "plots.csv", "field": "plot_id", "description": "Synthetic plot identifier"},
        {"file": "plots.csv", "field": "available_water_m3", "description": "Seasonal water available to the plot"},
        {"file": "plots.csv", "field": "hazard_zone", "description": "Correlated-failure zone identifier"},
        {"file": "collectives.csv", "field": "collective_id", "description": "Collective identifier"},
        {"file": "collectives.csv", "field": "region_id", "description": "Region the collective operates in"},
        {"file": "collectives.csv", "field": "season", "description": "Season context (kharif/rabi)"},
        {"file": "crop_region_season_params.csv", "field": "crop_water_requirement_mm", "description": "FAO-56 Kc x regional ET0 (derived)"},
        {"file": "crop_region_season_params.csv", "field": "expected_yield_kg_ha", "description": "REQUIRES_SOURCING (DES district-season)"},
        {"file": "parameter_provenance.csv", "field": "provenance_type", "description": "OBSERVED / DERIVED / SYNTHETIC_GROUNDED / SYNTHETIC_EXPERIMENTAL"},
        {"file": "parameter_provenance.csv", "field": "confidence", "description": "HIGH/MEDIUM/LOW or REQUIRES_SOURCING"},
    ]
