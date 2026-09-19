"""Tests for the OFFLINE post-hoc audit of the closed live benchmark. No network / no live client."""
import csv
import hashlib
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

import farmsync_llm_benchmark_posthoc as PH

_DIR = os.path.join(_ROOT, "results", "farmsync", "qa", "llm_benchmark")
_SRCS = [
    os.path.join(_DIR, "benchmark_report_live_p7-parse-live-v3.json"),
    os.path.join(_DIR, "benchmark_predictions_live_p7-parse-live-v3.json"),
]

EXPECTED_REPORT_SHA256 = (
    "636d8e784572488d127ddf28908fc24facf38e0246536e97072a1b562bc859a5"
)

EXPECTED_PREDICTIONS_SHA256 = (
    "05ca4ad6a30599847a7474f33c82d629acdec4dd73faeb48503ad5917b26d2ee"
)

_SRC_SHA_AT_IMPORT = {
    p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    for p in _SRCS
}

def test_authoritative_live_artifact_hashes():
    report_sha = hashlib.sha256(open(_SRCS[0], "rb").read()).hexdigest()
    predictions_sha = hashlib.sha256(open(_SRCS[1], "rb").read()).hexdigest()

    assert report_sha == EXPECTED_REPORT_SHA256
    assert predictions_sha == EXPECTED_PREDICTIONS_SHA256

def test_source_live_artifacts_read_only():
    # running the audit must not mutate the source live files
    PH.run()
    for p in _SRCS:
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() == _SRC_SHA_AT_IMPORT[p], "source mutated: %s" % p


def test_counts_reconcile_to_322():
    report, preds = PH.load()
    a = PH.audit(report, preds)
    assert a["n_cases"] == 322
    assert a["reconciliation"]["n_cases_equals_322"] is True
    assert a["reconciliation"]["status_sum_equals_n"] is True
    # parser action: correct + mismatch == 322
    assert a["parser_metrics_derived"]["action"]["correct"] + a["action_mismatch"]["count"] == 322


def test_mismatch_sets_reconcile():
    report, preds = PH.load()
    a = PH.audit(report, preds)
    # payload-equiv mismatch set equals the union of the 4 known downstream cases
    assert set(
        a["deterministic_mismatch"]["validated_payload"]["case_ids"]
    ) == {"b214_qry", "b228_qry", "b258_injlike", "b285_polite"}
    # action confusion pairs sum to the action mismatch count
    assert sum(a["action_mismatch"]["confusion_pairs"].values()) == a["action_mismatch"]["count"]
    # may_execute mismatch set == conservative flips (no unsafe flips here) union
    may = set(a["deterministic_mismatch"]["may_execute"]["case_ids"])
    assert may == set(a["may_execute_directional"]["conservative_true_to_false"]["case_ids"])


def test_unsafe_direction_derived_not_hardcoded():
    # recompute directly from predictions and compare to the audit's derived value
    report, preds = PH.load()
    a = PH.audit(report, preds)
    unsafe = [p["case_id"] for p in preds if p["expected_may_execute"] is False and p["may_execute"] is True]
    cons = [p["case_id"] for p in preds if p["expected_may_execute"] is True and p["may_execute"] is False]
    assert a["may_execute_directional"]["unsafe_false_to_true"]["count"] == len(unsafe)
    assert a["may_execute_directional"]["conservative_true_to_false"]["count"] == len(cons)
    # this benchmark's file-derived truth: 0 unsafe, 2 conservative
    assert a["may_execute_directional"]["unsafe_false_to_true"]["count"] == 0
    assert a["may_execute_directional"]["conservative_true_to_false"]["count"] == 2


def test_execution_equivalence_from_flags():
    report, preds = PH.load()
    a = PH.audit(report, preds)
    applic = sum(1 for p in preds if p["exec_applicable"])
    eq = sum(1 for p in preds if p["exec_applicable"] and p["exec_equivalent"] is True)
    assert a["execution_equivalence"]["applicable_denominator"] == applic
    assert a["execution_equivalence"]["equivalent_count"] == eq
    assert a["execution_equivalence"]["non_applicable_count"] == 322 - applic


def test_output_is_deterministic():
    PH.run()
    b1 = open(PH.AUDIT_OUT, "rb").read(); c1 = open(PH.CSV_OUT, "rb").read()
    PH.run()
    b2 = open(PH.AUDIT_OUT, "rb").read(); c2 = open(PH.CSV_OUT, "rb").read()
    assert b1 == b2 and c1 == c2


def test_no_network_or_live_llm_path():
    src = open(os.path.join(_ROOT, "scripts", "farmsync_llm_benchmark_posthoc.py")).read()
    for bad in ("import openai", "from openai", "ResponsesLLMClient", "make_client", "responses.create",
                "urllib.request", "requests.", "api.openai.com", "build_p7_fixture", "run_dev_benchmark"):
        assert bad not in src, "posthoc must not reference %r" % bad


def test_source_sha_recorded_in_audit():
    report, preds = PH.load()
    a = PH.audit(report, preds)
    assert a["source_files"]["report"]["sha256"] == hashlib.sha256(open(_SRCS[0], "rb").read()).hexdigest()
    assert a["source_files"]["predictions"]["sha256"] == hashlib.sha256(open(_SRCS[1], "rb").read()).hexdigest()


def test_error_csv_rows_match_union_mismatch():
    report, preds = PH.load()
    a = PH.audit(report, preds)
    PH.run()
    with open(PH.CSV_OUT, newline="") as f:
        rows = list(csv.DictReader(f))
    assert {r["case_id"] for r in rows} == set(a["mismatch_breakdown"]["union_mismatch_case_ids"])
