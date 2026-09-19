"""
FarmSync interactive-resilience-v1.

Deterministic immediate-exposure analysis for the exact FINAL_REALIZED
interactive working plan.

This protocol is deliberately separate from the frozen Phase-5/Stage-6
resilience pipeline.

Scientific contract
-------------------
* Fixed FINAL_REALIZED allocation only.
* No optimisation / CBC / PuLP.
* No backup allocation.
* No post-shock recovery claim.
* No new consent state.
* N-1 producer failure removes ALL realised allocations of the selected farmer.
* Hazard-zone outage removes ALL realised allocations in the selected zone.
* Expected production uses the same operational yield layer as FarmSync.
* Cash exposure uses authoritative final_cash already attached to the final plan.

Representative-selection semantics mirror the frozen integration demonstration:
* N-1 target crop = active crop with maximum pre-shock largest-producer share.
* Failed farmer = largest expected producer of that target crop.
* Hazard representative = lexicographically first non-empty realised hazard zone.

Tie-breaking is made explicit and deterministic: lexical ascending.
"""

from __future__ import annotations

from collections import defaultdict
import math

from .ingest import operational as opdata
from .planning import op_yield_value
from .interactive_stress import final_plan_hash


PROTOCOL_VERSION = "interactive-resilience-v1"

POST_SHOCK_RECOVERY_MESSAGE = (
    "Post-shock recovery: Not evaluated for the current interactive plan. "
    "The frozen Phase-5 backup optimiser is defined over its own "
    "Stage-3/Stage-5 decision state and is not applied to this working plan."
)


def _season_value(v):
    return v.value if hasattr(v, "value") else str(v)


def _require_operational_data():
    if not opdata.is_loaded():
        raise RuntimeError(
            "interactive-resilience-v1 requires loaded processed operational data"
        )


def _records(allocations, plots_by_id):
    rows = []
    missing = []
    seen = set()

    for a in allocations or []:
        fid = str(a["farmer_id"])
        pid = str(a["plot_id"])
        crop = str(a["final_crop"]).lower()

        if pid in seen:
            return None, [{
                "plot_id": pid,
                "reason": "duplicate realised plot",
            }]
        seen.add(pid)

        plot = plots_by_id.get(pid)

        if plot is None:
            missing.append({
                "farmer_id": fid,
                "plot_id": pid,
                "reason": "plot record unavailable",
            })
            continue

        if str(plot.farmer_id) != fid:
            missing.append({
                "farmer_id": fid,
                "plot_id": pid,
                "reason": "allocation owner does not match plot owner",
            })
            continue

        hazard_zone = getattr(plot, "hazard_zone", None)

        if not hazard_zone:
            missing.append({
                "farmer_id": fid,
                "plot_id": pid,
                "reason": "hazard_zone unavailable",
            })
            continue

        season = _season_value(plot.active_season)

        yld, y_scope = op_yield_value(
            crop,
            plot.region_id,
            season,
        )

        if yld is None:
            missing.append({
                "farmer_id": fid,
                "plot_id": pid,
                "reason": "operational yield unavailable",
            })
            continue

        try:
            cash = float(a["final_cash"])
        except (TypeError, ValueError, KeyError):
            missing.append({
                "farmer_id": fid,
                "plot_id": pid,
                "reason": "final_cash unavailable",
            })
            continue

        if not math.isfinite(cash):
            missing.append({
                "farmer_id": fid,
                "plot_id": pid,
                "reason": "final_cash is not finite",
            })
            continue

        area = float(plot.area_ha)
        production = float(yld) * area

        rows.append({
            "farmer_id": fid,
            "plot_id": pid,
            "crop": crop,
            "region_id": plot.region_id,
            "season": season,
            "hazard_zone": str(hazard_zone),
            "area_ha": area,
            "yield_kg_ha": float(yld),
            "yield_scope": y_scope,
            "expected_production_kg": production,
            "final_cash": cash,
        })

    return rows, missing


