"""
Phase 5 sourcing report (as required before values enter the optimiser).

Produces a single report showing, per crop and parameter: value/range, unit,
provenance class, source, derivation, confidence, and any unresolved gap. Grounded
water/duration parameters and open economic/sensitivity obligations are shown
together so a reviewer can see exactly what rests on a citation and what does not.
"""

from __future__ import annotations

import csv
import io
import json

from .crop_water import CROP_WATER, crop_water_provenance, FAO56_SOURCE, FAO56_URL
from .parameters import economic_parameter_provenance
from .climate import region_et0_provenance, REGION_ET0, compute_crop_water_requirements
from .crop_economics import crop_economics_provenance, CROP_PRICE, price_summary
from .crop_yield import crop_yield_provenance, CROP_YIELD, yield_summary
from .provenance import ProvenanceRegistry, Confidence


def build_phase5_registry(crop_names) -> ProvenanceRegistry:
    reg = ProvenanceRegistry()
    for r in crop_water_provenance():
        reg.add(r)
    for r in region_et0_provenance():
        reg.add(r)
    from .climate import rainfall_provenance
    for r in rainfall_provenance():
        reg.add(r)
    for r in crop_economics_provenance():
        reg.add(r)
    for r in crop_yield_provenance():
        reg.add(r)
    from .crop_agronomy import agronomy_provenance
    from .market import market_provenance
    from .market_price import market_price_provenance
    for r in agronomy_provenance():
        reg.add(r)
    for r in market_provenance():
        reg.add(r)
    for r in market_price_provenance():
        reg.add(r)
    for r in economic_parameter_provenance(crop_names):
        reg.add(r)
    return reg


def sourcing_report(crop_names) -> dict:
    reg = build_phase5_registry(crop_names)
    rows = reg.rows()
    grounded = [r for r in rows if r["confidence"] != Confidence.REQUIRES_SOURCING.value]
    open_obl = [r for r in rows if r["confidence"] == Confidence.REQUIRES_SOURCING.value]

    # per-crop readiness for the water block specifically
    water_ready = {
        name: {
            "kc": (cw.kc_ini, cw.kc_mid, cw.kc_end),
            "duration_days": cw.duration_days,
            "provenance": cw.provenance_type,
            "confidence": cw.confidence,
        }
        for name, cw in CROP_WATER.items()
    }

    # per-region ET0 + CWR readiness
    et0_coverage = {}
    for rid, r in REGION_ET0.items():
        kh = compute_crop_water_requirements(rid, "kharif")
        et0_coverage[rid] = {
            "kharif_mm_day": r.kharif_mm_day, "rabi_mm_day": r.rabi_mm_day,
            "confidence": r.confidence,
            "cwr_computed": kh.get("_status") == "OK",
            "source": r.source,
        }

    return {
        "phase": "5 — agricultural parameter sourcing",
        "primary_water_source": {"source": FAO56_SOURCE, "url": FAO56_URL},
        "summary": {
            "total_parameter_records": len(rows),
            "grounded_or_observed": len(grounded),
            "open_sourcing_obligations": len(open_obl),
            "crops_with_water_block": len(water_ready),
            "regions_with_sourced_et0": sum(
                1 for r in REGION_ET0.values() if r.kharif_mm_day is not None),
            "crops_with_msp_price": len(price_summary()["msp_anchored"]),
            "crops_price_requires_sourcing": price_summary()["price_requires_sourcing"],
            "crops_with_yield": len(yield_summary()["yield_sourced"]),
            "crops_yield_requires_sourcing": yield_summary()["yield_requires_sourcing"],
        },
        "water_and_duration_block": water_ready,
        "region_et0_coverage": et0_coverage,
        "open_obligations": [
            {"crop": r["crop"], "parameter": r["parameter"],
             "unit": r["unit"], "plan": r["notes"]}
            for r in open_obl
        ],
        "gate": {
            "optimiser_may_use_water_block": True,
            "optimiser_may_use_cwr_for_regions": [
                rid for rid, r in REGION_ET0.items() if r.kharif_mm_day is not None],
            "optimiser_may_use_economics": False,
            "reason": ("Economic/market/sensitivity parameters remain REQUIRES_SOURCING; "
                       "per integrity rules they must not enter the optimiser until sourced. "
                       "CWR is available only for regions with sourced ET0."),
        },
    }


def sourcing_report_csv(crop_names) -> str:
    reg = build_phase5_registry(crop_names)
    rows = reg.rows()
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def sourcing_report_json(crop_names) -> str:
    return json.dumps(sourcing_report(crop_names), indent=2)
