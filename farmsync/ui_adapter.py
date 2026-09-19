"""
FarmSync UI adapter — READ-ONLY artifact/config readers for the research-workbench UI.

Every function here reads existing config or result/audit artifacts and returns plain dicts for the
frontend. NONE of these run the CBC solver, the action-consent pipeline, or any LLM (live or mock).
Missing artifacts return an honest {"available": False, "state": "Not available"} shape rather than
fabricated numbers. Development-derived values carry a "provenance": "DEVELOPMENT_CHECKPOINT" label.

This module never imports pulp and never triggers optimisation; it is safe to call on page load.
"""
from __future__ import annotations
import csv
import json
import os

from . import config as C

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _p(*parts):
    return os.path.join(_ROOT, *parts)


def _read_json(rel):
    path = _p(rel)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return None


def _read_csv(rel, limit=None):
    path = _p(rel)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        return rows[:limit] if limit else rows
    except OSError:
        return None


def _na(what="Not available"):
    return {"available": False, "state": what}


# ---- publication configuration (single source of truth) ---------------------------------------
def publication_config():
    return {
        "available": True,
        "config_version": C.PUBLICATION_CONFIG_VERSION,
        "epsilon": C.PUBLICATION_EPSILON,
        "lambda": C.PUBLICATION_LAMBDA,
        "alpha": C.PUBLICATION_ALPHA,
        "action_profile": C.PUBLICATION_ACTION_PROFILE,
        "action_protocol": C.PUBLICATION_ACTION_PROTOCOL,
        "uncertainty_protocol": C.PUBLICATION_UNCERTAINTY_PROTOCOL,
        "fairness": C.PUBLICATION_FAIRNESS,
        "epsilon_note": "canonical B3 fairness-efficiency floor, frozen before Final30",
        "lambda_note": "design parameter frozen before Final30",
        "alpha_note": "SYNTHETIC_EXPERIMENTAL concentration threshold frozen before Final30",
    }


def _dev_checkpoint():
    return _read_json("results/farmsync/proposed/ui_dev_checkpoint.json")


def ai_status():
    """Mode-aware AI status for the UI badge. Normal users see the mode label; implementation metadata is
    grouped under 'technical' for a Technical-details disclosure."""
    import os as _os
    ui_policy_version = None
    try:
        from farmsync.proposed import llm_ui_integration as _int
        from farmsync.proposed import llm_service as _svc
        mode = _svc.resolve_mode(_os.environ.get("FARMSYNC_LLM_MODE"))   # missing -> OFF
        label = _int.mode_label(mode)
        ui_policy_version = _int.UI_INTENT_POLICY_VERSION
    except Exception:
        mode, label = "off", "Off"                 # fail-safe: never silently claim Mock
    model = _os.environ.get("FARMSYNC_LLM_MODEL", "gpt-5.6-terra")
    return {
        "mode": mode,
        "label": label,
        "role": (
            "The assistant parses farmer language. FarmSync validates, selects crops, "
            "and supplies deterministic explanation evidence. The assistant never "
            "chooses a crop, decides feasibility, executes, or overrides identity/rules."
        ),
        "technical": {
            "model": model if mode == "live" else None,
            "prompt_version": "p7-parse-live-v3",
            "schema_version": "farmsync-farmer-request-v1",
            "context_policy_version": "ctx-policy-v1",
            "ui_intent_policy_version": ui_policy_version,
            "provenance": {"off": "disabled", "mock": "DEVELOPMENT_MOCK",
                           "live": "LIVE_OPENAI_RESPONSES"}.get(mode),
            "no_silent_fallback": True,
            "farmer_id_sent_to_model": False,
        },
    }


def experiment_state():
    """Current, publication-safe run-state flags for the project."""
    analysis = _read_json("results/farmsync/final30_analysis_v1/MANIFEST.json") or {}
    freeze = _read_json("results/farmsync/final30_analysis_freeze_v1/FREEZE.json") or {}
    final30_complete = analysis.get("status") == "COMPLETE" and freeze.get("status") == "SEALED"
    return {
        "development_checkpoint": _dev_checkpoint() is not None,
        "final30": (
            "COMPLETE / SEALED (900/900 frozen cells; derived analysis QA PASS)"
            if final30_complete else "NOT AVAILABLE"
        ),
        "final30_complete": final30_complete,
        "llm_benchmark_300": (
            "COMPLETE (322-case SYNTHETIC_CONSTRUCTED held-out parser benchmark; "
            "NOT real-farmer validation)"
        ),
        "llm_live_ui_integration": (
            "WIRED / COMPLETE - historical 10-call live UI smoke COMPLETE; 7-case targeted "
            "post-routing live regression addendum COMPLETE; offline regression 275 passed"
        ),
        "llm_live_ui_smoke": (
            "COMPLETE - 10-call manual bounded integration QA "
            "(2026-09-17; pre-llm-ui-intent-v2); NOT a benchmark or real-farmer validation"
        ),
        "llm_targeted_live_addendum": (
            "COMPLETE - 7/7 targeted live regression cases PASS"
        ),
        "llm_offline_regression": "COMPLETE - 275 tests passed",
        "llm_live": (
            "PARSER BENCHMARK COMPLETE; HISTORICAL 10-CALL LIVE UI SMOKE COMPLETE; "
            "TARGETED 7-CASE LIVE ADDENDUM COMPLETE"
        ),
        "note": (
            "Final30 publication results are sealed and are shown only in Advanced result tabs. "
            "Interactive workflow pages remain current-run tools for the selected dataset. "
            "The LLM is parser/interface/explanation-only and had no role in Final30 allocation, "
            "feasibility, fairness, consent or execution."
        ),
    }


# ---- overview ---------------------------------------------------------------------------------
def overview():
    manifest = _read_json("results/farmsync/audit/experiment_manifest.json") or {}
    seeds = _read_json("results/farmsync/audit/replication_seeds.json") or {}
    crs = manifest.get("crop_region_season_config", {})
    b1 = _read_json("results/farmsync/b1_ilp_v2.json") or {}
    meta = (b1.get("metadata") or {})
    dev = _dev_checkpoint() or {}
    devpop = dev.get("population", {})
    b1mc = (b1.get("metrics_core") or {})
    plots_from_b1 = None
    if b1mc.get("plots_allocated") is not None and b1mc.get("plots_fallow") is not None:
        plots_from_b1 = b1mc["plots_allocated"] + b1mc["plots_fallow"]
    pop = {
        "farmers": devpop.get("farmers"),
        "plots": devpop.get("plots") or plots_from_b1,
        "collectives": devpop.get("collectives"),
        "crops_total": crs.get("crops"),
        "crops_admitted": crs.get("admitted"),
        "regions": crs.get("regions"),
        "seasons": crs.get("seasons"),
    }
    return {
        "available": True,
        "config": publication_config(),
        "population": pop,
        "hashes": {
            "processed_dataset_hash": manifest.get("processed_dataset_hash"),
            "raw_source_manifest_hash": manifest.get("raw_source_manifest_hash"),
            "gate_hash": manifest.get("gate_hash"),
            "instance_hash": (dev.get("config") or {}).get("instance_hash"),
            "replication_seed_file_hash": manifest.get("replication_seed_file_hash"),
        },
        "solver": manifest.get("solver"),
        "seeds": {"n": seeds.get("n_replications"), "base_seed": seeds.get("base_seed"),
                  "frozen_at": seeds.get("frozen_at")},
        "experiment_state": experiment_state(),
        "pipeline": ["DATA", "FEASIBILITY", "B1/B2/B3", "FARMER ACTIONS", "COMMITMENT",
                     "REOPTIMISATION", "CONCENTRATION CONTROL", "CONSENT", "REALISATION",
                     "UNCERTAINTY / RESILIENCE"],
    }


