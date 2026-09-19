"""Tests for fairness-v2, the ILP baseline family, and the paired-instance harness."""
import os, pytest
RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(RAW, "des_apy")),
                                reason="raw sources not present")
from farmsync.ingest.run_ingest import run
from farmsync.ingest import operational as opdata
from farmsync.generate import generate_dataset, CROPS
from farmsync.baselines import verify_hard_constraints
from farmsync import fairness as fair
from farmsync import experiment as exp

def _load():
    run(RAW, os.path.join(RAW, "..", "processed"))
    opdata.load(os.path.join(RAW, "..", "processed"))

def test_fairness_v2_primary_metrics_present_and_valid():
    _load()
    from farmsync.baselines import run_b1
    f, plots, *_ = generate_dataset(master_seed=9, n_farmers=120)
    b1 = run_b1(f, plots, CROPS)
    rep = fair.fairness_report(b1, f, b1_reference=fair.farmer_cash(b1))
    assert 0 <= rep["primary"]["per_ha_gini_all"] <= 1
    assert 0 <= rep["primary"]["participation_rate_pct"] <= 100
    assert "benefit_loss_vs_b1" in rep["primary"] and "fixed_cohort_mean_cash" in rep["primary"]
    assert rep["impl_version"] == "fairness-v2"
    opdata._DATA["loaded"] = False

def test_ilp_baselines_optimal_and_feasible():
    _load()
    from farmsync.ilp_reference import run_b1_ilp, run_b2_ilp, run_b3_ilp
    f, plots, *_ = generate_dataset(master_seed=9, n_farmers=120)
    for res in [run_b1_ilp(f, plots, CROPS), run_b2_ilp(f, plots, CROPS),
                run_b3_ilp(f, plots, CROPS, epsilon=0.95)]:
        assert res.solver["status"] == "Optimal"
        assert verify_hard_constraints(res, f, plots, CROPS)["hard_constraints_satisfied"]
    opdata._DATA["loaded"] = False

def test_harness_instance_deterministic_and_unique():
    _load()
    seeds = [9, 10]
    h9a = exp.build_instance(9)["record"]["instance_hash"]
    h9b = exp.build_instance(9)["record"]["instance_hash"]
    h10 = exp.build_instance(10)["record"]["instance_hash"]
    assert h9a == h9b and h9a != h10
    opdata._DATA["loaded"] = False

def test_b3_epsilon_improves_worst_off_below_one():
    _load()
    from farmsync.ilp_reference import run_b3_ilp
    f, plots, *_ = generate_dataset(master_seed=9, n_farmers=120)
    lo = run_b3_ilp(f, plots, CROPS, epsilon=0.9).solver["min_normalized_return"]
    hi = run_b3_ilp(f, plots, CROPS, epsilon=1.0).solver["min_normalized_return"]
    assert lo >= hi   # relaxing the efficiency floor never worsens the worst-off
    opdata._DATA["loaded"] = False


def test_canonical_b3_epsilon_is_095_everywhere():
    from farmsync import config
    from farmsync.ilp_reference import run_b1_ilp, run_b2_ilp, run_b3_ilp
    import inspect
    from farmsync.experiment import run_baselines_on
    assert config.CANONICAL_B3_EPSILON == 0.95
    _load()
    # The default-epsilon contract (epsilon=None -> CANONICAL_B3_EPSILON, recorded in solver meta)
    # is instance-size-independent, so it is verified on a TINY instance to avoid a redundant
    # expensive canonical solve. Real-scale B1/B2/B3 optimality/feasibility is validated by
    # test_ilp_baselines_optimal_and_feasible and the other n=120 tests in this file.
    f, plots, *_ = generate_dataset(master_seed=9, n_farmers=8)
    b3 = run_b3_ilp(f, plots, CROPS)          # no epsilon -> canonical; small solve
    assert b3.solver["status"] == "Optimal"
    assert b3.solver["epsilon"] == 0.95
    # harness default must not silently be 0.90
    src = inspect.getsource(run_baselines_on)
    assert "epsilon=0.9)" not in src and "0.9," not in src
    opdata._DATA["loaded"] = False


def test_b2_tstar_single_canonical_value():
    from farmsync import config, fairness as fair
    from farmsync.ilp_reference import b2_ilp_total, run_b2_ilp
    _load()
    f, plots, *_ = generate_dataset(master_seed=9, n_farmers=120)
    t_obj = b2_ilp_total(f, plots, CROPS)["b2_ilp_cash_total"]
    t_alloc = round(sum(fair.farmer_cash(run_b2_ilp(f, plots, CROPS)).values()))
    assert abs(t_obj - t_alloc) <= config.TSTAR_TOLERANCE   # documented tolerance ₹1
    opdata._DATA["loaded"] = False
