"""Phase-3 freeze self-tests (QA-only): scope discovery, self-hash exclusion, determinism, tamper detection."""
import hashlib
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
sys.path.insert(0, os.path.join(_ROOT, "tests"))

import farmsync_pre_eval_freeze as F


def test_scope_is_recursive_over_farmsync_subpackages():
    scope = F.discover_scope()
    src = scope["scientific_source"]
    # recursion: farmsync/proposed/*.py must be present (not just farmsync/*.py)
    assert any(p.startswith("farmsync/proposed/") and p.endswith(".py") for p in src)
    # discovered count, not hard-coded 27
    assert len(src) >= 40


def test_freeze_output_and_caches_excluded():
    for rp in ("results/farmsync/qa/pre_eval_freeze/FREEZE.json",
               "farmsync/__pycache__/config.cpython-312.pyc",
               "results/farmsync/exploratory/run-x/run.json",
               "data/farmsync/snapshots/x.json"):
        assert F._excluded(rp), "%s should be excluded" % rp


def test_freeze_script_and_test_are_in_qa_authority_scope():
    scope = F.discover_scope()
    assert "scripts/farmsync_pre_eval_freeze.py" in scope["qa_authority"]
    assert "tests/test_farmsync_freeze.py" in scope["qa_authority"]
    # but the freeze OUTPUT dir is excluded
    assert F._excluded("results/farmsync/qa/pre_eval_freeze/FREEZE.json")


def test_qa_authority_tests_not_double_counted_in_scientific_tests():
    scope = F.discover_scope()
    for t in ("tests/test_farmsync_qa_backend.py", "tests/test_farmsync_browser.py", "tests/test_farmsync_freeze.py"):
        assert t not in scope["scientific_tests"]


def test_snapshot_and_diff_detect_modification(tmp_path=None):
    scope = F.discover_scope()
    before = F.snapshot_hashes(scope)
    after = dict(before)
    # simulate a modification
    k = next(iter(after))
    after[k] = "deadbeef"
    d = F.diff_snapshots(before, after)
    assert d["modified"] == [k] and not d["added"] and not d["removed"]


def test_category_rollups_deterministic():
    scope = F.discover_scope()
    _, r1 = F.hash_scope(scope)
    _, r2 = F.hash_scope(scope)
    assert r1 == r2
    for cat, meta in r1.items():
        assert len(meta["rollup_sha256"]) == 64


def test_manifest_core_sha_excludes_metadata_and_self():
    scope = F.discover_scope()
    flat, rollups = F.hash_scope(scope)
    rep = {"authority": {"phase1": {}, "phase2": {}}, "regressions": {}, "repeatability": {"match": True},
           "reconciliation_911": {"match": True}, "solver_free_read": {"solver_loaded_on_reads": False},
           "config_seed": {"replication_seeds_sha256": "x"}}
    diff = {"added": [], "removed": [], "modified": []}
    man, core_sha = F.build_manifest(scope, flat, rollups, rep, diff)
    # recompute core without manifest_core_sha256 / _metadata -> must match
    core = {k: v for k, v in man.items() if k not in ("manifest_core_sha256", "_metadata")}
    recomputed = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    assert recomputed == man["manifest_core_sha256"] == core_sha
    # metadata present but not in core
    assert "_metadata" in man and "generated_at" in man["_metadata"]


def test_frozen_constants_match_expected():
    assert F.FROZEN_CONSTANTS["instance_hash"] == "5ea24037c2d9cb6a"
    assert F.FROZEN_CONSTANTS["epsilon"] == 0.95
    assert F.FROZEN_CONSTANTS["alpha"] == 0.40


# ---------------- verify() re-discovery integrity self-tests ----------------
import shutil as _shutil
import tempfile as _tempfile


def _make_manifest_from_current(tmp_freeze_json):
    """Build a FREEZE.json (into a temp path) from the current repo scope, mirroring build_manifest()."""
    scope = F.discover_scope()
    flat, rollups = F.hash_scope(scope)
    rep = {"authority": {"phase1": {}, "phase2": {}}, "regressions": {},
           "repeatability": {"match": True}, "reconciliation_911": {"match": True},
           "solver_free_read": {"solver_loaded_on_reads": False},
           "config_seed": {"replication_seeds_sha256": "x"}}
    man, _ = F.build_manifest(scope, flat, rollups, rep, {"added": [], "removed": [], "modified": []})
    with open(tmp_freeze_json, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=2, sort_keys=True, ensure_ascii=False)
    return man


def _run_verify_against(freeze_json_path):
    """Point F.FREEZE_JSON at a temp manifest, run verify_manifest, restore. Returns (ok, rep)."""
    orig_json, orig_dir = F.FREEZE_JSON, F.FREEZE_DIR
    tmpdir = _tempfile.mkdtemp(prefix="fsqa_freeze_ev_")
    F.FREEZE_JSON = freeze_json_path
    F.FREEZE_DIR = tmpdir              # redirect evidence write away from the real dir
    try:
        rep = {}
        ok = F.verify_manifest(rep)
        return ok, rep
    finally:
        F.FREEZE_JSON, F.FREEZE_DIR = orig_json, orig_dir
        _shutil.rmtree(tmpdir, ignore_errors=True)