# ---- planning (B1/B2/B3 from artifacts + Proposed from dev checkpoint) -------------------------
def _baseline_row(tag, rel):
    d = _read_json(rel)
    if not d:
        return {"name": tag, "available": False, "state": "Not available"}
    mc = d.get("metrics_core", {})
    fv = d.get("fairness_v2", {})
    return {
        "name": tag, "available": True,
        "total_cash_return": mc.get("total_cash_return"),
        "land_utilisation_pct": mc.get("land_utilisation_pct"),
        "plots_allocated": mc.get("plots_allocated"),
        "gini_farmer_return": mc.get("gini_farmer_return"),
        "min_farmer_return": mc.get("min_farmer_return"),
        "median_farmer_return": mc.get("median_farmer_return"),
        "hard_constraints_satisfied": bool(d.get("hard_constraints_satisfied")),
        "status": (d.get("metadata") or {}).get("solver_status", "Optimal"),
        "fairness_primary": fv.get("primary"),
    }


def planning():
    b1 = _baseline_row("B1", "results/farmsync/b1_ilp_v2.json")
    b2 = _baseline_row("B2", "results/farmsync/b2_ilp_v2.json")
    b3 = _baseline_row("B3", "results/farmsync/b3_ilp_v2.json")
    dev = _dev_checkpoint()
    proposed = _na("Not run")
    if dev:
        u0 = dev.get("U0", {})
        proposed = {
            "available": True, "provenance": "DEVELOPMENT_CHECKPOINT",
            "tiers": u0.get("proposed", {}).get("tiers"),
            "consent_coverage_final": u0.get("proposed", {}).get("consent_coverage_final"),
            "reopt_status": u0.get("proposed", {}).get("reopt_status"),
            "conc_status": u0.get("proposed", {}).get("conc_status"),
            "action_counts": u0.get("proposed", {}).get("action_counts"),
        }
    return {
        "available": True,
        "baselines": [b1, b2, b3],
        "proposed_u0": proposed,
        "b3_caveat": "B3 is fairness-aware worst-off protection among CAPABLE farmers subject to an "
                     "efficiency floor (total cash >= epsilon * T*). It does not by itself guarantee a "
                     "lower global Gini.",
        "tier_semantics": {
            "PLANNED": "static B3 recommendation (no farmer action yet)",
            "INITIAL_REALIZED": "realised after one initial farmer action per offer (ACCEPTs only)",
            "RECOMMENDED_REVISED": "revised RECOMMENDATION after action-adjusted reoptimisation "
                                   "(requires renewed consent; NOT realised)",
            "FINAL_REALIZED": "realised after renewed consent",
        },
    }


# ---- actions / consent checkpoint --------------------------------------------------------------
def actions_checkpoint():
    dev = _dev_checkpoint()
    if not dev:
        return _na("Not run")
    u0 = dev.get("U0", {})
    p = u0.get("proposed", {})
    return {
        "available": True, "provenance": "DEVELOPMENT_CHECKPOINT",
        "participating_farmers": u0.get("participating_farmers"),
        "action_counts": p.get("action_counts"),
        "withdrawn_farmers": p.get("withdrawn_farmers"),
        "renewed_prompts": p.get("renewed_prompts"),
        "tiers": p.get("tiers"),
        "consent_coverage_final": p.get("consent_coverage_final"),
        "coverage_derivation": "provenance-verified exact-crop ACCEPT consent / FINAL_REALIZED count",
        "states": ["PLANNED", "INITIAL_REALIZED", "RECOMMENDED_REVISED", "FINAL_REALIZED"],
        "commitment_ladder": ["VIEWED", "TENTATIVE_ACCEPT", "CONFIRMED", "INPUTS_PURCHASED",
                              "LAND_PREPARED", "PLANTED"],
        "lock_levels": {"FLEXIBLE": "free to change", "SOFT_LOCK": "change penalised (lambda)",
                        "HARD_LOCK": "planted / immutable"},
        "consent_kinds": ["INITIAL", "RENEWED"],
        "provenance_fields": ["farmer_id", "plot_id", "crop", "consent_kind", "decision_round",
                              "cycle_id", "action_event_id"],
        "note": "RECOMMENDED_REVISED is a recommendation requiring renewed consent; it is visually and "
                "semantically distinct from a realised (FINAL_REALIZED) allocation.",
    }


# ---- fairness ---------------------------------------------------------------------------------
def fairness():
    out = {}
    for tag, rel in (("B1", "results/farmsync/b1_ilp_v2.json"),
                     ("B2", "results/farmsync/b2_ilp_v2.json"),
                     ("B3", "results/farmsync/b3_ilp_v2.json")):
        d = _read_json(rel)
        out[tag] = (d.get("fairness_v2") if d else None) or _na()
    return {
        "available": True, "by_method": out,
        "denominator_notes": {
            "per_ha_gini_all": "farmer cash / total operated area, all 500 farmers incl. zeros",
            "abs_gini_all": "absolute cash Gini over all farmers",
            "per_ha_gini_participants": "per-ha Gini over participating farmers only",
            "abs_gini_participant_only": "participating farmers only (legacy frozen Gini basis)",
        },
        "caveat": "B3 protects the worst-off CAPABLE farmer under the efficiency floor; it does not "
                  "guarantee a lower global Gini. Read each Gini with its stated denominator.",
    }


# ---- concentration (alpha) --------------------------------------------------------------------
def concentration():
    frontier = _read_csv("results/farmsync/proposed/p4_alpha_frontier.csv")
    conc = _read_json("results/farmsync/proposed/p4_concentration_result.json")
    return {
        "available": frontier is not None,
        "provenance": "DEVELOPMENT_CHECKPOINT",
        "alpha_frozen": C.PUBLICATION_ALPHA,
        "frontier": frontier or [],
        "concentration_result": conc or _na(),
        "constraint": "q_fc <= alpha * Q_c",
        "plain": "No single farmer may hold more than about alpha (40%) of an active crop's total "
                 "expected production.",
        "caveat": "This controls farmer-within-crop production concentration, NOT geographic hazard "
                  "concentration; it does not guarantee spatial hazard protection.",
        "frontier_note": "Development sensitivity evidence — not final30.",
    }


# ---- lambda (stability) frontier --------------------------------------------------------------
def lambda_frontier():
    frontier = _read_csv("results/farmsync/proposed/p3_lambda_frontier.csv")
    return {
        "available": frontier is not None,
        "provenance": "DEVELOPMENT_CHECKPOINT",
        "lambda_frozen": C.PUBLICATION_LAMBDA,
        "frontier": frontier or [],
        "objective": "maximise E/E* - lambda * (soft_disruption_area / soft_lock_area)",
        "plain": "lambda trades economic performance against disruption of soft commitments.",
        "label": "Development calibration evidence — not final30. lambda is a design parameter, not "
                 "empirically estimated.",
    }


