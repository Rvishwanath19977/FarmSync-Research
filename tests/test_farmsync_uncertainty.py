"""Tests for uncertainty-v1 (UNCERTAINTY_PROTOCOL v1-FROZEN).

These assert uncertainty CAUSALLY reaches the actual optimiser inputs (not metadata), that state does
not leak (UJ->U0), that U0 reproduces frozen baselines, and that channel semantics match the freeze."""
import os
import pytest

from farmsync.proposed import uncertainty as U
from farmsync import config as C, climate
from farmsync.ingest import operational as opdata

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(RAW, "des_apy")),
                                reason="raw sources not present")


def _load():
    from farmsync.ingest.run_ingest import run
    run(RAW, os.path.join(RAW, "..", "processed")); opdata.load(os.path.join(RAW, "..", "processed"))


@pytest.fixture(scope="module", autouse=True)
def _restore_global_state():
    yield
    opdata._DATA["loaded"] = False
    opdata.clear_market_mult(); climate.clear_et0_mult()
    import farmsync.planning as planning
    planning._INGESTED = {"prices": {}, "costs": {}, "active": False}


# ---- unit: frozen values ----------------------------------------------------------------------
def test_frozen_uncertainty_values():
    assert C.WEATHER_ET0_STATES == {"LOW_EVAPORATIVE_DEMAND": (0.90, 0.20), "NORMAL": (1.00, 0.60),
                                    "HIGH_EVAPORATIVE_DEMAND": (1.15, 0.20)}
    assert C.MARKET_PRICE_STATES["HIGH"] == (1.10, 0.25)
    assert C.MARKET_ABSORPTION_STATES["LOW"] == (0.85, 0.20)
    assert C.RESOURCE_STATES == {"NORMAL": (1.00, 0.70), "CONSTRAINED": (0.85, 0.30)}
    assert C.PARTICIPATION_PRIMARY_RATE == 0.90
    assert C.UNCERTAINTY_CONDITIONS == ["U0", "UW", "UM", "UR", "UP", "UJ"]
    assert C.UNCERTAINTY_PROVENANCE == "SYNTHETIC_EXPERIMENTAL"


# ---- causal path: weather ET0 -> feasibility --------------------------------------------------
def test_weather_mult_reaches_et0_accessor():
    base = climate._et0_for("R1", "kharif")
    climate.set_et0_mult({("R1", "kharif"): 1.15})
    try:
        assert climate._et0_for("R1", "kharif") == pytest.approx(base * 1.15)
    finally:
        climate.clear_et0_mult()
    assert climate._et0_for("R1", "kharif") == base          # cleared


# ---- causal path: price shock -> projected_return; NOT MSP-floored ----------------------------
def test_price_shock_reaches_projected_return_no_msp_floor():
    _load()
    from farmsync.planning import projected_return, operational_price
    # pick a crop/region with an operational price
    region, crop = "R1", "wheat"
    base_price, basis = operational_price(crop, region, "rabi")
    if base_price is None:
        pytest.skip("no operational price for probe crop")
    opdata.set_market_mult({(region, crop): 0.50}, {})       # aggressive downward shock
    try:
        shocked, _b = operational_price(crop, region, "rabi")
        assert shocked == pytest.approx(base_price * 0.50)    # exactly scaled -> NO MSP floor clip
    finally:
        opdata.clear_market_mult()


# ---- causal path: absorption is crop-GLOBAL (no region in key) --------------------------------
def test_absorption_shock_is_crop_global():
    _load()
    crop = "wheat"
    base = opdata.op_absorption(crop)
    if base is None:
        pytest.skip("no absorption for probe crop")
    opdata.set_market_mult({}, {crop: 0.85})
    try:
        assert opdata.op_absorption(crop) == pytest.approx(base * 0.85)
    finally:
        opdata.clear_market_mult()


def test_realisation_absorption_keyed_by_crop_only():
    _load()
    from farmsync import experiment as exp
    inst = exp.build_instance(20260812, tightness="base")
    r = U.draw_realisation(20260812, "UM", inst["farmers"], inst["plots"])
    # absorption_state keys must be crop names (strings), never (region, crop) tuples
    assert all(isinstance(k, str) for k in r.absorption_state)
    # price keys ARE (region, crop) tuples
    assert all(isinstance(k, tuple) and len(k) == 2 for k in r.price_mult)


