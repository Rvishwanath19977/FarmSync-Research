"""FarmSync Phase-2 browser QA — pytest gates (QA-only).

Two explicit levels (§2):
  A. DEVELOPMENT SMOKE (this default test): Chromium-only, may report INCOMPLETE, skips if Playwright/
     Chromium unavailable. NOT authoritative.
  B. AUTHORITATIVE: run `python scripts/farmsync_browser_qa.py` (chromium+firefox+webkit, real mode).
     It returns non-zero unless the required-category gate yields a complete PASS.

Plus harness self-tests (§26) that need no browser and prove the gating model is trustworthy.
"""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
sys.path.insert(0, os.path.join(_ROOT, "tests"))

import farmsync_browser_qa as O    # noqa: E402


# ---------------- §26 harness self-tests (no browser) ----------------
def _all_pass_bqa():
    q = O.BQA()
    for c in O.REQUIRED_CATEGORIES:
        q.set(c, "PASS")
    q.set("return_original_branch", "SEMANTIC_BACKEND_COVERED")
    q.set("hard_refresh_known_limitation", "KNOWN_LIMITATION")
    return q


def test_gate_all_pass_is_pass():
    q = _all_pass_bqa()
    assert q.overall(["chromium", "firefox", "webkit"]) == "PASS"


def test_gate_missing_category_blocks_pass():
    q = _all_pass_bqa()
    del q.cats["accessibility_light"]
    assert q.overall(["chromium", "firefox", "webkit"]) == "INCOMPLETE"
    assert "accessibility_light" in q.missing_required()


def test_gate_one_fail_is_fail():
    q = _all_pass_bqa()
    q.check("accessibility_light", False, "serious color-contrast", defect=True)
    assert q.overall(["chromium", "firefox", "webkit"]) == "FAIL"


def test_gate_incomplete_blocks_pass():
    q = _all_pass_bqa()
    q.set("keyboard_navigation", "INCOMPLETE")
    assert q.overall(["chromium", "firefox", "webkit"]) != "PASS"


def test_gate_env_incomplete_blocks_pass():
    q = _all_pass_bqa()
    q.set("webkit_core", "ENV_INCOMPLETE")
    assert q.overall(["chromium", "firefox"]) != "PASS"


def test_gate_missing_browser_blocks_authoritative_pass():
    q = _all_pass_bqa()
    # even all-pass categories cannot be authoritative PASS without all three engines executed
    assert q.overall(["chromium"]) == "INCOMPLETE"


def test_absent_accessibility_cannot_silently_pass():
    q = _all_pass_bqa()
    del q.cats["accessibility_light"]
    assert q.overall(["chromium", "firefox", "webkit"]) != "PASS"


def test_absent_keyboard_and_visual_cannot_silently_pass():
    for cat in ("keyboard_navigation", "visual_stability"):
        q = _all_pass_bqa()
        del q.cats[cat]
        assert q.overall(["chromium", "firefox", "webkit"]) != "PASS"


def test_return_original_semantic_state_permitted_only_there():
    q = _all_pass_bqa()
    # SEMANTIC_BACKEND_COVERED on a NON-permitted category must not pass
    q.set("use_recommendation_all_buttons", "SEMANTIC_BACKEND_COVERED")
    assert q.overall(["chromium", "firefox", "webkit"]) != "PASS"


def test_required_category_count():
    assert len(O.REQUIRED_CATEGORIES) >= 55
    for must in ("accessibility_light", "accessibility_dark", "keyboard_navigation", "visual_stability",
                 "workflow_gating", "use_recommendation_all_buttons", "candidate_askwhy_exact_crop",
                 "bulk_accept_pending_only", "bulk_reject_pending_only", "final_ui_911_traversal",
                 "hard_refresh_known_limitation", "farmer_accept_ui", "farmer_reject_ui",
                 "renewed_accept_ui", "workflow_revision_guard", "consent_metrics_display",
                 "chromium_cross_engine", "firefox_cross_engine", "webkit_cross_engine"):
        assert must in O.REQUIRED_CATEGORIES


