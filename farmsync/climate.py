"""
Phase 5c — regional reference evapotranspiration (ET0) and crop water requirement.

ET0 per region/season is sourced from published FAO-56 Penman-Monteith studies for
representative Indian stations and mapped to the five synthetic regions. Crop water
requirement (CWR) is then computed by the FAO-56 Kc method already implemented in
crop_water.py — nothing is hard-coded per crop.

SOURCES
  R1 Indo-Gangetic (Ludhiana / central Punjab):
     Punjab FAO-PM ET0 study — seasonal ~755 mm kharif, ~490 mm rabi
     (ScienceDirect S2666154323001473, 2023). kharif~6.2, rabi~4.1 mm/day.
  R2 Deccan (Parbhani, Maharashtra):
     Phad, Dakhore & Sayyad (2020), MAUSAM 71(1):145-148, IMD (Govt. of India).
     kharif mean 6.23 mm/day, rabi mean 4.29 mm/day.  [HIGH confidence]
     https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/13/14/61
  R3 Eastern (Patna, Bihar): annual mean 4.1 mm/day (J. Agrometeorology, Bihar).
     Seasonal kharif/rabi split NOT yet extracted -> left open, anchor recorded.
  R4 Semi-arid West, R5 Southern Peninsula: NOT yet sourced -> REQUIRES_SOURCING.

DOCUMENTED SIMPLIFICATION
  Where only a seasonal MEAN daily ET0 is available (not stage-resolved), the same
  ET0 is applied across all four crop stages. This is a first-order estimate; the
  Kc curve still varies by stage. Flagged in provenance. Refined stage-resolved ET0
  (monthly IMD/CROPWAT) is a later obligation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .crop_water import CROP_WATER
from .provenance import ProvenanceRecord, ProvenanceType, Confidence


@dataclass
class RegionET0:
    region_id: str
    kharif_mm_day: Optional[float]
    rabi_mm_day: Optional[float]
    source: Optional[str]
    source_url: Optional[str]
    source_year: Optional[int]
    confidence: str
    note: str = ""
    station_based: bool = True     # True = OBSERVED station value; False = SYNTHETIC_GROUNDED characterisation


REGION_ET0 = {
    "R1": RegionET0("R1", 6.2, 4.1,
                    "Central Punjab (Ludhiana) FAO-PM ET0 study",
                    "https://www.sciencedirect.com/science/article/pii/S2666154323001473",
                    2023, "MEDIUM",
                    "Seasonal ~755 mm kharif / ~490 mm rabi; FAO-PM as standard. Divided by season length."),
    "R2": RegionET0("R2", 6.23, 4.29,
                    "Phad et al. (2020) MAUSAM 71(1), IMD (Govt. of India), Parbhani",
                    "https://mausamjournal.imd.gov.in/index.php/MAUSAM/article/download/13/14/61",
                    2020, "HIGH",
                    "Directly reported seasonal mean daily ET0 (kharif 6.23, rabi 4.29)."),
    "R3": RegionET0("R3", 4.2, 3.5,
                    "Rao et al. ET0 over India (Penman-Monteith spatial characterisation); "
                    "Bihar/Patna annual 4.1 mm/day supporting anchor",
                    "https://www.researchgate.net/publication/293484465",
                    2012, "LOW",
                    "Humid eastern India: lower ET0. Regional characterisation (kharif monsoon-"
                    "suppressed, rabi cool), NOT a station seasonal mean; refine with a WB station.",
                    station_based=False),
    "R4": RegionET0("R4", 6.5, 4.5,
                    "Rao et al. ET0 over India (southern Rajasthan among highest, summer 7-13 "
                    "mm/day); arid-Rajasthan CWR studies supporting",
                    "https://www.researchgate.net/publication/293484465",
                    2012, "MEDIUM",
                    "Semi-arid west: high ET0. Regional characterisation, not a station seasonal "
                    "mean; refine with a Rajasthan (e.g. Bikaner/Jodhpur) station.",
                    station_based=False),
    "R5": RegionET0("R5", 5.0, 4.3,
                    "Rao et al. ET0 over India (western Karnataka 5-6 mm/day)",
                    "https://www.researchgate.net/publication/293484465",
                    2012, "LOW",
                    "Southern peninsula: moderate ET0. Regional characterisation, not a station "
                    "seasonal mean; refine with a Karnataka station.",
                    station_based=False),
}


# --- scoped weather (ET0) override for uncertainty-v1 -----------------------------------------
# Read-time multiplier keyed (region_id, season). Default empty => multiplier 1.0 (no perturbation).
# The baseline REGION_ET0 values are never mutated; the multiplier is applied at read and cleared
# by the uncertainty context (try/finally), guaranteeing UJ->U0 isolation.
_ET0_MULT = {}


def set_et0_mult(mult_by_region_season):
    _ET0_MULT.clear(); _ET0_MULT.update(mult_by_region_season)


def clear_et0_mult():
    _ET0_MULT.clear()


def _et0_for(region_id: str, season: str) -> Optional[float]:
    r = REGION_ET0.get(region_id)
    if not r:
        return None
    base = r.kharif_mm_day if season == "kharif" else r.rabi_mm_day
    if base is None:
        return None
    m = _ET0_MULT.get((region_id, season), 1.0)
    return base * m


# --------------------------------------------------------------------------- #
# Effective rainfall + net irrigation requirement (water balance)
# --------------------------------------------------------------------------- #
# Seasonal rainfall (mm). All-India SW-monsoon LPA (868.6 mm) and the East & NE
# subdivision normal (1367.3 mm) are IMD-sourced; per-state seasonal values are
# representative figures from IMD climatology (SYNTHETIC_GROUNDED). Rabi rainfall
# is small (western disturbances in the north, NE monsoon in the south).
RAINFALL_SRC = "IMD seasonal rainfall climatology (all-India LPA 868.6 mm; East&NE subdivision 1367.3 mm)"
RAINFALL_URL = "https://mausam.imd.gov.in/responsive/rainfall_statistics.php"

REGION_RAINFALL = {   # region: (kharif_mm, rabi_mm, confidence)
    "R1": (460, 100, "MEDIUM"),   # Punjab: low monsoon, winter western disturbances
    "R2": (700, 60, "MEDIUM"),    # Deccan/Marathwada interior
    "R3": (1200, 100, "MEDIUM"),  # West Bengal (East & NE subdivision, high)
    "R4": (400, 30, "MEDIUM"),    # semi-arid Rajasthan
    "R5": (600, 150, "LOW"),      # interior Karnataka + NE monsoon in rabi
}

# FAO effective-rainfall fraction (documented simplification of FAO/USDA method):
# high-intensity monsoon rainfall has more runoff/percolation loss than gentler
# rabi rain. Experimental parameter, sensitivity-tested.
RAINFALL_EFFECTIVENESS = {"kharif": 0.75, "rabi": 0.80}


def effective_rainfall_mm(region_id: str, season: str) -> Optional[float]:
    rf = REGION_RAINFALL.get(region_id)
    if not rf:
        return None
    total = rf[0] if season == "kharif" else rf[1]
    return round(total * RAINFALL_EFFECTIVENESS[season], 1)


def net_irrigation_requirement_mm(crop_name: str, region_id: str, season: str) -> Optional[float]:
    """NIR = max(0, CWR - effective rainfall). None if CWR or rainfall unavailable."""
    cwr = compute_crop_water_requirements(region_id, season)
    if cwr.get("_status") != "OK" or crop_name not in cwr:
        return None
    eff = effective_rainfall_mm(region_id, season)
    if eff is None:
        return None
    return round(max(0.0, cwr[crop_name] - eff), 1)


def rainfall_provenance() -> list:
    from .provenance import ProvenanceRecord, ProvenanceType, Confidence
    recs = []
    for rid, (kh, ra, conf) in REGION_RAINFALL.items():
        recs.append(ProvenanceRecord(
            parameter="climate.seasonal_rainfall", provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
            region=rid, value=f"kharif {kh}, rabi {ra}", unit="mm",
            source=RAINFALL_SRC, source_url=RAINFALL_URL, source_year=2020,
            assumption="Representative state seasonal rainfall from IMD climatology; "
                       "all-India LPA and East&NE subdivision normal are IMD-sourced anchors.",
            confidence=Confidence[conf], notes="Refine with IMD district/subdivision normals."))
    recs.append(ProvenanceRecord(
        parameter="climate.rainfall_effectiveness", provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
        value="kharif 0.75, rabi 0.80", unit="fraction", confidence=Confidence.REQUIRES_SOURCING,
        notes="FAO/USDA effective-rainfall fraction, simplified to a fixed ratio; "
              "experimental parameter for sensitivity analysis."))
    return recs


def compute_crop_water_requirements(region_id: str, season: str) -> dict:
    """
    CWR (mm) for each crop grown in `season` in `region_id`, via FAO-56 Kc method.
    Returns {} with a reason if the region's ET0 for that season is not sourced.
    Uniform seasonal ET0 across stages (documented simplification).
    """
    et0 = _et0_for(region_id, season)
    if et0 is None:
        return {"_status": "ET0_NOT_SOURCED",
                "_reason": f"{region_id}/{season} ET0 is REQUIRES_SOURCING; CWR not computed."}
    et0_by_stage = {k: et0 for k in ("init", "dev", "mid", "late")}
    out = {"_status": "OK", "_et0_mm_day": et0}
    for name, cw in CROP_WATER.items():
        crop = next((c for c in _crop_seasons() if c[0] == name), None)
        if crop and season in crop[1]:
            out[name] = cw.crop_water_requirement_mm(et0_by_stage)
    return out


def _crop_seasons():
    """(crop_name, [season,...]) — read from the schemas crop list."""
    from .generate import CROPS
    return [(c.crop_name, c.seasons) for c in CROPS]


def region_et0_provenance() -> list:
    records = []
    for r in REGION_ET0.values():
        if r.confidence == "REQUIRES_SOURCING":
            records.append(ProvenanceRecord(
                parameter="climate.ET0_seasonal", provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
                region=r.region_id, unit="mm/day", confidence=Confidence.REQUIRES_SOURCING,
                notes=r.note,
            ))
        else:
            ptype = (ProvenanceType.OBSERVED if r.station_based
                     else ProvenanceType.SYNTHETIC_GROUNDED)
            records.append(ProvenanceRecord(
                parameter="climate.ET0_seasonal", provenance_type=ptype,
                region=r.region_id, unit="mm/day",
                value=f"kharif {r.kharif_mm_day}, rabi {r.rabi_mm_day}",
                source=r.source, source_url=r.source_url, source_year=r.source_year,
                confidence=Confidence[r.confidence] if r.confidence in Confidence.__members__ else Confidence.MEDIUM,
                transformation="Seasonal totals divided by season length where reported as totals",
                assumption=(None if r.station_based else
                            "Regional ET0 interpolated from a published all-India ET0 spatial "
                            "characterisation; not a station seasonal mean."),
                notes=r.note,
            ))
    # CWR derivation record
    records.append(ProvenanceRecord(
        parameter="crop.crop_water_requirement", provenance_type=ProvenanceType.DERIVED,
        unit="mm/season",
        source="FAO-56 Kc method (crop_water.py) x regional ET0 (this module)",
        source_url="https://www.fao.org/4/x0490e/x0490e0b.htm",
        source_year=1998,
        transformation="CWR = sum_stages(Kc_stage * ET0 * stage_days); uniform seasonal ET0 across stages",
        assumption="Stage-uniform ET0 pending monthly IMD/CROPWAT stage-resolved values",
        confidence=Confidence.MEDIUM,
        notes="Computed for all five regions; R1/R2 station-based, R3-R5 characterisation-based.",
    ))
    return records
