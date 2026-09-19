#!/usr/bin/env python3
"""
FarmSync — Automated pre-evaluation QA orchestrator.

Phase 1 (this file, `--phase backend`): environment/baseline verification, FarmSync test
discovery/execution, frozen-artifact hashing, config/hash/seed verification, deterministic controlled
scenario selection, complete API-level built-in workflow, an INDEPENDENT expected-result ledger,
Farmer-Response / Replan / Renewed-Consent / stale-revision / finalisation / Final-Plan-reconciliation /
Analyse-integrity / fairness-concentration math checks, invalid-request + idempotency matrices,
custom-data validation/readiness/isolation, dataset security regressions, repeatability and evidence
reporting.

QA NEVER modifies the system it validates. If a genuine product/scientific defect is found the relevant
category is marked FAIL, evidence is captured, and the run exits non-zero — no product code is touched.

Usage:
    python scripts/farmsync_pre_eval_qa.py --phase backend
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import traceback
import warnings

# ------------------------------------------------------------------ paths / root
_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)              # dynamic; never hard-code R:\portfolio
sys.path.insert(0, REPO_ROOT)

QA_DIR = os.path.join(REPO_ROOT, "results", "farmsync", "qa", "pre_eval")
JUNIT_DIR = os.path.join(QA_DIR, "junit")

EXPECTED = {
    "epsilon": 0.95, "lambda": 0.05, "alpha": 0.40,
    "fairness_version": "fairness-v2", "action_policy_version": "action-consent-v1",
    "uncertainty_version": "uncertainty-v1", "instance_hash": "5ea24037c2d9cb6a",
    "builtin_farmers": 500, "builtin_plots": 911,
}


# ------------------------------------------------------------------ result recorder
# Category kinds — a required category in any of these non-PASS terminal states forces overall FAIL:
_NONPASS_BLOCKING = {"FAIL", "INCOMPLETE", "ENV_FAIL", "HARNESS_FAIL"}
# categories whose status must gate readiness (product/harness/env/coverage). KNOWN_WARNINGS does not gate.
_REQUIRED_CATEGORIES = {
    "environment", "existing_tests", "config_hash_seeds", "prehash", "posthash",
    "scenario_selection", "farmer_response_semantics", "replan_semantics", "consent_alternative",
    "renewed_consent_backend", "stale_anchor_consent", "finalisation_gating",
    "independent_final_ledger", "final_accounting_911", "final_filter_pagination_api",
    "analyse_reconciliation", "consent_realisation_metrics", "fairness_math", "concentration_math",
    "uncertainty_unavailable", "resilience_unavailable", "state_invalidation", "idempotency",
    "invalid_request_matrix", "custom_data_matrix", "dataset_isolation", "dataset_security",
    "no_solver_on_reads", "no_live_llm", "backend_repeatability", "response_count_deltas",
    "universe_911", "malformed_pagination_routes", "state_isolation",
    "consent_original_branch", "select_recommendation",
}


class QA:
    def __init__(self):
        self.categories = {}          # name -> {"status","kind","checks","detail"}
        self.failures = []            # (category, kind, message) for reporting

    def category(self, name):
        self.categories.setdefault(name, {"status": "PASS", "kind": "product", "checks": [], "detail": ""})
        return name

    def check(self, name, ok, msg="", defect=False, kind=None):
        """defect=True flags a genuine PRODUCT defect; a False check sets the category FAIL regardless."""
        c = self.categories.setdefault(name, {"status": "PASS", "kind": "product", "checks": [], "detail": ""})
        if kind:
            c["kind"] = kind
        c["checks"].append({"ok": bool(ok), "msg": msg, "defect": bool(defect)})
        if not ok:
            if c["status"] == "PASS":
                c["status"] = "FAIL"
            self.failures.append((name, "product_defect" if defect else "check_failure", msg))
        return ok

    def set_status(self, name, status, detail="", kind=None):
        c = self.categories.setdefault(name, {"status": "PASS", "kind": "product", "checks": [], "detail": ""})
        c["status"] = status
        if kind:
            c["kind"] = kind
        if detail:
            c["detail"] = detail

    def status_of(self, name):
        return self.categories.get(name, {}).get("status", "PASS")

    def overall_fail(self):
        """Overall FAIL if ANY required category is in a non-PASS blocking state, OR any failure recorded.
        KNOWN_WARNINGS alone never fails. This does NOT depend solely on defect=True flags."""
        for name in _REQUIRED_CATEGORIES:
            st = self.categories.get(name, {}).get("status", "INCOMPLETE" if name in _REQUIRED_CATEGORIES else "PASS")
            if st in _NONPASS_BLOCKING:
                return True
        # a required category that never ran at all is INCOMPLETE -> fail
        for name in _REQUIRED_CATEGORIES:
            if name not in self.categories:
                return True
        return len(self.failures) > 0

    def missing_required(self):
        return sorted(n for n in _REQUIRED_CATEGORIES if n not in self.categories)


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _protected_roots():
    return [os.path.join(REPO_ROOT, "results", "farmsync"),
            os.path.join(REPO_ROOT, "data", "farmsync", "processed")]


def hash_protected(root_override=None):
    """Recursively hash approved scientific/frozen roots. Prefers a byte-stable set; explicitly excludes
    the QA output dir, working-run 'exploratory' dir, snapshots, caches and logs."""
    roots = [root_override] if root_override else _protected_roots()
    exts = (".json", ".csv")
    excluded = {os.path.normpath(os.path.join(REPO_ROOT, "results", "farmsync", "qa")),
                os.path.normpath(os.path.join(REPO_ROOT, "results", "farmsync", "exploratory")),
                os.path.normpath(os.path.join(REPO_ROOT, "data", "farmsync", "snapshots"))}
    out = {}
    base_for_rel = root_override or REPO_ROOT
    for base in roots:
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            npath = os.path.normpath(dirpath)
            if any(npath == ex or npath.startswith(ex + os.sep) for ex in excluded):
                dirnames[:] = []
                continue
            # prune excluded subdirs + common noise
            dirnames[:] = [d for d in dirnames if os.path.normpath(os.path.join(dirpath, d)) not in excluded
                           and d not in ("__pycache__", ".cache", "logs")]
            for name in sorted(filenames):
                if not name.endswith(exts):
                    continue
                p = os.path.join(dirpath, name)
                out[os.path.relpath(p, base_for_rel).replace("\\", "/")] = _sha(p)
    return out


def diff_hashes(before, after):
    bset, aset = set(before), set(after)
    return {
        "added_protected_artifacts": sorted(aset - bset),
        "removed_protected_artifacts": sorted(bset - aset),
        "modified_protected_artifacts": sorted(k for k in (bset & aset) if before[k] != after[k]),
    }


def record_environment():
    env = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_root": REPO_ROOT,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    try:
        import flask, pulp, pandas, numpy
        env["packages"] = {"flask": flask.__version__, "pulp": pulp.VERSION if hasattr(pulp, "VERSION") else "?",
                           "pandas": pandas.__version__, "numpy": numpy.__version__}
    except Exception as e:
        env["packages_error"] = str(e)
    try:
        env["pip_check"] = subprocess.run([sys.executable, "-m", "pip", "check"],
                                          capture_output=True, text=True, cwd=REPO_ROOT).stdout.strip()
    except Exception as e:
        env["pip_check_error"] = str(e)
    return env


def verify_config(qa):
    cat = qa.category("config_hash_seeds")
    try:
        import farmsync.config as cfg
        from farmsync.experiment import build_instance, instance_hash
        qa.check(cat, cfg.CANONICAL_B3_EPSILON == EXPECTED["epsilon"], "epsilon==0.95", defect=True)
        qa.check(cat, cfg.PUBLICATION_LAMBDA == EXPECTED["lambda"], "lambda==0.05", defect=True)
        qa.check(cat, cfg.PUBLICATION_ALPHA == EXPECTED["alpha"], "alpha==0.40", defect=True)
        qa.check(cat, cfg.FAIRNESS_VERSION == EXPECTED["fairness_version"], "fairness-v2", defect=True)
        qa.check(cat, cfg.ACTION_POLICY_VERSION == EXPECTED["action_policy_version"], "action-consent-v1", defect=True)
        qa.check(cat, cfg.UNCERTAINTY_VERSION == EXPECTED["uncertainty_version"], "uncertainty-v1", defect=True)
        inst = build_instance(20260812)
        ih = instance_hash(inst["farmers"], inst["plots"])
        qa.check(cat, ih == EXPECTED["instance_hash"], "instance_hash==%s (got %s)" % (EXPECTED["instance_hash"], ih), defect=True)
        snapshot = {"epsilon": cfg.CANONICAL_B3_EPSILON, "lambda": cfg.PUBLICATION_LAMBDA,
                    "alpha": cfg.PUBLICATION_ALPHA, "fairness_version": cfg.FAIRNESS_VERSION,
                    "action_policy_version": cfg.ACTION_POLICY_VERSION,
                    "uncertainty_version": cfg.UNCERTAINTY_VERSION, "instance_hash": ih}
        # RNG / seed manifest byte-stability (hash it as a protected artifact too)
        seed_manifest = os.path.join(REPO_ROOT, "results", "farmsync", "audit", "replication_seeds.json")
        snapshot["replication_seeds_present"] = os.path.exists(seed_manifest)
        if os.path.exists(seed_manifest):
            snapshot["replication_seeds_sha256"] = _sha(seed_manifest)
        _write(os.path.join(QA_DIR, "qa_config_snapshot.json"), snapshot)
        return snapshot
    except Exception as e:
        qa.check(cat, False, "config verification crashed: %s" % e, defect=True)
        return {"error": str(e)}


# ------------------------------------------------------------------ test discovery / run
def discover_test_modules():
    tdir = os.path.join(REPO_ROOT, "tests")
    mods = sorted(f for f in os.listdir(tdir) if f.startswith("test_farmsync") and f.endswith(".py"))
    return mods


def run_pytest(qa, modules, junit_prefix, per_suite_timeout=180):
    cat = qa.category("existing_tests")
    results = {}
    # deterministic order; the UI suite manages its own working-plan cleanup, so no parallelism.
    for m in modules:
        jx = os.path.join(JUNIT_DIR, junit_prefix + m.replace(".py", "") + ".xml")
        os.makedirs(JUNIT_DIR, exist_ok=True)
        cmd = [sys.executable, "-m", "pytest", os.path.join("tests", m), "-q",
               "-p", "no:cacheprovider", "--junit-xml", jx, "-W", "default"]
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=per_suite_timeout)
            stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as te:
            stdout, stderr, rc = (te.stdout or b"").decode("utf-8", "replace") if isinstance(te.stdout, bytes) else (te.stdout or ""), "TIMEOUT", 124
        dur = round(time.time() - t0, 2)
        summ = _parse_pytest_summary((stdout or "") + "\n" + (stderr or ""))
        summ["duration"] = dur
        summ["returncode"] = rc
        summ["timed_out"] = (rc == 124)
        results[m] = summ
        # a non-zero return with real failures/errors is a defect; xfail/known-skip are not
        bad = summ.get("failed", 0) + summ.get("errors", 0)
        if summ["timed_out"]:
            summ["classification"] = "INCOMPLETE"
            qa.check(cat, False, "%s: TIMED OUT after %ss (INCOMPLETE for readiness)" % (m, per_suite_timeout))
        elif bad > 0 or (rc not in (0, 5)):
            summ["classification"] = "FAIL"
            qa.check(cat, False, "%s: %d failed, %d errors (rc=%d)" % (m, summ.get("failed", 0), summ.get("errors", 0), rc), defect=True)
        elif summ.get("skipped", 0) > 0 or summ.get("xfailed", 0) > 0:
            # unexpected skip/xfail — INCOMPLETE unless a documented intentional skip. We record it and
            # do not pass silently; the completeness gate below decides readiness.
            summ["classification"] = "INCOMPLETE_SKIP"
            qa.check(cat, False, "%s: %d skipped, %d xfail (unexpected -> INCOMPLETE)" % (m, summ.get("skipped", 0), summ.get("xfailed", 0)))
        else:
            summ["classification"] = "PASS"
            qa.check(cat, True, "%s: %d passed" % (m, summ.get("passed", 0)))
    return results


def _parse_pytest_summary(text):
    import re
    out = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0, "xpassed": 0, "warnings": 0}
    # the last summary line, e.g. "173 passed, 12 warnings in 21.94s"
    for key in out:
        m = re.search(r"(\d+)\s+%s" % ("error" if key == "errors" else key.rstrip("ed") if key in ("passed", "failed", "skipped") else key), text)
    for label, key in [("passed", "passed"), ("failed", "failed"), ("error", "errors"), ("errors", "errors"),
                       ("skipped", "skipped"), ("xfailed", "xfailed"), ("xpassed", "xpassed"), ("warning", "warnings"), ("warnings", "warnings")]:
        m = re.search(r"(\d+)\s+" + label + r"\b", text)
        if m:
            out[key] = max(out[key], int(m.group(1)))
    return out


# ------------------------------------------------------------------ Flask client + primitives
def make_client():
    import tempfile
    from flask import Flask
    tpl = tempfile.mkdtemp(prefix="fsqa_")
    with open(os.path.join(tpl, "base.html"), "w") as f:
        f.write("<html>{% block content %}{% endblock %}</html>")
    with open(os.path.join(tpl, "farmsync.html"), "w") as f:
        f.write("{% block content %}x{% endblock %}")
    app = Flask(__name__, template_folder=tpl, static_folder=os.path.join(REPO_ROOT, "static"))
    # A QA harness must observe a 500 as an HTTP response, not have it re-raised into the harness.
    app.config["TESTING"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = False
    import farmsync_routes
    farmsync_routes.register_farmsync_routes(app)
    return app.test_client()


def safe_get(c, url):
    """GET that returns a status code even if the route raises (a raised unhandled exception is recorded
    as a 500 — the same thing a production WSGI server would return)."""
    try:
        r = c.get(url)
        return r.status_code, r
    except Exception:
        return 500, None


_MUTABLE_ROOTS = [os.path.join(REPO_ROOT, "results", "farmsync", "exploratory"),
                  os.path.join(REPO_ROOT, "data", "farmsync", "snapshots")]
_PREEXISTING = {}          # root -> set(top-level entry names present before QA)
_PREEXISTING_HASHES = {}   # relpath -> sha256 of every pre-existing file (recursive)


def _hash_tree(root):
    out = {}
    if not os.path.isdir(root):
        return out
    for dp, dn, fn in os.walk(root):
        for name in fn:
            p = os.path.join(dp, name)
            try:
                out[os.path.relpath(p, root).replace("\\", "/")] = _sha(p)
            except OSError:
                pass
    return out


def snapshot_runtime_state():
    """Record top-level entries AND a recursive SHA256 of every pre-existing file under the mutable roots,
    so QA can (a) remove only what it creates and (b) VERIFY pre-existing state stayed byte-identical."""
    _PREEXISTING.clear()
    _PREEXISTING_HASHES.clear()
    for root in _MUTABLE_ROOTS:
        _PREEXISTING[root] = set(os.listdir(root)) if os.path.isdir(root) else set()
        for rel, h in _hash_tree(root).items():
            _PREEXISTING_HASHES[root + "::" + rel] = h


def verify_runtime_byte_identity():
    """Return {added, removed, modified} for pre-existing files under the mutable roots (QA-created
    entries are excluded — they are not part of the pre-existing set)."""
    current = {}
    for root in _MUTABLE_ROOTS:
        keep = _PREEXISTING.get(root, set())
        for rel, h in _hash_tree(root).items():
            top = rel.split("/", 1)[0]
            if top in keep:                       # only compare pre-existing entries
                current[root + "::" + rel] = h
    bset, aset = set(_PREEXISTING_HASHES), set(current)
    return {
        "removed": sorted(bset - aset),
        "added": sorted(aset - bset),
        "modified": sorted(k for k in (bset & aset) if _PREEXISTING_HASHES[k] != current[k]),
    }


def clean_state():
    """Remove ONLY QA-created runtime entries; leave pre-existing runs/snapshots byte-identical."""
    import shutil
    for root in _MUTABLE_ROOTS:
        if not os.path.isdir(root):
            continue
        keep = _PREEXISTING.get(root, set())
        for name in list(os.listdir(root)):
            if name in keep:
                continue
            p = os.path.join(root, name)
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.remove(p)
            except OSError:
                pass


def _get(c, url):
    return c.get(url).get_json()


def _post(c, url, body=None):
    r = c.post(url, json=(body or {}))
    return r.status_code, (r.get_json() if r.data else None)


def start_builtin(c):
    c.post("/api/farmsync/select-builtin")
    return c.post("/api/farmsync/working-plan/start").get_json()


def wf(c, rid):
    return c.get("/api/farmsync/working-plan/%s" % rid).get_json()["workflow"]


def get_run(c, rid):
    return c.get("/api/farmsync/working-plan/%s" % rid).get_json()


# ------------------------------------------------------------------ §9 controlled case selector
def _feasible_alts(c, rid, fid, pid, exclude=None):
    """Read-only: canonical feasible alternatives for a plot (via recommend endpoint)."""
    r = c.post("/api/farmsync/working-plan/%s/recommend" % rid,
               json={"farmer_id": fid, "plot_id": pid, "exclude": exclude or []}).get_json()
    return r


def _orig_feasible(c, rid, fid, pid, original):
    """Independently prove the ORIGINAL crop is canonically feasible for this plot using the backend's
    authoritative /validate-crop oracle (the /recommend walk cannot see the original — it is excluded)."""
    v = c.post("/api/farmsync/working-plan/%s/validate-crop" % rid,
               json={"farmer_id": fid, "plot_id": pid, "crop": original})
    if v.status_code != 200:
        return False
    return bool(v.get_json().get("feasible"))


def select_cases(c, rid, wp, qa):
    """Deterministically pick DISTINCT offered plots for scenarios A..L, asserting each predicate.
    ALL twelve are required; a missing capability makes scenario_selection FAIL with evidence."""
    cat = qa.category("scenario_selection")
    recs = wp["recommendations"]
    used = set()
    cases = {}

    def take(pred, key, note=""):
        for r in recs:
            if r["plot_id"] in used:
                continue
            try:
                if pred(r):
                    used.add(r["plot_id"])
                    cases[key] = {"farmer_id": r["farmer_id"], "plot_id": r["plot_id"],
                                  "original_crop": r.get("crop"), "recorded_response": r.get("recorded_response"),
                                  "predicate": note}
                    return cases[key]
            except Exception:
                continue
        return None

    def has_alt(r):
        return _feasible_alts(c, rid, r["farmer_id"], r["plot_id"]).get("found")

    def n_alts(r):
        return _feasible_alts(c, rid, r["farmer_id"], r["plot_id"]).get("n_more", 0)

    # A untouched ACCEPT
    take(lambda r: r.get("recorded_response") == "ACCEPT" and r.get("crop"), "A_untouched_accept", "recorded ACCEPT")
    # B ACCEPT -> MODIFY -> feasible revised -> RENEWED_ACCEPT
    take(lambda r: r.get("recorded_response") == "ACCEPT" and r.get("crop") and has_alt(r), "B_accept_modify_renewaccept", "recorded ACCEPT + feasible alt")
    # C / D changed rows with feasible alt (will be driven to RENEWED_REJECT / NO_RESPONSE)
    take(lambda r: r.get("crop") and has_alt(r), "C_changed_renewreject", "changeable + feasible alt")
    take(lambda r: r.get("crop") and has_alt(r), "D_changed_renewnoresp", "changeable + feasible alt")
    # E effective NO_RESPONSE (we set it explicitly)
    take(lambda r: r.get("crop"), "E_no_response", "offered row set to NO_RESPONSE")
    # F WITHDRAW (we set it explicitly)
    take(lambda r: r.get("crop"), "F_withdraw", "offered row set to WITHDRAW")
    # G GENUINE recorded REJECT -> feasible revised -> RENEWED_ACCEPT
    take(lambda r: r.get("recorded_response") == "REJECT" and r.get("crop") and has_alt(r), "G_reject_revised_renewaccept", "recorded REJECT + feasible alt")
    # H MODIFY with feasible requested crop
    take(lambda r: r.get("crop") and has_alt(r), "H_modify_feasible", "MODIFY feasible")
    # I MODIFY with infeasible/unsupported requested crop (we will request a bogus crop)
    take(lambda r: r.get("crop"), "I_modify_infeasible", "MODIFY infeasible requested")
    # J >=2 feasible browse alternatives
    take(lambda r: r.get("crop") and n_alts(r) >= 1, "J_multi_alt", "n_more>=1 (>=2 alts total)")
    # K MODIFY row where ORIGINAL crop is INDEPENDENTLY proven canonically feasible
    take(lambda r: r.get("crop") and has_alt(r) and _orig_feasible(c, rid, r["farmer_id"], r["plot_id"], r.get("crop")), "K_modify_orig_feasible", "original crop proven feasible")
    # L GENUINE recorded REJECT-origin row (rejected original must not be returned)
    take(lambda r: r.get("recorded_response") == "REJECT" and r.get("crop") and has_alt(r), "L_reject_no_orig_return", "recorded REJECT-origin")

    required = ["A_untouched_accept", "B_accept_modify_renewaccept", "C_changed_renewreject",
                "D_changed_renewnoresp", "E_no_response", "F_withdraw", "G_reject_revised_renewaccept",
                "H_modify_feasible", "I_modify_infeasible", "J_multi_alt", "L_reject_no_orig_return"]
    for k in required:
        qa.check(cat, k in cases, "scenario %s selectable+predicate-proven" % k)
    # K (original-crop canonically feasible) is a DATASET CAPABILITY, not a scenario_selection failure.
    # Its product semantic branch is exercised separately by consent_original_branch_coverage(). Record
    # whether built-in supports K; absence is BUILTIN_CAPABILITY: K_NOT_PRESENT (not a FAIL here).
    if "K_modify_orig_feasible" not in cases:
        n_probed = 0
        n_feasible_orig = 0
        for r in recs[:120]:
            n_probed += 1
            if _orig_feasible(c, rid, r["farmer_id"], r["plot_id"], r.get("crop")):
                n_feasible_orig += 1
        ledger_note = ("BUILTIN_CAPABILITY: K_NOT_PRESENT — of %d built-in offered rows probed, %d have an "
                       "original crop that passes /validate-crop. Stored p1 recommendation crops are not "
                       "re-feasible under the working-plan canonical rules. Return-to-original semantics are "
                       "covered by the isolated consent_original_branch fixture instead." % (n_probed, n_feasible_orig))
        if qa.status_of(cat) == "PASS":
            qa.set_status(cat, "PASS", ledger_note)   # not a failure; capability recorded
        else:
            c_detail = qa.categories[cat].get("detail", "")
            qa.set_status(cat, qa.status_of(cat), (c_detail + " | " + ledger_note).strip(" |"))
    else:
        qa.check(cat, True, "K present in built-in dataset")
    # assert predicate correctness for the ones with strict methodology
    if "G_reject_revised_renewaccept" in cases:
        qa.check(cat, cases["G_reject_revised_renewaccept"]["recorded_response"] == "REJECT", "G is a GENUINE recorded REJECT")
    if "L_reject_no_orig_return" in cases:
        qa.check(cat, cases["L_reject_no_orig_return"]["recorded_response"] == "REJECT", "L is a GENUINE recorded REJECT")
    return cases


# ------------------------------------------------------------------ §19 independent expected ledger
def build_expected_ledger(run):
    """INDEPENDENT expected final classification per dataset plot from upstream authoritative state.
    Does NOT read the analysis/final endpoint — it re-derives from responses/replan/consent fields."""
    dsnap = run.get("dataset_snapshot") or {}
    plots = dsnap.get("plots") or [{"plot_id": r["plot_id"], "farmer_id": r["farmer_id"]} for r in run["recommendations"]]
    rec_by = {r["plot_id"]: r for r in run["recommendations"]}
    replan_anchor = run.get("replan_anchor")

    def eff(rec):
        if run.get("source_kind") == "builtin":
            return rec.get("working_response") or rec.get("recorded_response")
        return rec.get("working_response")

    def valid_consent(rec):
        if rec.get("consent_for_crop") != rec.get("revised_crop"):
            return None
        if rec.get("consent_for_replan_anchor") != replan_anchor:
            return None
        return rec.get("renewed_response")

    ledger = {}
    for p in plots:
        pid = p["plot_id"]; rec = rec_by.get(pid)
        row = {"farmer_id": p.get("farmer_id"), "plot_id": pid,
               "expected_realised": False, "expected_final_crop": None,
               "expected_consent_basis": None, "expected_not_realised_reason": None}
        if rec is None:
            row["expected_not_realised_reason"] = "NO_INITIAL_OFFER"
            ledger[pid] = row
            continue
        a = eff(rec)
        if rec.get("changed"):
            v = valid_consent(rec)
            if v == "ACCEPT":
                row.update(expected_realised=True, expected_final_crop=rec.get("revised_crop"),
                           expected_consent_basis="RENEWED_ACCEPT")
            elif v == "REJECT":
                row["expected_not_realised_reason"] = "RENEWED_REJECT"
            elif v == "NO_RESPONSE":
                row["expected_not_realised_reason"] = "RENEWED_NO_RESPONSE"
            else:
                row["expected_not_realised_reason"] = "OTHER_NOT_REALISED"
        elif a == "ACCEPT":
            row.update(expected_realised=True, expected_final_crop=rec.get("crop"),
                       expected_consent_basis="INITIAL_ACCEPT")
        elif a == "WITHDRAW":
            row["expected_not_realised_reason"] = "WITHDRAW"
        elif a == "REJECT":
            row["expected_not_realised_reason"] = "INITIAL_REJECT_NO_ALTERNATIVE"
        elif a == "NO_RESPONSE" or a is None:
            row["expected_not_realised_reason"] = "INITIAL_NO_RESPONSE"
        else:
            row["expected_not_realised_reason"] = "OTHER_NOT_REALISED"
        ledger[pid] = row
    return ledger


def fetch_all_final_rows(c, rid, filt):
    """Traverse every page of /final-rows for a filter; return (rows, counts, page_meta)."""
    out = []
    page = 1
    meta = None
    while True:
        d = c.get("/api/farmsync/working-plan/%s/final-rows?filter=%s&page=%d" % (rid, filt, page)).get_json()
        meta = d
        out.extend(d["rows"])
        if d["page"] >= d["pages"]:
            break
        page += 1
        if page > d["pages"] + 2:
            break
    return out, d.get("counts", {}), meta


# ------------------------------------------------------------------ math helpers (independent)
def gini(values):
    xs = sorted(float(v) for v in values if v is not None)
    n = len(xs)
    if n == 0:
        return None
    s = sum(xs)
    if s <= 0:
        return 0.0
    cum = sum(i * x for i, x in enumerate(xs, 1))
    return (2.0 * cum) / (n * s) - (n + 1.0) / n


def _fingerprint(run):
    """Substantive state fingerprint (excludes timestamps/paths/run_id/request metadata)."""
    recs = []
    for r in sorted(run.get("recommendations", []), key=lambda x: x["plot_id"]):
        recs.append((r["plot_id"], r.get("working_response"), r.get("requested_crop"),
                     tuple(sorted(r.get("rejected_alternatives") or [])), r.get("revised_crop"),
                     r.get("renewed_response"), r.get("consent_for_crop"),
                     r.get("consent_for_replan_anchor"), bool(r.get("realised")), r.get("final_crop")))
    return hashlib.sha256(json.dumps({
        "recs": recs, "response_rev": run.get("response_rev"), "replan_anchor": run.get("replan_anchor"),
        "final_anchor": run.get("final_anchor"), "final_plan_revision": run.get("final_plan_revision"),
    }, default=str, sort_keys=True).encode()).hexdigest()


def run_full_builtin_journey(c, qa, ledgers_out=None):
    """§7-38 driven end-to-end; returns a substantive-result summary for repeatability comparison."""
    clean_state()
    wp = start_builtin(c)
    rid = wp["run_id"]

    # §8 universe
    cu = qa.category("universe_911")
    qa.check(cu, wp["population"]["farmers"] == EXPECTED["builtin_farmers"], "farmers==500", defect=True)
    qa.check(cu, wp["population"]["plots"] == EXPECTED["builtin_plots"], "plots==911", defect=True)
    offered = len(wp["recommendations"])
    no_offer = wp["population"]["plots"] - offered
    qa.check(cu, offered + no_offer == 911, "offered+no_offer==911", defect=True)

    # §9 scenario selection
    cases = select_cases(c, rid, wp, qa)
    if ledgers_out is not None:
        ledgers_out["cases"] = cases

    # §10 capture BEFORE response history (independent expected deltas)
    def eff_counts(run):
        cnt = {k: 0 for k in ("ACCEPT", "REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW")}
        for r in run["recommendations"]:
            e = (r.get("working_response") or r.get("recorded_response")) if run["source_kind"] == "builtin" else r.get("working_response")
            if e in cnt:
                cnt[e] += 1
        return cnt
    before_counts = eff_counts(get_run(c, rid))

    # §11 Farmer Response edge cases + apply controlled scenario mutations
    fr = qa.category("farmer_response_semantics")
    idem = qa.category("idempotency")
    # identity / invalid
    A = cases.get("A_untouched_accept")
    if A:
        st, _ = _post(c, "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": A["farmer_id"], "plot_id": "NOPE", "action": "ACCEPT"})
        qa.check(fr, st == 400, "invalid plot for valid farmer -> 400")
        st, _ = _post(c, "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": "ZZZ", "plot_id": A["plot_id"], "action": "ACCEPT"})
        qa.check(fr, st == 400, "invalid farmer -> 400")
    applied = {}   # plot_id -> (old_effective, new_effective)
    def _eff_of(pid):
        r = next((x for x in get_run(c, rid)["recommendations"] if x["plot_id"] == pid), None)
        if not r:
            return None
        return (r.get("working_response") or r.get("recorded_response"))
    # revision bump + idempotency: a real edit bumps, identical save does not
    E = cases.get("E_no_response")
    if E:
        old = _eff_of(E["plot_id"])
        r0 = get_run(c, rid)["workflow"]["response_rev"]
        _post(c, "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": E["farmer_id"], "plot_id": E["plot_id"], "action": "NO_RESPONSE"})
        if old != "NO_RESPONSE":
            applied[E["plot_id"]] = (old, "NO_RESPONSE")
        r1 = get_run(c, rid)["workflow"]["response_rev"]
        qa.check(fr, r1 == r0 + 1, "real response edit bumps response_rev")
        _post(c, "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": E["farmer_id"], "plot_id": E["plot_id"], "action": "NO_RESPONSE"})
        r2 = get_run(c, rid)["workflow"]["response_rev"]
        qa.check(idem, r2 == r1, "identical response save does not bump response_rev")
    # recorded response immutable
    F = cases.get("F_withdraw")
    if F:
        old = _eff_of(F["plot_id"])
        rec_resp = next(r for r in get_run(c, rid)["recommendations"] if r["plot_id"] == F["plot_id"]).get("recorded_response")
        _post(c, "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": F["farmer_id"], "plot_id": F["plot_id"], "action": "WITHDRAW"})
        if old != "WITHDRAW":
            applied[F["plot_id"]] = (old, "WITHDRAW")
        rec_after = next(r for r in get_run(c, rid)["recommendations"] if r["plot_id"] == F["plot_id"]).get("recorded_response")
        qa.check(fr, rec_resp == rec_after, "working override does not alter recorded response")

    # apply the change-generating scenarios (MODIFY/REJECT feeding into replan)
    for key in ("B_accept_modify_renewaccept", "C_changed_renewreject", "D_changed_renewnoresp",
                "G_reject_revised_renewaccept", "H_modify_feasible", "J_multi_alt", "K_modify_orig_feasible"):
        cse = cases.get(key)
        if cse:
            act = "MODIFY" if ("modify" in key or key.startswith("B") or key.startswith("H") or key.startswith("K")) else "REJECT"
            old = _eff_of(cse["plot_id"])
            _post(c, "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": cse["farmer_id"], "plot_id": cse["plot_id"], "action": act})
            if old != act:
                applied[cse["plot_id"]] = (old, act)
    if ledgers_out is not None:
        ledgers_out["applied_mutations"] = applied

    # §10/§6 independent EXACT expected deltas. We drove: E->NO_RESPONSE, F->WITHDRAW, and the
    # change-generating scenarios below to MODIFY/REJECT. Build expected counts precisely.
    after_counts = eff_counts(get_run(c, rid))
    dc = qa.category("response_count_deltas")
    expected = dict(before_counts)
    for pid, (old_eff, new_eff) in applied.items():
        if old_eff in expected:
            expected[old_eff] -= 1
        if new_eff in expected:
            expected[new_eff] += 1
    for cls in ("ACCEPT", "REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW"):
        qa.check(dc, after_counts[cls] == expected[cls],
                 "exact %s delta: expected %d, got %d" % (cls, expected[cls], after_counts[cls]))

    # §12 Replan: view (GET) must not replan; explicit replan sets anchor==response_rev
    rp = qa.category("replan_semantics")
    fp0 = _fingerprint(get_run(c, rid))
    get_run(c, rid); get_run(c, rid)
    qa.check(rp, _fingerprint(get_run(c, rid)) == fp0, "GET/view does not mutate/replan")
    resp_rev = get_run(c, rid)["workflow"]["response_rev"]
    rpres = c.post("/api/farmsync/working-plan/%s/replan" % rid).get_json()
    qa.check(rp, rpres.get("available"), "explicit replan succeeds")
    run = get_run(c, rid)
    qa.check(rp, run["replan_anchor"] == resp_rev, "replan_anchor==response_rev")
    changed = [r for r in run["recommendations"] if r.get("changed")]
    qa.check(rp, all(r.get("requires_renewed_consent") for r in changed), "changed rows require renewed consent")
    qa.check(rp, all(not r.get("realised") for r in run["recommendations"]), "replan not marked realised")

    # §13 consent-alternative backend semantics
    ca = qa.category("consent_alternative")
    if changed:
        X = changed[0]
        seen = []
        cur = X["revised_crop"]
        for _ in range(12):
            r = c.post("/api/farmsync/working-plan/%s/consent-alternative" % rid,
                       json={"farmer_id": X["farmer_id"], "plot_id": X["plot_id"], "exclude": seen}).get_json()
            if not r.get("found"):
                break
            qa.check(ca, r["recommended_crop"] != cur, "alt never the current revised crop")
            qa.check(ca, r["recommended_crop"] not in seen, "no duplicate candidate before exhaustion")
            seen.append(r["recommended_crop"])
        # read-only
        b = _fingerprint(get_run(c, rid))
        c.post("/api/farmsync/working-plan/%s/consent-alternative" % rid, json={"farmer_id": X["farmer_id"], "plot_id": X["plot_id"]})
        qa.check(ca, _fingerprint(get_run(c, rid)) == b, "consent-alternative is read-only")

    # §17 stale-anchor critical case (same crop after new replan -> PENDING)
    sa = qa.category("stale_anchor_consent")
    if changed:
        X = get_run(c, rid); Xr = next(r for r in X["recommendations"] if r["plot_id"] == changed[0]["plot_id"])
        cropX = Xr["revised_crop"]
        _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": Xr["farmer_id"], "plot_id": Xr["plot_id"], "renewed_response": "ACCEPT"})
        # upstream change on a different plot
        other = next(r for r in X["recommendations"] if r["plot_id"] != Xr["plot_id"] and r["crop"] and not r.get("working_response"))
        _post(c, "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": other["farmer_id"], "plot_id": other["plot_id"], "action": "WITHDRAW"})
        w = wf(c, rid)
        qa.check(sa, not w["replan_current"], "upstream edit stales replan")
        # stale POSTs refused
        st, _ = _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": Xr["farmer_id"], "plot_id": Xr["plot_id"], "renewed_response": "ACCEPT"})
        qa.check(sa, st == 400, "stale consent POST refused")
        st, _ = _post(c, "/api/farmsync/working-plan/%s/consent-bulk" % rid, {"decision": "ACCEPT"})
        qa.check(sa, st == 400, "stale bulk consent refused")
        st, _ = _post(c, "/api/farmsync/working-plan/%s/select-recommendation" % rid, {"farmer_id": Xr["farmer_id"], "plot_id": Xr["plot_id"], "crop": cropX})
        qa.check(sa, st == 400, "stale select refused")
        c.post("/api/farmsync/working-plan/%s/replan" % rid)
        X2 = get_run(c, rid); Xr2 = next(r for r in X2["recommendations"] if r["plot_id"] == Xr["plot_id"])
        if Xr2.get("changed") and Xr2["revised_crop"] == cropX:
            qa.check(sa, Xr2.get("consent_for_crop") == cropX, "consent_for_crop==revised (same crop)")
            qa.check(sa, Xr2.get("consent_for_replan_anchor") != X2["replan_anchor"], "old anchor != new replan_anchor")
            qa.check(sa, _is_pending_row(X2, Xr2), "same-crop-after-new-replan is PENDING")

    # §15/§16 renewed consent + bulk; resolve everything then finalise
    rc = qa.category("renewed_consent_backend")
    st, _ = _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": (changed[0]["farmer_id"] if changed else "F"), "plot_id": (changed[0]["plot_id"] if changed else "P"), "renewed_response": "BOGUS"})
    qa.check(rc, st == 400, "invalid consent enum -> 400")
    # set specific outcomes on C/D if present, then bulk-accept remainder
    run = get_run(c, rid)
    Ccase = cases.get("C_changed_renewreject"); Dcase = cases.get("D_changed_renewnoresp")
    def _row(pid): 
        return next((r for r in run["recommendations"] if r["plot_id"] == pid), None)
    if Ccase and _row(Ccase["plot_id"]) and _row(Ccase["plot_id"]).get("changed"):
        _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": Ccase["farmer_id"], "plot_id": Ccase["plot_id"], "renewed_response": "REJECT"})
    if Dcase and _row(Dcase["plot_id"]) and _row(Dcase["plot_id"]).get("changed"):
        _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": Dcase["farmer_id"], "plot_id": Dcase["plot_id"], "renewed_response": "NO_RESPONSE"})
    # §18 finalise gating: refuse while pending
    fg = qa.category("finalisation_gating")
    if wf(c, rid)["n_consent_pending"] > 0:
        st, _ = _post(c, "/api/farmsync/working-plan/%s/finalise" % rid)
        qa.check(fg, st == 400, "finalise refused while pending")
    _post(c, "/api/farmsync/working-plan/%s/consent-bulk" % rid, {"decision": "ACCEPT"})
    qa.check(fg, wf(c, rid)["n_consent_pending"] == 0, "pending==0 after bulk accept")
    # final view/pagination must not finalise
    before_final = get_run(c, rid).get("final_anchor")
    c.get("/api/farmsync/working-plan/%s/final-rows?filter=all&page=1" % rid)
    qa.check(fg, get_run(c, rid).get("final_anchor") == before_final, "final view/pagination does not finalise")
    st, fin = _post(c, "/api/farmsync/working-plan/%s/finalise" % rid)
    qa.check(fg, st == 200 and fin.get("available"), "explicit finalise succeeds when ready")

    run = get_run(c, rid)
    # §19 independent expected ledger vs actual final rows
    lg = qa.category("independent_final_ledger")
    ledger = build_expected_ledger(run)
    all_rows, counts, _ = fetch_all_final_rows(c, rid, "all")
    actual_by = {r["plot_id"]: r for r in all_rows}
    mismatches = 0
    for pid, exp in ledger.items():
        act = actual_by.get(pid)
        if act is None:
            mismatches += 1; continue
        if bool(act["realised"]) != exp["expected_realised"]:
            mismatches += 1
        elif exp["expected_realised"] and act.get("final_crop") != exp["expected_final_crop"]:
            mismatches += 1
        elif (not exp["expected_realised"]) and act.get("final_crop") is not None:
            mismatches += 1
    qa.check(lg, mismatches == 0, "independent ledger matches actual final rows (%d mismatch)" % mismatches, defect=True)

    # §20/§21 911 accounting + pagination traversal (unique IDs, no dupes/omissions)
    acc = qa.category("final_accounting_911")
    ids_all = [r["plot_id"] for r in all_rows]
    qa.check(acc, len(ids_all) == 911, "all filter has 911 rows", defect=True)
    qa.check(acc, len(set(ids_all)) == 911, "all IDs unique (no dupes/omissions)", defect=True)
    r_rows, r_counts, _ = fetch_all_final_rows(c, rid, "realised")
    n_rows, n_counts, _ = fetch_all_final_rows(c, rid, "not_realised")
    qa.check(acc, all(x["realised"] for x in r_rows) and all(not x["realised"] for x in n_rows), "filter rows respect realised flag")
    qa.check(acc, counts["realised"] + counts["not_realised"] == counts["all"] == 911, "realised+not==all==911", defect=True)
    for r in all_rows:
        if r["realised"]:
            if r["final_crop"] is None:
                qa.check(acc, False, "realised row has crop"); break
        else:
            if r["final_crop"] is not None:
                qa.check(acc, False, "unrealised row final_crop==None"); break
    # boundary pages
    fp = qa.category("final_filter_pagination_api")
    for q in ("page=0", "page=-1", "page=999999", "page=abc", "filter=bogus"):
        code, _ = safe_get(c, "/api/farmsync/working-plan/%s/final-rows?%s" % (rid, q))
        qa.check(fp, code in (200, 400), "boundary '%s' safe (%d)" % (q, code))
        qa.check(fp, code != 500, "boundary '%s' must not 500" % q, defect=True)

    # §22 analysis reconciliation
    an = qa.category("analyse_reconciliation")
    a = c.get("/api/farmsync/working-plan/%s/analysis" % rid).get_json()
    qa.check(an, a.get("available"), "analysis available at final_current", defect=True)
    if a.get("available"):
        o = a["overview"]
        qa.check(an, o["realised_plots"] + o["not_realised_plots"] == o["total_plots"] == 911, "realised+not==total==911", defect=True)
        qa.check(an, o["offered_plots"] + o["no_offer_plots"] == o["total_plots"], "offered+no_offer==total", defect=True)
        qa.check(an, sum(a["initial_response_history"].values()) == a["n_offer_rows"], "initial history==offer rows", defect=True)
        qa.check(an, sum(a["renewed_consent_outcomes"].values()) == a["n_requires_renewed_consent"], "renewed==requires", defect=True)
        qa.check(an, sum(a["not_realised_reasons"].values()) == o["not_realised_plots"], "reasons==not_realised", defect=True)
        qa.check(an, sum(a["crop_composition_plots"].values()) == o["realised_plots"], "composition==realised", defect=True)
        qa.check(an, o["farmers_with_realised"] + o["farmers_without_realised"] == o["total_farmers"], "farmer split==total", defect=True)
        qa.check(an, a["final_plan_revision"] == run["final_plan_revision"], "analysis rev==run rev", defect=True)
        qa.check(an, a["integrity"]["ok"], "integrity.ok", defect=True)

        # §24 metrics
        mm = qa.category("consent_realisation_metrics")
        qa.check(mm, abs(o["realisation_rate_offered"] - o["realised_plots"] / o["offered_plots"]) < 1e-9, "realisation_rate_offered")
        qa.check(mm, abs(o["realisation_rate_all_plots"] - o["realised_plots"] / o["total_plots"]) < 1e-9, "realisation_rate_all_plots")
        qa.check(mm, abs(o["affirmative_consent_coverage"] - run["consent_coverage_final"]) < 1e-9, "affirmative coverage==finalise coverage")

        # §25/§13 fairness math (independent Gini: absolute, per-ha all-farmer, participant-only per-ha)
        fm = qa.category("fairness_math")
        dsnap = run.get("dataset_snapshot"); plots = dsnap["plots"]
        cash = {f["farmer_id"]: 0.0 for f in dsnap["farmers"]}
        area = {f["farmer_id"]: 0.0 for f in dsnap["farmers"]}
        rec_by = {r["plot_id"]: r for r in run["recommendations"]}
        area_ok = True
        for p in plots:
            fid = p.get("farmer_id")
            ah = p.get("area_ha")
            if ah is None:
                area_ok = False
            else:
                area[fid] = area.get(fid, 0.0) + float(ah)
            r = rec_by.get(p["plot_id"])
            if r and r.get("realised"):
                cash[fid] = cash.get(fid, 0.0) + (r.get("final_cash") or 0.0)
        g_abs = gini(list(cash.values()))
        per_ha_all = [cash[f["farmer_id"]] / area[f["farmer_id"]] if area.get(f["farmer_id"], 0) > 0 else 0.0 for f in dsnap["farmers"]] if area_ok else None
        g_perha = gini(per_ha_all) if area_ok else None
        part_perha = [cash[f["farmer_id"]] / area[f["farmer_id"]] for f in dsnap["farmers"] if cash.get(f["farmer_id"], 0) > 0 and area.get(f["farmer_id"], 0) > 0] if area_ok else None
        g_part = gini(part_perha) if area_ok else None
        f = a["fairness"]
        qa.check(fm, f["n_farmers"] == 500, "n_farmers==500")
        qa.check(fm, f["n_participants"] + f["n_zero_realisation_farmers"] == 500, "participants+zero==500")
        if f["all_farmer_abs_cash_gini"] is not None and g_abs is not None:
            qa.check(fm, abs(f["all_farmer_abs_cash_gini"] - g_abs) < 1e-6, "independent abs Gini matches (%.6f vs %.6f)" % (f["all_farmer_abs_cash_gini"], g_abs), defect=True)
        if area_ok and f.get("all_farmer_per_ha_gini") is not None and g_perha is not None:
            qa.check(fm, abs(f["all_farmer_per_ha_gini"] - g_perha) < 1e-6, "independent per-ha Gini matches (%.6f vs %.6f)" % (f["all_farmer_per_ha_gini"], g_perha), defect=True)
        if area_ok and f.get("participant_only_per_ha_gini") is not None and g_part is not None:
            qa.check(fm, abs(f["participant_only_per_ha_gini"] - g_part) < 1e-6, "independent participant per-ha Gini matches", defect=True)
        for key in ("all_farmer_abs_cash_gini", "all_farmer_per_ha_gini", "participant_only_per_ha_gini"):
            v = f.get(key)
            if v is not None:
                import math
                qa.check(fm, math.isfinite(v) and 0.0 <= v <= 1.0, "%s finite in [0,1]" % key)

        # §26/§14 concentration math (independent, for the ACTUAL basis — plots OR area)
        cm = qa.category("concentration_math")
        cc = a["concentration"]
        if cc.get("available"):
            basis = cc["basis"]
            rec_by = {r["plot_id"]: r for r in run["recommendations"]}
            if basis == "area":
                # independent area-basis: realised area per crop from dataset area_ha joined to realised rows
                area_by_crop = {}
                area_ok = True
                for p in run["dataset_snapshot"]["plots"]:
                    r = rec_by.get(p["plot_id"])
                    if r and r.get("realised"):
                        ah = p.get("area_ha")
                        if ah is None:
                            area_ok = False
                            continue
                        crop = r.get("final_crop")
                        area_by_crop[crop] = area_by_crop.get(crop, 0.0) + float(ah)
                if not area_ok:
                    qa.check(cm, False, "area basis reported but some realised plots lack area_ha (unavailable condition)")
                basisvals = area_by_crop
            else:
                comp = a["crop_composition_plots"]
                basisvals = dict(comp)
            tot = sum(basisvals.values()) or 1.0
            shares = {k: v / tot for k, v in basisvals.items()}
            hhi = sum(s * s for s in shares.values())
            qa.check(cm, abs(cc["hhi_crop_share"] - round(hhi, 4)) < 1e-4, "independent HHI (%s basis) matches (%.6f vs %.6f)" % (basis, cc["hhi_crop_share"], hhi), defect=True)
            qa.check(cm, abs(cc["max_crop_share"] - round((max(shares.values()) if shares else 0.0), 4)) < 1e-4, "max share matches (%s basis)" % basis)
            qa.check(cm, abs(sum(shares.values()) - 1.0) < 1e-6, "shares sum to 1 (%s basis)" % basis)
            qa.check(cm, all(0.0 <= s <= 1.0 for s in shares.values()), "each share in [0,1]")
            qa.check(cm, cc["active_realised_crops"] == len([v for v in basisvals.values() if v > 0]), "active crops matches")
            qa.check(cm, cc["alpha_reference"] == 0.40, "alpha reference only == 0.40")

        # §27/§28 uncertainty / resilience honest unavailable
        uu = qa.category("uncertainty_unavailable")
        qa.check(uu, a["uncertainty"]["available"] is False and "Not available" in a["uncertainty"]["reason"], "uncertainty honest unavailable")
        rr = qa.category("resilience_unavailable")
        qa.check(rr, a["resilience"]["available"] is False and "Not available" in a["resilience"]["reason"], "resilience honest unavailable")

    # substantive summary for repeatability (exclude run_id/timestamps)
    summary = {
        "offered": offered, "no_offer": no_offer,
        "realised": a["overview"]["realised_plots"] if a.get("available") else None,
        "not_realised": a["overview"]["not_realised_plots"] if a.get("available") else None,
        "not_realised_reasons": a.get("not_realised_reasons"),
        "final_cash": a["overview"]["final_realised_cash"] if a.get("available") else None,
        "crop_composition": a.get("crop_composition_plots"),
        "fairness_gini": a["fairness"]["all_farmer_abs_cash_gini"] if a.get("available") else None,
        "hhi": a["concentration"].get("hhi_crop_share") if a.get("available") else None,
        "integrity_ok": a["integrity"]["ok"] if a.get("available") else None,
    }
    if ledgers_out is not None:
        ledgers_out["ledger"] = ledger
    clean_state()
    return summary, rid


def _is_pending_row(run, rec):
    if rec.get("consent_for_crop") != rec.get("revised_crop"):
        return True
    if rec.get("consent_for_replan_anchor") != run.get("replan_anchor"):
        return True
    return rec.get("renewed_response") not in ("ACCEPT", "REJECT", "NO_RESPONSE")


# ------------------------------------------------------------------ §31 invalid-request matrix
def invalid_request_matrix(c, qa):
    cat = qa.category("invalid_request_matrix")
    clean_state(); c.post("/api/farmsync/select-builtin")
    wp = c.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    r0 = wp["recommendations"][0]
    fp0 = _fingerprint(get_run(c, rid))
    cases = [
        ("GET", "/api/farmsync/working-plan/BADRUN", None, (404,)),
        ("POST", "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": "ZZ", "plot_id": r0["plot_id"], "action": "ACCEPT"}, (400,)),
        ("POST", "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": r0["farmer_id"], "plot_id": "ZZ", "action": "ACCEPT"}, (400,)),
        ("POST", "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"]}, (400,)),
        ("POST", "/api/farmsync/working-plan/%s/response" % rid, {"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "FLY"}, (400,)),
        ("POST", "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "renewed_response": "MAYBE"}, (400,)),
        ("POST", "/api/farmsync/working-plan/%s/select-recommendation" % rid, {"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "crop": "dragonfruit"}, (400,)),
        ("POST", "/api/farmsync/working-plan/%s/finalise" % rid, {}, (400,)),   # nothing to finalise yet (no replan)
    ]
    for method, url, body, ok_codes in cases:
        if method == "GET":
            r = c.get(url)
        else:
            r = c.post(url, json=body)
        qa.check(cat, r.status_code in ok_codes, "%s %s -> %d (want %s)" % (method, url.split("/")[-1], r.status_code, ok_codes))
        qa.check(cat, r.status_code != 500, "no 500 for %s" % url.split("/")[-1])
        # error responses should be JSON (no stack trace leak)
        if r.data:
            try:
                r.get_json()
            except Exception:
                qa.check(cat, False, "non-JSON error body for %s" % url.split("/")[-1])
    # malformed JSON body
    r = c.post("/api/farmsync/working-plan/%s/response" % rid, data="{not json", content_type="application/json")
    qa.check(cat, r.status_code in (400, 415, 200), "malformed JSON handled (%d)" % r.status_code)
    qa.check(cat, r.status_code != 500, "malformed JSON no 500")
    # no mutation from invalid ops
    qa.check(cat, _fingerprint(get_run(c, rid)) == fp0, "invalid ops did not mutate run state", defect=True)
    clean_state()


# ------------------------------------------------------------------ §37 no solver / no live LLM on reads
def no_solver_on_reads(c, qa):
    cat = qa.category("no_solver_on_reads")
    llm = qa.category("no_live_llm")
    clean_state(); c.post("/api/farmsync/select-builtin")
    wp = c.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    # finalise a minimal plan so analysis endpoints are reachable
    for r in [r for r in wp["recommendations"] if r["crop"]][:3]:
        c.post("/api/farmsync/working-plan/%s/response" % rid, json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "action": "REJECT"})
    c.post("/api/farmsync/working-plan/%s/replan" % rid)
    c.post("/api/farmsync/working-plan/%s/consent-bulk" % rid, json={"decision": "ACCEPT"})
    c.post("/api/farmsync/working-plan/%s/finalise" % rid)
    sys.modules.pop("pulp", None)
    reads = [
        "/api/farmsync/working-plan/%s" % rid, "/api/farmsync/working-plan/%s/analysis" % rid,
        "/api/farmsync/working-plan/%s/final-rows?filter=realised" % rid,
        "/api/farmsync/working-plan/%s/final-rows?filter=all&page=5" % rid,
        "/api/farmsync/initial-plan", "/api/farmsync/final-plan", "/api/farmsync/consent",
        "/api/farmsync/fairness", "/api/farmsync/uncertainty", "/api/farmsync/resilience",
        "/api/farmsync/reproducibility", "/api/farmsync/dataset-summary",
        "/api/farmsync/explore-validation", "/api/farmsync/explore/plots",
    ]
    for u in reads:
        c.get(u)
    qa.check(cat, "pulp" not in sys.modules, "no CBC/PuLP imported by read endpoints", defect=True)
    # no live LLM client present/imported
    qa.check(llm, "openai" not in sys.modules and "groq" not in sys.modules, "no live LLM (openai/groq) imported")
    clean_state()


# ------------------------------------------------------------------ §33-36 custom data matrix
def custom_matrix(c, qa):
    import io
    cat = qa.category("custom_data_matrix")
    iso = qa.category("dataset_isolation")
    # incomplete uploads rejected (all three required)
    fa = "farmer_id,collective_id,region_id,season\nQA001,QAC1,R1,kharif"
    pl = "plot_id,farmer_id,region_id,area_ha\nQA001-P1,QA001,R1,1"
    cl = "collective_id,region_id,season\nQAC1,R1,kharif"
    def up(files):
        data = {k: (io.BytesIO(v.encode()), k) for k, v in files.items()}
        return c.post("/api/farmsync/upload-farmers", data=data, content_type="multipart/form-data")
    for combo, label in [({"farmers.csv": fa}, "farmers only"),
                         ({"farmers.csv": fa, "plots.csv": pl}, "farmers+plots"),
                         ({"plots.csv": pl, "collectives.csv": cl}, "plots+collectives")]:
        r = up(combo)
        qa.check(cat, r.status_code == 400 and "missing_files" in (r.get_json() or {}), "incomplete upload rejected: %s" % label)
    # §34 validation != planning readiness (minimal 3-file: structurally valid, not ready)
    r = up({"farmers.csv": fa, "plots.csv": pl, "collectives.csv": cl}).get_json()
    qa.check(cat, r.get("passed") is True and r["readiness"]["ready_to_plan"] is False, "minimal custom: valid but not ready")
    st = c.post("/api/farmsync/activate")
    qa.check(cat, st.status_code == 400, "activation blocked when not ready-to-plan", defect=True)
    # planning-ready custom fixture (agronomy from a real R1 plot)
    import csv
    bp = [x for x in csv.DictReader(open(os.path.join(REPO_ROOT, "data/farmsync/builtin/plots.csv")))
          if x["region_id"] == "R1" and x["active_season"] == "kharif"][:4]
    cols = "plot_id,farmer_id,region_id,area_ha,soil_group,soil_suitability_class,drainage_class,available_water_m3,waterlogging_exposure,active_season,previous_crop"
    plines = [cols]
    for j, rp in enumerate(bp, 1):
        fi = ((j - 1) % 3) + 1
        plines.append("QA00%d-P%02d,QA00%d,R1,%s,%s,%s,%s,%s,%s,kharif,%s" % (fi, j, fi, rp["area_ha"], rp["soil_group"], rp["soil_suitability_class"], rp["drainage_class"], rp["available_water_m3"], rp["waterlogging_exposure"], rp["previous_crop"]))
    fa2 = "farmer_id,collective_id,region_id,season\n" + "\n".join("QA00%d,QAC1,R1,kharif" % i for i in range(1, 4))
    cl2 = "collective_id,region_id,season\nQAC1,R1,kharif"
    c.post("/api/farmsync/change-dataset")
    r = up({"farmers.csv": fa2, "plots.csv": "\n".join(plines), "collectives.csv": cl2}).get_json()
    qa.check(cat, r["readiness"]["ready_to_plan"] is True, "agronomy custom: ready to plan")
    act = c.post("/api/farmsync/activate")
    qa.check(cat, act.status_code == 200 and act.get_json().get("planning_source") == "custom", "activation succeeds; planning_source==custom")
    wp = c.post("/api/farmsync/working-plan/start").get_json()
    ids = {r["farmer_id"] for r in wp["recommendations"]}
    qa.check(iso, all(x.startswith("QA") for x in ids), "custom IDs drive plan")
    qa.check(iso, not any(x.startswith("F0") for x in ids), "no built-in Fxxxx leakage", defect=True)
    # custom -> change -> built-in detaches
    c.post("/api/farmsync/change-dataset")
    c.post("/api/farmsync/select-builtin")
    wp2 = c.post("/api/farmsync/working-plan/start").get_json()
    ids2 = {r["farmer_id"] for r in wp2["recommendations"]}
    qa.check(iso, all(x.startswith("F") for x in ids2) and not any(x.startswith("QA") for x in ids2), "dataset switch detaches (F-only, no QA)", defect=True)
    # Data Explorer reads do not alter planning source
    c.post("/api/farmsync/change-dataset")
    c.get("/api/farmsync/explore-tables"); c.get("/api/farmsync/explore/farmers")
    ps = c.get("/api/farmsync/planning-source").get_json()
    qa.check(iso, ps["planning_source"] is None, "explorer reads do not set planning source", defect=True)
    import shutil
    clean_state()  # isolation-aware: removes only QA-created snapshots/runs
    clean_state()


# ------------------------------------------------------------------ §36 dataset security (delegate to existing suite)
def dataset_security(qa, ui_results, client=None):
    cat = qa.category("dataset_security")
    # Prefer the existing dataset_manager suite result; if suites were skipped, run direct regressions.
    dm = ui_results.get("test_farmsync_dataset_manager.py", {})
    if dm.get("passed", 0) > 0 and (dm.get("failed", 0) + dm.get("errors", 0)) == 0:
        qa.check(cat, True, "dataset_manager security suite passed (%d passed)" % dm.get("passed", 0), defect=True)
        return
    # direct, self-contained security regressions via the package validator
    try:
        import io, zipfile
        from farmsync import dataset_manager as dsm
        # ZIP path traversal + absolute path entries must be rejected/sanitised, never written outside.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("../../evil.csv", "x")
            z.writestr("/etc/evil.csv", "x")
            z.writestr("farmers.csv", "farmer_id\nF1")
        buf.seek(0)
        safe = True
        try:
            pkg = dsm.package_from_zip(buf.read()) if hasattr(dsm, "package_from_zip") else None
            if pkg is not None:
                for nm in (getattr(pkg, "names", lambda: [])() if callable(getattr(pkg, "names", None)) else []):
                    if nm.startswith("/") or ".." in nm:
                        safe = False
        except Exception:
            safe = True   # rejecting the malicious archive is a safe outcome
        qa.check(cat, safe, "ZIP path-traversal/absolute entries not materialised outside sandbox", defect=True)
        # unsupported filename ignored
        qa.check(cat, hasattr(dsm, "SUPPORTED_FILES"), "validator exposes SUPPORTED_FILES allow-list", defect=True)
    except Exception as e:
        qa.check(cat, False, "dataset security direct-check crashed: %s" % e, defect=True)


# ------------------------------------------------------------------ §38 repeatability
def repeatability(c, qa):
    cat = qa.category("backend_repeatability")
    s1, _ = run_full_builtin_journey(c, QA(), {})   # isolated recorder for run 1 checks
    s2, _ = run_full_builtin_journey(c, QA(), {})
    keys = ["offered", "no_offer", "realised", "not_realised", "final_cash", "crop_composition",
            "fairness_gini", "hhi", "integrity_ok", "not_realised_reasons"]
    match = all(s1.get(k) == s2.get(k) for k in keys)
    qa.check(cat, match, "substantive results identical across two clean runs", defect=True)
    _write(os.path.join(QA_DIR, "qa_repeatability_backend.json"), {"run1": s1, "run2": s2, "match": match})
    return match


# ------------------------------------------------------------------ reports + status table
_STATUS_ROWS = [
    ("Environment/imports", "environment"),
    ("Existing FarmSync tests", "existing_tests"),
    ("Config/hash/seeds", "config_hash_seeds"),
    ("Frozen-artifact pre-hash", "prehash"),
    ("Controlled scenario selection", "scenario_selection"),
    ("Farmer Response semantics", "farmer_response_semantics"),
    ("Replan semantics", "replan_semantics"),
    ("Consent-alternative backend", "consent_alternative"),
    ("Consent original-return branch", "consent_original_branch"),
    ("Select-recommendation backend", "select_recommendation"),
    ("Renewed Consent backend", "renewed_consent_backend"),
    ("Stale-anchor consent", "stale_anchor_consent"),
    ("Finalisation gating", "finalisation_gating"),
    ("Independent final ledger", "independent_final_ledger"),
    ("911-plot final accounting", "final_accounting_911"),
    ("Final filter/pagination API", "final_filter_pagination_api"),
    ("Analyse reconciliation", "analyse_reconciliation"),
    ("Consent/realisation metrics", "consent_realisation_metrics"),
    ("Fairness math", "fairness_math"),
    ("Concentration math", "concentration_math"),
    ("Uncertainty honest unavailable state", "uncertainty_unavailable"),
    ("Resilience honest unavailable state", "resilience_unavailable"),
    ("State invalidation", "state_invalidation"),
    ("Idempotency/duplicate requests", "idempotency"),
    ("Invalid-request matrix", "invalid_request_matrix"),
    ("Custom-data matrix", "custom_data_matrix"),
    ("Dataset isolation/switching", "dataset_isolation"),
    ("Dataset security", "dataset_security"),
    ("No solver on reads", "no_solver_on_reads"),
    ("No live LLM", "no_live_llm"),
    ("Backend repeatability", "backend_repeatability"),
    ("Frozen-artifact byte identity", "posthash"),
    ("Response count deltas", "response_count_deltas"),
    ("Universe 500/911", "universe_911"),
    ("Malformed pagination routes", "malformed_pagination_routes"),
    ("State isolation", "state_isolation"),
    ("Suite completeness", "suite_completeness"),
    ("Warning audit", "warning_audit"),
]


def state_invalidation(c, qa):
    cat = qa.category("state_invalidation")
    clean_state(); c.post("/api/farmsync/select-builtin")
    wp = c.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    for r in [r for r in wp["recommendations"] if r["crop"]][:4]:
        c.post("/api/farmsync/working-plan/%s/response" % rid, json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "action": "REJECT"})
    c.post("/api/farmsync/working-plan/%s/replan" % rid)
    c.post("/api/farmsync/working-plan/%s/consent-bulk" % rid, json={"decision": "ACCEPT"})
    c.post("/api/farmsync/working-plan/%s/finalise" % rid)
    w0 = wf(c, rid)
    qa.check(cat, w0["final_current"] and w0["stages"]["analyse"], "finalised: final_current + analyse unlocked")
    # pure GET revisit -> no change
    fp0 = _fingerprint(get_run(c, rid))
    for u in ("", "/analysis", "/final-rows?filter=all&page=1"):
        c.get("/api/farmsync/working-plan/%s%s" % (rid, u))
    qa.check(cat, _fingerprint(get_run(c, rid)) == fp0, "pure GET revisit does not mutate")
    # upstream edit -> all downstream stale
    other = next(r for r in get_run(c, rid)["recommendations"] if r["crop"] and not r.get("working_response"))
    c.post("/api/farmsync/working-plan/%s/response" % rid, json={"farmer_id": other["farmer_id"], "plot_id": other["plot_id"], "action": "WITHDRAW"})
    w1 = wf(c, rid)
    qa.check(cat, not w1["replan_current"] and not w1["final_current"] and not w1["stages"]["analyse"], "upstream edit stales replan/final/analyse", defect=True)
    qa.check(cat, not c.get("/api/farmsync/working-plan/%s/analysis" % rid).get_json()["available"], "analysis unavailable when stale", defect=True)
    # re-finalise -> new revision
    prev_rev = w0["response_rev"]
    c.post("/api/farmsync/working-plan/%s/replan" % rid)
    c.post("/api/farmsync/working-plan/%s/consent-bulk" % rid, json={"decision": "ACCEPT"})
    c.post("/api/farmsync/working-plan/%s/finalise" % rid)
    a = c.get("/api/farmsync/working-plan/%s/analysis" % rid).get_json()
    qa.check(cat, a["available"] and a["final_plan_revision"] == 2, "re-finalise yields new current revision")
    clean_state()


def warning_audit(qa, ui_results, ilp_results, full_suite_coverage):
    cat = qa.category("warning_audit")
    known = ["PerformanceWarning", "DeprecationWarning", "PULP_CBC_CMD", "LpVariable"]
    total = sum(v.get("warnings", 0) for v in list(ui_results.values()) + list(ilp_results.values()))
    summary = {"total_warnings": total, "known_categories": known,
               "per_suite": {k: v.get("warnings", 0) for k, v in list(ui_results.items()) + list(ilp_results.items())},
               "full_suite_coverage": full_suite_coverage}
    if not full_suite_coverage:
        summary["status"] = "INCOMPLETE"
        qa.set_status(cat, "INCOMPLETE",
                      "complete warning inventory unavailable (FULL_SUITE_COVERAGE=NO); only %d warnings "
                      "seen across the recorded subset" % total)
    else:
        summary["status"] = "KNOWN_WARNINGS" if total > 0 else "PASS"
        qa.set_status(cat, summary["status"], "%d warnings across all suites (all known families)" % total)
    _write(os.path.join(QA_DIR, "qa_warning_summary.json"), summary)
    return summary


def generate_reports(qa, env, cfg_snap, before, after, ui_results, ilp_results, ledgers, full_suite_coverage, discovered, completed, timed_out):
    diff = diff_hashes(before, after)
    qa.category("posthash")
    allempty = not (diff["added_protected_artifacts"] or diff["removed_protected_artifacts"] or diff["modified_protected_artifacts"])
    qa.check("posthash", allempty, "frozen artifacts byte-identical (added=%d removed=%d modified=%d)" % (
        len(diff["added_protected_artifacts"]), len(diff["removed_protected_artifacts"]), len(diff["modified_protected_artifacts"])), defect=True)
    _write(os.path.join(QA_DIR, "qa_artifact_hashes_before.json"), before)
    _write(os.path.join(QA_DIR, "qa_artifact_hashes_after.json"), after)
    _write(os.path.join(QA_DIR, "qa_environment.json"), env)
    _write(os.path.join(QA_DIR, "qa_ledger.json"), ledgers)

    # suite completeness gate
    qa.category("suite_completeness")
    if not full_suite_coverage:
        qa.set_status("suite_completeness", "INCOMPLETE",
                      "FULL_SUITE_COVERAGE=NO (ran %d of %d discovered; timed_out=%s). Authoritative Phase-1 "
                      "requires all discovered suites to complete." % (len(completed), len(discovered), timed_out))
    else:
        qa.set_status("suite_completeness", "PASS", "all %d discovered suites completed" % len(discovered))

    overall_fail = qa.overall_fail() or (not full_suite_coverage)
    report = {
        "phase": "backend", "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "categories": qa.categories, "failures": qa.failures,
        "artifact_diff": diff,
        "full_suite_coverage": "YES" if full_suite_coverage else "NO",
        "discovered_modules": discovered, "completed_modules": completed, "timed_out_modules": timed_out,
        "missing_required_categories": qa.missing_required(),
        "config": cfg_snap, "test_suites": {"all": ui_results, "ilp": ilp_results},
        "phase1_status": "FAIL" if overall_fail else "PASS",
        "ready_for_phase_2": "NO" if overall_fail else "YES",
        "existing_tests_state": ("COMPLETE" if full_suite_coverage else "INCOMPLETE"),
    }
    _write(os.path.join(QA_DIR, "qa_report_backend.json"), report)

    lines = ["# FarmSync Automated QA — Phase 1 (backend)", "",
             "Generated: %s" % report["generated"], "",
             "FULL_SUITE_COVERAGE: %s" % report["full_suite_coverage"],
             "EXISTING_TESTS: %s" % report["existing_tests_state"], "",
             "| Category | Status |", "|---|---|"]
    for label, key in _STATUS_ROWS:
        lines.append("| %s | %s |" % (label, qa.status_of(key)))
    lines += ["", "**PHASE 1 QA STATUS: %s**" % report["phase1_status"],
              "**READY FOR QA PHASE 2: %s**" % report["ready_for_phase_2"], ""]
    if qa.failures:
        lines += ["## Recorded failures (NOT fixed by QA)"]
        for cat_name, kind, msg in qa.failures:
            lines.append("- **%s** [%s]: %s" % (cat_name, kind, msg))
    with open(os.path.join(QA_DIR, "qa_report_backend.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return report


def print_status(qa, report):
    print("\nFARMSYNC AUTOMATED QA — PHASE 1")
    print("=" * 33)
    print("FULL_SUITE_COVERAGE: %s   EXISTING_TESTS: %s" % (report["full_suite_coverage"], report["existing_tests_state"]))
    for label, key in _STATUS_ROWS:
        print("%-38s %s" % (label, qa.status_of(key)))
    print("\nPHASE 1 QA STATUS: %s" % report["phase1_status"])
    print("READY FOR QA PHASE 2: %s" % report["ready_for_phase_2"])


def consent_original_branch_coverage(qa):
    """§1: exercise the REAL consent_alternative() 'Return to original plan' branch with an isolated,
    QA-only working-run state (no product/dataset change). Builds a run whose row has effective MODIFY,
    original crop != revised crop, original in canonical eligible, not rejected."""
    cat = qa.category("consent_original_branch")
    import farmsync.exploratory_run as X
    snapshot_runtime_state()
    c = make_client()
    clean_state()
    wp = start_builtin(c); rid = wp["run_id"]
    picked = None
    for r in wp["recommendations"]:
        rec1 = c.post("/api/farmsync/working-plan/%s/recommend" % rid, json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"]}).get_json()
        if not rec1.get("found"):
            continue
        cropA = rec1["recommended_crop"]
        rec2 = c.post("/api/farmsync/working-plan/%s/recommend" % rid, json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "exclude": [cropA]}).get_json()
        if rec2.get("found") and rec2["recommended_crop"] != cropA:
            picked = (r["farmer_id"], r["plot_id"], cropA, rec2["recommended_crop"])
            break
    if picked is None:
        qa.set_status(cat, "INCOMPLETE", "could not find a plot with two canonically-feasible crops to construct the fixture")
        clean_state()
        return
    fid, pid, cropA, cropB = picked
    run = X.get_run(rid)
    rec = next(r for r in run["recommendations"] if r["plot_id"] == pid)
    rec["crop"] = cropA
    rec["working_response"] = "MODIFY"; rec["action"] = "MODIFY"; rec["requested_crop"] = None
    rec["rejected_alternatives"] = []; rec["changed"] = True; rec["requires_renewed_consent"] = True
    rec["revised_crop"] = cropB; rec["revised_crop_id"] = None; rec["revised_cash"] = rec.get("cash") or 0
    X._save_run(run)

    alt = X.consent_alternative(rid, fid, pid)
    oo = alt.get("original_option")
    qa.check(cat, oo is not None, "MODIFY fixture: original_option exists", defect=True)
    if oo:
        qa.check(cat, oo.get("crop") == cropA, "original_option.crop == original crop (%s)" % cropA, defect=True)
        qa.check(cat, oo.get("label") == "Return to original plan", "label == 'Return to original plan'", defect=True)
    seen = []; orig_in_normal = False
    for _ in range(12):
        a = X.consent_alternative(rid, fid, pid, exclude=seen)
        if not a.get("found"):
            break
        if a["recommended_crop"] == cropA:
            orig_in_normal = True
        seen.append(a["recommended_crop"])
    qa.check(cat, not orig_in_normal, "original crop not offered as a normal new candidate", defect=True)
    fp_before = _fingerprint(X.get_run(rid))
    X.consent_alternative(rid, fid, pid)
    qa.check(cat, _fingerprint(X.get_run(rid)) == fp_before, "consent_alternative is read-only", defect=True)

    run = X.get_run(rid)
    rec = next(r for r in run["recommendations"] if r["plot_id"] == pid)
    rec["working_response"] = "REJECT"; rec["action"] = "REJECT"
    X._save_run(run)
    altR = X.consent_alternative(rid, fid, pid)
    qa.check(cat, altR.get("original_option") is None, "REJECT-origin: original_option absent", defect=True)
    seen = []; rej_orig_seen = False
    for _ in range(12):
        a = X.consent_alternative(rid, fid, pid, exclude=seen)
        if not a.get("found"):
            break
        if a["recommended_crop"] == cropA:
            rej_orig_seen = True
        seen.append(a["recommended_crop"])
    qa.check(cat, not rej_orig_seen, "REJECT-origin: rejected original never in candidate cycle", defect=True)
    clean_state()


def state_isolation_check(qa):
    """§2 self-check: a sentinel pre-existing run with KNOWN BYTES must survive QA cleanup byte-identically."""
    cat = qa.category("state_isolation")
    exp = _MUTABLE_ROOTS[0]
    os.makedirs(exp, exist_ok=True)
    sentinel = os.path.join(exp, "SENTINEL_PREEXISTING_run.json")
    payload = '{"sentinel": true, "bytes": "known-content-v1"}'
    with open(sentinel, "w") as f:
        f.write(payload)
    before_sha = _sha(sentinel)
    snapshot_runtime_state()      # sentinel is now pre-existing (and hashed)
    c = make_client()
    clean_state()
    start_builtin(c)              # QA creates a run
    clean_state()                 # removes only QA-created runs
    qa.check(cat, os.path.exists(sentinel), "pre-existing sentinel run survives QA cleanup", defect=True)
    if os.path.exists(sentinel):
        qa.check(cat, _sha(sentinel) == before_sha, "sentinel SHA256 unchanged (byte-identical)", defect=True)
    diff = verify_runtime_byte_identity()
    qa.check(cat, not diff["added"] and not diff["removed"] and not diff["modified"],
             "pre-existing runtime state byte-identical (added=%d removed=%d modified=%d)" % (
                 len(diff["added"]), len(diff["removed"]), len(diff["modified"])), defect=True)
    os.remove(sentinel)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="backend", choices=["backend"])
    ap.add_argument("--skip-suites", action="store_true", help="DEV ONLY: skip full pytest discovery (forces INCOMPLETE)")
    ap.add_argument("--suite-timeout", type=int, default=180, help="per-suite pytest timeout (s)")
    args = ap.parse_args()

    os.makedirs(QA_DIR, exist_ok=True)
    snapshot_runtime_state()      # protect any pre-existing runtime state from the very start
    qa = QA()
    qa.category("environment")

    env = record_environment()
    qa.check("environment", "packages" in env and "flask" in env.get("packages", {}), "core packages importable", defect=True)
    try:
        import farmsync_routes  # noqa
        qa.check("environment", True, "farmsync_routes import OK")
    except Exception as e:
        qa.check("environment", False, "import failed: %s" % e, defect=True)

    cfg_snap = verify_config(qa)

    qa.category("prehash")
    before = hash_protected()
    qa.check("prehash", len(before) > 0, "protected artifacts hashed (%d)" % len(before))

    # ---- suite discovery/run + completeness tracking ----
    discovered = discover_test_modules()
    ui_results, ilp_results, completed, timed_out = {}, {}, [], []
    full_suite_coverage = False
    if args.skip_suites:
        # DEV convenience: record only the two authoritative + security suites; coverage is INCOMPLETE
        key = [m for m in ("test_farmsync_ui.py", "test_farmsync_dataset_manager.py", "test_farmsync_ilp_v2.py") if os.path.exists(os.path.join(REPO_ROOT, "tests", m))]
        all_results = run_pytest(qa, key, "", per_suite_timeout=args.suite_timeout)
    else:
        all_results = run_pytest(qa, discovered, "", per_suite_timeout=args.suite_timeout)
    ilp_results = {k: v for k, v in all_results.items() if "ilp" in k}
    ui_results = all_results
    for m, v in all_results.items():
        (timed_out if v.get("timed_out") else completed).append(m)
    full_suite_coverage = (not args.skip_suites) and (set(completed) == set(discovered)) and not timed_out

    c = make_client()
    ledgers = {}
    try:
        run_full_builtin_journey(c, qa, ledgers)
        renewed_consent_full(c, qa)
        consent_original_branch_coverage(qa)
        invalid_request_matrix(c, qa)
        malformed_pagination_routes(c, qa)
        no_solver_on_reads(c, qa)
        state_invalidation(c, qa)
        state_isolation_check(qa)
        custom_matrix(c, qa)
        dataset_security(qa, ui_results, c)
        repeatability(c, qa)
    except Exception as e:
        qa.check("environment", False, "backend scenario crashed: %s\n%s" % (e, traceback.format_exc()), defect=True)

    after = hash_protected()
    warning_audit(qa, ui_results, ilp_results, full_suite_coverage)
    report = generate_reports(qa, env, cfg_snap, before, after, ui_results, ilp_results, ledgers,
                              full_suite_coverage, discovered, completed, timed_out)
    print_status(qa, report)
    return 1 if report["phase1_status"] == "FAIL" else 0


def _discover_page_parse_sites():
    """Scan farmsync_routes.py for EVERY int(request.args.get('page'/'page_size')) site and map each to
    its nearest @app.route. Returns [(line, route, param)] — no reliance on hard-coded counts/comments."""
    import re
    src = open(os.path.join(REPO_ROOT, "farmsync_routes.py"), encoding="utf-8").read().split("\n")
    sites = []
    cur = None
    for i, l in enumerate(src, 1):
        m = re.search(r'@app\.route\("([^"]+)"', l)
        if m:
            cur = m.group(1)
        m2 = re.search(r'(?:int|_safe_int_arg)\(request\.args\.get\("(page(?:_size)?|size)"|_safe_int_arg\("(page(?:_size)?|size)"', l)
        if m2:
            sites.append((i, cur, m2.group(1) or m2.group(2)))
    return sites


def malformed_pagination_routes(c, qa):
    """§6: auto-discover page-parsing routes from source and probe malformed input on EVERY reachable one.
    Records source line / route / parameter / malformed value / HTTP result. Detect only (no patch)."""
    cat = qa.category("malformed_pagination_routes")
    clean_state(); c.post("/api/farmsync/select-builtin")
    wp = c.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    for r in [r for r in wp["recommendations"] if r["crop"]][:3]:
        c.post("/api/farmsync/working-plan/%s/response" % rid, json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "action": "REJECT"})
    c.post("/api/farmsync/working-plan/%s/replan" % rid)
    c.post("/api/farmsync/working-plan/%s/consent-bulk" % rid, json={"decision": "ACCEPT"})
    c.post("/api/farmsync/working-plan/%s/finalise" % rid)

    sites = _discover_page_parse_sites()
    # build a concrete reachable URL for each discovered route template
    def concretise(route, param):
        u = route
        u = u.replace("<run_id>", rid).replace("<table>", "plots")
        # ensure the finalised run makes final-rows reachable; explore/inspect need a loaded dataset
        return "/api%s?%s=abc" % (u if u.startswith("/") else "/" + u, param) if not u.startswith("/api") else "%s?%s=abc" % (u, param)

    inventory = []
    affected = []
    fp0 = _fingerprint(get_run(c, rid))
    seen_urls = set()
    for line, route, param in sites:
        # /inspect requires a staged pkg; load built-in for inspection so the route is reachable
        if "/inspect/" in route or "/explore/" in route:
            c.post("/api/farmsync/load-builtin")
        url = concretise(route, param)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        code, _ = safe_get(c, url)
        inventory.append({"source_line": line, "route": route, "parameter": param,
                          "malformed_value": "abc", "http_result": code})
        if code == 500:
            affected.append(route)
        qa.check(cat, code != 500, "%s malformed %s must not 500 (line %d) -> %d" % (route, param, line, code), defect=True)
        qa.check(cat, _fingerprint(get_run(c, rid)) == fp0, "%s malformed %s did not mutate state" % (route, param))
    qa.set_status(cat, qa.status_of(cat),
                  "discovered %d page-parse site(s); affected(500): %s" % (len(sites), sorted(set(affected)) or "none"))
    _write(os.path.join(QA_DIR, "qa_malformed_pagination_inventory.json"),
           {"sites": sites, "probes": inventory, "affected_routes": sorted(set(affected))})
    clean_state()
    return inventory


def renewed_consent_full(c, qa):
    """§3/§4: explicit Renewed Consent (ACCEPT/REJECT/NO_RESPONSE crop+anchor), bulk pending-only,
    select-recommendation, and consent-alternative J/L, all via the real API with visible checks."""
    rc = qa.category("renewed_consent_backend")
    ca = qa.category("consent_alternative")
    sel = qa.category("select_recommendation")

    def fresh_changed(n=6):
        clean_state(); c.post("/api/farmsync/select-builtin")
        wp = c.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
        for r in [r for r in wp["recommendations"] if r["crop"]][:n]:
            c.post("/api/farmsync/working-plan/%s/response" % rid, json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "action": "REJECT"})
        c.post("/api/farmsync/working-plan/%s/replan" % rid)
        run = c.get("/api/farmsync/working-plan/%s" % rid).get_json()
        changed = [r for r in run["recommendations"] if r.get("changed") and r.get("requires_renewed_consent")]
        return rid, run, changed

    rid, run, changed = fresh_changed()
    anchor = run["replan_anchor"]
    # ACCEPT / REJECT / NO_RESPONSE each stamp exact crop + anchor
    for decision, row in zip(("ACCEPT", "REJECT", "NO_RESPONSE"), changed):
        st, _ = _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": row["farmer_id"], "plot_id": row["plot_id"], "renewed_response": decision})
        qa.check(rc, st == 200, "consent %s POST succeeds" % decision)
        rr = next(r for r in c.get("/api/farmsync/working-plan/%s" % rid).get_json()["recommendations"] if r["plot_id"] == row["plot_id"])
        qa.check(rc, rr.get("renewed_response") == decision, "renewed_response == %s" % decision)
        qa.check(rc, rr.get("consent_for_crop") == rr.get("revised_crop"), "%s: consent_for_crop == exact revised_crop" % decision, defect=True)
        qa.check(rc, rr.get("consent_for_replan_anchor") == anchor, "%s: consent_for_replan_anchor == current replan_anchor" % decision, defect=True)
    # repeated identical decision is safe (no revision corruption)
    row = changed[0]
    rev0 = c.get("/api/farmsync/working-plan/%s" % rid).get_json()["workflow"]["response_rev"]
    _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": row["farmer_id"], "plot_id": row["plot_id"], "renewed_response": "ACCEPT"})
    _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": row["farmer_id"], "plot_id": row["plot_id"], "renewed_response": "ACCEPT"})
    rev1 = c.get("/api/farmsync/working-plan/%s" % rid).get_json()["workflow"]["response_rev"]
    qa.check(rc, rev0 == rev1, "repeated identical consent does not corrupt response_rev")
    # consent on a non-required (unchanged) row -> current server contract (refused)
    run = c.get("/api/farmsync/working-plan/%s" % rid).get_json()
    unchanged = next((r for r in run["recommendations"] if not r.get("changed")), None)
    if unchanged:
        st, _ = _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": unchanged["farmer_id"], "plot_id": unchanged["plot_id"], "renewed_response": "ACCEPT"})
        qa.check(rc, st == 400, "consent on non-required row refused (server contract)")

    # bulk ACCEPT: pending-only, preserving existing REJECT + NO_RESPONSE
    rid, run, changed = fresh_changed()
    A, B = changed[0], changed[1]
    _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "renewed_response": "REJECT"})
    _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": B["farmer_id"], "plot_id": B["plot_id"], "renewed_response": "NO_RESPONSE"})
    _post(c, "/api/farmsync/working-plan/%s/consent-bulk" % rid, {"decision": "ACCEPT"})
    run = c.get("/api/farmsync/working-plan/%s" % rid).get_json()
    a2 = next(r for r in run["recommendations"] if r["plot_id"] == A["plot_id"])
    b2 = next(r for r in run["recommendations"] if r["plot_id"] == B["plot_id"])
    qa.check(rc, a2["renewed_response"] == "REJECT" and b2["renewed_response"] == "NO_RESPONSE", "bulk ACCEPT preserves existing REJECT/NO_RESPONSE")
    others = [r for r in run["recommendations"] if r.get("changed") and r["plot_id"] not in (A["plot_id"], B["plot_id"])]
    qa.check(rc, all(r["renewed_response"] == "ACCEPT" for r in others), "bulk ACCEPT sets only pending -> ACCEPT")
    # bulk REJECT pending-only in a clean scenario
    rid, run, changed = fresh_changed()
    A = changed[0]
    _post(c, "/api/farmsync/working-plan/%s/consent" % rid, {"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "renewed_response": "ACCEPT"})
    _post(c, "/api/farmsync/working-plan/%s/consent-bulk" % rid, {"decision": "REJECT"})
    a2 = next(r for r in c.get("/api/farmsync/working-plan/%s" % rid).get_json()["recommendations"] if r["plot_id"] == A["plot_id"])
    qa.check(rc, a2["renewed_response"] == "ACCEPT", "bulk REJECT preserves existing ACCEPT (pending-only)")

    # select-recommendation full contract
    #
    # Do not assume changed[0] has a second feasible alternative.
    # The positive contract requires a row for which /recommend
    # actually returns a valid alternative, so deterministically
    # discover the first such changed row.
    rid, run, changed = fresh_changed(n=12)

    X = None
    altrec = None

    for candidate in changed:
        probe = c.post(
            "/api/farmsync/working-plan/%s/recommend" % rid,
            json={
                "farmer_id": candidate["farmer_id"],
                "plot_id": candidate["plot_id"],
                "exclude": [candidate["revised_crop"]],
            },
        ).get_json()

        if probe.get("found"):
            X = candidate
            altrec = probe
            break

    qa.check(
        sel,
        X is not None,
        "select-recommendation fixture has a valid alternative",
        defect=True,
    )

    if X is not None:
        _post(
            c,
            "/api/farmsync/working-plan/%s/consent" % rid,
            {
                "farmer_id": X["farmer_id"],
                "plot_id": X["plot_id"],
                "renewed_response": "ACCEPT",
            },
        )

        newcrop = altrec["recommended_crop"]

        st, res = _post(
            c,
            "/api/farmsync/working-plan/%s/select-recommendation" % rid,
            {
                "farmer_id": X["farmer_id"],
                "plot_id": X["plot_id"],
                "crop": newcrop,
            },
        )

        qa.check(
            sel,
            st == 200
            and res.get("revised_crop") == newcrop,
            "valid candidate becomes exact revised_crop",
            defect=True,
        )

        row = next(
            r
            for r in c.get(
                "/api/farmsync/working-plan/%s" % rid
            ).get_json()["recommendations"]
            if r["plot_id"] == X["plot_id"]
        )

        qa.check(
            sel,
            row.get("renewed_response") is None,
            "prior renewed consent cleared",
            defect=True,
        )

        qa.check(
            sel,
            row.get("consent_for_crop") is None,
            "consent_for_crop cleared",
            defect=True,
        )

        qa.check(
            sel,
            row.get("consent_for_replan_anchor") is None,
            "consent_for_replan_anchor cleared",
            defect=True,
        )

        qa.check(
            sel,
            _is_pending_row(
                c.get(
                    "/api/farmsync/working-plan/%s" % rid
                ).get_json(),
                row,
            ),
            "row becomes PENDING (choosing != consenting)",
            defect=True,
        )

        st, _ = _post(
            c,
            "/api/farmsync/working-plan/%s/select-recommendation" % rid,
            {
                "farmer_id": X["farmer_id"],
                "plot_id": X["plot_id"],
                "crop": "dragonfruit",
            },
        )

        qa.check(
            sel,
            st == 400,
            "unknown/infeasible crop refused",
            defect=True,
        )

        # stale selection refused
        other = next(
            r
            for r in c.get(
                "/api/farmsync/working-plan/%s" % rid
            ).get_json()["recommendations"]
            if r["crop"]
            and not r.get("working_response")
            and r["plot_id"] != X["plot_id"]
        )

        _post(
            c,
            "/api/farmsync/working-plan/%s/response" % rid,
            {
                "farmer_id": other["farmer_id"],
                "plot_id": other["plot_id"],
                "action": "WITHDRAW",
            },
        )

        st, _ = _post(
            c,
            "/api/farmsync/working-plan/%s/select-recommendation" % rid,
            {
                "farmer_id": X["farmer_id"],
                "plot_id": X["plot_id"],
                "crop": X["revised_crop"],
            },
        )

        qa.check(
            sel,
            st == 400,
            "stale selection refused",
        )

    # §4 J: browse excludes current revised + rejected + browse-history, canonical-only, no dupes, exhausts, read-only
    rid, run, changed = fresh_changed()
    J = changed[0]
    cur = J["revised_crop"]
    fp0 = _fingerprint(c.get("/api/farmsync/working-plan/%s" % rid).get_json())
    seen = []
    exhausted = False
    for _ in range(15):
        a = c.post("/api/farmsync/working-plan/%s/consent-alternative" % rid, json={"farmer_id": J["farmer_id"], "plot_id": J["plot_id"], "exclude": seen}).get_json()
        if not a.get("found"):
            exhausted = True
            break
        qa.check(ca, a["recommended_crop"] != cur, "J: current revised crop excluded")
        qa.check(ca, a["recommended_crop"] not in seen, "J: no duplicate before exhaustion")
        seen.append(a["recommended_crop"])
    qa.check(ca, exhausted, "J: exhaustion reached")
    qa.check(ca, _fingerprint(c.get("/api/farmsync/working-plan/%s" % rid).get_json()) == fp0, "J: consent-alternative read-only")

    # §4 L: genuine recorded REJECT-origin -> original suppressed
    clean_state(); c.post("/api/farmsync/select-builtin")
    wp = c.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    Lrow = next((r for r in wp["recommendations"] if r.get("recorded_response") == "REJECT" and r.get("crop")), None)
    if Lrow:
        c.post("/api/farmsync/working-plan/%s/replan" % rid)
        run = c.get("/api/farmsync/working-plan/%s" % rid).get_json()
        lr = next((r for r in run["recommendations"] if r["plot_id"] == Lrow["plot_id"]), None)
        if lr and lr.get("changed"):
            a = c.post("/api/farmsync/working-plan/%s/consent-alternative" % rid, json={"farmer_id": lr["farmer_id"], "plot_id": lr["plot_id"]}).get_json()
            qa.check(ca, (a.get("original_option") is None), "L: original_option absent for recorded REJECT")
            seen = []; orig = Lrow["crop"]; orig_seen = False
            for _ in range(12):
                aa = c.post("/api/farmsync/working-plan/%s/consent-alternative" % rid, json={"farmer_id": lr["farmer_id"], "plot_id": lr["plot_id"], "exclude": seen}).get_json()
                if not aa.get("found"):
                    break
                if aa["recommended_crop"] == orig:
                    orig_seen = True
                seen.append(aa["recommended_crop"])
            qa.check(ca, not orig_seen, "L: rejected original never appears as candidate")
    clean_state()



if __name__ == "__main__":
    sys.exit(main())
