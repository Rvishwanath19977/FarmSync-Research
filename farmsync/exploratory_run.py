"""
FarmSync — SAFE INTERACTIVE EXPLORATORY RUN engine.

Scope + safety contract
-----------------------
* A run is created only by an EXPLICIT POST. GET / page load / inspection run ZERO solver calls and
  never create or mutate a run.
* Runs are stored ONLY under results/farmsync/exploratory/<run_id>/. This engine NEVER reads for
  mutation, and NEVER writes, any publication / development-checkpoint / P1/P3/P6 / frontier /
  replication artifact. Those remain byte-identical.
* This is a DETERMINISTIC, commitment-aware exploratory engine — NOT the frozen B3 MILP and NOT a
  publication result. Crop choice comes from deterministic rules over the activated dataset + the
  built-in crop economics (expected value = yield*price - cost, gated by plot feasibility). The LLM
  never chooses crops. Results are labelled exploratory everywhere.
* It is honest about what it is: a minimal custom upload lacks the agronomic attributes the B3 MILP
  needs, so the exploratory engine uses the deterministic recommendation for both built-in and custom
  datasets, under one coherent provenance, rather than fabricating optimiser inputs.

Config is recorded (not retuned): epsilon=0.95, lambda=0.05, alpha=0.40, action-consent-v1.
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
import uuid

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUN_ROOT = os.path.join(_BASE, "results", "farmsync", "exploratory")
_BUILTIN_DIR = os.path.join(_BASE, "data", "farmsync", "builtin")
_PROCESSED_DIR = os.path.join(_BASE, "data", "farmsync", "processed")

EXPLORATORY_CONFIG = {
    "config_version": "farmsync-exploratory-config-v1",
    "epsilon": 0.95, "lambda": 0.05, "alpha": 0.40,
    "action_protocol": "action-consent-v1",
    "engine": "deterministic-exploratory-v1",
    "note": "Deterministic, commitment-aware exploratory engine. NOT the frozen B3 MILP; NOT a "
            "publication result.",
}

SUPPORTED_ACTIONS = ["ACCEPT", "REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW"]


# --------------------------------------------------------------------------- #
# small CSV helpers (read-only over built-in economics; never over frozen replay artifacts)
# --------------------------------------------------------------------------- #
def _read_csv_text(text):
    return list(csv.DictReader(io.StringIO(text)))


def _read_builtin(name):
    p = os.path.join(_BUILTIN_DIR, name)
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _num(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _ensure_operational_data():
    """Load the existing processed scientific parameter tables for interactive
    feasibility/economic calculations.

    READ-ONLY: this loads existing processed CSVs only. It does not regenerate
    data and does not modify frozen publication artifacts. Missing data fails
    loudly instead of silently falling back to legacy economics.
    """
    from farmsync.ingest import operational as opdata

    if opdata.is_loaded():
        return

    required = (
        "yield_state.csv",
        "cost_state.csv",
        "market_price_state.csv",
        "absorption_proxy.csv",
    )

    missing = [
        name for name in required
        if not os.path.isfile(os.path.join(_PROCESSED_DIR, name))
    ]

    if missing:
        raise RuntimeError(
            "FarmSync processed operational data unavailable: "
            + ", ".join(missing)
        )

    opdata.load(_PROCESSED_DIR)


# --------------------------------------------------------------------------- #
# built-in crop economics (expected value per crop x region x season) + feasibility
# --------------------------------------------------------------------------- #






def _crop_name_map():
    return {r.get("crop_id"): (r.get("crop_name") or r.get("crop_id"))
            for r in _read_builtin("crops.csv")}


# --------------------------------------------------------------------------- #
# run storage
# --------------------------------------------------------------------------- #
def _run_dir(run_id):
    return os.path.join(_RUN_ROOT, run_id)


def _safe_run_id(run_id):
    # only our generated ids (hex + 'run-') are valid; blocks path traversal
    return isinstance(run_id, str) and run_id.startswith("run-") and run_id[4:].isalnum()


def _load_run(run_id):
    if not _safe_run_id(run_id):
        return None
    p = os.path.join(_run_dir(run_id), "run.json")
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_run(run):
    d = _run_dir(run["run_id"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "run.json"), "w", encoding="utf-8") as f:
        json.dump(run, f, indent=2)
    return run


# --------------------------------------------------------------------------- #
# deterministic recommendation (crop choice = optimiser/rules, never the LLM)
# --------------------------------------------------------------------------- #


def _snapshot_from_pkg(pkg):
    """Build a run snapshot (farmers, plots) from an activated dataset package (built-in or custom)."""
    farmers = [{"farmer_id": r.get("farmer_id"), "collective_id": r.get("collective_id"),
                "region_id": r.get("region_id"), "season": r.get("season")}
               for r in pkg.rows("farmers.csv")]
    plots = [{"plot_id": r.get("plot_id"), "farmer_id": r.get("farmer_id"),
              "region_id": r.get("region_id"), "area_ha": _num(r.get("area_ha"), 1.0)}
             for r in pkg.rows("plots.csv")]
    # region/season for a plot: prefer plot.region_id + owning farmer's season
    fseason = {f["farmer_id"]: f["season"] for f in farmers}
    for p in plots:
        p["season"] = fseason.get(p["farmer_id"])
    return farmers, plots


def dataset_fingerprint(farmers, plots):
    import hashlib
    h = hashlib.sha256()
    for f in sorted(farmers, key=lambda x: x["farmer_id"]):
        h.update((f["farmer_id"] + "|" + str(f.get("collective_id")) + "|" + str(f.get("region_id")) + ";").encode())
    for p in sorted(plots, key=lambda x: x["plot_id"]):
        h.update((p["plot_id"] + "|" + p["farmer_id"] + "|" + str(p.get("area_ha")) + ";").encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# public API — all mutations are POST-driven from the routes layer
# --------------------------------------------------------------------------- #
def _dataset_snapshot_from_pkg(pkg):
    """Immutable, lightweight snapshot of the FULL selected dataset universe (does NOT mutate the pkg).
    Captures farmer + plot identity/area needed for Final Plan completeness, reconciliation and fairness."""
    if pkg is None or not pkg.has("farmers.csv") or not pkg.has("plots.csv"):
        return None
    farmers = [{"farmer_id": r.get("farmer_id"), "collective_id": r.get("collective_id"),
                "region_id": r.get("region_id"), "season": r.get("season")}
               for r in pkg.rows("farmers.csv")]
    plots = [{"plot_id": r.get("plot_id"), "farmer_id": r.get("farmer_id"),
              "region_id": r.get("region_id"), "area_ha": _num(r.get("area_ha"))}
             for r in pkg.rows("plots.csv")]
    ncoll = len(pkg.rows("collectives.csv")) if pkg.has("collectives.csv") else None
    import hashlib
    h = hashlib.sha256()
    for f in sorted(farmers, key=lambda x: x["farmer_id"] or ""):
        h.update((str(f["farmer_id"]) + "|").encode())
    for p in sorted(plots, key=lambda x: x["plot_id"] or ""):
        h.update((str(p["plot_id"]) + "|" + str(p["area_ha"]) + ";").encode())
    return {"farmers": farmers, "plots": plots, "n_farmers": len(farmers), "n_plots": len(plots),
            "n_collectives": ncoll, "hash": h.hexdigest()[:16]}


def _dataset_snapshot_from_custom(snap):
    """Reuse the exact activated custom snapshot as the working-run dataset universe."""
    if not snap:
        return None
    farmers = [{"farmer_id": r.get("farmer_id"), "collective_id": r.get("collective_id"),
                "region_id": r.get("region_id"), "season": r.get("season")}
               for r in snap.get("farmers", [])]
    plots = [{"plot_id": r.get("plot_id"), "farmer_id": r.get("farmer_id"),
              "region_id": r.get("region_id"), "area_ha": _num(r.get("area_ha"))}
             for r in snap.get("plots", [])]
    return {"farmers": farmers, "plots": plots, "n_farmers": len(farmers), "n_plots": len(plots),
            "n_collectives": len(snap.get("collectives", [])) or None, "hash": snap.get("hash")}


def _gini(values):
    """Standard Gini over a list of non-negative values (includes zeros). Returns None if undefined."""
    xs = [float(v) for v in values if v is not None]
    n = len(xs)
    if n == 0:
        return None
    s = sum(xs)
    if s <= 0:
        return 0.0                      # all-zero cohort -> perfectly equal (Gini 0) by convention
    xs.sort()
    cum = 0.0
    for i, x in enumerate(xs, 1):
        cum += i * x
    return (2.0 * cum) / (n * s) - (n + 1.0) / n


def _current_final_allocations(run):
    """Exact realised allocation identity for the stored final plan.

    Pure/read-only. Non-realised rows are deliberately absent.
    """
    out = []

    for rec in run.get("recommendations", []):
        if not rec.get("realised"):
            continue

        crop = rec.get("final_crop")
        cash = rec.get("final_cash")

        if not crop or cash is None:
            continue

        out.append({
            "farmer_id": rec["farmer_id"],
            "plot_id": rec["plot_id"],
            "final_crop": crop,
            "final_cash": cash,
        })

    return out


def _final_plan_identity_hash(allocations):
    """Hash identical to interactive_stress.final_plan_hash().

    Kept lightweight so GET /analysis does not execute the stress engine.
    """
    import hashlib

    rows = []

    for a in allocations:
        rows.append({
            "farmer_id": str(a["farmer_id"]),
            "plot_id": str(a["plot_id"]),
            "final_crop": str(a["final_crop"]).lower(),
            "final_cash": round(float(a["final_cash"]), 6),
        })

    rows.sort(
        key=lambda x: (
            x["farmer_id"],
            x["plot_id"],
            x["final_crop"],
            x["final_cash"],
        )
    )

    raw = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(raw).hexdigest()[:16]


def _interactive_uncertainty_view(run):
    """Read-only NOT_RUN / CURRENT / STALE analysis projection.

    Stale scientific metrics are never exposed as current-plan metrics.
    """
    expected_protocol = "interactive-stress-v1"

    saved = run.get("interactive_analysis")
    allocations = _current_final_allocations(run)

    current_hash = (
        _final_plan_identity_hash(allocations)
        if allocations
        else None
    )

    current_revision = run.get("final_plan_revision")
    current_dataset_hash = run.get("dataset_hash")

    if not saved:
        return {
            "available": False,
            "status": "NOT_RUN",
            "protocol_version": expected_protocol,
            "reason": (
                "Not evaluated for the current final plan. "
                "Run interactive stress analysis first."
            ),
            "current_final_plan_hash": current_hash,
            "current_final_plan_revision": current_revision,
        }

    matches = (
        saved.get("protocol_version") == expected_protocol
        and saved.get("dataset_hash") == current_dataset_hash
        and saved.get("final_plan_hash") == current_hash
        and saved.get("final_plan_revision") == current_revision
    )

    if not matches:
        return {
            "available": False,
            "status": "STALE",
            "protocol_version": expected_protocol,
            "reason": (
                "The saved interactive stress analysis belongs to an older "
                "final-plan revision or allocation. Run analysis again for "
                "the current final plan."
            ),
            "analysed_dataset_hash": saved.get("dataset_hash"),
            "current_dataset_hash": current_dataset_hash,
            "analysed_final_plan_hash": saved.get("final_plan_hash"),
            "current_final_plan_hash": current_hash,
            "analysed_final_plan_revision":
                saved.get("final_plan_revision"),
            "current_final_plan_revision": current_revision,
            "analysed_at": saved.get("generated_at"),
        }

    result = dict(saved.get("result") or {})

    result["available"] = True
    result["status"] = "CURRENT"
    result["analysed_at"] = saved.get("generated_at")

    return result


def _interactive_resilience_view(run):
    """Read-only NOT_RUN / CURRENT / STALE resilience projection.

    Uses the exact same final-plan identity as interactive stress.
    Stale resilience metrics are never exposed as current-plan metrics.
    """
    expected_protocol = "interactive-resilience-v1"

    saved = run.get("interactive_analysis")
    allocations = _current_final_allocations(run)

    current_hash = (
        _final_plan_identity_hash(allocations)
        if allocations
        else None
    )

    current_revision = run.get("final_plan_revision")
    current_dataset_hash = run.get("dataset_hash")

    # Older stress-only analysis records are valid historical records,
    # but resilience simply has not been run for them.
    if (
        not saved
        or not saved.get("resilience_result")
    ):
        return {
            "available": False,
            "status": "NOT_RUN",
            "protocol_version": expected_protocol,
            "reason": (
                "Not evaluated for the current final plan. "
                "Run interactive analysis first."
            ),
            "current_final_plan_hash": current_hash,
            "current_final_plan_revision":
                current_revision,
        }

    matches = (
        saved.get("resilience_protocol_version")
        == expected_protocol
        and saved.get("dataset_hash")
        == current_dataset_hash
        and saved.get("final_plan_hash")
        == current_hash
        and saved.get("final_plan_revision")
        == current_revision
    )

    if not matches:
        return {
            "available": False,
            "status": "STALE",
            "protocol_version": expected_protocol,
            "reason": (
                "The saved interactive resilience analysis "
                "belongs to an older final-plan revision or "
                "allocation. Run analysis again for the "
                "current final plan."
            ),
            "analysed_dataset_hash":
                saved.get("dataset_hash"),
            "current_dataset_hash":
                current_dataset_hash,
            "analysed_final_plan_hash":
                saved.get("final_plan_hash"),
            "current_final_plan_hash":
                current_hash,
            "analysed_final_plan_revision":
                saved.get("final_plan_revision"),
            "current_final_plan_revision":
                current_revision,
            "analysed_at":
                saved.get("generated_at"),
        }

    result = dict(
        saved.get("resilience_result") or {}
    )

    result["available"] = True
    result["status"] = "CURRENT"
    result["analysed_at"] = saved.get(
        "generated_at"
    )

    return result



def run_interactive_analysis(run_id):
    """POST-only execution of the current interactive analysis bundle.

    Both interactive-stress-v1 and interactive-resilience-v1 are evaluated
    against the exact same CURRENT FINAL_REALIZED allocation identity.

    Atomic rule:
      if either scientific component cannot be evaluated defensibly,
      no new analysis bundle is persisted.

    No publication artifact is substituted or modified.
    """
    run = _load_run(run_id)

    if not run:
        return {
            "available": False,
            "error": "run not found",
        }

    wf = workflow_state(run)

    if not wf["final_current"]:
        return {
            "available": False,
            "error": (
                "No current finalised plan. Finalise the "
                "consent-verified plan before running "
                "interactive analysis."
            ),
            "workflow": wf,
        }

    allocations = _current_final_allocations(
        run
    )

    if not allocations:
        return {
            "available": False,
            "error": (
                "The current final plan contains no "
                "realised allocations to analyse."
            ),
            "workflow": wf,
        }

    resolved = _resolve_objects(run)

    if resolved is None:
        return {
            "available": False,
            "error": (
                "Required agronomic inputs are missing "
                "for the current dataset; interactive "
                "analysis cannot be derived defensibly."
            ),
            "workflow": wf,
        }

    plots_by_id, farmer_by_id, _crops = (
        resolved
    )

    # Both interactive scientific layers use the same canonical
    # processed operational data. Never fall back silently.
    _ensure_operational_data()

    from farmsync.interactive_stress import (
        PROTOCOL_VERSION as STRESS_PROTOCOL_VERSION,
        analyse_fixed_final_plan as analyse_stress,
    )

    from farmsync.interactive_resilience import (
        PROTOCOL_VERSION as RESILIENCE_PROTOCOL_VERSION,
        analyse_fixed_final_plan as analyse_resilience,
    )

    stress_result = analyse_stress(
        allocations,
        plots_by_id,
        farmer_by_id,
        dataset_hash=run.get("dataset_hash"),
        final_plan_revision=run.get(
            "final_plan_revision"
        ),
    )

    if not stress_result.get("available"):
        return {
            "available": False,
            "error": stress_result.get(
                "reason",
                "Interactive stress analysis could "
                "not be evaluated.",
            ),
            "analysis_component": "uncertainty",
            "analysis": stress_result,
            "workflow": wf,
        }

    resilience_result = analyse_resilience(
        allocations,
        plots_by_id,
        dataset_hash=run.get("dataset_hash"),
        final_plan_revision=run.get(
            "final_plan_revision"
        ),
    )

    if not resilience_result.get("available"):
        return {
            "available": False,
            "error": resilience_result.get(
                "reason",
                "Interactive resilience analysis "
                "could not be evaluated.",
            ),
            "analysis_component": "resilience",
            "analysis": resilience_result,
            "workflow": wf,
        }

    expected_hash = (
        _final_plan_identity_hash(
            allocations
        )
    )

    current_dataset_hash = run.get(
        "dataset_hash"
    )
    current_revision = run.get(
        "final_plan_revision"
    )

    # Both scientific engines MUST prove they analysed
    # exactly the same plan identity.
    for name, result in (
        ("uncertainty", stress_result),
        ("resilience", resilience_result),
    ):
        if (
            result.get("final_plan_hash")
            != expected_hash
        ):
            return {
                "available": False,
                "error": (
                    f"{name} final-plan identity "
                    "does not match the working-plan "
                    "session. Analysis was not saved."
                ),
                "workflow": wf,
            }

        if (
            result.get("dataset_hash")
            != current_dataset_hash
        ):
            return {
                "available": False,
                "error": (
                    f"{name} dataset identity does "
                    "not match the working-plan "
                    "session. Analysis was not saved."
                ),
                "workflow": wf,
            }

        if (
            result.get("final_plan_revision")
            != current_revision
        ):
            return {
                "available": False,
                "error": (
                    f"{name} final-plan revision does "
                    "not match the working-plan "
                    "session. Analysis was not saved."
                ),
                "workflow": wf,
            }

    generated_at = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(),
    )

    run["interactive_analysis"] = {
        "analysis_kind":
            "fixed_final_plan_analysis_bundle",

        "analysis_bundle_version":
            "interactive-analysis-bundle-v1",

        # Backward-compatible alias retained for the
        # existing uncertainty state reader/tests.
        "protocol_version":
            STRESS_PROTOCOL_VERSION,

        "uncertainty_protocol_version":
            STRESS_PROTOCOL_VERSION,

        "resilience_protocol_version":
            RESILIENCE_PROTOCOL_VERSION,

        "dataset_hash":
            current_dataset_hash,

        "final_plan_hash":
            expected_hash,

        "final_plan_revision":
            current_revision,

        "generated_at":
            generated_at,

        # Backward-compatible stress-result field.
        "result":
            stress_result,

        "resilience_result":
            resilience_result,
    }

    _save_run(run)

    return {
        "available": True,
        "status": "CURRENT",

        "run_id": run_id,

        "analysis_bundle_version":
            "interactive-analysis-bundle-v1",

        # Existing API field retained.
        "protocol_version":
            STRESS_PROTOCOL_VERSION,

        "uncertainty_protocol_version":
            STRESS_PROTOCOL_VERSION,

        "resilience_protocol_version":
            RESILIENCE_PROTOCOL_VERSION,

        "dataset_hash":
            current_dataset_hash,

        "final_plan_hash":
            expected_hash,

        "final_plan_revision":
            current_revision,

        "generated_at":
            generated_at,

        "uncertainty": {
            **stress_result,
            "status": "CURRENT",
            "analysed_at": generated_at,
        },

        "resilience": {
            **resilience_result,
            "status": "CURRENT",
            "analysed_at": generated_at,
        },

        "workflow":
            workflow_state(run),
    }



def analysis(run):
    """Read-only Analyse of the CURRENT FINAL_REALIZED working plan, projected over the FULL selected
    dataset universe. No CBC/PuLP, no mutation. Requires final_current; otherwise returns unavailable.
    Frozen recorded-development results are NEVER substituted here."""
    wf = workflow_state(run)
    if not wf["final_current"]:
        return {"available": False, "reason": "No current finalised plan. Finalise the consent-verified "
                                              "plan first; if you changed upstream state, re-finalise.",
                "workflow": wf}
    dsnap = run.get("dataset_snapshot")
    recs = run.get("recommendations", [])
    rec_by_plot = {r["plot_id"]: r for r in recs}
    # ---- FULL dataset universe (built-in 500/911 or exact custom) ----
    if dsnap and dsnap.get("plots"):
        univ_plots = dsnap["plots"]
        univ_farmers = dsnap["farmers"]
    else:                               # defensive fallback: offer subset only
        univ_plots = [{"plot_id": r["plot_id"], "farmer_id": r["farmer_id"], "area_ha": r.get("area_ha")} for r in recs]
        seen = {}
        for r in recs:
            seen.setdefault(r["farmer_id"], {"farmer_id": r["farmer_id"]})
        univ_farmers = list(seen.values())
    total_plots = len(univ_plots)
    total_farmers = len(univ_farmers)

    # ---- per-plot final-row projection over the FULL universe ----
    rows = []
    realised_plots = 0
    not_realised = 0
    reason_counts = {}
    comp_plots = {}                     # realised crop composition (plots)
    comp_area = {}                      # realised crop composition (area)
    farmer_realised_cash = {f["farmer_id"]: 0.0 for f in univ_farmers}
    farmer_operated_area = {f["farmer_id"]: 0.0 for f in univ_farmers}
    area_available = True
    # consent-eligible = offer rows that could be realised via a consent path (matches finalise's
    # n_eligible): a changed row (renewed-consent path) OR an unchanged INITIAL_ACCEPT.
    n_consent_eligible = 0
    for rec in recs:
        if rec.get("changed") or (_replan_effective(run, rec) == "ACCEPT"):
            n_consent_eligible += 1

    for p in univ_plots:
        fid = p.get("farmer_id"); pid = p.get("plot_id")
        area = p.get("area_ha")
        if area is None:
            area_available = False
        else:
            farmer_operated_area[fid] = farmer_operated_area.get(fid, 0.0) + float(area)
        rec = rec_by_plot.get(pid)
        if rec is None:
            # no initial offer/recommendation existed for this plot
            rows.append({"farmer_id": fid, "plot_id": pid, "final_crop": None,
                         "consent_basis": None, "realised": False, "reason": "NO_INITIAL_OFFER"})
            not_realised += 1
            reason_counts["NO_INITIAL_OFFER"] = reason_counts.get("NO_INITIAL_OFFER", 0) + 1
            continue
        if rec.get("realised"):
            realised_plots += 1
            crop = rec.get("final_crop")
            comp_plots[crop] = comp_plots.get(crop, 0) + 1
            if area is not None and crop:
                comp_area[crop] = comp_area.get(crop, 0.0) + float(area)
            cash = rec.get("final_cash") or 0.0
            farmer_realised_cash[fid] = farmer_realised_cash.get(fid, 0.0) + float(cash)
            rows.append({"farmer_id": fid, "plot_id": pid, "final_crop": crop,
                         "consent_basis": rec.get("consent_basis"), "realised": True, "reason": None})
        else:
            reason = _not_realised_reason(run, rec)
            not_realised += 1
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            rows.append({"farmer_id": fid, "plot_id": pid, "final_crop": None,
                         "consent_basis": None, "realised": False, "reason": reason})

    # ---- initial response history (OFFER rows only; effective per source) ----
    init = {k: 0 for k in ("ACCEPT", "REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW")}
    n_offer = 0
    for rec in recs:
        n_offer += 1
        eff = _replan_effective(run, rec)
        if eff in init:
            init[eff] += 1
    n_no_offer = total_plots - n_offer

    # ---- renewed-consent outcomes (rows requiring renewed consent in the CURRENT replan) ----
    renewed = {"RENEWED_ACCEPT": 0, "RENEWED_REJECT": 0, "RENEWED_NO_RESPONSE": 0}
    n_requires = 0
    for rec in recs:
        if rec.get("changed") and rec.get("requires_renewed_consent"):
            n_requires += 1
            v = _valid_current_consent(run, rec)
            if v == "ACCEPT":
                renewed["RENEWED_ACCEPT"] += 1
            elif v == "REJECT":
                renewed["RENEWED_REJECT"] += 1
            elif v == "NO_RESPONSE":
                renewed["RENEWED_NO_RESPONSE"] += 1

    # ---- fairness-v2 (all selected farmers incl. zeros) ----
    per_ha = []
    abs_cash = []
    participants = 0
    zero_farmers = 0
    for f in univ_farmers:
        fid = f["farmer_id"]
        cash = farmer_realised_cash.get(fid, 0.0)
        oa = farmer_operated_area.get(fid, 0.0)
        abs_cash.append(cash)
        if cash > 0:
            participants += 1
        else:
            zero_farmers += 1
        if area_available and oa > 0:
            per_ha.append(cash / oa)
        elif area_available:
            per_ha.append(0.0)
    fairness = {
        "all_farmer_abs_cash_gini": _gini(abs_cash),
        "all_farmer_per_ha_gini": (_gini(per_ha) if area_available else None),
        "participant_only_per_ha_gini": (_gini([v for v, f in zip(per_ha, univ_farmers)
                                                if farmer_realised_cash.get(f["farmer_id"], 0.0) > 0])
                                         if area_available else None),
        "n_farmers": total_farmers, "n_participants": participants,
        "n_zero_realisation_farmers": zero_farmers,
        "per_ha_unavailable_reason": (None if area_available else "Not available — plot area_ha missing for this dataset"),
    }

    # ---- concentration (descriptive, over REALISED allocations only) ----
    concentration = _concentration(comp_plots, comp_area, realised_plots, area_available)

    final_cash = round(sum(farmer_realised_cash.values()))
    realised_area = round(sum(comp_area.values()), 3) if area_available else None

    payload = {
        "available": True,
        "provenance": "CURRENT_WORKING_FINAL_PLAN",
        "run_id": run.get("run_id"),
        "final_plan_revision": run.get("final_plan_revision"),
        "response_rev": run.get("response_rev"),
        "replan_anchor": run.get("replan_anchor"),
        "dataset_source": run.get("source"),
        "dataset_kind": run.get("source_kind"),
        "dataset_hash": run.get("dataset_hash"),
        "created": run.get("created"),
        "finalised_at": (run.get("final_anchor") or {}).get("finalised_at"),
        "engine": run.get("engine"),
        "config_version": (run.get("config") or {}).get("config_version"),
        "overview": {
            "total_farmers": total_farmers, "total_plots": total_plots,
            "offered_plots": n_offer, "no_offer_plots": n_no_offer,
            "realised_plots": realised_plots, "not_realised_plots": not_realised,
            "farmers_with_realised": sum(1 for f in univ_farmers if farmer_realised_cash.get(f["farmer_id"], 0.0) > 0),
            "farmers_without_realised": sum(1 for f in univ_farmers if farmer_realised_cash.get(f["farmer_id"], 0.0) <= 0),
            "final_realised_cash": final_cash,
            "final_realised_area": realised_area,
            # §3: explicit, non-ambiguous denominators (never call these all "consent coverage").
            # affirmative_consent_coverage = realised / consent-ELIGIBLE (matches finalisation semantics);
            # REJECT / NO_RESPONSE are explicit outcomes, NOT affirmative consent.
            "affirmative_consent_coverage": (realised_plots / n_consent_eligible) if n_consent_eligible else 0.0,
            "realisation_rate_offered": (realised_plots / n_offer) if n_offer else 0.0,
            "realisation_rate_all_plots": (realised_plots / total_plots) if total_plots else 0.0,
            "n_consent_eligible": n_consent_eligible,
        },
        "initial_response_history": init,
        "n_offer_rows": n_offer, "n_no_offer_rows": n_no_offer,
        "renewed_consent_outcomes": renewed, "n_requires_renewed_consent": n_requires,
        "realised": realised_plots, "not_realised": not_realised,
        "not_realised_reasons": reason_counts,
        "crop_composition_plots": comp_plots,
        "crop_composition_area": (comp_area if area_available else None),
        "fairness": fairness,
        "concentration": concentration,
        # frozen uncertainty-v1 / resilience require a recorded Stage-5 allocation / reoptimisation the
        # working plan did not run; do NOT fabricate. Explicit unavailable per scientific honesty.
        "uncertainty": {"available": False,
                        "reason": "Not available — uncertainty-v1 evaluates the frozen recorded Stage-5 "
                                  "allocation/scenarios; applying it to this working final plan without "
                                  "reoptimisation or the recorded scenario mapping is not defensible."},
        "resilience": {"available": False,
                       "reason": "Not available — resilience evaluation is defined over the frozen "
                                 "recorded plan / backup pipeline; it is not derivable for this working "
                                 "final plan without unsupported reoptimisation."},
    }
    payload["uncertainty"] = _interactive_uncertainty_view(run)
    payload["resilience"] = _interactive_resilience_view(run)
    payload["integrity"] = _analysis_integrity(payload, wf["n_consent_pending"], run.get("final_plan_revision"))
    return payload


def _not_realised_reason(run, rec):
    """Derive a NOT-realised reason from ACTUAL current state (never invented)."""
    if rec.get("changed") and rec.get("requires_renewed_consent"):
        v = _valid_current_consent(run, rec)
        if v == "REJECT":
            return "RENEWED_REJECT"
        if v == "NO_RESPONSE":
            return "RENEWED_NO_RESPONSE"
        return "OTHER_NOT_REALISED"     # should not occur at final_current (pending == 0)
    eff = _replan_effective(run, rec)
    if eff == "WITHDRAW":
        return "WITHDRAW"
    if eff == "REJECT":
        return "INITIAL_REJECT_NO_ALTERNATIVE"   # rejected but no defensible revised alternative
    if eff == "NO_RESPONSE":
        return "INITIAL_NO_RESPONSE"
    if eff is None:
        return "INITIAL_NO_RESPONSE"    # custom unset shouldn't reach final; classify honestly
    return "OTHER_NOT_REALISED"


def _concentration(comp_plots, comp_area, realised_plots, area_available):
    """Descriptive concentration over REALISED allocations only. alpha=0.40 is a FROZEN REFERENCE,
    NOT enforced by this working plan's mechanism."""
    ALPHA_REF = 0.40
    if realised_plots == 0:
        return {"available": False, "reason": "No realised allocations to describe."}
    # per-crop LPS = largest single farmer's share within the crop is not derivable from aggregate
    # composition alone; we report crop-share concentration (share of realised plots/area per crop) and
    # HHI over crop shares — the existing descriptive definition reusable without per-farmer joins here.
    basis = comp_area if (area_available and comp_area) else comp_plots
    total = sum(basis.values()) or 1.0
    shares = {k: (v / total) for k, v in basis.items()}
    hhi = sum(s * s for s in shares.values())
    max_share = max(shares.values()) if shares else 0.0
    per_crop = {k: round(s, 4) for k, s in sorted(shares.items(), key=lambda kv: -kv[1])}
    above = [k for k, s in shares.items() if s > ALPHA_REF]
    return {
        "available": True,
        "basis": "area" if (area_available and comp_area) else "plots",
        "active_realised_crops": len(basis),
        "max_crop_share": round(max_share, 4),
        "hhi_crop_share": round(hhi, 4),
        "per_crop_share": per_crop,
        "alpha_reference": ALPHA_REF,
        "crops_above_reference": above,
        "note": "Descriptive comparison against the frozen \u03b1=0.40 reference. The working plan uses "
                "deterministic action-consent + feasibility; it did NOT run the concentration-control "
                "MILP, so \u03b1 is a reference, not an enforced constraint.",
    }


