"""
Proposed Phase 7 — development benchmark harness (offline / mock-driven).

Runs a fixed DEVELOPMENT case set through the full boundary
(parse -> deterministic validate -> equivalence -> grounded explanation) and computes
reproducible metrics. This is a prompt-engineering / architecture-validation set, NOT the
publication benchmark. With a mock client, parse-side numbers reflect the mock; live LLM
parse accuracy is reported separately and marked NOT RUN when no API is available.
"""

from __future__ import annotations
from . import llm_interaction as li


PARSE_FIELDS = ["farmer_id", "plot_id", "requested_crop", "requested_value", "unit"]


def _field_prf(preds, golds):
    tp = fp = fn = 0
    for p, g in zip(preds, golds):
        for k in PARSE_FIELDS:
            pv, gv = p.get(k), g.get(k)
            if gv is not None and pv == gv: tp += 1
            elif gv is not None and pv != gv: fn += 1
            elif gv is None and pv is not None: fp += 1
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2*prec*rec/(prec+rec) if (prec+rec) else 0.0
    return round(prec, 4), round(rec, 4), round(f1, 4)


def run_dev_benchmark(cases, client, snapshot, base_state=None):
    preds = []
    for c in cases:
        rec = {"id": c["id"], "category": c["category"], "source_text": c["source_text"]}
        pr, status, meta = li.parse_request(c["source_text"], client,
                                            trusted_context=c.get("trusted_context"))
        rec["parse_status"] = status
        rec["schema_valid"] = status == "OK"
        rec["llm_meta"] = meta
        if pr is None:
            rec.update({"validation_outcome": None, "llm_payload": None,
                        "gold_payload": c.get("gold_payload"),
                        "payload_equiv": (c.get("gold_payload") is None),
                        "exec_applicable": False, "exec_equivalent": None})
            preds.append(rec); continue
        rec["source_text_authoritative"] = (pr.source_text == c["source_text"])
        rec["parsed"] = {k: getattr(pr, k) for k in ["action"] + PARSE_FIELDS}
        rec["unsupported_claims"] = pr.unsupported_claims
        vr = li.validate_request(pr, snapshot, trusted_context=c.get("trusted_context"))
        rec["validation_outcome"] = vr.outcome
        rec["reason_codes"] = vr.reason_codes
        rec["may_execute"] = vr.may_execute
        rec["requires_renewed_consent"] = vr.requires_renewed_consent
        rec["llm_payload"] = vr.deterministic_action_payload
        rec["gold_payload"] = c.get("gold_payload")
        rec["payload_equiv"] = li.payload_equivalent(vr.deterministic_action_payload, c.get("gold_payload"))
        # TRUE execution-level outcome equivalence (only when both payloads are executable)
        if base_state is not None and vr.may_execute and c.get("gold_payload"):
            applicable, equivalent, detail = li.outcome_execution_equivalent(
                vr.deterministic_action_payload, c.get("gold_payload"), base_state)
        else:
            applicable, equivalent, detail = False, None, {"reason": "not_executed"}
        rec["exec_applicable"] = applicable
        rec["exec_equivalent"] = equivalent
        rec["exec_detail"] = detail
        # grounded explanation from ONLY deterministic facts
        facts = dict(c.get("deterministic_facts", {}))
        facts.update({"parsed_action": pr.action, "outcome": vr.outcome,
                      "reason_codes": vr.reason_codes, "requested_crop": pr.requested_crop,
                      "requires_renewed_consent": vr.requires_renewed_consent})
        try:
            expl = li.build_grounded_explanation(vr, facts)
            rec["explanation"] = expl["explanation_text"]
            rec["explanation_grounded"] = all(fid in facts for fid in expl["referenced_fact_ids"])
            rec["numeric_consistency_ok"] = expl["numeric_consistency_ok"]
        except AssertionError:
            rec["explanation"] = None; rec["explanation_grounded"] = False
            rec["numeric_consistency_ok"] = False; rec["explanation_status"] = li.EXPLANATION_ERROR
        preds.append(rec)
    return preds, _metrics(cases, preds)


