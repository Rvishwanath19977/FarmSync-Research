"""
Proposed — Uncertainty-v1 layer (UNCERTAINTY_PROTOCOL v1-FROZEN).

Paired scenario-based uncertainty evaluation with SYNTHETIC EXOGENOUS realisations. For each
(seed, condition) exactly ONE Realisation is drawn deterministically from the frozen substreams and
reused across B1/B2/B3/Proposed. This is NOT stochastic optimisation: the existing deterministic
optimisation is solved under the realised scenario. All severities/frequencies are
SYNTHETIC_EXPERIMENTAL (config), not empirical frequencies.

Channels (each perturbs only its own causal variable):
  W weather      -> ET0 multiplier (region x season) via climate._ET0_MULT -> CWR/NIR feasibility. No Ky.
  M market       -> AGMARKNET price mult (crop x region) + absorption mult (crop GLOBAL) via operational.
                    No MSP floor; no cost perturbation.
  R resource     -> one shared per-farmer multiplier applied to BOTH cultivation_budget and
                    labour_capacity (instance perturbation). No cost/water perturbation.
  P participation -> pre-offer per-farmer Bernoulli membership; non-participants + plots removed from
                    the instance BEFORE planning (no farmer_response events).

State isolation: weather/market use scoped read-time multipliers on the operational/climate modules,
set and CLEARED via the apply() context (try/finally). Resource/participation transform a DEEP COPY of
the instance. Baseline data and the frozen artifacts are never mutated. farmer_response is unchanged.
"""
from __future__ import annotations
import copy
import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass, field

from .. import config as C
from .. import climate
from ..ingest import operational as opdata
from ..generate import CROPS


SEASONS = ("kharif", "rabi")


# --- deterministic keyed draw ------------------------------------------------------------------
def _u01(*parts) -> float:
    key = ":".join(str(p) for p in parts)
    return int(hashlib.sha256(key.encode()).hexdigest(), 16) / (1 << 256)


def _pick(u: float, states: dict):
    """states = {label: (multiplier, probability)}; ordered. Returns (label, multiplier)."""
    acc = 0.0
    for label, (mult, prob) in states.items():
        acc += prob
        if u < acc:
            return label, mult
    last = list(states)[-1]
    return last, states[last][0]


def _cycle_id(seed) -> str:
    return str(seed)


@dataclass
class Realisation:
    seed: int
    condition: str
    channels: set
    weather_state: dict = field(default_factory=dict)      # (region, season) -> (label, mult)
    price_mult: dict = field(default_factory=dict)         # (region, crop) -> mult
    absorption_state: dict = field(default_factory=dict)   # crop -> (label, mult)
    resource_state: dict = field(default_factory=dict)     # farmer_id -> (label, mult)
    participation: dict = field(default_factory=dict)      # farmer_id -> bool (True = participates)
    realisation_hash: str = ""

    def _et0_mult(self):
        return {k: m for k, (_l, m) in self.weather_state.items()}

    def _abs_mult(self):
        return {c: m for c, (_l, m) in self.absorption_state.items()}


def _regions_seasons(plots):
    rs = set()
    for p in plots:
        rs.add((p.region_id, "kharif")); rs.add((p.region_id, "rabi"))
    return sorted(rs)


