"""
Phase 5d — crop price + cost anchors from authoritative Government of India sources.

PRICES: Minimum Support Prices (MSP), recommended by CACP and approved by the
Cabinet (CCEA). Recorded as OBSERVED with citation.

CRITICAL LABELLING (per project integrity rules):
  * MSP is a NATIONAL POLICY FLOOR, not the market price and not demand. It is
    stored as `msp_floor_per_kg`, never silently as "the price". Region-specific
    market prices (AGMARKNET modal, with a documented aggregation rule) remain a
    separate open obligation. Using MSP as a national floor with explicit scope
    is not "reusing one region's value for another" — it carries no regional claim.

COSTS: The MSP tables publish a CACP cost of production per quintal. The kharif
table reports A2+FL; the rabi note reports C2. These bases differ and MUST NOT be
mixed. They are stored with an explicit `cost_basis`. Cultivation cost per hectare
is DERIVED = cost_per_quintal x yield_q_per_ha, so it stays pending sourced yield
on a consistent basis; it is not fabricated here.

SOURCES
  Kharif MSP (KMS 2025-26): PIB PRID 2131983 (CCEA, 28 May 2025).
    https://www.pib.gov.in/PressReleasePage.aspx?PRID=2131983
  Rabi MSP (RMS 2026-27): PIB PRID 2173567 (CCEA, 01 Oct 2025).
    https://www.pib.gov.in/PressReleasePage.aspx?PRID=2173567
  Rabi C2 costs: CACP price policy (via farmingcosmos summary of CACP RMS 2026-27).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .provenance import ProvenanceRecord, ProvenanceType, Confidence

KHARIF_SRC = "CACP/CCEA MSP, Kharif Marketing Season 2025-26 (PIB PRID 2131983)"
KHARIF_URL = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2131983"
RABI_SRC = "CACP/CCEA MSP, Rabi Marketing Season 2026-27 (PIB PRID 2173567)"
RABI_URL = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2173567"
ACCESS_DATE = "2026-08-13"


@dataclass
class CropPrice:
    crop_name: str
    msp_floor_per_kg: Optional[float]     # None = no MSP (vegetables)
    season_marketing: str                 # marketing season the MSP applies to
    source: Optional[str]
    source_url: Optional[str]
    cost_per_quintal: Optional[float] = None   # CACP cost of production
    cost_basis: Optional[str] = None           # "A2+FL" | "C2"
    note: str = ""


# MSP in Rs/quintal -> Rs/kg (divide by 100). Values transcribed from PIB tables.
CROP_PRICE = {
    # Kharif (KMS 2025-26), A2+FL cost per quintal from same PIB table
    "rice":         CropPrice("rice", 23.69, "KMS 2025-26", KHARIF_SRC, KHARIF_URL, 1579, "A2+FL", "Paddy Common"),
    "maize":        CropPrice("maize", 24.00, "KMS 2025-26", KHARIF_SRC, KHARIF_URL, 1508, "A2+FL"),
    "sorghum":      CropPrice("sorghum", 36.99, "KMS 2025-26", KHARIF_SRC, KHARIF_URL, 2466, "A2+FL", "Jowar Hybrid"),
    "pearl_millet": CropPrice("pearl_millet", 27.75, "KMS 2025-26", KHARIF_SRC, KHARIF_URL, 1703, "A2+FL", "Bajra"),
    "pigeon_pea":   CropPrice("pigeon_pea", 80.00, "KMS 2025-26", KHARIF_SRC, KHARIF_URL, 5038, "A2+FL", "Tur/Arhar"),
    "groundnut":    CropPrice("groundnut", 72.63, "KMS 2025-26", KHARIF_SRC, KHARIF_URL, 4842, "A2+FL"),
    "soybean":      CropPrice("soybean", 53.28, "KMS 2025-26", KHARIF_SRC, KHARIF_URL, 3552, "A2+FL", "Soybean Yellow"),
    "cotton":       CropPrice("cotton", 77.10, "KMS 2025-26", KHARIF_SRC, KHARIF_URL, 5140, "A2+FL", "Medium Staple"),
    # Rabi (RMS 2026-27); C2 cost per quintal where available (different basis!)
    "wheat":        CropPrice("wheat", 25.85, "RMS 2026-27", RABI_SRC, RABI_URL, 1804, "C2"),
    "chickpea":     CropPrice("chickpea", 58.75, "RMS 2026-27", RABI_SRC, RABI_URL, 5243, "C2", "Gram"),
    "mustard":      CropPrice("mustard", 62.00, "RMS 2026-27", RABI_SRC, RABI_URL, 4294, "C2", "Rapeseed & Mustard; C2 cost RMS 2025-26 (CACP)"),
    # Vegetables — no MSP; require AGMARKNET mandi-derived price
    "potato":       CropPrice("potato", None, "-", None, None, None, None, "No MSP; AGMARKNET modal price required"),
    "onion":        CropPrice("onion", None, "-", None, None, None, None, "No MSP; AGMARKNET modal price required"),
    "tomato":       CropPrice("tomato", None, "-", None, None, None, None, "No MSP; AGMARKNET modal price required"),
}


def crop_economics_provenance() -> list:
    records = []
    for name, p in CROP_PRICE.items():
        if p.msp_floor_per_kg is not None:
            records.append(ProvenanceRecord(
                parameter="crop.msp_floor_per_kg", provenance_type=ProvenanceType.OBSERVED,
                crop=name, value=str(p.msp_floor_per_kg), unit="INR/kg",
                source=p.source, source_url=p.source_url, source_year=2025,
                transformation="MSP Rs/quintal / 100",
                assumption=None, confidence=Confidence.HIGH,
                notes=(f"{p.note}. MSP is a NATIONAL POLICY FLOOR ({p.season_marketing}), "
                       f"not the market price and not demand. Region-specific AGMARKNET "
                       f"market price remains a separate obligation. Access {ACCESS_DATE}."),
            ))
        else:
            records.append(ProvenanceRecord(
                parameter="crop.price_per_kg", provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
                crop=name, unit="INR/kg", confidence=Confidence.REQUIRES_SOURCING,
                notes=f"{p.note}. Derive from AGMARKNET modal prices with a documented aggregation rule.",
            ))
        # cost anchor
        if p.cost_per_quintal is not None:
            records.append(ProvenanceRecord(
                parameter="crop.cost_per_quintal", provenance_type=ProvenanceType.OBSERVED,
                crop=name, value=str(p.cost_per_quintal), unit=f"INR/quintal ({p.cost_basis})",
                source=p.source, source_url=p.source_url, source_year=2025,
                assumption=None, confidence=Confidence.HIGH,
                notes=(f"CACP cost of production, basis {p.cost_basis}. Bases differ across "
                       f"seasons (kharif A2+FL vs rabi C2) and MUST NOT be mixed. "
                       f"cultivation_cost/ha = cost_per_quintal x yield_q_per_ha (DERIVED, "
                       f"pending consistent-basis yield)."),
            ))
    # remaining cost/ha obligation
    records.append(ProvenanceRecord(
        parameter="crop.cultivation_cost_per_ha", provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
        unit="INR/ha", confidence=Confidence.REQUIRES_SOURCING,
        notes=("Will be DERIVED as cost_per_quintal x yield_q_per_ha once yield is sourced on a "
               "consistent CACP basis; not fabricated. Prefer DES Cost of Cultivation "
               "(A2+FL or C2, stated) over deriving from MSP cost."),
    ))
    return records


def price_summary() -> dict:
    have = {k: v.msp_floor_per_kg for k, v in CROP_PRICE.items() if v.msp_floor_per_kg is not None}
    need = [k for k, v in CROP_PRICE.items() if v.msp_floor_per_kg is None]
    return {"msp_anchored": have, "price_requires_sourcing": need}