# ---- causal path: resource same multiplier on budget AND labour; original data intact ----------
def test_resource_same_mult_budget_and_labour_and_original_intact():
    _load()
    from farmsync import experiment as exp
    inst = exp.build_instance(20260812, tightness="base")
    f0 = inst["farmers"][0]
    orig_budget, orig_labour = f0.cultivation_budget, f0.labour_capacity
    r = U.draw_realisation(20260812, "UR", inst["farmers"], inst["plots"])
    pert = U.perturb_instance(inst, r)
    lbl, m = r.resource_state[f0.farmer_id]
    pf0 = next(f for f in pert["farmers"] if f.farmer_id == f0.farmer_id)
    assert pf0.cultivation_budget == pytest.approx(orig_budget * m)
    assert pf0.labour_capacity == pytest.approx(orig_labour * m)
    # original instance object is NOT mutated (deep copy)
    assert inst["farmers"][0].cultivation_budget == orig_budget
    assert inst["farmers"][0].labour_capacity == orig_labour


# ---- causal path: participation removes farmer + all their plots BEFORE planning ---------------
def test_participation_removes_farmer_and_plots():
    _load()
    from farmsync import experiment as exp
    inst = exp.build_instance(20260812, tightness="base")
    r = U.draw_realisation(20260812, "UP", inst["farmers"], inst["plots"])
    dropped = {fid for fid, keep in r.participation.items() if not keep}
    assert dropped                                            # some farmers dropped at rate 0.90
    pert = U.perturb_instance(inst, r)
    kept_ids = {f.farmer_id for f in pert["farmers"]}
    assert not (dropped & kept_ids)                          # dropped farmers absent
    assert all(p.farmer_id not in dropped for p in pert["plots"])   # their plots absent


# ---- realisation hash: stable, order-independent, shared across methods ------------------------
def test_realisation_hash_stable_and_deterministic():
    _load()
    from farmsync import experiment as exp
    inst = exp.build_instance(20260812, tightness="base")
    r1 = U.draw_realisation(20260812, "UJ", inst["farmers"], inst["plots"])
    r2 = U.draw_realisation(20260812, "UJ", inst["farmers"], inst["plots"])
    assert r1.realisation_hash == r2.realisation_hash
    # order-independent: shuffling farmers/plots does not change the hash
    import random
    fs = list(inst["farmers"]); ps = list(inst["plots"])
    random.Random(1).shuffle(fs); random.Random(2).shuffle(ps)
    r3 = U.draw_realisation(20260812, "UJ", fs, ps)
    assert r3.realisation_hash == r1.realisation_hash


# ---- integration: U0 parity, UJ causal, state isolation (module-scoped, heavier) ---------------
@pytest.fixture(scope="module")
def u0_uj():
    _load()
    u0 = U.run_uncertainty_condition(20260812, "U0")
    uj = U.run_uncertainty_condition(20260812, "UJ")
    u0_after = U.run_uncertainty_condition(20260812, "U0")   # isolation probe
    return u0, uj, u0_after


def test_u0_parity_frozen_baselines(u0_uj):
    u0, _uj, _a = u0_uj
    assert u0["baselines"]["B1"]["cash"] == 14644537.0
    assert u0["baselines"]["B2"]["cash"] == 13822731.0
    assert u0["baselines"]["B3"]["cash"] == 13142166.0
    assert u0["participating_farmers"] == 500                # U0 removes no one
    assert u0["proposed"]["consent_coverage_final"] == 1.0


def test_uj_is_causal(u0_uj):
    u0, uj, _a = u0_uj
    # uncertainty reaches the actual optimiser: baselines differ from U0
    assert uj["baselines"]["B1"]["cash"] != u0["baselines"]["B1"]["cash"]
    assert uj["participating_farmers"] < 500                 # participation removed farmers pre-planning
    assert uj["meta"]["realisation_hash"] != u0["meta"]["realisation_hash"]
    assert uj["proposed"]["reopt_status"] == "Optimal" and uj["proposed"]["conc_status"] == "Optimal"
    assert uj["proposed"]["consent_coverage_final"] == 1.0


