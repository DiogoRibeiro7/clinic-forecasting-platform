# Capacity-target benchmark result

This benchmark compares two fixed-origin recursive global-ML models on identical rolling folds:

1. a model trained on capacity-censored completed visits;
2. a model trained on pre-capacity attended demand.

Both are evaluated against realised attended demand. The design therefore isolates target choice while holding the estimator, folds, horizon and evaluation target fixed.

## Frozen run

- synthetic network: repository default generator, 12 clinics, seed 42;
- estimator: HistGradientBoosting (`hgb`);
- initial training window: 1,095 days;
- forecast horizon: 28 days;
- rolling origins: 4;
- workflow run: `33386367808`;
- evidence artifact: `9755736473`.

The generated machine-readable evidence is committed beside this note in `summary.csv` and `fold_scores.csv`. The workflow artifact also retains the row-level paired predictions and resolved environment.

## Main result

On capacity-censored clinic-days, using attended demand as the training target materially improves forecasting of the demand that staffing is intended to serve:

| Metric, censored days | Attended-demand target | Completed-visits target | Difference |
| --- | ---: | ---: | ---: |
| WAPE | 29.43% | 33.33% | -3.90 pp |
| MAE | 61.33 | 69.41 | -8.08 |
| Mean demand shortfall | 61.15 | 69.41 | -8.26 |
| Bias | -29.26 | -33.33 | +4.07 |
| Underforecast rate | 98.08% | 100.00% | -1.92 pp |

The censored-period WAPE reduction is about 11.7% relative, and mean demand shortfall falls by about 11.9% relative.

Across all clinic-days, point accuracy is essentially tied: WAPE is 24.09% for the attended-demand target versus 24.08% for completed visits. The attended-demand target nevertheless reduces mean shortfall from 13.45 to 12.45 and reduces the underforecast rate from 47.69% to 44.94%.

On uncensored days, completed visits is modestly more accurate as a point target: WAPE is 21.36% versus 22.47% for attended demand. This is expected because, without censoring, the two operational quantities are much closer and the completed-visits target directly matches observed throughput.

## Decision

The evidence does **not** support replacing completed visits as the universal forecasting target. It supports the narrower operational design already implemented:

- clinicians and nurses should be sized from forecast attended demand, because capacity censoring otherwise reproduces the existing ceiling on saturated days;
- front-desk staffing should continue to use scheduled appointments;
- completed visits remains useful as an observed-throughput forecasting and monitoring target.

This is a decision-target result, not evidence that attended-demand forecasting is globally superior. The value appears exactly where the causal concern predicted it should: capacity-censored periods.

## Next gate

Before making the role-specific path the default serving contract, evaluate the staffing-policy consequences directly: compare roster shortfall, overtime/unmet-demand penalties and total cost for completed-visit versus role-specific demand forecasts on held-out folds.
