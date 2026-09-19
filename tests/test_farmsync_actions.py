"""Tests for the CAUSAL farmer-action + renewed-consent layer (ACTION_CONSENT_PROTOCOL v1).

These assert the actions causally drive reoptimisation (not overlaid afterwards), consent is
record-derived, the ledger separates recommendation from consent, withdrawn farmers are never
re-prompted, and the fairness B1 reference is B1 (not B3)."""
import os, inspect, copy
import pytest

from farmsync.proposed import actions as A
from farmsync import config as C

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(RAW, "des_apy")),
                                reason="raw sources not present")


def _load():
    from farmsync.ingest.run_ingest import run
    from farmsync.ingest import operational as opdata
    run(RAW, os.path.join(RAW, "..", "processed")); opdata.load(os.path.join(RAW, "..", "processed"))


@pytest.fixture(scope="module", autouse=True)
def _restore_global_state():
    yield
    from farmsync.ingest import operational as opdata
    import farmsync.planning as planning
    opdata._DATA["loaded"] = False
    planning._INGESTED = {"prices": {}, "costs": {}, "active": False}


# ---- policy / provenance / draws (unit) -------------------------------------------------------
def test_probabilities_are_synthetic_experimental():
    assert C.ACTION_PROVENANCE == "SYNTHETIC_EXPERIMENTAL"
    assert C.INITIAL_NONACCEPT_SPLIT == {"REJECT": 0.45, "MODIFY": 0.35, "NO_RESPONSE": 0.20}
    assert C.RENEWED_NONACCEPT_SPLIT == {"REJECT": 0.70, "NO_RESPONSE": 0.30}
    assert C.P_WITHDRAW == 0.02


def test_p_accept_model_and_profiles():
    assert A.p_accept(0.5, "PRIMARY") == pytest.approx(0.85)
    assert A.p_accept(0.0, "PRIMARY") == pytest.approx(0.75)
    assert A.p_accept(1.0, "PRIMARY") == pytest.approx(0.95)
    assert A.p_accept(0.5, "S1") == pytest.approx(0.70)
    assert A.p_accept(0.5, "S2") == pytest.approx(0.95)


def test_withdraw_key_has_no_plot_id():
    src = inspect.getsource(A.withdraw_draw)
    assert "plot_id" not in src
    assert A.withdraw_draw(12345, "F0001", "20260812") == A.withdraw_draw(12345, "F0001", "20260812")


def test_keyed_draws_order_independent():
    u1 = A._u01(999, "F0007", "F0007-P02", "20260812", "initial_accept")
    u2 = A._u01(999, "F0007", "F0007-P02", "20260812", "initial_accept")
    assert u1 == u2 and 0.0 <= u1 < 1.0


def test_matrix_hard_lock_blocks_reject_and_modify():
    assert A.matrix_cell("REJECT", A.LOCK_HARD)[2] == "REJECTED_HARD_LOCK"
    assert A.matrix_cell("MODIFY", A.LOCK_HARD)[2] == "MODIFY_HARD_LOCK"
    assert A.matrix_cell("NO_RESPONSE", A.LOCK_FLEXIBLE)[1] == A.OfferStatus.PENDING_LAPSED


def test_consent_matches_rejects_mismatch():
    from types import SimpleNamespace
    a = SimpleNamespace(farmer_id="F1", plot_id="P1", crop="wheat")
    good = A.Consent("F1", "P1", "wheat", "INITIAL", "INITIAL", "c", True)
    bad_crop = A.Consent("F1", "P1", "rice", "INITIAL", "INITIAL", "c", True)
    invalid = A.Consent("F1", "P1", "wheat", "INITIAL", "INITIAL", "c", False)
    assert A.consent_matches(a, good) is True
    assert A.consent_matches(a, bad_crop) is False       # exact-crop required
    assert A.consent_matches(a, invalid) is False        # valid required
    assert A.consent_matches(a, None) is False


def test_modify_target_canonical_and_deterministic():
    _load()
    from farmsync import experiment as exp
    from farmsync.generate import CROPS
    from farmsync.ilp_reference import _eligible
    from farmsync.feasibility import FeasibilityConfig
    inst = exp.build_instance(20260812, tightness="base")
    farmers = {f.farmer_id: f for f in inst["farmers"]}
    p = inst["plots"][0]; f = farmers[p.farmer_id]
    t1, _ = A.modify_target(p, f, CROPS, "onion")
    t2, _ = A.modify_target(p, f, CROPS, "onion")
    assert t1 == t2
    if t1 is not None:
        assert t1 != "onion"
        elig = {n for (n, *_r) in _eligible([p], {f.farmer_id: f}, {c.crop_name: c for c in CROPS}, FeasibilityConfig()).get(p.plot_id, [])}
        assert t1 in elig                                # canonical region-season eligibility