def test_absent_dark_accessibility_blocks_pass():
    q = _all_pass_bqa(); del q.cats["accessibility_dark"]
    assert q.overall(["chromium", "firefox", "webkit"]) != "PASS"


def test_shallow_cross_engine_blocks_authoritative_pass():
    # Firefox/WebKit that only loaded (core PASS) but did NOT run the cross-engine core cannot authorise PASS
    q = _all_pass_bqa()
    q.set("webkit_cross_engine", "INCOMPLETE")
    assert q.overall(["chromium", "firefox", "webkit"]) != "PASS"
    assert q.cross_engine_ok() is False


def test_all_engines_cross_pass_required_for_authority():
    q = _all_pass_bqa()
    assert q.cross_engine_ok() is True
    assert q.overall(["chromium", "firefox", "webkit"]) == "PASS"


# ---------------- §2A development smoke (Chromium, may be INCOMPLETE) ----------------
def test_dev_smoke_server_lifecycle():
    """Server starts on an ephemeral port and stops deterministically (port closed). No browser needed."""
    import farmsync_browser_lib as L
    s = L.QAServer(mode="isolated")
    s.start(timeout=45)
    assert s.port_open() is True
    ok = s.stop()
    assert ok is True and s.port_open() is False


# ---------------- §13 producer + no-vacuous authority self-tests (static, no browser) ----------------
import re as _re

_SRC = open(os.path.join(_ROOT, "scripts", "farmsync_browser_qa.py")).read()
_LIB_SRC = open(os.path.join(_ROOT, "tests", "farmsync_browser_lib.py")).read()


def _src_without_required_list():
    i = _SRC.index("REQUIRED_CATEGORIES = [")
    j = _SRC.index("]", i) + 1
    return _SRC.replace(_SRC[i:j], "")


def test_every_required_category_has_a_producer():
    rest = _src_without_required_list()
    missing = []
    for c in O.REQUIRED_CATEGORIES:
        has = ('"%s"' % c in rest) or ("'%s'" % c in rest)
        dynamic = c.endswith("_core") or c.endswith("_cross_engine")   # produced via %s templating per engine
        if not has and not dynamic:
            missing.append(c)
    assert missing == [], "required categories without a producer: %s" % missing


def test_obsolete_coarse_categories_removed():
    for obsolete in ('"farmer_response_ui"', '"renewed_consent_ui"', '"bulk_consent_pending_only"'):
        assert obsolete not in _SRC, "obsolete coarse category still present: %s" % obsolete
    # and they are not in the required set
    for c in ("farmer_response_ui", "renewed_consent_ui", "bulk_consent_pending_only"):
        assert c not in O.REQUIRED_CATEGORIES


def test_no_vacuous_count_ge_zero_assertions():
    assert "count() >= 0" not in _SRC


def test_hard_refresh_uses_browser_created_run():
    fn = _SRC.split("def _hard_refresh(")[1].split("\ndef ")[0]
    assert "_fresh_changed(server)" not in fn                  # must NOT use server-only run
    assert "current_run_id()" in fn and "_browser_changed_run" in fn or "click_ws(page, \"farmer\")" in fn


def test_cross_engine_contains_real_ui_mutations():
    fn = _SRC.split("def run_cross_engine(")[1].split("\ndef run_engine(")[0]
    assert "data-why-candidate" in fn                          # candidate Ask Why
    assert "[data-use]" in fn                                  # one Use click
    assert 'data-consent="ACCEPT"' in fn                       # renewed consent mutation
    assert "fs-filter" in fn                                   # Final filter interaction


def test_accessibility_helper_builds_populated_workflow():
    fn = _SRC.split("def _accessibility_theme(")[1].split("\ndef ")[0]
    # Home is scanned first; then one browser-owned populated/finalised run is built and
    # downstream stages are scanned without reloading Home (preserves WORK.runId).
    assert "A11Y_STAGES" in fn
    assert "goto_home(page, server)" in fn
    assert "_browser_changed_run" in fn
    assert "doFinalise" in fn
    assert "final_current" in fn


