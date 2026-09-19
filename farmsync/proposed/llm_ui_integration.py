#!/usr/bin/env python3
"""FarmSync — Live-LLM UI INTEGRATION layer (non-frozen; parser/interface only).

Boundary preserved: Farmer NL -> Terra parser (frozen contract) -> run-bound guards/context ->
deterministic FarmSync recommendation/feasibility -> user explicitly saves/acts. The LLM NEVER chooses or
invents a crop, decides feasibility, executes, mutates consent/state, overrides identity, or bypasses rules;
and there is NO silent LIVE->MOCK fallback.

This module is READ-ONLY: it parses + fetches deterministic recommendation/feasibility and returns a
structured interpretation for the UI to display. It performs NO state mutation. Actual crop
recommendations and feasibility verdicts come ONLY from the injected deterministic callables
(recommend_alternative / validate_requested_crop), never from the model.

parser_action  : the FROZEN parser schema action (ACCEPT/REJECT/MODIFY/WITHDRAW/QUERY/CLARIFY).
ui_intent      : an integration-layer intent (REQUEST_ALTERNATIVE/MODIFY/ACCEPT/REJECT/WITHDRAW/QUERY/
                 CLARIFY) derived from parser_action + a deterministic alternative-seeking text signal.
                 REQUEST_ALTERNATIVE is NEVER added to the frozen schema.
"""
from __future__ import annotations

import os
import time

from farmsync.proposed import llm_interaction as li
from farmsync.proposed import llm_service as svc

# Deterministic parser-action -> UI-intent bridge policy version (non-frozen integration layer). Recorded in
# every response + ai-status technical metadata so the manuscript/code can state exactly which deterministic
# UI-intent policy converted frozen parser output into UI behaviour. Bump on any change to the bridge rules
# (cue set, MODIFY-no-crop handling, etc.).
UI_INTENT_POLICY_VERSION = "llm-ui-intent-v2"

# Deterministic alternative-seeking cues (integration layer only; not a parser action).
_ALT_CUES = ("what else", "what other", "another crop", "other crop", "something else", "alternative",
             "options", "what can i grow", "what else can i grow", "different crop", "anything else")

# QUERY routing cues (integration layer only). An explanation query about the current plan/crop is
# answerable from deterministic evidence; an out-of-model prediction question is NOT and must not produce
# an invented answer. These route to integration UI intents (EXPLAIN_CURRENT / EXPLAIN_CROP /
# UNSUPPORTED_QUERY) — they are NOT parser-schema actions.
_EXPLAIN_CUES = ("why", "explain", "reason", "how was", "how did", "basis", "justif", "recommend",
                 "chosen", "picked", "selected")
_OUT_OF_MODEL_CUES = ("survive", "disease", "outbreak", "pest", "next year", "next season", "weather",
                      "forecast", "rain next", "guarantee", "will it", "will this", "future", "predict",
                      "market price", "profit next", "definitely")

# Human-readable phrasings for deterministic feasibility reason codes. Codes without a mapping are shown
# verbatim (never invented). This only VERBALISES codes the deterministic model actually returned.
_REASON_PHRASES = {
    "WATER_INSUFFICIENT": "the available water is insufficient for its requirement",
    "WATERLOGGING_RISK": "the plot's waterlogging exposure is too high for it",
    "SOIL_UNSUITABLE": "the soil is unsuitable for it",
    "SOIL_CLASS_UNSUITABLE": "the soil suitability class does not support it",
    "ROTATION_RESTRICTED": "the crop rotation rules restrict it this season",
    "SEASON_MISMATCH": "it does not match the plot's active season",
    "BUDGET_INSUFFICIENT": "the available budget is insufficient for it",
    "LABOUR_INSUFFICIENT": "the available labour is insufficient for it",
    "CROP_NOT_ADMITTED": "it is not admitted for this plot under the current model",
}