def test_same_realisation_reused_across_methods(u0_uj):
    _u0, uj, _a = u0_uj
    assert uj["proposed"]["realisation_hash_match"] is True   # Proposed used the baselines' realisation


def test_state_isolation_uj_then_u0(u0_uj):
    u0, _uj, u0_after = u0_uj
    assert {k: v["cash"] for k, v in u0_after["baselines"].items()} == \
           {k: v["cash"] for k, v in u0["baselines"].items()}
    assert opdata._PRICE_MULT == {} and opdata._ABS_MULT == {} and climate._ET0_MULT == {}


def test_farmer_response_substream_unchanged(u0_uj):
    # uncertainty must not touch the frozen farmer_response substream
    from farmsync import experiment as exp
    assert exp.substream(20260812, "farmer_response") == 1120031581


# ---- STRENGTHENED causal tests (correction turn) ----------------------------------------------
def test_non_optimal_baseline_not_reported_optimal():
    # baseline_record must never label a non-Optimal solve Optimal, never expose cash/area
    class _Fake:
        solver = {"status": "Infeasible"}
        allocations = []
    rec = U.baseline_record("B1", _Fake())
    assert rec["optimal"] is False and rec["status"] == "Infeasible"
    assert rec["cash"] is None and rec["area"] is None and rec["failed_stage"] == "B1.solve"
    # and an Optimal one exposes cash
    class _Ok:
        solver = {"status": "Optimal"}
        class _A:
            farmer_id = "F"; plot_id = "P"; crop = "x"; cash_net = 100.0; area_ha = 1.0
        allocations = [_A()]
    ok = U.baseline_record("B1", _Ok())
    assert ok["optimal"] is True and ok["cash"] == 100.0


def test_weather_mult_reaches_nir_water_path():
    # prove the ET0 multiplier reaches the ACTUAL net-irrigation-requirement pathway used by
    # feasibility (net_irrigation_requirement_mm -> compute_crop_water_requirements -> _et0_for).
    _load()
    from farmsync import climate
    # find a (crop, region, season) with a defined NIR at baseline
    probe = None
    for region in ("R1", "R2", "R4"):
        cwr = climate.compute_crop_water_requirements(region, "kharif")
        if cwr.get("_status") == "OK":
            for crop in cwr:
                if not crop.startswith("_"):
                    nir = climate.net_irrigation_requirement_mm(crop, region, "kharif")
                    if nir is not None and nir > 0:
                        probe = (crop, region, "kharif"); break
        if probe:
            break
    if probe is None:
        pytest.skip("no positive-NIR probe available")
    crop, region, season = probe
    base_nir = climate.net_irrigation_requirement_mm(crop, region, season)
    climate.set_et0_mult({(region, season): 1.15})     # HIGH_EVAPORATIVE_DEMAND
    try:
        high_nir = climate.net_irrigation_requirement_mm(crop, region, season)
    finally:
        climate.clear_et0_mult()
    assert high_nir > base_nir                          # higher ET0 -> higher CWR -> higher NIR
    assert climate.net_irrigation_requirement_mm(crop, region, season) == base_nir   # cleared


def test_absorption_shock_binds_actual_b2_cap():
    # prove the shocked crop-GLOBAL absorption cap reaches the actual B2 optimiser constraint:
    # a severely reduced cap for the most-allocated crop must reduce that crop's allocated area.
    _load()
    from farmsync import experiment as exp
    from farmsync.ilp_reference import run_b2_ilp
    from farmsync.generate import CROPS
    inst = exp.build_instance(20260812, tightness="base")
    f, plots = inst["farmers"], inst["plots"]
    base = run_b2_ilp(f, plots, CROPS)
    from collections import Counter
    area_by_crop = Counter()
    for a in base.allocations:
        area_by_crop[a.crop] += a.area_ha
    top_crop = max(area_by_crop, key=area_by_crop.get)
    opdata.set_market_mult({}, {top_crop: 0.10})       # crush the cap for the dominant crop
    try:
        shocked = run_b2_ilp(f, plots, CROPS)
    finally:
        opdata.clear_market_mult()
    shocked_area = sum(a.area_ha for a in shocked.allocations if a.crop == top_crop)
    assert shocked_area < area_by_crop[top_crop]       # reduced cap causally bound the optimiser


