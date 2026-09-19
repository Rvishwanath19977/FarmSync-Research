"""
Data-quality report + exporters (spec sections 4, 32).

Pure stdlib so it runs anywhere. Produces:
  * a quality report (invariants + distributions) used both in tests and later
    in the Dataset Overview UI;
  * CSV/JSON exports so numeric values are recoverable without screenshots.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter


def quality_report(farmers, plots, manifest) -> dict:
    plots_by_farmer = Counter(p.farmer_id for p in plots)

    # invariant: every farmer's plot areas sum to their total_area_ha (3 dp)
    area_mismatches = []
    farmer_area = {f.farmer_id: f.total_area_ha for f in farmers}
    plot_area_sum = {}
    for p in plots:
        plot_area_sum[p.farmer_id] = round(plot_area_sum.get(p.farmer_id, 0.0) + p.area_ha, 3)
    for fid, total in farmer_area.items():
        if abs(plot_area_sum.get(fid, 0.0) - total) > 0.011:
            area_mismatches.append((fid, total, plot_area_sum.get(fid, 0.0)))

    # invariants: no impossible resources
    negative_water = [p.plot_id for p in plots if p.available_water_m3 < 0]
    zero_area = [p.plot_id for p in plots if p.area_ha <= 0]
    orphan_plots = [p.plot_id for p in plots if p.farmer_id not in farmer_area]
    farmers_without_plots = [f.farmer_id for f in farmers if plots_by_farmer[f.farmer_id] == 0]

    return {
        "dataset_version": manifest.dataset_version,
        "master_seed": manifest.master_seed,
        "counts": {
            "farmers": len(farmers), "plots": len(plots),
            "collectives": manifest.n_collectives, "crops": manifest.n_crops,
            "regions": manifest.n_regions,
        },
        "plots_per_farmer": {
            "min": min(plots_by_farmer.values()) if plots_by_farmer else 0,
            "max": max(plots_by_farmer.values()) if plots_by_farmer else 0,
            "mean": round(len(plots) / len(farmers), 2) if farmers else 0,
        },
        "holding_distribution": dict(Counter(f.holding_category.value for f in farmers)),
        "irrigation_distribution": dict(Counter(p.irrigation_access.value for p in plots)),
        "region_distribution": dict(Counter(f.region_id for f in farmers)),
        "integrity": {
            "area_mismatches": area_mismatches,
            "negative_water_plots": negative_water,
            "zero_area_plots": zero_area,
            "orphan_plots": orphan_plots,
            "farmers_without_plots": farmers_without_plots,
            "all_ok": not any([area_mismatches, negative_water, zero_area,
                               orphan_plots, farmers_without_plots]),
        },
        "label": manifest.label,
    }


def _rows_to_csv(rows) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def farmers_csv(farmers) -> str:
    return _rows_to_csv([f.to_row() for f in farmers])


def plots_csv(plots) -> str:
    return _rows_to_csv([p.to_row() for p in plots])


def provenance_csv(prov) -> str:
    return _rows_to_csv(prov.rows())


def manifest_json(manifest) -> str:
    from dataclasses import asdict
    return json.dumps(asdict(manifest), indent=2)