def _humanize_reasons(reasons, binding):
    """Turn deterministic assessment reason codes (+ optional binding detail) into a human sentence. Uses
    only codes/values the deterministic model returned; unknown codes are shown verbatim."""
    reasons = [r for r in (reasons or []) if r]
    if not reasons:
        return None
    phrases = [_REASON_PHRASES.get(r, r) for r in reasons]
    if len(phrases) == 1:
        body = phrases[0]
    else:
        body = ", and ".join([", ".join(phrases[:-1]), phrases[-1]]) if len(phrases) > 2 else " and ".join(phrases)
    detail = ""
    if binding:
        detail = " (" + "; ".join(str(b) for b in binding if b) + ")"
    return body + detail


def _query_route(text):
    """Deterministic QUERY sub-routing. Returns 'EXPLAIN' for an answerable explanation of the current
    plan/crop, or 'UNSUPPORTED' for out-of-model prediction/fact questions. Conservative: anything that is
    not clearly an explanation request, or that asks for a prediction/fact FarmSync's planning model does
    not hold, is UNSUPPORTED (no invented answer)."""
    low = (text or "").lower()
    if any(c in low for c in _OUT_OF_MODEL_CUES):
        return "UNSUPPORTED"
    if any(c in low for c in _EXPLAIN_CUES):
        return "EXPLAIN"
    return "UNSUPPORTED"


def _wants_alternative(text):
    low = (text or "").lower()
    return any(cue in low for cue in _ALT_CUES)


class DeterministicMockParser:
    """Offline deterministic parser for MOCK mode that works on ARBITRARY UI text (unlike the mapping-based
    frozen MockLLMClient). Projects lexical cues into the FROZEN request-schema fields — does NOT modify the
    frozen parser/schema; produces a schema-shaped raw dict that the frozen parse_request validates. Emits
    ONLY frozen-schema actions (ACCEPT/REJECT/MODIFY/WITHDRAW/QUERY/CLARIFY); alternative-seeking is the
    integration ui_intent layer's job. Lives here so llm_service.py stays byte-identical to the closed
    benchmark reference."""
    def __init__(self, allowed_crops=None):
        self.allowed_crops = [c for c in (allowed_crops or []) if isinstance(c, str)]
        self.live = False

    def parse(self, text, trusted_context=None):
        import re as _re
        low = (text or "").strip().lower()
        crops = self.allowed_crops or (list(trusted_context.get("allowed_crops"))
                                       if trusted_context and trusted_context.get("allowed_crops") else [])
        requested = None
        for name in sorted(crops, key=len, reverse=True):
            if name and name.lower() in low:
                requested = name
                break
        target = None
        if requested:
            rl = requested.lower()
            if _re.search(r"(grow|switch to|change to|change .* to|prefer|plant|set .* to)\s*" + _re.escape(rl), low) \
               or _re.search(_re.escape(rl) + r"\s+instead", low) or _re.search(r"grow\s+" + _re.escape(rl), low) \
               or _re.search(r"can i grow\s+" + _re.escape(rl), low):
                target = requested
        vague_alt = _wants_alternative(text)
        rejecting = any(k in low for k in ("don't want", "do not want", "reject", "refuse", "not this", "no thanks"))
        withdrawing = any(k in low for k in ("withdraw", "leave the program", "opt out", "pull out", "stop participating"))
        querying = any(k in low for k in ("why", "explain", "how was", "reasoning", "what is the"))
        accepting = any(k in low for k in ("accept", "i agree", "sounds good", "that works", "go ahead", "confirm"))
        if withdrawing:
            action, crop, clar = "WITHDRAW", None, False
        elif target:
            action, crop, clar = "MODIFY", target, False
        elif vague_alt:
            action, crop, clar = "CLARIFY", None, True
        elif rejecting:
            action, crop, clar = "REJECT", None, False
        elif requested and not target:
            action, crop, clar = "MODIFY", requested, False
        elif querying:
            action, crop, clar = "QUERY", None, False
        elif accepting:
            action, crop, clar = "ACCEPT", None, False
        else:
            action, crop, clar = "CLARIFY", None, True
        raw = {"action": action, "farmer_id": None, "plot_id": None, "requested_crop": crop,
               "requested_value": None, "unit": None, "reason": None,
               "clarification_required": clar, "clarification_question": None, "confidence": 1.0}
        return {"_status": "OK", "raw": raw,
                "meta": {"model": "deterministic-mock", "schema_version": li.SCHEMA_VERSION,
                         "prompt_version": svc.INTEGRATION_PROMPT_VERSION, "live": False, "mode": "mock", "attempts": 1}}


