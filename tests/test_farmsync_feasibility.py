"""
Phase 6 tests — deterministic agronomic feasibility. Uses the real generator so
plots/crops are internally consistent; also constructs targeted edge cases.
"""

import copy

from farmsync.generate import generate_dataset, CROPS
from farmsync.feasibility import (
    assess_plot_crop, feasible_crops_for_plot, FeasibilityConfig,
    SEASON_INCOMPATIBLE, SOIL_INCOMPATIBLE, WATER_INSUFFICIENT, ROTATION_RESTRICTED,
    WATERLOGGING_RISK, FARMER_EXCLUDED, POST_PLANTING_LOCK,
)
from farmsync.schemas import Season, SuitabilityClass, Exposure, DrainageClass

CROP_BY_NAME = {c.crop_name: c for c in CROPS}


def _one_plot(season=Season.KHARIF):
    _, plots, *_ = generate_dataset(master_seed=7, n_farmers=30, season=season)
    return plots[0], plots


def test_season_incompatible_flagged():
    plot, _ = _one_plot(Season.KHARIF)
    wheat = CROP_BY_NAME["wheat"]              # rabi crop on a kharif plot
    res = assess_plot_crop(plot, wheat)
    assert not res.feasible
    assert SEASON_INCOMPATIBLE in res.reasons


def test_unsuitable_land_class_flagged():
    plot, _ = _one_plot()
    p = copy.deepcopy(plot)
    p.soil_suitability_class = SuitabilityClass.UNSUITABLE
    res = assess_plot_crop(p, CROP_BY_NAME["rice"])
    assert SOIL_INCOMPATIBLE in res.reasons


def test_waterlogging_risk_for_non_rice_but_not_rice():
    plot, _ = _one_plot()
    p = copy.deepcopy(plot)
    p.waterlogging_exposure = Exposure.HIGH
    tomato = assess_plot_crop(p, CROP_BY_NAME["tomato"])
    rice = assess_plot_crop(p, CROP_BY_NAME["rice"])
    assert WATERLOGGING_RISK in tomato.reasons
    assert WATERLOGGING_RISK not in rice.reasons     # rice tolerates ponding


def test_monocropping_restricted():
    plot, _ = _one_plot()
    p = copy.deepcopy(plot)
    p.previous_crop = "rice"
    res = assess_plot_crop(p, CROP_BY_NAME["rice"])
    assert ROTATION_RESTRICTED in res.reasons


def test_farmer_exclusion_flagged():
    plot, _ = _one_plot()
    res = assess_plot_crop(plot, CROP_BY_NAME["cotton"], exclusions={"cotton"})
    assert FARMER_EXCLUDED in res.reasons


def test_post_planting_lock():
    plot, _ = _one_plot()
    res = assess_plot_crop(plot, CROP_BY_NAME["maize"],
                           commitment_state="PLANTED", planted_crop="rice")
    assert POST_PLANTING_LOCK in res.reasons


def test_water_insufficient_when_water_tiny():
    # R1/R2 have sourced ET0 -> CWR exists -> water is actually evaluated
    _, plots, *_ = generate_dataset(master_seed=3, n_farmers=60)
    target = next((p for p in plots if p.region_id in ("R1", "R2")), None)
    assert target is not None
    p = copy.deepcopy(target)
    p.available_water_m3 = 1.0                 # force insufficiency
    p.waterlogging_exposure = Exposure.NONE
    p.previous_crop = None
    res = assess_plot_crop(p, CROP_BY_NAME["rice"] if p.active_season.value == "kharif"
                           else CROP_BY_NAME["wheat"])
    assert res.checks["water"] in ("INSUFFICIENT", "UNKNOWN")
    if res.checks["water"] == "INSUFFICIENT":
        assert WATER_INSUFFICIENT in res.reasons


def test_water_evaluated_for_all_regions_now():
    # all five regions have ET0 -> water is decided (OK/INSUFFICIENT), never UNKNOWN
    _, plots, *_ = generate_dataset(master_seed=3, n_farmers=80)
    seen = set()
    for p in plots:
        res = assess_plot_crop(p, CROP_BY_NAME["rice"] if p.active_season.value == "kharif"
                               else CROP_BY_NAME["wheat"])
        seen.add(res.checks["water"])
    assert "UNKNOWN" not in seen                 # every region now has CWR


def test_budget_labour_deferred_not_fabricated():
    plot, _ = _one_plot()
    res = assess_plot_crop(plot, CROP_BY_NAME["rice"])
    assert res.checks["budget"] == "NOT_EVALUATED"
    assert res.checks["labour"] == "NOT_EVALUATED"


def test_feasible_crops_for_plot_returns_all_crops():
    plot, _ = _one_plot()
    result = feasible_crops_for_plot(plot, CROPS)
    assert len(result) == 14
    # at least one crop should be feasible on a normal plot in its season
    assert any(r.feasible for r in result.values())


def test_independent_constraint_verification():
    # spirit of spec §28: independently re-verify a hard invariant after assessment
    plot, _ = _one_plot()
    for c in CROPS:
        res = assess_plot_crop(plot, c)
        # a feasible result must have NO reason codes; infeasible must have >=1
        assert (res.feasible and not res.reasons) or (not res.feasible and res.reasons)
