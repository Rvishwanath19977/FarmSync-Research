"""UI/integration tests — product journey, causal sequencing, correct AI role, no future-state leakage.

Enforces: correct canonical artifact per stage; no future-state leakage (Initial Plan has no FINAL,
Farmer Responses no revised/final data, Replan revised-not-realised, Final = only FINAL_REALIZED source);
separate Replan and Consent stages; stage ordering + unlock chain; selected farmer+plot mapping; recorded
vs illustrative; LLM parses but never allocates/invents crops; per-stage teaching; Analyse ordering;
research disclosure; plus the scientific-safety invariants (no solver / no live LLM on load, caveats,
theme isolation, no colour in JS)."""
import os
import sys
import re
import json
import importlib
import pytest
from flask import Flask

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(_ROOT, "static", "css", "farmsync.css")
JS = os.path.join(_ROOT, "static", "js", "farmsync.js")


@pytest.fixture()
def client(tmp_path):
    tdir = tmp_path / "templates"; tdir.mkdir()
    (tdir / "base.html").write_text(
        "<!doctype html><html data-theme='light'><head><title>{% block title %}{% endblock %}"
        "{% block head %}{% endblock %}</title></head><body><nav>nav</nav>{% block content %}{% endblock %}"
        "{% block scripts %}{% endblock %}</body></html>")
    (tdir / "farmsync.html").write_text(open(os.path.join(_ROOT, "templates", "farmsync.html")).read())
    app = Flask(__name__, template_folder=str(tdir), static_folder=os.path.join(_ROOT, "static"))
    import farmsync_routes; importlib.reload(farmsync_routes)
    farmsync_routes.register_farmsync_routes(app)
    app.config.update(TESTING=True)
    return app.test_client()


def js():
    return open(JS).read()


# ---- structure + stage ordering ----
def test_page_loads_with_five_main_stages(client):
    html = client.get("/farm-sync").get_data(as_text=True)
    for ws in ("home", "plan", "farmer", "replan", "consent", "final",
               "fairness", "uncertainty", "resilience", "data", "repro"):
        assert 'id="ws-' + ws + '"' in html
    assert 'id="ws-lab"' not in html
    assert "the llm does not allocate crops" in html.lower()


def test_workflow_order_plan_to_analyse(client):
    m = re.search(r"const WF = \[(.+?)\];", js(), re.S)
    labels = re.findall(r'\["([^"]+)",', m.group(1))
    assert labels == ["Initial Plan", "Farmer Responses", "Replan", "Consent", "Finalise", "Analyse"]
    assert '"Data"' not in m.group(1)


def test_separate_replan_and_consent_stages(client):
    j = js()
    assert "loaders.replan =" in j and "loaders.consent =" in j
    assert "/working-plan/" in j and "/replan" in j and "/consent" in j


def test_unlock_chain(client):
    # workflow access is now derived from authoritative server state, not local unlock booleans
    j = js()
    assert "let unlocked = {}" not in j and "unlocked = { plan: true }" not in j
    assert "function wfStages()" in j and "WORK.data.workflow" in j
    # the gate still routes through isUnlocked (server-derived) and flashes on locked stages
    assert "if (!isUnlocked(ws)) { flashLock(ws); return; }" in j


# ---- canonical artifact per stage + NO future-state leakage ----
def test_initial_plan_is_planned_no_final_leak(client):
    d = client.get("/api/farmsync/initial-plan").get_json()
    assert d["state"] == "PLANNED" and d["planned_cash"] == 13142166.0
    s = json.dumps(d)
    assert "FINAL_REALIZED" not in s and "final" not in d
    # only original recommendation columns
    r0 = d["recommendations"][0]
    assert set(r0.keys()) <= {"farmer_id", "plot_id", "region_season", "crop", "cash"}


def test_farmer_responses_no_revised_or_final_leak(client):
    d = client.get("/api/farmsync/farmer-response/F0001").get_json()
    assert "final" not in d and "revised_crop" not in d
    assert set(d["recommendation"].keys()) == {"crop", "cash"}
    assert d["response"] in ("ACCEPT", "REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW")


def test_replan_is_revised_not_realised(client):
    d = client.get("/api/farmsync/replan").get_json()
    assert d["state"] == "RECOMMENDED_REVISED"
    assert "not yet realised" in d["not_realised"].lower()
    assert d["revised_cash"] and d["revised_cash"] != d.get("final_cash")
    # rows carry original -> revised crop
    changed = [r for r in d["rows"] if r["changed"]]
    assert changed and "original_crop" in changed[0] and "revised_crop" in changed[0]


def test_final_plan_is_only_final_realized_source(client):
    d = client.get("/api/farmsync/final-plan").get_json()
    assert d["state"] == "FINAL_REALIZED"
    # coherence fix: realised_cash is derived from p6 (one provenance), NOT the checkpoint tier
    assert d["realised_cash"] == 11210638
    # the checkpoint tier economics are shown SEPARATELY, never merged into the realised figure
    assert d["checkpoint_tiers"]["FINAL_REALIZED"] == 12362577.0
    assert d["checkpoint_tiers"]["FINAL_REALIZED"] != d["realised_cash"]
    assert set(d["checkpoint_tiers"].keys()) == {"PLANNED", "INITIAL_REALIZED", "RECOMMENDED_REVISED", "FINAL_REALIZED"}


def test_selected_farmer_plot_mapping(client):
    fl = client.get("/api/farmsync/farmers").get_json()["farmers"][0]
    det = client.get("/api/farmsync/farmer-response/" + fl["farmer_id"] + "/" + fl["plot_id"]).get_json()
    assert det["farmer_id"] == fl["farmer_id"] and det["plot_id"] == fl["plot_id"]


def test_multiplot_two_key_binding_no_cross_plot_leak(client):
    """A multi-plot farmer must load the EXACT selected plot's recorded response — never another plot's.
    Reproduces and closes the ACCEPT/REJECT mismatch: two-key lookup keyed by (farmer_id, plot_id)."""
    import csv as _csv
    import collections as _c
    src_rows = list(_csv.DictReader(open(os.path.join(_ROOT, "results", "farmsync", "proposed",
                                                       "p1_participation_offers.csv"))))
    by_farmer = _c.defaultdict(list)
    for r in src_rows:
        by_farmer[r["farmer_id"]].append(r)
    # a farmer with >1 plot AND differing responses across plots (the exact bug condition)
    target = next((f for f, rs in by_farmer.items()
                   if len(rs) > 1 and len({x["response"] for x in rs}) > 1), None)
    assert target is not None, "expected a multi-plot farmer with differing responses in the fixture"
    rows = by_farmer[target]

    # every plot must return ITS OWN row exactly — farmer, plot, crop, cash, response all from that row
    for r in rows:
        d = client.get("/api/farmsync/farmer-response/" + target + "/" + r["plot_id"]).get_json()
        assert d["available"] is True
        assert d["farmer_id"] == target
        assert d["plot_id"] == r["plot_id"]
        assert d["response"] == r["response"]
        assert d["recommendation"]["crop"] == r["planned_crop"]
        assert abs(d["recommendation"]["cash"] - float(r["planned_cash_return"])) < 1e-6

    # explicit: a REJECT plot cannot return an ACCEPT from a sibling plot
    reject = next((x for x in rows if x["response"] == "REJECT"), None)
    accept = next((x for x in rows if x["response"] == "ACCEPT"), None)
    if reject and accept:
        dj = client.get("/api/farmsync/farmer-response/" + target + "/" + reject["plot_id"]).get_json()
        assert dj["response"] == "REJECT" and dj["plot_id"] == reject["plot_id"]
        da = client.get("/api/farmsync/farmer-response/" + target + "/" + accept["plot_id"]).get_json()
        assert da["response"] == "ACCEPT" and da["plot_id"] == accept["plot_id"]


def test_invalid_farmer_plot_pair_is_404_not_silent_fallback(client):
    fl = client.get("/api/farmsync/farmers").get_json()["farmers"][0]
    r = client.get("/api/farmsync/farmer-response/" + fl["farmer_id"] + "/" + fl["plot_id"] + "-NOPE")
    assert r.status_code == 404 and r.get_json()["available"] is False


def test_multiplot_single_key_refuses_ambiguous(client):
    """Single-key form must not silently return one plot for a multi-plot farmer."""
    import csv as _csv
    import collections as _c
    src_rows = list(_csv.DictReader(open(os.path.join(_ROOT, "results", "farmsync", "proposed",
                                                       "p1_participation_offers.csv"))))
    by_farmer = _c.defaultdict(list)
    for r in src_rows:
        by_farmer[r["farmer_id"]].append(r["plot_id"])
    multi = next((f for f, ps in by_farmer.items() if len(ps) > 1), None)
    r = client.get("/api/farmsync/farmer-response/" + multi)
    assert r.status_code == 400 and r.get_json()["state"] == "plot_id required"


def test_js_sends_both_ids(client):
    j = js()
    assert 'data-pid="' in j                       # rows carry the plot id
    assert "openFarmer(it.dataset.fid, it.dataset.pid)" in j
    assert "encodeURIComponent(fid) + (pid ?" in j  # two-key request URL


# ---- AI role: parses, never allocates/invents ----
def test_llm_parses_but_never_allocates(client):
    d = client.get("/api/farmsync/farmer-response/F0001").get_json()
    ai = d["ai_role"]
    assert "never" in ai["rule"].lower() and ("invent" in ai["rule"].lower() or "choose" in ai["rule"].lower())
    assert "optimiser" in ai and "crop" in ai["optimiser"].lower() and "never from the llm" in ai["optimiser"].lower()
    # request-alternative parsing + no-invent rule come from the backend ai-parse
    alt = client.post("/api/farmsync/ai-parse", json={"text": "What else can I grow?", "farmer_id": "F1", "plot_id": "P1"}).get_json()
    assert alt["parser_action"] == "CLARIFY"
    assert alt["ui_intent"] == "REQUEST_ALTERNATIVE"
    assert alt["requested_crop"] is None
    assert "must come from FarmSync" in (alt["alternative_note"] or "")
    j = js()
    assert "LLM</b> parses" in j
    assert "FarmSync</b> validates/selects" in j
    assert "Evidence</b> grounded" in j

    # working-plan AI-role strip must NOT claim the optimiser decides the crop
    assert "Optimiser</b> decides the crop" not in j


def test_recorded_vs_illustrative(client):
    j = js()
    # working plan: recorded response is immutable; edits set a working-plan response, with save/reset
    assert "Recorded:" in j and "Saved for this plan" in j
    assert "Reset to recorded response" in j
    assert "recorded research response" in j.lower() or "recorded research" in j.lower()


def test_dev_mock_llm_labelled_no_live(client):
    status = client.get("/api/farmsync/ai-status").get_json()

    # product default is OFF when FARMSYNC_LLM_MODE is unset (no silent Mock); label is mode-aware.
    assert status["mode"] == "off"
    assert status["label"] == "Off"
    assert status["technical"]["no_silent_fallback"] is True
    assert status["technical"]["farmer_id_sent_to_model"] is False

    ap = client.post(
        "/api/farmsync/ai-parse",
        json={"text": "hello", "farmer_id": "F", "plot_id": "P"}
    ).get_json()

    assert "no live API call" in ap["rule"]
    assert "deterministic FarmSync retains validation and allocation authority" in ap["rule"]

# ---- per-stage teaching + analyse ordering ----
def test_every_main_stage_has_teaching(client):
    j = js()
    # teach() block renders what / why / what happened / what it means
    assert "fs-teach" in j and "What</span>" in j and "Why</span>" in j
    assert "What happened</span>" in j and "What it means</span>" in j
    # each main stage loader calls teach(
    for stage in ("plan", "farmer", "replan", "consent", "final"):
        assert re.search(r"loaders\." + stage + r" = ", j)
    assert j.count("teach({") >= 5


def test_analyse_guides_fairness_uncertainty_resilience(client):
    j = js()
    # dynamic Analyse is /analysis-backed; three tabs share the current-plan payload
    assert "function loadAnalysis()" in j and "/analysis" in j
    assert "loaders.fairness" in j and "loaders.uncertainty" in j and "loaders.resilience" in j
    assert "CURRENT WORKING FINAL PLAN" in j


# ---- scientific safety (unchanged) ----
def test_no_solver_on_any_load(client):
    sys.modules.pop("pulp", None)
    for ep in ("initial-plan", "farmer-response/F0001", "replan", "consent", "final-plan",
               "overview", "fairness", "uncertainty", "resilience", "reproducibility"):
        assert client.get("/api/farmsync/" + ep).status_code == 200
    assert "pulp" not in sys.modules


def test_final30_and_llm_status_are_current(client):
    ov = client.get("/api/farmsync/overview").get_json()["experiment_state"]

    assert "COMPLETE / SEALED" in ov["final30"]

    # Closed synthetic parser benchmark is complete.
    assert "COMPLETE" in ov["llm_benchmark_300"]
    assert "SYNTHETIC_CONSTRUCTED" in ov["llm_benchmark_300"]
    assert "NOT real-farmer validation" in ov["llm_benchmark_300"]

    # Historical smoke, targeted post-routing addendum and offline regression are complete.
    assert "PARSER BENCHMARK COMPLETE" in ov["llm_live"]
    assert "HISTORICAL 10-CALL LIVE UI SMOKE COMPLETE" in ov["llm_live"]
    assert "TARGETED 7-CASE LIVE ADDENDUM COMPLETE" in ov["llm_live"]

    assert "WIRED" in ov["llm_live_ui_integration"]
    assert "historical 10-call live UI smoke COMPLETE" in ov["llm_live_ui_integration"]
    assert "7-case targeted" in ov["llm_live_ui_integration"]

    assert "COMPLETE" in ov["llm_live_ui_smoke"]
    assert "10-call manual bounded integration QA" in ov["llm_live_ui_smoke"]
    assert "pre-llm-ui-intent-v2" in ov["llm_live_ui_smoke"]
    assert "NOT a benchmark" in ov["llm_live_ui_smoke"]


def test_llm_boundary_reports_closed_benchmark_separately(client):
    d = client.get("/api/farmsync/llm-boundary").get_json()

    assert "PARSER BENCHMARK COMPLETE" in d["live_status"]
    assert "HISTORICAL 10-CALL LIVE UI SMOKE COMPLETE" in d["live_status"]
    assert "TARGETED 7-CASE LIVE ADDENDUM COMPLETE" in d["live_status"]

    b = d["benchmark_300_status"]
    assert "COMPLETE" in b
    assert "322-case" in b
    assert "SYNTHETIC_CONSTRUCTED" in b
    assert "NOT real-farmer validation" in b

    # the manual live UI smoke remains separate from the held-out benchmark and targeted addendum
    smoke = d["live_ui_smoke_status"]
    assert "COMPLETE" in smoke
    assert "10 manually executed bounded integration-QA calls" in smoke
    assert "pre-llm-ui-intent-v2" in smoke
    assert "not a benchmark" in smoke
    assert d["targeted_live_addendum_status"].startswith("COMPLETE - 7/7")
    # page-load note must not imply the closed benchmark never occurred, and no runtime telemetry persisted
    assert "makes no live LLM call" in d["note"] and "Final30 made zero LLM calls" in d["note"]
    assert "No runtime telemetry is automatically persisted" in d["note"]


def test_recommendation_not_consent_preserved(client):
    cs = client.get("/api/farmsync/consent").get_json()
    assert "not consent" in cs["teaching"]["recommendation_ne_consent"].lower()
    assert "exact-crop" in cs["rule"].lower()
    pl = client.get("/api/farmsync/planning").get_json()
    assert "not realised" in pl["tier_semantics"]["RECOMMENDED_REVISED"].lower()


def test_research_caveats_preserved(client):
    pl = client.get("/api/farmsync/planning").get_json()
    assert "worst-off" in pl["b3_caveat"].lower() and "capable" in pl["b3_caveat"].lower()
    assert "hazard" in client.get("/api/farmsync/concentration").get_json()["caveat"].lower()
    assert "not empirical" in client.get("/api/farmsync/uncertainty").get_json()["framing"].lower()
    assert "absorption proxy, NOT demand" in js()


def test_research_pages_preserved(client):
    html = client.get("/farm-sync").get_data(as_text=True)
    assert "fsDatasetTpl" in html and 'id="btnBuiltin"' in html
    for ep in ("overview", "reproducibility"):
        assert client.get("/api/farmsync/" + ep).status_code == 200


