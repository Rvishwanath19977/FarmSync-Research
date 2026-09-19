from farmsync.exploratory_run import (
    _current_final_allocations,
    _final_plan_identity_hash,
    _interactive_uncertainty_view,
)
from farmsync.interactive_stress import final_plan_hash


def _run():
    return {
        "dataset_hash": "dataset-A",
        "final_plan_revision": 3,
        "recommendations": [
            {
                "farmer_id": "F1",
                "plot_id": "P1",
                "final_crop": "onion",
                "final_cash": 12345,
                "realised": True,
            },
            {
                "farmer_id": "F2",
                "plot_id": "P2",
                "final_crop": None,
                "final_cash": None,
                "realised": False,
            },
        ],
    }


def test_session_hash_matches_scientific_engine_hash():
    run = _run()
    allocations = _current_final_allocations(run)

    assert _final_plan_identity_hash(
        allocations
    ) == final_plan_hash(allocations)


def test_analysis_state_not_run():
    view = _interactive_uncertainty_view(_run())

    assert view["available"] is False
    assert view["status"] == "NOT_RUN"
    assert view["current_final_plan_revision"] == 3


def test_analysis_state_current():
    run = _run()

    allocations = _current_final_allocations(run)
    h = _final_plan_identity_hash(allocations)

    run["interactive_analysis"] = {
        "protocol_version": "interactive-stress-v1",
        "dataset_hash": "dataset-A",
        "final_plan_hash": h,
        "final_plan_revision": 3,
        "generated_at": "2026-09-18T10:00:00Z",
        "result": {
            "available": True,
            "protocol_version": "interactive-stress-v1",
            "final_plan_hash": h,
            "scenarios": {
                "UW": {"available": True},
            },
        },
    }

    view = _interactive_uncertainty_view(run)

    assert view["available"] is True
    assert view["status"] == "CURRENT"
    assert view["final_plan_hash"] == h
    assert view["scenarios"]["UW"]["available"] is True


def test_analysis_state_stale_on_revision_change_and_hides_metrics():
    run = _run()

    allocations = _current_final_allocations(run)
    h = _final_plan_identity_hash(allocations)

    run["interactive_analysis"] = {
        "protocol_version": "interactive-stress-v1",
        "dataset_hash": "dataset-A",
        "final_plan_hash": h,
        "final_plan_revision": 2,
        "generated_at": "2026-09-18T10:00:00Z",
        "result": {
            "available": True,
            "scenarios": {
                "UW": {
                    "SECRET_OLD_METRIC": 999,
                },
            },
        },
    }

    view = _interactive_uncertainty_view(run)

    assert view["available"] is False
    assert view["status"] == "STALE"

    # Old scientific metrics must not leak into the active-plan view.
    assert "scenarios" not in view
    assert "SECRET_OLD_METRIC" not in str(view)


def test_analysis_state_stale_on_allocation_change():
    run = _run()

    allocations = _current_final_allocations(run)
    old_hash = _final_plan_identity_hash(allocations)

    run["interactive_analysis"] = {
        "protocol_version": "interactive-stress-v1",
        "dataset_hash": "dataset-A",
        "final_plan_hash": old_hash,
        "final_plan_revision": 3,
        "generated_at": "2026-09-18T10:00:00Z",
        "result": {
            "available": True,
            "scenarios": {"UM": {"available": True}},
        },
    }

    run["recommendations"][0]["final_cash"] = 54321

    view = _interactive_uncertainty_view(run)

    assert view["available"] is False
    assert view["status"] == "STALE"
    assert view["analysed_final_plan_hash"] != (
        view["current_final_plan_hash"]
    )


from farmsync.exploratory_run import (
    _interactive_resilience_view,
)


def test_resilience_state_not_run():
    view = _interactive_resilience_view(
        _run()
    )

    assert view["available"] is False
    assert view["status"] == "NOT_RUN"
    assert (
        view["protocol_version"]
        == "interactive-resilience-v1"
    )


def test_resilience_state_current():
    run = _run()

    allocations = (
        _current_final_allocations(run)
    )

    h = _final_plan_identity_hash(
        allocations
    )

    run["interactive_analysis"] = {
        "protocol_version":
            "interactive-stress-v1",
        "resilience_protocol_version":
            "interactive-resilience-v1",
        "dataset_hash":
            "dataset-A",
        "final_plan_hash":
            h,
        "final_plan_revision":
            3,
        "generated_at":
            "2026-09-18T10:00:00Z",
        "result": {
            "available": True,
        },
        "resilience_result": {
            "available": True,
            "protocol_version":
                "interactive-resilience-v1",
            "final_plan_hash":
                h,
            "nminus1_representative": {
                "failed_farmer": "F1",
            },
        },
    }

    view = _interactive_resilience_view(
        run
    )

    assert view["available"] is True
    assert view["status"] == "CURRENT"

    assert (
        view["nminus1_representative"][
            "failed_farmer"
        ]
        == "F1"
    )


def test_resilience_state_stale_hides_old_metrics():
    run = _run()

    allocations = (
        _current_final_allocations(run)
    )

    h = _final_plan_identity_hash(
        allocations
    )

    run["interactive_analysis"] = {
        "protocol_version":
            "interactive-stress-v1",
        "resilience_protocol_version":
            "interactive-resilience-v1",
        "dataset_hash":
            "dataset-A",
        "final_plan_hash":
            h,
        "final_plan_revision":
            2,
        "generated_at":
            "2026-09-18T10:00:00Z",
        "result": {
            "available": True,
        },
        "resilience_result": {
            "available": True,
            "SECRET_OLD_RESILIENCE":
                999,
        },
    }

    view = _interactive_resilience_view(
        run
    )

    assert view["available"] is False
    assert view["status"] == "STALE"

    assert (
        "SECRET_OLD_RESILIENCE"
        not in str(view)
    )
