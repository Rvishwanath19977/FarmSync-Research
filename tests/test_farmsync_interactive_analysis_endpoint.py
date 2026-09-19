import importlib

import pytest
from flask import Flask


@pytest.fixture()
def client_and_xr(tmp_path, monkeypatch):
    app = Flask(__name__)

    import farmsync_routes
    importlib.reload(farmsync_routes)

    from farmsync import exploratory_run as xr

    # Keep test-created working runs completely outside the real results tree.
    monkeypatch.setattr(
        xr,
        "_RUN_ROOT",
        str(tmp_path / "exploratory"),
    )

    farmsync_routes.register_farmsync_routes(app)
    app.config.update(TESTING=True)

    return app.test_client(), xr


def _create_finalised_builtin(client, xr):
    r = client.post("/api/farmsync/select-builtin")
    assert r.status_code == 200

    r = client.post(
        "/api/farmsync/working-plan/start"
    )
    assert r.status_code == 200

    wp = r.get_json()
    assert wp["run_id"]

    rid = wp["run_id"]

    r = client.post(
        f"/api/farmsync/working-plan/{rid}/replan"
    )
    assert r.status_code == 200
    assert r.get_json()["available"] is True

    run = xr.get_run(rid)

    if run["workflow"]["n_consent_pending"] > 0:
        r = client.post(
            f"/api/farmsync/working-plan/{rid}/consent-bulk",
            json={"decision": "ACCEPT"},
        )
        assert r.status_code == 200

    r = client.post(
        f"/api/farmsync/working-plan/{rid}/finalise"
    )

    assert r.status_code == 200
    fin = r.get_json()

    assert fin["available"] is True
    assert fin["state"] == "FINAL_REALIZED"

    return rid


def test_run_analysis_requires_current_final_plan(
    client_and_xr,
):
    client, _xr = client_and_xr

    assert client.post(
        "/api/farmsync/select-builtin"
    ).status_code == 200

    wp = client.post(
        "/api/farmsync/working-plan/start"
    ).get_json()

    rid = wp["run_id"]

    r = client.post(
        f"/api/farmsync/working-plan/{rid}/run-analysis"
    )

    assert r.status_code == 400

    body = r.get_json()

    assert body["available"] is False
    assert "finalised plan" in body["error"].lower()


