"""
Ingestion tests against the REAL raw source artifacts (spec item 17).
These require the raw files under data/farmsync/raw_sources/ (preserved copies).
"""

import os
import glob
import pytest
import pandas as pd

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "farmsync", "raw_sources")
pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(RAW, "des_apy")),
    reason="raw sources not present")

from farmsync.ingest.pipeline import ingest_des_yield, ingest_coc, ingest_agmarknet
from farmsync.ingest import operational as opdata


def _des():
    return ingest_des_yield(os.path.join(RAW, "des_apy", "horizontal_crop_vertical_year_report.xls"))


def test_des_yield_uses_production_over_area_not_mean_of_district_yields():
    y = _des()
    # method column records the aggregation rule
    assert (y["method"] == "SUM(prod)/SUM(area)").all()
    # Punjab wheat ~4700 kg/ha (state total), a known high value
    pw = y[(y["region_id"] == "R1") & (y["crop"] == "wheat") & (y["year"] == "2022-23")]
    assert not pw.empty and 4000 <= pw.iloc[0]["yield_kg_ha"] <= 5500


def test_des_two_years_preserved():
    y = _des()
    years = set(y["year"].unique())
    assert "2021-22" in years and "2022-23" in years


def test_des_cotton_lint_converted_to_kapas():
    y = _des()
    cot = y[y["crop"] == "cotton"]
    if not cot.empty:
        assert (cot["unit_note"].str.contains("kapas")).all()


def test_coc_a2fl_and_c2_separate_and_per_ha():
    c = ingest_coc(os.path.join(RAW, "cost_of_cultivation", "cost-of-cultivation.csv"))
    row = c[(c["region_id"] == "R1") & (c["crop"] == "wheat")]
    assert not row.empty
    a2fl = row.iloc[0]["cost_a2fl_per_ha"]; c2 = row.iloc[0]["cost_c2_per_ha"]
    assert a2fl != c2 and c2 > a2fl                 # C2 (comprehensive) > A2+FL
    assert 20000 < a2fl < 200000                    # plausible ₹/ha


def test_coc_labour_person_days_from_man_hours():
    c = ingest_coc(os.path.join(RAW, "cost_of_cultivation", "cost-of-cultivation.csv"))
    row = c[c["labour_person_days_ha"].notna()].iloc[0]
    assert row["labour_person_days_ha"] == round(row["labour_man_hours_ha"]/8.0, 1)


def test_agmarknet_parses_and_converts_units_and_maps_five_states():
    paths = sorted(glob.glob(os.path.join(RAW, "agmarknet", "All_Type_of_Report*.csv")))
    prices, arrivals, absorp = ingest_agmarknet(paths)
    assert set(prices["region_id"].unique()) <= {"R1", "R2", "R3", "R4", "R5"}
    # rice price in a sane Rs/kg band (Rs/quintal ÷100)
    rice = prices[prices["crop"] == "rice"]
    assert (rice["price_rs_per_kg"].between(15, 45)).all()
    # absorption proxy labelled not demand
    assert "not" in absorp.iloc[0]["note"].lower() and "demand" in absorp.iloc[0]["note"].lower()


def test_agmarknet_cotton_is_kapas_not_lint():
    paths = sorted(glob.glob(os.path.join(RAW, "agmarknet", "All_Type_of_Report*.csv")))
    prices, *_ = ingest_agmarknet(paths)
    cot = prices[prices["crop"] == "cotton"]
    assert (cot["agmarknet_commodity"] == "Cotton").all()   # fibre-group Cotton = kapas, not Lint


def test_sparse_price_and_missing_cost_excluded_from_gate():
    from farmsync.ingest.run_ingest import run
    from farmsync.planning import admitted_gate_report, is_admitted
    run(RAW, os.path.join(RAW, "..", "processed"))
    opdata.load(os.path.join(RAW, "..", "processed"))
    try:
        g = admitted_gate_report()
        assert g["gate_valid"] is True
        assert "tomato" in g["fully_excluded_crops"]       # no CoC cost
        # sparse Punjab paddy excluded
        ok, reason = is_admitted("rice", "R1", "kharif")
        assert not ok and "SPARSE" in reason
        # onion & potato now admitted (real yield+price+cost)
        assert "onion" in g["admitted_crops"] and "potato" in g["admitted_crops"]
    finally:
        opdata._DATA["loaded"] = False                      # reset for other tests
