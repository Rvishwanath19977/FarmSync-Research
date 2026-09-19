"""
Ingestion-pathway tests. Uses a SYNTHETIC fixture (clearly not real data) only to
prove the pipeline: when AGMARKNET price + DES-CoC cost are ingested, vegetables
pass the same validity gate and B1 uses the operational market price.
"""

import os
import tempfile
import csv

import farmsync.planning as planning
from farmsync.planning import is_admitted, projected_return, operational_price, load_operational_market
from farmsync.market_ingest import ingest_agmarknet, ingest_des_coc


def _reset_ingest():
    planning._INGESTED["prices"] = {}
    planning._INGESTED["costs"] = {}
    planning._INGESTED["active"] = False


def test_agmarknet_aggregation_protocol():
    # synthetic monthly modal prices for tomato in Maharashtra (R2), one outlier
    rows = [{"crop_name": "tomato", "state": "Maharashtra", "year": 2025,
             "month": m, "modal_price_rs_per_quintal": 1500} for m in range(1, 12)]
    rows.append({"crop_name": "tomato", "state": "Maharashtra", "year": 2025,
                 "month": 12, "modal_price_rs_per_quintal": 99999})   # outlier
    out = ingest_agmarknet(rows)
    key = ("tomato", "R2")
    assert key in out
    assert out[key]["price_per_kg"] == 15.0        # 1500 Rs/q -> 15 Rs/kg, outlier dropped


def test_des_coc_ingest_maps_state_to_region():
    rows = [{"crop_name": "tomato", "state": "Maharashtra", "cost_basis": "C2",
             "cost_per_ha_rs": 120000, "year": 2025}]
    out = ingest_des_coc(rows)
    assert out[("tomato", "R2")]["cost_per_ha"] == 120000


def test_ingested_data_admits_vegetable_and_b1_uses_market_price():
    _reset_ingest()
    # before ingest: tomato not admitted (no cost)
    ok0, _ = is_admitted("tomato", "R2", "kharif")
    assert not ok0
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "agmarknet_prices.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["crop_name", "state", "year", "month", "modal_price_rs_per_quintal"])
            for m in range(1, 13):
                w.writerow(["tomato", "Maharashtra", 2025, m, 1500])
        with open(os.path.join(d, "des_coc.csv"), "w", newline="") as f:
            w = csv.writer(f); w.writerow(["crop_name", "state", "cost_basis", "cost_per_ha_rs", "year"])
            w.writerow(["tomato", "Maharashtra", "C2", 120000, 2025])
        load_operational_market(d)
    ok1, reason = is_admitted("tomato", "R2", "kharif")
    assert ok1, reason                              # now admitted
    r = projected_return("tomato", "R2", "kharif", 1.0)
    assert r["price_basis"].startswith("MARKET_AGMARKNET")
    assert r["cost_basis"].startswith("DES_CoC")
    _reset_ingest()


def test_msp_used_as_reference_when_no_ingest():
    _reset_ingest()
    price, basis = operational_price("rice", "R1", "kharif")
    assert basis == "MSP_FLOOR_REFERENCE"           # MSP is the labelled reference, not market
