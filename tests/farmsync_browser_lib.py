"""FarmSync Phase-2 browser QA — shared infrastructure (QA-only; never modifies product code).

Spins up an ephemeral localhost Flask server serving the REAL templates/JS/CSS, provides console/network
capture, no-solver/no-LLM instrumentation, protected-artifact hashing and mutable-runtime isolation.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sys
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, REPO_ROOT)

BROWSER_QA_DIR = os.path.join(REPO_ROOT, "results", "farmsync", "qa", "browser")
SHOTS_DIR = os.path.join(BROWSER_QA_DIR, "screenshots")
TRACES_DIR = os.path.join(BROWSER_QA_DIR, "traces")

# a real base.html (site chrome). Prefer the repo's, else the known uploads copy, else a minimal shim.
_BASE_CANDIDATES = [
    os.path.join(REPO_ROOT, "templates", "base.html"),
    "/mnt/user-data/uploads/base.html",
]

_MUTABLE_ROOTS = [os.path.join(REPO_ROOT, "results", "farmsync", "exploratory"),
                  os.path.join(REPO_ROOT, "data", "farmsync", "snapshots")]
_PREEXISTING = {}
_PREEXISTING_HASHES = {}


# ------------------------------------------------------------------ hashing / isolation
def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
    _PREEXISTING.clear(); _PREEXISTING_HASHES.clear()
    for root in _MUTABLE_ROOTS:
        _PREEXISTING[root] = set(os.listdir(root)) if os.path.isdir(root) else set()
        for rel, h in _hash_tree(root).items():
            _PREEXISTING_HASHES[root + "::" + rel] = h


def verify_runtime_byte_identity():
    current = {}
    for root in _MUTABLE_ROOTS:
        keep = _PREEXISTING.get(root, set())
        for rel, h in _hash_tree(root).items():
            if rel.split("/", 1)[0] in keep:
                current[root + "::" + rel] = h
    b, a = set(_PREEXISTING_HASHES), set(current)
    return {"removed": sorted(b - a), "added": sorted(a - b),
            "modified": sorted(k for k in (b & a) if _PREEXISTING_HASHES[k] != current[k])}


def clean_state():
    for root in _MUTABLE_ROOTS:
        if not os.path.isdir(root):
            continue
        keep = _PREEXISTING.get(root, set())
        for name in list(os.listdir(root)):
            if name in keep:
                continue
            p = os.path.join(root, name)
            try:
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
            except OSError:
                pass


_PROTECTED_ROOTS = [os.path.join(REPO_ROOT, "results", "farmsync"),
                    os.path.join(REPO_ROOT, "data", "farmsync", "processed")]
_PROTECTED_EXCLUDE = {os.path.normpath(os.path.join(REPO_ROOT, "results", "farmsync", "qa")),
                      os.path.normpath(os.path.join(REPO_ROOT, "results", "farmsync", "exploratory")),
                      os.path.normpath(os.path.join(REPO_ROOT, "data", "farmsync", "snapshots"))}


def hash_protected():
    out = {}
    for base in _PROTECTED_ROOTS:
        if not os.path.isdir(base):
            continue
        for dp, dn, fn in os.walk(base):
            npath = os.path.normpath(dp)
            if any(npath == ex or npath.startswith(ex + os.sep) for ex in _PROTECTED_EXCLUDE):
                dn[:] = []
                continue
            dn[:] = [d for d in dn if os.path.normpath(os.path.join(dp, d)) not in _PROTECTED_EXCLUDE
                     and d not in ("__pycache__", ".cache", "logs")]
            for name in sorted(fn):
                if name.endswith((".json", ".csv")):
                    p = os.path.join(dp, name)
                    out[os.path.relpath(p, REPO_ROOT).replace("\\", "/")] = _sha(p)
    return out


def diff_hashes(before, after):
    b, a = set(before), set(after)
    return {"added_protected_artifacts": sorted(a - b),
            "removed_protected_artifacts": sorted(b - a),
            "modified_protected_artifacts": sorted(k for k in (b & a) if before[k] != after[k])}


# ------------------------------------------------------------------ ephemeral server
class QAServer:
    """Runs the REAL FarmSync app on 127.0.0.1:<ephemeral> via a stoppable werkzeug server.
    mode='real'      -> uses the actual templates/base.html (authoritative real-site run);
    mode='isolated'  -> minimal base that loads only FarmSync's own JS/CSS (component isolation/debug).
    """
    def __init__(self, mode="real"):
        assert mode in ("real", "isolated")
        self.mode = mode
        self.port = None
        self.thread = None
        self.app = None
        self._srv = None
        self._tpl_dir = None

    def _free_port(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        return p

    def _make_templates(self):
        import tempfile
        d = tempfile.mkdtemp(prefix="fsqa_browser_tpl_")
        if self.mode == "real":
            # AUTHORITATIVE: use the actual repository base + page. If templates/base.html is absent in the
            # repo, fall back to the known real base (uploads copy) — never a minimal stub in real mode.
            base = None
            for cand in _BASE_CANDIDATES:
                if os.path.exists(cand):
                    base = open(cand, encoding="utf-8").read()
                    break
            if base is None:
                raise RuntimeError("real-site mode requires templates/base.html (or a real base) — none found")
            open(os.path.join(d, "base.html"), "w", encoding="utf-8").write(base)
        else:
            # ISOLATED: minimal base, FarmSync JS/CSS only (no external site chrome).
            base = ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
                    "<meta name='viewport' content='width=device-width, initial-scale=1'>"
                    "<title>{% block title %}{% endblock %}</title>"
                    "<link rel='stylesheet' href='/static/css/farmsync.css'></head>"
                    "<body>{% block content %}{% endblock %}{% block scripts %}{% endblock %}</body></html>")
            open(os.path.join(d, "base.html"), "w", encoding="utf-8").write(base)
        shutil.copy(os.path.join(REPO_ROOT, "templates", "farmsync.html"), os.path.join(d, "farmsync.html"))
        self._tpl_dir = d
        return d

    def start(self, timeout=45):
        from flask import Flask
        from werkzeug.serving import make_server
        tpl = self._make_templates()
        app = Flask(__name__, template_folder=tpl, static_folder=os.path.join(REPO_ROOT, "static"),
                    static_url_path="/static")
        app.config["TESTING"] = False
        app.config["PROPAGATE_EXCEPTIONS"] = False
        import farmsync_routes
        farmsync_routes.register_farmsync_routes(app)
        self.app = app
        self.port = self._free_port()
        # deterministic, stoppable server (make_server + shutdown), not app.run in a daemon thread
        self._srv = make_server("127.0.0.1", self.port, app, threaded=True)
        self.thread = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self.thread.start()
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                import urllib.request
                with urllib.request.urlopen("http://127.0.0.1:%d/farm-sync" % self.port, timeout=2) as r:
                    if r.status == 200:
                        return True
            except Exception:
                time.sleep(0.25)
        raise RuntimeError("QA Flask server (%s mode) not ready on 127.0.0.1:%s within %ss" % (self.mode, self.port, timeout))

    @property
    def base_url(self):
        return "http://127.0.0.1:%d" % self.port

    def solver_loaded(self):
        return "pulp" in sys.modules

    def llm_loaded(self):
        return ("openai" in sys.modules) or ("groq" in sys.modules)

    def port_open(self):
        try:
            s = socket.socket(); s.settimeout(1)
            s.connect(("127.0.0.1", self.port)); s.close()
            return True
        except Exception:
            return False

    def stop(self):
        """Deterministic shutdown: stop the werkzeug server and join the thread; then verify the port is
        closed. Returns True if the server actually stopped accepting connections."""
        try:
            if self._srv is not None:
                self._srv.shutdown()
            if self.thread is not None:
                self.thread.join(timeout=10)
        except Exception:
            pass
        try:
            if self._tpl_dir and os.path.isdir(self._tpl_dir):
                shutil.rmtree(self._tpl_dir, ignore_errors=True)
        except Exception:
            pass
        # confirm port closed
        t0 = time.time()
        while time.time() - t0 < 5:
            if not self.port_open():
                return True
            time.sleep(0.2)
        return not self.port_open()


# ------------------------------------------------------------------ browser capture helpers
def attach_capture(page):
    """Attach console + network + pageerror capture to a Playwright page. Returns a dict of lists."""
    cap = {"console_errors": [], "console_warnings": [], "page_errors": [],
           "requests": [], "failed_requests": [], "responses_5xx": [], "external_requests": []}

    def on_console(msg):
        if msg.type == "error":
            cap["console_errors"].append(msg.text)
        elif msg.type == "warning":
            cap["console_warnings"].append(msg.text)

    def on_pageerror(err):
        cap["page_errors"].append(str(err))

    def on_request(req):
        cap["requests"].append({"method": req.method, "url": req.url, "resource_type": req.resource_type})
        if not (req.url.startswith("http://127.0.0.1") or req.url.startswith("http://localhost")):
            if req.url.startswith("data:") or req.url.startswith("blob:"):
                return
            cap["external_requests"].append(req.url)

    def on_requestfailed(req):
        cap["failed_requests"].append({"url": req.url, "failure": (req.failure or "")})

    def on_response(resp):
        if resp.status >= 500:
            cap["responses_5xx"].append({"url": resp.url, "status": resp.status})

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("request", on_request)
    page.on("requestfailed", on_requestfailed)
    page.on("response", on_response)
    return cap


def write_json(name, obj):
    os.makedirs(BROWSER_QA_DIR, exist_ok=True)
    with open(os.path.join(BROWSER_QA_DIR, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)


def playwright_versions():
    import importlib.metadata as im
    out = {"playwright": None, "python": sys.version.split()[0]}
    try:
        out["playwright"] = im.version("playwright")
    except Exception:
        out["playwright"] = "unknown"
    return out


def browser_version(pw, name):
    try:
        b = getattr(pw, name).launch()
        v = b.version
        b.close()
        return v
    except Exception as e:
        return "unavailable: %s" % str(e).split("\n")[0][:120]


def run_axe(page, context=None, include_nodes=False, sample_limit=12):
    """Run bundled axe-core (no CDN).

    `context` scopes axe to the product under test (e.g. ``#fsApp``) so unrelated portfolio-shell
    accessibility findings do not contaminate FarmSync authority. When ``include_nodes`` is true,
    record compact target/html/failure samples for exact fail-stop diagnosis without changing the gate.
    """
    try:
        from axe_playwright_python.sync_playwright import Axe
        axe = Axe()
        res = axe.run(page, context=context) if context is not None else axe.run(page)
        data = res.response if hasattr(res, "response") else res
        viols = data.get("violations", []) if isinstance(data, dict) else []
    except Exception as e:
        return {"available": False, "error": str(e)[:200], "context": context}
    buckets = {"critical": [], "serious": [], "moderate": [], "minor": []}
    for v in viols:
        imp = (v.get("impact") or "minor").lower()
        item = {"id": v.get("id"), "help": v.get("help"), "nodes": len(v.get("nodes", []))}
        if include_nodes:
            samples = []
            for n in (v.get("nodes") or [])[:sample_limit]:
                samples.append({
                    "target": n.get("target"),
                    "html": (n.get("html") or "")[:500],
                    "failureSummary": (n.get("failureSummary") or "")[:1000],
                })
            item["samples"] = samples
        buckets.setdefault(imp, []).append(item)
    return {"available": True, "context": context,
            "counts": {k: len(v) for k, v in buckets.items()}, "buckets": buckets}


def api(server, method, path, body=None):
    """Backend inspection/setup only (never replaces the UI action under test)."""
    import urllib.request
    url = server.base_url + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, (json.loads(raw) if raw else None)


def run_fingerprint(server, rid):
    st, run = api(server, "GET", "/api/farmsync/working-plan/%s" % rid)
    if not run:
        return None
    recs = []
    for r in sorted(run.get("recommendations", []), key=lambda x: x["plot_id"]):
        recs.append((r["plot_id"], r.get("working_response"), r.get("requested_crop"),
                     r.get("revised_crop"), r.get("renewed_response"), r.get("consent_for_crop"),
                     r.get("consent_for_replan_anchor"), bool(r.get("realised")), r.get("final_crop")))
    return hashlib.sha256(json.dumps({
        "recs": recs, "response_rev": run.get("response_rev"), "replan_anchor": run.get("replan_anchor"),
        "final_anchor": run.get("final_anchor"), "final_plan_revision": run.get("final_plan_revision"),
    }, default=str, sort_keys=True).encode()).hexdigest()
