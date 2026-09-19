from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from farmsync import exploratory_run as xr


PROTOCOL_VERSION = "scenario-ab-v3"

SCENARIO_DEFINITION = {
    "A": {
        "label": "Reference workflow",
        "initial_intervention": "none",
        "renewed_consent": (
            "ACCEPT all genuinely pending changed rows"
        ),
    },

    "B": {
        "label": (
            "Constructed illustrative behavioural scenario"
        ),

        "interpretation": (
            "Constructed case-study inputs only. "
            "The behavioural proportions are experimental "
            "scenario definitions, not estimates of empirical "
            "farmer behaviour."
        ),

        "population_scope": (
            "Farmer withdrawal eligibility is defined over "
            "farmers with at least one reference-ACCEPT offer. "
            "A selected withdrawal is farmer-cycle scoped and "
            "therefore applies to all offered rows belonging "
            "to that farmer."
        ),

        "withdrawal": {
            "unit": "farmer",
            "rate": 0.025,
            "quota_rule": "deterministic round-half-up",
            "selection": (
                "SHA-256 deterministic ranking of eligible "
                "farmer_id values"
            ),
            "scope": (
                "all offered rows for each selected farmer"
            ),
        },

        "remaining_initial_actions": {
            "unit": "offer_row",
            "denominator": (
                "remaining reference-ACCEPT offer rows after "
                "selected withdrawn farmers are removed"
            ),
            "REJECT_rate": 0.10,
            "NO_RESPONSE_rate": 0.05,
            "MODIFY_rate": 0.0,
            "quota_rule": "deterministic round-half-up",
            "selection": (
                "SHA-256 deterministic ranking of "
                "farmer_id + plot_id"
            ),
        },

        "renewed_consent": {
            "unit": "genuinely_pending_changed_row",
            "REJECT_rate": 0.10,
            "NO_RESPONSE_rate": 0.05,
            "ACCEPT": "all remaining rows",
            "quota_rule": "deterministic round-half-up",
            "selection": (
                "SHA-256 deterministic ranking of "
                "farmer_id + plot_id"
            ),
        },

        "modify": (
            "Not used in scenario-ab-v3. "
            "Crop-preference perturbation is kept separate "
            "from this participation-and-consent case study."
        ),
    },
}

def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha16(value: Any) -> str:
    return hashlib.sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()[:16]


def _rank_key(
    stage: str,
    farmer_id: str,
    plot_id: str,
) -> tuple[str, str, str]:
    token = (
        f"{PROTOCOL_VERSION}|{stage}|"
        f"{farmer_id}|{plot_id}"
    )

    digest = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    return (
        digest,
        str(farmer_id),
        str(plot_id),
    )


def _farmer_rank_key(
    stage: str,
    farmer_id: str,
) -> tuple[str, str]:
    token = (
        f"{PROTOCOL_VERSION}|{stage}|"
        f"{farmer_id}"
    )

    digest = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    return (
        digest,
        str(farmer_id),
    )


def _is_offer(rec: dict) -> bool:
    return (
        rec.get("crop_id") is not None
        or rec.get("crop") is not None
    )


def _quota(
    n: int,
    numerator: int,
    denominator: int,
) -> int:
    """Deterministic round-half-up quota."""
    return (
        n * numerator
        + denominator // 2
    ) // denominator


def _effective_initial_response(rec: dict) -> str | None:
    if rec.get("action") is not None:
        return rec.get("action")
    return rec.get("recorded_response")


def _manifest_hash(
    stage: str,
    entries: list[dict],
) -> str:
    return _sha16({
        "protocol_version": PROTOCOL_VERSION,
        "stage": stage,
        "entries": entries,
    })


def _counts(
    rows: list[dict],
    key: str,
) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                row[key]
                for row in rows
            ).items()
        )
    )



def _withdrawn_farmer_ids(
    rows: list[dict],
) -> list[str]:
    return sorted({
        str(row["farmer_id"])
        for row in rows
        if row.get("action")
        == "WITHDRAW"
    })


