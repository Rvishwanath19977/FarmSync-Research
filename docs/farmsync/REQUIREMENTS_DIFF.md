# FarmSync → AskVish requirements.txt merge

Package: `farmsync-phase7-integration-2026-08-19`

The existing AskVish `requirements.txt` is preserved in full. Only the three packages below
were **added** for the FarmSync research build. No existing AskVish dependency was removed or
changed.

| Dependency | Existing / Added | Version | Reason | Importing module(s) | Scope |
|---|---|---|---|---|---|
| pulp | **Added** | `==3.3.2` | MILP solver for all baseline (B1/B2/B3) and Proposed (Phase 3/4/5/6) optimisation; bundles CBC 2.10.3. Pinned because the solver build affects deterministic optimisation output. | `farmsync/ilp_reference.py`, `farmsync/baselines.py`, `farmsync/proposed/{reoptimize,concentration,resilience}.py` | runtime |
| xlrd | **Added** | `==2.0.2` | Reads the legacy `.xls` DES APY raw source during ingest (openpyxl cannot read `.xls`). | `farmsync/ingest/run_ingest.py` | runtime (ingest) |
| pytest | **Added** | `>=7.4.0` | Runs the FarmSync deterministic test suite (198 tests). | `tests/test_farmsync_*.py` | test-only |

Already present in AskVish `requirements.txt` and reused by FarmSync (not re-added):
`pandas` (data frames / ingest), `openpyxl` (reads the `.xlsx` Cost-of-Cultivation codebook),
`numpy` (numeric), `Flask` / `Werkzeug` (routes + Dataset Manager test client),
`python-dotenv` (root `.env` discovery for the live smoke test).

Solver note: CBC 2.10.3 ships inside the `pulp==3.3.2` wheel; no separate system solver install
is required on Windows.
