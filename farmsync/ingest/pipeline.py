"""
Ingestion pipeline for the official source artifacts (spec items 5-12).

Reads immutable raw sources, filters to the five FarmSync states, applies the
documented rules, and writes processed FarmSync parameter tables. Raw files are
never modified.

Key rules enforced here:
  * DES state yield = SUM(production)/SUM(area), never a mean of district yields.
  * CoC A2+FL and C2 kept SEPARATE, ₹/ha, one basis per crop; labour from
    man-hours/ha (÷8 -> person-days), no double counting.
  * AGMARKNET monthly weighted modal -> state×crop operational price by median of
    monthly modal (Rs/q -> Rs/kg), outliers >3×IQR dropped, coverage reported,
    missing months preserved (not carried forward).
  * Cotton uses seed-cotton (kapas) throughout; DES lint yield converted via ginning
    ratio; AGMARKNET 'Cotton' (fibre group) is kapas.
  * Arrivals -> market_absorption_proxy (throughput, NOT demand).
"""

from __future__ import annotations

import os
import warnings
import pandas as pd

from .commodity_map import (
    AGMARKNET_MAP, DES_MAP, COC_MAP, COTTON_GINNING_RATIO, CROP_PRIMARY_SEASON,
)

warnings.filterwarnings("ignore")

FIVE_STATES = ["Punjab", "Maharashtra", "West Bengal", "Rajasthan", "Karnataka"]
STATE_TO_REGION = {"Punjab": "R1", "Maharashtra": "R2", "West Bengal": "R3",
                   "Rajasthan": "R4", "Karnataka": "R5"}
PARSER_VERSION = "ingest-v1.0"


# --------------------------------------------------------------------------- #
# DES Area-Production-Yield  ->  state yield (kg/ha)
# --------------------------------------------------------------------------- #
def ingest_des_yield(xls_path: str) -> pd.DataFrame:
    df = pd.read_html(xls_path)[0]
    # flatten state prefix "25. Punjab" -> "Punjab"
    state_col = ("State", "State", "State")
    year_col = ("Year", "Year", "Year")
    df["_state"] = df[state_col].astype(str).str.replace(r"^\s*\d+\.\s*", "", regex=True)
    df["_year"] = df[year_col].astype(str).str.replace(r"\s*-\s*", "-", regex=True).str.replace(
        r"(\d{4})-(\d{4})", lambda m: f"{m.group(1)}-{m.group(2)[2:]}", regex=True)
    d5 = df[df["_state"].isin(FIVE_STATES)].copy()
    states = d5["_state"].values
    years = d5["_year"].values

    rows = []
    for des_crop, fs_crop in DES_MAP.items():
        for season in ("Kharif", "Rabi", "Whole Year"):
            acol = (des_crop, season, "Area (Hectare)")
            pcol = (des_crop, season, "Production (Tonnes)")
            if acol not in d5.columns or pcol not in d5.columns:
                continue
            tmp = pd.DataFrame({
                "_state": states, "_year": years,
                "_area": pd.to_numeric(d5[acol], errors="coerce").values,
                "_prod": pd.to_numeric(d5[pcol], errors="coerce").values,
            })
            grouped = tmp.groupby(["_state", "_year"], as_index=False).agg(
                area=("_area", "sum"), prod=("_prod", "sum"))
            for _, r in grouped.iterrows():
                if r["area"] and r["area"] > 0:
                    yld_t_ha = r["prod"] / r["area"]        # Tonne/ha
                    yld_kg_ha = yld_t_ha * 1000.0
                    if fs_crop == "cotton":                 # DES cotton is LINT -> kapas
                        yld_kg_ha = yld_kg_ha / COTTON_GINNING_RATIO
                    rows.append({
                        "region_id": STATE_TO_REGION[r["_state"]], "state": r["_state"],
                        "crop": fs_crop, "season_reported": season, "year": r["_year"],
                        "area_ha": round(r["area"], 1), "production_t": round(r["prod"], 1),
                        "yield_kg_ha": round(yld_kg_ha, 1),
                        "unit_note": "lint->kapas /0.35" if fs_crop == "cotton" else "",
                        "source": "DES APY (data.desagri.gov.in)", "method": "SUM(prod)/SUM(area)",
                    })
    out = pd.DataFrame(rows)
    # collapse Kharif/Rabi/Whole Year to the crop's primary season where available
    keep = []
    for (rid, crop, year), grp in out.groupby(["region_id", "crop", "year"]):
        want = CROP_PRIMARY_SEASON[crop].capitalize()
        pick = grp[grp["season_reported"] == want]
        if pick.empty:
            pick = grp[grp["season_reported"] == "Whole Year"]
        if pick.empty:
            pick = grp
        keep.append(pick.iloc[0])
    return pd.DataFrame(keep).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Cost of Cultivation  ->  A2+FL, C2 (₹/ha) + labour (person-days/ha)