def draw_realisation(seed, condition, farmers, plots, base=None):
    """Draw the single paired Realisation for (seed, condition) from the frozen substreams."""
    from .. import experiment as exp
    chans = C.UNCERTAINTY_CHANNELS_BY_CONDITION[condition]
    cyc = _cycle_id(seed)
    r = Realisation(seed=seed, condition=condition, channels=set(chans))

    # Weather (region x season) from weather_hazard
    if "W" in chans:
        sub = exp.substream(seed, "weather_hazard", base)
        for (region, season) in _regions_seasons(plots):
            u = _u01(sub, region, season, cyc, "weather")
            r.weather_state[(region, season)] = _pick(u, C.WEATHER_ET0_STATES)

    # Market: price (crop x region) + absorption (crop GLOBAL) from market_shock
    if "M" in chans:
        sub = exp.substream(seed, "market_shock", base)
        crop_names = [c.crop_name for c in CROPS]
        regions = sorted({p.region_id for p in plots})
        for crop in crop_names:
            for region in regions:
                u = _u01(sub, crop, region, cyc, "price")
                _lbl, m = _pick(u, C.MARKET_PRICE_STATES)
                r.price_mult[(region, crop)] = m
            ua = _u01(sub, crop, cyc, "absorption")            # crop-GLOBAL: NO region in key
            r.absorption_state[crop] = _pick(ua, C.MARKET_ABSORPTION_STATES)

    # Resource: one shared per-farmer state from resource_shock (applied to budget AND labour)
    if "R" in chans:
        sub = exp.substream(seed, "resource_shock", base)
        for f in farmers:
            u = _u01(sub, f.farmer_id, cyc, "resource_state")
            r.resource_state[f.farmer_id] = _pick(u, C.RESOURCE_STATES)

    # Participation: pre-offer per-farmer Bernoulli from participation_scenario
    if "P" in chans:
        sub = exp.substream(seed, "participation_scenario", base)
        rate = C.PARTICIPATION_PRIMARY_RATE
        for f in farmers:
            u = _u01(sub, f.farmer_id, cyc, "participation")
            r.participation[f.farmer_id] = (u < rate)
    else:
        for f in farmers:
            r.participation[f.farmer_id] = True

    r.realisation_hash = realisation_hash(r)
    return r


