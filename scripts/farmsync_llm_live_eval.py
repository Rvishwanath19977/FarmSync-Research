#!/usr/bin/env python3
"""FarmSync — LIVE DEVELOPMENT EVALUATION (41-case dev set). QA/evaluation only.

*** LIVE DEVELOPMENT EVALUATION — NOT THE >=300-CASE BENCHMARK. ***
The 41-case set is a prompt-engineering / architecture-validation set; live accuracy here informs prompt/
schema work and is NOT publication accuracy or the frozen benchmark.

Loads the FROZEN case set `results/farmsync/proposed/p7_dev_cases.jsonl` and verifies it BEFORE any API
call with a DUAL GATE: the case-file byte SHA-256 (46a005d5…, matches RESULT_FROZEN PACKAGE_MANIFEST) AND
the semantic case_set_hash the frozen function actually produces (da556e3923daec5a). The frozen manifest's
recorded value (9b408d5d013ac284) is an inherited P7 metadata inconsistency — recorded for reference,
never a gate, and never "fixed" by touching any frozen artifact. Reconstructs the deterministic snapshot /
base-state via the same pipeline that generated the frozen P7 metrics (build helper below; outside the
frozen scientific files).

Two-layer WITHDRAW handling (the preserved P7 gold predates the action-consent-v1 deterministic withdrawal
policy, so raw historical equivalence is INTENTIONALLY 39/41):
  LAYER 1 — RAW HISTORICAL COMPATIBILITY: records the raw/original-gold profile and requires the KNOWN
            profile to be unchanged (n_cases 41; frozen deterministic-boundary + n_cases comparisons true;
            payload 39/41=0.9512 den 41; execution 1.0 den 12; outcome-N/A 29). This is NOT a claim of
            reproducing the frozen mock metrics — it documents compatibility and pins the known delta.
  LAYER 2 — CURRENT-SEMANTICS PROJECTION: only wd0/wd1 gold labels are replaced by values DERIVED FROM the
            frozen validate_request (never hard-coded); requires payload 41/41=1.0 and execution 12/12=1.0
            with WITHDRAW execution N/A. Both layers gate mock AND live; live-development scoring uses the
            reconciled projection so a correctly-parsed current-policy WITHDRAW is not penalised.

Explicit mode (off|mock|live). In `live`, missing key / cases-unavailable / hash-mismatch / client-init
failure -> NON-ZERO exit (never SKIPPED-success). A model/API failure per case is an explicit sentinel,
never silently replaced by mock output.

PowerShell (Windows):
    $env:FARMSYNC_LLM_MODE="live"
    $env:FARMSYNC_LLM_MODEL="gpt-5.6-terra"
    $env:OPENAI_API_KEY="..."          # env only; never persisted
    python scripts/farmsync_llm_live_eval.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from farmsync.proposed import llm_interaction as li
from farmsync.proposed import llm_eval as le
from farmsync.proposed import llm_service as svc

# ---------------------------------------------------------------------------------------------------- #
# CASE-SET IDENTITY — DUAL GATE (inherited P7 metadata inconsistency; resolved WITHOUT touching any
# frozen artifact). Investigation (byte-hash matched RESULT_FROZEN PACKAGE_MANIFEST; manifest + JSONL +
# llm_interaction.py all byte-match the immutable freeze) found the frozen `p7_llm_manifest.json` records
# a case_set_hash (9b408d5d013ac284) that does NOT equal the value the frozen `case_set_hash()` produces
# over the authentic on-disk JSONL (da556e3923daec5a). The HISTORICAL CAUSE of that recorded value is
# UNKNOWN (not established); the case file itself is authentic (its byte SHA-256 matches the RESULT_FROZEN
# PACKAGE_MANIFEST). This is treated as an inherited metadata inconsistency, not drift.
#
# We therefore gate on the STRONGEST identity of the authentic artifact:
#   (a) byte SHA-256 of p7_dev_cases.jsonl                    -> primary, tamper-evident
#   (b) semantic case_set_hash() the frozen function produces -> confirms the parsed case set
# BOTH must match their pinned values (a future real drift still cannot slip through). The legacy manifest
# value is RECORDED for provenance/reference only — it is NOT a gate (it is known-inconsistent).
EXPECTED_CASE_FILE_SHA256 = "46a005d5089aaf9a2db4f922806ef503d3b9bd7bb8b2a1867ce639f75b2530fe"
EXPECTED_CASE_SET_HASH = "da556e3923daec5a"     # semantic hash the frozen case_set_hash() ACTUALLY returns
LEGACY_MANIFEST_CASE_SET_HASH = "9b408d5d013ac284"  # value recorded in frozen p7_llm_manifest.json (reference only)
CASE_SET_HASH_DISCREPANCY_NOTE = (
    "Inherited P7 metadata inconsistency: frozen p7_llm_manifest.json records case_set_hash "
    "9b408d5d013ac284, but the frozen case_set_hash() over the authentic on-disk p7_dev_cases.jsonl "
    "yields da556e3923daec5a. The historical cause of the recorded manifest value is UNKNOWN (not "
    "established). The case file is authentic (byte SHA-256 matches RESULT_FROZEN PACKAGE_MANIFEST). No "
    "frozen artifact was modified; the evaluator gates on the byte SHA-256 + the actual semantic hash and "
    "records the legacy manifest value for reference only.")
MASTER_SEED = 20260812                          # frozen instance seed (from p7_llm_manifest.json)
N_FARMERS = 500                                 # PROVEN below via instance_hash, not inferred
EXPECTED_INSTANCE_HASH = "5ea24037c2d9cb6a"     # p7_llm_manifest.json instance_hash (proves 20260812/500)
CASES_JSONL = os.path.join(_ROOT, "results", "farmsync", "proposed", "p7_dev_cases.jsonl")
FROZEN_MOCK_METRICS = os.path.join(_ROOT, "results", "farmsync", "proposed", "p7_dev_metrics.json")
FROZEN_MANIFEST = os.path.join(_ROOT, "results", "farmsync", "proposed", "p7_llm_manifest.json")
PROCESSED_DIR = os.path.join(_ROOT, "data", "farmsync", "processed")
OUT_DIR = os.path.join(_ROOT, "results", "farmsync", "qa", "llm_live")


# --------------------------------------------------------------------------- case set
def load_jsonl_cases(path=CASES_JSONL):
    if not os.path.exists(path):
        raise FileNotFoundError("frozen dev cases not found: %s" % path)
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_case_identity(cases, cases_path=CASES_JSONL):
    """DUAL GATE: the authentic case set must match BOTH its pinned byte SHA-256 AND the semantic hash the
    frozen case_set_hash() actually produces. Returns an identity record (recorded in report + provenance);
    raises RuntimeError if EITHER gate fails. The legacy manifest value is recorded for reference only."""
    byte_sha = _file_sha256(cases_path)
    semantic = li.case_set_hash(cases)
    manifest_recorded = None
    try:
        manifest_recorded = json.load(open(FROZEN_MANIFEST)).get("case_set_hash")
    except Exception:
        pass
    try:
        case_file_display = os.path.relpath(cases_path, _ROOT).replace("\\", "/")
    except ValueError:
        # Windows cross-drive paths (e.g. pytest temp on C:, repo on R:) cannot be made relative.
        case_file_display = os.path.basename(cases_path)
    identity = {
        "case_file": case_file_display,
        "case_file_sha256": byte_sha,
        "case_file_sha256_expected": EXPECTED_CASE_FILE_SHA256,
        "case_file_sha256_match": (byte_sha == EXPECTED_CASE_FILE_SHA256),
        "semantic_case_set_hash": semantic,
        "semantic_case_set_hash_expected": EXPECTED_CASE_SET_HASH,
        "semantic_case_set_hash_match": (semantic == EXPECTED_CASE_SET_HASH),
        "legacy_manifest_case_set_hash": LEGACY_MANIFEST_CASE_SET_HASH,
        "legacy_manifest_case_set_hash_in_manifest": manifest_recorded,
        "legacy_matches_actual": (semantic == LEGACY_MANIFEST_CASE_SET_HASH),   # expected False (the discrepancy)
        "discrepancy_note": CASE_SET_HASH_DISCREPANCY_NOTE,
        # precise: this evaluator verifies ONLY the case-file byte identity, not all frozen artifacts.
        "frozen_case_file_byte_identity_verified": (byte_sha == EXPECTED_CASE_FILE_SHA256),
    }
    if not identity["case_file_sha256_match"]:
        raise RuntimeError("case-file byte SHA-256 mismatch: got %s expected %s" % (byte_sha, EXPECTED_CASE_FILE_SHA256))
    if not identity["semantic_case_set_hash_match"]:
        raise RuntimeError("semantic case_set_hash mismatch: got %s expected %s" % (semantic, EXPECTED_CASE_SET_HASH))
    return identity


# --------------------------------------------------------------------------- deterministic fixture
# Reconstructs the snapshot/base-state the frozen P7 evaluation used, from the deterministic FarmSync
# pipeline. FREEZE-SAFE: the frozen processed data is loaded READ-ONLY (operational.load reads existing
# CSVs; run_ingest is NOT called, so data/farmsync/processed is never regenerated). The population
# (master_seed=20260812, n_farmers=500) is PROVEN by asserting the reconstructed instance_hash equals the
# manifest's recorded instance_hash 5ea24037c2d9cb6a (only 20260812/500 reproduces it — n=120/300 differ),
# i.e. derived from the artifact chain, not merely read from the manifest.
_FIX = {}


def _manifest_instance_hash():
    try:
        return json.load(open(FROZEN_MANIFEST)).get("instance_hash")
    except Exception:
        return EXPECTED_INSTANCE_HASH


def build_p7_fixture(master_seed=MASTER_SEED, n_farmers=N_FARMERS, processed_dir=PROCESSED_DIR):
    if _FIX.get("v"):
        return _FIX["v"]
    from farmsync.ingest import operational as opdata
    from farmsync.generate import generate_dataset, CROPS
    from farmsync.ilp_reference import run_b3_ilp, b2_ilp_total
    from farmsync import experiment as exp
    from farmsync.experiment import instance_hash
    from farmsync.proposed.participation import AcceptanceConfig, apply_participation
    from farmsync.proposed import commitment as cm

    # A: FREEZE-SAFE read-only load of the existing frozen processed data. Never regenerate the frozen dir.
    if not os.path.isdir(processed_dir) or not os.path.exists(os.path.join(processed_dir, "yield_state.csv")):
        # fallback ONLY if the frozen processed data is missing: regenerate into a TEMP dir (outside freeze
        # scope), never into data/farmsync/processed.
        import tempfile
        from farmsync.ingest.run_ingest import run as _ingest_run
        tmp = tempfile.mkdtemp(prefix="fsqa_p7_processed_")
        raw = os.path.join(_ROOT, "data", "farmsync", "raw_sources")
        _ingest_run(raw, tmp)
        processed_dir = tmp
    opdata.load(processed_dir)                       # read existing CSVs; NO write to the frozen dir

    f, plots, *_ = generate_dataset(master_seed=master_seed, n_farmers=n_farmers)
    # B: PROVE the population from the artifact's recorded instance_hash (only 20260812/500 reproduces it).
    ih = instance_hash(f, plots)
    manifest_ih = _manifest_instance_hash()
    if ih != manifest_ih:
        raise RuntimeError("fixture instance_hash %s != manifest instance_hash %s (population mismatch: "
                           "master_seed/n_farmers do not match the artifact-generation inputs)" % (ih, manifest_ih))
    tstar = b2_ilp_total(f, plots, CROPS)["b2_ilp_cash_total"]
    planned = run_b3_ilp(f, plots, CROPS, tstar=tstar)
    realised, offers = apply_participation(planned, f, exp.substream(master_seed, "farmer_response"), AcceptanceConfig())
    scen = cm.mixed_commitment_scenario(offers, "P3_MIXED_V1")
    snap = li.DeterministicSnapshot.from_pipeline(f, plots, scen, offers)
    base = li.BoundaryState.from_snapshot(snap)
    _FIX["v"] = (snap, base, {"instance_hash": ih, "instance_hash_verified": True,
                              "processed_dir_readonly": (processed_dir == PROCESSED_DIR)})
    return _FIX["v"]


def _relabel_live(metrics, model, mode):
    """§3: reuse the frozen scorer's numeric formulas but relabel the report for LIVE (never write the
    mock-only labels into a live report). Preserves scorer provenance."""
    m = dict(metrics)
    m["live_evaluation"] = (mode == "live")
    m["client"] = mode                                  # 'live' or 'mock'
    m["model"] = model
    m["scorer_provenance"] = "farmsync.proposed.llm_eval._metrics (frozen; formulas reused, not modified)"
    grp = m.pop("_group_parse_metrics_MOCK_architecture_validation_only", None)
    if grp is not None:
        key = "_group_parse_metrics_LIVE_development" if mode == "live" else "_group_parse_metrics_MOCK_development"
        m[key] = grp
    m["note"] = ("LIVE DEVELOPMENT evaluation (41-case dev set); parse-side numbers reflect the live model."
                 if mode == "live" else
                 "MOCK development reproduction (architecture validation); not live accuracy.")
    return m


def _boundary_gate(metrics):
    """§4: None never counts as 100%. Require positive denominators AND rate==1.0 for both equivalence
    groups. Report denominators explicitly."""
    eq = metrics.get("_group_equivalence", {})
    pd = eq.get("validated_payload_equivalence_denominator")
    pr = eq.get("validated_payload_equivalence_rate")
    xd = eq.get("boundary_state_execution_equivalence_denominator")
    xr = eq.get("boundary_state_execution_equivalence_rate")
    ok = (isinstance(pd, int) and pd > 0 and pr == 1.0 and
          isinstance(xd, int) and xd > 0 and xr == 1.0)
    return {"boundary_integrity_pass": bool(ok),
            "validated_payload_equivalence_rate": pr, "validated_payload_equivalence_denominator": pd,
            "boundary_state_execution_equivalence_rate": xr, "boundary_state_execution_equivalence_denominator": xd}


# --------------------------------------------------------------------------- mock reproduction proof
def _reliability_from_preds(preds):
    """§C: live reliability from preds (not only frozen metrics). Counts reconcile exactly to n_cases."""
    n = len(preds)
    ok = sum(1 for p in preds if p.get("parse_status") == "OK")
    api_err = sum(1 for p in preds if p.get("parse_status") == li.API_ERROR)
    refusal = sum(1 for p in preds if p.get("parse_status") == li.MODEL_REFUSAL)
    schema_inv = sum(1 for p in preds if p.get("parse_status") == li.SCHEMA_INVALID)
    other = n - (ok + api_err + refusal + schema_inv)
    schema_valid = sum(1 for p in preds if p.get("schema_valid"))
    schema_invalid = n - schema_valid
    rec = {"n_cases": n, "OK": ok, "API_ERROR": api_err, "MODEL_REFUSAL": refusal,
           "SCHEMA_INVALID": schema_inv, "other_status": other,
           "schema_valid": schema_valid, "schema_invalid": schema_invalid,
           "reconciles": (ok + api_err + refusal + schema_inv + other == n) and (schema_valid + schema_invalid == n)}
    return rec


def verify_fixture_reproduces_mock(cases, snapshot, base_state):
    """LAYER 1 (raw/original-gold historical COMPATIBILITY): score the frozen p7_dev_metrics.json using the
    ORIGINAL preserved gold labels. After the action-consent-v1 WITHDRAW policy this INTENTIONALLY yields
    39/41 payload equivalence (wd0/wd1 diverge). We do NOT expect reproduced=True; instead we assert the
    KNOWN historical profile is unchanged (n_cases 41; frozen deterministic-boundary + n_cases comparisons
    true; payload 39/41=0.9512 den 41; execution 1.0 den 12; outcome-N/A count 29). A hard-fail here means
    the historical profile itself shifted."""
    mock = li.MockLLMClient({c["source_text"]: c["gold_parse"] for c in cases})
    preds, metrics = le.run_dev_benchmark(cases, mock, snapshot, base_state=base_state)
    eq = metrics.get("_group_equivalence", {}) or {}
    out = {"recomputed_equivalence": eq, "n_cases": metrics.get("n_cases")}
    frozen = json.load(open(FROZEN_MOCK_METRICS)) if os.path.exists(FROZEN_MOCK_METRICS) else None
    det_boundary_match = bool(frozen) and (metrics.get("_group_deterministic_boundary") == frozen.get("_group_deterministic_boundary"))
    n_cases_frozen_match = bool(frozen) and (metrics.get("n_cases") == frozen.get("n_cases"))
    pr = eq.get("validated_payload_equivalence_rate")
    pd = eq.get("validated_payload_equivalence_denominator")
    xr = eq.get("boundary_state_execution_equivalence_rate")
    xd = eq.get("boundary_state_execution_equivalence_denominator")
    na = eq.get("outcome_equivalence_not_applicable")
    profile_ok = (
        metrics.get("n_cases") == 41 and det_boundary_match and n_cases_frozen_match
        and pd == 41 and (pr is not None and abs(pr - 0.9512) < 0.001)
        and xd == 12 and xr == 1.0
        and na == 29
    )
    out.update({
        "raw_historical_compatibility_pass": bool(profile_ok),
        "deterministic_boundary_frozen_match": det_boundary_match,
        "n_cases_frozen_match": n_cases_frozen_match,
        "validated_payload_equivalence_rate": pr, "validated_payload_equivalence_denominator": pd,
        "boundary_state_execution_equivalence_rate": xr, "boundary_state_execution_equivalence_denominator": xd,
        "outcome_equivalence_not_applicable": na,
        "expected_profile": {"n_cases": 41, "payload_rate": 0.9512, "payload_denominator": 41,
                             "execution_rate": 1.0, "execution_denominator": 12, "outcome_na": 29},
    })
    return out


# WITHDRAW cases whose PRESERVED P7 gold predates the current action-consent-v1 deterministic withdrawal
# policy. This is the ONLY sanctioned reconciliation scope; anything outside it is a hard failure.
RECONCILE_IDS = frozenset({"wd0", "wd1"})
LEGACY_WITHDRAW_OUTCOME = "NOT_IMPLEMENTED"
LEGACY_WITHDRAW_REASON = "WITHDRAW_REQUIRES_POLICY"


def _derive_current_expectation(case, snapshot, trusted_context=None):
    """Derive the CURRENT authoritative validation outcome + payload for a case from the FROZEN
    validate_request (never hard-coded)."""
    client = li.MockLLMClient({case["source_text"]: case["gold_parse"]})
    pr, st, m = li.parse_request(case["source_text"], client, trusted_context=trusted_context)
    vr = li.validate_request(pr, snapshot, trusted_context=trusted_context)
    return {"validation_outcome": vr.outcome, "payload": vr.deterministic_action_payload,
            "reason_codes": list(vr.reason_codes or [])}


def build_reconciled_projection(cases, snapshot):
    """Compute the exact legacy-vs-current divergence for ALL 41 cases and, if (and only if) the divergent
    set is exactly {wd0, wd1} with the expected legacy WITHDRAW semantics, produce a current-semantics
    evaluation projection where ONLY wd0/wd1 gold labels are replaced by the frozen-validator-derived
    current values. HARD-FAILS otherwise. The on-disk artifacts are never modified; this is in-memory."""
    divergent = []
    for c in cases:
        cur = _derive_current_expectation(c, snapshot, c.get("trusted_context"))
        leg_out = c.get("gold_validation_outcome")
        leg_pay = c.get("gold_payload")
        if cur["validation_outcome"] != leg_out or (cur["payload"] or None) != (leg_pay or None):
            divergent.append((c["id"], c.get("category"), c["gold_parse"].get("action"), leg_out, cur))

    div_ids = {d[0] for d in divergent}
    # SCOPE GUARD (hard-fail): the divergent set must be EXACTLY the sanctioned reconciliation scope, and
    # each must be a WITHDRAW case whose legacy reference is the known pre-policy stub.
    if div_ids != set(RECONCILE_IDS):
        raise RuntimeError("reconciliation scope violation: divergent IDs %s != sanctioned %s "
                           "(a mismatch outside {wd0,wd1} indicates real drift — aborting)"
                           % (sorted(div_ids), sorted(RECONCILE_IDS)))
    for cid, cat, act, leg_out, cur in divergent:
        if act != "WITHDRAW" or cat != "withdraw_parsing" or leg_out != LEGACY_WITHDRAW_OUTCOME:
            raise RuntimeError("reconciliation semantic violation for %s: expected legacy WITHDRAW/"
                               "%s, got action=%s category=%s legacy_outcome=%s"
                               % (cid, LEGACY_WITHDRAW_OUTCOME, act, cat, leg_out))
        if cur["validation_outcome"] != "VALIDATED":
            raise RuntimeError("reconciliation: current validator did not VALIDATE %s (got %s)"
                               % (cid, cur["validation_outcome"]))

    # build the in-memory projection: only wd0/wd1 gold labels replaced with validator-derived current
    recon = []
    manifest = []
    for c in cases:
        if c["id"] in RECONCILE_IDS:
            cur = _derive_current_expectation(c, snapshot, c.get("trusted_context"))
            pc = dict(c)
            pc["gold_validation_outcome"] = cur["validation_outcome"]
            pc["gold_payload"] = cur["payload"]
            recon.append(pc)
            manifest.append({
                "id": c["id"], "category": c.get("category"),
                "legacy_gold_validation_outcome": c.get("gold_validation_outcome"),
                "legacy_reason_codes": [LEGACY_WITHDRAW_REASON],
                "legacy_gold_payload": c.get("gold_payload"),
                "current_authoritative_validation_outcome": cur["validation_outcome"],
                "current_authoritative_payload": cur["payload"],
                "current_reason_codes": cur["reason_codes"],
                "derivation": "frozen validate_request (not hard-coded)",
                "note": ("Legacy Phase-7 WITHDRAW reference (NOT_IMPLEMENTED / WITHDRAW_REQUIRES_POLICY / "
                         "payload None) predates the action-consent-v1 deterministic withdrawal policy now "
                         "implemented by the frozen validator; earlier P7 artifacts are intentionally "
                         "preserved and NOT modified."),
            })
        else:
            recon.append(c)
    # projection identity (hash over the effective scoring basis)
    projection_id = li.case_set_hash(recon)
    projection_sha256 = hashlib.sha256(
        json.dumps(recon, sort_keys=True, default=str).encode()).hexdigest()
    return recon, {"reconciliation_ids": sorted(RECONCILE_IDS), "divergent_ids": sorted(div_ids),
                   "reconciled_cases": manifest,
                   "evaluation_projection_id": projection_id,
                   "evaluation_projection_sha256": projection_sha256}


def current_semantics_projection_check(recon_cases, snapshot, base_state):
    """LAYER 2 (current-semantics): score the validator-derived projection. Expect payload-equivalence
    41/41=1.0 and execution-equivalence 12/12=1.0 with WITHDRAW remaining execution-N/A (not fabricated)."""
    mock = li.MockLLMClient({c["source_text"]: c["gold_parse"] for c in recon_cases})
    preds, metrics = le.run_dev_benchmark(recon_cases, mock, snapshot, base_state=base_state)
    eq = metrics.get("_group_equivalence", {})
    pr = eq.get("validated_payload_equivalence_rate")
    pd = eq.get("validated_payload_equivalence_denominator")
    xr = eq.get("boundary_state_execution_equivalence_rate")
    xd = eq.get("boundary_state_execution_equivalence_denominator")
    # WITHDRAW must remain execution-N/A: it must NOT be in the execution-equivalence denominator.
    withdraw_exec_na = all((not p.get("exec_applicable")) for p in preds
                           if p.get("id") in RECONCILE_IDS or (isinstance(p.get("parsed"), dict)
                                                               and p.get("parsed", {}).get("action") == "WITHDRAW"))
    ok = (pd == 41 and pr == 1.0 and xd == 12 and xr == 1.0 and withdraw_exec_na)
    return {"current_semantics_projection_pass": bool(ok),
            "validated_payload_equivalence_rate": pr, "validated_payload_equivalence_denominator": pd,
            "boundary_state_execution_equivalence_rate": xr, "boundary_state_execution_equivalence_denominator": xd,
            "withdraw_execution_not_applicable": bool(withdraw_exec_na),
            "recomputed_equivalence": eq}


# --------------------------------------------------------------------------- main
# Genuinely implicit-context cases: the message contains no plot, so the current plot is exposed to the
# PARSER (never the trusted farmer identity). This reconstruction is allowed ONLY for the 41-case dev set;
# the >=300 benchmark must carry explicit context from the start and never derive it from gold.
IMPLICIT_CONTEXT_IDS = frozenset({"vague0", "vague1", "vague2", "vague3"})


def build_development_context_projection(cases, allowed_crops=None):
    """Per-case DEVELOPMENT context projection (non-frozen; dev-set only):
      trusted_context["farmer_id"]  = authenticated/requesting farmer (server-side authority for the
                                      validator; NEVER sent to the model).
      trusted_context["current_plot_id"] = current plot exposed to the PARSER ONLY for the four genuinely
                                      implicit-context vague cases; NOT for missing_plot or any other case.
      trusted_context["allowed_crops"] = crop vocabulary (parser context).
    Returns (per_case_trusted, projection_meta). The farmer_id is the authenticated identity the real app
    supplies; here it is reconstructed from the dev gold for the 41-case set only, and this is disclosed."""
    per = {}
    entries = []
    for c in cases:
        fid = c["gold_parse"].get("farmer_id")           # authenticated/requesting farmer (server-side)
        tc = {"farmer_id": fid}
        if allowed_crops:
            tc["allowed_crops"] = list(allowed_crops)
        expose_plot = None
        if c["id"] in IMPLICIT_CONTEXT_IDS:
            expose_plot = c["gold_parse"].get("plot_id")  # current plot, PARSER-visible (vague only)
            tc["current_plot_id"] = expose_plot
        per[c["id"]] = tc
        entries.append({"case_id": c["id"], "category": c.get("category"),
                        "trusted_farmer_id_server_side": fid,
                        "current_plot_id_exposed_to_parser": expose_plot})
    proj = {
        "description": ("Development context projection for the 41-case prompt-engineering set ONLY. "
                        "trusted_context.farmer_id is the authenticated/requesting farmer used server-side "
                        "by validate_request and is NEVER sent to the model. current_plot_id is exposed to "
                        "the parser ONLY for the four genuinely implicit-context vague cases (vague0-3); it "
                        "is NOT provided to missing_plot or any other case. Reconstructed from dev gold for "
                        "this development set only; the >=300 benchmark MUST carry explicit context from the "
                        "start and MUST NOT derive context from gold labels."),
        "implicit_context_ids": sorted(IMPLICIT_CONTEXT_IDS),
        "entries": entries,
        "development_context_projection_id": li.case_set_hash(entries),
        "development_context_projection_sha256": hashlib.sha256(
            json.dumps(entries, sort_keys=True, default=str).encode()).hexdigest(),
    }
    return per, proj


def _crop_vocab():
    from farmsync.generate import CROPS

    vocab = []
    for crop in CROPS:
        if isinstance(crop, str):
            name = crop
        else:
            name = getattr(crop, "crop_name", None)

        if not isinstance(name, str) or not name.strip():
            raise RuntimeError(
                "CROPS contains an entry without a valid string crop_name: %r" % (crop,)
            )

        vocab.append(name)

    if not vocab:
        raise RuntimeError("canonical crop vocabulary is empty")

    return vocab

def _expected_deterministic(case, snapshot, trusted_context):
    """Derive the EXPECTED deterministic result (outcome/reason_codes/may_execute) from the frozen
    validate_request using the GOLD parse + the SAME dev trusted context."""
    client = li.MockLLMClient({case["source_text"]: case["gold_parse"]})
    pr, st, m = li.parse_request(case["source_text"], client, trusted_context=trusted_context)
    vr = li.validate_request(pr, snapshot, trusted_context=trusted_context)
    return {"validation_outcome": vr.outcome,
            "reason_codes": sorted(vr.reason_codes or []),
            "may_execute": vr.may_execute}


def validation_semantics_equivalence(ctx_cases, preds, snapshot, per_tc):
    """§1: compare the LIVE deterministic result to the GOLD-derived expected result on validation_outcome,
    reason_codes AND may_execute — so a WRONG rejection path (e.g. IDENTITY_MISMATCH instead of the intended
    OWNERSHIP_MISMATCH) is NOT hidden by both yielding payload=None. Returns aggregate rates (positive
    denominators) + per-case booleans."""
    per = {}
    n = 0
    o_ok = rc_ok = me_ok = 0
    for c, p in zip(ctx_cases, preds):
        exp = _expected_deterministic(c, snapshot, per_tc.get(c["id"]))
        got_outcome = p.get("validation_outcome")
        got_rc = sorted(p.get("reason_codes") or [])
        got_me = p.get("may_execute")
        oe = (got_outcome == exp["validation_outcome"])
        re = (got_rc == exp["reason_codes"])
        mee = (got_me == exp["may_execute"])
        per[c["id"]] = {"validation_outcome_equiv": oe, "reason_code_equiv": re, "may_execute_equiv": mee,
                        "expected_outcome": exp["validation_outcome"], "predicted_outcome": got_outcome,
                        "expected_reason_codes": exp["reason_codes"], "predicted_reason_codes": got_rc,
                        "expected_may_execute": exp["may_execute"], "predicted_may_execute": got_me}
        n += 1; o_ok += oe; rc_ok += re; me_ok += mee
    agg = {"denominator": n,
           "validation_outcome_equivalence_rate": (o_ok / n) if n else None,
           "reason_code_equivalence_rate": (rc_ok / n) if n else None,
           "may_execute_equivalence_rate": (me_ok / n) if n else None,
           "semantics_equivalence_pass": bool(n > 0 and o_ok == n and rc_ok == n and me_ok == n)}
    return agg, per


# model-responsible parse fields (v3): farmer_id is server-authoritative and EXCLUDED from the primary score
V3_MODEL_FIELDS = ["action", "plot_id", "requested_crop", "requested_value", "unit", "clarification_required"]


class _RecordingClient:
    """Evaluator-local wrapper around the mock/live client. It forwards each .parse() call UNCHANGED and,
    from the SAME call's return, records a sanitized subset of the raw structured response (here just
    `clarification_required`, which the frozen scorer's `parsed` projection omits). No extra parse/API call;
    no raw farmer text or key retained."""
    def __init__(self, inner):
        self._inner = inner
        self.live = getattr(inner, "live", False)
        self.recorded = {}          # source_text -> {"clarification_required": bool|None}

    def parse(self, text, trusted_context=None):
        out = self._inner.parse(text, trusted_context)          # the ONE and only call
        raw = out.get("raw") if isinstance(out, dict) else None
        self.recorded[text] = {"clarification_required": (raw or {}).get("clarification_required")
                               if isinstance(raw, dict) else None}
        return out                                              # forwarded unchanged


def _expected_clarification_flag(case, snapshot, trusted_context):
    """Expected clarification flag = (gold-derived deterministic outcome == CLARIFICATION_REQUIRED). Does
    NOT depend on the legacy gold parse carrying the flag."""
    exp = _expected_deterministic(case, snapshot, trusted_context)
    return exp["validation_outcome"] == li.CLARIFICATION_REQUIRED


def v3_parser_metrics(ctx_cases, preds, recorded=None, snapshot=None, per_tc=None):
    """§2: non-frozen PRIMARY v3 parser metrics over model-responsible fields only (excludes the
    server-authoritative farmer_id). `clarification_required` is scored from the RAW structured response
    captured by the recording client (the frozen scorer's `parsed` omits it), with the expected flag
    derived from the deterministic gold-derived outcome (== CLARIFICATION_REQUIRED)."""
    recorded = recorded or {}
    per_tc = per_tc or {}
    non_flag = [f for f in V3_MODEL_FIELDS if f != "clarification_required"]
    per_field = {f: {"correct": 0, "n": 0} for f in non_flag}
    clar = {"correct": 0, "n": 0}
    for c, p in zip(ctx_cases, preds):
        gold = c["gold_parse"]; parsed = p.get("parsed") or {}
        for f in non_flag:
            per_field[f]["n"] += 1
            if parsed.get(f) == gold.get(f):
                per_field[f]["correct"] += 1
        # clarification_required: predicted from the raw recorded flag; expected from deterministic outcome
        pred_flag = bool(recorded.get(c["source_text"], {}).get("clarification_required"))
        exp_flag = bool(_expected_clarification_flag(c, snapshot, per_tc.get(c["id"]))) if snapshot is not None else None
        if exp_flag is not None:
            clar["n"] += 1
            if pred_flag == exp_flag:
                clar["correct"] += 1
    out = {f: {"accuracy": (v["correct"] / v["n"]) if v["n"] else None, "denominator": v["n"]}
           for f, v in per_field.items()}
    out["clarification_required"] = {"accuracy": (clar["correct"] / clar["n"]) if clar["n"] else None,
                                     "denominator": clar["n"],
                                     "source": "raw structured response (recording client)"}
    out["_fields_scored"] = list(V3_MODEL_FIELDS)
    out["_excludes_server_authoritative_farmer_id"] = True
    out["trusted_identity_supplied_server_side"] = True
    out["trusted_identity_sent_to_model"] = False
    return out


def _case_hash(case):
    """Stable per-case hash (references the case without persisting raw source text)."""
    return hashlib.sha256(json.dumps(case, sort_keys=True, default=str).encode()).hexdigest()[:16]


def build_prediction_records(cases, preds, mode, model, projection_meta, ctx_proj=None, sem_per=None,
                             per_tc=None, recorded=None, snapshot=None):
    """AUDIT-GAP FIX: a sanitized, version-stamped per-case prediction artifact so the exact live parses are
    reconstructable after the fact (store=False means the API side keeps nothing). PRIVACY: NO raw source
    text is persisted (only case id + case hash), NO API key. Field-level predicted structured output IS
    recorded — those fields derive from the already-public synthetic development case set."""
    ctx_proj = ctx_proj or {}
    sem_per = sem_per or {}
    per_tc = per_tc or {}
    recorded = recorded or {}
    recs = []
    for c, p in zip(cases, preds):
        meta = p.get("llm_meta", {}) or {}
        tc = per_tc.get(c["id"], {}) or {}
        sem = sem_per.get(c["id"], {})
        pred_clar = recorded.get(c.get("source_text", ""), {}).get("clarification_required")
        exp_clar = (_expected_clarification_flag(c, snapshot, tc) if snapshot is not None else None)
        recs.append({
            "case_id": c["id"],
            "case_hash": _case_hash(c),
            "category": c.get("category"),
            "expected_action": c["gold_parse"].get("action"),
            "predicted_action": (p.get("parsed") or {}).get("action"),
            "action_match": ((p.get("parsed") or {}).get("action") == c["gold_parse"].get("action")),
            "expected_fields": {k: c["gold_parse"].get(k) for k in ("farmer_id", "plot_id", "requested_crop", "requested_value", "unit")},
            "predicted_fields": {k: (p.get("parsed") or {}).get(k) for k in ("farmer_id", "plot_id", "requested_crop", "requested_value", "unit")},
            # clarification flag: predicted from raw recorded response; expected from deterministic outcome
            "expected_clarification_required": (bool(exp_clar) if exp_clar is not None else None),
            "predicted_clarification_required": (bool(pred_clar) if pred_clar is not None else None),
            "validation_outcome": p.get("validation_outcome"),
            "reason_codes": p.get("reason_codes"),
            "may_execute": p.get("may_execute"),
            "expected_payload": c.get("gold_payload"),
            "deterministic_live_derived_payload": p.get("llm_payload"),
            "payload_equiv": p.get("payload_equiv"),
            "exec_applicable": p.get("exec_applicable"),
            "exec_equivalent": p.get("exec_equivalent"),
            "validation_outcome_equiv": sem.get("validation_outcome_equiv"),
            "reason_code_equiv": sem.get("reason_code_equiv"),
            "may_execute_equiv": sem.get("may_execute_equiv"),
            "expected_validation_outcome": sem.get("expected_outcome"),
            "expected_reason_codes": sem.get("expected_reason_codes"),
            "parse_status": p.get("parse_status"),
            "schema_valid": p.get("schema_valid"),
            "model": meta.get("model"), "prompt_version": meta.get("prompt_version"),
            "schema_version": meta.get("schema_version"), "mode": mode,
            "latency_ms": meta.get("latency_ms"),
            "retries": (meta.get("attempts", 1) - 1) if meta.get("attempts") else None,
            "response_id": meta.get("response_id"), "token_usage": meta.get("usage"),
            "reconciled_case": (c["id"] in RECONCILE_IDS),
            "evaluation_projection_id": projection_meta.get("evaluation_projection_id"),
            "evaluation_projection_sha256": projection_meta.get("evaluation_projection_sha256"),
            "development_context_projection_id": ctx_proj.get("development_context_projection_id"),
            "development_context_projection_sha256": ctx_proj.get("development_context_projection_sha256"),
            "trusted_identity_used_server_side": (tc.get("farmer_id") is not None),
            "current_plot_id_supplied_to_parser": tc.get("current_plot_id"),
            "raw_text_persisted": False, "api_key_persisted": False,
        })
    return recs


def _emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    mode = svc.resolve_mode(os.environ.get("FARMSYNC_LLM_MODE", "off"))
    model = os.environ.get("FARMSYNC_LLM_MODEL", "gpt-5.6-terra")
    header = {"evaluation": "LIVE DEVELOPMENT EVALUATION - NOT THE >=300 BENCHMARK",
              "mode": mode, "model_requested": model, "schema_version": li.SCHEMA_VERSION,
              "frozen_prompt_version": li.PROMPT_VERSION,
              "integration_prompt_version": svc.INTEGRATION_PROMPT_VERSION,
              "expected_case_file_sha256": EXPECTED_CASE_FILE_SHA256,
              "expected_semantic_case_set_hash": EXPECTED_CASE_SET_HASH,
              "legacy_manifest_case_set_hash": LEGACY_MANIFEST_CASE_SET_HASH,
              "case_set_hash_discrepancy_note": CASE_SET_HASH_DISCREPANCY_NOTE,
              "master_seed": MASTER_SEED}

    if mode == "off":
        _emit({**header, "status": "DISABLED", "reason": "FARMSYNC_LLM_MODE=off"})
        return 0                                         # 'off' is a benign no-op

    # §6: explicit non-zero exit for live failure states
    if mode == "live" and not os.environ.get("OPENAI_API_KEY"):
        _emit({**header, "status": "FAILED", "reason": "no OPENAI_API_KEY in env (live)"})
        return 3

    # cases + DUAL-GATE identity (byte SHA-256 AND semantic hash; abort on absence/mismatch), BEFORE any API call
    try:
        cases = load_jsonl_cases()
        identity = verify_case_identity(cases)
    except Exception as e:
        _emit({**header, "status": "FAILED", "reason": "cases: %s" % (str(e)[:200])})
        return 4 if mode == "live" else 0

    # deterministic fixture (gate before live)
    try:
        snapshot, base_state, fixture_meta = build_p7_fixture()
    except Exception as e:
        _emit({**header, "status": "FAILED", "reason": "fixture build failed: %s" % (str(e)[:200])})
        return 5 if mode == "live" else 0

    # LAYER 1 - raw/original-gold historical COMPATIBILITY (expect the KNOWN 39/41 profile) + LAYER 2 -
    # validator-derived current-semantics projection (require 41/41). Both gate mock AND live.
    raw_repro = verify_fixture_reproduces_mock(cases, snapshot, base_state)
    if not raw_repro["raw_historical_compatibility_pass"]:
        _emit({**header, "status": "FAILED", "reason": "raw historical compatibility profile changed "
               "(expected the known 39/41 / exec 12/12 / N/A 29 profile)",
               "raw_historical_reproduction": raw_repro})
        return 6
    try:
        recon_cases, recon_meta = build_reconciled_projection(cases, snapshot)   # HARD-FAILS outside {wd0,wd1}
    except Exception as e:
        _emit({**header, "status": "FAILED", "reason": "reconciliation scope/semantic violation: %s" % (str(e)[:250]),
               "raw_historical_reproduction": raw_repro})
        return 6

    # DEVELOPMENT CONTEXT PROJECTION (v3): attach per-case trusted_context (authenticated farmer_id
    # server-side; current_plot_id parser-visible for vague only). In-memory; the on-disk cases are never
    # modified. Applied to the reconciled cases used for live-development scoring.
    per_tc, ctx_proj = build_development_context_projection(recon_cases, allowed_crops=_crop_vocab())
    ctx_cases = []
    for c in recon_cases:
        cc = dict(c); cc["trusted_context"] = per_tc.get(c["id"]); ctx_cases.append(cc)

    current_proj = current_semantics_projection_check(recon_cases, snapshot, base_state)
    if not current_proj["current_semantics_projection_pass"]:      # gates mock AND live (change 1)
        _emit({**header, "status": "FAILED", "reason": "current-semantics projection did not pass",
               "raw_historical_reproduction": raw_repro, "current_semantics_projection": current_proj,
               "reconciliation": recon_meta})
        return 7

    # build client (live raises without a key -> non-zero; never silent mock). MOCK uses the canonical gold
    # mapping of the RECONCILED projection (fixes the empty-mapping bug that returned 41 refusals).
    try:
        if mode == "mock":
            client = svc.make_client("mock", mock_responses={c["source_text"]: c["gold_parse"] for c in ctx_cases})
        else:
            client = svc.make_client(mode)
    except Exception as e:
        _emit({**header, "status": "FAILED", "reason": "client init failed: %s" % type(e).__name__})
        return 8

    # LIVE-DEVELOPMENT scoring uses the RECONCILED + context-projected cases. Wrap the client in an
    # evaluator-local recording client so the SAME parse() calls also capture the raw clarification_required
    # flag (the frozen scorer's `parsed` projection omits it) -- no extra parse/API call.
    rec_client = _RecordingClient(client)
    t0 = time.time()
    preds, metrics = le.run_dev_benchmark(ctx_cases, rec_client, snapshot, base_state=base_state)
    dur = round(time.time() - t0, 3)
    metrics = _relabel_live(metrics, model, mode)
    gate = _boundary_gate(metrics)
    reliab = _reliability_from_preds(preds)

    # §1 deterministic VALIDATION-SEMANTICS equivalence (outcome + reason_codes + may_execute vs gold-derived)
    sem_agg, sem_per = validation_semantics_equivalence(ctx_cases, preds, snapshot, per_tc)
    # §2 non-frozen PRIMARY v3 parser metrics; clarification_required from RAW recorded flag, expected
    # from the deterministic gold-derived outcome.
    v3_metrics = v3_parser_metrics(ctx_cases, preds, recorded=rec_client.recorded, snapshot=snapshot, per_tc=per_tc)
    # development boundary-integrity gate ALSO requires semantics equivalence == 1.0 (positive denominators)
    dev_boundary_integrity_pass = bool(gate["boundary_integrity_pass"] and sem_agg["semantics_equivalence_pass"])

    disc = {"case_file_sha256": identity["case_file_sha256"],
            "semantic_case_set_hash": identity["semantic_case_set_hash"],
            "legacy_manifest_case_set_hash": LEGACY_MANIFEST_CASE_SET_HASH,
            "case_set_hash_discrepancy": True,
            "evaluation_projection_id": recon_meta["evaluation_projection_id"],
            "evaluation_projection_sha256": recon_meta["evaluation_projection_sha256"],
            "reconciled_ids": recon_meta["reconciliation_ids"],
            "development_context_projection_id": ctx_proj["development_context_projection_id"],
            "development_context_projection_sha256": ctx_proj["development_context_projection_sha256"]}

    provenance = []
    latencies = []
    for c, rec in zip(ctx_cases, preds):
        meta = dict(rec.get("llm_meta", {}) or {}); meta["mode"] = mode
        if meta.get("latency_ms") is not None:
            latencies.append(meta["latency_ms"])
        prov = svc.provenance_record(
            c.get("source_text", ""), rec.get("parse_status"), meta,
            validation_outcome=rec.get("validation_outcome"), case_category=c.get("category"))
        prov.update(disc)
        prov["reconciled_case"] = (c["id"] in RECONCILE_IDS)
        tc = per_tc.get(c["id"], {}) or {}
        prov["trusted_identity_used_server_side"] = (tc.get("farmer_id") is not None)
        prov["current_plot_id_supplied_to_parser"] = tc.get("current_plot_id")
        provenance.append(prov)

    report = {**header, "status": "COMPLETE", "live": mode == "live",
              "case_set_identity": identity,
              "raw_historical_reproduction": raw_repro,
              "current_semantics_projection": current_proj,
              "reconciliation": recon_meta,
              "development_context_projection": ctx_proj,
              "n_cases": len(recon_cases), "duration_s": dur, "fixture": fixture_meta,
              "boundary_gate": gate, "reliability": reliab,
              "latency_ms_summary": ({"n": len(latencies), "min": min(latencies), "max": max(latencies),
                                      "mean": round(sum(latencies)/len(latencies), 1)} if latencies else None),
              "metrics_legacy_frozen_scorer": metrics,
              "metrics_legacy_note": ("frozen llm_eval scorer metrics; farmer-containing field metrics are "
                                      "LEGACY/REFERENCE — v3 sets farmer_id=null when requester identity is "
                                      "not explicit and uses authenticated identity server-side."),
              "v3_primary_parser_metrics": v3_metrics,
              "validation_semantics_equivalence": sem_agg,
              "validation_semantics_note": ("The deterministic boundary reaches the intended reason codes "
                                            "under the SIMULATED v3 parse contract and development context "
                                            "projection; this offline check proves the contract simulation, "
                                            "not Terra prompt adherence (that is measured by the live run)."),
              "development_boundary_integrity_pass": dev_boundary_integrity_pass,
              "api_key_persisted": False, "raw_text_persisted": False}
    _tag = "%s_%s" % (mode, svc.INTEGRATION_PROMPT_VERSION.replace("/", "-"))
    with open(os.path.join(OUT_DIR, "live_dev_eval_%s.json" % _tag), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str); f.write("\n")
    svc.write_provenance(provenance, "live_dev_provenance_%s.json" % _tag)
    # AUDIT-GAP FIX: sanitized per-case prediction artifact (version-stamped; no raw text, no key)
    pred_records = build_prediction_records(ctx_cases, preds, mode, model, recon_meta,
                                            ctx_proj=ctx_proj, sem_per=sem_per, per_tc=per_tc,
                                            recorded=rec_client.recorded, snapshot=snapshot)
    with open(os.path.join(OUT_DIR, "live_dev_predictions_%s.json" % _tag), "w", encoding="utf-8") as f:
        json.dump(pred_records, f, indent=2, ensure_ascii=False, default=str); f.write("\n")

    _emit({k: report[k] for k in ("evaluation", "status", "mode", "model_requested", "case_set_identity",
                                  "raw_historical_reproduction", "current_semantics_projection",
                                  "n_cases", "boundary_gate", "validation_semantics_equivalence",
                                  "v3_primary_parser_metrics", "development_boundary_integrity_pass",
                                  "reliability", "latency_ms_summary")})
    # §1/§4: non-zero unless BOTH boundary integrity AND validation-semantics equivalence pass
    return 0 if dev_boundary_integrity_pass else 2


if __name__ == "__main__":
    sys.exit(main())