def _parse_for_mode(text, mode, trusted_context, live_kwargs):
    """off -> disabled; mock -> DeterministicMockParser + frozen parse_request; live -> svc.parse_with_mode
    (no silent fallback). Keeps llm_service.py unchanged (frozen-benchmark reference)."""
    if mode == "off":
        return None, "LLM_DISABLED", {"mode": "off"}
    if mode == "mock":
        client = DeterministicMockParser(allowed_crops=(trusted_context or {}).get("allowed_crops"))
        pr, status, meta = li.parse_request(text, client, trusted_context=trusted_context)
        meta = dict(meta or {}); meta["mode"] = "mock"
        return pr, status, meta
    return svc.parse_with_mode(text, mode="live", trusted_context=trusted_context, **(live_kwargs or {}))


def derive_ui_intent(parser_action, source_text, requested_crop):
    """Map the frozen parser action + a deterministic text signal to a UI intent. An alternative-seeking
    message with NO explicitly requested crop becomes REQUEST_ALTERNATIVE; an explicit crop stays MODIFY."""
    if parser_action in ("MODIFY", "CLARIFY", "QUERY") and _wants_alternative(source_text) and not requested_crop:
        return "REQUEST_ALTERNATIVE"
    return parser_action


def ai_parse_run_bound(run_id, farmer_id, plot_id, text, *, recommend_alternative, validate_requested_crop,
                       find_row, run_exists, explain_recommendation=None, mode=None, allowed_crops=None,
                       current_plot_id=None, exclude=None, live_kwargs=None):
    """Run-bound, READ-ONLY parse+interpret for the Farmer Responses UI.

    Verifies run + exact farmer/plot binding; run-bound farmer/plot context wins; a parsed EXPLICIT identity
    that disagrees with the trusted context is rejected. Never mutates state. Crop recommendation/feasibility
    come only from the injected deterministic callables. In live mode a model failure returns an explicit
    sentinel (never mock). `find_row(run_id, farmer_id, plot_id)` -> truthy if the exact pair is in the run;
    `run_exists(run_id)` -> bool.
    """
    live_kwargs = live_kwargs or {}
    m = svc.resolve_mode(mode)
    out = {"mode": m, "run_id": run_id, "farmer_id": farmer_id, "plot_id": plot_id,
           "source_text": text,                      # ephemeral UI response data ONLY; never persisted
           "ui_intent_policy_version": UI_INTENT_POLICY_VERSION,
           "mutated": False, "recommendation_source": "not_applicable",   # set to deterministic_farmsync ONLY
           "llm_role": "parser_interface_only"}      # when a deterministic recommend/validate actually runs

    # ---- server-side guards (no model call yet) ----
    if not run_exists(run_id):
        return {**out, "available": False, "error": "run not found"}
    if not find_row(run_id, farmer_id, plot_id):
        return {**out, "available": False, "error": "farmer/plot pair not in this run"}
    if m == "off":
        return {**out, "available": False, "status": "LLM_DISABLED",
                "error": "AI parsing is off; use the manual controls."}

    # ---- minimal parsing context ONLY (never the run-bound farmer_id / dataset / economics / others) ----
    trusted_context = {"farmer_id": farmer_id}                      # run-validated farmer context; not sent to model
    if allowed_crops:
        trusted_context["allowed_crops"] = list(allowed_crops)     # sent to model (vocab)
    if current_plot_id:
        trusted_context["current_plot_id"] = current_plot_id       # sent to model (parser backfill only)

    # ---- parse (mode-explicit; live failure => sentinel, NEVER silent mock; mock uses the deterministic
    #      mock parser so arbitrary UI text works end-to-end without a response mapping) ----
    t0 = time.time()
    try:
        pr, status, meta = _parse_for_mode(text, m, trusted_context, live_kwargs)
    except Exception as e:
        return {**out, "available": False, "status": li.API_ERROR, "error": type(e).__name__,
                "user_message": "AI is unavailable right now — please use the manual controls.",
                "requires_explicit_user_action": False}
    latency_ms = int((time.time() - t0) * 1000)
    out["latency_ms"] = latency_ms
    out["prompt_version"] = (meta or {}).get("prompt_version")
    out["schema_version"] = li.SCHEMA_VERSION
    out["model"] = (meta or {}).get("model")

    if pr is None or status != "OK":
        # explicit failure surface; manual controls retained by the UI
        return {**out, "available": False, "status": status,
                "requires_explicit_user_action": False,
                "user_message": {
                    li.API_ERROR: "AI is unavailable right now — please use the manual controls.",
                    li.MODEL_REFUSAL: "The assistant declined to interpret that — please use the manual controls.",
                    li.SCHEMA_INVALID: "Couldn't read a clear request — please rephrase or use the manual controls.",
                }.get(status, "AI parsing failed — please use the manual controls.")}

    parser_action = pr.action
    # identity guard: a parsed EXPLICIT farmer id that disagrees with the trusted context is rejected
    parsed_fid = getattr(pr, "farmer_id", None)
    if parsed_fid is not None and parsed_fid != farmer_id:
        return {**out, "available": False, "status": "IDENTITY_MISMATCH", "parser_action": parser_action,
                "requires_explicit_user_action": False,
                "user_message": "That request names a different farmer than the run-bound farmer — not applied."}
    # plot guard: a parsed EXPLICIT plot id that disagrees with the run-bound plot is rejected (never
    # re-target the interpreted action onto the run-bound plot)
    parsed_pid = getattr(pr, "plot_id", None)
    if parsed_pid is not None and parsed_pid != plot_id:
        return {**out, "available": False, "status": "PLOT_CONTEXT_MISMATCH", "parser_action": parser_action,
                "requires_explicit_user_action": False,
                "user_message": "That request names a different plot than the one you're editing — not applied."}

    # authority-manipulation guard: an explicit attempt to override rules/locks/authority is NON-ACTIONABLE.
    # Block BEFORE any deterministic recommendation/feasibility call; no Use button from this parsed request.
    authority_codes = list(li.detect_authority_attempts(text) or [])
    requested_crop = getattr(pr, "requested_crop", None)
    if authority_codes:
        return {**out, "available": True, "status": "AUTHORITY_ATTEMPT_BLOCKED",
                "parser_action": parser_action, "ui_intent": parser_action,
                "requested_crop_parsed": requested_crop,
                "authority_attempt": True, "authority_reason_codes": authority_codes,
                "unsupported_claims": list(getattr(pr, "unsupported_claims", []) or []),
                "deterministic": None, "requires_explicit_user_action": False,
                "understood": "FarmSync rules cannot be overridden. This request was not applied.",
                "user_message": ("FarmSync's feasibility, ownership and lock rules cannot be overridden by a "
                                 "message. The request was not applied; use the standard controls if you "
                                 "want to make an allowed change.")}

    ui_intent = derive_ui_intent(parser_action, text, requested_crop)
    out.update({"parser_action": parser_action, "ui_intent": ui_intent,
                "requested_crop_parsed": requested_crop,
                "unsupported_claims": list(getattr(pr, "unsupported_claims", []) or []),
                "authority_attempt": False, "available": True})

    # ---- deterministic recommendation / feasibility (crop ALWAYS from FarmSync, never the model) ----
    if ui_intent == "REQUEST_ALTERNATIVE":
        det = recommend_alternative(run_id, farmer_id, plot_id, exclude=exclude)
        out["deterministic"] = det
        out["recommendation_source"] = "deterministic_farmsync"   # a deterministic recommend actually ran
        out["understood"] = "You asked for another crop option; FarmSync suggests a feasible alternative."
    elif parser_action == "MODIFY" and requested_crop:
        det = validate_requested_crop(run_id, farmer_id, plot_id, requested_crop)
        out["deterministic"] = det
        out["recommendation_source"] = "deterministic_farmsync"   # deterministic validation ran

        if (
            det.get("available")
            and det.get("feasible") is False
            and det.get("agronomic_feasible") is True
        ):
            out["understood"] = (
                "%s passes FarmSync's current agronomic checks, but it is not "
                "eligible for a new working-plan selection under the current "
                "admitted and cash-positive projected-return rules."
                % requested_crop
            )

        elif (
            det.get("available")
            and det.get("feasible") is False
            and det.get("agronomic_feasible") is False
            and explain_recommendation is not None
        ):
            # Attach deterministic agronomic reason(s) for this exact requested crop.
            ev = explain_recommendation(
                run_id,
                farmer_id,
                plot_id,
                crop=requested_crop
            )

            reasons = (
                ev.get("assessment_reasons")
                if ev.get("available")
                else None
            )
            binding = (
                ev.get("assessment_binding")
                if ev.get("available")
                else None
            )

            out["feasibility_reasons"] = reasons
            out["feasibility_binding"] = binding
            out["explanation_evidence"] = (
                ev if ev.get("available") else None
            )

            human = _humanize_reasons(reasons, binding)

            if human:
                out["understood"] = (
                    "%s does not pass FarmSync's current agronomic checks "
                    "for this plot because %s."
                    % (requested_crop, human)
                )
            else:
                out["understood"] = (
                    "%s does not pass FarmSync's current agronomic checks "
                    "for this plot."
                    % requested_crop
                )

        elif (
            det.get("available")
            and det.get("feasible") is False
            and det.get("agronomic_feasible") is None
        ):
            out["understood"] = (
                "FarmSync cannot establish agronomic feasibility for %s from "
                "the current deterministic evidence, and the crop is not "
                "eligible for a new working-plan selection."
                % requested_crop
            )

        else:
            out["understood"] = (
                "You want to change the crop to %s; FarmSync checked its "
                "agronomic feasibility and working-plan selection eligibility."
                % requested_crop
            )
    elif parser_action == "QUERY" and explain_recommendation is not None:
        route = _query_route(text)
        if route == "EXPLAIN":
            # Gap 1: grounded deterministic explanation of the current row crop (or a named crop).
            crop_arg = requested_crop or None       # None -> explain the current recommendation for this row
            ev = explain_recommendation(run_id, farmer_id, plot_id, crop=crop_arg)
            out["ui_intent"] = "EXPLAIN_CROP" if crop_arg else "EXPLAIN_CURRENT"
            if ev.get("available"):
                out["deterministic"] = ev
                out["recommendation_source"] = "deterministic_farmsync"   # deterministic explanation ran
                crop = ev.get("crop")
                agronomic = ev.get("agronomic_feasible")
                eligible = ev.get("eligible_for_selection")
                current_plan = ev.get("current_plan_crop")

                if agronomic is False:
                    human = _humanize_reasons(
                        ev.get("assessment_reasons"),
                        ev.get("assessment_binding")
                    )

                    out["understood"] = (
                        "%s does not pass the current FarmSync agronomic checks for this plot%s."
                        % (crop, (" because " + human) if human else "")
                    )

                elif current_plan and not eligible:
                    parts = [
                        "%s is the current FarmSync recommendation for this plot" % crop,
                        "the current agronomic checks show no blocking constraint",
                    ]

                    cash = ev.get("expected_cash")
                    if cash is not None:
                        parts.append(
                            "the stored current plan records an expected cash figure of %s"
                            % cash
                        )

                    parts.append(
                        "the current alternative-selection layer does not reproduce a "
                        "rankable cash-positive entry for this crop, so FarmSync does not "
                        "invent a new rank"
                    )

                    out["understood"] = ". ".join(parts) + "."

                elif eligible:
                    cash = ev.get("expected_cash")
                    rank = ev.get("overall_rank")

                    parts = [
                        "%s passes the current FarmSync agronomic checks and is eligible "
                        "for selection" % crop
                    ]

                    if rank:
                        parts.append(
                            "ranked #%s by projected return among currently eligible crops"
                            % rank
                        )

                    if cash is not None:
                        parts.append(
                            "with an expected cash figure of %s" % cash
                        )

                    out["understood"] = ", ".join(parts) + "."

                elif agronomic is True:
                    out["understood"] = (
                        "%s passes the current agronomic checks, but FarmSync does not have "
                        "a current selectable cash-positive ranking entry for this crop."
                        % crop
                    )

                else:
                    out["understood"] = (
                        "FarmSync cannot establish a grounded feasibility explanation for %s "
                        "from the current deterministic evidence." % crop
                    )
            else:
                out["deterministic"] = None
                out["understood"] = "FarmSync cannot resolve an explanation for this plot from the current evidence."
        else:
            # Gap 3: out-of-model / non-explanation query -> safe, no invented answer, no recommendation.
            out["ui_intent"] = "UNSUPPORTED_QUERY"
            out["deterministic"] = None
            out["understood"] = "FarmSync cannot determine that from the current planning evidence."
            out["user_message"] = ("FarmSync cannot determine that from the current planning evidence. It "
                                   "can explain why a crop was recommended or whether a specific crop is "
                                   "feasible for this plot.")
    elif parser_action == "MODIFY" and not requested_crop:
        # vague MODIFY, no crop, and no explicit alternative-seeking cue (else ui_intent would already be
        # REQUEST_ALTERNATIVE above). Conservative pre-results policy (v1): do NOT silently generate a crop
        # recommendation — keep it clarification-oriented so the farmer specifies a crop or asks for options.
        out["deterministic"] = None
        out["ui_intent"] = "CLARIFY"
        out["understood"] = ("You want to change the crop but didn't say which. Please name a crop (e.g. "
                             "\"grow maize\") or ask \"what else can I grow?\" for feasible options.")
    else:
        # ACCEPT / REJECT / WITHDRAW / QUERY / CLARIFY: no crop recommendation needed; show understood action
        out["deterministic"] = None
        out["understood"] = {
            "ACCEPT": "You want to accept the current plan for this plot.",
            "REJECT": "You want to reject the current proposal for this plot.",
            "WITHDRAW": "You want to withdraw this plot from the planning cycle.",
            "QUERY": "You asked for an explanation of the current plan.",
            "CLARIFY": "Your request needs clarification before FarmSync can act.",
        }.get(parser_action, "FarmSync understood your request.")

    # Parsing and explanation never mutate state. Only intents that could
    # result in a later explicit Save / Use operation are actionable.
    actionable_intents = {
        "REQUEST_ALTERNATIVE",
        "MODIFY",
        "ACCEPT",
        "REJECT",
        "WITHDRAW",
    }

    out["requires_explicit_user_action"] = (
        out.get("ui_intent") in actionable_intents
    )

    return out


def mode_label(mode=None, model=None):
    """UI-facing mode label. 'Live · <model>' only in live mode."""
    m = svc.resolve_mode(mode)
    model = model or os.environ.get("FARMSYNC_LLM_MODEL", "gpt-5.6-terra")
    return {"off": "Off", "mock": "Development · Mock", "live": "Live · %s" % model}[m]
