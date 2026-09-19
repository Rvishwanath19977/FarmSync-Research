"""
Planning-gate + B1 tests. Ensures no ungrounded value enters optimisation and that
B1 respects hard constraints.
"""

import pytest

from farmsync.generate import generate_dataset, CROPS
from farmsync.planning import (
    is_admitted, projected_return, admitted_gate_report, ADMITTED_CROPS, EXCLUDED_CROPS,
)
from farmsync.baselines import run_b1, verify_hard_constraints


def test_gate_admits_only_grounded_crops():
    g = admitted_gate_report()
    assert g["gate_valid"] is True
    # without ingested operational data, vegetables lack cost -> excluded
    assert "tomato" in g["fully_excluded_crops"]
    assert len(g["admitted_crops"]) >= 11


def test_excluded_crops_raise_in_return():
    for crop in ("potato", "onion", "tomato"):
        with pytest.raises(ValueError):
            projected_return(crop, "R1", "rabi" if crop != "tomato" else "kharif", 1.0)


def test_state_yield_used_in_return():
    r1 = projected_return("rice", "R1", "kharif", 1.0)     # Punjab
    r2 = projected_return("rice", "R2", "kharif", 1.0)     # national
    assert r1["yield_scope"] == "STATE:Punjab"
    assert r1["net_return"] > r2["net_return"]             # higher Punjab yield -> higher return


def test_price_basis_is_labelled_msp_floor():
    import farmsync.planning as planning
    planning._INGESTED["prices"] = {}; planning._INGESTED["costs"] = {}; planning._INGESTED["active"] = False
    r = projected_return("wheat", "R1", "rabi", 1.0)
    assert r["price_basis"] == "MSP_FLOOR_REFERENCE"     # MSP as labelled reference, not market


def test_b1_runs_and_respects_hard_constraints():
    f, plots, *_ = generate_dataset(master_seed=1, n_farmers=120)
    res = run_b1(f, plots, CROPS)
    assert res.metrics["plots_allocated"] > 0
    assert res.total_return > 0
    chk = verify_hard_constraints(res, f, plots, CROPS)
    assert chk["hard_constraints_satisfied"], chk["violations"][:3]


def test_b1_reproducible():
    f, plots, *_ = generate_dataset(master_seed=5, n_farmers=100)
    a = run_b1(f, plots, CROPS)
    b = run_b1(f, plots, CROPS)
    assert a.total_return == b.total_return
    assert a.metrics["crop_area_ha"] == b.metrics["crop_area_ha"]


def test_b1_only_uses_admitted_crops():
    f, plots, *_ = generate_dataset(master_seed=3, n_farmers=100)
    res = run_b1(f, plots, CROPS)
    used = {a.crop for a in res.allocations}
    assert used <= set(ADMITTED_CROPS)


def test_budget_tightness_scales_utilisation():
    from farmsync.generate import generate_dataset, BUDGET_TIGHTNESS
    from farmsync.baselines import run_b1
    assert set(BUDGET_TIGHTNESS) == {"tight", "base", "loose"}
    util = {}
    for t in ("tight", "base", "loose"):
        f, plots, *_ = generate_dataset(master_seed=9, n_farmers=120, budget_tightness=t)
        util[t] = run_b1(f, plots, CROPS).metrics["land_utilisation_pct"]
    assert util["tight"] <= util["base"] <= util["loose"]   # tighter budget -> less land used


def test_b2_respects_market_absorption_cap_and_hard_constraints():
    from farmsync.generate import generate_dataset
    from farmsync.baselines import run_b2, verify_hard_constraints
    f, plots, *_ = generate_dataset(master_seed=9, n_farmers=150)
    b2 = run_b2(f, plots, CROPS)
    chk = verify_hard_constraints(b2, f, plots, CROPS)
    assert chk["hard_constraints_satisfied"]
    assert 0 <= b2.metrics["gini_farmer_return"] <= 1


def test_b3_is_more_equitable_than_b1():
    from farmsync.generate import generate_dataset
    from farmsync.baselines import run_b1, run_b3, verify_hard_constraints
    f, plots, *_ = generate_dataset(master_seed=9, n_farmers=150)
    b1 = run_b1(f, plots, CROPS); b3 = run_b3(f, plots, CROPS)
    assert verify_hard_constraints(b3, f, plots, CROPS)["hard_constraints_satisfied"]
    # fairness-aware B3 should not be less equal than B1 (Gini no higher)
    assert b3.metrics["gini_farmer_return"] <= b1.metrics["gini_farmer_return"] + 0.02
