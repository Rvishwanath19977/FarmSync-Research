"""
Phase 1 tests (spec section 34 — the subset applicable to the data layer).
Covers: synthetic reproducibility, farmer land aggregation, plot area limits,
water/resource sanity, and provenance completeness / integrity guarding.
"""

import hashlib
import json

import pytest

from farmsync.generate import generate_dataset
from farmsync.schemas import Season
from farmsync.quality import quality_report, farmers_csv, plots_csv
from farmsync.provenance import (
    ProvenanceRecord, ProvenanceType, Confidence,
)


def _digest(farmers, plots):
    blob = json.dumps(
        [f.to_row() for f in farmers] + [p.to_row() for p in plots],
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()


def test_reproducible_same_seed_identical():
    a = generate_dataset(master_seed=123, n_farmers=120, n_collectives=6)
    b = generate_dataset(master_seed=123, n_farmers=120, n_collectives=6)
    assert _digest(a[0], a[1]) == _digest(b[0], b[1])


def test_different_seed_differs():
    a = generate_dataset(master_seed=1, n_farmers=120)
    b = generate_dataset(master_seed=2, n_farmers=120)
    assert _digest(a[0], a[1]) != _digest(b[0], b[1])


def test_farmer_land_aggregation_matches_plots():
    farmers, plots, *_ = generate_dataset(master_seed=7, n_farmers=200)
    total_by_farmer = {}
    for p in plots:
        total_by_farmer[p.farmer_id] = round(total_by_farmer.get(p.farmer_id, 0.0) + p.area_ha, 3)
    for f in farmers:
        assert abs(total_by_farmer[f.farmer_id] - f.total_area_ha) <= 0.011, f.farmer_id


def test_plot_area_and_water_are_valid():
    _, plots, *_ = generate_dataset(master_seed=42, n_farmers=200)
    for p in plots:
        assert p.area_ha > 0
        assert p.available_water_m3 >= 0
        # rainfed plots must never carry more water than a canal plot of same area band
        if p.irrigation_access.value == "rainfed":
            assert p.available_water_m3 <= p.area_ha * 1500 * 1.3 * 1.16


def test_every_farmer_has_at_least_one_plot():
    farmers, plots, *_ = generate_dataset(master_seed=99, n_farmers=300)
    have = {p.farmer_id for p in plots}
    assert have == {f.farmer_id for f in farmers}


def test_holding_distribution_is_non_uniform():
    farmers, *_ = generate_dataset(master_seed=5, n_farmers=500)
    from collections import Counter
    dist = Counter(f.holding_category.value for f in farmers)
    # marginal must dominate (skew, not uniform)
    assert dist["marginal"] > dist.get("large", 0)
    assert dist["marginal"] > dist.get("medium", 0)


def test_quality_report_all_ok():
    farmers, plots, crops, regions, manifest, prov, collectives = generate_dataset(
        master_seed=11, n_farmers=500, n_collectives=10)
    rep = quality_report(farmers, plots, manifest)
    assert rep["integrity"]["all_ok"], rep["integrity"]
    assert rep["counts"]["farmers"] == 500
    assert rep["counts"]["collectives"] == 10


def test_exports_have_headers_and_rows():
    farmers, plots, *_ = generate_dataset(master_seed=3, n_farmers=50)
    fcsv, pcsv = farmers_csv(farmers), plots_csv(plots)
    assert fcsv.splitlines()[0].startswith("farmer_id")
    assert "synthetic" in fcsv.splitlines()[0]
    assert pcsv.splitlines()[0].startswith("plot_id")
    assert len(pcsv.splitlines()) > len(farmers)  # at least one plot each


def test_provenance_flags_open_sourcing_obligations():
    *_, prov, _coll = generate_dataset(master_seed=1)
    check = prov.completeness_check()
    # agronomic parameters must be flagged, not silently invented
    assert check["open_sourcing_obligations"] >= 10
    assert "crop.expected_yield" in check["obligations"]
    assert "crop.market_absorption_proxy" in check["obligations"]
    assert check["complete"] is False


def test_provenance_rejects_unsourced_observed_claim():
    with pytest.raises(ValueError):
        ProvenanceRecord(
            parameter="crop.price",
            provenance_type=ProvenanceType.OBSERVED,   # claims real origin
            value="18.5",                                # ...but no source
        )


def test_provenance_grounded_requires_assumption():
    with pytest.raises(ValueError):
        ProvenanceRecord(
            parameter="farmer.total_area_ha",
            provenance_type=ProvenanceType.SYNTHETIC_GROUNDED,
            value="generated",  # missing the 'assumption' anchor
        )