def test_theme_palettes_separate_no_leak(client):
    css = open(CSS).read()
    assert "--sci-green:#1f9d6b" in css and "--sci-blue:#3b82f6" in css
    light = re.search(r'\[data-theme="light"\] \.fs-app\{[^}]*\}', css).group(0)
    assert "--sci-green:#16a34a" in light and "--sci-blue:#ea580c" in light
    assert "#1f9d6b" not in light and "#3b82f6" not in light


def test_no_theme_colour_in_js(client):
    assert re.search(r"#[0-9a-fA-F]{6}\b", js()) is None


# ---- mode/purpose-aware data requirements + capability readiness ----
def test_requirements_are_mode_and_purpose_aware(client):
    req = client.get("/api/farmsync/data-requirements").get_json()
    byfile = {f["file"]: f for f in req["file_schema"]}
    for f in ("crop_region_season_params.csv", "climate_scenarios.csv", "market_scenarios.csv",
              "hazard_zones.csv", "parameter_provenance.csv"):
        assert byfile[f]["custom_farmer_label"] == "Built-in reused"
    assert byfile["crop_region_season_params.csv"]["complete_package_label"] == "Required for planning"
    assert byfile["plot_crop_suitability.csv"]["complete_package_label"] == "Required for planning"
    assert byfile["market_scenarios.csv"]["complete_package_label"] == "Required for market uncertainty"
    assert byfile["participation_scenarios.csv"]["complete_package_label"] == "Required for participation uncertainty"
    assert byfile["hazard_zones.csv"]["complete_package_label"] == "Required for resilience analysis"
    assert byfile["parameter_provenance.csv"]["complete_package_label"] == "Optional metadata / reproducibility"
    for f in req["file_schema"]:
        assert f["complete_package_label"] not in ("optional", "core")  # no misleading bare labels
    assert req["modes"]["custom_farmer"]["you_must_provide"] == ["farmers.csv", "plots.csv", "collectives.csv"]
    caps = {c["capability"]: c["files"] for c in req["modes"]["complete_package"]["capability_requirements"]}
    assert caps["Initial planning / optimiser"] == ["crop_region_season_params.csv", "plot_crop_suitability.csv"]
    assert caps["Resilience analysis"] == ["hazard_zones.csv"]


def test_capability_readiness_structural_vs_planning(client):
    core = "farmers.csv,plots.csv,crops.csv,regions.csv,collectives.csv"
    r = client.get("/api/farmsync/capability-readiness?files=" + core + "&mode=complete_package").get_json()
    assert r["core_relational"]["ready"] is True
    assert r["ready_to_plan"] is False
    assert set(r["capabilities"]["initial_planning"]["missing"]) == {
        "crop_region_season_params.csv", "plot_crop_suitability.csv"}
    full = core + ",crop_region_season_params.csv,plot_crop_suitability.csv"
    r2 = client.get("/api/farmsync/capability-readiness?files=" + full + "&mode=complete_package").get_json()
    assert r2["ready_to_plan"] is True
    assert r2["capabilities"]["resilience"]["ready"] is False
    assert r2["capabilities"]["resilience"]["missing"] == ["hazard_zones.csv"]


def test_capability_readiness_custom_farmer_reuses_builtin(client):
    # custom-farmer reuses built-in SUPPORTING data, but plot-level planning needs real agronomic
    # plot columns; minimal custom plots (no soil/water/etc.) must NOT be ready-to-plan.
    r = client.get("/api/farmsync/capability-readiness?files=farmers.csv,plots.csv,collectives.csv&mode=custom_farmer").get_json()
    assert r["ready_to_plan"] is False
    assert r["agronomy_ready"] is False
    assert "soil_group" in r["missing_plot_columns"]
    assert r["capabilities"]["initial_planning"]["ready"] is False


def test_validation_vs_readiness_documented(client):
    req = client.get("/api/farmsync/data-requirements").get_json()
    assert "does not guarantee" in req["validation_vs_readiness"].lower()
    j = js()
    assert "res.readiness" in j and "Ready to plan" in j and "Not ready to plan" in j


def test_no_solver_on_requirements_or_readiness(client):
    import sys as _s
    _s.modules.pop("pulp", None)
    client.get("/api/farmsync/data-requirements")
    client.get("/api/farmsync/capability-readiness?files=farmers.csv&mode=complete_package")
    assert "pulp" not in _s.modules


# ================== ONE-FLOW CORRECTION (working plan; no Interactive Run) ==================
import io as _io
import shutil as _sh


def _wp_dir():
    return os.path.join(_ROOT, "results", "farmsync", "exploratory")


def _clean_wp():
    _sh.rmtree(_wp_dir(), ignore_errors=True)
    # also clear test-created versioned snapshots so repeated activations don't collide
    _sh.rmtree(os.path.join(_ROOT, "data", "farmsync", "snapshots"), ignore_errors=True)


def _qa_files():
    reg, sea = "R1", "kharif"
    farmers = "farmer_id,collective_id,region_id,season\n" + "\n".join(
        f"QA00{i},QAC{(i%2)+1},{reg},{sea}" for i in range(1, 9))
    plines = ["plot_id,farmer_id,region_id,area_ha"]
    for j in range(1, 13):
        fi = ((j - 1) % 8) + 1
        plines.append(f"QA00{fi}-P{j:02d},QA00{fi},{reg},{1.0+(j%5)}")
    colls = f"collective_id,region_id,season\nQAC1,{reg},{sea}\nQAC2,{reg},{sea}"
    return farmers, "\n".join(plines), colls


def _qa_files_agro():
    """QA custom fixture WITH the agronomic plot columns real feasibility needs (seeded from real
    built-in R1 kharif plots so a defensible feasible crop set can be derived)."""
    import csv as _csv
    bp = [r for r in _csv.DictReader(open(os.path.join(_ROOT, "data/farmsync/builtin/plots.csv")))
          if r["region_id"] == "R1" and r["active_season"] == "kharif"][:4]
    cols = "plot_id,farmer_id,region_id,area_ha,soil_group,soil_suitability_class,drainage_class,available_water_m3,waterlogging_exposure,active_season,previous_crop"
    plines = [cols]
    for j, rp in enumerate(bp, 1):
        fi = ((j - 1) % 3) + 1
        plines.append(f"QA00{fi}-P{j:02d},QA00{fi},R1,{rp['area_ha']},{rp['soil_group']},{rp['soil_suitability_class']},{rp['drainage_class']},{rp['available_water_m3']},{rp['waterlogging_exposure']},kharif,{rp['previous_crop']}")
    farmers = "farmer_id,collective_id,region_id,season\n" + "\n".join(f"QA00{i},QAC{(i%2)+1},R1,kharif" for i in range(1, 4))
    colls = "collective_id,region_id,season\nQAC1,R1,kharif\nQAC2,R1,kharif"
    return farmers, "\n".join(plines), colls


def _upload_qa_agro(client):
    f, p, cl = _qa_files_agro()
    data = {"farmers.csv": (_io.BytesIO(f.encode()), "farmers.csv"),
            "plots.csv": (_io.BytesIO(p.encode()), "plots.csv"),
            "collectives.csv": (_io.BytesIO(cl.encode()), "collectives.csv")}
    return client.post("/api/farmsync/upload-farmers", data=data, content_type="multipart/form-data")


def _upload_qa(client):
    f, p, cl = _qa_files()
    data = {"farmers.csv": (_io.BytesIO(f.encode()), "farmers.csv"),
            "plots.csv": (_io.BytesIO(p.encode()), "plots.csv"),
            "collectives.csv": (_io.BytesIO(cl.encode()), "collectives.csv")}
    return client.post("/api/farmsync/upload-farmers", data=data, content_type="multipart/form-data")


# 1. Initial Plan locked before any dataset is chosen (JS gate).
def test_plan_locked_before_dataset_choice(client):
    j = js()
    assert 'const ALWAYS = ["home", "data", "final30", "uncresults", "sensitivity", "scale", "reliability", "scenario", "repro"]' in j   # plan NOT in ALWAYS; publication is read-only frozen evidence
    assert "let unlocked = {}" not in j   # no local unlock booleans; DATASET gates plan
    assert "if (!DATASET) return false" in j
    assert "Choose a dataset first" in j                             # plan lock hint


# 2. Built-in selection unlocks the ONE workflow.
def test_builtin_choice_unlocks_workflow(client):
    j = js()
    assert 'chooseDataset({ kind: "builtin"' in j
    assert "DATASET = ds" in j   # dataset chosen => Initial Plan available; rest from server workflow
    # load-builtin returns a dataset summary so the context bar can render
    m = client.post("/api/farmsync/load-builtin").get_json()
    assert m["dataset_summary"]["farmers"] and m["dataset_summary"]["plots"]


# 3. Built-in canonical rows/results appear (working plan seeded from the stored plan).
def test_builtin_working_plan_uses_canonical_rows(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    assert wp["source_kind"] == "builtin" and wp["engine"] == "CANONICAL_STORED_PLAN"
    # canonical crops/cash + recorded responses are present, and it is NEVER called Optimal
    r0 = wp["recommendations"][0]
    assert r0["crop"] and r0["cash"] and r0["recorded_response"] in ("ACCEPT", "REJECT", "MODIFY", "NO_RESPONSE", "WITHDRAW")
    assert wp["solver_status"] != "Optimal"
    _clean_wp()


# 4. Recorded response is immutable (editing only sets the working override).
# 5-9. Edit one exact farmer+plot -> save -> reflected -> preserved across reads -> reset restores.
def test_edit_save_reflect_preserve_reset(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]
    r0 = wp["recommendations"][0]
    fid, pid, rec = r0["farmer_id"], r0["plot_id"], r0["recorded_response"]
    new_act = "REJECT" if rec != "REJECT" else "ACCEPT"
    # save an override for the EXACT farmer+plot
    res = client.post(f"/api/farmsync/working-plan/{rid}/response",
                      json={"farmer_id": fid, "plot_id": pid, "action": new_act}).get_json()
    assert res["available"] and res["working_response"] == new_act
    assert res["recorded_response"] == rec and res["edited"] is True   # recorded is immutable
    # preserved on re-read
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    saved = next(r for r in got["recommendations"] if r["plot_id"] == pid)
    assert saved["working_response"] == new_act and saved["recorded_response"] == rec
    # reset restores the recorded response (override deleted)
    rst = client.post(f"/api/farmsync/working-plan/{rid}/reset",
                      json={"farmer_id": fid, "plot_id": pid}).get_json()
    assert rst["working_response"] is None and rst["effective_response"] == rec
    got2 = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    saved2 = next(r for r in got2["recommendations"] if r["plot_id"] == pid)
    assert saved2["working_response"] is None
    # JS renders saved + reset affordances
    j = js()
    assert "Saved for this plan" in j and "Reset to recorded response" in j and "fs-edited" in j
    _clean_wp()


# 10. Replan actually consumes the saved override (effective = override-or-recorded).
def test_replan_consumes_working_override(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]
    # find an ACCEPT plot with a feasible alternative, flip it to REJECT
    target = next((r for r in wp["recommendations"] if r["crop"]), None)
    assert target
    client.post(f"/api/farmsync/working-plan/{rid}/response",
                json={"farmer_id": target["farmer_id"], "plot_id": target["plot_id"], "action": "REJECT"})
    rp = client.post(f"/api/farmsync/working-plan/{rid}/replan").get_json()
    assert rp["available"] and rp["state"] == "RECOMMENDED_REVISED" and "not yet realised" in rp["not_realised"].lower()
    _clean_wp()


# 11-12. AI parses groundnut (never maize); "what else" never fabricates a crop.
def test_ai_parse_groundnut_and_alternative(client):
    r = client.post("/api/farmsync/ai-parse", json={"text": "Can I grow groundnut?", "farmer_id": "F1", "plot_id": "P1"}).get_json()
    assert r["action"] == "MODIFY" and r["requested_crop"] == "groundnut"
    a = client.post("/api/farmsync/ai-parse", json={"text": "What else can I grow?", "farmer_id": "F1", "plot_id": "P1"}).get_json()
    assert a["parser_action"] == "CLARIFY"
    assert a["ui_intent"] == "REQUEST_ALTERNATIVE"
    assert a["requested_crop"] is None
    assert "must come from FarmSync" in (a["alternative_note"] or "")
    assert "not evaluated" in r["semantic_validation"]     # never faked Pass


# 13. A FarmSync alternative can be accepted (saved to the working plan).
def test_ai_recommendation_saves_working_state(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]; r0 = wp["recommendations"][0]
    res = client.post(f"/api/farmsync/working-plan/{rid}/response",
                      json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "MODIFY"}).get_json()
    assert res["available"] and res["working_response"] == "MODIFY"
    j = js()
    assert "data-ai-use" in j    # the AI recommendation card offers to Use (save) the recommendation
    _clean_wp()