def _analysis_integrity(p, n_pending, current_final_plan_revision):
    """Verify ALL reconciliation invariants against AUTHORITATIVE values (no placeholders). Returns
    {ok, failures[]} so the UI withholds every metric when inconsistent."""
    o = p["overview"]; fails = []
    if o["realised_plots"] + o["not_realised_plots"] != o["total_plots"]:
        fails.append("realised+not_realised != total_plots")
    if o["offered_plots"] + o["no_offer_plots"] != o["total_plots"]:
        fails.append("offered+no_offer != total_plots")
    if sum(p["initial_response_history"].values()) != p["n_offer_rows"]:
        fails.append("initial_response_history != n_offer_rows")
    if sum(p["renewed_consent_outcomes"].values()) != p["n_requires_renewed_consent"]:
        fails.append("renewed outcomes != rows requiring renewed consent")
    if n_pending != 0:
        fails.append("authoritative renewed-consent pending != 0 at final_current")
    if sum(p["not_realised_reasons"].values()) != o["not_realised_plots"]:
        fails.append("not_realised_reason_counts != not_realised_plots")
    if sum(p["crop_composition_plots"].values()) != o["realised_plots"]:
        fails.append("crop composition plots != realised_plots")
    if p.get("final_plan_revision") != current_final_plan_revision:
        fails.append("analysis final_plan_revision != current run final_plan_revision")
    return {"ok": not fails, "failures": fails}


