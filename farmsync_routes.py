"""
FarmSync Flask routes — Dataset Manager.

Wires the dataset-manager engine into the existing AskVish app the same way the
other tools do:  register_farmsync_routes(app)  from app.py.

Routes are thin: all validation/security/versioning lives in farmsync/. State for
the staged (not-yet-activated) dataset is kept in-process, which is appropriate
for a single-user research demonstrator; a note is surfaced in the UI.
"""

from __future__ import annotations

import io
import os
import json
import hashlib

from flask import request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename

from farmsync.build_builtin_dataset import build_builtin_dataset
from farmsync.dataset_manager import (
    package_from_files, validate_package, safe_read_zip, ZipSecurityError,
    dataset_hash, activate_snapshot, SUPPORTED_FILES,
)

_BASE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_BASE, "data", "farmsync")
_BUILTIN_DIR = os.path.join(_DATA_DIR, "builtin")
_SNAPSHOTS_DIR = os.path.join(_DATA_DIR, "snapshots")
_UPLOADS_DIR = os.path.join(_DATA_DIR, "uploads")

_CASE_STUDY_DIR = os.path.join(
    _BASE,
    "results",
    "farmsync",
    "case_study",
    "scenario_ab_v3",
)

_FINAL30_ANALYSIS_DIR = os.path.join(
    _BASE, "results", "farmsync", "final30_analysis_v1"
)
_FINAL30_ANALYSIS_FREEZE_DIR = os.path.join(
    _BASE, "results", "farmsync", "final30_analysis_freeze_v1"
)

MAX_UPLOAD_BYTES = 60 * 1024 * 1024


def _sha256_matches_frozen_text(blob, expected_sha):
    """Verify frozen text while tolerating checkout-only newline conversion.

    Scientific content remains immutable. Only LF / CRLF / CR byte
    representations of the exact same text are accepted.
    """
    if not isinstance(expected_sha, str) or not expected_sha:
        return False

    expected = expected_sha.lower()

    # Canonical newline-neutral representation.
    lf = blob.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    variants = (
        blob,                         # exact bytes
        lf,                           # Unix checkout
        lf.replace(b"\n", b"\r\n"),  # Windows checkout
        lf.replace(b"\n", b"\r"),     # legacy CR representation
    )

    return any(
        hashlib.sha256(candidate).hexdigest() == expected
        for candidate in variants
    )

# In-process staged dataset (single-user research demo).
_state = {"pkg": None, "report": None, "active": None, "active_snapshot": None,
          # explicit planning source — the ONLY thing working-plan/start obeys.
          # None | {"kind":"builtin"} | {"kind":"custom","version":..,"hash":..,"snapshot":{...}}
          "planning_source": None}


def _ensure_dirs():
    for d in (_BUILTIN_DIR, _SNAPSHOTS_DIR, _UPLOADS_DIR):
        os.makedirs(d, exist_ok=True)


def _load_builtin_files():
    """Load built-in CSVs, materializing them on first use if absent."""
    _ensure_dirs()
    if not os.path.exists(os.path.join(_BUILTIN_DIR, "farmers.csv")):
        build_builtin_dataset(_BUILTIN_DIR)
    files = {}
    for name in os.listdir(_BUILTIN_DIR):
        if name in SUPPORTED_FILES:
            with open(os.path.join(_BUILTIN_DIR, name), "rb") as f:
                files[name] = f.read()
    return files


def _package_report(pkg, source, mode="complete"):
    """Build validation + planning-readiness payload WITHOUT mutating global route state.

    This is deliberately pure so Data Explorer can inspect the built-in dataset without staging it,
    changing the active snapshot, or changing planning_source.
    """
    report = validate_package(pkg, mode=mode)
    summ = report.summary()
    present = sorted(pkg.raw_files)
    n_err = len(summ.get("errors") or [])
    n_warn = len(summ.get("warnings") or [])
    file_states = [{"file": f, "uploaded": f in pkg.raw_files,
                    "rows": len(pkg.rows(f)) if pkg.has(f) else 0} for f in present]
    ui_mode = "custom_farmer" if (mode in ("farmer_only", "custom_farmer") or
                                    "custom" in (source or "").lower()) else "complete"
    from farmsync import ui_adapter as _ui2
    plot_cols = list(pkg.rows("plots.csv")[0].keys()) if pkg.has("plots.csv") and pkg.rows("plots.csv") else []
    readiness = _ui2.capability_readiness(
        present,
        "custom_farmer" if ui_mode == "custom_farmer" else "complete_package",
        plot_columns=plot_cols,
    )
    payload = {
        "source": source,
        "mode": ui_mode,
        "validation": summ,
        "passed": bool(summ.get("passed")),
        "n_files": len(present),
        "n_errors": n_err,
        "n_warnings": n_warn,
        "files_present": present,
        "file_states": file_states,
        "row_counts": {f: len(pkg.rows(f)) for f in present if pkg.has(f)},
        "dataset_hash": dataset_hash(pkg),
        "supported_files": SUPPORTED_FILES,
        "readiness": readiness,
    }
    return report, payload


