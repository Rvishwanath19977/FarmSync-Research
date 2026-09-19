from collections import Counter

import pytest

import farmsync_routes
from farmsync import exploratory_run as xr
from farmsync import scenario_ab as sab


@pytest.fixture
def builtin_pkg():
    return farmsync_routes.package_from_files(
        farmsync_routes._load_builtin_files(),
        source="builtin",
    )


@pytest.fixture
def isolated_runs(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        xr,
        "_RUN_ROOT",
        str(tmp_path / "exploratory"),
    )


def test_scenario_b_initial_manifest_is_deterministic_and_farmer_withdrawal_scoped(
    builtin_pkg,
    isolated_runs,
):
    run = xr.create_run(
        builtin_pkg,
        "FarmSync built-in dataset",
        kind="builtin",
    )

    first = sab.build_initial_manifest(
        run,
        "B",
    )

    second = sab.build_initial_manifest(
        run,
        "B",
    )

    assert first == second
    assert first

    recommendations = list(
        run["recommendations"]
    )

    offer_rows = [
        rec
        for rec in recommendations
        if sab._is_offer(rec)
    ]

    accept_rows = [
        rec
        for rec in offer_rows
        if sab._effective_initial_response(
            rec
        )
        == "ACCEPT"
    ]

    eligible_farmers = {
        str(rec["farmer_id"])
        for rec in accept_rows
    }

    withdraw_rows = [
        row
        for row in first
        if row["action"]
        == "WITHDRAW"
    ]

    withdrawn_farmers = {
        row["farmer_id"]
        for row in withdraw_rows
    }

    assert len(
        withdrawn_farmers
    ) == sab._quota(
        len(eligible_farmers),
        1,
        40,
    )

    # Every selected farmer is withdrawn from
    # ALL of that farmer's offered rows.
    for farmer_id in withdrawn_farmers:
        expected_plots = {
            str(rec["plot_id"])
            for rec in offer_rows
            if str(
                rec["farmer_id"]
            )
            == farmer_id
        }

        actual_plots = {
            row["plot_id"]
            for row in withdraw_rows
            if row["farmer_id"]
            == farmer_id
        }

        assert actual_plots == (
            expected_plots
        )

    assert all(
        row["selection_scope"]
        == "FARMER_CYCLE"
        for row in withdraw_rows
    )

    assert all(
        sab._is_offer(
            next(
                rec
                for rec
                in recommendations
                if str(
                    rec["farmer_id"]
                )
                == row["farmer_id"]
                and str(
                    rec["plot_id"]
                )
                == row["plot_id"]
            )
        )
        for row in withdraw_rows
    )

    remaining_accept_rows = [
        rec
        for rec in accept_rows
        if str(rec["farmer_id"])
        not in withdrawn_farmers
    ]

    reject_rows = [
        row
        for row in first
        if row["action"]
        == "REJECT"
    ]

    no_response_rows = [
        row
        for row in first
        if row["action"]
        == "NO_RESPONSE"
    ]

    assert len(
        reject_rows
    ) == sab._quota(
        len(remaining_accept_rows),
        1,
        10,
    )

    assert len(
        no_response_rows
    ) == sab._quota(
        len(remaining_accept_rows),
        1,
        20,
    )

    assert all(
        row["reference_response"]
        == "ACCEPT"
        for row
        in reject_rows
        + no_response_rows
    )

    assert all(
        row["selection_scope"]
        == "OFFER_ROW"
        for row
        in reject_rows
        + no_response_rows
    )

    assert not any(
        row["action"] == "MODIFY"
        for row in first
    )

    assert (
        sab._manifest_hash(
            "initial",
            first,
        )
        == sab._manifest_hash(
            "initial",
            second,
        )
    )


def test_scenario_a_has_no_constructed_initial_override(
    builtin_pkg,
    isolated_runs,
):
    run = xr.create_run(
        builtin_pkg,
        "FarmSync built-in dataset",
        kind="builtin",
    )

    assert (
        sab.build_initial_manifest(
            run,
            "A",
        )
        == []
    )


