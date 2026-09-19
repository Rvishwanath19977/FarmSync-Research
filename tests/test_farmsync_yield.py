"""
Phase 5e tests — national season-split yields + derived cost/ha + unit guards.
"""

from farmsync.crop_yield import (
    CROP_YIELD, derive_cost_per_ha, crop_yield_provenance, yield_summary, REGION_STATE,
)
from farmsync.provenance import ProvenanceType, Confidence


def test_all_fourteen_crops_have_yield():
    have = yield_summary()["yield_sourced"]
    assert len(have) == 14                       # onion/tomato added (NHB); potato (DES)
    assert yield_summary()["yield_requires_sourcing"] == []


def test_yield_values_spot_check():
    assert CROP_YIELD["rice"].yield_for("kharif") == 2825
    assert CROP_YIELD["wheat"].yield_for("rabi") == 3595
    assert CROP_YIELD["maize"].yield_for("rabi") == 5306
    assert CROP_YIELD["soybean"].yield_for("kharif") == 1063


def test_cotton_kapas_basis_now_consistent():
    from farmsync.crop_yield import CROP_YIELD
    # cotton yield converted lint->kapas (1257) so units match seed-cotton MSP/cost
    assert CROP_YIELD["cotton"].unit_consistent_with_price is True
    assert CROP_YIELD["cotton"].yield_for("kharif") == 1257
    d = derive_cost_per_ha("cotton", "kharif")
    assert d["cost_per_ha"] is not None          # 5140 INR/q x 12.57 q/ha
    assert 55000 <= d["cost_per_ha"] <= 75000


def test_cost_per_ha_derived_for_grain_crops():
    d = derive_cost_per_ha("rice", "kharif")
    assert d["cost_per_ha"] is not None
    # 1579 INR/q x 28.25 q/ha ~ 44,607
    assert 40000 <= d["cost_per_ha"] <= 50000
    assert d["basis"] == "A2+FL"


def test_wheat_cost_uses_c2_basis():
    d = derive_cost_per_ha("wheat", "rabi")
    assert d["basis"] == "C2"


def test_yield_provenance_scope_labelled():
    recs = crop_yield_provenance()
    ricerec = next(r for r in recs if r.crop == "rice" and r.parameter == "crop.expected_yield")
    assert ricerec.provenance_type == ProvenanceType.OBSERVED
    assert "ALL_INDIA" in (ricerec.assumption or "")


def test_region_state_mapping_present():
    assert REGION_STATE["R1"] == "Punjab"
    assert REGION_STATE["R2"] == "Maharashtra"
    assert len(REGION_STATE) == 5


def test_state_override_wins_for_r1_punjab():
    from farmsync.crop_yield import resolve_yield
    r1 = resolve_yield("rice", "kharif", "R1")          # Punjab override
    assert r1["value"] == 4193
    assert r1["scope"] == "STATE:Punjab"
    w1 = resolve_yield("wheat", "rabi", "R1")
    assert w1["value"] == 5045 and w1["scope"] == "STATE:Punjab"


def test_national_fallback_for_unmapped_state_crop():
    from farmsync.crop_yield import resolve_yield
    # R2 (Maharashtra) has no rice override yet -> national figure, labelled scope
    r2 = resolve_yield("rice", "kharif", "R2")
    assert r2["value"] == 2825
    assert r2["scope"] == "ALL_INDIA"