def build_initial_manifest(
    run: dict,
    scenario: str,
) -> list[dict]:
    scenario = scenario.upper()

    if scenario == "A":
        return []

    if scenario != "B":
        raise ValueError(
            "scenario must be A or B"
        )

    recommendations = list(
        run.get(
            "recommendations",
            [],
        )
    )

    # Only genuine offered rows belong to the
    # initial farmer-response surface.
    offer_rows = [
        rec
        for rec in recommendations
        if _is_offer(rec)
    ]

    # Withdrawal candidates are FARMERS having
    # at least one reference-ACCEPT offer.
    reference_accept_rows = [
        rec
        for rec in offer_rows
        if _effective_initial_response(rec)
        == "ACCEPT"
    ]

    eligible_farmer_ids = sorted({
        str(rec["farmer_id"])
        for rec in reference_accept_rows
    })

    ranked_farmers = sorted(
        eligible_farmer_ids,
        key=lambda farmer_id:
            _farmer_rank_key(
                "initial_farmer_withdrawal",
                farmer_id,
            ),
    )

    n_withdraw_farmers = _quota(
        len(ranked_farmers),
        1,
        40,
    )

    selected_withdrawn_farmers = set(
        ranked_farmers[
            :n_withdraw_farmers
        ]
    )

    farmer_rank = {
        farmer_id: rank
        for rank, farmer_id
        in enumerate(
            ranked_farmers,
            start=1,
        )
    }

    manifest = []

    # Farmer-cycle withdrawal supersedes the
    # row-level reference response for ALL offered
    # rows belonging to the selected farmer.
    for rec in sorted(
        offer_rows,
        key=lambda row: (
            str(row.get("farmer_id")),
            str(row.get("plot_id")),
        ),
    ):
        farmer_id = str(
            rec["farmer_id"]
        )

        if (
            farmer_id
            not in selected_withdrawn_farmers
        ):
            continue

        manifest.append({
            "farmer_id":
                farmer_id,

            "plot_id":
                str(rec["plot_id"]),

            "reference_response":
                _effective_initial_response(
                    rec
                ),

            "reference_crop":
                rec.get("crop"),

            "selection_scope":
                "FARMER_CYCLE",

            "candidate_farmer_count":
                len(ranked_farmers),

            "selected_farmer_quota":
                n_withdraw_farmers,

            "farmer_rank":
                farmer_rank[
                    farmer_id
                ],

            "action":
                "WITHDRAW",
        })

    # REJECT and NO_RESPONSE operate only on
    # remaining reference-ACCEPT offer rows after
    # withdrawn farmers have been removed.
    remaining_accept_rows = [
        rec
        for rec in reference_accept_rows
        if str(rec["farmer_id"])
        not in selected_withdrawn_farmers
    ]

    ranked_rows = sorted(
        remaining_accept_rows,
        key=lambda rec: _rank_key(
            "initial_remaining_offer_action",
            str(rec["farmer_id"]),
            str(rec["plot_id"]),
        ),
    )

    n_remaining = len(
        ranked_rows
    )

    n_reject = _quota(
        n_remaining,
        1,
        10,
    )

    n_no_response = _quota(
        n_remaining,
        1,
        20,
    )

    for rank, rec in enumerate(
        ranked_rows,
        start=1,
    ):
        if rank <= n_reject:
            action = "REJECT"

        elif rank <= (
            n_reject
            + n_no_response
        ):
            action = "NO_RESPONSE"

        else:
            continue

        manifest.append({
            "farmer_id":
                str(rec["farmer_id"]),

            "plot_id":
                str(rec["plot_id"]),

            "reference_response":
                "ACCEPT",

            "reference_crop":
                rec.get("crop"),

            "selection_scope":
                "OFFER_ROW",

            "candidate_count":
                n_remaining,

            "deterministic_rank":
                rank,

            "action":
                action,
        })

    return sorted(
        manifest,
        key=lambda row: (
            row["farmer_id"],
            row["plot_id"],
        ),
    )


def apply_initial_manifest(
    run_id: str,
    manifest: list[dict],
) -> None:
    for row in manifest:
        result = xr.set_response(
            run_id,
            row["farmer_id"],
            row["plot_id"],
            row["action"],
        )

        if not result.get("available"):
            raise RuntimeError(
                "Initial response write failed for "
                f'{row["farmer_id"]}/'
                f'{row["plot_id"]}: '
                f'{result.get("error")}'
            )


def build_renewed_manifest(
    run: dict,
    scenario: str,
) -> list[dict]:
    scenario = scenario.upper()

    if scenario not in ("A", "B"):
        raise ValueError(
            "scenario must be A or B"
        )

    pending = [
        rec
        for rec in run.get(
            "recommendations",
            [],
        )
        if rec.get("changed")
        and rec.get(
            "requires_renewed_consent"
        )
        and rec.get(
            "renewed_response"
        ) is None
    ]

    if scenario == "A":
        ranked = sorted(
            pending,
            key=lambda rec: (
                str(rec["farmer_id"]),
                str(rec["plot_id"]),
            ),
        )

        return [
            {
                "farmer_id":
                    str(rec["farmer_id"]),

                "plot_id":
                    str(rec["plot_id"]),

                "revised_crop":
                    rec.get("revised_crop"),

                "deterministic_rank":
                    rank,

                "candidate_count":
                    len(ranked),

                "decision":
                    "ACCEPT",
            }
            for rank, rec in enumerate(
                ranked,
                start=1,
            )
        ]

    ranked = sorted(
        pending,
        key=lambda rec: _rank_key(
            "renewed",
            str(rec["farmer_id"]),
            str(rec["plot_id"]),
        ),
    )

    n = len(ranked)

    n_reject = _quota(n, 1, 10)
    n_no_response = _quota(
        n,
        1,
        20,
    )

    manifest = []

    for rank, rec in enumerate(
        ranked,
        start=1,
    ):
        if rank <= n_reject:
            decision = "REJECT"
        elif rank <= (
            n_reject
            + n_no_response
        ):
            decision = "NO_RESPONSE"
        else:
            decision = "ACCEPT"

        manifest.append({
            "farmer_id":
                str(rec["farmer_id"]),

            "plot_id":
                str(rec["plot_id"]),

            "revised_crop":
                rec.get("revised_crop"),

            "deterministic_rank":
                rank,

            "candidate_count":
                n,

            "decision":
                decision,
        })

    return sorted(
        manifest,
        key=lambda row: (
            row["farmer_id"],
            row["plot_id"],
        ),
    )


