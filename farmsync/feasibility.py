"""
Phase 6 — deterministic plot x crop agronomic feasibility engine.

Operates at: plot x crop x region x season x climate_state.
Returns feasible / infeasible + reason codes + binding constraints.

SCOPE OF THIS PHASE (per the checkpoint decision: agronomic first, no economics)
  Evaluated here: season, land suitability class, crop water requirement vs
  available water, rotation (no-monocrop), drainage/waterlogging, farmer crop
  exclusions, and post-planting commitment locks.
  DEFERRED (returns NOT_EVALUATED, never fabricated): budget and labour, which
  need sourced cultivation cost and labour requirement (Phase 5, in progress).

HONESTY
  * Water is only decided where crop water requirement exists (regions with
    sourced ET0: R1, R2). Elsewhere the water check returns UNKNOWN — never a
    fabricated pass/fail.
  * Crop-specific soil and waterlogging tolerances used here are COARSE, general
    agronomy (rice tolerates ponding; tubers/pulses do not), recorded as
    SYNTHETIC_GROUNDED with the assumption stated — not a sourced crop x soil
    matrix. Hard SOIL_INCOMPATIBLE is driven by the plot's own land-suitability
    class ('N'), which is in the dataset, plus these coarse rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .crop_water import CROP_WATER
from .climate import compute_crop_water_requirements, REGION_ET0
from .provenance import ProvenanceRecord, ProvenanceType, Confidence

# Reason codes
SEASON_INCOMPATIBLE = "SEASON_INCOMPATIBLE"
SOIL_INCOMPATIBLE = "SOIL_INCOMPATIBLE"
WATER_INSUFFICIENT = "WATER_INSUFFICIENT"
ROTATION_RESTRICTED = "ROTATION_RESTRICTED"
WATERLOGGING_RISK = "WATERLOGGING_RISK"
FARMER_EXCLUDED = "FARMER_EXCLUDED"
POST_PLANTING_LOCK = "POST_PLANTING_LOCK"
BUDGET_INSUFFICIENT = "BUDGET_INSUFFICIENT"      # deferred (economics)
LABOUR_INSUFFICIENT = "LABOUR_INSUFFICIENT"      # deferred (economics)

# Coarse, documented agronomy (SYNTHETIC_GROUNDED). Only rice tolerates sustained
# waterlogging/ponding among these crops; others are treated as intolerant.
WATERLOGGING_TOLERANT = {"rice"}

# Climate-state water multipliers applied to available water. These are EXPERIMENTAL
# scenario parameters (documented), not observed coefficients.
CLIMATE_WATER_FACTOR = {
    "baseline": 1.0, "water_shortage": 0.8, "drought": 0.6,
    "water_-10": 0.9, "water_-20": 0.8, "water_-40": 0.6,
    "excessive_rainfall": 1.1,
}


@dataclass
class FeasibilityConfig:
    enforce_rotation_no_monocrop: bool = True
    enforce_waterlogging: bool = True
    enforce_water: bool = True
    min_plot_area_ha: float = 0.0            # 0 = off (min-area comes from prefs later)
    climate_state: str = "baseline"


@dataclass
class FeasibilityResult:
    plot_id: str
    crop_name: str
    feasible: bool
    reasons: list = field(default_factory=list)      # reason codes (empty if feasible)
    binding: list = field(default_factory=list)      # human-readable binding constraints
    checks: dict = field(default_factory=dict)       # per-check status
    water_need_m3: float = None
    water_available_m3: float = None

    def to_row(self):
        return {
            "plot_id": self.plot_id, "crop_id": self.crop_name,
            "feasible": self.feasible,
            "reason_code": "|".join(self.reasons) if self.reasons else "",
            "binding": "; ".join(self.binding),
        }


def _water_status(plot, crop_name, region_id, season, config):
    """
    Return (status, need_m3, avail_m3). status in {OK, INSUFFICIENT, UNKNOWN}.
    Water need is the NET IRRIGATION REQUIREMENT = max(0, CWR - effective rainfall),
    not the full crop water requirement — rainfed crops draw most of their water
    from rainfall. This is the corrected water balance (spec item: NIR).
    """
    if not config.enforce_water:
        return "OK", None, None
    from .climate import net_irrigation_requirement_mm
    nir_mm = net_irrigation_requirement_mm(crop_name, region_id, season)
    if nir_mm is None:
        return "UNKNOWN", None, None                     # never fabricate
    # 1 mm over 1 ha = 10 m3
    need_m3 = round(nir_mm * plot.area_ha * 10, 1)
    factor = CLIMATE_WATER_FACTOR.get(config.climate_state, 1.0)
    avail = round(plot.available_water_m3 * factor, 1)
    # if NIR is 0 (rainfall covers the crop), water is satisfied regardless of irrigation
    return ("OK" if avail >= need_m3 else "INSUFFICIENT"), need_m3, avail


def assess_plot_crop(plot, crop, farmer=None, exclusions=None,
                     commitment_state=None, planted_crop=None,
                     config=None) -> FeasibilityResult:
    """
    plot: Plot; crop: Crop; exclusions: set of crop_names; commitment_state: str;
    planted_crop: crop_name locked if commitment_state == PLANTED.
    """
    config = config or FeasibilityConfig()
    exclusions = exclusions or set()
    reasons, binding, checks = [], [], {}
    season = plot.active_season.value

    # 1. post-planting lock takes precedence
    if commitment_state == "PLANTED":
        if planted_crop and planted_crop != crop.crop_name:
            reasons.append(POST_PLANTING_LOCK)
            binding.append(f"plot planted with {planted_crop}; locked")
        checks["commitment"] = "PLANTED_LOCK" if planted_crop != crop.crop_name else "OK"

    # 2. season
    if season not in crop.seasons:
        reasons.append(SEASON_INCOMPATIBLE)
        binding.append(f"{crop.crop_name} not grown in {season}")
    checks["season"] = "OK" if season in crop.seasons else "FAIL"

    # 3. farmer exclusion
    if crop.crop_name in exclusions:
        reasons.append(FARMER_EXCLUDED)
        binding.append(f"farmer excluded {crop.crop_name}")
    checks["exclusion"] = "EXCLUDED" if crop.crop_name in exclusions else "OK"

    # 4. land suitability class (plot-level, in dataset) + crop x soil matrix
    from .crop_agronomy import soil_incompatible
    if plot.soil_suitability_class.value == "N":
        reasons.append(SOIL_INCOMPATIBLE)
        binding.append("plot land-suitability class N (unsuitable)")
    elif soil_incompatible(crop.crop_name, plot.soil_group.value):
        reasons.append(SOIL_INCOMPATIBLE)
        binding.append(f"{crop.crop_name} ill-suited to {plot.soil_group.value} soil")
    checks["soil_class"] = plot.soil_suitability_class.value

    # 5. waterlogging (coarse agronomy)
    if config.enforce_waterlogging:
        wl = plot.waterlogging_exposure.value
        poor_drain = plot.drainage_class.value == "poor"
        risky = (wl == "high") or (poor_drain and wl in ("moderate", "high"))
        if risky and crop.crop_name not in WATERLOGGING_TOLERANT:
            reasons.append(WATERLOGGING_RISK)
            binding.append(f"{crop.crop_name} intolerant of waterlogging on this plot")
        checks["waterlogging"] = "RISK" if (risky and crop.crop_name not in WATERLOGGING_TOLERANT) else "OK"

    # 6. rotation (no monocrop)
    if config.enforce_rotation_no_monocrop and plot.previous_crop == crop.crop_name:
        reasons.append(ROTATION_RESTRICTED)
        binding.append(f"previous crop was also {crop.crop_name} (monocropping)")
    checks["rotation"] = "RESTRICTED" if plot.previous_crop == crop.crop_name else "OK"

    # 7. water (only where CWR exists)
    wstatus, need_m3, avail_m3 = _water_status(plot, crop.crop_name, plot.region_id, season, config)
    if wstatus == "INSUFFICIENT":
        reasons.append(WATER_INSUFFICIENT)
        binding.append(f"needs {need_m3} m3, has {avail_m3} m3")
    checks["water"] = wstatus

    # 8. budget / labour — deterministic per-plot affordability (necessary condition;
    #    the farmer-level aggregate across plots is enforced in the optimiser).
    from .crop_yield import derive_cost_per_ha
    from .crop_agronomy import labour_pd_ha
    from .ingest import operational as opdata
    if farmer is not None:
        if opdata.is_loaded():
            cph, _ = opdata.op_cost(plot.region_id, crop.crop_name, basis="A2FL")  # cash basis
        else:
            cost = derive_cost_per_ha(crop.crop_name, season)
            cph = cost.get("cost_per_ha") if cost else None
        if cph is not None:
            plot_cost = cph * plot.area_ha
            if plot_cost > farmer.cultivation_budget:
                reasons.append(BUDGET_INSUFFICIENT)
                binding.append(f"A2+FL cost {round(plot_cost)} > farmer budget {round(farmer.cultivation_budget)}")
            checks["budget"] = "OK" if plot_cost <= farmer.cultivation_budget else "INSUFFICIENT"
        else:
            checks["budget"] = "NO_COST_DATA"      # crop not in admitted set
        lph = opdata.op_labour(plot.region_id, crop.crop_name) if opdata.is_loaded() else None
        if lph is None:
            lph = labour_pd_ha(crop.crop_name)
        if lph is not None:
            plot_labour = lph * plot.area_ha
            if plot_labour > farmer.labour_capacity:
                reasons.append(LABOUR_INSUFFICIENT)
                binding.append(f"plot labour {round(plot_labour)} pd > farmer capacity {round(farmer.labour_capacity)} pd")
            checks["labour"] = "OK" if plot_labour <= farmer.labour_capacity else "INSUFFICIENT"
        else:
            checks["labour"] = "NO_LABOUR_DATA"
    else:
        checks["budget"] = "NOT_EVALUATED"         # no farmer context supplied
        checks["labour"] = "NOT_EVALUATED"

    # min area (off unless configured)
    if config.min_plot_area_ha and plot.area_ha < config.min_plot_area_ha:
        reasons.append("AREA_TOO_SMALL")
        binding.append(f"area {plot.area_ha} < min {config.min_plot_area_ha}")

    return FeasibilityResult(
        plot_id=plot.plot_id, crop_name=crop.crop_name,
        feasible=len(reasons) == 0, reasons=reasons, binding=binding, checks=checks,
        water_need_m3=need_m3, water_available_m3=avail_m3,
    )


def feasible_crops_for_plot(plot, crops, farmer=None, exclusions=None,
                            commitment_state=None, planted_crop=None, config=None):
    """Return {crop_name: FeasibilityResult} for all crops on one plot."""
    return {c.crop_name: assess_plot_crop(plot, c, farmer, exclusions,
                                          commitment_state, planted_crop, config)
            for c in crops}


def feasibility_provenance() -> list:
    return [
        ProvenanceRecord(
            parameter="feasibility.waterlogging_tolerance",
            provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
            value="rice tolerant; others intolerant", unit="rule",
            assumption=("Coarse general agronomy: among the 14 crops only rice tolerates "
                        "sustained ponding/waterlogging. Not a sourced crop-specific "
                        "tolerance index; refine with ICAR where a study exists."),
            confidence=Confidence.MEDIUM,
        ),
        ProvenanceRecord(
            parameter="feasibility.rotation_rule",
            provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
            value="no monocropping (same crop consecutively restricted)", unit="rule",
            assumption="Deterministic agronomic rule; configurable. Same-group rotation "
                       "effects treated as preference, not hard restriction.",
            confidence=Confidence.MEDIUM,
        ),
        ProvenanceRecord(
            parameter="feasibility.climate_water_factor",
            provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
            value="baseline 1.0; shortage 0.8; drought 0.6", unit="multiplier",
            confidence=Confidence.REQUIRES_SOURCING,
            notes="Experimental scenario multipliers on available water; to be varied in "
                  "sensitivity analysis, not asserted as observed.",
        ),
    ]
