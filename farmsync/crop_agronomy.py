"""
Phase 5g / 6 — labour, crop x soil suitability, sowing/harvest windows.

These are documented agronomic parameters. Labour/ha and the crop x soil matrix
are representative values grounded in ICAR package-of-practices and standard Indian
agronomy (SYNTHETIC_GROUNDED with stated assumptions), not a single sourced table.
Sowing/harvest windows follow the standard kharif/rabi calendar. All are flagged so
a reviewer sees exactly what rests on a citation versus documented agronomy.
"""

from __future__ import annotations

from .provenance import ProvenanceRecord, ProvenanceType, Confidence

# Representative human-labour requirement (person-days/ha), grounded in ICAR/SAU
# package-of-practices and DES Cost-of-Cultivation labour components (typical ranges).
LABOUR_PD_HA = {
    "rice": 130, "wheat": 55, "maize": 65, "sorghum": 55, "pearl_millet": 50,
    "chickpea": 45, "pigeon_pea": 55, "groundnut": 85, "soybean": 45, "mustard": 45,
    "cotton": 110, "potato": 120, "onion": 160, "tomato": 180,
}

# Crop x soil suitability. Lists the soils on which a crop is clearly ILL-suited
# (hard SOIL_INCOMPATIBLE) and its preferred soils (informational). Conservative:
# only clear agronomic mismatches are marked unsuitable. Documented agronomy.
CROP_SOIL = {
    # crop: (preferred_soils, unsuitable_soils)
    "rice":         (["alluvial", "black"], ["sandy"]),        # needs water retention
    "wheat":        (["alluvial", "black"], ["laterite", "sandy"]),
    "maize":        (["alluvial", "red"], []),
    "sorghum":      (["black", "red"], []),
    "pearl_millet": (["sandy", "red"], []),                    # drought-hardy on light soils
    "chickpea":     (["black", "alluvial"], ["sandy"]),
    "pigeon_pea":   (["red", "black"], []),
    "groundnut":    (["sandy", "red"], ["black"]),             # needs loose, well-drained soil for pegging
    "soybean":      (["black", "alluvial"], ["sandy"]),
    "mustard":      (["alluvial", "black"], ["laterite"]),
    "cotton":       (["black"], ["sandy", "laterite"]),        # classic black-cotton soil
    "potato":       (["alluvial", "sandy"], ["black"]),        # tuber expansion needs loose soil
    "onion":        (["alluvial", "red"], []),
    "tomato":       (["red", "alluvial"], []),
}

# Sowing/harvest windows by season (month ranges). Standard Indian crop calendar.
SEASON_WINDOWS = {
    "kharif": {"sow": "Jun-Jul", "harvest": "Oct-Nov"},
    "rabi":   {"sow": "Oct-Nov", "harvest": "Feb-Apr"},
}


def labour_pd_ha(crop_name: str):
    return LABOUR_PD_HA.get(crop_name)


def soil_incompatible(crop_name: str, soil_group: str) -> bool:
    entry = CROP_SOIL.get(crop_name)
    return bool(entry and soil_group in entry[1])


def agronomy_provenance() -> list:
    recs = [
        ProvenanceRecord(
            parameter="crop.labour_pd_ha", provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
            value="per-crop table", unit="person-days/ha",
            source="ICAR/SAU package-of-practices; DES Cost-of-Cultivation labour component",
            assumption="Representative national human-labour requirement; not a single sourced "
                       "state table. Refine with DES CoC per state.",
            confidence=Confidence.MEDIUM,
            notes="Used for deterministic labour feasibility."),
        ProvenanceRecord(
            parameter="crop.soil_suitability_matrix", provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
            value="preferred/unsuitable soils per crop", unit="rule",
            source="Standard Indian agronomy (ICAR crop production practices)",
            assumption="Conservative: only clear agronomic mismatches marked unsuitable "
                       "(e.g. cotton on sandy, groundnut on heavy black soil). Documented.",
            confidence=Confidence.MEDIUM),
        ProvenanceRecord(
            parameter="crop.sowing_harvest_windows", provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
            value="kharif sow Jun-Jul/harvest Oct-Nov; rabi sow Oct-Nov/harvest Feb-Apr", unit="month range",
            source="Standard Indian kharif/rabi crop calendar",
            assumption="Season-level windows; crop-specific durations from FAO-56 already stored.",
            confidence=Confidence.MEDIUM),
    ]
    return recs