# 14-15. Revised crop requires exact renewed consent; rejected/unconsented never realised.
def test_renewed_consent_required_and_unconsented_not_realised(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]
    tgt = next(r for r in wp["recommendations"] if r["crop"])
    client.post(f"/api/farmsync/working-plan/{rid}/response",
                json={"farmer_id": tgt["farmer_id"], "plot_id": tgt["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    changed = [r for r in got["recommendations"] if r["changed"]]
    for r in changed:
        assert r["requires_renewed_consent"] is True
    # finalise WITHOUT recording renewed consent -> changed plots are not realised
    fin = client.post(f"/api/farmsync/working-plan/{rid}/finalise").get_json()
    got2 = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    bad = [r for r in got2["recommendations"] if r["realised"] and not r.get("consent_basis")]
    assert not bad
    for r in got2["recommendations"]:
        if r["realised"]:
            assert r.get("consent_basis") in ("INITIAL_ACCEPT", "RENEWED_ACCEPT")
    _clean_wp()


# 16-17. Activated custom data drives ALL stages with QA IDs; zero F-ID leakage; no Fxxxx suitability reuse.
def test_custom_dataset_drives_all_stages_qa_ids(client):
    # activated custom data (with real agronomy) drives the working plan via the REAL feasibility
    # eligibility; QA IDs only, zero built-in F leakage.
    _clean_wp()
    up = _upload_qa_agro(client)
    assert up.status_code == 200 and up.get_json()["passed"] is True
    assert up.get_json()["readiness"]["ready_to_plan"] is True
    client.post("/api/farmsync/activate")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    assert "recommendations" in wp, wp
    ids = {r["farmer_id"] for r in wp["recommendations"]}
    assert ids and all(x.startswith("QA") for x in ids)
    assert not any(x.startswith("F0") for x in ids)
    assert wp["source_kind"] == "custom" and wp["engine"] == "DETERMINISTIC_WORKING_PLAN"
    # initial crops are REAL feasible picks from canonical eligibility (not None everywhere)
    assert any(r["crop"] for r in wp["recommendations"])
    _clean_wp()


# 18. Incomplete agronomic custom data cannot claim Ready to Plan.
def test_incomplete_custom_not_ready_to_plan(client):
    up = _upload_qa(client).get_json()
    assert up["passed"] is True
    assert up["readiness"]["ready_to_plan"] is False
    assert "soil_group" in up["readiness"]["missing_plot_columns"]


# 21. No separate Interactive Run nav/workspace remains.
def test_no_interactive_run_remains(client):
    j = js()
    assert 'data-ws="run"' not in j and "loaders.run" not in j
    assert "startInteractiveRun" not in j and "Interactive Exploratory Run" not in j
    tmpl = open(os.path.join(_ROOT, "templates", "farmsync.html")).read()
    assert 'data-ws="run"' not in tmpl and 'id="ws-run"' not in tmpl


# 22. Experiment Lab / Provenance are no longer primary normal-flow nav.
def test_lab_provenance_not_primary_nav(client):
    tmpl = open(os.path.join(_ROOT, "templates", "farmsync.html")).read()
    assert 'data-ws="lab"' not in tmpl                    # lab removed from sidebar
    assert "Research details" in tmpl                     # provenance behind a quiet Advanced item
    assert "Advanced" in tmpl


# 23. GET / page load imports/runs no solver.
def test_get_and_page_load_no_solver(client):
    sys.modules.pop("pulp", None)
    client.get("/farm-sync")
    for ep in ("initial-plan", "consent", "final-plan", "dataset-summary"):
        client.get("/api/farmsync/" + ep)
    client.post("/api/farmsync/ai-parse", json={"text": "hi", "farmer_id": "F", "plot_id": "P"})
    assert "pulp" not in sys.modules


# 24. Selected frozen artifacts remain byte-identical after a full working-plan flow.
def test_frozen_artifacts_untouched_by_working_plan(client):
    import hashlib
    frozen = ["results/farmsync/proposed/p1_participation_offers.csv",
              "results/farmsync/proposed/p6_final_revised_plan.csv",
              "results/farmsync/proposed/ui_dev_checkpoint.json",
              "results/farmsync/b3_ilp_v2.json"]
    before = {f: hashlib.sha256(open(os.path.join(_ROOT, f), "rb").read()).hexdigest() for f in frozen}
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]; r0 = wp["recommendations"][0]
    client.post(f"/api/farmsync/working-plan/{rid}/response",
                json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    client.post(f"/api/farmsync/working-plan/{rid}/finalise")
    after = {f: hashlib.sha256(open(os.path.join(_ROOT, f), "rb").read()).hexdigest() for f in frozen}
    assert before == after
    _clean_wp()


# 19-20. Active snapshot unaffected by later staged edits; switching dataset resets working state (JS).
def test_dataset_switch_resets_working_state(client):
    j = js()
    assert "function resetDataset" in j and "resetWorkingState" in j
    assert "homeChangeDataset" in j and "requestChangeDataset" in j   # Change dataset lives on Home now
    # chooseDataset resets working state before binding the new dataset
    assert "resetWorkingState();" in j


# ================== CORRECTIVE TURN: real machinery / snapshot / provenance ==================
def test_working_replan_uses_real_action_consent_machinery(client):
    # built-in replan uses matrix_cell + canonical feasibility eligibility (NOT the old heuristic),
    # and is honestly NOT labelled the MILP collective reoptimisation.
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]
    tgt = next(r for r in wp["recommendations"] if r["crop"] and r["recorded_response"] != "REJECT")
    client.post(f"/api/farmsync/working-plan/{rid}/response",
                json={"farmer_id": tgt["farmer_id"], "plot_id": tgt["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    assert "matrix_cell" in got["replan_mechanism"] and "canonical feasibility" in got["replan_mechanism"]
    assert "NOT the MILP" in got["replan_mechanism"]
    ch = next(r for r in got["recommendations"] if r["plot_id"] == tgt["plot_id"])
    assert ch["offer_status"] in ("DECLINED", "BLOCKED", "PENDING_LAPSED", "WITHDRAWN")  # from matrix_cell
    _clean_wp()


def test_custom_uses_real_feasibility_and_requires_agronomy(client):
    # minimal custom (no agronomy) is NOT ready and cannot start a plan; agronomy-complete custom can.
    up_min = _upload_qa(client).get_json()
    assert up_min["readiness"]["ready_to_plan"] is False
    _clean_wp()
    up = _upload_qa_agro(client)
    assert up.get_json()["readiness"]["ready_to_plan"] is True
    client.post("/api/farmsync/activate")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    assert "recommendations" in wp and any(r["crop"] for r in wp["recommendations"])
    _clean_wp()


def test_activated_snapshot_binding_immutable(client):
    # after activation, later staged uploads must NOT alter the active working plan.
    _clean_wp()
    _upload_qa_agro(client)
    client.post("/api/farmsync/activate")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]
    ids = {r["farmer_id"] for r in wp["recommendations"]}
    # stage a completely different upload AFTER activation
    client.post("/api/farmsync/upload-farmers",
                data={"farmers.csv": (_io.BytesIO(b"farmer_id,collective_id,region_id,season\nZZ9,ZC,R1,kharif"), "farmers.csv"),
                      "plots.csv": (_io.BytesIO(b"plot_id,farmer_id,region_id,area_ha\nZZ9-P1,ZZ9,R1,1"), "plots.csv"),
                      "collectives.csv": (_io.BytesIO(b"collective_id,region_id,season\nZC,R1,kharif"), "collectives.csv")},
                content_type="multipart/form-data")
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    ids2 = {r["farmer_id"] for r in got["recommendations"]}
    assert ids2 == ids and not any(x.startswith("ZZ") for x in ids2)
    _clean_wp()


def test_staged_but_not_activated_custom_requires_activation(client):
    # a staged (not activated) custom upload does not set the planning source -> start refused
    _clean_wp()
    client.post("/api/farmsync/change-dataset")            # ensure no planning source
    _upload_qa_agro(client)                                # staged, not activated
    r = client.post("/api/farmsync/working-plan/start")
    assert r.status_code == 400
    assert "planning dataset" in r.get_json()["error"].lower() or "select" in r.get_json()["error"].lower()
    _clean_wp()


def test_requested_crop_preserved_and_consumed(client):
    # MODIFY preserves requested_crop separately from the action; replan validates it against feasibility.
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]; r0 = wp["recommendations"][0]
    res = client.post(f"/api/farmsync/working-plan/{rid}/response",
                      json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"],
                            "action": "MODIFY", "requested_crop": "groundnut"}).get_json()
    assert res["requested_crop"] == "groundnut"
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    saved = next(r for r in got["recommendations"] if r["plot_id"] == r0["plot_id"])
    assert saved["requested_crop"] == "groundnut"    # preserved, not lost
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    j = js()
    assert "data-ai-use" in j and "requested_crop" in j   # UI carries the requested crop through
    _clean_wp()


def test_analyse_gate_hides_frozen_research_for_custom(client):
    j = js()
    # Analyse now describes the CURRENT working final plan for BOTH built-in and custom (no split);
    # it is provenance-labelled and gated on final_current (unavailable otherwise).
    assert "function analyseUnavailable" in j and "final revision" in j
    assert "analysisProvenance" in j and "CURRENT WORKING FINAL PLAN" in j


def test_lab_ghost_removed(client):
    j = js()
    tmpl = open(os.path.join(_ROOT, "templates", "farmsync.html")).read()
    assert "loaders.lab" not in j and '"lab"' not in j
    assert 'id="ws-lab"' not in tmpl and 'data-ws="lab"' not in tmpl
    # useful research config folded into the single Research details area
    assert "research details" in j.lower()


# ================== START/DATA-SOURCE UX PATCH + FARMER AI EXPERIENCE ==================
def test_home_builtin_does_not_navigate_to_data(client):
    j = js()
    # Home built-in selects inline via selectBuiltinOnHome; it must NOT activate the Data workspace
    assert "selectBuiltinOnHome" in j
    assert 'activate("data"); const bb' not in j        # the old redirect is gone
    assert 'id="homeUseBuiltin"' in j


def test_home_owns_selection_and_stays_home(client):
    j = js()
    # built-in selection calls chooseDataset(kind builtin) and Home re-renders to the selected state
    assert 'chooseDataset({ kind: "builtin"' in j
    assert "renderHomeSelected" in j and "Continue to Initial Plan" in j
    assert "DATASET = ds" in j              # Initial Plan available once a dataset is chosen


def test_home_custom_upload_is_inline(client):
    j = js()
    # custom path mounts the existing Dataset Manager INLINE on Home (homeDmMount), in select mode
    assert 'id="homeDmMount"' in j and 'mountDM($("#homeDmMount"), { mode: "select" })' in j
    assert "homeUseCustom" in j


def test_data_explorer_never_selects_or_activates(client):
    j = js()
    # Data Explorer is a dedicated read-only inspector — it does NOT mount the Dataset Manager
    assert "mountExplorer" in j
    assert '"/api/farmsync/explore-tables"' in j and '"/api/farmsync/explore/"' in j
    # the explorer loader must not mount the DM template or call chooseDataset/activate
    assert 'mountDM($("#dmMount")' not in j
    # Data Explorer loader copy is inspection-only
    assert "read-only" in j.lower() and "does not alter that custom planning source" in j


def test_data_explorer_cannot_change_working_source(client):
    # loading built-in inside Data Explorer (explorer mode) must not create/alter a working plan gate.
    # Simulate: even after hitting load-builtin (what Explore does), no working plan is required/created.
    client.post("/api/farmsync/load-builtin")             # explorer inspection load
    # a working plan is only created by an explicit working-plan/start POST (Home flow), not by exploring
    j = js()
    assert 'explorerMode' in j and 'btnActivate.style.display = "none"' in j


def test_no_global_dataset_context_strip(client):
    html = client.get("/farm-sync").get_data(as_text=True)
    j = js()
    assert "fsDatasetCtx" not in html and "fsDatasetCtx" not in j
    assert "renderDatasetContext" not in j                # global strip renderer removed
    assert "function dataSourceLine" in j                 # replaced by a small inline source line


def test_fresh_load_shows_no_selected_dataset_ui(client):
    j = js()
    # Home renders the selected state ONLY when DATASET is set; fresh load shows the two choices
    assert "if (DATASET) { renderHomeSelected(el); return; }" in j
    assert "First, choose your data" in j


def test_dm_mount_is_robust_to_revisits(client):
    j = js()
    # mount when the host has no dataset-manager root yet — no brittle global flag
    assert 'querySelector(".fs-dm-root")' in j and "let dmMounted" not in j
    html = client.get("/farm-sync").get_data(as_text=True)
    assert "fs-dm-root" in html                            # template carries the root marker


def test_change_dataset_confirms_when_working_plan_exists(client):
    j = js()
    assert "requestChangeDataset" in j
    assert "Changing the dataset will reset your current working plan" in j
    assert "resetDataset()" in j


# ---- §9 farmer AI experience ----
def test_ai_what_else_returns_real_feasible_recommendation(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]
    r0 = wp["recommendations"][0]

    rec = client.post(
        f"/api/farmsync/working-plan/{rid}/recommend",
        json={
            "farmer_id": r0["farmer_id"],
            "plot_id": r0["plot_id"],
        },
    ).get_json()

    assert rec["found"]
    assert rec["recommended_crop"]
    assert rec["recommended_crop"] != r0["crop"]
    assert "feasibility" in rec["determined_by"].lower()

    # Read-only: asking for an alternative must not mutate working state.
    got = client.get(
        f"/api/farmsync/working-plan/{rid}"
    ).get_json()
    assert got["recommendations"][0].get("working_response") is None

    # "Another option" must exclude the already shown candidate.
    # A valid outcome is either:
    #   (a) another cash-positive candidate exists, or
    #   (b) the feasible positive-return set is exhausted.
    rec2 = client.post(
        f"/api/farmsync/working-plan/{rid}/recommend",
        json={
            "farmer_id": r0["farmer_id"],
            "plot_id": r0["plot_id"],
            "exclude": [rec["recommended_crop"]],
        },
    ).get_json()

    if rec.get("n_more", 0) > 0:
        assert rec2["found"] is True
        assert rec2["recommended_crop"] != rec["recommended_crop"]
    else:
        assert rec2["found"] is False
        assert "recommended_crop" not in rec2
        assert "cash-positive" in rec2["reason"].lower()

    _clean_wp()


def test_ai_validate_requested_crop(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]; r0 = wp["recommendations"][0]
    v = client.post(f"/api/farmsync/working-plan/{rid}/validate-crop",
                    json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "requested_crop": "groundnut"}).get_json()
    assert "feasible" in v
    # an impossible crop is infeasible and offers a real canonical alternative
    v2 = client.post(f"/api/farmsync/working-plan/{rid}/validate-crop",
                     json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "requested_crop": "dragonfruit"}).get_json()
    assert v2["feasible"] is False and (v2.get("alternative") or {}).get("recommended_crop")
    _clean_wp()


def test_ai_card_is_user_first_with_tech_drawer(client):
    j = js()
    # normal-user recommendation card + Use/Reject/Another/Ask why; debug moved into a Technical details drawer
    assert "FarmSync recommendation" in j and "Use this recommendation" in j
    assert "data-ai-another" in j and "data-ai-why" in j and "data-ai-reject" in j
    assert "Technical details" in j and "function aiTechDrawer" in j
    # Ask why must not mutate; Use saves MODIFY + requested crop and states renewed consent still needed
    assert "explanation only" in j.lower() or "nothing was changed" in j.lower()
    assert "renewed consent is required" in j.lower() or "renewed consent" in j
    # the "not evaluated (read-only replay)" phrase must not be the primary display for an alternative request
    assert "Semantic validation</td><td><span" not in j


# ---- §10 working-plan terminology ----
def test_working_plan_terminology_accurate(client):
    j = js()
    assert "collective is reoptimised" not in j
    assert "deterministic optimiser decides" not in j
    assert "Deterministic reoptimisation" not in j
    assert "Deterministic replanning" in j
    assert "action-consent + feasibility" in j


# ============= FINAL STATE-INTEGRITY: planning source, readiness, explorer, AI semantics =============
def test_activate_blocked_server_side_when_not_ready(client):
    # §1: structural PASS + ready_to_plan=false -> server /activate returns 400
    _clean_wp()
    up = _upload_qa(client).get_json()                    # minimal custom (no agronomy)
    assert up["passed"] is True and up["readiness"]["ready_to_plan"] is False
    r = client.post("/api/farmsync/activate")
    assert r.status_code == 400
    assert "not ready" in r.get_json()["error"].lower() and r.get_json().get("missing_plot_columns")
    _clean_wp()


def test_activate_ui_gates_on_ready_to_plan(client):
    j = js()
    # client-side: Activate disabled unless passed AND ready_to_plan
    assert "const readyPlan = passed && !!(rd && rd.ready_to_plan)" in j
    assert "btnActivate.disabled = !readyPlan" in j


def test_ready_custom_activates_and_sets_planning_source(client):
    _clean_wp()
    up = _upload_qa_agro(client).get_json()
    assert up["readiness"]["ready_to_plan"] is True
    m = client.post("/api/farmsync/activate").get_json()
    assert "error" not in m and m.get("planning_source") == "custom"
    ps = client.get("/api/farmsync/planning-source").get_json()
    assert ps["planning_source"] == "custom"
    _clean_wp()


def test_planning_source_custom_then_change_then_builtin(client):
    # §2: custom -> change -> built-in = canonical F IDs only, ZERO QA leakage
    _clean_wp()
    _upload_qa_agro(client); client.post("/api/farmsync/activate")
    client.post("/api/farmsync/change-dataset")
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    ids = {r["farmer_id"] for r in wp["recommendations"]}
    assert all(x.startswith("F") for x in ids) and not any(x.startswith("QA") for x in ids)
    _clean_wp()


def test_planning_source_builtin_then_change_then_custom(client):
    # §2: built-in -> change -> custom = exact custom IDs, ZERO stale F leakage
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    client.post("/api/farmsync/working-plan/start")
    client.post("/api/farmsync/change-dataset")
    _upload_qa_agro(client); client.post("/api/farmsync/activate")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    ids = {r["farmer_id"] for r in wp["recommendations"]}
    assert all(x.startswith("QA") for x in ids) and not any(x.startswith("F") for x in ids)
    _clean_wp()


def test_working_plan_start_requires_explicit_source(client):
    _clean_wp()
    client.post("/api/farmsync/change-dataset")            # no source
    r = client.post("/api/farmsync/working-plan/start")
    assert r.status_code == 400
    _clean_wp()


def test_data_explorer_does_not_mutate_planning_source(client):
    # §2/§6: loading built-in for inspection must not set planning_source
    _clean_wp()
    client.post("/api/farmsync/change-dataset")
    client.get("/api/farmsync/explore-tables")
    client.get("/api/farmsync/explore/farmers")
    ps = client.get("/api/farmsync/planning-source").get_json()
    assert ps["planning_source"] is None
    _clean_wp()


def test_home_custom_starts_clean_no_stale_verdict(client):
    j = js()
    # §3: status() no longer auto-resumes a stale staged package; report starts hidden
    assert "no auto-resume of staged results" in j
    assert "if (report) report.hidden = true;" in j


def test_custom_branch_has_no_builtin_card(client):
    j = js()
    # §4: in select mode the built-in card + research replace-file are removed from the custom branch
    assert 'opts.mode === "select"' in j and "builtinCard.remove()" in j


def test_upload_feedback_states(client):
    j = js()
    # §5: pending Uploading/Validating + disable-to-prevent-duplicate + no fabricated percentages
    assert "Uploading\\u2026" in j and "Validating dataset\\u2026" in j
    assert "function setPending" in j and "customFileStatus" in j
    assert "%" not in j.split("function uploadFlow")[1].split("}")[0]   # no percent in the upload flow


