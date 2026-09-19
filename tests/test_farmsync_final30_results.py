import os
import sys

from flask import Flask

from farmsync_routes import register_farmsync_routes


def _client():
    app = Flask(__name__)
    app.config.update(TESTING=True)
    register_farmsync_routes(app)
    return app.test_client()


def test_final30_results_endpoint_is_sealed_read_only_and_verified():
    sys.modules.pop("pulp", None)
    c = _client()
    r = c.get("/api/farmsync/final30-results")
    assert r.status_code == 200
    d = r.get_json()
    assert d["available"] is True
    assert d["read_only"] is True
    assert d["scientific_recomputation"] is False
    assert d["integrity"]["verified"] is True
    assert d["manifest"]["status"] == "COMPLETE"
    assert d["freeze"]["status"] == "SEALED"
    assert d["qa"]["final_analysis_qa_pass"] is True
    assert d["manifest"]["raw_cell_count"] == 900
    assert d["numbers"]["schema"] == "farmsync-manuscript-numbers-v1"
    assert d["freeze"]["analysis_set_sha256"] == "2d5641c4a2e93321707a7f0400d9ad1e61e966bdc31147bb6c591b74f35b1df2"
    assert "pulp" not in sys.modules


def test_final30_results_endpoint_is_get_only():
    assert _client().post("/api/farmsync/final30-results").status_code == 405


def test_final30_figure_is_indexed_and_hash_verified():
    c = _client()
    r = c.get("/api/farmsync/final30-figure/figure_01_primary_workflow_cash.png")
    assert r.status_code == 200
    assert r.mimetype == "image/png"
    assert c.get("/api/farmsync/final30-figure/not-listed.png").status_code == 404


def test_advanced_result_workspaces_are_explicitly_separated_from_interactive_analysis():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html = open(os.path.join(root, "templates", "farmsync.html"), encoding="utf-8").read()
    for ws, label in [
        ("final30", "Final30 Results"),
        ("uncresults", "Uncertainty Results"),
        ("sensitivity", "Sensitivity &amp; Robustness Results"),
        ("scale", "Scalability Results"),
        ("reliability", "Reliability &amp; Statistical Evidence"),
        ("scenario", "Scenario A/B Results"),
        ("repro", "Research details &amp; reproducibility"),
    ]:
        assert f'data-ws="{ws}"' in html
        assert f'id="ws-{ws}"' in html
        assert label in html
    assert 'data-ws="uncertainty">Uncertainty<' in html
    assert 'data-ws="uncresults">Uncertainty Results<' in html


def test_final30_ui_loaders_are_read_only_and_use_sealed_endpoint():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, "static", "js", "farmsync.js"), encoding="utf-8").read()
    assert '"/api/farmsync/final30-results"' in js
    for loader in ("final30", "uncresults", "sensitivity", "scale", "reliability"):
        assert f"loaders.{loader}" in js
    section = js[js.index("let FINAL30_CACHE"):js.index("function pubRow", js.index("let FINAL30_CACHE"))]
    assert 'method: "POST"' not in section
    assert "/run-analysis" not in section
    assert "scientific recomputation" in js.lower()


def test_navigation_scroll_targets_workflow_anchor_not_hero():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, "static", "js", "farmsync.js"), encoding="utf-8").read()
    act = js.split("function activate(ws, options = {})")[1].split("function flashLock")[0]
    assert 'getElementById("fsWorkflow")' in act
    assert 'getElementById("fsApp")' not in act
    assert 'scrollIntoView({ behavior: "auto", block: "start" })' in act



def test_final30_frozen_text_hashes_survive_git_newline_normalization():
    """Git/Render LF checkout must verify against the immutable Windows freeze."""
    import json
    from pathlib import Path
    import farmsync_routes as routes

    analysis = Path(routes._FINAL30_ANALYSIS_DIR)
    freeze_dir = Path(routes._FINAL30_ANALYSIS_FREEZE_DIR)

    freeze = json.loads(
        (freeze_dir / "FREEZE.json").read_text(encoding="utf-8")
    )

    frozen_text = (
        (
            analysis / "MANIFEST.json",
            freeze["analysis_manifest_sha256"],
        ),
        (
            analysis / "qa" / "final_analysis_check.json",
            freeze["final_analysis_qa_sha256"],
        ),
        (
            analysis / "manuscript_inputs" / "manuscript_numbers.json",
            freeze["manuscript_numbers_sha256"],
        ),
        (
            analysis / "manuscript_inputs" / "figure_index.json",
            freeze["figure_index_sha256"],
        ),
    )

    for path, expected in frozen_text:
        raw = path.read_bytes()
        lf_checkout = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

        assert routes._sha256_matches_frozen_text(lf_checkout, expected)

        # A real content mutation must still fail.
        assert not routes._sha256_matches_frozen_text(
            lf_checkout + b" ",
            expected,
        )
