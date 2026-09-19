# FarmSync Phase-7 — AskVish Integration README (Windows)

**Package:** `farmsync-phase7-integration-2026-08-19`
**Filename:** `farmsync_phase7_askvish_integration.zip`
**Type:** integration checkpoint (NOT the final publication/reproducibility release)

This package integrates the validated FarmSync Phase-1–7 build into your existing AskVish
`PORTFOLIO/` project, alongside ATS Forge, RecordsInsight, SheetInsight, AdCraft and the chatbot.
No live API call, benchmark, or experiment is run by this package.

## What changes in your existing project

**UPDATED EXISTING (review before overwrite):**
- `app.py` — exactly two lines added (import + `register_farmsync_routes(app)`), matching the
  existing `register_*_routes(app)` pattern. All existing AskVish functionality is preserved.
- `requirements.txt` — three FarmSync packages appended (`pulp`, `xlrd`, `pytest`); nothing removed.

**SAFE TO COPY DIRECTLY (all NEW — no existing file touched):**
- `farmsync/` (complete package, Phases 1–7)
- `farmsync_routes.py`
- `templates/farmsync.html`, `static/css/farmsync.css`, `static/js/farmsync.js`
- `scripts/p7_live_smoketest.py`
- `tests/test_farmsync_*.py`
- `data/farmsync/**` (builtin synthetic data, processed tables, snapshots, raw government sources)
- `results/farmsync/**` (frozen baseline + Phase 1–7 artifacts)
- `docs/farmsync/**`

`templates/base.html` and `templates/projects.html` are **not** modified. FarmSync is reachable
directly at `/farm-sync`. If you want a nav/card link, add one line to your own nav template
(optional): `<a href="/farm-sync">FarmSync</a>` — this package does not overwrite those files.

## Step-by-step (Windows PowerShell)

1. **Back up PORTFOLIO.** In the folder that contains `PORTFOLIO\`:
   ```powershell
   Copy-Item -Recurse -Force .\PORTFOLIO .\PORTFOLIO_backup_before_farmsync
   ```
2. **Extract the ZIP** to a temporary location:
   ```powershell
   Expand-Archive -Path .\farmsync_phase7_askvish_integration.zip -DestinationPath .\_farmsync_pkg -Force
   ```
3. **Copy/merge into PORTFOLIO** (this overlays the new files and the updated `app.py` /
   `requirements.txt`; your `.env` is untouched because the package contains no `.env`):
   ```powershell
   Copy-Item -Recurse -Force .\_farmsync_pkg\* .\PORTFOLIO\
   ```
4. **Preserve your `.env`.** The package contains no `.env`, so your existing
   `PORTFOLIO\.env` (with `GROQ_API_KEY`, `OPENAI_API_KEY`) is left in place. Confirm it still exists:
   ```powershell
   Test-Path .\PORTFOLIO\.env
   ```
5. **Confirm file locations:**
   ```powershell
   cd .\PORTFOLIO
   Test-Path .\farmsync\proposed\llm_interaction.py
   Test-Path .\farmsync_routes.py
   Test-Path .\scripts\p7_live_smoketest.py
   Test-Path .\data\farmsync\raw_sources\SHA256SUMS.txt
   ```
6. **Activate your virtual environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
7. **Install merged requirements:**
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
8. **Verify imports:**
   ```powershell
   python -c "import farmsync; import farmsync_routes; print('FarmSync imports OK')"
   ```
9. **Run tests** (chunked — Phase 5/6 MILP solves are heavy):
   ```powershell
   python -m pytest tests/ -q --ignore=tests/test_farmsync_proposed_p5.py --ignore=tests/test_farmsync_proposed_p6.py
   python -m pytest tests/test_farmsync_proposed_p5.py -q
   python -m pytest tests/test_farmsync_proposed_p6.py -q
   ```
10. **Start AskVish:**
    ```powershell
    python app.py
    ```
11. **Open FarmSync UI:** browse to `http://127.0.0.1:5000/farm-sync`
12. **Verify the Dataset Manager UI loads** (load built-in dataset / inspect tables).
13. **Stop Flask:** press `Ctrl+C` in the PowerShell window.
14. **Run the Phase-7 live smoke test** (auto-discovers `PORTFOLIO\.env`):
    ```powershell
    python scripts/p7_live_smoketest.py
    ```
15. **Interpret the JSON `status`:**
    - `PASSED` — all 5 probes met expectations, exit 0. Good to proceed (after review).
    - `FAILED` — at least one probe failed, exit non-zero. The JSON lists failing probes/reasons.
    - `SKIPPED` — no API key/provider/network detected, exit 0. Nothing was called; not an error.
16. **What to send back for review:** the full JSON printed by step 14 (it never contains your
    API key). Also send the three pytest summary lines from step 9.
17. **Exact next step after `PASSED`:** STOP and send the smoke-test JSON. The live 41-case
    development evaluation is the next phase and runs only after that output is reviewed — it is
    not part of this checkpoint.

## Notes
- The live smoke test makes exactly one API call per probe (5 total), never prints/persists your
  key, exits non-zero on failure, and returns `SKIPPED` safely when credentials are unavailable.
- No FarmSync optimisation result was changed by packaging; Phase 1–6 artifacts are frozen.
