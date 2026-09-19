"""
Phase 5 tests. Verifies the water block is genuinely grounded, the CWR guard
refuses to fabricate, and every economic/sensitivity parameter is flagged.
"""

import pytest

from farmsync.crop_water import CROP_WATER, crop_water_provenance
from farmsync.sourcing_report import sourcing_report, build_phase5_registry
from farmsync.provenance import ProvenanceType, Confidence

CROPS = list(CROP_WATER.keys())


def test_all_fourteen_crops_have_water_block():
    assert len(CROP_WATER) == 14
    for cw in CROP_WATER.values():
        assert 0.1 <= cw.kc_ini <= 1.3
        assert 0.5 <= cw.kc_mid <= 1.3
        assert cw.duration_days > 0
        assert sum(cw.stage_days) == cw.duration_days


def test_observed_crops_carry_a_source():
    for rec in crop_water_provenance():
        if rec.provenance_type == ProvenanceType.OBSERVED:
            assert rec.source, rec.parameter          # OBSERVED must cite
            assert rec.source_url


def test_mapped_crops_are_grounded_with_assumption():
    # pigeon_pea and mustard are mapped, not in FAO-56 directly
    recs = {(r.crop): r for r in crop_water_provenance() if r.crop}
    for crop in ("pigeon_pea", "mustard", "chickpea"):
        assert recs[crop].provenance_type == ProvenanceType.SYNTHETIC_GROUNDED
        assert recs[crop].assumption          # must state the mapping assumption


def test_cwr_refuses_without_et0():
    rice = CROP_WATER["rice"]
    with pytest.raises(ValueError):
        rice.crop_water_requirement_mm(None)
    with pytest.raises(ValueError):
        rice.crop_water_requirement_mm({"init": 5})   # incomplete


def test_cwr_computes_with_et0():
    rice = CROP_WATER["rice"]
    et0 = {"init": 4.0, "dev": 4.5, "mid": 5.0, "late": 4.0}
    val = rice.crop_water_requirement_mm(et0)
    assert val > 0


def test_economic_parameters_all_flagged():
    rep = sourcing_report(CROPS)
    # 8 economic/sensitivity params x 14 crops = 112 open obligations
    assert rep["summary"]["open_sourcing_obligations"] >= 112
    assert rep["gate"]["optimiser_may_use_economics"] is False
    assert rep["gate"]["optimiser_may_use_water_block"] is True


def test_price_plan_does_not_call_arrivals_demand():
    reg = build_phase5_registry(CROPS)
    proxy = [r for r in reg.rows() if r["parameter"] == "crop.market_absorption_proxy"][0]
    assert "not demand" in proxy["notes"].lower() or "not label" in proxy["notes"].lower()