def final_rows(run, page, per, filt="realised"):
    """Read-only paginated Final Plan projection over the FULL selected dataset universe, with a filter
    (realised | not_realised | all). Returns authoritative counts for every filter. A plot with no
    initial offer -> final_crop None, realised False, reason NO_INITIAL_OFFER. No mutation, no solver."""
    dsnap = run.get("dataset_snapshot")
    recs = run.get("recommendations", [])
    rec_by_plot = {r["plot_id"]: r for r in recs}
    if dsnap and dsnap.get("plots"):
        univ = dsnap["plots"]
    else:
        univ = [{"plot_id": r["plot_id"], "farmer_id": r["farmer_id"]} for r in recs]

    def project(p):
        rec = rec_by_plot.get(p["plot_id"])
        if rec is None:
            return {"farmer_id": p.get("farmer_id"), "plot_id": p.get("plot_id"),
                    "final_crop": None, "consent_basis": None, "realised": False,
                    "reason": "NO_INITIAL_OFFER"}
        return {"farmer_id": rec["farmer_id"], "plot_id": rec["plot_id"],
                "final_crop": (rec.get("final_crop") if rec.get("realised") else None),
                "consent_basis": rec.get("consent_basis"),
                "realised": bool(rec.get("realised")),
                "reason": None if rec.get("realised") else _not_realised_reason(run, rec)}

    all_rows = [project(p) for p in univ]
    n_all = len(all_rows)
    n_realised = sum(1 for r in all_rows if r["realised"])
    n_not = n_all - n_realised
    counts = {"realised": n_realised, "not_realised": n_not, "all": n_all}

    if filt == "realised":
        rows_f = [r for r in all_rows if r["realised"]]
    elif filt == "not_realised":
        rows_f = [r for r in all_rows if not r["realised"]]
    else:
        filt = "all"
        rows_f = all_rows

    total = len(rows_f)
    pages = max(1, (total + per - 1) // per)
    page = min(max(1, page), pages)
    start = (page - 1) * per
    return {"available": True, "filter": filt, "counts": counts,
            "rows": rows_f[start:start + per], "page": page, "pages": pages, "total": total,
            "per_page": per, "first": (start + 1 if total else 0), "last": min(start + per, total),
            "final_current": workflow_state(run)["final_current"]}


def _canonical_builtin_recs():
    """Seed the built-in working plan from the CANONICAL stored plan + recorded responses.
    Reuses the existing artifact readers (initial_plan recommendations + farmers_list recorded
    response). This is the real FarmSync development plan, NOT the deterministic heuristic."""
    from farmsync import ui_adapter as _ui
    plan = _ui.initial_plan()
    if not plan.get("available"):
        return None
    resp = {}
    try:
        fl = _ui.farmers_list(limit=100000)
        for r in fl.get("farmers", []):
            resp[(r.get("farmer_id"), r.get("plot_id"))] = r.get("response")
    except Exception:
        pass
    recs = []
    for r in plan.get("recommendations", []):
        key = (r.get("farmer_id"), r.get("plot_id"))
        rs = (r.get("region_season") or ":").split(":")
        recs.append({"farmer_id": r.get("farmer_id"), "plot_id": r.get("plot_id"),
                     "region_id": rs[0] if rs else None,
                     "season": rs[1] if len(rs) > 1 else None,
                     "area_ha": None,
                     "crop_id": None, "crop": r.get("crop"),
                     "expected_value_per_ha": None, "cash": _num(r.get("cash")),
                     "recorded_response": resp.get(key)})
    return recs or None


def _custom_objects(snapshot):
    """Build real Plot/Farmer objects from an ACTIVATED custom snapshot's own agronomic columns
    (never any built-in Fxxxx plot data) + built-in crops. Returns (plots_by_id, farmer_by_id, crops)
    or None when the snapshot lacks the agronomic attributes real feasibility requires."""
    if not snapshot:
        return None
    from farmsync.experiment import build_instance
    from farmsync.schemas import (Plot, Farmer, Season, SoilGroup, SuitabilityClass, DrainageClass,
                                  IrrigationAccess, Exposure, HoldingCategory, ParticipationState)
    crops = build_instance(20260812)["crops"]           # borrow canonical crop objects only

    def _enum(E, v, default):
        try:
            return E(v)
        except Exception:
            try:
                return E[str(v).upper()]
            except Exception:
                return default
    plots_by_id, farmer_by_id = {}, {}
    try:
        for fr in snapshot.get("farmers", []):
            farmer_by_id[fr["farmer_id"]] = Farmer(
                farmer_id=fr["farmer_id"], collective_id=fr.get("collective_id") or "C?",
                region_id=fr.get("region_id"), season=_enum(Season, fr.get("season"), Season.KHARIF),
                holding_category=HoldingCategory.SMALL, total_area_ha=1.0,
                cultivation_budget=1e9, labour_capacity=1e9, minimum_projected_income=0.0,
                risk_tolerance=0.5, participation_state=ParticipationState.CONFIRMED,
                synthetic_seed=0, synthetic=True)
        for pl in snapshot.get("plots", []):
            fseason = farmer_by_id[pl["farmer_id"]].season.value if pl["farmer_id"] in farmer_by_id else "kharif"
            plots_by_id[pl["plot_id"]] = Plot(
                plot_id=pl["plot_id"], farmer_id=pl["farmer_id"], region_id=pl.get("region_id"),
                area_ha=_num(pl.get("area_ha"), 1.0),
                soil_group=_enum(SoilGroup, pl.get("soil_group"), None),
                soil_suitability_class=_enum(SuitabilityClass, pl.get("soil_suitability_class"), None),
                drainage_class=_enum(DrainageClass, pl.get("drainage_class"), None),
                irrigation_access=_enum(IrrigationAccess, pl.get("irrigation_access"), IrrigationAccess.RAINFED),
                available_water_m3=_num(pl.get("available_water_m3"), 0.0),
                previous_crop=pl.get("previous_crop") or None,
                rotation_group=pl.get("rotation_group") or None,
                flood_exposure=_enum(Exposure, pl.get("flood_exposure"), Exposure.LOW),
                drought_exposure=_enum(Exposure, pl.get("drought_exposure"), Exposure.LOW),
                waterlogging_exposure=_enum(Exposure, pl.get("waterlogging_exposure"), Exposure.LOW),
                hazard_zone=pl.get("hazard_zone") or "HZ?",
                active_season=_enum(Season, pl.get("active_season") or fseason, Season.KHARIF),
                synthetic_seed=0, synthetic=True)
    except Exception:
        return None
    if not plots_by_id or any(p.soil_suitability_class is None or p.soil_group is None for p in plots_by_id.values()):
        return None                          # cannot derive a defensible feasible set — do not fabricate
    return plots_by_id, farmer_by_id, crops


def create_run(pkg, source, kind=None, custom_snapshot=None):
    """Create a working-plan session from the chosen dataset. POST-only (caller enforces).
    Built-in: seeded from the CANONICAL stored plan + recorded responses (real FarmSync plan).
    Custom: seeded from the ACTIVATED snapshot; the initial recommendation is the top crop from the
    CANONICAL feasibility eligibility (_eligible) — a defensible feasible pick, not the old ad-hoc
    heuristic. Labelled DETERMINISTIC_WORKING_PLAN — never 'Optimal', never a publication result."""
    kind = kind or ("builtin" if "built" in (source or "").lower() else "custom")
    base = _canonical_builtin_recs() if kind == "builtin" else None
    recs = []
    total = 0.0
    n_infeasible = 0
    snap = None
    if base:
        engine_status = "CANONICAL_STORED_PLAN"
        for b in base:
            total += b.get("cash") or 0.0
            recs.append({**b,
                         "action": None, "commitment": None, "revised_crop_id": None,
                         "revised_crop": None, "revised_cash": None, "changed": False,
                         "requires_renewed_consent": False, "renewed_response": None,
                         "requested_crop": None, "rejected_alternatives": [],
                         "consent_state": None, "final_crop": None, "final_cash": None, "realised": False})
        farmers = [{"farmer_id": r["farmer_id"], "collective_id": None} for r in recs]
        plots = [{"plot_id": r["plot_id"]} for r in recs]
        # Gap B: the working run's UNIVERSE is the FULL selected dataset (not the offer subset). Capture
        # a lightweight immutable dataset snapshot from the built-in package for Final Plan completeness,
        # reconciliation and all-farmer fairness. The recommendation array stays the genuine offer subset.
        dsnap = _dataset_snapshot_from_pkg(pkg) if pkg is not None else None
        if dsnap:
            pop = {"farmers": dsnap["n_farmers"], "plots": dsnap["n_plots"],
                   "collectives": dsnap["n_collectives"]}
            dhash = dsnap.get("hash") or "builtin-canonical"
        else:
            pop = {"farmers": len({r["farmer_id"] for r in recs}), "plots": len(recs), "collectives": None}
            dhash = "builtin-canonical"
    else:
        snap = custom_snapshot
        objs = _custom_objects(snap)
        if objs is None:
            return {"available": False,
                    "error": "cannot derive a defensible feasible crop set: the activated custom plots "
                             "lack the agronomic attributes real feasibility requires"}
        plots_by_id, farmer_by_id, crops = objs
        from farmsync.ilp_reference import _eligible
        from farmsync.feasibility import FeasibilityConfig
        crop_by_name = {c.crop_name: c for c in crops}
        elig = _eligible(list(plots_by_id.values()), farmer_by_id, crop_by_name, FeasibilityConfig())
        engine_status = "DETERMINISTIC_WORKING_PLAN"      # NOT 'Optimal' — no optimiser ran
        for pid, plot in plots_by_id.items():
            opts = elig.get(pid, [])
            if opts:
                # canonical initial pick: top feasible cash-positive option (desc cash, then crop_id)
                opts_sorted = sorted(opts, key=lambda t: (-t[1], crop_by_name[t[0]].crop_id))
                crop, cash = opts_sorted[0][0], opts_sorted[0][1]
            else:
                crop, cash = None, None
                n_infeasible += 1
            if cash:
                total += cash
            recs.append({"farmer_id": plot.farmer_id, "plot_id": pid,
                         "region_id": plot.region_id, "season": plot.active_season.value,
                         "area_ha": plot.area_ha,
                         "crop_id": None, "crop": crop,
                         "expected_value_per_ha": None, "cash": cash,
                         "recorded_response": None,          # custom has no defensible recorded response
                         "action": None, "commitment": None, "revised_crop_id": None,
                         "revised_crop": None, "revised_cash": None, "changed": False,
                         "requires_renewed_consent": False, "renewed_response": None,
                         "requested_crop": None, "rejected_alternatives": [],
                         "consent_state": None, "final_crop": None, "final_cash": None, "realised": False})
        dsnap = _dataset_snapshot_from_custom(snap)
        pop = {"farmers": (dsnap["n_farmers"] if dsnap else len(farmer_by_id)),
               "plots": (dsnap["n_plots"] if dsnap else len(plots_by_id)),
               "collectives": len({f.get("collective_id") for f in snap.get("farmers", [])}) if snap else None}
        dhash = (snap.get("hash") if snap else None) or "custom"
        if all(r["crop"] is None for r in recs):
            # column-presence readiness was met, but the canonical feasibility rules derive NO
            # cash-positive feasible crop for any plot — do not present an empty "plan" as ready.
            return {"available": False,
                    "error": "no defensible feasible crop could be derived for any custom plot under "
                             "FarmSync's canonical feasibility rules (e.g. insufficient water, soil "
                             "class, or rotation constraints). Adjust the plot agronomic attributes."}
    run_id = "run-" + uuid.uuid4().hex[:12]
    run = {
        "run_id": run_id, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source, "source_kind": kind,
        "dataset_hash": dhash,
        "config": dict(EXPLORATORY_CONFIG),
        "population": pop,
        "provenance": "WORKING_PLAN",
        "engine": engine_status,
        "solver_status": engine_status,          # never 'Optimal' unless a real optimiser returned it
        "stage": "initial_plan",
        "planned_cash": round(total) if total else 0,
        "n_infeasible": n_infeasible,
        "recommendations": recs,
        "custom_snapshot": snap,
        "dataset_snapshot": dsnap,      # Gap B: FULL selected dataset universe (farmers/plots/area)
        # WORKFLOW revision anchors (server-owned authoritative state)
        "response_rev": 0,
        "replan_anchor": None,
        "final_anchor": None,
        "isolated_from": ["publication", "development_checkpoint", "p1/p3/p6", "frontiers", "final30"],
    }
    _save_run(run)
    return get_run(run["run_id"])   # 0A: return the authoritative shape (includes derived `workflow`)


def get_run(run_id):
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    run["workflow"] = workflow_state(run)   # authoritative derived stage/revision state (read-only)
    return run


def _find(run, farmer_id, plot_id):
    for r in run["recommendations"]:
        if r["farmer_id"] == farmer_id and r["plot_id"] == plot_id:
            return r
    return None


_OMITTED = object()   # distinguishes "field omitted" from an explicit null


def record_action(run_id, farmer_id, plot_id, action, requested_crop=_OMITTED):
    """Save a WORKING-PLAN response override for the exact (farmer_id, plot_id). POST-only.
    The recorded research response is immutable; this only sets the working-plan override. A MODIFY may
    carry the farmer's requested_crop, preserved separately from the action.
    §10 semantics: for a MODIFY save, requested_crop OMITTED preserves any already-saved crop; an
    explicit value sets/replaces it; an explicit null clears it. Omission never erases a saved crop."""
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    if action not in SUPPORTED_ACTIONS:
        return {"available": False, "error": "unsupported action '%s'" % action}
    rec = _find(run, farmer_id, plot_id)
    if rec is None:
        return {"available": False, "error": "farmer/plot pair not in this run"}
    before_sig = _effective_response_sig(rec)          # for idempotent invalidation
    prev_crop = rec.get("requested_crop")
    rec["action"] = action                         # working-plan override (recorded_response untouched)
    rec["working_response"] = action
    if action == "MODIFY":
        if requested_crop is _OMITTED:
            rec["requested_crop"] = prev_crop      # preserve an already-saved specific crop
        else:
            rec["requested_crop"] = requested_crop  # explicit set (value) or clear (None)
    else:
        rec["requested_crop"] = None               # non-MODIFY actions carry no requested crop
    if action == "ACCEPT":
        area = rec.get("area_ha") or 1.0
        rec["commitment"] = "HARD_LOCK" if (area or 0) >= 4 else ("SOFT_LOCK" if (area or 0) >= 2 else "FLEXIBLE")
    else:
        rec["commitment"] = None
    run["stage"] = "responses"
    # §"idempotent save": bump the response revision (invalidating downstream) ONLY on a real change
    changed_effective = _effective_response_sig(rec) != before_sig
    if changed_effective:
        _bump_response_rev(run)
    _save_run(run)
    edited = rec.get("recorded_response") is not None and action != rec.get("recorded_response")
    return {"available": True, "farmer_id": farmer_id, "plot_id": plot_id, "action": action,
            "working_response": action, "recorded_response": rec.get("recorded_response"),
            "requested_crop": rec.get("requested_crop"),
            "edited": bool(edited), "commitment": rec["commitment"], "run_id": run_id}


# working-plan aliases (semantic names used by the routes)
set_response = record_action


# --------------------------------------------------------------------------- #
# WORKFLOW REVISION BACKBONE (server-owned, authoritative). Minimal anchors:
#   response_rev   : bumped whenever effective response state actually changes (idempotent otherwise)
#   replan_anchor  : the response_rev captured when replan last succeeded (None if never)
#   final_anchor   : {response_rev, replan_anchor, consent_sig} captured at finalise (None if never)
# Consent is per-(plot, revised_crop): a rec's renewed_response is valid only while
# rec.consent_for_crop == rec.revised_crop. Derived currency answers "is X current for its inputs?".
# --------------------------------------------------------------------------- #
def _effective_response_sig(rec):
    # the tuple that defines a rec's effective replan input; used to detect REAL changes idempotently
    return (rec.get("working_response"), rec.get("requested_crop"),
            tuple(sorted(rec.get("rejected_alternatives") or [])))


def _ensure_wf(run):
    if "response_rev" not in run:
        run["response_rev"] = 0
    if "replan_anchor" not in run:
        run["replan_anchor"] = None
    if "final_anchor" not in run:
        run["final_anchor"] = None
    return run


def _bump_response_rev(run):
    _ensure_wf(run)
    run["response_rev"] = int(run["response_rev"]) + 1
    # an actual upstream change makes any prior replan/final derived-stale (anchors no longer match)


def _valid_current_consent(run, rec):
    """A renewed-consent decision is valid ONLY for the exact CURRENT revised recommendation:
    same revised crop AND same replan revision. This defeats the "same crop after a new replan" leak:
    a fresh replan (new replan_anchor) invalidates prior consent even if the crop name is identical."""
    _ensure_wf(run)
    if rec.get("consent_for_crop") != rec.get("revised_crop"):
        return None
    if rec.get("consent_for_replan_anchor") != run.get("replan_anchor"):
        return None
    return rec.get("renewed_response")


def _consent_sig(run):
    # signature of the CURRENT renewed-consent decisions for CURRENTLY changed rows, keyed to the exact
    # revised crop AND current replan anchor. Any consent edit, crop change, or new replan alters this.
    parts = []
    for rec in run.get("recommendations", []):
        if rec.get("changed") and rec.get("requires_renewed_consent"):
            valid = _valid_current_consent(run, rec)
            parts.append((rec.get("plot_id"), rec.get("revised_crop"), run.get("replan_anchor"), valid))
    return tuple(sorted(parts))


def _consent_counts(run):
    n_changed = n_requires = n_pending = 0
    for rec in run.get("recommendations", []):
        if rec.get("changed"):
            n_changed += 1
            if rec.get("requires_renewed_consent"):
                n_requires += 1
                if _valid_current_consent(run, rec) not in ("ACCEPT", "REJECT", "NO_RESPONSE"):
                    n_pending += 1
    return n_changed, n_requires, n_pending


def _replan_effective(run, rec):
    """The response Replan should consume for a row, HONESTLY per dataset source.
    Built-in: working override else the recorded synthetic response (always present).
    Custom:   working override ONLY (no recorded response exists) -> None if the user has not set one."""
    if run.get("source_kind") == "builtin":
        return rec.get("working_response") or rec.get("recorded_response")
    return rec.get("working_response")   # custom: unset == None == UNRESOLVED (never ACCEPT/CONSENTED)


def _unresolved_custom_rows(run):
    if run.get("source_kind") == "builtin":
        return 0
    return sum(1 for rec in run.get("recommendations", []) if not rec.get("working_response"))


def workflow_state(run):
    """Authoritative, DERIVED workflow/stage state. No mutation. The client must use this instead of
    local unlock booleans. UNLOCKED (prerequisite exists) is distinct from COMPLETED (operation ran)."""
    _ensure_wf(run)
    response_rev = int(run["response_rev"])
    replan_anchor = run["replan_anchor"]
    final_anchor = run["final_anchor"]
    replan_current = (replan_anchor is not None) and (replan_anchor == response_rev)
    n_changed, n_requires, n_pending = _consent_counts(run) if replan_current else (0, 0, 0)
    consent_complete = replan_current and (n_pending == 0)
    final_current = bool(final_anchor) and replan_current and \
        final_anchor.get("response_rev") == response_rev and \
        final_anchor.get("replan_anchor") == replan_anchor and \
        final_anchor.get("consent_sig") == list(_serialise_sig(_consent_sig(run)))
    # 0C: for CUSTOM datasets every plot must have an explicit working response before replan is valid.
    n_unresolved = _unresolved_custom_rows(run)
    replan_ready = (run.get("source_kind") == "builtin") or (n_unresolved == 0)
    stages = {
        "plan": True,                 # a run exists => an initial plan exists
        "farmer": True,               # initial plan exists => responses stage available
        "replan": replan_ready,       # custom: only when no plot is unresolved; built-in: always
        "consent": replan_current,    # only after the CURRENT replan succeeded
        "final": replan_current and consent_complete,
        "analyse": final_current,
    }
    return {
        "response_rev": response_rev,
        "replan_current": replan_current,
        "replan_ready": replan_ready,
        "n_unresolved": n_unresolved,
        "consent_complete": consent_complete,
        "final_current": final_current,
        "n_changed": n_changed, "n_requires_consent": n_requires, "n_consent_pending": n_pending,
        "finalisable": stages["final"],
        "stages": stages,
        # staleness signals for messaging (a prior derived result exists but is no longer current)
        "replan_stale": (replan_anchor is not None) and not replan_current,
        "final_stale": bool(final_anchor) and not final_current,
    }


def _serialise_sig(sig):
    # tuples -> JSON-friendly lists (stable for equality checks across save/load)
    return [list(x) for x in sig]


def reset_response(run_id, farmer_id, plot_id):
    """§15 Reset: remove ALL working-plan override state for the exact (farmer_id, plot_id) — response,
    requested crop, rejected alternatives and any override commitment — restoring the recorded response
    and original recommendation. Frozen artifacts are untouched. POST-only."""
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    rec = _find(run, farmer_id, plot_id)
    if rec is None:
        return {"available": False, "error": "farmer/plot pair not in this run"}
    before_sig = _effective_response_sig(rec)
    rec["action"] = None
    rec["working_response"] = None
    rec["requested_crop"] = None
    rec["rejected_alternatives"] = []
    rec["commitment"] = None
    if _effective_response_sig(rec) != before_sig:     # reset only invalidates if it changed something
        _bump_response_rev(run)
    _save_run(run)
    return {"available": True, "farmer_id": farmer_id, "plot_id": plot_id,
            "working_response": None, "requested_crop": None, "rejected_alternatives": [],
            "recorded_response": rec.get("recorded_response"),
            "effective_response": rec.get("recorded_response"), "edited": False, "run_id": run_id}


def reject_alternative(run_id, farmer_id, plot_id, crop):
    """§12: persist a rejected candidate crop for the exact (farmer_id, plot_id) in this working plan.
    Does NOT change the recorded research response, does NOT reject the original crop, is NOT consent.
    Future recommendations and replan exclude it. POST-only."""
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    rec = _find(run, farmer_id, plot_id)
    if rec is None:
        return {"available": False, "error": "farmer/plot pair not in this run"}
    if not crop:
        return {"available": False, "error": "no crop to reject"}
    rej = rec.get("rejected_alternatives") or []
    if crop not in rej:
        rej.append(crop)
        rec["rejected_alternatives"] = rej
        _bump_response_rev(run)                         # a new rejection changes the replan input
    else:
        rec["rejected_alternatives"] = rej             # already present -> idempotent, no invalidation
    _save_run(run)
    return {"available": True, "farmer_id": farmer_id, "plot_id": plot_id,
            "rejected_alternatives": rej, "rejected": crop, "run_id": run_id}


def _effective(rec):
    """The response Replan consumes: working override if set, else the recorded response."""
    return rec.get("working_response") or rec.get("action") or rec.get("recorded_response")


def _resolve_objects(run):
    """Resolve real Plot/Farmer/Crop objects for the run's dataset so the working replan can use the
    REAL frozen action-consent matrix (matrix_cell) + canonical feasibility eligibility (_eligible /
    modify_target). Heavy imports are LAZY (POST-only) so GET/page-load never import them.
    - built-in: the canonical generated instance objects (build_instance seed).
    - custom: Plot/Farmer objects built from the ACTIVATED snapshot's own agronomic columns (never any
      built-in Fxxxx plot data), with built-in crops. Returns (plots_by_id, farmer_by_id, crops) or None
      when custom plots lack the agronomic attributes real feasibility needs (then no defensible feasible
      set can be derived — caller must not fabricate one)."""
    kind = run.get("source_kind")
    if kind == "builtin":
        from farmsync.experiment import build_instance
        inst = build_instance(20260812)
        plots_by_id = {p.plot_id: p for p in inst["plots"]}
        farmer_by_id = {f.farmer_id: f for f in inst["farmers"]}
        return plots_by_id, farmer_by_id, inst["crops"]
    # custom: rebuild from the activated snapshot rows carried immutably on the run
    return _custom_objects(run.get("custom_snapshot"))


def _plot_farmer_crops(run, plot_id):
    """Resolve the real Plot/Farmer objects + crops for one plot in this run (built-in or custom)."""
    resolved = _resolve_objects(run)
    if resolved is None:
        return None, None, None
    plots_by_id, farmer_by_id, crops = resolved
    return plots_by_id.get(plot_id), farmer_by_id.get(_owner(run, plot_id)), crops


def _owner(run, plot_id):
    for r in run["recommendations"]:
        if r["plot_id"] == plot_id:
            return r["farmer_id"]
    return None


def _eligible_options(plot, farmer, crops, exclude=None):
    """Real canonical feasibility eligibility for one plot, ranked (cash desc, crop_id asc). Read-only."""
    _ensure_operational_data()
    from farmsync.ilp_reference import _eligible
    from farmsync.feasibility import FeasibilityConfig
    crop_by_name = {c.crop_name: c for c in crops}
    opts = _eligible([plot], {farmer.farmer_id: farmer}, crop_by_name, FeasibilityConfig()).get(plot.plot_id, [])
    exclude = set(exclude or [])
    ranked = sorted([(nm, cash) for (nm, cash, *_r) in opts if nm not in exclude],
                    key=lambda t: (-t[1], crop_by_name[t[0]].crop_id))
    return ranked


def consent_alternative(run_id, farmer_id, plot_id, exclude=None):
    """Renewed-Consent stage browsing (READ-ONLY, no mutation, no solver). Stage-specific semantics:
    the next feasible alternative EXCLUDES the CURRENT revised_crop, the persistent rejected_alternatives,
    and the crops already viewed in this browse sequence (`exclude`). Separately, if the effective initial
    action was MODIFY and the ORIGINAL crop remains canonically feasible and was not explicitly rejected,
    it is offered as a 'return to original plan' option (never as a newly discovered recommendation). If
    the effective initial action was REJECT, the rejected original crop is never re-offered."""
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    rec = _find(run, farmer_id, plot_id)
    if rec is None:
        return {"available": False, "error": "farmer/plot pair not in this run"}
    plot, farmer, crops = _plot_farmer_crops(run, plot_id)
    if plot is None or farmer is None:
        return {"available": False, "error": "cannot resolve plot feasibility for this dataset"}
    viewed = list(exclude or [])
    rejected = list(rec.get("rejected_alternatives") or [])
    original = rec.get("crop")
    revised = rec.get("revised_crop")
    eff = _replan_effective(run, rec)
    # exclusions for a NEW alternative: current revised crop + persistent rejections + browse-history.
    # The original crop is handled separately below (never surfaced as a "new" alternative here).
    excl = viewed + rejected + ([revised] if revised else []) + ([original] if original else [])
    ranked = _eligible_options(plot, farmer, crops, exclude=excl)

    # original-crop return option (MODIFY only; feasible; not rejected; not the current revised crop)
    original_option = None
    if eff == "MODIFY" and original and original not in rejected and original != revised:
        orig_rank = _eligible_options(plot, farmer, crops, exclude=[])
        for nm, cash in orig_rank:
            if nm == original:
                original_option = {"crop": original, "expected_cash": cash,
                                   "label": "Return to original plan"}
                break

    if not ranked:
        return {"available": True, "found": False,
                "original_option": original_option,
                "reason": "No other cash-positive feasible crop remains for this plot (season, soil, "
                          "water, rotation), excluding the current recommendation and any rejected or "
                          "already-viewed crops."}
    crop, cash = ranked[0]
    return {"available": True, "found": True, "farmer_id": farmer_id, "plot_id": plot_id,
            "revised_crop": revised, "recommended_crop": crop, "expected_cash": cash,
            "reason": "Feasible for this plot's season, soil, water and rotation, with the best "
                      "cash-positive projected return among the remaining alternatives.",
            "determined_by": "FarmSync feasibility + deterministic selection (the LLM does not choose crops)",
            "n_more": max(0, len(ranked) - 1),
            "original_option": original_option}


def recommend_alternative(run_id, farmer_id, plot_id, exclude=None):
    """Return a live, real feasible alternative for the exact farmer+plot via canonical eligibility.
    READ-ONLY — never mutates working state. 'exclude' lets the UI ask for the next option. POST (no
    solve). The LLM never invents the crop; this is FarmSync's deterministic feasibility selection."""
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    rec = _find(run, farmer_id, plot_id)
    if rec is None:
        return {"available": False, "error": "farmer/plot pair not in this run"}
    plot, farmer, crops = _plot_farmer_crops(run, plot_id)
    if plot is None or farmer is None:
        return {"available": False, "error": "cannot resolve plot feasibility for this dataset"}
    exclude = list(exclude or [])
    if rec.get("crop"):
        exclude = exclude + [rec["crop"]]              # exclude the current crop by default
    exclude = exclude + list(rec.get("rejected_alternatives") or [])   # §12: exclude rejected candidates
    ranked = _eligible_options(plot, farmer, crops, exclude=exclude)
    if not ranked:
        return {"available": True, "found": False,
                "current_crop": rec.get("crop"),
                "reason": "No other cash-positive feasible crop is available for this plot under "
                          "FarmSync's feasibility rules (season, soil, water, rotation)."}
    crop, cash = ranked[0]
    return {"available": True, "found": True, "farmer_id": farmer_id, "plot_id": plot_id,
            "current_crop": rec.get("crop"), "recommended_crop": crop, "expected_cash": cash,
            "reason": "Feasible for this plot's season, soil, water and rotation, with the best "
                      "cash-positive projected return among the remaining options.",
            "determined_by": "FarmSync feasibility + deterministic selection (the LLM does not choose crops)",
            "n_more": max(0, len(ranked) - 1)}


def validate_requested_crop(run_id, farmer_id, plot_id, requested_crop):
    """Validate a requested crop for the exact farmer + plot.

    Distinguishes:
    - agronomic feasibility from assess_plot_crop(), and
    - eligibility for a NEW working-plan selection from _eligible().

    _eligible() is stricter because it also requires the crop to be admitted
    and to have a positive projected-return entry. Absence from _eligible()
    must therefore never be described automatically as agronomic infeasibility.

    READ-ONLY: no working-plan state is changed.
    """
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}

    rec = _find(run, farmer_id, plot_id)
    if rec is None:
        return {"available": False, "error": "farmer/plot pair not in this run"}

    plot, farmer, crops = _plot_farmer_crops(run, plot_id)
    if plot is None or farmer is None:
        return {
            "available": False,
            "error": "cannot resolve plot feasibility for this dataset"
        }

    # NEW-selection eligibility: canonical _eligible includes more than
    # agronomic feasibility (admission + positive projected return).
    ranked = _eligible_options(plot, farmer, crops, exclude=[])
    eligible_names = {nm: cash for nm, cash in ranked}
    eligible_for_selection = requested_crop in eligible_names

    # Independent agronomic assessment.
    from farmsync.feasibility import FeasibilityConfig, assess_plot_crop

    crop_by_name = {c.crop_name: c for c in crops}
    checks = None
    reasons = None
    binding = None
    agronomic_feasible = None

    if requested_crop in crop_by_name:
        assessment = assess_plot_crop(
            plot,
            crop_by_name[requested_crop],
            farmer=farmer,
            config=FeasibilityConfig()
        )

        checks = _json_safe(getattr(assessment, "checks", None))
        reasons = _json_safe(getattr(assessment, "reasons", None)) or []
        binding = _json_safe(getattr(assessment, "binding", None)) or []

        assessed = getattr(assessment, "feasible", None)
        agronomic_feasible = (
            bool(assessed)
            if assessed is not None
            else not bool(reasons)
        )

    if eligible_for_selection:
        return {
            "available": True,
            "requested_crop": requested_crop,

            # Backward-compatible field: selectable by the working-plan mechanism.
            "feasible": True,

            "agronomic_feasible": agronomic_feasible,
            "eligible_for_selection": True,

            "recommended_crop": requested_crop,
            "expected_cash": eligible_names[requested_crop],
            "current_crop": rec.get("crop"),

            "assessment_checks": checks,
            "assessment_reasons": reasons,
            "assessment_binding": binding,

            "reason": (
                "Agronomic checks pass and the crop is eligible for selection "
                "under FarmSync's current working-plan rules."
            ),
            "determined_by": (
                "FarmSync deterministic agronomic assessment + "
                "working-plan selection eligibility"
            ),
        }

    alt = recommend_alternative(run_id, farmer_id, plot_id)

    if agronomic_feasible is False:
        reason = (
            "The crop does not pass FarmSync's deterministic agronomic "
            "feasibility checks for this plot."
        )
    elif agronomic_feasible is True:
        reason = (
            "Agronomic checks show no blocking constraint for this crop, "
            "but it is not eligible for a new FarmSync selection under the "
            "current admitted and cash-positive projected-return rules."
        )
    else:
        reason = (
            "FarmSync cannot establish agronomic feasibility for this crop "
            "from the current deterministic evidence."
        )

    return {
        "available": True,
        "requested_crop": requested_crop,

        # Backward-compatible: False means not selectable as a NEW working-plan crop.
        # Do not interpret this alone as agronomic infeasibility.
        "feasible": False,

        "agronomic_feasible": agronomic_feasible,
        "eligible_for_selection": False,

        "current_crop": rec.get("crop"),

        "assessment_checks": checks,
        "assessment_reasons": reasons,
        "assessment_binding": binding,

        "reason": reason,
        "alternative": alt if alt.get("found") else None,

        "determined_by": (
            "FarmSync deterministic agronomic assessment + "
            "working-plan selection eligibility"
        ),
    }


