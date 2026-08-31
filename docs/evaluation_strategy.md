# Evaluation Strategy

Forecasting models are evaluated with rolling-origin backtesting. This mirrors the intended deployment: at each forecast origin, the model sees historical observations and genuinely known future inputs, then predicts the complete future horizon.

## Fixed-origin contract

For a 28-day planning horizon, every primary model must forecast all 28 days from the same origin.

For lag-based global ML, predictions are generated recursively. Realised targets from inside the holdout window are never fed back into lag features during evaluation. Teacher-forced predictions may be useful for a separate sequential one-day-ahead experiment, but they are not comparable with a fixed-origin 28-day staffing forecast and must not be used in the primary leaderboard.

The primary benchmark uses multiple rolling origins. A one-fold leaderboard is insufficient for model selection because month-specific demand episodes can dominate the ranking.

## Why not random train-test split?

Random splits leak future information into training data. For forecasting, validation must preserve temporal order and the information set available at each forecast origin.

## Metrics

- **WAPE** is the primary network-level accuracy metric because it is volume-weighted and remains defined on closure days.
- **Bias** is a co-primary operational diagnostic because under- and over-forecasting have asymmetric staffing consequences.
- **MAE** gives an interpretable average absolute error in visits.
- **RMSE** penalises larger misses.
- **sMAPE** is reported as a scale-normalised secondary metric.
- **MAPE** is descriptive only because zero-visit days make it unsuitable as a primary criterion.

Metrics must be reported across rolling folds and by clinic. Performance by forecast horizon should also be reported for recursive models because error propagation generally increases with horizon.

## Prediction intervals

Split-conformal intervals are calibrated from residuals produced by the **same fixed-origin recursive forecast mechanism used at deployment**. Calibration residuals from teacher-forced predictions are not valid substitutes.

Coverage and interval width should be checked on held-out folds, by clinic and by forecast horizon where sample size permits.

## Model selection

The production estimator is selected only after the corrected multi-fold benchmark has been run. Old one-fold teacher-forced global-ML WAPE values are retired and must not be cited as deployment performance.

## Operational evaluation

The final system is not judged only by forecast accuracy. It should also be evaluated by the decisions the forecasts support:

- Fewer understaffed days.
- Less excess staffing.
- Lower overtime and unmet-demand cost.
- Robustness to interval-based conservative planning.
- Better coordination between planned marketing activity and clinic capacity.

Because completed visits are capacity-censored, future work will separate latent attended demand from observed completed visits before making stronger capacity-planning claims.
