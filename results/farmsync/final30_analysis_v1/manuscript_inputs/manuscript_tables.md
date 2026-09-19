## Table 1. Primary results

| Method | State | n | Mean cash | SD | Median | Min | Max | Scope |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B1 | PLANNED | 30 | 14,729,243 | 1,631,754 | 14,581,457 | 11,907,597 | 17,924,836 | all_30_primary_seeds |
| B2 | PLANNED | 30 | 14,006,372 | 1,503,411 | 13,816,292 | 11,907,597 | 17,152,116 | all_30_primary_seeds |
| B3 | PLANNED | 30 | 13,314,896 | 1,432,426 | 13,126,546 | 11,317,399 | 16,331,308 | all_30_primary_seeds |
| PROPOSED | PLANNED | 26 | 13,361,874 | 1,430,751 | 13,126,546 | 11,317,399 | 16,331,308 | optimal_proposed_only |
| PROPOSED | INITIAL_REALIZED | 26 | 10,880,986 | 1,022,609 | 10,711,398 | 9,187,238 | 12,797,649 | optimal_proposed_only |
| PROPOSED | RECOMMENDED_REVISED | 26 | 12,207,737 | 1,344,681 | 11,666,591 | 10,096,135 | 14,603,372 | optimal_proposed_only |
| PROPOSED | FINAL_REALIZED | 26 | 11,961,110 | 1,267,604 | 11,517,926 | 9,866,936 | 14,341,497 | optimal_proposed_only |

*Note: B1/B2/B3 are PLANNED-state results across all 30 seeds. Proposed outcome tiers use the 26 Optimal PRIMARY runs only. Baseline PLANNED and Proposed FINAL_REALIZED are not equivalent treatment states.*

## Table 2. Uncertainty results

| Condition | Optimal n | Mean FINAL_REALIZED cash | SD | Median | Optimal runs | Optimal rate |
| --- | --- | --- | --- | --- | --- | --- |
| U0 | 26 | 11,961,110 | 1,267,604 | 11,517,926 | 26/30 | 86.7% |
| UW | 27 | 12,001,991 | 1,461,119 | 11,532,198 | 27/30 | 90.0% |
| UM | 24 | 12,456,424 | 1,560,231 | 12,373,078 | 24/30 | 80.0% |
| UR | 26 | 11,487,320 | 1,315,439 | 11,096,086 | 26/30 | 86.7% |
| UP | 25 | 10,582,058 | 1,346,386 | 10,460,735 | 25/30 | 83.3% |
| UJ | 25 | 10,232,449 | 1,469,771 | 10,457,864 | 25/30 | 83.3% |

*Note: Performance summaries are Optimal-only. Feasibility/reliability is reported separately rather than using zero imputation.*

## Table 3. Epsilon sensitivity

| Epsilon | Optimal n | Mean B3 cash | SD | Median | Optimal runs | Optimal rate |
| --- | --- | --- | --- | --- | --- | --- |
| 0.8 | 30 | 11,448,508 | 1,188,216 | 11,380,600 | 30/30 | 100.0% |
| 0.9 | 30 | 12,645,854 | 1,360,385 | 12,444,699 | 30/30 | 100.0% |
| 0.95 | 30 | 13,314,896 | 1,432,426 | 13,126,546 | 30/30 | 100.0% |
| 1.0 | 28 | 14,096,828 | 1,501,021 | 13,833,835 | 28/30 | 93.3% |

*Note: At epsilon=1.0, two B3 solves reached the frozen 120-second limit and were recorded as Not Solved.*

## Table 4. Lambda stability

| Lambda | Optimal n | Mean FINAL_REALIZED cash | SD | Mean disruption rate | Optimal runs | Optimal rate |
| --- | --- | --- | --- | --- | --- | --- |
| 0.0 | 26 | 11,967,156 | 1,261,431 | 0.0615 | 26/30 | 86.7% |
| 0.05 | 26 | 11,961,110 | 1,267,604 | 0.0222 | 26/30 | 86.7% |
| 0.1 | 26 | 11,958,881 | 1,267,597 | 0.0207 | 26/30 | 86.7% |
| 0.25 | 26 | 11,931,894 | 1,255,548 | 0.0072 | 26/30 | 86.7% |
| 0.5 | 26 | 11,931,721 | 1,250,842 | 0.0052 | 26/30 | 86.7% |
| 1.0 | 26 | 11,893,126 | 1,258,584 | 0.0003 | 26/30 | 86.7% |

