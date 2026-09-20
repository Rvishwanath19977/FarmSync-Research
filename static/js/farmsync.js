/* FarmSync guided research workbench — product journey, causal sequencing, correct AI role.
   Recorded research artifacts are read-only; the Farmer Responses stage adds an ISOLATED, editable
   working-plan layer (responses, requested crop, rejected alternatives) that never writes the source
   dataset or any frozen artifact. No scientific calculation, no solver (CBC/PuLP) and no live LLM run
   on page load or GET. Semantic colours come from theme-scoped CSS only — no colour hex in JS. */
(function () {
  "use strict";
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const rup = (n) => (n == null ? "&mdash;" : "\u20B9" + Math.round(Number(n)).toLocaleString("en-IN"));
  const pct = (n) => (n == null ? "&mdash;" : (Number(n) * 100).toFixed(1) + "%");
  const api = (p) => fetch(p, { headers: { "Accept": "application/json" } }).then(r => r.json());
  const loading = (el) => { el.innerHTML = '<div class="fs-loading"><span class="fs-spinner"></span>Loading&hellip;</div>'; };
  const errbox = (el, m) => { el.innerHTML = '<div class="fs-errbox">Could not load: ' + esc(m) + '</div>'; };
  const naTag = (s) => '<span class="fs-run notrun">' + esc(s || "Not available") + '</span>';
  const devProv = '<span class="fs-prov">Development checkpoint</span>';
  const empty = (msg, cta) => '<div class="fs-panel"><div class="fs-empty"><p>' + esc(msg) + '</p>' + (cta || "") + '</div></div>';
  const mtile = (k, v, sub) => '<div class="fs-metric"><div class="k">' + k + '</div><div class="v">' + (v == null ? "&mdash;" : v) + '</div>' + (sub ? '<div class="sub">' + sub + '</div>' : "") + '</div>';
  // stage teaching block: what / why / result / meaning
  const teach = (o) => '<div class="fs-teach">' +
    (o.what ? '<div class="fs-teach-row"><span class="fs-teach-k">What</span><span>' + o.what + '</span></div>' : "") +
    (o.why ? '<div class="fs-teach-row"><span class="fs-teach-k">Why</span><span>' + o.why + '</span></div>' : "") +
    (o.result ? '<div class="fs-teach-row"><span class="fs-teach-k">What happened</span><span>' + o.result + '</span></div>' : "") +
    (o.meaning ? '<div class="fs-teach-row"><span class="fs-teach-k">What it means</span><span>' + o.meaning + '</span></div>' : "") +
    '</div>';
  const nextCta = (label, ws) => '<div class="fs-cta-row fs-next"><span class="fs-next-k">Next</span><button class="fs-btn fs-btn-primary" data-ws="' + ws + '">' + esc(label) + '</button></div>';
  const advancedNext = (label, ws) => '<div class="fs-cta-row fs-advanced-next"><button class="fs-btn" data-ws="' + ws + '">' + esc(label) + '</button></div>';

  /* ---------- FarmSync modal (Records Insight interaction pattern, FarmSync theme) ---------- */
  function fsConfirm(message, onConfirm, opts) {
    const o = opts || {};
    const root = document.body;
    const previous = document.getElementById("fsConfirmModal");
    if (previous) previous.remove();

    const overlay = document.createElement("div");
    const titleId = "fsConfirmTitle";
    overlay.id = "fsConfirmModal";
    overlay.className = "fs-modal-overlay";
    overlay.innerHTML =
      '<div class="fs-modal-card" role="dialog" aria-modal="true" aria-labelledby="' + titleId + '">' +
      '<div class="fs-modal-accent-bar"></div>' +
      '<div class="fs-modal-icon ' + (o.warning ? 'warning' : 'info') + '" aria-hidden="true">' +
      (o.warning
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 1 1 5.8 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>') +
      '</div>' +
      '<h3 class="fs-modal-title" id="' + titleId + '">' + esc(o.title || "Please confirm") + '</h3>' +
      '<p class="fs-modal-text">' + esc(message) + '</p>' +
      '<div class="fs-modal-actions">' +
      '<button class="fs-modal-btn fs-modal-btn-ghost fs-modal-cancel" type="button">' + esc(o.cancelText || "Cancel") + '</button>' +
      '<button class="fs-modal-btn fs-modal-confirm" type="button">' + esc(o.confirmText || "Confirm") + '</button>' +
      '</div></div>';

    const priorFocus = document.activeElement;
    let closed = false;
    function dismiss(confirmed) {
      if (closed) return;
      closed = true;
      overlay.classList.add("fs-modal-exiting");
      overlay.classList.remove("fs-modal-visible");
      document.removeEventListener("keydown", onKey);
      setTimeout(() => {
        if (overlay.parentNode) overlay.remove();
        if (!confirmed && priorFocus && priorFocus.focus) priorFocus.focus();
      }, 500);
      if (confirmed && typeof onConfirm === "function") onConfirm();
    }
    function onKey(e) {
      if (e.key === "Escape") { e.preventDefault(); dismiss(false); return; }
      if (e.key === "Enter" && document.activeElement !== overlay.querySelector(".fs-modal-cancel")) {
        e.preventDefault(); dismiss(true); return;
      }
      if (e.key !== "Tab") return;
      const focusable = Array.from(overlay.querySelectorAll("button:not([disabled])"));
      if (!focusable.length) return;
      const first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }

    overlay.querySelector(".fs-modal-cancel").addEventListener("click", () => dismiss(false));
    overlay.querySelector(".fs-modal-confirm").addEventListener("click", () => dismiss(true));
    overlay.addEventListener("click", e => { if (e.target === overlay) dismiss(false); });
    document.addEventListener("keydown", onKey);
    root.appendChild(overlay);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      overlay.classList.add("fs-modal-visible");
      const focusTarget = overlay.querySelector(".fs-modal-confirm");
      if (focusTarget) focusTarget.focus();
    }));
  }

  function explainLockedStage(ws) {
    const wf = (WORK && WORK.data && WORK.data.workflow) || {};
    const pending = Number(wf.n_consent_pending || 0);
    if (ws === "final" && pending > 0) {
      fsConfirm(
        pending + " changed recommendation" + (pending === 1 ? " still needs" : "s still need") +
        " a renewed-consent decision. Record Accept, Reject, or No response for every pending changed recommendation before continuing to Final Plan.",
        () => activate("consent"),
        { title: "Renewed consent incomplete", confirmText: "Review renewed consent", cancelText: "Stay here" }
      );
      return true;
    }
    return false;
  }

  /* ---------- progressive-disclosure state (session/UI; no solver) ---------- */
  const ALWAYS = ["home", "data", "final30", "uncresults", "sensitivity", "scale", "reliability", "scenario", "repro"];
  const ANALYSE_WS = ["fairness", "uncertainty", "resilience"];
  const LOCK_HINT = {
    plan: "Choose a dataset first", farmer: "View the initial plan first", replan: "Review farmer responses first",
    consent: "Run the replan first", final: "Verify renewed consent first",
    fairness: "Finalise the plan first", uncertainty: "Finalise the plan first", resilience: "Finalise the plan first",
  };
  // a dataset MUST be explicitly chosen/activated before Initial Plan (or any downstream stage) unlocks.
  let DATASET = null;              // { kind:'builtin'|'custom', label, farmers, plots, collectives, version, hash }
  // AUTHORITATIVE workflow access is derived from server run state (WORK.data.workflow.stages), NOT from
  // local booleans. The only local gate is "a planning dataset has been chosen" (plan-gate), which is
  // itself server-backed (planning_source) and mirrored by DATASET for immediate UI.
  function wfStages() { return (WORK.data && WORK.data.workflow && WORK.data.workflow.stages) || null; }
  const isUnlocked = (ws) => {
    if (ALWAYS.includes(ws)) return true;
    if (!DATASET) return false;                 // nothing downstream until a dataset is chosen
    if (ws === "plan") return true;             // dataset chosen => Initial Plan available
    const st = wfStages();
    // 0A: before a working run/Initial Plan exists, ONLY Initial Plan is available. Farmer Responses
    // must not be reachable merely because a dataset is selected (opening it must not bypass the plan).
    if (!st) return false;
    if (ANALYSE_WS.includes(ws)) return !!st.analyse;
    return !!st[ws];
  };
  // unlock() is retained as a NO-OP shim so legacy call sites do not throw; it is NOT a source of truth.
  // Stage access always re-derives from server state; we just re-render the nav/stepper.
  function unlock(_stage) { renderNavLocks(); renderWorkflow(); }

  /* ---------- workflow stepper (Home outside; no Data step) ---------- */
  const WF = [["Initial Plan", "plan"], ["Farmer Responses", "farmer"], ["Replan", "replan"], ["Consent", "consent"], ["Finalise", "final"], ["Analyse", "fairness"]];
  const WF_GATE = ["plan", "farmer", "replan", "consent", "final", "analyse"];
  let wfCurrent = 0;
  const stepOpen = (i) => isUnlocked(WF_GATE[i] === "analyse" ? "fairness" : WF_GATE[i]);
  function renderWorkflow() {
    const host = $("#fsWorkflow"); if (!host) return;
    const pctW = (wfCurrent / (WF.length - 1)) * 100;
    host.innerHTML = '<div class="fs-stepper"><div class="fs-stepper-track"><div class="fs-stepper-progress" style="width:' + pctW + '%"></div></div><div class="fs-stepper-steps">' +
      WF.map((w, i) => {
        const open = stepOpen(i), cls = i < wfCurrent ? "done" : (i === wfCurrent ? "current" : "future"), locked = !open && i > wfCurrent;
        return '<button class="fs-step ' + cls + (locked ? " locked" : "") + '"' + (locked ? ' disabled aria-disabled="true" title="' + esc(LOCK_HINT[w[1]] || "Locked") + '"' : ' data-ws="' + w[1] + '"') + ' data-wf="' + i + '"><span class="fs-step-ind">' + (i < wfCurrent ? "\u2713" : (locked ? lockGlyph() : (i + 1))) + '</span><span class="fs-step-label">' + esc(w[0]) + '</span></button>';
      }).join("") + '</div></div>';
  }
  const lockGlyph = () => '<svg class="fs-lockico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';
  const WF_IDX = { plan: 0, farmer: 1, replan: 2, consent: 3, final: 4, fairness: 5, uncertainty: 5, resilience: 5 };
  function setWf(ws) { if (ws in WF_IDX) { wfCurrent = WF_IDX[ws]; renderWorkflow(); } }

  /* ---------- navigation ---------- */
  const loaded = {}, loaders = {};
  function renderNavLocks() {
    $$(".fs-navbtn").forEach(b => {
      const ws = b.dataset.ws, locked = !isUnlocked(ws);
      b.classList.toggle("is-locked", locked); b.disabled = locked;
      if (locked) { b.setAttribute("aria-disabled", "true"); b.title = LOCK_HINT[ws] || "Locked until reached"; b.dataset.locked = "1"; }
      else { b.removeAttribute("aria-disabled"); b.removeAttribute("title"); delete b.dataset.locked; }
      let ic = b.querySelector(".fs-nav-lock");
      if (locked && !ic) b.insertAdjacentHTML("beforeend", '<span class="fs-nav-lock">' + lockGlyph() + '</span>');
      else if (!locked && ic) ic.remove();
    });
  }
  let activeWs = "home";
  // A11y (WCAG / axe scrollable-region-focusable): a table wrapper that actually overflows must be
  // keyboard-focusable so keyboard users can scroll it. Decorate ONLY .fs-tablewrap regions that genuinely
  // overflow (a non-overflowing wrapper is left alone — no extra tab stops). Presentation/read-only only:
  // no state mutation. Runs after renders and on async/paginated re-renders via a MutationObserver.
  function _a11yDecorateScrollRegions(root) {
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll(".fs-tablewrap").forEach(function (w) {
      var overflow = (w.scrollWidth > w.clientWidth + 1) || (w.scrollHeight > w.clientHeight + 1);
      if (overflow) {
        if (w.getAttribute("tabindex") === null) w.setAttribute("tabindex", "0");
        if (w.getAttribute("role") === null) w.setAttribute("role", "region");
        if (!w.getAttribute("aria-label")) w.setAttribute("aria-label", "Scrollable data table");
      } else if (w.getAttribute("data-a11y-scroll") !== "keep") {
        // if it later fits, drop the tab stop we added (never a stale focusable non-scrolling region)
        if (w.getAttribute("role") === "region") { w.removeAttribute("tabindex"); w.removeAttribute("role"); w.removeAttribute("aria-label"); }
      }
    });
  }
  var _a11yScrollScheduled = false;
  function _a11yScheduleScrollDecorate() {
    if (_a11yScrollScheduled) return;
    _a11yScrollScheduled = true;
    (window.requestAnimationFrame || function (f) { setTimeout(f, 16); })(function () {
      _a11yScrollScheduled = false;
      _a11yDecorateScrollRegions(document);
    });
  }
  try {
    var _a11yObs = new MutationObserver(function () { _a11yScheduleScrollDecorate(); });
    _a11yObs.observe(document.documentElement, { childList: true, subtree: true });
    (window.addEventListener) && window.addEventListener("resize", _a11yScheduleScrollDecorate);
  } catch (e) { /* MutationObserver unavailable: decoration still runs after each activate() */ }

  function activate(ws, options = {}) {
    if (!isUnlocked(ws)) { flashLock(ws); return; }
    const shouldScroll = options.scroll !== false;
    activeWs = ws;
    $$(".fs-navbtn").forEach(b => b.classList.toggle("is-active", b.dataset.ws === ws));
    $$(".fs-ws").forEach(s => s.classList.toggle("is-active", s.id === "ws-" + ws));
    setWf(ws);
    const panel = $("#ws-" + ws);
    let _loadResult = null;
    if (panel && loaders[ws]) { loaded[ws] = true; _loadResult = loaders[ws](panel); }
    _a11yScheduleScrollDecorate();
    // Land at the workflow/progress bar rather than the global FarmSync hero. CSS scroll-margin-top
    // keeps the stepper visible below the sticky site header on desktop and mobile.
    const _scrollWorkbench = () => {
      const anchor = document.getElementById("fsWorkflow");
      if (anchor && anchor.scrollIntoView) anchor.scrollIntoView({ behavior: "auto", block: "start" });
    };
    if (shouldScroll) {
      _scrollWorkbench();
      if (_loadResult && typeof _loadResult.then === "function") {
        _loadResult.then(_scrollWorkbench).catch(() => {});
      }
    }
    if (history.replaceState) history.replaceState(null, "", "#" + ws);
  }
  function flashLock(ws) {
    if (explainLockedStage(ws)) return;
    const b = $('.fs-navbtn[data-ws="' + ws + '"]');
    if (!b) return;
    b.classList.add("fs-locked-shake");
    setTimeout(() => b.classList.remove("fs-locked-shake"), 500);
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-ws]"); if (!b) return; if (b.disabled || b.dataset.locked) { e.preventDefault(); flashLock(b.dataset.ws); return; } activate(b.dataset.ws); });

  /* ---------- dataset choice gate: nothing downstream until a dataset is chosen ---------- */
  function chooseDataset(ds) {
    // switching datasets must reset the working plan + relock everything downstream
    resetWorkingState();     // §"dataset change": fully detach the previous workflow (run id + state)
    DATASET = ds;            // dataset chosen => Initial Plan available; downstream from server workflow
    wfCurrent = 0;
    renderNavLocks(); renderWorkflow();
    if (activeWs === "home") loaders.home($("#ws-home"));
  }
  function resetDataset() {
    // explicit server call clears planning_source (historical snapshots are NOT deleted)
    fetch("/api/farmsync/change-dataset", { method: "POST" }).catch(() => {});
    resetWorkingState(); DATASET = null; wfCurrent = 0;
    renderNavLocks(); renderWorkflow();
    activate("home"); loaders.home($("#ws-home"));
  }
  function resetWorkingState() {
    WORK.runId = null; WORK.data = null; S.farmer = null; S.plot = null; FINAL_PAGE = 1;
  }
  function dataSourceLine() {
    if (!DATASET) return "";
    const label = DATASET.kind === "builtin" ? "FarmSync research dataset"
      : "Custom dataset" + (DATASET.version ? " \u00b7 " + esc(DATASET.version) : "");
    return '<p class="fs-source-line fs-muted">Data source: ' + label + '</p>';
  }

  /* ================= HOME — three entry paths ================= */
  loaders.home = (el) => {
    if (DATASET) { renderHomeSelected(el); return; }
    loading(el);
    Promise.all([api("/api/farmsync/dataset-summary"), api("/api/farmsync/overview")]).then(([d, ov]) => {
      const st = ov.experiment_state || {};
      el.innerHTML =
        '<div class="fs-panel"><span class="fs-h-eyebrow">Get started</span><h2>First, choose your data</h2>' +
        '<p class="fs-lede">Every stage &mdash; Initial Plan, Farmer Responses, Replan, Renewed Consent, Final Plan, Analyse &mdash; runs on the dataset you choose here. Pick one to begin.</p>' +
        '<div class="fs-paths">' +
        '<div class="fs-path fs-path-primary"><div class="fs-path-badge">Recommended</div><h3>Use the FarmSync research dataset</h3>' +
        '<p>A validated synthetic research dataset. Nothing to upload &mdash; start the full workflow straight away.</p>' +
        '<div class="fs-path-stat"><span class="fs-run optimal">Validated</span> ' + esc(d.farmers) + ' farmers &middot; ' + esc(d.plots) + ' plots</div>' +
        '<div class="fs-card-actions"><button class="fs-btn fs-btn-primary" id="homeUseBuiltin">Use built-in dataset</button></div></div>' +
        '<div class="fs-path"><h3>Use my own data</h3><p>Upload farmer / plot / collective files (built-in supporting parameters reused) or a complete FarmSync package. Data is validated and activated right here before planning.</p>' +
        '<p class="fs-path-flow">Upload &rarr; Validate &rarr; Review &rarr; Activate &rarr; Plan</p>' +
        '<div class="fs-card-actions"><button class="fs-btn fs-btn-primary" id="homeUseCustom">Use my own data</button><button class="fs-btn" id="homeReq">View data requirements</button></div><div id="homeReqBox"></div></div>' +
        '</div>' +
        '<div id="homeDmMount" hidden style="margin-top:16px"></div>' +
        '<p class="fs-hint fs-muted" style="margin-top:14px">Initial Plan and every later stage stay locked until a dataset is chosen here. Configuration, seeds, hashes and publication status live under <b>Advanced &rsaquo; Research details &amp; reproducibility</b>. To just browse the data without planning, use <b>Data Explorer</b>.</p></div>' +
        '<div class="fs-panel fs-disclose"><div class="fs-disclose-row"><span class="fs-badge fs-badge-final">FINAL30 SEALED</span><span class="fs-muted">Final30: <b>' + esc(st.final30 || "Not available") + '</b> &middot; LLM QA: <b>' + esc(st.llm_live || "Not available") + '</b>. Frozen publication evidence is under <b>Advanced</b>; the main workflow remains an interactive current-run tool.</span></div></div>';
      const ub = $("#homeUseBuiltin"); if (ub) ub.addEventListener("click", () => selectBuiltinOnHome());
      const uc = $("#homeUseCustom"); if (uc) uc.addEventListener("click", () => { mountDM($("#homeDmMount"), { mode: "select" }); });
      const rb = $("#homeReq"); if (rb) rb.addEventListener("click", () => renderRequirements($("#homeReqBox")));
    }).catch(e => errbox(el, e.message));
  };
  function selectBuiltinOnHome() {
    fetch("/api/farmsync/select-builtin", { method: "POST" }).then(r => r.json()).then(m => {
      const d = m.dataset_summary || {};
      chooseDataset({ kind: "builtin", label: "FarmSync research dataset", farmers: d.farmers, plots: d.plots, collectives: d.collectives });
    }).catch(() => {});
  }
  function renderHomeSelected(el) {
    const d = DATASET;
    const meta = d.kind === "builtin"
      ? esc(d.farmers) + " farmers &middot; " + esc(d.plots) + " plots"
      : esc(d.farmers) + " farmers &middot; " + esc(d.plots) + " plots" + (d.collectives != null ? " &middot; " + esc(d.collectives) + " collectives" : "") + (d.hash ? ' &middot; <span class="mono">' + esc(d.hash) + "</span>" : "");
    const title = d.kind === "builtin" ? "FarmSync research dataset selected" : "Custom dataset selected" + (d.version ? " &middot; " + esc(d.version) : "");
    el.innerHTML =
      '<div class="fs-panel"><span class="fs-h-eyebrow">Dataset selected \u2713</span><h2>' + title + '</h2>' +
      '<div class="fs-dataset-picked"><span class="fs-run optimal">Ready</span> <span class="fs-dsctx-meta">' + meta + '</span></div>' +
      '<div class="fs-note-box info" style="margin-top:10px">Every planning stage now uses this dataset. Built-in supporting parameters are reused for custom uploads.</div>' +
      '<div class="fs-cta-row" style="margin-top:14px"><button class="fs-btn fs-btn-primary" data-ws="plan">Continue to Initial Plan &rarr;</button><button class="fs-btn" id="homeChangeDataset">Change dataset</button></div></div>';
    const cd = $("#homeChangeDataset"); if (cd) cd.addEventListener("click", () => requestChangeDataset());
  }
  function requestChangeDataset() {
    const hasWork = !!(WORK && WORK.runId);
    const message = hasWork
      ? "Changing the dataset will reset your current working plan and return you to dataset selection. Frozen Final30 research results are not affected."
      : "Change the selected dataset and return to dataset selection? Frozen Final30 research results are not affected.";
    fsConfirm(message, resetDataset, {
      title: "Change dataset?",
      confirmText: "Change dataset",
      cancelText: "Keep current dataset",
      warning: hasWork
    });
  }
  function renderRequirements(host) {
    if (host.dataset.open === "1") { host.innerHTML = ""; host.dataset.open = "0"; return; }
    host.dataset.open = "1"; loading(host);
    api("/api/farmsync/data-requirements").then(d => {
      if (!d.available) { host.innerHTML = naTag("Not available"); return; }
      const cf = d.modes.custom_farmer, cp = d.modes.complete_package;
      const labelClass = (lab) => /^Required$/.test(lab) ? "final" : (/^Required for/.test(lab) ? "revised" : (/reused/i.test(lab) ? "initial" : "planned"));
      const schema = d.file_schema.map(f =>
        '<tr><td class="mono">' + esc(f.file) + '</td><td><span class="fs-state ' + labelClass(f.custom_farmer_label) + '">' + esc(f.custom_farmer_label) + '</span></td><td><span class="fs-state ' + labelClass(f.complete_package_label) + '">' + esc(f.complete_package_label) + '</span></td><td class="fs-muted">' + esc(f.purpose) + '</td></tr>').join("");
      const capRows = cp.capability_requirements.map(c => '<tr><td>' + esc(c.capability) + '</td><td class="mono">' + (c.files.length ? c.files.map(esc).join(", ") : "&mdash;") + '</td></tr>').join("");
      host.innerHTML =
        '<div class="fs-req"><div class="fs-h-eyebrow">Data requirements</div>' +
        '<div class="fs-note-box warn">' + esc(d.validation_vs_readiness) + '</div>' +
        '<div class="fs-req-mode"><b>' + esc(cf.label) + '</b><p>' + esc(cf.answers) + '</p><div class="fs-req-files">' + cf.you_must_provide.map(f => '<span class="fs-chip"><span class="fs-req-core">required</span> ' + esc(f) + '</span>').join("") + '</div><p class="fs-hint fs-muted">Reused from built-in (not required): ' + cf.reused_from_builtin.map(esc).join(", ") + '.</p></div>' +
        '<div class="fs-req-mode"><b>' + esc(cp.label) + '</b><p>' + esc(cp.answers) + '</p><div class="fs-tablewrap"><table class="fs-tbl"><thead><tr><th>FarmSync capability</th><th>Required files</th></tr></thead><tbody>' + capRows + '</tbody></table></div></div>' +
        '<div class="fs-note-box info">Limits: package .zip &le; ' + d.limits.max_zip_mb + ' MB (&le; ' + d.limits.max_uncompressed_mb + ' MB uncompressed), single file &le; ' + d.limits.max_file_mb + ' MB. Valid seasons: ' + d.valid_seasons.map(esc).join(", ") + '.</div>' +
        '<details class="fs-drawer"><summary>Per-file requirement by mode &amp; required columns</summary><div class="fs-drawer-body"><div class="fs-tablewrap"><table class="fs-tbl"><thead><tr><th>File</th><th>Custom farmer</th><th>Complete package</th><th>Purpose</th></tr></thead><tbody>' + schema + '</tbody></table></div></div></details>' +
        '<div class="fs-card-actions"><button class="fs-btn fs-btn-primary" id="reqUpload">Upload my data</button></div></div>';
      const ru = host.querySelector ? host.querySelector("#reqUpload") : $("#reqUpload");
      if (ru) ru.addEventListener("click", () => { const m = $("#homeDmMount"); if (m) mountDM(m, { mode: "select" }); });
    }).catch(e => errbox(host, e.message));
  }

  /* ================= 1. INITIAL PLAN (PLANNED only) ================= */
  loaders.plan = (el) => {
    loading(el);
    return ensureWorkingSession().then(run => {
      const recs = run.recommendations || [];
      const builtin = run.source_kind === "builtin";
      const totalPlots = (run.population && run.population.plots) || recs.length;
      const offered = recs.length;
      const noOffer = totalPlots - offered;
      const rows = recs.slice(0, 60).map(r => '<tr><td class="mono">' + esc(r.farmer_id) + '</td><td class="mono">' + esc(r.plot_id) + '</td><td>' + esc(r.crop) + '</td><td class="num">' + rup(r.cash) + '</td></tr>').join("");
      el.innerHTML =
        '<div class="fs-panel"><span class="fs-h-eyebrow">Stage 1 &middot; Initial plan</span><h2>Initial recommendation <span class="fs-state planned">PLANNED</span></h2>' +
        teach({ what: "FarmSync produced an initial crop recommendation for the offered farmer/plots from the chosen dataset.", why: "Farmers need a concrete starting recommendation to respond to.", result: offered + " of " + totalPlots + " dataset plots received an initial allocation.", meaning: "This is the starting point, before farmers respond. Not a realised allocation, and not every plot is allocated." }) +
        '<div class="fs-note-box info">' + (builtin
          ? 'This reads the stored FarmSync <b>development plan</b> for the built-in dataset. It does not run the optimiser (CBC/PuLP) in your browser.'
          : 'This is a <b>deterministic recommendation</b> from your activated dataset (not the frozen MILP; not a publication result). It does not run the optimiser in your browser.') + '</div>' +
        '<div class="fs-metrics" style="margin-top:12px">' + mtile("Plots in dataset", totalPlots) + mtile("Initially allocated / offered", offered) + mtile("No initial allocation", noOffer) + mtile("Farmers", run.population.farmers) + mtile("Planned cash", rup(run.planned_cash)) + '</div>' +
        '<p class="fs-muted" style="margin-top:8px">Every plot remains part of the study, but the planning model does not have to allocate a crop to every plot. Unallocated plots remain part of coverage, fairness and final accounting and are not treated as missing data.</p>' +
        '<details class="fs-drawer" style="margin-top:12px"><summary>Where does this plan come from?</summary><div class="fs-drawer-body">' +
        '<p><b>B1 &mdash; Individual profit planning.</b> Each farmer is planned independently to maximise feasible return.</p>' +
        '<p><b>B2 &mdash; Collective market-aware planning.</b> Plans farmers together and adds collective market-absorption constraints to reduce excessive crop concentration.</p>' +
        '<p><b>B3 &mdash; Fairness-aware collective planning.</b> Builds on B2 and adds protection for worse-off capable farmers while retaining most attainable efficiency.</p>' +
        '<p><b>FarmSync Proposed.</b> Starts from the B3 planned allocation and adds farmer responses, commitment-aware replanning, concentration control, renewed consent and final realisation.</p>' +
        '<div class="fs-note-box info" style="margin-top:6px">This working journey starts from the <b>B3 initial planned allocation</b>. B3 does not allocate a crop to every dataset plot. The frozen 30-seed B1&rarr;B2&rarr;B3 and FarmSync evidence is under <b>Advanced &rsaquo; Final30 Results</b>.</div>' +
        '</div></details></div>' +
        '<div class="fs-panel"><h2>Initial recommendations <span class="fs-muted">(first ' + Math.min(60, recs.length) + ' of ' + recs.length + ' offered)</span></h2><div class="fs-tablewrap"><table class="fs-tbl"><thead><tr><th>Farmer</th><th>Plot</th><th>Original recommended crop</th><th>Expected value</th></tr></thead><tbody>' + rows + '</tbody></table></div><p class="fs-realised-key">FarmSync\u2019s initial recommendation <b>before farmers respond</b>. It is not a realised allocation.</p>' +
        nextCta("Review Farmer Responses", "farmer") + '</div>';
      unlock("farmer");
    }).catch(e => errbox(el, e.message));
  };
  const cmpRadio = (v, t) => '<button class="fs-radio" data-val="' + v + '"><span class="fs-radio-dot"></span><span><span class="fs-radio-t">' + t + '</span></span></button>';

  /* ================= 2. FARMER RESPONSES ================= */
  loaders.farmer = (el) => {
    loading(el);
    return ensureWorkingSession().then(run => {
      const recs = run.recommendations || [];
      const item = (r) => {
        const eff = r.working_response || r.recorded_response;
        const edited = r.working_response && r.recorded_response && r.working_response !== r.recorded_response;
        const badge = eff ? '<span class="fs-act ' + esc(eff) + '">' + esc(eff) + '</span>' + (edited ? ' <span class="fs-edited">edited</span>' : (r.working_response ? ' <span class="fs-edited">set</span>' : '')) : '<span class="fs-muted">not set</span>';
        return '<button class="fs-farmer-item" data-fid="' + esc(r.farmer_id) + '" data-pid="' + esc(r.plot_id) + '"><span class="fs-fi-ids"><span class="mono">' + esc(r.farmer_id) + '</span> <span class="fs-muted mono">' + esc(r.plot_id) + '</span></span> ' + badge + '</button>';
      };
      const list = recs.map(item).join("");
      const synthetic = run.source_kind === "custom";
      el.innerHTML =
        '<div class="fs-panel"><span class="fs-h-eyebrow">Stage 2 &middot; Farmer responses</span><h2>Record each farmer\u2019s response for this plan</h2>' +
        teach({ what: "Each farmer responds to FarmSync\u2019s recommendation for their plot.", why: "The plan must reflect what farmers will actually accept, reject or want changed.", result: (synthetic ? "This is your own dataset \u2014 there is no recorded research response; set each farmer\u2019s response for this plan." : "Each farmer has a recorded research response. Editing sets a working-plan response for this plan only."), meaning: "Replan consumes the working-plan response where set, otherwise the recorded response." }) +
        workingModeNote() +
        '<div class="fs-farmer-layout"><div class="fs-farmer-list" id="farmerList"><input type="search" id="farmerSearch" placeholder="Filter by farmer or plot&hellip;">' + list + '</div><div class="fs-farmer-detail" id="farmerDetail"><div class="fs-empty">Choose a row (farmer + plot) to review and set a response.</div></div></div>' +
        nextCta("Continue to Replan", "replan") + '</div>';
      $("#farmerSearch").addEventListener("input", e => { const q = e.target.value.toLowerCase(); $$("#farmerList .fs-farmer-item").forEach(it => { it.style.display = it.textContent.toLowerCase().includes(q) ? "" : "none"; }); });
      $("#farmerList").addEventListener("click", e => { const it = e.target.closest(".fs-farmer-item"); if (!it) return; $$("#farmerList .fs-farmer-item").forEach(x => x.classList.toggle("sel", x === it)); openFarmer(it.dataset.fid, it.dataset.pid); });
      if (S.farmer) { const sel = $('#farmerList .fs-farmer-item[data-fid="' + S.farmer + '"][data-pid="' + S.plot + '"]'); if (sel) sel.classList.add("sel"); openFarmer(S.farmer, S.plot); }
      unlock("replan");
    }).catch(e => errbox(el, e.message));
  };
  function wpRec(fid, pid) { return (WORK.data && WORK.data.recommendations || []).find(r => r.farmer_id === fid && r.plot_id === pid); }
  function refreshFarmerListItem(fid, pid) {
    const r = wpRec(fid, pid); if (!r) return;
    const it = $('#farmerList .fs-farmer-item[data-fid="' + fid + '"][data-pid="' + pid + '"]'); if (!it) return;
    const eff = r.working_response || r.recorded_response;
    const edited = r.working_response && r.recorded_response && r.working_response !== r.recorded_response;
    const badge = eff ? '<span class="fs-act ' + esc(eff) + '">' + esc(eff) + '</span>' + (edited ? ' <span class="fs-edited">edited</span>' : (r.working_response ? ' <span class="fs-edited">set</span>' : '')) : '<span class="fs-muted">not set</span>';
    it.innerHTML = '<span class="fs-fi-ids"><span class="mono">' + esc(fid) + '</span> <span class="fs-muted mono">' + esc(pid) + '</span></span> ' + badge;
  }
  const S = { farmer: null, plot: null };

  function openFarmer(fid, pid) {
    S.farmer = fid; S.plot = pid; const host = $("#farmerDetail"); loading(host);
    const w = wpRec(fid, pid) || {};
    const url = "/api/farmsync/farmer-response/" + encodeURIComponent(fid) + (pid ? "/" + encodeURIComponent(pid) : "");
    api(url).then(d => (d && d.available) ? d : null).catch(() => null).then(canon => {
      const d = canon || {
        available: true, farmer_id: fid, plot_id: pid,
        region_season: (w.region_id && w.season) ? (w.region_id + ":" + w.season) : "\u2014",
        response: null, recommendation: { crop: w.crop, cash: w.cash },
      };
      const isBuiltin = !!(WORK.data && WORK.data.source_kind === "builtin");
      const recorded = w.recorded_response || d.response || null;
      const working = w.working_response || null;
      const requestedCrop = w.requested_crop || null;
      const effective = working || recorded;
      const rec = d.recommendation || { crop: w.crop, cash: w.cash };
      const PENDING = "__pending__";
      let selected = PENDING;
      const actionText = (a) => {
        if (a === "MODIFY" && requestedCrop) return "Modify \u2014 " + requestedCrop + " requested";
        return actionLabel(a);
      };
      const actionBtns = () => ["ACCEPT", "REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW"].map(a => '<button class="fs-btn fs-action-btn' + (a === selected ? " is-active" : "") + (a === working ? " is-saved" : "") + '" data-act="' + a + '">' + esc(actionText(a)) + (a === working ? ' \u2713' : '') + '</button>').join("");
      const recordedRow = recorded
        ? '<div><div class="fs-muted">' + (isBuiltin ? 'Recorded synthetic farmer response' : 'Recorded response') + '</div><div><span class="fs-act ' + esc(recorded) + '">' + esc(recorded) + '</span></div></div>'
        : '<div><div class="fs-muted">Recorded response</div><div><span class="fs-muted">None</span> <span class="fs-badge fs-badge-muted">custom &mdash; no recorded response</span></div></div>';
      const thisPlanLabel = working
        ? '<span class="fs-act ' + esc(working) + '">' + esc(working) + '</span>' + (requestedCrop && working === "MODIFY" ? ' <span class="fs-saved-ok">&mdash; ' + esc(requestedCrop) + ' requested \u2713</span>' : '') + (recorded && working !== recorded ? ' <span class="fs-edited">edited</span>' : '')
        : '<span class="fs-muted">' + (recorded ? "unchanged" : "not set") + '</span>';
      const thisPlanRow = '<div><div class="fs-muted">Working-plan response</div><div>' + thisPlanLabel + '</div></div>';
      const savedRequestCard = requestedCrop
        ? '<div class="fs-saved-request-card"><div><div class="fs-h-eyebrow">Your saved crop-change request</div><div class="fs-saved-request-crop">' + esc(requestedCrop) + ' <span class="fs-saved-ok">\u2713</span></div><div class="fs-muted">Saved for this plan &middot; Pending Replan</div></div><div class="fs-saved-request-note">This is a farmer request, not an allocation or consent. Replan still validates/selects the revised recommendation.</div></div>'
        : '';
      host.innerHTML =
        '<div class="fs-farmer-head"><div><div class="fs-muted">Farmer</div><div class="fs-farmer-id mono">' + esc(d.farmer_id) + '</div></div><div><div class="fs-muted">Plot</div><div class="mono">' + esc(d.plot_id) + '</div></div><div><div class="fs-muted">Region / season</div><div>' + esc(d.region_season) + '</div></div>' + recordedRow + thisPlanRow + '</div>' +
        '<div class="fs-reco-box"><div class="fs-h-eyebrow">Original FarmSync recommendation</div><div class="fs-reco-crop">' + esc(rec.crop) + '</div><div class="fs-reco-cash">' + rup(rec.cash) + ' expected value</div></div>' +
        savedRequestCard +
        '<div class="fs-field-h" style="margin-top:16px">Tell FarmSync what you want</div>' +
        '<div class="fs-ai-role"><span class="fs-ai-role-item"><b>LLM</b> parses</span><span class="fs-ai-arrow">&rarr;</span><span class="fs-ai-role-item"><b>FarmSync</b> validates/selects</span><span class="fs-ai-arrow">&rarr;</span><span class="fs-ai-role-item"><b>Evidence</b> grounded</span></div>' +
        '<div class="fs-askai"><div class="fs-ai-input"><input type="text" id="aiMsg" placeholder="e.g. I don\u2019t want ' + esc(rec.crop || "onion") + '. What else can I grow?"><button class="fs-btn" id="askAiBtn">Ask FarmSync AI</button> <span class="fs-badge fs-badge-muted" id="aiModeBadge">AI mode\u2026</span></div><div id="askAiBox"></div></div>' +
        '<div class="fs-field-h" style="margin-top:18px">Response for this plan</div>' +
        '<p class="fs-hint fs-muted">Choose an action, then <b>Save response</b>. This sets your working-plan response for this exact farmer + plot; the recorded synthetic response (built-in) is never changed.</p>' +
        '<div class="fs-action-row">' + actionBtns() + '</div>' +
        '<div class="fs-save-row"><button class="fs-btn fs-btn-primary" id="wpSave" disabled>Save response</button>' + (working ? '<button class="fs-btn" id="wpReset">Reset to recorded response</button>' : '') + '<span id="wpSaveMsg" class="fs-save-msg"></span></div>' +
        '<div id="actionOutcome"></div>';
      const bindActionRow = () => host.querySelector(".fs-action-row").addEventListener("click", e => { const b = e.target.closest("[data-act]"); if (!b) return; selected = b.dataset.act; $$(".fs-action-btn", host).forEach(x => x.classList.toggle("is-active", x === b)); $("#wpSave").disabled = false; showActionOutcome(b.dataset.act, recorded, "pending", requestedCrop); });
      bindActionRow();
      $("#wpSave").addEventListener("click", () => {
        if (selected === PENDING) return;
        fetch("/api/farmsync/working-plan/" + WORK.runId + "/response", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ farmer_id: fid, plot_id: pid, action: selected }) })
          .then(r => r.json()).then(res => {
            if (!res.available) { $("#wpSaveMsg").innerHTML = '<span class="fs-run infeasible">' + esc(res.error || "failed") + '</span>'; return; }
            return refreshWorkingRun().then(() => { refreshFarmerListItem(fid, pid); openFarmer(fid, pid); });
          }).catch(e => { const m = $("#wpSaveMsg"); if (m) m.innerHTML = '<span class="fs-run infeasible">' + esc(e.message) + '</span>'; });
      });
      const rb = $("#wpReset");
      if (rb) rb.addEventListener("click", () => {
        fetch("/api/farmsync/working-plan/" + WORK.runId + "/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ farmer_id: fid, plot_id: pid }) })
          .then(r => r.json()).then(res => {
            if (!res.available) throw new Error(res.error || "reset failed");
            return refreshWorkingRun();
          }).then(() => { refreshFarmerListItem(fid, pid); openFarmer(fid, pid); })
          .catch(e => errbox(host, e.message));
      });
      if (effective) showActionOutcome(effective, recorded, working ? "working" : "recorded", requestedCrop);
      $("#askAiBtn").addEventListener("click", () => showAskAi(d));
      $("#aiMsg").addEventListener("keydown", e => { if (e.key === "Enter") showAskAi(d); });
      refreshAiMode();
    }).catch(e => errbox(host, e.message));
  }

  const actionLabel = (a) => ({ ACCEPT: "Accept", REJECT: "Reject", MODIFY: "Request another crop", NO_RESPONSE: "No response", WITHDRAW: "Withdraw" }[a] || a);

  function showActionOutcome(act, recorded, state, requestedCrop) {
    const EX = {
      ACCEPT: ["Accepted", "The farmer consents to the recommended crop. A commitment state (FLEXIBLE / SOFT_LOCK / HARD_LOCK) will govern later changes."],
      REJECT: ["Rejected", "No consent. Where the protocol requires it the current crop is excluded, and FarmSync's action-consent + feasibility logic selects a fresh feasible recommendation (Replan) that needs renewed consent."],
      MODIFY: ["Requested another crop", "Interpreted as MODIFY. The requested crop is an input, not an allocation \u2014 FarmSync validates it and selects a feasible recommendation in Replan."],
      NO_RESPONSE: ["No response (pending / lapsed)", "Not silently accepted. No consent exists and the plot is not realised on this recommendation."],
      WITHDRAW: ["Withdrew", "The farmer leaves this round; the outcome follows the frozen FLEXIBLE / SOFT_LOCK / HARD_LOCK semantics for the plot\u2019s commitment state."]
    };
    const e = EX[act] || [act, ""];
    if (act === "MODIFY" && requestedCrop) e[0] = "Modify — " + requestedCrop + " requested";
    let tag;
    if (state === "pending") tag = '<span class="fs-outcome-tag illustrative">Pending &mdash; press Save response to set this for the plan</span>';
    else if (state === "working") tag = '<span class="fs-outcome-tag recorded">Saved for this plan' + (recorded ? ' (recorded: ' + esc(recorded) + ')' : '') + '</span>';
    else tag = '<span class="fs-outcome-tag recorded">Recorded: ' + esc(recorded) + '</span>';
    $("#actionOutcome").innerHTML = '<div class="fs-outcome ' + (state === "pending" ? "is-illustrative" : "is-recorded") + '"><span class="fs-act ' + act + '">' + esc(e[0]) + '</span> ' + tag + '<p>' + esc(e[1]) + '</p></div>';
  }

  function refreshAiMode() {
    fetch("/api/farmsync/ai-status").then(r => r.json()).then(s => {
      const label = (s && s.label) || "AI mode";
      const badge = $("#aiModeBadge");
      if (badge) badge.textContent = label;
      $$(".fs-ai-mode-badge").forEach(b => { b.textContent = label; });
    }).catch(() => {});
  }

  function showAskAi(d) {
    const box = $("#askAiBox");
    const msg = ($("#aiMsg") && $("#aiMsg").value) || "";
    if (!msg.trim()) { box.innerHTML = '<div class="fs-muted" style="margin-top:8px">Type a request above, e.g. "Can I grow groundnut?" or "What else can I grow?"</div>'; return; }
    loading(box);
    // RUN-BOUND integration endpoint: parses via the mode-selected parser AND returns the deterministic
    // recommendation/feasibility in ai.deterministic — no second /recommend or /validate-crop call.
    fetch("/api/farmsync/working-plan/" + WORK.runId + "/ai-parse", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: msg, farmer_id: d.farmer_id, plot_id: d.plot_id }) })
      .then(r => r.json()).then(ai => renderAiResult(box, d, ai)).catch(e => errbox(box, e.message));
  }

  function renderAiResult(box, d, ai) {
    // explicit failure / disabled / identity or plot mismatch
    if (ai.available === false) {
      box.innerHTML = aiHeader(ai) +
        '<div class="fs-errbox" style="margin-top:8px">' + esc(ai.user_message || ai.error || "AI parsing failed — use the manual controls.") + '</div>' +
        aiTechDrawer(ai, "");
      return;
    }
    // non-actionable authority attempt: blocked, no recommendation, no Use button
    if (ai.status === "AUTHORITY_ATTEMPT_BLOCKED") {
      box.innerHTML = aiHeader(ai) +
        '<div class="fs-note-box warn" style="margin-top:8px">' + esc(ai.user_message) + '</div>' +
        aiTechDrawer(ai, "");
      return;
    }
    // alternative-seeking or crop-modify: the deterministic result is already in ai.deterministic
    if (ai.ui_intent === "REQUEST_ALTERNATIVE") {
      return renderAiRecommendation(box, d, ai, ai.deterministic || {}, []);
    }
    if (ai.parser_action === "MODIFY" && ai.requested_crop_parsed) {
      return renderAiValidation(box, d, ai, ai.deterministic || {});
    }
    // grounded explanation (QUERY -> EXPLAIN_CURRENT/EXPLAIN_CROP) or safe out-of-model (UNSUPPORTED_QUERY):
    // read-only, no Save, no Use button.
    if (ai.ui_intent === "EXPLAIN_CURRENT" || ai.ui_intent === "EXPLAIN_CROP" || ai.ui_intent === "UNSUPPORTED_QUERY") {
      return renderAiExplanation(box, ai);
    }
    // ACCEPT / REJECT / WITHDRAW / QUERY / CLARIFY — understood action only; explicit save still required
    return renderAiUnderstoodOnly(box, ai);
  }

  function renderAiExplanation(box, ai) {
    const unsupported = ai.ui_intent === "UNSUPPORTED_QUERY";
    const ev = ai.deterministic || {};

    // Out-of-model questions remain conservative and do not invent an answer.
    if (unsupported) {
      const msg = ai.user_message || ai.understood ||
        "FarmSync cannot determine that from the current planning evidence.";

      box.innerHTML =
        aiHeader(ai) +
        '<div class="fs-note-box warn" style="margin-top:8px">' +
        esc(msg) +
        '</div>' +
        aiTechDrawer(ai, "");

      return;
    }

    // Presentation helpers only. No case-specific crop or result is hardcoded.
    const prettyCrop = (name) =>
      String(name || "")
        .replace(/_/g, " ")
        .replace(/\b\w/g, c => c.toUpperCase());

    const humanList = (items) => {
      if (!items.length) return "";
      if (items.length === 1) return items[0];
      if (items.length === 2) return items[0] + " and " + items[1];
      return items.slice(0, -1).join(", ") + ", and " + items[items.length - 1];
    };

    const crop = prettyCrop(ev.crop);
    const checks = ev.assessment_checks || {};
    const evidence = ev.plot_evidence || {};

    // Only mention checks that the deterministic payload actually reports as
    // satisfactory. Never invent soil/weather/resource facts.
    const passed = [];

    if (checks.season === "OK") {
      passed.push("season");
    }

    if (
      checks.soil_class &&
      /^S\d/i.test(String(checks.soil_class))
    ) {
      passed.push("soil suitability");
    }

    if (checks.water === "OK") {
      passed.push("water availability");
    }

    if (checks.waterlogging === "OK") {
      passed.push("waterlogging risk");
    }

    if (checks.rotation === "OK") {
      passed.push("crop rotation");
    }

    if (checks.labour === "OK") {
      passed.push("labour");
    }

    let responseHtml = "";

    // Current-plan explanation.
    if (
      ai.ui_intent === "EXPLAIN_CURRENT" &&
      ev.current_plan_crop === true &&
      ev.agronomic_feasible === true
    ) {
      responseHtml +=
        '<p><b>' + esc(crop) +
        '</b> is the current FarmSync recommendation for this plot.</p>';

      if (passed.length) {
        responseHtml +=
          '<p>FarmSync&rsquo;s current deterministic checks show no blocking issue for ' +
          esc(humanList(passed)) +
          '.</p>';
      } else {
        responseHtml +=
          '<p>FarmSync&rsquo;s current deterministic agronomic checks show no blocking constraint for this crop.</p>';
      }

      if (ev.expected_cash != null) {
        if (ev.expected_cash_source === "stored_current_plan") {
          responseHtml +=
            '<p>The stored current plan records an expected value of <b>' +
            rup(ev.expected_cash) +
            '</b> for this allocation.</p>';
        } else {
          responseHtml +=
            '<p>FarmSync&rsquo;s current deterministic selection evidence gives an expected value of <b>' +
            rup(ev.expected_cash) +
            '</b> for this allocation.</p>';
        }
      }

      if (ev.eligible_for_selection === false) {
        responseHtml +=
          '<p>This recommendation comes from the current FarmSync plan; FarmSync does not claim that <b>' +
          esc(crop) +
          '</b> is simply the highest-ranked standalone alternative for this plot.</p>';
      } else if (
        ev.rank_reproducible === true &&
        ev.overall_rank != null
      ) {
        responseHtml +=
          '<p>Under the current standalone selection evidence, this crop has a reproducible projected-return rank of <b>#' +
          esc(ev.overall_rank) +
          '</b>.</p>';
      }
    } else {
      // Named-crop explanations retain the grounded server wording.
      // Capitalise the crop at the start when possible, but do not change its meaning.
      let msg = ai.understood || "FarmSync explanation.";

      if (ev.crop) {
        const rawCrop = String(ev.crop);
        if (msg.toLowerCase().indexOf(rawCrop.toLowerCase()) === 0) {
          msg = prettyCrop(rawCrop) + msg.slice(rawCrop.length);
        }
      }

      responseHtml = '<p>' + esc(msg) + '</p>';
    }

    // ---------------- Technical evidence ----------------
    // These values come directly from deterministic FarmSync evidence.
    const checkParts = [];

    [
      ["Season", "season"],
      ["Exclusion", "exclusion"],
      ["Soil suitability", "soil_class"],
      ["Waterlogging", "waterlogging"],
      ["Rotation", "rotation"],
      ["Water", "water"],
      ["Budget", "budget"],
      ["Labour", "labour"]
    ].forEach(([label, key]) => {
      if (checks[key] != null) {
        checkParts.push(label + ": " + String(checks[key]));
      }
    });

    const evidenceParts = [];

    if (evidence.season) {
      evidenceParts.push("Season: " + evidence.season);
    }

    if (evidence.soil_group) {
      evidenceParts.push("Soil: " + evidence.soil_group);
    }

    if (evidence.soil_suitability_class) {
      evidenceParts.push(
        "Soil suitability: " + evidence.soil_suitability_class
      );
    }

    if (evidence.drainage_class) {
      evidenceParts.push("Drainage: " + evidence.drainage_class);
    }

    if (evidence.irrigation_access) {
      evidenceParts.push(
        "Irrigation: " + evidence.irrigation_access
      );
    }

    if (evidence.available_water_m3 != null) {
      evidenceParts.push(
        "Available water: " +
        Number(evidence.available_water_m3).toLocaleString("en-IN") +
        " m³"
      );
    }

    if (evidence.previous_crop) {
      evidenceParts.push(
        "Previous crop: " + prettyCrop(evidence.previous_crop)
      );
    }

    let tech = "";

    if (checkParts.length) {
      tech +=
        '<tr><td>Deterministic checks</td><td style="white-space:normal;overflow-wrap:anywhere">' +
        esc(checkParts.join(" · ")) +
        '</td></tr>';
    }

    if (evidenceParts.length) {
      tech +=
        '<tr><td>Plot evidence</td><td style="white-space:normal;overflow-wrap:anywhere">' +
        esc(evidenceParts.join(" · ")) +
        '</td></tr>';
    }

    if (typeof ev.agronomic_feasible === "boolean") {
      tech +=
        '<tr><td>Agronomic feasibility</td><td>' +
        (ev.agronomic_feasible ? "No blocking constraint" : "Blocking constraint detected") +
        '</td></tr>';
    }

    if (typeof ev.eligible_for_selection === "boolean") {
      tech +=
        '<tr><td>New-selection eligible</td><td>' +
        (ev.eligible_for_selection ? "Yes" : "No") +
        '</td></tr>';
    }

    if (typeof ev.rank_reproducible === "boolean") {
      tech +=
        '<tr><td>New rank reproduced</td><td>' +
        (ev.rank_reproducible ? "Yes" : "No") +
        '</td></tr>';
    }

    if (ev.expected_cash_source) {
      const cashSource =
        ev.expected_cash_source === "stored_current_plan"
          ? "stored current plan"
          : ev.expected_cash_source === "current_selection_eligibility"
            ? "current selection eligibility"
            : ev.expected_cash_source;

      tech +=
        '<tr><td>Expected-value source</td><td>' +
        esc(cashSource) +
        '</td></tr>';
    }

    if (
      ev.current_plan_crop === true &&
      ev.eligible_for_selection === false
    ) {
      tech +=
        '<tr><td>Ranking note</td><td style="white-space:normal;overflow-wrap:anywhere">' +
        'The current alternative-selection layer does not reproduce a rankable cash-positive entry for this crop, so FarmSync does not invent a new rank.' +
        '</td></tr>';
    }

    box.innerHTML =
      aiHeader(ai) +
      '<div class="fs-note-box info" style="margin-top:8px">' +
      responseHtml +
      '</div>' +
      aiTechDrawer(ai, tech);
  }

  function aiTechDrawer(ai, extra) {
    const src = (ai.parsed && ai.parsed.farmer_id) ? (esc(ai.parsed.farmer_id) + ' / ' + esc(ai.parsed.plot_id))
                                                    : (esc(ai.farmer_id) + ' / ' + esc(ai.plot_id));
    return '<details class="fs-drawer" style="margin-top:10px"><summary>Technical details</summary><div class="fs-drawer-body"><div class="fs-tablewrap"><table class="fs-tbl"><tbody>' +
      '<tr><td>Parser action</td><td>' + esc(ai.parser_action || ai.action || "") + '</td></tr>' +
      '<tr><td>UI intent</td><td>' + esc(ai.ui_intent || "") + '</td></tr>' +
      ((ai.requested_crop_parsed || ai.requested_crop) ? '<tr><td>Requested crop</td><td>' + esc(ai.requested_crop_parsed || ai.requested_crop) + '</td></tr>' : '') +
      '<tr><td>Farmer / plot</td><td class="mono">' + src + '</td></tr>' +
      '<tr><td>Mode / model</td><td>' + esc(ai.mode || "") + (ai.model ? ' · ' + esc(ai.model) : '') + '</td></tr>' +
      '<tr><td>Schema / prompt</td><td class="mono">' + esc(ai.schema_version || "") + ' / ' + esc(ai.prompt_version || "") + '</td></tr>' +
      (ai.status ? '<tr><td>Status</td><td>' + esc(ai.status) + '</td></tr>' : '') +
      (ai.authority_reason_codes ? '<tr><td>Authority codes</td><td class="mono">' + esc((ai.authority_reason_codes || []).join(", ")) + '</td></tr>' : '') +
      '<tr><td>Recommendation source</td><td>' + esc(ai.recommendation_source === "deterministic_farmsync" ? "deterministic FarmSync" : "not applicable") + '</td></tr>' +
      '<tr><td>LLM role</td><td>parser only; FarmSync remains authoritative</td></tr>' +
      (extra || "") + '</tbody></table></div></div></details>';
  }

  function aiHeader(ai) {
    const mode = String(ai.mode || "").toLowerCase();

    const parserLabel =
      mode === "live" ? "LLM parsed" :
      mode === "mock" ? "Mock parser" :
      "Parser";

    return '<div class="fs-ai-convo"><div class="fs-ai-msg fs-ai-user">' +
      esc(ai.source_text || "") +
      '</div></div>' +
      '<div class="fs-h-eyebrow fs-ai-response-head" style="margin-top:8px">' +
        '<span>FarmSync response</span>' +
        '<span class="fs-ai-provenance" ' +
          'title="The parser interprets the farmer request; deterministic FarmSync supplies the grounded evidence.">' +
          '<span>' + esc(parserLabel) + '</span>' +
          '<span class="fs-ai-prov-sep" aria-hidden="true">&middot;</span>' +
          '<span>FarmSync grounded</span>' +
        '</span>' +
      '</div>';
  }

  function recCard(d, rec, offered) {
    const w = wpRec(d.farmer_id, d.plot_id) || {};
    const savedCrop = w.requested_crop || null;
    const savedLine = savedCrop
      ? '<div class="fs-saved-request-mini"><span>Your saved crop-change request</span><b>' + esc(savedCrop) + ' \u2713</b><small>Pending Replan. Browsing below does not replace it until you press Use.</small></div>'
      : "";
    const isSaved = savedCrop && savedCrop === rec.recommended_crop;
    return savedLine +
      '<div class="fs-reco-box" style="margin-top:8px"><div class="fs-h-eyebrow">FarmSync ' + (savedCrop ? "is currently showing" : "recommendation") + '</div><div class="fs-reco-crop">' + esc(rec.recommended_crop) + (isSaved ? ' <span class="fs-saved-ok">\u2713 saved</span>' : '') + '</div>' +
      '<div class="fs-reco-cash">' + rup(rec.expected_cash) + ' expected value</div><p class="fs-muted" style="margin-top:6px">' + esc(rec.reason) + '</p>' +
      '<p class="fs-muted" style="font-size:12px">Determined by ' + esc(rec.determined_by) + '.</p></div>' +
      '<div class="fs-action-row" style="margin-top:10px"><button class="fs-btn fs-btn-primary" data-ai-use="' + esc(rec.recommended_crop) + '">' + (savedCrop && !isSaved ? "Use this instead" : "Use this recommendation") + '</button>' +
      '<button class="fs-btn" data-ai-reject="' + esc(rec.recommended_crop) + '">Reject</button>' +
      (rec.n_more > 0 ? '<button class="fs-btn" data-ai-another="' + esc(offered.concat([rec.recommended_crop]).join("|")) + '">Another option</button>' : '') +
      '<button class="fs-btn" data-ai-why="' + esc(rec.recommended_crop) + '">Ask why</button></div><div id="aiActOut"></div>';
  }

  function evidenceValue(v) {
    if (v === null || v === undefined || v === "") return null;
    if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
    return String(v);
  }

  function renderWhyExplanation(ex) {
    const pe = ex.plot_evidence || {};
    const facts = [
      ["Region", pe.region_id],
      ["Season", pe.season],
      ["Area", pe.area_ha != null ? evidenceValue(pe.area_ha) + " ha" : null],
      ["Soil group", pe.soil_group],
      ["Soil suitability class", pe.soil_suitability_class],
      ["Drainage", pe.drainage_class],
      ["Irrigation access", pe.irrigation_access],
      ["Available water", pe.available_water_m3 != null ? evidenceValue(pe.available_water_m3) + " m\u00b3" : null],
      ["Waterlogging exposure", pe.waterlogging_exposure],
      ["Previous crop", pe.previous_crop],
      ["Rotation group", pe.rotation_group]
    ].filter(x => evidenceValue(x[1]) !== null);

    const factRows = facts.length ? facts.map(x => '<div class="fs-evidence-item"><span>' + esc(x[0]) + '</span><b>' + esc(x[1]) + '</b></div>').join("") : '<div class="fs-muted">No plot attribute values were available to display.</div>';

    const rawChecks = ex.assessment_checks || ex.passed_constraints || {};
    const checks = (rawChecks && typeof rawChecks === "object" && !Array.isArray(rawChecks)) ? rawChecks : {};
    const checkRows = Object.keys(checks).length ? Object.keys(checks).map(k => '<span class="fs-check-chip"><b>' + esc(k) + '</b>: ' + esc(checks[k]) + '</span>').join("") : '<span class="fs-muted">No per-check detail returned.</span>';

    let ranking = "";
    if (ex.available_rank) ranking += '<div><b>Current available-alternative rank:</b> #' + esc(ex.available_rank) + ' of ' + esc(ex.n_available) + '</div>';
    if (ex.overall_rank) ranking += '<div><b>Overall feasible rank:</b> #' + esc(ex.overall_rank) + ' of ' + esc(ex.n_feasible_overall) + '</div>';
    if (!ranking) ranking = '<div class="fs-muted">No feasible ranking is available for this crop.</div>';

    const exclusions = (ex.exclusions || []).length
      ? '<div class="fs-evidence-block"><div class="fs-h-eyebrow">Why some crops are not in the current choice set</div>' + ex.exclusions.map(x => '<div class="fs-exclusion-row"><b>' + esc(x.crop) + '</b><span>' + esc(x.reason) + '</span></div>').join("") + '</div>'
      : '';

    const reasonList = Array.isArray(ex.assessment_reasons) ? ex.assessment_reasons : (ex.assessment_reasons ? [ex.assessment_reasons] : []);
    const reasons = reasonList.length ? '<div class="fs-muted" style="margin-top:8px"><b>Feasibility reason codes:</b> ' + reasonList.map(esc).join(", ") + '</div>' : '';

    return '<div class="fs-why-card"><div class="fs-why-title">Why ' + esc(ex.crop) + ' for <span class="mono">' + esc(ex.farmer_id) + ' / ' + esc(ex.plot_id) + '</span>?</div>' +
      '<div class="fs-why-summary">' + (ex.feasible ? '<span class="fs-run optimal">Feasible</span>' : '<span class="fs-run infeasible">Not feasible</span>') + (ex.expected_cash != null ? ' <b>' + rup(ex.expected_cash) + '</b> projected return' : '') + '</div>' +
      '<div class="fs-evidence-block"><div class="fs-h-eyebrow">Actual plot evidence used</div><div class="fs-evidence-grid">' + factRows + '</div></div>' +
      '<div class="fs-evidence-block"><div class="fs-h-eyebrow">Deterministic feasibility checks</div><div class="fs-check-list">' + checkRows + '</div>' + reasons + '</div>' +
      '<div class="fs-evidence-block"><div class="fs-h-eyebrow">Ranking</div>' + ranking + '</div>' + exclusions +
      '<div class="fs-muted" style="margin-top:10px">' + esc(ex.basis) + ' This is an explanation only \u2014 nothing was changed.</div></div>';
  }

  function bindRecCard(box, d, ai, rec, offered) {
    const use = box.querySelector("[data-ai-use]");
    if (use) use.addEventListener("click", () => {
      const prev = (wpRec(d.farmer_id, d.plot_id) || {}).requested_crop || null;
      fetch("/api/farmsync/working-plan/" + WORK.runId + "/response", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          farmer_id: d.farmer_id,
          plot_id: d.plot_id,
          action: "MODIFY",
          requested_crop: use.dataset.aiUse
        })
      })
        .then(r => r.json()).then(res => {
          if (!res.available) throw new Error(res.error || "could not save requested crop");
          const replaced = prev && prev !== res.requested_crop;
          return refreshWorkingRun().then(() => {
            refreshFarmerListItem(d.farmer_id, d.plot_id);
            openFarmer(d.farmer_id, d.plot_id);
          });
        }).catch(e => {
          const out = box.querySelector("#aiActOut");
          if (out) out.innerHTML = '<div class="fs-errbox">' + esc(e.message) + '</div>';
        });
    });

    const rej = box.querySelector("[data-ai-reject]");
    if (rej) rej.addEventListener("click", () => {
      const crop = rej.dataset.aiReject;
      fetch("/api/farmsync/working-plan/" + WORK.runId + "/reject-candidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          farmer_id: d.farmer_id,
          plot_id: d.plot_id,
          crop: crop
        })
      })
        .then(r => r.json()).then(res => {
          if (!res.available) throw new Error(res.error || "could not reject candidate");
          return refreshWorkingRun().then(() => {
            const out = box.querySelector("#aiActOut");
            if (out) out.innerHTML = '<div class="fs-outcome"><span class="fs-saved-ok">\u2713 ' + esc(crop) + ' rejected for this plan</span> <span class="fs-muted">FarmSync will exclude this candidate from future alternatives and Replan for this farmer + plot. The recorded synthetic farmer response is unchanged.</span></div>';
          });
        }).catch(e => {
          const out = box.querySelector("#aiActOut");
          if (out) out.innerHTML = '<div class="fs-errbox">' + esc(e.message) + '</div>';
        });
    });

    const another = box.querySelector("[data-ai-another]");
    if (another) another.addEventListener("click", () => {
      const excl = another.dataset.aiAnother.split("|").filter(Boolean);
      fetch("/api/farmsync/working-plan/" + WORK.runId + "/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          farmer_id: d.farmer_id,
          plot_id: d.plot_id,
          exclude: excl
        })
      })
        .then(r => r.json()).then(rc => renderAiRecommendation(box, d, ai, rc, excl));
    });

    const why = box.querySelector("[data-ai-why]");
    if (why) why.addEventListener("click", () => {
      fetch("/api/farmsync/working-plan/" + WORK.runId + "/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          farmer_id: d.farmer_id,
          plot_id: d.plot_id,
          crop: why.dataset.aiWhy,
          exclude: offered || []
        })
      })
        .then(r => r.json()).then(ex => {
          const out = box.querySelector("#aiActOut");
          if (!out) return;
          if (!ex.available) {
            out.innerHTML = '<div class="fs-note-box info">' + esc(ex.error || rec.reason) + '</div>';
            return;
          }
          out.innerHTML = renderWhyExplanation(ex);
        }).catch(e => {
          const out = box.querySelector("#aiActOut");
          if (out) out.innerHTML = '<div class="fs-errbox">' + esc(e.message) + '</div>';
        });
    });
  }

  function renderAiRecommendation(box, d, ai, rc, offered) {
    if (!rc.available) {
      box.innerHTML = aiHeader(ai) + '<div class="fs-errbox">' + esc(rc.error || "could not get a recommendation") + '</div>';
      return;
    }
    if (!rc.found) {
      box.innerHTML = aiHeader(ai) + '<div class="fs-note-box warn" style="margin-top:8px">' + esc(rc.reason) + '</div>' + aiTechDrawer(ai, "");
      return;
    }
    box.innerHTML = aiHeader(ai) + recCard(d, rc, offered || []) + aiTechDrawer(ai, "");
    bindRecCard(box, d, ai, rc, offered || []);
  }

  function renderAiValidation(box, d, ai, v) {
    if (!v.available) {
      box.innerHTML = aiHeader(ai) + '<div class="fs-errbox">' + esc(v.error || "could not validate") + '</div>';
      return;
    }
    if (v.feasible) {
      const rec = {
        recommended_crop: v.recommended_crop,
        expected_cash: v.expected_cash,
        reason: v.reason,
        determined_by: v.determined_by,
        n_more: 0
      };
      box.innerHTML = aiHeader(ai) +
        '<div class="fs-note-box info" style="margin-top:8px"><b>' + esc(v.requested_crop) + '</b> is feasible for this plot.</div>' +
        recCard(d, rec, []) +
        aiTechDrawer(ai, "");
      bindRecCard(box, d, ai, rec, []);
    } else {
      const alt = v.alternative;
      const reasonText = ai.understood || v.reason ||
        "FarmSync's deterministic feasibility rules rejected this crop.";

      let html = aiHeader(ai) +
        '<div class="fs-note-box warn" style="margin-top:8px"><b>FarmSync feasibility result:</b> ' +
        esc(reasonText) + '</div>';

      if (alt && alt.found) {
        const rec = {
          recommended_crop: alt.recommended_crop,
          expected_cash: alt.expected_cash,
          reason: alt.reason,
          determined_by: alt.determined_by,
          n_more: alt.n_more
        };
        html += '<p class="fs-muted" style="margin-top:8px">FarmSync\u2019s feasible alternative:</p>' + recCard(d, rec, []);
        box.innerHTML = html + aiTechDrawer(ai, "");
        bindRecCard(box, d, ai, rec, []);
      } else {
        box.innerHTML = html + aiTechDrawer(ai, "");
      }
    }
  }

  function renderAiUnderstoodOnly(box, ai) {
    // user-facing copy follows the EFFECTIVE ui_intent (a vague MODIFY resolves to CLARIFY); parser_action
    // is preserved in Technical details for provenance.
    var intent = ai.ui_intent || ai.parser_action || ai.action || "";
    var note;
    if (intent === "QUERY") {
      note = 'Understood as <b>a question</b>. This is explanation-only \u2014 it does not change the plan.';
    } else if (intent === "CLARIFY") {
      note = 'This request needs clarification. Please name a crop or ask for feasible alternatives. Nothing has been changed.';
    } else {
      // ACCEPT / REJECT / WITHDRAW: explicit response buttons/save still required to set it for this plan
      note = 'Understood as <b>' + esc(intent) + '</b>. Use the response buttons below and press Save to set it for this plan.';
    }
    box.innerHTML = aiHeader(ai) +
      '<div class="fs-note-box info" style="margin-top:8px">' + note + '</div>' +
      aiTechDrawer(ai, "");
  }

  /* ================= 3. REPLAN ================= */
  loaders.replan = (el) => {
    // §3C/§3D: Replan is READ-ONLY on open. It NEVER POSTs /replan. "Run Replan" is the explicit action.
    // Opening this tab does not complete replan or unlock Renewed Consent.
    loading(el);
    return ensureWorkingSession()
      .then(() => refreshWorkingRun())
      .then(run => {
        const wf = (run && run.workflow) || {};
        if (wf.replan_current) {
          renderReplanResult(el, run, wf, false);       // current replan exists -> show it read-only
        } else {
          renderRunReplan(el, run, wf);                 // stale or never-run -> explicit Run Replan
        }
      })
      .catch(e => errbox(el, e.message));
  };

  function renderRunReplan(el, run, wf) {
    const stale = wf.replan_stale;
    el.innerHTML =
      '<div class="fs-panel">' + modeBanner("working") +
      '<span class="fs-h-eyebrow">Stage 3 &middot; Replan</span>' +
      '<h2>' + (stale ? "Replan is out of date" : "Run the deterministic replan") + ' <span class="fs-state revised">' + (stale ? "stale" : "not yet run") + '</span></h2>' +
      teach({
        what: "FarmSync applies this plan\u2019s responses and commitment states through its action-consent + feasibility logic.",
        why: "Rejections, modifications and withdrawals change what is feasible; the plan is recomputed.",
        result: stale ? "Your responses changed since the last replan. Re-run replan to refresh the revised recommendations." : "Run replan to produce revised recommendations for changed responses.",
        meaning: "This is an explicit action \u2014 opening this page does not run replan."
      }) +
      '<div class="fs-cta-row" style="margin-top:14px"><button class="fs-btn fs-btn-primary" id="doReplan">Run Replan</button></div>' +
      '<div id="replanOut"></div></div>';
    const b = $("#doReplan");
    if (b) b.addEventListener("click", () => {
      b.disabled = true; b.textContent = "Running replan\u2026";
      fetch("/api/farmsync/working-plan/" + WORK.runId + "/replan", { method: "POST" })
        .then(r => r.json()).then(rp => {
          if (!rp.available) { b.disabled = false; b.textContent = "Run Replan"; $("#replanOut").innerHTML = '<div class="fs-errbox">' + esc(rp.error || "could not replan") + '</div>'; return; }
          return refreshWorkingRun().then(run => renderReplanResult(el, run, run.workflow || {}, true));
        })
        .catch(e => { b.disabled = false; b.textContent = "Run Replan"; $("#replanOut").innerHTML = '<div class="fs-errbox">' + esc(e.message) + '</div>'; });
    });
  }

  function renderReplanResult(el, run, wf, justRan) {
    const changed = (run.recommendations || []).filter(r => r.changed);
    const nChanged = wf.n_changed != null ? wf.n_changed : changed.length;
    const rows = changed.slice(0, 60).map(r =>
      '<tr><td class="mono">' + esc(r.farmer_id) + '</td><td class="mono">' + esc(r.plot_id) + '</td><td>' +
      esc(r.crop) + ' <span class="fs-arrow">&rarr;</span> <b>' + esc(r.revised_crop) + '</b></td><td>' +
      (r.commitment ? '<span class="fs-rung ' + (r.commitment === "HARD_LOCK" ? "hard" : (r.commitment === "SOFT_LOCK" ? "soft" : "flex")) + '">' + esc(r.commitment) + '</span>' : "&mdash;") +
      '</td><td>' + (r.requires_renewed_consent ? '<span class="fs-state revised">needs renewed consent</span>' : "&mdash;") + '</td></tr>'
    ).join("");
    el.innerHTML =
      '<div class="fs-panel">' + modeBanner("working") +
      '<span class="fs-h-eyebrow">Stage 3 &middot; Replan</span><h2>Deterministic replanning <span class="fs-state revised">RECOMMENDED_REVISED</span></h2>' +
      teach({
        what: "FarmSync applied this plan\u2019s responses and commitment states through its action-consent + feasibility logic.",
        why: "Rejections, modifications and withdrawals change what is feasible; the plan is recomputed.",
        result: nChanged + " plot(s) received a revised recommendation.",
        meaning: "This is a revised recommendation, not a realised plan. Crop choice comes from the deterministic engine, not the LLM."
      }) +
      '<div class="fs-metrics" style="margin-top:12px">' +
      mtile("Plots changed", nChanged) +
      mtile("Revised working cash", rup(run.revised_cash)) +
      mtile("Engine", esc(run.engine)) +
      '</div>' +
      '<div class="fs-note-box warn" style="margin-top:12px"><b>This is a revised recommendation from the deterministic engine; it is NOT yet realised. Renewed consent is required for any changed crop.</b></div>' +
      '<div class="fs-cta-row" style="margin-top:10px"><button class="fs-btn" id="reRunReplan">Re-run replan</button><span class="fs-muted">Re-run only if you change responses.</span></div></div>' +
      '<div class="fs-panel"><h2>Changed recommendations <span class="fs-muted">(original &rarr; revised)</span></h2>' +
      (changed.length
        ? '<div class="fs-tablewrap"><table class="fs-tbl"><thead><tr><th>Farmer</th><th>Plot</th><th>Original &rarr; revised crop</th><th>Commitment</th><th>Consent</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
        : '<p class="fs-muted">No plots changed &mdash; every response kept its recommended crop, so nothing needs renewed consent.</p>') +
      nextCta("Request Renewed Consent", "consent") + '</div>';
    const rr = $("#reRunReplan");
    if (rr) rr.addEventListener("click", () => {
      rr.disabled = true; rr.textContent = "Running\u2026";
      fetch("/api/farmsync/working-plan/" + WORK.runId + "/replan", { method: "POST" })
        .then(r => r.json()).then(() => refreshWorkingRun().then(run2 => renderReplanResult(el, run2, run2.workflow || {}, true)));
    });
  }

  const lockClass = (l) => /hard/i.test(l) ? "hard" : (/soft/i.test(l) ? "soft" : "flex");

  /* ================= 4. RENEWED CONSENT ================= */
  loaders.consent = (el) => {
    // 0B: renewed consent ALWAYS rehydrates authoritative state via refreshWorkingRun(). Read-only on
    // open; every decision/browse re-derives workflow from the server. Single renewed-consent pass.
    loading(el);
    return ensureWorkingSession()
      .then(() => refreshWorkingRun())
      .then(run => {
        const wf = (run && run.workflow) || {};
        if (!wf.replan_current) {
          el.innerHTML = empty(
            wf.replan_stale ? "Your responses changed. Re-run Replan before renewed consent."
                            : "Run Replan before renewed consent.",
            '<button class="fs-btn fs-btn-primary fs-cta" data-ws="replan">Go to Replan</button>');
          return;
        }
        renderConsentStage(el, run, wf);
      })
      .catch(e => errbox(el, e.message));
  };

  function _consentStateOf(r, replanAnchor) {
    // valid decision ONLY for the EXACT current revised recommendation: same crop AND same replan
    // revision (mirrors the authoritative backend _valid_current_consent). A stale anchor -> PENDING,
    // even when the crop name is identical after a fresh replan.
    const cropOk = (r.consent_for_crop === r.revised_crop);
    const anchorOk = (r.consent_for_replan_anchor === replanAnchor);
    const valid = (cropOk && anchorOk) ? r.renewed_response : null;
    return valid || "PENDING";
  }

  function renderConsentStage(el, run, wf) {
    const changed = (run.recommendations || []).filter(r => r.changed && r.requires_renewed_consent);
    // summary counts computed from CURRENT run state
    let nAccept = 0, nReject = 0, nNo = 0, nPending = 0;
    const _anchor = run.replan_anchor;
    changed.forEach(r => { const st = _consentStateOf(r, _anchor); if (st === "ACCEPT") nAccept++; else if (st === "REJECT") nReject++; else if (st === "NO_RESPONSE") nNo++; else nPending++; });

    if (!changed.length) {
      el.innerHTML =
        '<div class="fs-panel">' + modeBanner("working") +
        '<span class="fs-h-eyebrow">Stage 4 &middot; Renewed consent</span><h2>No renewed consent required</h2>' +
        '<div class="fs-note-box info">No crop changed in the current replan, so no renewed consent is required. You can finalise directly.</div>' +
        nextCta("Finalise Consent-Verified Plan", "final") + '</div>';
      return;
    }

    const summary =
      '<div class="fs-metrics" style="margin-top:12px">' +
      mtile("Changed recommendations", changed.length) +
      mtile("Pending", nPending) + mtile("Accepted", nAccept) +
      mtile("Rejected", nReject) + mtile("No response", nNo) + '</div>';

    const bulk =
      '<div class="fs-cta-row" style="margin-top:10px"><span class="fs-muted">Bulk (pending only):</span>' +
      '<button class="fs-btn" id="bulkAccept"' + (nPending ? "" : " disabled") + '>Accept all pending</button>' +
      '<button class="fs-btn" id="bulkReject"' + (nPending ? "" : " disabled") + '>Reject all pending</button></div>';

    el.innerHTML =
      '<div class="fs-panel">' + modeBanner("working") +
      '<span class="fs-h-eyebrow">Stage 4 &middot; Renewed consent</span>' +
      '<h2>Decide on each changed crop <span class="fs-state revised">single consent pass</span></h2>' +
      teach({
        what: "Where the current Replan changed a crop, the farmer decides on that EXACT revised crop.",
        why: "A revised recommendation is not something the farmer already agreed to.",
        result: changed.length + " changed plot(s); " + nPending + " pending.",
        meaning: "Choosing a crop is not consent. Accept makes the exact crop eligible for realisation; reject / no response are never realised, with no fallback to the original crop."
      }) + summary + bulk +
      '<div id="consentCards" style="margin-top:12px">' + changed.map(r => consentCardHTML(r, _anchor)).join("") + '</div>' +
      nextCta("Finalise Consent-Verified Plan", "final") + '</div>';

    $("#bulkAccept") && $("#bulkAccept").addEventListener("click", () => bulkConsent("ACCEPT", el));
    $("#bulkReject") && $("#bulkReject").addEventListener("click", () => bulkConsent("REJECT", el));
    wireConsentCards(el);
  }

  function consentCardHTML(r, replanAnchor) {
    const st = _consentStateOf(r, replanAnchor);
    const decided = st !== "PENDING";
    const stChip = decided
      ? '<span class="fs-act ' + esc(st) + '">' + esc(st) + '</span>'
      : '<span class="fs-state revised">PENDING</span>';
    const actions = decided
      ? '<button class="fs-btn" data-edit="1">Edit response</button>'
      : '<button class="fs-btn fs-btn-primary" data-consent="ACCEPT">Accept recommendation</button>' +
        '<button class="fs-btn" data-consent="REJECT">Reject</button>' +
        '<button class="fs-btn" data-consent="NO_RESPONSE">No response</button>';
    return '<div class="fs-consent-card" data-fid="' + esc(r.farmer_id) + '" data-pid="' + esc(r.plot_id) + '">' +
      '<div class="fs-consent-head"><span class="mono fs-muted">' + esc(r.farmer_id) + ' / ' + esc(r.plot_id) + '</span> <span class="fs-consent-state">' + stChip + '</span></div>' +
      '<div class="fs-consent-crops"><div class="fs-cc-old"><div class="fs-muted">Original</div><div class="fs-cc-oldcrop">' + esc(r.crop) + '</div></div>' +
      '<span class="fs-cc-arrow">&rarr;</span>' +
      '<div class="fs-cc-new"><div class="fs-h-eyebrow">Current revised recommendation</div><div class="fs-cc-newcrop">' + esc(r.revised_crop) + '</div><div class="fs-cc-cash">' + rup(r.revised_cash) + '</div></div></div>' +
      '<div class="fs-consent-actions">' + actions + '</div>' +
      '<div class="fs-consent-extra"><button class="fs-btn fs-btn-sm" data-why-current="1">Ask why</button><button class="fs-btn fs-btn-sm" data-explore="1">Explore another option</button></div>' +
      '<div class="fs-consent-out"></div></div>';
  }

  function wireConsentCards(el) {
    const host = $("#consentCards"); if (!host) return;
    host.addEventListener("click", e => {
      const card = e.target.closest(".fs-consent-card"); if (!card) return;
      const fid = card.dataset.fid, pid = card.dataset.pid;
      const dec = e.target.closest("[data-consent]");
      const edit = e.target.closest("[data-edit]");
      // The parent handles ONLY the top-level current-recommendation Ask Why (data-why-current). Candidate
      // and original-return Ask Why (data-why-candidate) live inside .fs-consent-out and are wired locally
      // by wireConsentAltButtons — the parent must never claim them (that was the Ask-Why collision).
      const inExplore = e.target.closest(".fs-consent-out");
      const whyCurrent = e.target.closest("[data-why-current]");
      const explore = e.target.closest("[data-explore]");
      if (dec) return consentDecide(fid, pid, dec.dataset.consent, el);
      if (edit) { renderConsentEdit(card, fid, pid, el); return; }
      if (whyCurrent && !inExplore) return consentAskWhy(card, fid, pid);   // current revised crop only
      if (explore && !inExplore) return consentExplore(card, fid, pid, el);
    });
  }

  function consentDecide(fid, pid, decision, el) {
    fetch("/api/farmsync/working-plan/" + WORK.runId + "/consent", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ farmer_id: fid, plot_id: pid, renewed_response: decision }) })
      .then(r => r.json()).then(res => {
        if (!res.available) return;
        // 0B: rehydrate authoritative state; nav/stepper + Final unlock re-derive from server
        return refreshWorkingRun().then(run => renderConsentStage(el, run, run.workflow || {}));
      });
  }

  function renderConsentEdit(card, fid, pid, el) {
    // ACCEPT <-> REJECT <-> NO_RESPONSE before finalisation; overrides any prior (incl. bulk) decision
    const out = card.querySelector(".fs-consent-actions");
    out.innerHTML = '<span class="fs-muted">Edit:</span>' +
      '<button class="fs-btn fs-btn-primary" data-consent="ACCEPT">Accept</button>' +
      '<button class="fs-btn" data-consent="REJECT">Reject</button>' +
      '<button class="fs-btn" data-consent="NO_RESPONSE">No response</button>';
  }

  function consentAskWhy(card, fid, pid) {
    const out = card.querySelector(".fs-consent-out");
    out.innerHTML = '<div class="fs-note-box">Loading deterministic evidence\u2026</div>';
    // Ask Why is exact farmer + plot + CURRENT revised crop; reuse the deterministic /explain endpoint
    const r = wpRec(fid, pid) || {};
    fetch("/api/farmsync/working-plan/" + WORK.runId + "/explain", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ farmer_id: fid, plot_id: pid, crop: r.revised_crop }) })
      .then(res => res.json()).then(ex => {
        if (!ex.available) { out.innerHTML = '<div class="fs-errbox">' + esc(ex.error || "no explanation") + '</div>'; return; }
        out.innerHTML = renderExplain(ex);
      });
  }

  function renderExplain(ex) {
    const pc = ex.passed_constraints || {};
    const keys = Object.keys(pc);
    const chips = keys.length ? keys.map(k => '<span class="fs-chip">' + esc(k) + ': ' + esc(String(pc[k])) + '</span>').join("") : '<span class="fs-muted">Not evaluated</span>';
    const others = (ex.other_feasible_ranked || []).map(o => esc(o.crop)).join(", ");
    return '<div class="fs-note-box info"><b>Why ' + esc(ex.crop) + '?</b> ' +
      (ex.feasible ? 'Feasible for this exact plot' : 'Not feasible for this exact plot') +
      (ex.rank_among_feasible ? ', ranked #' + ex.rank_among_feasible + ' of ' + ex.n_feasible + ' by cash-positive projected return.' : '.') +
      '<div class="fs-h-eyebrow" style="margin-top:8px">Deterministic checks</div><div class="fs-req-files">' + chips + '</div>' +
      (ex.expected_cash != null ? '<p class="fs-muted" style="margin-top:6px">Projected return: ' + rup(ex.expected_cash) + '</p>' : '') +
      (others ? '<p class="fs-muted">Other feasible options: ' + others + '.</p>' : '') +
      (ex.rejected_alternatives && ex.rejected_alternatives.length ? '<p class="fs-muted">Excluded (rejected for this plan): ' + ex.rejected_alternatives.map(esc).join(", ") + '.</p>' : '') +
      '<p class="fs-muted" style="font-size:12px">' + esc(ex.basis) + ' The LLM only verbalises these validated facts; it never chooses the crop. This is read-only \u2014 nothing was changed.</p></div>';
  }

  function consentExplore(card, fid, pid, el, exclude) {
    // #1/#2/#3 Renewed-Consent browsing (READ-ONLY). Stage-specific: excludes the CURRENT revised crop,
    // persistent rejected_alternatives, and this browse sequence's viewed crops. Offers a "return to
    // original plan" option only when valid. Every candidate has Use / Ask why / Another option.
    const out = card.querySelector(".fs-consent-out");
    out.innerHTML = '<div class="fs-note-box">Finding another feasible option\u2026</div>';
    fetch("/api/farmsync/working-plan/" + WORK.runId + "/consent-alternative", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ farmer_id: fid, plot_id: pid, exclude: exclude || [] }) })
      .then(r => r.json()).then(rc => {
        const orig = rc.original_option;
        const origBtn = orig
          ? '<div class="fs-consent-orig"><b>Return to original plan &mdash; ' + esc(orig.crop) + '</b> <span class="fs-muted">(' + rup(orig.expected_cash) + ')</span> <button class="fs-btn fs-btn-sm" data-use="' + esc(orig.crop) + '">Use this</button> <button class="fs-btn fs-btn-sm" data-why-candidate="' + esc(orig.crop) + '">Ask why</button></div>'
          : "";
        if (!rc.available || !rc.found) {
          // #3 exhaustion: all currently available alternatives viewed -> restart temporary history only
          out.innerHTML =
            '<div class="fs-note-box warn"><b>All feasible alternatives viewed.</b> ' + esc((rc && rc.reason) || "") + '</div>' + origBtn +
            '<div class="fs-cta-row" style="margin-top:8px"><button class="fs-btn" data-restart="1">Review from beginning</button></div>' +
            '<div class="fs-consent-why"></div>';
          wireConsentAltButtons(out, card, fid, pid, el, []);
          return;
        }
        const offered = (exclude || []).concat([rc.recommended_crop]);   // this browse sequence's viewed
        out.innerHTML =
          '<div class="fs-note-box info"><b>Feasible alternative:</b> ' + esc(rc.recommended_crop) + ' <span class="fs-muted">(' + rup(rc.expected_cash) + ')</span> \u2014 ' + esc(rc.reason) +
          '<div class="fs-cta-row" style="margin-top:8px"><button class="fs-btn fs-btn-primary" data-use="' + esc(rc.recommended_crop) + '">Use this recommendation</button>' +
          '<button class="fs-btn" data-why-candidate="' + esc(rc.recommended_crop) + '">Ask why</button>' +
          (rc.n_more > 0 ? '<button class="fs-btn" data-more="' + esc(offered.join("|")) + '">Another option</button>' : '<span class="fs-muted"><b>All feasible alternatives viewed.</b></span><button class="fs-btn" data-restart="1">Review from beginning</button>') +
          '</div>' + origBtn +
          '<div class="fs-consent-why"></div>' +
          '<p class="fs-muted" style="font-size:12px">Browsing does not change the revised crop or grant consent. Only \u201cUse this recommendation\u201d replaces the current pending recommendation \u2014 which then needs a fresh renewed-consent decision.</p></div>';
        wireConsentAltButtons(out, card, fid, pid, el, offered);
      });
  }
  function wireConsentAltButtons(out, card, fid, pid, el, offered) {
    // Renewed Consent can render BOTH a normal "Use this recommendation" AND a "Return to original
    // plan → Use this". Bind EVERY [data-use], each sending its own exact crop.
    out.querySelectorAll("[data-use]").forEach(u => u.addEventListener("click", () => consentUseRecommendation(fid, pid, u.dataset.use, el)));
    const more = out.querySelector("[data-more]");
    if (more) more.addEventListener("click", () => consentExplore(card, fid, pid, el, more.dataset.more.split("|").filter(Boolean)));
    const restart = out.querySelector("[data-restart]");
    if (restart) restart.addEventListener("click", () => consentExplore(card, fid, pid, el, []));   // clears ONLY temp browse history
    // Ask why on the exact displayed candidate(s) (read-only /explain). Renders into the dedicated
    // .fs-consent-why div so it never replaces the exhaustion message / restart / original-return controls.
    out.querySelectorAll("[data-why-candidate]").forEach(w => w.addEventListener("click", () => {
      const host = out.querySelector(".fs-consent-why") || out;
      host.innerHTML = '<div class="fs-note-box">Loading deterministic evidence\u2026</div>';
      fetch("/api/farmsync/working-plan/" + WORK.runId + "/explain", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ farmer_id: fid, plot_id: pid, crop: w.dataset.whyCandidate }) })
        .then(r => r.json()).then(ex => { host.innerHTML = ex.available ? renderExplain(ex) : ('<div class="fs-errbox">' + esc(ex.error || "no explanation") + '</div>'); });
    }));
  }

  function consentUseRecommendation(fid, pid, crop, el) {
    // Server revalidates feasibility; replaces the pending revised crop; clears old consent -> PENDING.
    // Any server rejection must be visible to the farmer instead of looking like an inert button.
    fetch("/api/farmsync/working-plan/" + WORK.runId + "/select-recommendation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ farmer_id: fid, plot_id: pid, crop: crop })
    })
      .then(r => r.json().then(res => ({ ok: r.ok, res: res })))
      .then(x => {
        if (!x.ok || !x.res.available) {
          throw new Error(x.res.error || "could not select recommendation");
        }
        return refreshWorkingRun().then(run =>
          renderConsentStage(el, run, run.workflow || {})
        );
      })
      .catch(e => {
        const card = Array.from(el.querySelectorAll(".fs-consent-card"))
          .find(c => c.dataset.fid === fid && c.dataset.pid === pid);
        const out = card && card.querySelector(".fs-consent-out");
        if (out) {
          out.innerHTML =
            '<div class="fs-errbox">' + esc(e.message) + '</div>';
        }
      });
  }

  function bulkConsent(decision, el) {
    fetch("/api/farmsync/working-plan/" + WORK.runId + "/consent-bulk", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision: decision }) })
      .then(r => r.json()).then(res => {
        if (!res.available) return;
        return refreshWorkingRun().then(run => renderConsentStage(el, run, run.workflow || {}));
      });
  }

  /* ================= 5. FINAL PLAN ================= */
  loaders.final = (el) => {
    // §1 CRITICAL: Final Plan is READ-ONLY on open. It NEVER POSTs /finalise. Finalisation happens only
    // via the explicit "Finalise Consent-Verified Plan" action. Pagination re-reads current state only.
    loading(el);
    return ensureWorkingSession()
      .then(() => refreshWorkingRun())
      .then(run => {
        const wf = (run && run.workflow) || {};
        // Gate: Final Plan is reachable only when finalisable OR already finalised.
        if (!wf.finalisable && !wf.final_current) {
          const pend = wf.n_consent_pending || 0;
          el.innerHTML = empty(
            pend > 0
              ? (pend + " changed row(s) still need an explicit renewed-consent decision before finalising.")
              : "Run Replan and resolve renewed consent before finalising.",
            '<button class="fs-btn fs-btn-primary fs-cta" data-ws="consent">Go to Renewed Consent</button>'
          );
          return;
        }
        if (!wf.final_current) {
          // finalisable but not yet finalised -> explicit ready-to-finalise state (NO auto POST)
          renderFinalReadyToFinalise(el, run, wf);
          return;
        }
        // a CURRENT final revision exists -> render it read-only (paginated)
        renderFinalPlan(el, run, wf);
      })
      .catch(e => errbox(el, e.message));
  };

  function renderFinalReadyToFinalise(el, run, wf) {
    const changed = wf.n_changed || 0, req = wf.n_requires_consent || 0;
    el.innerHTML =
      '<div class="fs-panel">' + modeBanner("working") +
      '<span class="fs-h-eyebrow">Stage 5 &middot; Final plan</span>' +
      '<h2>Ready to finalise <span class="fs-state revised">not yet finalised</span></h2>' +
      teach({
        what: "Every changed row that required renewed consent now has an explicit decision.",
        why: "Finalisation realises only consent-verified allocations for the CURRENT revised crops.",
        result: changed + " changed plot(s); " + req + " required renewed consent (all resolved).",
        meaning: "This is an explicit action \u2014 opening this page does not finalise anything."
      }) +
      '<div class="fs-note-box info">Finalisation is an explicit step. It creates the current FINAL_REALIZED revision from the exact current responses, replan and renewed-consent decisions.</div>' +
      '<div class="fs-cta-row" style="margin-top:14px"><button class="fs-btn fs-btn-primary" id="doFinalise">Finalise Consent-Verified Plan</button></div>' +
      '<div id="finaliseOut"></div></div>';
    const b = $("#doFinalise");
    if (b) b.addEventListener("click", () => {
      b.disabled = true; b.textContent = "Finalising\u2026";
      // the ONLY place that POSTs /finalise
      fetch("/api/farmsync/working-plan/" + WORK.runId + "/finalise", { method: "POST" })
        .then(r => r.json()).then(fin => {
          if (!fin.available) {
            b.disabled = false; b.textContent = "Finalise Consent-Verified Plan";
            $("#finaliseOut").innerHTML = '<div class="fs-errbox">' + esc(fin.error || "could not finalise") + '</div>';
            return;
          }
          return refreshWorkingRun().then(() => { loaders.final(el); });   // re-render as read-only final
        })
        .catch(e => { b.disabled = false; b.textContent = "Finalise Consent-Verified Plan"; $("#finaliseOut").innerHTML = '<div class="fs-errbox">' + esc(e.message) + '</div>'; });
    });
  }

  function renderFinalPlan(el, run, wf) {
    // #4-#7 Final Plan: dataset-universe accounting with Realised / Not realised / All-plots filters.
    // READ-ONLY; filtering + pagination never POST/mutate. Five columns preserved; unrealised crop = —.
    wfCurrent = 4; renderWorkflow();
    const total = (run.population && run.population.plots) || (run.recommendations || []).length;
    const offered = (run.recommendations || []).length;
    const noOffer = total - offered;
    const realisedCount = (run.recommendations || []).filter(r => r.realised).length;
    const notRealised = total - realisedCount;
    const finalCash = (run.recommendations || []).reduce((a, r) => a + (r.realised ? (r.final_cash || 0) : 0), 0);

    el.innerHTML =
      '<div class="fs-panel">' + modeBanner("working") +
      '<span class="fs-h-eyebrow">Stage 5 &middot; Final plan</span>' +
      '<h2>Consent-verified realised plan <span class="fs-state final">FINAL_REALIZED</span></h2>' +
      teach({
        what: "The crops actually realised after responses, replan and renewed consent, accounted across the whole dataset.",
        why: "Only consent-verified allocations are realised; every dataset plot is accounted for.",
        result: realisedCount + " realised of " + total + " plots in the dataset.",
        meaning: "A plot is realised only with valid exact-crop consent. The planning model need not allocate a crop to every plot."
      }) +
      '<div class="fs-metrics" style="margin-top:12px">' +
      mtile("Plots in dataset", total) +
      mtile("Initially allocated / offered", offered) +
      mtile("No initial allocation", noOffer) +
      mtile("Finally realised", realisedCount) +
      mtile("Not realised", notRealised) +
      mtile("Final realised cash", rup(Math.round(finalCash))) +
      '</div>' +
      '<p class="fs-realised-key" style="margin-top:8px">Reconciliation: initially allocated + no initial allocation = ' + offered + ' + ' + noOffer + ' = ' + total + '; finally realised + not realised = ' + realisedCount + ' + ' + notRealised + ' = ' + total + '.</p></div>' +
      '<div class="fs-panel" id="finalTablePanel">' +
      '<div class="fs-filter-row"><span class="fs-muted">Show:</span>' +
      '<button class="fs-btn fs-filter is-active" data-filter="realised">Realised</button>' +
      '<button class="fs-btn fs-filter" data-filter="not_realised">Not realised</button>' +
      '<button class="fs-btn fs-filter" data-filter="all">All plots</button></div>' +
      '<h2 id="finalTableHeading">Final realised allocations</h2>' +
      '<p class="fs-muted" id="finalTableNote">All dataset plots remain accounted for. A dash does not mean the plot is missing; it means no crop was ultimately realised for that plot. Some plots received no initial allocation from the planning model.</p>' +
      '<div id="finalRowsWrap"><div class="fs-uploading"><span class="fs-spin"></span> Loading\u2026</div></div></div>';

    let FINAL_FILTER = "realised"; FINAL_PAGE = 1;
    const headings = { realised: "Final realised allocations", not_realised: "Plots not realised", all: "Final plan accounting \u2014 all dataset plots" };
    el.querySelectorAll(".fs-filter").forEach(b => b.addEventListener("click", () => {
      FINAL_FILTER = b.dataset.filter; FINAL_PAGE = 1;
      el.querySelectorAll(".fs-filter").forEach(x => x.classList.toggle("is-active", x === b));
      $("#finalTableHeading").textContent = headings[FINAL_FILTER];
      loadFinalRows(el, run, FINAL_FILTER);
    }));
    loadFinalRows(el, run, "realised");
  }

  var REASON_LABEL = {
    NO_INITIAL_OFFER: "no initial allocation",
    RENEWED_REJECT: "renewed reject",
    RENEWED_NO_RESPONSE: "renewed no response",
    WITHDRAW: "withdrawn",
    INITIAL_NO_RESPONSE: "initial no response",
    INITIAL_REJECT_NO_ALTERNATIVE: "initial reject \u2014 no feasible alternative",
    OTHER_NOT_REALISED: "not realised",
  };
  function humanReason(code) { return REASON_LABEL[code] || (code ? String(code).toLowerCase().replace(/_/g, " ") : "not realised"); }

  function loadFinalRows(el, run, filt) {
    filt = filt || "realised";
    fetch("/api/farmsync/working-plan/" + WORK.runId + "/final-rows?filter=" + encodeURIComponent(filt) + "&page=" + FINAL_PAGE)
      .then(r => r.json()).then(d => {
        if (!d.available) { $("#finalRowsWrap").innerHTML = '<div class="fs-errbox">could not load final rows</div>'; return; }
        FINAL_PAGE = d.page;
        // #7: realised -> realised crop; not realised -> — with the actual reason inside the Realised cell
        const realisedCell = (r) => r.realised
          ? '<span class="fs-run optimal">realised</span>'
          : '<span class="fs-run notrun">not realised &middot; ' + esc(humanReason(r.reason)) + '</span>';
        const rows = d.rows.map(r =>
          '<tr><td class="mono">' + esc(r.farmer_id) + '</td><td class="mono">' + esc(r.plot_id) +
          '</td><td>' + (r.realised ? esc(r.final_crop) : '<span class="fs-muted">&mdash;</span>') +
          '</td><td>' + (r.consent_basis ? '<span class="fs-state final">' + esc(r.consent_basis) + '</span>' : '<span class="fs-muted">&mdash;</span>') +
          '</td><td>' + realisedCell(r) + '</td></tr>'
        ).join("");
        // filter tab counts
        const cnt = d.counts || {};
        el.querySelectorAll(".fs-filter").forEach(b => {
          const k = b.dataset.filter; const n = cnt[k] != null ? cnt[k] : "";
          b.textContent = ({ realised: "Realised", not_realised: "Not realised", all: "All plots" }[k]) + (n !== "" ? " (" + n + ")" : "");
        });
        const empty = d.total === 0 ? '<tr><td colspan="5" class="fs-muted">No plots in this view.</td></tr>' : rows;
        const pager =
          '<div class="fs-pager" style="margin-top:10px"><span class="fs-muted">' + d.first + '\u2013' + d.last + ' of ' + d.total + '</span>' +
          '<button id="finalPrev" class="fs-btn"' + (d.page <= 1 ? " disabled" : "") + '>Previous</button>' +
          '<span class="fs-muted">Page ' + d.page + ' of ' + d.pages + '</span>' +
          '<button id="finalNext" class="fs-btn"' + (d.page >= d.pages ? " disabled" : "") + '>Next</button></div>';
        $("#finalRowsWrap").innerHTML =
          '<div class="fs-tablewrap"><table class="fs-tbl"><thead><tr><th>Farmer</th><th>Plot</th><th>Final crop</th><th>Consent basis</th><th>Realised</th></tr></thead><tbody>' + empty + '</tbody></table></div>' + pager +
          '<div class="fs-cta-row fs-next" style="margin-top:12px"><span class="fs-next-k">Next</span><button class="fs-btn fs-btn-primary" data-ws="fairness">Evaluate the Final Plan</button></div>';
        const fp = $("#finalPrev"); if (fp) fp.addEventListener("click", () => { if (FINAL_PAGE > 1) { FINAL_PAGE--; loadFinalRows(el, run, filt); } });
        const fn = $("#finalNext"); if (fn) fn.addEventListener("click", () => { if (FINAL_PAGE < d.pages) { FINAL_PAGE++; loadFinalRows(el, run, filt); } });
      });
  }

  function _effectiveResp(r) { return r.working_response || r.recorded_response || null; }

  /* ================= 6. EVALUATE ================= */
  // ============ DYNAMIC ANALYSE (CURRENT WORKING FINAL PLAN) ============
  // All three tabs render from ONE authoritative /analysis payload (final_current gated). Frozen
  // recorded-research analyses are NOT shown here (they live under Advanced / Research details).
  function loadAnalysis() {
    return ensureWorkingSession().then(() => refreshWorkingRun()).then(() =>
      fetch("/api/farmsync/working-plan/" + WORK.runId + "/analysis").then(r => r.json()));
  }
  function analyseUnavailable(el, a, title) {
    el.innerHTML = '<div class="fs-panel"><span class="fs-h-eyebrow">Analyse</span><h2>' + esc(title) + '</h2>' +
      '<div class="fs-note-box warn">' + esc((a && a.reason) || "Analyse is unavailable until the current plan is finalised.") + '</div>' +
      '<div class="fs-cta-row" style="margin-top:12px"><button class="fs-btn fs-btn-primary fs-cta" data-ws="final">Go to Final Plan</button></div></div>';
  }
  function analysisProvenance(a) {
    return '<div class="fs-note-box info"><b>CURRENT WORKING FINAL PLAN</b> \u2014 run ' + esc(a.run_id) +
      ', final revision ' + esc(a.final_plan_revision) + ', ' + esc(a.dataset_kind) + ' dataset (' + esc(a.dataset_hash) + '). ' +
      'These metrics describe the current working plan, not the recorded research/publication result.</div>';
  }
  function integrityBanner(a) {
    if (a.integrity && a.integrity.ok) return "";
    return '<div class="fs-errbox">Analysis integrity error: ' + esc((a.integrity && a.integrity.failures || []).join("; ")) + '. Metrics are withheld.</div>';
  }
  function integrityBlocked(el, a, title) {
    // If integrity failed, render ONLY the provenance + error and STOP — never show metrics as valid.
    if (a.integrity && a.integrity.ok) return false;
    el.innerHTML = '<div class="fs-panel"><span class="fs-h-eyebrow">Analyse</span><h2>' + esc(title) + '</h2>' +
      analysisProvenance(a) + integrityBanner(a) +
      '<div class="fs-note-box warn" style="margin-top:8px">Metrics are withheld because the current final plan failed a reconciliation invariant. Re-finalise the plan (or fix upstream state) to restore consistent metrics.</div></div>';
    return true;
  }
  function cleanUnavail(reason) {
    return (reason || "").replace(/^\s*not available\s*[\u2014:-]\s*/i, "");
  }
  function overviewBlock(a) {
    const o = a.overview, ih = a.initial_response_history, rc = a.renewed_consent_outcomes, nr = a.not_realised_reasons;
    const mt = (k, v) => mtile(k, v);
    const INIT_LABEL = { ACCEPT: "Accepted", REJECT: "Rejected", MODIFY: "Requested another crop", NO_RESPONSE: "No response", WITHDRAW: "Withdrawn" };
    const REN_LABEL = { RENEWED_ACCEPT: "Accepted", RENEWED_REJECT: "Rejected", RENEWED_NO_RESPONSE: "No response" };
    const initRows = ["ACCEPT", "REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW"].map(k => '<tr><td>' + INIT_LABEL[k] + '</td><td class="num">' + (ih[k] || 0) + '</td></tr>').join("");
    const renRows = ["RENEWED_ACCEPT", "RENEWED_REJECT", "RENEWED_NO_RESPONSE"].map(k => '<tr><td>' + REN_LABEL[k] + '</td><td class="num">' + (rc[k] || 0) + '</td></tr>').join("");
    const reasonRows = Object.keys(nr).sort((x, y) => nr[y] - nr[x]).map(k => '<tr><td>' + esc(humanReason(k)) + '</td><td class="num">' + nr[k] + '</td></tr>').join("");
    return '<div class="fs-panel">' + analysisProvenance(a) +
      '<span class="fs-h-eyebrow">Current final plan &middot; overview</span><h2>Consent &amp; participation outcomes</h2>' +
      '<div class="fs-metrics">' + mt("Total farmers", o.total_farmers) + mt("Total plots", o.total_plots) +
      mt("Offered plots", o.offered_plots) + mt("No initial offer", o.no_offer_plots) +
      mt("Realised", o.realised_plots) + mt("Not realised", o.not_realised_plots) +
      mt("Farmers with realised", o.farmers_with_realised) + mt("Farmers w/o realised", o.farmers_without_realised) +
      mt("Final-plan projected cash", rup(o.final_realised_cash)) +
      mt("Affirmative consent coverage", pct(o.affirmative_consent_coverage)) +
      mt("Realisation rate (offered)", pct(o.realisation_rate_offered)) +
      mt("Realisation rate (all plots)", pct(o.realisation_rate_all_plots)) + '</div>' +
      '<p class="fs-muted" style="font-size:12px">Affirmative consent coverage = realised / consent-eligible (' + o.n_consent_eligible + ' rows) &mdash; matches finalisation. REJECT / NO_RESPONSE are explicit outcomes, not affirmative consent, and remain in the renewed-consent accounting.</p>' +
      '<p class="fs-realised-key" style="margin-top:8px">Reconciliation: realised + not-realised = ' + o.realised_plots + ' + ' + o.not_realised_plots + ' = ' + o.total_plots + ' total plots. Offered + no-offer = ' + o.offered_plots + ' + ' + o.no_offer_plots + '.</p>' +
      '<div class="fs-analyse-grid" style="margin-top:12px">' +
      '<div><div class="fs-h-eyebrow">Initial farmer responses <span class="fs-muted">(' + a.n_offer_rows + ' offer rows; history only)</span></div><div class="fs-tablewrap"><table class="fs-tbl"><tbody>' + initRows + '</tbody></table></div><p class="fs-muted" style="font-size:12px">An initial REJECT may later become RENEWED_ACCEPT and be realised \u2014 initial history is not the final outcome.</p></div>' +
      '<div><div class="fs-h-eyebrow">Renewed consent on changed crops <span class="fs-muted">(' + a.n_requires_renewed_consent + ' rows)</span></div><div class="fs-tablewrap"><table class="fs-tbl"><tbody>' + renRows + '</tbody></table></div></div>' +
      '<div><div class="fs-h-eyebrow">Why not realised <span class="fs-muted">(sum = ' + o.not_realised_plots + ')</span></div><div class="fs-tablewrap"><table class="fs-tbl"><tbody>' + reasonRows + '</tbody></table></div></div>' +
      '</div></div>';
  }

  loaders.fairness = (el) => {
    loading(el);
    loadAnalysis().then(a => {
      if (!a || !a.available) return analyseUnavailable(el, a, "Fairness & concentration");
      if (integrityBlocked(el, a, "Fairness & concentration")) return;
      const f = a.fairness, cc = a.concentration;
      const giniCell = (v, reason) => v == null ? '<span class="fs-run notrun">' + esc(reason || "Not available") + '</span>' : v.toFixed(4);
      const comp = a.crop_composition_plots || {};
      const compRows = Object.keys(comp).sort((x, y) => comp[y] - comp[x]).map(k => '<tr><td>' + esc(k) + '</td><td class="num">' + comp[k] + '</td>' + (cc.per_crop_share && cc.per_crop_share[k] != null ? '<td class="num">' + (cc.per_crop_share[k] * 100).toFixed(1) + '%</td>' : '<td>&mdash;</td>') + '</tr>').join("");
      el.innerHTML = overviewBlock(a) +
        '<div class="fs-panel"><span class="fs-h-eyebrow">Current final plan &middot; fairness (fairness-v2)</span><h2>Fairness of projected returns on realised allocations</h2>' +
        '<p class="fs-lede">Projected cash net return per operated hectare across <b>all selected farmers</b>, including farmers with zero realised allocation.</p>' +
        '<div class="fs-metrics">' +
        mtile("All-farmer per-ha Gini", giniCell(f.all_farmer_per_ha_gini, f.per_ha_unavailable_reason)) +
        mtile("All-farmer absolute-cash Gini", giniCell(f.all_farmer_abs_cash_gini)) +
        mtile("Participant-only per-ha Gini", giniCell(f.participant_only_per_ha_gini, f.per_ha_unavailable_reason)) +
        mtile("Farmers", f.n_farmers) + mtile("Participants", f.n_participants) + mtile("Zero-realisation farmers", f.n_zero_realisation_farmers) +
        '</div>' + (f.per_ha_unavailable_reason ? '<div class="fs-note-box warn" style="margin-top:8px">' + esc(f.per_ha_unavailable_reason) + '</div>' : '') + '</div>' +
        '<div class="fs-panel"><span class="fs-h-eyebrow">Current final plan &middot; concentration (descriptive)</span><h2>Realised crop concentration</h2>' +
        (cc.available
          ? '<div class="fs-metrics">' + mtile("Active realised crops", cc.active_realised_crops) + mtile("Max crop share", (cc.max_crop_share * 100).toFixed(1) + "%") + mtile("HHI (crop share)", cc.hhi_crop_share) + mtile("Basis", esc(cc.basis)) + '</div>' +
            '<div class="fs-note-box caveat" style="margin-top:8px">' + esc(cc.note) + '</div>' +
            '<div class="fs-h-eyebrow" style="margin-top:12px">Realised composition <span class="fs-muted">(realised plots only)</span></div><div class="fs-tablewrap"><table class="fs-tbl"><thead><tr><th>Crop</th><th>Realised plots</th><th>' + (cc.basis === "area" ? "Area share" : "Plot share") + '</th></tr></thead><tbody>' + compRows + '</tbody></table></div>' +
            (cc.crops_above_reference && cc.crops_above_reference.length ? '<p class="fs-muted" style="margin-top:8px">Above the \u03b1=0.40 reference: ' + cc.crops_above_reference.map(esc).join(", ") + '.</p>' : '<p class="fs-muted" style="margin-top:8px">No crop exceeds the \u03b1=0.40 reference share.</p>')
          : '<div class="fs-note-box warn">' + esc(cc.reason) + '</div>') + nextCta("Continue to Uncertainty", "uncertainty") + '</div>';
    }).catch(e => errbox(el, e.message));
  };

  // ---------- Interactive scientific Analyse controls ----------
  function anaNum(v, digits) {
    if (v == null) return "&mdash;";
    const n = Number(v);
    if (!Number.isFinite(n)) return "&mdash;";
    const d = digits == null ? 0 : digits;
    return n.toLocaleString(undefined, {
      minimumFractionDigits: d,
      maximumFractionDigits: d
    });
  }

  function anaMoney(v) {
    if (v == null) return "&mdash;";
    const n = Number(v);
    if (!Number.isFinite(n)) return "&mdash;";
    return n < 0 ? "-" + rup(Math.abs(n)) : rup(n);
  }

  function anaPctRatio(v, digits) {
    if (v == null) return "&mdash;";
    const n = Number(v);
    if (!Number.isFinite(n)) return "&mdash;";
    return (n * 100).toFixed(digits == null ? 1 : digits) + "%";
  }

  function anaPctValue(v, digits) {
    if (v == null) return "&mdash;";
    const n = Number(v);
    if (!Number.isFinite(n)) return "&mdash;";
    return n.toFixed(digits == null ? 1 : digits) + "%";
  }

  function analysisScientificProvenance(x) {
    if (!x) return "";

    if (x.status === "STALE") {
      return '<div class="fs-note-box caveat" style="margin-top:10px">' +
        '<b>Saved analysis is stale.</b> Analysed final-plan hash <span class="mono">' +
        esc(x.analysed_final_plan_hash || "?") + '</span>, revision ' +
        esc(x.analysed_final_plan_revision == null ? "?" : x.analysed_final_plan_revision) +
        '; current hash <span class="mono">' +
        esc(x.current_final_plan_hash || "?") + '</span>, revision ' +
        esc(x.current_final_plan_revision == null ? "?" : x.current_final_plan_revision) +
        '. Old scientific metrics are withheld.' +
        '</div>';
    }

    const hash = x.final_plan_hash || x.current_final_plan_hash;
    const rev = x.final_plan_revision != null
      ? x.final_plan_revision
      : x.current_final_plan_revision;

    const bits = [];

    if (x.protocol_version) {
      bits.push('protocol <span class="mono">' + esc(x.protocol_version) + '</span>');
    }

    if (hash) {
      bits.push('final-plan hash <span class="mono">' + esc(hash) + '</span>');
    }

    if (rev != null) {
      bits.push('revision ' + esc(rev));
    }

    if (x.analysed_at) {
      bits.push('analysed ' + esc(x.analysed_at));
    }

    if (!bits.length) return "";

    const identityLabel = x.analysed_at
      ? "Analysis provenance:"
      : "Analysis target:";

    return '<div class="fs-note-box info" style="margin-top:10px"><b>' +
      identityLabel + '</b> ' +
      bits.join(' &middot; ') + '.</div>';
  }

  function analysisRunState(x) {
    const status = (x && x.status) || "NOT_RUN";

    if (status === "CURRENT") return "";

    const stale = status === "STALE";
    const label = stale ? "Re-run Analysis" : "Run Analysis";
    const reason = cleanUnavail(
      (x && x.reason) ||
      "This final plan has not yet been evaluated."
    );

    return '<div class="fs-note-box ' + (stale ? 'caveat' : 'warn') + '">' +
      '<b>' + (stale ? 'Analysis needs to be refreshed.' : 'Analysis has not been run yet.') + '</b> ' +
      esc(reason) +
      '</div>' +
      '<div class="fs-cta-row" style="margin-top:10px">' +
      '<button class="fs-btn fs-btn-primary" type="button" data-run-analysis="1">' +
      esc(label) +
      '</button>' +
      '</div>' +
      '<p class="fs-muted" style="font-size:12px;margin-top:8px">' +
      'Analysis runs only after this explicit action. Opening or refreshing this page never runs the scientific engines.' +
      '</p>';
  }

  function bindRunAnalysis(el, workspace) {
    const btn = el.querySelector("[data-run-analysis]");
    if (!btn) return;

    btn.addEventListener("click", () => {
      const oldText = btn.textContent;

      btn.disabled = true;
      btn.textContent = "Running analysis\u2026";

      fetch(
        "/api/farmsync/working-plan/" + WORK.runId + "/run-analysis",
        { method: "POST" }
      )
        .then(r => r.json().then(body => ({ ok: r.ok, body })))
        .then(({ ok, body }) => {
          if (!ok || !body || !body.available) {
            throw new Error(
              (body && (body.error || body.reason)) ||
              "Interactive analysis could not be completed."
            );
          }

          return refreshWorkingRun();
        })
        .then(() => loaders[workspace](el))
        .catch(e => {
          btn.disabled = false;
          btn.textContent = oldText;
          errbox(el, e.message);
        });
    });
  }

  function uncertaintyCurrentHtml(a, u) {
    const sc = u.scenarios || {};
    const uw = (sc.UW && sc.UW.weather) || {};
    const um = (sc.UM && sc.UM.market) || {};
    const ur = (sc.UR && sc.UR.resources) || {};
    const uj = sc.UJ || {};
    const base = u.baseline || {};
    const absorption = um.absorption || {};

    const absorptionRows = Object.keys(absorption)
      .sort()
      .map(crop => {
        const r = absorption[crop] || {};

        return '<tr>' +
          '<td>' + esc(crop) + '</td>' +
          '<td class="num">' + anaNum(r.realised_area_ha, 3) + '</td>' +
          '<td class="num">' + anaNum(r.stressed_area_cap_ha, 3) + '</td>' +
          '<td>' +
          (r.available === false
            ? '<span class="fs-run notrun">Unavailable</span>'
            : r.exposed
              ? '<span class="fs-run notrun">Exposed</span>'
              : '<span class="fs-run optimal">Within cap</span>') +
          '</td>' +
          '</tr>';
      })
      .join("");

    const absorptionTable = absorptionRows
      ? '<div class="fs-h-eyebrow" style="margin-top:14px">Market-throughput exposure by realised crop</div>' +
        '<div class="fs-tablewrap"><table class="fs-tbl">' +
        '<thead><tr><th>Crop</th><th>Realised area (ha)</th><th>Stressed area cap (ha)</th><th>Status</th></tr></thead>' +
        '<tbody>' + absorptionRows + '</tbody></table></div>'
      : '';

    return analysisProvenance(a) +
      '<div class="fs-panel">' +
      '<span class="fs-h-eyebrow">Current final plan &middot; interactive-stress-v1</span>' +
      '<h2>Uncertainty sensitivity of the realised plan</h2>' +

      '<p class="fs-lede">A deterministic fixed-plan sensitivity check. The final allocation is held unchanged: no rejected, withdrawn, no-offer or non-realised plot is reintroduced, and no reoptimisation is performed.</p>' +

      '<div class="fs-metrics">' +
      mtile("Realised area", anaNum(base.realised_area_ha, 3) + " ha") +
      mtile("Baseline projected cash", anaMoney(base.cash_net_return)) +
      mtile("Selected dataset area", anaNum(u.selected_dataset_area_ha, 3) + " ha") +
      mtile("Final-plan revision", esc(u.final_plan_revision)) +
      '</div>' +

      analysisScientificProvenance(u) +

      '<div class="fs-panel" style="margin-top:12px">' +
      '<span class="fs-h-eyebrow">UW &middot; weather sensitivity</span>' +
      '<h3>Higher evaporative demand</h3>' +
      '<div class="fs-metrics">' +
      mtile("ET0 multiplier", uw.et0_multiplier == null ? "?" : "&times;" + anaNum(uw.et0_multiplier, 2)) +
      mtile("Water-exposed plots", uw.n_water_exposed_plots == null ? "?" : uw.n_water_exposed_plots) +
      mtile("Water-exposed area", anaNum(uw.water_exposed_area_ha, 3) + " ha") +
      mtile("Baseline cash on exposed plots", anaMoney(uw.baseline_cash_at_water_exposure)) +
      '</div>' +
      '<div class="fs-note-box caveat" style="margin-top:8px">' +
      'Weather exposure is based on the higher ET0 state increasing crop-water requirement and net irrigation requirement. ' +
      '<b>This is exposure, not a predicted cash loss.</b> interactive-stress-v1 does not invent a weather-yield penalty.' +
      '</div>' +
      '</div>' +

      '<div class="fs-panel" style="margin-top:12px">' +
      '<span class="fs-h-eyebrow">UM &middot; market sensitivity</span>' +
      '<h3>Lower price and lower absorption throughput</h3>' +
      '<div class="fs-metrics">' +
      mtile("Price multiplier", um.price_multiplier == null ? "?" : "&times;" + anaNum(um.price_multiplier, 2)) +
      mtile("Baseline projected cash", anaMoney(um.baseline_cash_net_return)) +
      mtile("Price-stressed projected cash", anaMoney(um.stressed_cash_net_return)) +
      mtile("Projected cash change", anaMoney(um.cash_change)) +
      mtile("Relative projected cash change", anaPctValue(um.cash_change_pct, 2)) +
      mtile("Absorption-exposed crops", um.n_absorption_exposed_crops == null ? "?" : um.n_absorption_exposed_crops) +
      '</div>' +
      '<div class="fs-note-box caveat" style="margin-top:8px">' +
      'The absorption measure is an <b>AGMARKNET-arrivals-derived throughput proxy</b>, not empirical demand. ' +
      'The stressed crop-area cap is the throughput proxy multiplied by total selected dataset area. ' +
      'The existing allocation is not changed. Because cultivation cash costs are held fixed while revenue falls with price, a 10% price reduction can produce a larger percentage change in projected net cash.' +
      '</div>' +
      absorptionTable +
      '</div>' +

      '<div class="fs-panel" style="margin-top:12px">' +
      '<span class="fs-h-eyebrow">UR &middot; resource sensitivity</span>' +
      '<h3>Reduced farmer budget and labour capacity</h3>' +
      '<div class="fs-metrics">' +
      mtile("Capacity multiplier", ur.resource_multiplier == null ? "?" : "&times;" + anaNum(ur.resource_multiplier, 2)) +
      mtile("Exposed farmers", ur.n_exposed_farmers == null ? "?" : ur.n_exposed_farmers) +
      mtile("Exposed plots", ur.n_exposed_plots == null ? "?" : ur.n_exposed_plots) +
      '</div>' +
      '<div class="fs-note-box caveat" style="margin-top:8px">' +
      'The fixed realised plan is checked against reduced cultivation-budget and labour capacities. ' +
      'Projected cash is not mechanically scaled by the resource multiplier.' +
      '</div>' +
      '</div>' +

      '<div class="fs-panel" style="margin-top:12px">' +
      '<span class="fs-h-eyebrow">UJ &middot; joint W + M + R sensitivity</span>' +
      '<h3>Combined adverse sensitivity state</h3>' +
      '<div class="fs-metrics">' +
      mtile("Channels", esc((uj.channels || []).join(" + ") || "W + M + R")) +
      mtile("Plots with weather/resource exposure",
        uj.n_plots_with_weather_or_resource_exposure == null
          ? "?"
          : uj.n_plots_with_weather_or_resource_exposure) +
      mtile("Area with weather/resource exposure",
        anaNum(uj.area_with_weather_or_resource_exposure, 3) + " ha") +
      mtile("Baseline cash on W/R exposed plots",
        anaMoney(uj.baseline_cash_at_weather_or_resource_exposure)) +
      '</div>' +
      '<div class="fs-note-box info" style="margin-top:8px">' +
      'UJ combines the weather, market and resource channels on the same fixed allocation. ' +
      'FarmSync does not add unsupported weather/resource cash penalties to the market-price effect.' +
      '</div>' +
      '</div>' +

      nextCta("Continue to Resilience", "resilience") +
      '</div>';
  }

  function resilienceCurrentHtml(a, rr) {
    const base = rr.baseline || {};
    const n1 = rr.nminus1_representative || {};
    const hz = rr.hazard_zone_outage || {};
    const rep = hz.representative || {};
    const recovery = rr.post_shock_recovery || {};

    const recoveryReason = (
      recovery.reason ||
      "The frozen Phase-5 backup optimiser is defined over its own Stage-3/Stage-5 decision state and is not applied to this working plan."
    )
      .replace(/^Post-shock recovery:\s*/i, "")
      .replace(/^Not evaluated for the current interactive plan\.\s*/i, "");

    const zones = hz.all_realised_zones || [];

    const zoneRows = zones.map(z =>
      '<tr>' +
      '<td>' + esc(z.zone) + '</td>' +
      '<td class="num">' + esc(z.affected_allocations) + '</td>' +
      '<td class="num">' + anaNum(z.affected_area_ha, 3) + '</td>' +
      '<td class="num">' + anaMoney(z.immediate_expected_cash_loss) + '</td>' +
      '<td class="num">' + anaPctRatio(z.cash_loss_fraction, 1) + '</td>' +
      '</tr>'
    ).join("");

    const zoneTable = zoneRows
      ? '<div class="fs-h-eyebrow" style="margin-top:14px">Immediate exposure across all realised hazard zones</div>' +
        '<div class="fs-tablewrap"><table class="fs-tbl">' +
        '<thead><tr><th>Hazard zone</th><th>Affected plots</th><th>Affected area (ha)</th><th>Expected cash exposure</th><th>Cash share</th></tr></thead>' +
        '<tbody>' + zoneRows + '</tbody></table></div>'
      : '';

    return analysisProvenance(a) +
      '<div class="fs-panel">' +
      '<span class="fs-h-eyebrow">Current final plan &middot; interactive-resilience-v1</span>' +
      '<h2>Immediate resilience exposure</h2>' +

      '<p class="fs-lede">Deterministic counterfactual exposure of the exact FINAL_REALIZED allocation. A failed farmer or affected hazard zone becomes physically unavailable; surviving plots are not reallocated.</p>' +

      '<div class="fs-metrics">' +
      mtile("Realised plots", base.n_realised_plots) +
      mtile("Realised area", anaNum(base.realised_area_ha, 3) + " ha") +
      mtile("Projected realised cash", anaMoney(base.expected_cash_net_return)) +
      mtile("Active crops", base.n_active_crops) +
      mtile("Realised hazard zones", base.n_realised_hazard_zones) +
      '</div>' +

      analysisScientificProvenance(rr) +

      '<div class="fs-panel" style="margin-top:12px">' +
      '<span class="fs-h-eyebrow">N&minus;1 producer failure</span>' +
      '<h3>Largest-producer exposure</h3>' +
      '<div class="fs-metrics">' +
      mtile("Target crop", esc(n1.target_crop || "?")) +
      mtile("Failed farmer", esc(n1.failed_farmer || "?")) +
      mtile("Pre-shock largest-producer share", anaPctRatio(n1.pre_shock_largest_producer_share, 1)) +
      mtile("Affected realised plots", n1.affected_allocations == null ? "?" : n1.affected_allocations) +
      mtile("Affected area", anaNum(n1.failed_area_ha, 3) + " ha") +
      mtile("Target production loss", anaPctRatio(n1.target_loss_fraction, 1)) +
      mtile("Immediate expected cash exposure", anaMoney(n1.immediate_expected_cash_loss)) +
      mtile("Expected cash remaining", anaMoney(n1.immediate_remaining_expected_cash)) +
      '</div>' +
      '<div class="fs-note-box caveat" style="margin-top:8px">' +
      'Selection mirrors the frozen resilience demonstration where applicable: the active crop with the maximum pre-shock largest-producer share is selected, then <b>all realised allocations of that farmer</b> are treated as unavailable. ' +
      'No backup plan is generated.' +
      '</div>' +
      '</div>' +

      '<div class="fs-panel" style="margin-top:12px">' +
      '<span class="fs-h-eyebrow">Hazard-zone outage</span>' +
      '<h3>Correlated spatial exposure</h3>' +
      '<div class="fs-metrics">' +
      mtile("Protocol representative zone", esc(rep.zone || "?")) +
      mtile("Affected realised plots", rep.affected_allocations == null ? "?" : rep.affected_allocations) +
      mtile("Affected area", anaNum(rep.affected_area_ha, 3) + " ha") +
      mtile("Immediate expected cash exposure", anaMoney(rep.immediate_expected_cash_loss)) +
      mtile("Expected cash remaining", anaMoney(rep.immediate_remaining_expected_cash)) +
      mtile("Cash exposure share", anaPctRatio(rep.cash_loss_fraction, 1)) +
      '</div>' +
      '<div class="fs-note-box caveat" style="margin-top:8px">' +
      'The representative scenario is the lexicographically first non-empty hazard zone in the realised plan, matching the frozen integration-demo selection rule. The table below reports the same immediate-exposure calculation for every realised zone without optimisation.' +
      '</div>' +
      zoneTable +
      '</div>' +

      '<div class="fs-note-box warn" style="margin-top:12px">' +
      '<b>Post-shock recovery is not evaluated for this interactive plan.</b> ' +
      esc(recoveryReason) +
      '</div>' +

      '<div class="fs-note-box info" style="margin-top:12px">' +
      '<b>Analysis complete.</b> These uncertainty and resilience results describe this exact working final-plan revision only.' +
      '</div>' +

      '<div class="fs-cta-row" style="margin-top:10px">' +
      '<button class="fs-btn fs-btn-primary" data-ws="final">Review Final Plan</button>' +
      '<button class="fs-btn" data-ws="repro">Research details &amp; reproducibility</button>' +
      '</div>' +
      '</div>';
  }

  loaders.uncertainty = (el) => {
    loading(el);

    loadAnalysis().then(a => {
      if (!a || !a.available) {
        return analyseUnavailable(el, a, "Uncertainty");
      }

      if (integrityBlocked(el, a, "Uncertainty")) return;

      const u = a.uncertainty || {};

      if (!u.available) {
        el.innerHTML =
          analysisProvenance(a) +
          '<div class="fs-panel">' +
          '<span class="fs-h-eyebrow">Current final plan &middot; uncertainty</span>' +
          '<h2>Uncertainty sensitivity of the realised plan</h2>' +
          analysisRunState(u) +
          analysisScientificProvenance(u) +
          '<p class="fs-muted" style="margin-top:10px">' +
          'The interactive protocol evaluates UW (weather), UM (market), UR (resources) and UJ (joint W + M + R) on the fixed final allocation. Participation uncertainty is intentionally excluded after finalisation.' +
          '</p>' +
          nextCta("Continue to Resilience", "resilience") +
          '</div>';

        bindRunAnalysis(el, "uncertainty");
        return;
      }

      el.innerHTML = uncertaintyCurrentHtml(a, u);
    }).catch(e => errbox(el, e.message));
  };

  loaders.resilience = (el) => {
    loading(el);

    loadAnalysis().then(a => {
      if (!a || !a.available) {
        return analyseUnavailable(el, a, "Resilience");
      }

      if (integrityBlocked(el, a, "Resilience")) return;

      const rr = a.resilience || {};

      if (!rr.available) {
        el.innerHTML =
          analysisProvenance(a) +
          '<div class="fs-panel">' +
          '<span class="fs-h-eyebrow">Current final plan &middot; resilience</span>' +
          '<h2>Immediate resilience exposure</h2>' +
          analysisRunState(rr) +
          analysisScientificProvenance(rr) +
          '<p class="fs-muted" style="margin-top:10px">' +
          'interactive-resilience-v1 evaluates immediate N\u22121 producer-failure and hazard-zone exposure only. It does not run the frozen Phase-5 backup optimiser.' +
          '</p>' +
          '</div>';

        bindRunAnalysis(el, "resilience");
        return;
      }

      el.innerHTML = resilienceCurrentHtml(a, rr);
    }).catch(e => errbox(el, e.message));
  };

  /* ================= RESEARCH: DATA / REPRO ================= */

  function explorerValidationHtml(v) {
    const rd = v.readiness || {};
    const passed = !!v.passed;
    const ready = passed && !!rd.ready_to_plan;
    const pop = v.dataset_summary || {};
    const caps = rd.capabilities || {};

    const capHtml = Object.keys(caps).length
      ? Object.keys(caps).map(k => {
          const c = caps[k] || {};
          return '<div class="fs-metric"><div class="k">' +
            esc(c.label || k) +
            '</div><div class="v small">' +
            (c.ready
              ? '<span class="fs-run optimal">Ready</span>'
              : '<span class="fs-run notrun">Missing</span>') +
            '</div>' +
            (c.missing && c.missing.length
              ? '<div class="sub">needs ' + c.missing.map(esc).join(", ") + '</div>'
              : '') +
            '</div>';
        }).join("")
      : '<div class="fs-muted">No capability breakdown returned.</div>';

    const missCols = rd.missing_plot_columns && rd.missing_plot_columns.length
      ? '<div class="fs-note-box warn" style="margin-top:10px"><b>Missing planning inputs:</b> ' +
        rd.missing_plot_columns.map(esc).join(", ") +
        '.</div>'
      : '';

    return '<div class="fs-explorer-validation">' +
      '<div class="fs-explorer-headline"><span class="fs-run optimal">Dataset</span> <b>FarmSync research dataset</b> <span class="fs-muted">&middot; ' +
      esc(pop.farmers) +
      ' farmers &middot; ' +
      esc(pop.plots) +
      ' plots</span></div>' +
      '<div class="fs-validation-title">Dataset Validation: <span class="fs-verdict ' +
      (passed ? 'pass' : 'fail') +
      '">' +
      (passed ? 'PASS' : 'ISSUES') +
      '</span></div>' +
      '<div class="fs-metrics">' +
      '<div class="fs-metric"><div class="k">Files</div><div class="v">' + esc(v.n_files) + '</div></div>' +
      '<div class="fs-metric"><div class="k">Errors</div><div class="v">' + esc(v.n_errors) + '</div></div>' +
      '<div class="fs-metric"><div class="k">Warnings</div><div class="v">' + esc(v.n_warnings) + '</div></div>' +
      '<div class="fs-metric"><div class="k">Planning readiness</div><div class="v small">' +
      (ready
        ? '<span class="fs-run optimal">READY</span>'
        : '<span class="fs-run notrun">NOT READY</span>') +
      '</div></div></div>' +
      '<div class="fs-note-box ' +
      (ready ? 'info' : 'warn') +
      '" style="margin-top:10px"><b>Structural validation and planning readiness are separate.</b> ' +
      (ready
        ? 'This built-in dataset passes validation and has the inputs required by the current planning-readiness checks.'
        : 'The dataset may structurally validate while some planning inputs remain unavailable.') +
      '</div>' +
      missCols +
      '<div class="fs-h-eyebrow" style="margin-top:14px">Capability readiness</div><div class="fs-metrics">' +
      capHtml +
      '</div>' +
      '<div class="fs-explorer-provenance"><span class="fs-muted">Read-only validation source:</span> ' +
      esc(v.source || 'Built-in research dataset') +
      (v.dataset_hash
        ? ' &middot; <span class="mono">dataset hash ' + esc(v.dataset_hash) + '</span>'
        : '') +
      '</div>' +
      '</div>';
  }

  loaders.data = (el) => {
    loading(el);

    api("/api/farmsync/explore-validation")
      .then(v => {
        el.innerHTML =
          '<div class="fs-panel"><span class="fs-h-eyebrow">Data Explorer</span><h2>Inspect the data</h2>' +
          '<p class="fs-lede">Read-only validation, readiness and table inspection for the FarmSync research dataset. Planning dataset selection and custom upload remain on <b>Home</b>.</p>' +
          '<div class="fs-note-box warn">AGMARKNET arrivals = absorption proxy, NOT demand. Yields from DES APY; costs from DES Cost of Cultivation (A2+FL / C2); water from FAO-56 CWR/NIR with effective rainfall. Provenance labels: OBSERVED &middot; DERIVED &middot; SYNTHETIC_GROUNDED &middot; SYNTHETIC_EXPERIMENTAL.</div>' +
          (DATASET && DATASET.kind === "custom"
            ? '<div class="fs-note-box info">A custom dataset is currently selected for planning. This Data Explorer shows the built-in research dataset for reference and does not alter that custom planning source.</div>'
            : "") +
          explorerValidationHtml(v) +
          '<div class="fs-h-eyebrow" style="margin-top:22px">Browse dataset</div><div id="explorerMount" class="fs-explorer-mount"></div></div>';

        mountExplorer($("#explorerMount"));
      })
      .catch(e => errbox(el, e.message));
  };

  function mountExplorer(host) {
    if (!host) return;
    host.hidden = false;

    host.innerHTML =
      '<div class="fs-explorer">' +
      '<div class="fs-inspect-head"><select id="exTable" aria-label="Dataset table"></select><input type="search" id="exSearch" placeholder="Filter rows&hellip;"></div>' +
      '<div class="fs-tablewrap"><table id="exTableEl" class="fs-tbl"><thead></thead><tbody></tbody></table></div>' +
      '<div class="fs-pager"><button id="exPrev" class="fs-btn">Prev</button><span id="exPageInfo" class="fs-muted"></span><button id="exNext" class="fs-btn">Next</button></div></div>';

    let exTable = null;
    let exPage = 1;

    const load = () => {
      if (!exTable) return;

      const qs = encodeURIComponent($("#exSearch").value || "");

      fetch("/api/farmsync/explore/" + encodeURIComponent(exTable) + "?page=" + exPage + "&q=" + qs)
        .then(r => r.json())
        .then(d => {
          if (d.error) return;

          $("#exTableEl thead").innerHTML =
            "<tr>" +
            (d.headers || []).map(h => "<th>" + esc(h) + "</th>").join("") +
            "</tr>";

          $("#exTableEl tbody").innerHTML =
            (d.rows || []).map(r =>
              "<tr>" +
              (d.headers || []).map(h => "<td>" + esc(r[h]) + "</td>").join("") +
              "</tr>"
            ).join("");

          $("#exPageInfo").textContent =
            "Page " + d.page + " · " + d.total + " rows";
        });
    };

    fetch("/api/farmsync/explore-tables")
      .then(r => r.json())
      .then(t => {
        const sel = $("#exTable");

        sel.innerHTML = (t.tables || [])
          .map(f => '<option>' + esc(f.replace(".csv", "")) + '</option>')
          .join("");

        exTable = (t.tables && t.tables[0])
          ? t.tables[0].replace(".csv", "")
          : null;

        load();
      });

    $("#exTable").addEventListener("change", e => {
      exTable = e.target.value;
      exPage = 1;
      load();
    });

    $("#exSearch").addEventListener("input", () => {
      exPage = 1;
      load();
    });

    $("#exPrev").addEventListener("click", () => {
      if (exPage > 1) {
        exPage--;
        load();
      }
    });

    $("#exNext").addEventListener("click", () => {
      exPage++;
      load();
    });

  }

  function mountDM(host, opts) {
    host = host || $("#dmMount");
    if (!host) return;

    host.hidden = false;

    if (!host.querySelector(".fs-dm-root")) {
      const frag = $("#fsDatasetTpl").content.cloneNode(true);
      host.appendChild(frag);

      if (opts && opts.mode === "select") {
        const root = host.querySelector(".fs-dm-root");
        const builtinCard = root.querySelector(".fs-modes .fs-card:first-child");
        if (builtinCard) builtinCard.remove();

        const replace = root.querySelector(".fs-replace");
        if (replace) replace.remove();
      }

      initDatasetManager(host, opts || {});
    }

    host.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function autoLoadBuiltin(host) {
    const b = (host || document).querySelector("#btnBuiltin");
    if (b) b.click();
  }

  /* ================= FROZEN PUBLICATION RESULTS ================= */

  function pubMoney(v) {
    const n = Number(v);

    if (!Number.isFinite(n)) {
      return "&mdash;";
    }

    const abs = Math.abs(
      Math.round(n)
    ).toLocaleString("en-IN");

    return (
      n < 0
        ? "-&#8377;" + abs
        : "&#8377;" + abs
    );
  }

  function pubNum(v, digits) {
    const n = Number(v);

    if (!Number.isFinite(n)) {
      return "&mdash;";
    }

    return n.toLocaleString(
      "en-IN",
      {
        maximumFractionDigits:
          digits == null ? 3 : digits
      }
    );
  }

  function pubPctRatio(v) {
    const n = Number(v);

    if (!Number.isFinite(n)) {
      return "&mdash;";
    }

    return (
      (n * 100).toFixed(2)
      + "%"
    );
  }

  function pubPctValue(v) {
    const n = Number(v);

    if (!Number.isFinite(n)) {
      return "&mdash;";
    }

    return (
      n.toFixed(2)
      + "%"
    );
  }

  function pubPp(v) {
    const n = Number(v);

    if (!Number.isFinite(n)) {
      return "&mdash;";
    }

    return (
      (n * 100).toFixed(2)
      + " pp"
    );
  }

  function pubPpValue(v) {
    const n = Number(v);

    if (!Number.isFinite(n)) {
      return "&mdash;";
    }

    return n.toFixed(2) + " pp";
  }

  function pubSame(a, b) {
    if (
      a === undefined || a === null ||
      b === undefined || b === null
    ) {
      return "&mdash;";
    }

    return (
      String(a) === String(b)
        ? "Same"
        : "Changed"
    );
  }

  let FINAL30_CACHE = null;

  function final30Data() {
    if (!FINAL30_CACHE) {
      FINAL30_CACHE = api("/api/farmsync/final30-results").then(d => {
        if (!d || !d.available || !d.integrity || !d.integrity.verified) {
          throw new Error((d && d.error) || "Sealed Final30 analysis is unavailable.");
        }
        return d;
      });
    }
    return FINAL30_CACHE;
  }

  function f30Find(rows, criteria) {
    return (rows || []).find(r => Object.keys(criteria).every(k => String(r[k]) === String(criteria[k]))) || null;
  }

  function f30P(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "&mdash;";
    return n < 0.001 ? "&lt;0.001" : n.toFixed(3);
  }

  function f30Money(v) { return pubMoney(v); }
  function f30Pct(v, digits) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "&mdash;";
    return n.toFixed(digits == null ? 1 : digits) + "%";
  }

  function f30CiMoney(row) {
    if (!row) return "&mdash;";
    return f30Money(row.bootstrap_95_ci_low) + " to " + f30Money(row.bootstrap_95_ci_high);
  }

  function f30Table(headers, rows) {
    return '<div class="fs-tablewrap"><table class="fs-tbl"><thead><tr>' +
      headers.map(h => '<th>' + esc(h) + '</th>').join("") +
      '</tr></thead><tbody>' + rows.join("") + '</tbody></table></div>';
  }

  function f30Cells(values) {
    return '<tr>' + values.map(v => '<td>' + (v == null ? "&mdash;" : v) + '</td>').join("") + '</tr>';
  }

  function f30Counts(v) {
    if (!v) return "&mdash;";
    try {
      const obj = typeof v === "string" ? JSON.parse(v) : v;
      const entries = Object.entries(obj || {});
      if (!entries.length) return "None";
      return entries.map(x => esc(x[0]) + " × " + esc(x[1])).join("<br>");
    } catch (e) {
      return esc(v);
    }
  }

  function f30Details(title, headers, rows) {
    return '<details class="fs-panel fs-results-details"><summary>' + esc(title) + '</summary><div class="fs-results-details-body">' +
      f30Table(headers, rows) + '</div></details>';
  }

  function f30Figure(d, number, caption) {
    const item = ((d.figures || {}).figures || []).find(x => Number(x.figure) === Number(number));
    if (!item || !item.png) return "";
    const file = String(item.png).split("/").pop();
    return '<figure class="fs-result-figure"><img loading="lazy" src="/api/farmsync/final30-figure/' +
      encodeURIComponent(file) + '" alt="' + esc(item.title || caption || ("Figure " + number)) + '">' +
      '<figcaption><b>Figure ' + esc(number) + '.</b> ' + esc(caption || item.description || item.title || "") + '</figcaption></figure>';
  }

  function f30Bootstrap(n, family, parameter, method, state, metric) {
    return f30Find(n.bootstrap_confidence_intervals, {
      family: family, parameter: parameter, method: method, state: state, metric: metric
    });
  }

  loaders.final30 = (el) => {
    loading(el);
    return final30Data().then(d => {
      const n = d.numbers || {}, p = n.primary || {};
      const family = n.family_solver_reliability || [];
      const clean = family.reduce((s, r) => s + Number(r.optimal_or_clean_cells || 0), 0);
      const nonclean = family.reduce((s, r) => s + Number(r.nonoptimal_cells || 0), 0);
      const rel = p.reliability || {};
      const primarySpecs = [
        ["B1", "PLANNED", "B1"], ["B2", "PLANNED", "B2"], ["B3", "PLANNED", "B3"],
        ["PROPOSED", "PLANNED", "Proposed"], ["PROPOSED", "INITIAL_REALIZED", "Proposed"],
        ["PROPOSED", "RECOMMENDED_REVISED", "Proposed"], ["PROPOSED", "FINAL_REALIZED", "Proposed"]
      ];
      const primaryRows = primarySpecs.map(x => {
        const b = f30Bootstrap(n, "PRIMARY", "publication_config", x[0], x[1], "cash");
        return f30Cells([esc(x[2]), esc(x[1]), esc(b ? b.n : ""), f30Money(b && b.mean), f30CiMoney(b), esc(b && b.analysis_scope)]);
      });
      const pairedRows = (n.paired_statistical_tests || []).map(r => f30Cells([
        esc(r.comparison), esc(r.n_pairs), f30Money(r.mean_difference),
        f30Money(r.mean_difference_bootstrap_ci_low) + " to " + f30Money(r.mean_difference_bootstrap_ci_high),
        f30P(r.p_value_two_sided), pubNum(r.rank_biserial, 3)
      ]));
      el.innerHTML =
        '<div class="fs-panel"><span class="fs-h-eyebrow">Advanced &middot; sealed Final30 evidence</span>' +
        '<h2>Final30 publication results</h2><p class="fs-lede">Read-only results from the sealed 900-cell publication evaluation and its QA-complete derived analysis. Opening this page performs no solver, LLM, or scientific recomputation.</p>' +
        '<div class="fs-metrics">' +
        mtile("Frozen cells", pubNum(d.manifest.raw_cell_count, 0), "900/900 integrity-checked") +
        mtile("Clean / Optimal", pubNum(clean, 0), "across all experiment families") +
        mtile("Non-clean", pubNum(nonclean, 0), "retained; never zero-imputed") +
        mtile("PRIMARY reliability", esc(rel.optimal_runs || "") + "/" + esc(rel.total_runs || ""), f30Pct(rel.optimal_rate_pct, 2) + " · Wilson 95% " + f30Pct(rel.wilson_95_ci_low_pct, 2) + "–" + f30Pct(rel.wilson_95_ci_high_pct, 2)) +
        '</div><div class="fs-note-box info"><b>State boundary preserved.</b> B1/B2/B3 are PLANNED-state baselines. Proposed FINAL_REALIZED is a later realised workflow state, so the analysis does not treat baseline PLANNED and Proposed FINAL_REALIZED as treatment-equivalent.</div></div>' +
        '<div class="fs-panel"><h2>Primary 30-seed results</h2>' +
        f30Table(["Method", "State", "n", "Mean projected cash", "Bootstrap 95% CI", "Scope"], primaryRows) +
        f30Figure(d, 1, "Primary workflow cash with 95% bootstrap confidence intervals.") + '</div>' +
        '<div class="fs-panel"><h2>Paired statistical evidence</h2><p class="fs-muted">Two-sided Wilcoxon signed-rank tests with 10,000-replicate paired bootstrap intervals for the mean A−B difference. Only scientifically valid paired states are tested.</p>' +
        f30Table(["Comparison", "n", "Mean A−B", "Bootstrap 95% CI", "Wilcoxon p", "Rank-biserial"], pairedRows) +
        '<p class="fs-stat-note">Bootstrap analysis seed: ' + esc(n.analysis_rules && n.analysis_rules.bootstrap_seed) + '. Non-Optimal performance values are excluded from outcome summaries and reported separately as reliability.</p>' +
        advancedNext("Uncertainty Results", "uncresults") + '</div>';
    }).catch(e => errbox(el, e.message));
  };

  loaders.uncresults = (el) => {
    loading(el);
    return final30Data().then(d => {
      const n = d.numbers || {}, u = n.uncertainty || {};
      const defs = {U0:"Reference", UW:"Weather", UM:"Market", UR:"Resource", UP:"Participation", UJ:"Joint"};
      const rows = ["U0","UW","UM","UR","UP","UJ"].map(c => {
        const s = f30Find(u.statistics, {condition:c, method:"PROPOSED", state:"FINAL_REALIZED", metric:"cash"}) || {};
        const rr = f30Find(u.reliability, {condition:c}) || {};
        const b = f30Bootstrap(n, "UNCERTAINTY", c, "PROPOSED", "FINAL_REALIZED", "cash");
        return f30Cells([esc(c), esc(defs[c]), esc(s.n), f30Money(s.mean), f30Money(s.sd), f30CiMoney(b), esc(rr.proposed_optimal_runs) + "/" + esc(rr.total_runs), f30Pct(rr.optimal_rate_pct, 1)]);
      });
      const mrows = (n.mcnemar_reliability_tests || []).filter(r => r.family === "UNCERTAINTY").map(r => f30Cells([
        esc(r.comparison), esc(r.n_paired_seeds), esc(r.A_optimal_B_nonoptimal), esc(r.A_nonoptimal_B_optimal), esc(r.discordant_pairs), f30P(r.exact_mcnemar_p_value)
      ]));
      el.innerHTML = '<div class="fs-panel"><span class="fs-h-eyebrow">Advanced &middot; frozen research results</span><h2>Uncertainty Results</h2>' +
        '<p class="fs-lede">These are frozen Final30 results across U0/UW/UM/UR/UP/UJ. The main <b>Uncertainty</b> tab remains the interactive current-plan analysis for the dataset selected in this session.</p>' +
        '<div class="fs-note-box info">Performance is Optimal-only; reliability is shown separately. No zero imputation is used.</div>' +
        f30Table(["Condition","Meaning","Optimal n","Mean FINAL_REALIZED cash","SD","Bootstrap 95% CI","Optimal runs","Rate"], rows) +
        f30Figure(d, 2, "Final realized projected cash across frozen uncertainty conditions.") + '</div>' +
        f30Details("Full uncertainty derived statistics", ["Condition","Method","State","Metric","n","Mean","SD","Median"], (u.statistics||[]).map(r=>f30Cells([esc(r.condition),esc(r.method),esc(r.state),esc(r.metric),esc(r.n),pubNum(r.mean,4),pubNum(r.sd,4),pubNum(r.median,4)]))) +
        '<div class="fs-panel"><h2>Paired reliability evidence</h2>' +
        f30Table(["Comparison","Paired seeds","A optimal / B nonoptimal","A nonoptimal / B optimal","Discordant","Exact McNemar p"], mrows) +
        advancedNext("Sensitivity & Robustness Results", "sensitivity") + '</div>';
    }).catch(e => errbox(el, e.message));
  };

  loaders.sensitivity = (el) => {
    loading(el);
    return final30Data().then(d => {
      const n = d.numbers || {};
      const eps = n.epsilon_sensitivity || {}, lam = n.lambda_stability || {}, al = n.alpha_concentration || {}, act = n.action_robustness || {};
      const erows = ["0.8","0.9","0.95","1.0"].map(v => {
        const s=f30Find(eps.statistics,{epsilon:v,metric:"cash"})||{}; const r=f30Find(eps.reliability,{epsilon:v})||{};
        return f30Cells([esc(v),esc(s.n),f30Money(s.mean),f30Money(s.sd),esc(r.optimal_runs)+"/"+esc(r.total_runs),f30Pct(r.optimal_rate_pct,1),f30Counts(r.failure_status_counts_json)]);
      });
      const lrows=["0.0","0.05","0.1","0.25","0.5","1.0"].map(v=>{const key=v; const cash=f30Find(lam.statistics,{lambda:key,metric:"final_realized_cash"})||{}; const dis=f30Find(lam.statistics,{lambda:key,metric:"disruption_rate"})||{}; const r=f30Find(lam.reliability,{lambda:key})||{}; return f30Cells([esc(v),esc(cash.n),f30Money(cash.mean),pubNum(dis.mean,4),esc(r.optimal_runs)+"/"+esc(r.total_runs),f30Pct(r.optimal_rate_pct,1)]);});
      const arows=["1.0","0.6","0.5","0.4","0.33"].map(v=>{const key=v; const cash=f30Find(al.statistics,{alpha:key,metric:"final_realized_cash"})||{}; const lps=f30Find(al.statistics,{alpha:key,metric:"max_LPS"})||{}; const r=f30Find(al.reliability,{alpha:key})||{}; return f30Cells([esc(v),esc(cash.n),f30Money(cash.mean),pubNum(lps.mean,4),esc(r.optimal_runs)+"/"+esc(r.total_runs),f30Pct(r.optimal_rate_pct,1)]);});
      const acrows=["PRIMARY","S1","S2"].map(v=>{const cash=f30Find(act.statistics,{profile:v,metric:"final_realized_cash"})||{}; const ratio=f30Find(act.statistics,{profile:v,metric:"final_vs_planned_ratio"})||{}; const r=f30Find(act.reliability,{profile:v})||{}; return f30Cells([esc(v),esc(cash.n),f30Money(cash.mean),pubNum(ratio.mean,4),esc(r.optimal_runs)+"/"+esc(r.total_runs),f30Pct(r.optimal_rate_pct,1)]);});
      el.innerHTML = '<div class="fs-panel"><span class="fs-h-eyebrow">Advanced &middot; frozen sensitivity / robustness</span><h2>Sensitivity &amp; Robustness Results</h2><p class="fs-lede">Predeclared ε, λ, α and action-profile experiments from Final30. Frozen publication settings are ε=0.95, λ=0.05 and α=0.40.</p></div>' +
        '<div class="fs-panel"><h2>ε fairness-efficiency sensitivity</h2>' + f30Table(["ε","Optimal n","Mean B3 cash","SD","Optimal runs","Rate","Failure status"],erows) + '<div class="fs-note-box warn"><b>ε=1.0:</b> two B3 cells reached the frozen 120-second time limit and were recorded as Not Solved; they were not selectively rerun.</div>' + f30Figure(d,3,"B3 planned cash across ε settings.") + '</div>' +
        '<div class="fs-panel"><h2>λ stability sensitivity</h2>' + f30Table(["λ","Optimal n","Mean FINAL_REALIZED cash","Mean disruption rate","Optimal runs","Rate"],lrows) + '<div class="fs-result-grid">'+f30Figure(d,4,"Final realized cash across λ settings.")+f30Figure(d,5,"Soft-lock disruption across λ settings.")+'</div></div>' +
        '<div class="fs-panel"><h2>α concentration sensitivity</h2>' + f30Table(["α","Optimal n","Mean FINAL_REALIZED cash","Mean max LPS","Optimal runs","Rate"],arows) + '<div class="fs-result-grid">'+f30Figure(d,6,"Final realized cash across α settings.")+f30Figure(d,7,"Maximum LPS across α settings.")+'</div></div>' +
        f30Details("Full ε derived statistics", ["ε","Metric","Scope","n","Mean","SD","Median","Min","Max"], (eps.statistics||[]).map(r=>f30Cells([esc(r.epsilon),esc(r.metric),esc(r.analysis_scope),esc(r.n),pubNum(r.mean,4),pubNum(r.sd,4),pubNum(r.median,4),pubNum(r.min,4),pubNum(r.max,4)]))) +
        f30Details("Full λ derived statistics", ["λ","Metric","n","Mean","SD","Median"], (lam.statistics||[]).map(r=>f30Cells([esc(r.lambda),esc(r.metric),esc(r.n),pubNum(r.mean,4),pubNum(r.sd,4),pubNum(r.median,4)]))) +
        f30Details("Full α derived statistics", ["α","Metric","n","Mean","SD","Median"], (al.statistics||[]).map(r=>f30Cells([esc(r.alpha),esc(r.metric),esc(r.n),pubNum(r.mean,4),pubNum(r.sd,4),pubNum(r.median,4)]))) +
        f30Details("Full action-profile derived statistics", ["Profile","Metric","n","Mean","SD","Median"], (act.statistics||[]).map(r=>f30Cells([esc(r.profile),esc(r.metric),esc(r.n),pubNum(r.mean,4),pubNum(r.sd,4),pubNum(r.median,4)]))) +
        '<div class="fs-panel"><h2>Action-profile robustness</h2>' + f30Table(["Profile","Optimal n","Mean FINAL_REALIZED cash","Mean FINAL/PLANNED","Optimal runs","Rate"],acrows) + f30Figure(d,8,"Final realized cash across PRIMARY, S1 and S2 action profiles.") +
        advancedNext("Scalability Results", "scale") + '</div>';
    }).catch(e => errbox(el,e.message));
  };

  loaders.scale = (el) => {
    loading(el);
    return final30Data().then(d => {
      const n=d.numbers||{}, sc=n.scalability||{};
      const rows=[25,50,100,250,500].map(v=>{const key=String(v); const cash=f30Find(sc.statistics,{n_farmers:key,method:"PROPOSED",state:"FINAL_REALIZED",metric:"cash"})||{}; const rt=f30Find(sc.statistics,{n_farmers:key,method:"PROPOSED",state:"PIPELINE",metric:"runtime_s"})||{}; const rr=f30Find(sc.reliability,{n_farmers:key})||{}; const ci=f30Find(n.reliability_inference,{family:"SCALABILITY",parameter:"n="+v})||{}; return f30Cells([esc(v),esc(cash.n),f30Money(cash.mean),pubNum(rt.mean,2),esc(rr.proposed_optimal_runs)+"/"+esc(rr.total_runs),f30Pct(rr.proposed_optimal_rate_pct,2),f30Pct(ci.wilson_95_ci_low_pct,2)+"–"+f30Pct(ci.wilson_95_ci_high_pct,2),f30Counts(rr.failure_types_json)]);});
      const mrows=(n.mcnemar_reliability_tests||[]).filter(r=>r.family==="SCALABILITY").map(r=>f30Cells([esc(r.comparison),esc(r.n_paired_seeds),esc(r.A_optimal_B_nonoptimal),esc(r.A_nonoptimal_B_optimal),esc(r.discordant_pairs),f30P(r.exact_mcnemar_p_value)]));
      el.innerHTML='<div class="fs-panel"><span class="fs-h-eyebrow">Advanced &middot; frozen scalability evidence</span><h2>Scalability Results</h2><p class="fs-lede">Population-size experiment with the frozen scientific configuration. B1/B2/B3 remained Optimal in every scalability cell; Proposed feasibility varied substantially by population size.</p>' +
        '<div class="fs-note-box warn"><b>Observed limitation:</b> Proposed Optimal rates were 6.67% at n=25, 13.33% at n=50 and 33.33% at n=100, increasing to 86.67% at n=250 and n=500. These failures are retained as scientific reliability outcomes, not tuned away.</div>' +
        f30Table(["Farmers","Optimal n","Mean FINAL_REALIZED cash","Mean pipeline runtime (s)","Optimal runs","Rate","Wilson 95% CI","Failure stages"],rows) + '<div class="fs-result-grid">'+f30Figure(d,9,"Proposed feasibility across population sizes with Wilson intervals.")+f30Figure(d,10,"Proposed pipeline runtime across population sizes.")+'</div></div>' +
        f30Details("Full scalability derived statistics", ["Farmers","Method","State","Metric","Scope","n","Mean","SD","Median"], (sc.statistics||[]).map(r=>f30Cells([esc(r.n_farmers),esc(r.method),esc(r.state),esc(r.metric),esc(r.analysis_scope),esc(r.n),pubNum(r.mean,4),pubNum(r.sd,4),pubNum(r.median,4)]))) +
        '<div class="fs-panel"><h2>Paired reliability tests</h2>'+f30Table(["Comparison","Paired seeds","A optimal / B nonoptimal","A nonoptimal / B optimal","Discordant","Exact McNemar p"],mrows) +
        advancedNext("Reliability & Statistical Evidence", "reliability") + '</div>';
    }).catch(e=>errbox(el,e.message));
  };

  loaders.reliability = (el) => {
    loading(el);
    return final30Data().then(d => {
      const n=d.numbers||{}, fam=n.family_solver_reliability||[], inf=n.reliability_inference||[], mc=n.mcnemar_reliability_tests||[];
      const clean=fam.reduce((s,r)=>s+Number(r.optimal_or_clean_cells||0),0), bad=fam.reduce((s,r)=>s+Number(r.nonoptimal_cells||0),0);
      const frows=fam.map(r=>f30Cells([esc(r.family),esc(r.total_cells),esc(r.optimal_or_clean_cells),f30Pct(r.clean_rate_pct,2),esc(r.nonoptimal_cells),f30Counts(r.status_counts_json),f30Counts(r.failed_stage_counts_json)]));
      const irows=inf.map(r=>f30Cells([esc(r.family),esc(r.parameter),esc(r.optimal_runs)+"/"+esc(r.total_runs),f30Pct(r.optimal_rate_pct,2),f30Pct(r.wilson_95_ci_low_pct,2)+"–"+f30Pct(r.wilson_95_ci_high_pct,2)]));
      const mrows=mc.map(r=>f30Cells([esc(r.family),esc(r.comparison),esc(r.n_paired_seeds),esc(r.discordant_pairs),f30P(r.exact_mcnemar_p_value)]));
      el.innerHTML='<div class="fs-panel"><span class="fs-h-eyebrow">Advanced &middot; reliability / inference</span><h2>Reliability &amp; Statistical Evidence</h2><div class="fs-metrics">'+mtile("All cells","900","frozen experiment matrix")+mtile("Clean / Optimal",pubNum(clean,0),f30Pct(100*clean/900,2))+mtile("Non-clean",pubNum(bad,0),f30Pct(100*bad/900,2))+mtile("Zero imputation","No","non-Optimal retained separately")+'</div>' +
        '<div class="fs-note-box info"><b>Interpretation rule.</b> Non-Optimal runs are not converted to zero performance. Outcome summaries are Optimal-only; solver/model reliability is a separate reported result.</div></div>' +
        '<div class="fs-panel"><h2>Reliability by experiment family</h2>'+f30Table(["Family","Cells","Clean","Clean rate","Non-clean","Statuses","Failed stages"],frows)+'</div>' +
        '<div class="fs-panel"><h2>Wilson 95% reliability intervals</h2>'+f30Table(["Family","Parameter","Optimal runs","Rate","Wilson 95% CI"],irows)+'</div>' +
        f30Details("All bootstrap confidence-interval rows", ["Family","Parameter","Method","State","Metric","n","Mean","95% CI"], (n.bootstrap_confidence_intervals||[]).map(r=>f30Cells([esc(r.family),esc(r.parameter),esc(r.method),esc(r.state),esc(r.metric),esc(r.n),pubNum(r.mean,4),pubNum(r.bootstrap_95_ci_low,4)+" to "+pubNum(r.bootstrap_95_ci_high,4)]))) +
        '<div class="fs-panel"><h2>Exact McNemar reliability tests</h2>'+f30Table(["Family","Comparison","Paired seeds","Discordant","p"],mrows)+'<p class="fs-stat-note">Exact two-sided binomial test on discordant pairs. Reliability tests are separate from continuous outcome tests.</p>' +
        advancedNext("Scenario A/B Results", "scenario") + '</div>';
    }).catch(e=>errbox(el,e.message));
  };

  function pubRow(
    label,
    a,
    b,
    delta
  ) {
    return (
      "<tr>" +
      "<th>" + esc(label) + "</th>" +
      "<td>" + a + "</td>" +
      "<td>" + b + "</td>" +
      "<td>" + delta + "</td>" +
      "</tr>"
    );
  }

  loaders.scenario = (el) => {
    loading(el);

    return api(
      "/api/farmsync/scenario-results"
    )
      .then(d => {
        if (
          !d
          || !d.available
          || !d.integrity
          || !d.integrity.verified
        ) {
          throw new Error(
            (
              d
              && d.error
            )
            || "Frozen publication result is unavailable."
          );
        }

        const s = d.summary || {};
        const f = d.freeze || {};

        const A = s.scenario_a || {};
        const B = s.scenario_b || {};

        const ah = A.headline || {};
        const bh = B.headline || {};

        const delta =
          s.delta_b_minus_a
          || {};

        const as =
          A.stress
          || {};

        const bs =
          B.stress
          || {};

        const ar =
          A.resilience
          || {};

        const br =
          B.resilience
          || {};

        const auw =
          as.UW
          || {};

        const buw =
          bs.UW
          || {};

        const aum =
          as.UM
          || {};

        const bum =
          bs.UM
          || {};

        const aur =
          as.UR
          || {};

        const bur =
          bs.UR
          || {};

        const auj =
          as.UJ
          || {};

        const buj =
          bs.UJ
          || {};

        const an1 =
          ar.nminus1
          || {};

        const bn1 =
          br.nminus1
          || {};

        const ahz =
          ar.hazard_representative
          || {};

        const bhz =
          br.hazard_representative
          || {};

        const aInitial =
          A.initial_action_counts
          || {};

        const bInitial =
          B.initial_action_counts
          || {};

        const aRenewed =
          A.renewed_decision_counts
          || {};

        const bRenewed =
          B.renewed_decision_counts
          || {};

        const headlineRows = [
          pubRow(
            "Realised plots",
            pubNum(
              ah.realised_plots,
              0
            ),
            pubNum(
              bh.realised_plots,
              0
            ),
            pubNum(
              delta.realised_plots,
              0
            )
          ),

          pubRow(
            "Farmers with realised allocation",
            pubNum(
              ah.farmers_with_realised,
              0
            ),
            pubNum(
              bh.farmers_with_realised,
              0
            ),
            pubNum(
              delta.farmers_with_realised,
              0
            )
          ),

          pubRow(
            "Final realised area (ha)",
            pubNum(
              ah.final_realised_area_ha,
              3
            ),
            pubNum(
              bh.final_realised_area_ha,
              3
            ),
            pubNum(
              delta.final_realised_area_ha,
              3
            )
          ),

          pubRow(
            "Final-plan projected cash",
            pubMoney(
              ah.final_plan_projected_cash
            ),
            pubMoney(
              bh.final_plan_projected_cash
            ),
            pubMoney(
              delta.final_plan_projected_cash
            )
          ),

          pubRow(
            "Offered-plot realisation rate",
            pubPctRatio(
              ah.realisation_rate_offered
            ),
            pubPctRatio(
              bh.realisation_rate_offered
            ),
            pubPp(
              delta.realisation_rate_offered
            )
          ),

          pubRow(
            "Affirmative consent coverage",
            pubPctRatio(
              ah.affirmative_consent_coverage
            ),
            pubPctRatio(
              bh.affirmative_consent_coverage
            ),
            pubPp(
              delta.affirmative_consent_coverage
            )
          ),

          pubRow(
            "All-farmer projected-cash Gini",
            pubNum(
              ah.all_farmer_abs_cash_gini,
              4
            ),
            pubNum(
              bh.all_farmer_abs_cash_gini,
              4
            ),
            pubNum(
              delta.all_farmer_abs_cash_gini,
              4
            )
          ),

          pubRow(
            "All-farmer projected return/ha Gini",
            pubNum(
              ah.all_farmer_per_ha_gini,
              4
            ),
            pubNum(
              bh.all_farmer_per_ha_gini,
              4
            ),
            pubNum(
              delta.all_farmer_per_ha_gini,
              4
            )
          ),

          pubRow(
            "Crop-share HHI",
            pubNum(
              ah.hhi_crop_share,
              4
            ),
            pubNum(
              bh.hhi_crop_share,
              4
            ),
            pubNum(
              delta.hhi_crop_share,
              4
            )
          ),

          pubRow(
            "Maximum crop area share",
            pubPctRatio(
              ah.max_crop_share
            ),
            pubPctRatio(
              bh.max_crop_share
            ),
            pubPp(
              delta.max_crop_share
            )
          )
        ].join("");

        const stressRows = [
          pubRow(
            "UW: water-exposed plots",
            pubNum(
              auw.n_water_exposed_plots,
              0
            ),
            pubNum(
              buw.n_water_exposed_plots,
              0
            ),
            pubNum(
              Number(buw.n_water_exposed_plots)
              - Number(auw.n_water_exposed_plots),
              0
            )
          ),

          pubRow(
            "UW: water-exposed area (ha)",
            pubNum(
              auw.water_exposed_area_ha,
              3
            ),
            pubNum(
              buw.water_exposed_area_ha,
              3
            ),
            pubNum(
              Number(buw.water_exposed_area_ha)
              - Number(auw.water_exposed_area_ha),
              3
            )
          ),

          pubRow(
            "UM: projected cash change",
            pubPctValue(
              aum.cash_change_pct
            ),
            pubPctValue(
              bum.cash_change_pct
            ),
            pubPpValue(
              Number(bum.cash_change_pct)
              - Number(aum.cash_change_pct)
            )
          ),

          pubRow(
            "UM: absorption-exposed crops",
            pubNum(
              aum.n_absorption_exposed_crops,
              0
            ),
            pubNum(
              bum.n_absorption_exposed_crops,
              0
            ),
            pubNum(
              Number(bum.n_absorption_exposed_crops)
              - Number(aum.n_absorption_exposed_crops),
              0
            )
          ),

          pubRow(
            "UR: exposed farmers",
            pubNum(
              aur.n_exposed_farmers,
              0
            ),
            pubNum(
              bur.n_exposed_farmers,
              0
            ),
            pubNum(
              Number(bur.n_exposed_farmers)
              - Number(aur.n_exposed_farmers),
              0
            )
          ),

          pubRow(
            "UR: exposed plots",
            pubNum(
              aur.n_exposed_plots,
              0
            ),
            pubNum(
              bur.n_exposed_plots,
              0
            ),
            pubNum(
              Number(bur.n_exposed_plots)
              - Number(aur.n_exposed_plots),
              0
            )
          ),

          pubRow(
            "UJ: weather/resource-exposed plots",
            pubNum(
              auj.n_plots_with_weather_or_resource_exposure,
              0
            ),
            pubNum(
              buj.n_plots_with_weather_or_resource_exposure,
              0
            ),
            pubNum(
              Number(buj.n_plots_with_weather_or_resource_exposure)
              - Number(auj.n_plots_with_weather_or_resource_exposure),
              0
            )
          ),

          pubRow(
            "UJ: weather/resource-exposed area (ha)",
            pubNum(
              auj.area_with_weather_or_resource_exposure,
              3
            ),
            pubNum(
              buj.area_with_weather_or_resource_exposure,
              3
            ),
            pubNum(
              Number(buj.area_with_weather_or_resource_exposure)
              - Number(auj.area_with_weather_or_resource_exposure),
              3
            )
          )
        ].join("");

        const resilienceRows = [
          pubRow(
            "N-1 representative farmer",
            esc(
              an1.failed_farmer
              || "&mdash;"
            ),
            esc(
              bn1.failed_farmer
              || "&mdash;"
            ),
            pubSame(
              an1.failed_farmer,
              bn1.failed_farmer
            )
          ),

          pubRow(
            "N-1 target crop",
            esc(
              an1.target_crop
              || "&mdash;"
            ),
            esc(
              bn1.target_crop
              || "&mdash;"
            ),
            pubSame(
              an1.target_crop,
              bn1.target_crop
            )
          ),

          pubRow(
            "N-1 immediate projected cash loss",
            pubMoney(
              an1.cash_loss
            ),
            pubMoney(
              bn1.cash_loss
            ),
            pubMoney(
              Number(bn1.cash_loss)
              - Number(an1.cash_loss)
            )
          ),

          pubRow(
            "N-1 cash-loss fraction",
            pubPctRatio(
              an1.cash_loss_fraction
            ),
            pubPctRatio(
              bn1.cash_loss_fraction
            ),
            pubPp(
              Number(bn1.cash_loss_fraction)
              - Number(an1.cash_loss_fraction)
            )
          ),

          pubRow(
            "Protocol representative hazard zone",
            esc(
              ahz.zone
              || "&mdash;"
            ),
            esc(
              bhz.zone
              || "&mdash;"
            ),
            pubSame(
              ahz.zone,
              bhz.zone
            )
          ),

          pubRow(
            "Hazard affected allocations",
            pubNum(
              ahz.affected_allocations,
              0
            ),
            pubNum(
              bhz.affected_allocations,
              0
            ),
            pubNum(
              Number(bhz.affected_allocations)
              - Number(ahz.affected_allocations),
              0
            )
          ),

          pubRow(
            "Hazard affected area (ha)",
            pubNum(
              ahz.affected_area_ha,
              3
            ),
            pubNum(
              bhz.affected_area_ha,
              3
            ),
            pubNum(
              Number(bhz.affected_area_ha)
              - Number(ahz.affected_area_ha),
              3
            )
          ),

          pubRow(
            "Hazard immediate projected cash loss",
            pubMoney(
              ahz.cash_loss
            ),
            pubMoney(
              bhz.cash_loss
            ),
            pubMoney(
              Number(bhz.cash_loss)
              - Number(ahz.cash_loss)
            )
          )
        ].join("");

        el.innerHTML =
          '<div class="fs-panel">' +

          '<span class="fs-h-eyebrow">' +
          'Advanced &middot; Scenario A/B results' +
          '</span>' +

          '<h2>Controlled A/B case study</h2>' +

          '<p class="fs-lede">' +
          'Read-only results from the frozen ' +
          '<b>scenario-ab-v3</b> controlled case study. ' +
          'This page reads committed evidence files; opening it does not rerun the experiment.' +
          '</p>' +

          '<div class="fs-note-box info">' +
          '<b>Frozen artifact verified.</b> ' +
          'Summary SHA-256 matches the committed freeze manifest. ' +
          'No solver, LLM, working-plan mutation or scientific recomputation is performed by this page.' +
          '</div>' +

          '<div class="fs-note-box warn" style="margin-top:10px">' +
          '<b>Interpretation boundary.</b> ' +
          esc(
            s.interpretation_boundary
            || (
              'Scenario B is a constructed illustrative behavioural case study. ' +
              'Its response rates are not empirical farmer-response estimates.'
            )
          ) +
          '</div>' +

          '<div class="fs-metrics" style="margin-top:12px">' +

          mtile(
            "Protocol",
            '<span class="mono" style="font-size:18px;white-space:nowrap">' +
            esc(
              s.protocol_version
              || f.protocol_version
              || ""
            ) +
            '</span>',
            "controlled case study"
          ) +

          mtile(
            "Dataset hash",
            '<span class="mono" style="font-size:13px">' +
            esc(
              s.dataset_hash
              || f.dataset_hash
              || ""
            ) +
            '</span>',
            "same dataset in A and B"
          ) +

          mtile(
            "Verification",
            '<span class="fs-run pass">&#10003; PASS</span>',
            "freeze integrity + protocol checks"
          ) +

          mtile(
            "Scientific recomputation",
            "None",
            "read-only frozen artifact"
          ) +

          '</div>' +
          '</div>' +

          '<div class="fs-panel">' +
          '<h2>Scenario definition &amp; participation</h2>' +

          '<div class="fs-analyse-grid">' +

          '<div>' +
          '<div class="fs-h-eyebrow">Scenario A &middot; reference workflow</div>' +
          '<div class="fs-tablewrap">' +
          '<table class="fs-tbl"><tbody>' +
          '<tr><th>Constructed initial overrides</th><td>None</td></tr>' +
          '<tr><th>Renewed ACCEPT</th><td>' +
          esc(
            aRenewed.ACCEPT
            ?? 0
          ) +
          '</td></tr>' +
          '</tbody></table>' +
          '</div>' +
          '</div>' +

          '<div>' +
          '<div class="fs-h-eyebrow">Scenario B &middot; constructed behaviour</div>' +
          '<div class="fs-tablewrap">' +
          '<table class="fs-tbl"><tbody>' +

          '<tr><th>Withdrawn farmers</th><td>' +
          esc(
            B.withdrawn_farmer_count
            ?? 0
          ) +
          '</td></tr>' +

          '<tr><th>Withdrawal-affected offered rows</th><td>' +
          esc(
            B.withdrawal_affected_offer_rows
            ?? 0
          ) +
          '</td></tr>' +

          '<tr><th>Initial REJECT</th><td>' +
          esc(
            bInitial.REJECT
            ?? 0
          ) +
          '</td></tr>' +

          '<tr><th>Initial NO_RESPONSE</th><td>' +
          esc(
            bInitial.NO_RESPONSE
            ?? 0
          ) +
          '</td></tr>' +

          '<tr><th>Renewed ACCEPT</th><td>' +
          esc(
            bRenewed.ACCEPT
            ?? 0
          ) +
          '</td></tr>' +

          '<tr><th>Renewed REJECT</th><td>' +
          esc(
            bRenewed.REJECT
            ?? 0
          ) +
          '</td></tr>' +

          '<tr><th>Renewed NO_RESPONSE</th><td>' +
          esc(
            bRenewed.NO_RESPONSE
            ?? 0
          ) +
          '</td></tr>' +

          '</tbody></table>' +
          '</div>' +

          '<p class="fs-muted" style="font-size:12px">' +
          'Withdrawal is farmer-cycle scoped: ' +
          '<b>' +
          esc(
            B.withdrawn_farmer_count
            ?? 0
          ) +
          ' farmers</b> affect <b>' +
          esc(
            B.withdrawal_affected_offer_rows
            ?? 0
          ) +
          ' offered rows</b>. These are not the same denominator.' +
          '</p>' +

          '</div>' +
          '</div>' +
          '</div>' +

          '<div class="fs-panel">' +
          '<h2>Headline comparison</h2>' +

          '<p class="fs-muted">' +
          'B &minus; A is descriptive for this exact frozen constructed case study. ' +
          'It is not a causal estimate or population-level treatment effect. ' +
          'Rate-share differences in the B &minus; A column are shown in percentage points (pp).' +
          '</p>' +

          '<div class="fs-tablewrap">' +
          '<table class="fs-tbl">' +
          '<thead><tr>' +
          '<th>Metric</th>' +
          '<th>Scenario A</th>' +
          '<th>Scenario B</th>' +
          '<th>B &minus; A</th>' +
          '</tr></thead>' +
          '<tbody>' +
          headlineRows +
          '</tbody>' +
          '</table>' +
          '</div>' +
          '</div>' +

          '<div class="fs-panel">' +
          '<span class="fs-h-eyebrow">Fixed final-plan sensitivity</span>' +
          '<h2>Uncertainty / stress comparison</h2>' +

          '<p class="fs-muted">' +
          'UW, UM, UR and UJ use the frozen interactive-stress-v1 rules on each exact FINAL_REALIZED plan. ' +
          'No post-stress crop reallocation is performed. ' +
          'Weather reports water exposure rather than an invented yield/cash penalty; ' +
          'resource stress reports capacity exposure rather than mechanically scaling cash. ' +
          'The market absorption measure is a throughput proxy, not empirical demand. ' +
          '<b>Delta = B &minus; A.</b> Exposure-count and area deltas are raw descriptive differences ' +
          'between differently sized realised plans; they are not normalised resilience improvements.' +
          '</p>' +

          '<div class="fs-tablewrap">' +
          '<table class="fs-tbl">' +
          '<thead><tr>' +
          '<th>Stress metric</th>' +
          '<th>Scenario A</th>' +
          '<th>Scenario B</th>' +
          '<th>Delta</th>' +
          '</tr></thead>' +
          '<tbody>' +
          stressRows +
          '</tbody>' +
          '</table>' +
          '</div>' +
          '</div>' +

          '<div class="fs-panel">' +
          '<span class="fs-h-eyebrow">Immediate exposure &middot; no recovery optimisation</span>' +
          '<h2>Resilience comparison</h2>' +

          '<p class="fs-muted">' +
          '<b>Delta = B &minus; A.</b> These are descriptive differences in immediate exposure. ' +
          'They do not establish that one scenario is more resilient, because the realised plans differ in size and composition.' +
          '</p>' +

          '<div class="fs-tablewrap">' +
          '<table class="fs-tbl">' +
          '<thead><tr>' +
          '<th>Resilience metric</th>' +
          '<th>Scenario A</th>' +
          '<th>Scenario B</th>' +
          '<th>Delta</th>' +
          '</tr></thead>' +
          '<tbody>' +
          resilienceRows +
          '</tbody>' +
          '</table>' +
          '</div>' +

          '<div class="fs-note-box info" style="margin-top:10px">' +
          '<b>Post-shock recovery is not evaluated here.</b> ' +
          'The frozen Phase-5 backup optimiser is not applied to these interactive final plans, ' +
          'and no counterfactual backup is presented as realised recovery.' +
          '</div>' +
          '</div>' +

          '<div class="fs-panel">' +
          '<h2>Evidence identity</h2>' +

          '<div class="fs-tablewrap">' +
          '<table class="fs-tbl"><tbody>' +

          '<tr><th>Protocol source commit</th><td class="mono">' +
          esc(
            f.source_commit
            || ""
          ) +
          '</td></tr>' +

          '<tr><th>Freeze version</th><td class="mono">' +
          esc(
            f.freeze_version
            || ""
          ) +
          '</td></tr>' +

          '<tr><th>Scenario A final-plan hash</th><td class="mono">' +
          esc(
            f.scenario_a_final_plan_hash
            || A.final_plan_hash
            || ""
          ) +
          '</td></tr>' +

          '<tr><th>Scenario B final-plan hash</th><td class="mono">' +
          esc(
            f.scenario_b_final_plan_hash
            || B.final_plan_hash
            || ""
          ) +
          '</td></tr>' +

          '<tr><th>Summary SHA-256</th><td class="mono">' +
          esc(
            d.integrity.summary_sha256
            || ""
          ) +
          '</td></tr>' +

          '</tbody></table>' +
          '</div>' +

          advancedNext("Research details & reproducibility", "repro") +

          '</div>';

      })
      .catch(e => {
        errbox(
          el,
          e.message
        );
      });
  };

  loaders.repro = (el) => {
    loading(el);
    return Promise.all([
      api("/api/farmsync/reproducibility"),
      api("/api/farmsync/llm-boundary"),
      final30Data()
    ]).then(([d, llm, f30]) => {
      const c=d.config||{}, s=d.solver_final30||{}, f=d.final30||{}, fr=f30.freeze||{}, m=f30.manifest||{}, rules=m.analysis_rules||{};
      const hm=(k,v)=>'<tr><td>'+esc(k)+'</td><td class="mono">'+esc(v == null ? "—" : v)+'</td></tr>';
      const runtime=f.analysis_runtime||{};
      el.innerHTML='<div class="fs-panel"><span class="fs-h-eyebrow">Advanced &middot; research details &amp; reproducibility</span><h2>Frozen publication configuration &amp; evidence identity</h2>' +
        '<p class="fs-lede">This page describes the sealed Final30 evaluation. Interactive working-plan pages are session tools and do not replace or mutate this evidence.</p>' +
        '<div class="fs-metrics">'+mtile("ε / λ / α",esc(c.epsilon)+" / "+esc(c.lambda)+" / "+esc(c.alpha),"frozen publication configuration")+mtile("Final30",'<span class="fs-run optimal">COMPLETE</span>',esc(f.raw_cell_count)+" frozen cells")+mtile("Analysis",'<span class="fs-run optimal">SEALED</span>',esc(f.analysis_file_count)+" derived files")+mtile("Final QA",'<span class="fs-run optimal">PASS</span>',"all final analysis checks")+'</div>' +
        '<div class="fs-note-box info"><b>Solver amendment was prospective.</b> The relative MIP gap was tightened from 1e-4 to 1e-6 during DEV reproducibility checks before any Final30 cell was generated. Dataset, seeds, RNG streams, ε, λ, α, action, uncertainty, fairness and experiment matrix were unchanged.</div></div>' +
        '<div class="fs-panel"><h2>Solver used for Final30</h2><div class="fs-tablewrap"><table class="fs-tbl"><tbody>'+hm("Engine",s.engine+" "+s.cbc)+hm("PuLP",s.pulp)+hm("Relative MIP gap",s.gapRel)+hm("Time limit",s.timeLimit_s+" s")+hm("Threads",s.threads_policy)+hm("Status semantics",s.status_semantics)+'</tbody></table></div></div>' +
        '<div class="fs-panel"><h2>Frozen hashes &amp; commits</h2><div class="fs-tablewrap"><table class="fs-tbl"><tbody>'+hm("Source commit",f.source_commit)+hm("Experiment matrix SHA-256",f.matrix_sha256)+hm("Dataset attestation SHA-256",f.dataset_attestation_sha256)+hm("Solver amendment SHA-256",f.solver_amendment_sha256)+hm("Raw cell-set SHA-256",f.raw_cell_set_sha256)+hm("Raw RUN_MANIFEST SHA-256",f.raw_run_manifest_sha256)+hm("Analysis-set SHA-256",f.analysis_set_sha256)+hm("Analysis manifest SHA-256",f.analysis_manifest_sha256)+'</tbody></table></div><div class="fs-note-box caveat">'+esc(f.raw_manifest_bookkeeping_note||"")+'</div></div>' +
        '<div class="fs-panel"><h2>Seeds &amp; statistical analysis</h2><div class="fs-tablewrap"><table class="fs-tbl"><tbody>'+hm("Final30 replications",d.seeds && d.seeds.n)+hm("Replication base seed",d.seeds && d.seeds.base_seed)+hm("Replication seed freeze",d.seeds && d.seeds.frozen_at)+hm("Bootstrap replicates",f.bootstrap_replicates||rules.bootstrap_replicates)+hm("Bootstrap analysis seed",f.bootstrap_seed||rules.bootstrap_seed)+hm("Performance rule","Optimal-only outcomes; reliability separate; no zero imputation")+hm("Comparison boundary","No baseline PLANNED vs Proposed FINAL_REALIZED treatment-equivalence test")+'</tbody></table></div><p class="fs-stat-note">The bootstrap seed is an analysis seed; it is not one of the Final30 replication identities.</p></div>' +
        '<div class="fs-panel"><h2>Analysis runtime</h2><div class="fs-metrics">'+mtile("Python",esc(runtime.python))+mtile("NumPy",esc(runtime.numpy))+mtile("SciPy",esc(runtime.scipy))+mtile("Matplotlib",esc(runtime.matplotlib))+'</div></div>' +
        '<div class="fs-panel"><h2>LLM boundary &amp; validation evidence</h2><div class="fs-note-box info"><b>Final30 LLM calls: '+esc(llm.final30_llm_calls)+'</b>. '+esc(llm.note)+'</div><div class="fs-tablewrap"><table class="fs-tbl"><tbody>'+hm("Held-out parser benchmark",llm.benchmark_300_status)+hm("Historical live UI smoke",llm.live_ui_smoke_status)+hm("Targeted live addendum",llm.targeted_live_addendum_status)+hm("Offline regression",llm.offline_regression_status)+'</tbody></table></div></div>';
    }).catch(e=>errbox(el,e.message));
  };

  /* ============ WORKING-PLAN SESSION ============ */

  function modeBanner(kind) {
    return kind === "working"
      ? '<div class="fs-mode-banner interactive"><b>Working plan</b> &mdash; edits apply to your plan for the chosen dataset. Recorded research responses and frozen artifacts are never changed.</div>'
      : '<div class="fs-mode-banner replay"><b>Recorded research</b> &mdash; the stored value. Your working-plan edits are shown alongside and never overwrite it.</div>';
  }

  var WORK = { runId: null, data: null };
  var FINAL_PAGE = 1;   // §4A Final Plan pagination (client-side over the current run rows)

  function ensureWorkingSession() {
    if (WORK.runId && WORK.data) return Promise.resolve(WORK.data);

    return fetch("/api/farmsync/working-plan/start", { method: "POST" })
      .then(r => r.json())
      .then(d => {
        if (!d.run_id) throw new Error(d.error || "could not start working plan");
        WORK.runId = d.run_id;
        WORK.data = d;                 // 0A: start now returns the authoritative shape (incl. workflow)
        renderNavLocks(); renderWorkflow();   // reflect the new run's derived stage access immediately
        return d;
      });
  }

  function refreshWorkingRun() {
    if (!WORK.runId) return Promise.resolve(null);

    return fetch("/api/farmsync/working-plan/" + WORK.runId, {
      headers: { "Accept": "application/json" }
    })
      .then(r => r.json())
      .then(d => {
        if (!d || d.error || d.available === false) {
          throw new Error((d && d.error) || "could not refresh working plan");
        }

        WORK.data = d;
        // authoritative workflow may have changed (unlock/invalidate) — re-derive nav + stepper
        renderNavLocks(); renderWorkflow();
        return d;
      });
  }

  function workingModeNote() {
    return '<div class="fs-note-box info">This is your <b>working plan</b> for the chosen dataset. Edits here never change the recorded research responses or any frozen artifact.</div>';
  }

  /* ---------- Dataset Manager ---------- */

  function initDatasetManager(root, opts) {
    root = root || document;
    opts = opts || {};

    const selectMode = opts.mode === "select";
    const explorerMode = opts.mode === "explorer";

    const q = (sel) => root.querySelector(sel);

    const post = (url, body) =>
      fetch(url, Object.assign({ method: "POST" }, body || {}))
        .then(r => r.json());

    const report = q("#report");
    const reportBody = q("#reportBody");
    const verdict = q("#verdict");
    const reportSource = q("#reportSource");
    const btnActivate = q("#btnActivate");
    const activeInfo = q("#activeInfo");
    const inspect = q("#inspect");

    if (explorerMode && btnActivate) {
      btnActivate.style.display = "none";
    }

    let curTable = null;
    let curPage = 1;

    function renderReport(res) {
      if (!res || res.error) {
        if (report) report.hidden = false;
        if (inspect) inspect.hidden = true;

        if (verdict) {
          verdict.textContent = "UPLOAD FAILED";
          verdict.className = "fs-verdict fail";
        }

        if (reportSource) {
          reportSource.textContent = "";
        }

        const miss = (res && res.missing_files)
          ? '<div class="fs-note-box warn" style="margin-top:10px"><b>Missing required files:</b> ' +
            res.missing_files.map(esc).join(", ") +
            '. farmers.csv, plots.csv and collectives.csv must be uploaded together.</div>'
          : "";

        if (reportBody) {
          reportBody.innerHTML =
            '<div class="fs-errbox">' +
            esc((res && res.error) || "upload failed") +
            '</div>' +
            miss;
        }

        if (btnActivate) {
          btnActivate.disabled = true;
        }

        if (activeInfo) {
          activeInfo.textContent = "";
        }

        return;
      }

      if (report) report.hidden = false;
      if (inspect) inspect.hidden = false;

      const v = res.validation || {};
      const passed = (res.passed !== undefined)
        ? res.passed
        : v.passed;

      if (verdict) {
        verdict.textContent = passed ? "PASS" : "ISSUES";
        verdict.className = "fs-verdict " + (passed ? "pass" : "fail");
      }

      if (reportSource) {
        reportSource.textContent =
          (res.source || "") +
          (res.mode ? " \u00b7 " + res.mode : "");
      }

      const rd = res.readiness;
      const readyPlan = passed && !!(rd && rd.ready_to_plan);

      if (btnActivate) {
        btnActivate.disabled = !readyPlan;
      }

      const nFiles = res.n_files != null
        ? res.n_files
        : (res.files_present || []).length;

      const nErr = res.n_errors != null
        ? res.n_errors
        : (v.errors || []).length;

      const nWarn = res.n_warnings != null
        ? res.n_warnings
        : (v.warnings || []).length;

      let html =
        '<div class="fs-metrics">' +
        '<div class="fs-metric"><div class="k">Files</div><div class="v">' + nFiles + '</div></div>' +
        '<div class="fs-metric"><div class="k">Errors</div><div class="v">' + nErr + '</div></div>' +
        '<div class="fs-metric"><div class="k">Warnings</div><div class="v">' + nWarn + '</div></div>' +
        '</div>';

      if (res.file_states && res.file_states.length) {
        html +=
          '<div class="fs-h-eyebrow" style="margin-top:12px">Uploaded files</div>' +
          '<div class="fs-req-files">' +
          res.file_states.map(f =>
            '<span class="fs-chip">' +
            esc(f.file) +
            ' <span class="fs-req-core">' +
            (f.uploaded
              ? "\u2713 " + (f.rows != null ? f.rows + " rows" : "uploaded")
              : "missing") +
            '</span></span>'
          ).join("") +
          '</div>';
      }

      const errs = (v.errors || []).slice(0, 30);

      if (errs.length) {
        html +=
          '<ul style="margin-top:12px;font-size:12.5px;color:var(--mut)">' +
          errs.map(m =>
            '<li>' +
            esc(typeof m === "string"
              ? m
              : (m.reason || JSON.stringify(m))) +
            '</li>'
          ).join("") +
          '</ul>';
      }

      if (reportBody) {
        reportBody.innerHTML = html;
      }

      if (rd && reportBody) {
        const cap = (c) =>
          '<div class="fs-metric"><div class="k">' +
          esc(c.label) +
          '</div><div class="v small">' +
          (c.ready
            ? '<span class="fs-run optimal">Ready</span>'
            : '<span class="fs-run notrun">Missing</span>') +
          '</div>' +
          (c.missing && c.missing.length
            ? '<div class="sub">needs ' + c.missing.map(esc).join(", ") + '</div>'
            : '') +
          '</div>';

        const missCols =
          (rd.missing_plot_columns && rd.missing_plot_columns.length)
            ? '<div class="fs-note-box warn" style="margin-top:8px"><b>Missing planning inputs (plots.csv columns):</b> ' +
              rd.missing_plot_columns.map(esc).join(", ") +
              '.</div>'
            : "";

        reportBody.insertAdjacentHTML(
          "beforeend",
          '<div class="fs-note-box ' +
          (readyPlan ? "info" : "warn") +
          '" style="margin-top:12px"><b>' +
          (readyPlan ? "Ready to plan \u2713" : "Not ready to plan") +
          '</b> \u2014 ' +
          (readyPlan
            ? "planning data is present."
            : (passed
              ? "structural validation passed, but planning inputs are missing \u2014 Activate is disabled."
              : "validation did not pass.")) +
          '</div>' +
          missCols +
          '<div class="fs-h-eyebrow" style="margin-top:12px">Capability readiness</div>' +
          '<div class="fs-metrics">' +
          Object.keys(rd.capabilities).map(k => cap(rd.capabilities[k])).join("") +
          '</div>'
        );

        if (readyPlan) {
          reportBody.insertAdjacentHTML(
            "beforeend",
            '<div class="fs-cta-row" style="margin-top:12px"><span class="fs-muted">Validation passed and planning inputs are present. Activate to lock a versioned snapshot, then continue to the Initial Plan.</span></div>'
          );
        }
      }

      const sel = q("#inspectTable");
      const rsel = q("#replaceName");
      const present = res.files_present || [];

      if (present.length) {
        const options = present
          .map(f => '<option>' + esc(f) + '</option>')
          .join("");

        if (sel) {
          sel.innerHTML = options;
          sel.disabled = false;
          curTable = present[0];
          loadTable();
        }

        if (rsel) {
          rsel.innerHTML = options;
          rsel.disabled = false;
        }
      }
    }

    if (report) report.hidden = true;
    if (inspect) inspect.hidden = true;

    function status() {
      /* intentionally no auto-resume of staged results */
    }

    function loadTable() {
      if (!curTable) return;

      const searchEl = q("#inspectSearch");
      const qq = encodeURIComponent(searchEl ? (searchEl.value || "") : "");

      fetch(
        "/api/farmsync/inspect/" +
        encodeURIComponent(curTable) +
        "?page=" +
        curPage +
        "&q=" +
        qq
      )
        .then(r => r.json())
        .then(d => {
          if (d.error) return;

          const table = q("#inspectTableEl");
          const thead = table ? table.querySelector("thead") : null;
          const tbody = table ? table.querySelector("tbody") : null;
          const pageInfo = q("#pageInfo");

          if (table) {
            table.className = "fs-tbl";
          }

          if (thead) {
            thead.innerHTML =
              "<tr>" +
              (d.headers || []).map(h => "<th>" + esc(h) + "</th>").join("") +
              "</tr>";
          }

          if (tbody) {
            tbody.innerHTML =
              (d.rows || []).map(r =>
                "<tr>" +
                (d.headers || []).map(h => "<td>" + esc(r[h]) + "</td>").join("") +
                "</tr>"
              ).join("");
          }

          if (pageInfo) {
            pageInfo.textContent =
              "Page " + d.page + " · " + d.total + " rows";
          }
        });
    }

    const on = (id, ev, fn) => {
      const e = q("#" + id);
      if (e) e.addEventListener(ev, fn);
    };

    on("btnBuiltin", "click", () =>
      post("/api/farmsync/load-builtin").then(m => {
        renderReport(m);

        if (!selectMode) return;

        const d = m.dataset_summary || {};

        chooseDataset({
          kind: "builtin",
          label: "FarmSync research dataset",
          farmers: d.farmers,
          plots: d.plots,
          collectives: d.collectives
        });
      })
    );

    function markSelected(inputId, chosen) {
      const inp = q("#" + inputId);
      if (!inp) return;

      const span =
        inp.parentElement &&
        inp.parentElement.querySelector("span");

      if (span) {
        span.classList.toggle("is-selected", !!chosen);
      }
    }

    function customFileStatus() {
      const map = [
        ["fileFarmers", "farmers.csv"],
        ["filePlots", "plots.csv"],
        ["fileColl", "collectives.csv"]
      ];

      const st = q("#customFileStatus");
      if (!st) return;

      st.innerHTML = map.map(([id, name]) => {
        const inp = q("#" + id);
        const has = inp && inp.files.length;

        return '<span class="fs-chip">' +
          esc(name) +
          ' <span class="fs-req-core">' +
          (has ? "Selected \u2713" : "not selected") +
          '</span></span>';
      }).join("");
    }

    ["fileFarmers", "filePlots", "fileColl"].forEach(id =>
      on(id, "change", () => {
        const inp = q("#" + id);
        markSelected(id, inp && inp.files.length);
        customFileStatus();
      })
    );

    (function () {
      const card =
        q(".fs-modes .fs-card:last-child .fs-card-actions");

      if (card && !q("#customFileStatus")) {
        card.insertAdjacentHTML(
          "afterend",
          '<div id="customFileStatus" class="fs-req-files" style="margin-top:8px"></div>'
        );

        customFileStatus();
      }
    })();

    function setPending(btn, label) {
      if (!btn) return;
      btn.dataset.orig = btn.textContent;
      btn.disabled = true;
      btn.textContent = label;
    }

    function clearPending(btn) {
      if (!btn) return;
      btn.disabled = false;

      if (btn.dataset.orig) {
        btn.textContent = btn.dataset.orig;
      }
    }

    function uploadFlow(btn, url, fd) {
      setPending(btn, "Uploading\u2026");

      if (report) {
        report.hidden = false;
      }

      if (reportBody) {
        reportBody.innerHTML =
          '<div class="fs-uploading"><span class="fs-spin"></span> Validating dataset\u2026</div>';
      }

      if (verdict) {
        verdict.textContent = "";
        verdict.className = "fs-verdict";
      }

      return post(url, { body: fd }).then(
        m => {
          clearPending(btn);

          try {
            renderReport(m);
          } catch (renderErr) {
            if (report) {
              report.hidden = false;
            }

            if (reportBody) {
              reportBody.insertAdjacentHTML(
                "beforeend",
                '<div class="fs-errbox">Validation response was received, but part of the report could not be rendered: ' +
                esc(renderErr.message) +
                '.</div>'
              );
            }

            console.error(
              "FarmSync validation render error",
              renderErr
            );
          }

          return m;
        },
        requestErr => {
          clearPending(btn);

          if (report) {
            report.hidden = false;
          }

          if (reportBody) {
            reportBody.innerHTML =
              '<div class="fs-errbox">Upload request failed: ' +
              esc(requestErr.message) +
              '. Your selected files are kept &mdash; try again.</div>';
          }

          return null;
        }
      );
    }

    on("filePackage", "change", e => {
      const b = q("#btnPackage");

      if (b) {
        b.disabled = !e.target.files.length;
      }

      markSelected(
        "filePackage",
        e.target.files.length
      );
    });

    on("btnPackage", "click", () => {
      const input = q("#filePackage");
      const f = input && input.files[0];

      if (!f) return;

      const fd = new FormData();
      fd.append("file", f);

      uploadFlow(
        q("#btnPackage"),
        "/api/farmsync/upload-package",
        fd
      );
    });

    on("btnFarmers", "click", () => {
      const fd = new FormData();

      [
        ["farmers.csv", "fileFarmers"],
        ["plots.csv", "filePlots"],
        ["collectives.csv", "fileColl"]
      ].forEach(([k, id]) => {
        const input = q("#" + id);
        const f = input && input.files[0];

        if (f) {
          fd.append(k, f);
        }
      });

      uploadFlow(
        q("#btnFarmers"),
        "/api/farmsync/upload-farmers",
        fd
      );
    });

    on("btnReplace", "click", () => {
      const replaceFile = q("#replaceFile");
      const replaceName = q("#replaceName");
      const f = replaceFile && replaceFile.files[0];

      if (!f || !replaceName) return;

      const fd = new FormData();

      fd.append(
        "file",
        new File([f], replaceName.value)
      );

      post(
        "/api/farmsync/upload-file",
        { body: fd }
      ).then(renderReport);
    });

    on("btnActivate", "click", () => {
      if (!selectMode) return;

      post("/api/farmsync/activate").then(m => {
        if (m.error) {
          const cols =
            (m.missing_plot_columns &&
             m.missing_plot_columns.length)
              ? ' Missing plots.csv columns: ' +
                m.missing_plot_columns.map(esc).join(", ") +
                '.'
              : '';

          if (activeInfo) {
            activeInfo.innerHTML =
              '<span class="fs-run infeasible">' +
              esc(m.error) +
              '</span>' +
              (cols
                ? '<span class="fs-muted">' + cols + '</span>'
                : '');
          }

          return;
        }

        const pop = m.population || {};

        if (activeInfo) {
          activeInfo.innerHTML = '';
        }

        chooseDataset({
          kind: "custom",
          label: "Custom dataset",
          farmers: pop.farmers,
          plots: pop.plots,
          collectives: pop.collectives,
          version: m.version,
          hash: m.dataset_hash
        });
      });
    });

    on("inspectTable", "change", e => {
      curTable = e.target.value;
      curPage = 1;
      loadTable();
    });

    on("inspectSearch", "input", () => {
      curPage = 1;
      loadTable();
    });

    on("prevPage", "click", () => {
      if (curPage > 1) {
        curPage--;
        loadTable();
      }
    });

    on("nextPage", "click", () => {
      curPage++;
      loadTable();
    });

    if (!explorerMode) {
      status();
    }
  }

  /* ---------- particles + boot ---------- */

  function initParticles() {
    const c = document.getElementById("fsParticles");

    if (
      !c ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }

    for (let i = 0; i < 28; i++) {
      const p = document.createElement("div");
      const size = 2 + Math.random() * 4;

      p.className = "forge-particle";
      p.style.left = (Math.random() * 100) + "%";
      p.style.animationDelay = (Math.random() * 8) + "s";
      p.style.animationDuration = (6 + Math.random() * 6) + "s";
      p.style.width = p.style.height = size + "px";

      c.appendChild(p);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    initParticles();
    renderNavLocks();
    renderWorkflow();

    const hash =
      (location.hash || "").replace("#", "");

    const valid = [
      "home",
      "plan",
      "farmer",
      "replan",
      "consent",
      "final",
      "fairness",
      "uncertainty",
      "resilience",
      "data",
      "final30",
      "uncresults",
      "sensitivity",
      "scale",
      "reliability",
      "scenario",
      "repro"
    ];

    const initialWs =
      valid.includes(hash) && isUnlocked(hash)
        ? hash
        : "home";

    activate(initialWs, {
      scroll: initialWs !== "home"
    });
  });
})();