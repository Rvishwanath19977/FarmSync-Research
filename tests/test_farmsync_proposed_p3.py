"""Proposed Phase 3 (stability-aware reoptimisation) tests."""
import os, pytest
from farmsync.proposed import commitment as cm
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
_have_raw = os.path.exists(os.path.join(RAW, "des_apy"))


def _offers(n=60):
    return [{"farmer_id": f"F{i}", "plot_id": f"P{i}", "planned_crop": "rice",
             "status": "REALISED" if i % 6 else "REJECTED_FALLOW"} for i in range(n)]


def test_mixed_scenario_deterministic():
    o = _offers()
    s1 = cm.mixed_commitment_scenario(o, "P3_MIXED_V1")
    s2 = cm.mixed_commitment_scenario(o, "P3_MIXED_V1")
    assert {k: v["state"] for k, v in s1.items()} == {k: v["state"] for k, v in s2.items()}


def test_mixed_scenario_approx_thirds():
    o = [{"farmer_id": f"F{i}", "plot_id": f"P{i}", "planned_crop": "rice", "status": "REALISED"}
         for i in range(300)]
    s = cm.mixed_commitment_scenario(o, "P3_MIXED_V1")
    from collections import Counter
    c = Counter(v["lock"] for v in s.values())
    n = len(o)
    for lock in (cm.LOCK_FLEXIBLE, cm.LOCK_SOFT, cm.LOCK_HARD):
        assert 0.25 <= c[lock] / n <= 0.42          # approximately one-third each


def test_rejected_stays_terminal_in_scenario():
    s = cm.mixed_commitment_scenario(_offers(), "P3_MIXED_V1")
    rej = [v for v in s.values() if not v["accepted"]]
    assert rej and all(v["lock"] == "REJECTED_TERMINAL" for v in rej)


# ---- solve-based tests (need raw data + solver) ----
pytestmark_solve = pytest.mark.skipif(not _have_raw, reason="raw sources not present")


def _setup(n=120, seed=9):
    from farmsync.ingest.run_ingest import run
    from farmsync.ingest import operational as opdata
    from farmsync.generate import generate_dataset, CROPS
    from farmsync.ilp_reference import run_b3_ilp, b2_ilp_total
    from farmsync import experiment as exp
    from farmsync.proposed.participation import AcceptanceConfig, apply_participation
    run(RAW, os.path.join(RAW, "..", "processed")); opdata.load(os.path.join(RAW, "..", "processed"))
    f, plots, *_ = generate_dataset(master_seed=seed, n_farmers=n)
    tstar = b2_ilp_total(f, plots, CROPS)["b2_ilp_cash_total"]
    planned = run_b3_ilp(f, plots, CROPS, tstar=tstar)
    realised, offers = apply_participation(planned, f, exp.substream(seed, "farmer_response"), AcceptanceConfig())
    scen = cm.mixed_commitment_scenario(offers, "P3_MIXED_V1")
    return f, plots, CROPS, scen, offers


@pytestmark_solve
def test_hard_locks_never_change_and_constraints_valid():
    from farmsync.proposed import reoptimize as ro
    from farmsync.baselines import verify_hard_constraints
    from farmsync.ingest import operational as opdata
    f, plots, CROPS, scen, _ = _setup()
    e_star, _ = ro.max_economic(f, plots, CROPS, scen)
    t_floor, _ = ro.fairness_floor(f, plots, CROPS, scen, e_star)
    r = ro.solve_phase3(f, plots, CROPS, scen, 0.1, e_star, t_floor)
    assert r.phase3["status"] == "Optimal" and r.phase3["hard_lock_ok"] and r.phase3["hard_lock_changes"] == 0
    assert verify_hard_constraints(r, f, plots, CROPS)["hard_constraints_satisfied"]
    # every hard-lock plot keeps its committed crop
    got = {(a.farmer_id, a.plot_id): a.crop for a in r.allocations}
    for (fid, pid), info in scen.items():
        if info["lock"] == cm.LOCK_HARD:
            assert got.get((fid, pid)) == info["crop"]
    opdata._DATA["loaded"] = False


@pytestmark_solve
def test_rejected_crop_not_reoffered_unchanged():
    from farmsync.proposed import reoptimize as ro
    from farmsync.ingest import operational as opdata
    f, plots, CROPS, scen, _ = _setup()
    e_star, _ = ro.max_economic(f, plots, CROPS, scen)
    t_floor, _ = ro.fairness_floor(f, plots, CROPS, scen, e_star)
    r = ro.solve_phase3(f, plots, CROPS, scen, 0.0, e_star, t_floor)
    got = {(a.farmer_id, a.plot_id): a.crop for a in r.allocations}
    for (fid, pid), info in scen.items():
        if info["lock"] == "REJECTED_TERMINAL" and (fid, pid) in got:
            assert got[(fid, pid)] != info["crop"]      # original rejected crop must not reappear
    opdata._DATA["loaded"] = False


@pytestmark_solve
def test_lambda_monotonicity_disruption_non_increasing():
    from farmsync.proposed import reoptimize as ro
    from farmsync.ingest import operational as opdata
    f, plots, CROPS, scen, _ = _setup()
    e_star, _ = ro.max_economic(f, plots, CROPS, scen)
    t_floor, _ = ro.fairness_floor(f, plots, CROPS, scen, e_star)
    soft = [ro.solve_phase3(f, plots, CROPS, scen, lam, e_star, t_floor).phase3["changed_soft_area"]
            for lam in (0.0, 0.5, 1.0)]
    assert soft[0] >= soft[1] >= soft[2]                # higher stability pref => no more disruption
    opdata._DATA["loaded"] = False


@pytestmark_solve
def test_phase3_deterministic_repeat():
    from farmsync.proposed import reoptimize as ro
    from farmsync.ingest import operational as opdata
    f, plots, CROPS, scen, _ = _setup()
    e_star, _ = ro.max_economic(f, plots, CROPS, scen)
    t_floor, _ = ro.fairness_floor(f, plots, CROPS, scen, e_star)
    a = ro.solve_phase3(f, plots, CROPS, scen, 0.25, e_star, t_floor)
    b = ro.solve_phase3(f, plots, CROPS, scen, 0.25, e_star, t_floor)
    ka = sorted((x.farmer_id, x.plot_id, x.crop) for x in a.allocations)
    kb = sorted((x.farmer_id, x.plot_id, x.crop) for x in b.allocations)
    assert ka == kb
    opdata._DATA["loaded"] = False


def test_phase1_phase2_artifacts_unchanged_present():
    OUT = os.path.join(_ROOT, "results", "farmsync", "proposed")
    for fn in ["p1_participation_result.json", "p2_commitment_result.json"]:
        assert os.path.exists(os.path.join(OUT, fn))
