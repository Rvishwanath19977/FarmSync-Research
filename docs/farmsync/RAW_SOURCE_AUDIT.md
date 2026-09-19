# FarmSync raw-source audit

Package: `farmsync-phase7-integration-2026-08-19`

All original government/source artifacts previously supplied and used by FarmSync are
**physically present** in this package under `data/farmsync/raw_sources/`. None are missing.
Integrity verified against `data/farmsync/raw_sources/SHA256SUMS.txt` — all data artifacts `OK`
(the only `sha256sum -c` mismatch is `SHA256SUMS.txt` verifying its own line, which is expected
and not a data-integrity problem).

Data-artifact classification — these are **ORIGINAL SOURCE** files (not processed, not synthetic,
not generated results):

| # | Source family | Original filename | SHA256 (short) | Used? | Processed derivative |
|---|---|---|---|---|---|
| 1 | DES APY (production/yield) | `des_apy/horizontal_crop_vertical_year_report.xls` | `77f9de27…` | yes | `data/farmsync/processed/yield_state.csv` |
| 2 | DES Cost of Cultivation | `cost_of_cultivation/cost-of-cultivation.csv` | `8419c53c…` | yes | `data/farmsync/processed/cost_state.csv` |
| 3 | Cost of Cultivation codebook | `cost_of_cultivation/Cost_of_Cultivation_codebook.xlsx` | `74f74ea6…` | yes | (schema/codebook for #2) |
| 4 | AGMARKNET | `agmarknet/All_Type_of_Report__All_Grades__14-08-2026_02-49-13_PM.csv` | `aa3c3027…` | yes | `market_price_state.csv`, `arrivals_state.csv`, `absorption_proxy.csv` |
| 5 | AGMARKNET | `agmarknet/All_Type_of_Report__All_Grades__14-08-2026_02-56-15_PM.csv` | `b6f4b401…` | yes | (same) |
| 6 | AGMARKNET | `agmarknet/All_Type_of_Report__All_Grades__14-08-2026_03-01-10_PM.csv` | `9b177688…` | yes | (same) |
| 7 | AGMARKNET | `agmarknet/All_Type_of_Report__All_Grades__14-08-2026_03-03-54_PM.csv` | `758e970e…` | yes | (same) |
| 8 | AGMARKNET | `agmarknet/All_Type_of_Report__All_Grades__14-08-2026_06-19-55_PM.csv` | `4d8a1c58…` | yes | (same) |

Plus the checksum record `data/farmsync/raw_sources/SHA256SUMS.txt`.

**Data-class boundaries (never conflated):**
- ORIGINAL SOURCE → `data/farmsync/raw_sources/**` (8 artifacts above).
- PROCESSED DERIVATIVE → `data/farmsync/processed/**` (state tables + `source_manifest.json`).
- SYNTHETIC DATA → `data/farmsync/builtin/**` and `data/farmsync/snapshots/**` (synthetic 500-farmer
  universe; labelled synthetic — NOT a government source).
- GENERATED RESULT → `results/farmsync/**` (baseline + Phase 1–7 optimisation/evaluation artifacts).

**Missing original sources:** NONE. Every original artifact used by FarmSync is included.