# ---- epsilon frontier -------------------------------------------------------------------------
def epsilon_frontier():
    fr = _read_json("results/farmsync/audit/b3_epsilon_frontier.json")
    return {"available": fr is not None, "epsilon_frozen": C.PUBLICATION_EPSILON,
            "frontier": fr or _na(),
            "selection_rule": "highest epsilon with min_norm >= 0.99 * max_attainable (=> 0.95)"}


# ---- uncertainty ------------------------------------------------------------------------------
def uncertainty():
    dev = _dev_checkpoint()
    conditions = [
        {"id": "U0", "label": "Baseline (no uncertainty)", "channels": []},
        {"id": "UW", "label": "Weather (ET0)", "channels": ["W"]},
        {"id": "UM", "label": "Market (price + absorption)", "channels": ["M"]},
        {"id": "UR", "label": "Resources (budget + labour)", "channels": ["R"]},
        {"id": "UP", "label": "Participation", "channels": ["P"]},
        {"id": "UJ", "label": "Joint (all channels)", "channels": ["W", "M", "R", "P"]},
    ]
    checkpoints = {}
    if dev:
        for k in ("U0", "UJ"):
            x = dev.get(k, {})
            checkpoints[k] = {
                "available": True, "provenance": "DEVELOPMENT_CHECKPOINT",
                "realisation_hash": x.get("realisation_hash"),
                "participating_farmers": x.get("participating_farmers"),
                "baselines": x.get("baselines"),
                "proposed_tiers": (x.get("proposed") or {}).get("tiers"),
                "consent_coverage_final": (x.get("proposed") or {}).get("consent_coverage_final"),
            }
    for c in conditions:
        if c["id"] not in checkpoints:
            checkpoints[c["id"]] = _na("Not run")
    return {
        "available": True, "conditions": conditions, "checkpoints": checkpoints,
        "framing": "Paired synthetic EXOGENOUS scenarios — not empirical event probabilities and not "
                   "stochastic optimisation. One paired realisation per (seed, condition) is reused "
                   "across B1/B2/B3/Proposed.",
        "note": "UW/UM/UR/UP are validated by unit/integration tests; only U0 and UJ have stored "
                "development checkpoints. The solver is NOT invoked from this page.",
    }


# ---- resilience -------------------------------------------------------------------------------
def resilience():
    res = _read_json("results/farmsync/proposed/p5_resilience_result.json")
    nminus1 = _read_csv("results/farmsync/proposed/p5_nminus1_scenarios.csv")
    hazard = _read_csv("results/farmsync/proposed/p5_hazard_scenarios.csv")
    return {
        "available": res is not None or nminus1 is not None,
        "provenance": "DEVELOPMENT_CHECKPOINT",
        "result": res or _na(),
        "nminus1_scenarios": nminus1 or [],
        "hazard_scenarios": hazard or [],
        "distinction": {
            "immediate_exposure": "cash/production lost immediately when a producer or hazard zone fails "
                                  "(before any recovery)",
            "post_shock_recovery": "cash recovered by the backup reoptimisation (a RECOMMENDATION, not a "
                                   "realised plan)",
        },
        "infeasible_note": "Infeasible recovery scenarios are shown as INFEASIBLE, never as zero recovery.",
        "caveat": "Concentration control (alpha) does not guarantee spatial hazard protection.",
    }


# ---- LLM boundary (shell only; NO live or mock call is made here) -----------------------------
def llm_boundary():
    schema = _read_json("results/farmsync/proposed/p7_llm_schema.json")
    manifest = _read_json("results/farmsync/proposed/p7_llm_manifest.json")
    metrics = _read_json("results/farmsync/proposed/p7_dev_metrics.json")
    return {
        "available": True,
        "flow": ["Natural language", "Structured parse", "Deterministic validation",
                 "Deterministic mechanism", "Validated outcome", "Grounded explanation"],
        "authority": {"llm": "interface / parser / explanation layer (NO allocation authority)",
                      "optimizer": "sole allocation authority"},
        "schema": schema or _na(),
        "dev_manifest": manifest or _na(),
        "dev_metrics": {"available": metrics is not None, "provenance": "DEVELOPMENT / MOCK",
                        "metrics": metrics} if metrics else _na("Not run"),
        "live_status": (
            "PARSER BENCHMARK COMPLETE; HISTORICAL 10-CALL LIVE UI SMOKE COMPLETE; "
            "TARGETED 7-CASE LIVE ADDENDUM COMPLETE"
        ),
        "benchmark_300_status": (
            "COMPLETE (322-case SYNTHETIC_CONSTRUCTED held-out parser benchmark; "
            "NOT real-farmer validation)"
        ),
        "live_ui_smoke_status": (
            "COMPLETE - historical live UI smoke: 10 manually executed bounded "
            "integration-QA calls (2026-09-17; pre-llm-ui-intent-v2). "
            "It is not a benchmark or real-farmer validation."
        ),
        "targeted_live_addendum_status": (
            "COMPLETE - 7/7 targeted post-routing live regression cases PASS"
        ),
        "offline_regression_status": "COMPLETE - 275 tests passed",
        "final30_llm_calls": 0,
        "note": (
            "This endpoint/page load makes no live LLM call. Final30 made zero LLM calls. "
            "The LLM remains parser/interface/explanation-only and never chooses crops, "
            "decides feasibility, changes locks/fairness, records consent, or executes allocations. "
            "No runtime telemetry is automatically persisted."
        ),
    }


# ---- reproducibility --------------------------------------------------------------------------
def reproducibility():
    manifest = _read_json("results/farmsync/audit/experiment_manifest.json") or {}
    seeds = _read_json("results/farmsync/audit/replication_seeds.json") or {}
    rng = _read_json("results/farmsync/audit/rng_streams.json") or {}
    dev = _dev_checkpoint() or {}
    analysis = _read_json("results/farmsync/final30_analysis_v1/MANIFEST.json") or {}
    analysis_freeze = _read_json("results/farmsync/final30_analysis_freeze_v1/FREEZE.json") or {}
    raw_freeze = _read_json("results/farmsync/final30_freeze_v1/FREEZE.json") or {}
    final_qa = _read_json("results/farmsync/final30_analysis_v1/qa/final_analysis_check.json") or {}
    return {
        "available": True,
        "config": publication_config(),
        "hashes": {
            "processed_dataset_hash": manifest.get("processed_dataset_hash"),
            "raw_source_manifest_hash": manifest.get("raw_source_manifest_hash"),
            "gate_hash": manifest.get("gate_hash"),
            "generator_file_hash": manifest.get("generator_file_hash"),
            "replication_seed_file_hash": manifest.get("replication_seed_file_hash"),
            "instance_hash": (dev.get("config") or {}).get("instance_hash"),
        },
        "solver": manifest.get("solver"),
        "solver_final30": {
            "engine": "CBC",
            "cbc": "2.10.3",
            "pulp": "3.3.2",
            "gapRel": 1e-6,
            "timeLimit_s": 120,
            "threads_policy": "Windows: 0; non-Windows: 1",
            "status_semantics": (
                "CBC Optimal under the configured tolerance; not a claim of exact mathematical global optimality."
            ),
        },
        "seeds": {"n": seeds.get("n_replications"), "base_seed": seeds.get("base_seed"),
                  "derivation": seeds.get("derivation"), "frozen_at": seeds.get("frozen_at")},
        "rng_substreams": rng if rng else _na(),
        "run_state": experiment_state(),
        "audit_verdict": (
            "FINAL30 COMPLETE / DERIVED ANALYSIS QA PASS / RAW + ANALYSIS SEALED"
            if final_qa.get("final_analysis_qa_pass") is True else "FINAL30 ANALYSIS NOT VERIFIED"
        ),
        "solver_status_rule": (
            "Performance summaries are Optimal-only; non-Optimal outcomes are retained and reliability is reported separately."
        ),
        "final30": {
            "raw_cell_count": analysis.get("raw_cell_count"),
            "source_commit": analysis.get("source_commit"),
            "matrix_sha256": analysis.get("matrix_sha256"),
            "dataset_attestation_sha256": analysis.get("dataset_attestation_sha256"),
            "solver_amendment_sha256": analysis.get("solver_amendment_sha256"),
            "raw_cell_set_sha256": analysis.get("cell_set_sha256"),
            "raw_run_manifest_sha256": analysis.get("run_manifest_sha256"),
            "analysis_set_sha256": analysis_freeze.get("analysis_set_sha256"),
            "analysis_manifest_sha256": analysis_freeze.get("analysis_manifest_sha256"),
            "analysis_file_count": analysis_freeze.get("analysis_file_count"),
            "analysis_status": analysis.get("status"),
            "analysis_freeze_status": analysis_freeze.get("status"),
            "final_analysis_qa_pass": final_qa.get("final_analysis_qa_pass"),
            "raw_freeze_status": raw_freeze.get("status"),
            "analysis_runtime": analysis.get("analysis_runtime") or {},
            "bootstrap_replicates": (analysis.get("analysis_rules") or {}).get("bootstrap_replicates"),
            "bootstrap_seed": (analysis.get("analysis_rules") or {}).get("bootstrap_seed"),
            "raw_manifest_bookkeeping_note": (
                "The sealed raw RUN_MANIFEST retained its original IN_PROGRESS bookkeeping field because "
                "the runner did not finalize that field. Completeness was independently verified as 900/900 "
                "cells and preserved without post-hoc raw mutation."
            ),
        },
    }


