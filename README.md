# Clinic Forecasting Platform

A portfolio-grade proof of concept for forecasting clinic usage and staffing needs across a large healthcare network.

The project simulates a realistic operational setting where multiple clinics have different demand patterns, marketing activity, seasonal effects, no-show behaviour, capacity constraints and staffing rules. The goal is not only to forecast appointment volume, but to translate forecasts into decisions that improve scheduling and resource allocation.

## What this project demonstrates

- Time-series forecasting for healthcare operations.
- Multi-clinic demand modelling with exogenous variables.
- Forecast validation with rolling-origin backtesting.
- Statistical forecasting with naive, seasonal naive, moving average and SARIMAX models.
- Machine-learning forecasting using lag features and a global multi-clinic model.
- Optional Prophet, XGBoost, LSTM and TimeGPT integrations.
- Decision-layer logic for converting forecasted demand into staffing recommendations.
- A clean Python package structure with tests, notebooks, scripts and API stubs.

## Business problem

Healthcare networks need to decide how many clinicians, nurses and front-desk staff should be available at each clinic. Understaffing creates waiting-time pressure, overtime costs and poor patient experience. Overstaffing wastes budget and leaves capacity idle.

This PoC predicts daily clinic usage for each clinic and then converts demand forecasts into staffing requirements under configurable productivity rules.

## Repository layout

```text
clinic-forecasting-platform/
├── notebooks/
│   ├── 00_business_problem_and_poc_design.ipynb
│   ├── 01_synthetic_healthcare_data_generation.ipynb
│   ├── 02_eda_and_forecasting_validation.ipynb
│   ├── 03_statistical_models_sarimax_prophet.ipynb
│   ├── 04_global_ml_forecaster_xgboost_style.ipynb
│   ├── 05_lstm_timegpt_optional_foundation_models.ipynb
│   └── 06_staffing_optimization_and_decision_layer.ipynb
├── src/clinic_forecast/
│   ├── data.py
│   ├── features.py
│   ├── metrics.py
│   ├── validation.py
│   ├── staffing.py
│   ├── visualization.py
│   ├── models/
│   ├── pipelines/
│   └── api/
├── scripts/
├── tests/
├── docs/
├── reports/
└── pyproject.toml
```

## Quick start

This project uses Poetry.

```bash
poetry install
poetry run python scripts/generate_data.py
poetry run python scripts/run_poc.py
poetry run pytest
```

Open the notebooks after generating the data:

```bash
poetry run jupyter lab notebooks/
```

## Optional dependencies

The core PoC runs without heavy optional dependencies. Optional integrations are isolated so the repository remains easy to run in interviews or technical reviews.

```bash
poetry install --with optional
```

Optional tools include:

- `prophet` for additive models with seasonality and holiday effects.
- `xgboost` for gradient-boosted forecasting.
- `torch` for the LSTM notebook.
- `nixtla` for TimeGPT API-based forecasts.

## Main modelling idea

The project treats clinic demand as a panel of related time series:

```text
clinic_id × date → visits
```

The models use:

- Calendar features.
- Clinic metadata.
- Marketing spend and campaign indicators.
- Lagged demand.
- Rolling-window statistics.
- Capacity and specialty mix.

## Expected PoC workflow

1. Generate realistic synthetic clinic and marketing data.
2. Explore demand, seasonality, capacity pressure and marketing effects.
3. Build baseline models.
4. Compare SARIMAX, Prophet and global ML models.
5. Optionally test LSTM or TimeGPT.
6. Convert forecasts into staffing requirements.
7. Report model accuracy and operational impact.

## Forecasting metrics

The repository reports:

- MAE.
- RMSE.
- MAPE.
- sMAPE.
- WAPE.
- Bias.
- Coverage when prediction intervals are available.

For operations, WAPE and bias are often more useful than MAPE because clinic volume can be low for some sites.

## Portfolio positioning

This project is designed to show that forecasting is not just model fitting. It shows the full path from business problem to deployable decision support:

```text
raw clinic data → features → forecasts → staffing recommendations → operational report
```

## Data note

The included data is synthetic. It is generated to mimic common healthcare-network demand patterns without exposing patient-level data or protected health information.
