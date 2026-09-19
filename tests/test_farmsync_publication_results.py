import json
import os

from flask import Flask

import farmsync_routes


def _client():
    app = Flask(__name__)
    app.testing = True

    farmsync_routes.register_farmsync_routes(
        app
    )

    return app.test_client()


def test_publication_results_endpoint_reads_frozen_artifact_only(
    monkeypatch,
):
    # If the endpoint accidentally tries to execute
    # the A/B scientific runner, this test must fail.
    import farmsync.scenario_ab as sab

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "publication-results GET must not "
            "execute scenario_ab.run_ab"
        )

    monkeypatch.setattr(
        sab,
        "run_ab",
        forbidden,
    )

    c = _client()

    response = c.get(
        "/api/farmsync/scenario-results"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["available"] is True
    assert data["read_only"] is True

    assert (
        data["scientific_recomputation"]
        is False
    )

    assert (
        data["integrity"]["verified"]
        is True
    )

    summary = data["summary"]
    freeze = data["freeze"]

    assert (
        summary["protocol_version"]
        == "scenario-ab-v3"
    )

    assert (
        summary["dataset_hash"]
        == "1f271676f5317088"
    )

    assert (
        freeze[
            "all_verification_checks_pass"
        ]
        is True
    )

    assert (
        summary["scenario_a"]
        ["headline"]
        ["realised_plots"]
        == 350
    )

    assert (
        summary["scenario_b"]
        ["headline"]
        ["realised_plots"]
        == 304
    )

    assert (
        summary["scenario_b"]
        ["withdrawn_farmer_count"]
        == 7
    )

    assert (
        summary["scenario_b"]
        ["withdrawal_affected_offer_rows"]
        == 8
    )


def test_publication_results_endpoint_is_get_only():
    c = _client()

    response = c.post(
        "/api/farmsync/scenario-results"
    )

    assert response.status_code == 405


def test_legacy_publication_results_alias_remains_read_only():
    c = _client()
    response = c.get("/api/farmsync/publication-results")
    assert response.status_code == 200
    assert response.get_json()["artifact_kind"] == "controlled_ab_case_study"


def test_publication_results_template_workspace_present():
    root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    html = open(
        os.path.join(
            root,
            "templates",
            "farmsync.html",
        ),
        encoding="utf-8",
    ).read()

    assert (
        'data-ws="scenario"'
        in html
    )

    assert (
        'id="ws-scenario"'
        in html
    )

    assert (
        "Scenario A/B Results"
        in html
    )


def test_publication_results_js_is_read_only_artifact_view():
    root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    js = open(
        os.path.join(
            root,
            "static",
            "js",
            "farmsync.js",
        ),
        encoding="utf-8",
    ).read()

    assert (
        'loaders.scenario'
        in js
    )

    assert (
        '"/api/farmsync/scenario-results"'
        in js
    )

    assert (
        '"scenario"'
        in js
    )

    section = js[
        js.index(
            "loaders.scenario"
        ):
        js.index(
            "loaders.repro"
        )
    ]

    assert "fetch(" not in section
    assert "post(" not in section

    assert (
        "scenario_ab"
        not in section
    )

    assert (
        "scientific recomputation"
        in section.lower()
        or "recomputation"
        in section.lower()
    )


def test_committed_summary_and_freeze_are_consistent():
    root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    base = os.path.join(
        root,
        "results",
        "farmsync",
        "case_study",
        "scenario_ab_v3",
    )

    with open(
        os.path.join(
            base,
            "scenario_ab_v3_summary.json",
        ),
        encoding="utf-8",
    ) as f:
        summary = json.load(f)

    with open(
        os.path.join(
            base,
            "FREEZE.json",
        ),
        encoding="utf-8",
    ) as f:
        freeze = json.load(f)

    assert (
        summary["protocol_version"]
        == freeze["protocol_version"]
        == "scenario-ab-v3"
    )

    assert (
        summary["dataset_hash"]
        == freeze["dataset_hash"]
    )

    assert (
        summary["scenario_a"]
        ["final_plan_hash"]
        == freeze[
            "scenario_a_final_plan_hash"
        ]
    )

    assert (
        summary["scenario_b"]
        ["final_plan_hash"]
        == freeze[
            "scenario_b_final_plan_hash"
        ]
    )

    assert (
        freeze[
            "all_verification_checks_pass"
        ]
        is True
    )



def test_scenario_summary_hash_survives_git_newline_normalization():
    """Frozen Scenario A/B content remains verified after LF Git checkout."""
    import json
    from pathlib import Path
    import farmsync_routes as routes

    case_dir = Path(routes._CASE_STUDY_DIR)

    freeze = json.loads(
        (case_dir / "FREEZE.json").read_text(encoding="utf-8")
    )

    expected = next(
        item["sha256"]
        for item in freeze["files"]
        if item.get("path") == "scenario_ab_v3_summary.json"
    )

    raw = (case_dir / "scenario_ab_v3_summary.json").read_bytes()
    lf_checkout = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    assert routes._sha256_matches_frozen_text(lf_checkout, expected)

    # Newline differences are allowed; content differences are not.
    assert not routes._sha256_matches_frozen_text(
        lf_checkout + b" ",
        expected,
    )