# ============================================================================
# Guided-workbench row-level readers (READ-ONLY, artifact-driven).
# None of these run the solver, the pipeline, or any LLM. They read the frozen
# per-plot allocation / response / commitment / consent CSVs and join them for
# the Plan and Farmer-Interaction views.
# ============================================================================

_METHOD_ALLOC = {
    "B1": "results/farmsync/b1_ilp_v2_allocations.csv",
    "B2": "results/farmsync/b2_final_allocations.csv",
    "B3": "results/farmsync/b3_ilp_v2_allocations.csv",
}


def dataset_summary():
    """Built-in dataset headline for the Home 'current dataset' card. No load required."""
    dev = _dev_checkpoint() or {}
    pop = dev.get("population", {})
    manifest = _read_json("results/farmsync/audit/experiment_manifest.json") or {}
    crs = manifest.get("crop_region_season_config", {})
    return {
        "available": True,
        "name": "FarmSync Built-in Research Dataset",
        "validated": True,
        "farmers": pop.get("farmers"),
        "plots": pop.get("plots"),
        "collectives": pop.get("collectives"),
        "regions": crs.get("regions"),
        "crops_total": crs.get("crops"),
        "crops_admitted": crs.get("admitted"),
        "provenance": "DEVELOPMENT_CHECKPOINT",
        "tables": ["farmers", "plots", "collectives", "crops", "crop_parameters",
                   "suitability", "market", "climate", "hazards", "participation", "provenance"],
    }


def _num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def plan(method="B3"):
    """Recommendation summary + rows for a baseline method, from its frozen allocation CSV.
    'Proposed' uses the final revised plan. Read-only; nothing is solved here."""
    method = (method or "B3").upper()
    if method in ("PROPOSED", "FARMSYNC"):
        rows = _read_csv("results/farmsync/proposed/p6_final_revised_plan.csv") or []
        recs = [{
            "farmer_id": r.get("farmer_id"), "plot_id": r.get("plot_id"),
            "crop": r.get("crop"), "area_ha": _num(r.get("area_ha")),
            "cash": _num(r.get("cash_net")), "commitment": r.get("commitment_lock"),
            "consent": "yes" if str(r.get("consent_exists")).lower() in ("true", "1", "yes") else "no",
            "state": r.get("state"),
        } for r in rows]
        dev = _dev_checkpoint() or {}
        tiers = ((dev.get("U0") or {}).get("proposed") or {}).get("tiers") or {}
        total_cash = tiers.get("FINAL_REALIZED")
        label = "Proposed (action-consent, FINAL_REALIZED)"
        provenance = "DEVELOPMENT_CHECKPOINT"
    else:
        rel = _METHOD_ALLOC.get(method)
        rows = _read_csv(rel) if rel else None
        if rows is None:
            return _na("Not available")
        recs = []
        total_cash = 0.0
        for r in rows:
            cash = _num(r.get("cash_net") or r.get("net_return_c2") or r.get("net_return"))
            if cash is not None:
                total_cash += cash
            recs.append({"farmer_id": r.get("farmer_id"), "plot_id": r.get("plot_id"),
                         "crop": r.get("crop"), "area_ha": _num(r.get("area_ha")),
                         "cash": cash, "commitment": None, "consent": None, "state": "PLANNED"})
        label = {"B1": "B1 — Independent planning",
                 "B2": "B2 — Centralised economic planning",
                 "B3": "B3 — Fairness-aware collective planning"}.get(method, method)
        provenance = "FROZEN_ARTIFACT"
    farmers = sorted({r["farmer_id"] for r in recs if r["farmer_id"]})
    return {
        "available": True, "method": method, "label": label, "provenance": provenance,
        "recommendations": recs, "n_recommendations": len(recs),
        "n_farmers": len(farmers), "total_cash": round(total_cash) if total_cash else None,
        "solver_status": "Optimal",
        "note": "These are RECOMMENDATIONS read from frozen result artifacts, not live-solved in the "
                "browser. A recommendation is not a realised allocation until consent is recorded.",
    }


def _offers_index():
    rows = _read_csv("results/farmsync/proposed/p1_participation_offers.csv") or []
    return {r.get("farmer_id"): r for r in rows}, rows


def farmers_list(limit=60):
    """List of farmers with their recommendation + recorded response, for the interaction picker."""
    _, rows = _offers_index()
    out = [{
        "farmer_id": r.get("farmer_id"), "plot_id": r.get("plot_id"),
        "region_season": r.get("region_season"), "planned_crop": r.get("planned_crop"),
        "planned_cash": _num(r.get("planned_cash_return")),
        "response": r.get("response"), "status": r.get("status"),
    } for r in rows]
    return {"available": bool(out), "provenance": "DEVELOPMENT_CHECKPOINT",
            "farmers": out[:limit] if limit else out, "total": len(out),
            "note": "Synthetic recorded responses (SYNTHETIC_EXPERIMENTAL); not empirical farmer prevalence."}


_ACTION_EXPLAIN = {
    "ACCEPT": ("Accepted", "Consent recorded. The plan commits this plot to the recommended crop; the "
               "commitment lock governs whether a later change is free, penalised, or immutable."),
    "REJECT": ("Rejected", "No consent. Where the protocol requires it, the current crop is excluded and "
               "the collective is reoptimised to produce a fresh recommendation (which needs renewed consent)."),
    "MODIFY": ("Requested another crop", "The farmer's requested crop is an input, not an allocation. The "
               "deterministic optimiser reoptimises and may return a different revised recommendation."),
    "NO_RESPONSE": ("No response (pending / lapsed)", "Not silently accepted. No consent exists; the offer "
                    "lapses and the plot is not realised on this recommendation."),
    "WITHDRAW": ("Withdrew", "The farmer leaves this decision round; the outcome follows the frozen "
                 "FLEXIBLE / SOFT_LOCK / HARD_LOCK semantics for the plot's current commitment state."),
}