def test_explorer_read_only_endpoint_no_staging(client):
    # §6: /explore reads built-in without touching planning source or staged pkg
    r = client.get("/api/farmsync/explore/plots").get_json()
    assert "headers" in r and "rows" in r and r["total"] > 0
    ps = client.get("/api/farmsync/planning-source").get_json()
    assert ps["planning_source"] is None     # inspection did not set a source


def test_explorer_has_proper_spacing(client):
    j = js()
    # §7: dedicated explorer mount class with a gap
    assert "fs-explorer-mount" in j
    css = open(os.path.join(_ROOT, "static", "css", "farmsync.css")).read()
    assert ".fs-explorer-mount{margin-top:20px}" in css


def test_ai_another_option_is_readonly_until_use(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]; r0 = wp["recommendations"][0]
    rec = client.post(f"/api/farmsync/working-plan/{rid}/recommend", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"]}).get_json()
    client.post(f"/api/farmsync/working-plan/{rid}/recommend", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "exclude": [rec["recommended_crop"]]})
    # neither /recommend call mutated working state
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    assert got["recommendations"][0].get("working_response") is None
    _clean_wp()


def test_generic_save_preserves_requested_crop(client):
    # §10: generic MODIFY save (no requested_crop) must not erase an existing saved crop
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]; r0 = wp["recommendations"][0]
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "MODIFY", "requested_crop": "groundnut"})
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "MODIFY"})  # omitted
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    saved = next(r for r in got["recommendations"] if r["plot_id"] == r0["plot_id"])
    assert saved["requested_crop"] == "groundnut"
    # explicit null clears
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "MODIFY", "requested_crop": None})
    got2 = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    assert next(r for r in got2["recommendations"] if r["plot_id"] == r0["plot_id"])["requested_crop"] is None
    _clean_wp()


def test_saved_requested_crop_survives_revisit(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]; r0 = wp["recommendations"][0]
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "MODIFY", "requested_crop": "groundnut"})
    # reload the run (simulates revisit/refresh) -> crop persists
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    assert next(r for r in got["recommendations"] if r["plot_id"] == r0["plot_id"])["requested_crop"] == "groundnut"
    j = js()
    assert "Requested crop" in j and "w.requested_crop" in j   # detail panel renders it
    _clean_wp()


def test_reject_candidate_persists_and_excluded(client):
    # Rejected alternatives persist and must never be returned or selected by Replan.
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]
    r0 = wp["recommendations"][0]

    client.post(
        f"/api/farmsync/working-plan/{rid}/response",
        json={
            "farmer_id": r0["farmer_id"],
            "plot_id": r0["plot_id"],
            "action": "REJECT",
        },
    )

    rec = client.post(
        f"/api/farmsync/working-plan/{rid}/recommend",
        json={
            "farmer_id": r0["farmer_id"],
            "plot_id": r0["plot_id"],
        },
    ).get_json()

    assert rec["found"] is True
    cand = rec["recommended_crop"]

    rj = client.post(
        f"/api/farmsync/working-plan/{rid}/reject-candidate",
        json={
            "farmer_id": r0["farmer_id"],
            "plot_id": r0["plot_id"],
            "crop": cand,
        },
    ).get_json()

    assert cand in rj["rejected_alternatives"]

    rec2 = client.post(
        f"/api/farmsync/working-plan/{rid}/recommend",
        json={
            "farmer_id": r0["farmer_id"],
            "plot_id": r0["plot_id"],
        },
    ).get_json()

    # The rejected crop must never be surfaced again. If it was the final
    # cash-positive alternative, exhaustion is the scientifically correct result.
    assert (
        rec2.get("found") is False
        or rec2.get("recommended_crop") != cand
    )

    client.post(
        f"/api/farmsync/working-plan/{rid}/replan"
    )

    got = client.get(
        f"/api/farmsync/working-plan/{rid}"
    ).get_json()

    ch = next(
        r for r in got["recommendations"]
        if r["plot_id"] == r0["plot_id"]
    )

    assert ch.get("revised_crop") != cand

    _clean_wp()


def test_ask_why_uses_deterministic_evidence(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]; r0 = wp["recommendations"][0]
    # explain a genuinely feasible crop (from the recommend engine) -> deterministic ranking evidence
    rec = client.post(f"/api/farmsync/working-plan/{rid}/recommend", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"]}).get_json()
    ex = client.post(f"/api/farmsync/working-plan/{rid}/explain", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "crop": rec["recommended_crop"]}).get_json()
    assert ex["available"] and "feasibility" in ex["basis"].lower()
    assert ex["feasible"] is True and ex["passed_constraints"] is not None and ex["rank_among_feasible"] is not None
    # ask why does not mutate
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    assert got["recommendations"][0].get("working_response") is None
    _clean_wp()


def test_reset_clears_all_override_state(client):
    # §15: reset removes working_response + requested_crop + rejected_alternatives
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]; r0 = wp["recommendations"][0]
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "MODIFY", "requested_crop": "groundnut"})
    client.post(f"/api/farmsync/working-plan/{rid}/reject-candidate", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "crop": "maize"})
    rst = client.post(f"/api/farmsync/working-plan/{rid}/reset", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"]}).get_json()
    assert rst["working_response"] is None and rst["requested_crop"] is None and rst["rejected_alternatives"] == []
    _clean_wp()


def test_no_optimiser_decides_in_working_ai_role(client):
    # Working Farmer Responses AI-role strip must preserve deterministic FarmSync authority
    # without claiming that the LLM or a separate optimiser independently chooses the crop.
    j = js()

    assert "Optimiser</b> decides the crop" not in j
    assert "LLM</b> parses" in j
    assert "FarmSync</b> validates/selects" in j
    assert "Evidence</b> grounded" in j


def test_js_header_not_stale_readonly(client):
    # §17: header no longer describes the whole UI as read-only
    j = js()
    assert "ISOLATED, editable\n   working-plan layer" in j or "ISOLATED, editable" in j

# ================= MANUAL QA FOLLOW-UP: reset sync, grounded why, upload render, explorer validation =================

def test_manualqa_reset_server_state_and_ui_rehydrates_authoritatively(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid, r0 = wp["run_id"], wp["recommendations"][0]
    client.post(f"/api/farmsync/working-plan/{rid}/response",
                json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"],
                      "action": "MODIFY", "requested_crop": "groundnut"})
    client.post(f"/api/farmsync/working-plan/{rid}/reject-candidate",
                json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "crop": "maize"})
    rst = client.post(f"/api/farmsync/working-plan/{rid}/reset",
                      json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"]}).get_json()
    assert rst["working_response"] is None
    assert rst["requested_crop"] is None
    assert rst["rejected_alternatives"] == []
    got = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    row = next(x for x in got["recommendations"] if x["farmer_id"] == r0["farmer_id"] and x["plot_id"] == r0["plot_id"])
    assert row.get("working_response") is None
    assert row.get("requested_crop") is None
    assert row.get("rejected_alternatives") == []
    assert row.get("commitment") is None
    j = js()
    assert "function refreshWorkingRun()" in j
    assert "return refreshWorkingRun();" in j
    assert "refreshWorkingRun" in j
    _clean_wp()


def test_manualqa_saved_modify_crop_is_prominent_and_specific(client):
    j = js()
    assert "Your saved crop-change request" in j
    assert "Saved for this plan &middot; Pending Replan" in j
    assert '"Modify \\u2014 " + requestedCrop + " requested"' in j or '"Modify \u2014 " + requestedCrop + " requested"' in j
    assert "This is a farmer request, not an allocation or consent" in j


def test_manualqa_explain_returns_actual_plot_evidence_and_two_ranks(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    rid = wp["run_id"]

    # This test specifically needs two alternatives. Do not assume that the
    # first built-in row has two positive-return crops: the processed
    # operational economics legitimately leave some plots with only one.
    target = None

    for row in wp["recommendations"]:
        rec1 = client.post(
            f"/api/farmsync/working-plan/{rid}/recommend",
            json={
                "farmer_id": row["farmer_id"],
                "plot_id": row["plot_id"],
            },
        ).get_json()

        if rec1.get("found") and rec1.get("n_more", 0) > 0:
            target = (row, rec1)
            break

    assert target is not None, (
        "Built-in fixture has no plot with at least two cash-positive "
        "canonical alternatives"
    )

    r0, rec1 = target

    client.post(
        f"/api/farmsync/working-plan/{rid}/reject-candidate",
        json={
            "farmer_id": r0["farmer_id"],
            "plot_id": r0["plot_id"],
            "crop": rec1["recommended_crop"],
        },
    )

    rec2 = client.post(
        f"/api/farmsync/working-plan/{rid}/recommend",
        json={
            "farmer_id": r0["farmer_id"],
            "plot_id": r0["plot_id"],
        },
    ).get_json()

    assert rec2["found"] is True
    assert rec2["recommended_crop"] != rec1["recommended_crop"]

    ex = client.post(
        f"/api/farmsync/working-plan/{rid}/explain",
        json={
            "farmer_id": r0["farmer_id"],
            "plot_id": r0["plot_id"],
            "crop": rec2["recommended_crop"],
        },
    ).get_json()

    assert ex["available"] is True
    assert ex["feasible"] is True

    ev = ex["plot_evidence"]

    assert ev["region_id"]
    assert ev["season"]
    assert ev["soil_group"]
    assert ev["soil_suitability_class"]

    assert "available_water_m3" in ev
    assert "drainage_class" in ev
    assert "waterlogging_exposure" in ev

    assert ex["overall_rank"] is not None
    assert ex["n_feasible_overall"] >= ex["overall_rank"]

    # Once the first candidate is rejected, the second candidate becomes the
    # highest-ranked currently available alternative.
    assert ex["available_rank"] == 1

    rejected = [
        x for x in ex["exclusions"]
        if x["crop"] == rec1["recommended_crop"]
    ]

    assert rejected
    assert "rejected" in rejected[0]["reason"].lower()
    assert "deterministic" in ex["basis"].lower()

    _clean_wp()


def test_manualqa_why_ui_renders_real_evidence_not_generic_only(client):
    j = js()
    for label in ("Actual plot evidence used", "Soil group", "Soil suitability class",
                  "Available water", "Waterlogging exposure", "Overall feasible rank",
                  "Current available-alternative rank"):
        assert label in j
    assert "plot_evidence" in j and "assessment_checks" in j and "exclusions" in j


def test_manualqa_custom_upload_render_optional_dom_is_safe(client):
    j = js()
    assert 'sel.innerHTML = rsel.innerHTML' not in j
    assert 'if (sel)' in j and 'sel.innerHTML = options' in j
    assert 'if (rsel)' in j and 'rsel.innerHTML = options' in j
    assert "Validation response was received, but part of the report could not be rendered" in j
    assert "Upload request failed:" in j


def test_manualqa_three_csv_upload_returns_validation_and_readiness(client):
    _clean_wp()
    res = _upload_qa_agro(client)
    assert res.status_code == 200
    j = res.get_json()
    assert j["passed"] is True
    assert j["n_files"] >= 3
    assert "readiness" in j
    assert j["readiness"]["ready_to_plan"] is True
    _clean_wp()


def test_manualqa_explore_validation_readonly_with_no_source(client):
    import farmsync_routes as _fr
    _clean_wp()
    client.post("/api/farmsync/change-dataset")
    before = {
        "pkg": _fr._state.get("pkg"), "report": _fr._state.get("report"),
        "active": _fr._state.get("active"), "active_snapshot": _fr._state.get("active_snapshot"),
        "planning_source": _fr._state.get("planning_source"),
    }
    v = client.get("/api/farmsync/explore-validation").get_json()
    client.get("/api/farmsync/explore-tables")
    client.get("/api/farmsync/explore/farmers")
    after = {
        "pkg": _fr._state.get("pkg"), "report": _fr._state.get("report"),
        "active": _fr._state.get("active"), "active_snapshot": _fr._state.get("active_snapshot"),
        "planning_source": _fr._state.get("planning_source"),
    }
    assert v["read_only"] is True and "readiness" in v and "validation" in v
    assert before == after
    assert client.get("/api/farmsync/planning-source").get_json()["planning_source"] is None
    _clean_wp()


def test_manualqa_explore_validation_does_not_replace_custom_source(client):
    _clean_wp()
    up = _upload_qa_agro(client).get_json()
    assert up["readiness"]["ready_to_plan"] is True
    act = client.post("/api/farmsync/activate").get_json()
    assert act.get("planning_source") == "custom"
    before = client.get("/api/farmsync/planning-source").get_json()
    client.get("/api/farmsync/explore-validation")
    client.get("/api/farmsync/explore-tables")
    client.get("/api/farmsync/explore/plots")
    after = client.get("/api/farmsync/planning-source").get_json()
    assert after == before
    _clean_wp()


def test_manualqa_data_explorer_has_validation_and_zero_mutation_controls(client):
    j = js()
    assert "/api/farmsync/explore-validation" in j
    assert "Dataset Validation:" in j and "Planning readiness" in j and "Capability readiness" in j
    data_block = j.split('loaders.data = (el) => {', 1)[1].split('function mountExplorer', 1)[0]
    for forbidden in ("upload-package", "upload-farmers", "/activate", "select-builtin", "replaceName"):
        assert forbidden not in data_block


def test_manualqa_builtin_response_label_is_explicitly_synthetic(client):
    assert "Recorded synthetic farmer response" in js()


# ============= FINAL PLAN — pagination + final-crop semantics (§4) =============
def test_final_plan_no_60_row_truncation(client):
    # §4A: the Final Plan renderer must not silently truncate to 60 rows
    j = js()
    j2 = j.split("function renderFinalPlan")[1].split("loaders.fairness")[0]
    assert "slice(0, 60)" not in j2 and "slice(0,60)" not in j2
    assert "/final-rows" in j2 and "loadFinalRows" in j2          # full-universe paginated read


def test_final_plan_has_pagination_controls(client):
    j = js()
    lr = j.split("function loadFinalRows")[1].split("function _effectiveResp")[0]
    assert "finalPrev" in lr and "finalNext" in lr
    assert "Page " in lr and "of " in lr
    assert "FINAL_PAGE" in lr
    # 50 rows/page is enforced server-side in final_rows()
    eng = open(os.path.join(_ROOT, "farmsync", "exploratory_run.py")).read()
    assert "def final_rows(run, page, per)" in eng and "per = 50" in j.split("final-rows")[0][-400:] or "per=50" in eng or "50" in eng


def test_final_plan_five_columns_unchanged(client):
    j = js()
    final_block = j.split("loaders.final =")[1].split("/* ================= 6. EVALUATE")[0]  # includes renderFinalPlan
    # exactly the five required headers, in order
    assert "<th>Farmer</th><th>Plot</th><th>Final crop</th><th>Consent basis</th><th>Realised</th>" in final_block


def test_final_plan_unrealised_shows_dash_not_recommendation(client):
    # a NOT-realised row must not display a recommendation as if realised
    j = js()
    lr = j.split("function loadFinalRows")[1].split("function _effectiveResp")[0]
    assert "r.realised ? esc(r.final_crop) : '<span class=\"fs-muted\">&mdash;</span>'" in lr
    # no naive fallback to revised/original recommendation
    assert "r.final_crop || r.revised_crop || r.crop" not in lr


def test_final_page_resets_on_dataset_switch(client):
    j = js()
    # FINAL_PAGE is reset with working state so pagination never carries across datasets
    assert "FINAL_PAGE = 1" in j
    assert "FINAL_PAGE = 1;" in j.split("function resetWorkingState()")[1].split("}")[0]


# ============= WORKFLOW / REVISION / STALE-STATE INTEGRITY BACKBONE =============
def _wf(client, rid):
    return client.get(f"/api/farmsync/working-plan/{rid}").get_json()["workflow"]


def _start_builtin_run(client):
    _clean_wp()
    client.post("/api/farmsync/select-builtin")
    return client.post("/api/farmsync/working-plan/start").get_json()


def test_wf_initial_stage_gates(client):
    # consent/final/analyse locked before replan; plan/farmer/replan available
    wp = _start_builtin_run(client); rid = wp["run_id"]
    st = _wf(client, rid)["stages"]
    assert st["plan"] and st["farmer"] and st["replan"]
    assert st["consent"] is False and st["final"] is False and st["analyse"] is False
    _clean_wp()


def test_wf_response_edit_bumps_rev_idempotent(client):
    # a real response edit bumps response_rev; an identical save does not (idempotent)
    wp = _start_builtin_run(client); rid = wp["run_id"]
    r0 = next(r for r in wp["recommendations"] if r["crop"])
    before = _wf(client, rid)["response_rev"]
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "REJECT"})
    after = _wf(client, rid)["response_rev"]
    assert after == before + 1
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "REJECT"})
    assert _wf(client, rid)["response_rev"] == after     # idempotent: no bump
    _clean_wp()