def test_resource_scaling_binds_solver():
    # prove the scaled budget is consumed by the actual solver constraint: crushing budgets lowers cash
    _load()
    from farmsync import experiment as exp
    from farmsync.ilp_reference import run_b1_ilp
    from farmsync.generate import CROPS
    inst = exp.build_instance(20260812, tightness="base")
    base_cash = round(sum(a.cash_net for a in run_b1_ilp(inst["farmers"], inst["plots"], CROPS).allocations))
    # build a UR-style realisation but force CONSTRAINED for everyone to guarantee a binding effect
    r = U.draw_realisation(20260812, "UR", inst["farmers"], inst["plots"])
    for fid in r.resource_state:
        r.resource_state[fid] = ("CONSTRAINED", 0.50)  # controlled: half budget+labour
    pert = U.perturb_instance(inst, r)
    pert_cash = round(sum(a.cash_net for a in run_b1_ilp(pert["farmers"], pert["plots"], CROPS).allocations))
    assert pert_cash < base_cash                       # budget/labour constraint bound the solver


def test_nonparticipant_has_no_action_or_consent_events():
    # a non-participating farmer must produce ZERO action/consent ledger events (removed pre-planning)
    _load()
    from farmsync import experiment as exp
    from farmsync.proposed import actions as A
    inst = exp.build_instance(20260812, tightness="base")
    r = U.draw_realisation(20260812, "UP", inst["farmers"], inst["plots"])
    dropped = {fid for fid, keep in r.participation.items() if not keep}
    pert = U.perturb_instance(inst, r)
    layer = A.run_action_consent_layer(seed=20260812, instance=pert,
                                       uncertainty_condition="UP", realisation_hash=r.realisation_hash)
    ledger_farmers = {row["farmer_id"] for row in layer["ledger"]}
    assert dropped and not (dropped & ledger_farmers)  # no events for any dropped farmer


def test_phase5_resilience_not_invoked_by_uncertainty(monkeypatch):
    # general uncertainty must NOT execute Phase-5 resilience
    _load()
    import farmsync.proposed.resilience as rz
    import farmsync.proposed.pipeline as pl
    called = {"hit": False}
    if hasattr(pl, "_resilience_demo"):
        monkeypatch.setattr(pl, "_resilience_demo",
                            lambda *a, **k: called.__setitem__("hit", True))
    for fn in ("immediate_nminus1", "hazard_zone_outage"):
        if hasattr(rz, fn):
            monkeypatch.setattr(rz, fn, lambda *a, **k: called.__setitem__("hit", True))
    U.run_uncertainty_condition(20260812, "U0")
    assert called["hit"] is False                      # resilience never called in uncertainty path


def test_single_initial_action_per_offer():
    # exactly ONE frozen initial action per eligible B3 offer (no duplicate Phase-1 gate)
    _load()
    from farmsync.proposed import actions as A
    layer = A.run_action_consent_layer(seed=20260812)
    assert sum(layer["action_counts"].values()) == layer["tiers"]["PLANNED"]["n"]


def test_unexpected_exception_not_classified_infeasible(monkeypatch):
    # a programming error inside Proposed must PROPAGATE, not be converted to optimal=False
    _load()
    from farmsync.proposed import actions as A
    def _boom(*a, **k):
        raise KeyError("unexpected programming error")
    monkeypatch.setattr(A, "run_action_consent_layer", _boom)
    with pytest.raises(KeyError):
        U.run_uncertainty_condition(20260812, "U0")


def test_typed_infeasible_is_recorded_structured():
    # the typed ProposedInfeasibleError carries failed_stage/status for structured recording
    from farmsync.proposed.actions import ProposedInfeasibleError
    e = ProposedInfeasibleError("proposed.reopt_phase3", "Infeasible")
    assert e.failed_stage == "proposed.reopt_phase3" and e.status == "Infeasible"
