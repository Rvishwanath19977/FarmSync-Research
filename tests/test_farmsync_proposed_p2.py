"""Proposed Phase 2 (commitment lifecycle + locking) tests. Mostly pure state-machine,
plus an allocation-invariance check against Phase-1 realised."""
import os, pytest
from farmsync.proposed import commitment as cm
from farmsync.schemas import ParticipationState as PS, COMMITMENT_LADDER
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def _rec(accepted=True):
    return cm.CommitmentRecord("t", 1, "hash", "F1", "P1", "rice", PS.VIEWED, accepted)


def test_valid_forward_transition():
    r = _rec()
    cm.transition(r, PS.TENTATIVE_ACCEPT, "ACCEPT", 1)
    assert r.state == PS.TENTATIVE_ACCEPT
    assert cm.valid_transition(PS.TENTATIVE_ACCEPT, PS.CONFIRMED)


def test_invalid_backward_and_skip_transitions_rejected():
    r = _rec(); cm.transition(r, PS.TENTATIVE_ACCEPT, "ACCEPT", 1)
    with pytest.raises(cm.InvalidTransition):        # backward
        cm.transition(r, PS.VIEWED, "COMMIT_ADVANCE", 2)
    r2 = _rec()
    with pytest.raises(cm.InvalidTransition):        # skip VIEWED -> CONFIRMED
        cm.transition(r2, PS.CONFIRMED, "COMMIT_ADVANCE", 1)


def test_rejected_offer_is_terminal_and_cannot_progress():
    r = _rec(accepted=False)
    with pytest.raises(cm.InvalidTransition):
        cm.transition(r, PS.TENTATIVE_ACCEPT, "COMMIT_ADVANCE", 1)


def test_only_accepted_enter_progression():
    offers = [{"farmer_id": "F1", "plot_id": "P1", "planned_crop": "rice", "status": "REALISED"},
              {"farmer_id": "F2", "plot_id": "P2", "planned_crop": "wheat", "status": "REJECTED_FALLOW"}]
    recs = cm.make_records(offers, "t", 1, "h")
    cm.progress_scripted(recs)
    assert recs[("F1", "P1")].state == PS.PLANTED
    assert recs[("F2", "P2")].state == PS.VIEWED and not recs[("F2", "P2")].accepted


def test_planted_is_hard_locked_and_mutation_blocked():
    r = _rec()
    for tgt in COMMITMENT_LADDER[1:]:
        cm.transition(r, tgt, "COMMIT_ADVANCE", 1)
    assert r.state == PS.PLANTED and cm.lock_level(PS.PLANTED) == cm.LOCK_HARD
    assert cm.can_change_crop(PS.PLANTED) is False
    with pytest.raises(cm.HardLockViolation):
        cm.attempt_crop_change(r, "wheat")


def test_soft_lock_states_are_changeable():
    for s in [PS.TENTATIVE_ACCEPT, PS.CONFIRMED, PS.INPUTS_PURCHASED, PS.LAND_PREPARED]:
        assert cm.lock_level(s) == cm.LOCK_SOFT and cm.can_change_crop(s) is True
    assert cm.lock_level(PS.VIEWED) == cm.LOCK_FLEXIBLE


def test_progression_is_deterministic():
    offers = [{"farmer_id": f"F{i}", "plot_id": f"P{i}", "planned_crop": "rice", "status": "REALISED"}
              for i in range(20)]
    r1 = cm.make_records(offers, "t", 1, "h"); s1 = cm.progress_scripted(r1)
    r2 = cm.make_records(offers, "t", 1, "h"); s2 = cm.progress_scripted(r2)
    assert s1 == s2 and cm.state_counts(r1) == cm.state_counts(r2)


def test_phase2_does_not_change_allocation_cash_area_or_fairness():
    RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
    if not os.path.exists(os.path.join(RAW, "des_apy")):
        pytest.skip("raw sources not present")
    from farmsync.ingest.run_ingest import run
    from farmsync.ingest import operational as opdata
    from farmsync.generate import generate_dataset, CROPS
    from farmsync.ilp_reference import run_b1_ilp, run_b3_ilp
    from farmsync import fairness as fair, experiment as exp
    from farmsync.proposed.participation import AcceptanceConfig, apply_participation
    run(RAW, os.path.join(RAW, "..", "processed")); opdata.load(os.path.join(RAW, "..", "processed"))
    f, plots, *_ = generate_dataset(master_seed=9, n_farmers=120)
    planned = run_b3_ilp(f, plots, CROPS)
    realised, offers = apply_participation(planned, f, exp.substream(9, "farmer_response"), AcceptanceConfig())
    before_cash = sum(a.cash_net for a in realised.allocations)
    before_rep = fair.fairness_report(realised, f, b1_reference=fair.farmer_cash(run_b1_ilp(f, plots, CROPS)))
    recs = cm.make_records(offers, "t", 9, "h"); cm.progress_scripted(recs)   # phase 2
    after_cash = sum(a.cash_net for a in realised.allocations)                 # allocations untouched
    after_rep = fair.fairness_report(realised, f, b1_reference=fair.farmer_cash(run_b1_ilp(f, plots, CROPS)))
    assert before_cash == after_cash and before_rep == after_rep
    opdata._DATA["loaded"] = False


def test_frozen_and_phase1_artifacts_present():
    OUT = os.path.join(_ROOT, "results", "farmsync")
    for fn in ["b3_final.json", "b3_ilp_v2.json", "proposed/p1_participation_result.json"]:
        assert os.path.exists(os.path.join(OUT, fn))