def test_interactive_analysis_not_run_current_stale_lifecycle(
    client_and_xr,
):
    client, xr = client_and_xr

    rid = _create_finalised_builtin(
        client,
        xr,
    )

    # ---------------------------------------------------------
    # 1. Final plan exists, but analysis has not been executed.
    # ---------------------------------------------------------
    r = client.get(
        f"/api/farmsync/working-plan/{rid}/analysis"
    )

    assert r.status_code == 200

    before = r.get_json()

    assert before["available"] is True
    assert before["uncertainty"]["available"] is False
    assert before["uncertainty"]["status"] == "NOT_RUN"

    revision_1 = before["final_plan_revision"]

    # ---------------------------------------------------------
    # 2. Explicit POST executes scientific stress analysis.
    # ---------------------------------------------------------
    r = client.post(
        f"/api/farmsync/working-plan/{rid}/run-analysis"
    )

    assert r.status_code == 200

    executed = r.get_json()

    assert executed["available"] is True
    assert executed["status"] == "CURRENT"
    assert (
        executed["protocol_version"]
        == "interactive-stress-v1"
    )

    hash_1 = executed["final_plan_hash"]

    assert hash_1
    assert executed["final_plan_revision"] == revision_1

    u = executed["uncertainty"]

    assert u["available"] is True
    assert u["status"] == "CURRENT"
    assert u["reoptimization"] is False
    assert u["participation_uncertainty"] is False

    assert set(u["scenarios"]) == {
        "UW",
        "UM",
        "UR",
        "UJ",
    }

    assert u["scenarios"]["UJ"]["channels"] == [
        "W",
        "M",
        "R",
    ]

    rr = executed["resilience"]

    assert rr["available"] is True
    assert rr["status"] == "CURRENT"

    assert (
        rr["protocol_version"]
        == "interactive-resilience-v1"
    )

    assert (
        rr["final_plan_hash"]
        == hash_1
    )

    assert rr["reoptimization"] is False
    assert rr["backup_optimiser"] is False

    assert (
        rr["post_shock_recovery"][
            "available"
        ]
        is False
    )

    # ---------------------------------------------------------
    # 3. Read-only GET returns persisted CURRENT analysis.
    # ---------------------------------------------------------
    r = client.get(
        f"/api/farmsync/working-plan/{rid}/analysis"
    )

    assert r.status_code == 200

    current = r.get_json()

    assert current["available"] is True

    cu = current["uncertainty"]

    assert cu["available"] is True
    assert cu["status"] == "CURRENT"
    assert cu["final_plan_hash"] == hash_1
    assert (
        cu["protocol_version"]
        == "interactive-stress-v1"
    )

    cr = current["resilience"]

    assert cr["available"] is True
    assert cr["status"] == "CURRENT"

    assert (
        cr["protocol_version"]
        == "interactive-resilience-v1"
    )

    assert (
        cr["final_plan_hash"]
        == hash_1
    )

    # It must genuinely be persisted in this run.
    persisted = xr.get_run(rid)

    assert (
        persisted["interactive_analysis"]["final_plan_hash"]
        == hash_1
    )

    assert (
        persisted["interactive_analysis"][
            "resilience_result"
        ]["final_plan_hash"]
        == hash_1
    )

    assert (
        persisted["interactive_analysis"][
            "resilience_protocol_version"
        ]
        == "interactive-resilience-v1"
    )

    # ---------------------------------------------------------
    # 4. Change one actually-realised upstream farmer decision.
    #    This invalidates the previous final plan.
    # ---------------------------------------------------------
    realised = next(
        rec
        for rec in persisted["recommendations"]
        if rec.get("realised")
    )

    r = client.post(
        f"/api/farmsync/working-plan/{rid}/response",
        json={
            "farmer_id": realised["farmer_id"],
            "plot_id": realised["plot_id"],
            "action": "REJECT",
        },
    )

    assert r.status_code == 200

    # Old final plan is now upstream-stale, so Analyse itself
    # must be unavailable until the plan is re-finalised.
    r = client.get(
        f"/api/farmsync/working-plan/{rid}/analysis"
    )

    invalidated = r.get_json()

    assert invalidated["available"] is False

    # ---------------------------------------------------------
    # 5. Replan + resolve renewed consent if any + finalise.
    # ---------------------------------------------------------
    r = client.post(
        f"/api/farmsync/working-plan/{rid}/replan"
    )

    assert r.status_code == 200
    assert r.get_json()["available"] is True

    run = xr.get_run(rid)

    if run["workflow"]["n_consent_pending"] > 0:
        r = client.post(
            f"/api/farmsync/working-plan/{rid}/consent-bulk",
            json={"decision": "ACCEPT"},
        )
        assert r.status_code == 200

    r = client.post(
        f"/api/farmsync/working-plan/{rid}/finalise"
    )

    assert r.status_code == 200
    assert r.get_json()["available"] is True

    # ---------------------------------------------------------
    # 6. New final plan exists. Old saved analysis is retained
    #    for audit history but MUST be classified STALE and its
    #    scientific scenario metrics MUST NOT leak into the
    #    current-plan Analyse response.
    # ---------------------------------------------------------
    r = client.get(
        f"/api/farmsync/working-plan/{rid}/analysis"
    )

    assert r.status_code == 200

    stale = r.get_json()

    assert stale["available"] is True

    su = stale["uncertainty"]

    assert su["available"] is False
    assert su["status"] == "STALE"

    assert "scenarios" not in su

    sr = stale["resilience"]

    assert sr["available"] is False
    assert sr["status"] == "STALE"

    assert (
        "nminus1_representative"
        not in sr
    )

    assert (
        "hazard_zone_outage"
        not in sr
    )

    assert (
        su["analysed_final_plan_revision"]
        == revision_1
    )

    assert (
        su["current_final_plan_revision"]
        > revision_1
    )

    # The historical result is still persisted, not silently erased.
    persisted_after = xr.get_run(rid)

    assert (
        persisted_after["interactive_analysis"][
            "final_plan_hash"
        ]
        == hash_1
    )
