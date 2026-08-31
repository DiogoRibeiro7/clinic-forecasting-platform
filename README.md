# Clinic Forecasting Platform

[![CI](https://github.com/DiogoRibeiro7/clinic-forecasting-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/DiogoRibeiro7/clinic-forecasting-platform/actions/workflows/ci.yml)

A portfolio-grade proof of concept for forecasting clinic usage and staffing needs across a large healthcare network.

The project simulates a realistic operational setting where multiple clinics have different demand patterns, marketing activity, seasonal effects, no-show behaviour, capacity constraints and staffing rules. The goal is not only to forecast appointment volume, but to translate forecasts into decisions that improve scheduling and resource allocation.

> **Reviewing this project?** Start with
> [`notebooks/10_executive_summary_forecasting_to_staffing.ipynb`](notebooks/10_executive_summary_forecasting_to_staffing.ipynb)
> — the end-to-end story from business problem to costed staffing decisions.
> For model-selection evidence, use notebook 11, which implements the corrected
> fixed-origin multi-fold evaluation contract described below.

## What this project demonstrates

Forecasting as decision support, not just model fitting — the full path from
raw data to a costed staffing decision:

- **Data engineering:** typed data contracts, a configurable synthetic
  generator with realistic difficulty (overdispersion, demand episodes, trend
  changepoints, marketing adstock, capacity censoring).
- **Time-series modelling:** a broad model zoo behind one common forecast
  schema — baselines, per-clinic SARIMAX (with exogenous inputs and automatic
  order selection), Prophet, global ML (HistGradientBoosting / XGBoost /
  LightGBM), the Nixtla ecosystem, LSTM, foundation models and TimeGPT.
- **Correct evaluation:** rolling-origin, fixed-origin backtesting. Lag-based
  global ML forecasts the complete holdout horizon recursively; realised
  targets inside the holdout are never fed back into lag features.
- **Uncertainty:** split-conformal prediction intervals calibrated from the
  same recursive rolling-fold residuals used by the deployment forecast path.
- **Decision layer:** forecasts → staffing → money, with transparent staffing
  rules, cost scenarios and conservative interval-based planning.
- **Hierarchical coherence:** clinic / region / network reconciliation.
- **Operational extensions:** no-show forecasting, marketing what-if
  scenarios, drift monitoring with retraining triggers.
- **MLOps without heavy infra:** batch pipeline, local model registry, a
  read-only FastAPI serving layer, CI, Docker and notebook execution checks.
- **Responsible ML:** model card and operational risk register.

## Business problem

Healthcare networks need to decide how many clinicians, nurses and front-desk staff should be available at each clinic. Understaffing creates waiting-time pressure, overtime costs and poor patient experience. Overstaffing wastes budget and leaves capacity idle.

This PoC predicts daily clinic usage for each clinic and converts demand forecasts into staffing requirements under configurable productivity rules. Completed visits are capacity-censored in the synthetic generator, so stronger capacity-planning claims require a future separation between latent attended demand and observed completed visits; that work is explicit in the roadmap rather than hidden behind the model.

## Forecast evaluation contract

The operational planning horizon is a fixed-origin multi-day forecast. Therefore the primary evaluation asks each model to predict the entire holdout horizon from one origin.

For lag-based global ML:

```text
train to origin
      ↓
drop future target/outcome columns
      ↓
recursive 28-day forecast
      ↓
score against held-out actuals
```

Teacher-forced predictions that use realised values from inside the test window are not used in the primary benchmark or conformal calibration. The earlier one-fold teacher-forced global-ML leaderboard is retired and should not be cited as deployment performance.

Notebook 11 uses multiple 28-day rolling origins for the primary comparison. Optional deep-learning, foundation and API models remain supplementary until they are run through the same fixed-origin contract.

## Architecture

```text
                 scripts/generate_data.py
synthetic  ─────────────────────────────────►  data/processed/*.csv
generator        (contracts validate)            (4 contract tables)
                                                        │
                                                        ▼
            ┌─────────────── batch pipeline (scripts/run_batch_forecast.py) ──────────────┐
            │                                                                              │
            │  validate → recursive rolling calibration → fit global ML →                 │
            │  recursive forecast → intervals → staffing plans → register model           │
            │                                                                              │
            └──────────────────────────────────┬───────────────────────────────────────────┘
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
├── backtesting.py    fixed-origin recursive evaluation adapters
├── contracts.py      data contracts / schema validation
├── data.py           synthetic network generator
├── features.py       leakage-safe feature engineering
├── metrics.py        forecast metrics (one definition, shared)
├── evaluation.py     grouped metrics, ranking, comparison tables
├── validation.py     RollingOriginSplitter
├── intervals.py      split conformal prediction intervals
├── reconciliation.py hierarchical aggregation + reconciliation
├── staffing.py       transparent staffing rules and cost scenarios
├── scenarios.py      marketing what-if planning
├── noshow.py         no-show / cancellation forecasting
├── monitoring.py     drift + quality alerts
├── registry.py       local model registry
├── benchmark.py      run models head-to-head on shared folds
├── models/           baseline, sarimax, global_ml, optional_prophet,
│                     nixtla_models, lstm, foundation, timegpt
├── pipelines/        batch_inference + helpers
└── api/              FastAPI serving layer
```

## Quick start

This project uses Poetry and targets **Python 3.11**.

```bash
poetry env use 3.11
poetry install
poetry run python scripts/generate_data.py
poetry run python scripts/run_poc.py
poetry run pytest
```

Run the production-shaped batch path:

```bash
poetry run python scripts/run_batch_forecast.py --horizon 28
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
- `statsforecast`, `mlforecast`, `neuralforecast` — the Nixtla ecosystem.
- `torch` for the LSTM benchmark.
- `chronos-forecasting` for the Chronos zero-shot foundation model.
- `nixtla` for the TimeGPT API benchmark.

Every optional model is wired behind a guarded import and returns the project's common forecast schema. The primary leaderboard is intentionally narrower than the historical 13-model exploratory run: only models executed under the same fixed-origin, multi-fold contract belong in the production-selection comparison. Heavy optional families can be added to that harness without changing the metric or fold definitions.

> **Python version:** use **Python 3.11** (the project supports `>=3.11,<3.13`).
> The numba-based Nixtla packages (`statsforecast`, `mlforecast`) are unstable on
> **Windows + Python 3.12**. The core PoC never depends on optional models.

## Main modelling idea

The project treats clinic demand as a panel of related time series:

```text
clinic_id × date → visits
```

The models use:

- Calendar features.
- Clinic metadata.
- Planned marketing spend and campaign indicators.
- Lagged demand.
- Rolling-window statistics.
- Capacity and specialty mix.

Same-day operational outcomes such as no-shows, cancellations and utilisation are explicitly excluded from the visit-forecast feature set.

## Notebooks

Read in order; start with 10 for the end-to-end summary and 11 for model-selection evidence.

| # | Notebook | Focus |
| --- | --- | --- |
| 00 | Business problem and PoC design | Decisions, data entities, evaluation design, scope |
| 01 | Synthetic data generation | Simulation design and why each feature exists |
| 02 | EDA and forecastability | Demand structure → modelling strategy |
| 03 | Statistical models | Baselines, SARIMAX (+ auto order), Prophet |
| 04 | Global ML forecaster | Feature design, importance, recursive forecasting |
| 05 | Optional benchmarks | LSTM and TimeGPT, gracefully optional |
| 06 | Staffing decision layer | Gaps, conformal upper-bound planning, costs, no-shows |
| 07 | Hierarchical reconciliation | Clinic / region / network coherence |
| 08 | Marketing scenario planning | Predictive what-if demand and staffing impact, explicitly non-causal |
| 09 | Monitoring and retraining | Drift alerts and retraining policy |
| 10 | Executive summary | End-to-end forecasting-to-staffing story |
| 11 | Fixed-origin model benchmark | Multi-fold 28-day primary benchmark with recursive global ML |

The historical one-fold teacher-forced outputs formerly stored in notebook 11 were removed rather than relabelled. New benchmark numbers must be regenerated under the corrected contract.

## Forecasting metrics

The repository reports:

- WAPE — primary network-level accuracy metric.
- Bias — primary operational direction-of-error diagnostic.
- MAE.
- RMSE.
- sMAPE.
- MAPE as a descriptive secondary metric only.
- Coverage and interval width when prediction intervals are available.

Metrics should be read across rolling folds and by clinic. Performance by forecast horizon is a planned extension because recursive error generally grows with horizon.

## Batch pipeline and serving API

Generate forecasts and staffing plans, then serve them locally:

```bash
# 1. Generate the processed contract data
poetry run python scripts/generate_data.py

# 2. Run the batch pipeline
poetry run python scripts/run_batch_forecast.py --horizon 28

# 3. Start the read-only serving API
poetry run uvicorn clinic_forecast.api.main:app --reload
```

Example requests once the server is running:

```bash
curl "http://127.0.0.1:8000/health"
curl "http://127.0.0.1:8000/clinics"
curl "http://127.0.0.1:8000/forecasts?clinic_id=CLINIC_001&start_date=2026-01-01&end_date=2026-01-14"
curl "http://127.0.0.1:8000/staffing?clinic_id=CLINIC_001"
```

The API serves the files written by the batch pipeline (`outputs/forecasts/latest.csv`, `outputs/staffing/latest.csv`); it trains nothing at request time. Missing artefacts return a 503 and unknown clinics return a 404. Interactive docs are at `http://127.0.0.1:8000/docs`.

## Portfolio positioning

This project is designed to show that forecasting is not just model fitting. It shows the path from business problem to deployable decision support:

```text
raw clinic data → validated features → fixed-origin forecasts → uncertainty → staffing recommendations → operational report
```

**Skills demonstrated:** time-series forecasting and temporal validation, panel/global ML with leakage control, uncertainty quantification, hierarchical reconciliation, operational decision modelling and costing, data contracts, batch pipelines, model registry, drift monitoring, API serving, CI/Docker, and responsible-ML documentation.

## Quality gates

CI runs the same commands available locally:

| Gate | Local command | What it checks |
| --- | --- | --- |
| Lint | `make lint` (ruff + mypy) | Style, imports and typing on `src/` |
| Tests | `make test` | The full pytest suite |
| Notebook smoke | `make notebook-check` | Notebooks 00, 01 and 06 execute after data generation |

Heavy optional models are tested at the wrapper/schema level in normal CI. A scheduled/manual integration workflow that installs the complete optional stack is listed in the roadmap.

## Responsible ML documentation

- [`reports/model_card.md`](reports/model_card.md) — intended and out-of-scope use, synthetic-data limitations, evaluation, failure modes and human review.
- [`docs/operational_risk.md`](docs/operational_risk.md) — forecast, data, decision-process and governance risks with mitigations and owners.
- [`docs/evaluation_strategy.md`](docs/evaluation_strategy.md) — the fixed-origin evaluation and conformal-calibration contract.

## Data note

The included data is synthetic. It is generated to mimic common healthcare-network demand patterns without exposing patient-level data or protected health information. Absolute accuracy and cost figures are demonstrations of method, not claims about a real healthcare network.

## License

Released under the [MIT License](LICENSE) — free to use, modify and distribute with attribution. This is a proof of concept on synthetic data; see [`reports/model_card.md`](reports/model_card.md) before adapting it to real operations.
