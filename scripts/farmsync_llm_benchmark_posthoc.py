#!/usr/bin/env python3
"""FarmSync — OFFLINE post-hoc audit of the CLOSED one-time live >=300 benchmark.

Reads ONLY the completed, frozen live result artifacts and deterministically derives an audit + an
error-case CSV. It NEVER imports/calls the live client, NEVER calls OpenAI, and NEVER modifies benchmark
cases/gold/manifest/prompt/schema/service. Post-hoc analysis, not benchmark evidence.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIR = os.path.join(_ROOT, "results", "farmsync", "qa", "llm_benchmark")
REPORT = os.path.join(_DIR, "benchmark_report_live_p7-parse-live-v3.json")
PREDS = os.path.join(_DIR, "benchmark_predictions_live_p7-parse-live-v3.json")
AUDIT_OUT = os.path.join(_DIR, "benchmark_live_audit_v1.json")
CSV_OUT = os.path.join(_DIR, "benchmark_live_error_cases_v1.csv")


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load():
    report = json.load(open(REPORT, encoding="utf-8"))
    preds = json.load(open(PREDS, encoding="utf-8"))
    return report, preds


def _norm_rc(x):
    return sorted(x or [])


def audit(report, preds):
    n = len(preds)
    # --- parser action mismatches (only meaningful when parse OK; fail-closed already applied upstream) ---
    action_mm = [p for p in preds if p["parse_status"] == "OK"
                 and (p["predicted_parser_fields"] or {}).get("action") != (p["expected_parser_fields"] or {}).get("action")]
    action_pairs = Counter((( p["expected_parser_fields"] or {}).get("action"),
                            (p["predicted_parser_fields"] or {}).get("action")) for p in action_mm)

    # --- other field mismatches ---
    def field_mm(f):
        return [p["case_id"] for p in preds if p["parse_status"] == "OK"
                and (p["predicted_parser_fields"] or {}).get(f) != (p["expected_parser_fields"] or {}).get(f)]

    field_mismatch_map = {
        f: field_mm(f)
        for f in ("plot_id", "requested_crop", "requested_value", "unit")
    }

    field_mismatch_ids = {
        case_id
        for ids in field_mismatch_map.values()
        for case_id in ids
    }

    clar_mm = [
        p["case_id"]
        for p in preds
        if p["parse_status"] == "OK"
        and bool(p["predicted_clarification_required"])
        != bool(p["expected_clarification_required"])
    ]

    # --- deterministic boundary mismatches ---
    outcome_mm = [p["case_id"] for p in preds if p["validation_outcome"] != p["expected_validation_outcome"]]
    reason_mm = [p["case_id"] for p in preds if _norm_rc(p["reason_codes"]) != _norm_rc(p["expected_reason_codes"])]
    may_mm = [p["case_id"] for p in preds if p["may_execute"] != p["expected_may_execute"]]
    payload_mm = [p["case_id"] for p in preds if not p["payload_equiv"]]

    # --- may_execute directional flips (derived, not hardcoded) ---
    unsafe_flips = [p["case_id"] for p in preds
                    if p["expected_may_execute"] is False and p["may_execute"] is True]   # false -> true
    conservative_flips = [p["case_id"] for p in preds
                          if p["expected_may_execute"] is True and p["may_execute"] is False]  # true -> false

    # --- execution equivalence (from the frozen per-case flags) ---
    exec_applic = [p for p in preds if p["exec_applicable"]]
    exec_eq = [p for p in exec_applic if p["exec_equivalent"] is True]

    # --- transport / reliability ---
    status_counts = Counter(p["parse_status"] for p in preds)
    lat = [p["latency_ms"] for p in preds if p.get("latency_ms") is not None]

    # --- mismatch breakdowns by category / difficulty (union of any boundary/parser mismatch) ---
    mismatch_ids = (
        set(p["case_id"] for p in action_mm)
        | set(clar_mm)
        | field_mismatch_ids
        | set(outcome_mm)
        | set(reason_mm)
        | set(may_mm)
        | set(payload_mm)
    )
    by_cat = Counter(p["category"] for p in preds if p["case_id"] in mismatch_ids)
    by_diff = Counter(p["difficulty"] for p in preds if p["case_id"] in mismatch_ids)

    def acc(field):
        ok = sum(1 for p in preds if p["parse_status"] == "OK"
                 and (p["predicted_parser_fields"] or {}).get(field) == (p["expected_parser_fields"] or {}).get(field))
        return ok, round(ok / n, 6)

    parser = {}
    for f in ("action", "plot_id", "requested_crop", "requested_value", "unit"):
        ok, rate = acc(f)
        parser[f] = {"correct": ok, "denominator": n, "accuracy": rate}
    clar_ok = sum(1 for p in preds if p["parse_status"] == "OK"
                  and bool(p["predicted_clarification_required"]) == bool(p["expected_clarification_required"]))
    parser["clarification_required"] = {"correct": clar_ok, "denominator": n, "accuracy": round(clar_ok / n, 6)}

    return {
        "source_files": {
            "report": {"path": os.path.relpath(REPORT, _ROOT).replace("\\", "/"), "sha256": _sha(REPORT)},
            "predictions": {"path": os.path.relpath(PREDS, _ROOT).replace("\\", "/"), "sha256": _sha(PREDS)},
        },
        "benchmark_identity": {k: report["integrity"].get(k) for k in
                               ("benchmark_version", "case_count", "case_file_sha256", "semantic_case_set_hash",
                                "prompt_version", "schema_version", "manifest_model", "manifest_fixture_instance_hash")}
        if "manifest_model" in report.get("integrity", {}) else report.get("integrity", {}),
        "data_nature": report.get("benchmark_data_nature"),
        "result_label": report.get("result_label"),
        "n_cases": n,
        "parser_metrics_derived": parser,
        "action_mismatch": {
            "count": len(action_mm),
            "case_ids": sorted(p["case_id"] for p in action_mm),
            "confusion_pairs": {("%s->%s" % k): v for k, v in sorted(action_pairs.items())},
        },
        "field_mismatch_case_ids": field_mismatch_map,
        "clarification_mismatch": {"count": len(clar_mm), "case_ids": sorted(clar_mm)},
        "deterministic_mismatch": {
            "validation_outcome": {"count": len(outcome_mm), "case_ids": sorted(outcome_mm)},
            "reason_codes": {"count": len(reason_mm), "case_ids": sorted(reason_mm)},
            "may_execute": {"count": len(may_mm), "case_ids": sorted(may_mm)},
            "validated_payload": {"count": len(payload_mm), "case_ids": sorted(payload_mm)},
        },
        "may_execute_directional": {
            "unsafe_false_to_true": {"count": len(unsafe_flips), "case_ids": sorted(unsafe_flips)},
            "conservative_true_to_false": {"count": len(conservative_flips), "case_ids": sorted(conservative_flips)},
        },
        "execution_equivalence": {
            "applicable_denominator": len(exec_applic),
            "equivalent_count": len(exec_eq),
            "rate": (round(len(exec_eq) / len(exec_applic), 6) if exec_applic else None),
            "non_applicable_count": n - len(exec_applic),
        },
        "mismatch_breakdown": {"by_category": dict(sorted(by_cat.items())), "by_difficulty": dict(sorted(by_diff.items())),
                               "union_mismatch_case_ids": sorted(mismatch_ids)},
        "reliability": {"status_counts": dict(status_counts),
                        "latency_ms": ({"n": len(lat), "min": min(lat), "max": max(lat),
                                        "mean": round(sum(lat) / len(lat), 1)} if lat else None),
                        "reconciles": sum(status_counts.values()) == n},
        "reconciliation": {"n_cases_equals_322": n == 322,
                           "status_sum_equals_n": sum(status_counts.values()) == n},
    }


def error_rows(preds):
    rows = []
    for p in preds:
        pf, ef = (p["predicted_parser_fields"] or {}), (p["expected_parser_fields"] or {})
        action_mm = p["parse_status"] == "OK" and pf.get("action") != ef.get("action")

        field_mm = (
            p["parse_status"] == "OK"
            and any(
                pf.get(f) != ef.get(f)
                for f in ("plot_id", "requested_crop", "requested_value", "unit")
            )
        )

        clar_mm = (
            p["parse_status"] == "OK"
            and bool(p["predicted_clarification_required"])
            != bool(p["expected_clarification_required"])
        )

        outcome_mm = p["validation_outcome"] != p["expected_validation_outcome"]
        reason_mm = _norm_rc(p["reason_codes"]) != _norm_rc(p["expected_reason_codes"])
        may_mm = p["may_execute"] != p["expected_may_execute"]
        payload_mm = not p["payload_equiv"]

        if any([action_mm, field_mm, clar_mm, outcome_mm, reason_mm, may_mm, payload_mm]):
            rows.append({
                "case_id": p["case_id"], "category": p["category"], "difficulty": p["difficulty"],
                "parse_status": p["parse_status"],
                "expected_action": ef.get("action"), "predicted_action": pf.get("action"),
                "action_mismatch": action_mm,
                "expected_clarification": p["expected_clarification_required"],
                "predicted_clarification": p["predicted_clarification_required"],
                "clarification_mismatch": clar_mm,
                "expected_validation_outcome": p["expected_validation_outcome"],
                "validation_outcome": p["validation_outcome"], "outcome_mismatch": outcome_mm,
                "expected_reason_codes": "|".join(_norm_rc(p["expected_reason_codes"])),
                "reason_codes": "|".join(_norm_rc(p["reason_codes"])), "reason_mismatch": reason_mm,
                "expected_may_execute": p["expected_may_execute"], "may_execute": p["may_execute"],
                "may_execute_mismatch": may_mm,
                "payload_equiv": p["payload_equiv"],
                "exec_applicable": p["exec_applicable"], "exec_equivalent": p["exec_equivalent"],
            })
    rows.sort(key=lambda r: r["case_id"])
    return rows


def write_outputs(audit_obj, rows):
    with open(AUDIT_OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(audit_obj, f, indent=2, ensure_ascii=False, sort_keys=True, default=str)
        f.write("\n")
    cols = ["case_id", "category", "difficulty", "parse_status", "expected_action", "predicted_action",
            "action_mismatch", "expected_clarification", "predicted_clarification", "clarification_mismatch",
            "expected_validation_outcome", "validation_outcome", "outcome_mismatch",
            "expected_reason_codes", "reason_codes", "reason_mismatch",
            "expected_may_execute", "may_execute", "may_execute_mismatch",
            "payload_equiv", "exec_applicable", "exec_equivalent"]
    with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def run():
    report, preds = load()
    a = audit(report, preds)
    rows = error_rows(preds)
    write_outputs(a, rows)
    return a, rows


def main():
    a, rows = run()
    print(json.dumps({
        "n_cases": a["n_cases"],
        "action_mismatch_count": a["action_mismatch"]["count"],
        "action_mismatch_case_ids": a["action_mismatch"]["case_ids"],
        "action_confusion_pairs": a["action_mismatch"]["confusion_pairs"],
        "clarification_mismatch": a["clarification_mismatch"],
        "deterministic_mismatch_counts": {k: v["count"] for k, v in a["deterministic_mismatch"].items()},
        "unsafe_false_to_true": a["may_execute_directional"]["unsafe_false_to_true"],
        "conservative_true_to_false": a["may_execute_directional"]["conservative_true_to_false"],
        "execution_equivalence": a["execution_equivalence"],
        "mismatch_by_category": a["mismatch_breakdown"]["by_category"],
        "mismatch_by_difficulty": a["mismatch_breakdown"]["by_difficulty"],
        "reliability": a["reliability"],
        "source_sha256": {k: v["sha256"] for k, v in a["source_files"].items()},
        "error_rows": len(rows),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
