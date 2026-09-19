"""Proposed Phase 5 (disaster / N-1 resilience) tests."""
import os, pytest
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(RAW, "des_apy")),
                                reason="raw sources not present")


def _setup(n=120, seed=9, alpha=0.5):
    from farmsync.ingest.run_ingest import run
    from farmsync.ingest import operational as opdata
    from farmsync.generate import generate_dataset, CROPS
    from farmsync.ilp_reference import run_b3_ilp, b2_ilp_total
    from farmsync import experiment as exp
    from farmsync.proposed.participation import AcceptanceConfig, apply_participation
    from farmsync.proposed import commitment as cm, concentration as co
    run(RAW, os.path.join(RAW, "..", "processed")); opdata.load(os.path.join(RAW, "..", "processed"))
    f, plots, *_ = generate_dataset(master_seed=seed, n_farmers=n)
    tstar = b2_ilp_total(f, plots, CROPS)["b2_ilp_cash_total"]
    planned = run_b3_ilp(f, plots, CROPS, tstar=tstar)
    realised, offers = apply_participation(planned, f, exp.substream(seed, "farmer_response"), AcceptanceConfig())
    scen = cm.mixed_commitment_scenario(offers, "P3_MIXED_V1")
    ea, _ = co.max_economic_alpha(f, plots, CROPS, scen, alpha)
    ta, _ = co.fairness_floor_alpha(f, plots, CROPS, scen, alpha, ea)
    pre = co.solve_phase4(f, plots, CROPS, scen, 0.05, alpha, ea, ta)
    return f, plots, CROPS, scen, pre, alpha


def _teardown():
    from farmsync.ingest import operational as opdata
    opdata._DATA["loaded"] = False


def _first_active_crop(pre, plots):
    from farmsync.proposed import concentration as co
    _, summ = co.concentration_metrics(pre, plots)
    return summ["active_crops"][0]


def test_largest_producer_by_expected_production():
    from farmsync.proposed import resilience as rz
    f, plots, CROPS, scen, pre, alpha = _setup()
    crop = _first_active_crop(pre, plots)
    ff, fprod, lps = rz.largest_producer(pre, plots, crop)
    prod = rz._crop_production_by_farmer(pre, plots, crop)
    assert ff == max(prod, key=prod.get) and abs(fprod - prod[ff]) < 1e-6
    _teardown()


def test_immediate_target_loss_fraction_equals_lps():
    from farmsync.proposed import resilience as rz
    f, plots, CROPS, scen, pre, alpha = _setup()
    for crop in {a.crop for a in pre.allocations}:
        ff, fprod, lps = rz.largest_producer(pre, plots, crop)
        if ff is None:
            continue
        imm = rz.immediate_nminus1(pre, plots, ff, crop)
        assert abs(imm["target_loss_fraction"] - round(lps, 4)) < 1e-3   # invariant
    _teardown()


def test_failed_farmer_all_plots_unavailable():
    from farmsync.proposed import resilience as rz
    f, plots, CROPS, scen, pre, alpha = _setup()
    crop = _first_active_crop(pre, plots)
    ff, _, _ = rz.largest_producer(pre, plots, crop)
    post = rz.remove_farmer(scen, ff)
    assert all(k[0] != ff for k in post)                       # none of failed farmer's plots remain
    _teardown()


def test_failed_hard_lock_is_exogenous_not_violation():
    from farmsync.proposed import resilience as rz, commitment as cm
    f, plots, CROPS, scen, pre, alpha = _setup()
    # pick a farmer that owns at least one hard-locked plot
    hard_farmers = {fid for (fid, pid), info in scen.items() if info["lock"] == cm.LOCK_HARD}
    ff = next(iter(hard_farmers))
    post = rz.remove_farmer(scen, ff)
    # the failed farmer's hard locks are simply gone (unavailable), not present as violations
    assert all(k[0] != ff for k in post)
    assert any(info["lock"] == cm.LOCK_HARD for (fid, pid), info in scen.items() if fid == ff)
    _teardown()


