# FarmSync Final30 reproducibility statement

The final publication evaluation used the frozen 30-seed experiment matrix and produced exactly 900 raw result cells.

## Frozen raw evaluation

- Raw result set: `results/farmsync/final30_v1`
- Raw cells: 900
- Cell-set SHA256: `71f43479f4048f7cf208b819bacb223e2fcb8fd9ff428e8bd36015d30c4de605`
- Source commit: `86129ec71998288db29bf562a7e1b1a9bcc2c9ae`
- Experiment matrix SHA256: `b339a43ab581a0d481da230b84918363bc82f771b993f575c50ea903cdecc0f0`
- Dataset attestation SHA256: `fd42123f24a6823484dc0fa0f5d34192c8c23ea9a03e45d4674e42515bb3514e`
- Solver amendment SHA256: `1d42d59e3c1ba404d13f5c557560e943c222030b1a21ec65094534140cf865b8`
- Development checkpoint SHA256: `207ea314537d0df4aa3ba578dd76d3f4127d63a9917b587bf960ee19f921fc09`

The raw result directory is treated as immutable after sealing.

## Solver

The frozen final evaluation used PuLP/CBC with the prospectively amended relative MIP gap of `1e-6` and a 120-second time limit. The numerical tolerance amendment was made before any Final30 result was generated. The dataset, frozen seeds, RNG streams, epsilon, lambda, alpha, action protocol, uncertainty protocol, fairness definition, and experiment matrix were not changed.

A CBC status of `Optimal` is interpreted under the configured solver tolerance; it is not presented as proof of exact mathematical global optimality.

## Non-Optimal outcomes

Non-Optimal runs were retained rather than replaced, discarded, or rerun under altered scientific settings. Performance summaries use Optimal runs only, while solver/model reliability is reported separately.

Across all 900 cells, 729 were clean/Optimal for the family-specific target and 171 were non-clean. The two epsilon=1.0 B3 `Not Solved` cells reached the frozen 120-second time limit. Other recorded failures are structured infeasibility outcomes at named Proposed pipeline stages.

No zero imputation was used.

## Statistical analysis

- Bootstrap replicates: 10,000
- Bootstrap analysis seed: 20260812
- Confidence interval: percentile 95%
- Paired continuous comparisons: two-sided Wilcoxon signed-rank tests
- Reliability intervals: 95% Wilson intervals
- Paired reliability comparisons: exact McNemar tests implemented through the exact two-sided binomial test on discordant pairs

B1/B2/B3 PLANNED results are not treated as treatment-equivalent to Proposed FINAL_REALIZED outcomes. No direct baseline-PLANNED versus Proposed-FINAL_REALIZED inferential test was performed.

## Analysis runtime

- Python: 3.12.8
- NumPy: 2.4.1
- SciPy: 1.18.1
- Matplotlib: 3.11.2

## LLM boundary

The Final30 scientific evaluation executed no LLM calls. The LLM is restricted to parsing/interface/explanation functions and does not hold authority over feasibility, crop allocation, crop selection, approvals, locks, fairness, optimization, consent, or execution.

All manuscript-facing numerical values, tables, and figures are generated from the sealed Final30 result set and its derived analysis package.