def _plain_enum(value):
    """JSON-safe display value for enum-like schema fields without inventing labels."""
    if value is None:
        return None
    return getattr(value, "value", value)


def _json_safe(value):
    """Recursively convert enum-like feasibility evidence into JSON-safe primitive values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    v = getattr(value, "value", None)
    return _json_safe(v) if v is not None else str(value)


def explain_recommendation(run_id, farmer_id, plot_id, crop=None, exclude=None):
    """Explain one exact crop from deterministic plot/farmer evidence only.

    Returns both the OVERALL feasible rank and the rank among CURRENTLY AVAILABLE alternatives after
    explicit exclusions (original crop, persisted rejected alternatives, and UI-provided previously
    browsed candidates). This keeps the explanation consistent with the recommendation the user saw.
    READ-ONLY: no working-plan state is changed.
    """
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    rec = _find(run, farmer_id, plot_id)
    if rec is None:
        return {"available": False, "error": "farmer/plot pair not in this run"}
    plot, farmer, crops = _plot_farmer_crops(run, plot_id)
    if plot is None or farmer is None:
        return {"available": False, "error": "cannot resolve plot feasibility for this dataset"}

    current_plan_crop = rec.get("revised_crop") or rec.get("crop")
    target = crop or current_plan_crop
    all_ranked = _eligible_options(plot, farmer, crops, exclude=[])
    all_names = [nm for nm, _cash in all_ranked]
    cash_by = {nm: cash for nm, cash in all_ranked}

    # Build an auditable exclusion ledger. Never claim an exclusion reason that is not actually known.
    exclusion_ledger = []
    seen = set()

    def add_exclusion(name, reason):
        if not name or name == target or name in seen:
            return
        seen.add(name)
        exclusion_ledger.append({"crop": name, "reason": reason})

    add_exclusion(rec.get("crop"), "original/current crop is excluded when asking for an alternative")
    for name in rec.get("rejected_alternatives") or []:
        add_exclusion(name, "farmer rejected this candidate for the current working plan")
    for name in exclude or []:
        add_exclusion(name, "already browsed in the current alternative sequence")

    available_exclude = [x["crop"] for x in exclusion_ledger]
    available_ranked = _eligible_options(plot, farmer, crops, exclude=available_exclude)
    available_names = [nm for nm, _cash in available_ranked]

    from farmsync.feasibility import FeasibilityConfig, assess_plot_crop
    crop_by_name = {c.crop_name: c for c in crops}
    assessment = None
    checks = None
    reasons = None
    binding = None
    agronomic_feasible = None

    if target in crop_by_name:
        assessment = assess_plot_crop(
            plot,
            crop_by_name[target],
            farmer=farmer,
            config=FeasibilityConfig()
        )

        checks = _json_safe(getattr(assessment, "checks", None))
        reasons = _json_safe(getattr(assessment, "reasons", None)) or []
        binding = _json_safe(getattr(assessment, "binding", None)) or []

        assessed = getattr(assessment, "feasible", None)
        agronomic_feasible = (
            bool(assessed)
            if assessed is not None
            else not bool(reasons)
        )

    overall_rank = (all_names.index(target) + 1) if target in all_names else None
    available_rank = (available_names.index(target) + 1) if target in available_names else None
    eligible_for_selection = target in all_names
    is_current_plan_crop = bool(current_plan_crop and target == current_plan_crop)

    # A built-in current recommendation may come from the stored canonical plan
    # even when the current per-plot alternative-selection layer cannot reconstruct
    # a cash-positive ranking entry for that crop.
    plan_cash = None

    if rec.get("revised_crop") == target:
        plan_cash = rec.get("revised_cash")
    elif rec.get("crop") == target:
        plan_cash = rec.get("cash")

    ranked_cash = cash_by.get(target)

    if ranked_cash is not None:
        explained_cash = ranked_cash
        explained_cash_source = "current_selection_eligibility"
    elif is_current_plan_crop and plan_cash is not None:
        explained_cash = plan_cash
        explained_cash_source = "stored_current_plan"
    else:
        explained_cash = None
        explained_cash_source = None

    # Actual plot attributes used by the deterministic feasibility path. Values are copied from the
    # resolved Plot object; unavailable fields remain None rather than being guessed.
    plot_evidence = {
        "region_id": getattr(plot, "region_id", None),
        "season": _plain_enum(getattr(plot, "active_season", None)),
        "area_ha": getattr(plot, "area_ha", None),
        "soil_group": _plain_enum(getattr(plot, "soil_group", None)),
        "soil_suitability_class": _plain_enum(getattr(plot, "soil_suitability_class", None)),
        "drainage_class": _plain_enum(getattr(plot, "drainage_class", None)),
        "irrigation_access": _plain_enum(getattr(plot, "irrigation_access", None)),
        "available_water_m3": getattr(plot, "available_water_m3", None),
        "waterlogging_exposure": _plain_enum(getattr(plot, "waterlogging_exposure", None)),
        "drought_exposure": _plain_enum(getattr(plot, "drought_exposure", None)),
        "flood_exposure": _plain_enum(getattr(plot, "flood_exposure", None)),
        "previous_crop": getattr(plot, "previous_crop", None),
        "rotation_group": getattr(plot, "rotation_group", None),
    }

    other_overall = [{"crop": nm, "expected_cash": cash}
                     for nm, cash in all_ranked if nm != target][:5]
    other_available = [{"crop": nm, "expected_cash": cash}
                       for nm, cash in available_ranked if nm != target][:5]

    return {
        "available": True,
        "farmer_id": farmer_id,
        "plot_id": plot_id,
        "crop": target,
        # Explanation feasibility refers to the direct agronomic assessment,
        # NOT mere membership in the stricter cash-positive selection set.
        "feasible": agronomic_feasible,
        "agronomic_feasible": agronomic_feasible,

        "eligible_for_selection": eligible_for_selection,
        "current_plan_crop": is_current_plan_crop,

        "expected_cash": explained_cash,
        "expected_cash_source": explained_cash_source,

        "rank_reproducible": eligible_for_selection,
        "plot_evidence": plot_evidence,
        "assessment_checks": checks,
        # Backward-compatible alias used by the current UI/tests.
        "passed_constraints": checks,
        "assessment_reasons": reasons,
        "assessment_binding": binding,
        "overall_rank": overall_rank,
        "n_feasible_overall": len(all_ranked),
        "available_rank": available_rank,
        "n_available": len(available_ranked),
        # Backward-compatible names: rank_among_feasible means overall feasible rank.
        "rank_among_feasible": overall_rank,
        "n_feasible": len(all_ranked),
        "other_feasible_ranked": other_overall,
        "other_available_ranked": other_available,
        "exclusions": exclusion_ledger,
        "rejected_alternatives": list(rec.get("rejected_alternatives") or []),
        "basis": (
            "FarmSync deterministic evidence for this exact farmer + plot + crop. "
            "Agronomic feasibility comes from assess_plot_crop(). Selection eligibility "
            "and ranking come separately from the current cash-positive working-plan "
            "eligibility layer. A stored current-plan recommendation is never labelled "
            "agronomically infeasible merely because that later eligibility layer cannot "
            "reconstruct a rank for it. The LLM does not choose crops or invent facts."
        ),
    }


def replan(run_id):
    """Working-plan reoptimisation using the REAL frozen deterministic action-consent machinery:
    matrix_cell(action, lock) (frozen ACTION_CONSENT_PROTOCOL v1) decides permission/outcome, and
    modify_target()/_eligible() (the CANONICAL optimiser feasibility eligibility) choose the revised
    crop. This is the real deterministic action-consent + feasibility layer applied to the working-plan
    responses — NOT the MILP collective reoptimisation (reoptimize.py re-solves the whole instance and
    is not reused per working-plan edit here). No CBC/PuLP solve is run. POST-only."""
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    # 0C: for CUSTOM data, refuse to replan while any plot has no explicit working response.
    n_unresolved = _unresolved_custom_rows(run)
    if n_unresolved > 0:
        return {"available": False,
                "error": "%d custom plot(s) have no working response. Record an explicit response "
                         "(ACCEPT/REJECT/MODIFY/NO_RESPONSE/WITHDRAW) for every plot before replanning." % n_unresolved,
                "n_unresolved": n_unresolved}
    # LAZY heavy imports (POST-only): keeps GET / page load free of these modules.
    from farmsync.proposed.actions import matrix_cell, modify_target, LOCK_HARD
    resolved = _resolve_objects(run)
    if resolved is None:
        return {"available": False,
                "error": "cannot derive a defensible feasible crop set for this dataset "
                         "(custom plots lack the agronomic attributes real feasibility requires)"}
    plots_by_id, farmer_by_id, crops = resolved
    n_changed = 0
    revised_total = 0.0
    for rec in run["recommendations"]:
        act = _replan_effective(run, rec)
        lock = rec.get("commitment") or "FLEXIBLE"
        rec["revised_crop_id"] = rec["crop_id"]
        rec["revised_crop"] = rec["crop"]
        rec["revised_cash"] = rec["cash"]
        rec["changed"] = False
        rec["requires_renewed_consent"] = False
        rec["offer_status"] = None
        rec["reason_code"] = None
        if not act:
            # UNRESOLVED (custom row with no explicit working response) — never accepted/consented.
            rec["offer_status"] = "UNRESOLVED"
            if rec["revised_cash"]:
                revised_total += rec["revised_cash"]
            continue
        if act == "ACCEPT":
            rec["offer_status"] = "CONSENTED"
            if rec["revised_cash"]:
                revised_total += rec["revised_cash"]
            continue
        permitted, offer_status, reason = matrix_cell(act, lock)  # REAL frozen action x lock matrix
        rec["offer_status"] = getattr(offer_status, "value", offer_status)
        rec["reason_code"] = reason
        plot = plots_by_id.get(rec["plot_id"])
        farmer = farmer_by_id.get(rec["farmer_id"])
        if act in ("REJECT", "MODIFY") and permitted and lock != LOCK_HARD and plot is not None and farmer is not None:
            # MODIFY may carry a farmer-requested crop; validate it against canonical eligibility.
            requested = rec.get("requested_crop") if act == "MODIFY" else None
            rejected = list(rec.get("rejected_alternatives") or [])   # §12: never pick a rejected candidate
            new_crop, new_cash = None, None
            if requested and requested not in rejected:
                from farmsync.ilp_reference import _eligible
                from farmsync.feasibility import FeasibilityConfig
                crop_by_name = {c.crop_name: c for c in crops}
                elig = _eligible([plot], {farmer.farmer_id: farmer}, crop_by_name, FeasibilityConfig()).get(plot.plot_id, [])
                match = [(nm, cash) for (nm, cash, *_r) in elig if nm == requested and nm != rec["crop"]]
                if match:
                    new_crop, new_cash = match[0]         # requested crop is feasible → honour it
            if new_crop is None:
                # canonical pick excluding the current crop AND any explicitly rejected alternatives
                ranked = _eligible_options(plot, farmer, crops, exclude=[rec["crop"]] + rejected)
                if ranked:
                    new_crop, new_cash = ranked[0]
            if new_crop is not None:
                rec["revised_crop_id"] = None
                rec["revised_crop"] = new_crop
                rec["revised_cash"] = new_cash
                rec["changed"] = True
                rec["requires_renewed_consent"] = True
                n_changed += 1
        if act in ("WITHDRAW", "NO_RESPONSE"):
            rec["revised_crop_id"] = None
            rec["revised_crop"] = None
            rec["revised_cash"] = None
        if rec["revised_cash"]:
            revised_total += rec["revised_cash"]
    run["stage"] = "replan"
    run["revised_cash"] = round(revised_total)
    run["n_changed"] = n_changed
    run["replan_mechanism"] = ("deterministic action-consent (matrix_cell) + canonical feasibility "
                               "eligibility (_eligible/modify_target); NOT the MILP collective reoptimisation")
    # WORKFLOW: this replan is now CURRENT for the current response revision.
    _ensure_wf(run)
    run["replan_anchor"] = int(run["response_rev"])
    # §"revised-crop change": any renewed consent tied to a crop that is no longer the revised crop is
    # invalidated (cleared), so it becomes pending again and Final/Analyse go stale.
    for rec in run["recommendations"]:
        if not (rec.get("changed") and rec.get("requires_renewed_consent")):
            rec["renewed_response"] = None
            rec["consent_state"] = None
            rec["consent_for_crop"] = None
            rec["consent_for_replan_anchor"] = None
        elif rec.get("consent_for_crop") not in (None, rec.get("revised_crop")):
            rec["renewed_response"] = None
            rec["consent_state"] = None
            rec["consent_for_crop"] = None
            rec["consent_for_replan_anchor"] = None
    run["final_anchor"] = None                      # a fresh replan makes any prior final stale
    _save_run(run)
    return {"available": True, "run_id": run_id, "n_changed": n_changed,
            "revised_cash": run["revised_cash"], "state": "RECOMMENDED_REVISED",
            "not_realised": "This is a revised recommendation from the deterministic engine; it is NOT "
                            "yet realised. Renewed consent is required for any changed crop."}


def record_renewed_consent(run_id, farmer_id, plot_id, renewed_response):
    """Record the run's own renewed consent for a changed plot. POST-only.
    Consent is bound to the EXACT current revised crop; editing an existing decision is allowed."""
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    rec = _find(run, farmer_id, plot_id)
    if rec is None:
        return {"available": False, "error": "farmer/plot pair not in this run"}
    if not rec.get("requires_renewed_consent"):
        return {"available": False, "error": "this plot does not require renewed consent"}
    if renewed_response not in ("ACCEPT", "REJECT", "NO_RESPONSE"):
        return {"available": False, "error": "renewed response must be ACCEPT/REJECT/NO_RESPONSE"}
    # SERVER GUARD: a stale (not-current) replan must never accept renewed-consent writes (UI lock is
    # not enough — a direct POST must be refused too).
    if not workflow_state(run)["replan_current"]:
        return {"available": False, "error": "Replan is not current; re-run Replan before recording consent."}
    rec["renewed_response"] = renewed_response
    rec["consent_state"] = "RENEWED_ACCEPT" if renewed_response == "ACCEPT" else (
        "RENEWED_REJECT" if renewed_response == "REJECT" else "RENEWED_NO_RESPONSE")
    rec["consent_for_crop"] = rec.get("revised_crop")            # bound to the EXACT current crop
    rec["consent_for_replan_anchor"] = run.get("replan_anchor")  # AND the current replan revision
    run["stage"] = "consent"
    run["final_anchor"] = None                          # a consent change makes any prior final stale
    _save_run(run)
    return {"available": True, "run_id": run_id, "farmer_id": farmer_id, "plot_id": plot_id,
            "consent_state": rec["consent_state"], "workflow": workflow_state(run)}


def _is_pending(run, rec):
    """A changed row requiring renewed consent with NO valid decision for the CURRENT revised
    recommendation (exact crop AND current replan anchor)."""
    if not (rec.get("changed") and rec.get("requires_renewed_consent")):
        return False
    return _valid_current_consent(run, rec) not in ("ACCEPT", "REJECT", "NO_RESPONSE")


def bulk_renewed_consent(run_id, decision):
    """Apply a decision to PENDING rows ONLY. Rows with an existing valid current decision are NOT
    overwritten. Server-side (not faked in JS). POST-only."""
    if decision not in ("ACCEPT", "REJECT", "NO_RESPONSE"):
        return {"available": False, "error": "decision must be ACCEPT/REJECT/NO_RESPONSE"}
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    if not workflow_state(run)["replan_current"]:
        return {"available": False, "error": "Replan is not current; re-run Replan before bulk consent."}
    n = 0
    for rec in run["recommendations"]:
        if _is_pending(run, rec):
            rec["renewed_response"] = decision
            rec["consent_state"] = "RENEWED_ACCEPT" if decision == "ACCEPT" else (
                "RENEWED_REJECT" if decision == "REJECT" else "RENEWED_NO_RESPONSE")
            rec["consent_for_crop"] = rec.get("revised_crop")
            rec["consent_for_replan_anchor"] = run.get("replan_anchor")
            n += 1
    if n:
        run["stage"] = "consent"
        run["final_anchor"] = None
        _save_run(run)
    return {"available": True, "run_id": run_id, "decision": decision, "n_applied": n,
            "workflow": workflow_state(run)}


def select_revised_recommendation(run_id, farmer_id, plot_id, crop):
    """"Use this recommendation": replace the CURRENT pending revised recommendation for the exact
    (farmer_id, plot_id) with a deterministically-REVALIDATED feasible crop. Choosing a crop is NOT
    consent: this clears any old crop-specific consent and leaves the new crop PENDING. It does NOT run
    a whole replan, does NOT realise, and does NOT touch frozen artifacts. POST-only (no CBC/PuLP solve)."""
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    rec = _find(run, farmer_id, plot_id)
    if rec is None:
        return {"available": False, "error": "farmer/plot pair not in this run"}
    if not rec.get("changed"):
        return {"available": False, "error": "this plot's crop did not change in the current replan"}
    if not crop:
        return {"available": False, "error": "no crop supplied"}
    if not workflow_state(run)["replan_current"]:
        return {"available": False, "error": "Replan is not current; re-run Replan before selecting a recommendation."}
    # SERVER revalidates feasibility (never trust the browser) via canonical eligibility.
    plot, farmer, crops = _plot_farmer_crops(run, plot_id)
    if plot is None or farmer is None:
        return {"available": False, "error": "cannot resolve plot feasibility for this dataset"}
    ranked = _eligible_options(plot, farmer, crops, exclude=[rec["crop"]])
    match = [(nm, cash) for nm, cash in ranked if nm == crop]
    if not match:
        return {"available": False,
                "error": "'%s' is not a feasible alternative for this plot." % crop}
    new_crop, new_cash = match[0]
    if new_crop == rec.get("revised_crop"):
        # no change — idempotent; keep existing consent state
        return {"available": True, "run_id": run_id, "farmer_id": farmer_id, "plot_id": plot_id,
                "revised_crop": rec["revised_crop"], "unchanged": True, "workflow": workflow_state(run)}
    # replace the current pending revised recommendation
    rec["revised_crop"] = new_crop
    rec["revised_crop_id"] = None
    rec["revised_cash"] = new_cash
    rec["changed"] = True
    rec["requires_renewed_consent"] = True
    # choosing != consenting: clear any old crop-specific consent -> NEW crop is PENDING
    rec["renewed_response"] = None
    rec["consent_state"] = None
    rec["consent_for_crop"] = None
    rec["consent_for_replan_anchor"] = None
    run["final_anchor"] = None                          # Final/Analyse become stale
    _save_run(run)
    return {"available": True, "run_id": run_id, "farmer_id": farmer_id, "plot_id": plot_id,
            "revised_crop": new_crop, "revised_cash": new_cash,
            "note": "New revised recommendation is now PENDING. Choosing a crop is not consent.",
            "workflow": workflow_state(run)}


def finalise(run_id):
    """Realise the run's final plan. A plot is realised ONLY with verified exact-crop consent:
    an unchanged ACCEPT (existing valid initial consent) or a changed plot with RENEWED_ACCEPT for the
    EXACT current revised crop. POST-only. WORKFLOW: refuses unless the current replan revision is
    finalisable (a current replan exists AND no required renewed-consent row is pending)."""
    run = _load_run(run_id)
    if not run:
        return {"available": False, "error": "run not found"}
    wf = workflow_state(run)
    if not wf["replan_current"]:
        return {"available": False, "error": "Run the current Replan before finalising.",
                "workflow": wf}
    if wf["n_consent_pending"] > 0:
        return {"available": False,
                "error": "%d changed row(s) still need an explicit renewed-consent decision." % wf["n_consent_pending"],
                "workflow": wf}
    final_total = 0.0
    n_final = 0
    n_eligible = 0
    for rec in run["recommendations"]:
        act = _replan_effective(run, rec)
        rec["final_crop"] = None
        rec["final_cash"] = None
        rec["realised"] = False
        rec["consent_basis"] = None
        if rec.get("changed"):
            n_eligible += 1
            # consent is valid only if it was given for the EXACT current revised crop
            valid_accept = _valid_current_consent(run, rec) == "ACCEPT"
            if valid_accept:
                rec["final_crop"] = rec["revised_crop"]
                rec["final_cash"] = rec["revised_cash"]
                rec["realised"] = True
                rec["consent_basis"] = "RENEWED_ACCEPT"
        elif act == "ACCEPT":
            n_eligible += 1
            rec["final_crop"] = rec["crop"]
            rec["final_cash"] = rec["cash"]
            rec["realised"] = True
            rec["consent_basis"] = "INITIAL_ACCEPT"
        if rec["realised"]:
            n_final += 1
            final_total += rec["final_cash"] or 0.0
    run["stage"] = "final"
    run["final_cash"] = round(final_total)
    run["n_final"] = n_final
    # affirmative consent coverage = realised / consent-eligible (same denominator as Analyse's
    # affirmative_consent_coverage). REJECT/NO_RESPONSE are not affirmative consent.
    run["consent_coverage_final"] = (n_final / n_eligible) if n_eligible else 0.0
    # WORKFLOW: create the CURRENT final-plan revision, tied to the exact response/replan/consent inputs.
    _ensure_wf(run)
    run["final_plan_revision"] = int(run.get("final_plan_revision") or 0) + 1
    run["final_anchor"] = {
        "response_rev": int(run["response_rev"]),
        "replan_anchor": run["replan_anchor"],
        "consent_sig": _serialise_sig(_consent_sig(run)),
        "final_plan_revision": run["final_plan_revision"],
        "finalised_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _save_run(run)
    return {"available": True, "run_id": run_id, "n_final": n_final,
            "final_cash": run["final_cash"], "consent_coverage_final": run["consent_coverage_final"],
            "state": "FINAL_REALIZED",
            "rule": "A plot is realised only with verified exact-crop consent (unchanged INITIAL_ACCEPT "
                    "or changed RENEWED_ACCEPT).",
            "workflow": workflow_state(run)}


def list_runs():
    if not os.path.isdir(_RUN_ROOT):
        return []
    out = []
    for name in sorted(os.listdir(_RUN_ROOT)):
        r = _load_run(name)
        if r:
            out.append({"run_id": r["run_id"], "created": r["created"], "source": r["source"],
                        "stage": r["stage"], "population": r["population"]})
    return out