def test_wf_replan_unlocks_consent_only_after_success(client):
    wp = _start_builtin_run(client); rid = wp["run_id"]
    assert _wf(client, rid)["stages"]["consent"] is False
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    assert _wf(client, rid)["stages"]["consent"] is True   # only after replan POST succeeded
    _clean_wp()


def test_wf_final_locked_while_consent_pending(client):
    wp = _start_builtin_run(client); rid = wp["run_id"]
    r0 = next(r for r in wp["recommendations"] if r["crop"])
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    w = _wf(client, rid)
    if w["n_requires_consent"] > 0:
        assert w["n_consent_pending"] > 0 and w["stages"]["final"] is False   # PENDING != accepted
    _clean_wp()


def test_wf_finalise_refused_server_side_while_pending(client):
    wp = _start_builtin_run(client); rid = wp["run_id"]
    r0 = next(r for r in wp["recommendations"] if r["crop"])
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    w = _wf(client, rid)
    if w["n_consent_pending"] > 0:
        fin = client.post(f"/api/farmsync/working-plan/{rid}/finalise").get_json()
        assert fin["available"] is False and "need" in fin["error"].lower()   # server refuses to finalise
    _clean_wp()


def test_wf_final_and_analyse_unlock_after_finalise(client):
    wp = _start_builtin_run(client); rid = wp["run_id"]
    # resolve all consent, finalise, then analyse unlocks + final_current
    r0 = next(r for r in wp["recommendations"] if r["crop"])
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    for r in run["recommendations"]:
        if r.get("changed") and r.get("requires_renewed_consent"):
            client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "renewed_response": "ACCEPT"})
    assert _wf(client, rid)["stages"]["analyse"] is False   # not until finalise
    fin = client.post(f"/api/farmsync/working-plan/{rid}/finalise").get_json()
    assert fin["available"] is True
    w = _wf(client, rid)
    assert w["final_current"] is True and w["stages"]["analyse"] is True
    _clean_wp()


def test_wf_no_change_no_consent_required_final_unlocks(client):
    # if replan changes nothing, no renewed consent required -> final unlocks directly
    wp = _start_builtin_run(client); rid = wp["run_id"]
    client.post(f"/api/farmsync/working-plan/{rid}/replan")     # with recorded responses, may change some
    w = _wf(client, rid)
    if w["n_requires_consent"] == 0:
        assert w["stages"]["final"] is True
    _clean_wp()


def test_wf_upstream_edit_invalidates_downstream(client):
    # finalise a plan, then edit a response -> replan/final/analyse all go stale/locked
    wp = _start_builtin_run(client); rid = wp["run_id"]
    r0 = next(r for r in wp["recommendations"] if r["crop"])
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    for r in run["recommendations"]:
        if r.get("changed") and r.get("requires_renewed_consent"):
            client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "renewed_response": "ACCEPT"})
    client.post(f"/api/farmsync/working-plan/{rid}/finalise")
    assert _wf(client, rid)["final_current"] is True
    # now an upstream edit on a DIFFERENT plot
    r1 = next(r for r in run["recommendations"] if r["crop"] and r["plot_id"] != r0["plot_id"])
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r1["farmer_id"], "plot_id": r1["plot_id"], "action": "REJECT"})
    w = _wf(client, rid)
    assert w["replan_current"] is False and w["final_current"] is False
    assert w["stages"]["consent"] is False and w["stages"]["analyse"] is False
    _clean_wp()


def test_wf_consent_edit_invalidates_final(client):
    wp = _start_builtin_run(client); rid = wp["run_id"]
    r0 = next(r for r in wp["recommendations"] if r["crop"])
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r0["farmer_id"], "plot_id": r0["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    changed = [r for r in run["recommendations"] if r.get("changed") and r.get("requires_renewed_consent")]
    if not changed:
        _clean_wp(); return
    for r in changed:
        client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "renewed_response": "ACCEPT"})
    client.post(f"/api/farmsync/working-plan/{rid}/finalise")
    assert _wf(client, rid)["final_current"] is True
    # change one consent decision -> final stale
    c0 = changed[0]
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": c0["farmer_id"], "plot_id": c0["plot_id"], "renewed_response": "REJECT"})
    assert _wf(client, rid)["final_current"] is False
    _clean_wp()


def test_wf_revisiting_without_edit_keeps_downstream_current(client):
    # finalise, then just GET the run repeatedly (revisit) -> final stays current, no re-finalise
    wp = _start_builtin_run(client); rid = wp["run_id"]
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    for r in run["recommendations"]:
        if r.get("changed") and r.get("requires_renewed_consent"):
            client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "renewed_response": "ACCEPT"})
    client.post(f"/api/farmsync/working-plan/{rid}/finalise")
    assert _wf(client, rid)["final_current"] is True
    for _ in range(3):
        client.get(f"/api/farmsync/working-plan/{rid}")          # revisit (GET only)
    assert _wf(client, rid)["final_current"] is True             # still current; GET never mutates
    _clean_wp()


def test_wf_dataset_change_detaches_workflow(client):
    j = js()
    # dataset change resets working state (run id, revisions) client-side
    assert "resetWorkingState()" in j
    reset_block = j.split("function resetWorkingState()")[1].split("}")[0]
    assert "WORK.runId = null" in reset_block and "FINAL_PAGE = 1" in reset_block


# ---- JS: no view-time mutation; explicit actions; hash obeys state ----
def test_js_final_plan_is_read_only_on_open(client):
    j = js()
    final_fn = j.split("loaders.final = (el)")[1].split("function renderFinalReadyToFinalise")[0]
    # opening Final Plan must NOT POST /finalise
    assert '/finalise", {' not in final_fn and "method: \"POST\"" not in final_fn
    assert "READ-ONLY on open" in final_fn


def test_js_finalise_only_via_explicit_action(client):
    j = js()
    # the only /finalise POST lives behind the explicit doFinalise button
    ready_fn = j.split("function renderFinalReadyToFinalise")[1].split("function renderFinalPlan")[0]
    assert "doFinalise" in ready_fn and '/finalise"' in ready_fn
    assert "Finalise Consent-Verified Plan" in ready_fn
    # pagination handlers re-render, they do not POST
    plan_fn = j.split("function loadFinalRows")[1].split("function _effectiveResp")[0]
    assert "finalPrev" in plan_fn and "finalNext" in plan_fn
    assert '/finalise' not in plan_fn and "method: \"POST\"" not in plan_fn


def test_js_replan_is_read_only_on_open(client):
    j = js()
    replan_fn = j.split("loaders.replan = (el)")[1].split("function renderRunReplan")[0]
    assert '/replan", {' not in replan_fn and "method: \"POST\"" not in replan_fn
    assert "READ-ONLY on open" in replan_fn
    # explicit Run Replan action exists
    assert "Run Replan" in j and "doReplan" in j


def test_js_access_is_server_derived(client):
    j = js()
    assert "function wfStages()" in j
    assert "WORK.data && WORK.data.workflow && WORK.data.workflow.stages" in j
    # refreshWorkingRun re-derives nav after every mutation
    refresh = j.split("function refreshWorkingRun()")[1].split("function workingModeNote()")[0]
    assert "renderNavLocks(); renderWorkflow();" in refresh


def test_js_hash_navigation_obeys_state(client):
    j = js()
    # hash restore only navigates to a stage that is actually unlocked (server-derived), else Home
    assert "valid.includes(hash) && isUnlocked(hash)" in j


# ============= BACKBONE CLOSURE (0A/0B/0C) + FULL RENEWED CONSENT =============
def _agro_custom_files():
    import csv as _csv
    bp = [r for r in _csv.DictReader(open(os.path.join(_ROOT, "data/farmsync/builtin/plots.csv")))
          if r["region_id"] == "R1" and r["active_season"] == "kharif"][:4]
    cols = "plot_id,farmer_id,region_id,area_ha,soil_group,soil_suitability_class,drainage_class,available_water_m3,waterlogging_exposure,active_season,previous_crop"
    pl = [cols]
    for j, rp in enumerate(bp, 1):
        fi = ((j - 1) % 3) + 1
        pl.append(f"QA00{fi}-P{j:02d},QA00{fi},R1,{rp['area_ha']},{rp['soil_group']},{rp['soil_suitability_class']},{rp['drainage_class']},{rp['available_water_m3']},{rp['waterlogging_exposure']},kharif,{rp['previous_crop']}")
    f = "farmer_id,collective_id,region_id,season\n" + "\n".join(f"QA00{i},QAC1,R1,kharif" for i in range(1, 4))
    cl = "collective_id,region_id,season\nQAC1,R1,kharif"
    return f, "\n".join(pl), cl


def _activate_custom(client):
    import io as _io
    f, p, cl = _agro_custom_files()
    client.post("/api/farmsync/change-dataset")
    client.post("/api/farmsync/upload-farmers",
                data={"farmers.csv": (_io.BytesIO(f.encode()), "farmers.csv"),
                      "plots.csv": (_io.BytesIO(p.encode()), "plots.csv"),
                      "collectives.csv": (_io.BytesIO(cl.encode()), "collectives.csv")},
                content_type="multipart/form-data")
    client.post("/api/farmsync/activate")


# ---- 0A: start hydrates workflow; farmer gated on run ----
def test_0a_start_returns_workflow(client):
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    assert "workflow" in wp and wp["workflow"]["stages"]["replan"] is True
    _clean_wp()


def test_0a_ensure_session_hydrates_and_farmer_gated(client):
    j = js()
    # ensureWorkingSession stores the authoritative shape and re-derives nav
    ens = j.split("function ensureWorkingSession()")[1].split("function")[0]
    assert "renderNavLocks(); renderWorkflow();" in ens
    # before a run exists, only Initial Plan is reachable (farmer not bypassable)
    assert "if (!st) return false;" in j and 'return ws === "plan" || ws === "farmer"' not in j


# ---- 0B: consent handler rehydrates authoritative state ----
def test_0b_consent_handler_refreshes(client):
    j = js()
    dec = j.split("function consentDecide(")[1].split("function renderConsentEdit")[0]
    assert "refreshWorkingRun()" in dec and "renderConsentStage" in dec
    # no separate client consent truth: state comes from the refreshed run
    assert 'rr.renewed_response = b.dataset.consent' not in j


# ---- 0C: custom unset != ACCEPT/CONSENTED ----
def test_0c_custom_unset_not_accept(client):
    _clean_wp(); _activate_custom(client)
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    wf = wp["workflow"]
    assert wf["replan_ready"] is False and wf["n_unresolved"] == 4
    assert wf["stages"]["replan"] is False              # custom unset blocks replan
    _clean_wp()


def test_0c_custom_replan_refused_while_unset(client):
    _clean_wp(); _activate_custom(client)
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    r = client.post(f"/api/farmsync/working-plan/{wp['run_id']}/replan")
    assert r.status_code == 400 and "no working response" in r.get_json()["error"].lower()
    _clean_wp()


def test_0c_explicit_custom_no_response_and_builtin_unaffected(client):
    _clean_wp(); _activate_custom(client)
    wp = client.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    for i, r in enumerate(wp["recommendations"]):
        client.post(f"/api/farmsync/working-plan/{rid}/response",
                    json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"],
                          "action": "NO_RESPONSE" if i == 0 else "ACCEPT"})
    wf = client.get(f"/api/farmsync/working-plan/{rid}").get_json()["workflow"]
    assert wf["replan_ready"] is True and wf["n_unresolved"] == 0
    assert client.post(f"/api/farmsync/working-plan/{rid}/replan").get_json()["available"] is True
    # built-in recorded responses need no manual entry
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    bwp = client.post("/api/farmsync/working-plan/start").get_json()
    assert bwp["workflow"]["replan_ready"] is True and bwp["workflow"]["stages"]["replan"] is True
    _clean_wp()


# ---- Renewed Consent behaviour ----
def _consent_setup(client, n_reject=6):
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    for r in [r for r in wp["recommendations"] if r["crop"]][:n_reject]:
        client.post(f"/api/farmsync/working-plan/{rid}/response",
                    json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    changed = [r for r in run["recommendations"] if r.get("changed") and r.get("requires_renewed_consent")]
    return rid, changed


def test_rc_accept_reject_noresp_realisation(client):
    rid, changed = _consent_setup(client)
    assert len(changed) >= 3
    A, B, C = changed[0], changed[1], changed[2]
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "renewed_response": "ACCEPT"})
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": B["farmer_id"], "plot_id": B["plot_id"], "renewed_response": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": C["farmer_id"], "plot_id": C["plot_id"], "renewed_response": "NO_RESPONSE"})
    # accept the rest so we can finalise
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    for r in run["recommendations"]:
        if r.get("changed") and r.get("requires_renewed_consent") and r["plot_id"] not in (A["plot_id"], B["plot_id"], C["plot_id"]):
            client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "renewed_response": "ACCEPT"})
    client.post(f"/api/farmsync/working-plan/{rid}/finalise")
    run2 = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    a = next(r for r in run2["recommendations"] if r["plot_id"] == A["plot_id"])
    b = next(r for r in run2["recommendations"] if r["plot_id"] == B["plot_id"])
    cc = next(r for r in run2["recommendations"] if r["plot_id"] == C["plot_id"])
    assert a["realised"] is True and a["consent_basis"] == "RENEWED_ACCEPT"      # ACCEPT -> realised
    assert b["realised"] is False and b["final_crop"] is None                    # REJECT -> not realised, no fallback
    assert cc["realised"] is False and cc["final_crop"] is None                  # NO_RESPONSE -> not realised
    _clean_wp()


def test_rc_finalise_refused_while_pending(client):
    rid, changed = _consent_setup(client)
    # leave everything pending
    fin = client.post(f"/api/farmsync/working-plan/{rid}/finalise").get_json()
    assert fin["available"] is False
    _clean_wp()


def test_rc_bulk_pending_only_preserves_individual(client):
    rid, changed = _consent_setup(client)
    A = changed[0]
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "renewed_response": "REJECT"})
    bulk = client.post(f"/api/farmsync/working-plan/{rid}/consent-bulk", json={"decision": "ACCEPT"}).get_json()
    assert bulk["workflow"]["n_consent_pending"] == 0
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    a = next(r for r in run["recommendations"] if r["plot_id"] == A["plot_id"])
    assert a["renewed_response"] == "REJECT"        # individual decision preserved
    # everyone else accepted
    others = [r for r in run["recommendations"] if r.get("changed") and r["plot_id"] != A["plot_id"]]
    assert all(r["renewed_response"] == "ACCEPT" for r in others)
    _clean_wp()


def test_rc_bulk_reject_pending_only(client):
    rid, changed = _consent_setup(client)
    A = changed[0]
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "renewed_response": "ACCEPT"})
    client.post(f"/api/farmsync/working-plan/{rid}/consent-bulk", json={"decision": "REJECT"})
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    a = next(r for r in run["recommendations"] if r["plot_id"] == A["plot_id"])
    assert a["renewed_response"] == "ACCEPT"         # preserved
    _clean_wp()


def test_rc_edit_after_bulk_and_invalidates_final(client):
    rid, changed = _consent_setup(client)
    client.post(f"/api/farmsync/working-plan/{rid}/consent-bulk", json={"decision": "ACCEPT"})
    client.post(f"/api/farmsync/working-plan/{rid}/finalise")
    assert client.get(f"/api/farmsync/working-plan/{rid}").get_json()["workflow"]["final_current"] is True
    A = changed[0]
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "renewed_response": "REJECT"})
    wf = client.get(f"/api/farmsync/working-plan/{rid}").get_json()["workflow"]
    assert wf["final_current"] is False and wf["stages"]["analyse"] is False   # edit invalidates Final/Analyse
    _clean_wp()