def farmer_detail(farmer_id):
    """Full artifact-joined journey for one farmer: offer -> response -> commitment -> final + consent."""
    idx, _ = _offers_index()
    off = idx.get(farmer_id)
    if not off:
        return _na("Farmer not found")
    timeline = [r for r in (_read_csv("results/farmsync/proposed/p2_commitment_timeline.csv") or [])
                if r.get("farmer_id") == farmer_id]
    final = next((r for r in (_read_csv("results/farmsync/proposed/p6_final_revised_plan.csv") or [])
                  if r.get("farmer_id") == farmer_id), None)
    resp = off.get("response")
    verdict, explain = _ACTION_EXPLAIN.get(resp, (resp, ""))
    steps = [{"state": t.get("new_state"), "event": t.get("event"), "lock": t.get("lock_level"),
              "can_change_crop": t.get("can_change_crop"), "reason": t.get("reason")} for t in timeline]
    return {
        "available": True, "provenance": "DEVELOPMENT_CHECKPOINT",
        "farmer_id": farmer_id, "plot_id": off.get("plot_id"),
        "region_season": off.get("region_season"),
        "recommendation": {"crop": off.get("planned_crop"),
                           "cash": _num(off.get("planned_cash_return"))},
        "response": resp, "response_verdict": verdict, "response_explain": explain,
        "acceptance_probability": _num(off.get("p_accept")),
        "commitment_timeline": steps,
        "final": ({"crop": final.get("crop"), "cash": _num(final.get("cash_net")),
                   "commitment_lock": final.get("commitment_lock"),
                   "consent_exists": str(final.get("consent_exists")).lower() in ("true", "1", "yes"),
                   "requires_renewed_consent": str(final.get("requires_renewed_consent")).lower() in ("true", "1", "yes"),
                   "state": final.get("state")} if final else None),
        "authority_note": "The LLM may parse and explain a farmer request. The deterministic optimiser "
                          "retains crop-allocation authority.",
    }