def apply_renewed_manifest(
    run_id: str,
    manifest: list[dict],
) -> None:
    for row in manifest:
        result = (
            xr.record_renewed_consent(
                run_id,
                row["farmer_id"],
                row["plot_id"],
                row["decision"],
            )
        )

        if not result.get("available"):
            raise RuntimeError(
                "Renewed-consent write failed for "
                f'{row["farmer_id"]}/'
                f'{row["plot_id"]}: '
                f'{result.get("error")}'
            )


def _headline(
    analysis: dict,
) -> dict:
    overview = (
        analysis.get("overview") or {}
    )
    fairness = (
        analysis.get("fairness") or {}
    )
    concentration = (
        analysis.get("concentration") or {}
    )

    return {
        "realised_plots":
            overview.get("realised_plots"),

        "not_realised_plots":
            overview.get(
                "not_realised_plots"
            ),

        "farmers_with_realised":
            overview.get(
                "farmers_with_realised"
            ),

        "farmers_without_realised":
            overview.get(
                "farmers_without_realised"
            ),

        "final_plan_projected_cash":
            overview.get(
                "final_realised_cash"
            ),

        "final_realised_area_ha":
            overview.get(
                "final_realised_area"
            ),

        "affirmative_consent_coverage":
            overview.get(
                "affirmative_consent_coverage"
            ),

        "realisation_rate_offered":
            overview.get(
                "realisation_rate_offered"
            ),

        "all_farmer_per_ha_gini":
            fairness.get(
                "all_farmer_per_ha_gini"
            ),

        "all_farmer_abs_cash_gini":
            fairness.get(
                "all_farmer_abs_cash_gini"
            ),

        "participant_only_per_ha_gini":
            fairness.get(
                "participant_only_per_ha_gini"
            ),

        "max_crop_share":
            concentration.get(
                "max_crop_share"
            ),

        "hhi_crop_share":
            concentration.get(
                "hhi_crop_share"
            ),
    }


def _numeric_delta(
    scenario_a: dict,
    scenario_b: dict,
) -> dict:
    delta = {}

    for key in sorted(
        set(scenario_a)
        | set(scenario_b)
    ):
        a = scenario_a.get(key)
        b = scenario_b.get(key)

        if (
            isinstance(a, (int, float))
            and not isinstance(a, bool)
            and isinstance(b, (int, float))
            and not isinstance(b, bool)
        ):
            delta[key] = b - a
        else:
            delta[key] = None

    return delta