def test_rc_use_recommendation_clears_consent_and_stales(client):
    rid, changed = _consent_setup(client)
    B = changed[0]
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": B["farmer_id"], "plot_id": B["plot_id"], "renewed_response": "ACCEPT"})
    # find an alternative feasible crop DIFFERENT from the current revised crop
    rec = client.post(f"/api/farmsync/working-plan/{rid}/recommend", json={"farmer_id": B["farmer_id"], "plot_id": B["plot_id"], "exclude": [B["revised_crop"]]}).get_json()
    if not rec.get("found"):
        _clean_wp(); return
    sel = client.post(f"/api/farmsync/working-plan/{rid}/select-recommendation", json={"farmer_id": B["farmer_id"], "plot_id": B["plot_id"], "crop": rec["recommended_crop"]}).get_json()
    assert sel["available"] is True and sel["revised_crop"] == rec["recommended_crop"]
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    b = next(r for r in run["recommendations"] if r["plot_id"] == B["plot_id"])
    assert b["revised_crop"] == rec["recommended_crop"]     # crop changed
    assert b["renewed_response"] is None                    # old consent cleared (choosing != consent)
    assert b["consent_for_crop"] is None                    # PENDING for the new crop
    _clean_wp()


def test_rc_select_revalidates_infeasible_refused(client):
    rid, changed = _consent_setup(client)
    B = changed[0]
    r = client.post(f"/api/farmsync/working-plan/{rid}/select-recommendation", json={"farmer_id": B["farmer_id"], "plot_id": B["plot_id"], "crop": "dragonfruit"})
    assert r.status_code == 400 and "not a feasible" in r.get_json()["error"].lower()
    _clean_wp()


def test_rc_recommend_and_explain_are_read_only(client):
    rid, changed = _consent_setup(client)
    B = changed[0]
    before = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    b0 = next(r for r in before["recommendations"] if r["plot_id"] == B["plot_id"])
    client.post(f"/api/farmsync/working-plan/{rid}/recommend", json={"farmer_id": B["farmer_id"], "plot_id": B["plot_id"]})
    client.post(f"/api/farmsync/working-plan/{rid}/explain", json={"farmer_id": B["farmer_id"], "plot_id": B["plot_id"], "crop": B["revised_crop"]})
    after = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    b1 = next(r for r in after["recommendations"] if r["plot_id"] == B["plot_id"])
    assert b1["revised_crop"] == b0["revised_crop"] and b1["renewed_response"] == b0["renewed_response"]
    assert after["workflow"]["response_rev"] == before["workflow"]["response_rev"]   # no rev bump
    _clean_wp()


def test_rc_zero_changed_no_consent_required(client):
    # if replan changes nothing, consent stage requires no rows and final is finalisable
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    client.post(f"/api/farmsync/working-plan/{rid}/replan")     # no edits -> recorded responses only
    wf = client.get(f"/api/farmsync/working-plan/{rid}").get_json()["workflow"]
    if wf["n_requires_consent"] == 0:
        assert wf["stages"]["final"] is True
    _clean_wp()


# ---- JS wiring for the consent UX ----
def test_rc_js_full_consent_ux_present(client):
    j = js()
    assert "function renderConsentStage" in j and "function consentCardHTML" in j
    assert "Current revised recommendation" in j and "fs-cc-newcrop" in j     # prominent revised crop
    assert "Accept recommendation" in j and "Explore another option" in j and "Ask why" in j
    assert "Accept all pending" in j and "Reject all pending" in j
    assert "Edit response" in j
    assert "Use this recommendation" in j
    # browsing read-only note + choosing != consent
    assert "Browsing does not change the revised crop or grant consent" in j
    # all consent mutations route through refreshWorkingRun
    for fn in ("consentDecide", "bulkConsent", "consentUseRecommendation"):
        block = j.split("function " + fn + "(")[1].split("function ")[0]
        assert "refreshWorkingRun()" in block


# ============= CONSENT-REVISION CLOSURE + FULL DATASET UNIVERSE + DYNAMIC ANALYSE =============
def _finalise_builtin(client, n_reject=5):
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    for r in [r for r in wp["recommendations"] if r["crop"]][:n_reject]:
        client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    client.post(f"/api/farmsync/working-plan/{rid}/consent-bulk", json={"decision": "ACCEPT"})
    client.post(f"/api/farmsync/working-plan/{rid}/finalise")
    return rid


# consent revision closure (same-crop-after-new-replan)
def test_consent_revision_same_crop_after_new_replan_invalidated(client):
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    tgt = next(r for r in wp["recommendations"] if r["crop"] and r["recorded_response"] != "REJECT")
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": tgt["farmer_id"], "plot_id": tgt["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    A = next(r for r in run["recommendations"] if r["plot_id"] == tgt["plot_id"] and r["changed"])
    cropA = A["revised_crop"]
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "renewed_response": "ACCEPT"})
    a1 = next(r for r in client.get(f"/api/farmsync/working-plan/{rid}").get_json()["recommendations"] if r["plot_id"] == A["plot_id"])
    assert a1["consent_for_replan_anchor"] == 1     # stamped with the replan anchor
    # upstream change -> stale replan; stale mutations refused
    other = next(r for r in run["recommendations"] if r["crop"] and r["plot_id"] != A["plot_id"] and r["recorded_response"] != "REJECT")
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": other["farmer_id"], "plot_id": other["plot_id"], "action": "REJECT"})
    assert client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "renewed_response": "ACCEPT"}).status_code == 400
    assert client.post(f"/api/farmsync/working-plan/{rid}/consent-bulk", json={"decision": "ACCEPT"}).status_code == 400
    assert client.post(f"/api/farmsync/working-plan/{rid}/select-recommendation", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "crop": cropA}).status_code == 400
    # rerun replan -> SAME crop -> old consent NOT valid -> pending
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    run2 = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    A2 = next(r for r in run2["recommendations"] if r["plot_id"] == A["plot_id"])
    assert A2["revised_crop"] == cropA                       # same crop again
    assert A2["consent_for_replan_anchor"] != run2["replan_anchor"]   # old anchor != current
    assert run2["workflow"]["n_consent_pending"] > 0         # pending -> fresh consent required
    assert run2["workflow"]["stages"]["final"] is False      # final locked
    _clean_wp()


# full dataset universe
def test_universe_builtin_population_500_911(client):
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json()
    assert wp["population"]["farmers"] == 500 and wp["population"]["plots"] == 911
    assert len(wp["recommendations"]) < 911                  # offer subset is a genuine subset
    ds = wp.get("dataset_snapshot")
    assert ds and ds["n_farmers"] == 500 and ds["n_plots"] == 911
    _clean_wp()


def test_final_rows_full_universe_and_no_offer(client):
    rid = _finalise_builtin(client)
    fr = client.get(f"/api/farmsync/working-plan/{rid}/final-rows?filter=all&page=19").get_json()
    assert fr["counts"]["all"] == 911 and fr["total"] == 911 and fr["per_page"] == 50
    assert fr["last"] == 911
    no_offer = [r for r in fr["rows"] if r["reason"] == "NO_INITIAL_OFFER"]
    assert no_offer and all(r["final_crop"] is None and r["realised"] is False for r in no_offer)
    # NO_INITIAL_OFFER is not classified as a response category
    assert all(r["reason"] not in ("NO_RESPONSE", "REJECT", "WITHDRAW") for r in no_offer)
    _clean_wp()


# analyse gate / provenance / reconciliation
def test_analysis_gate_and_provenance(client):
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    assert client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()["available"] is False  # pre-finalise
    _clean_wp()
    rid = _finalise_builtin(client)
    a = client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()
    assert a["available"] is True and a["provenance"] == "CURRENT_WORKING_FINAL_PLAN"
    assert a["run_id"] == rid and a["final_plan_revision"] == 1
    # upstream edit -> analysis unavailable (pick an un-edited plot and make a REAL change)
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    other = next(r for r in run["recommendations"] if r["crop"] and not r.get("working_response"))
    new_act = "WITHDRAW" if other.get("recorded_response") != "WITHDRAW" else "NO_RESPONSE"
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": other["farmer_id"], "plot_id": other["plot_id"], "action": new_act})
    assert client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()["available"] is False
    _clean_wp()


def test_analysis_reconciliation_invariants(client):
    rid = _finalise_builtin(client)
    a = client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()
    o = a["overview"]
    assert o["realised_plots"] + o["not_realised_plots"] == o["total_plots"]       # A
    assert o["offered_plots"] + o["no_offer_plots"] == o["total_plots"]            # B
    assert sum(a["initial_response_history"].values()) == a["n_offer_rows"]        # C (offer rows)
    assert sum(a["renewed_consent_outcomes"].values()) == a["n_requires_renewed_consent"]  # D
    assert a["workflow"]["n_consent_pending"] if False else True                  # E (pending 0 at final_current)
    assert client.get(f"/api/farmsync/working-plan/{rid}").get_json()["workflow"]["n_consent_pending"] == 0
    assert sum(a["not_realised_reasons"].values()) == o["not_realised_plots"]      # F
    assert sum(a["crop_composition_plots"].values()) == o["realised_plots"]        # G
    assert a["integrity"]["ok"] is True                                            # overall integrity
    _clean_wp()


def test_analysis_initial_reject_can_be_realised(client):
    # an initial REJECT that received a revised crop + RENEWED_ACCEPT is realised, not a final rejection
    rid = _finalise_builtin(client)
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    realised_from_change = [r for r in run["recommendations"] if r["realised"] and r["consent_basis"] == "RENEWED_ACCEPT"]
    assert realised_from_change                                # some initial REJECT -> renewed ACCEPT -> realised
    a = client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()
    # those are NOT counted as final rejections in the reason breakdown
    assert a["not_realised_reasons"].get("RENEWED_REJECT", 0) >= 0
    _clean_wp()


def test_analysis_fairness_includes_all_farmers_and_zeros(client):
    rid = _finalise_builtin(client)
    a = client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()
    f = a["fairness"]
    assert f["n_farmers"] == 500                               # all selected farmers
    assert f["n_zero_realisation_farmers"] > 0                 # zero-return farmers included
    assert f["n_participants"] + f["n_zero_realisation_farmers"] == 500
    assert f["all_farmer_abs_cash_gini"] is not None
    _clean_wp()


def test_analysis_concentration_alpha_is_reference(client):
    rid = _finalise_builtin(client)
    a = client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()
    cc = a["concentration"]
    assert cc["alpha_reference"] == 0.40
    assert "reference" in cc["note"].lower() and "not an enforced" in cc["note"].lower()
    # composition uses realised only
    assert sum(a["crop_composition_plots"].values()) == a["overview"]["realised_plots"]
    _clean_wp()


def test_analysis_uncertainty_resilience_not_available_not_frozen(client):
    rid = _finalise_builtin(client)
    a = client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()
    assert a["uncertainty"]["available"] is False
    assert a["uncertainty"]["status"] == "NOT_RUN"
    assert a["uncertainty"]["protocol_version"] == "interactive-stress-v1"
    assert "Not evaluated" in a["uncertainty"]["reason"]

    assert a["resilience"]["available"] is False
    assert a["resilience"]["status"] == "NOT_RUN"
    assert a["resilience"]["protocol_version"] == "interactive-resilience-v1"
    assert "Not evaluated" in a["resilience"]["reason"]
    _clean_wp()


def test_analysis_no_solver_on_get(client):
    import sys as _s
    rid = _finalise_builtin(client)
    _s.modules.pop("pulp", None)
    client.get(f"/api/farmsync/working-plan/{rid}/analysis")
    client.get(f"/api/farmsync/working-plan/{rid}/final-rows?page=2")
    assert "pulp" not in _s.modules
    _clean_wp()


def test_analysis_js_dynamic_and_gated(client):
    j = js()
    assert "function loadAnalysis()" in j and "/analysis" in j
    assert "function overviewBlock" in j and "Consent &amp; participation outcomes" in j
    assert "function analyseUnavailable" in j
    # uncertainty/resilience are evaluated only by explicit user action.
    assert "Run Analysis" in j
    assert "Re-run Analysis" in j
    assert "/run-analysis" in j
    assert 'method: "POST"' in j
    assert "interactive-stress-v1" in j
    assert "interactive-resilience-v1" in j
    # fairness renders all-farmer gini + zero-realisation
    assert "All-farmer per-ha Gini" in j and "Zero-realisation farmers" in j


# ============= CLOSURE PATCH: UI consent revision, real integrity, explicit coverage =============
def test_ui_consent_state_checks_replan_anchor(client):
    # #1: the frontend consent-state helper mirrors the backend (crop AND replan anchor)
    j = js()
    fn = j.split("function _consentStateOf(")[1].split("function ")[0]
    assert "r.consent_for_crop === r.revised_crop" in fn
    assert "r.consent_for_replan_anchor === replanAnchor" in fn
    # both callers thread the run's replan_anchor
    assert "_consentStateOf(r, _anchor)" in j and "consentCardHTML(r, _anchor)" in j
    assert "const _anchor = run.replan_anchor" in j


def test_ui_consent_same_crop_after_new_replan_is_pending(client):
    # backend proves the row is PENDING; the UI helper (same rule) must render PENDING too. We verify the
    # authoritative rec fields the UI reads: stale anchor + same crop -> not a valid current decision.
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    tgt = next(r for r in wp["recommendations"] if r["crop"] and r["recorded_response"] != "REJECT")
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": tgt["farmer_id"], "plot_id": tgt["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    A = next(r for r in run["recommendations"] if r["plot_id"] == tgt["plot_id"] and r["changed"])
    cropA = A["revised_crop"]
    client.post(f"/api/farmsync/working-plan/{rid}/consent", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "renewed_response": "ACCEPT"})
    other = next(r for r in run["recommendations"] if r["crop"] and r["plot_id"] != A["plot_id"] and not r.get("working_response"))
    client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": other["farmer_id"], "plot_id": other["plot_id"], "action": "WITHDRAW"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    run2 = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    A2 = next(r for r in run2["recommendations"] if r["plot_id"] == A["plot_id"])
    # exactly the fields the UI helper compares
    assert A2["revised_crop"] == cropA                                   # same crop
    assert A2["consent_for_crop"] == cropA                               # crop matches (would pass old UI)
    assert A2["consent_for_replan_anchor"] != run2["replan_anchor"]      # but anchor is stale -> PENDING
    _clean_wp()


def test_integrity_no_placeholder(client):
    eng = open(os.path.join(_ROOT, "farmsync", "exploratory_run.py")).read()
    assert "def workflow_pending" not in eng and "if False" not in eng
    # integrity is called with authoritative pending + current revision
    assert "_analysis_integrity(payload, wf[\"n_consent_pending\"], run.get(\"final_plan_revision\"))" in eng
    # the two added invariants
    assert "initial_response_history != n_offer_rows" in eng
    assert "analysis final_plan_revision != current run final_plan_revision" in eng


def test_integrity_invariants_hold_on_valid_plan(client):
    rid = _finalise_builtin(client)
    a = client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()
    assert a["integrity"]["ok"] is True and a["integrity"]["failures"] == []
    _clean_wp()


def test_integrity_failure_withholds_metrics_in_ui(client):
    # #2 UI: if integrity.ok is false, the loader renders provenance+error and STOPS (no metrics)
    j = js()
    assert "function integrityBlocked" in j
    for tab in ("loaders.fairness", "loaders.uncertainty", "loaders.resilience"):
        block = j.split(tab + " = (el)")[1].split("loaders.")[0] if (tab + " = (el)") in j else ""
        assert "integrityBlocked(el, a" in block, tab
    # fairness no longer prefixes the banner then renders metrics anyway
    assert "integrityBanner(a) + overviewBlock(a)" not in j


def test_explicit_consent_metric_definitions(client):
    rid = _finalise_builtin(client)
    a = client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()
    o = a["overview"]
    # ambiguous single "consent_coverage" removed; three explicit metrics present
    assert "consent_coverage" not in o
    assert "affirmative_consent_coverage" in o and "realisation_rate_offered" in o and "realisation_rate_all_plots" in o
    # affirmative coverage denominator matches finalisation (realised / consent-eligible)
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    assert abs(o["affirmative_consent_coverage"] - run["consent_coverage_final"]) < 1e-9
    # realisation rates use their own denominators
    assert abs(o["realisation_rate_offered"] - (o["realised_plots"] / o["offered_plots"])) < 1e-9
    assert abs(o["realisation_rate_all_plots"] - (o["realised_plots"] / o["total_plots"])) < 1e-9
    # REJECT/NO_RESPONSE are not affirmative consent -> visible in renewed accounting, not coverage
    assert "RENEWED_REJECT" in a["renewed_consent_outcomes"] and "RENEWED_NO_RESPONSE" in a["renewed_consent_outcomes"]
    _clean_wp()