def test_responsive_computes_clipped_controls():
    fn = _SRC.split("def responsive(")[1].split("\ndef ")[0]
    assert 'vp["clipped_primary"] +=' in fn                    # actually computed, not left at 0


def test_bulk_split_categories_both_produced():
    fn = _SRC.split("def _bulk_pending_only(")[1].split("\ndef ")[0]
    assert '"bulk_accept_pending_only"' in fn and '"bulk_reject_pending_only"' in fn


def test_farmer_split_categories_all_produced():
    fn = _SRC.split("def _farmer_response_ui(")[1].split("\ndef ")[0]
    for c in ("farmer_accept_ui", "farmer_reject_ui", "farmer_modify_ui", "farmer_no_response_ui",
              "farmer_withdraw_ui", "farmer_exact_plot_binding", "farmer_reset_edit_ui", "farmer_askwhy_readonly"):
        assert c in fn, "farmer producer missing %s" % c


# ---------------- micro-patch self-tests: real Farmer selectors, all Use buttons, populated a11y ----------------
def test_farmer_producer_uses_real_product_selectors():
    fn = _SRC.split("def _farmer_response_ui(")[1].split("\ndef ")[0]
    helper = _SRC.split("def _farmer_action_ui(")[1].split("\ndef ")[0]
    openf = _SRC.split("def _farmer_open_first(")[1].split("\ndef ")[0]
    blob = fn + helper + openf
    assert ".fs-farmer-item" in blob
    assert 'data-act=' in blob
    assert "#wpSave" in blob
    assert "#wpReset" in blob
    assert "data-ai-use" in blob            # MODIFY requested_crop via real crop UI


def test_farmer_categories_not_hardcoded_incomplete():
    fn = _SRC.split("def _farmer_response_ui(")[1].split("\ndef ")[0]
    # must not blanket-set the action categories INCOMPLETE with a "no stable selector" reason
    assert "not addressable by a stable selector" not in fn
    # each farmer action category is produced through the real-UI helper (bqa.check inside _farmer_action_ui)
    helper = _SRC.split("def _farmer_action_ui(")[1].split("\ndef ")[0]
    assert 'working_response==%s' in helper or 'working_response == action' in helper or "working_response')" in helper


def test_use_buttons_not_only_first():
    fn = _SRC.split("def _use_buttons(")[1].split("\ndef ")[0]
    # exercises each discovered crop in an isolated scenario, not just uses.first
    assert "for crop in crops" in fn
    assert '[data-use="%s"]' in fn                 # targets the exact crop's button
    assert "exercised" in fn


def test_accessibility_builds_populated_finalised_workflow():
    fn = _SRC.split("def _accessibility_theme(")[1].split("\ndef ")[0]
    assert "_browser_changed_run" in fn           # dataset + changed rows + explicit Replan
    assert "consent-bulk" in fn                    # renewed consent completed
    assert "doFinalise" in fn                      # explicit Finalise before downstream scan


def test_a11y_stages_cover_full_workflow():
    for stage in ("home", "plan", "farmer", "replan", "consent", "final", "fairness", "uncertainty", "resilience", "data"):
        assert stage in O.A11Y_STAGES


# ---------------- final audit hardening: multi-plot, real Farmer AI, exhaustive Use, no a11y reload ----------------
def test_farmer_exact_binding_targets_same_farmer_sibling():
    helper = _SRC.split("def _farmer_action_ui(")[1].split("\ndef ")[0]
    opener = _SRC.split("def _farmer_open_first(")[1].split("\ndef ")[0]
    assert "f2 == fid and p2 != pid" in helper
    assert "counts.get(f, 0) >= 2" in opener


def test_farmer_modify_and_askwhy_use_real_ai_controls():
    fn = _SRC.split("def _farmer_response_ui(")[1].split("\ndef ")[0]
    assert '#aiMsg' in fn and '#askAiBtn' in fn
    assert "What else can I grow?" in fn
    assert "[data-ai-use]" in fn
    assert "[data-ai-why]" in fn
    assert "run_fingerprint" in fn