# --------------------------------------------------------------------------- #
def ingest_coc(csv_path: str, year: str = "2021-22") -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    d = df[(df["state_name"].isin(FIVE_STATES)) & (df["year"] == year)].copy()
    rows = []
    for coc_crop, fs_crop in COC_MAP.items():
        sub = d[d["crop_name"] == coc_crop]
        for _, r in sub.iterrows():
            man_hrs = pd.to_numeric(r.get("mat_lab_input_hmn_lab"), errors="coerce")
            rows.append({
                "region_id": STATE_TO_REGION[r["state_name"]], "state": r["state_name"],
                "crop": fs_crop, "year": year,
                "cost_a2fl_per_ha": pd.to_numeric(r.get("cul_cost_a2fl"), errors="coerce"),
                "cost_c2_per_ha": pd.to_numeric(r.get("cul_cost_c2"), errors="coerce"),
                "labour_man_hours_ha": man_hrs,
                "labour_person_days_ha": round(man_hrs/8.0, 1) if pd.notna(man_hrs) else None,
                "coc_yield_q_ha": pd.to_numeric(r.get("derived_yield"), errors="coerce"),
                "source": "DES Cost of Cultivation (via India Data Portal)",
                "labour_note": "man-hours/ha ÷8 = person-days/ha (total human labour, no double count)",
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# AGMARKNET  ->  operational price (₹/kg) + arrivals + absorption proxy
# --------------------------------------------------------------------------- #
def _read_agmarknet(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, skiprows=1)
    df.columns = [c.split(" 0")[0].strip() for c in df.columns]   # trim date-range suffix
    return df


def ingest_agmarknet(paths: list) -> tuple:
    frames = []
    for p in paths:
        df = _read_agmarknet(p)
        df = df[df["State/UT"].isin(FIVE_STATES)].copy()
        df["crop"] = df["Commodity"].map(AGMARKNET_MAP)
        df = df[df["crop"].notna()]
        df["modal_rs_q"] = pd.to_numeric(df["Modal Price"], errors="coerce")
        df["arrival_mt"] = pd.to_numeric(df["Arrival Quantity"], errors="coerce")
        frames.append(df[["State/UT", "crop", "Commodity", "Month", "modal_rs_q", "arrival_mt"]])
    allm = pd.concat(frames, ignore_index=True)

    def drop_iqr(s):
        s = s[s > 0]
        if len(s) < 4:
            return s
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        return s[(s >= q1 - 3*iqr) & (s <= q3 + 3*iqr)]

    price_rows, arr_rows = [], []
    for (state, crop), grp in allm.groupby(["State/UT", "crop"]):
        cleaned = drop_iqr(grp["modal_rs_q"].dropna())
        if cleaned.empty:
            continue
        median_q = cleaned.median()
        months_present = grp["Month"].nunique()
        coverage = round(100 * months_present / 36.0, 1)     # 36 months Jan2023-Dec2025
        price_rows.append({
            "region_id": STATE_TO_REGION[state], "state": state, "crop": crop,
            "agmarknet_commodity": grp["Commodity"].mode().iloc[0],
            "price_rs_per_quintal": round(median_q, 1),
            "price_rs_per_kg": round(median_q/100.0, 2),
            "n_months": int(months_present), "coverage_pct": coverage,
            "sparse_flag": coverage < 50.0,
            "method": "median of monthly weighted-modal, >3xIQR dropped, nonpositive removed",
            "source": "AGMARKNET portal (Jan2023-Dec2025 monthly)",
        })
        arr_rows.append({"region_id": STATE_TO_REGION[state], "state": state, "crop": crop,
                         "total_arrival_mt": round(grp["arrival_mt"].sum(), 1)})
    prices = pd.DataFrame(price_rows)
    arrivals = pd.DataFrame(arr_rows)
    # market absorption proxy: national throughput per crop (sum arrivals across 5 states),
    # normalised to [0,1] by max. NOT demand.
    nat = arrivals.groupby("crop")["total_arrival_mt"].sum().reset_index()
    mx = nat["total_arrival_mt"].max() or 1.0
    nat["absorption_proxy"] = (nat["total_arrival_mt"]/mx).round(3)
    nat["note"] = "market-throughput/absorption proxy from mandi arrivals; NOT observed demand"
    return prices, arrivals, nat
