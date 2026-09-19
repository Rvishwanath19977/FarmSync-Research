# FarmSync Research

**Resilient Farmer-in-the-Loop Collective Crop Planning under Market,
Resource, and Participation Uncertainty: A Fairness-Aware Dynamic
Reoptimization Framework**

FarmSync is a reproducible research implementation for collective crop
planning under economic, resource, participation, and operational
uncertainty.

The repository contains the scientific implementation, frozen
publication experiments, source and processed datasets, statistical
analysis artifacts, reproducibility checks, and a standalone research
web demonstrator.

## Research idea

FarmSync studies a planning setting in which individually rational crop
choices may conflict with collective market capacity, fairness, and
changing farmer participation.

The framework compares:

- **B1** — individual profit-oriented planning,
- **B2** — collective market-aware planning,
- **B3** — fairness-aware collective planning, and
- **Proposed** — farmer-in-the-loop dynamic reoptimization beginning
  from the B3 allocation.

The publication configuration uses:

- fairness threshold `epsilon = 0.95`
- disruption weight `lambda = 0.05`
- concentration parameter `alpha = 0.40`
- fairness protocol `fairness-v2`
- consent protocol `action-consent-v1`
- uncertainty protocol `uncertainty-v1`

## Human and LLM authority boundary

The language model is not the decision-maker.

Where enabled, the LLM is restricted to interface functions such as:

- interpreting farmer text,
- mapping requests to supported structured actions, and
- explaining deterministic system results.

The LLM does **not** determine:

- crop allocations,
- feasibility,
- farmer approvals,
- hard or soft locks,
- fairness,
- optimization,
- consent,
- reoptimization,
- or execution.

Those decisions remain under deterministic FarmSync logic.

The core scientific experiments require no LLM and no API key.

## Frozen publication evaluation

The final evaluation contains:

- **30 frozen replication seeds**
- **900 planned experiment cells**
- **729 clean/optimal cells**
- **171 recorded non-clean outcomes**

Non-optimal or infeasible outcomes are retained as outcomes of the
experiment. They are not silently repaired, dropped, selectively
rerun, or replaced with zero-valued performance observations.

The frozen experiment families are:

| Family | Cells |
|---|---:|
| PRIMARY | 30 |
| EPSILON_SENSITIVITY | 120 |
| LAMBDA_STABILITY | 180 |
| ALPHA_CONCENTRATION | 150 |
| ACTION_ROBUSTNESS | 90 |
| UNCERTAINTY | 180 |
| SCALABILITY | 150 |
| **Total** | **900** |

## Repository layout

```text
farmsync/                 Core scientific implementation
scripts/                  Reproduction and verification scripts
tests/                    Scientific and application tests
data/farmsync/            Synthetic, processed, and source data
results/farmsync/         Frozen experiment and analysis artifacts
docs/farmsync/            Scientific protocols and audit history
templates/                Research web interface
static/                   Research web assets
```

## Quick start

Validated research environment:

- Python 3.12.8

Create a virtual environment and install the scientific/runtime
dependencies:

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run the core frozen-result verification:

```powershell
python -m pytest -q `
  tests/test_farmsync_final30.py `
  tests/test_farmsync_freeze.py `
  tests/test_farmsync_portability.py
```

Run the standalone research application:

```powershell
python app.py
```

Then open:

```text
http://127.0.0.1:5000/farm-sync
```

## Final30 analysis reproduction

The repository includes:

```text
scripts/analyze_farmsync_final30.py
```

The script reads the sealed Final30 outputs and regenerates analysis
artifacts only under:

```text
results/farmsync/reproduction/
```

It refuses to write inside the frozen raw or analysis directories.

Verify the sealed inputs:

```powershell
python scripts/analyze_farmsync_final30.py --check-inputs
```

Reproduce deterministic seed-level statistics:

```powershell
python scripts/analyze_farmsync_final30.py --seed-level
```

Reproduce deterministic aggregate statistics:

```powershell
python scripts/analyze_farmsync_final30.py --aggregates
```

Reproduce deterministic reliability inference:

```powershell
python scripts/analyze_farmsync_final30.py --deterministic-inference
```

Regenerate bootstrap and paired statistical inference:

```powershell
python scripts/analyze_farmsync_final30.py --stochastic-inference
```

See `REPRODUCIBILITY.md` for the important distinction between exact
historical reproduction and reconstructed bootstrap RNG sequencing.

## Data

The publication experiments use a constructed research dataset with:

- **500 synthetic farmers**
- **911 plots**

FarmSync also contains processed agricultural parameters derived from
documented public data sources.

Third-party raw data is not relicensed by the FarmSync software
licence.

See:

```text
DATA_AND_SOURCES.md
```

for source provenance, transformations, integrity information, and
licence boundaries.

## Results

Frozen results and statistical evidence are available under:

```text
results/farmsync/final30_v1/
results/farmsync/final30_freeze_v1/
results/farmsync/final30_analysis_v1/
results/farmsync/final30_analysis_freeze_v1/
```

See `RESULTS.md` for interpretation rules and the principal result
structure.

## Reproducibility principles

FarmSync preserves:

- fixed publication parameters,
- fixed experiment matrix,
- fixed seeds,
- source hashes,
- dataset attestation,
- solver configuration,
- raw per-cell outcomes,
- immutable result manifests,
- explicit non-optimal outcomes,
- deterministic authority boundaries,
- statistical-analysis provenance.

The repository does not claim exact mathematical global optimality
beyond the status returned by the documented CBC configuration and
tolerance.

## License

FarmSync-authored software is licensed under the
[Apache License 2.0](LICENSE).

Third-party raw data is not relicensed under Apache-2.0 and remains
subject to its upstream terms. See `DATA_AND_SOURCES.md` and `NOTICE`.

The associated manuscript/article is licensed separately under the
applicable Wiley publishing agreement and Creative Commons licence.

## Citation

See:

```text
CITATION.cff
```

## Status

This repository is the standalone research release extracted from the
FarmSync implementation developed and evaluated for the associated
research manuscript.

The frozen publication artifacts must be treated as immutable research
records.
