"""Proposed Phase 4 (producer concentration) + Phase-3 correction tests."""
import os, pytest
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(RAW, "des_apy")),
                                reason="raw sources not present")


def _setup(n=120, seed=9):
    from farmsync.ingest.run_ingest import run
    from farmsync.ingest import operational as opdata
    from farmsync.generate import generate_dataset, CROPS
    from farmsync.ilp_reference import run_b3_ilp, b2_ilp_total
    from farmsync import experiment as exp
    from farmsync.proposed.participation import AcceptanceConfig, apply_participation
    from farmsync.proposed import commitment as cm
    run(RAW, os.path.join(RAW, "..", "processed")); opdata.load(os.path.join(RAW, "..", "processed"))
    f, plots, *_ = generate_dataset(master_seed=seed, n_farmers=n)
    tstar = b2_ilp_total(f, plots, CROPS)["b2_ilp_cash_total"]
    planned = run_b3_ilp(f, plots, CROPS, tstar=tstar)
    realised, offers = apply_participation(planned, f, exp.substream(seed, "farmer_response"), AcceptanceConfig())
    scen = cm.mixed_commitment_scenario(offers, "P3_MIXED_V1")
    return f, plots, CROPS, scen


def _teardown():
    from farmsync.ingest import operational as opdata
    opdata._DATA["loaded"] = False


# ---------- Phase-3 corrections ----------
def test_phase3_enforces_both_eps_and_floor():
    from farmsync.proposed import reoptimize as ro
    from farmsync import fairness as fair, config
    f, plots, CROPS, scen = _setup()
    e_star, _ = ro.max_economic(f, plots, CROPS, scen)
    t_floor, _ = ro.fairness_floor(f, plots, CROPS, scen, e_star)
    r = ro.solve_phase3(f, plots, CROPS, scen, 0.05, e_star, t_floor)
    assert r.phase3["status"] == "Optimal"
    total = sum(a.cash_net for a in r.allocations)
    assert total >= config.CANONICAL_B3_EPSILON * e_star - 1        # (i) E >= 0.95 E*
    A = {x.farmer_id: x.total_area_ha for x in f}
    cash = fair.farmer_cash(r)
    min_norm = min(cash[fid] / A[fid] for fid in cash)
    assert min_norm >= t_floor - 1e-6                               # (ii) min-norm >= t_floor
    _teardown()


def test_final_fairness_tolerance_is_exact_zero():
    from farmsync import config
    from farmsync.proposed import reoptimize as ro
    assert config.FAIRNESS_FLOOR_NUMERIC_TOL == 0.0
    f, plots, CROPS, scen = _setup()
    e_star, _ = ro.max_economic(f, plots, CROPS, scen)
    t_floor, _ = ro.fairness_floor(f, plots, CROPS, scen, e_star)
    assert ro.solve_phase3(f, plots, CROPS, scen, 0.0, e_star, t_floor).phase3["status"] == "Optimal"
    _teardown()


# ---------- Phase-4 ----------
def test_alpha1_reproduces_corrected_phase3_lambda005():
    from farmsync.proposed import reoptimize as ro, concentration as co
    from farmsync import config
    f, plots, CROPS, scen = _setup()
    e_star, _ = ro.max_economic(f, plots, CROPS, scen)
    t_floor, _ = ro.fairness_floor(f, plots, CROPS, scen, e_star)
    p3 = ro.solve_phase3(f, plots, CROPS, scen, 0.05, e_star, t_floor)
    ea, _ = co.max_economic_alpha(f, plots, CROPS, scen, 1.0)
    ta, _ = co.fairness_floor_alpha(f, plots, CROPS, scen, 1.0, ea)
    r4 = co.solve_phase4(f, plots, CROPS, scen, 0.05, 1.0, ea, ta)
    assert abs(sum(a.cash_net for a in r4.allocations) - sum(a.cash_net for a in p3.allocations)) <= config.TSTAR_TOLERANCE
    _teardown()


def test_shares_sum_to_one_hhi_valid_effective_reciprocal():
    from farmsync.proposed import reoptimize as ro, concentration as co
    f, plots, CROPS, scen = _setup()
    ea, _ = co.max_economic_alpha(f, plots, CROPS, scen, 0.5)
    ta, _ = co.fairness_floor_alpha(f, plots, CROPS, scen, 0.5, ea)
    r = co.solve_phase4(f, plots, CROPS, scen, 0.05, 0.5, ea, ta)
    conc, summ = co.concentration_metrics(r, plots, alpha=0.5)
    # recompute shares directly to check they sum to 1
    pby = {p.plot_id: p for p in plots}
    from farmsync.planning import op_yield_value
    from collections import defaultdict
    q = defaultdict(dict)
    for a in r.allocations:
        p = pby[a.plot_id]; y, _ = op_yield_value(a.crop, p.region_id, p.active_season.value)
        q[a.crop][a.farmer_id] = q[a.crop].get(a.farmer_id, 0.0) + (y or 0) * a.area_ha
    for crop, fm in q.items():
        Q = sum(fm.values())
        if Q > 0:
            assert abs(sum(v / Q for v in fm.values()) - 1.0) < 1e-6
            hhi = conc[crop]["HHI"]; assert 0 < hhi <= 1.0
            if hhi > 0:
                assert abs(conc[crop]["effective_producers"] - round(1.0 / hhi, 2)) < 0.02
    _teardown()