# ---- causal layer (module fixture) ------------------------------------------------------------
@pytest.fixture(scope="module")
def layer():
    _load()
    return A.run_action_consent_layer(seed=20260812, profile="PRIMARY")


def test_reopt_ran_and_optimal(layer):
    assert layer["reopt_status"] == "Optimal" and layer["conc_status"] == "Optimal"


def test_four_tiers_present_and_planned_is_frozen_b3(layer):
    for t in ("PLANNED", "INITIAL_REALIZED", "RECOMMENDED_REVISED", "FINAL_REALIZED"):
        assert t in layer["tiers"]
    assert layer["tiers"]["PLANNED"]["cash"] == 13142166.0     # frozen B3 planned input unchanged


def test_recommended_revised_is_action_dependent(layer):
    # Causal proof: the action-driven revised plan differs from the frozen (action-free) pipeline
    # concentration plan (12,285,254). If actions were overlaid AFTER reopt, these would be equal.
    assert layer["tiers"]["RECOMMENDED_REVISED"]["cash"] != 12285254.0


def test_withdrawn_never_in_renewed_prompts(layer):
    assert layer["withdrawn_in_renewed_prompts"] == []        # invariant: disjoint sets


def test_withdrawn_flexible_plot_absent_from_revised(layer):
    # withdrawn flexible/soft plots are removed from the decision set -> not in RECOMMENDED_REVISED
    withdrawn_removed = {(r["farmer_id"], r["plot_id"]) for r in layer["ledger"]
                         if r["event_type"] == "ACTION" and r["behavioural_action"] == "WITHDRAW"
                         and r["reason_code"] == "WITHDRAW_CYCLE_PARTICIPATION"}
    revised_keys = {(r["farmer_id"], r["plot_id"]) for r in layer["ledger"]
                    if r["event_type"] == "RECOMMENDATION"}
    assert withdrawn_removed and not (withdrawn_removed & revised_keys)


def test_modify_reaches_reopt_and_is_recorded(layer):
    # a validated MODIFY request is classified against the ACTUAL revised recommendation
    assert layer["modify_valid"] >= 1
    assert (layer["modify_requested_and_recommended"] + layer["modify_requested_not_recommended"]
            == layer["modify_valid"])
    types = {r["reason_code"] for r in layer["ledger"] if r["event_type"] == "MODIFY_RESULT"}
    assert types <= {"REQUESTED_AND_RECOMMENDED", "REQUESTED_NOT_RECOMMENDED"}


def test_reject_excluded_in_reopt_scenario():
    # a permitted FLEXIBLE REJECT converts the plot to REJECTED_TERMINAL, which _phase3_options
    # consumes by excluding the rejected crop — proving REJECT reaches reoptimisation.
    from farmsync.proposed.reoptimize import _phase3_options
    from farmsync.feasibility import FeasibilityConfig
    from farmsync import experiment as exp
    from farmsync.generate import CROPS
    _load()
    inst = exp.build_instance(20260812, tightness="base")
    plots = inst["plots"]; farmers = inst["farmers"]
    p = plots[0]; scen = {(p.farmer_id, p.plot_id): {"lock": "REJECTED_TERMINAL", "crop": "onion", "accepted": False}}
    opts, _ = _phase3_options(farmers, [p], CROPS, scen, FeasibilityConfig())
    assert all(name != "onion" for (name, *_r) in opts.get(p.plot_id, []))   # rejected crop excluded


def test_consent_coverage_is_one_and_record_derived(layer):
    assert layer["consent_coverage_final"] == 1.0
    d = layer["consent_coverage_derivation"]
    assert "provenance-verified" in d and "FINAL_REALIZED" in d


def test_ledger_separates_recommendation_and_consent(layer):
    et = layer["ledger_event_types"]
    assert "RECOMMENDATION" in et and "CONSENT" in et         # distinct event types
    # renewed consent/actions appear in the ledger
    renewed = [r for r in layer["ledger"] if r["decision_round"] == "RENEWED"]
    assert len(renewed) >= layer["renewed_prompts"]