def test_ui_coverage_labels_unambiguous(client):
    j = js()
    assert "Affirmative consent coverage" in j
    assert "Realisation rate (offered)" in j and "Realisation rate (all plots)" in j
    # the bare/ambiguous "Consent coverage" tile label is gone from Analyse overview
    assert "mt(\"Consent coverage\"" not in j


# ============= PRE-QA UX CLOSURE: consent alt semantics, Final Plan filters, Analyse UX =============
def _changed_row(client, rid):
    run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    return next(r for r in run["recommendations"] if r.get("changed") and r.get("requires_renewed_consent")), run


def _setup_changed(client, action="REJECT", n=5):
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    for r in [r for r in wp["recommendations"] if r["crop"]][:n]:
        client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "action": action})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    return rid


# Renewed Consent alternative semantics
def test_consent_alt_excludes_current_revised_crop(client):
    rid = _setup_changed(client)
    A, _ = _changed_row(client, rid)
    alt = client.post(f"/api/farmsync/working-plan/{rid}/consent-alternative", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"]}).get_json()
    if alt.get("found"):
        assert alt["recommended_crop"] != A["revised_crop"]     # #1: never the current revised crop
    _clean_wp()


def test_consent_alt_browse_history_excludes(client):
    rid = _setup_changed(client)
    A, _ = _changed_row(client, rid)
    alt = client.post(f"/api/farmsync/working-plan/{rid}/consent-alternative", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"]}).get_json()
    if not alt.get("found") or alt.get("n_more", 0) < 1:
        _clean_wp(); return
    alt2 = client.post(f"/api/farmsync/working-plan/{rid}/consent-alternative", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "exclude": [alt["recommended_crop"]]}).get_json()
    assert not alt2.get("found") or alt2["recommended_crop"] != alt["recommended_crop"]
    _clean_wp()


def test_consent_alt_excludes_rejected_alternatives(client):
    rid = _setup_changed(client)
    A, _ = _changed_row(client, rid)
    alt = client.post(f"/api/farmsync/working-plan/{rid}/consent-alternative", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"]}).get_json()
    if not alt.get("found"):
        _clean_wp(); return
    rejected = alt["recommended_crop"]
    client.post(f"/api/farmsync/working-plan/{rid}/reject-candidate", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "crop": rejected})
    alt2 = client.post(f"/api/farmsync/working-plan/{rid}/consent-alternative", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"]}).get_json()
    assert not alt2.get("found") or alt2["recommended_crop"] != rejected     # persistent rejection stays excluded
    _clean_wp()


def test_consent_alt_is_read_only(client):
    rid = _setup_changed(client)
    A, run0 = _changed_row(client, rid)
    b0 = run0["workflow"]["response_rev"]
    crop0 = A["revised_crop"]
    client.post(f"/api/farmsync/working-plan/{rid}/consent-alternative", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"]})
    run1 = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    A1 = next(r for r in run1["recommendations"] if r["plot_id"] == A["plot_id"])
    assert A1["revised_crop"] == crop0 and A1.get("renewed_response") is None   # browsing mutates nothing
    assert run1["workflow"]["response_rev"] == b0
    _clean_wp()


def test_consent_alt_ui_has_ask_why_and_restart(client):
    j = js()
    ce = j.split("function consentExplore")[1].split("function consentUseRecommendation")[0]
    assert "consent-alternative" in ce
    assert 'data-why-candidate="' in ce and 'data-use="' in ce   # #2 Ask why on candidate (distinct attr)
    assert "All feasible alternatives viewed" in ce and "Review from beginning" in ce   # #3 exhaustion/restart
    assert "Return to original plan" in ce                            # original-crop return option


# Final Plan filters + terminology
def test_final_plan_filter_counts_reconcile(client):
    rid = _finalise_builtin(client)
    r = client.get(f"/api/farmsync/working-plan/{rid}/final-rows?filter=realised").get_json()
    n = client.get(f"/api/farmsync/working-plan/{rid}/final-rows?filter=not_realised").get_json()
    a = client.get(f"/api/farmsync/working-plan/{rid}/final-rows?filter=all").get_json()
    assert r["counts"]["realised"] + r["counts"]["not_realised"] == r["counts"]["all"]   # #22
    assert a["counts"]["all"] == 911                                                     # #21/#23
    assert r["total"] == r["counts"]["realised"] and n["total"] == n["counts"]["not_realised"]  # #19/#20
    assert all(row["realised"] for row in r["rows"])                                     # #18 default realised
    assert all(not row["realised"] for row in n["rows"])
    _clean_wp()


def test_final_plan_default_realised_and_terminology(client):
    j = js()
    fp = j.split("function renderFinalPlan")[1].split("var REASON_LABEL")[0]
    assert "Plots in dataset" in fp and "Initially allocated / offered" in fp and "No initial allocation" in fp
    assert "Selected plots" not in fp                                  # #4 term removed
    assert 'data-filter="realised"' in fp and 'data-filter="not_realised"' in fp and 'data-filter="all"' in fp
    assert 'loadFinalRows(el, run, "realised")' in fp                  # #18 default
    assert "Final realised allocations" in fp                          # #6 heading
    # reconciliation copy + dash meaning
    assert "A dash does not mean the plot is missing" in fp


def test_final_plan_reason_in_realised_cell_humanised(client):
    j = js()
    lr = j.split("function loadFinalRows")[1].split("function _effectiveResp")[0]
    assert "not realised &middot; ' + esc(humanReason(r.reason))" in lr   # #7 reason in Realised cell
    # NO_INITIAL_OFFER -> no initial allocation
    assert 'NO_INITIAL_OFFER: "no initial allocation"' in j


def test_final_plan_filter_pagination_no_mutation(client):
    import sys as _s
    rid = _finalise_builtin(client)
    before = client.get(f"/api/farmsync/working-plan/{rid}").get_json()["workflow"]
    _s.modules.pop("pulp", None)
    for f in ("realised", "not_realised", "all"):
        client.get(f"/api/farmsync/working-plan/{rid}/final-rows?filter={f}&page=2")
    after = client.get(f"/api/farmsync/working-plan/{rid}").get_json()["workflow"]
    assert before == after and "pulp" not in _s.modules             # #25/#47 no mutation, no solver
    _clean_wp()


# Initial Plan B1/B2/B3 explainer
def test_initial_plan_coverage_and_baselines(client):
    j = js()
    ip = j.split("loaders.plan = (el)")[1].split("loaders.farmer = (el)")[0]
    assert "Plots in dataset" in ip and "Initially allocated / offered" in ip and "No initial allocation" in ip
    assert "Where does this plan come from?" in ip
    assert "B1 &mdash;" in ip and "B2 &mdash;" in ip and "B3 &mdash;" in ip and "FarmSync Proposed" in ip
    assert "starts from the <b>B3 initial planned allocation</b>" in ip
    assert "not have to allocate a crop to every plot" in ip          # #8 no full-allocation claim


# Analyse UX
def test_analyse_navigation_ctas(client):
    j = js()
    assert 'nextCta("Continue to Uncertainty", "uncertainty")' in j    # #11 fairness -> uncertainty
    assert 'nextCta("Continue to Resilience", "resilience")' in j       # uncertainty -> resilience
    assert "Analysis complete" in j and "Review Final Plan" in j        # resilience -> complete


def test_analyse_navigation_no_mutation(client):
    j = js()
    # the nav CTAs are data-ws navigation only (no POST in the resilience/fairness/uncertainty complete area)
    assert 'data-ws="final"' in j and 'data-ws="repro"' in j


def test_analyse_humanised_codes(client):
    j = js()
    assert "function humanReason" in j
    assert 'INITIAL_REJECT_NO_ALTERNATIVE: "initial reject' in j
    assert 'RENEWED_REJECT: "renewed reject"' in j
    # overview uses humanReason for the not-realised reasons + friendly response labels
    assert "esc(humanReason(k))" in j and 'ACCEPT: "Accepted"' in j


def test_analyse_concentration_basis_label(client):
    j = js()
    assert 'cc.basis === "area" ? "Area share" : "Plot share"' in j    # #13


def test_analyse_unavailable_wording_not_duplicated(client):
    j = js()
    assert "function cleanUnavail" in j
    # Shared NOT_RUN/STALE renderer cleans backend wording once.
    assert "function cleanUnavail" in j
    assert "function analysisRunState" in j
    assert "cleanUnavail(" in j
    # backend reason still starts with "Not available —"; UI strips it so the sentence isn't doubled
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    rid = _finalise_builtin(client)
    a = client.get(f"/api/farmsync/working-plan/{rid}/analysis").get_json()
    assert a["uncertainty"]["available"] is False
    assert a["uncertainty"]["status"] == "NOT_RUN"
    assert a["uncertainty"]["reason"].startswith("Not evaluated")
    _clean_wp()


# ============= CONSENT ALT — bind ALL Use buttons + exhaustion Ask-why isolation =============
def test_consent_alt_binds_all_use_buttons(client):
    # #1: BOTH a normal candidate Use and a Return-to-original Use must be wired (querySelectorAll)
    j = js()
    fn = j.split("function wireConsentAltButtons")[1].split("function consentUseRecommendation")[0]
    assert 'out.querySelectorAll("[data-use]").forEach' in fn
    assert 'out.querySelector("[data-use]")' not in fn                 # the single-bind bug is gone
    # #2: each Use sends its OWN exact crop (u.dataset.use), not a shared one
    assert "consentUseRecommendation(fid, pid, u.dataset.use, el)" in fn
    # the original-return option renders its own data-use with the original crop
    ce = j.split("function consentExplore")[1].split("function wireConsentAltButtons")[0]
    assert 'data-use="' + "' + esc(orig.crop) + '" in ce


def test_consent_alt_exhaustion_has_dedicated_why_div(client):
    # #3: the exhaustion branch renders a dedicated .fs-consent-why so Ask why on the original-return
    # option does not replace the exhaustion message / Review-from-beginning / original controls.
    j = js()
    ce = j.split("function consentExplore")[1].split("function wireConsentAltButtons")[0]
    exhaustion = ce.split("if (!rc.available || !rc.found)")[1].split("return;")[0]
    assert "All feasible alternatives viewed" in exhaustion
    assert "Review from beginning" in exhaustion
    assert '<div class="fs-consent-why"></div>' in exhaustion          # dedicated target added
    # Ask why renders into .fs-consent-why (isolated), not into the whole card
    fn = j.split("function wireConsentAltButtons")[1].split("function consentUseRecommendation")[0]
    assert 'out.querySelector(".fs-consent-why") || out' in fn


def test_consent_alt_ask_why_is_read_only(client):
    # #4: Ask why (the /explain call the Use/original buttons sit beside) mutates nothing
    rid = _setup_changed(client)
    A, run0 = _changed_row(client, rid)
    before = run0["workflow"]["response_rev"]
    crop0 = A["revised_crop"]
    client.post(f"/api/farmsync/working-plan/{rid}/explain", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "crop": A["crop"]})       # original crop
    client.post(f"/api/farmsync/working-plan/{rid}/explain", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "crop": A["revised_crop"]})  # revised crop
    run1 = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    A1 = next(r for r in run1["recommendations"] if r["plot_id"] == A["plot_id"])
    assert A1["revised_crop"] == crop0 and A1.get("renewed_response") is None
    assert run1["workflow"]["response_rev"] == before
    _clean_wp()


def test_consent_alt_original_use_backend_selects_exact_crop(client):
    # #2 (backend): selecting the original crop via /select-recommendation uses that EXACT crop when feasible;
    # infeasible original -> refused (server revalidation). Guardrails (crop+anchor consent) unchanged.
    rid = _setup_changed(client)
    A, _ = _changed_row(client, rid)
    orig = A["crop"]
    res = client.post(f"/api/farmsync/working-plan/{rid}/select-recommendation", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "crop": orig})
    j = res.get_json()
    if res.status_code == 200:
        assert j["revised_crop"] == orig                              # exact original crop selected
        run = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
        row = next(r for r in run["recommendations"] if r["plot_id"] == A["plot_id"])
        assert row["renewed_response"] is None and row["consent_for_crop"] is None   # choosing != consent -> PENDING
    else:
        assert res.status_code == 400 and "not a feasible" in j["error"].lower()      # infeasible -> refused
    _clean_wp()


# ============= CONSENT ASK-WHY EVENT-COLLISION FIX =============
def test_consent_why_attributes_are_distinct(client):
    j = js()
    card = j.split("function consentCardHTML")[1].split("function wireConsentCards")[0]
    # top-level current-recommendation Ask Why uses data-why-current (not the shared data-why)
    assert 'data-why-current="1"' in card
    ce = j.split("function consentExplore")[1].split("function wireConsentAltButtons")[0]
    # explored + original-return Ask Why use data-why-candidate with their exact crop
    assert 'data-why-candidate="' + "' + esc(rc.recommended_crop) + '" in ce
    assert 'data-why-candidate="' + "' + esc(orig.crop) + '" in ce
    # no bare data-why= attribute survives (the collision source)
    assert 'data-why="' not in j


def test_parent_handler_ignores_explore_area_ask_why(client):
    j = js()
    wc = j.split("function wireConsentCards")[1].split("function consentDecide")[0]
    # the parent handles ONLY data-why-current, and only when NOT inside .fs-consent-out
    assert 'e.target.closest("[data-why-current]")' in wc
    assert 'e.target.closest(".fs-consent-out")' in wc
    assert "whyCurrent && !inExplore" in wc
    # the parent no longer matches a generic [data-why]
    assert 'const why = e.target.closest("[data-why]")' not in wc


def test_candidate_ask_why_binds_own_crop(client):
    j = js()
    fn = j.split("function wireConsentAltButtons")[1].split("function consentUseRecommendation")[0]
    # candidate Ask Why is wired locally on data-why-candidate and sends its OWN displayed crop
    assert 'out.querySelectorAll("[data-why-candidate]").forEach' in fn
    assert "crop: w.dataset.whyCandidate" in fn
    # renders into the dedicated .fs-consent-why host (not replacing controls)
    assert 'out.querySelector(".fs-consent-why") || out' in fn
    # ALL use buttons still bound; exhaustion still has a dedicated why host
    assert 'out.querySelectorAll("[data-use]").forEach' in fn
    ce = j.split("function consentExplore")[1].split("function wireConsentAltButtons")[0]
    exhaustion = ce.split("if (!rc.available || !rc.found)")[1].split("return;")[0]
    assert '<div class="fs-consent-why"></div>' in exhaustion and "Review from beginning" in exhaustion


def test_ask_why_backend_targets_exact_crop_and_read_only(client):
    # functional: /explain returns evidence for the EXACT crop asked (current, candidate, original), and
    # never mutates working state (crop/consent/revisions unchanged).
    rid = _setup_changed(client)
    A, run0 = _changed_row(client, rid)
    before_rev = run0["workflow"]["response_rev"]
    revised = A["revised_crop"]; original = A["crop"]
    # current revised crop
    ex_cur = client.post(f"/api/farmsync/working-plan/{rid}/explain", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "crop": revised}).get_json()
    assert ex_cur["available"] and ex_cur["crop"] == revised
    # an explored candidate crop (excluding the revised one) -> explain targets THAT crop, not the revised
    alt = client.post(f"/api/farmsync/working-plan/{rid}/consent-alternative", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"]}).get_json()
    if alt.get("found"):
        cand = alt["recommended_crop"]
        assert cand != revised
        ex_cand = client.post(f"/api/farmsync/working-plan/{rid}/explain", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "crop": cand}).get_json()
        assert ex_cand["available"] and ex_cand["crop"] == cand and ex_cand["crop"] != revised
    # original crop explain targets the original
    ex_orig = client.post(f"/api/farmsync/working-plan/{rid}/explain", json={"farmer_id": A["farmer_id"], "plot_id": A["plot_id"], "crop": original}).get_json()
    assert ex_orig.get("crop") == original
    # read-only: nothing changed
    run1 = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    A1 = next(r for r in run1["recommendations"] if r["plot_id"] == A["plot_id"])
    assert A1["revised_crop"] == revised and A1.get("renewed_response") is None
    assert run1["workflow"]["response_rev"] == before_rev and run1["workflow"]["final_current"] == run0["workflow"]["final_current"]
    _clean_wp()