def _crop_concentration(records):
    by_crop_farmer = defaultdict(
        lambda: defaultdict(float)
    )

    for r in records:
        by_crop_farmer[r["crop"]][
            r["farmer_id"]
        ] += r["expected_production_kg"]

    out = {}

    for crop in sorted(by_crop_farmer):
        by_farmer = by_crop_farmer[crop]
        total = sum(by_farmer.values())

        ordered = sorted(
            by_farmer.items(),
            key=lambda x: (-x[1], x[0]),
        )

        largest_farmer, largest_prod = ordered[0]

        lps = (
            largest_prod / total
            if total > 0
            else 0.0
        )

        out[crop] = {
            "crop": crop,
            "total_expected_production_kg": round(
                total, 1
            ),
            "largest_producer": largest_farmer,
            "largest_producer_expected_production_kg":
                round(largest_prod, 1),
            "largest_producer_share": round(
                lps, 6
            ),
            "n_producers": len(by_farmer),
        }

    return out


def _select_target_crop(crop_stats):
    if not crop_stats:
        return None

    # Highest LPS first; lexical crop name breaks exact ties.
    return sorted(
        crop_stats,
        key=lambda crop: (
            -crop_stats[crop][
                "largest_producer_share"
            ],
            crop,
        ),
    )[0]


def _nminus1(records, crop_stats):
    target_crop = _select_target_crop(
        crop_stats
    )

    if target_crop is None:
        return {
            "available": False,
            "reason": "No active crop exists in the realised plan.",
        }

    target = crop_stats[target_crop]
    failed_farmer = target["largest_producer"]

    affected = [
        r for r in records
        if r["farmer_id"] == failed_farmer
    ]

    total_cash = sum(
        r["final_cash"]
        for r in records
    )

    cash_loss = sum(
        r["final_cash"]
        for r in affected
    )

    failed_area = sum(
        r["area_ha"]
        for r in affected
    )

    failed_all_prod = sum(
        r["expected_production_kg"]
        for r in affected
    )

    target_before = float(
        target["total_expected_production_kg"]
    )

    failed_target = sum(
        r["expected_production_kg"]
        for r in affected
        if r["crop"] == target_crop
    )

    target_after = max(
        0.0,
        target_before - failed_target,
    )

    target_loss_fraction = (
        failed_target / target_before
        if target_before > 0
        else 0.0
    )

    return {
        "available": True,
        "selection_rule": (
            "active crop with maximum pre-shock "
            "largest-producer share; lexical tie-break"
        ),
        "shock_type": "N-1_largest_producer",
        "target_crop": target_crop,
        "failed_farmer": failed_farmer,
        "pre_shock_largest_producer_share":
            target["largest_producer_share"],

        # All allocations of the failed farmer disappear.
        "affected_allocations": len(affected),
        "failed_plot_ids": sorted(
            r["plot_id"]
            for r in affected
        ),
        "failed_area_ha": round(
            failed_area, 3
        ),
        "failed_expected_production_kg":
            round(failed_all_prod, 1),

        # Target-crop production effect.
        "target_production_before_kg":
            round(target_before, 1),
        "failed_target_production_kg":
            round(failed_target, 1),
        "target_production_after_immediate_kg":
            round(target_after, 1),
        "target_loss_fraction": round(
            target_loss_fraction, 6
        ),

        # Economic exposure.
        "total_expected_cash_before":
            round(total_cash, 0),
        "immediate_expected_cash_loss":
            round(cash_loss, 0),
        "immediate_remaining_expected_cash":
            round(total_cash - cash_loss, 0),
        "cash_loss_fraction": (
            round(cash_loss / total_cash, 6)
            if total_cash
            else None
        ),

        "counterfactual": True,
        "reoptimization": False,
        "recovery_realised": False,
    }


