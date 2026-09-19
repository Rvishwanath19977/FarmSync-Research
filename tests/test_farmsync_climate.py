"""
Phase 5c tests — regional ET0 sourcing + crop water requirement computation.
"""

import pytest

from farmsync.climate import (
    compute_crop_water_requirements, REGION_ET0, region_et0_provenance,
)
from farmsync.provenance import ProvenanceType, Confidence


def test_sourced_regions_compute_cwr():
    r = compute_crop_water_requirements("R2", "kharif")
    assert r["_status"] == "OK"
    # rice CWR should land in a plausible agronomic band (~900-1300 mm)
    assert 900 <= r["rice"] <= 1300, r["rice"]


def test_wheat_rabi_cwr_plausible():
    r = compute_crop_water_requirements("R2", "rabi")
    assert r["_status"] == "OK"
    assert 350 <= r["wheat"] <= 600, r["wheat"]   # wheat CWR ~400-550 mm


def test_unknown_region_refuses_cwr():
    # a region with no ET0 entry must still refuse (never fabricate)
    r = compute_crop_water_requirements("R9", "kharif")
    assert r["_status"] == "ET0_NOT_SOURCED"


def test_all_five_regions_now_compute_cwr():
    for rid in ("R1", "R2", "R3", "R4", "R5"):
        r = compute_crop_water_requirements(rid, "kharif")
        assert r["_status"] == "OK"


def test_only_season_appropriate_crops_returned():
    kharif = compute_crop_water_requirements("R1", "kharif")
    rabi = compute_crop_water_requirements("R1", "rabi")
    assert "rice" in kharif and "rice" not in rabi        # rice is kharif
    assert "wheat" in rabi and "wheat" not in kharif       # wheat is rabi


def test_sourced_et0_provenance_carries_source():
    for rec in region_et0_provenance():
        if rec.parameter == "climate.ET0_seasonal" and rec.provenance_type == ProvenanceType.OBSERVED:
            assert rec.source and rec.source_url


def test_net_irrigation_requirement_water_balance():
    from farmsync.climate import net_irrigation_requirement_mm
    # West Bengal (R3) monsoon rainfall exceeds rice CWR -> NIR 0 (rainfed feasible)
    assert net_irrigation_requirement_mm("rice", "R3", "kharif") == 0.0
    # arid Rajasthan (R4) needs substantial irrigation for rice
    assert net_irrigation_requirement_mm("rice", "R4", "kharif") > 500
    # never fabricates for an unknown region
    assert net_irrigation_requirement_mm("rice", "R9", "kharif") is None


def test_characterisation_regions_are_grounded_not_unsourced():
    from farmsync.provenance import ProvenanceType
    recs = {r.region: r for r in region_et0_provenance()
            if r.parameter == "climate.ET0_seasonal" and r.region}
    # R3/R4/R5 are interpolated from a published characterisation -> SYNTHETIC_GROUNDED
    for rid in ("R3", "R4", "R5"):
        assert recs[rid].provenance_type == ProvenanceType.SYNTHETIC_GROUNDED
        assert recs[rid].assumption            # must state the interpolation assumption
    # R1/R2 are station-based -> OBSERVED
    for rid in ("R1", "R2"):
        assert recs[rid].provenance_type == ProvenanceType.OBSERVED