def test_use_buttons_exercises_every_discovered_crop_without_cap():
    fn = _SRC.split("def _use_buttons(")[1].split("\ndef ")[0]
    assert "for crop in crops:" in fn
    assert "crops[:6]" not in fn
    assert "exercised == len(crops)" in fn


def test_accessibility_does_not_reload_home_after_finalising():
    fn = _SRC.split("def _accessibility_theme(")[1].split("\ndef ")[0]
    # Home is scanned first; the browser-owned finalised run is then preserved for all downstream scans.
    assert 'results["home"]' in fn
    assert "_browser_changed_run" in fn
    assert "final_current" in fn
    assert 'if s != "home"' in fn
    assert "missing_or_unscanned" in fn


# ---------------- seed-gate execution semantics regression ----------------
def test_seeded_category_promotes_to_pass_when_real_check_executes():
    q = O.BQA()
    O._seed_required(q)
    assert q.status_of("workflow_gating") == "INCOMPLETE"
    q.check("workflow_gating", True, "executed successfully")
    assert q.status_of("workflow_gating") == "PASS"


def test_seeded_category_promotes_to_fail_when_real_check_fails():
    q = O.BQA()
    O._seed_required(q)
    q.check("workflow_gating", False, "executed and failed", defect=True)
    assert q.status_of("workflow_gating") == "FAIL"
    assert ("workflow_gating", "executed and failed") in q.defects


def test_merely_touching_seeded_category_does_not_fake_pass():
    q = O.BQA()
    O._seed_required(q)
    q.cat("workflow_gating")
    assert q.status_of("workflow_gating") == "INCOMPLETE"


# ---------------- report-driven harness regressions (Windows authoritative run 2026-09-09) ----------------
def test_run_engine_reestablishes_browser_run_after_isolated_farmer_matrix():
    fn = _SRC.split("def run_engine(")[1].split("\ndef main(")[0]
    # _farmer_response_ui intentionally cleans state for isolated action scenarios, so the linked
    # Replan -> Renewed Consent journey must not reuse the pre-Farmer rid.
    i = fn.index("_farmer_response_ui")
    j = fn.index("_replan_ui", i)
    between = fn[i:j]
    assert "_fresh_browser_run" in between
    assert "rid = _fresh_browser_run" in between


def test_external_network_gate_allows_only_shared_google_font_assets():
    assert '"fonts.googleapis.com"' in _SRC
    assert '"fonts.gstatic.com"' in _SRC
    assert "def _unexpected_external" in _SRC
    net = _SRC.split("def _network_console(")[1].split("\ndef ")[0]
    cross = _SRC.split("def run_cross_engine(")[1].split("\ndef run_engine(")[0]
    assert "_unexpected_external" in net
    assert "_unexpected_external" in cross
    # Authority still blocks any non-allowlisted external host.
    assert "unexpected external" in net.lower()


def test_responsive_clipping_ignores_intentional_horizontal_scroll_containers():
    fn = _SRC.split("def responsive(")[1].split("\ndef ")[0]
    assert "inHScroll" in fn
    assert "scrollWidth>p.clientWidth+2" in fn
    assert "ox==='auto'||ox==='scroll'" in fn
    assert "#fsApp" in fn


def test_accessibility_authority_is_scoped_to_farmsync_and_keeps_node_evidence():
    fn = _SRC.split("def _accessibility_theme(")[1].split("\ndef ")[0]
    assert 'context="#fsApp"' in fn
    assert "include_nodes=True" in fn
    assert "def run_axe(page, context=None, include_nodes=False" in _LIB_SRC
    assert "failureSummary" in _LIB_SRC and '"target"' in _LIB_SRC

def test_accessibility_theme_is_persisted_and_transition_settled_before_axe():
    fn = _SRC.split("def _accessibility_theme(")[1].split("\ndef ")[0]
    assert "localStorage.setItem('theme',t)" in fn
    assert "page.wait_for_timeout(700)" in fn
    assert 'context="#fsApp"' in fn