def test_concentration_constraint_satisfied_no_violations():
    from farmsync.proposed import reoptimize as ro, concentration as co
    f, plots, CROPS, scen = _setup()
    for alpha in (0.5, 0.4):
        ea, est = co.max_economic_alpha(f, plots, CROPS, scen, alpha)
        if est != "Optimal":
            continue
        ta, _ = co.fairness_floor_alpha(f, plots, CROPS, scen, alpha, ea)
        r = co.solve_phase4(f, plots, CROPS, scen, 0.05, alpha, ea, ta)
        _, summ = co.concentration_metrics(r, plots, alpha=alpha)
        assert summ["target_violations"] == 0 and summ["max_LPS"] <= alpha + 1e-6
    _teardown()


def test_hard_locks_never_change_under_alpha():
    from farmsync.proposed import concentration as co, commitment as cm
    from farmsync.baselines import verify_hard_constraints
    f, plots, CROPS, scen = _setup()
    ea, _ = co.max_economic_alpha(f, plots, CROPS, scen, 0.4)
    ta, _ = co.fairness_floor_alpha(f, plots, CROPS, scen, 0.4, ea)
    r = co.solve_phase4(f, plots, CROPS, scen, 0.05, 0.4, ea, ta)
    assert r.phase3["hard_lock_ok"] and r.phase3["hard_lock_changes"] == 0
    assert verify_hard_constraints(r, f, plots, CROPS)["hard_constraints_satisfied"]
    got = {(a.farmer_id, a.plot_id): a.crop for a in r.allocations}
    for (fid, pid), info in scen.items():
        if info["lock"] == cm.LOCK_HARD:
            assert got.get((fid, pid)) == info["crop"]
    _teardown()


def test_infeasible_alpha_handled_honestly():
    from farmsync.proposed import concentration as co
    f, plots, CROPS, scen = _setup()
    ea, est = co.max_economic_alpha(f, plots, CROPS, scen, 0.05)   # extreme -> expect infeasible
    assert est != "Optimal" and ea is None                        # no pseudo-solution extracted
    diag = co.diagnose_infeasibility(f, plots, CROPS, scen, 0.05)
    assert isinstance(diag, list) and len(diag) >= 1              # honest cause identification
    _teardown()


def test_rejected_crop_excluded_and_outputs_are_recommendations():
    from farmsync.proposed import concentration as co
    import json
    f, plots, CROPS, scen = _setup()
    ea, _ = co.max_economic_alpha(f, plots, CROPS, scen, 0.5)
    ta, _ = co.fairness_floor_alpha(f, plots, CROPS, scen, 0.5, ea)
    r = co.solve_phase4(f, plots, CROPS, scen, 0.05, 0.5, ea, ta)
    got = {(a.farmer_id, a.plot_id): a.crop for a in r.allocations}
    for (fid, pid), info in scen.items():
        if info["lock"] == "REJECTED_TERMINAL" and (fid, pid) in got:
            assert got[(fid, pid)] != info["crop"]
    res = json.load(open(os.path.join(_ROOT, "results", "farmsync", "proposed", "p4_concentration_result.json")))
    assert res["revised_requires_renewed_consent"] is True
    _teardown()


def test_phase4_deterministic_repeat():
    from farmsync.proposed import concentration as co
    f, plots, CROPS, scen = _setup()
    ea, _ = co.max_economic_alpha(f, plots, CROPS, scen, 0.5)
    ta, _ = co.fairness_floor_alpha(f, plots, CROPS, scen, 0.5, ea)
    a = co.solve_phase4(f, plots, CROPS, scen, 0.05, 0.5, ea, ta)
    b = co.solve_phase4(f, plots, CROPS, scen, 0.05, 0.5, ea, ta)
    assert (sorted((x.farmer_id, x.plot_id, x.crop) for x in a.allocations)
            == sorted((x.farmer_id, x.plot_id, x.crop) for x in b.allocations))
    _teardown()


def test_earlier_artifacts_preserved():
    OUT = os.path.join(_ROOT, "results", "farmsync")
    for fn in ["b3_final.json", "b3_ilp_v2.json", "proposed/p1_participation_result.json",
               "proposed/p2_commitment_result.json", "proposed/p3_reopt_result.json"]:
        assert os.path.exists(os.path.join(OUT, fn))