def realisation_hash(r: Realisation) -> str:
    """Deterministic hash of the realisation content (order-independent, stable across methods)."""
    payload = {
        "seed": r.seed, "condition": r.condition, "channels": sorted(r.channels),
        "weather": sorted((f"{a}|{b}", lbl, round(m, 6)) for (a, b), (lbl, m) in r.weather_state.items()),
        "price": sorted((f"{a}|{b}", round(m, 6)) for (a, b), m in r.price_mult.items()),
        "absorption": sorted((c, lbl, round(m, 6)) for c, (lbl, m) in r.absorption_state.items()),
        "resource": sorted((fid, lbl, round(m, 6)) for fid, (lbl, m) in r.resource_state.items()),
        "participation": sorted((fid, bool(v)) for fid, v in r.participation.items()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


# --- scoped application context (weather + market read-time multipliers) ------------------------
@contextmanager
def apply(r: Realisation):
    """Install weather ET0 + market price/absorption multipliers for the duration of the block, then
    ALWAYS clear them (try/finally) so a later U0 in the same process is unaffected (UJ->U0 isolation).
    Resource + participation are applied by perturb_instance (explicit deep copy), not here."""
    try:
        if "W" in r.channels:
            climate.set_et0_mult(r._et0_mult())
        if "M" in r.channels:
            opdata.set_market_mult(r.price_mult, r._abs_mult())
        yield r
    finally:
        climate.clear_et0_mult()
        opdata.clear_market_mult()


# --- instance perturbation (participation removal + resource scaling) ---------------------------
def perturb_instance(instance, r: Realisation):
    """Return a DEEP COPY of the instance with participation removed and resource multipliers applied.
    The original instance (and baseline data) is never mutated. Hard-lock/planted state is not touched
    here (planning-input stage). Non-participants and all their plots are removed BEFORE planning."""
    inst = copy.deepcopy(instance)
    keep_farmers = [f for f in inst["farmers"] if r.participation.get(f.farmer_id, True)]
    keep_ids = {f.farmer_id for f in keep_farmers}
    keep_plots = [p for p in inst["plots"] if p.farmer_id in keep_ids]
    if "R" in r.channels:
        for f in keep_farmers:
            _lbl, m = r.resource_state.get(f.farmer_id, ("NORMAL", 1.0))
            f.cultivation_budget = max(0.0, f.cultivation_budget * m)
            f.labour_capacity = max(0.0, f.labour_capacity * m)
    inst["farmers"] = keep_farmers
    inst["plots"] = keep_plots
    return inst


# --- orchestrator: one condition, paired across B1/B2/B3/Proposed -------------------------------
def _tier_cash_area(allocs):
    return round(sum(a.cash_net for a in allocs), 0), round(sum(a.area_ha for a in allocs), 3)


def baseline_record(name, res):
    """Structured baseline record from the ACTUAL solver status. Only Optimal exposes allocations /
    continuous metrics; non-Optimal never exposes a pseudo-solution and never imputes zero."""
    status = getattr(res, "solver", {}).get("status", None)
    if status == "Optimal":
        cash, area = _tier_cash_area(res.allocations)
        return {"status": "Optimal", "optimal": True, "failed_stage": None,
                "cash": cash, "area": area, "n": len(res.allocations)}
    return {"status": status, "optimal": False, "failed_stage": f"{name}.solve",
            "cash": None, "area": None, "n": None}


def run_uncertainty_condition(seed, condition, base=None, run_proposed=True):
    """Run one uncertainty condition end-to-end on the SAME realisation for all methods.

    Sequence: base instance -> draw ONE realisation -> perturb instance (participation+resource)
    -> within apply() (weather+market) solve B1/B2/B3 on the perturbed instance and, if requested,
    run the causal Proposed action-consent layer on the SAME perturbed instance. Baselines and
    Proposed share the identical realisation_hash.
    """
    from .. import experiment as exp
    from ..ilp_reference import run_b1_ilp, run_b2_ilp, run_b3_ilp
    from .. import fairness as fair
    from . import actions as A

    inst0 = exp.build_instance(seed, tightness="base")
    r = draw_realisation(seed, condition, inst0["farmers"], inst0["plots"], base)
    inst = perturb_instance(inst0, r)
    farmers, plots = inst["farmers"], inst["plots"]

    out = {"meta": {"protocol": "uncertainty-v1", "provenance": C.UNCERTAINTY_PROVENANCE,
                    "seed": seed, "condition": condition, "channels": sorted(r.channels),
                    "realisation_hash": r.realisation_hash, "instance_hash": inst0["record"]["instance_hash"]},
           "participating_farmers": len(farmers), "participating_plots": len(plots),
           "channel_summary": _summarise(r)}

    with apply(r):
        out["baselines"] = {}
        for name, runner in (("B1", run_b1_ilp), ("B2", run_b2_ilp), ("B3", run_b3_ilp)):
            res = runner(farmers, plots, CROPS)
            out["baselines"][name] = baseline_record(name, res)
        if run_proposed:
            try:
                layer = A.run_action_consent_layer(
                    seed=seed, profile="PRIMARY", base=base, instance=inst,
                    uncertainty_condition=condition, realisation_hash=r.realisation_hash)
                out["proposed"] = {
                    "optimal": True,
                    "realisation_hash": layer["meta"]["realisation_hash"],
                    "realisation_hash_match": (layer["meta"]["realisation_hash"] == r.realisation_hash),
                    "uncertainty_condition": layer["meta"]["uncertainty_condition"],
                    "tiers": layer["tiers"], "action_counts": layer["action_counts"],
                    "withdrawn_farmers": layer["withdrawn_farmers"],
                    "renewed_prompts": layer["renewed_prompts"], "renewed_counts": layer["renewed_counts"],
                    "consent_coverage_final": layer["consent_coverage_final"],
                    "reopt_status": layer["reopt_status"], "conc_status": layer["conc_status"],
                    "fairness_v2_final": layer["fairness_v2_final"]}
            except A.ProposedInfeasibleError as e:
                # a non-Optimal reopt/concentration under the shock is a valid recorded outcome.
                # Programming errors (KeyError/TypeError/etc.) are NOT caught here — they propagate.
                out["proposed"] = {"optimal": False, "failed_stage": e.failed_stage,
                                   "status": e.status, "cash": None,
                                   "realisation_hash": r.realisation_hash,
                                   "realisation_hash_match": True,
                                   "uncertainty_condition": condition}
    return out


def _summarise(r: Realisation):
    def counts(items):
        d = {}
        for lbl in items:
            d[lbl] = d.get(lbl, 0) + 1
        return d
    return {
        "weather_states": counts([lbl for (lbl, _m) in r.weather_state.values()]),
        "absorption_states": counts([lbl for (lbl, _m) in r.absorption_state.values()]),
        "resource_states": counts([lbl for (lbl, _m) in r.resource_state.values()]),
        "price_cells": len(r.price_mult),
        "participation_true": sum(1 for v in r.participation.values() if v),
        "participation_false": sum(1 for v in r.participation.values() if not v),
    }
