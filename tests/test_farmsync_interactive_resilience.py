import importlib
import sys
from pathlib import Path

import pytest

from farmsync.experiment import build_instance
from farmsync.ingest import operational as opdata
from farmsync.planning import projected_return
from farmsync.interactive_resilience import (
    PROTOCOL_VERSION,
    POST_SHOCK_RECOVERY_MESSAGE,
    analyse_fixed_final_plan,
)
from farmsync.interactive_stress import final_plan_hash


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = (
    ROOT / "data" / "farmsync" / "processed"
)


@pytest.fixture(autouse=True)
def operational():
    opdata.clear_market_mult()
    opdata.load(str(PROCESSED))
    yield
    opdata.clear_market_mult()


def _onion_plan(min_farmers=2):
    inst = build_instance(
        20260812,
        tightness="base",
    )

    plots = {
        p.plot_id: p
        for p in inst["plots"]
    }

    selected = []
    seen_farmers = set()

    for p in inst["plots"]:
        if p.farmer_id in seen_farmers:
            continue

        try:
            pr = projected_return(
                "onion",
                p.region_id,
                p.active_season.value,
                p.area_ha,
            )
        except (ValueError, TypeError):
            continue

        if pr["cash_net_return"] <= 0:
            continue

        selected.append({
            "farmer_id": p.farmer_id,
            "plot_id": p.plot_id,
            "final_crop": "onion",
            "final_cash":
                pr["cash_net_return"],
        })

        seen_farmers.add(
            p.farmer_id
        )

        if len(selected) >= min_farmers:
            break

    assert len(selected) >= min_farmers

    return inst, plots, selected


def test_protocol_is_immediate_only():
    assert (
        PROTOCOL_VERSION
        == "interactive-resilience-v1"
    )

    assert "Not evaluated" in (
        POST_SHOCK_RECOVERY_MESSAGE
    )


def test_module_does_not_import_solver():
    sys.modules.pop("pulp", None)

    import farmsync.interactive_resilience as ir
    importlib.reload(ir)

    assert "pulp" not in sys.modules


def test_nminus1_selects_largest_expected_producer():
    _inst, plots, allocations = (
        _onion_plan(2)
    )

    out = analyse_fixed_final_plan(
        allocations,
        plots,
        dataset_hash="test",
        final_plan_revision=7,
    )

    assert out["available"] is True

    n1 = out["nminus1_representative"]

    expected = max(
        allocations,
        key=lambda a: (
            opdata.op_yield(
                plots[a["plot_id"]].region_id,
                "onion",
            )[0]
            * plots[a["plot_id"]].area_ha
        ),
    )

    assert n1["target_crop"] == "onion"
    assert (
        n1["failed_farmer"]
        == expected["farmer_id"]
    )

    assert (
        n1["target_loss_fraction"]
        == pytest.approx(
            n1[
                "pre_shock_largest_producer_share"
            ],
            abs=1e-6,
        )
    )


def test_nminus1_removes_all_realised_plots_of_failed_farmer():
    inst = build_instance(
        20260812,
        tightness="base",
    )

    plots = {
        p.plot_id: p
        for p in inst["plots"]
    }

    # Use two positive onion allocations owned by the same farmer
    # when available, plus a second producer. This validates that
    # N-1 removes the farmer's entire realised footprint.
    by_farmer = {}

    for p in inst["plots"]:
        try:
            pr = projected_return(
                "onion",
                p.region_id,
                p.active_season.value,
                p.area_ha,
            )
        except (ValueError, TypeError):
            continue

        if pr["cash_net_return"] <= 0:
            continue

        by_farmer.setdefault(
            p.farmer_id, []
        ).append((p, pr))

    multi = next(
        (
            (fid, rows)
            for fid, rows in by_farmer.items()
            if len(rows) >= 2
        ),
        None,
    )

    if multi is None:
        pytest.skip(
            "No two positive onion plots for one farmer"
        )

    fid, rows = multi

    p1, pr1 = rows[0]
    p2, pr2 = rows[1]

    other = next(
        (ofid, orows[0])
        for ofid, orows in by_farmer.items()
        if ofid != fid
    )

    ofid, (p3, pr3) = other

    allocations = [
        {
            "farmer_id": fid,
            "plot_id": p1.plot_id,
            "final_crop": "onion",
            "final_cash":
                pr1["cash_net_return"],
        },
        {
            "farmer_id": fid,
            "plot_id": p2.plot_id,
            "final_crop": "onion",
            "final_cash":
                pr2["cash_net_return"],
        },
        {
            "farmer_id": ofid,
            "plot_id": p3.plot_id,
            "final_crop": "onion",
            "final_cash":
                pr3["cash_net_return"],
        },
    ]

    out = analyse_fixed_final_plan(
        allocations,
        plots,
    )

    n1 = out["nminus1_representative"]

    if n1["failed_farmer"] == fid:
        assert (
            n1["affected_allocations"]
            == 2
        )

        assert set(
            n1["failed_plot_ids"]
        ) == {
            p1.plot_id,
            p2.plot_id,
        }


def test_hazard_representative_is_lexically_first_realised_zone():
    _inst, plots, allocations = (
        _onion_plan(4)
    )

    out = analyse_fixed_final_plan(
        allocations,
        plots,
    )

    hz = out[
        "hazard_zone_outage"
    ]

    zones = sorted({
        plots[a["plot_id"]].hazard_zone
        for a in allocations
    })

    assert hz["available"] is True

    assert (
        hz["representative"]["zone"]
        == zones[0]
    )

    assert (
        hz["representative"][
            "selection_rule"
        ]
        == (
            "lexicographically first non-empty "
            "hazard zone in the realised plan"
        )
    )


def test_cash_exposure_reconciles_exactly():
    _inst, plots, allocations = (
        _onion_plan(3)
    )

    out = analyse_fixed_final_plan(
        allocations,
        plots,
    )

    n1 = out["nminus1_representative"]

    total = sum(
        a["final_cash"]
        for a in allocations
    )

    assert (
        n1["total_expected_cash_before"]
        == pytest.approx(
            round(total, 0)
        )
    )

    assert (
        n1["immediate_expected_cash_loss"]
        + n1[
            "immediate_remaining_expected_cash"
        ]
        == pytest.approx(
            round(total, 0)
        )
    )


def test_identity_matches_stress_protocol_hash():
    _inst, plots, allocations = (
        _onion_plan(2)
    )

    out = analyse_fixed_final_plan(
        allocations,
        plots,
    )

    assert (
        out["final_plan_hash"]
        == final_plan_hash(allocations)
    )


def test_recovery_is_explicitly_not_evaluated():
    _inst, plots, allocations = (
        _onion_plan(2)
    )

    out = analyse_fixed_final_plan(
        allocations,
        plots,
    )

    recovery = out[
        "post_shock_recovery"
    ]

    assert recovery["available"] is False

    assert (
        recovery["reason"]
        == POST_SHOCK_RECOVERY_MESSAGE
    )

    assert out["reoptimization"] is False
    assert out["backup_optimiser"] is False