def test_scenario_ab_end_to_end(
    builtin_pkg,
    isolated_runs,
):
    result = sab.run_ab(
        builtin_pkg
    )

    a = result["scenario_a"]
    b = result["scenario_b"]
    cmp = result["comparison"]

    assert result["protocol_version"] == (
        "scenario-ab-v3"
    )

    assert a["scenario"] == "A"
    assert b["scenario"] == "B"

    assert (
        a["dataset_hash"]
        == b["dataset_hash"]
    )

    assert cmp["same_dataset"] is True

    assert (
        a["uncertainty_protocol_version"]
        == "interactive-stress-v1"
    )

    assert (
        b["uncertainty_protocol_version"]
        == "interactive-stress-v1"
    )

    assert (
        a["resilience_protocol_version"]
        == "interactive-resilience-v1"
    )

    assert (
        b["resilience_protocol_version"]
        == "interactive-resilience-v1"
    )

    assert (
        a["finalisation"]["state"]
        == "FINAL_REALIZED"
    )

    assert (
        b["finalisation"]["state"]
        == "FINAL_REALIZED"
    )

    assert (
        a["analysis"]["uncertainty"]["status"]
        == "CURRENT"
    )

    assert (
        b["analysis"]["uncertainty"]["status"]
        == "CURRENT"
    )

    assert (
        a["analysis"]["resilience"]["status"]
        == "CURRENT"
    )

    assert (
        b["analysis"]["resilience"]["status"]
        == "CURRENT"
    )

    assert set(
        a["analysis"]["uncertainty"][
            "scenarios"
        ]
    ) == {
        "UW",
        "UM",
        "UR",
        "UJ",
    }

    assert set(
        b["analysis"]["uncertainty"][
            "scenarios"
        ]
    ) == {
        "UW",
        "UM",
        "UR",
        "UJ",
    }

    assert not a["initial_manifest"]
    assert b["initial_manifest"]

    initial_counts = Counter(
        row["action"]
        for row in b["initial_manifest"]
    )

    assert (
        sum(initial_counts.values())
        == len(b["initial_manifest"])
    )

    assert "MODIFY" not in initial_counts

    assert (
        a["final_plan_hash"]
        != b["final_plan_hash"]
    )

    assert (
        cmp["final_plan_hash_changed"]
        is True
    )

    assert (
        cmp["headline_scenario_a"]
        == a["headline"]
    )

    assert (
        cmp["headline_scenario_b"]
        == b["headline"]
    )


def test_scenario_b_renewed_manifest_is_deterministic_and_exact_quota(
    builtin_pkg,
    isolated_runs,
):
    created = xr.create_run(
        builtin_pkg,
        "FarmSync built-in dataset",
        kind="builtin",
    )

    manifest = sab.build_initial_manifest(
        created,
        "B",
    )

    sab.apply_initial_manifest(
        created["run_id"],
        manifest,
    )

    replanned = xr.replan(
        created["run_id"]
    )

    assert replanned["available"] is True

    run = xr.get_run(
        created["run_id"]
    )

    renewed = sab.build_renewed_manifest(
        run,
        "B",
    )

    assert renewed

    assert all(
        row["decision"]
        in {
            "ACCEPT",
            "REJECT",
            "NO_RESPONSE",
        }
        for row in renewed
    )

    assert (
        renewed
        == sab.build_renewed_manifest(
            run,
            "B",
        )
    )

    candidate_counts = {
        row["candidate_count"]
        for row in renewed
    }

    assert len(candidate_counts) == 1

    n = candidate_counts.pop()

    counts = Counter(
        row["decision"]
        for row in renewed
    )

    assert counts["REJECT"] == sab._quota(
        n,
        1,
        10,
    )

    assert counts["NO_RESPONSE"] == sab._quota(
        n,
        1,
        20,
    )

    assert counts["ACCEPT"] == (
        n
        - sab._quota(n, 1, 10)
        - sab._quota(n, 1, 20)
    )


def test_scenario_a_renewed_manifest_accepts_all_pending(
    builtin_pkg,
    isolated_runs,
):
    created = xr.create_run(
        builtin_pkg,
        "FarmSync built-in dataset",
        kind="builtin",
    )

    replanned = xr.replan(
        created["run_id"]
    )

    assert replanned["available"] is True

    run = xr.get_run(
        created["run_id"]
    )

    renewed = sab.build_renewed_manifest(
        run,
        "A",
    )

    assert renewed

    assert all(
        row["decision"] == "ACCEPT"
        for row in renewed
    )