def test_verify_clean_repo_passes():
    tmp = _tempfile.mktemp(suffix=".json")
    _make_manifest_from_current(tmp)
    ok, rep = _run_verify_against(tmp)
    assert ok is True, rep["verify"]["artifact_diff"]
    assert rep["verify"]["manifest_core_sha256_ok"] is True
    os.remove(tmp)


def test_verify_detects_modification():
    tmp = _tempfile.mktemp(suffix=".json")
    man = _make_manifest_from_current(tmp)
    # corrupt one recorded hash so the on-disk file differs from the manifest
    victim = next(p for p in man["artifacts"] if p.startswith("farmsync/"))
    man["artifacts"][victim]["sha256"] = "0" * 64
    # recompute core so the tamper is only in artifacts, not core (isolates the modified-detection path)
    core = {k: v for k, v in man.items() if k not in ("manifest_core_sha256", "_metadata")}
    man["manifest_core_sha256"] = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    json.dump(man, open(tmp, "w"), indent=2, sort_keys=True, ensure_ascii=False)
    ok, rep = _run_verify_against(tmp)
    assert ok is False
    assert victim in rep["verify"]["artifact_diff"]["modified"]
    os.remove(tmp)


def test_verify_detects_deletion():
    tmp = _tempfile.mktemp(suffix=".json")
    man = _make_manifest_from_current(tmp)
    # record a frozen path that does not exist on disk -> must be reported removed
    man["artifacts"]["farmsync/__DELETED_SENTINEL__.py"] = {"sha256": "a" * 64, "size": 1, "category": "scientific_source"}
    core = {k: v for k, v in man.items() if k not in ("manifest_core_sha256", "_metadata")}
    man["manifest_core_sha256"] = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    json.dump(man, open(tmp, "w"), indent=2, sort_keys=True, ensure_ascii=False)
    ok, rep = _run_verify_against(tmp)
    assert ok is False
    assert "farmsync/__DELETED_SENTINEL__.py" in rep["verify"]["artifact_diff"]["removed"]
    os.remove(tmp)


def test_verify_detects_newly_added_inscope_source():
    tmp = _tempfile.mktemp(suffix=".json")
    _make_manifest_from_current(tmp)                 # manifest built BEFORE the new file exists
    new_src = os.path.join(F.REPO_ROOT, "farmsync", "proposed", "__freeze_probe_added__.py")
    try:
        with open(new_src, "w") as fh:
            fh.write("# temporary in-scope probe file for freeze verify test\n")
        ok, rep = _run_verify_against(tmp)           # verify re-discovers scope -> sees the new file
        assert ok is False
        assert "farmsync/proposed/__freeze_probe_added__.py" in rep["verify"]["artifact_diff"]["added"]
    finally:
        if os.path.exists(new_src):
            os.remove(new_src)


def test_verify_ignores_excluded_runtime_file():
    tmp = _tempfile.mktemp(suffix=".json")
    _make_manifest_from_current(tmp)
    # a new EXCLUDED file (freeze output dir / runtime) must NOT invalidate the freeze
    ex_dir = os.path.join(F.REPO_ROOT, "results", "farmsync", "exploratory", "run-probe")
    os.makedirs(ex_dir, exist_ok=True)
    ex_file = os.path.join(ex_dir, "run.json")
    try:
        with open(ex_file, "w") as fh:
            fh.write("{}")
        ok, rep = _run_verify_against(tmp)
        assert ok is True, rep["verify"]["artifact_diff"]
        assert not any("run-probe" in p for p in rep["verify"]["artifact_diff"]["added"])
    finally:
        _shutil.rmtree(ex_dir, ignore_errors=True)
        os.remove(tmp)


def test_verify_ignores_metadata_and_timestamp_differences():
    tmp = _tempfile.mktemp(suffix=".json")
    man = _make_manifest_from_current(tmp)
    # mutate ONLY the non-hashed metadata (timestamp/host) -> must not affect verification
    man["_metadata"]["generated_at"] = "1999-01-01T00:00:00Z"
    man["_metadata"]["python"] = "0.0.0"
    json.dump(man, open(tmp, "w"), indent=2, sort_keys=True, ensure_ascii=False)
    ok, rep = _run_verify_against(tmp)
    assert ok is True
    assert rep["verify"]["manifest_core_sha256_ok"] is True
    os.remove(tmp)


def test_verify_detects_core_sha_tamper():
    tmp = _tempfile.mktemp(suffix=".json")
    man = _make_manifest_from_current(tmp)
    man["manifest_core_sha256"] = "f" * 64          # tampered core digest
    json.dump(man, open(tmp, "w"), indent=2, sort_keys=True, ensure_ascii=False)
    ok, rep = _run_verify_against(tmp)
    assert ok is False
    assert rep["verify"]["manifest_core_sha256_ok"] is False
    os.remove(tmp)
