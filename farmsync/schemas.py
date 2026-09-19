"""
Research data schemas (spec section 2).

Modular record definitions. These are the units every later phase reads:
feasibility (6), the four planning models (7), replanning (12), resilience (13),
disaster (15), and the evaluation dashboards (25). Kept as plain dataclasses +
enums so the engine has zero framework dependencies and serialises cleanly to
CSV/JSON for export (spec section 32).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------- #
# Controlled vocabularies
# --------------------------------------------------------------------------- #

class Season(str, Enum):
    KHARIF = "kharif"        # monsoon-sown
    RABI = "rabi"            # winter-sown


class ParticipationState(str, Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    VIEWED = "VIEWED"
    TENTATIVE_ACCEPT = "TENTATIVE_ACCEPT"
    CONFIRMED = "CONFIRMED"
    INPUTS_PURCHASED = "INPUTS_PURCHASED"
    LAND_PREPARED = "LAND_PREPARED"
    PLANTED = "PLANTED"
    NON_RESPONSE = "NON_RESPONSE"
    WITHDRAWN = "WITHDRAWN"


# Ordered commitment ladder (spec section 11). Higher index = harder to change.
COMMITMENT_LADDER = [
    ParticipationState.VIEWED,
    ParticipationState.TENTATIVE_ACCEPT,
    ParticipationState.CONFIRMED,
    ParticipationState.INPUTS_PURCHASED,
    ParticipationState.LAND_PREPARED,
    ParticipationState.PLANTED,
]


class FarmerEvent(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    NO_RESPONSE = "NO_RESPONSE"
    WITHDRAW = "WITHDRAW"


class SoilGroup(str, Enum):
    # Coarse soil groupings only. We intentionally do NOT invent pH/salinity
    # precision (spec section 2: "Do not create fake scientific precision").
    ALLUVIAL = "alluvial"
    BLACK = "black"
    RED = "red"
    LATERITE = "laterite"
    SANDY = "sandy"


class SuitabilityClass(str, Enum):
    HIGH = "S1"
    MODERATE = "S2"
    MARGINAL = "S3"
    UNSUITABLE = "N"


class DrainageClass(str, Enum):
    WELL = "well"
    MODERATE = "moderate"
    POOR = "poor"


class IrrigationAccess(str, Enum):
    CANAL = "canal"
    TUBEWELL = "tubewell"
    RAINFED = "rainfed"       # no assured irrigation


class Exposure(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


# Indian operational-holding size categories (Agriculture Census structure).
# This classification is real and citable; the per-farmer draw within it is
# synthetic. Recorded as SYNTHETIC_GROUNDED by the generator.
class HoldingCategory(str, Enum):
    MARGINAL = "marginal"        # < 1.0 ha
    SMALL = "small"              # 1.0 - 2.0 ha
    SEMI_MEDIUM = "semi_medium"  # 2.0 - 4.0 ha
    MEDIUM = "medium"            # 4.0 - 10.0 ha
    LARGE = "large"              # >= 10.0 ha


HOLDING_BOUNDS_HA = {
    HoldingCategory.MARGINAL: (0.2, 1.0),
    HoldingCategory.SMALL: (1.0, 2.0),
    HoldingCategory.SEMI_MEDIUM: (2.0, 4.0),
    HoldingCategory.MEDIUM: (4.0, 10.0),
    HoldingCategory.LARGE: (10.0, 20.0),
}


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #

@dataclass
class Region:
    region_id: str
    name: str
    dominant_soil: SoilGroup
    rainfall_regime: str            # "high" | "moderate" | "low"
    irrigation_propensity: float    # P(assured irrigation) in [0,1]
    synthetic: bool = True


@dataclass
class Collective:
    collective_id: str
    collective_name: str
    region_id: str
    season: Season
    description: str = ""
    active: bool = True
    synthetic: bool = True

    def to_row(self) -> dict:
        d = asdict(self)
        d["season"] = self.season.value
        return d


@dataclass
class Crop:
    crop_id: str
    crop_name: str
    crop_group: str                 # cereal | pulse | oilseed | fibre | vegetable | tuber
    seasons: list = field(default_factory=list)   # list[Season value]
    duration_days: Optional[int] = None
    rotation_group: Optional[str] = None
    perishability: Optional[str] = None            # low | moderate | high | None
    synthetic: bool = True          # crop identity is real; parameters are sourced later


@dataclass
class Farmer:
    farmer_id: str
    collective_id: str
    region_id: str
    season: Season
    holding_category: HoldingCategory
    total_area_ha: float                 # aggregates across owned plots
    cultivation_budget: float            # currency units, farmer-level
    labour_capacity: float               # person-days available, farmer-level
    minimum_projected_income: float
    risk_tolerance: float                # [0,1], 0 = risk-averse
    participation_state: ParticipationState
    synthetic_seed: int
    synthetic: bool = True
    # preferred/excluded crops are intentionally NOT set here. Spec section 4:
    # "crop preferences should be generated after feasible crop context is
    # known." They are realised after the Phase 6 feasibility engine exists.

    def to_row(self) -> dict:
        d = asdict(self)
        d["season"] = self.season.value
        d["holding_category"] = self.holding_category.value
        d["participation_state"] = self.participation_state.value
        return d


@dataclass
class Plot:
    plot_id: str
    farmer_id: str
    region_id: str
    area_ha: float
    soil_group: SoilGroup
    soil_suitability_class: SuitabilityClass
    drainage_class: DrainageClass
    irrigation_access: IrrigationAccess
    available_water_m3: float            # seasonal water available to the plot
    previous_crop: Optional[str]
    rotation_group: Optional[str]
    flood_exposure: Exposure
    drought_exposure: Exposure
    waterlogging_exposure: Exposure
    hazard_zone: str                     # correlated-failure zone id
    active_season: Season
    synthetic_seed: int
    synthetic: bool = True

    def to_row(self) -> dict:
        d = asdict(self)
        for k in ("soil_group", "soil_suitability_class", "drainage_class",
                  "irrigation_access", "flood_exposure", "drought_exposure",
                  "waterlogging_exposure", "active_season"):
            d[k] = getattr(self, k).value
        return d


@dataclass
class DatasetManifest:
    """Reproducibility record written with every dataset (spec section 4)."""
    dataset_version: str
    master_seed: int
    n_farmers: int
    n_collectives: int
    n_plots: int
    n_crops: int
    n_regions: int
    seasons: list
    generated_at: str
    generator_git_commit: Optional[str] = None
    label: str = "SYNTHETIC — no record represents a real farmer"
