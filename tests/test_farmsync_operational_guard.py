"""Regression tests for interactive FarmSync operational-data initialization.

Guards the 2026-09-18 defect where canonical interactive eligibility could run
with opdata.is_loaded()==False and therefore use legacy fallback economics.
"""

from copy import deepcopy

import pytest


@pytest.fixture
def restore_operational_state():
    from farmsync.ingest import operational as opdata

    old_data = deepcopy(opdata._DATA)
    old_price = deepcopy(opdata._PRICE_MULT)
    old_abs = deepcopy(opdata._ABS_MULT)

    yield

    opdata._DATA.clear()
    opdata._DATA.update(old_data)
    opdata._PRICE_MULT.clear()
    opdata._PRICE_MULT.update(old_price)
    opdata._ABS_MULT.clear()
    opdata._ABS_MULT.update(old_abs)


def test_interactive_recommendation_auto_loads_processed_operational_data(
    restore_operational_state,
):
    from app import app
    from farmsync.ingest import operational as opdata

    # Reproduce the dangerous initial condition explicitly.
    opdata._DATA["loaded"] = False

    client = app.test_client()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]

    assert opdata.is_loaded() is False

    result = client.post(
        f"/api/farmsync/working-plan/{rid}/recommend",
        json={"farmer_id": "F0001", "plot_id": "F0001-P03"},
    ).get_json()

    # Regression contract: recommendation itself initializes the scientific
    # operational parameter layer.
    assert opdata.is_loaded() is True

    # Scientific sentinel for the frozen current processed dataset.
    assert result["available"] is True
    assert result["found"] is True
    assert result["current_crop"] == "onion"
    assert result["recommended_crop"] == "soybean"
    assert result["expected_cash"] == pytest.approx(19996.0)
    assert result["n_more"] == 0


def test_auto_loaded_and_explicitly_loaded_recommendations_are_identical(
    restore_operational_state,
):
    from app import app
    from farmsync.ingest import operational as opdata

    client = app.test_client()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]

    opdata._DATA["loaded"] = False
    automatic = client.post(
        f"/api/farmsync/working-plan/{rid}/recommend",
        json={"farmer_id": "F0001", "plot_id": "F0001-P03"},
    ).get_json()

    opdata._DATA["loaded"] = False
    opdata.load("data/farmsync/processed")

    explicit = client.post(
        f"/api/farmsync/working-plan/{rid}/recommend",
        json={"farmer_id": "F0001", "plot_id": "F0001-P03"},
    ).get_json()

    assert automatic["recommended_crop"] == explicit["recommended_crop"]
    assert automatic["expected_cash"] == pytest.approx(explicit["expected_cash"])
    assert automatic["n_more"] == explicit["n_more"]


def test_missing_processed_data_fails_loudly_instead_of_using_legacy_fallback(
    tmp_path,
    monkeypatch,
    restore_operational_state,
):
    import farmsync.exploratory_run as er
    from farmsync.ingest import operational as opdata

    opdata._DATA["loaded"] = False
    monkeypatch.setattr(er, "_PROCESSED_DIR", str(tmp_path))

    with pytest.raises(
        RuntimeError,
        match="FarmSync processed operational data unavailable",
    ):
        er._ensure_operational_data()