def test_renewed_accept_creates_real_consent_record(layer):
    renewed_accepts = [r for r in layer["ledger"] if r["event_type"] == "CONSENT"
                       and r["decision_round"] == "RENEWED" and r["consent_kind"] == "RENEWED"]
    assert len(renewed_accepts) == layer["renewed_counts"]["ACCEPT"]
    for r in renewed_accepts:
        assert r["consent_valid"] is True and r["crop_recommended"] is not None


def test_renewed_reject_and_no_response_create_no_consent(layer):
    for r in layer["ledger"]:
        if r["event_type"] == "ACTION" and r["decision_round"] == "RENEWED":
            # renewed ACCEPT now emits its own ACTION row (authorising the RENEWED consent); only
            # REJECT / NO_RESPONSE create no consent and are not realised.
            assert r["behavioural_action"] in ("ACCEPT", "REJECT", "NO_RESPONSE")
            if r["behavioural_action"] in ("REJECT", "NO_RESPONSE"):
                assert r["consent_kind"] is None and r["realised"] is False


def test_b1_reference_is_b1_not_b3(layer):
    assert layer["meta"]["b1_reference_source"] == "B1_ILP (run_b1_ilp)"
    assert layer["meta"]["b1_reference_total_cash"] == 14644537     # authoritative frozen B1


def test_withdrawal_only_among_participating(layer):
    assert layer["withdrawn_farmers"] <= layer["participating_farmers"]


def test_determinism_same_seed(layer):
    again = A.run_action_consent_layer(seed=20260812, profile="PRIMARY")
    assert again["action_counts"] == layer["action_counts"]
    assert again["tiers"] == layer["tiers"]
    assert again["consent_coverage_final"] == layer["consent_coverage_final"]


def test_substream_change_can_change_actions():
    cyc = "20260812"
    base = [A.initial_action(1111, f"F{n:04d}", f"F{n:04d}-P01", cyc, 0.5, False) for n in range(200)]
    other = [A.initial_action(2222, f"F{n:04d}", f"F{n:04d}-P01", cyc, 0.5, False) for n in range(200)]
    assert base != other


def test_instance_hash_unchanged(layer):
    assert layer["meta"]["instance_hash"] == "5ea24037c2d9cb6a"


# ---- commitment-after-acceptance ordering (correction turn) -----------------------------------
def test_prefix_offers_are_all_fresh_flexible():
    _load()
    from farmsync.proposed import pipeline as pl
    prep = pl.prepare_proposed_prerequisites(seed=20260812)
    # prefix returns fresh offers only — NO scen, NO pre-assigned commitment locks
    assert "scen" not in prep and "offers" in prep
    for o in prep["offers"]:
        assert set(o.keys()) == {"farmer_id", "plot_id", "crop"}   # no lock/state/accepted keys


def test_only_accepts_enter_commitment_ladder_and_hardlock_has_prior_accept():
    _load()
    from farmsync.proposed import actions as A
    r = A.run_action_consent_layer(seed=20260812)
    ledg = r["ledger"]
    accepts = {(x["farmer_id"], x["plot_id"]) for x in ledg
               if x["event_type"] == "ACTION" and x["behavioural_action"] == "ACCEPT"}
    # rebuild the committed ladder the same way the layer does, from accepted offers
    from farmsync.proposed import pipeline as pl
    prep = pl.prepare_proposed_prerequisites(seed=20260812)
    # reconstruct which offers were accepted via the ledger, then commit
    accepted_offers = [{"farmer_id": fid, "plot_id": pid,
                        "crop": next(o["crop"] for o in prep["offers"] if o["farmer_id"] == fid and o["plot_id"] == pid)}
                       for (fid, pid) in accepts]
    committed = pl.commit_accepted(accepted_offers)
    # only accepted plots are committed; every HARD_LOCK traces to an ACCEPT
    assert set(committed.keys()) <= accepts
    hard = {k for k, v in committed.items() if v["lock"] == "HARD_LOCK"}
    assert hard <= accepts                                   # every hard-lock has a prior ACCEPT
    assert all(v.get("accepted") for v in committed.values())