def test_return_original_requires_phase1_passed_semantic_evidence():
    # The helper parses persisted Phase-1 JSON; module-scope json import is required.
    assert "import json" in _SRC
    assert hasattr(O, "json")
    fn = _SRC.split("def _phase1_return_original_semantic_coverage(")[1].split("\ndef ")[0]
    assert 'qa_report_backend.json' in fn
    assert 'phase1_status' in fn and 'ready_for_phase_2' in fn
    assert 'consent_original_branch' in fn
    assert 'SEMANTIC_BACKEND_COVERED' in fn
    assert '_phase1_return_original_semantic_coverage(bqa)' in _SRC

# ---------------- visual-stability closure regression (Windows authoritative run 2026-09-09) ----------------
def test_visual_stability_uses_reduced_motion_to_remove_random_particle_noise():
    fn = _SRC.split("def visual_stability(")[1].split("\ndef ")[0]
    assert 'reduced_motion="reduce"' in fn
    assert 'animations="disabled"' in fn
    assert 'caret="hide"' in fn


def test_visual_stability_waits_for_fonts_before_capture():
    fn = _SRC.split("def visual_stability(")[1].split("\ndef ")[0]
    assert "document.fonts.ready" in fn
    assert "page.wait_for_timeout(150)" in fn



# ---------------- navigation scroll-reset regression (post-freeze UI correction) ----------------
def _pw_available():
    try:
        from playwright.sync_api import sync_playwright  # noqa
        import farmsync_browser_lib as L  # noqa
        return True
    except Exception:
        return False


import pytest as _pytest


