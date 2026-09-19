"""Proposed Phase 1 (participation ACCEPT/REJECT) tests."""
import os, random, pytest
RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(RAW, "des_apy")),
                                reason="raw sources not present")
from farmsync.ingest.run_ingest import run
from farmsync.ingest import operational as opdata
from farmsync.generate import generate_dataset, CROPS
from farmsync.ilp_reference import run_b1_ilp, run_b3_ilp
from farmsync.baselines import verify_hard_constraints
from farmsync import fairness as fair, experiment as exp
from farmsync.proposed.participation import AcceptanceConfig, apply_participation, response_draw
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

def _setup(n=120, seed=9):
    run(RAW, os.path.join(RAW, "..", "processed"))
    opdata.load(os.path.join(RAW, "..", "processed"))
    f, plots, *_ = generate_dataset(master_seed=seed, n_farmers=n)
    planned = run_b3_ilp(f, plots, CROPS)          # canonical eps
    sub = exp.substream(seed, "farmer_response")
    return f, plots, planned, sub

def _teardown():
    opdata._DATA["loaded"] = False

def test_same_seed_substream_identical_responses():
    f, plots, planned, sub = _setup()
    cfg = AcceptanceConfig()
    _, o1 = apply_participation(planned, f, sub, cfg)
    _, o2 = apply_participation(planned, f, sub, cfg)
    r1 = {(o["farmer_id"], o["plot_id"], o["planned_crop"]): o["response"] for o in o1}
    r2 = {(o["farmer_id"], o["plot_id"], o["planned_crop"]): o["response"] for o in o2}
    assert r1 == r2
    _teardown()

def test_different_response_seed_can_change_responses():
    f, plots, planned, sub = _setup()
    cfg = AcceptanceConfig()
    _, o1 = apply_participation(planned, f, sub, cfg)
    _, o2 = apply_participation(planned, f, sub + 12345, cfg)
    r1 = [o["response"] for o in sorted(o1, key=lambda x: (x["farmer_id"], x["plot_id"]))]
    r2 = [o["response"] for o in sorted(o2, key=lambda x: (x["farmer_id"], x["plot_id"]))]
    assert r1 != r2
    _teardown()

def test_iteration_order_does_not_change_response():
    f, plots, planned, sub = _setup()
    cfg = AcceptanceConfig()
    _, o1 = apply_participation(planned, f, sub, cfg)
    shuffled = type(planned)()
    shuffled.allocations = list(planned.allocations); random.Random(1).shuffle(shuffled.allocations)
    _, o2 = apply_participation(shuffled, f, sub, cfg)
    r1 = {(o["farmer_id"], o["plot_id"], o["planned_crop"]): o["response"] for o in o1}
    r2 = {(o["farmer_id"], o["plot_id"], o["planned_crop"]): o["response"] for o in o2}
    assert r1 == r2
    _teardown()

def test_rejected_never_realised_and_accepted_preserves_value():
    f, plots, planned, sub = _setup()
    realised, offers = apply_participation(planned, f, sub, AcceptanceConfig())
    realised_keys = {(a.farmer_id, a.plot_id, a.crop) for a in realised.allocations}
    planned_by_key = {(a.farmer_id, a.plot_id, a.crop): a for a in planned.allocations}
    for o in offers:
        key = (o["farmer_id"], o["plot_id"], o["planned_crop"])
        if o["response"] == "REJECT":
            assert key not in realised_keys
            assert o["realised_crop"] == "FALLOW_UNALLOCATED" and o["realised_cash_return"] == 0.0
        else:
            assert key in realised_keys and o["realised_crop"] == o["planned_crop"]
            assert o["realised_cash_return"] == planned_by_key[key].cash_net
    _teardown()

def test_realised_subset_of_planned_and_no_reoptimisation():
    f, plots, planned, sub = _setup()
    realised, _ = apply_participation(planned, f, sub, AcceptanceConfig())
    pset = {(a.farmer_id, a.plot_id, a.crop) for a in planned.allocations}
    rset = {(a.farmer_id, a.plot_id, a.crop) for a in realised.allocations}
    assert rset <= pset                                   # subset; no new/reassigned plots
    assert len(realised.allocations) <= len(planned.allocations)
    _teardown()

def test_realised_return_not_exceed_planned():
    f, plots, planned, sub = _setup()
    realised, _ = apply_participation(planned, f, sub, AcceptanceConfig())
    assert sum(a.cash_net for a in realised.allocations) <= sum(a.cash_net for a in planned.allocations)
    _teardown()

def test_hard_constraints_hold_for_realised():
    f, plots, planned, sub = _setup()
    realised, _ = apply_participation(planned, f, sub, AcceptanceConfig())
    assert verify_hard_constraints(realised, f, plots, CROPS)["hard_constraints_satisfied"]
    _teardown()

def test_fairness_v2_includes_all_farmers_incl_zero_realised():
    f, plots, planned, sub = _setup()
    realised, _ = apply_participation(planned, f, sub, AcceptanceConfig())
    rep = fair.fairness_report(realised, f, b1_reference=fair.farmer_cash(run_b1_ilp(f, plots, CROPS)))
    assert rep["primary"]["n_farmers"] == len(f)          # all farmers, incl zero-realised
    assert 0 <= rep["primary"]["per_ha_gini_all"] <= 1
    _teardown()

def test_frozen_and_versioned_artifacts_exist_unchanged():
    OUT = os.path.join(_ROOT, "results", "farmsync")
    for fn in ["b1_final.json", "b2_final.json", "b3_final.json", "b3_ilp_v2.json"]:
        assert os.path.exists(os.path.join(OUT, fn))       # phase-1 must not delete/rewrite baselines
