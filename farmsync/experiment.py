"""
Paired-instance experiment harness (built; the full 30-replication Proposed run is
NOT executed here).

Guarantees:
  * for each frozen master seed, the (farmers, plots) instance is generated exactly
    once and reused by B1/B2/B3 and every Proposed ablation;
  * shared stochastic mechanisms draw from the frozen RNG substreams so comparable
    variants receive identical scenario realizations;
  * instance/config/run identifiers and hashes are saved for reproducibility.
"""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

from .generate import generate_dataset, DATASET_VERSION
from .config import CANONICAL_B3_EPSILON, FORMULATION_VERSION, FAIRNESS_VERSION

SEEDS_FILE = "results/farmsync/audit/replication_seeds.json"
RNG_FILE = "results/farmsync/audit/rng_streams.json"


def project_root() -> Path:
    """Repository/project root, derived portably from this file's location.

    farmsync/experiment.py lives at <root>/farmsync/experiment.py, so the root is two
    parents up. Works identically on Windows and Linux and never hardcodes an absolute
    path. Frozen audit artifacts resolve as <root>/results/farmsync/audit/...
    """
    return Path(__file__).resolve().parents[1]


def _resolve(base, rel) -> str:
    """Join a project-relative artifact path onto `base` (default: project_root()).
    pathlib normalises separators, so no mixed sandbox/OS path fragments are produced."""
    root = project_root() if base is None else Path(base)
    return str(root / rel)


def instance_hash(farmers, plots):
    h = hashlib.sha256()
    for f in sorted(farmers, key=lambda x: x.farmer_id):
        h.update(f"{f.farmer_id}|{f.region_id}|{round(f.total_area_ha,3)}|"
                 f"{round(f.cultivation_budget,1)}|{round(f.labour_capacity,1)}\n".encode())
    for p in sorted(plots, key=lambda x: x.plot_id):
        h.update(f"{p.plot_id}|{p.farmer_id}|{p.region_id}|{round(p.area_ha,3)}|"
                 f"{p.active_season.value}\n".encode())
    return h.hexdigest()[:16]


def build_instance(seed, tightness="base", n_farmers=500):
    """Generate the exogenous instance exactly once for a master seed."""
    farmers, plots, crops, regions, manifest, prov, *rest = generate_dataset(
        master_seed=seed, n_farmers=n_farmers, budget_tightness=tightness)
    ih = instance_hash(farmers, plots)
    record = {"master_seed": seed, "tightness": tightness, "n_farmers": n_farmers,
              "dataset_version": DATASET_VERSION, "instance_hash": ih,
              "n_plots": len(plots)}
    return {"farmers": farmers, "plots": plots, "crops": crops,
            "regions": regions, "record": record}


def load_rng_streams(base=None):
    """Load frozen RNG substreams. base defaults to the project root (portable);
    an explicit base is still honoured for callers that intentionally supply one."""
    with open(_resolve(base, RNG_FILE)) as f:
        return json.load(f)


def load_seeds(base=None):
    with open(_resolve(base, SEEDS_FILE)) as f:
        return json.load(f)["replication_seeds"]


def substream(seed, stream, base=None):
    """Frozen paired sub-seed for a shared stochastic mechanism (same across variants).
    For seeds in the frozen 30-seed replication set, returns the stored value. For the
    canonical dev seed (not in that set), derives via the SAME documented formula
    sha256('{master}:{stream}') mod 2^31 so it is reproducible and consistent.
    base defaults to the project root (portable); explicit base still honoured."""
    import hashlib
    streams = load_rng_streams(base)["per_seed_substreams"]
    if str(seed) in streams:
        return streams[str(seed)][stream]
    return int(hashlib.sha256(f"{seed}:{stream}".encode()).hexdigest(), 16) % (2 ** 31)


def run_record(model, res, instance):
    """Common run-metadata schema across models. epsilon = None for B1/B2."""
    sv = getattr(res, "solver", {}) or {}
    return {
        "model": model,
        "epsilon": sv.get("epsilon"),                       # None / n.a. for B1, B2
        "fairness_version": FAIRNESS_VERSION,
        "formulation_version": sv.get("formulation_version", FORMULATION_VERSION),
        "seed": instance["record"]["master_seed"],
        "instance_hash": instance["record"]["instance_hash"],
        "solver_status": sv.get("status"),
        "runtime_s": sv.get("runtime_s"),
        "min_normalized_return": sv.get("min_normalized_return"),  # B3 only
    }


def run_baselines_on(instance, run_b1_ilp, run_b2_ilp, run_b3_ilp, epsilon=None):
    """Run the ILP baseline family on ONE shared instance. Model fns injected to keep
    the harness free of solver imports at module load. B3 uses the canonical epsilon
    unless an explicit sensitivity value is passed."""
    if epsilon is None:
        epsilon = CANONICAL_B3_EPSILON
    f, plots, crops = instance["farmers"], instance["plots"], instance["crops"]
    b1 = run_b1_ilp(f, plots, crops)
    b2 = run_b2_ilp(f, plots, crops)
    b3 = run_b3_ilp(f, plots, crops, epsilon=epsilon)
    return {"B1": b1, "B2": b2, "B3": b3}
