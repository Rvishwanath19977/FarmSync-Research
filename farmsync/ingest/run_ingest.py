"""
Run ingestion end-to-end and write processed FarmSync parameter tables +
a provenance/source manifest. Raw sources are read-only; processed files are
written separately (spec item 15).

Representative rules (documented):
  * DES yield: keep both 2021-22 and 2022-23; PRIMARY = 2022-23 (latest), alternate
    2021-22 retained. National DES/NHB yield is the labelled fallback only where a
    state value is unavailable.
  * Cost: CoC 2021-22 (only recent year with both A2+FL and C2). PRIMARY for return
    = C2; budget/cash constraint = A2+FL; both retained for sensitivity. One basis
    per crop; never mixed silently.
  * Price: AGMARKNET median of monthly modal 2023-2025; sparse cells (coverage<50%)
    flagged and excluded from final admission.
  * Labour: CoC total human labour (man-hours/ha ÷8 = person-days/ha).
"""

from __future__ import annotations

import glob
import hashlib
import json
import os

import pandas as pd

from .pipeline import (
    ingest_des_yield, ingest_coc, ingest_agmarknet, PARSER_VERSION, FIVE_STATES,
)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()[:16]


def run(raw_dir: str, processed_dir: str) -> dict:
    os.makedirs(processed_dir, exist_ok=True)
    des_path = os.path.join(raw_dir, "des_apy", "horizontal_crop_vertical_year_report.xls")
    coc_path = os.path.join(raw_dir, "cost_of_cultivation", "cost-of-cultivation.csv")
    agm_paths = sorted(glob.glob(os.path.join(raw_dir, "agmarknet", "All_Type_of_Report*.csv")))

    yld = ingest_des_yield(des_path)
    cost = ingest_coc(coc_path)
    price, arrivals, absorp = ingest_agmarknet(agm_paths)

    yld.to_csv(os.path.join(processed_dir, "yield_state.csv"), index=False)
    cost.to_csv(os.path.join(processed_dir, "cost_state.csv"), index=False)
    price.to_csv(os.path.join(processed_dir, "market_price_state.csv"), index=False)
    arrivals.to_csv(os.path.join(processed_dir, "arrivals_state.csv"), index=False)
    absorp.to_csv(os.path.join(processed_dir, "absorption_proxy.csv"), index=False)

    manifest = {
        "parser_version": PARSER_VERSION,
        "five_states": FIVE_STATES,
        "sources": [
            {"name": "DES Area-Production-Yield", "org": "Directorate of Economics & Statistics, GoI",
             "url": "https://data.desagri.gov.in/website/crops-apy-report-web",
             "file": "horizontal_crop_vertical_year_report.xls", "period": "2021-22, 2022-23",
             "orig_units": "Area ha, Production tonnes, Yield tonne/ha",
             "transformation": "state yield = SUM(prod)/SUM(area) x1000 -> kg/ha; cotton lint->kapas /0.35",
             "sha16": _sha(des_path)},
            {"name": "Cost of Cultivation", "org": "DES, GoI (primary); India Data Portal (distribution)",
             "url": "https://desagri.gov.in/document-report-category/cost-of-cultivation-production-estimates/",
             "distribution_url": "https://indiadataportal.com/p/cost-of-cultivation/r/moafw-cost_of_cultivation-st-yr-dvq",
             "file": "cost-of-cultivation.csv", "period": "2021-22",
             "orig_units": "cul_cost_* Rs/ha; human labour Man_Hours/ha",
             "transformation": "A2+FL & C2 kept separate; labour man-hrs/ha ÷8 -> person-days/ha",
             "sha16": _sha(coc_path)},
            {"name": "AGMARKNET price & arrivals", "org": "DMI, Ministry of Agriculture, GoI",
             "url": "https://agmarknet.gov.in/", "files": [os.path.basename(p) for p in agm_paths],
             "period": "Jan-2023 to Dec-2025 (monthly)",
             "orig_units": "Modal Rs/Quintal; Arrival Metric Tonnes",
             "transformation": "median monthly modal, >3xIQR dropped, Rs/q->Rs/kg; arrivals->absorption proxy (NOT demand)",
             "sha16_list": [_sha(p) for p in agm_paths]},
        ],
        "counts": {"yield_rows": len(yld), "cost_rows": len(cost),
                   "price_rows": len(price), "crops_priced": int(price["crop"].nunique())},
    }
    with open(os.path.join(processed_dir, "source_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return {"yield": yld, "cost": cost, "price": price,
            "arrivals": arrivals, "absorption": absorp, "manifest": manifest}


if __name__ == "__main__":
    import sys
    run(sys.argv[1], sys.argv[2])
