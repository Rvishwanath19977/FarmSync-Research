"""
Synthetic farmer + plot generator (spec section 4).

Guarantees:
  * Reproducible: the same master seed regenerates a byte-identical dataset.
    Each farmer/plot carries the seed used for its own draws, so any single
    record is independently reconstructable.
  * Conditional plausibility: water relates to region/irrigation/area; soil
    relates to region; previous crop is plausible for region+season; resources
    are never impossible for the holding size.
  * Non-uniform farm size: drawn via Indian operational-holding categories,
    heavily skewed to marginal/small, then a size within the category's bounds.

Honest labelling:
  * Farmer/plot draws are SYNTHETIC_EXPERIMENTAL.
  * The holding-size *category structure* is SYNTHETIC_GROUNDED (anchored to the
    Agriculture Census operational-holding classification). The proportions used
    to weight the categories are an experimental assumption to be
    sensitivity-tested, NOT asserted as census fact.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone

from . import DATASET_VERSION, DEFAULT_MASTER_SEED
from .schemas import (
    Season, ParticipationState, SoilGroup, SuitabilityClass, DrainageClass,
    IrrigationAccess, Exposure, HoldingCategory, HOLDING_BOUNDS_HA,
    Region, Crop, Farmer, Plot, Collective, DatasetManifest,
)
from .provenance import (
    ProvenanceRegistry, ProvenanceRecord, ProvenanceType, Confidence,
)

# --------------------------------------------------------------------------- #
# Fixed reference structures
# --------------------------------------------------------------------------- #

# Holding-size category weights. ASSUMPTION (sensitivity-tested later), shape
# anchored to the well-known skew toward small/marginal holdings in India.
HOLDING_WEIGHTS = {
    HoldingCategory.MARGINAL: 0.62,
    HoldingCategory.SMALL: 0.19,
    HoldingCategory.SEMI_MEDIUM: 0.12,
    HoldingCategory.MEDIUM: 0.06,
    HoldingCategory.LARGE: 0.01,
}

REGIONS = [
    Region("R1", "Indo-Gangetic Plain",  SoilGroup.ALLUVIAL, "moderate", 0.75),
    Region("R2", "Deccan Plateau",       SoilGroup.BLACK,    "low",      0.40),
    Region("R3", "Eastern Delta",        SoilGroup.ALLUVIAL, "high",     0.55),
    Region("R4", "Semi-arid West",       SoilGroup.SANDY,    "low",      0.30),
    Region("R5", "Southern Peninsula",   SoilGroup.RED,      "moderate", 0.50),
]

# Crop identities are real; agronomic parameters are sourced in Phase 5.
CROPS = [
    Crop("C01", "rice",         "cereal",    [Season.KHARIF.value],                     rotation_group="cereal"),
    Crop("C02", "wheat",        "cereal",    [Season.RABI.value],                       rotation_group="cereal"),
    Crop("C03", "maize",        "cereal",    [Season.KHARIF.value, Season.RABI.value],  rotation_group="cereal"),
    Crop("C04", "sorghum",      "cereal",    [Season.KHARIF.value, Season.RABI.value],  rotation_group="cereal"),
    Crop("C05", "pearl_millet", "cereal",    [Season.KHARIF.value],                     rotation_group="cereal"),
    Crop("C06", "chickpea",     "pulse",     [Season.RABI.value],                       rotation_group="legume"),
    Crop("C07", "pigeon_pea",   "pulse",     [Season.KHARIF.value],                     rotation_group="legume"),
    Crop("C08", "groundnut",    "oilseed",   [Season.KHARIF.value],                     rotation_group="legume"),
    Crop("C09", "soybean",      "oilseed",   [Season.KHARIF.value],                     rotation_group="legume"),
    Crop("C10", "mustard",      "oilseed",   [Season.RABI.value],                       rotation_group="oilseed"),
    Crop("C11", "cotton",       "fibre",     [Season.KHARIF.value],                     rotation_group="fibre"),
    Crop("C12", "potato",       "tuber",     [Season.RABI.value],           perishability="moderate", rotation_group="tuber"),
    Crop("C13", "onion",        "vegetable", [Season.KHARIF.value, Season.RABI.value], perishability="high", rotation_group="vegetable"),
    Crop("C14", "tomato",       "vegetable", [Season.KHARIF.value, Season.RABI.value], perishability="high", rotation_group="vegetable"),
]

# Plausible previous crops by region+season (kept coarse, not invented precision)
_PREV_CROP_POOL = {
    (Season.KHARIF): ["rice", "maize", "cotton", "groundnut", "pigeon_pea", None],
    (Season.RABI):   ["wheat", "chickpea", "mustard", "potato", "onion", None],
}

_SOIL_BY_REGION = {
    "R1": [SoilGroup.ALLUVIAL, SoilGroup.SANDY],
    "R2": [SoilGroup.BLACK, SoilGroup.RED],
    "R3": [SoilGroup.ALLUVIAL, SoilGroup.LATERITE],
    "R4": [SoilGroup.SANDY, SoilGroup.RED],
    "R5": [SoilGroup.RED, SoilGroup.LATERITE],
}


def _plots_for_category(cat: HoldingCategory) -> tuple:
    """(min_plots, max_plots) — larger holdings fragment into more plots."""
    return {
        HoldingCategory.MARGINAL: (1, 2),
        HoldingCategory.SMALL: (1, 3),
        HoldingCategory.SEMI_MEDIUM: (2, 3),
        HoldingCategory.MEDIUM: (2, 4),
        HoldingCategory.LARGE: (3, 5),
    }[cat]


def _partition_area(total: float, n: int, rng: random.Random) -> list:
    """Split total_area into n positive plot areas that sum (to 3 dp) to total."""
    cuts = sorted(rng.random() for _ in range(n - 1))
    bounds = [0.0] + cuts + [1.0]
    fracs = [bounds[i + 1] - bounds[i] for i in range(n)]
    # avoid degenerate tiny plots
    fracs = [max(f, 0.05) for f in fracs]
    s = sum(fracs)
    areas = [round(total * f / s, 3) for f in fracs]
    # fix rounding drift onto the largest plot
    drift = round(total - sum(areas), 3)
    areas[areas.index(max(areas))] = round(max(areas) + drift, 3)
    return areas


BUDGET_TIGHTNESS = {"tight": 0.6, "base": 1.2, "loose": 2.5}
REP_A2FL_PER_HA = 55000     # ≈ median ingested CoC A2+FL (₹55,361/ha), documented anchor


def generate_dataset(master_seed: int = DEFAULT_MASTER_SEED,
                     n_farmers: int = 500,
                     n_collectives: int = 10,
                     season: Season = Season.KHARIF,
                     budget_tightness: str = "base"):
    """
    Returns (farmers, plots, crops, regions, manifest, provenance_registry).

    budget_tightness (tight/base/loose) is a documented robustness parameter that
    scales the realistic A2+FL-anchored farmer cash budget. Base is calibrated so
    farmers can cultivate their land near the median ingested A2+FL cost, replacing
    the earlier unrealistically tight default.

    Deterministic in master_seed. Every draw derives from a per-record seed so
    the population is order-independent and individually reproducible.
    """
    master = random.Random(master_seed)
    farmers, plots = [], []

    # Collectives are region-coherent: each is bound to one region + season, and
    # farmers inherit their region from their collective (spec: every collective
    # references a valid region_id; every farmer references a valid collective_id).
    collectives = _build_collectives(n_collectives, season)
    collectives_by_region = {}
    for c in collectives:
        collectives_by_region.setdefault(c.region_id, []).append(c)

    for i in range(n_farmers):
        fid = f"F{i+1:04d}"
        # per-farmer seed derived deterministically from the master seed
        f_seed = master.randint(1, 2_000_000_000)
        frng = random.Random(f_seed)

        collective = collectives[frng.randrange(len(collectives))]
        collective_id = collective.collective_id
        region = next(r for r in REGIONS if r.region_id == collective.region_id)

        # non-uniform holding size
        cat = frng.choices(list(HOLDING_WEIGHTS), weights=list(HOLDING_WEIGHTS.values()))[0]
        lo, hi = HOLDING_BOUNDS_HA[cat]
        total_area = round(frng.uniform(lo, hi), 3)

        # resources scale with area so nobody gets impossible resources
        # realistic cash budget: A2+FL-anchored × tightness scenario × heterogeneity
        tf = BUDGET_TIGHTNESS.get(budget_tightness, 1.2)
        budget = round(total_area * REP_A2FL_PER_HA * tf * frng.uniform(0.85, 1.15), 0)
        labour = round(total_area * frng.uniform(60, 110), 0)            # person-days/ha band
        min_income = round(budget * frng.uniform(0.8, 1.4), 0)
        risk = round(frng.uniform(0.1, 0.9), 2)

        farmers.append(Farmer(
            farmer_id=fid, collective_id=collective_id, region_id=region.region_id,
            season=season, holding_category=cat, total_area_ha=total_area,
            cultivation_budget=budget, labour_capacity=labour,
            minimum_projected_income=min_income, risk_tolerance=risk,
            participation_state=ParticipationState.INVITED, synthetic_seed=f_seed,
        ))

        # plots — conditional on region, irrigation propensity, area
        n_plots_min, n_plots_max = _plots_for_category(cat)
        n_plots = frng.randint(n_plots_min, n_plots_max)
        areas = _partition_area(total_area, n_plots, frng)

        for j, area in enumerate(areas):
            p_seed = frng.randint(1, 2_000_000_000)
            prng = random.Random(p_seed)

            soil = prng.choice(_SOIL_BY_REGION[region.region_id])
            suitability = prng.choices(
                [SuitabilityClass.HIGH, SuitabilityClass.MODERATE,
                 SuitabilityClass.MARGINAL, SuitabilityClass.UNSUITABLE],
                weights=[0.35, 0.4, 0.2, 0.05])[0]

            # irrigation conditioned on region propensity
            if prng.random() < region.irrigation_propensity:
                irrig = prng.choice([IrrigationAccess.CANAL, IrrigationAccess.TUBEWELL])
            else:
                irrig = IrrigationAccess.RAINFED

            # water conditioned on irrigation + rainfall regime + area
            rain_factor = {"high": 1.3, "moderate": 1.0, "low": 0.7}[region.rainfall_regime]
            base_water_per_ha = {
                IrrigationAccess.CANAL: 6000,
                IrrigationAccess.TUBEWELL: 5000,
                IrrigationAccess.RAINFED: 1500,
            }[irrig]
            available_water = round(
                area * base_water_per_ha * rain_factor * prng.uniform(0.85, 1.15), 1)

            drainage = prng.choices(
                [DrainageClass.WELL, DrainageClass.MODERATE, DrainageClass.POOR],
                weights=[0.5, 0.35, 0.15])[0]

            # exposures conditioned on drainage/rainfall (plausible correlation)
            flood = prng.choices(list(Exposure),
                                 weights=[0.4, 0.3, 0.2, 0.1] if region.rainfall_regime != "high"
                                 else [0.2, 0.3, 0.3, 0.2])[0]
            drought = prng.choices(list(Exposure),
                                   weights=[0.2, 0.3, 0.3, 0.2] if region.rainfall_regime == "low"
                                   else [0.45, 0.3, 0.2, 0.05])[0]
            waterlog = (Exposure.HIGH if drainage == DrainageClass.POOR and prng.random() < 0.5
                        else prng.choice([Exposure.NONE, Exposure.LOW, Exposure.MODERATE]))

            prev = prng.choice(_PREV_CROP_POOL[season])
            rot = next((c.rotation_group for c in CROPS if c.crop_name == prev), None)

            # hazard zone = region + spatial cluster (correlated failure unit)
            hazard_zone = f"{region.region_id}-HZ{(j % 3) + 1}"

            plots.append(Plot(
                plot_id=f"{fid}-P{j+1:02d}", farmer_id=fid, region_id=region.region_id,
                area_ha=area, soil_group=soil, soil_suitability_class=suitability,
                drainage_class=drainage, irrigation_access=irrig,
                available_water_m3=available_water, previous_crop=prev,
                rotation_group=rot, flood_exposure=flood, drought_exposure=drought,
                waterlogging_exposure=waterlog, hazard_zone=hazard_zone,
                active_season=season, synthetic_seed=p_seed,
            ))

    manifest = DatasetManifest(
        dataset_version=DATASET_VERSION, master_seed=master_seed,
        n_farmers=len(farmers), n_collectives=n_collectives, n_plots=len(plots),
        n_crops=len(CROPS), n_regions=len(REGIONS), seasons=[season.value],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    prov = _build_provenance()
    # collectives appended as the final element to avoid disturbing existing
    # positional unpacking of the leading six values.
    return farmers, plots, CROPS, REGIONS, manifest, prov, collectives


_COLLECTIVE_NAMES = [
    "Sunrise", "Riverbend", "Greenfield", "Highland", "Meadow",
    "Delta", "Prairie", "Orchard", "Terrace", "Harvest",
]


def _build_collectives(n_collectives, season):
    """Assign collectives round-robin across regions; each is region+season bound."""
    out = []
    for k in range(n_collectives):
        region = REGIONS[k % len(REGIONS)]
        name = _COLLECTIVE_NAMES[k % len(_COLLECTIVE_NAMES)]
        out.append(Collective(
            collective_id=f"C{k+1:02d}",
            collective_name=f"{name} Collective",
            region_id=region.region_id,
            season=season,
            description=f"Synthetic {season.value} collective in {region.name}",
            active=True,
        ))
    return out


def _build_provenance() -> ProvenanceRegistry:
    """Field-family provenance for everything Phase 4 generates + open Phase-5 obligations."""
    reg = ProvenanceRegistry()

    reg.add(ProvenanceRecord(
        parameter="farmer.total_area_ha", provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
        value="generated", unit="ha",
        assumption=("Farm size drawn via Indian operational-holding categories "
                    "(marginal/small/semi-medium/medium/large). Category structure is "
                    "anchored to the Agriculture Census operational-holding classification; "
                    "the weighting proportions are an experimental assumption to be "
                    "sensitivity-tested, not asserted as census fact."),
        confidence=Confidence.MEDIUM,
        notes="Non-uniform by design; skewed toward marginal/small.",
    ))
    for p in ["farmer.cultivation_budget", "farmer.labour_capacity",
              "farmer.minimum_projected_income", "farmer.risk_tolerance"]:
        reg.add(ProvenanceRecord(
            parameter=p, provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
            value="generated",
            notes="Scaled with holding area so resources are never impossible for the size.",
        ))
    for p in ["plot.area_ha", "plot.soil_group", "plot.soil_suitability_class",
              "plot.drainage_class", "plot.irrigation_access", "plot.available_water_m3",
              "plot.previous_crop", "plot.flood_exposure", "plot.drought_exposure",
              "plot.waterlogging_exposure", "plot.hazard_zone"]:
        reg.add(ProvenanceRecord(
            parameter=p, provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
            value="generated",
            notes="Conditionally generated on region/irrigation/rainfall/drainage for plausibility.",
        ))

    # Phase-5 obligations: agronomic parameters that MUST be sourced before use.
    for p, unit in [
        ("crop.expected_yield", "kg/ha"),
        ("crop.cultivation_cost", "currency/ha"),
        ("crop.crop_water_requirement", "mm/season"),
        ("crop.irrigation_requirement", "mm/season"),
        ("crop.labour_requirement", "person-days/ha"),
        ("crop.price", "currency/kg"),
        ("crop.price_variability", "coefficient"),
        ("crop.market_absorption_proxy", "index"),
        ("crop.drought_sensitivity", "index"),
        ("crop.heat_sensitivity", "index"),
        ("crop.waterlogging_sensitivity", "index"),
    ]:
        reg.add(ProvenanceRecord(
            parameter=p, provenance_type=ProvenanceType.SYNTHETIC_EXPERIMENTAL,
            unit=unit, confidence=Confidence.REQUIRES_SOURCING,
            notes=("Phase 5. Must be populated from an authoritative Indian agricultural "
                   "source or peer-reviewed literature before the feasibility engine or "
                   "optimiser may treat it as valid. AGMARKNET arrivals must NOT be "
                   "labelled true demand; market_absorption_proxy must document derivation."),
        ))
    return reg
