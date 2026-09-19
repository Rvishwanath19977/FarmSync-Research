from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "js" / "farmsync.js"


def _source():
    return JS.read_text(encoding="utf-8")


def _analyse_section():
    s = _source()

    start = s.index(
        "// ============ DYNAMIC ANALYSE"
    )

    end = s.index(
        "/* ================= RESEARCH: DATA / REPRO",
        start,
    )

    return s[start:end]


def test_analysis_view_does_not_auto_run_scientific_engines():
    src = _analyse_section()

    start = src.index(
        "function loadAnalysis()"
    )

    end = src.index(
        "function analyseUnavailable",
        start,
    )

    loader = src[start:end]

    assert "/analysis" in loader
    assert "/run-analysis" not in loader
    assert 'method: "POST"' not in loader


def test_run_analysis_is_explicit_post_action():
    src = _analyse_section()

    assert (
        "/run-analysis"
        in src
    )

    assert (
        '{ method: "POST" }'
        in src
    )

    assert (
        'data-run-analysis="1"'
        in src
    )

    assert "Run Analysis" in src
    assert "Re-run Analysis" in src


def test_analysis_ui_never_renders_raw_json():
    src = _analyse_section()

    assert "JSON.stringify" not in src


def test_uncertainty_ui_preserves_scientific_meaning():
    src = _analyse_section()

    assert "interactive-stress-v1" in src
    assert "UW" in src
    assert "UM" in src
    assert "UR" in src
    assert "W + M + R" in src

    assert (
        "AGMARKNET-arrivals-derived throughput proxy"
        in src
    )

    assert (
        "not empirical demand"
        in src
    )

    assert (
        "This is exposure, not a predicted cash loss."
        in src
    )

    assert (
        "Projected cash is not mechanically scaled"
        in src
    )


def test_resilience_ui_is_immediate_exposure_only():
    src = _analyse_section()

    assert "interactive-resilience-v1" in src

    assert (
        "N&minus;1 producer failure"
        in src
    )

    assert (
        "Hazard-zone outage"
        in src
    )

    assert (
        "Post-shock recovery is not evaluated"
        in src
    )

    assert (
        "No backup plan is generated."
        in src
    )


def test_analysis_ui_exposes_identity_and_staleness():
    src = _analyse_section()

    assert "final-plan hash" in src
    assert "revision" in src
    assert "analysed" in src

    assert (
        "Saved analysis is stale."
        in src
    )

    assert (
        "Old scientific metrics are withheld."
        in src
    )


def test_analysis_ui_uses_projected_not_observed_cash_language():
    src = _analyse_section()

    assert "Final-plan projected cash" in src

    assert (
        "Fairness of projected returns on realised allocations"
        in src
    )

    assert (
        "Projected cash net return per operated hectare"
        in src
    )

    assert (
        "Because cultivation cash costs are held fixed"
        in src
    )

    assert "Protocol representative zone" in src
