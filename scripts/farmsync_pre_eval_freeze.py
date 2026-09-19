#!/usr/bin/env python3
"""FarmSync Phase-3 — Pre-Evaluation Freeze (QA-only; never modifies product/scientific code).

Verification-and-freeze phase that attests the authoritative Phase-1 + Phase-2 PASS state, proves
deterministic repeatability, enforces a PRE->POST zero-drift integrity gate over the full freeze scope,
and seals a SHA-256 integrity manifest (FREEZE.json). It computes no new science.

Subcommands:
  freeze  (default) : discover scope -> PRE hashes -> verify authority -> regressions -> config/seed ->
                      journey x2 -> substantive compare -> 911 reconciliation -> fresh-process solver-free
                      read check -> POST hashes -> PRE/POST zero-drift -> generate FREEZE.json ->
                      verify FREEZE.json -> verdict
  verify            : re-hash the recorded artifact scope against an existing FREEZE.json (added/removed/
                      modified must all be empty)

Methodological boundaries (enforced by omission): no final30, no >=300 benchmark, no live LLM, no PuLP/CBC
on GET/page-load, no dataset/artifact regeneration, no config/seed/hash change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tests"))

FREEZE_DIR = os.path.join(REPO_ROOT, "results", "farmsync", "qa", "pre_eval_freeze")
FREEZE_JSON = os.path.join(FREEZE_DIR, "FREEZE.json")

# Frozen constants that must not change (attested, not modified).
FROZEN_CONSTANTS = {
    "epsilon": 0.95, "lambda": 0.05, "alpha": 0.40,
    "fairness_version": "fairness-v2", "action_policy_version": "action-consent-v1",
    "uncertainty_version": "uncertainty-v1", "instance_hash": "5ea24037c2d9cb6a",
}

# Exclusion globs (prune list): volatile runtime / cache / QA output / freeze self-output.
_EXCLUDE_DIR_PARTS = {"__pycache__", ".pytest_cache", ".cache", "logs", ".git"}
_EXCLUDE_PATH_PREFIXES = [
    os.path.join("results", "farmsync", "qa", "pre_eval_freeze"),   # freeze's own output (no self-hash)
    os.path.join("results", "farmsync", "qa", "browser", "screenshots"),
    os.path.join("results", "farmsync", "qa", "browser", "traces"),
    os.path.join("results", "farmsync", "qa", "browser", "junit"),
    os.path.join("results", "farmsync", "exploratory"),            # working-run state
    os.path.join("data", "farmsync", "snapshots"),                 # runtime snapshots
]
_EXCLUDE_SUFFIXES = (".pyc",)

EXCLUSION_GLOBS = sorted(
    [p.replace("\\", "/") + "/**" for p in _EXCLUDE_PATH_PREFIXES]
    + ["**/%s/**" % d for d in sorted(_EXCLUDE_DIR_PARTS)]
    + ["**/*" + s for s in _EXCLUDE_SUFFIXES]
)


def _rel(p):
    return os.path.relpath(p, REPO_ROOT).replace("\\", "/")


def _excluded(relpath):
    parts = relpath.split("/")
    if any(seg in _EXCLUDE_DIR_PARTS for seg in parts):
        return True
    if relpath.endswith(_EXCLUDE_SUFFIXES):
        return True
    for pre in _EXCLUDE_PATH_PREFIXES:
        pre = pre.replace("\\", "/")
        if relpath == pre or relpath.startswith(pre + "/"):
            return True
    return False


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk_glob(root_rel, exts=None):
    """Return sorted repo-relative file paths under root_rel (a repo-relative dir), honoring exclusions."""
    out = []
    base = os.path.join(REPO_ROOT, root_rel)
    if not os.path.isdir(base):
        return out
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if d not in _EXCLUDE_DIR_PARTS]
        for name in fn:
            rp = _rel(os.path.join(dp, name))
            if _excluded(rp):
                continue
            if exts and not name.endswith(exts):
                continue
            out.append(rp)
    return sorted(out)


def discover_scope():
    """Discover the EXACT freeze scope from defined rules (not hard-coded lists). Returns
    {category: [relpaths...]} with deterministic ordering. Reuses the Phase-1 authoritative
    protected-artifact discovery for frozen scientific artifacts."""
    import farmsync_pre_eval_qa as Q

    scope = {}

    # A. Scientific/engine source — RECURSIVE farmsync/**/*.py (incl. subpackages e.g. farmsync/proposed/)
    scope["scientific_source"] = _walk_glob("farmsync", exts=(".py",))

    # B. Routes / templates / static
    b = [p for p in ["farmsync_routes.py", "templates/farmsync.html",
                     "static/js/farmsync.js", "static/css/farmsync.css"]
         if os.path.exists(os.path.join(REPO_ROOT, p))]
    scope["routes_templates_static"] = sorted(b)

    # C. Scientific/product tests — tests/test_farmsync_*.py EXCEPT the QA-authority tests (-> E)
    qa_authority_tests = {"tests/test_farmsync_qa_backend.py", "tests/test_farmsync_browser.py",
                          "tests/test_farmsync_freeze.py"}
    all_tests = _walk_glob("tests", exts=(".py",))
    scope["scientific_tests"] = sorted(t for t in all_tests
                                       if os.path.basename(t).startswith("test_farmsync_")
                                       and t not in qa_authority_tests)

    # D. Datasets (frozen inputs) — processed + built-in
    scope["datasets"] = sorted(_walk_glob("data/farmsync/processed") + _walk_glob("data/farmsync/builtin"))

    # E. QA authority — Phase-1 + Phase-2 + Phase-3 orchestrators/libs/self-tests (freeze script INCLUDED,
    #    hashed like any other QA-authority source; only its OUTPUT dir is excluded).
    e = [p for p in ["scripts/farmsync_pre_eval_qa.py", "tests/test_farmsync_qa_backend.py",
                     "scripts/farmsync_browser_qa.py", "tests/farmsync_browser_lib.py",
                     "tests/test_farmsync_browser.py",
                     "scripts/farmsync_pre_eval_freeze.py", "tests/test_farmsync_freeze.py"]
         if os.path.exists(os.path.join(REPO_ROOT, p))]
    scope["qa_authority"] = sorted(e)

    # F. Authoritative reports + visual manifest
    f = [p for p in ["results/farmsync/qa/pre_eval/qa_report_backend.json",
                     "results/farmsync/qa/browser/qa_report_browser.json",
                     "results/farmsync/qa/browser/qa_visual_manifest.json"]
         if os.path.exists(os.path.join(REPO_ROOT, p))]
    scope["authoritative_reports"] = sorted(f)

    # G. Seed / RNG manifest
    g = [p for p in ["results/farmsync/audit/replication_seeds.json",
                     "results/farmsync/audit/rng_streams.json"]
         if os.path.exists(os.path.join(REPO_ROOT, p))]
    scope["seed_rng_manifest"] = sorted(g)

    # H. Frozen scientific artifacts — reuse Phase-1 authoritative protected discovery, minus categories
    #    already covered above (datasets/reports/seed) to avoid double-listing.
    protected = set(Q.hash_protected().keys())
    already = set(scope["datasets"]) | set(scope["authoritative_reports"]) | set(scope["seed_rng_manifest"])
    scope["frozen_artifacts"] = sorted(p for p in protected if p not in already and not _excluded(p))

    return scope


def hash_scope(scope):
    """Hash every file in the scope. Returns {relpath: {sha256,size}} sorted, plus per-category rollups."""
    flat = {}
    rollups = {}
    for cat, files in scope.items():
        cat_entries = []
        for rp in files:
            ap = os.path.join(REPO_ROOT, rp)
            if not os.path.exists(ap):
                flat[rp] = {"sha256": None, "size": None, "category": cat, "missing": True}
                cat_entries.append((rp, "MISSING"))
                continue
            sh = _sha(ap)
            flat[rp] = {"sha256": sh, "size": os.path.getsize(ap), "category": cat}
            cat_entries.append((rp, sh))
        # deterministic per-category rollup = sha256 over sorted "relpath:sha" lines
        roll = hashlib.sha256("\n".join("%s:%s" % (r, s) for r, s in sorted(cat_entries)).encode()).hexdigest()
        rollups[cat] = {"file_count": len(files), "rollup_sha256": roll}
    return flat, rollups


def snapshot_hashes(scope):
    """A flat {relpath: sha256} over the whole scope, for PRE/POST comparison."""
    out = {}
    for cat, files in scope.items():
        for rp in files:
            ap = os.path.join(REPO_ROOT, rp)
            out[rp] = _sha(ap) if os.path.exists(ap) else None
    return out


def diff_snapshots(before, after):
    b, a = set(before), set(after)
    return {"added": sorted(a - b), "removed": sorted(b - a),
            "modified": sorted(k for k in (b & a) if before[k] != after[k])}


def _write(name, obj):
    os.makedirs(FREEZE_DIR, exist_ok=True)
    with open(os.path.join(FREEZE_DIR, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")


# ------------------------------------------------------------------ verification steps
def verify_authority(rep):
    """Read + assert the authoritative Phase-1 and Phase-2 reports (no re-run)."""
    p1p = os.path.join(REPO_ROOT, "results/farmsync/qa/pre_eval/qa_report_backend.json")
    p2p = os.path.join(REPO_ROOT, "results/farmsync/qa/browser/qa_report_browser.json")
    out = {"phase1": {}, "phase2": {}}
    ok = True
    try:
        p1 = json.load(open(p1p))
        out["phase1"] = {"phase1_status": p1.get("phase1_status"), "ready_for_phase_2": p1.get("ready_for_phase_2"),
                         "full_suite_coverage": p1.get("full_suite_coverage"),
                         "consent_original_branch": p1.get("categories", {}).get("consent_original_branch", {}).get("status")}
        ok &= p1.get("phase1_status") == "PASS" and p1.get("ready_for_phase_2") == "YES"
        ok &= p1.get("full_suite_coverage") == "YES"
        ok &= out["phase1"]["consent_original_branch"] == "PASS"
    except Exception as e:
        out["phase1"]["error"] = str(e)[:200]; ok = False
    try:
        p2 = json.load(open(p2p))
        engines = set(p2.get("browsers_executed", []))
        cats = p2.get("categories", {})
        allowed = {"PASS", "SEMANTIC_BACKEND_COVERED", "KNOWN_LIMITATION"}
        cat_ok = all(v.get("status") in allowed for v in cats.values())
        out["phase2"] = {"phase2_status": p2.get("phase2_status"), "ready_for_pre_eval_freeze": p2.get("ready_for_pre_eval_freeze"),
                         "browsers_executed": sorted(engines), "defects": p2.get("defects"),
                         "missing_required_categories": p2.get("missing_required_categories"),
                         "all_categories_allowed": cat_ok}
        ok &= p2.get("phase2_status") == "PASS" and p2.get("ready_for_pre_eval_freeze") == "YES"
        ok &= {"chromium", "firefox", "webkit"}.issubset(engines)
        ok &= not p2.get("defects") and not p2.get("missing_required_categories")
        ok &= cat_ok
    except Exception as e:
        out["phase2"]["error"] = str(e)[:200]; ok = False
    rep["authority"] = out
    return ok


def run_regressions(rep):
    suites = {"tests/test_farmsync_qa_backend.py": 19, "tests/test_farmsync_ui.py": 183,
              "tests/test_farmsync_ilp_v2.py": 6, "tests/test_farmsync_browser.py": 43}
    results = {}
    ok = True
    for suite, expected in suites.items():
        # each suite in its own clean-state subprocess
        _clean_runtime()
        proc = subprocess.run([sys.executable, "-m", "pytest", suite, "-q", "-p", "no:cacheprovider"],
                              capture_output=True, text=True, cwd=REPO_ROOT, timeout=600)
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        passed = 0
        for line in reversed(tail):
            m = line.strip()
            if " passed" in m:
                import re
                mm = re.search(r"(\d+) passed", m)
                if mm:
                    passed = int(mm.group(1)); break
        results[suite] = {"expected": expected, "passed": passed, "rc": proc.returncode, "match": passed == expected and proc.returncode == 0}
        ok &= results[suite]["match"]
    # node --check
    try:
        nc = subprocess.run(["node", "--check", os.path.join(REPO_ROOT, "static/js/farmsync.js")],
                            capture_output=True, text=True, timeout=60)
        results["node_check"] = {"rc": nc.returncode, "pass": nc.returncode == 0}
        ok &= nc.returncode == 0
    except Exception as e:
        results["node_check"] = {"error": str(e)[:120], "pass": False}; ok = False
    rep["regressions"] = results
    _write("freeze_regression.json", results)
    return ok


def verify_config_seed(rep):
    import farmsync.config as cfg
    from farmsync.experiment import build_instance, instance_hash
    inst = build_instance(20260812)
    ih = instance_hash(inst["farmers"], inst["plots"])
    got = {"epsilon": cfg.CANONICAL_B3_EPSILON, "lambda": cfg.PUBLICATION_LAMBDA, "alpha": cfg.PUBLICATION_ALPHA,
           "fairness_version": cfg.FAIRNESS_VERSION, "action_policy_version": cfg.ACTION_POLICY_VERSION,
           "uncertainty_version": cfg.UNCERTAINTY_VERSION, "instance_hash": ih}
    seed_path = os.path.join(REPO_ROOT, "results/farmsync/audit/replication_seeds.json")
    seed_sha = _sha(seed_path) if os.path.exists(seed_path) else None
    ok = all(abs(got[k] - FROZEN_CONSTANTS[k]) < 1e-12 if isinstance(FROZEN_CONSTANTS[k], float)
             else got[k] == FROZEN_CONSTANTS[k] for k in FROZEN_CONSTANTS)
    rep["config_seed"] = {"got": got, "expected": FROZEN_CONSTANTS, "match": ok, "replication_seeds_sha256": seed_sha}
    return ok


def _clean_runtime():
    import farmsync_pre_eval_qa as Q
    try:
        Q.snapshot_runtime_state(); Q.clean_state()
    except Exception:
        pass


def clean_journey_x2(rep):
    """Run the Phase-1 deterministic built-in journey twice from clean state; compare substantive summaries."""
    import farmsync_pre_eval_qa as Q
    summaries = []
    for _ in range(2):
        Q.snapshot_runtime_state(); Q.clean_state()
        c = Q.make_client()
        summary, rid = Q.run_full_builtin_journey(c, Q.QA(), {})
        summaries.append(summary)
        Q.clean_state()
    match = summaries[0] is not None and summaries[0] == summaries[1]
    rep["repeatability"] = {"match": bool(match)}
    _write("freeze_repeatability.json", {"run1": summaries[0], "run2": summaries[1], "match": bool(match)})
    return bool(match)


def reconcile_911(rep):
    """Independent 911-plot ledger reconciliation on the frozen built-in run (reuse build_expected_ledger)."""
    import farmsync_pre_eval_qa as Q
    Q.snapshot_runtime_state(); Q.clean_state()
    c = Q.make_client()
    wp = Q.start_builtin(c)
    rid = wp["run_id"]
    run = Q.get_run(c, rid)
    ledger = Q.build_expected_ledger(run)
    ok = len(ledger) == 911
    Q.clean_state()
    rep["reconciliation_911"] = {"ledger_rows": len(ledger), "match": ok}
    return ok


def solver_free_read_fresh_process(rep):
    """§4: verify PuLP/CBC is NOT imported by a GET/page-load path — in a FRESH subprocess (because the
    ILP regression legitimately imports PuLP in this interpreter)."""
    code = r'''
import sys, os
sys.path.insert(0, os.getcwd())
from flask import Flask
import tempfile
d = tempfile.mkdtemp()
# minimal base so the page renders without the site chrome
open(os.path.join(d, "base.html"), "w").write("<!doctype html><html><head><title>{% block title %}{% endblock %}</title></head><body>{% block content %}{% endblock %}{% block scripts %}{% endblock %}</body></html>")
import shutil
shutil.copy(os.path.join("templates", "farmsync.html"), os.path.join(d, "farmsync.html"))
app = Flask(__name__, template_folder=d, static_folder=os.path.join(os.getcwd(), "static"), static_url_path="/static")
app.config["PROPAGATE_EXCEPTIONS"] = False
import farmsync_routes
farmsync_routes.register_farmsync_routes(app)
c = app.test_client()
# READ / page-load / navigation paths only
c.get("/farm-sync")
c.post("/api/farmsync/select-builtin")
wp = c.post("/api/farmsync/working-plan/start").get_json()
rid = wp["run_id"]
c.get("/api/farmsync/working-plan/" + rid)                       # GET run
c.get("/api/farmsync/explore/plots?page=1")                     # explorer read
c.get("/api/farmsync/planning-source")
c.post("/api/farmsync/load-builtin")
c.get("/api/farmsync/inspect/plots?page=1&size=25")
loaded = ("pulp" in sys.modules) or ("cbc" in sys.modules)
print("SOLVER_LOADED=%s" % loaded)
'''
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO_ROOT, timeout=180)
    out = proc.stdout + proc.stderr
    loaded = "SOLVER_LOADED=True" in out
    ran = "SOLVER_LOADED=" in out
    ok = ran and not loaded
    rep["solver_free_read"] = {"fresh_process": True, "ran": ran, "solver_loaded_on_reads": loaded,
                               "rc": proc.returncode, "tail": out.strip().splitlines()[-3:]}
    return ok


# ------------------------------------------------------------------ manifest
def build_manifest(scope, flat, rollups, rep, pre_post_diff):
    core = {
        "manifest_kind": "SHA-256 integrity / freeze manifest (not cryptographically signed)",
        "phase": "pre_evaluation_freeze",
        "frozen_constants": FROZEN_CONSTANTS,
        "replication_seeds_sha256": rep.get("config_seed", {}).get("replication_seeds_sha256"),
        "exclusion_globs": EXCLUSION_GLOBS,
        "category_counts": {k: len(v) for k, v in scope.items()},
        "category_rollups": rollups,
        "artifacts": flat,
        "verdicts": {
            "phase1": rep.get("authority", {}).get("phase1"),
            "phase2": rep.get("authority", {}).get("phase2"),
            "regressions_ok": all(v.get("match", v.get("pass", False)) for v in rep.get("regressions", {}).values()),
            "repeatability_match": rep.get("repeatability", {}).get("match"),
            "reconciliation_911_match": rep.get("reconciliation_911", {}).get("match"),
            "solver_free_read": rep.get("solver_free_read", {}).get("solver_loaded_on_reads") is False,
            "pre_post_zero_drift": (not pre_post_diff["added"] and not pre_post_diff["removed"] and not pre_post_diff["modified"]),
        },
        "philosophy": [
            "The dataset is synthetic.",
            "The current working-plan mechanism is deterministic action-consent + canonical feasibility, NOT the collective MILP.",
            "Uncertainty/resilience are unavailable for the current edited working plan unless explicitly evaluated later.",
            "LLM functionality is NOT yet integrated into the frozen baseline.",
            "This is a pre-evaluation software/reproducibility checkpoint, not final research evidence.",
        ],
        "hashing_note": "Files hashed as raw bytes (no line-ending normalization); a CRLF/LF change is a modification.",
    }
    core_sha = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    manifest = dict(core)
    manifest["manifest_core_sha256"] = core_sha
    # non-hashed metadata (kept out of core so verify never depends on it)
    manifest["_metadata"] = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version.split()[0],
        "note": "_metadata is NOT part of manifest_core_sha256 and is ignored by verify.",
    }
    return manifest, core_sha


def verify_manifest(rep):
    """`verify` subcommand: re-DISCOVER the current in-scope artifact set and compare it against the set
    recorded in FREEZE.json. Re-discovery (not just re-hashing recorded paths) is what lets a newly-added
    in-scope file — e.g. a new farmsync/**/*.py — be detected as `added`. Also recomputes and verifies
    manifest_core_sha256. Verification FAILS if any of added/removed/modified is non-empty."""
    if not os.path.exists(FREEZE_JSON):
        rep["verify"] = {"error": "FREEZE.json not found", "pass": False}
        return False
    man = json.load(open(FREEZE_JSON))
    recorded = man.get("artifacts", {})
    recorded_sha = {rp: v.get("sha256") for rp, v in recorded.items()}

    # (1) re-run discovery on the CURRENT repository; (2) build the current full in-scope set + hashes.
    scope = discover_scope()
    current_sha = snapshot_hashes(scope)          # {relpath: sha256} over freshly-discovered scope

    # (3) compare current discovered set vs recorded manifest set.
    rec_paths, cur_paths = set(recorded_sha), set(current_sha)
    added = sorted(cur_paths - rec_paths)          # in-scope now, absent from the frozen manifest
    removed = sorted(rec_paths - cur_paths)        # frozen but no longer present/in-scope
    modified = sorted(p for p in (rec_paths & cur_paths) if recorded_sha[p] != current_sha[p])
    diff = {"added": added, "removed": removed, "modified": modified}

    # (6) recompute manifest_core_sha256 for tamper-evidence (metadata excluded by construction).
    core = {k: v for k, v in man.items() if k not in ("manifest_core_sha256", "_metadata")}
    recomputed = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    core_ok = recomputed == man.get("manifest_core_sha256")

    # (5) FAIL if any diff array is non-empty (or core sha mismatches).
    ok = (not added and not removed and not modified) and core_ok
    rep["verify"] = {"artifact_diff": diff, "manifest_core_sha256_ok": core_ok,
                     "rediscovered_scope_counts": {k: len(v) for k, v in scope.items()},
                     "recorded_artifact_count": len(recorded_sha),
                     "current_in_scope_count": len(current_sha), "pass": ok}
    _write("freeze_verify.json", rep["verify"])
    return ok


# ------------------------------------------------------------------ main
def cmd_freeze():
    os.makedirs(FREEZE_DIR, exist_ok=True)
    rep = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # 1. discover exact scope
    scope = discover_scope()
    rep["scope_counts"] = {k: len(v) for k, v in scope.items()}

    # 2. PRE hashes (whole scope)
    pre = snapshot_hashes(scope)
    _write("freeze_hashes_before.json", pre)

    # 3-9. verification activity
    checks = {}
    checks["authority"] = verify_authority(rep)
    checks["regressions"] = run_regressions(rep)
    checks["config_seed"] = verify_config_seed(rep)
    checks["repeatability"] = clean_journey_x2(rep)
    checks["reconciliation_911"] = reconcile_911(rep)
    checks["solver_free_read"] = solver_free_read_fresh_process(rep)

    # POST hashes + PRE/POST zero-drift gate
    post = snapshot_hashes(scope)
    _write("freeze_hashes_after.json", post)
    diff = diff_snapshots(pre, post)
    _write("freeze_artifact_diff.json", diff)
    checks["pre_post_zero_drift"] = (not diff["added"] and not diff["removed"] and not diff["modified"])

    # browser-authority safeguard (§5): if any product/scientific or Phase-1/2 QA-authority file changed
    # during this run, the existing Phase-2 report is insufficient.
    guarded = {rp for cat in ("scientific_source", "routes_templates_static", "scientific_tests",
                              "datasets", "frozen_artifacts") for rp in scope.get(cat, [])}
    guarded |= {"scripts/farmsync_pre_eval_qa.py", "tests/test_farmsync_qa_backend.py",
                "scripts/farmsync_browser_qa.py", "tests/farmsync_browser_lib.py", "tests/test_farmsync_browser.py"}
    touched_guarded = [p for p in (diff["added"] + diff["removed"] + diff["modified"]) if p in guarded]
    checks["browser_authority_still_valid"] = (len(touched_guarded) == 0)
    rep["browser_authority_guard"] = {"touched_guarded_files": touched_guarded,
                                      "note": "Creating only Phase-3 freeze script/test/evidence does not invalidate Phase-2."}

    # generate manifest from POST state
    flat, rollups = hash_scope(scope)
    manifest, core_sha = build_manifest(scope, flat, rollups, rep, diff)
    _write("FREEZE.json", manifest)

    # verify the just-written manifest
    checks["manifest_verify"] = verify_manifest(rep)

    all_ok = all(checks.values())
    status = "PASS" if all_ok else "FAIL"
    ready = "YES" if all_ok else "NO"
    rep["checks"] = checks
    rep["freeze_status"] = status
    rep["ready_for_live_llm_integration"] = ready
    rep["manifest_core_sha256"] = core_sha
    _write("freeze_report.json", rep)
    _write_markdown(rep, manifest, checks)

    _print_summary(rep, checks)
    return 0 if all_ok else 1


def _write_markdown(rep, manifest, checks):
    L = ["# FarmSync Phase-3 — Pre-Evaluation Freeze Report", "",
         "Generated: %s" % rep["generated"], "",
         "## Verdict", ""]
    L.append("**PRE-EVALUATION FREEZE STATUS: %s**" % rep["freeze_status"])
    L.append("**READY FOR LIVE LLM INTEGRATION: %s**" % rep["ready_for_live_llm_integration"])
    L += ["", "## Checks", "", "| Check | Result |", "|---|---|"]
    for k, v in checks.items():
        L.append("| %s | %s |" % (k, "PASS" if v else "FAIL"))
    L += ["", "## Scope (discovered, not hard-coded)", "", "| Category | Files | Rollup SHA-256 |", "|---|---|---|"]
    for cat, meta in manifest["category_rollups"].items():
        L.append("| %s | %d | %s |" % (cat, meta["file_count"], meta["rollup_sha256"][:16]))
    L += ["", "manifest_core_sha256: `%s`" % manifest["manifest_core_sha256"], "",
          "## Frozen constants", ""]
    for k, v in manifest["frozen_constants"].items():
        L.append("- %s = %s" % (k, v))
    L += ["- replication_seeds_sha256 = %s" % manifest.get("replication_seeds_sha256"), "",
          "## Freeze philosophy", ""]
    for s in manifest["philosophy"]:
        L.append("- %s" % s)
    L += ["", "## Non-goals (not performed by this freeze)",
          "- No final30, no >=300 LLM benchmark, no live LLM, no publication Results.",
          "- No PuLP/CBC on GET/page-load (verified in a fresh process).",
          "- No dataset / B1-B2-B3 / allocation / feasibility / replanning change; no artifact regeneration.",
          "- ε/λ/α, seeds and instance_hash unchanged."]
    with open(os.path.join(FREEZE_DIR, "FREEZE_REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


def _print_summary(rep, checks):
    print("\nFARMSYNC PHASE-3 — PRE-EVALUATION FREEZE")
    print("=" * 40)
    for k, v in checks.items():
        print("%-32s %s" % (k, "PASS" if v else "FAIL"))
    print("\nPRE-EVALUATION FREEZE STATUS: %s" % rep["freeze_status"])
    print("READY FOR LIVE LLM INTEGRATION: %s" % rep["ready_for_live_llm_integration"])


def cmd_verify():
    rep = {}
    ok = verify_manifest(rep)
    print("FREEZE VERIFY:", "PASS" if ok else "FAIL")
    print(json.dumps(rep.get("verify", {}), indent=2))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", nargs="?", default="freeze", choices=["freeze", "verify"])
    args = ap.parse_args()
    return cmd_freeze() if args.command == "freeze" else cmd_verify()


if __name__ == "__main__":
    sys.exit(main())