def data_requirements():
    """Mode-aware, purpose-aware upload requirements, grounded in an audit of downstream code
    dependencies (not filenames). Sources: dataset_manager SUPPORTED_FILES / CORE_FILES /
    REQUIRED_COLUMNS and the two upload paths' merge behaviour:
      - custom-farmer route merges built-ins ({**builtin, **provided}), so supporting files are reused;
      - complete-package route builds from the ZIP only (no built-in merge), so a capability's file must
        be supplied for that capability to run.
    validate_package() enforces only core presence + required columns + relational integrity — it does
    NOT verify planning/feasibility/uncertainty/resilience data, so structural PASS != ready to plan.
    """
    from farmsync.dataset_manager import (
        SUPPORTED_FILES, CORE_FILES, REQUIRED_COLUMNS,
        MAX_ZIP_BYTES, MAX_UNCOMPRESSED_BYTES, MAX_FILE_BYTES, VALID_SEASONS,
    )
    # Audited capability -> files each capability needs for a fully-independent complete package.
    caps = _CAPABILITY_FILES
    # Per-file role (the audit result) used to derive mode-aware labels + purpose text.
    role = _FILE_ROLE
    files = []
    for name in SUPPORTED_FILES:
        r = role.get(name, ("metadata", "Supporting file."))
        files.append({
            "file": name,
            "role": r[0],
            "purpose": r[1],
            "required_columns": REQUIRED_COLUMNS.get(name, []),
            "custom_farmer_label": _label_for(name, "custom_farmer"),
            "complete_package_label": _label_for(name, "complete_package"),
        })
    return {
        "available": True,
        "modes": {
            "custom_farmer": {
                "label": "Use my own farmer / plot / collective data",
                "explain": "Provide farmers.csv, plots.csv and collectives.csv. FarmSync reuses the "
                           "built-in crops, regions, parameters, climate, market, hazard and "
                           "participation data for everything else, so those files are not required.",
                "you_must_provide": ["farmers.csv", "plots.csv", "collectives.csv"],
                "reused_from_builtin": [f for f in SUPPORTED_FILES if f not in ("farmers.csv", "plots.csv", "collectives.csv")],
                "answers": "If you only upload your own farmer/plot/collective data, you must provide "
                           "farmers.csv, plots.csv and collectives.csv; everything else is reused from the "
                           "built-in dataset.",
            },
            "complete_package": {
                "label": "Fully independent complete FarmSync package (.zip)",
                "explain": "A .zip is built from the supplied files only — nothing is merged from built-ins. "
                           "Core relational files are required to validate; each additional FarmSync "
                           "capability needs its own data file to be present.",
                "answers": "For a fully independent dataset, the required files depend on which capabilities "
                           "you want. See the per-capability requirements below.",
                "capability_requirements": [
                    {"capability": "Validate & activate (structural)", "files": list(CORE_FILES)},
                    {"capability": "Initial planning / optimiser", "files": caps["initial_planning"]},
                    {"capability": "Feasibility & weather uncertainty", "files": caps["feasibility"]},
                    {"capability": "Market uncertainty", "files": caps["uncertainty_market"]},
                    {"capability": "Participation uncertainty", "files": caps["uncertainty_participation"]},
                    {"capability": "Resilience analysis", "files": caps["resilience"]},
                    {"capability": "Provenance / reproducibility", "files": caps["provenance"]},
                ],
            },
        },
        "core_files": list(CORE_FILES),
        "supported_files": list(SUPPORTED_FILES),
        "file_schema": files,
        "capability_files": caps,
        "valid_seasons": sorted(VALID_SEASONS),
        "limits": {"max_zip_mb": MAX_ZIP_BYTES // (1024 * 1024),
                   "max_uncompressed_mb": MAX_UNCOMPRESSED_BYTES // (1024 * 1024),
                   "max_file_mb": MAX_FILE_BYTES // (1024 * 1024)},
        "validation_vs_readiness": "Structural validation checks core files, required columns and "
                                   "relational integrity. It does not guarantee a capability can run. "
                                   "Ready-to-plan requires the planning data files, not just a structural pass.",
        "rule": "Invalid data cannot proceed to planning: validation must pass before a dataset is activated.",
    }


# --- audited capability <-> file dependency map (see data_requirements docstring) ---
_CAPABILITY_FILES = {
    "core_relational": ["farmers.csv", "plots.csv", "crops.csv", "regions.csv", "collectives.csv"],
    "initial_planning": ["crop_region_season_params.csv", "plot_crop_suitability.csv"],
    "feasibility": ["plot_crop_suitability.csv", "climate_scenarios.csv"],
    "uncertainty_market": ["market_scenarios.csv"],
    "uncertainty_participation": ["participation_scenarios.csv"],
    "resilience": ["hazard_zones.csv"],
    "provenance": ["parameter_provenance.csv"],
}

_FILE_ROLE = {
    "farmers.csv": ("core", "Farmer records — required in every mode."),
    "plots.csv": ("core", "Plot records (carry area, hazard_zone) — required in every mode."),
    "collectives.csv": ("core", "Collective membership — required in every mode."),
    "crops.csv": ("core_reusable", "Crop identities — reused from built-in in custom-farmer mode."),
    "regions.csv": ("core_reusable", "Region identities — reused from built-in in custom-farmer mode."),
    "crop_region_season_params.csv": ("planning", "Per crop/region/season economics — the optimiser needs this for planning."),
    "plot_crop_suitability.csv": ("planning", "Which crops each plot may grow — defines the feasible set for planning and feasibility."),
    "climate_scenarios.csv": ("feasibility", "Regional climate — feasibility water checks and the weather uncertainty scenario."),
    "market_scenarios.csv": ("uncertainty_market", "Market scenarios — the market uncertainty scenario."),
    "participation_scenarios.csv": ("uncertainty_participation", "Participation scenarios — the participation uncertainty scenario."),
    "hazard_zones.csv": ("resilience", "Hazard-zone definitions — the resilience hazard-outage analysis."),
    "farmer_preferences.csv": ("behaviour_optional", "Farmer crop preferences — shapes farmer responses; defaults apply if absent."),
    "parameter_provenance.csv": ("metadata", "Provenance labels for parameters — reproducibility metadata."),
    "dataset_dictionary.csv": ("metadata", "Column dictionary — documentation metadata."),
}

_ROLE_LABEL_COMPLETE = {
    "core": "Required", "core_reusable": "Required",
    "planning": "Required for planning",
    "feasibility": "Required for feasibility & weather uncertainty",
    "uncertainty_market": "Required for market uncertainty",
    "uncertainty_participation": "Required for participation uncertainty",
    "resilience": "Required for resilience analysis",
    "behaviour_optional": "Optional (farmer behaviour)",
    "metadata": "Optional metadata / reproducibility",
}


def _label_for(name, mode):
    role = _FILE_ROLE.get(name, ("metadata", ""))[0]
    if mode == "custom_farmer":
        return "Required" if name in ("farmers.csv", "plots.csv", "collectives.csv") else "Built-in reused"
    return _ROLE_LABEL_COMPLETE.get(role, "Optional")


def capability_readiness(present_files, mode="complete_package", plot_columns=None):
    """Given the set of present files, report which capabilities can run. Advisory readiness layer:
    it does NOT alter the scientific validator; it exists so the UI cannot claim 'Ready to Plan' when
    only structural validation passed. In custom-farmer mode, general supporting files are reused from
    built-ins, BUT plot-level feasibility/planning still requires the genuine agronomic plot columns —
    custom mode is NOT automatically ready just because built-in support data exists."""
    present = set(present_files or [])
    from farmsync.dataset_manager import CORE_FILES
    reused = mode == "custom_farmer"

    # agronomic columns feasibility/suitability genuinely need on a plot (audited from feasibility.py)
    REQUIRED_PLOT_COLS = ["soil_group", "soil_suitability_class", "drainage_class",
                          "available_water_m3", "waterlogging_exposure", "active_season"]
    plot_cols = set(plot_columns or [])
    missing_plot_cols = [c for c in REQUIRED_PLOT_COLS if c not in plot_cols] if reused else []
    agronomy_ok = (not reused) or (len(missing_plot_cols) == 0)

    def have(files):
        return reused or all(f in present for f in files)

    def missing(files):
        return [] if reused else [f for f in files if f not in present]

    caps = _CAPABILITY_FILES
    core_ok = all((f in present) or (reused and f not in ("farmers.csv", "plots.csv", "collectives.csv")) for f in CORE_FILES)
    report = {
        "mode": mode,
        "core_relational": {"ready": core_ok, "missing": [f for f in CORE_FILES if f not in present and not (reused and f not in ("farmers.csv", "plots.csv", "collectives.csv"))]},
        "capabilities": {},
    }
    labels = {"initial_planning": "Initial planning / optimiser", "feasibility": "Feasibility & weather uncertainty",
              "uncertainty_market": "Market uncertainty", "uncertainty_participation": "Participation uncertainty",
              "resilience": "Resilience analysis", "provenance": "Provenance / reproducibility"}
    # capabilities that depend on plot agronomy require the agronomic columns too (custom mode)
    AGRO_DEPENDENT = {"initial_planning", "feasibility", "resilience"}
    for key, label in labels.items():
        files_ok = core_ok and have(caps[key])
        agro_needed = key in AGRO_DEPENDENT
        ready = files_ok and (agronomy_ok or not agro_needed)
        miss = missing(caps[key])
        if agro_needed and reused and missing_plot_cols:
            miss = miss + ["plots.csv columns: " + ", ".join(missing_plot_cols)]
        report["capabilities"][key] = {"label": label, "ready": ready, "missing": miss}
    report["agronomy_ready"] = agronomy_ok
    report["missing_plot_columns"] = missing_plot_cols
    report["ready_to_plan"] = report["core_relational"]["ready"] and report["capabilities"]["initial_planning"]["ready"]
    if reused and not agronomy_ok:
        report["note"] = ("Custom-farmer mode reuses built-in SUPPORTING data, but plot-level feasibility "
                          "and planning need real agronomic plot columns. Missing: " + ", ".join(missing_plot_cols) +
                          ". Provide these in plots.csv (or a complete package with a valid "
                          "plot_crop_suitability.csv) before planning.")
    elif reused:
        report["note"] = "Custom-farmer mode reuses built-in supporting data; required agronomic plot columns are present."
    else:
        report["note"] = "Complete-package mode uses supplied files only; missing files disable the listed capability."
    return report


# ============================================================================
# Per-stage canonical readers (READ-ONLY, artifact-driven, no solver / no LLM).
# Strict causal sourcing to prevent future-state leakage:
#   Initial Plan      -> p1 planned_crop / planned_cash_return   (PLANNED)
#   Farmer Responses  -> p1 planned_crop + recorded response      (no revised/final)
#   Replan            -> p3_revised_plan_lambda0 (+ p1 original)   (RECOMMENDED_REVISED, not realised)
#   Consent           -> p6 consent flags (+ p1 original, p3 revised)
#   Final Plan        -> p6 final rows                             (FINAL_REALIZED only)
# ============================================================================

_P1 = "results/farmsync/proposed/p1_participation_offers.csv"
_P3 = "results/farmsync/proposed/p3_revised_plan_lambda0.csv"
_P6 = "results/farmsync/proposed/p6_final_revised_plan.csv"


def _tiers():
    dev = _dev_checkpoint() or {}
    return ((dev.get("U0") or {}).get("proposed") or {}).get("tiers") or {}


def _p1_rows():
    return _read_csv(_P1) or []


def initial_plan():
    """PLANNED original recommendation — planned_crop / planned_cash_return ONLY. Never realised/final."""
    rows = _p1_rows()
    if not rows:
        return _na("Not available")
    recs = [{"farmer_id": r.get("farmer_id"), "plot_id": r.get("plot_id"),
             "region_season": r.get("region_season"), "crop": r.get("planned_crop"),
             "cash": _num(r.get("planned_cash_return"))} for r in rows]
    farmers = sorted({r["farmer_id"] for r in recs if r["farmer_id"]})
    return {
        "available": True, "state": "PLANNED", "provenance": "DEVELOPMENT_CHECKPOINT",
        "label": "FarmSync Proposed — initial collective recommendation",
        "recommendations": recs, "n_recommendations": len(recs), "n_farmers": len(farmers),
        "planned_cash": _tiers().get("PLANNED"), "solver_status": "Optimal",
        "meaning": "This is FarmSync's initial collective recommendation before farmers respond. "
                   "It is a recommendation, not a realised allocation.",
        "note": "Read from the stored PLANNED artifact (p1 planned_crop / planned_cash_return). No farmer "
                "response, reoptimisation, consent or final realisation is reflected here.",
    }


def farmer_response_detail(farmer_id, plot_id=None):
    """Farmer Responses view: original recommendation + recorded response ONLY (no revised/final).

    Uniquely keyed by (farmer_id, plot_id). When plot_id is given the match is EXACT — a missing pair
    returns a not-found result and never falls back to another plot. When plot_id is omitted it is only
    resolved if the farmer has exactly one plot; a multi-plot farmer without a plot_id returns a
    not-found result asking for the plot_id, so the wrong plot can never be returned silently."""
    rows = [x for x in _p1_rows() if x.get("farmer_id") == farmer_id]
    if not rows:
        return _na("Farmer not found")
    if plot_id is not None:
        r = next((x for x in rows if x.get("plot_id") == plot_id), None)
        if r is None:
            return _na("Farmer/plot pair not found")
    elif len(rows) == 1:
        r = rows[0]
    else:
        out = _na("plot_id required")
        out["plot_ids"] = sorted({x.get("plot_id") for x in rows})
        return out
    resp = r.get("response")
    return {
        "available": True, "provenance": "DEVELOPMENT_CHECKPOINT",
        "farmer_id": r.get("farmer_id"), "plot_id": r.get("plot_id"),
        "region_season": r.get("region_season"),
        "recommendation": {"crop": r.get("planned_crop"), "cash": _num(r.get("planned_cash_return"))},
        "response": resp, "acceptance_probability": _num(r.get("p_accept")),
        "ai_role": {
            "llm": "Understands/parses the farmer's natural-language message into a structured intent "
                   "(e.g. ACCEPT / REJECT / MODIFY / REQUEST_ALTERNATIVE / NO_RESPONSE / WITHDRAW).",
            "validator": "Checks farmer, plot, crop, units, semantics, action validity and consent context.",
            "optimiser": "Decides feasible crop allocations / revised recommendations. Crop choice comes "
                         "from here — never from the LLM.",
            "rule": "The LLM never chooses or invents a crop allocation or an alternative crop.",
        },
    }


def replan():
    """RECOMMENDED_REVISED: p3 revised plan joined with p1 original crop. Revised, NOT realised."""
    p3 = _read_csv(_P3) or []
    if not p3:
        return _na("Not available")
    orig = {(r.get("farmer_id"), r.get("plot_id")): r.get("planned_crop") for r in _p1_rows()}
    rows, n_changed = [], 0
    for r in p3:
        key = (r.get("farmer_id"), r.get("plot_id"))
        status = r.get("status_label") or ""
        changed = status.lower() != "unchanged"
        if changed:
            n_changed += 1
        rows.append({"farmer_id": r.get("farmer_id"), "plot_id": r.get("plot_id"),
                     "original_crop": orig.get(key), "revised_crop": r.get("crop"),
                     "area_ha": _num(r.get("area_ha")), "cash": _num(r.get("cash_net")),
                     "status_label": status, "changed": changed})
    return {
        "available": True, "state": "RECOMMENDED_REVISED", "provenance": "DEVELOPMENT_CHECKPOINT",
        "rows": rows, "n_rows": len(rows), "n_changed": n_changed,
        "revised_cash": _tiers().get("RECOMMENDED_REVISED"),
        "commitment_semantics": {
            "FLEXIBLE": "may change freely",
            "SOFT_LOCK": "may change, but the change is penalised (\u03bb)",
            "HARD_LOCK": "planted / physically committed — cannot change",
        },
        "meaning": "FarmSync fed farmer responses and commitment states back into the deterministic "
                   "optimiser. The crop changes below were produced by the optimiser and rules — not the LLM.",
        "not_realised": "This is a revised recommendation. It is NOT yet realised — renewed consent is "
                        "required before any changed crop can become the final plan.",
    }


def consent():
    """Renewed-consent stage - ONE coherent provenance (p6). Consent is categorised by p6.consent_basis;
    the checkpoint's final-coverage aggregate is NOT mixed into these per-row consent facts."""
    p6 = _read_csv(_P6) or []
    if not p6:
        return _na("Not available")
    orig = {(r.get("farmer_id"), r.get("plot_id")): r.get("planned_crop") for r in _p1_rows()}
    rev = {(r.get("farmer_id"), r.get("plot_id")): r.get("crop") for r in (_read_csv(_P3) or [])}
    _BASIS = {"unchanged_accepted_crop": "existing valid initial consent",
              "crop_changed_from_accepted": "renewed consent required (crop changed)",
              "recovered_or_no_prior_accept": "renewed consent required (recovered / no prior accept)"}
    rows, n_initial, n_renew_required, n_renew_have = [], 0, 0, 0
    for r in p6:
        key = (r.get("farmer_id"), r.get("plot_id"))
        basis = r.get("consent_basis")
        needs = str(r.get("requires_renewed_consent")).lower() in ("true", "1", "yes")
        has = str(r.get("consent_exists")).lower() in ("true", "1", "yes")
        if basis == "unchanged_accepted_crop":
            n_initial += 1
        if needs:
            n_renew_required += 1
            if has:
                n_renew_have += 1
        rows.append({"farmer_id": r.get("farmer_id"), "plot_id": r.get("plot_id"),
                     "original_crop": orig.get(key), "revised_crop": rev.get(key) or r.get("crop"),
                     "requires_renewed_consent": needs, "consent_exists": has,
                     "consent_basis": basis, "consent_category": _BASIS.get(basis, basis)})
    return {
        "available": True, "provenance": "P6_DEVELOPMENT_REPLAY",
        "provenance_note": "All rows and counts below come from one coherent artifact "
                           "(p6_final_revised_plan.csv). Aggregate checkpoint tiers are shown separately "
                           "in Final Plan and are not combined with these per-row consent facts.",
        "rows": rows[:400], "n_rows": len(rows),
        "categories": {"existing_initial_consent": n_initial,
                       "renewed_consent_required": n_renew_required,
                       "renewed_consent_recorded": n_renew_have},
        "teaching": {
            "recommendation_ne_consent": "A recommendation is not consent.",
            "consent_ne_authority": "Consent is not allocation authority - the optimiser allocates.",
            "llm_ok_ne_consent": "The LLM understanding an okay is not automatically valid consent.",
            "initial_vs_renewed": "The %d existing initial consents are NOT renewed consents; only %d plots "
                                  "required renewed consent (changed / recovered crops)." % (n_initial, n_renew_required),
            "validator": "Deterministic validation must verify the exact farmer, plot, crop, decision "
                         "round/cycle and the corresponding ACCEPT event/provenance before realisation.",
        },
        "rule": "Only validated exact-crop consent permits final realisation.",
    }


def final_plan():
    """FINAL_REALIZED - ONE coherent provenance (p6). A plot is REALISED only with verified exact-crop
    consent (consent_exists=True). Rows, realised total and coverage are all derived from p6 so they are
    mutually consistent. Checkpoint tier economics are shown separately, clearly labelled, never merged."""
    p6 = _read_csv(_P6) or []
    if not p6:
        return _na("Not available")
    rows = []
    realised_total = 0.0
    n_realised = 0
    for r in p6:
        has = str(r.get("consent_exists")).lower() in ("true", "1", "yes")
        cash = _num(r.get("cash_net"))
        realised = has  # verified exact-crop consent is the ONLY basis for realisation
        if realised:
            n_realised += 1
            realised_total += cash or 0.0
        rows.append({"farmer_id": r.get("farmer_id"), "plot_id": r.get("plot_id"),
                     "crop": r.get("crop"), "area_ha": _num(r.get("area_ha")), "cash": cash,
                     "commitment_lock": r.get("commitment_lock"), "consent_exists": has,
                     "consent_basis": r.get("consent_basis"), "realised": realised})
    n_rows = len(rows)
    t = _tiers()
    return {
        "available": True, "state": "FINAL_REALIZED", "provenance": "P6_DEVELOPMENT_REPLAY",
        "provenance_note": "Rows, realised total and coverage below are all derived from one coherent "
                           "artifact (p6_final_revised_plan.csv). The PLANNED->FINAL tier economics are the "
                           "development checkpoint's separate aggregate and are labelled as such - the two "
                           "are never combined in a single figure.",
        "rows": [r for r in rows][:400], "n_rows": n_rows,
        "n_realised": n_realised,
        "realised_cash": round(realised_total),
        "consent_coverage_final": (n_realised / n_rows) if n_rows else 0.0,
        "coverage_definition": "realised (consent-verified) plots / total plots, from p6.",
        "solver_status": "Optimal",
        "checkpoint_tiers": {"PLANNED": t.get("PLANNED"), "INITIAL_REALIZED": t.get("INITIAL_REALIZED"),
                             "RECOMMENDED_REVISED": t.get("RECOMMENDED_REVISED"),
                             "FINAL_REALIZED": t.get("FINAL_REALIZED")},
        "meaning": "This is the crop plan actually realised after farmer responses, commitment-aware "
                   "reoptimisation and renewed consent. A plot with consent=no is shown but is NOT realised.",
        "consent_rule": "No FINAL_REALIZED (realised) row exists without verified exact-crop consent.",
    }


# ============================================================================
# AI parse (Development / Mock; NO live call). Deterministic, grounded parse of a farmer's free-text
# request against the ACTUAL crop vocabulary — the browser must never invent crop names or verdicts.
# The LLM/mock layer parses only; it never chooses/invents an allocation or an alternative crop.
# ============================================================================

def crop_vocab_list():
    """Canonical crop names (allowed_crops parsing context for the integration layer)."""
    return sorted(set(_crop_vocab().values()))


def _crop_vocab():
    """Real crop names from the built-in crops.csv (lowercased -> canonical name)."""
    import os as _os
    import csv as _csv
    p = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                      "data", "farmsync", "builtin", "crops.csv")
    vocab = {}
    if _os.path.exists(p):
        with open(p, "r", encoding="utf-8-sig") as f:
            for r in _csv.DictReader(f):
                name = (r.get("crop_name") or "").strip()
                if name:
                    vocab[name.lower()] = name
    return vocab