def test_fresh_nonaccept_actions_create_no_consent():
    _load()
    from farmsync.proposed import actions as A
    r = A.run_action_consent_layer(seed=20260812)
    for x in r["ledger"]:
        if x["event_type"] == "ACTION" and x["decision_round"] == "INITIAL" \
                and x["behavioural_action"] in ("REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW"):
            assert x["consent_kind"] is None            # no INITIAL consent for a non-ACCEPT fresh offer
            assert x["realised"] is not True


def test_no_initial_hardlock_block_events():
    _load()
    from farmsync.proposed import actions as A
    r = A.run_action_consent_layer(seed=20260812)
    blocked = [x for x in r["ledger"] if x["decision_round"] == "INITIAL"
               and x.get("reason_code") in ("REJECTED_HARD_LOCK", "MODIFY_HARD_LOCK")]
    assert blocked == []                                # fresh offers are FLEXIBLE; no hard-lock blocks


def test_consent_coverage_still_record_derived_after_reorder():
    _load()
    from farmsync.proposed import actions as A
    r = A.run_action_consent_layer(seed=20260812)
    assert r["consent_coverage_final"] == 1.0
    # every INITIAL consent event corresponds to an ACCEPT action
    inits = [x for x in r["ledger"] if x["event_type"] == "ACTION"
             and x["consent_kind"] == "INITIAL"]
    assert inits and all(x["behavioural_action"] == "ACCEPT" for x in inits)


# ---- auxiliary solver-status guard (correction turn) ------------------------------------------
import pytest as _pytest

@_pytest.mark.parametrize("helper,module,failed_stage,downstream,downstream_module", [
    ("max_economic",            "reoptimize",   "proposed.phase3_e_star",              "fairness_floor",       "reoptimize"),
    ("fairness_floor",          "reoptimize",   "proposed.phase3_fairness_floor",      "solve_phase3",         "reoptimize"),
    ("max_economic_alpha",      "concentration","proposed.phase4_e_star_alpha",        "fairness_floor_alpha", "concentration"),
    ("fairness_floor_alpha",    "concentration","proposed.phase4_fairness_floor_alpha","solve_phase4",         "concentration"),
])
def test_auxiliary_solver_status_guard(monkeypatch, helper, module, failed_stage, downstream, downstream_module):
    _load()
    from farmsync.proposed import actions as A
    import importlib
    ro = importlib.import_module("farmsync.proposed.reoptimize")
    co = importlib.import_module("farmsync.proposed.concentration")
    mod = ro if module == "reoptimize" else co
    dmod = ro if downstream_module == "reoptimize" else co

    # helper returns a non-Optimal status tuple (value, status)
    monkeypatch.setattr(mod, helper, lambda *a, **k: (None, "Infeasible"))
    # prove the immediate downstream solver is NOT called once a prerequisite is non-Optimal
    called = {"hit": False}
    orig = getattr(dmod, downstream)
    monkeypatch.setattr(dmod, downstream, lambda *a, **k: called.__setitem__("hit", True) or orig(*a, **k))

    with _pytest.raises(A.ProposedInfeasibleError) as ei:
        A.run_action_consent_layer(seed=20260812)
    assert ei.value.failed_stage == failed_stage and ei.value.status == "Infeasible"
    assert called["hit"] is False                       # downstream solve never reached


def test_uncertainty_records_auxiliary_infeasible(monkeypatch):
    # run_uncertainty_condition converts a typed auxiliary infeasibility to a structured record
    _load()
    from farmsync.proposed import uncertainty as U
    from farmsync.proposed import reoptimize as ro
    monkeypatch.setattr(ro, "max_economic", lambda *a, **k: (None, "Infeasible"))
    out = U.run_uncertainty_condition(20260812, "U0")
    p = out["proposed"]
    assert p["optimal"] is False
    assert p["failed_stage"] == "proposed.phase3_e_star" and p["status"] == "Infeasible"
    assert p["cash"] is None


# ---- consent provenance traceability (publication-freeze turn) --------------------------------
def test_initial_and_renewed_consents_link_valid_accept_events():
    _load()
    from farmsync.proposed import actions as A
    r = A.run_action_consent_layer(seed=20260812)
    ledger_by_id = {row["event_id"]: row for row in r["ledger"]}
    # collect CONSENT ledger rows and confirm each references an AUTH_EVENT that is an ACCEPT ACTION
    consent_rows = [x for x in r["ledger"] if x["event_type"] == "CONSENT"]
    assert consent_rows
    for cr in consent_rows:
        assert cr["reason_code"] and cr["reason_code"].startswith("AUTH_EVENT:")
        ev_id = int(cr["reason_code"].split(":")[1])
        ev = ledger_by_id[ev_id]
        assert ev["event_type"] == "ACTION" and ev["behavioural_action"] == "ACCEPT"
        assert ev["farmer_id"] == cr["farmer_id"] and ev["plot_id"] == cr["plot_id"]
        assert ev["decision_round"] == cr["decision_round"]   # INITIAL->INITIAL, RENEWED->RENEWED


