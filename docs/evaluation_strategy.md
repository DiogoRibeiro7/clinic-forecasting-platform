# Evaluation Strategy

Forecasting models are evaluated with rolling-origin backtesting. This mirrors a real deployment where a model is trained on historical data and predicts a future horizon.

## Why not random train-test split?

Random splits leak future information into training data. For forecasting, validation must preserve temporal order.

## Metrics

- **MAE** gives an interpretable average absolute error in visits.
- **RMSE** penalises larger misses.
- **WAPE** is useful for comparing across clinics with different volume levels.
- **Bias** shows systematic over-forecasting or under-forecasting.
- **sMAPE** is more stable than MAPE when actual volume is low.

## Operational evaluation

The final system should not be judged only by forecast accuracy. It should also be judged by staffing impact:

- Fewer understaffed days.
- Less excess staffing.
- Lower overtime risk.
- Better matching between marketing campaigns and clinic capacity.