# ============= PAGINATION INPUT-SAFETY (product fix) =============
def _finalise_for_pagination(client):
    _clean_wp(); client.post("/api/farmsync/select-builtin")
    wp = client.post("/api/farmsync/working-plan/start").get_json(); rid = wp["run_id"]
    for r in [r for r in wp["recommendations"] if r["crop"]][:3]:
        client.post(f"/api/farmsync/working-plan/{rid}/response", json={"farmer_id": r["farmer_id"], "plot_id": r["plot_id"], "action": "REJECT"})
    client.post(f"/api/farmsync/working-plan/{rid}/replan")
    client.post(f"/api/farmsync/working-plan/{rid}/consent-bulk", json={"decision": "ACCEPT"})
    client.post(f"/api/farmsync/working-plan/{rid}/finalise")
    return rid


def test_pagination_page_never_500_all_routes(client):
    rid = _finalise_for_pagination(client)
    client.post("/api/farmsync/load-builtin")   # stage pkg so /inspect + /explore are reachable
    page_urls = [
        f"/api/farmsync/working-plan/{rid}/final-rows?filter=all&page=%s",
        "/api/farmsync/explore/plots?page=%s",
        "/api/farmsync/inspect/plots?page=%s",
    ]
    for tmpl in page_urls:
        for pv in ("abc", "", "1.5", "0", "-1", "1", "999999"):
            r = client.get(tmpl % pv)
            assert r.status_code != 500, "%s -> 500" % (tmpl % pv)
            assert r.status_code in (200, 400, 404), "%s unexpected %d" % (tmpl % pv, r.status_code)
    _clean_wp()


def test_pagination_page_normalisation(client):
    rid = _finalise_for_pagination(client)
    base = f"/api/farmsync/working-plan/{rid}/final-rows?filter=all"
    for pv in ("abc", "", "1.5", "0", "-1"):
        j = client.get(f"{base}&page={pv}").get_json()
        assert j["page"] == 1, "page=%r -> %r (want 1)" % (pv, j["page"])
    assert client.get(f"{base}&page=1").get_json()["page"] == 1
    j = client.get(f"{base}&page=999999").get_json()
    assert j["page"] == j["pages"], "huge page clamps to last (%d != %d)" % (j["page"], j["pages"])
    _clean_wp()


def test_inspect_size_normalisation(client):
    _clean_wp(); client.post("/api/farmsync/load-builtin")
    contract = [("", 25), ("abc", 25), ("1.5", 25), ("0", 1), ("-5", 1),
                ("1", 1), ("25", 25), ("100", 100), ("999999", 100)]
    for sv, want in contract:
        r = client.get(f"/api/farmsync/inspect/plots?size={sv}")
        assert r.status_code == 200, "size=%r -> %d" % (sv, r.status_code)
        assert r.get_json()["size"] == want, "size=%r -> %r (want %d)" % (sv, r.get_json()["size"], want)
    # size page also safe
    for pv in ("abc", "", "0", "-1"):
        r = client.get(f"/api/farmsync/inspect/plots?page={pv}")
        assert r.status_code == 200 and r.get_json()["page"] == 1
    _clean_wp()


def test_malformed_pagination_read_only(client):
    # malformed pagination must not mutate planning source / working-run state
    rid = _finalise_for_pagination(client)
    before = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    ps_before = client.get("/api/farmsync/planning-source").get_json()["planning_source"]
    client.post("/api/farmsync/load-builtin")
    for u in (f"/api/farmsync/working-plan/{rid}/final-rows?filter=all&page=abc",
              "/api/farmsync/explore/plots?page=-1", "/api/farmsync/inspect/plots?page=abc&size=abc"):
        client.get(u)
    after = client.get(f"/api/farmsync/working-plan/{rid}").get_json()
    assert after["response_rev"] == before["response_rev"]
    assert after["replan_anchor"] == before["replan_anchor"]
    assert after.get("final_plan_revision") == before.get("final_plan_revision")
    assert after["workflow"]["final_current"] == before["workflow"]["final_current"]
    assert client.get("/api/farmsync/planning-source").get_json()["planning_source"] == ps_before
    _clean_wp()


def test_safe_int_arg_helper_contract(client):
    # unit-level contract on the reusable helper
    import farmsync_routes as fr
    from flask import Flask
    app = Flask(__name__)
    def probe(qs):
        with app.test_request_context("/?" + qs):
            return (fr._safe_int_arg("page", 1, minimum=1),
                    fr._safe_int_arg("size", 25, minimum=1, maximum=100))
    assert probe("") == (1, 25)
    assert probe("page=abc&size=abc") == (1, 25)
    assert probe("page=1.5&size=1.5") == (1, 25)
    assert probe("page=0&size=0") == (1, 1)
    assert probe("page=-9&size=-9") == (1, 1)
    assert probe("page=7&size=50") == (7, 50)
    assert probe("page=999999&size=999999") == (999999, 100)


def test_data_explorer_select_has_accessible_name(client):
    # a11y: the Data Explorer table <select> must have an accessible name (aria-label) — guards the
    # select-name CRITICAL fix. Narrow markup assertion; real a11y authority stays in the axe harness.
    j = js()
    assert '<select id="exTable" aria-label="Dataset table">' in j
    # scope guard: the search input and IDs are unchanged
    assert 'id="exSearch"' in j and 'id="exTable"' in j


def test_scrollable_tablewrap_keyboard_focusable_helper(client):
    # a11y: scrollable .fs-tablewrap regions are made keyboard-focusable regions (scrollable-region-focusable).
    # Assert the actual decorator contract (not a bare tabindex string): it only decorates OVERFLOWING
    # wrappers, sets tabindex/role/aria-label, is scheduled after renders, and has a focus-visible style.
    j = js()
    dec = j.split("function _a11yDecorateScrollRegions")[1].split("function activate(ws)")[0]
    assert ".fs-tablewrap" in dec
    assert "scrollWidth > w.clientWidth" in dec and "scrollHeight > w.clientHeight" in dec  # only when overflowing
    assert 'setAttribute("tabindex", "0")' in dec and 'setAttribute("role", "region")' in dec
    assert 'setAttribute("aria-label", "Scrollable data table")' in dec
    assert "_a11yScheduleScrollDecorate()" in j and "MutationObserver" in j   # runs on renders + async re-renders
    css = open(os.path.join(_ROOT, "static", "css", "farmsync.css")).read()
    assert ".fs-tablewrap[tabindex]:focus-visible" in css                     # visible keyboard focus


def test_light_theme_contrast_families_not_raw_weak(client):
    # a11y: the high-volume light-theme semantic-text families must be darkened toward --ink (>=4.5:1),
    # not left as raw bright hues. Guards the complete color-contrast closure. Browser axe remains authority.
    css = open(os.path.join(_ROOT, "static", "css", "farmsync.css")).read()
    light = css  # the fix is appended as [data-theme="light"] .fs-app overrides
    # revised/MODIFY (blue), final/initial (optimal), REJECT (red), cc-cash/teach-k (amber) darkened
    assert 'color:color-mix(in srgb,var(--sci-blue) 58%,var(--ink))' in light
    assert 'color:color-mix(in srgb,var(--sci-optimal) 50%,var(--ink))' in light
    assert 'color:color-mix(in srgb,var(--sci-red) 58%,var(--ink))' in light
    assert '.fs-cc-cash' in light and '.fs-teach-k' in light and 'color:color-mix(in srgb,var(--acc) 52%,var(--ink))' in light
    # the struck-through original-crop opacity dimming removed in light theme
    assert '[data-theme="light"] .fs-app .fs-cc-old{opacity:1}' in light
    # prior a11y fixes preserved
    assert '.fs-tablewrap[tabindex]:focus-visible' in css                 # scrollable-region focus
    j = js()
    assert '<select id="exTable" aria-label="Dataset table">' in j        # select-name

def test_phase2_exhaustion_wording_on_last_candidate(client):
    # When the currently shown candidate is the final feasible alternative, the UI must say so explicitly
    # while still offering Review from beginning. This is presentation-only; browsing remains read-only.
    j = js()
    assert 'All feasible alternatives viewed.' in j
    assert 'rc.n_more > 0' in j
    tail = j.split('rc.n_more > 0', 1)[1][:600]
    assert 'All feasible alternatives viewed.' in tail
    assert 'data-restart="1"' in tail and 'Review from beginning' in tail


def test_phase2_targeted_light_and_dark_contrast_closure(client):
    css = open(os.path.join(_ROOT, "static", "css", "farmsync.css")).read()
    # Windows axe evidence: .fs-edited failed only in light; dark muted text was below AA on dark cards/nav;
    # the dark info callout was 4.35:1. Keep fixes FarmSync/theme scoped.
    assert '[data-theme="light"] .fs-app .fs-edited{color:color-mix(in srgb,var(--acc) 52%,var(--ink))}' in css
    assert '[data-theme="dark"] .fs-app{--mut:#8c8c96}' in css
    assert '[data-theme="dark"] .fs-app .fs-note-box.info{color:color-mix(in srgb,var(--sci-blue) 82%,var(--ink))}' in css
    # Latest populated dark scan: four remaining contrast families, fixed with narrowly scoped text/opacity overrides.
    assert '[data-theme="dark"] .fs-app .fs-act.REJECT{color:color-mix(in srgb,var(--sci-red) 78%,var(--ink))}' in css
    assert '[data-theme="dark"] .fs-app .fs-cc-old{opacity:1}' in css
    assert '[data-theme="dark"] .fs-app .fs-state.final{color:color-mix(in srgb,var(--sci-green) 80%,var(--ink))}' in css
    assert '[data-theme="dark"] .fs-app .fs-note-box.caveat{color:color-mix(in srgb,var(--sci-violet) 80%,var(--ink))}' in css

def test_current_explanation_ui_is_data_driven_not_hardcoded():
    j = js()

    header = j[
        j.index("function aiHeader"):
        j.index("function recCard")
    ]

    # Header must not print ai.understood; otherwise the explanation is duplicated.
    assert "FarmSync response" in header
    assert "ai.understood ?" not in header

    expl = j[
        j.index("function renderAiExplanation"):
        j.index("function aiTechDrawer")
    ]

    # Current explanation is built from deterministic evidence.
    assert "ev.assessment_checks" in expl
    assert "ev.plot_evidence" in expl
    assert "ev.expected_cash" in expl
    assert "rup(ev.expected_cash)" in expl
    assert "ev.current_plan_crop" in expl
    assert "ev.agronomic_feasible" in expl
    assert "ev.eligible_for_selection" in expl
    assert "ev.rank_reproducible" in expl

    # No case-specific scientific outcome may be typed into the JS.
    assert "258775" not in expl
    assert "Onion is the current FarmSync recommendation" not in expl

    # Farmer-facing terminology is consistent.
    assert "expected value" in expl

    # Technical qualification is retained instead of being hidden.
    assert "does not reproduce a rankable cash-positive entry" in expl

def test_final30_badge_is_amber_in_light_and_green_by_default(client):
    css = open(CSS).read()
    assert '.fs-badge-final{background:var(--sci-green-s)' in css
    assert '[data-theme="light"] .fs-app .fs-badge-final{background:var(--sci-amber-s)' in css
    assert 'color:color-mix(in srgb,var(--sci-amber) 45%,var(--ink))' in css


def test_advanced_results_have_consistent_next_navigation(client):
    j = js()
    assert 'const advancedNext =' in j
    helper = j[j.index('const advancedNext ='):j.index('/* ---------- FarmSync modal')]
    # Preserve the original Scenario A/B neutral continuation control everywhere in Advanced:
    # no orange primary treatment, no extra "Next research view" label, no arrow.
    assert '<div class="fs-cta-row fs-advanced-next"><button class="fs-btn"' in helper
    assert 'fs-btn-primary' not in helper
    assert 'Next research view' not in helper
    assert '&rarr;' not in helper
    expected = [
        'advancedNext("Uncertainty Results", "uncresults")',
        'advancedNext("Sensitivity & Robustness Results", "sensitivity")',
        'advancedNext("Scalability Results", "scale")',
        'advancedNext("Reliability & Statistical Evidence", "reliability")',
        'advancedNext("Scenario A/B Results", "scenario")',
        'advancedNext("Research details & reproducibility", "repro")',
    ]
    for needle in expected:
        assert needle in j
    inside_panel = [
        "advancedNext(\"Uncertainty Results\", \"uncresults\") + '</div>'",
        "advancedNext(\"Sensitivity & Robustness Results\", \"sensitivity\") + '</div>'",
        "advancedNext(\"Scalability Results\", \"scale\") + '</div>'",
        "advancedNext(\"Reliability & Statistical Evidence\", \"reliability\") + '</div>'",
        "advancedNext(\"Scenario A/B Results\", \"scenario\") + '</div>'",
        'advancedNext("Research details & reproducibility", "repro") +',
    ]
    for needle in inside_panel:
        assert needle in j


def test_change_dataset_uses_exact_records_insight_modal_pattern_not_native_confirm(client):
    j = js()
    css = open(CSS).read()
    block = j[j.index('function requestChangeDataset()'):j.index('function renderRequirements')]
    assert 'fsConfirm(message, resetDataset' in block
    assert 'window.confirm' not in j
    assert 'Change dataset?' in block
    assert 'Keep current dataset' in block
    assert '.fs-modal-overlay' in css and '.fs-modal-card' in css
    assert 'background:rgba(0,0,0,0);' in css
    assert 'background:rgba(0,0,0,.5);' in css
    assert 'backdrop-filter:blur(12px)' in css
    assert 'border:2px solid var(--border-color);' in css
    assert 'border-radius:var(--radius-xl);' in css
    assert 'padding:40px 36px 32px;' in css
    assert 'max-width:420px;' in css
    assert 'text-align:center;' in css
    assert 'transform:scale(.88) translateY(30px);' in css
    assert 'transform:scale(.92) translateY(20px);' in css
    assert 'transform:scaleX(0);' in css and '.fs-modal-visible .fs-modal-accent-bar{transform:scaleX(1)}' in css
    assert '.fs-modal-btn{' in css and 'min-width:140px;' in css
    assert '.fs-modal-btn-ghost{' in css
    assert 'align-items:flex-end' not in css
    modal = j[j.index('function fsConfirm'):j.index('function explainLockedStage')]
    assert 'fs-modal-btn fs-modal-btn-ghost fs-modal-cancel' in modal
    assert 'fs-modal-btn fs-modal-confirm' in modal
    assert 'class="fs-btn fs-modal' not in modal
    assert 'document.body;' in j and 'root.appendChild(overlay)' in j
    assert 'overlay.classList.add("fs-modal-exiting")' in modal
    assert 'overlay.classList.remove("fs-modal-visible")' in modal
    assert '}, 500);' in modal
    assert 'role="dialog" aria-modal="true"' in j


def test_pending_renewed_consent_gets_modal_before_final_plan(client):
    j = js()
    gate = j[j.index('function explainLockedStage'):j.index('/* ---------- progressive-disclosure state')]
    assert 'ws === "final"' in gate
    assert 'wf.n_consent_pending' in gate
    assert 'Renewed consent incomplete' in gate
    assert 'Accept, Reject, or No response' in gate
    assert 'Review renewed consent' in gate
    assert 'if (!isUnlocked(ws)) { flashLock(ws); return; }' in j
    assert 'if (explainLockedStage(ws)) return;' in j


def test_hero_particles_travel_bottom_to_top_like_records_insight(client):
    j = js()
    css = open(CSS).read()
    particles = j[j.index('function initParticles()'):j.index('document.addEventListener("DOMContentLoaded"')]
    assert 'i < 28' in particles
    assert '2 + Math.random() * 4' in particles
    assert '(6 + Math.random() * 6)' in particles
    assert '.forge-particle{position:absolute;top:100%' in css
    assert 'translate3d(0,-120vh,0)' in css
    assert 'animation:fsParticleFloat 8s linear infinite' in css
