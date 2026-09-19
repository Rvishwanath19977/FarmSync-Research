"""
Phase 5d tests — MSP price anchors + cost basis integrity.
"""

from farmsync.crop_economics import (
    CROP_PRICE, crop_economics_provenance, price_summary,
)
from farmsync.provenance import ProvenanceType, Confidence


def test_eleven_crops_have_msp_anchor():
    have = price_summary()["msp_anchored"]
    assert len(have) == 11
    # spot-check a few authoritative values (Rs/kg)
    assert CROP_PRICE["rice"].msp_floor_per_kg == 23.69
    assert CROP_PRICE["wheat"].msp_floor_per_kg == 25.85
    assert CROP_PRICE["pigeon_pea"].msp_floor_per_kg == 80.00


def test_vegetables_have_no_msp_and_are_flagged():
    need = price_summary()["price_requires_sourcing"]
    assert set(need) == {"potato", "onion", "tomato"}


def test_msp_recorded_as_floor_not_market_price():
    recs = crop_economics_provenance()
    msp_recs = [r for r in recs if r.parameter == "crop.msp_floor_per_kg"]
    assert msp_recs
    for r in msp_recs:
        assert r.provenance_type == ProvenanceType.OBSERVED
        assert r.source and r.source_url
        # must state it is a policy floor, not the market price / demand
        assert "floor" in r.notes.lower() and "not the market price" in r.notes.lower()


def test_cost_basis_not_silently_mixed():
    # kharif costs are A2+FL, rabi are C2 — basis must be explicit
    assert CROP_PRICE["rice"].cost_basis == "A2+FL"
    assert CROP_PRICE["wheat"].cost_basis == "C2"


def test_cultivation_cost_per_ha_remains_open():
    recs = crop_economics_provenance()
    cost_ha = [r for r in recs if r.parameter == "crop.cultivation_cost_per_ha"]
    assert cost_ha and cost_ha[0].confidence == Confidence.REQUIRES_SOURCING
