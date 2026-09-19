"""
Phase 5h — market absorption proxy + climate/yield sensitivities.

market_absorption_proxy: an explicitly-labelled PROXY for market-clearing capacity,
derived from relative national production/throughput. It is NOT observed demand and
is never treated as such (project integrity rule). Higher proxy = a crop the market
absorbs in larger volume; used only to penalise oversupply relative to typical
throughput, not to assert a demand quantity.

Climate/yield sensitivities: FAO Irrigation & Drainage Paper 33 seasonal yield
response factor Ky (fractional yield loss per fractional ET deficit) where a value
exists; otherwise an explicit experimental scenario parameter. Both are used as
experimental sensitivity parameters, not asserted as observed crop coefficients.
"""

from __future__ import annotations

from .provenance import ProvenanceRecord, ProvenanceType, Confidence

# Relative absorption proxy (0-1), from approximate national production share/throughput
# ordering. Documented proxy, NOT demand. Staples absorb high volume; vegetables lower.
MARKET_ABSORPTION_PROXY = {
    "rice": 1.00, "wheat": 0.95, "maize": 0.70, "sorghum": 0.45, "pearl_millet": 0.40,
    "chickpea": 0.55, "pigeon_pea": 0.45, "groundnut": 0.55, "soybean": 0.65,
    "mustard": 0.60, "cotton": 0.75, "potato": 0.70, "onion": 0.65, "tomato": 0.60,
}

# FAO-33 seasonal yield response factor Ky (whole growing period) where published;
# else None -> handled as an experimental scenario parameter.
FAO33_KY = {
    "rice": 1.09, "wheat": 1.05, "maize": 1.25, "sorghum": 0.90, "groundnut": 0.70,
    "soybean": 0.85, "cotton": 0.85, "potato": 1.10, "onion": 1.10, "tomato": 1.05,
    # not in FAO-33 core table -> experimental
    "pearl_millet": None, "chickpea": None, "pigeon_pea": None, "mustard": None,
}


def absorption_proxy(crop_name: str):
    return MARKET_ABSORPTION_PROXY.get(crop_name)


def yield_sensitivity_ky(crop_name: str):
    """Returns (ky, kind) where kind is 'FAO33' or 'EXPERIMENTAL'."""
    ky = FAO33_KY.get(crop_name)
    if ky is not None:
        return ky, "FAO33"
    return 1.0, "EXPERIMENTAL"     # neutral default, varied in sensitivity analysis


def market_provenance() -> list:
    recs = [
        ProvenanceRecord(
            parameter="crop.market_absorption_proxy", provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
            value="per-crop 0-1 index", unit="index",
            source="Relative national production/throughput ordering (DES production statistics)",
            source_url="https://www.indiabudget.gov.in/economicsurvey/",
            transformation="Normalised relative throughput ordering",
            assumption="Index values are judgement-assigned from national production ordering, NOT "
                       "computed from mandi arrivals. A PROXY for market-clearing capacity, explicitly "
                       "NOT observed demand; used only to penalise oversupply vs typical throughput.",
            confidence=Confidence.LOW,
            notes="This is a proxy, NOT demand and NOT observed. Never call it demand. "
                  "Refine with AGMARKNET arrivals + processing capacity."),
    ]
    for crop, ky in FAO33_KY.items():
        if ky is not None:
            recs.append(ProvenanceRecord(
                parameter="crop.yield_response_factor_ky", provenance_type=ProvenanceType.OBSERVED,
                crop=crop, value=str(ky), unit="Ky (dimensionless)",
                source="FAO Irrigation & Drainage Paper 33 (Doorenbos & Kassam, 1979)",
                source_url="https://www.fao.org/3/x5648e/x5648e00.htm", source_year=1979,
                confidence=Confidence.MEDIUM,
                notes="Seasonal yield response to water deficit; used as a sensitivity parameter."))
        else:
            recs.append(ProvenanceRecord(
                parameter="crop.yield_response_factor_ky", provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
                crop=crop, unit="Ky (dimensionless)", confidence=Confidence.REQUIRES_SOURCING,
                notes="No FAO-33 Ky; handled as an experimental scenario parameter (default 1.0), "
                      "varied in sensitivity analysis per project directive."))
    return recs
