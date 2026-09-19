"""
Authoritative experiment configuration — single source of truth.

Import these constants; never hard-code the canonical epsilon or version strings
elsewhere. Explicit sensitivity/frontier runs may pass a different epsilon, but the
publication-candidate default is CANONICAL_B3_EPSILON.
"""

CANONICAL_B3_EPSILON = 0.95          # approved publication-candidate B3 fairness floor
FORMULATION_VERSION = "ilp-ref-v1"   # optimisation formulation family
FAIRNESS_VERSION = "fairness-v2"     # canonical fairness metric implementation
TSTAR_TOLERANCE = 1.0                # ₹ tolerance for canonical-B2-optimum agreement
# Numerical-only slack on the per-capable-farmer fairness floor (min normalised return).
# Set to 0.0 => enforce the exact full-precision floor; a positive value is a purely
# numerical guard against the max-attainable knife-edge, NOT a substantive fairness
# relaxation. Value determined empirically (see PROGRESS Phase-3 correction).
FAIRNESS_FLOOR_NUMERIC_TOL = 0.0
# Post-shock (Phase-5) reoptimisation re-imposes a recomputed t_floor_shock (a MAX-attained
# value) as a hard floor on a tighter reduced instance, which hits a max-attained-floor
# knife-edge on some correlated-hazard scenarios: a feasible recovery plan provably exists
# (the t_floor stage found it) but CBC rejects it at exact tolerance. This is the smallest
# tolerance (== CBC's native feasibility-tolerance scale) that lets the provably-feasible
# plan be extracted; verified numerical, NOT a substantive fairness relaxation (achieved
# min_norm stays within ~2.5e-6 of the exact floor). Genuine infeasibility (e.g. surviving
# hard locks + concentration with no feasible plan) is NOT masked by this — it fails at the
# E*_shock stage, before any fairness floor, and is preserved as INFEASIBLE.
RESILIENCE_FLOOR_NUMERIC_TOL = 1e-7


# ------------------------------------------------------------------------------
# Frozen farmer-action + renewed-consent policy (ACTION_CONSENT_PROTOCOL v1).
# ALL values are SYNTHETIC_EXPERIMENTAL design parameters — NOT empirical
# Indian-farmer prevalence estimates. Frozen before final30; never tuned from results.
# ------------------------------------------------------------------------------
ACTION_POLICY_VERSION = "action-consent-v1"
ACTION_PROVENANCE = "SYNTHETIC_EXPERIMENTAL"

# p_accept(f) = clip(P_ACCEPT_BASE + P_ACCEPT_SLOPE * (risk_tolerance - 0.5), 0, 1)
P_ACCEPT_BASE = 0.85
P_ACCEPT_SLOPE = 0.20

# Conditional shares of the NON-acceptance mass (initial round). Not unconditional rates.
INITIAL_NONACCEPT_SPLIT = {"REJECT": 0.45, "MODIFY": 0.35, "NO_RESPONSE": 0.20}
# Conditional shares of the NON-acceptance mass (renewed round).
RENEWED_NONACCEPT_SPLIT = {"REJECT": 0.70, "NO_RESPONSE": 0.30}

# Farmer-level withdrawal, drawn once per farmer per cycle (keyed WITHOUT plot_id).
P_WITHDRAW = 0.02

# Sensitivity profiles: additive shift to p_accept (clipped [0,1]); splits + P_WITHDRAW unchanged.
ACTION_SENSITIVITY = {"PRIMARY": 0.0, "S1": -0.15, "S2": 0.10}


# ------------------------------------------------------------------------------
# Frozen uncertainty-v1 policy (UNCERTAINTY_PROTOCOL v1-FROZEN). Paired scenario-based
# uncertainty evaluation with SYNTHETIC EXOGENOUS realisations — NOT stochastic optimisation,
# NOT empirical Indian agricultural frequencies. Frozen before final30; never tuned from results.
# ------------------------------------------------------------------------------
UNCERTAINTY_VERSION = "uncertainty-v1"
UNCERTAINTY_PROVENANCE = "SYNTHETIC_EXPERIMENTAL"

# Weather: ET0 multiplier states (region x season). ET0-only; NO Ky penalty in v1.
WEATHER_ET0_STATES = {"LOW_EVAPORATIVE_DEMAND": (0.90, 0.20),
                      "NORMAL": (1.00, 0.60),
                      "HIGH_EVAPORATIVE_DEMAND": (1.15, 0.20)}
# Market price multiplier states (crop x region). AGMARKNET operational price; NO MSP floor.
MARKET_PRICE_STATES = {"LOW": (0.90, 0.25), "NORMAL": (1.00, 0.50), "HIGH": (1.10, 0.25)}
# Market absorption multiplier states (crop GLOBAL — matches op_absorption(crop)).
MARKET_ABSORPTION_STATES = {"LOW": (0.85, 0.20), "NORMAL": (1.00, 0.60), "HIGH": (1.15, 0.20)}
# Resource: one shared per-farmer state applied to BOTH budget and labour. No cost/water perturbation.
RESOURCE_STATES = {"NORMAL": (1.00, 0.70), "CONSTRAINED": (0.85, 0.30)}
# Participation: pre-offer per-farmer Bernoulli membership. PRIMARY/core level.
PARTICIPATION_PRIMARY_RATE = 0.90
# Descriptive-only participation sensitivity ladder (NOT in the inferential U-family).
PARTICIPATION_LADDER = [1.0, 0.90, 0.75, 0.60, 0.40]
# Core ablation conditions (exactly six). No S x U cross in v1.
UNCERTAINTY_CONDITIONS = ["U0", "UW", "UM", "UR", "UP", "UJ"]
UNCERTAINTY_CHANNELS_BY_CONDITION = {
    "U0": set(), "UW": {"W"}, "UM": {"M"}, "UR": {"R"}, "UP": {"P"},
    "UJ": {"W", "M", "R", "P"}}
# Analysis-only bootstrap seed for 95% CIs (NOT a FarmSync scientific substream).
UNCERTAINTY_ANALYSIS_BOOTSTRAP_SEED = 20260812
UNCERTAINTY_BOOTSTRAP_RESAMPLES = 10000


# ------------------------------------------------------------------------------
# Publication configuration (single source of truth), frozen BEFORE final30.
# ε/λ/α are development-calibrated EXPERIMENTAL DESIGN parameters — NOT empirical
# agricultural constants, NOT regulatory thresholds, and NOT selected from final30.
# Any later change requires a protocol amendment + version increment (see
# docs/farmsync/PUBLICATION_CONFIG_FREEZE.md).
# ------------------------------------------------------------------------------
PUBLICATION_CONFIG_VERSION = "farmsync-publication-config-v1"
PUBLICATION_EPSILON = 0.95          # canonical B3 fairness-efficiency floor (== CANONICAL_B3_EPSILON)
PUBLICATION_LAMBDA = 0.05           # Phase-3 stability penalty weight (smallest positive; see freeze doc)
PUBLICATION_ALPHA = 0.40            # Phase-4 within-crop concentration cap (~40% max largest-producer share)
PUBLICATION_ACTION_PROFILE = "PRIMARY"
PUBLICATION_ACTION_PROTOCOL = "action-consent-v1"
PUBLICATION_UNCERTAINTY_PROTOCOL = "uncertainty-v1"
PUBLICATION_FAIRNESS = "fairness-v2"
# Consistency guard: publication epsilon must equal the canonical B3 epsilon.
assert PUBLICATION_EPSILON == CANONICAL_B3_EPSILON, "publication epsilon must match CANONICAL_B3_EPSILON"
