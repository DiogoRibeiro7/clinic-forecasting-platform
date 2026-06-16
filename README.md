# Clinic Forecasting Platform

[![CI](https://github.com/DiogoRibeiro7/clinic-forecasting-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/DiogoRibeiro7/clinic-forecasting-platform/actions/workflows/ci.yml)

A portfolio-grade proof of concept for forecasting clinic usage and staffing needs across a large healthcare network.

The project simulates a realistic operational setting where multiple clinics have different demand patterns, marketing activity, seasonal effects, no-show behaviour, capacity constraints and staffing rules. The goal is not only to forecast appointment volume, but to translate forecasts into decisions that improve scheduling and resource allocation.

> **Reviewing this project?** Start with
> [`notebooks/10_executive_summary_forecasting_to_staffing.ipynb`](notebooks/10_executive_summary_forecasting_to_staffing.ipynb)
> — the end-to-end story from business problem to costed staffing decisions,
> with every number computed live. Implementation depth lives in notebooks 01-06.

## What this project demonstrates

Forecasting as decision support, not just model fitting — the full path from
raw data to a costed, served staffing decision:

- **Data engineering:** typed data contracts, a configurable synthetic
  generator with realistic difficulty (overdispersion, demand episodes, trend
  changepoints, marketing adstock, capacity censoring).
- **Time-series modelling:** a broad model zoo behind one common forecast
  schema — baselines, per-clinic SARIMAX (with exogenous inputs and automatic
  order selection), Prophet, a leakage-controlled global ML model
  (HistGradientBoosting / XGBoost / LightGBM) with recursive multi-step
  forecasting, the Nixtla ecosystem (StatsForecast, MLForecast,
  NeuralForecast), zero-shot foundation models (TimesFM, Chronos, Lag-Llama)
  and the TimeGPT API — all comparable in one benchmark harness.
- **Correct evaluation:** rolling-origin backtesting and one shared set of
  metrics across every notebook.
- **Uncertainty:** split conformal prediction intervals with per-clinic
  calibration.
- **Decision layer:** forecasts → staffing → money, with cost scenarios and
  conservative interval-based planning.
- **Hierarchical coherence:** clinic / region / network reconciliation.
- **Operational extensions:** no-show forecasting, marketing what-if
  scenarios, drift monitoring with retraining triggers.
- **MLOps without heavy infra:** batch pipeline, local model registry, a
  read-only FastAPI serving layer, CI, Docker and notebook execution checks.
- **Responsible ML:** model card and operational risk register.

## Business problem

Healthcare networks need to decide how many clinicians, nurses and front-desk staff should be available at each clinic. Understaffing creates waiting-time pressure, overtime costs and poor patient experience. Overstaffing wastes budget and leaves capacity idle.

This PoC predicts daily clinic usage for each clinic and then converts demand forecasts into staffing requirements under configurable productivity rules.

## Architecture

```text
                 scripts/generate_data.py
synthetic  ─────────────────────────────────►  data/processed/*.csv
generator        (contracts validate)            (4 contract tables)
                                                        │
                                                        ▼
            ┌─────────────── batch pipeline (scripts/run_batch_forecast.py) ──────────────┐
            │                                                                              │
            │  validate → calibrate conformal intervals → fit global ML →                 │
            │  recursive forecast → staffing plans → register model                       │
            │                                                                              │
            └──────────────────────────────────┬───────────────────────────────────────-─┘
                                                ▼
                       outputs/forecasts/latest.csv   outputs/staffing/latest.csv
                       outputs/model_registry/*.json
                                                │
                                                ▼
                            FastAPI serving layer (read-only)
                   /health  /clinics  /forecasts  /staffing  /scenario/marketing
```

The package mirrors this flow:

```text
src/clinic_forecast/
├── contracts.py      data contracts / schema validation
├── data.py           synthetic network generator
├── features.py       leakage-safe feature engineering
├── metrics.py        forecast metrics (one definition, shared)
├── evaluation.py     grouped metrics, ranking, comparison tables
├── validation.py     RollingOriginSplitter
├── intervals.py      split conformal prediction intervals
├── reconciliation.py hierarchical aggregation + reconciliation
├── staffing.py       rules, costs, scenario comparison
├── scenarios.py      marketing what-if planning
├── noshow.py         no-show / cancellation forecasting
├── monitoring.py     drift + quality alerts
├── registry.py       local model registry
├── benchmark.py      run any set of models head-to-head on shared folds
├── models/           baseline, sarimax, global_ml, optional_prophet,
│                     nixtla_models (Stats/ML/NeuralForecast), lstm,
│                     foundation (TimesFM/Chronos/Lag-Llama), timegpt
├── pipelines/        batch_inference + helpers
└── api/              FastAPI serving layer
```

## Quick start

This project uses Poetry and targets **Python 3.11** (see the Python-version
note under Optional dependencies if you plan to run the Nixtla models).

```bash
poetry env use 3.11
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

- `prophet` for additive trend/seasonality/holiday models.
- `xgboost` and `lightgbm` as alternative global-model estimators.
- `statsforecast`, `mlforecast`, `neuralforecast` — the Nixtla ecosystem
  (AutoARIMA/AutoETS, gradient-boosted MLForecast, NHITS/NBEATS).
- `torch` for the LSTM benchmark.
- `chronos-forecasting` for the Chronos zero-shot foundation model.
- `nixtla` for the TimeGPT API benchmark.

Every optional model is wired behind a guarded import and returns the project's
common forecast schema, so the benchmark harness, evaluation utilities,
prediction intervals and staffing layer consume them with no special-casing.
Notebook 11 runs thirteen installed models — including the Chronos zero-shot
foundation model — in one head-to-head leaderboard.

> **Python version:** use **Python 3.11** (the project supports `>=3.11,<3.13`).
> The numba-based Nixtla packages (`statsforecast`, `mlforecast`) are unstable on
> **Windows + Python 3.12** — statsforecast itself pins an older numba for
> Windows 3.10/3.11 for exactly this reason — and will crash there. On Python
> 3.11 the entire model zoo runs. Several of these packages bundle their own
> OpenMP runtime; `tests/conftest.py` sets `KMP_DUPLICATE_LIB_OK=TRUE` so they
> co-load cleanly. The core PoC never depends on any optional model.

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

## Notebooks

Read in order; start with 10 for the summary. All ship executed with outputs.

| # | Notebook | Focus |
| --- | --- | --- |
| 00 | Business problem and PoC design | Decisions, data entities, evaluation design, scope |
| 01 | Synthetic data generation | Simulation design and why each feature exists |
| 02 | EDA and forecastability | Demand structure → modelling strategy |
| 03 | Statistical models | Baselines, SARIMAX (+ auto order), Prophet |
| 04 | Global ML forecaster | Feature design, fold comparison, importance, intervals, recursive forecasting |
| 05 | Optional benchmarks | LSTM and TimeGPT, gracefully optional |
| 06 | Staffing optimisation | Gaps, conformal upper-bound planning, costs, no-shows |
| 07 | Hierarchical reconciliation | Clinic / region / network coherence |
| 08 | Marketing scenario planning | What-if demand and staffing impact |
| 09 | Monitoring and retraining | Drift alerts and retraining policy |
| 10 | Executive summary | End-to-end story, every number live |
| 11 | Comprehensive model benchmark | 13 models across all families (incl. Chronos foundation) head-to-head on one leaderboard |

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

## Batch pipeline and serving API

Generate forecasts and staffing plans, then serve them locally:

```bash
# 1. Generate the processed contract data
poetry run python scripts/generate_data.py

# 2. Run the batch pipeline (forecasts + conformal intervals + staffing plans)
poetry run python scripts/run_batch_forecast.py --horizon 28

# 3. Start the read-only serving API
poetry run uvicorn clinic_forecast.api.main:app --reload
```

Example requests once the server is running:

```bash
# Service health and artefact availability
curl "http://127.0.0.1:8000/health"

# List clinics
curl "http://127.0.0.1:8000/clinics"

# Forecasts with 90% prediction intervals for one clinic
curl "http://127.0.0.1:8000/forecasts?clinic_id=CLINIC_001&start_date=2026-01-01&end_date=2026-01-14"

# Staffing recommendations (mean and conservative upper-bound plans)
curl "http://127.0.0.1:8000/staffing?clinic_id=CLINIC_001"

# What-if: double planned marketing spend for two clinics
curl -X POST "http://127.0.0.1:8000/scenario/marketing" \
  -H "Content-Type: application/json" \
  -d '{"clinic_ids": ["CLINIC_001", "CLINIC_002"], "spend_multiplier": 2.0}'
```

The API serves the files written by the batch pipeline (`outputs/forecasts/latest.csv`,
`outputs/staffing/latest.csv`); it trains nothing at request time. Missing
artefacts return a 503 with the command to run; unknown clinics return a 404
listing where to find valid ids. Interactive docs are at `http://127.0.0.1:8000/docs`.

## Portfolio positioning

This project is designed to show that forecasting is not just model fitting. It shows the full path from business problem to deployable decision support:

```text
raw clinic data → features → forecasts → staffing recommendations → operational report
```

**Skills demonstrated:** time-series forecasting and validation, panel/global
ML with leakage control, uncertainty quantification (conformal), hierarchical
reconciliation, operational decision modelling and costing, data contracts,
batch pipelines, model registry, drift monitoring, API serving, CI/Docker,
and responsible-ML documentation — all with typed code, tests and executed
notebooks.

## Quality gates

CI (GitHub Actions) runs the same commands available locally, so a green
badge means the repo works from a clean checkout:

| Gate | Local command | What it checks |
| --- | --- | --- |
| Lint | `make lint` (ruff + mypy) | Style, imports, line length; strict typing on `src/` |
| Tests | `make test` | The full pytest suite |
| Notebook smoke | `make notebook-check` | Notebooks 00, 01 and 06 execute end to end after data generation |

## Responsible ML documentation

This project takes forecasting risk in healthcare operations seriously:

- [`reports/model_card.md`](reports/model_card.md) — intended and out-of-scope
  use, data and synthetic-data limitations, evaluation, known failure modes,
  clinic/region-level fairness, the human-review process and retraining
  triggers.
- [`docs/operational_risk.md`](docs/operational_risk.md) — a practical risk
  register (forecast-quality, data, decision-process and governance risks)
  with mitigations, owners and an escalation summary.

## Data note

The included data is synthetic. It is generated to mimic common healthcare-network demand patterns without exposing patient-level data or protected health information.
