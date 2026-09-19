#!/usr/bin/env python3
"""FarmSync — publication ≥300-case LLM parser benchmark EVALUATOR.

Runs the frozen case set through the parse -> deterministic validate boundary and reports THREE separate
metric groups: parser metrics, deterministic boundary metrics, and transport reliability. Reuses the
frozen contract (llm_interaction) and the frozen scorer formulas where applicable; the model-responsible
`clarification_required` flag is captured from the raw structured response via the evaluator-local
_RecordingClient (single parse/API call). The authenticated farmer_id stays server-side (never sent to the
model); current_plot_id is exposed to the parser only where the benchmark case's trusted_context supplies
one.

Modes (explicit; no silent fallback): FARMSYNC_LLM_MODE = off | mock | live. This turn runs mock only.
Once a live benchmark starts, NO prompt tuning may be based on its results.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from farmsync.proposed import llm_interaction as li
from farmsync.proposed import llm_service as svc
import farmsync_llm_live_eval as EV          # reuse _RecordingClient, _crop_vocab, fixture builder
import farmsync_llm_benchmark_build as BB

OUT_DIR = os.path.join(_ROOT, "results", "farmsync", "qa", "llm_benchmark")
CASE_FILE = os.path.join(OUT_DIR, "benchmark_cases_v1.jsonl")
MANIFEST = os.path.join(OUT_DIR, "benchmark_manifest_v1.json")

V3_MODEL_FIELDS = ["action", "plot_id", "requested_crop", "requested_value", "unit", "clarification_required"]


def load_cases():
    with open(CASE_FILE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _sha_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def verify_case_integrity(cases):
    """Re-derive/re-hash all frozen identities and check them against the manifest. Returns a dict; the
    live gate (below) requires ALL of these plus runtime version/endpoint checks."""
    man = json.load(open(MANIFEST))
    def sha_file(rel):
        return hashlib.sha256(open(os.path.join(_ROOT, rel), "rb").read()).hexdigest()
    got_case = _sha_file(CASE_FILE)
    got_sem = BB.semantic_case_set_hash(cases)
    got_gold = hashlib.sha256(open(os.path.join(_ROOT, man["gold_semantics_file"]), "rb").read()).hexdigest()
    checks = {
        "case_file_sha256": got_case == man["case_file_sha256"],
        "gold_semantics_sha256": got_gold == man["gold_semantics_sha256"],
        "semantic_case_set_hash": got_sem == man["semantic_case_set_hash"],
        "case_count": len(cases) == man["case_count"],
        "builder_sha256": sha_file("scripts/farmsync_llm_benchmark_build.py") == man["builder_sha256"],
        "evaluator_sha256": sha_file("scripts/farmsync_llm_benchmark_eval.py") == man["evaluator_sha256"],
        "service_sha256": sha_file("farmsync/proposed/llm_service.py") == man["service_sha256"],
        "frozen_contract_sha256": sha_file("farmsync/proposed/llm_interaction.py") == man["frozen_contract_sha256"],
        "model_is_terra": man["model"] == "gpt-5.6-terra",
        "runtime_prompt_version": svc.INTEGRATION_PROMPT_VERSION == man["prompt_version"] == "p7-parse-live-v3",
        "runtime_schema_version": li.SCHEMA_VERSION == man["schema_version"] == "farmsync-farmer-request-v1",
        "context_policy_version": man["context_policy_version"] == BB.CONTEXT_POLICY_VERSION,
    }
    return {"all_pass": all(checks.values()), "checks": checks,
            "case_file_sha256": got_case, "semantic_case_set_hash": got_sem, "case_count": len(cases),
            "benchmark_version": man["benchmark_version"], "benchmark_data_nature": man["benchmark_data_nature"],
            "prompt_version": man["prompt_version"], "schema_version": man["schema_version"],
            "manifest_model": man["model"], "manifest_fixture_instance_hash": man.get("fixture_instance_hash")}


def _official_endpoint_ok():
    """Require the official/default OpenAI endpoint for the benchmark — no stale custom base_url."""
    base = os.environ.get("FARMSYNC_LLM_BASE_URL")
    return base in (None, "", "https://api.openai.com/v1", "https://api.openai.com")


def runtime_model_gate(requested_model, manifest_model):
    """Hard equality: runtime requested model == manifest model == gpt-5.6-terra."""
    return requested_model == manifest_model == "gpt-5.6-terra"


def fixture_hash_gate(fx_instance_hash, manifest_instance_hash):
    """Hard equality: reconstructed fixture instance_hash == manifest == 5ea24037c2d9cb6a."""
    return fx_instance_hash == manifest_instance_hash == "5ea24037c2d9cb6a"


def run(cases, client, snapshot, base_state, mode="mock"):
    """Parse each case, run the frozen validator with the case's trusted context, and collect per-case
    results. In MOCK mode each case uses a fresh single-entry MockLLMClient keyed by its own source_text
    (several cases legitimately share identical text differing only by trusted_context, so a shared dict
    would collide); LIVE mode uses the one shared client (the model sees text + context per call). Both are
    wrapped per call in _RecordingClient so the raw clarification_required flag is captured in the SAME
    parse (no extra call)."""
    records = []
    for c in cases:
        tc = c["trusted_context"]
        if mode == "mock":
            inner = li.MockLLMClient({c["source_text"]: c["gold_parse"]})
        else:
            inner = client
        rec_client = EV._RecordingClient(inner)
        t0 = time.time()
        pr, status, meta = li.parse_request(c["source_text"], rec_client, trusted_context=tc)
        latency_ms = int((time.time() - t0) * 1000)
        parsed = {f: getattr(pr, f, None) for f in ("action", "farmer_id", "plot_id", "requested_crop",
                  "requested_value", "unit")} if pr is not None else {}
        if pr is not None:
            vr = li.validate_request(pr, snapshot, trusted_context=tc)
            outcome, reason_codes, may_exec = vr.outcome, sorted(vr.reason_codes or []), vr.may_execute
            payload = vr.deterministic_action_payload
        else:
            outcome, reason_codes, may_exec, payload = None, [], None, None
        # execution equivalence (frozen): unpack (applicable, equivalent, detail). Applicability is decided
        # by the frozen function (missing payload / unimplemented-execution action => NOT applicable), NOT by
        # "payload is not None".
        exp_payload = c["expected_payload"]
        try:
            applicable, equivalent, detail = li.outcome_execution_equivalent(payload, exp_payload, base_state)
            exec_applicable = bool(applicable)
            exec_equivalent = (bool(equivalent) if applicable else None)
            exec_detail = detail
        except Exception as e:
            exec_applicable, exec_equivalent, exec_detail = False, None, {"reason": "exception: %s" % type(e).__name__}
        # fail-closed payload equivalence: a non-OK parse cannot earn payload credit for None/None.
        payload_equiv = bool(status == "OK" and li.payload_equivalent(payload, exp_payload))
        meta = dict(meta or {})
        records.append({
            "case_id": c["case_id"], "category": c["category"], "difficulty": c["difficulty"],
            "parse_status": status, "schema_valid": status == "OK",
            "parsed": parsed,
            "predicted_clarification_required": rec_client.recorded.get(c["source_text"], {}).get("clarification_required"),
            "validation_outcome": outcome, "reason_codes": reason_codes, "may_execute": may_exec, "payload": payload,
            "expected": {k: c["gold_parse"].get(k) for k in ("action", "plot_id", "requested_crop", "requested_value", "unit")},
            "expected_clarification_required": bool(c["gold_parse"].get("clarification_required")),
            "expected_validation_outcome": c["expected_validation_outcome"],
            "expected_reason_codes": c["expected_reason_codes"],
            "expected_may_execute": c["expected_may_execute"],
            "expected_payload": exp_payload,
            "payload_equiv": payload_equiv,
            "exec_applicable": exec_applicable, "exec_equivalent": exec_equivalent, "exec_detail": exec_detail,
            "latency_ms": meta.get("latency_ms", latency_ms),
            "retries": (meta.get("attempts", 1) - 1) if meta.get("attempts") else 0,
            "response_id": meta.get("response_id"), "token_usage": meta.get("usage"),
            "model": meta.get("model"), "prompt_version": meta.get("prompt_version"),
            "schema_version": li.SCHEMA_VERSION,
        })
    return records


def parser_metrics(records):
    """Group 1 — parser metrics over model-responsible fields only (farmer_id is server-authoritative and
    excluded). FAIL-CLOSED: a non-OK parse (API_ERROR/MODEL_REFUSAL/SCHEMA_INVALID) earns NO field credit,
    so a failed parse cannot score a 'correct' None/False. clarification_required uses the raw recorded
    flag vs the expected flag, also only credited when the parse is OK."""
    field_ok = {f: 0 for f in ("action", "plot_id", "requested_crop", "requested_value", "unit")}
    n = 0
    clar_ok = 0
    for r in records:
        n += 1
        ok = (r["parse_status"] == "OK")
        for f in field_ok:
            if ok and (r["parsed"] or {}).get(f) == r["expected"].get(f):
                field_ok[f] += 1
        if ok and bool(r["predicted_clarification_required"]) == bool(r["expected_clarification_required"]):
            clar_ok += 1
    out = {f: {"accuracy": field_ok[f] / n if n else None, "denominator": n} for f in field_ok}
    out["clarification_required"] = {"accuracy": clar_ok / n if n else None, "denominator": n,
                                     "source": "raw structured response (recording client)"}
    out["_fields_scored"] = list(V3_MODEL_FIELDS)
    out["_scoring"] = "fail-closed: non-OK parse earns no field credit"
    out["_excludes_server_authoritative_farmer_id"] = True
    out["trusted_identity_supplied_server_side"] = True
    out["trusted_identity_sent_to_model"] = False
    return out


def deterministic_metrics(records):
    """Group 2 — deterministic boundary metrics vs the frozen-validator-derived expectations. Includes
    execution equivalence (frozen outcome_execution_equivalent) — non-applicable cases are N/A and are
    NOT counted as successes."""
    n = len(records)
    o = sum(1 for r in records if r["validation_outcome"] == r["expected_validation_outcome"])
    rc = sum(1 for r in records if r["reason_codes"] == r["expected_reason_codes"])
    me = sum(1 for r in records if r["may_execute"] == r["expected_may_execute"])
    pe = sum(1 for r in records if r["payload_equiv"])
    exec_applic = [r for r in records if r["exec_applicable"]]
    exec_den = len(exec_applic)
    exec_eq = sum(1 for r in exec_applic if r["exec_equivalent"] is True)
    return {
        "denominator": n,
        "validation_outcome_equivalence_rate": o / n if n else None,
        "reason_code_equivalence_rate": rc / n if n else None,
        "may_execute_equivalence_rate": me / n if n else None,
        "validated_payload_equivalence_rate": pe / n if n else None,
        "execution_equivalence_denominator": exec_den,
        "execution_equivalent_count": exec_eq,
        "execution_equivalence_rate": (exec_eq / exec_den) if exec_den else None,
        "execution_non_applicable_count": n - exec_den,
        "boundary_integrity_pass": bool(n > 0 and o == n and rc == n and me == n and pe == n
                                        and (exec_den == 0 or exec_eq == exec_den)),
    }


def reliability_metrics(records):
    """Group 3 — transport/schema reliability."""
    n = len(records)
    def cnt(s): return sum(1 for r in records if r["parse_status"] == s)
    lat = [r["latency_ms"] for r in records if r.get("latency_ms") is not None]
    return {
        "n_cases": n, "OK": cnt("OK"), "API_ERROR": cnt(li.API_ERROR),
        "MODEL_REFUSAL": cnt(li.MODEL_REFUSAL), "SCHEMA_INVALID": cnt(li.SCHEMA_INVALID),
        "schema_valid": sum(1 for r in records if r["schema_valid"]),
        "latency_ms": ({"n": len(lat), "min": min(lat), "max": max(lat),
                        "mean": round(sum(lat) / len(lat), 1)} if lat else None),
        "reconciles": (cnt("OK") + cnt(li.API_ERROR) + cnt(li.MODEL_REFUSAL) + cnt(li.SCHEMA_INVALID)) == n,
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    mode = svc.resolve_mode(os.environ.get("FARMSYNC_LLM_MODE", "off"))
    model = os.environ.get("FARMSYNC_LLM_MODEL", "gpt-5.6-terra")
    cases = load_cases()
    integrity = verify_case_integrity(cases)
    header = {"benchmark": BB.BENCH_VERSION, "benchmark_data_nature": BB.BENCH_DATA_NATURE,
              "mode": mode, "model_requested": model, "integrity": integrity}
    if mode == "off":
        print(json.dumps({**header, "status": "DISABLED"}, indent=2, default=str)); return 0

    # HARD LIVE-FREEZE GATE — before constructing any client, ALL frozen identities + runtime versions +
    # runtime model + fixture instance hash + endpoint must match, else fail-closed (no API budget spent).
    if mode == "live":
        if not os.environ.get("OPENAI_API_KEY"):
            print(json.dumps({**header, "status": "FAILED", "reason": "no OPENAI_API_KEY"}, indent=2, default=str)); return 3
        if not integrity["all_pass"]:
            failed = [k for k, v in integrity["checks"].items() if not v]
            print(json.dumps({**header, "status": "FAILED", "reason": "integrity gate failed", "failed_checks": failed}, indent=2, default=str)); return 4
        if not _official_endpoint_ok():
            print(json.dumps({**header, "status": "FAILED", "reason": "non-official OpenAI endpoint (stale FARMSYNC_LLM_BASE_URL); unset it for the benchmark"}, indent=2, default=str)); return 5
        if not runtime_model_gate(model, integrity["manifest_model"]):
            print(json.dumps({**header, "status": "FAILED", "reason": "runtime model gate: requested %r vs manifest %r (must both be gpt-5.6-terra)" % (model, integrity["manifest_model"])}, indent=2, default=str)); return 6
        # build the deterministic fixture BEFORE creating the client; hard-fail on instance-hash mismatch.
        snapshot, base_state, fx = EV.build_p7_fixture()
        if not fixture_hash_gate(fx["instance_hash"], integrity["manifest_fixture_instance_hash"]):
            print(json.dumps({**header, "status": "FAILED", "reason": "fixture instance_hash gate: fixture %r vs manifest %r (must both be 5ea24037c2d9cb6a)" % (fx["instance_hash"], integrity["manifest_fixture_instance_hash"])}, indent=2, default=str)); return 7
        client = svc.make_client("live")
    else:
        snapshot, base_state, fx = EV.build_p7_fixture()
        client = None                                   # mock builds per-case single-entry clients

    t0 = time.time()
    records = run(cases, client, snapshot, base_state, mode=mode)
    dur = round(time.time() - t0, 3)

    pm = parser_metrics(records); dm = deterministic_metrics(records); rel = reliability_metrics(records)
    result_label = ("OFFLINE HARNESS SELF-CONSISTENCY (MockLLMClient returns gold by construction; NOT "
                    "parser accuracy / benchmark performance)") if mode == "mock" else "LIVE BENCHMARK RESULT"
    report = {**header, "status": "COMPLETE", "duration_s": dur, "result_label": result_label,
              "parser_metrics": pm, "deterministic_metrics": dm, "reliability": rel,
              "fixture_instance_hash": fx["instance_hash"], "api_key_persisted": False, "raw_text_persisted": False}
    tag = "%s_%s" % (mode, svc.INTEGRATION_PROMPT_VERSION.replace("/", "-"))
    with open(os.path.join(OUT_DIR, "benchmark_report_%s.json" % tag), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, sort_keys=True, default=str); f.write("\n")

    # FULL sanitized per-case audit artifact (no raw source_text — it lives in the frozen case file; no key)
    preds = []
    for r in records:
        preds.append({
            "case_id": r["case_id"], "case_hash": hashlib.sha256(r["case_id"].encode()).hexdigest()[:16],
            "category": r["category"], "difficulty": r["difficulty"],
            "parse_status": r["parse_status"], "schema_valid": r["schema_valid"],
            "predicted_parser_fields": {k: r["parsed"].get(k) for k in ("action", "plot_id", "requested_crop", "requested_value", "unit")},
            "expected_parser_fields": r["expected"],
            "predicted_clarification_required": r["predicted_clarification_required"],
            "expected_clarification_required": r["expected_clarification_required"],
            "validation_outcome": r["validation_outcome"], "expected_validation_outcome": r["expected_validation_outcome"],
            "reason_codes": r["reason_codes"], "expected_reason_codes": r["expected_reason_codes"],
            "may_execute": r["may_execute"], "expected_may_execute": r["expected_may_execute"],
            "predicted_deterministic_payload": r["payload"], "expected_deterministic_payload": r["expected_payload"],
            "payload_equiv": r["payload_equiv"],
            "exec_applicable": r["exec_applicable"], "exec_equivalent": r["exec_equivalent"], "exec_detail": r["exec_detail"],
            "latency_ms": r["latency_ms"], "retries": r["retries"], "response_id": r["response_id"],
            "model": r["model"], "prompt_version": r["prompt_version"], "schema_version": r["schema_version"],
            "raw_text_persisted": False, "api_key_persisted": False,
        })
    with open(os.path.join(OUT_DIR, "benchmark_predictions_%s.json" % tag), "w", encoding="utf-8") as f:
        json.dump(preds, f, indent=2, ensure_ascii=False, default=str); f.write("\n")

    print(json.dumps({"status": report["status"], "mode": mode, "result_label": result_label,
                      "case_count": integrity["case_count"], "integrity_all_pass": integrity["all_pass"],
                      "parser_metrics": pm, "deterministic_metrics": dm, "reliability": rel}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
