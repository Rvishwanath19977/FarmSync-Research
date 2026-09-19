from copy import copy
from pathlib import Path

import pytest

from farmsync import climate
from farmsync.experiment import build_instance
from farmsync.ingest import operational as opdata
from farmsync.interactive_stress import (
    PROTOCOL_VERSION,
    WEATHER_ET0_MULT,
    MARKET_PRICE_MULT,
    MARKET_ABSORPTION_MULT,
    RESOURCE_MULT,
    analyse_fixed_final_plan,
    final_plan_hash,
)
from farmsync.planning import projected_return


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "farmsync" / "processed"


@pytest.fixture(autouse=True)
def clean_scoped_state():
    climate.clear_et0_mult()
    opdata.clear_market_mult()
    opdata.load(str(PROCESSED))
    yield
    climate.clear_et0_mult()
    opdata.clear_market_mult()


def _f1p3():
    inst = build_instance(20260812, tightness="base")
    plot = next(p for p in inst["plots"] if p.plot_id == "F0001-P03")
    farmer = next(f for f in inst["farmers"] if f.farmer_id == "F0001")

    pr = projected_return(
        "onion",
        plot.region_id,
        plot.active_season.value,
        plot.area_ha,
    )

    allocation = {
        "farmer_id": "F0001",
        "plot_id": "F0001-P03",
        "final_crop": "onion",
        "final_cash": pr["cash_net_return"],
    }

    return plot, farmer, allocation, pr


def test_protocol_uses_fixed_adverse_states_without_participation():
    assert PROTOCOL_VERSION == "interactive-stress-v1"
    assert WEATHER_ET0_MULT == pytest.approx(1.15)
    assert MARKET_PRICE_MULT == pytest.approx(0.90)
    assert MARKET_ABSORPTION_MULT == pytest.approx(0.85)
    assert RESOURCE_MULT == pytest.approx(0.85)


def test_final_plan_hash_is_order_independent_and_cash_sensitive():
    a = {
        "farmer_id": "F2",
        "plot_id": "P2",
        "final_crop": "wheat",
        "final_cash": 200,
    }
    b = {
        "farmer_id": "F1",
        "plot_id": "P1",
        "final_crop": "rice",
        "final_cash": 100,
    }

    assert final_plan_hash([a, b]) == final_plan_hash([b, a])

    b2 = dict(b)
    b2["final_cash"] = 101

    assert final_plan_hash([a, b]) != final_plan_hash([a, b2])


def test_fixed_plan_market_cash_matches_canonical_formula():
    plot, farmer, allocation, pr = _f1p3()

    out = analyse_fixed_final_plan(
        [allocation],
        {plot.plot_id: plot},
        {farmer.farmer_id: farmer},
        dataset_hash="test-dataset",
        final_plan_revision=1,
    )

    assert out["available"] is True
    assert out["reoptimization"] is False
    assert out["participation_uncertainty"] is False

    market = out["scenarios"]["UM"]["market"]

    expected = round(
        pr["price_per_kg"]
        * 0.90
        * pr["yield_kg_ha"]
        * plot.area_ha
        - pr["cash_cost"],
        0,
    )

    assert market["baseline_cash_net_return"] == pytest.approx(
        pr["cash_net_return"]
    )
    assert market["stressed_cash_net_return"] == pytest.approx(expected)


def test_weather_stress_changes_water_requirement_not_yield_or_allocation():
    plot, farmer, allocation, pr = _f1p3()

    out = analyse_fixed_final_plan(
        [allocation],
        {plot.plot_id: plot},
        {farmer.farmer_id: farmer},
    )

    w = out["scenarios"]["UW"]["weather"]["details"][0]

    assert w["et0_multiplier"] == pytest.approx(1.15)
    assert w["stressed_cwr_mm"] >= w["baseline_cwr_mm"]
    assert w["stressed_nir_mm"] >= w["baseline_nir_mm"]

    assert out["n_realised_plots"] == 1
    assert allocation["final_crop"] == "onion"

    assert "weather_yield_loss" in out["excluded"]


