# Frozen hybrid policy result

The prospectively frozen capacity-aware hybrid policy was evaluated without changing its switch after PR #11.

## Design

The policy uses completed-visits clinical staffing by default and switches to attended-demand clinical staffing when the 90% upper split-conformal bound for completed visits reaches or exceeds known clinic capacity. The realised `capacity_censored` indicator is evaluation-only. Front desk uses scheduled appointments under all policies.

The confirmatory run used the default 12-clinic synthetic network (seed 42), HGB, four 28-day outer folds with 1,095 initial training days, and nested training-only conformal calibration using 730 initial days, four inner folds and 90% coverage.

## Result

Across all clinic-days, the hybrid policy averaged total cost 1,980,398.5 and 1,284.95 unmet visits per outer fold. Completed-visits staffing averaged 1,966,615.3 and 1,416.90 unmet visits. Thus the hybrid costs about 0.70% more than completed-visits staffing while reducing unmet demand by about 9.31%.

Compared with attended-demand staffing, the hybrid is strictly better overall in this run: total cost is about 0.32% lower and unmet demand about 4.59% lower.

On realised capacity-censored days, the hybrid strictly beats both pure policies. Relative to completed-visits staffing it reduces total cost by about 1.01% and unmet visits by about 14.48%. Relative to attended-demand staffing it reduces total cost by about 0.20% and unmet visits by about 2.37%.

On uncensored days, completed-visits staffing remains best: the hybrid costs about 1.13% more and produces about 4.88% more unmet demand. The hybrid therefore improves the cost/service frontier overall but does not dominate completed-visits staffing in every state.

## Switch behaviour

The frozen trigger fires on 29.69% of all evaluated clinic-days. It fires on 83.64% of realised censored days, but also on 24.26% of uncensored days. This is not a perfect censoring classifier and should not be described as one. Its value is operational: without access to future realised censoring, the forecast-time trigger captures enough high-pressure periods to reduce overall unmet demand substantially while avoiding the higher overall cost of always using attended demand.

## Interpretation

The evidence supports the frozen hybrid as the preferred clinical staffing policy among the three tested policies for this synthetic decision problem. It Pareto-dominates the attended-demand-only policy overall and offers a substantial service improvement over completed-visits-only staffing for a modest total-cost increase. The result is conditional on the registered synthetic generator, staffing productivity assumptions and cost coefficients; no real-clinic deployment claim follows from it.
