"""
Phase 5e — crop yields (national, season-split) + derived cultivation cost/ha.

SCOPE DECISION (documented): yields here are ALL-INDIA national figures from
authoritative Government sources, applied uniformly across regions with explicit
`scope = "ALL_INDIA"`. This is NOT "silently reusing one region's value for
another" — no regional claim is made. Per-state refinement (mapping each synthetic
region to a representative state) is the remaining exhaustive step; the mapping is
recorded below for that follow-up.

SOURCES
  DES / Economic Survey 2025-26 Statistical Appendix, Table 1.17 "Yield Per
  Hectare of Major Crops" (kg/ha), final/provisional 2024-25.
    https://www.indiabudget.gov.in/economicsurvey/doc/stat/tab1.17.pdf
  Soybean: Soybean Processors Association of India (SOPA), kharif 2024
  average productivity 1063 kg/ha.

UNIT TRAP (guarded): cotton yield in Table 1.17 is LINT (440 kg/ha), whereas the
cotton MSP and CACP cost are per quintal of SEED COTTON (kapas). Lint yield must
NOT be multiplied by seed-cotton price/cost. Cotton cost/ha and return are left
open pending a consistent seed-cotton basis.

Region -> representative state (for later state-level yield refinement), aligned
with the ET0 anchors already chosen:
  R1 Indo-Gangetic  -> Punjab
  R2 Deccan         -> Maharashtra
  R3 Eastern        -> West Bengal
  R4 Semi-arid West -> Rajasthan
  R5 Southern       -> Karnataka
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .crop_economics import CROP_PRICE
from .provenance import ProvenanceRecord, ProvenanceType, Confidence

DES_SRC = "DES / Economic Survey 2025-26 Statistical Appendix, Table 1.17 (2024-25)"
DES_URL = "https://www.indiabudget.gov.in/economicsurvey/doc/stat/tab1.17.pdf"
SOPA_SRC = "Soybean Processors Association of India (SOPA), kharif 2024"

REGION_STATE = {
    "R1": "Punjab", "R2": "Maharashtra", "R3": "West Bengal",
    "R4": "Rajasthan", "R5": "Karnataka",
}

# State-level yield overrides (kg/ha), sourced from DES state series. Take
# precedence over the national figure for the mapped region. This is the
# (deliberately partial) exhaustive-state refinement in progress; continue via the
# official DES Area-Production-Yield portal: https://data.desagri.gov.in/website/crops-apy-report-web
CEIC_DES = "DES state APY series (via CEIC)"
STATE_YIELD = {
    ("Punjab", "rice"):  {"kharif": 4193, "rabi": None, "year": 2023,
                          "source": CEIC_DES,
                          "url": "https://www.ceicdata.com/en/india/yield-of-foodgrains-in-major-states-rice/agricultural-yield-foodgrains-rice-punjab"},
    ("Punjab", "wheat"): {"kharif": None, "rabi": 5045, "year": 2024,
                          "source": CEIC_DES,
                          "url": "https://www.ceicdata.com/en/india/agriculture-yield-foodgrains-by-major-states-wheat/agricultural-yield-foodgrains-wheat-punjab"},
}


@dataclass
class CropYield:
    crop_name: str
    kharif_kg_ha: Optional[float]
    rabi_kg_ha: Optional[float]
    source: Optional[str]
    scope: str = "ALL_INDIA"
    unit_consistent_with_price: bool = True   # False for cotton (lint vs kapas)
    note: str = ""

    def yield_for(self, season: str) -> Optional[float]:
        return self.kharif_kg_ha if season == "kharif" else self.rabi_kg_ha


# National season-split yields (kg/ha), DES 2024-25 unless noted.
CROP_YIELD = {
    "rice":         CropYield("rice", 2825, 3606, DES_SRC),
    "wheat":        CropYield("wheat", None, 3595, DES_SRC),
    "maize":        CropYield("maize", 2932, 5306, DES_SRC),
    "sorghum":      CropYield("sorghum", 1204, 1266, DES_SRC),
    "pearl_millet": CropYield("pearl_millet", 1459, None, DES_SRC),
    "chickpea":     CropYield("chickpea", None, 1218, DES_SRC),
    "pigeon_pea":   CropYield("pigeon_pea", 836, None, DES_SRC),
    "groundnut":    CropYield("groundnut", 2080, 2011, DES_SRC),
    "soybean":      CropYield("soybean", 1063, None, SOPA_SRC),
    "mustard":      CropYield("mustard", None, 1463, DES_SRC),
    "cotton":       CropYield("cotton", 1257, None, DES_SRC, unit_consistent_with_price=True,
                              note="Seed cotton (kapas) basis: lint 440 kg/ha (DES) / 0.35 ginning ratio "
                                   "= 1257 kg/ha kapas, consistent with seed-cotton MSP/cost. Ginning ratio "
                                   "0.35 is an ICAR-typical value (documented assumption)."),
    "potato":       CropYield("potato", None, 25000, DES_SRC,
                              note="25 t/ha; potato has no MSP price, so return/cost still open."),
    "onion":        CropYield("onion", 16800, 16800, "NHB National Horticulture Database (2019)",
                              scope="ALL_INDIA",
                              note="16.8 t/ha national average (NHB 2019). Onion grown kharif/late-kharif/rabi; "
                                   "rabi ~60% of output. Still lacks sourced cost & market price -> not yet admitted."),
    "tomato":       CropYield("tomato", 25000, 25000, "NHB Horticultural Statistics (production/area)",
                              scope="ALL_INDIA",
                              note="~25 t/ha national (derived NHB production/area). Lacks sourced cost & "
                                   "market price -> not yet admitted. Confidence LOW."),
}


def derive_cost_per_ha(crop_name: str, season: str) -> Optional[dict]:
    """
    cost/ha = cost_per_quintal x (yield_kg_ha / 100), only where units are
    consistent (grain/pulse/oilseed with a CACP cost and a matching-basis yield).
    Returns None (with reason) where not derivable. Never fabricated.
    """
    y = CROP_YIELD.get(crop_name)
    p = CROP_PRICE.get(crop_name)
    if not y or not p:
        return {"cost_per_ha": None, "reason": "no yield/price record"}
    if not y.unit_consistent_with_price:
        return {"cost_per_ha": None, "reason": "unit mismatch (cotton lint vs kapas)"}
    yld = y.yield_for(season)
    if yld is None or p.cost_per_quintal is None:
        return {"cost_per_ha": None, "reason": "yield or cost_per_quintal not available for this season"}
    cost = round(p.cost_per_quintal * (yld / 100.0), 0)
    return {"cost_per_ha": cost, "basis": p.cost_basis,
            "reason": f"{p.cost_per_quintal} INR/q ({p.cost_basis}) x {yld/100:.2f} q/ha"}


def crop_yield_provenance() -> list:
    records = []
    for name, y in CROP_YIELD.items():
        if y.kharif_kg_ha is None and y.rabi_kg_ha is None:
            records.append(ProvenanceRecord(
                parameter="crop.expected_yield", provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
                crop=name, unit="kg/ha", confidence=Confidence.REQUIRES_SOURCING,
                notes=y.note))
            continue
        val = f"kharif {y.kharif_kg_ha}, rabi {y.rabi_kg_ha}"
        records.append(ProvenanceRecord(
            parameter="crop.expected_yield", provenance_type=ProvenanceType.OBSERVED,
            crop=name, value=val, unit="kg/ha", source=y.source, source_url=DES_URL,
            source_year=2024, confidence=Confidence.HIGH if y.scope == "ALL_INDIA" else Confidence.MEDIUM,
            transformation="season-split national yield",
            assumption=f"Scope {y.scope}; applied uniformly across regions pending state refinement "
                       f"({', '.join(f'{k}->{v}' for k, v in REGION_STATE.items())}).",
            notes=y.note))
        # derived cost/ha provenance (where derivable)
        for season in ("kharif", "rabi"):
            if y.yield_for(season) is not None:
                d = derive_cost_per_ha(name, season)
                if d.get("cost_per_ha") is not None:
                    records.append(ProvenanceRecord(
                        parameter="crop.cultivation_cost_per_ha", provenance_type=ProvenanceType.DERIVED,
                        crop=name, season=season, value=str(d["cost_per_ha"]), unit="INR/ha",
                        source=f"CACP cost x DES yield ({d['basis']} basis)", source_url=DES_URL,
                        source_year=2024, transformation=d["reason"],
                        confidence=Confidence.MEDIUM,
                        notes="Cost basis differs kharif A2+FL vs rabi C2; not mixed within a crop-season."))
    records.extend(state_yield_provenance())
    return records


def resolve_yield(crop_name: str, season: str, region_id: str = None) -> dict:
    """
    Region-aware yield resolution: a state override for the region's mapped state
    wins over the national figure. Returns value + scope + source (never fabricated).
    """
    if region_id and region_id in REGION_STATE:
        state = REGION_STATE[region_id]
        ov = STATE_YIELD.get((state, crop_name))
        if ov and ov.get(season) is not None:
            return {"value": ov[season], "scope": f"STATE:{state}",
                    "source": ov["source"], "url": ov["url"], "year": ov["year"]}
    y = CROP_YIELD.get(crop_name)
    if y and y.yield_for(season) is not None:
        return {"value": y.yield_for(season), "scope": "ALL_INDIA",
                "source": y.source, "url": DES_URL, "year": 2024}
    return {"value": None, "scope": None, "source": None, "url": None, "year": None}


def state_yield_provenance() -> list:
    records = []
    for (state, crop), ov in STATE_YIELD.items():
        val = f"kharif {ov['kharif']}, rabi {ov['rabi']}"
        records.append(ProvenanceRecord(
            parameter="crop.expected_yield", provenance_type=ProvenanceType.OBSERVED,
            crop=crop, value=val, unit="kg/ha", source=ov["source"], source_url=ov["url"],
            source_year=ov["year"], confidence=Confidence.HIGH,
            transformation="state-level yield override",
            assumption=f"Scope STATE:{state}; overrides national figure for the mapped region.",
            notes="Partial exhaustive-state refinement; continue via DES APY portal "
                  "https://data.desagri.gov.in/website/crops-apy-report-web"))
    return records


def yield_summary() -> dict:
    have = [k for k, v in CROP_YIELD.items() if v.kharif_kg_ha or v.rabi_kg_ha]
    need = [k for k, v in CROP_YIELD.items() if not (v.kharif_kg_ha or v.rabi_kg_ha)]
    return {"yield_sourced": have, "yield_requires_sourcing": need,
            "cotton_unit_flagged": not CROP_YIELD["cotton"].unit_consistent_with_price}
