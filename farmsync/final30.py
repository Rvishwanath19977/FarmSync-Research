"""
FarmSync publication Final30 execution harness.

This is the publication-evaluation runner for the predeclared
publication-experiment-matrix-v1.

Scientific boundaries:
- consumes the exact frozen 30 master seeds;
- never tunes epsilon/lambda/alpha/action/uncertainty from results;
- no LLM calls;
- loads the existing processed operational data read-only;
- verifies frozen dataset hashes before execution;
- records non-Optimal outcomes without zero-imputation;
- unexpected programming/invariant errors propagate;
- results are atomic and resumable;
- an existing result is never silently overwritten.

The runner produces raw per-cell evidence only.
Publication statistics are a separate post-run stage.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "farmsync-final30-runner-v1"
CELL_SCHEMA = "farmsync-final30-cell-v1"

MATRIX_REL = Path(
    "results/farmsync/audit/publication_experiment_matrix_v1.json"
)
FREEZE_REL = Path(
    "results/farmsync/qa/pre_eval_freeze/FREEZE.json"
)
SOLVER_AMENDMENT_REL = Path(
    "results/farmsync/audit/solver_amendment_pre_final30_v1.json"
)
DEV_CHECKPOINT_REL = Path(
    "results/farmsync/proposed/ui_dev_checkpoint_solver_amended_v1.json"
)
OUT_REL = Path(
    "results/farmsync/final30_v1"
)

EXPECTED_MATRIX_SHA256 = (
    "b339a43ab581a0d481da230b84918363"
    "bc82f771b993f575c50ea903cdecc0f0"
)

EXPECTED_SEEDS_SHA256 = (
    "7224b558c8afc0071152f0b9d3bcc4d"
    "9972452f52a480ef333233facc981bf40"
)

EXPECTED_RNG_SHA256 = (
    "3bd23959a9e93e0fdf87c580c9a0c9f"
    "140de5a9889f28b859144862f4c257ec9"
)

EXPECTED_PROVENANCE_SHA256 = (
    "e92d6db3fcd316fde7c9a9c24cd62980"
    "c771e55bc6eebe5692269f289b83d4f8"
)

EXPECTED_SOLVER_AMENDMENT_SHA256 = (
    "1d42d59e3c1ba404d13f5c557560e943"
    "c222030b1a21ec65094534140cf865b8"
)

EXPECTED_DEV_CHECKPOINT_SHA256 = (
    "207ea314537d0df4aa3ba578dd76d3f4"
    "127d63a9917b587bf960ee19f921fc09"
)

MATRIX_FREEZE_COMMIT = (
    "9d068294bfa30ccb2050203433a99dee35112694"
)

REQUIRED_IMPLEMENTATION_BASE_COMMIT = (
    "18c18b44dd31de993c9d952d0153b553cd682147"
)

FAMILY_ORDER = (
    "PRIMARY",
    "EPSILON_SENSITIVITY",
    "LAMBDA_STABILITY",
    "ALPHA_CONCENTRATION",
    "ACTION_ROBUSTNESS",
    "UNCERTAINTY",
    "SCALABILITY",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha256(obj) -> str:
    raw = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_output(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=project_root(),
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def current_commit() -> str:
    return git_output("rev-parse", "HEAD")


def is_ancestor(commit: str) -> bool:
    p = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=project_root(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return p.returncode == 0


def tracked_tree_clean() -> bool:
    root = project_root()

    unstaged = subprocess.run(
        ["git", "diff", "--quiet"],
        cwd=root,
    ).returncode == 0

    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=root,
    ).returncode == 0

    # Untracked files are intentionally ignored here:
    # Final30 outputs themselves are untracked while the run is in progress.
    return unstaged and staged


def load_matrix() -> dict:
    p = project_root() / MATRIX_REL

    if not p.is_file():
        raise RuntimeError(
            f"Missing frozen experiment matrix: {p}"
        )

    got = sha256_file(p)

    if got.lower() != EXPECTED_MATRIX_SHA256:
        raise RuntimeError(
            "Frozen experiment matrix hash mismatch: "
            f"{got}"
        )

    m = read_json(p)

    if m.get("version") != "publication-experiment-matrix-v1":
        raise RuntimeError("Unexpected experiment matrix version")

    if m.get("status") != "FROZEN_BEFORE_FINAL30":
        raise RuntimeError("Experiment matrix is not frozen")

    families = m["families"]

    assert families["EPSILON_SENSITIVITY"]["values"] == [
        0.80, 0.90, 0.95, 1.00
    ]

    assert families["LAMBDA_STABILITY"]["values"] == [
        0.0, 0.05, 0.10, 0.25, 0.50, 1.00
    ]

    assert families["ALPHA_CONCENTRATION"]["values"] == [
        1.00, 0.60, 0.50, 0.40, 0.33
    ]

    assert families["ACTION_ROBUSTNESS"]["profiles"] == [
        "PRIMARY", "S1", "S2"
    ]

    assert families["UNCERTAINTY"]["conditions"] == [
        "U0", "UW", "UM", "UR", "UP", "UJ"
    ]

    assert families["SCALABILITY"]["n_farmers_values"] == [
        25, 50, 100, 250, 500
    ]

    return m


def _verify_matrix_reproducibility(m: dict) -> dict:
    root = project_root()
    r = m["reproducibility"]

    checks = (
        (
            root / r["replication_seeds_path"],
            r["replication_seeds_sha256"],
            EXPECTED_SEEDS_SHA256,
            "replication seeds",
        ),
        (
            root / r["rng_streams_path"],
            r["rng_streams_sha256"],
            EXPECTED_RNG_SHA256,
            "RNG streams",
        ),
        (
            root / r["provenance_manifest_path"],
            r["provenance_manifest_sha256"],
            EXPECTED_PROVENANCE_SHA256,
            "provenance manifest",
        ),
    )

    out = {}

    for path, matrix_hash, expected_hash, label in checks:
        if not path.is_file():
            raise RuntimeError(f"Missing {label}: {path}")

        got = sha256_file(path).lower()

        if matrix_hash.lower() != expected_hash:
            raise RuntimeError(
                f"Frozen matrix {label} identity changed"
            )

        if got != expected_hash:
            raise RuntimeError(
                f"{label} hash mismatch: {got}"
            )

        out[label] = got

    seeds_obj = read_json(root / r["replication_seeds_path"])
    seeds = seeds_obj["replication_seeds"]

    if seeds != r["seed_list"]:
        raise RuntimeError(
            "Frozen seed list does not match experiment matrix"
        )

    if len(seeds) != 30 or len(set(seeds)) != 30:
        raise RuntimeError(
            "Final30 requires exactly 30 unique frozen seeds"
        )

    return {
        "seed_count": len(seeds),
        "seeds": seeds,
        "hashes": out,
    }


def verify_pre_final30_solver_amendment() -> dict:
    """
    Verify the prospective numerical-reproducibility amendment and its
    superseding DEV checkpoint.

    This is solver-free with respect to scientific optimisation: constructing
    PULP_CBC_CMD is permitted, but no model is solved here.
    """
    root = project_root()

    amendment_path = root / SOLVER_AMENDMENT_REL
    checkpoint_path = root / DEV_CHECKPOINT_REL

    if not amendment_path.is_file():
        raise RuntimeError(
            f"Missing pre-Final30 solver amendment: {amendment_path}"
        )

    if not checkpoint_path.is_file():
        raise RuntimeError(
            f"Missing solver-amended DEV checkpoint: {checkpoint_path}"
        )

    amendment_sha = sha256_file(amendment_path).lower()
    checkpoint_sha = sha256_file(checkpoint_path).lower()

    if amendment_sha != EXPECTED_SOLVER_AMENDMENT_SHA256:
        raise RuntimeError(
            "Pre-Final30 solver amendment hash mismatch: "
            f"{amendment_sha}"
        )

    if checkpoint_sha != EXPECTED_DEV_CHECKPOINT_SHA256:
        raise RuntimeError(
            "Solver-amended DEV checkpoint hash mismatch: "
            f"{checkpoint_sha}"
        )

    amendment = read_json(amendment_path)
    checkpoint = read_json(checkpoint_path)

    if amendment.get("schema") != "farmsync-solver-amendment-v1":
        raise RuntimeError(
            "Unexpected solver amendment schema"
        )

    if amendment.get("status") != "FROZEN_BEFORE_FINAL30":
        raise RuntimeError(
            "Solver amendment is not frozen before Final30"
        )

    if amendment.get("final30_cells_executed_before_amendment") != 0:
        raise RuntimeError(
            "Solver amendment was not made before Final30 execution"
        )

    effective = amendment.get("effective_solver", {})

    if effective.get("gapRel") != 1e-6:
        raise RuntimeError(
            "Solver amendment does not require gapRel=1e-6"
        )

    if effective.get("timeLimit_s") != 120:
        raise RuntimeError(
            "Solver amendment does not require timeLimit=120"
        )

    if (
        checkpoint.get("provenance")
        != "DEVELOPMENT_CHECKPOINT_SOLVER_AMENDED"
    ):
        raise RuntimeError(
            "Unexpected superseding DEV checkpoint provenance"
        )

    cp_amendment = checkpoint.get("solver_amendment", {})

    expected_rel = str(
        SOLVER_AMENDMENT_REL
    ).replace("\\", "/")

    if cp_amendment.get("path") != expected_rel:
        raise RuntimeError(
            "DEV checkpoint references unexpected solver amendment"
        )

    if (
        cp_amendment.get("sha256")
        != EXPECTED_SOLVER_AMENDMENT_SHA256
    ):
        raise RuntimeError(
            "DEV checkpoint solver-amendment hash mismatch"
        )

    if cp_amendment.get("effective_gapRel") != 1e-6:
        raise RuntimeError(
            "DEV checkpoint does not record gapRel=1e-6"
        )

    # Verify that the actual code/runtime agrees with the amendment.
    from . import solver as solver_config

    configured = solver_config.cbc_solver()

    if configured.optionsDict.get("gapRel") != 1e-6:
        raise RuntimeError(
            "Effective CBC solver gapRel is not 1e-6"
        )

    if configured.timeLimit != 120:
        raise RuntimeError(
            "Effective CBC solver timeLimit is not 120"
        )

    threads = solver_config.cbc_threads()

    if configured.optionsDict.get("threads") != threads:
        raise RuntimeError(
            "Effective CBC solver thread metadata is inconsistent"
        )

    return {
        "solver_amendment_path":
            str(SOLVER_AMENDMENT_REL).replace("\\", "/"),
        "solver_amendment_sha256":
            amendment_sha,
        "dev_checkpoint_path":
            str(DEV_CHECKPOINT_REL).replace("\\", "/"),
        "dev_checkpoint_sha256":
            checkpoint_sha,
        "effective_solver": {
            "engine": "CBC",
            "gapRel": 1e-6,
            "timeLimit_s": 120,
            "threads": threads,
        },
    }


def verify_frozen_datasets() -> dict:
    """
    Verify only the immutable dataset category from the historical
    pre-evaluation FREEZE.

    We intentionally do NOT require all scientific-source hashes in that
    historical manifest to match because publication-only API/observability
    changes were intentionally committed after the pre-evaluation freeze.
    """
    root = project_root()
    freeze_path = root / FREEZE_REL

    if not freeze_path.is_file():
        raise RuntimeError(
            f"Missing pre-evaluation FREEZE: {freeze_path}"
        )

    freeze = read_json(freeze_path)
    artifacts = freeze["artifacts"]

    dataset_entries = {
        rel: meta
        for rel, meta in artifacts.items()
        if meta.get("category") == "datasets"
    }

    if not dataset_entries:
        raise RuntimeError(
            "FREEZE contains no dataset entries"
        )

    failures = []

    for rel, meta in sorted(dataset_entries.items()):
        p = root / Path(rel)

        if not p.is_file():
            failures.append(
                f"MISSING {rel}"
            )
            continue

        size = p.stat().st_size
        got = sha256_file(p)

        if size != meta["size"]:
            failures.append(
                f"SIZE {rel}: {size} != {meta['size']}"
            )

        if got.lower() != meta["sha256"].lower():
            failures.append(
                f"SHA256 {rel}: {got} != {meta['sha256']}"
            )

    if failures:
        raise RuntimeError(
            "Frozen dataset verification failed:\n"
            + "\n".join(failures)
        )

    attestation_rows = [
        {
            "path": rel,
            "sha256": dataset_entries[rel]["sha256"],
            "size": dataset_entries[rel]["size"],
        }
        for rel in sorted(dataset_entries)
    ]

    return {
        "freeze_manifest_sha256": sha256_file(freeze_path),
        "dataset_file_count": len(dataset_entries),
        "dataset_attestation_sha256": canonical_sha256(
            attestation_rows
        ),
    }


def planned_cell_count(m: dict) -> int:
    n = m["reproducibility"]["seed_count"]
    f = m["families"]

    per_seed = (
        1
        + len(f["EPSILON_SENSITIVITY"]["values"])
        + len(f["LAMBDA_STABILITY"]["values"])
        + len(f["ALPHA_CONCENTRATION"]["values"])
        + len(f["ACTION_ROBUSTNESS"]["profiles"])
        + len(f["UNCERTAINTY"]["conditions"])
        + len(f["SCALABILITY"]["n_farmers_values"])
    )

    return n * per_seed


def validate_environment(
    *,
    require_clean: bool,
) -> dict:
    m = load_matrix()
    repro = _verify_matrix_reproducibility(m)
    datasets = verify_frozen_datasets()
    solver_amendment = verify_pre_final30_solver_amendment()

    if not is_ancestor(MATRIX_FREEZE_COMMIT):
        raise RuntimeError(
            "Current branch does not contain the frozen "
            "experiment-matrix commit"
        )

    if not is_ancestor(REQUIRED_IMPLEMENTATION_BASE_COMMIT):
        raise RuntimeError(
            "Current branch does not contain the required "
            "Final30 scientific API implementation commit"
        )

    clean = tracked_tree_clean()

    if require_clean and not clean:
        raise RuntimeError(
            "Tracked Git tree must be clean before executing "
            "publication Final30 results"
        )

    return {
        "matrix": m,
        "current_commit": current_commit(),
        "tracked_tree_clean": clean,
        "matrix_sha256": EXPECTED_MATRIX_SHA256,
        "reproducibility": repro,
        "datasets": datasets,
        "solver_amendment": solver_amendment,
        "planned_cells": planned_cell_count(m),
    }


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).replace(microsecond=0).isoformat()


def _atomic_json(path: Path, obj) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = path.with_name(
        path.name + ".tmp"
    )

    tmp.write_text(
        json.dumps(
            obj,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(
        tmp,
        path,
    )


def _run_manifest_path() -> Path:
    return project_root() / OUT_REL / "RUN_MANIFEST.json"


def ensure_run_manifest(env: dict) -> dict:
    p = _run_manifest_path()

    if p.exists():
        r = read_json(p)

        if r.get("schema") != SCHEMA:
            raise RuntimeError(
                "Existing Final30 run manifest has unexpected schema"
            )

        if r.get("source_commit") != env["current_commit"]:
            raise RuntimeError(
                "Final30 run is pinned to source commit "
                f"{r.get('source_commit')}, but HEAD is "
                f"{env['current_commit']}. Checkout the pinned commit "
                "before resuming."
            )

        if r.get("matrix_sha256") != EXPECTED_MATRIX_SHA256:
            raise RuntimeError(
                "Existing Final30 run uses a different matrix"
            )

        if (
            r.get("solver_amendment_sha256")
            != EXPECTED_SOLVER_AMENDMENT_SHA256
        ):
            raise RuntimeError(
                "Existing Final30 run uses a different solver amendment"
            )

        if (
            r.get("dev_checkpoint_sha256")
            != EXPECTED_DEV_CHECKPOINT_SHA256
        ):
            raise RuntimeError(
                "Existing Final30 run uses a different DEV checkpoint"
            )

        if (
            r.get("dataset_attestation_sha256")
            != env["datasets"]["dataset_attestation_sha256"]
        ):
            raise RuntimeError(
                "Frozen dataset attestation differs from the "
                "existing Final30 run"
            )

        return r

    r = {
        "schema": SCHEMA,
        "status": "IN_PROGRESS",
        "created_utc": _utc_now(),
        "source_commit": env["current_commit"],
        "matrix_commit": MATRIX_FREEZE_COMMIT,
        "matrix_sha256": EXPECTED_MATRIX_SHA256,
        "required_implementation_base_commit":
            REQUIRED_IMPLEMENTATION_BASE_COMMIT,
        "seed_count": 30,
        "planned_cells": env["planned_cells"],
        "replication_seeds_sha256": EXPECTED_SEEDS_SHA256,
        "rng_streams_sha256": EXPECTED_RNG_SHA256,
        "provenance_manifest_sha256":
            EXPECTED_PROVENANCE_SHA256,
        "solver_amendment_sha256":
            env["solver_amendment"]["solver_amendment_sha256"],
        "dev_checkpoint_sha256":
            env["solver_amendment"]["dev_checkpoint_sha256"],
        "effective_solver":
            env["solver_amendment"]["effective_solver"],
        "pre_eval_freeze_sha256":
            env["datasets"]["freeze_manifest_sha256"],
        "dataset_file_count":
            env["datasets"]["dataset_file_count"],
        "dataset_attestation_sha256":
            env["datasets"]["dataset_attestation_sha256"],
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "scientific_boundaries": {
            "llm_calls": False,
            "post_hoc_tuning": False,
            "zero_imputation_for_nonoptimal": False,
            "overwrite_existing_cells": False,
            "statistics_in_this_stage": False,
        },
    }

    _atomic_json(
        p,
        r,
    )

    return r


def _tag(value) -> str:
    if isinstance(value, float):
        return (
            f"{value:.2f}"
            .replace("-", "m")
            .replace(".", "p")
        )

    return str(value)


def cell_path(
    family: str,
    seed: int,
    parameter=None,
) -> Path:
    base = (
        project_root()
        / OUT_REL
        / family.lower()
    )

    if parameter is None:
        name = f"seed_{seed}.json"
    else:
        name = (
            f"seed_{seed}__{_tag(parameter)}.json"
        )

    return base / name


def _cell_identity(
    run_manifest: dict,
    family: str,
    seed: int,
    parameters: dict,
) -> dict:
    return {
        "schema": CELL_SCHEMA,
        "family": family,
        "seed": int(seed),
        "parameters": parameters,
        "source_commit": run_manifest["source_commit"],
        "matrix_sha256": run_manifest["matrix_sha256"],
        "dataset_attestation_sha256":
            run_manifest["dataset_attestation_sha256"],
    }


def _existing_cell(
    path: Path,
    identity: dict,
):
    if not path.exists():
        return None

    obj = read_json(path)

    for k, v in identity.items():
        if obj.get(k) != v:
            raise RuntimeError(
                f"Existing Final30 cell identity mismatch: {path}\n"
                f"field {k}: {obj.get(k)!r} != {v!r}"
            )

    if obj.get("completion") != "COMPLETE":
        raise RuntimeError(
            f"Existing Final30 cell is incomplete: {path}"
        )

    return obj


def _write_cell(
    path: Path,
    identity: dict,
    payload: dict,
    *,
    reused_from: str | None = None,
) -> dict:
    existing = _existing_cell(
        path,
        identity,
    )

    if existing is not None:
        return existing

    obj = dict(identity)
    obj.update(
        {
            "completion": "COMPLETE",
            "written_utc": _utc_now(),
            "reused_from": reused_from,
            "payload": payload,
        }
    )

    _atomic_json(
        path,
        obj,
    )

    return obj


class SeedContext:
    def __init__(
        self,
        seed: int,
        n_farmers: int = 500,
    ):
        from farmsync import experiment as exp

        self.seed = int(seed)
        self.n_farmers = int(n_farmers)

        self.instance = exp.build_instance(
            self.seed,
            tightness="base",
            n_farmers=self.n_farmers,
        )

        self._b1 = None
        self._b2 = None
        self._b2_total = None
        self._b3 = {}
        self._fairness_refs = None

    @property
    def farmers(self):
        return self.instance["farmers"]

    @property
    def plots(self):
        return self.instance["plots"]

    @property
    def crops(self):
        return self.instance["crops"]

    def b1(self):
        from farmsync.ilp_reference import run_b1_ilp

        if self._b1 is None:
            self._b1 = run_b1_ilp(
                self.farmers,
                self.plots,
                self.crops,
            )

        return self._b1

    def b2(self):
        from farmsync.ilp_reference import run_b2_ilp

        if self._b2 is None:
            self._b2 = run_b2_ilp(
                self.farmers,
                self.plots,
                self.crops,
            )

        return self._b2

    def b2_total(self):
        from farmsync.ilp_reference import b2_ilp_total

        if self._b2_total is None:
            self._b2_total = b2_ilp_total(
                self.farmers,
                self.plots,
                self.crops,
            )["b2_ilp_cash_total"]

        return self._b2_total

    def b3(self, epsilon: float):
        from farmsync.ilp_reference import run_b3_ilp

        key = float(epsilon)

        if key not in self._b3:
            self._b3[key] = run_b3_ilp(
                self.farmers,
                self.plots,
                self.crops,
                epsilon=key,
                tstar=self.b2_total(),
            )

        return self._b3[key]

    def fairness_refs(self):
        from farmsync import fairness as fair

        if self._fairness_refs is not None:
            return self._fairness_refs

        b1 = self.b1()

        if (
            getattr(b1, "solver", {}).get("status")
            != "Optimal"
        ):
            self._fairness_refs = None
            return None

        b1cash = fair.farmer_cash(
            b1
        )

        all_ids = [
            f.farmer_id
            for f in self.farmers
        ]

        cohorts = fair.bottom_cohorts(
            b1cash,
            all_ids,
        )

        self._fairness_refs = (
            b1cash,
            cohorts,
        )

        return self._fairness_refs


def _baseline_summary(
    name: str,
    result,
    ctx: SeedContext,
) -> dict:
    from farmsync import fairness as fair
    from farmsync.proposed import concentration as co

    solver = (
        getattr(result, "solver", {})
        or {}
    )

    status = solver.get("status")

    rec = {
        "method": name,
        "state": "PLANNED",
        "status": status,
        "optimal": status == "Optimal",
        "runtime_s": solver.get("runtime_s"),
        "epsilon": solver.get("epsilon"),
        "min_normalized_return":
            solver.get("min_normalized_return"),
        "cash": None,
        "area": None,
        "n": None,
        "cash_per_allocated_ha": None,
        "fairness_v2": None,
        "concentration": None,
    }

    if status != "Optimal":
        return rec

    cash = round(
        sum(
            a.cash_net
            for a in result.allocations
        ),
        0,
    )

    area = round(
        sum(
            a.area_ha
            for a in result.allocations
        ),
        3,
    )

    rec["cash"] = cash
    rec["area"] = area
    rec["n"] = len(
        result.allocations
    )

    rec["cash_per_allocated_ha"] = (
        cash / area
        if area
        else None
    )

    refs = ctx.fairness_refs()

    if refs is not None:
        b1cash, cohorts = refs

        fr = fair.fairness_report(
            result,
            ctx.farmers,
            b1_reference=b1cash,
            cohorts=cohorts,
        )

        rec["fairness_v2"] = {
            "primary": fr.get("primary"),
            "supporting": fr.get("supporting"),
            "efficiency": fr.get("efficiency"),
        }

    _per_crop, csum = co.concentration_metrics(
        result,
        ctx.plots,
        alpha=None,
    )

    rec["concentration"] = csum

    return rec


def _proposed_summary(
    *,
    seed: int,
    instance: dict,
    profile: str,
    lam: float,
    alpha: float,
) -> dict:
    from farmsync.proposed import actions as A
    from farmsync.proposed import pipeline as pl

    t0 = time.perf_counter()

    try:
        layer = A.run_action_consent_layer(
            seed=seed,
            profile=profile,
            instance=instance,
            lam=lam,
            alpha=alpha,
        )

    except A.ProposedInfeasibleError as e:
        return {
            "status": e.status,
            "optimal": False,
            "failed_stage": e.failed_stage,
            "runtime_s": time.perf_counter() - t0,
            "profile": profile,
            "lambda": lam,
            "alpha": alpha,
            "tiers": None,
        }

    except pl.PipelineError as e:
        # The current action-consent path reaches PipelineError only
        # through prerequisite Optimal guards. Record those solver
        # outcomes; unrelated programming errors are not caught here.
        msg = str(e)

        if not msg.startswith("prep."):
            raise

        status = None

        if "got " in msg:
            status = (
                msg.split("got ", 1)[1]
                .split(" ?", 1)[0]
                .strip()
                .strip("'")
                .strip('"')
            )

        return {
            "status": status,
            "optimal": False,
            "failed_stage":
                msg.split(":", 1)[0],
            "runtime_s": time.perf_counter() - t0,
            "profile": profile,
            "lambda": lam,
            "alpha": alpha,
            "tiers": None,
        }

    runtime = time.perf_counter() - t0

    tiers = {}

    for name, tier in layer["tiers"].items():
        t = dict(tier)

        area = t.get("area")
        cash = t.get("cash")

        t["cash_per_allocated_ha"] = (
            cash / area
            if cash is not None and area
            else None
        )

        tiers[name] = t

    ledger = layer["ledger"]

    return {
        "status": "Optimal",
        "optimal": True,
        "failed_stage": None,
        "runtime_s": runtime,
        "profile": profile,
        "lambda": layer["meta"]["lambda"],
        "alpha": layer["meta"]["alpha"],
        "protocol": layer["meta"]["protocol"],
        "instance_hash": layer["meta"]["instance_hash"],
        "tiers": tiers,
        "action_counts": layer["action_counts"],
        "withdrawn_farmers": layer["withdrawn_farmers"],
        "renewed_prompts": layer["renewed_prompts"],
        "renewed_counts": layer["renewed_counts"],
        "consent_coverage_final":
            layer["consent_coverage_final"],
        "recommendation_realisation_ratio_vs_planned":
            layer[
                "recommendation_realisation_ratio_vs_planned"
            ],
        "recommendation_realisation_ratio_vs_recommended":
            layer[
                "recommendation_realisation_ratio_vs_recommended"
            ],
        "fairness_v2_initial":
            layer["fairness_v2_initial"],
        "fairness_v2_final":
            layer["fairness_v2_final"],
        "recommended_revised_stability":
            layer["recommended_revised_stability"],
        "recommended_revised_phase4":
            layer["recommended_revised_phase4"],
        "recommended_revised_concentration":
            layer["recommended_revised_concentration"],
        "final_realized_concentration":
            layer["final_realized_concentration"],
        "concentration_constraint_scope":
            layer["concentration_constraint_scope"],
        "ledger_event_count": len(ledger),
        "ledger_sha256": canonical_sha256(ledger),
    }


def _disruption_metrics(
    p: dict,
):
    if not p.get("optimal"):
        return {
            "changed_soft_area": None,
            "soft_lock_area": None,
            "disruption_rate": None,
        }

    s = p[
        "recommended_revised_stability"
    ]

    changed = s.get(
        "changed_soft_area"
    )

    total = s.get(
        "soft_lock_area"
    )

    rate = (
        changed / total
        if changed is not None
        and total not in (None, 0)
        else 0.0
        if total == 0
        else None
    )

    return {
        "changed_soft_area": changed,
        "soft_lock_area": total,
        "disruption_rate": rate,
    }


def _retention(
    p: dict,
    numerator: str,
    denominator: str,
):
    if not p.get("optimal"):
        return None

    tiers = p["tiers"]

    a = tiers[numerator]["cash"]
    b = tiers[denominator]["cash"]

    if a is None or not b:
        return None

    return a / b


def _primary_payload(
    seed: int,
    ctx: SeedContext,
    matrix: dict,
) -> dict:
    from farmsync import config as C

    b1 = ctx.b1()
    b2 = ctx.b2()
    b3 = ctx.b3(
        C.PUBLICATION_EPSILON
    )

    proposed = _proposed_summary(
        seed=seed,
        instance=ctx.instance,
        profile=C.PUBLICATION_ACTION_PROFILE,
        lam=C.PUBLICATION_LAMBDA,
        alpha=C.PUBLICATION_ALPHA,
    )

    return {
        "instance": ctx.instance["record"],
        "publication_config": {
            "version":
                C.PUBLICATION_CONFIG_VERSION,
            "epsilon":
                C.PUBLICATION_EPSILON,
            "lambda":
                C.PUBLICATION_LAMBDA,
            "alpha":
                C.PUBLICATION_ALPHA,
            "action_profile":
                C.PUBLICATION_ACTION_PROFILE,
            "action_protocol":
                C.PUBLICATION_ACTION_PROTOCOL,
            "uncertainty_protocol":
                C.PUBLICATION_UNCERTAINTY_PROTOCOL,
            "fairness":
                C.PUBLICATION_FAIRNESS,
        },
        "baselines": {
            "B1": _baseline_summary(
                "B1", b1, ctx
            ),
            "B2": _baseline_summary(
                "B2", b2, ctx
            ),
            "B3": _baseline_summary(
                "B3", b3, ctx
            ),
        },
        "proposed": proposed,
        "comparison_boundary": {
            "B1_B2_B3_state": "PLANNED",
            "proposed_states_recorded": [
                "PLANNED",
                "INITIAL_REALIZED",
                "RECOMMENDED_REVISED",
                "FINAL_REALIZED",
            ],
            "rule":
                "Do not treat baseline PLANNED and "
                "Proposed FINAL_REALIZED as equivalent "
                "treatment states.",
        },
    }


def ensure_primary(
    seed: int,
    ctx: SeedContext,
    matrix: dict,
    run_manifest: dict,
) -> dict:
    path = cell_path(
        "PRIMARY",
        seed,
    )

    identity = _cell_identity(
        run_manifest,
        "PRIMARY",
        seed,
        {},
    )

    existing = _existing_cell(
        path,
        identity,
    )

    if existing is not None:
        print(
            f"[SKIP] PRIMARY seed={seed}"
        )
        return existing

    print(
        f"[RUN ] PRIMARY seed={seed}"
    )

    payload = _primary_payload(
        seed,
        ctx,
        matrix,
    )

    return _write_cell(
        path,
        identity,
        payload,
    )


def run_epsilon_family(
    seed: int,
    ctx: SeedContext,
    matrix: dict,
    run_manifest: dict,
) -> None:
    values = matrix["families"][
        "EPSILON_SENSITIVITY"
    ]["values"]

    tstar = ctx.b2_total()

    for epsilon in values:
        path = cell_path(
            "EPSILON_SENSITIVITY",
            seed,
            f"epsilon={epsilon:.2f}",
        )

        params = {
            "epsilon": float(epsilon),
        }

        identity = _cell_identity(
            run_manifest,
            "EPSILON_SENSITIVITY",
            seed,
            params,
        )

        if _existing_cell(
            path,
            identity,
        ) is not None:
            print(
                f"[SKIP] EPSILON seed={seed} "
                f"epsilon={epsilon}"
            )
            continue

        print(
            f"[RUN ] EPSILON seed={seed} "
            f"epsilon={epsilon}"
        )

        b3 = ctx.b3(
            float(epsilon)
        )

        summary = _baseline_summary(
            "B3",
            b3,
            ctx,
        )

        efficiency_retained = (
            summary["cash"] / tstar
            if summary["optimal"]
            and tstar
            else None
        )

        payload = {
            "epsilon": float(epsilon),
            "b2_total_cash_reference": tstar,
            "b3": summary,
            "min_normalized_return":
                summary[
                    "min_normalized_return"
                ],
            "efficiency_retained":
                efficiency_retained,
        }

        _write_cell(
            path,
            identity,
            payload,
        )


def run_lambda_family(
    seed: int,
    ctx: SeedContext,
    matrix: dict,
    run_manifest: dict,
    primary: dict,
) -> None:
    from farmsync import config as C

    values = matrix["families"][
        "LAMBDA_STABILITY"
    ]["values"]

    primary_p = primary[
        "payload"
    ]["proposed"]

    for lam in values:
        lam = float(lam)

        path = cell_path(
            "LAMBDA_STABILITY",
            seed,
            f"lambda={lam:.2f}",
        )

        params = {
            "lambda": lam,
            "alpha_fixed":
                C.PUBLICATION_ALPHA,
            "profile_fixed":
                C.PUBLICATION_ACTION_PROFILE,
        }

        identity = _cell_identity(
            run_manifest,
            "LAMBDA_STABILITY",
            seed,
            params,
        )

        if _existing_cell(
            path,
            identity,
        ) is not None:
            print(
                f"[SKIP] LAMBDA seed={seed} "
                f"lambda={lam}"
            )
            continue

        if lam == C.PUBLICATION_LAMBDA:
            p = primary_p
            reused = str(
                cell_path(
                    "PRIMARY",
                    seed,
                ).relative_to(project_root())
            )
        else:
            print(
                f"[RUN ] LAMBDA seed={seed} "
                f"lambda={lam}"
            )

            p = _proposed_summary(
                seed=seed,
                instance=ctx.instance,
                profile=C.PUBLICATION_ACTION_PROFILE,
                lam=lam,
                alpha=C.PUBLICATION_ALPHA,
            )

            reused = None

        payload = {
            "lambda": lam,
            "proposed": p,
            "disruption":
                _disruption_metrics(p),
            "economic_retention_recommended_vs_planned":
                _retention(
                    p,
                    "RECOMMENDED_REVISED",
                    "PLANNED",
                ),
            "economic_retention_final_vs_planned":
                _retention(
                    p,
                    "FINAL_REALIZED",
                    "PLANNED",
                ),
        }

        _write_cell(
            path,
            identity,
            payload,
            reused_from=reused,
        )


def run_alpha_family(
    seed: int,
    ctx: SeedContext,
    matrix: dict,
    run_manifest: dict,
    primary: dict,
) -> None:
    from farmsync import config as C

    values = matrix["families"][
        "ALPHA_CONCENTRATION"
    ]["values"]

    primary_p = primary[
        "payload"
    ]["proposed"]

    for alpha in values:
        alpha = float(alpha)

        path = cell_path(
            "ALPHA_CONCENTRATION",
            seed,
            f"alpha={alpha:.2f}",
        )

        params = {
            "alpha": alpha,
            "lambda_fixed":
                C.PUBLICATION_LAMBDA,
            "profile_fixed":
                C.PUBLICATION_ACTION_PROFILE,
        }

        identity = _cell_identity(
            run_manifest,
            "ALPHA_CONCENTRATION",
            seed,
            params,
        )

        if _existing_cell(
            path,
            identity,
        ) is not None:
            print(
                f"[SKIP] ALPHA seed={seed} "
                f"alpha={alpha}"
            )
            continue

        if alpha == C.PUBLICATION_ALPHA:
            p = primary_p
            reused = str(
                cell_path(
                    "PRIMARY",
                    seed,
                ).relative_to(project_root())
            )
        else:
            print(
                f"[RUN ] ALPHA seed={seed} "
                f"alpha={alpha}"
            )

            p = _proposed_summary(
                seed=seed,
                instance=ctx.instance,
                profile=C.PUBLICATION_ACTION_PROFILE,
                lam=C.PUBLICATION_LAMBDA,
                alpha=alpha,
            )

            reused = None

        conc = (
            p.get(
                "recommended_revised_concentration"
            )
            if p.get("optimal")
            else None
        )

        payload = {
            "alpha": alpha,
            "proposed": p,
            "concentration": conc,
            "economic_retention_recommended_vs_planned":
                _retention(
                    p,
                    "RECOMMENDED_REVISED",
                    "PLANNED",
                ),
        }

        _write_cell(
            path,
            identity,
            payload,
            reused_from=reused,
        )


def run_action_family(
    seed: int,
    ctx: SeedContext,
    matrix: dict,
    run_manifest: dict,
    primary: dict,
) -> None:
    from farmsync import config as C

    profiles = matrix["families"][
        "ACTION_ROBUSTNESS"
    ]["profiles"]

    primary_p = primary[
        "payload"
    ]["proposed"]

    for profile in profiles:
        path = cell_path(
            "ACTION_ROBUSTNESS",
            seed,
            f"profile={profile}",
        )

        params = {
            "profile": profile,
            "lambda_fixed":
                C.PUBLICATION_LAMBDA,
            "alpha_fixed":
                C.PUBLICATION_ALPHA,
        }

        identity = _cell_identity(
            run_manifest,
            "ACTION_ROBUSTNESS",
            seed,
            params,
        )

        if _existing_cell(
            path,
            identity,
        ) is not None:
            print(
                f"[SKIP] ACTION seed={seed} "
                f"profile={profile}"
            )
            continue

        if profile == C.PUBLICATION_ACTION_PROFILE:
            p = primary_p
            reused = str(
                cell_path(
                    "PRIMARY",
                    seed,
                ).relative_to(project_root())
            )
        else:
            print(
                f"[RUN ] ACTION seed={seed} "
                f"profile={profile}"
            )

            p = _proposed_summary(
                seed=seed,
                instance=ctx.instance,
                profile=profile,
                lam=C.PUBLICATION_LAMBDA,
                alpha=C.PUBLICATION_ALPHA,
            )

            reused = None

        payload = {
            "profile": profile,
            "proposed": p,
            "tiers":
                p.get("tiers"),
            "consent_coverage_final":
                p.get(
                    "consent_coverage_final"
                ),
            "disruption":
                _disruption_metrics(p),
        }

        _write_cell(
            path,
            identity,
            payload,
            reused_from=reused,
        )


def run_uncertainty_family(
    seed: int,
    matrix: dict,
    run_manifest: dict,
) -> None:
    from farmsync.proposed import uncertainty as U

    conditions = matrix["families"][
        "UNCERTAINTY"
    ]["conditions"]

    for condition in conditions:
        path = cell_path(
            "UNCERTAINTY",
            seed,
            f"condition={condition}",
        )

        params = {
            "condition": condition,
        }

        identity = _cell_identity(
            run_manifest,
            "UNCERTAINTY",
            seed,
            params,
        )

        if _existing_cell(
            path,
            identity,
        ) is not None:
            print(
                f"[SKIP] UNCERTAINTY seed={seed} "
                f"condition={condition}"
            )
            continue

        print(
            f"[RUN ] UNCERTAINTY seed={seed} "
            f"condition={condition}"
        )

        out = U.run_uncertainty_condition(
            seed,
            condition,
            run_proposed=True,
        )

        if (
            out.get("proposed", {}).get("optimal")
            and not out["proposed"].get(
                "realisation_hash_match"
            )
        ):
            raise RuntimeError(
                "Proposed/baseline uncertainty realisation "
                "hash mismatch"
            )

        _write_cell(
            path,
            identity,
            {
                "uncertainty": out,
            },
        )


def _scalability_payload(
    seed: int,
    ctx: SeedContext,
) -> dict:
    from farmsync import config as C

    b1 = ctx.b1()
    b2 = ctx.b2()
    b3 = ctx.b3(
        C.PUBLICATION_EPSILON
    )

    proposed = _proposed_summary(
        seed=seed,
        instance=ctx.instance,
        profile=C.PUBLICATION_ACTION_PROFILE,
        lam=C.PUBLICATION_LAMBDA,
        alpha=C.PUBLICATION_ALPHA,
    )

    return {
        "n_farmers": ctx.n_farmers,
        "instance": ctx.instance["record"],
        "methods": {
            "B1":
                _baseline_summary(
                    "B1",
                    b1,
                    ctx,
                ),
            "B2":
                _baseline_summary(
                    "B2",
                    b2,
                    ctx,
                ),
            "B3":
                _baseline_summary(
                    "B3",
                    b3,
                    ctx,
                ),
            "PROPOSED":
                proposed,
        },
    }


def run_scalability_family(
    seed: int,
    ctx500: SeedContext,
    matrix: dict,
    run_manifest: dict,
    primary: dict,
) -> None:
    values = matrix["families"][
        "SCALABILITY"
    ]["n_farmers_values"]

    for n in values:
        n = int(n)

        path = cell_path(
            "SCALABILITY",
            seed,
            f"n_farmers={n}",
        )

        params = {
            "n_farmers": n,
            "population_semantics":
                "total generated synthetic farmers",
        }

        identity = _cell_identity(
            run_manifest,
            "SCALABILITY",
            seed,
            params,
        )

        if _existing_cell(
            path,
            identity,
        ) is not None:
            print(
                f"[SKIP] SCALABILITY seed={seed} "
                f"n={n}"
            )
            continue

        if n == 500:
            p = primary["payload"]

            payload = {
                "n_farmers": 500,
                "instance": p["instance"],
                "methods": {
                    **p["baselines"],
                    "PROPOSED":
                        p["proposed"],
                },
            }

            reused = str(
                cell_path(
                    "PRIMARY",
                    seed,
                ).relative_to(project_root())
            )

        else:
            print(
                f"[RUN ] SCALABILITY seed={seed} "
                f"n={n}"
            )

            ctx = SeedContext(
                seed,
                n_farmers=n,
            )

            payload = _scalability_payload(
                seed,
                ctx,
            )

            reused = None

        _write_cell(
            path,
            identity,
            payload,
            reused_from=reused,
        )


def _load_operational_data() -> None:
    from farmsync.ingest import operational as opdata

    processed = (
        project_root()
        / "data"
        / "farmsync"
        / "processed"
    )

    # Explicitly load the existing frozen derivative.
    # No ingest/generation pipeline is called here.
    opdata.load(
        str(processed)
    )

    if not opdata.is_loaded():
        raise RuntimeError(
            "Operational processed data failed to load"
        )


def execute(
    *,
    family: str = "ALL",
    seeds: list[int] | None = None,
) -> None:
    env = validate_environment(
        require_clean=True,
    )

    matrix = env["matrix"]
    frozen_seeds = env[
        "reproducibility"
    ]["seeds"]

    if seeds is None:
        selected_seeds = list(
            frozen_seeds
        )
    else:
        bad = [
            s
            for s in seeds
            if s not in frozen_seeds
        ]

        if bad:
            raise RuntimeError(
                "Requested seed is not in frozen Final30 set: "
                + ", ".join(map(str, bad))
            )

        selected_seeds = list(
            seeds
        )

    if family != "ALL" and family not in FAMILY_ORDER:
        raise RuntimeError(
            f"Unknown family: {family}"
        )

    selected_families = (
        set(FAMILY_ORDER)
        if family == "ALL"
        else {family}
    )

    run_manifest = ensure_run_manifest(
        env
    )

    _load_operational_data()

    for i, seed in enumerate(
        selected_seeds,
        start=1,
    ):
        print()
        print(
            f"=== FINAL30 seed {seed} "
            f"({i}/{len(selected_seeds)}) ==="
        )

        needs_500 = bool(
            selected_families
            - {"UNCERTAINTY"}
        )

        ctx500 = (
            SeedContext(seed, 500)
            if needs_500
            else None
        )

        primary = None

        need_primary = bool(
            selected_families
            & {
                "PRIMARY",
                "LAMBDA_STABILITY",
                "ALPHA_CONCENTRATION",
                "ACTION_ROBUSTNESS",
                "SCALABILITY",
            }
        )

        if need_primary:
            primary = ensure_primary(
                seed,
                ctx500,
                matrix,
                run_manifest,
            )

        if "EPSILON_SENSITIVITY" in selected_families:
            run_epsilon_family(
                seed,
                ctx500,
                matrix,
                run_manifest,
            )

        if "LAMBDA_STABILITY" in selected_families:
            run_lambda_family(
                seed,
                ctx500,
                matrix,
                run_manifest,
                primary,
            )

        if "ALPHA_CONCENTRATION" in selected_families:
            run_alpha_family(
                seed,
                ctx500,
                matrix,
                run_manifest,
                primary,
            )

        if "ACTION_ROBUSTNESS" in selected_families:
            run_action_family(
                seed,
                ctx500,
                matrix,
                run_manifest,
                primary,
            )

        if "UNCERTAINTY" in selected_families:
            run_uncertainty_family(
                seed,
                matrix,
                run_manifest,
            )

        if "SCALABILITY" in selected_families:
            run_scalability_family(
                seed,
                ctx500,
                matrix,
                run_manifest,
                primary,
            )


def check() -> dict:
    env = validate_environment(
        require_clean=False,
    )

    print("FarmSync Final30 readiness")
    print("--------------------------")
    print(
        "HEAD:",
        env["current_commit"],
    )
    print(
        "tracked tree clean:",
        env["tracked_tree_clean"],
    )
    print(
        "matrix SHA256:",
        env["matrix_sha256"],
    )
    print(
        "frozen seeds:",
        env["reproducibility"]["seed_count"],
    )
    print(
        "frozen dataset files verified:",
        env["datasets"]["dataset_file_count"],
    )
    print(
        "dataset attestation:",
        env["datasets"]["dataset_attestation_sha256"],
    )
    print(
        "planned result cells:",
        env["planned_cells"],
    )
    print(
        "solver execution:",
        "NONE",
    )
    print(
        "LLM execution:",
        "NONE",
    )

    return env
