# Results

## Frozen Final30 evaluation

The FarmSync publication evaluation contains 900 pre-specified
experiment cells across seven experiment families.

| Family | Planned cells |
|---|---:|
| PRIMARY | 30 |
| EPSILON_SENSITIVITY | 120 |
| LAMBDA_STABILITY | 180 |
| ALPHA_CONCENTRATION | 150 |
| ACTION_ROBUSTNESS | 90 |
| UNCERTAINTY | 180 |
| SCALABILITY | 150 |
| **Total** | **900** |

Final recorded integrity classification:

```text
729 clean
171 non-clean
```

The non-clean cells are retained as reliability outcomes.

They are not converted to performance observations.

## Primary experiment

The PRIMARY experiment compares:

```text
B1 — individual profit
B2 — collective market-aware
B3 — fairness-aware collective
Proposed — farmer-in-the-loop dynamic reoptimization
```

Baseline B1/B2/B3 values are PLANNED allocation outcomes.

Proposed is evaluated across multiple states:

```text
PLANNED
INITIAL_REALIZED
RECOMMENDED_REVISED
FINAL_REALIZED
```

These states are intentionally distinct.

A baseline PLANNED value must not be interpreted as equivalent to a
Proposed FINAL_REALIZED value.

## Reliability

For the PRIMARY Proposed workflow:

```text
26 / 30 runs were optimal/clean
4 / 30 were non-optimal
```

Performance summaries for Proposed use the optimal runs only.

Reliability is reported independently.

The analysis includes Wilson 95% confidence intervals for optimal-run
rates and exact paired McNemar tests for selected reliability
comparisons.

## Statistical inference

The frozen analysis includes:

- descriptive statistics,
- 10,000-resample bootstrap confidence intervals,
- two-sided paired Wilcoxon signed-rank tests,
- matched-pairs rank-biserial effects,
- Wilson confidence intervals for reliability,
- exact McNemar tests for paired reliability outcomes.

Bootstrap analysis seed:

```text
20260812
```

No non-optimal result is zero-imputed into performance statistics.

## Sensitivity analyses

### Fairness threshold

The epsilon experiment evaluates B3 across the frozen epsilon grid.

Its purpose is to expose the relationship between fairness constraints
and economic outcomes rather than to retune epsilon after Final30.

The publication configuration remains:

```text
epsilon = 0.95
```

### Disruption penalty

The lambda experiment evaluates Proposed stability across:

```text
0.00
0.05
0.10
0.25
0.50
1.00
```

The publication configuration remains:

```text
lambda = 0.05
```

### Concentration control

The alpha experiment evaluates:

```text
1.00
0.60
0.50
0.40
0.33
```

The publication configuration remains:

```text
alpha = 0.40
```

## Action robustness

Action robustness evaluates:

```text
PRIMARY
S1
S2
```

as pre-specified behavioural profiles.

The behavioural probabilities are experimental scenario parameters,
not empirical estimates of farmer behaviour.

## Uncertainty

The frozen uncertainty conditions are:

```text
U0 — reference
UW — weather
UM — market
UR — resource
UP — participation
UJ — joint
```

The same seed-level stochastic realization is used consistently across
the compared methods for each condition.

Uncertainty parameters marked synthetic/experimental are not presented
as observed empirical distributions.

## Scalability

Scalability experiments evaluate:

```text
25
50
100
250
500
```

farmers.

Reliability and runtime are both reported because feasibility rates
change materially across problem sizes.

A failed/non-optimal run is not assigned zero economic performance.

## Figures

The frozen analysis contains ten publication figures covering:

1. Primary workflow cash
2. Uncertainty final cash
3. Epsilon / B3 cash
4. Lambda / final cash
5. Lambda / disruption
6. Alpha / final cash
7. Alpha / maximum LPS
8. Action robustness / final cash
9. Scalability / optimal rate
10. Scalability / Proposed pipeline runtime

Both PNG and PDF versions are retained in the frozen analysis artifact.

## Authoritative result locations

Raw Final30 results:

```text
results/farmsync/final30_v1/
```

Raw-result freeze:

```text
results/farmsync/final30_freeze_v1/
```

Statistical analysis:

```text
results/farmsync/final30_analysis_v1/
```

Analysis freeze:

```text
results/farmsync/final30_analysis_freeze_v1/
```

The freeze manifests and SHA-256 records are the authoritative
integrity references.

## Interpretation boundary

FarmSync is evaluated on a constructed/synthetic farmer population with
source-grounded agricultural parameters and explicit experimental
uncertainty assumptions.

The results demonstrate the behaviour of the specified computational
framework under the frozen experimental design.

They should not be interpreted as direct causal estimates of real-world
farmer behaviour, market response, or agricultural policy effects.