def test_renewed_accept_has_separate_action_and_consent_rows():
    _load()
    from farmsync.proposed import actions as A
    r = A.run_action_consent_layer(seed=20260812)
    renewed_actions = [x for x in r["ledger"] if x["event_type"] == "ACTION"
                       and x["decision_round"] == "RENEWED" and x["behavioural_action"] == "ACCEPT"]
    renewed_consents = [x for x in r["ledger"] if x["event_type"] == "CONSENT"
                        and x["decision_round"] == "RENEWED"]
    assert len(renewed_actions) == r["renewed_counts"]["ACCEPT"] == len(renewed_consents)


def test_verify_provenance_predicate_rejects_all_break_cases():
    from farmsync.proposed import actions as A
    from types import SimpleNamespace
    a = SimpleNamespace(farmer_id="F1", plot_id="P1", crop="wheat")
    good_ev = {"event_id": 7, "event_type": "ACTION", "behavioural_action": "ACCEPT",
               "farmer_id": "F1", "plot_id": "P1", "decision_round": "INITIAL",
               "crop_before": "wheat", "cycle_id": "C"}
    ledger = {7: good_ev}
    good = A.Consent("F1", "P1", "wheat", "INITIAL", "INITIAL", "C", True, action_event_id=7)
    assert A.verify_consent_provenance(a, good, ledger, "C") is True
    # 5 missing action_event_id
    assert A.verify_consent_provenance(a, A.Consent("F1","P1","wheat","INITIAL","INITIAL","C",True,None), ledger, "C") is False
    # 5b action_event_id referencing missing event
    assert A.verify_consent_provenance(a, A.Consent("F1","P1","wheat","INITIAL","INITIAL","C",True,999), ledger, "C") is False
    # 6 mismatched farmer linkage (event farmer differs)
    ev6 = dict(good_ev, farmer_id="FX"); assert A.verify_consent_provenance(a, good, {7: ev6}, "C") is False
    # 7 mismatched plot linkage
    ev7 = dict(good_ev, plot_id="PX"); assert A.verify_consent_provenance(a, good, {7: ev7}, "C") is False
    # 8 mismatched crop (consent crop differs from alloc)
    assert A.verify_consent_provenance(a, A.Consent("F1","P1","rice","INITIAL","INITIAL","C",True,7), ledger, "C") is False
    # 9 mismatched decision_round
    assert A.verify_consent_provenance(a, A.Consent("F1","P1","wheat","INITIAL","RENEWED","C",True,7), ledger, "C") is False
    # non-ACCEPT referenced event
    evx = dict(good_ev, behavioural_action="REJECT"); assert A.verify_consent_provenance(a, good, {7: evx}, "C") is False
    # wrong cycle
    assert A.verify_consent_provenance(a, A.Consent("F1","P1","wheat","INITIAL","INITIAL","OTHER",True,7), ledger, "C") is False


def test_hardlock_without_prior_consent_raises_provenance_error(monkeypatch):
    # genuinely exercise the production HARD_LOCK guard: force accepted plots to HARD_LOCK and
    # invalidate ONE real prior consent, so a real hard-locked allocation reaches the guard with an
    # invalid prior INITIAL ACCEPT consent and raises ConsentProvenanceError.
    _load()
    from farmsync.proposed import actions as A
    from farmsync.proposed import pipeline as pl
    target = {}
    real_consent = A.Consent
    def _wrap(*a, **k):
        c = real_consent(*a, **k)
        if not target:                                 # first INITIAL ACCEPT consent
            c.valid = False; target["key"] = (c.farmer_id, c.plot_id)
        return c
    monkeypatch.setattr(A, "Consent", _wrap)
    orig = pl.commit_accepted
    def _one_hard(accepted_offers, scenario_id="P3_MIXED_V1"):
        scen = orig(accepted_offers, scenario_id)
        k = target.get("key")                          # force just that plot to HARD_LOCK (feasible)
        if k in scen:
            scen[k] = dict(scen[k], lock="HARD_LOCK", state="PLANTED")
        return scen
    monkeypatch.setattr(pl, "commit_accepted", _one_hard)
    with pytest.raises(A.ConsentProvenanceError):
        A.run_action_consent_layer(seed=20260812)


