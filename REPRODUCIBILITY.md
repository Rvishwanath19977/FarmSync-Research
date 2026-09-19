# Reproducibility

## Reproduction levels

FarmSync distinguishes four different reproducibility tasks.

### 1. Verify frozen scientific artifacts

This is the fastest and strongest integrity check.

It verifies that the committed experiment matrix, dataset identities,
raw Final30 cells, freeze manifests, and analysis artifacts have not
changed.

```powershell
python -m pytest -q `
  tests/test_farmsync_final30.py `
  tests/test_farmsync_freeze.py `
  tests/test_farmsync_portability.py
```

### 2. Reproduce the statistical analysis from frozen Final30 cells

The analysis reproduction script is:

```text
scripts/analyze_farmsync_final30.py
```

It reads the immutable raw Final30 results and writes only under:

```text
results/farmsync/reproduction/
```

The script explicitly refuses to write into:

```text
results/farmsync/final30_v1/
results/farmsync/final30_freeze_v1/
results/farmsync/final30_analysis_v1/
results/farmsync/final30_analysis_freeze_v1/
```

Input verification:

```powershell
python scripts/analyze_farmsync_final30.py --check-inputs
```

Seed-level reconstruction:

```powershell
python scripts/analyze_farmsync_final30.py --seed-level
```

Aggregate/reliability reconstruction:

```powershell
python scripts/analyze_farmsync_final30.py --aggregates
```

Wilson intervals and exact McNemar inference:

```powershell
python scripts/analyze_farmsync_final30.py --deterministic-inference
```

Bootstrap and paired inference:

```powershell
python scripts/analyze_farmsync_final30.py --stochastic-inference
```

## Analysis reproduction status

Of the 25 statistical CSV outputs:

- **23 reproduce exactly against the frozen reference**, including:
  - all seven seed-level datasets,
  - descriptive statistics,
  - reliability summaries,
  - solver reliability,
  - Wilson confidence intervals,
  - exact McNemar tests.

Two files contain bootstrap confidence intervals:

```text
bootstrap_confidence_intervals.csv
paired_tests.csv
```

For these two files, the historical analysis records preserve:

- bootstrap replicates: **10,000**
- analysis seed: **20260812**
- percentile 95% confidence intervals
- optimal-only outcome policy
- no zero-imputation of non-optimal outcomes.

However, the original analysis-generator source and its exact random
number generator API/call sequence were not preserved.

The reconstructed implementation therefore uses an explicit,
deterministic NumPy Generator convention.

For `paired_tests.csv`, deterministic quantities including:

- sample identities,
- paired differences,
- means,
- medians,
- Wilcoxon statistics,
- two-sided p-values,
- matched-pairs rank-biserial effects,
- non-zero pair counts

are verified against the frozen historical reference.

The newly regenerated bootstrap interval endpoints are not represented
as byte-identical historical outputs.

The script writes:

```text
RECONSTRUCTION_NOTE.json
```

inside the reproduction output to record this distinction.

## Scientific environment

The frozen analysis runtime records:

```text
Python      3.12.8
NumPy       2.4.1
SciPy       1.18.1
Matplotlib  3.11.2
```

The scientific solver environment uses:

```text
PuLP 3.3.2
CBC  2.10.3
```

The publication solver configuration uses:

```text
gapRel = 1e-6
threads = 0
timeLimit = 120 seconds
```

An `Optimal` solver outcome means CBC returned `Optimal` under this
documented configuration. It is not presented as an independent proof
of exact mathematical global optimality.

## Publication configuration

Frozen publication settings:

```text
epsilon = 0.95
lambda  = 0.05
alpha   = 0.40
```

Protocols:

```text
fairness-v2
action-consent-v1
uncertainty-v1
```

Dataset instance identity:

```text
5ea24037c2d9cb6a
```

Dataset:

```text
500 farmers
911 plots
```

## Non-optimal outcomes

Final30 contains 900 planned cells.

Recorded classification:

```text
729 clean
171 non-clean
```

These outcomes are part of the scientific result.

FarmSync does not:

- silently rerun only failed cells,
- tune parameters after observing Final30,
- convert solver failures to zero-valued outcomes,
- include non-optimal outcomes in optimal-only performance summaries,
- equate baseline PLANNED outcomes with Proposed FINAL_REALIZED outcomes.

Reliability is analysed separately from conditional performance.

## Full experiment rerun

The committed Final30 raw outputs are the authoritative frozen
publication record.

A full solver rerun is computationally more expensive and may exhibit
environment-dependent solver/runtime behaviour.

Users interested only in verifying the publication evidence should use
the frozen-artifact and analysis-reproduction workflows above.

## LLM independence

The Final30 scientific experiments and their statistical reproduction
require no language model.

LLM integration is optional and constrained to interface/parsing and
explanation functions.

The LLM has no authority over optimization, allocation, feasibility,
fairness, consent, locks, or execution.

## Data provenance

See:

```text
DATA_AND_SOURCES.md
data/farmsync/processed/source_manifest.json
data/farmsync/raw_sources/SHA256SUMS.txt
```

for the upstream-data and integrity trail.