*Note: Lambda=0.05 is the frozen publication configuration.*

## Table 5. Alpha concentration

| Alpha | Optimal n | Mean FINAL_REALIZED cash | SD | Mean max LPS | Optimal runs | Optimal rate |
| --- | --- | --- | --- | --- | --- | --- |
| 1.0 | 26 | 12,004,787 | 1,258,918 | 0.6698 | 26/30 | 86.7% |
| 0.6 | 26 | 11,994,024 | 1,269,254 | 0.4514 | 26/30 | 86.7% |
| 0.5 | 26 | 11,976,083 | 1,261,284 | 0.3819 | 26/30 | 86.7% |
| 0.4 | 26 | 11,961,110 | 1,267,604 | 0.3412 | 26/30 | 86.7% |
| 0.33 | 26 | 11,922,934 | 1,255,702 | 0.2844 | 26/30 | 86.7% |

*Note: Alpha=0.40 is the frozen publication configuration.*

## Table 6. Action robustness

| Profile | Optimal n | Mean FINAL_REALIZED cash | SD | Mean FINAL/PLANNED ratio | Optimal runs | Optimal rate |
| --- | --- | --- | --- | --- | --- | --- |
| PRIMARY | 26 | 11,961,110 | 1,267,604 | 0.8960 | 26/30 | 86.7% |
| S1 | 27 | 10,536,838 | 1,215,183 | 0.7939 | 27/30 | 90.0% |
| S2 | 25 | 12,811,318 | 1,420,469 | 0.9625 | 25/30 | 83.3% |

*Note: PRIMARY is the frozen action profile; S1 and S2 are predeclared robustness profiles.*

## Table 7. Scalability

| Farmers | Optimal n | Mean FINAL_REALIZED cash | SD | Mean pipeline runtime (s) | Optimal runs | Optimal rate |
| --- | --- | --- | --- | --- | --- | --- |
| 25 | 2 | 130,592 | 104,389 | 0.85 | 2/30 | 6.7% |
| 50 | 4 | 961,867 | 156,223 | 1.43 | 4/30 | 13.3% |
| 100 | 10 | 1,781,019 | 643,535 | 2.72 | 10/30 | 33.3% |
| 250 | 26 | 5,650,057 | 912,135 | 12.28 | 26/30 | 86.7% |
| 500 | 26 | 11,961,110 | 1,267,604 | 16.47 | 26/30 | 86.7% |

*Note: FINAL_REALIZED performance is summarized only over Optimal Proposed runs. Runtime uses all attempts. Small-population feasibility is a major observed limitation.*

## Table 8. Solver reliability