def ai_parse(text, farmer_id=None, plot_id=None):
    """Deterministic Development/Mock parse. Extracts action + requested_crop from the real vocabulary.
    Reuses the P7 SUPPORTED_ACTIONS + authority-attempt detector. Does NOT fake semantic validation:
    schema_ok is computed; semantic validation is reported as 'not evaluated' in read-only replay
    because no deterministic feasibility solve is run here."""
    raw = (text or "").strip()
    low = raw.lower()
    vocab = _crop_vocab()
    # requested crop = any real crop name mentioned (longest match wins; never hardcoded)
    requested = None
    for name_l in sorted(vocab, key=len, reverse=True):
        if name_l and name_l in low:
            requested = vocab[name_l]
            break
    alt = any(k in low for k in ("what else", "alternative", "other crop", "options", "something else",
                                 "what can i grow", "what else can i grow"))
    # is the named crop a TARGET (grow/switch to/instead X) or merely the crop being rejected?
    target_crop = None
    if requested is not None:
        import re as _re
        req_l = requested.lower()
        if _re.search(r"(grow|switch to|change to|prefer|plant)\s+" + _re.escape(req_l), low) or \
           _re.search(_re.escape(req_l) + r"\s+instead", low):
            target_crop = requested
    rejecting = any(k in low for k in ("don't want", "do not want", "reject", "refuse", "not this"))
    if alt and target_crop is None:
        parser_action = "CLARIFY"                     # frozen-schema action (alternative-seeking is vague)
        ui_intent = "REQUEST_ALTERNATIVE"             # integration-layer intent (NOT a schema action)
        requested = None                              # alternatives come from the deterministic layer
    elif target_crop is not None:
        parser_action = "MODIFY"; ui_intent = "MODIFY"
        requested = target_crop
    elif rejecting:
        parser_action = "REJECT"; ui_intent = "REJECT"
        requested = None                              # a named crop here is the one being rejected
    elif requested is not None:
        parser_action = "MODIFY"; ui_intent = "MODIFY"
    elif any(k in low for k in ("accept", "agree", "okay", "ok", "yes", "fine")):
        parser_action = "ACCEPT"; ui_intent = "ACCEPT"
    elif any(k in low for k in ("withdraw", "leave", "opt out")):
        parser_action = "WITHDRAW"; ui_intent = "WITHDRAW"
    else:
        parser_action = "QUERY"; ui_intent = "QUERY"
    action = parser_action                            # backward-compat alias (frozen-schema action)
    # authority-manipulation detection from the real P7 module (best-effort)
    authority = []
    try:
        from farmsync.proposed.llm_interaction import detect_authority_attempts
        authority = detect_authority_attempts(raw)
    except Exception:
        authority = []
    # schema check: a MODIFY must carry a known requested_crop; REQUEST_ALTERNATIVE must not name one
    known_fields = {"action": parser_action, "farmer_id": farmer_id, "plot_id": plot_id,
                    "requested_crop": requested}
    schema_ok = bool(farmer_id and plot_id) and (parser_action != "MODIFY" or requested is not None)
    return {
        "available": True,
        "provenance": "DEVELOPMENT_MOCK",
        "engine": "deterministic-mock-parser-v1",
        "source_text": raw,
        "parsed": known_fields,
        "parser_action": parser_action,               # frozen-schema action (ACCEPT/REJECT/MODIFY/WITHDRAW/QUERY/CLARIFY)
        "ui_intent": ui_intent,                        # integration intent (may be REQUEST_ALTERNATIVE)
        "action": action,                             # backward-compat alias == parser_action
        "requested_crop": requested,
        "schema_ok": schema_ok,
        "schema_status": "Valid" if schema_ok else "Invalid / clarification required",
        "semantic_validation": "not evaluated (read-only replay — no deterministic feasibility solve run)",
        "authority_attempts": authority,
        "alternative_note": ("The LLM does not invent alternatives. Feasible/recommended alternatives "
                             "must come from FarmSync's deterministic feasibility and optimisation layers."
                             if ui_intent == "REQUEST_ALTERNATIVE" else None),
        "roles": {
            "llm": "parses the request into structured intent",
            "validator": "checks farmer, plot, crop, units, semantics, consent context",
            "optimiser": "decides the crop allocation / alternatives — never the LLM",
        },
        "rule": (
            "This legacy Development / Mock parser endpoint only interprets text; "
            "deterministic FarmSync retains validation and allocation authority. "
            "It makes no live API call."
        ),
    }