def run_scenario(
    pkg,
    scenario: str,
    *,
    source: str = (
        "FarmSync built-in dataset"
    ),
) -> dict:
    scenario = scenario.upper()

    if scenario not in ("A", "B"):
        raise ValueError(
            "scenario must be A or B"
        )

    created = xr.create_run(
        pkg,
        source,
        kind="builtin",
    )

    run_id = created.get("run_id")

    if not run_id:
        raise RuntimeError(
            created.get(
                "error",
                "working-plan creation failed",
            )
        )

    initial_manifest = (
        build_initial_manifest(
            created,
            scenario,
        )
    )

    apply_initial_manifest(
        run_id,
        initial_manifest,
    )

    replanned = xr.replan(run_id)

    if not replanned.get("available"):
        raise RuntimeError(
            replanned.get(
                "error",
                "replan failed",
            )
        )

    after_replan = xr.get_run(
        run_id
    )

    renewed_manifest = (
        build_renewed_manifest(
            after_replan,
            scenario,
        )
    )

    apply_renewed_manifest(
        run_id,
        renewed_manifest,
    )

    finalised = xr.finalise(
        run_id
    )

    if not finalised.get("available"):
        raise RuntimeError(
            finalised.get(
                "error",
                "finalisation failed",
            )
        )

    interactive = (
        xr.run_interactive_analysis(
            run_id
        )
    )

    if not interactive.get("available"):
        raise RuntimeError(
            interactive.get(
                "error",
                "interactive analysis failed",
            )
        )

    final_run = xr.get_run(
        run_id
    )

    analysed = xr.analysis(
        final_run
    )

    if not analysed.get("available"):
        raise RuntimeError(
            analysed.get(
                "reason",
                "analysis unavailable",
            )
        )

    return {
        "protocol_version":
            PROTOCOL_VERSION,

        "scenario":
            scenario,

        "scenario_definition":
            SCENARIO_DEFINITION[
                scenario
            ],

        "run_id":
            run_id,

        "dataset_hash":
            final_run.get(
                "dataset_hash"
            ),

        "final_plan_hash":
            interactive.get(
                "final_plan_hash"
            ),

        "final_plan_revision":
            interactive.get(
                "final_plan_revision"
            ),

        "analysis_bundle_version":
            interactive.get(
                "analysis_bundle_version"
            ),

        "uncertainty_protocol_version":
            interactive.get(
                "uncertainty_protocol_version"
            ),

        "resilience_protocol_version":
            interactive.get(
                "resilience_protocol_version"
            ),

        "initial_manifest":
            initial_manifest,

        "initial_manifest_hash":
            _manifest_hash(
                "initial",
                initial_manifest,
            ),

        "initial_action_counts":
            _counts(
                initial_manifest,
                "action",
            ),

        "withdrawn_farmer_ids":
            _withdrawn_farmer_ids(
                initial_manifest,
            ),

        "withdrawn_farmer_count":
            len(
                _withdrawn_farmer_ids(
                    initial_manifest,
                )
            ),

        "renewed_manifest":
            renewed_manifest,

        "renewed_manifest_hash":
            _manifest_hash(
                "renewed",
                renewed_manifest,
            ),

        "renewed_decision_counts":
            _counts(
                renewed_manifest,
                "decision",
            ),

        "finalisation": {
            "state":
                finalised.get("state"),

            "n_final":
                finalised.get("n_final"),

            "final_plan_projected_cash":
                finalised.get(
                    "final_cash"
                ),

            "consent_coverage_final":
                finalised.get(
                    "consent_coverage_final"
                ),
        },

        "headline":
            _headline(analysed),

        "analysis":
            analysed,
    }


def run_ab(
    pkg,
    *,
    source: str = (
        "FarmSync built-in dataset"
    ),
) -> dict:
    scenario_a = run_scenario(
        pkg,
        "A",
        source=source,
    )

    scenario_b = run_scenario(
        pkg,
        "B",
        source=source,
    )

    if (
        scenario_a["dataset_hash"]
        != scenario_b["dataset_hash"]
    ):
        raise RuntimeError(
            "Scenario A and B dataset hashes differ."
        )

    if (
        scenario_a[
            "uncertainty_protocol_version"
        ]
        != scenario_b[
            "uncertainty_protocol_version"
        ]
    ):
        raise RuntimeError(
            "Scenario A and B uncertainty "
            "protocols differ."
        )

    if (
        scenario_a[
            "resilience_protocol_version"
        ]
        != scenario_b[
            "resilience_protocol_version"
        ]
    ):
        raise RuntimeError(
            "Scenario A and B resilience "
            "protocols differ."
        )

    comparison = {
        "same_dataset": True,

        "dataset_hash":
            scenario_a["dataset_hash"],

        "same_uncertainty_protocol":
            True,

        "same_resilience_protocol":
            True,

        "final_plan_hash_changed":
            (
                scenario_a[
                    "final_plan_hash"
                ]
                != scenario_b[
                    "final_plan_hash"
                ]
            ),

        "scenario_a_final_plan_hash":
            scenario_a[
                "final_plan_hash"
            ],

        "scenario_b_final_plan_hash":
            scenario_b[
                "final_plan_hash"
            ],

        "headline_scenario_a":
            scenario_a["headline"],

        "headline_scenario_b":
            scenario_b["headline"],

        "headline_delta_b_minus_a":
            _numeric_delta(
                scenario_a["headline"],
                scenario_b["headline"],
            ),

        "interpretation_boundary": (
            "Scenario B is a constructed "
            "illustrative behavioural case "
            "study. Differences are conditional "
            "on this frozen action manifest and "
            "are not estimates of empirical "
            "farmer response probabilities."
        ),
    }

    return {
        "protocol_version":
            PROTOCOL_VERSION,

        "scenario_definition":
            SCENARIO_DEFINITION,

        "scenario_a":
            scenario_a,

        "scenario_b":
            scenario_b,

        "comparison":
            comparison,
    }


def write_artifact(
    result: dict,
    path: str | Path,
) -> Path:
    path = Path(path)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return path