def test_wrong_initial_authorising_crop_fails_provenance():
    from farmsync.proposed import actions as A
    from types import SimpleNamespace
    a = SimpleNamespace(farmer_id="F1", plot_id="P1", crop="wheat")
    # INITIAL: the ACCEPT ACTION's crop_before must equal the consent crop; here it doesn't
    ev = {"event_id": 5, "event_type": "ACTION", "behavioural_action": "ACCEPT",
          "farmer_id": "F1", "plot_id": "P1", "decision_round": "INITIAL",
          "crop_before": "rice", "cycle_id": "C"}
    c = A.Consent("F1", "P1", "wheat", "INITIAL", "INITIAL", "C", True, action_event_id=5)
    assert A.verify_consent_provenance(a, c, {5: ev}, "C") is False
    ev_ok = dict(ev, crop_before="wheat")
    assert A.verify_consent_provenance(a, c, {5: ev_ok}, "C") is True


def test_wrong_renewed_authorising_crop_fails_provenance():
    from farmsync.proposed import actions as A
    from types import SimpleNamespace
    a = SimpleNamespace(farmer_id="F1", plot_id="P1", crop="wheat")
    # RENEWED: the ACCEPT ACTION's crop_recommended must equal the consent crop; here it doesn't
    ev = {"event_id": 6, "event_type": "ACTION", "behavioural_action": "ACCEPT",
          "farmer_id": "F1", "plot_id": "P1", "decision_round": "RENEWED",
          "crop_recommended": "rice", "cycle_id": "C"}
    c = A.Consent("F1", "P1", "wheat", "RENEWED", "RENEWED", "C", True, action_event_id=6)
    assert A.verify_consent_provenance(a, c, {6: ev}, "C") is False
    ev_ok = dict(ev, crop_recommended="wheat")
    assert A.verify_consent_provenance(a, c, {6: ev_ok}, "C") is True


def test_consent_ledger_rows_carry_structural_action_event_id(layer):
    # every CONSENT ledger row carries a real action_event_id pointing at the correct ACCEPT ACTION
    ledger = layer["ledger"]
    by_id = {r["event_id"]: r for r in ledger}
    consent_rows = [r for r in ledger if r["event_type"] == "CONSENT"]
    assert consent_rows
    for cr in consent_rows:
        aid = cr["action_event_id"]
        assert aid is not None and aid in by_id           # structural field, not reason_code parsing
        ev = by_id[aid]
        assert ev["event_type"] == "ACTION" and ev["behavioural_action"] == "ACCEPT"
        assert ev["farmer_id"] == cr["farmer_id"] and ev["plot_id"] == cr["plot_id"]
        assert ev["decision_round"] == cr["decision_round"]
        # the referenced ACCEPT authorises the consent crop
        crop = cr["crop_recommended"]
        if cr["decision_round"] == "INITIAL":
            assert ev["crop_before"] == crop
        else:
            assert ev["crop_recommended"] == crop


def test_provenance_error_propagates_not_infeasible(monkeypatch):
    _load()
    from farmsync.proposed import actions as A
    from farmsync.proposed import uncertainty as U
    monkeypatch.setattr(A, "verify_consent_provenance", lambda *a, **k: False)
    with pytest.raises(A.ConsentProvenanceError):
        U.run_uncertainty_condition(20260812, "U0")       # NOT converted to optimal=False


def test_modify_tiebreak_is_crop_id(monkeypatch):
    from farmsync.proposed import actions as A
    from types import SimpleNamespace
    # two eligible alternatives with EQUAL expected cash; crop_id order opposite to crop_name order
    crops = [SimpleNamespace(crop_name="zebra", crop_id="C01"),
             SimpleNamespace(crop_name="apple", crop_id="C02")]
    plot = SimpleNamespace(plot_id="P1", farmer_id="F1")
    farmer = SimpleNamespace(farmer_id="F1")
    monkeypatch.setattr(A, "_eligible",
                        lambda *a, **k: {"P1": [("zebra", 100.0, 0, 0, 0), ("apple", 100.0, 0, 0, 0)]})
    # tie broken by crop_id asc -> C01 -> "zebra" (NOT crop_name asc which would pick "apple")
    tgt, _ = A.modify_target(plot, farmer, crops, current_crop="onion")
    assert tgt == "zebra"


