"""Offline integrity + policy proofs for the publication >=300-case parser benchmark (no live call)."""
import hashlib
import json
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import farmsync_llm_benchmark_build as BB
from farmsync.proposed import llm_interaction as li

_DIR = os.path.join(_ROOT, "results", "farmsync", "qa", "llm_benchmark")
_CASE_FILE = os.path.join(_DIR, "benchmark_cases_v1.jsonl")
_MAN = os.path.join(_DIR, "benchmark_manifest_v1.json")


def _load():
    with open(_CASE_FILE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _man():
    return json.load(open(_MAN))


_FROZEN_SHA_AT_IMPORT = {
    f: hashlib.sha256(open(os.path.join(_DIR, f), "rb").read()).hexdigest()
    for f in ("benchmark_cases_v1.jsonl", "benchmark_gold_semantics_v1.jsonl", "benchmark_manifest_v1.json")
}


def test_live_integrity_gate_passes_in_offline_preflight():
    import farmsync_llm_benchmark_eval as EVAL
    integ = EVAL.verify_case_integrity(_load())
    assert integ["all_pass"] is True, [k for k, v in integ["checks"].items() if not v]
    old = os.environ.pop("FARMSYNC_LLM_BASE_URL", None)
    try:
        assert EVAL._official_endpoint_ok() is True
        os.environ["FARMSYNC_LLM_BASE_URL"] = "https://stale.example.com/v1"
        assert EVAL._official_endpoint_ok() is False
    finally:
        os.environ.pop("FARMSYNC_LLM_BASE_URL", None)
        if old is not None:
            os.environ["FARMSYNC_LLM_BASE_URL"] = old


def test_case_count_at_least_300():
    assert len(_load()) >= 300


def test_linguistic_diversity_audit():
    man = _man()
    cases = _load()
    audit = BB.template_audit(cases)
    assert man["normalized_template_count"] == audit["normalized_template_count"]
    assert man["max_template_reuse"] == audit["max_template_reuse"]
    # publication-grade diversity: >=150 templates for >=300 cases, no template dominating (<=4 reuse)
    assert audit["normalized_template_count"] >= 150, audit["normalized_template_count"]
    assert audit["max_template_reuse"] <= 4, audit["top_templates"]


def test_data_nature_labelled_synthetic_constructed():
    assert _man()["benchmark_data_nature"] == "SYNTHETIC_CONSTRUCTED"


def test_no_synthetic_uniqueness_markers_in_source_text():
    for c in _load():
        assert "#" not in c["source_text"] and not re.search(r"#\d", c["source_text"])


def test_authenticated_farmer_id_never_sent_to_model():
    from farmsync.proposed import llm_service as svc
    cli = svc.ResponsesLLMClient.__new__(svc.ResponsesLLMClient)
    for c in _load():
        ctx = svc.ResponsesLLMClient._minimal_context(cli, c["trusted_context"])
        assert "farmer_id" not in ctx, "farmer_id leaked: %s" % ctx
        assert set(ctx.keys()).issubset({"allowed_actions", "allowed_crops", "current_plot_id"})
        assert c["trusted_context"].get("farmer_id"), c["case_id"]


def test_allowed_crops_is_canonical_and_present_in_context():
    canon = BB.crop_vocab()
    for c in _load():
        assert c["trusted_context"].get("allowed_crops") == canon, c["case_id"]


def test_current_plot_id_policy():
    for c in _load():
        has = "current_plot_id" in c["trusted_context"]
        if c["category"] in ("accept_implicit_plot", "vague_modify_implicit_plot", "explicit_vs_current_plot"):
            assert has, c["case_id"]
        if c["category"] == "nonexistent_plot":
            assert not has, c["case_id"]


def test_gold_fields_traceable_and_requested_value_literal():
    for c in _load():
        prov = c["field_provenance"]; gp = c["gold_parse"]; st = c["source_text"]
        for f in ("action", "plot_id", "requested_crop", "requested_value", "unit"):
            v = gp.get(f)
            if v is None:
                continue
            assert prov.get(f) in ("text", "ctx"), "%s.%s" % (c["case_id"], f)
            if prov[f] == "ctx":
                assert f == "plot_id" and c["trusted_context"].get("current_plot_id") == v
            if prov[f] == "text":
                if f in ("requested_crop", "plot_id", "unit") and isinstance(v, str):
                    assert v.lower() in st.lower(), "%s.%s=%r" % (c["case_id"], f, v)
                if f == "requested_value":
                    num = ("%g" % v) if isinstance(v, float) else str(v)
                    assert re.search(r"(?<!\w)%s(?!\d)" % re.escape(num), st), "%s value %r not literal" % (c["case_id"], v)


def test_numeric_identifier_trap_plots_exist_and_no_requested_value():
    import farmsync_llm_live_eval as EV
    snap, base, _ = EV.build_p7_fixture()
    traps = [c for c in _load() if c["category"] == "numeric_identifier_trap"]
    assert traps
    for c in traps:
        assert c["gold_parse"]["plot_id"] in snap.plots_by_id, "%s plot missing" % c["case_id"]
        assert c["gold_parse"]["requested_value"] is None
        # deterministic outcome must NOT be PLOT_NOT_FOUND
        assert c["expected_validation_outcome"] != "VALIDATION_REJECTED" or "PLOT_NOT_FOUND" not in c["expected_reason_codes"]


def test_explicit_vs_current_plot_same_farmer():
    import farmsync_llm_live_eval as EV
    snap, base, _ = EV.build_p7_fixture()
    evs = [c for c in _load() if c["category"] == "explicit_vs_current_plot"]
    assert evs
    for c in evs:
        fid = c["trusted_context"]["farmer_id"]
        explicit = c["gold_parse"]["plot_id"]; current = c["trusted_context"]["current_plot_id"]
        assert explicit != current
        assert snap.plot_owner.get(explicit) == fid, "%s explicit plot not owned by requester" % c["case_id"]
        assert snap.plot_owner.get(current) == fid, "%s current plot not owned by requester" % c["case_id"]


def test_no_response_excluded():
    assert "NO_RESPONSE" not in li.SUPPORTED_ACTIONS
    for c in _load():
        assert c["gold_parse"]["action"] in li.SUPPORTED_ACTIONS


def test_expected_semantics_match_frozen_validator():
    import farmsync_llm_live_eval as EV
    snap, base, _ = EV.build_p7_fixture()
    mism = 0
    for c in _load():
        cl = li.MockLLMClient({c["source_text"]: c["gold_parse"]})
        pr, st, m = li.parse_request(c["source_text"], cl, trusted_context=c["trusted_context"])
        vr = li.validate_request(pr, snap, trusted_context=c["trusted_context"])
        if vr.outcome != c["expected_validation_outcome"] or sorted(vr.reason_codes or []) != c["expected_reason_codes"]:
            mism += 1
    assert mism == 0, mism


def test_manifest_reproducible_from_builder(tmp_path):
    # PROOF (READ-ONLY): re-run the deterministic build+freeze into a TEMP dir and compare core identities
    # to the frozen manifest. Never writes to the authoritative benchmark dir.
    man0 = _man()
    man1, _audit = BB.build_and_freeze(out_dir=str(tmp_path))
    for k in ("case_file_sha256", "gold_semantics_sha256", "semantic_case_set_hash", "case_count",
              "normalized_template_count", "max_template_reuse", "builder_sha256", "evaluator_sha256",
              "service_sha256", "frozen_contract_sha256", "fixture_instance_hash", "model",
              "prompt_version", "schema_version", "context_policy_version", "benchmark_data_nature",
              "category_distribution", "difficulty_distribution"):
        assert man1[k] == man0[k], "manifest field %s not reproducible" % k
    for k in ("builder_sha256", "evaluator_sha256", "service_sha256", "frozen_contract_sha256",
              "freeze_timestamp", "normalized_template_count"):
        assert k in man1


def test_running_tests_leaves_frozen_benchmark_byte_identical():
    # PROOF: the benchmark test module must not mutate the authoritative files. This test records SHAs so a
    # session-level before/after comparison (below) can assert byte-identity.
    import hashlib as _h
    files = ["benchmark_cases_v1.jsonl", "benchmark_gold_semantics_v1.jsonl", "benchmark_manifest_v1.json"]
    shas = {f: _h.sha256(open(os.path.join(_DIR, f), "rb").read()).hexdigest() for f in files}
    # compare against the SHAs captured at module import (before any test ran)
    for f in files:
        assert shas[f] == _FROZEN_SHA_AT_IMPORT[f], "%s was mutated by the test run" % f


def test_execution_equivalence_semantics():
    # PROOF: (a) identical executable payloads -> applicable True, equivalent True; (b) different -> True/False;
    # (c) QUERY/(d) WITHDRAW/(e) missing payload -> applicable False, equivalent None.
    import farmsync_llm_live_eval as EV
    snap, base, _ = EV.build_p7_fixture()
    def payload_for(action, pid, fid, crop=None):
        gp = {"action": action, "farmer_id": None, "plot_id": pid, "requested_crop": crop,
              "requested_value": None, "unit": None, "reason": None, "clarification_required": False,
              "clarification_question": None, "confidence": 1.0}
        cl = li.MockLLMClient({"x": gp})
        pr, st, m = li.parse_request("x", cl, trusted_context={"farmer_id": fid})
        vr = li.validate_request(pr, snap, trusted_context={"farmer_id": fid})
        return vr.deterministic_action_payload
    acc = payload_for("ACCEPT", "F0001-P03", "F0001")
    acc2 = payload_for("ACCEPT", "F0004-P02", "F0004")
    qry = payload_for("QUERY", "F0001-P03", "F0001")
    wd = payload_for("WITHDRAW", "F0001-P03", "F0001")
    # (a) identical
    ap, eq, d = li.outcome_execution_equivalent(acc, acc, base)
    assert ap is True and eq is True
    # (b) different executable payloads
    ap, eq, d = li.outcome_execution_equivalent(acc, acc2, base)
    assert ap is True and eq is False
    # (c) QUERY -> N/A ; (d) WITHDRAW -> N/A ; (e) missing payload -> N/A
    for pl in (qry, wd, None):
        ap, eq, d = li.outcome_execution_equivalent(pl, acc, base)
        assert ap is False and eq is None


def test_execution_denominator_derived_not_hardcoded():
    # run the evaluator's run() in mock and derive the execution-applicable denominator from the data.
    import farmsync_llm_benchmark_eval as EVAL
    import farmsync_llm_live_eval as EV
    from farmsync.proposed import llm_service as svc
    snap, base, _ = EV.build_p7_fixture()
    cases = _load()
    recs = EVAL.run(cases, None, snap, base, mode="mock")
    den = sum(1 for r in recs if r["exec_applicable"])
    # QUERY/WITHDRAW/CLARIFICATION/rejected cases must NOT be applicable
    for r in recs:
        if r["validation_outcome"] in ("CLARIFICATION_REQUIRED",) or (r["parsed"] or {}).get("action") in ("QUERY", "WITHDRAW"):
            assert r["exec_applicable"] is False, "%s should be exec N/A" % r["case_id"]
    dm = EVAL.deterministic_metrics(recs)
    assert dm["execution_equivalence_denominator"] == den
    assert dm["execution_equivalent_count"] == den   # mock returns gold -> all applicable are equivalent
    assert dm["execution_equivalence_rate"] == 1.0
    assert den > 0


def test_parser_scoring_fail_closed():
    # PROOF: a non-OK parse earns no field credit and no payload-equivalence credit.
    import farmsync_llm_benchmark_eval as EVAL
    # craft records: one OK-correct, one SCHEMA_INVALID whose (empty) fields "happen" to match None expected
    rec_ok = {"parse_status": "OK", "parsed": {"action": "ACCEPT", "plot_id": "F0001-P03", "requested_crop": None,
              "requested_value": None, "unit": None}, "expected": {"action": "ACCEPT", "plot_id": "F0001-P03",
              "requested_crop": None, "requested_value": None, "unit": None},
              "predicted_clarification_required": False, "expected_clarification_required": False}
    rec_fail = {"parse_status": li.SCHEMA_INVALID, "parsed": {}, "expected": {"action": "ACCEPT", "plot_id": "F0001-P03",
                "requested_crop": None, "requested_value": None, "unit": None},
                "predicted_clarification_required": None, "expected_clarification_required": False}
    pm = EVAL.parser_metrics([rec_ok, rec_fail])
    # action accuracy: only the OK case counts -> 1/2
    assert pm["action"]["accuracy"] == 0.5
    # requested_crop: OK case matches None(=None); fail case must NOT get credit -> 1/2 (not 2/2)
    assert pm["requested_crop"]["accuracy"] == 0.5
    assert pm["clarification_required"]["accuracy"] == 0.5


def test_wrong_runtime_model_and_fixture_hash_fail_gate():
    import farmsync_llm_benchmark_eval as EVAL
    man = _man()
    # runtime model gate
    assert EVAL.runtime_model_gate("gpt-5.6-terra", man["model"]) is True
    assert EVAL.runtime_model_gate("gpt-5.6-luna", man["model"]) is False       # wrong runtime model
    assert EVAL.runtime_model_gate("gpt-5.6-terra", "gpt-5.6-sol") is False      # manifest disagreement
    # fixture instance-hash gate
    assert EVAL.fixture_hash_gate("5ea24037c2d9cb6a", man["fixture_instance_hash"]) is True
    assert EVAL.fixture_hash_gate("deadbeefdeadbeef", man["fixture_instance_hash"]) is False   # wrong fixture
    assert EVAL.fixture_hash_gate("5ea24037c2d9cb6a", "0000000000000000") is False             # manifest disagreement


def test_pools_no_tmp_override():
    # PROOF: /tmp/pools.json can no longer influence the builder.
    src = open(os.path.join(_ROOT, "scripts", "farmsync_llm_benchmark_build.py")).read()
    assert "/tmp/pools.json" not in src
    assert "AUTHORING_POOLS" not in src
    # _load_pools returns the embedded pools regardless of any temp file
    assert BB._load_pools() is BB._EMBEDDED_POOLS


def test_accept_vs_approve_clean_and_probe_reclassified():
    import farmsync_llm_live_eval as EV
    snap, base, _ = EV.build_p7_fixture()
    cases = _load()
    # clean accept_vs_approve cases: expected outcome is a genuine ACCEPT validation (not rejection)
    clean = [c for c in cases if c["category"] == "accept_vs_approve"]
    assert clean
    for c in clean:
        assert "UNSUPPORTED_AUTHORITY_INSTRUCTION" not in c["expected_reason_codes"], c["case_id"]
        assert not li.detect_authority_attempts(c["source_text"]), c["case_id"]
    # the authority-approve wording is reclassified as a probe with expected REJECTION
    probe = [c for c in cases if c["category"] == "authority_false_positive_probe"]
    assert probe
    for c in probe:
        assert c["expected_validation_outcome"] == "VALIDATION_REJECTED"
        assert "UNSUPPORTED_AUTHORITY_INSTRUCTION" in c["expected_reason_codes"]


def test_broad_category_coverage():
    cats = {c["category"] for c in _load()}
    required = {"accept_explicit_plot", "accept_implicit_plot", "reject_explicit", "withdraw_explicit",
                "modify_explicit_crop", "vague_modify", "vague_modify_implicit_plot", "wrong_ownership",
                "invalid_farmer", "nonexistent_plot", "hard_locked_modify", "infeasible_crop",
                "unknown_crop", "modify_numeric_unit", "numeric_identifier_trap", "authority_override",
                "prompt_injection_like", "negation", "polite_indirect", "casing_variation", "terse",
                "long_conversational", "query_explain", "explicit_vs_current_plot", "accept_vs_approve",
                "authority_false_positive_probe"}
    assert not (required - cats), sorted(required - cats)


def test_boundary_integrity_requires_payload_equivalence():
    # PROOF: a payload mismatch cannot yield boundary_integrity_pass=True, even if outcome/reason/
    # may_execute all match and execution is N/A.
    import farmsync_llm_benchmark_eval as EVAL
    base = {"validation_outcome": "X", "expected_validation_outcome": "X",
            "reason_codes": ["R"], "expected_reason_codes": ["R"],
            "may_execute": False, "expected_may_execute": False,
            "exec_applicable": False, "exec_equivalent": None}
    good = dict(base, payload_equiv=True)
    bad = dict(base, payload_equiv=False)   # only payload differs
    dm_good = EVAL.deterministic_metrics([good, dict(good)])
    dm_bad = EVAL.deterministic_metrics([good, bad])
    assert dm_good["boundary_integrity_pass"] is True
    assert dm_bad["boundary_integrity_pass"] is False       # payload mismatch blocks the pass
    assert dm_bad["execution_equivalence_denominator"] == 0  # exec N/A here


def test_ordinary_accept_categories_have_no_authority_false_positive():
    # PROOF: normal ACCEPT categories must not contain authority-triggering wording.
    for c in _load():
        if c["category"] in {"accept_explicit_plot", "accept_implicit_plot", "accept_vs_approve"}:
            assert "UNSUPPORTED_AUTHORITY_INSTRUCTION" not in c["expected_reason_codes"], c["case_id"]
            assert not li.detect_authority_attempts(c["source_text"]), (c["case_id"], c["source_text"])
    # the dedicated probe remains intact (still triggers, still expected-rejected)
    probe = [c for c in _load() if c["category"] == "authority_false_positive_probe"]
    assert probe
    for c in probe:
        assert "UNSUPPORTED_AUTHORITY_INSTRUCTION" in c["expected_reason_codes"]
        assert li.detect_authority_attempts(c["source_text"])