@_pytest.mark.skipif(not _pw_available(), reason="playwright/browser lib unavailable")
def test_navigation_resets_scroll_to_farmsync_top_desktop_and_mobile():
    """After Next / Previous / direct tab navigation, the new active FarmSync panel must land at the
    FarmSync workflow anchor (#fsWorkflow below the sticky header), NOT inherit the previous tab's scroll position and NOT
    jump to the global site header. Verified on desktop and mobile viewports, with active-tab/panel
    correctness, no horizontal overflow, focus/a11y unchanged, single (non-duplicated) navigation, and no
    smooth-scroll timing dependency."""
    import farmsync_browser_lib as L
    from playwright.sync_api import sync_playwright

    s = L.QAServer(mode="real")
    s.start(45)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for vp, label in ((({"width": 1280, "height": 700}), "desktop"),
                              (({"width": 390, "height": 844}), "mobile")):
                ctx = b.new_context(viewport=vp)
                pg = ctx.new_page()
                # count activate()-driven history.replaceState calls (one per navigation) to prove the
                # scroll fix introduces no duplicate/re-entrant navigation.
                pg.add_init_script("window.__navCount = 0; const _rs = history.replaceState.bind(history);"
                                   " history.replaceState = function(){ window.__navCount++; return _rs.apply(history, arguments); };")
                js_errors = []          # JS exceptions — strict (must be empty)
                console_errors = []     # console errors — filtered for environmental 404 asset noise
                pg.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
                pg.on("pageerror", lambda e: js_errors.append(str(e)))
                pg.goto(s.base_url + "/farm-sync", wait_until="networkidle")
                pg.click("#homeUseBuiltin"); pg.wait_for_timeout(400)
                pg.evaluate("window.__navCount = 0")   # count only the test navigations below

                def workflow_top():
                    return pg.evaluate("() => Math.round(document.getElementById('fsWorkflow').getBoundingClientRect().top)")

                def h_overflow():
                    return pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")

                def active_ok(ws):
                    return pg.evaluate("""(ws) => {
                        const btn = document.querySelector('.fs-navbtn[data-ws="'+ws+'"]');
                        const panel = document.getElementById('ws-'+ws);
                        const others = [...document.querySelectorAll('.fs-ws')].filter(s => s.id !== 'ws-'+ws);
                        return !!btn && btn.classList.contains('is-active')
                            && !!panel && panel.classList.contains('is-active')
                            && others.every(s => !s.classList.contains('is-active'));
                    }""", ws)

                nav_count_expected = {"n": 0}

                def _scroll_current_to_bottom():
                    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    pg.wait_for_timeout(120)
                    return pg.evaluate("() => window.scrollY")

                def go_strict(ws, from_scrolled=True):
                    """Navigate to a SYNC panel; assert it lands exactly at the FarmSync top and (when the
                    source was scrollable) that the scroll was actually reset. Waits deterministically for
                    workspace activation, loader settlement (.fs-loading gone), and the post-render scroll
                    to land — no fixed sleep (Windows /working-plan/start can be slow)."""
                    before = _scroll_current_to_bottom()
                    pg.locator('.fs-navbtn[data-ws="%s"]' % ws).first.click()
                    # 1) workspace becomes active
                    pg.wait_for_function(
                        "(ws) => { const p = document.getElementById('ws-' + ws);"
                        " return !!p && p.classList.contains('is-active'); }", arg=ws, timeout=5000)
                    # 2) loader settled: no .fs-loading spinner remains in the active panel
                    pg.wait_for_function(
                        "(ws) => { const p = document.getElementById('ws-' + ws);"
                        " return !!p && !p.querySelector('.fs-loading'); }", arg=ws, timeout=5000)
                    # 3) deterministic post-render scroll landed at the workflow/progress anchor.
                    pg.wait_for_function(
                        "() => { const t=document.getElementById('fsWorkflow').getBoundingClientRect().top; return t >= 70 && t <= 140; }",
                        timeout=5000)
                    top = workflow_top()
                    print("   [%s] nav %-6s -> final #fsWorkflow top = %d" % (label, ws, top))
                    assert 70 <= top <= 140, "%s: nav to %s did not land at workflow anchor (top=%d)" % (label, ws, top)
                    if from_scrolled and before > 5:
                        assert top < before, "%s: nav to %s did not reset scroll (before=%d top=%d)" % (label, ws, before, top)
                    assert active_ok(ws), "%s: active tab/panel incorrect after nav to %s" % (label, ws)
                    assert not h_overflow(), "%s: horizontal overflow introduced after nav to %s" % (label, ws)
                    nav_count_expected["n"] += 1

                def go_reset_only(ws):
                    """Navigate to Data Explorer and wait for its nested async table load to settle.
                    Data Explorer must obey the same workflow-anchor landing contract as the workflow panels."""
                    before = _scroll_current_to_bottom()
                    pg.locator('.fs-navbtn[data-ws="%s"]' % ws).first.click()
                    # Workspace shell is active and its outer validation loader has settled.
                    pg.wait_for_function(
                        "(ws) => { const p = document.getElementById('ws-' + ws);"
                        " return !!p && p.classList.contains('is-active') && !p.querySelector('.fs-loading'); }",
                        arg=ws, timeout=5000)
                    # Data Explorer has a nested async fetch for table metadata + first page.
                    # Wait for the pager text, which is written only after that first page resolves.
                    pg.wait_for_function(
                        "() => { const p = document.querySelector('#ws-data #exPageInfo');"
                        " return !!p && p.textContent.trim().length > 0; }",
                        timeout=5000)
                    # The explorer must not override activate()'s workflow-anchor navigation position.
                    pg.wait_for_function(
                        "() => { const t=document.getElementById('fsWorkflow').getBoundingClientRect().top; return t >= 70 && t <= 140; }",
                        timeout=5000)
                    top = workflow_top()
                    print("   [%s] nav %-6s -> final #fsWorkflow top = %d (from scrollY %d)" % (label, ws, top, before))
                    assert 70 <= top <= 140, "%s: nav to %s did not land at workflow anchor (top=%d)" % (label, ws, top)
                    if before > 5:
                        assert top < before, "%s: nav to %s did not reset scroll (before=%d top=%d)" % (label, ws, before, top)
                    assert active_ok(ws), "%s: active tab/panel incorrect after nav to %s" % (label, ws)
                    assert not h_overflow(), "%s: horizontal overflow introduced after nav to %s" % (label, ws)
                    nav_count_expected["n"] += 1

                # Reach the tall 'plan' panel first (home is short -> no scroll precondition there).
                go_strict("plan", from_scrolled=False)
                # From the scrolled-down tall 'plan', SYNC targets must land exactly at the FarmSync top:
                go_strict("final30")      # direct advanced-results navigation
                go_strict("plan")         # back to tall panel ("Previous"-style)
                go_strict("home")         # direct nav to a different sync panel
                go_strict("plan")         # return to the tall panel
                # ASYNC data-explorer: prove the inherited deep scroll is reset (its own mount may re-position).
                go_reset_only("data")

                # focus/a11y unchanged: active panel remains focusable (tabindex=-1 preserved)
                ti = pg.evaluate("() => document.getElementById('ws-data').getAttribute('tabindex')")
                assert ti == "-1", "%s: active panel focusability changed" % label

                # exactly one hashchange per navigation -> no duplicate navigation event
                nav_count = pg.evaluate("() => window.__navCount")
                assert nav_count == nav_count_expected["n"], (
                    "%s: expected %d navigations, got %s (duplicate nav?)" % (label, nav_count_expected["n"], nav_count))
                # No JS exceptions from navigation (strict). The isolated QA base template does not serve
                # every static asset (favicon/fonts), so 404 resource-load console noise is environmental and
                # excluded here; the authoritative real-site Phase-2 run validates console/network fully.
                assert not js_errors, "%s: JS exceptions during navigation: %s" % (label, js_errors[:3])
                real_console = [e for e in console_errors if "Failed to load resource" not in e and "404" not in e]
                assert not real_console, "%s: unexpected console errors during navigation: %s" % (label, real_console[:3])
                ctx.close()
            b.close()
    finally:
        s.stop()


