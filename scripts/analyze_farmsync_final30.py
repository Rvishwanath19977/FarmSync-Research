#!/usr/bin/env python3
"""Reproduce FarmSync Final30 post-run analysis from sealed raw cells.

Important:
- sealed raw results are READ-ONLY;
- sealed reference analysis is READ-ONLY;
- reproduction output may be written only under:
  results/farmsync/reproduction/
- non-Optimal outcomes are never zero-imputed;
- performance summaries are Optimal-only unless explicitly reliability-only.

This script is being reconstructed from the frozen analysis specification.
The first gate validates all frozen inputs before scientific recomputation.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RAW_DIR = ROOT / "results/farmsync/final30_v1"
RAW_FREEZE_DIR = ROOT / "results/farmsync/final30_freeze_v1"

REF_DIR = ROOT / "results/farmsync/final30_analysis_v1"
REF_FREEZE_DIR = (
    ROOT / "results/farmsync/final30_analysis_freeze_v1"
)

REPRO_ROOT = ROOT / "results/farmsync/reproduction"
DEFAULT_OUTPUT = REPRO_ROOT / "final30_analysis_v1"


EXPECTED = {
    "matrix_sha256":
        "b339a43ab581a0d481da230b84918363"
        "bc82f771b993f575c50ea903cdecc0f0",

    "dataset_attestation_sha256":
        "fd42123f24a6823484dc0fa0f5d34192"
        "c8c23ea9a03e45d4674e42515bb3514e",

    "raw_cell_set_sha256":
        "71f43479f4048f7cf208b819bacb223e"
        "2fcb8fd9ff428e8bd36015d30c4de605",

    "run_manifest_sha256":
        "c285f65def80ab131f5f8c9b084c6f7"
        "fa573ae1553cd3c2357459b050bb09809",

    "solver_amendment_sha256":
        "1d42d59e3c1ba404d13f5c557560e943"
        "c222030b1a21ec65094534140cf865b8",

    "analysis_set_sha256":
        "2d5641c4a2e93321707a7f0400d9ad1"
        "e61e966bdc31147bb6c591b74f35b1df2",

    "analysis_manifest_sha256":
        "eaec4dfaac62e4f744833045aaf820263"
        "1debd959f0da4eab6d6f10291cf88a4",
}


EXPECTED_FAMILY_COUNTS = {
    "PRIMARY": 30,
    "EPSILON_SENSITIVITY": 120,
    "LAMBDA_STABILITY": 180,
    "ALPHA_CONCENTRATION": 150,
    "ACTION_ROBUSTNESS": 90,
    "UNCERTAINTY": 180,
    "SCALABILITY": 150,
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def assert_safe_output(output: Path) -> None:
    output = output.resolve()
    repro = REPRO_ROOT.resolve()

    protected = [
        RAW_DIR.resolve(),
        RAW_FREEZE_DIR.resolve(),
        REF_DIR.resolve(),
        REF_FREEZE_DIR.resolve(),
    ]

    for p in protected:
        if output == p or _is_relative_to(output, p):
            raise RuntimeError(
                "Refusing to write inside sealed/protected path: "
                f"{output}"
            )

    if not _is_relative_to(output, repro):
        raise RuntimeError(
            "Reproduction output must stay under "
            f"{repro}"
        )


def verify_raw_freeze() -> dict:
    freeze_path = RAW_FREEZE_DIR / "FREEZE.json"
    cell_index_path = RAW_FREEZE_DIR / "CELL_SHA256.csv"
    run_manifest_path = RAW_DIR / "RUN_MANIFEST.json"

    if not freeze_path.is_file():
        raise RuntimeError(
            f"Missing raw freeze manifest: {freeze_path}"
        )

    if not cell_index_path.is_file():
        raise RuntimeError(
            f"Missing raw cell hash index: {cell_index_path}"
        )

    if not run_manifest_path.is_file():
        raise RuntimeError(
            f"Missing raw RUN_MANIFEST: {run_manifest_path}"
        )

    freeze = read_json(freeze_path)

    if freeze.get("schema") != "farmsync-final30-freeze-v1":
        raise RuntimeError("Unexpected raw freeze schema")

    if freeze.get("status") != "SEALED":
        raise RuntimeError("Raw Final30 freeze is not SEALED")

    if freeze.get("raw_cell_count") != 900:
        raise RuntimeError(
            "Raw freeze does not attest exactly 900 cells"
        )

    for key in (
        "matrix_sha256",
        "dataset_attestation_sha256",
        "cell_set_sha256",
        "run_manifest_sha256",
        "solver_amendment_sha256",
    ):
        expected_key = (
            "raw_cell_set_sha256"
            if key == "cell_set_sha256"
            else key
        )

        if freeze.get(key) != EXPECTED[expected_key]:
            raise RuntimeError(
                f"Raw freeze identity mismatch: {key}"
            )

    got_manifest = sha256_file(run_manifest_path)

    if got_manifest != EXPECTED["run_manifest_sha256"]:
        raise RuntimeError(
            "RUN_MANIFEST.json SHA-256 mismatch"
        )

    rows = list(
        csv.DictReader(
            cell_index_path.open(
                "r",
                encoding="utf-8",
                newline="",
            )
        )
    )

    if len(rows) != 900:
        raise RuntimeError(
            f"CELL_SHA256.csv has {len(rows)} rows, expected 900"
        )

    family_counts = Counter()

    for row in rows:
        rel = row["relative_path"]
        path = RAW_DIR / rel

        if not path.is_file():
            raise RuntimeError(
                f"Missing frozen raw cell: {rel}"
            )

        got = sha256_file(path)

        if got != row["sha256"]:
            raise RuntimeError(
                f"Raw cell SHA-256 mismatch: {rel}"
            )

        cell = read_json(path)

        if cell.get("schema") != "farmsync-final30-cell-v1":
            raise RuntimeError(
                f"Unexpected cell schema: {rel}"
            )

        if cell.get("completion") != "COMPLETE":
            raise RuntimeError(
                f"Incomplete frozen cell: {rel}"
            )

        if (
            cell.get("matrix_sha256")
            != EXPECTED["matrix_sha256"]
        ):
            raise RuntimeError(
                f"Matrix identity mismatch in {rel}"
            )

        if (
            cell.get("dataset_attestation_sha256")
            != EXPECTED["dataset_attestation_sha256"]
        ):
            raise RuntimeError(
                f"Dataset identity mismatch in {rel}"
            )

        family_counts[cell["family"]] += 1

    if dict(family_counts) != EXPECTED_FAMILY_COUNTS:
        raise RuntimeError(
            "Raw family counts differ from frozen design:\n"
            f"got={dict(family_counts)}"
        )

    return {
        "cell_count": len(rows),
        "family_counts": dict(family_counts),
        "run_manifest_sha256": got_manifest,
        "source_commit": freeze.get("source_commit"),
        "clean_cells":
            freeze.get("integrity", {}).get("clean_cells"),
        "non_clean_cells":
            freeze.get("integrity", {}).get("non_clean_cells"),
    }


def verify_reference_analysis() -> dict:
    freeze_path = REF_FREEZE_DIR / "FREEZE.json"
    file_index_path = REF_FREEZE_DIR / "FILE_SHA256.csv"
    manifest_path = REF_DIR / "MANIFEST.json"

    if not freeze_path.is_file():
        raise RuntimeError(
            f"Missing analysis freeze manifest: {freeze_path}"
        )

    if not file_index_path.is_file():
        raise RuntimeError(
            f"Missing analysis hash index: {file_index_path}"
        )

    if not manifest_path.is_file():
        raise RuntimeError(
            f"Missing analysis MANIFEST: {manifest_path}"
        )

    freeze = read_json(freeze_path)
    manifest = read_json(manifest_path)

    if (
        freeze.get("schema")
        != "farmsync-final30-analysis-freeze-v1"
    ):
        raise RuntimeError(
            "Unexpected analysis freeze schema"
        )

    if freeze.get("status") != "SEALED":
        raise RuntimeError(
            "Reference analysis is not SEALED"
        )

    if freeze.get("analysis_file_count") != 83:
        raise RuntimeError(
            "Reference analysis does not contain 83 files"
        )

    if (
        freeze.get("analysis_set_sha256")
        != EXPECTED["analysis_set_sha256"]
    ):
        raise RuntimeError(
            "Reference analysis set identity mismatch"
        )

    got_manifest = sha256_file(manifest_path)

    if (
        got_manifest
        != EXPECTED["analysis_manifest_sha256"]
    ):
        raise RuntimeError(
            "Reference MANIFEST.json SHA-256 mismatch"
        )

    rows = list(
        csv.DictReader(
            file_index_path.open(
                "r",
                encoding="utf-8",
                newline="",
            )
        )
    )

    if len(rows) != 83:
        raise RuntimeError(
            f"FILE_SHA256.csv has {len(rows)} rows, expected 83"
        )

    for row in rows:
        rel = row["relative_path"]
        path = REF_DIR / rel

        if not path.is_file():
            raise RuntimeError(
                f"Missing sealed analysis file: {rel}"
            )

        got = sha256_file(path)

        if got != row["sha256"]:
            raise RuntimeError(
                f"Reference analysis SHA mismatch: {rel}"
            )

    rules = manifest.get("analysis_rules", {})

    if rules.get("bootstrap_replicates") != 10000:
        raise RuntimeError(
            "Unexpected bootstrap replicate count"
        )

    if rules.get("bootstrap_seed") != 20260812:
        raise RuntimeError(
            "Unexpected bootstrap seed"
        )

    if not rules.get(
        "optimal_only_outcome_summaries"
    ):
        raise RuntimeError(
            "Optimal-only analysis rule missing"
        )

    if rules.get("zero_imputation_nonoptimal") is not False:
        raise RuntimeError(
            "Zero-imputation rule violated"
        )

    return {
        "analysis_file_count": len(rows),
        "analysis_set_sha256":
            freeze.get("analysis_set_sha256"),
        "bootstrap_replicates":
            rules.get("bootstrap_replicates"),
        "bootstrap_seed":
            rules.get("bootstrap_seed"),
        "analysis_runtime":
            manifest.get("analysis_runtime"),
    }



# ============================================================
# REPRODUCTION STAGE 1
# Deterministic raw-cell -> seed-level statistics extraction.
# No solver, no LLM, no bootstrap RNG.
# ============================================================

def _family_cells(family: str):
    out = []

    for path in sorted(RAW_DIR.rglob("*.json")):
        if path.name == "RUN_MANIFEST.json":
            continue

        cell = read_json(path)

        if cell.get("family") == family:
            out.append((path, cell))

    return out


def _tiers(proposed):
    if not isinstance(proposed, dict):
        return {}

    tiers = proposed.get("tiers")

    return tiers if isinstance(tiers, dict) else {}


def _tier_cash(proposed, state):
    tier = _tiers(proposed).get(state)

    if not isinstance(tier, dict):
        return None

    return tier.get("cash")


def _ratio(a, b):
    if a is None or b in (None, 0):
        return None

    return a / b


def _blank_if_none(value):
    return "" if value is None else value


def _write_csv(path, fieldnames, rows):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            lineterminator="\n",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    k: _blank_if_none(row.get(k))
                    for k in fieldnames
                }
            )


def _compare_csv_exact(generated, reference):
    with generated.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        got = list(csv.reader(f))

    with reference.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        expected = list(csv.reader(f))

    if got == expected:
        return True, None

    if len(got) != len(expected):
        return (
            False,
            "row count differs: "
            f"generated={len(got)} reference={len(expected)}",
        )

    for row_index, (a, b) in enumerate(
        zip(got, expected),
        start=1,
    ):
        if len(a) != len(b):
            return (
                False,
                f"column count differs at row {row_index}",
            )

        for col_index, (x, y) in enumerate(
            zip(a, b),
            start=1,
        ):
            if x != y:
                return (
                    False,
                    "first mismatch at "
                    f"row={row_index}, col={col_index}: "
                    f"generated={x!r}, reference={y!r}",
                )

    return False, "unknown CSV difference"


def _proposed_common(cell):
    payload = cell.get("payload") or {}
    proposed = payload.get("proposed") or {}

    optimal = bool(proposed.get("optimal"))
    planned = (
        _tier_cash(proposed, "PLANNED")
        if optimal
        else None
    )
    initial = (
        _tier_cash(proposed, "INITIAL_REALIZED")
        if optimal
        else None
    )
    revised = (
        _tier_cash(proposed, "RECOMMENDED_REVISED")
        if optimal
        else None
    )
    final = (
        _tier_cash(proposed, "FINAL_REALIZED")
        if optimal
        else None
    )

    return {
        "payload": payload,
        "proposed": proposed,
        "optimal": optimal,
        "planned": planned,
        "initial": initial,
        "revised": revised,
        "final": final,
    }


def _primary_seed_rows():
    rows = []

    for _, cell in _family_cells("PRIMARY"):
        payload = cell["payload"]
        baselines = payload["baselines"]
        x = _proposed_common(cell)
        p = x["proposed"]

        rows.append(
            {
                "seed": cell["seed"],

                "b1_status":
                    baselines["B1"].get("status"),
                "b1_cash_planned":
                    baselines["B1"].get("cash"),

                "b2_status":
                    baselines["B2"].get("status"),
                "b2_cash_planned":
                    baselines["B2"].get("cash"),

                "b3_status":
                    baselines["B3"].get("status"),
                "b3_cash_planned":
                    baselines["B3"].get("cash"),

                "proposed_status":
                    p.get("status"),
                "proposed_optimal":
                    x["optimal"],
                "proposed_failed_stage":
                    p.get("failed_stage"),
                "proposed_runtime_s":
                    p.get("runtime_s"),

                "proposed_planned_cash":
                    x["planned"],
                "proposed_initial_realized_cash":
                    x["initial"],
                "proposed_recommended_revised_cash":
                    x["revised"],
                "proposed_final_realized_cash":
                    x["final"],

                "final_vs_planned_ratio":
                    _ratio(
                        x["final"],
                        x["planned"],
                    ),

                "final_vs_recommended_ratio":
                    _ratio(
                        x["final"],
                        x["revised"],
                    ),

                "planned_to_final_cash_loss":
                    (
                        x["planned"] - x["final"]
                        if (
                            x["planned"] is not None
                            and x["final"] is not None
                        )
                        else None
                    ),

                "consent_coverage_final":
                    (
                        p.get("consent_coverage_final")
                        if x["optimal"]
                        else None
                    ),

                "renewed_prompts":
                    (
                        p.get("renewed_prompts")
                        if x["optimal"]
                        else None
                    ),

                "withdrawn_farmers":
                    (
                        p.get("withdrawn_farmers")
                        if x["optimal"]
                        else None
                    ),
            }
        )

    return rows


def _epsilon_seed_rows():
    rows = []

    for _, cell in _family_cells(
        "EPSILON_SENSITIVITY"
    ):
        payload = cell["payload"]
        b3 = payload.get("b3") or {}

        rows.append(
            {
                "seed": cell["seed"],
                "epsilon":
                    cell["parameters"]["epsilon"],
                "status":
                    b3.get("status"),
                "optimal":
                    bool(b3.get("optimal")),
                "runtime_s":
                    b3.get("runtime_s"),
                "cash":
                    b3.get("cash"),
                "area":
                    b3.get("area"),
                "cash_per_allocated_ha":
                    b3.get("cash_per_allocated_ha"),
                "min_normalized_return":
                    b3.get("min_normalized_return"),
            }
        )

    return rows


def _lambda_seed_rows():
    rows = []

    for _, cell in _family_cells(
        "LAMBDA_STABILITY"
    ):
        x = _proposed_common(cell)
        p = x["proposed"]

        disruption = (
            x["payload"].get("disruption") or {}
            if x["optimal"]
            else {}
        )

        rows.append(
            {
                "seed": cell["seed"],
                "lambda":
                    cell["parameters"]["lambda"],
                "status":
                    p.get("status"),
                "optimal":
                    x["optimal"],
                "failed_stage":
                    p.get("failed_stage"),
                "runtime_s":
                    p.get("runtime_s"),

                "planned_cash":
                    x["planned"],
                "initial_realized_cash":
                    x["initial"],
                "recommended_revised_cash":
                    x["revised"],
                "final_realized_cash":
                    x["final"],

                "final_vs_planned_ratio":
                    _ratio(
                        x["final"],
                        x["planned"],
                    ),

                "changed_soft_area":
                    disruption.get(
                        "changed_soft_area"
                    ),

                "soft_lock_area":
                    disruption.get(
                        "soft_lock_area"
                    ),

                "disruption_rate":
                    disruption.get(
                        "disruption_rate"
                    ),
            }
        )

    return rows


def _alpha_seed_rows():
    rows = []

    for _, cell in _family_cells(
        "ALPHA_CONCENTRATION"
    ):
        x = _proposed_common(cell)
        p = x["proposed"]

        concentration = (
            x["payload"].get("concentration") or {}
            if x["optimal"]
            else {}
        )

        rows.append(
            {
                "seed": cell["seed"],
                "alpha":
                    cell["parameters"]["alpha"],
                "status":
                    p.get("status"),
                "optimal":
                    x["optimal"],
                "failed_stage":
                    p.get("failed_stage"),
                "runtime_s":
                    p.get("runtime_s"),

                "planned_cash":
                    x["planned"],
                "initial_realized_cash":
                    x["initial"],
                "recommended_revised_cash":
                    x["revised"],
                "final_realized_cash":
                    x["final"],

                "final_vs_planned_ratio":
                    _ratio(
                        x["final"],
                        x["planned"],
                    ),

                "max_LPS":
                    concentration.get("max_LPS"),

                "mean_HHI":
                    concentration.get("mean_HHI"),

                "median_HHI":
                    concentration.get("median_HHI"),

                "n_active_crops":
                    concentration.get(
                        "n_active_crops"
                    ),

                "target_violations":
                    concentration.get(
                        "target_violations"
                    ),
            }
        )

    return rows


def _action_seed_rows():
    rows = []

    for _, cell in _family_cells(
        "ACTION_ROBUSTNESS"
    ):
        x = _proposed_common(cell)
        p = x["proposed"]

        actions = (
            p.get("action_counts") or {}
            if x["optimal"]
            else {}
        )

        rows.append(
            {
                "seed": cell["seed"],
                "profile":
                    cell["parameters"]["profile"],
                "status":
                    p.get("status"),
                "optimal":
                    x["optimal"],
                "failed_stage":
                    p.get("failed_stage"),
                "runtime_s":
                    p.get("runtime_s"),

                "planned_cash":
                    x["planned"],
                "initial_realized_cash":
                    x["initial"],
                "recommended_revised_cash":
                    x["revised"],
                "final_realized_cash":
                    x["final"],

                "final_vs_planned_ratio":
                    _ratio(
                        x["final"],
                        x["planned"],
                    ),

                "consent_coverage_final":
                    (
                        p.get("consent_coverage_final")
                        if x["optimal"]
                        else None
                    ),

                "renewed_prompts":
                    (
                        p.get("renewed_prompts")
                        if x["optimal"]
                        else None
                    ),

                "withdrawn_farmers":
                    (
                        p.get("withdrawn_farmers")
                        if x["optimal"]
                        else None
                    ),

                "accept_count":
                    actions.get("ACCEPT"),

                "reject_count":
                    actions.get("REJECT"),

                "modify_count":
                    actions.get("MODIFY"),

                "no_response_count":
                    actions.get("NO_RESPONSE"),

                "withdraw_count":
                    actions.get("WITHDRAW"),
            }
        )

    return rows


def _uncertainty_seed_rows():
    rows = []

    for _, cell in _family_cells("UNCERTAINTY"):
        u = (
            cell["payload"].get("uncertainty")
            or {}
        )

        baselines = u.get("baselines") or {}
        p = u.get("proposed") or {}
        optimal = bool(p.get("optimal"))

        planned = (
            _tier_cash(p, "PLANNED")
            if optimal
            else None
        )
        initial = (
            _tier_cash(p, "INITIAL_REALIZED")
            if optimal
            else None
        )
        revised = (
            _tier_cash(
                p,
                "RECOMMENDED_REVISED",
            )
            if optimal
            else None
        )
        final = (
            _tier_cash(p, "FINAL_REALIZED")
            if optimal
            else None
        )

        rows.append(
            {
                "seed": cell["seed"],
                "condition":
                    cell["parameters"]["condition"],

                "b1_status":
                    (baselines.get("B1") or {})
                    .get("status"),
                "b1_cash_planned":
                    (baselines.get("B1") or {})
                    .get("cash"),

                "b2_status":
                    (baselines.get("B2") or {})
                    .get("status"),
                "b2_cash_planned":
                    (baselines.get("B2") or {})
                    .get("cash"),

                "b3_status":
                    (baselines.get("B3") or {})
                    .get("status"),
                "b3_cash_planned":
                    (baselines.get("B3") or {})
                    .get("cash"),

                "proposed_status":
                    p.get("status"),
                "proposed_optimal":
                    optimal,
                "proposed_failed_stage":
                    p.get("failed_stage"),

                "proposed_planned_cash":
                    planned,
                "proposed_initial_realized_cash":
                    initial,
                "proposed_recommended_revised_cash":
                    revised,
                "proposed_final_realized_cash":
                    final,

                "final_vs_planned_ratio":
                    _ratio(final, planned),

                "final_vs_recommended_ratio":
                    _ratio(final, revised),

                "consent_coverage_final":
                    (
                        p.get(
                            "consent_coverage_final"
                        )
                        if optimal
                        else None
                    ),

                "reopt_status":
                    p.get("reopt_status"),

                "conc_status":
                    p.get("conc_status"),
            }
        )

    return rows


def _scalability_seed_rows():
    rows = []

    for _, cell in _family_cells("SCALABILITY"):
        methods = (
            cell["payload"].get("methods")
            or {}
        )

        b1 = methods.get("B1") or {}
        b2 = methods.get("B2") or {}
        b3 = methods.get("B3") or {}
        p = methods.get("PROPOSED") or {}

        optimal = bool(p.get("optimal"))

        planned = (
            _tier_cash(p, "PLANNED")
            if optimal
            else None
        )
        initial = (
            _tier_cash(p, "INITIAL_REALIZED")
            if optimal
            else None
        )
        revised = (
            _tier_cash(
                p,
                "RECOMMENDED_REVISED",
            )
            if optimal
            else None
        )
        final = (
            _tier_cash(p, "FINAL_REALIZED")
            if optimal
            else None
        )

        rows.append(
            {
                "seed": cell["seed"],
                "n_farmers":
                    cell["parameters"]["n_farmers"],

                "b1_status": b1.get("status"),
                "b1_optimal":
                    bool(b1.get("optimal")),
                "b1_cash": b1.get("cash"),
                "b1_runtime_s":
                    b1.get("runtime_s"),

                "b2_status": b2.get("status"),
                "b2_optimal":
                    bool(b2.get("optimal")),
                "b2_cash": b2.get("cash"),
                "b2_runtime_s":
                    b2.get("runtime_s"),

                "b3_status": b3.get("status"),
                "b3_optimal":
                    bool(b3.get("optimal")),
                "b3_cash": b3.get("cash"),
                "b3_runtime_s":
                    b3.get("runtime_s"),

                "proposed_status":
                    p.get("status"),
                "proposed_optimal":
                    optimal,
                "proposed_failed_stage":
                    p.get("failed_stage"),
                "proposed_runtime_s":
                    p.get("runtime_s"),

                "proposed_planned_cash":
                    planned,
                "proposed_initial_realized_cash":
                    initial,
                "proposed_recommended_revised_cash":
                    revised,
                "proposed_final_realized_cash":
                    final,
            }
        )

    return rows


SEED_LEVEL_SPECS = {
    "primary_seed_level.csv": (
        [
            "seed",
            "b1_status",
            "b1_cash_planned",
            "b2_status",
            "b2_cash_planned",
            "b3_status",
            "b3_cash_planned",
            "proposed_status",
            "proposed_optimal",
            "proposed_failed_stage",
            "proposed_runtime_s",
            "proposed_planned_cash",
            "proposed_initial_realized_cash",
            "proposed_recommended_revised_cash",
            "proposed_final_realized_cash",
            "final_vs_planned_ratio",
            "final_vs_recommended_ratio",
            "planned_to_final_cash_loss",
            "consent_coverage_final",
            "renewed_prompts",
            "withdrawn_farmers",
        ],
        _primary_seed_rows,
    ),

    "epsilon_seed_level.csv": (
        [
            "seed",
            "epsilon",
            "status",
            "optimal",
            "runtime_s",
            "cash",
            "area",
            "cash_per_allocated_ha",
            "min_normalized_return",
        ],
        _epsilon_seed_rows,
    ),

    "lambda_seed_level.csv": (
        [
            "seed",
            "lambda",
            "status",
            "optimal",
            "failed_stage",
            "runtime_s",
            "planned_cash",
            "initial_realized_cash",
            "recommended_revised_cash",
            "final_realized_cash",
            "final_vs_planned_ratio",
            "changed_soft_area",
            "soft_lock_area",
            "disruption_rate",
        ],
        _lambda_seed_rows,
    ),

    "alpha_seed_level.csv": (
        [
            "seed",
            "alpha",
            "status",
            "optimal",
            "failed_stage",
            "runtime_s",
            "planned_cash",
            "initial_realized_cash",
            "recommended_revised_cash",
            "final_realized_cash",
            "final_vs_planned_ratio",
            "max_LPS",
            "mean_HHI",
            "median_HHI",
            "n_active_crops",
            "target_violations",
        ],
        _alpha_seed_rows,
    ),

    "action_robustness_seed_level.csv": (
        [
            "seed",
            "profile",
            "status",
            "optimal",
            "failed_stage",
            "runtime_s",
            "planned_cash",
            "initial_realized_cash",
            "recommended_revised_cash",
            "final_realized_cash",
            "final_vs_planned_ratio",
            "consent_coverage_final",
            "renewed_prompts",
            "withdrawn_farmers",
            "accept_count",
            "reject_count",
            "modify_count",
            "no_response_count",
            "withdraw_count",
        ],
        _action_seed_rows,
    ),

    "uncertainty_seed_level.csv": (
        [
            "seed",
            "condition",
            "b1_status",
            "b1_cash_planned",
            "b2_status",
            "b2_cash_planned",
            "b3_status",
            "b3_cash_planned",
            "proposed_status",
            "proposed_optimal",
            "proposed_failed_stage",
            "proposed_planned_cash",
            "proposed_initial_realized_cash",
            "proposed_recommended_revised_cash",
            "proposed_final_realized_cash",
            "final_vs_planned_ratio",
            "final_vs_recommended_ratio",
            "consent_coverage_final",
            "reopt_status",
            "conc_status",
        ],
        _uncertainty_seed_rows,
    ),

    "scalability_seed_level.csv": (
        [
            "seed",
            "n_farmers",
            "b1_status",
            "b1_optimal",
            "b1_cash",
            "b1_runtime_s",
            "b2_status",
            "b2_optimal",
            "b2_cash",
            "b2_runtime_s",
            "b3_status",
            "b3_optimal",
            "b3_cash",
            "b3_runtime_s",
            "proposed_status",
            "proposed_optimal",
            "proposed_failed_stage",
            "proposed_runtime_s",
            "proposed_planned_cash",
            "proposed_initial_realized_cash",
            "proposed_recommended_revised_cash",
            "proposed_final_realized_cash",
        ],
        _scalability_seed_rows,
    ),
}


def reproduce_seed_level(output: Path):
    assert_safe_output(output)

    # Re-verify immutable scientific inputs before reading them.
    verify_raw_freeze()
    verify_reference_analysis()

    stats_out = output / "statistics"

    print("FINAL30 SEED-LEVEL REPRODUCTION")
    print("==============================")

    passed = 0

    for filename, (
        fieldnames,
        builder,
    ) in SEED_LEVEL_SPECS.items():

        rows = builder()

        dst = stats_out / filename
        ref = REF_DIR / "statistics" / filename

        _write_csv(
            dst,
            fieldnames,
            rows,
        )

        ok, detail = _compare_csv_exact(
            dst,
            ref,
        )

        print(
            f"{filename:40} "
            f"{'PASS' if ok else 'FAIL'} "
            f"({len(rows)} rows)"
        )

        if not ok:
            print("  ", detail)
        else:
            passed += 1

    print()
    print(
        f"Seed-level CSVs matching frozen reference: "
        f"{passed}/{len(SEED_LEVEL_SPECS)}"
    )

    if passed != len(SEED_LEVEL_SPECS):
        raise SystemExit(
            "SEED-LEVEL REPRODUCTION: FAIL"
        )

    print("SEED-LEVEL REPRODUCTION: PASS")
    print(
        "Solver executions: 0"
    )
    print(
        "LLM executions: 0"
    )



# ============================================================
# REPRODUCTION STAGE 2
# Deterministic seed-level -> aggregate/reliability statistics.
# ============================================================

def _summary(values):
    values = [
        float(x)
        for x in values
        if x is not None
    ]

    if not values:
        raise RuntimeError(
            "Cannot summarize an empty value set"
        )

    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "sd": (
            statistics.stdev(values)
            if len(values) > 1
            else 0.0
        ),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _summary_row(
    prefix,
    metric,
    scope,
    values,
):
    row = dict(prefix)

    row["metric"] = metric
    row["analysis_scope"] = scope

    row.update(
        _summary(values)
    )

    return row


def _write_compare(
    stats_out,
    filename,
    fieldnames,
    rows,
):
    dst = stats_out / filename
    ref = REF_DIR / "statistics" / filename

    _write_csv(
        dst,
        fieldnames,
        rows,
    )

    ok, detail = _compare_csv_exact(
        dst,
        ref,
    )

    print(
        f"{filename:40} "
        f"{'PASS' if ok else 'FAIL'} "
        f"({len(rows)} rows)"
    )

    if not ok:
        print("  ", detail)

    return ok


def _simple_group_statistics(
    rows,
    group_key,
    group_order,
    metric_specs,
    optimal_key="optimal",
):
    out = []

    for group in group_order:
        selected_group = [
            row
            for row in rows
            if row[group_key] == group
        ]

        for (
            source_column,
            output_metric,
            scope,
        ) in metric_specs:

            selected = selected_group

            if scope == "optimal_only":
                selected = [
                    row
                    for row in selected_group
                    if bool(row[optimal_key])
                ]

            values = [
                row[source_column]
                for row in selected
                if row.get(source_column) is not None
            ]

            out.append(
                _summary_row(
                    {group_key: group},
                    output_metric,
                    scope,
                    values,
                )
            )

    return out


def _primary_statistics_rows():
    rows = _primary_seed_rows()
    out = []

    specs = [
        (
            "B1",
            "PLANNED",
            "cash",
            "all_30_primary_seeds",
            "b1_cash_planned",
            False,
        ),
        (
            "B2",
            "PLANNED",
            "cash",
            "all_30_primary_seeds",
            "b2_cash_planned",
            False,
        ),
        (
            "B3",
            "PLANNED",
            "cash",
            "all_30_primary_seeds",
            "b3_cash_planned",
            False,
        ),
        (
            "PROPOSED",
            "PLANNED",
            "cash",
            "optimal_proposed_only",
            "proposed_planned_cash",
            True,
        ),
        (
            "PROPOSED",
            "INITIAL_REALIZED",
            "cash",
            "optimal_proposed_only",
            "proposed_initial_realized_cash",
            True,
        ),
        (
            "PROPOSED",
            "RECOMMENDED_REVISED",
            "cash",
            "optimal_proposed_only",
            "proposed_recommended_revised_cash",
            True,
        ),
        (
            "PROPOSED",
            "FINAL_REALIZED",
            "cash",
            "optimal_proposed_only",
            "proposed_final_realized_cash",
            True,
        ),
        (
            "PROPOSED",
            "FINAL_vs_PLANNED",
            "ratio",
            "optimal_proposed_only",
            "final_vs_planned_ratio",
            True,
        ),
        (
            "PROPOSED",
            "FINAL_vs_RECOMMENDED",
            "ratio",
            "optimal_proposed_only",
            "final_vs_recommended_ratio",
            True,
        ),
        (
            "PROPOSED",
            "PLANNED_MINUS_FINAL",
            "cash_loss",
            "optimal_proposed_only",
            "planned_to_final_cash_loss",
            True,
        ),
    ]

    for (
        method,
        state,
        metric,
        scope,
        column,
        proposed_only,
    ) in specs:

        selected = rows

        if proposed_only:
            selected = [
                row
                for row in rows
                if row["proposed_optimal"]
            ]

        values = [
            row[column]
            for row in selected
            if row.get(column) is not None
        ]

        out.append(
            _summary_row(
                {
                    "method": method,
                    "state": state,
                },
                metric,
                scope,
                values,
            )
        )

    return out


def _epsilon_statistics_rows():
    return _simple_group_statistics(
        _epsilon_seed_rows(),
        "epsilon",
        [0.8, 0.9, 0.95, 1.0],
        [
            (
                "cash",
                "cash",
                "optimal_only",
            ),
            (
                "area",
                "area",
                "optimal_only",
            ),
            (
                "cash_per_allocated_ha",
                "cash_per_allocated_ha",
                "optimal_only",
            ),
            (
                "min_normalized_return",
                "min_normalized_return",
                "optimal_only",
            ),
            (
                "runtime_s",
                "runtime_s",
                "all_runs",
            ),
        ],
    )


def _lambda_statistics_rows():
    metrics = [
        "planned_cash",
        "initial_realized_cash",
        "recommended_revised_cash",
        "final_realized_cash",
        "final_vs_planned_ratio",
        "changed_soft_area",
        "soft_lock_area",
        "disruption_rate",
    ]

    return _simple_group_statistics(
        _lambda_seed_rows(),
        "lambda",
        [0.0, 0.05, 0.1, 0.25, 0.5, 1.0],
        [
            (x, x, "optimal_only")
            for x in metrics
        ],
    )


def _alpha_statistics_rows():
    metrics = [
        "planned_cash",
        "initial_realized_cash",
        "recommended_revised_cash",
        "final_realized_cash",
        "final_vs_planned_ratio",
        "max_LPS",
        "mean_HHI",
        "median_HHI",
        "n_active_crops",
        "target_violations",
    ]

    # Preserve the ordering in the sealed publication analysis.
    return _simple_group_statistics(
        _alpha_seed_rows(),
        "alpha",
        [1.0, 0.6, 0.5, 0.4, 0.33],
        [
            (x, x, "optimal_only")
            for x in metrics
        ],
    )


def _action_statistics_rows():
    metrics = [
        "planned_cash",
        "initial_realized_cash",
        "recommended_revised_cash",
        "final_realized_cash",
        "final_vs_planned_ratio",
        "consent_coverage_final",
        "renewed_prompts",
        "withdrawn_farmers",
        "accept_count",
        "reject_count",
        "modify_count",
        "no_response_count",
        "withdraw_count",
    ]

    return _simple_group_statistics(
        _action_seed_rows(),
        "profile",
        ["PRIMARY", "S1", "S2"],
        [
            (x, x, "optimal_only")
            for x in metrics
        ],
    )


def _uncertainty_statistics_rows():
    rows = _uncertainty_seed_rows()
    out = []

    conditions = [
        "U0",
        "UW",
        "UM",
        "UR",
        "UP",
        "UJ",
    ]

    specs = [
        (
            "B1",
            "PLANNED",
            "cash",
            "all_30",
            "b1_cash_planned",
            False,
        ),
        (
            "B2",
            "PLANNED",
            "cash",
            "all_30",
            "b2_cash_planned",
            False,
        ),
        (
            "B3",
            "PLANNED",
            "cash",
            "all_30",
            "b3_cash_planned",
            False,
        ),
        (
            "PROPOSED",
            "PLANNED",
            "cash",
            "optimal_only",
            "proposed_planned_cash",
            True,
        ),
        (
            "PROPOSED",
            "INITIAL_REALIZED",
            "cash",
            "optimal_only",
            "proposed_initial_realized_cash",
            True,
        ),
        (
            "PROPOSED",
            "RECOMMENDED_REVISED",
            "cash",
            "optimal_only",
            "proposed_recommended_revised_cash",
            True,
        ),
        (
            "PROPOSED",
            "FINAL_REALIZED",
            "cash",
            "optimal_only",
            "proposed_final_realized_cash",
            True,
        ),
        (
            "PROPOSED",
            "FINAL_vs_PLANNED",
            "ratio",
            "optimal_only",
            "final_vs_planned_ratio",
            True,
        ),
        (
            "PROPOSED",
            "FINAL_vs_RECOMMENDED",
            "ratio",
            "optimal_only",
            "final_vs_recommended_ratio",
            True,
        ),
    ]

    for condition in conditions:
        group = [
            row
            for row in rows
            if row["condition"] == condition
        ]

        for (
            method,
            state,
            metric,
            scope,
            column,
            proposed_only,
        ) in specs:

            selected = group

            if proposed_only:
                selected = [
                    row
                    for row in group
                    if row["proposed_optimal"]
                ]

            values = [
                row[column]
                for row in selected
                if row.get(column) is not None
            ]

            out.append(
                _summary_row(
                    {
                        "condition": condition,
                        "method": method,
                        "state": state,
                    },
                    metric,
                    scope,
                    values,
                )
            )

    return out


def _scalability_statistics_rows():
    rows = _scalability_seed_rows()
    out = []

    specs = [
        (
            "B1",
            "PLANNED",
            "cash",
            "all_runs",
            "b1_cash",
            False,
        ),
        (
            "B1",
            "PLANNED",
            "runtime_s",
            "all_runs",
            "b1_runtime_s",
            False,
        ),
        (
            "B2",
            "PLANNED",
            "cash",
            "all_runs",
            "b2_cash",
            False,
        ),
        (
            "B2",
            "PLANNED",
            "runtime_s",
            "all_runs",
            "b2_runtime_s",
            False,
        ),
        (
            "B3",
            "PLANNED",
            "cash",
            "all_runs",
            "b3_cash",
            False,
        ),
        (
            "B3",
            "PLANNED",
            "runtime_s",
            "all_runs",
            "b3_runtime_s",
            False,
        ),
        (
            "PROPOSED",
            "PLANNED",
            "cash",
            "optimal_only",
            "proposed_planned_cash",
            True,
        ),
        (
            "PROPOSED",
            "INITIAL_REALIZED",
            "cash",
            "optimal_only",
            "proposed_initial_realized_cash",
            True,
        ),
        (
            "PROPOSED",
            "RECOMMENDED_REVISED",
            "cash",
            "optimal_only",
            "proposed_recommended_revised_cash",
            True,
        ),
        (
            "PROPOSED",
            "FINAL_REALIZED",
            "cash",
            "optimal_only",
            "proposed_final_realized_cash",
            True,
        ),
        (
            "PROPOSED",
            "PIPELINE",
            "runtime_s",
            "all_runs",
            "proposed_runtime_s",
            False,
        ),
    ]

    for n_farmers in [
        25,
        50,
        100,
        250,
        500,
    ]:
        group = [
            row
            for row in rows
            if row["n_farmers"] == n_farmers
        ]

        for (
            method,
            state,
            metric,
            scope,
            column,
            proposed_only,
        ) in specs:

            selected = group

            if proposed_only:
                selected = [
                    row
                    for row in group
                    if row["proposed_optimal"]
                ]

            values = [
                row[column]
                for row in selected
                if row.get(column) is not None
            ]

            out.append(
                _summary_row(
                    {
                        "n_farmers": n_farmers,
                        "method": method,
                        "state": state,
                    },
                    metric,
                    scope,
                    values,
                )
            )

    return out


def _failure_json(
    rows,
    optimal_key,
    status_key,
    stage_key=None,
    status_only=False,
):
    failures = Counter()

    for row in rows:
        if bool(row[optimal_key]):
            continue

        status = (
            row.get(status_key)
            or "None"
        )

        if status_only:
            key = status
        else:
            stage = (
                row.get(stage_key)
                or "None"
            )

            key = f"{status}|{stage}"

        failures[key] += 1

    return json.dumps(
        dict(
            sorted(
                failures.items()
            )
        ),
        sort_keys=True,
    )


def _reliability_rows(
    rows,
    group_key,
    group_order,
    optimal_key,
    status_key,
    stage_key,
    output_optimal_key,
    output_nonoptimal_key,
    output_rate_key,
    output_failure_key,
    status_only=False,
):
    out = []

    for group in group_order:
        selected = [
            row
            for row in rows
            if row[group_key] == group
        ]

        total = len(selected)

        optimal = sum(
            bool(row[optimal_key])
            for row in selected
        )

        nonoptimal = total - optimal

        out.append(
            {
                group_key: group,
                "total_runs": total,
                output_optimal_key: optimal,
                output_nonoptimal_key: nonoptimal,
                output_rate_key: round(
                    100.0 * optimal / total,
                    4,
                ),
                output_failure_key:
                    _failure_json(
                        selected,
                        optimal_key,
                        status_key,
                        stage_key,
                        status_only,
                    ),
            }
        )

    return out


def _action_reliability_rows():
    return _reliability_rows(
        _action_seed_rows(),
        "profile",
        ["PRIMARY", "S1", "S2"],
        "optimal",
        "status",
        "failed_stage",
        "optimal_runs",
        "nonoptimal_runs",
        "optimal_rate_pct",
        "failure_types_json",
    )


def _epsilon_reliability_rows():
    return _reliability_rows(
        _epsilon_seed_rows(),
        "epsilon",
        [0.8, 0.9, 0.95, 1.0],
        "optimal",
        "status",
        None,
        "optimal_runs",
        "nonoptimal_runs",
        "optimal_rate_pct",
        "failure_status_counts_json",
        status_only=True,
    )


def _lambda_reliability_rows():
    return _reliability_rows(
        _lambda_seed_rows(),
        "lambda",
        [0.0, 0.05, 0.1, 0.25, 0.5, 1.0],
        "optimal",
        "status",
        "failed_stage",
        "optimal_runs",
        "nonoptimal_runs",
        "optimal_rate_pct",
        "failure_types_json",
    )


def _alpha_reliability_rows():
    return _reliability_rows(
        _alpha_seed_rows(),
        "alpha",
        [1.0, 0.6, 0.5, 0.4, 0.33],
        "optimal",
        "status",
        "failed_stage",
        "optimal_runs",
        "nonoptimal_runs",
        "optimal_rate_pct",
        "failure_types_json",
    )


def _uncertainty_reliability_rows():
    return _reliability_rows(
        _uncertainty_seed_rows(),
        "condition",
        [
            "U0",
            "UW",
            "UM",
            "UR",
            "UP",
            "UJ",
        ],
        "proposed_optimal",
        "proposed_status",
        "proposed_failed_stage",
        "proposed_optimal_runs",
        "proposed_nonoptimal_runs",
        "optimal_rate_pct",
        "failure_types_json",
    )


def _scalability_reliability_rows():
    return _reliability_rows(
        _scalability_seed_rows(),
        "n_farmers",
        [
            25,
            50,
            100,
            250,
            500,
        ],
        "proposed_optimal",
        "proposed_status",
        "proposed_failed_stage",
        "proposed_optimal_runs",
        "proposed_nonoptimal_runs",
        "proposed_optimal_rate_pct",
        "failure_types_json",
    )


def _solver_reliability_row(
    family,
    rows,
    optimal_key,
    status_key,
    stage_key=None,
):
    total = len(rows)

    clean = sum(
        bool(row[optimal_key])
        for row in rows
    )

    nonoptimal = total - clean

    statuses = Counter()
    stages = Counter()

    for row in rows:
        if bool(row[optimal_key]):
            continue

        statuses[
            row.get(status_key) or "None"
        ] += 1

        stages[
            (
                row.get(stage_key)
                if stage_key
                else None
            )
            or "None"
        ] += 1

    return {
        "family": family,
        "total_cells": total,
        "optimal_or_clean_cells": clean,
        "nonoptimal_cells": nonoptimal,
        "clean_rate_pct": round(
            100.0 * clean / total,
            4,
        ),
        "nonoptimal_rate_pct": round(
            100.0 * nonoptimal / total,
            4,
        ),
        "status_counts_json":
            json.dumps(
                dict(
                    sorted(
                        statuses.items()
                    )
                ),
                sort_keys=True,
            ),
        "failed_stage_counts_json":
            json.dumps(
                dict(
                    sorted(
                        stages.items()
                    )
                ),
                sort_keys=True,
            ),
    }


def _solver_reliability_rows():
    return [
        _solver_reliability_row(
            "PRIMARY",
            _primary_seed_rows(),
            "proposed_optimal",
            "proposed_status",
            "proposed_failed_stage",
        ),
        _solver_reliability_row(
            "EPSILON_SENSITIVITY",
            _epsilon_seed_rows(),
            "optimal",
            "status",
            None,
        ),
        _solver_reliability_row(
            "LAMBDA_STABILITY",
            _lambda_seed_rows(),
            "optimal",
            "status",
            "failed_stage",
        ),
        _solver_reliability_row(
            "ALPHA_CONCENTRATION",
            _alpha_seed_rows(),
            "optimal",
            "status",
            "failed_stage",
        ),
        _solver_reliability_row(
            "ACTION_ROBUSTNESS",
            _action_seed_rows(),
            "optimal",
            "status",
            "failed_stage",
        ),
        _solver_reliability_row(
            "UNCERTAINTY",
            _uncertainty_seed_rows(),
            "proposed_optimal",
            "proposed_status",
            "proposed_failed_stage",
        ),
        _solver_reliability_row(
            "SCALABILITY",
            _scalability_seed_rows(),
            "proposed_optimal",
            "proposed_status",
            "proposed_failed_stage",
        ),
    ]


AGGREGATE_SPECS = {
    "primary_statistics.csv": (
        [
            "method",
            "state",
            "metric",
            "analysis_scope",
            "n",
            "mean",
            "sd",
            "median",
            "min",
            "max",
        ],
        _primary_statistics_rows,
    ),

    "epsilon_statistics.csv": (
        [
            "epsilon",
            "metric",
            "analysis_scope",
            "n",
            "mean",
            "sd",
            "median",
            "min",
            "max",
        ],
        _epsilon_statistics_rows,
    ),

    "lambda_statistics.csv": (
        [
            "lambda",
            "metric",
            "analysis_scope",
            "n",
            "mean",
            "sd",
            "median",
            "min",
            "max",
        ],
        _lambda_statistics_rows,
    ),

    "alpha_statistics.csv": (
        [
            "alpha",
            "metric",
            "analysis_scope",
            "n",
            "mean",
            "sd",
            "median",
            "min",
            "max",
        ],
        _alpha_statistics_rows,
    ),

    "action_robustness_statistics.csv": (
        [
            "profile",
            "metric",
            "analysis_scope",
            "n",
            "mean",
            "sd",
            "median",
            "min",
            "max",
        ],
        _action_statistics_rows,
    ),

    "uncertainty_statistics.csv": (
        [
            "condition",
            "method",
            "state",
            "metric",
            "analysis_scope",
            "n",
            "mean",
            "sd",
            "median",
            "min",
            "max",
        ],
        _uncertainty_statistics_rows,
    ),

    "scalability_statistics.csv": (
        [
            "n_farmers",
            "method",
            "state",
            "metric",
            "analysis_scope",
            "n",
            "mean",
            "sd",
            "median",
            "min",
            "max",
        ],
        _scalability_statistics_rows,
    ),

    "action_robustness_reliability.csv": (
        [
            "profile",
            "total_runs",
            "optimal_runs",
            "nonoptimal_runs",
            "optimal_rate_pct",
            "failure_types_json",
        ],
        _action_reliability_rows,
    ),

    "epsilon_reliability.csv": (
        [
            "epsilon",
            "total_runs",
            "optimal_runs",
            "nonoptimal_runs",
            "optimal_rate_pct",
            "failure_status_counts_json",
        ],
        _epsilon_reliability_rows,
    ),

    "lambda_reliability.csv": (
        [
            "lambda",
            "total_runs",
            "optimal_runs",
            "nonoptimal_runs",
            "optimal_rate_pct",
            "failure_types_json",
        ],
        _lambda_reliability_rows,
    ),

    "alpha_reliability.csv": (
        [
            "alpha",
            "total_runs",
            "optimal_runs",
            "nonoptimal_runs",
            "optimal_rate_pct",
            "failure_types_json",
        ],
        _alpha_reliability_rows,
    ),

    "uncertainty_reliability.csv": (
        [
            "condition",
            "total_runs",
            "proposed_optimal_runs",
            "proposed_nonoptimal_runs",
            "optimal_rate_pct",
            "failure_types_json",
        ],
        _uncertainty_reliability_rows,
    ),

    "scalability_reliability.csv": (
        [
            "n_farmers",
            "total_runs",
            "proposed_optimal_runs",
            "proposed_nonoptimal_runs",
            "proposed_optimal_rate_pct",
            "failure_types_json",
        ],
        _scalability_reliability_rows,
    ),

    "solver_reliability.csv": (
        [
            "family",
            "total_cells",
            "optimal_or_clean_cells",
            "nonoptimal_cells",
            "clean_rate_pct",
            "nonoptimal_rate_pct",
            "status_counts_json",
            "failed_stage_counts_json",
        ],
        _solver_reliability_rows,
    ),
}


def reproduce_aggregates(output: Path):
    assert_safe_output(output)

    verify_raw_freeze()
    verify_reference_analysis()

    stats_out = output / "statistics"

    print(
        "FINAL30 DETERMINISTIC AGGREGATE REPRODUCTION"
    )
    print(
        "==========================================="
    )

    passed = 0

    for filename, (
        fieldnames,
        builder,
    ) in AGGREGATE_SPECS.items():

        rows = builder()

        if _write_compare(
            stats_out,
            filename,
            fieldnames,
            rows,
        ):
            passed += 1

    print()

    print(
        "Aggregate/reliability CSVs matching "
        f"frozen reference: "
        f"{passed}/{len(AGGREGATE_SPECS)}"
    )

    if passed != len(AGGREGATE_SPECS):
        raise SystemExit(
            "DETERMINISTIC AGGREGATE "
            "REPRODUCTION: FAIL"
        )

    print(
        "DETERMINISTIC AGGREGATE "
        "REPRODUCTION: PASS"
    )
    print("Solver executions: 0")
    print("LLM executions: 0")



# ============================================================
# REPRODUCTION STAGE 3
# Wilson reliability intervals + exact paired McNemar tests.
# No bootstrap RNG is used in this stage.
# ============================================================

def _wilson_95(k, n):
    if n <= 0:
        raise RuntimeError(
            "Wilson interval requires n > 0"
        )

    z = 1.959963984540054
    p = k / n

    denom = 1.0 + (z * z) / n

    center = (
        p + (z * z) / (2.0 * n)
    ) / denom

    half = (
        z
        * (
            p * (1.0 - p) / n
            + (z * z) / (4.0 * n * n)
        ) ** 0.5
        / denom
    )

    return center - half, center + half


def _reliability_inference_row(
    family,
    parameter,
    total,
    optimal,
):
    nonoptimal = total - optimal
    rate = optimal / total

    low, high = _wilson_95(
        optimal,
        total,
    )

    return {
        "family": family,
        "parameter": parameter,
        "total_runs": total,
        "optimal_runs": optimal,
        "nonoptimal_runs": nonoptimal,
        "optimal_rate": rate,
        "optimal_rate_pct":
            optimal * 100.0 / total,
        "wilson_95_ci_low": low,
        "wilson_95_ci_high": high,
        "wilson_95_ci_low_pct": low * 100.0,
        "wilson_95_ci_high_pct": high * 100.0,
    }


def _count_optimal(
    rows,
    optimal_key,
):
    return (
        len(rows),
        sum(
            bool(row[optimal_key])
            for row in rows
        ),
    )


def _reliability_inference_rows():
    out = []

    # PRIMARY
    primary = _primary_seed_rows()

    total, optimal = _count_optimal(
        primary,
        "proposed_optimal",
    )

    out.append(
        _reliability_inference_row(
            "PRIMARY",
            "publication_config",
            total,
            optimal,
        )
    )

    # UNCERTAINTY
    rows = _uncertainty_seed_rows()

    for condition in [
        "U0",
        "UW",
        "UM",
        "UR",
        "UP",
        "UJ",
    ]:
        group = [
            r
            for r in rows
            if r["condition"] == condition
        ]

        total, optimal = _count_optimal(
            group,
            "proposed_optimal",
        )

        out.append(
            _reliability_inference_row(
                "UNCERTAINTY",
                condition,
                total,
                optimal,
            )
        )

    # EPSILON
    rows = _epsilon_seed_rows()

    for epsilon in [
        0.8,
        0.9,
        0.95,
        1.0,
    ]:
        group = [
            r
            for r in rows
            if r["epsilon"] == epsilon
        ]

        total, optimal = _count_optimal(
            group,
            "optimal",
        )

        out.append(
            _reliability_inference_row(
                "EPSILON_SENSITIVITY",
                f"epsilon={epsilon}",
                total,
                optimal,
            )
        )

    # LAMBDA
    rows = _lambda_seed_rows()

    for value in [
        0.0,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
    ]:
        group = [
            r
            for r in rows
            if r["lambda"] == value
        ]

        total, optimal = _count_optimal(
            group,
            "optimal",
        )

        out.append(
            _reliability_inference_row(
                "LAMBDA_STABILITY",
                f"lambda={value}",
                total,
                optimal,
            )
        )

    # ALPHA ? preserve frozen publication ordering.
    rows = _alpha_seed_rows()

    for value in [
        1.0,
        0.6,
        0.5,
        0.4,
        0.33,
    ]:
        group = [
            r
            for r in rows
            if r["alpha"] == value
        ]

        total, optimal = _count_optimal(
            group,
            "optimal",
        )

        out.append(
            _reliability_inference_row(
                "ALPHA_CONCENTRATION",
                f"alpha={value}",
                total,
                optimal,
            )
        )

    # ACTION ROBUSTNESS
    rows = _action_seed_rows()

    for profile in [
        "PRIMARY",
        "S1",
        "S2",
    ]:
        group = [
            r
            for r in rows
            if r["profile"] == profile
        ]

        total, optimal = _count_optimal(
            group,
            "optimal",
        )

        out.append(
            _reliability_inference_row(
                "ACTION_ROBUSTNESS",
                profile,
                total,
                optimal,
            )
        )

    # SCALABILITY
    rows = _scalability_seed_rows()

    for value in [
        25,
        50,
        100,
        250,
        500,
    ]:
        group = [
            r
            for r in rows
            if r["n_farmers"] == value
        ]

        total, optimal = _count_optimal(
            group,
            "proposed_optimal",
        )

        out.append(
            _reliability_inference_row(
                "SCALABILITY",
                f"n={value}",
                total,
                optimal,
            )
        )

    if len(out) != 30:
        raise RuntimeError(
            "Expected 30 reliability inference rows, "
            f"got {len(out)}"
        )

    return out


def _paired_optimal_map(
    rows,
    group_key,
    group_value,
    optimal_key,
):
    selected = [
        row
        for row in rows
        if row[group_key] == group_value
    ]

    result = {
        int(row["seed"]):
            bool(row[optimal_key])
        for row in selected
    }

    if len(result) != 30:
        raise RuntimeError(
            "Expected 30 paired seeds for "
            f"{group_key}={group_value}, "
            f"got {len(result)}"
        )

    return result


def _exact_mcnemar_row(
    family,
    comparison,
    a,
    b,
):
    from scipy.stats import binomtest

    seeds_a = set(a)
    seeds_b = set(b)

    if seeds_a != seeds_b:
        raise RuntimeError(
            f"Paired seed mismatch for {comparison}"
        )

    seeds = sorted(seeds_a)

    a_opt_b_non = sum(
        bool(a[seed])
        and not bool(b[seed])
        for seed in seeds
    )

    a_non_b_opt = sum(
        not bool(a[seed])
        and bool(b[seed])
        for seed in seeds
    )

    discordant = (
        a_opt_b_non
        + a_non_b_opt
    )

    if discordant == 0:
        p_value = 1.0
    else:
        p_value = binomtest(
            min(
                a_opt_b_non,
                a_non_b_opt,
            ),
            n=discordant,
            p=0.5,
            alternative="two-sided",
        ).pvalue

    return {
        "family": family,
        "comparison": comparison,
        "n_paired_seeds": len(seeds),
        "A_optimal_B_nonoptimal":
            a_opt_b_non,
        "A_nonoptimal_B_optimal":
            a_non_b_opt,
        "discordant_pairs":
            discordant,
        "exact_mcnemar_p_value":
            p_value,
        "test":
            (
                "exact McNemar via two-sided "
                "binomial test on discordant pairs"
            ),
    }


def _mcnemar_rows():
    out = []

    # UNCERTAINTY
    rows = _uncertainty_seed_rows()

    u0 = _paired_optimal_map(
        rows,
        "condition",
        "U0",
        "proposed_optimal",
    )

    for condition in [
        "UW",
        "UM",
        "UR",
        "UP",
        "UJ",
    ]:
        other = _paired_optimal_map(
            rows,
            "condition",
            condition,
            "proposed_optimal",
        )

        out.append(
            _exact_mcnemar_row(
                "UNCERTAINTY",
                f"U0_vs_{condition}",
                u0,
                other,
            )
        )

    # EPSILON
    rows = _epsilon_seed_rows()

    eps_095 = _paired_optimal_map(
        rows,
        "epsilon",
        0.95,
        "optimal",
    )

    eps_10 = _paired_optimal_map(
        rows,
        "epsilon",
        1.0,
        "optimal",
    )

    out.append(
        _exact_mcnemar_row(
            "EPSILON_SENSITIVITY",
            "epsilon_0.95_vs_1.0",
            eps_095,
            eps_10,
        )
    )

    # ACTION ROBUSTNESS
    rows = _action_seed_rows()

    action = {
        profile: _paired_optimal_map(
            rows,
            "profile",
            profile,
            "optimal",
        )
        for profile in [
            "PRIMARY",
            "S1",
            "S2",
        ]
    }

    for a_name, b_name in [
        ("PRIMARY", "S1"),
        ("PRIMARY", "S2"),
        ("S1", "S2"),
    ]:
        out.append(
            _exact_mcnemar_row(
                "ACTION_ROBUSTNESS",
                f"{a_name}_vs_{b_name}",
                action[a_name],
                action[b_name],
            )
        )

    # SCALABILITY
    rows = _scalability_seed_rows()

    n500 = _paired_optimal_map(
        rows,
        "n_farmers",
        500,
        "proposed_optimal",
    )

    for value in [
        25,
        50,
        100,
        250,
    ]:
        other = _paired_optimal_map(
            rows,
            "n_farmers",
            value,
            "proposed_optimal",
        )

        out.append(
            _exact_mcnemar_row(
                "SCALABILITY",
                f"n500_vs_n{value}",
                n500,
                other,
            )
        )

    if len(out) != 13:
        raise RuntimeError(
            "Expected 13 McNemar rows, "
            f"got {len(out)}"
        )

    return out


DETERMINISTIC_INFERENCE_SPECS = {
    "reliability_inference.csv": (
        [
            "family",
            "parameter",
            "total_runs",
            "optimal_runs",
            "nonoptimal_runs",
            "optimal_rate",
            "optimal_rate_pct",
            "wilson_95_ci_low",
            "wilson_95_ci_high",
            "wilson_95_ci_low_pct",
            "wilson_95_ci_high_pct",
        ],
        _reliability_inference_rows,
    ),

    "mcnemar_reliability_tests.csv": (
        [
            "family",
            "comparison",
            "n_paired_seeds",
            "A_optimal_B_nonoptimal",
            "A_nonoptimal_B_optimal",
            "discordant_pairs",
            "exact_mcnemar_p_value",
            "test",
        ],
        _mcnemar_rows,
    ),
}


def reproduce_deterministic_inference(
    output: Path,
):
    assert_safe_output(output)

    verify_raw_freeze()
    verify_reference_analysis()

    stats_out = output / "statistics"

    print(
        "FINAL30 DETERMINISTIC INFERENCE REPRODUCTION"
    )
    print(
        "==========================================="
    )

    passed = 0

    for filename, (
        fieldnames,
        builder,
    ) in DETERMINISTIC_INFERENCE_SPECS.items():

        rows = builder()

        if _write_compare(
            stats_out,
            filename,
            fieldnames,
            rows,
        ):
            passed += 1

    print()

    print(
        "Deterministic inference CSVs matching "
        f"frozen reference: "
        f"{passed}/"
        f"{len(DETERMINISTIC_INFERENCE_SPECS)}"
    )

    if passed != len(
        DETERMINISTIC_INFERENCE_SPECS
    ):
        raise SystemExit(
            "DETERMINISTIC INFERENCE "
            "REPRODUCTION: FAIL"
        )

    print(
        "DETERMINISTIC INFERENCE "
        "REPRODUCTION: PASS"
    )
    print("Solver executions: 0")
    print("LLM executions: 0")



# ============================================================
# REPRODUCTION STAGE 4
# Bootstrap confidence intervals + paired Wilcoxon inference.
#
# Historical note:
# The sealed analysis records:
#   - percentile 95% bootstrap intervals
#   - 10,000 resamples
#   - analysis seed 20260812
#
# The original analysis generator / RNG API call sequence was
# not preserved. Therefore this reconstruction uses an explicit,
# documented NumPy Generator convention. Deterministic statistics
# are required to match the sealed reference; bootstrap endpoints
# are regenerated, not claimed to be historical byte matches.
# ============================================================

BOOTSTRAP_REPLICATES = 10000
BOOTSTRAP_SEED = 20260812


def _bootstrap_mean_ci(values, rng):
    import numpy as np

    x = np.asarray(
        [
            float(v)
            for v in values
            if v is not None
        ],
        dtype=float,
    )

    if x.size == 0:
        raise RuntimeError(
            "Cannot bootstrap an empty value set"
        )

    indices = rng.integers(
        0,
        x.size,
        size=(
            BOOTSTRAP_REPLICATES,
            x.size,
        ),
    )

    means = x[indices].mean(axis=1)

    low, high = np.quantile(
        means,
        [0.025, 0.975],
        method="linear",
    )

    return (
        int(x.size),
        float(np.mean(x)),
        float(low),
        float(high),
    )


def _values(rows, column):
    return [
        row[column]
        for row in rows
        if row.get(column) is not None
    ]


def _bootstrap_specs():
    specs = []

    def add(
        family,
        parameter,
        method,
        state,
        metric,
        scope,
        values,
    ):
        specs.append(
            {
                "family": family,
                "parameter": parameter,
                "method": method,
                "state": state,
                "metric": metric,
                "analysis_scope": scope,
                "values": values,
            }
        )

    # --------------------------------------------------------
    # PRIMARY ? 8 rows
    # --------------------------------------------------------

    rows = _primary_seed_rows()

    optimal = [
        r
        for r in rows
        if r["proposed_optimal"]
    ]

    add(
        "PRIMARY",
        "publication_config",
        "B1",
        "PLANNED",
        "cash",
        "all_30",
        _values(
            rows,
            "b1_cash_planned",
        ),
    )

    add(
        "PRIMARY",
        "publication_config",
        "B2",
        "PLANNED",
        "cash",
        "all_30",
        _values(
            rows,
            "b2_cash_planned",
        ),
    )

    add(
        "PRIMARY",
        "publication_config",
        "B3",
        "PLANNED",
        "cash",
        "all_30",
        _values(
            rows,
            "b3_cash_planned",
        ),
    )

    for state, column, metric in [
        (
            "PLANNED",
            "proposed_planned_cash",
            "cash",
        ),
        (
            "INITIAL_REALIZED",
            "proposed_initial_realized_cash",
            "cash",
        ),
        (
            "RECOMMENDED_REVISED",
            "proposed_recommended_revised_cash",
            "cash",
        ),
        (
            "FINAL_REALIZED",
            "proposed_final_realized_cash",
            "cash",
        ),
        (
            "FINAL_vs_PLANNED",
            "final_vs_planned_ratio",
            "ratio",
        ),
    ]:
        add(
            "PRIMARY",
            "publication_config",
            "PROPOSED",
            state,
            metric,
            "optimal_only",
            _values(
                optimal,
                column,
            ),
        )

    # --------------------------------------------------------
    # UNCERTAINTY ? 12 rows
    # --------------------------------------------------------

    rows = _uncertainty_seed_rows()

    for condition in [
        "U0",
        "UW",
        "UM",
        "UR",
        "UP",
        "UJ",
    ]:
        group = [
            r
            for r in rows
            if (
                r["condition"] == condition
                and r["proposed_optimal"]
            )
        ]

        add(
            "UNCERTAINTY",
            condition,
            "PROPOSED",
            "FINAL_REALIZED",
            "cash",
            "optimal_only",
            _values(
                group,
                "proposed_final_realized_cash",
            ),
        )

        add(
            "UNCERTAINTY",
            condition,
            "PROPOSED",
            "FINAL_vs_PLANNED",
            "ratio",
            "optimal_only",
            _values(
                group,
                "final_vs_planned_ratio",
            ),
        )

    # --------------------------------------------------------
    # EPSILON ? 4 rows
    # --------------------------------------------------------

    rows = _epsilon_seed_rows()

    for value in [
        0.8,
        0.9,
        0.95,
        1.0,
    ]:
        group = [
            r
            for r in rows
            if (
                r["epsilon"] == value
                and r["optimal"]
            )
        ]

        add(
            "EPSILON_SENSITIVITY",
            f"epsilon={value}",
            "B3",
            "PLANNED",
            "cash",
            "optimal_only",
            _values(
                group,
                "cash",
            ),
        )

    # --------------------------------------------------------
    # LAMBDA ? 12 rows
    # --------------------------------------------------------

    rows = _lambda_seed_rows()

    for value in [
        0.0,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
    ]:
        group = [
            r
            for r in rows
            if (
                r["lambda"] == value
                and r["optimal"]
            )
        ]

        add(
            "LAMBDA_STABILITY",
            f"lambda={value}",
            "PROPOSED",
            "FINAL_REALIZED",
            "cash",
            "optimal_only",
            _values(
                group,
                "final_realized_cash",
            ),
        )

        add(
            "LAMBDA_STABILITY",
            f"lambda={value}",
            "PROPOSED",
            "RECOMMENDED_REVISED",
            "disruption_rate",
            "optimal_only",
            _values(
                group,
                "disruption_rate",
            ),
        )

    # --------------------------------------------------------
    # ALPHA ? 10 rows
    # --------------------------------------------------------

    rows = _alpha_seed_rows()

    for value in [
        1.0,
        0.6,
        0.5,
        0.4,
        0.33,
    ]:
        group = [
            r
            for r in rows
            if (
                r["alpha"] == value
                and r["optimal"]
            )
        ]

        add(
            "ALPHA_CONCENTRATION",
            f"alpha={value}",
            "PROPOSED",
            "FINAL_REALIZED",
            "cash",
            "optimal_only",
            _values(
                group,
                "final_realized_cash",
            ),
        )

        add(
            "ALPHA_CONCENTRATION",
            f"alpha={value}",
            "PROPOSED",
            "RECOMMENDED_REVISED",
            "max_LPS",
            "optimal_only",
            _values(
                group,
                "max_LPS",
            ),
        )

    # --------------------------------------------------------
    # ACTION ROBUSTNESS ? 6 rows
    # --------------------------------------------------------

    rows = _action_seed_rows()

    for profile in [
        "PRIMARY",
        "S1",
        "S2",
    ]:
        group = [
            r
            for r in rows
            if (
                r["profile"] == profile
                and r["optimal"]
            )
        ]

        add(
            "ACTION_ROBUSTNESS",
            profile,
            "PROPOSED",
            "FINAL_REALIZED",
            "cash",
            "optimal_only",
            _values(
                group,
                "final_realized_cash",
            ),
        )

        add(
            "ACTION_ROBUSTNESS",
            profile,
            "PROPOSED",
            "FINAL_vs_PLANNED",
            "ratio",
            "optimal_only",
            _values(
                group,
                "final_vs_planned_ratio",
            ),
        )

    # --------------------------------------------------------
    # SCALABILITY ? 10 rows
    # --------------------------------------------------------

    rows = _scalability_seed_rows()

    for value in [
        25,
        50,
        100,
        250,
        500,
    ]:
        group = [
            r
            for r in rows
            if r["n_farmers"] == value
        ]

        optimal = [
            r
            for r in group
            if r["proposed_optimal"]
        ]

        add(
            "SCALABILITY",
            f"n={value}",
            "PROPOSED",
            "FINAL_REALIZED",
            "cash",
            "optimal_only",
            _values(
                optimal,
                "proposed_final_realized_cash",
            ),
        )

        add(
            "SCALABILITY",
            f"n={value}",
            "PROPOSED",
            "PIPELINE",
            "runtime_s",
            "all_attempts",
            _values(
                group,
                "proposed_runtime_s",
            ),
        )

    if len(specs) != 62:
        raise RuntimeError(
            "Expected 62 bootstrap specifications, "
            f"got {len(specs)}"
        )

    return specs


def _bootstrap_rows():
    import numpy as np

    # One explicitly seeded stream over the fixed publication
    # row order above. This is the reconstruction convention.
    rng = np.random.default_rng(
        BOOTSTRAP_SEED
    )

    out = []

    for spec in _bootstrap_specs():
        (
            n,
            mean,
            low,
            high,
        ) = _bootstrap_mean_ci(
            spec["values"],
            rng,
        )

        out.append(
            {
                "family":
                    spec["family"],
                "parameter":
                    spec["parameter"],
                "method":
                    spec["method"],
                "state":
                    spec["state"],
                "metric":
                    spec["metric"],
                "analysis_scope":
                    spec["analysis_scope"],
                "n": n,
                "mean": mean,
                "bootstrap_95_ci_low": low,
                "bootstrap_95_ci_high": high,
                "bootstrap_replicates":
                    BOOTSTRAP_REPLICATES,
                "bootstrap_seed":
                    BOOTSTRAP_SEED,
            }
        )

    return out


def _rank_biserial(differences):
    import numpy as np
    from scipy.stats import rankdata

    d = np.asarray(
        differences,
        dtype=float,
    )

    d = d[d != 0.0]

    if d.size == 0:
        return 0.0

    ranks = rankdata(
        np.abs(d),
        method="average",
    )

    positive = float(
        ranks[d > 0.0].sum()
    )

    negative = float(
        ranks[d < 0.0].sum()
    )

    total = positive + negative

    return (
        (positive - negative) / total
        if total
        else 0.0
    )


def _paired_specs():
    rows = _primary_seed_rows()

    optimal = [
        r
        for r in rows
        if r["proposed_optimal"]
    ]

    return [
        (
            "B1_PLANNED_vs_B2_PLANNED",
            "B1_PLANNED",
            "B2_PLANNED",
            [
                r["b1_cash_planned"]
                - r["b2_cash_planned"]
                for r in rows
            ],
        ),
        (
            "B2_PLANNED_vs_B3_PLANNED",
            "B2_PLANNED",
            "B3_PLANNED",
            [
                r["b2_cash_planned"]
                - r["b3_cash_planned"]
                for r in rows
            ],
        ),
        (
            "B1_PLANNED_vs_B3_PLANNED",
            "B1_PLANNED",
            "B3_PLANNED",
            [
                r["b1_cash_planned"]
                - r["b3_cash_planned"]
                for r in rows
            ],
        ),
        (
            "PROPOSED_INITIAL_vs_PLANNED",
            "INITIAL_REALIZED",
            "PLANNED",
            [
                r[
                    "proposed_initial_realized_cash"
                ]
                - r[
                    "proposed_planned_cash"
                ]
                for r in optimal
            ],
        ),
        (
            "PROPOSED_REVISED_vs_INITIAL",
            "RECOMMENDED_REVISED",
            "INITIAL_REALIZED",
            [
                r[
                    "proposed_recommended_revised_cash"
                ]
                - r[
                    "proposed_initial_realized_cash"
                ]
                for r in optimal
            ],
        ),
        (
            "PROPOSED_FINAL_vs_REVISED",
            "FINAL_REALIZED",
            "RECOMMENDED_REVISED",
            [
                r[
                    "proposed_final_realized_cash"
                ]
                - r[
                    "proposed_recommended_revised_cash"
                ]
                for r in optimal
            ],
        ),
        (
            "PROPOSED_FINAL_vs_PLANNED",
            "FINAL_REALIZED",
            "PLANNED",
            [
                r[
                    "proposed_final_realized_cash"
                ]
                - r[
                    "proposed_planned_cash"
                ]
                for r in optimal
            ],
        ),
    ]


def _paired_rows():
    import numpy as np
    from scipy.stats import wilcoxon

    # Separate explicitly seeded bootstrap stream for paired
    # difference intervals.
    rng = np.random.default_rng(
        BOOTSTRAP_SEED
    )

    out = []

    for (
        comparison,
        state_a,
        state_b,
        differences,
    ) in _paired_specs():

        d = np.asarray(
            differences,
            dtype=float,
        )

        (
            n,
            mean,
            low,
            high,
        ) = _bootstrap_mean_ci(
            d,
            rng,
        )

        result = wilcoxon(
            d,
            zero_method="wilcox",
            correction=False,
            alternative="two-sided",
            method="auto",
        )

        nonzero = int(
            np.count_nonzero(d)
        )

        out.append(
            {
                "family": "PRIMARY",
                "comparison":
                    comparison,
                "state_A":
                    state_a,
                "state_B":
                    state_b,
                "difference_direction":
                    "A_minus_B",
                "n_pairs": n,
                "mean_difference":
                    mean,
                "mean_difference_bootstrap_ci_low":
                    low,
                "mean_difference_bootstrap_ci_high":
                    high,
                "median_difference":
                    float(np.median(d)),
                "wilcoxon_statistic":
                    float(result.statistic),
                "p_value_two_sided":
                    float(result.pvalue),
                "rank_biserial":
                    _rank_biserial(d),
                "nonzero_difference_pairs":
                    nonzero,
                "bootstrap_replicates":
                    BOOTSTRAP_REPLICATES,
                "bootstrap_seed":
                    BOOTSTRAP_SEED,
            }
        )

    if len(out) != 7:
        raise RuntimeError(
            "Expected 7 paired tests, "
            f"got {len(out)}"
        )

    return out


def _read_csv_dicts(path):
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        return list(
            csv.DictReader(f)
        )


def _float_close(a, b):
    import math

    aa = float(a)
    bb = float(b)

    return math.isclose(
        aa,
        bb,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def _compare_bootstrap_reconstruction(
    generated,
    reference,
):
    got = _read_csv_dicts(
        generated
    )

    ref = _read_csv_dicts(
        reference
    )

    if len(got) != 62 or len(ref) != 62:
        raise RuntimeError(
            "Expected 62 bootstrap rows"
        )

    identity_fields = [
        "family",
        "parameter",
        "method",
        "state",
        "metric",
        "analysis_scope",
        "n",
        "bootstrap_replicates",
        "bootstrap_seed",
    ]

    max_width_fraction = 0.0
    endpoint_deltas = []

    for i, (a, b) in enumerate(
        zip(got, ref),
        start=1,
    ):
        for key in identity_fields:
            if a[key] != b[key]:
                raise RuntimeError(
                    "Bootstrap identity mismatch "
                    f"row={i} field={key}: "
                    f"{a[key]!r} != {b[key]!r}"
                )

        if not _float_close(
            a["mean"],
            b["mean"],
        ):
            raise RuntimeError(
                "Bootstrap source mean mismatch "
                f"at row {i}"
            )

        ref_low = float(
            b["bootstrap_95_ci_low"]
        )

        ref_high = float(
            b["bootstrap_95_ci_high"]
        )

        got_low = float(
            a["bootstrap_95_ci_low"]
        )

        got_high = float(
            a["bootstrap_95_ci_high"]
        )

        width = ref_high - ref_low

        for x, y in [
            (got_low, ref_low),
            (got_high, ref_high),
        ]:
            delta = abs(x - y)

            endpoint_deltas.append(
                delta
            )

            if width > 0.0:
                max_width_fraction = max(
                    max_width_fraction,
                    delta / width,
                )

    return {
        "rows": len(got),
        "source_identity_and_means_match":
            True,
        "historical_ci_byte_match":
            got == ref,
        "max_ci_endpoint_absolute_delta":
            max(endpoint_deltas),
        "max_ci_endpoint_delta_as_fraction_of_reference_ci_width":
            max_width_fraction,
    }


def _compare_paired_reconstruction(
    generated,
    reference,
):
    got = _read_csv_dicts(
        generated
    )

    ref = _read_csv_dicts(
        reference
    )

    if len(got) != 7 or len(ref) != 7:
        raise RuntimeError(
            "Expected 7 paired-test rows"
        )

    exact_fields = [
        "family",
        "comparison",
        "state_A",
        "state_B",
        "difference_direction",
        "n_pairs",
        "nonzero_difference_pairs",
        "bootstrap_replicates",
        "bootstrap_seed",
    ]

    numeric_fields = [
        "mean_difference",
        "median_difference",
        "wilcoxon_statistic",
        "p_value_two_sided",
        "rank_biserial",
    ]

    max_width_fraction = 0.0
    endpoint_deltas = []

    for i, (a, b) in enumerate(
        zip(got, ref),
        start=1,
    ):
        for key in exact_fields:
            if a[key] != b[key]:
                raise RuntimeError(
                    "Paired deterministic mismatch "
                    f"row={i} field={key}"
                )

        for key in numeric_fields:
            if not _float_close(
                a[key],
                b[key],
            ):
                raise RuntimeError(
                    "Paired deterministic mismatch "
                    f"row={i} field={key}: "
                    f"{a[key]} != {b[key]}"
                )

        ref_low = float(
            b[
                "mean_difference_bootstrap_ci_low"
            ]
        )

        ref_high = float(
            b[
                "mean_difference_bootstrap_ci_high"
            ]
        )

        got_low = float(
            a[
                "mean_difference_bootstrap_ci_low"
            ]
        )

        got_high = float(
            a[
                "mean_difference_bootstrap_ci_high"
            ]
        )

        width = ref_high - ref_low

        for x, y in [
            (got_low, ref_low),
            (got_high, ref_high),
        ]:
            delta = abs(x - y)

            endpoint_deltas.append(
                delta
            )

            if width > 0.0:
                max_width_fraction = max(
                    max_width_fraction,
                    delta / width,
                )

    return {
        "rows": len(got),
        "deterministic_fields_match":
            True,
        "historical_ci_byte_match":
            got == ref,
        "max_ci_endpoint_absolute_delta":
            max(endpoint_deltas),
        "max_ci_endpoint_delta_as_fraction_of_reference_ci_width":
            max_width_fraction,
    }


def reproduce_stochastic_inference(
    output: Path,
):
    assert_safe_output(output)

    verify_raw_freeze()
    verify_reference_analysis()

    stats_out = output / "statistics"

    print(
        "FINAL30 STOCHASTIC INFERENCE RECONSTRUCTION"
    )

    print(
        "==========================================="
    )

    bootstrap_file = (
        stats_out
        / "bootstrap_confidence_intervals.csv"
    )

    paired_file = (
        stats_out
        / "paired_tests.csv"
    )

    _write_csv(
        bootstrap_file,
        [
            "family",
            "parameter",
            "method",
            "state",
            "metric",
            "analysis_scope",
            "n",
            "mean",
            "bootstrap_95_ci_low",
            "bootstrap_95_ci_high",
            "bootstrap_replicates",
            "bootstrap_seed",
        ],
        _bootstrap_rows(),
    )

    _write_csv(
        paired_file,
        [
            "family",
            "comparison",
            "state_A",
            "state_B",
            "difference_direction",
            "n_pairs",
            "mean_difference",
            "mean_difference_bootstrap_ci_low",
            "mean_difference_bootstrap_ci_high",
            "median_difference",
            "wilcoxon_statistic",
            "p_value_two_sided",
            "rank_biserial",
            "nonzero_difference_pairs",
            "bootstrap_replicates",
            "bootstrap_seed",
        ],
        _paired_rows(),
    )

    bootstrap_check = (
        _compare_bootstrap_reconstruction(
            bootstrap_file,
            REF_DIR
            / "statistics"
            / "bootstrap_confidence_intervals.csv",
        )
    )

    paired_check = (
        _compare_paired_reconstruction(
            paired_file,
            REF_DIR
            / "statistics"
            / "paired_tests.csv",
        )
    )

    note = {
        "schema":
            "farmsync-final30-analysis-reconstruction-v1",

        "historical_bootstrap_generator_recovered":
            False,

        "historical_rule_preserved": {
            "interval":
                "percentile_95",
            "bootstrap_replicates":
                BOOTSTRAP_REPLICATES,
            "bootstrap_seed":
                BOOTSTRAP_SEED,
            "optimal_only_outcome_summaries":
                True,
            "zero_imputation_nonoptimal":
                False,
        },

        "reconstruction_rng": {
            "library":
                "numpy",
            "api":
                "numpy.random.default_rng",
            "seed":
                BOOTSTRAP_SEED,
            "bootstrap_stream":
                (
                    "one shared seeded stream in fixed "
                    "publication row order per output file"
                ),
            "quantile_method":
                "linear",
        },

        "bootstrap_reference_comparison":
            bootstrap_check,

        "paired_reference_comparison":
            paired_check,

        "interpretation": (
            "Deterministic source identities, sample sizes, "
            "means, paired differences, Wilcoxon statistics, "
            "p-values and rank-biserial effects are required "
            "to agree with the sealed reference. Bootstrap "
            "endpoints are newly regenerated because the "
            "historical RNG API/call sequence was not preserved."
        ),
    }

    note_path = (
        output
        / "RECONSTRUCTION_NOTE.json"
    )

    note_path.write_text(
        json.dumps(
            note,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print(
        "bootstrap_confidence_intervals.csv : "
        f"GENERATED ({bootstrap_check['rows']} rows)"
    )

    print(
        "  source identities / means        : PASS"
    )

    print(
        "  historical byte-exact CI match   : "
        + (
            "YES"
            if bootstrap_check[
                "historical_ci_byte_match"
            ]
            else "NO (expected)"
        )
    )

    print(
        "  max endpoint shift / frozen width: "
        f"{bootstrap_check[
            'max_ci_endpoint_delta_as_fraction_of_reference_ci_width'
        ]:.6f}"
    )

    print()
    print(
        "paired_tests.csv                   : "
        f"GENERATED ({paired_check['rows']} rows)"
    )

    print(
        "  deterministic statistics         : PASS"
    )

    print(
        "  historical byte-exact CI match   : "
        + (
            "YES"
            if paired_check[
                "historical_ci_byte_match"
            ]
            else "NO (expected)"
        )
    )

    print(
        "  max endpoint shift / frozen width: "
        f"{paired_check[
            'max_ci_endpoint_delta_as_fraction_of_reference_ci_width'
        ]:.6f}"
    )

    print()
    print(
        "STOCHASTIC INFERENCE RECONSTRUCTION: PASS"
    )

    print(
        "Historical RNG call sequence recovered: NO"
    )

    print(
        "Solver executions: 0"
    )

    print(
        "LLM executions: 0"
    )


def check_inputs(output: Path) -> None:
    assert_safe_output(output)

    raw = verify_raw_freeze()
    ref = verify_reference_analysis()

    print("FINAL30 ANALYSIS INPUT CHECK")
    print("============================")
    print("Raw sealed cells       :", raw["cell_count"])
    print("Clean cells            :", raw["clean_cells"])
    print("Non-clean cells        :", raw["non_clean_cells"])
    print("Raw source commit      :", raw["source_commit"])
    print("Reference files        :", ref["analysis_file_count"])
    print("Bootstrap replicates   :", ref["bootstrap_replicates"])
    print("Bootstrap seed         :", ref["bootstrap_seed"])
    print("Output directory       :", output)
    print()

    print("Family counts:")
    for family, expected in EXPECTED_FAMILY_COUNTS.items():
        print(
            f"  {family:22} "
            f"{raw['family_counts'][family]:3d}"
        )

    print()
    print("Protected input verification: PASS")
    print("Output path safety: PASS")
    print("Scientific recomputation: NOT RUN")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=(
            "Reproduction output directory. Must be under "
            "results/farmsync/reproduction/."
        ),
    )

    parser.add_argument(
        "--check-inputs",
        action="store_true",
        help=(
            "Verify sealed raw/reference artifacts only; "
            "do not generate analysis outputs."
        ),
    )

    parser.add_argument(
        "--seed-level",
        action="store_true",
        help=(
            "Reproduce the seven deterministic seed-level "
            "statistics CSVs and compare them with the "
            "sealed reference."
        ),
    )

    parser.add_argument(
        "--aggregates",
        action="store_true",
        help=(
            "Reproduce deterministic aggregate and "
            "reliability CSVs and compare them with the "
            "sealed reference."
        ),
    )

    parser.add_argument(
        "--deterministic-inference",
        action="store_true",
        help=(
            "Reproduce Wilson reliability intervals and "
            "exact paired McNemar tests."
        ),
    )

    parser.add_argument(
        "--stochastic-inference",
        action="store_true",
        help=(
            "Regenerate bootstrap confidence intervals and "
            "paired Wilcoxon inference using the documented "
            "reconstruction convention."
        ),
    )

    args = parser.parse_args()

    selected = sum(
        [
            bool(args.check_inputs),
            bool(args.seed_level),
            bool(args.aggregates),
            bool(args.deterministic_inference),
            bool(args.stochastic_inference),
        ]
    )

    if selected != 1:
        raise SystemExit(
            "Choose exactly one mode: "
            "--check-inputs, --seed-level, "
            "--aggregates, "
            "--deterministic-inference, or "
            "--stochastic-inference"
        )

    if args.check_inputs:
        check_inputs(args.output_dir)
        return

    if args.seed_level:
        reproduce_seed_level(
            args.output_dir.resolve()
        )
        return

    if args.aggregates:
        reproduce_aggregates(
            args.output_dir.resolve()
        )
        return

    if args.deterministic_inference:
        reproduce_deterministic_inference(
            args.output_dir.resolve()
        )
        return

    reproduce_stochastic_inference(
        args.output_dir.resolve()
    )


if __name__ == "__main__":
    main()