def _stage(pkg, source, mode="complete"):
    """Stage a package for Home's explicit upload/activate flow."""
    report, payload = _package_report(pkg, source, mode=mode)
    _state["pkg"], _state["report"] = pkg, report
    return payload


def _safe_int_arg(name, default, minimum=None, maximum=None):
    """Deterministic, crash-proof coercion of a numeric query-string parameter.
    Malformed / blank / non-integer (incl. '1.5') / missing -> `default`. Values are then clamped to
    [minimum, maximum] when those bounds are given. Never raises, so malformed pagination input can never
    produce an HTTP 500. Pure input-normalisation: no state is touched."""
    raw = request.args.get(name, None)
    if raw is None or raw == "":
        val = default
    else:
        try:
            val = int(raw)
        except (TypeError, ValueError):
            val = default
    if minimum is not None and val < minimum:
        val = minimum
    if maximum is not None and val > maximum:
        val = maximum
    return val


def register_farmsync_routes(app):
    # cap request size for uploads on this app (harmless if already set higher)
    app.config.setdefault("MAX_CONTENT_LENGTH", MAX_UPLOAD_BYTES)

    @app.route("/farm-sync")
    def farmsync_page():
        return render_template("farmsync.html")

    @app.route("/api/farmsync/status")
    def farmsync_status():
        rep = _state["report"]
        return jsonify({
            "has_staged": _state["pkg"] is not None,
            "validation": rep.summary() if rep else None,
            "active": _state["active"],
            "supported_files": SUPPORTED_FILES,
        })

    @app.route("/api/farmsync/load-builtin", methods=["POST"])
    def farmsync_load_builtin():
        pkg = package_from_files(_load_builtin_files(), source="builtin")
        res = _stage(pkg, "Built-in research dataset")
        res["dataset_summary"] = {
            "farmers": len(pkg.rows("farmers.csv")) if pkg.has("farmers.csv") else None,
            "plots": len(pkg.rows("plots.csv")) if pkg.has("plots.csv") else None,
            "collectives": len(pkg.rows("collectives.csv")) if pkg.has("collectives.csv") else None,
        }
        return jsonify(res)

    @app.route("/api/farmsync/upload-package", methods=["POST"])
    def farmsync_upload_package():
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "No file provided."}), 400
        name = secure_filename(f.filename or "")
        if not name.lower().endswith(".zip"):
            return jsonify({"error": "Complete package must be a .zip."}), 400
        data = f.read()
        try:
            files = safe_read_zip(data)
        except ZipSecurityError as e:
            return jsonify({"error": f"ZIP rejected: {e}"}), 400
        if not files:
            return jsonify({"error": "ZIP contained no supported dataset files."}), 400
        _ensure_dirs()
        with open(os.path.join(_UPLOADS_DIR, name), "wb") as out:
            out.write(data)                    # preserve original upload
        pkg = package_from_files(files, source=f"package:{name}")
        return jsonify(_stage(pkg, f"Complete package ({name})"))

    @app.route("/api/farmsync/upload-file", methods=["POST"])
    def farmsync_upload_file():
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "No file provided."}), 400
        name = secure_filename(f.filename or "")
        if name not in SUPPORTED_FILES:
            return jsonify({"error": f"'{name}' is not a supported dataset file."}), 400
        if _state["pkg"] is None:
            _state["pkg"] = package_from_files(_load_builtin_files(), source="builtin+edits")
        _state["pkg"].raw_files[name] = f.read()
        # reparse just this file
        from farmsync.dataset_manager import load_csv_text
        hdr, rows = load_csv_text(_state["pkg"].raw_files[name].decode("utf-8-sig", "replace"))
        _state["pkg"].tables[name] = {"headers": hdr, "rows": rows}
        return jsonify(_stage(_state["pkg"], f"File replaced: {name}"))

    @app.route("/api/farmsync/upload-farmers", methods=["POST"])
    def farmsync_upload_farmers():
        """Custom farmer mode: farmers.csv + plots.csv + collectives.csv are ALL required together.
        Missing any of the three -> 400 with the exact missing filenames. Supporting crops/regions/
        parameters/climate/market/hazard/participation continue to come from built-ins; the three
        farmer/plot/collective files are NOT silently replaced by built-ins."""
        required = ("farmers.csv", "plots.csv", "collectives.csv")
        provided = {}
        for key in required:
            f = request.files.get(key)
            if f:
                data = f.read()
                if data:
                    provided[key] = data
        missing = [k for k in required if k not in provided]
        if missing:
            return jsonify({
                "error": "Custom farmer mode requires all three files together.",
                "missing_files": missing,
                "required_files": list(required),
                "provided_files": sorted(provided.keys()),
            }), 400
        base = _load_builtin_files()
        # general supporting data is reused; plot-keyed files (suitability) are NOT reused because they
        # are keyed to built-in plots and would dangle against custom plots (feasibility is recomputed).
        plot_keyed = {"plot_crop_suitability.csv"}
        supporting = {k: v for k, v in base.items() if k not in required and k not in plot_keyed}
        merged = {**supporting, **provided}
        pkg = package_from_files(merged, source="custom-farmer")
        res = _stage(pkg, "Custom farmer dataset (built-in crops/params reused)", mode="farmer_only")
        res["provided_files"] = sorted(provided.keys())
        res["mode"] = "custom_farmer"
        return jsonify(res)

    @app.route("/api/farmsync/activate", methods=["POST"])
    def farmsync_activate():
        if _state["pkg"] is None or _state["report"] is None:
            return jsonify({"error": "Nothing staged to activate."}), 400
        if not _state["report"].passed:
            return jsonify({"error": "Validation has critical errors; resolve them first."}), 400
        # SERVER-SIDE planning-readiness gate — never trust the browser. A structurally valid but
        # NOT planning-ready dataset must never become the selected planning dataset.
        pkg = _state["pkg"]
        mode = "custom_farmer" if "custom" in (pkg.source or "").lower() else "complete"
        present = sorted(pkg.raw_files)
        plot_cols = list(pkg.rows("plots.csv")[0].keys()) if pkg.has("plots.csv") and pkg.rows("plots.csv") else []
        readiness = _ui.capability_readiness(present, "custom_farmer" if mode == "custom_farmer" else "complete_package", plot_columns=plot_cols)
        if not readiness.get("ready_to_plan"):
            return jsonify({
                "error": "Dataset is not ready to plan.",
                "readiness_error": readiness.get("note"),
                "missing_plot_columns": readiness.get("missing_plot_columns"),
                "missing_capabilities": [k for k, c in (readiness.get("capabilities") or {}).items() if not c.get("ready")],
            }), 400
        _ensure_dirs()
        try:
            manifest = activate_snapshot(_state["pkg"], _state["report"], _SNAPSHOTS_DIR)
        except (FileExistsError, ValueError) as e:
            return jsonify({"error": str(e)}), 400
        _state["active"] = manifest
        version = manifest.get("dataset_version") or manifest.get("version")
        snap = {
            "version": version,
            "hash": manifest.get("dataset_hash"),
            "mode": mode,
            "farmers": [dict(r) for r in pkg.rows("farmers.csv")] if pkg.has("farmers.csv") else [],
            "plots": [dict(r) for r in pkg.rows("plots.csv")] if pkg.has("plots.csv") else [],
            "collectives": [dict(r) for r in pkg.rows("collectives.csv")] if pkg.has("collectives.csv") else [],
        }
        _state["active_snapshot"] = snap
        # EXPLICIT planning source: this exact activated custom version is now the planning dataset.
        _state["planning_source"] = {"kind": "custom", "version": version, "hash": manifest.get("dataset_hash"), "snapshot": snap}
        out = dict(manifest)
        out["version"] = version
        out["mode"] = mode
        out["planning_source"] = "custom"
        out["population"] = {
            "farmers": len(pkg.rows("farmers.csv")) if pkg.has("farmers.csv") else None,
            "plots": len(pkg.rows("plots.csv")) if pkg.has("plots.csv") else None,
            "collectives": len(pkg.rows("collectives.csv")) if pkg.has("collectives.csv") else None,
        }
        return jsonify(out)

    @app.route("/api/farmsync/explore-validation")
    def farmsync_explore_validation():
        """READ-ONLY validation/readiness for the built-in research dataset.

        The package/report are local variables only. This endpoint MUST NOT stage data or mutate
        _state, the active snapshot, planning_source, a working run, or any frozen artifact.
        """
        files = _load_builtin_files()
        pkg = package_from_files(files, source="builtin-explorer-readonly")
        _report, out = _package_report(pkg, "Built-in research dataset", mode="complete")
        out["read_only"] = True
        out["dataset_summary"] = {
            "farmers": len(pkg.rows("farmers.csv")) if pkg.has("farmers.csv") else None,
            "plots": len(pkg.rows("plots.csv")) if pkg.has("plots.csv") else None,
            "collectives": len(pkg.rows("collectives.csv")) if pkg.has("collectives.csv") else None,
        }
        return jsonify(out)

    @app.route("/api/farmsync/explore-tables")
    def farmsync_explore_tables():
        # read-only list of inspectable built-in tables (no staging, no planning mutation)
        files = _load_builtin_files()
        return jsonify({"tables": sorted(k for k in files.keys()),
                        "dataset": "FarmSync research dataset"})

    @app.route("/api/farmsync/explore/<table>")
    def farmsync_explore(table):
        # READ-ONLY inspection of a built-in table. Does NOT touch _state["pkg"], active_snapshot or
        # planning_source — viewing never alters the planning source (§2/§6).
        import csv as _csv
        import io as _io
        fname = table if table.endswith(".csv") else table + ".csv"
        files = _load_builtin_files()
        if fname not in files:
            return jsonify({"error": "'%s' not available." % fname}), 404
        rows = list(_csv.DictReader(_io.StringIO(files[fname].decode("utf-8-sig"))))
        headers = list(rows[0].keys()) if rows else []
        page = _safe_int_arg("page", 1, minimum=1)
        qstr = (request.args.get("q") or "").strip().lower()
        if qstr:
            rows = [r for r in rows if any(qstr in str(v).lower() for v in r.values())]
        per = 25
        total = len(rows)
        start = (page - 1) * per
        return jsonify({"headers": headers, "rows": rows[start:start + per],
                        "page": page, "total": total, "per_page": per})

    @app.route("/api/farmsync/inspect/<table>")
    def farmsync_inspect(table):
        fname = table if table.endswith(".csv") else f"{table}.csv"
        if _state["pkg"] is None or not _state["pkg"].has(fname):
            return jsonify({"error": f"'{fname}' not loaded."}), 404
        q = (request.args.get("q") or "").lower()
        page = _safe_int_arg("page", 1, minimum=1)
        size = _safe_int_arg("size", 25, minimum=1, maximum=100)
        rows = _state["pkg"].rows(fname)
        if q:
            rows = [r for r in rows if any(q in str(v).lower() for v in r.values())]
        total = len(rows)
        start = (page - 1) * size
        page_rows = [{k: v for k, v in r.items() if k != "_line"}
                     for r in rows[start:start + size]]
        return jsonify({
            "table": fname, "headers": _state["pkg"].headers(fname),
            "total": total, "page": page, "size": size, "rows": page_rows,
        })

    @app.route("/api/farmsync/feasibility/<plot_id>")
    def farmsync_feasibility(plot_id):
        """On-demand agronomic feasibility for one plot across all crops."""
        from farmsync.generate import generate_dataset, CROPS
        from farmsync.feasibility import feasible_crops_for_plot, FeasibilityConfig
        climate = request.args.get("climate", "baseline")
        # rebuild the built-in population deterministically to locate the plot
        _, plots, *_ = generate_dataset()
        plot = next((p for p in plots if p.plot_id == plot_id), None)
        if plot is None:
            return jsonify({"error": f"plot '{plot_id}' not found in built-in dataset."}), 404
        cfg = FeasibilityConfig(climate_state=climate)
        results = feasible_crops_for_plot(plot, CROPS, config=cfg)
        return jsonify({
            "plot_id": plot_id, "region_id": plot.region_id,
            "season": plot.active_season.value, "climate_state": climate,
            "crops": {name: {"feasible": r.feasible, "reasons": r.reasons,
                             "binding": r.binding, "checks": r.checks}
                      for name, r in results.items()},
        })

    # --- read-only, artifact-driven research-workbench endpoints ------------------------------
    # None of these invoke the CBC solver, the action-consent pipeline, or any LLM (live or mock).
    from farmsync import ui_adapter as _ui

    @app.route("/api/farmsync/overview")
    def farmsync_overview():
        return jsonify(_ui.overview())

    @app.route("/api/farmsync/planning")
    def farmsync_planning():
        return jsonify(_ui.planning())

    @app.route("/api/farmsync/actions-checkpoint")
    def farmsync_actions_checkpoint():
        return jsonify(_ui.actions_checkpoint())

    @app.route("/api/farmsync/fairness")
    def farmsync_fairness():
        return jsonify(_ui.fairness())

    @app.route("/api/farmsync/concentration")
    def farmsync_concentration():
        return jsonify(_ui.concentration())

    @app.route("/api/farmsync/lambda-frontier")
    def farmsync_lambda_frontier():
        return jsonify(_ui.lambda_frontier())

    @app.route("/api/farmsync/epsilon-frontier")
    def farmsync_epsilon_frontier():
        return jsonify(_ui.epsilon_frontier())

    @app.route("/api/farmsync/uncertainty")
    def farmsync_uncertainty():
        return jsonify(_ui.uncertainty())

    @app.route("/api/farmsync/resilience")
    def farmsync_resilience():
        return jsonify(_ui.resilience())

    @app.route("/api/farmsync/llm-boundary")
    def farmsync_llm_boundary():
        return jsonify(_ui.llm_boundary())

    @app.route("/api/farmsync/reproducibility")
    def farmsync_reproducibility():
        return jsonify(_ui.reproducibility())

    # --- guided-workbench row-level endpoints (read-only; no solver / no LLM) ------------------
    @app.route("/api/farmsync/dataset-summary")
    def farmsync_dataset_summary():
        return jsonify(_ui.dataset_summary())

    @app.route("/api/farmsync/plan")
    def farmsync_plan():
        return jsonify(_ui.plan(request.args.get("method", "B3")))

    @app.route("/api/farmsync/farmers")
    def farmsync_farmers():
        return jsonify(_ui.farmers_list())

    @app.route("/api/farmsync/farmer/<farmer_id>")
    def farmsync_farmer_detail(farmer_id):
        return jsonify(_ui.farmer_detail(farmer_id))

    @app.route("/api/farmsync/data-requirements")
    def farmsync_data_requirements():
        return jsonify(_ui.data_requirements())

    @app.route("/api/farmsync/capability-readiness")
    def farmsync_capability_readiness():
        # advisory only — does not change the scientific validator. Uses the staged package if present,
        # else an explicit ?files=a.csv,b.csv&mode=... for direct inspection/testing.
        mode = request.args.get("mode", "complete_package")
        q = request.args.get("files")
        if q is not None:
            present = [f.strip() for f in q.split(",") if f.strip()]
        elif _state["pkg"] is not None:
            present = sorted(_state["pkg"].raw_files)
            src = (_state["pkg"].source or "")
            if "custom-farmer" in src or "farmer" in src:
                mode = "custom_farmer"
        else:
            present = []
        return jsonify(_ui.capability_readiness(present, mode))

    # --- per-stage canonical read-only endpoints (no solver / no LLM) -------------------------
    @app.route("/api/farmsync/initial-plan")
    def farmsync_initial_plan():
        return jsonify(_ui.initial_plan())

    @app.route("/api/farmsync/farmer-response/<farmer_id>")
    def farmsync_farmer_response(farmer_id):
        res = _ui.farmer_response_detail(farmer_id)
        # single-key form is only unambiguous for single-plot farmers; otherwise ask for the plot_id
        return (jsonify(res), 400) if (not res.get("available") and res.get("state") == "plot_id required") else jsonify(res)

    @app.route("/api/farmsync/farmer-response/<farmer_id>/<plot_id>")
    def farmsync_farmer_response_plot(farmer_id, plot_id):
        res = _ui.farmer_response_detail(farmer_id, plot_id)
        # exact (farmer_id, plot_id) miss is a 404 — never fall back to another plot
        return (jsonify(res), 404) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/replan")
    def farmsync_replan():
        return jsonify(_ui.replan())

    @app.route("/api/farmsync/consent")
    def farmsync_consent():
        return jsonify(_ui.consent())

    @app.route("/api/farmsync/final-plan")
    def farmsync_final_plan():
        return jsonify(_ui.final_plan())

    @app.route("/api/farmsync/final30-results")
    def farmsync_final30_results():
        """Read-only, integrity-checked presentation of the sealed Final30 analysis bundle."""
        paths = {
            "numbers": os.path.join(_FINAL30_ANALYSIS_DIR, "manuscript_inputs", "manuscript_numbers.json"),
            "figures": os.path.join(_FINAL30_ANALYSIS_DIR, "manuscript_inputs", "figure_index.json"),
            "manifest": os.path.join(_FINAL30_ANALYSIS_DIR, "MANIFEST.json"),
            "qa": os.path.join(_FINAL30_ANALYSIS_DIR, "qa", "final_analysis_check.json"),
            "freeze": os.path.join(_FINAL30_ANALYSIS_FREEZE_DIR, "FREEZE.json"),
        }
        if not all(os.path.isfile(p) for p in paths.values()):
            return jsonify({"available": False, "error": "Sealed Final30 analysis bundle is unavailable."}), 404

        try:
            blobs = {}
            docs = {}
            for key, path in paths.items():
                with open(path, "rb") as f:
                    blobs[key] = f.read()
                docs[key] = json.loads(blobs[key].decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            return jsonify({"available": False, "error": "Final30 analysis bundle could not be read.", "detail": str(exc)}), 500

        freeze = docs["freeze"]
        manifest = docs["manifest"]
        qa = docs["qa"]
        actual = {key: hashlib.sha256(blob).hexdigest() for key, blob in blobs.items()}
        checks = {
            "freeze_schema": freeze.get("schema") == "farmsync-final30-analysis-freeze-v1",
            "manifest_schema": manifest.get("schema") == "farmsync-final30-analysis-v1",
            "numbers_schema": docs["numbers"].get("schema") == "farmsync-manuscript-numbers-v1",
            "figure_index_schema": docs["figures"].get("schema") == "farmsync-figure-index-v1",
            "qa_schema": qa.get("schema") == "farmsync-final30-analysis-final-qa-v1",
            "freeze_sealed": freeze.get("status") == "SEALED",
            "manifest_complete": manifest.get("status") == "COMPLETE",
            "final_analysis_qa_pass": qa.get("final_analysis_qa_pass") is True,
            "manifest_sha256": _sha256_matches_frozen_text(blobs["manifest"], freeze.get("analysis_manifest_sha256")),
            "qa_sha256": _sha256_matches_frozen_text(blobs["qa"], freeze.get("final_analysis_qa_sha256")),
            "numbers_sha256": _sha256_matches_frozen_text(blobs["numbers"], freeze.get("manuscript_numbers_sha256")),
            "figure_index_sha256": _sha256_matches_frozen_text(blobs["figures"], freeze.get("figure_index_sha256")),
            "source_commit_match": manifest.get("source_commit") == freeze.get("source_commit"),
            "matrix_sha256_match": manifest.get("matrix_sha256") == freeze.get("matrix_sha256"),
            "raw_cell_count_900": manifest.get("raw_cell_count") == 900,
            "raw_cell_count_freeze_match": manifest.get("raw_cell_count") == freeze.get("raw_cell_count"),
        }
        if not all(checks.values()):
            return jsonify({
                "available": False,
                "error": "Sealed Final30 analysis bundle failed integrity verification.",
                "integrity": {"verified": False, "checks": checks},
            }), 500

        return jsonify({
            "available": True,
            "artifact_kind": "final30_analysis_v1",
            "read_only": True,
            "scientific_recomputation": False,
            "integrity": {"verified": True, "checks": checks, "analysis_set_sha256": freeze.get("analysis_set_sha256")},
            "numbers": docs["numbers"],
            "figures": docs["figures"],
            "manifest": manifest,
            "freeze": freeze,
            "qa": qa,
        })

    @app.route("/api/farmsync/final30-figure/<filename>")
    def farmsync_final30_figure(filename):
        """Serve only hash-verified PNG figures listed in the sealed figure index."""
        if filename != os.path.basename(filename) or not filename.lower().endswith(".png"):
            return jsonify({"error": "Unknown Final30 figure."}), 404
        index_path = os.path.join(_FINAL30_ANALYSIS_DIR, "manuscript_inputs", "figure_index.json")
        freeze_path = os.path.join(_FINAL30_ANALYSIS_FREEZE_DIR, "FREEZE.json")
        try:
            with open(index_path, "rb") as f:
                index_bytes = f.read()
            with open(freeze_path, "r", encoding="utf-8") as f:
                freeze = json.load(f)
            if not _sha256_matches_frozen_text(index_bytes, freeze.get("figure_index_sha256")):
                raise ValueError("figure index hash mismatch")
            index = json.loads(index_bytes.decode("utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            return jsonify({"error": "Final30 figure index failed integrity verification.", "detail": str(exc)}), 500

        entry = next((x for x in index.get("figures", []) if os.path.basename(x.get("png") or "") == filename), None)
        if not entry:
            return jsonify({"error": "Unknown Final30 figure."}), 404
        path = os.path.join(_FINAL30_ANALYSIS_DIR, "figures", filename)
        if not os.path.isfile(path):
            return jsonify({"error": "Final30 figure is unavailable."}), 404
        with open(path, "rb") as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()
        if actual_sha != entry.get("png_sha256"):
            return jsonify({"error": "Final30 figure failed integrity verification."}), 500
        return send_file(path, mimetype="image/png", conditional=True, max_age=3600)

    @app.route("/api/farmsync/scenario-results")
    @app.route("/api/farmsync/publication-results")
    def farmsync_publication_results():
        """
        Read-only presentation endpoint for the committed
        scenario-ab-v3 controlled case-study artifact.

        IMPORTANT:
        - reads frozen files only;
        - does not execute scenario_ab.py;
        - does not invoke a solver;
        - does not invoke an LLM;
        - does not mutate working-plan state.
        """
        summary_path = os.path.join(
            _CASE_STUDY_DIR,
            "scenario_ab_v3_summary.json",
        )

        freeze_path = os.path.join(
            _CASE_STUDY_DIR,
            "FREEZE.json",
        )

        if (
            not os.path.isfile(summary_path)
            or not os.path.isfile(freeze_path)
        ):
            return jsonify({
                "available": False,
                "error": (
                    "Frozen scenario-ab-v3 publication "
                    "artifact is unavailable."
                ),
            }), 404

        try:
            with open(
                freeze_path,
                "r",
                encoding="utf-8",
            ) as f:
                freeze = json.load(f)

            with open(
                summary_path,
                "rb",
            ) as f:
                summary_bytes = f.read()

            summary = json.loads(
                summary_bytes.decode("utf-8")
            )

        except (
            OSError,
            ValueError,
            UnicodeDecodeError,
        ) as exc:
            return jsonify({
                "available": False,
                "error": (
                    "Frozen publication artifact "
                    "could not be read."
                ),
                "detail": str(exc),
            }), 500

        expected_sha = None

        for entry in freeze.get(
            "files",
            [],
        ):
            if (
                entry.get("path")
                == "scenario_ab_v3_summary.json"
            ):
                expected_sha = entry.get(
                    "sha256"
                )
                break

        actual_sha = hashlib.sha256(
            summary_bytes
        ).hexdigest()

        integrity_ok = bool(
            expected_sha
            and _sha256_matches_frozen_text(summary_bytes, expected_sha)
            and freeze.get(
                "protocol_version"
            ) == "scenario-ab-v3"
            and freeze.get(
                "all_verification_checks_pass"
            ) is True
            and summary.get(
                "protocol_version"
            ) == "scenario-ab-v3"
            and summary.get(
                "dataset_hash"
            )
            == freeze.get(
                "dataset_hash"
            )
        )

        if not integrity_ok:
            return jsonify({
                "available": False,
                "error": (
                    "Frozen publication artifact "
                    "failed integrity verification."
                ),
                "integrity": {
                    "summary_sha256_expected":
                        expected_sha,

                    "summary_sha256_actual":
                        actual_sha,

                    "verified":
                        False,
                },
            }), 500

        return jsonify({
            "available": True,

            "artifact_kind":
                "controlled_ab_case_study",

            "read_only":
                True,

            "scientific_recomputation":
                False,

            "summary":
                summary,

            "freeze": {
                "freeze_version":
                    freeze.get(
                        "freeze_version"
                    ),

                "protocol_version":
                    freeze.get(
                        "protocol_version"
                    ),

                "source_commit":
                    freeze.get(
                        "source_commit"
                    ),

                "dataset_hash":
                    freeze.get(
                        "dataset_hash"
                    ),

                "scenario_a_final_plan_hash":
                    freeze.get(
                        "scenario_a_final_plan_hash"
                    ),

                "scenario_b_final_plan_hash":
                    freeze.get(
                        "scenario_b_final_plan_hash"
                    ),

                "all_verification_checks_pass":
                    freeze.get(
                        "all_verification_checks_pass"
                    ),
            },

            "integrity": {
                "summary_sha256":
                    actual_sha,

                "verified":
                    True,
            },
        })

    # --- WORKING PLAN (behind the ONE original workflow; POST-only mutations; GET never solves) ----
    from farmsync import exploratory_run as _xr

    def _start_working_plan():
        # created ONLY by explicit POST; never on GET / page load. It obeys ONLY the explicit
        # planning_source set from Home — never _state["pkg"], a stale active_snapshot, the most
        # recently inspected data, or Data Explorer state.
        src = _state.get("planning_source")
        if not src:
            return {"error": "No planning dataset selected. Choose a dataset on Home first."}, 400
        if src["kind"] == "builtin":
            pkg = package_from_files(_load_builtin_files(), source="builtin")
            res = _xr.create_run(pkg, "FarmSync built-in dataset", kind="builtin")
            return (res, 400) if not res.get("run_id") else (res, 200)
        # custom: use the EXACT activated snapshot recorded on the planning source
        res = _xr.create_run(None, "Custom dataset " + str(src.get("version") or ""),
                             kind="custom", custom_snapshot=src["snapshot"])
        return (res, 400) if not res.get("run_id") else (res, 200)

    @app.route("/api/farmsync/select-builtin", methods=["POST"])
    def farmsync_select_builtin():
        # Home explicitly selects the built-in dataset as the planning source. This OVERRIDES any old
        # custom active_snapshot (which stays stored historically but no longer controls planning).
        _state["planning_source"] = {"kind": "builtin"}
        pkg = package_from_files(_load_builtin_files(), source="builtin")
        summ = {
            "farmers": len(pkg.rows("farmers.csv")) if pkg.has("farmers.csv") else None,
            "plots": len(pkg.rows("plots.csv")) if pkg.has("plots.csv") else None,
            "collectives": len(pkg.rows("collectives.csv")) if pkg.has("collectives.csv") else None,
        }
        return jsonify({"planning_source": "builtin", "dataset_summary": summ})

    @app.route("/api/farmsync/change-dataset", methods=["POST"])
    def farmsync_change_dataset():
        # Home explicitly clears the planning source. Historical snapshots are NOT deleted.
        _state["planning_source"] = None
        _state["pkg"] = None
        _state["report"] = None
        return jsonify({"planning_source": None, "cleared": True})

    @app.route("/api/farmsync/planning-source")
    def farmsync_planning_source():
        src = _state.get("planning_source")
        if not src:
            return jsonify({"planning_source": None})
        return jsonify({"planning_source": src["kind"],
                        "version": src.get("version"), "hash": src.get("hash")})

    @app.route("/api/farmsync/working-plan/start", methods=["POST"])
    def farmsync_wp_start():
        res, code = _start_working_plan()
        return jsonify(res), code

    @app.route("/api/farmsync/working-plan/<run_id>")
    def farmsync_wp_get(run_id):
        res = _xr.get_run(run_id)
        return (jsonify(res), 404) if not res.get("available", True) and res.get("error") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/response", methods=["POST"])
    def farmsync_wp_response(run_id):
        b = request.get_json(silent=True) or {}
        # §10: distinguish "requested_crop omitted" (preserve saved crop) from explicit value/null
        rc = b["requested_crop"] if "requested_crop" in b else _xr._OMITTED
        res = _xr.set_response(run_id, b.get("farmer_id"), b.get("plot_id"), b.get("action"), requested_crop=rc)
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/reset", methods=["POST"])
    def farmsync_wp_reset(run_id):
        b = request.get_json(silent=True) or {}
        res = _xr.reset_response(run_id, b.get("farmer_id"), b.get("plot_id"))
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/reject-candidate", methods=["POST"])
    def farmsync_wp_reject_candidate(run_id):
        b = request.get_json(silent=True) or {}
        res = _xr.reject_alternative(run_id, b.get("farmer_id"), b.get("plot_id"), b.get("crop"))
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/explain", methods=["POST"])
    def farmsync_wp_explain(run_id):
        b = request.get_json(silent=True) or {}
        res = _xr.explain_recommendation(run_id, b.get("farmer_id"), b.get("plot_id"), b.get("crop"), exclude=b.get("exclude"))
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/recommend", methods=["POST"])
    def farmsync_wp_recommend(run_id):
        b = request.get_json(silent=True) or {}
        res = _xr.recommend_alternative(run_id, b.get("farmer_id"), b.get("plot_id"), exclude=b.get("exclude"))
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/validate-crop", methods=["POST"])
    def farmsync_wp_validate_crop(run_id):
        b = request.get_json(silent=True) or {}
        res = _xr.validate_requested_crop(run_id, b.get("farmer_id"), b.get("plot_id"), b.get("requested_crop"))
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/replan", methods=["POST"])
    def farmsync_wp_replan(run_id):
        res = _xr.replan(run_id)
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/analysis")
    def farmsync_wp_analysis(run_id):
        run = _xr.get_run(run_id)
        if not run.get("run_id"):
            return jsonify({"available": False, "reason": "run not found"}), 404
        return jsonify(_xr.analysis(run))

    @app.route(
        "/api/farmsync/working-plan/<run_id>/run-analysis",
        methods=["POST"],
    )
    def farmsync_wp_run_analysis(run_id):
        res = _xr.run_interactive_analysis(run_id)

        if res.get("available"):
            return jsonify(res)

        if res.get("error") == "run not found":
            return jsonify(res), 404

        return jsonify(res), 400

    @app.route("/api/farmsync/working-plan/<run_id>/final-rows")
    def farmsync_wp_final_rows(run_id):
        # read-only paginated Final Plan projection over the FULL selected dataset universe (filtered)
        page = _safe_int_arg("page", 1, minimum=1)
        per = 50
        filt = request.args.get("filter", "realised")
        run = _xr.get_run(run_id)
        if not run.get("run_id"):
            return jsonify({"available": False, "error": "run not found"}), 404
        res = _xr.final_rows(run, page, per, filt=filt)
        return jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/consent-alternative", methods=["POST"])
    def farmsync_wp_consent_alternative(run_id):
        b = request.get_json(silent=True) or {}
        res = _xr.consent_alternative(run_id, b.get("farmer_id"), b.get("plot_id"), exclude=b.get("exclude"))
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/consent", methods=["POST"])
    def farmsync_wp_consent(run_id):
        b = request.get_json(silent=True) or {}
        res = _xr.record_renewed_consent(run_id, b.get("farmer_id"), b.get("plot_id"), b.get("renewed_response"))
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/consent-bulk", methods=["POST"])
    def farmsync_wp_consent_bulk(run_id):
        b = request.get_json(silent=True) or {}
        res = _xr.bulk_renewed_consent(run_id, b.get("decision"))
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/select-recommendation", methods=["POST"])
    def farmsync_wp_select_recommendation(run_id):
        b = request.get_json(silent=True) or {}
        res = _xr.select_revised_recommendation(run_id, b.get("farmer_id"), b.get("plot_id"), b.get("crop"))
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    @app.route("/api/farmsync/working-plan/<run_id>/finalise", methods=["POST"])
    def farmsync_wp_finalise(run_id):
        res = _xr.finalise(run_id)
        return (jsonify(res), 400) if not res.get("available") else jsonify(res)

    # --- AI parse (Development/Mock; no live call). Backend returns the structured interpretation;
    #     the browser never invents crop names or validation verdicts. -----------------------------
    @app.route("/api/farmsync/ai-parse", methods=["POST"])
    def farmsync_ai_parse():
        b = request.get_json(silent=True) or {}
        return jsonify(_ui.ai_parse(b.get("text", ""), b.get("farmer_id"), b.get("plot_id")))

    @app.route("/api/farmsync/ai-status")
    def farmsync_ai_status():
        return jsonify(_ui.ai_status())

    # --- Run-bound AI parse (integration layer). READ-ONLY: parses NL via the mode-selected parser
    #     (off|mock|live; no silent LIVE->MOCK), enforces run + exact farmer/plot binding + identity, and
    #     sources any crop recommendation/feasibility ONLY from deterministic FarmSync. Never mutates
    #     state; the user must still press an explicit save/use control. A live model call happens ONLY on
    #     this explicit POST, never on GET/page-load/navigation. ------------------------------------------
    @app.route("/api/farmsync/working-plan/<run_id>/ai-parse", methods=["POST"])
    def farmsync_wp_ai_parse(run_id):
        from farmsync.proposed import llm_ui_integration as _int
        b = request.get_json(silent=True) or {}
        fid, pid = b.get("farmer_id"), b.get("plot_id")

        def _run_exists(rid):
            return bool(_xr.get_run(rid).get("run_id"))

        def _find_row(rid, f, p):
            run = _xr.get_run(rid)
            return any(r.get("farmer_id") == f and r.get("plot_id") == p for r in run.get("recommendations", []))

        res = _int.ai_parse_run_bound(
            run_id, fid, pid, b.get("text", ""),
            recommend_alternative=_xr.recommend_alternative,
            validate_requested_crop=_xr.validate_requested_crop,
            explain_recommendation=_xr.explain_recommendation,
            find_row=_find_row, run_exists=_run_exists,
            mode=os.environ.get("FARMSYNC_LLM_MODE"),   # None -> resolve_mode() default OFF (no silent Mock)
            allowed_crops=_ui.crop_vocab_list() if hasattr(_ui, "crop_vocab_list") else None,
            current_plot_id=pid,                      # RUN-VALIDATED: bound to the validated farmer/plot pair; ignore body current_plot_id
            exclude=b.get("exclude"))
        code = 200 if res.get("available") else 400
        return jsonify(res), code

    return app