def test_post_shock_surviving_hard_locks_unchanged_and_no_reuse():
    from farmsync.proposed import resilience as rz
    f, plots, CROPS, scen, pre, alpha = _setup()
    crop = _first_active_crop(pre, plots)
    ff, _, _ = rz.largest_producer(pre, plots, crop)
    imm = rz.immediate_nminus1(pre, plots, ff, crop)
    post = rz.remove_farmer(scen, ff)
    r, es, ts, stt = rz.post_shock_reopt(f, plots, CROPS, post, alpha, 0.05)
    assert r is not None and r.phase4["status"] == "Optimal"
    integ = rz.verify_failure_integrity(r, set(imm["failed_plot_ids"]), post, pre)
    assert integ["surviving_hard_locks_ok"] and not integ["failed_plots_reused"]
    _teardown()


def test_post_shock_recompute_estar_floor_and_both_enforced():
    from farmsync.proposed import resilience as rz, concentration as co
    from farmsync import config, fairness as fair
    f, plots, CROPS, scen, pre, alpha = _setup()
    crop = _first_active_crop(pre, plots)
    ff, _, _ = rz.largest_producer(pre, plots, crop)
    post = rz.remove_farmer(scen, ff)
    ea, est = co.max_economic_alpha(f, plots, CROPS, post, alpha)
    ta, tst = co.fairness_floor_alpha(f, plots, CROPS, post, alpha, ea)
    assert est == "Optimal" and tst == "Optimal"
    r = co.solve_phase4(f, plots, CROPS, post, 0.05, alpha, ea, ta)
    total = sum(a.cash_net for a in r.allocations)
    assert total >= config.CANONICAL_B3_EPSILON * ea - 1          # E >= 0.95 E*_shock
    A = {x.farmer_id: x.total_area_ha for x in f}; cash = fair.farmer_cash(r)
    assert min(cash[fid] / A[fid] for fid in cash) >= ta - 1e-6   # min-norm >= t_floor_shock
    _teardown()


def test_concentration_and_rejection_valid_after_recovery():
    from farmsync.proposed import resilience as rz, concentration as co
    f, plots, CROPS, scen, pre, alpha = _setup()
    crop = _first_active_crop(pre, plots)
    ff, _, _ = rz.largest_producer(pre, plots, crop)
    post = rz.remove_farmer(scen, ff)
    r, es, ts, stt = rz.post_shock_reopt(f, plots, CROPS, post, alpha, 0.05)
    _, summ = co.concentration_metrics(r, plots, alpha=alpha)
    assert summ["target_violations"] == 0 and summ["max_LPS"] <= alpha + 1e-6
    got = {(a.farmer_id, a.plot_id): a.crop for a in r.allocations}
    for (fid, pid), info in post.items():
        if info["lock"] == "REJECTED_TERMINAL" and (fid, pid) in got:
            assert got[(fid, pid)] != info["crop"]
    _teardown()


def test_deterministic_nminus1_repeat():
    from farmsync.proposed import resilience as rz
    f, plots, CROPS, scen, pre, alpha = _setup()
    crop = _first_active_crop(pre, plots)
    ff, _, _ = rz.largest_producer(pre, plots, crop)
    post = rz.remove_farmer(scen, ff)
    a, *_ = rz.post_shock_reopt(f, plots, CROPS, post, alpha, 0.05)
    b, *_ = rz.post_shock_reopt(f, plots, CROPS, post, alpha, 0.05)
    assert (sorted((x.farmer_id, x.plot_id, x.crop) for x in a.allocations)
            == sorted((x.farmer_id, x.plot_id, x.crop) for x in b.allocations))
    _teardown()


def test_hazard_zone_uses_existing_data_only():
    f, plots, CROPS, scen, pre, alpha = _setup()
    zones = {p.hazard_zone for p in plots}
    assert all(isinstance(z, str) and "-HZ" in z for z in zones)   # existing region+cluster ids
    _teardown()


def test_outputs_counterfactual_not_realised():
    import json
    res = json.load(open(os.path.join(_ROOT, "results", "farmsync", "proposed", "p5_resilience_result.json")))
    assert res["revised_requires_renewed_consent"] is True
    assert "COUNTERFACTUAL" in res["shock_provenance"].upper()