| Family | Parameter | Optimal runs | Optimal rate | 95% Wilson CI |
| --- | --- | --- | --- | --- |
| PRIMARY | publication_config | 26/30 | 86.67% | 70.32%?94.69% |
| UNCERTAINTY | U0 | 26/30 | 86.67% | 70.32%?94.69% |
| UNCERTAINTY | UW | 27/30 | 90.00% | 74.38%?96.54% |
| UNCERTAINTY | UM | 24/30 | 80.00% | 62.69%?90.49% |
| UNCERTAINTY | UR | 26/30 | 86.67% | 70.32%?94.69% |
| UNCERTAINTY | UP | 25/30 | 83.33% | 66.44%?92.66% |
| UNCERTAINTY | UJ | 25/30 | 83.33% | 66.44%?92.66% |
| EPSILON_SENSITIVITY | epsilon=0.8 | 30/30 | 100.00% | 88.65%?100.00% |
| EPSILON_SENSITIVITY | epsilon=0.9 | 30/30 | 100.00% | 88.65%?100.00% |
| EPSILON_SENSITIVITY | epsilon=0.95 | 30/30 | 100.00% | 88.65%?100.00% |
| EPSILON_SENSITIVITY | epsilon=1.0 | 28/30 | 93.33% | 78.68%?98.15% |
| LAMBDA_STABILITY | lambda=0.0 | 26/30 | 86.67% | 70.32%?94.69% |
| LAMBDA_STABILITY | lambda=0.05 | 26/30 | 86.67% | 70.32%?94.69% |
| LAMBDA_STABILITY | lambda=0.1 | 26/30 | 86.67% | 70.32%?94.69% |
| LAMBDA_STABILITY | lambda=0.25 | 26/30 | 86.67% | 70.32%?94.69% |
| LAMBDA_STABILITY | lambda=0.5 | 26/30 | 86.67% | 70.32%?94.69% |
| LAMBDA_STABILITY | lambda=1.0 | 26/30 | 86.67% | 70.32%?94.69% |
| ALPHA_CONCENTRATION | alpha=1.0 | 26/30 | 86.67% | 70.32%?94.69% |
| ALPHA_CONCENTRATION | alpha=0.6 | 26/30 | 86.67% | 70.32%?94.69% |
| ALPHA_CONCENTRATION | alpha=0.5 | 26/30 | 86.67% | 70.32%?94.69% |
| ALPHA_CONCENTRATION | alpha=0.4 | 26/30 | 86.67% | 70.32%?94.69% |
| ALPHA_CONCENTRATION | alpha=0.33 | 26/30 | 86.67% | 70.32%?94.69% |
| ACTION_ROBUSTNESS | PRIMARY | 26/30 | 86.67% | 70.32%?94.69% |
| ACTION_ROBUSTNESS | S1 | 27/30 | 90.00% | 74.38%?96.54% |
| ACTION_ROBUSTNESS | S2 | 25/30 | 83.33% | 66.44%?92.66% |
| SCALABILITY | n=25 | 2/30 | 6.67% | 1.85%?21.32% |
| SCALABILITY | n=50 | 4/30 | 13.33% | 5.31%?29.68% |
| SCALABILITY | n=100 | 10/30 | 33.33% | 19.23%?51.22% |
| SCALABILITY | n=250 | 26/30 | 86.67% | 70.32%?94.69% |
| SCALABILITY | n=500 | 26/30 | 86.67% | 70.32%?94.69% |

*Note: Non-Optimal outcomes are retained and reported; no zero imputation was used.*

## Table 9. Paired statistical tests

| Comparison | n | Mean A-B | Bootstrap 95% CI | Median A-B | Wilcoxon p | Rank-biserial |
| --- | --- | --- | --- | --- | --- | --- |
| B1_PLANNED_vs_B2_PLANNED | 30 | 722,872 | 507,334 to 949,733 | 565,800 | <0.001 | 1.000 |
| B2_PLANNED_vs_B3_PLANNED | 30 | 691,476 | 666,766 to 717,468 | 689,689 | <0.001 | 1.000 |
| B1_PLANNED_vs_B3_PLANNED | 30 | 1,414,347 | 1,198,786 to 1,644,409 | 1,287,436 | <0.001 | 1.000 |
| PROPOSED_INITIAL_vs_PLANNED | 26 | -2,480,887 | -2,758,578 to -2,221,360 | -2,352,482 | <0.001 | -1.000 |
| PROPOSED_REVISED_vs_INITIAL | 26 | 1,326,750 | 1,153,575 to 1,508,823 | 1,190,688 | <0.001 | 1.000 |
| PROPOSED_FINAL_vs_REVISED | 26 | -246,626 | -345,405 to -168,244 | -155,018 | <0.001 | -1.000 |
| PROPOSED_FINAL_vs_PLANNED | 26 | -1,400,763 | -1,616,486 to -1,184,650 | -1,361,016 | <0.001 | -1.000 |

*Note: No B1/B2/B3 PLANNED versus Proposed FINAL_REALIZED test is performed because those states are not treatment-equivalent.*
