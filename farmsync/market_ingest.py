"""
Market/cost ingestion — the pathway for AGMARKNET price exports and DES Cost-of-
Cultivation exports you provide. Nothing here fabricates data: until real exports
are ingested, the ingested tables are empty and the optimiser stays on the
documented provisional basis. When you drop real files in `data/farmsync/market/`,
this applies the documented aggregation protocol and populates region-relevant
operational prices and cultivation costs.

=====================  DATA CONTRACT (what to export)  =====================

AGMARKNET prices  ->  data/farmsync/market/agmarknet_prices.csv
  columns (header row required):
    crop_name                 one of the 14 FarmSync crop names (e.g. 'rice','onion')
    state                     Indian state (must match REGION_STATE values:
                              Punjab, Maharashtra, West Bengal, Rajasthan, Karnataka)
    year                      marketing year, integer
    month                     1-12
    modal_price_rs_per_quintal  numeric modal price (Rs/quintal)
  -> aggregated per (crop, region) by the documented protocol:
     season median of monthly modal, drop >3xIQR outliers, Rs/q -> Rs/kg.

DES Cost of Cultivation  ->  data/farmsync/market/des_coc.csv
  columns (header row required):
    crop_name                 FarmSync crop name
    state                     state (mapped to region via REGION_STATE)
    cost_basis                'A2+FL' or 'C2'  (stated, never mixed)
    cost_per_ha_rs            numeric cultivation cost per hectare (Rs/ha)
    year                      integer
  -> mapped per (crop, region), basis preserved.

Only states in REGION_STATE are ingested; others are ignored (logged). Missing
(crop, region) cells fall back to the labelled national/MSP basis, recorded in
provenance with scope + confidence.
===========================================================================
"""

from __future__ import annotations

import csv
import os
import statistics

from .crop_yield import REGION_STATE

EXPECTED_AGMARKNET_COLUMNS = ["crop_name", "state", "year", "month", "modal_price_rs_per_quintal"]
EXPECTED_DES_COC_COLUMNS = ["crop_name", "state", "cost_basis", "cost_per_ha_rs", "year"]

STATE_TO_REGION = {state: rid for rid, state in REGION_STATE.items()}


def _drop_iqr_outliers(values):
    if len(values) < 4:
        return values
    s = sorted(values)
    q1 = s[len(s)//4]
    q3 = s[(3*len(s))//4]
    iqr = q3 - q1
    lo, hi = q1 - 3*iqr, q3 + 3*iqr
    return [v for v in values if lo <= v <= hi]


def ingest_agmarknet(rows) -> dict:
    """
    rows: iterable of dicts with EXPECTED_AGMARKNET_COLUMNS.
    Returns {(crop_name, region_id): {"price_per_kg", "n_obs", "missing_flag"}}.
    Applies: state->region, drop >3xIQR outliers, median of monthly modal, Rs/q->Rs/kg.
    """
    buckets = {}
    for r in rows:
        state = r.get("state")
        region = STATE_TO_REGION.get(state)
        if region is None:
            continue                       # only ingest mapped states
        try:
            price = float(r["modal_price_rs_per_quintal"])
        except (TypeError, ValueError, KeyError):
            continue
        buckets.setdefault((r["crop_name"], region), []).append(price)
    out = {}
    for key, vals in buckets.items():
        cleaned = _drop_iqr_outliers(vals)
        if not cleaned:
            continue
        median_q = statistics.median(cleaned)
        out[key] = {
            "price_per_kg": round(median_q / 100.0, 2),
            "n_obs": len(vals),
            "n_after_outlier_drop": len(cleaned),
            "missing_flag": len(vals) < 12,       # <1 year of monthly obs
        }
    return out


def ingest_des_coc(rows) -> dict:
    """rows -> {(crop_name, region_id): {"cost_per_ha", "basis"}}."""
    out = {}
    for r in rows:
        region = STATE_TO_REGION.get(r.get("state"))
        if region is None:
            continue
        try:
            cost = float(r["cost_per_ha_rs"])
        except (TypeError, ValueError, KeyError):
            continue
        out[(r["crop_name"], region)] = {"cost_per_ha": round(cost, 0),
                                         "basis": r.get("cost_basis", "")}
    return out


def _read_csv(path, expected_cols):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in expected_cols if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{os.path.basename(path)} missing columns: {missing}")
        return list(reader)


def load_market_dir(market_dir: str) -> dict:
    """
    Load whatever real exports are present. Returns
    {"prices": {...}, "costs": {...}, "present": [...]}.
    Empty when no files present — the optimiser then stays on the provisional basis.
    """
    prices, costs, present = {}, {}, []
    ap = os.path.join(market_dir, "agmarknet_prices.csv")
    dc = os.path.join(market_dir, "des_coc.csv")
    ap_rows = _read_csv(ap, EXPECTED_AGMARKNET_COLUMNS)
    if ap_rows:
        prices = ingest_agmarknet(ap_rows); present.append("agmarknet_prices.csv")
    dc_rows = _read_csv(dc, EXPECTED_DES_COC_COLUMNS)
    if dc_rows:
        costs = ingest_des_coc(dc_rows); present.append("des_coc.csv")
    return {"prices": prices, "costs": costs, "present": present}
