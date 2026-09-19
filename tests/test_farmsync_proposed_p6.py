"""Proposed Phase 6 (end-to-end integration pipeline) tests.

Performance: the canonical 500-farmer pipeline is deterministic, so it is executed exactly ONCE
per module (module-scoped fixture) and each test receives an independent deep copy of the
result/ledger. This removes ~12 redundant re-solves of the same immutable canonical pipeline
without weakening any checkpoint/invariant assertion. Determinism is still verified by an explicit
second fresh run in test_pipeline_deterministic_repeat. Canonical semantics (seed 20260812,
500 farmers, epsilon/lambda/alpha, stage order) are unchanged.
"""
import os, json, copy, pytest
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
OUTP = os.path.join(_ROOT, "results", "farmsync", "proposed")
pytestmark = pytest.mark.skipif(not os.path.exists(os.path.join(RAW, "des_apy")),
                                reason="raw sources not present")


def _load():
    from farmsync.ingest.run_ingest import run
    from farmsync.ingest import operational as opdata
    run(RAW, os.path.join(RAW, "..", "processed")); opdata.load(os.path.join(RAW, "..", "processed"))


def _teardown():
    from farmsync.ingest import operational as opdata
    opdata._DATA["loaded"] = False


@pytest.fixture(scope="module")
def _pipeline_cache():
    """Run the canonical deterministic pipeline exactly once for the whole module."""
    _load()
    from farmsync.proposed import pipeline as pl
    out = pl.run_proposed_pipeline()               # ONE canonical 500-farmer solve
    yield out
    _teardown()


@pytest.fixture
def pipeline(_pipeline_cache):
    """Per-test independent deep copy of the single canonical run (isolation + mutation safety)."""
    return {"result": copy.deepcopy(_pipeline_cache["result"]),
            "ledger": copy.deepcopy(_pipeline_cache["ledger"])}


def test_pipeline_runs_and_stage_order_exact(pipeline):
    from farmsync.proposed import pipeline as pl
    out = pipeline
    assert out["result"]["stage_order"] == pl.STAGE_ORDER
    for s in pl.STAGE_ORDER:
        assert s in out["result"]


def test_metadata_propagation(pipeline):
    from farmsync.proposed import pipeline as pl
    from farmsync import config
    r = pipeline["result"]
    s0 = r["stage0_instance"]
    assert s0["master_seed"] == pl.DEV_SEED
    assert s0["config"]["epsilon"] == config.CANONICAL_B3_EPSILON
    assert s0["config"]["scenario_id"] == "P3_MIXED_V1"
    assert s0["config"]["alpha_dev_ref"] == pl.DEV_ALPHA and s0["config"]["lambda_dev_ref"] == pl.DEV_LAMBDA


def test_reproduces_existing_checkpoints(pipeline):
    r = pipeline["result"]
    p1 = json.load(open(f"{OUTP}/p1_participation_result.json"))
    p3 = json.load(open(f"{OUTP}/p3_reopt_result.json"))
    p4 = json.load(open(f"{OUTP}/p4_concentration_result.json"))
    a040 = [x for x in p4["alpha_sweep"] if x.get("alpha") == 0.40][0]
    l005 = [x for x in p3["lambda_frontier"] if x["lambda"] == 0.05][0]
    assert r["stage2_initial_response"]["accepted"] == p1["accepted"]
    assert r["stage4_stability_reopt"]["revised_cash"] == l005["revised_cash"]
    assert r["stage5_concentration"]["cash"] == a040["revised_cash"]
    assert r["stage5_concentration"]["max_LPS"] == a040["max_LPS"]


def test_realised_vs_revised_labels_never_confused(pipeline):
    r = pipeline["result"]
    assert r["stage2_initial_response"]["state"] == "REALIZED_INITIAL" and r["stage2_initial_response"]["consent_exists"]
    assert r["stage4_stability_reopt"]["state"] == "REVISED"
    assert r["stage4_stability_reopt"]["contains_unconsented_recommendations"] is True
    assert r["stage4_stability_reopt"]["revised_requires_renewed_consent"] is True
    assert r["stage5_concentration"]["state"] == "CONCENTRATION_CONTROLLED_REVISED_PLAN"
    assert r["stage5_concentration"]["contains_unconsented_recommendations"] is True
    assert "consent_exists" not in r["stage4_stability_reopt"]


def test_renewed_consent_flag_propagates(pipeline):
    r = pipeline["result"]
    assert r["revised_requires_renewed_consent"] is True
    assert r["stage4_stability_reopt"]["revised_requires_renewed_consent"] is True
    assert r["stage5_concentration"]["revised_requires_renewed_consent"] is True


def test_mixed_commitment_snapshot_reused_exactly(pipeline):
    r = pipeline["result"]
    locks = r["stage3_commitment"]["lock_counts"]
    assert locks == {"FLEXIBLE": 119, "SOFT_LOCK": 117, "HARD_LOCK": 95, "REJECTED_TERMINAL": 50}
    assert r["stage3_commitment"]["scenario_id"] == "P3_MIXED_V1"


def test_hardlock_invariant_and_concentration_validity(pipeline):
    r = pipeline["result"]
    assert r["stage4_stability_reopt"]["hard_lock_changes"] == 0
    assert r["stage5_concentration"]["hard_lock_changes"] == 0
    assert r["stage5_concentration"]["concentration_violations"] == 0
    assert r["stage5_concentration"]["max_LPS"] <= 0.40 + 1e-6


def test_representative_resilience_paths(pipeline):
    s6 = pipeline["result"]["stage6_resilience_demo"]
    n1, hz, infp = s6["nminus1_representative"], s6["hazard_representative"], s6["infeasible_path"]
    assert n1["backup_optimal"] and not n1["failed_plots_reused"] and n1["surviving_hard_lock_changes"] == 0
    assert hz["backup_optimal"] and not hz["failed_plots_reused"]
    assert infp is not None and infp["backup_optimal"] is False and infp["extracted_plan"] is False


def test_pipeline_refuses_non_optimal_upstream():
    from farmsync.proposed import pipeline as pl
    with pytest.raises(pl.PipelineError):
        pl._require_optimal("unit", "Infeasible")


def test_pipeline_deterministic_repeat(_pipeline_cache):
    from farmsync.proposed import pipeline as pl
    a = _pipeline_cache                              # the canonical run
    b = pl.run_proposed_pipeline()                  # one genuine fresh run to prove determinism
    assert json.dumps(a["result"], sort_keys=True, default=str) == json.dumps(b["result"], sort_keys=True, default=str)
    assert len(a["ledger"]) == len(b["ledger"])


def test_ledger_preserves_identity(pipeline):
    ledger = pipeline["ledger"]
    assert len(ledger) > 0
    seqs = [l["sequence"] for l in ledger]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    for l in ledger:
        assert l.get("farmer_id") is None or isinstance(l["farmer_id"], str)


def test_phase1_5_artifacts_unchanged_and_manifest_references():
    for fn in ["p1_participation_result.json", "p2_commitment_result.json", "p3_reopt_result.json",
               "p4_concentration_result.json", "p5_resilience_result.json"]:
        assert os.path.exists(os.path.join(OUTP, fn))
    man = json.load(open(os.path.join(OUTP, "p6_integration_manifest.json")))
    assert man["all_invariants_pass"] is True
    assert man["referenced_phase_artifacts"]["p3_reopt_result.json"] is not None