def test_activate_uses_auto_not_smooth_scroll():
    """Static guard: the scroll reset must use behavior:'auto' (no smooth-scroll timing dependency) and
    target the workflow/progress anchor #fsWorkflow (not the hero or global document top)."""
    src = open(os.path.join(_ROOT, "static", "js", "farmsync.js")).read()
    act = src.split("function activate(ws, options = {})")[1].split("function ")[0]
    assert 'getElementById("fsWorkflow")' in act
    assert 'scrollIntoView({ behavior: "auto", block: "start" })' in act
    assert "smooth" not in act.split("scrollIntoView")[1][:60]
    # not a blind window.scrollTo(0,0) that would land on the global header
    assert "window.scrollTo(0, 0)" not in act and "scrollTo(0,0)" not in act


@_pytest.mark.skipif(not _pw_available(), reason="playwright/browser lib unavailable")
def test_change_dataset_modal_matches_records_insight_and_mobile_safe():
    """FarmSync confirmation uses the Records Insight floating-card geometry/motion on desktop and
    mobile, keeps BOTH controls visible, and introduces no page/button overflow."""
    import farmsync_browser_lib as L
    from playwright.sync_api import sync_playwright

    s = L.QAServer(mode="real")
    s.start(45)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for vp, label in ((({"width": 1280, "height": 720}), "desktop"),
                              (({"width": 390, "height": 844}), "mobile"),
                              (({"width": 360, "height": 740}), "small-mobile")):
                ctx = browser.new_context(viewport=vp)
                pg = ctx.new_page()
                errors = []
                pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.goto(s.base_url + "/farm-sync", wait_until="networkidle")
                pg.click("#homeUseBuiltin")
                pg.wait_for_timeout(250)
                pg.click("#homeChangeDataset")
                pg.wait_for_selector("#fsConfirmModal.fs-modal-visible", state="visible")
                pg.wait_for_function(
                    """() => {
                        const c = document.querySelector("#fsConfirmModal .fs-modal-card");
                        return c && parseFloat(getComputedStyle(c).opacity) > 0.95;
                    }"""
                )

                m = pg.evaluate("""() => {
                    const o = document.getElementById('fsConfirmModal');
                    const c = o.querySelector('.fs-modal-card');
                    const r = c.getBoundingClientRect();
                    const cs = getComputedStyle(c);
                    const ors = getComputedStyle(o);
                    const buttons = [...c.querySelectorAll('.fs-modal-actions .fs-modal-btn')].map(b => {
                      const br=b.getBoundingClientRect(); const bs=getComputedStyle(b);
                      return {left:br.left,right:br.right,top:br.top,bottom:br.bottom,
                              width:br.width,height:br.height,display:bs.display,visibility:bs.visibility,
                              opacity:parseFloat(bs.opacity)};
                    });
                    return {
                      left:r.left, right:r.right, top:r.top, bottom:r.bottom, width:r.width, height:r.height,
                      radius:parseFloat(cs.borderTopLeftRadius), border:parseFloat(cs.borderTopWidth),
                      opacity:parseFloat(cs.opacity), textAlign:cs.textAlign,
                      overlayAlign:ors.alignItems,
                      overflow:document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                      buttonCount:buttons.length,
                      buttons,
                      buttonOverflow:buttons.some(b => b.left < r.left - 1 || b.right > r.right + 1 || b.top < r.top - 1 || b.bottom > r.bottom + 1),
                      centerDelta:Math.abs(((r.top+r.bottom)/2) - (innerHeight/2))
                    };
                }""")
                assert m["radius"] >= 20, "%s: modal lost rounded floating-card shape: %s" % (label, m)
                assert m["border"] == 2, "%s: modal does not match Records Insight 2px card border: %s" % (label, m)
                assert m["textAlign"] == "center", "%s: modal content is not Records Insight centered: %s" % (label, m)
                assert m["overlayAlign"] == "center", "%s: modal became a bottom sheet: %s" % (label, m)
                assert m["left"] >= 8 and m["right"] <= vp["width"] - 8, "%s: modal clips horizontally: %s" % (label, m)
                assert m["top"] >= 8 and m["bottom"] <= vp["height"] - 8, "%s: modal clips vertically: %s" % (label, m)
                assert m["centerDelta"] <= 80, "%s: modal is not visually centered: %s" % (label, m)
                assert m["buttonCount"] == 2, "%s: expected both modal controls, got: %s" % (label, m)
                assert all(b["display"] != "none" and b["visibility"] == "visible" and b["opacity"] > .95 and b["width"] >= 120 for b in m["buttons"]), ("%s: one of the modal controls is not visibly rendered: %s" % (label, m))
                assert not m["overflow"] and not m["buttonOverflow"], "%s: modal introduces overflow: %s" % (label, m)
                assert m["opacity"] > .95, "%s: modal did not finish Records Insight pop-in: %s" % (label, m)

                pg.click("#fsConfirmModal .fs-modal-cancel")
                pg.wait_for_function("() => { const m=document.getElementById('fsConfirmModal'); return !!m && m.classList.contains('fs-modal-exiting') && !m.classList.contains('fs-modal-visible'); }")
                pg.wait_for_selector("#fsConfirmModal", state="detached", timeout=2000)
                assert not errors, "%s: JS exceptions during modal interaction: %s" % (label, errors[:3])
                ctx.close()
            browser.close()
    finally:
        s.stop()