def test_referenced_accept_wrong_cycle_fails_provenance():
    # consent.cyc correct + ACCEPT otherwise valid, but the referenced ACTION has the WRONG cycle_id
    from farmsync.proposed import actions as A
    from types import SimpleNamespace
    a = SimpleNamespace(farmer_id="F1", plot_id="P1", crop="wheat")
    ev = {"event_id": 8, "event_type": "ACTION", "behavioural_action": "ACCEPT",
          "farmer_id": "F1", "plot_id": "P1", "decision_round": "INITIAL",
          "crop_before": "wheat", "cycle_id": "OTHER"}          # wrong cycle
    c = A.Consent("F1", "P1", "wheat", "INITIAL", "INITIAL", "C", True, action_event_id=8)
    assert A.verify_consent_provenance(a, c, {8: ev}, "C") is False
    ev_ok = dict(ev, cycle_id="C")
    assert A.verify_consent_provenance(a, c, {8: ev_ok}, "C") is True


def test_consent_kind_decision_round_mismatch_fails_provenance():
    # consent_kind must equal decision_round; a mismatch is malformed provenance
    from farmsync.proposed import actions as A
    from types import SimpleNamespace
    a = SimpleNamespace(farmer_id="F1", plot_id="P1", crop="wheat")
    ev = {"event_id": 9, "event_type": "ACTION", "behavioural_action": "ACCEPT",
          "farmer_id": "F1", "plot_id": "P1", "decision_round": "RENEWED",
          "crop_recommended": "wheat", "cycle_id": "C"}
    # consent_kind=INITIAL but decision_round=RENEWED -> inconsistent -> False
    c = A.Consent("F1", "P1", "wheat", "INITIAL", "RENEWED", "C", True, action_event_id=9)
    assert A.verify_consent_provenance(a, c, {9: ev}, "C") is False



# ---- Final30 publication-parameter exposure -----------------------------------
def test_publication_lambda_alpha_parameterisation_for_final30(layer):
    import inspect

    from farmsync import config as C
    from farmsync.proposed import actions as A
    from farmsync.proposed import pipeline as pl

    sig = inspect.signature(
        A.run_action_consent_layer
    )

    assert "lam" in sig.parameters
    assert "alpha" in sig.parameters

    # Compatibility constants remain numerically identical,
    # but the publication config is now the action-layer default.
    assert pl.DEV_LAMBDA == C.PUBLICATION_LAMBDA == 0.05
    assert pl.DEV_ALPHA == C.PUBLICATION_ALPHA == 0.40

    assert layer["meta"]["lambda"] == C.PUBLICATION_LAMBDA
    assert layer["meta"]["alpha"] == C.PUBLICATION_ALPHA

    src = inspect.getsource(
        A.run_action_consent_layer
    )

    assert "pl.DEV_LAMBDA" not in src
    assert "pl.DEV_ALPHA" not in src

    # Existing current Phase-3/4 machinery receives the exposed values.
    assert (
        "ro.solve_phase3(farmers, plots2, crops, scen2, lam, es, tfl)"
        in src
    )

    assert (
        "co.solve_phase4(farmers, plots2, crops, scen2, lam, alpha, ea, ta)"
        in src
    )



def test_final30_observability_metrics_are_exposed(layer):
    """Final30 needs existing P3/P4 measurements without reconstructing them."""
    st = layer["recommended_revised_stability"]
    p4 = layer["recommended_revised_phase4"]
    rc = layer["recommended_revised_concentration"]
    fc = layer["final_realized_concentration"]

    assert st["status"] == "Optimal"
    assert st["lambda"] == 0.05
    assert "changed_soft_area" in st
    assert "soft_lock_area" in st

    assert p4["status"] == "Optimal"
    assert p4["alpha"] == 0.40

    assert "max_LPS" in rc
    assert "mean_HHI" in rc
    assert "median_HHI" in rc
    assert "target_violations" in rc
    assert rc["target_violations"] == 0

    assert "max_LPS" in fc
    assert "mean_HHI" in fc
    assert "median_HHI" in fc

    assert layer["concentration_constraint_scope"] == "RECOMMENDED_REVISED only"