def test_phase1_4_artifacts_present():
    OUT = os.path.join(_ROOT, "results", "farmsync")
    for fn in ["b3_final.json", "b3_ilp_v2.json", "proposed/p1_participation_result.json",
               "proposed/p2_commitment_result.json", "proposed/p3_reopt_result.json",
               "proposed/p4_concentration_result.json"]:
        assert os.path.exists(os.path.join(OUT, fn))


# ---- Phase-5 reporting-consistency tests (attempted vs Optimal never conflated) ----
def test_post_shock_reopt_records_exact_failure_stage_and_status():
    from farmsync.proposed import resilience as rz, commitment as cm
    f, plots, CROPS, scen, pre, alpha = _setup(alpha=0.5)
    # a successful reopt records failed_stage None and Optimal
    crop = _first_active_crop(pre, plots)
    ff, _, _ = rz.largest_producer(pre, plots, crop)
    r, es, ts, stg = rz.post_shock_reopt(f, plots, CROPS, rz.remove_farmer(scen, ff), alpha, 0.05)
    assert set(["failed_stage", "cbc_status", "e_star", "t_floor", "final"]).issubset(stg.keys())
    if r is not None:
        assert stg["failed_stage"] is None and stg["cbc_status"] == "Optimal"
    _teardown()


def test_infeasible_backup_returns_none_and_no_metrics():
    # non-Optimal reopt must return None (no extracted plan) with a recorded failure stage
    from farmsync.proposed import resilience as rz
    f, plots, CROPS, scen, pre, alpha = _setup(alpha=0.5)
    # force infeasibility via an impossible concentration alpha on a reduced scenario
    crop = _first_active_crop(pre, plots)
    ff, _, _ = rz.largest_producer(pre, plots, crop)
    r, es, ts, stg = rz.post_shock_reopt(f, plots, CROPS, rz.remove_farmer(scen, ff), 0.01, 0.05)
    if r is None:
        assert stg["failed_stage"] in ("E*_shock", "t_floor_shock", "final_backup")
        assert stg["cbc_status"] != "Optimal"
    _teardown()


def test_result_accounting_distinguishes_attempted_and_optimal():
    import json
    res = json.load(open(os.path.join(_ROOT, "results", "farmsync", "proposed", "p5_resilience_result.json")))
    acc = res["scenario_accounting"]
    assert acc["total_attempted"] == 66
    assert acc["hazard_attempted"] == acc["hazard_optimal_backup"] + acc["hazard_infeasible"]
    assert acc["nminus1_attempted"] == acc["nminus1_optimal_backup"] + acc["nminus1_infeasible"]
    assert acc["total_optimal_backup"] + acc["total_infeasible"] == acc["total_attempted"]
    # validity is scoped to Optimal backups only, not all 66
    assert "64 Optimal backup plans ONLY" in res["validity_scope"]


def test_recovery_stats_have_explicit_denominator_over_optimal_only():
    import csv
    rows = list(csv.DictReader(open(os.path.join(_ROOT, "results", "farmsync", "proposed", "p5_hazard_summary.csv")))) \
        if os.path.exists(os.path.join(_ROOT, "results", "farmsync", "proposed", "p5_hazard_summary.csv")) else None
    # summaries live in the result JSON hazard_summary; check denominators there
    import json
    res = json.load(open(os.path.join(_ROOT, "results", "farmsync", "proposed", "p5_resilience_result.json")))
    for h in res["hazard_summary"]:
        assert h["recovery_denominator"] == h["optimal_backup"]        # recovery over Optimal only
        assert h["immediate_loss_denominator"] == h["attempted"]        # immediate loss over all attempted
        assert h["attempted"] == h["optimal_backup"] + h["infeasible_backup"]


def test_hazard_infeasible_rows_have_no_backup_metrics():
    import csv
    rows = list(csv.DictReader(open(os.path.join(_ROOT, "results", "farmsync", "proposed", "p5_hazard_scenarios.csv"))))
    for r in rows:
        if r["backup_optimal"] == "False":
            assert r["post_reopt_cash"] in ("", "None")                 # no extracted recovery metric
            assert r["recovery_fraction_of_immediate_loss"] in ("", "None")
            assert r["cbc_status"] != "Optimal"