def _hazard_zone_row(records, zone):
    affected = [
        r for r in records
        if r["hazard_zone"] == zone
    ]

    total_cash = sum(
        r["final_cash"]
        for r in records
    )

    cash_loss = sum(
        r["final_cash"]
        for r in affected
    )

    area_loss = sum(
        r["area_ha"]
        for r in affected
    )

    prod_loss = sum(
        r["expected_production_kg"]
        for r in affected
    )

    return {
        "zone": zone,
        "affected_allocations": len(affected),
        "affected_plot_ids": sorted(
            r["plot_id"]
            for r in affected
        ),
        "affected_area_ha": round(
            area_loss, 3
        ),
        "affected_expected_production_kg":
            round(prod_loss, 1),
        "total_expected_cash_before":
            round(total_cash, 0),
        "immediate_expected_cash_loss":
            round(cash_loss, 0),
        "immediate_remaining_expected_cash":
            round(total_cash - cash_loss, 0),
        "cash_loss_fraction": (
            round(cash_loss / total_cash, 6)
            if total_cash
            else None
        ),
        "counterfactual": True,
        "reoptimization": False,
        "recovery_realised": False,
    }


def _hazard(records):
    zones = sorted({
        r["hazard_zone"]
        for r in records
    })

    if not zones:
        return {
            "available": False,
            "reason": (
                "No realised hazard zone exists "
                "in the current plan."
            ),
        }

    rows = [
        _hazard_zone_row(records, z)
        for z in zones
    ]

    representative = dict(rows[0])

    representative.update({
        "available": True,
        "selection_rule": (
            "lexicographically first non-empty "
            "hazard zone in the realised plan"
        ),
        "shock_type": "hazard_zone_outage",
    })

    return {
        "available": True,
        "representative": representative,

        # Read-only complete immediate-exposure table.
        # No additional selection or optimisation occurs.
        "all_realised_zones": rows,
        "n_realised_zones": len(rows),
    }


def analyse_fixed_final_plan(
    allocations,
    plots_by_id,
    *,
    dataset_hash=None,
    final_plan_revision=None,
):
    """
    Evaluate immediate resilience exposure of an exact final realised plan.

    No planning decision is changed and no recovery plan is produced.
    """
    _require_operational_data()

    allocations = list(
        allocations or []
    )

    if not allocations:
        return {
            "available": False,
            "protocol_version": PROTOCOL_VERSION,
            "reason": (
                "No realised allocations exist "
                "in the current final plan."
            ),
        }

    records, missing = _records(
        allocations,
        plots_by_id,
    )

    if missing:
        return {
            "available": False,
            "protocol_version": PROTOCOL_VERSION,
            "reason": (
                "Required inputs are missing for "
                "interactive resilience analysis."
            ),
            "missing": missing,
        }

    plan_hash = final_plan_hash(
        allocations
    )

    crop_stats = _crop_concentration(
        records
    )

    n1 = _nminus1(
        records,
        crop_stats,
    )

    hazard = _hazard(
        records
    )

    total_cash = sum(
        r["final_cash"]
        for r in records
    )

    total_area = sum(
        r["area_ha"]
        for r in records
    )

    return {
        "available": (
            n1.get("available", False)
            and hazard.get("available", False)
        ),
        "protocol_version": PROTOCOL_VERSION,
        "method": (
            "deterministic_immediate_exposure_"
            "fixed_final_realised"
        ),
        "deterministic": True,
        "allocation_policy": "fixed-final-realised",
        "reoptimization": False,
        "backup_optimiser": False,
        "new_consent": False,
        "counterfactual": True,

        "dataset_hash": dataset_hash,
        "final_plan_revision":
            final_plan_revision,
        "final_plan_hash": plan_hash,

        "baseline": {
            "n_realised_plots":
                len(records),
            "realised_area_ha":
                round(total_area, 3),
            "expected_cash_net_return":
                round(total_cash, 0),
            "n_active_crops":
                len(crop_stats),
            "n_realised_hazard_zones":
                len({
                    r["hazard_zone"]
                    for r in records
                }),
        },

        "crop_producer_concentration":
            crop_stats,

        "nminus1_representative":
            n1,

        "hazard_zone_outage":
            hazard,

        "post_shock_recovery": {
            "available": False,
            "reason":
                POST_SHOCK_RECOVERY_MESSAGE,
        },

        "interpretation": (
            "Immediate exposure of the exact current "
            "FINAL_REALIZED allocation. Failed farmers "
            "or hazard-zone plots are treated as physically "
            "unavailable. No crop is reassigned and no "
            "counterfactual backup plan is presented as "
            "realised recovery."
        ),
    }
