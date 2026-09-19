"""
Phase 5b — economic + market + sensitivity parameter scaffold.

These parameters are NOT populated from memory. Each is registered as an open
sourcing obligation with a concrete, documented plan naming the authoritative
source and the derivation rule to apply. The feasibility engine (Phase 6) and
optimiser (Phase 8) must refuse to treat any REQUIRES_SOURCING parameter as a
valid input until it is filled and its confidence upgraded.

Source hierarchy (as directed):
  1. GoI Directorate of Economics & Statistics (DES) — area/production/yield
  2. AGMARKNET — mandi price & arrivals (arrivals != demand)
  3. ICAR & institutes — agronomic practice, sensitivities, water
  4. FAO-56 / CROPWAT — evapotranspiration & crop water requirement
  5. IMD — climatic inputs
  6. Peer-reviewed literature — where a government value is unavailable
"""

from __future__ import annotations

from .provenance import ProvenanceRecord, ProvenanceType, Confidence

# crop_name -> parameter -> (unit, planned_source, derivation_rule)
SOURCING_PLAN = {
    "expected_yield": (
        "kg/ha",
        "GoI DES — Agricultural Statistics at a Glance / district-season yield",
        "Use district- or state-and-season-specific yield where available; do NOT "
        "fall back to national yield when finer data exists. Record year + geography.",
    ),
    "cultivation_cost": (
        "currency/ha",
        "GoI DES — Cost of Cultivation / Cultivation Practices surveys (CACP CoC)",
        "Use paid-out cost (A2) or A2+FL per study design; state which. State/season specific.",
    ),
    "price": (
        "currency/kg",
        "AGMARKNET modal mandi price (MSP from CACP for MSP-notified crops as a floor anchor)",
        "Derive representative price from historical modal prices via a documented "
        "aggregation rule (e.g. season-median of monthly modal prices over N years, "
        "specified market set). Do NOT invent from a range. For MSP crops, record MSP "
        "separately as a policy floor, not as the market price.",
    ),
    "price_variability": (
        "coefficient of variation",
        "AGMARKNET price series",
        "CV of the same aggregated price series used for `price`. Document window.",
    ),
    "market_absorption_proxy": (
        "index (labelled proxy)",
        "AGMARKNET arrivals + processing/consumption studies",
        "EXPLICITLY a proxy for market-clearing capacity, NOT demand. Derive from "
        "arrivals capacity with a documented transformation; never label arrivals 'demand'.",
    ),
    "labour_requirement": (
        "person-days/ha",
        "ICAR / SAU package-of-practices; DES CoC labour component",
        "Crop-and-operation specific; state/season where available.",
    ),
    "drought_sensitivity": (
        "yield-response index",
        "ICAR / peer-reviewed water-stress response (FAO-33 Ky as fallback)",
        "Prefer crop-specific Ky (yield response factor) from FAO-33 or ICAR trials. "
        "If defensible crop-specific values are unavailable, represent the shock via "
        "documented experimental scenario parameters + sensitivity analysis rather "
        "than pretending a coefficient is observed. (spec directive)",
    ),
    "heat_sensitivity": (
        "yield-response index",
        "ICAR / peer-reviewed heat-stress studies",
        "Same rule as drought_sensitivity: sourced Ky-style value, or explicit "
        "experimental scenario parameter — never a fabricated observed coefficient.",
    ),
    "waterlogging_sensitivity": (
        "yield-response index",
        "ICAR / peer-reviewed waterlogging studies",
        "Same rule; many crops lack defensible values -> likely scenario parameter.",
    ),
}


def economic_parameter_provenance(crop_names) -> list:
    """Register every (crop x economic/sensitivity parameter) as an open obligation."""
    records = []
    for crop in crop_names:
        for param, (unit, source_plan, rule) in SOURCING_PLAN.items():
            records.append(ProvenanceRecord(
                parameter=f"crop.{param}",
                provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
                crop=crop, unit=unit,
                confidence=Confidence.REQUIRES_SOURCING,
                notes=f"PLANNED SOURCE: {source_plan}. DERIVATION: {rule}",
            ))
    return records
