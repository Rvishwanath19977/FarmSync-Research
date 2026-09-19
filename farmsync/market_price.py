"""
Phase 5i — market prices (operational) with a documented aggregation protocol.

This module separates the OPERATIONAL market price used in final return calculations
from the MSP policy floor (which stays in crop_economics.py as a labelled reference).
MSP is never called the observed market price.

AGGREGATION PROTOCOL (documented, to be applied when AGMARKNET series are ingested):
  * Window: trailing 3 marketing years of monthly modal prices.
  * Mandi/state selection: principal producing state's main APMC(s) for the crop,
    mapped to the FarmSync region via REGION_STATE.
  * Central tendency: season median of monthly modal prices (robust to spikes).
  * Outliers: drop observations beyond 3x IQR before taking the median.
  * Missing observations: carry-forward last valid month; flag if >30% missing.
  * Units: AGMARKNET Rs/quintal -> Rs/kg (÷100).

STATUS: rigorous per-crop x region AGMARKNET ingestion is not yet performed (the
bulk series are not machine-fetchable here). Representative annual market prices are
recorded ONLY for the vegetables (where MSP does not exist), at LOW confidence, so
their gap is visible; grain/pulse/oilseed operational market prices remain an
explicit AGMARKNET obligation, with MSP available as the labelled reference anchor.
"""

from __future__ import annotations

from .provenance import ProvenanceRecord, ProvenanceType, Confidence

AGG_PROTOCOL = {
    "window": "trailing 3 marketing years, monthly modal prices",
    "mandi_selection": "principal producing state APMC(s), mapped to region via REGION_STATE",
    "central_tendency": "season median of monthly modal prices",
    "outliers": "drop beyond 3x IQR before median",
    "missing": "carry-forward last valid month; flag if >30% missing",
    "units": "AGMARKNET Rs/quintal -> Rs/kg (÷100)",
}

# Representative operational market prices (Rs/kg). Only vegetables populated
# (no MSP exists for them); LOW confidence, clearly provisional pending AGMARKNET.
MARKET_PRICE = {
    "onion":  {"price_per_kg": 18.0, "confidence": "LOW",
               "source": "Representative wholesale annual average (pending AGMARKNET series)"},
    "tomato": {"price_per_kg": 15.0, "confidence": "LOW",
               "source": "Representative wholesale annual average (pending AGMARKNET series)"},
    "potato": {"price_per_kg": 11.0, "confidence": "LOW",
               "source": "Representative wholesale annual average (pending AGMARKNET series)"},
}


def market_price(crop_name: str):
    entry = MARKET_PRICE.get(crop_name)
    return entry["price_per_kg"] if entry else None


def market_price_provenance() -> list:
    recs = [ProvenanceRecord(
        parameter="market.aggregation_protocol", provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
        value="; ".join(f"{k}={v}" for k, v in AGG_PROTOCOL.items()), unit="protocol",
        source="AGMARKNET methodology (documented)", source_url="https://agmarknet.gov.in/",
        assumption="Protocol defined; per-crop×region series not yet ingested (not machine-fetchable here).",
        confidence=Confidence.MEDIUM,
        notes="MSP remains a labelled policy-floor reference, never the observed market price.")]
    for crop, e in MARKET_PRICE.items():
        recs.append(ProvenanceRecord(
            parameter="crop.market_price_per_kg", provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
            crop=crop, value=str(e["price_per_kg"]), unit="INR/kg",
            source=e["source"], source_url="https://agmarknet.gov.in/",
            assumption="Representative wholesale annual average; provisional pending AGMARKNET "
                       "series under the documented protocol.",
            confidence=Confidence.LOW,
            notes="Vegetables have no MSP; this is the operational price. Refine with AGMARKNET."))
    # explicit obligation: operational market prices for MSP crops
    recs.append(ProvenanceRecord(
        parameter="crop.market_price_per_kg", provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
        unit="INR/kg", confidence=Confidence.REQUIRES_SOURCING,
        notes="Grain/pulse/oilseed operational market prices via AGMARKNET (documented protocol) "
              "remain to be ingested for the FINAL experiment; MSP is the reference anchor meanwhile."))
    return recs