def _metrics(cases, preds):
    by_id = {c["id"]: c for c in cases}
    n = len(preds)
    api_fail = sum(1 for p in preds if p["parse_status"] in (li.API_ERROR, li.MODEL_REFUSAL))
    schema_valid = sum(1 for p in preds if p["schema_valid"])
    parsed = [p for p in preds if "parsed" in p]
    # action exact match (over parsed, vs gold action)
    action_match = sum(1 for p in parsed if p["parsed"]["action"] == by_id[p["id"]]["gold_parse"]["action"])
    pred_fields = [p["parsed"] for p in parsed]
    gold_fields = [by_id[p["id"]]["gold_parse"] for p in parsed]
    prec, rec, f1 = _field_prf(pred_fields, gold_fields)
    def acc(field):
        rel = [p for p in parsed if by_id[p["id"]]["gold_parse"].get(field) is not None]
        if not rel: return None
        return round(sum(1 for p in rel if p["parsed"].get(field) == by_id[p["id"]]["gold_parse"].get(field))/len(rel), 4)
    # clarification P/R
    gold_clar = {c["id"] for c in cases if c.get("gold_validation_outcome") == li.CLARIFICATION_REQUIRED}
    pred_clar = {p["id"] for p in preds if p.get("validation_outcome") == li.CLARIFICATION_REQUIRED}
    cp = len(gold_clar & pred_clar)/len(pred_clar) if pred_clar else 1.0
    cr = len(gold_clar & pred_clar)/len(gold_clar) if gold_clar else 1.0
    # rejection metrics
    invalid_ids = {c["id"] for c in cases if c.get("gold_validation_outcome") == li.VALIDATION_REJECTED}
    rej_ok = sum(1 for p in preds if p["id"] in invalid_ids and p.get("validation_outcome") == li.VALIDATION_REJECTED)
    hl_ids = {c["id"] for c in cases if c["category"] == "hard_locked_modify"}
    hl_ok = sum(1 for p in preds if p["id"] in hl_ids and "HARD_LOCK_IMMUTABLE" in (p.get("reason_codes") or []))
    unsup_ids = {c["id"] for c in cases if c["category"] in ("unsupported_injection", "choose_for_me") or c.get("expect_unsupported")}
    unsup_ok = sum(1 for p in preds if p["id"] in unsup_ids and (p.get("unsupported_claims") or p.get("validation_outcome") in (li.CLARIFICATION_REQUIRED, li.VALIDATION_REJECTED)))
    # equivalence + grounding
    val = [p for p in preds if "payload_equiv" in p]
    payload_equiv = sum(1 for p in val if p["payload_equiv"])
    # TRUE execution outcome equivalence: only over cases actually executed on cloned state
    executed = [p for p in preds if p.get("exec_applicable")]
    exec_equiv = sum(1 for p in executed if p.get("exec_equivalent"))
    na_outcome = sum(1 for p in preds if p.get("exec_applicable") is False and "parsed" in p)
    src_recs = [p for p in preds if "source_text_authoritative" in p]
    src_ok = sum(1 for p in src_recs if p["source_text_authoritative"])
    expl_recs = [p for p in preds if "explanation_grounded" in p]
    grounded = sum(1 for p in expl_recs if p["explanation_grounded"])
    numeric_ok = sum(1 for p in expl_recs if p.get("numeric_consistency_ok"))
    unsupported_expl = sum(1 for p in expl_recs if not p["explanation_grounded"])
    return {
        "n_cases": n, "live_evaluation": False, "client": "mock",
        "api_failures": api_fail, "api_success": n - api_fail,
        "_group_parse_metrics_MOCK_architecture_validation_only": {
            "schema_valid_rate": round(schema_valid/n, 4),
            "action_exact_match": round(action_match/len(parsed), 4) if parsed else None,
            "field_precision": prec, "field_recall": rec, "field_f1": f1,
            "crop_extraction_accuracy": acc("requested_crop"),
            "farmer_extraction_accuracy": acc("farmer_id"),
            "plot_extraction_accuracy": acc("plot_id"),
            "numeric_extraction_accuracy": acc("requested_value"), "unit_accuracy": acc("unit"),
            "clarification_precision": round(cp, 4), "clarification_recall": round(cr, 4),
        },
        "_group_deterministic_boundary": {
            "invalid_action_rejection_rate": round(rej_ok/len(invalid_ids), 4) if invalid_ids else None,
            "hard_lock_rejection_rate": round(hl_ok/len(hl_ids), 4) if hl_ids else None,
            "unsupported_constraint_handled_rate": round(unsup_ok/len(unsup_ids), 4) if unsup_ids else None,
            "source_text_authoritative_rate": round(src_ok/len(src_recs), 4) if src_recs else None,
        },
        "_group_equivalence": {
            "validated_payload_equivalence_rate": round(payload_equiv/len(val), 4) if val else None,
            "validated_payload_equivalence_denominator": len(val),
            "boundary_state_execution_equivalence_rate": round(exec_equiv/len(executed), 4) if executed else None,
            "boundary_state_execution_equivalence_denominator": len(executed),
            "boundary_state_execution_equivalence_true": exec_equiv,
            "outcome_equivalence_not_applicable": na_outcome,
            "note": ("EXECUTION-level equivalence over the minimal BoundaryState executor "
                     "(action applied to independent cloned plan state), NOT the full FarmSync "
                     "optimiser/reoptimisation handler. Full deterministic FarmSync outcome "
                     "equivalence (running the actual reopt handler) is a publication-evaluation "
                     "strengthening item, not built here. Payload equivalence is separate/weaker."),
        },
        "_group_explanation": {
            "explanation_groundedness_rate": round(grounded/len(expl_recs), 4) if expl_recs else None,
            "numerical_consistency_rate": round(numeric_ok/len(expl_recs), 4) if expl_recs else None,
            "unsupported_explanation_rate": round(unsupported_expl/len(expl_recs), 4) if expl_recs else None,
        },
        "note": "DEVELOPMENT / prompt-engineering set with MOCK client; live LLM parse accuracy NOT RUN. Parse-side numbers reflect the mock, not a live model.",
    }