@_pytest.mark.skipif(not _pw_available(), reason="playwright/browser lib unavailable")
def test_initial_farmsync_landing_stays_at_page_top():
    """A normal /farm-sync visit must show the hero, not auto-scroll to the workflow bar."""
    import farmsync_browser_lib as L
    from playwright.sync_api import sync_playwright

    s = L.QAServer(mode="real")
    s.start(45)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()

            for viewport, label in (
                ({"width": 1280, "height": 700}, "desktop"),
                ({"width": 390, "height": 844}, "mobile"),
            ):
                ctx = browser.new_context(viewport=viewport)
                pg = ctx.new_page()

                pg.goto(s.base_url + "/farm-sync", wait_until="networkidle")
                pg.wait_for_timeout(150)

                scroll_y = pg.evaluate("() => Math.round(window.scrollY)")
                workflow_top = pg.evaluate(
                    "() => Math.round(document.getElementById('fsWorkflow').getBoundingClientRect().top)"
                )

                assert scroll_y <= 2, (
                    "%s: initial FarmSync visit auto-scrolled to y=%s"
                    % (label, scroll_y)
                )

                assert workflow_top > 0, (
                    "%s: workflow bar should remain below the initial viewport origin"
                    % label
                )

                ctx.close()

            browser.close()
    finally:
        s.stop()
