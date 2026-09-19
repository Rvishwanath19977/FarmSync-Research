"""
Phase 5a — crop water + growth-duration parameters, sourced from FAO-56.

PRIMARY SOURCE
  Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998).
  "Crop Evapotranspiration — Guidelines for computing crop water requirements."
  FAO Irrigation and Drainage Paper No. 56. FAO, Rome.
  Table 11 (stage lengths) and Table 12 (Kc ini / mid / end, crop height).
  URL: https://www.fao.org/4/x0490e/x0490e0b.htm   (accessed 2026-08-12)

WHAT IS GROUNDED HERE
  * Kc ini / mid / end and growth-stage lengths for crops listed in FAO-56 are
    recorded as OBSERVED (taken from the source, with citation).
  * Crops NOT in FAO-56 (e.g. pigeon pea) or mapped to a near relative
    (mustard -> rapeseed/canola) are recorded as SYNTHETIC_GROUNDED with the
    mapping stated as an explicit assumption.

WHAT IS DELIBERATELY NOT DONE HERE (integrity, spec sections 3 & 35)
  * Crop water requirement (CWR) is NOT hard-coded per region. FAO-56 method is
    CWR = sum_over_stages( Kc_stage * ET0_stage ). ET0 is region/season-specific
    and must come from IMD / CROPWAT (not yet sourced). `crop_water_requirement`
    is therefore computed on demand from a supplied ET0 and is refused (raises)
    if ET0 is absent — we never fabricate a single national CWR and copy it
    across regions.
  * Kc values are FAO-56 reference values for a sub-humid climate (RHmin ~45%,
    u2 ~2 m/s). Local adjustment (FAO-56 Eq. 62/65) needs RHmin/wind, also not
    yet sourced. Recorded as a documented limitation.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

from .provenance import (
    ProvenanceRecord, ProvenanceType, Confidence,
)

FAO56_SOURCE = "FAO Irrigation & Drainage Paper 56 (Allen et al. 1998), Tables 11-12"
FAO56_URL = "https://www.fao.org/4/x0490e/x0490e0b.htm"
FAO56_YEAR = 1998
ACCESS_DATE = "2026-08-12"


@dataclass
class CropWater:
    crop_name: str
    kc_ini: float
    kc_mid: float
    kc_end: float           # representative; ranges noted in `notes`
    height_m: float
    stage_days: tuple       # (init, dev, mid, late)
    duration_days: int
    provenance_type: str    # OBSERVED (in FAO-56) | SYNTHETIC_GROUNDED (mapped)
    confidence: str
    stage_region_note: str  # what region/planting the stage lengths came from
    notes: str = ""

    def crop_water_requirement_mm(self, et0_by_stage_mm_day):
        """
        FAO-56 CWR = sum_over_stages( Kc_stage * ET0_stage_total ).
        et0_by_stage_mm_day: dict with keys init/dev/mid/late giving mean daily
        ET0 (mm/day) for that stage, from an authoritative source (IMD/CROPWAT).

        Refuses to guess: raises if ET0 is not supplied. This is the guard that
        stops a fabricated single CWR being reused across regions.
        """
        required = {"init", "dev", "mid", "late"}
        if not et0_by_stage_mm_day or set(et0_by_stage_mm_day) < required:
            raise ValueError(
                f"{self.crop_name}: crop water requirement needs region/season ET0 "
                f"per stage (init/dev/mid/late) from IMD/CROPWAT. ET0 not sourced yet — "
                f"refusing to fabricate a value. (spec sections 3, 6, 35)"
            )
        li, ld, lm, ll = self.stage_days
        # Kc during development ramps ini->mid; late ramps mid->end. Use stage
        # means (trapezoidal) rather than a single Kc, per FAO-56 curve.
        kc_dev = (self.kc_ini + self.kc_mid) / 2.0
        kc_late = (self.kc_mid + self.kc_end) / 2.0
        return round(
            self.kc_ini * et0_by_stage_mm_day["init"] * li
            + kc_dev * et0_by_stage_mm_day["dev"] * ld
            + self.kc_mid * et0_by_stage_mm_day["mid"] * lm
            + kc_late * et0_by_stage_mm_day["late"] * ll,
            1,
        )

    def to_row(self) -> dict:
        d = asdict(self)
        d["stage_days"] = "/".join(str(x) for x in self.stage_days)
        return d


# Values transcribed from FAO-56 Table 11 (stage lengths) and Table 12 (Kc).
# Where FAO-56 gives a range for Kc end, a representative value is stored and the
# full range is kept in `notes`.
_OBS = ProvenanceType.OBSERVED.value
_GRD = ProvenanceType.SYNTHETIC_GROUNDED.value

CROP_WATER = {
    "rice":         CropWater("rice", 1.05, 1.20, 0.90, 1.0, (30, 30, 60, 30), 150, _OBS, "HIGH",
                              "Tropics/Mediterranean (Table 11)",
                              "Kc end range 0.90-0.60; 0.90 for continuously ponded paddy. Kc ini for paddy adjust via Table 14."),
    "wheat":        CropWater("wheat", 0.30, 1.15, 0.30, 1.0, (15, 25, 50, 30), 120, _OBS, "HIGH",
                              "Central India, Nov planting (Table 11)",
                              "Spring/rabi wheat. Kc end range 0.25-0.40 (0.40 if hand-harvested green)."),
    "maize":        CropWater("maize", 0.30, 1.20, 0.35, 2.0, (20, 35, 40, 30), 125, _OBS, "HIGH",
                              "India, dry cool (Table 11)",
                              "Grain maize; Kc end 0.60 (high grain moisture) to 0.35 (field-dried)."),
    "sorghum":      CropWater("sorghum", 0.30, 1.05, 0.55, 1.5, (20, 35, 45, 30), 130, _OBS, "MEDIUM",
                              "USA/Pakistan/Mediterranean (Table 11)",
                              "Grain sorghum; Kc mid range 1.00-1.10."),
    "pearl_millet": CropWater("pearl_millet", 0.30, 1.00, 0.30, 1.5, (15, 25, 40, 25), 105, _OBS, "MEDIUM",
                              "Millet, Pakistan Jun planting (Table 11)",
                              "FAO 'Millet' used for pearl millet."),
    "chickpea":     CropWater("chickpea", 0.40, 1.00, 0.35, 0.4, (20, 30, 60, 40), 150, _GRD, "MEDIUM",
                              "Stage lengths mapped from rabi legume analogue",
                              "Kc from FAO-56 Table 12 (chickpea, OBSERVED). Stage lengths not listed for chickpea in Table 11; mapped to a ~150d rabi pulse cycle — ASSUMPTION, verify locally."),
    "pigeon_pea":   CropWater("pigeon_pea", 0.40, 1.15, 0.55, 1.0, (30, 40, 70, 40), 180, _GRD, "LOW",
                              "Legume group default; long-duration kharif pulse",
                              "Pigeon pea is NOT in FAO-56. Kc mapped to legume group default (ini 0.4/mid 1.15/end 0.55). Duration ~180d ASSUMED for medium-duration variety. Both are assumptions — flag for sourcing."),
    "groundnut":    CropWater("groundnut", 0.40, 1.15, 0.60, 0.4, (25, 35, 45, 25), 130, _OBS, "HIGH",
                              "Groundnut, dry West Africa (Table 11)",
                              ""),
    "soybean":      CropWater("soybean", 0.40, 1.15, 0.50, 0.75, (20, 32, 60, 25), 137, _OBS, "MEDIUM",
                              "Central USA, May (Table 11)",
                              "Indian kharif soybean varieties are often shorter (~95-110d); FAO duration retained but flagged — prefer local ICAR variety data."),
    "mustard":      CropWater("mustard", 0.35, 1.10, 0.35, 0.6, (25, 35, 45, 25), 130, _GRD, "MEDIUM",
                              "Rapeseed/Canola mapping (Table 12 oil crops)",
                              "Indian mustard mapped to FAO rapeseed/canola (Kc mid 1.0-1.15 -> 1.10). Duration ~130d rabi ASSUMED — verify with ICAR/DES."),
    "cotton":       CropWater("cotton", 0.35, 1.18, 0.60, 1.35, (30, 50, 60, 55), 195, _OBS, "HIGH",
                              "Cotton, Egypt/Pakistan/Calif. (Table 11)",
                              "Kc mid range 1.15-1.20; Kc end range 0.70-0.50."),
    "potato":       CropWater("potato", 0.50, 1.15, 0.75, 0.6, (25, 30, 45, 30), 130, _OBS, "MEDIUM",
                              "Continental, May (Table 11)",
                              "Indian rabi potato often 90-120d; FAO continental cycle retained but flagged."),
    "onion":        CropWater("onion", 0.70, 1.05, 0.75, 0.4, (15, 25, 70, 40), 150, _OBS, "HIGH",
                              "Onion (dry), Mediterranean Apr (Table 11)",
                              ""),
    "tomato":       CropWater("tomato", 0.60, 1.15, 0.80, 0.6, (30, 40, 40, 25), 135, _OBS, "HIGH",
                              "Tomato, arid region Jan (Table 11)",
                              "Kc end range 0.70-0.90."),
}


def crop_water_provenance() -> list:
    """One provenance record per crop for the Kc/duration block."""
    records = []
    for name, cw in CROP_WATER.items():
        is_observed = cw.provenance_type == _OBS
        rec = ProvenanceRecord(
            parameter="crop.kc_and_stage_lengths",
            provenance_type=ProvenanceType.OBSERVED if is_observed else ProvenanceType.SYNTHETIC_GROUNDED,
            crop=name,
            value=f"Kc {cw.kc_ini}/{cw.kc_mid}/{cw.kc_end}; {cw.duration_days}d",
            unit="Kc dimensionless; days",
            source=FAO56_SOURCE if is_observed else None,
            source_url=FAO56_URL,
            source_year=FAO56_YEAR,
            transformation="Kc ranges reduced to representative value; stage means used for CWR curve",
            assumption=(None if is_observed else cw.notes),
            confidence=Confidence[cw.confidence],
            notes=f"Access {ACCESS_DATE}. Stage lengths: {cw.stage_region_note}. {cw.notes}".strip(),
        )
        records.append(rec)
    # ET0 dependency is an explicit open obligation
    records.append(ProvenanceRecord(
        parameter="climate.ET0_by_region_stage", provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
        unit="mm/day", confidence=Confidence.REQUIRES_SOURCING,
        notes=("Reference evapotranspiration per region/season/stage required to turn Kc "
               "into a crop water requirement. Source: IMD / CROPWAT / FAO CLIMWAT. "
               "Not yet sourced — CWR is computed on demand and refused without it."),
    ))
    return records
