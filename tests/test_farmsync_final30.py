from __future__ import annotations

import inspect

from farmsync import final30


def test_frozen_matrix_identity_and_shape():
    m = final30.load_matrix()

    assert m["version"] == "publication-experiment-matrix-v1"
    assert m["status"] == "FROZEN_BEFORE_FINAL30"

    assert m["families"]["EPSILON_SENSITIVITY"]["values"] == [
        0.80, 0.90, 0.95, 1.00
    ]

    assert m["families"]["LAMBDA_STABILITY"]["values"] == [
        0.0, 0.05, 0.10, 0.25, 0.50, 1.00
    ]

    assert m["families"]["ALPHA_CONCENTRATION"]["values"] == [
        1.00, 0.60, 0.50, 0.40, 0.33
    ]

    assert m["families"]["ACTION_ROBUSTNESS"]["profiles"] == [
        "PRIMARY", "S1", "S2"
    ]

    assert m["families"]["UNCERTAINTY"]["conditions"] == [
        "U0", "UW", "UM", "UR", "UP", "UJ"
    ]

    assert m["families"]["SCALABILITY"]["n_farmers_values"] == [
        25, 50, 100, 250, 500
    ]


def test_exact_final30_cell_count():
    m = final30.load_matrix()
    assert final30.planned_cell_count(m) == 900


def test_reproducibility_artifacts_match_frozen_hashes():
    m = final30.load_matrix()
    out = final30._verify_matrix_reproducibility(m)

    assert out["seed_count"] == 30
    assert len(out["seeds"]) == 30
    assert len(set(out["seeds"])) == 30


def test_frozen_dataset_subset_matches_pre_eval_freeze():
    out = final30.verify_frozen_datasets()

    assert out["dataset_file_count"] > 0
    assert len(out["dataset_attestation_sha256"]) == 64


def test_required_source_provenance_is_verified():
    out = final30.verify_source_provenance()

    assert out["verified"] is True

    assert out["mode"] in {
        "historical_git_ancestry",
        "standalone_extraction",
    }

    if out["mode"] == "historical_git_ancestry":
        assert final30.is_ancestor(
            final30.MATRIX_FREEZE_COMMIT
        )
        assert final30.is_ancestor(
            final30.REQUIRED_IMPLEMENTATION_BASE_COMMIT
        )
    else:
        assert (
            out["source_commit"]
            == final30.EXPECTED_SOURCE_COMMIT
        )
        assert (
            out["source_snapshot_sha256"]
            == final30.EXPECTED_SOURCE_SNAPSHOT_SHA256
        )
        assert (
            out["extraction_baseline_sha256"]
            == final30.EXPECTED_EXTRACTION_BASELINE_SHA256
        )


def test_action_layer_has_publication_parameter_hooks():
    from farmsync.proposed import actions as A

    sig = inspect.signature(
        A.run_action_consent_layer
    )

    assert "lam" in sig.parameters
    assert "alpha" in sig.parameters


def test_action_layer_exposes_final30_measurements():
    from farmsync.proposed import actions as A

    src = inspect.getsource(
        A.run_action_consent_layer
    )

    for key in (
        "recommended_revised_stability",
        "recommended_revised_phase4",
        "recommended_revised_concentration",
        "final_realized_concentration",
    ):
        assert key in src


def test_check_is_solver_free_and_has_expected_plan():
    out = final30.check()

    assert out["planned_cells"] == 900
    assert out["reproducibility"]["seed_count"] == 30
    assert (
        out["solver_amendment"]["solver_amendment_sha256"]
        == final30.EXPECTED_SOLVER_AMENDMENT_SHA256
    )
    assert (
        out["solver_amendment"]["dev_checkpoint_sha256"]
        == final30.EXPECTED_DEV_CHECKPOINT_SHA256
    )
    assert (
        out["solver_amendment"]["effective_solver"]["gapRel"]
        == 1e-6
    )


def test_pre_final30_solver_amendment_is_pinned():
    out = final30.verify_pre_final30_solver_amendment()

    assert (
        out["solver_amendment_sha256"]
        == final30.EXPECTED_SOLVER_AMENDMENT_SHA256
    )
    assert (
        out["dev_checkpoint_sha256"]
        == final30.EXPECTED_DEV_CHECKPOINT_SHA256
    )

    assert out["effective_solver"]["engine"] == "CBC"
    assert out["effective_solver"]["gapRel"] == 1e-6
    assert out["effective_solver"]["timeLimit_s"] == 120


def test_effective_cbc_solver_uses_amended_tolerance():
    from farmsync import solver

    configured = solver.cbc_solver()

    assert configured.optionsDict["gapRel"] == 1e-6
    assert configured.timeLimit == 120
    assert configured.optionsDict["threads"] == solver.cbc_threads()


def test_solver_amended_dev_checkpoint_identity_and_values():
    checkpoint = final30.read_json(
        final30.project_root() / final30.DEV_CHECKPOINT_REL
    )

    assert (
        checkpoint["provenance"]
        == "DEVELOPMENT_CHECKPOINT_SOLVER_AMENDED"
    )

    assert checkpoint["seed"] == 20260812

    assert checkpoint["U0"]["baselines"]["B2"]["cash"] == 13822731.0
    assert checkpoint["U0"]["baselines"]["B3"]["cash"] == 13142166.0
    assert (
        checkpoint["U0"]["proposed"]["tiers"]["FINAL_REALIZED"]
        == 12362577.0
    )

    assert checkpoint["UJ"]["realisation_hash"] == "daf331e3d0b2a1fc"
    assert checkpoint["UJ"]["baselines"]["B1"]["cash"] == 13158690.0
    assert checkpoint["UJ"]["baselines"]["B2"]["cash"] == 12545988.0
    assert checkpoint["UJ"]["baselines"]["B3"]["cash"] == 11930066.0
    assert (
        checkpoint["UJ"]["proposed"]["tiers"]["INITIAL_REALIZED"]
        == 10716058.0
    )
    assert (
        checkpoint["UJ"]["proposed"]["tiers"]["RECOMMENDED_REVISED"]
        == 11315824.0
    )
    assert (
        checkpoint["UJ"]["proposed"]["tiers"]["FINAL_REALIZED"]
        == 11208694.0
    )
    assert checkpoint["UJ"]["proposed"]["renewed_prompts"] == 52
    assert checkpoint["UJ"]["proposed"]["consent_coverage_final"] == 1.0