def test_resource_stress_reports_exposure_without_scaling_cash():
    plot, farmer, allocation, pr = _f1p3()

    constrained = copy(farmer)
    constrained.cultivation_budget = pr["cash_cost"]
    constrained.labour_capacity = pr["labour_pd"]

    out = analyse_fixed_final_plan(
        [allocation],
        {plot.plot_id: plot},
        {farmer.farmer_id: constrained},
    )

    r = out["scenarios"]["UR"]["resources"]

    # Baseline capacity exactly covers the allocation, but the 0.85 stress does not.
    assert r["n_exposed_farmers"] == 1
    assert r["n_exposed_plots"] == 1

    # Resource exposure is not converted into invented cash loss.
    assert out["baseline"]["cash_net_return"] == pytest.approx(
        pr["cash_net_return"]
    )


def test_joint_contains_only_w_m_r_and_no_up():
    plot, farmer, allocation, _pr = _f1p3()

    out = analyse_fixed_final_plan(
        [allocation],
        {plot.plot_id: plot},
        {farmer.farmer_id: farmer},
    )

    assert set(out["scenarios"]) == {"UW", "UM", "UR", "UJ"}
    assert out["scenarios"]["UJ"]["channels"] == ["W", "M", "R"]
    assert "UP_participation" in out["excluded"]


def test_analysis_refuses_mixed_economic_provenance():
    plot, farmer, allocation, _pr = _f1p3()

    bad = dict(allocation)
    bad["final_cash"] += 50000

    out = analyse_fixed_final_plan(
        [bad],
        {plot.plot_id: plot},
        {farmer.farmer_id: farmer},
    )

    assert out["available"] is False
    assert "does not match" in out["reason"].lower()
    assert out["economic_mismatches"]


def test_analysis_does_not_leave_global_uncertainty_state():
    plot, farmer, allocation, _pr = _f1p3()

    base_et0 = climate._et0_for(
        plot.region_id,
        plot.active_season.value,
    )
    base_price = projected_return(
        "onion",
        plot.region_id,
        plot.active_season.value,
        plot.area_ha,
    )["price_per_kg"]

    analyse_fixed_final_plan(
        [allocation],
        {plot.plot_id: plot},
        {farmer.farmer_id: farmer},
    )

    assert climate._et0_for(
        plot.region_id,
        plot.active_season.value,
    ) == pytest.approx(base_et0)

    after_price = projected_return(
        "onion",
        plot.region_id,
        plot.active_season.value,
        plot.area_ha,
    )["price_per_kg"]

    assert after_price == pytest.approx(base_price)


def test_absorption_proxy_is_scaled_by_full_selected_dataset_area():
    inst = build_instance(
        20260812,
        tightness="base",
    )

    plots = {
        p.plot_id: p
        for p in inst["plots"]
    }

    farmers = {
        f.farmer_id: f
        for f in inst["farmers"]
    }

    plot = plots["F0001-P03"]

    pr = projected_return(
        "onion",
        plot.region_id,
        plot.active_season.value,
        plot.area_ha,
    )

    allocation = {
        "farmer_id": "F0001",
        "plot_id": "F0001-P03",
        "final_crop": "onion",
        "final_cash": pr["cash_net_return"],
    }

    out = analyse_fixed_final_plan(
        [allocation],
        plots,
        farmers,
    )

    market = out["scenarios"]["UM"]["market"]
    onion = market["absorption"]["onion"]

    total_area = sum(
        p.area_ha for p in inst["plots"]
    )

    proxy = opdata.op_absorption("onion")

    assert out["selected_dataset_area_ha"] == pytest.approx(
        total_area,
        abs=0.001,
    )

    assert onion["baseline_area_cap_ha"] == pytest.approx(
        proxy * total_area,
        abs=0.001,
    )

    assert onion["stressed_area_cap_ha"] == pytest.approx(
        proxy * 0.85 * total_area,
        abs=0.001,
    )

    # Critical dimensional regression:
    # realised hectares are compared against a derived hectare cap,
    # never directly against the dimensionless absorption proxy.
    assert onion["realised_area_ha"] == pytest.approx(
        plot.area_ha,
        abs=0.001,
    )

    assert onion["stressed_area_cap_ha"] > 1.0
