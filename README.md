# Clinic Forecasting Platform

[![CI](https://github.com/DiogoRibeiro7/clinic-forecasting-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/DiogoRibeiro7/clinic-forecasting-platform/actions/workflows/ci.yml)

A portfolio-grade proof of concept for **clinic demand forecasting, uncertainty
quantification and staffing decision support** across a healthcare network.

The project goes beyond a forecasting leaderboard. It treats the operational
question as a chain:

```text
validated clinic data
→ fixed-origin forecasts
→ calibrated uncertainty
→ demand-target selection
→ staffing decisions
→ cost / unmet-demand evaluation
→ monitoring and serving
```

All included data are synthetic and contain no patient-level information.

> **Reviewing this project?** Start with the committed decision evidence:
> `reports/evidence/capacity_target_benchmark/`,
> `reports/evidence/staffing_decision_benchmark/`, and
> `reports/evidence/hybrid_policy_benchmark/`. Then use
> [`docs/demo_guide.md`](docs/demo_guide.md) for a 10-minute walkthrough.

## What this project demonstrates

- **Data engineering:** typed contracts and a configurable synthetic generator
  with overdispersion, demand episodes, changepoints, marketing effects and
  capacity censoring.
- **Correct time-series evaluation:** rolling-origin, fixed-origin multi-day
  evaluation. Lag-based global ML forecasts the complete holdout recursively;
  realised targets inside the holdout are never fed back as lag features.
- **Model breadth with a common contract:** baselines, SARIMAX, Prophet, global
  ML, Nixtla models, LSTM, foundation models and TimeGPT, with optional families
  isolated behind guarded imports.
- **Uncertainty quantification:** split-conformal intervals calibrated from the
  same recursive rolling-fold residuals used by deployment-style forecasts.
- **Decision science:** explicit separation between throughput forecasting and
  staffing demand targets, followed by costed policy comparison.
- **Capacity-aware hybrid staffing:** a prospectively frozen rule selects the
  clinical staffing target using only forecast-time information.
- **Role-specific demand:** clinicians/nurses use the selected hybrid clinical
  target; front desk uses scheduled appointments.
- **Hierarchical coherence:** clinic / region / network reconciliation.
- **Operational engineering:** batch pipelines, model registry, descriptive
  hybrid monitoring, FastAPI, CI, Docker and notebook execution checks.
- **Responsible ML:** model card, operational-risk documentation and explicit
  synthetic-data limits.

## Business problem

Healthcare networks need to decide how many clinicians, nurses and front-desk
staff should be available at each clinic. Understaffing creates waiting-time
pressure, overtime and unmet demand; overstaffing wastes budget and leaves
capacity idle.

A subtle problem appears when the observed target is **completed visits**.
Completed visits are capped by clinic capacity in the synthetic generator, so
on busy days they can understate the demand that staffing actually needs to
serve.

The repository therefore separates three quantities:

```text
completed visits        → observed throughput / legacy forecast target
attended demand         → pre-capacity clinical demand
scheduled appointments  → front-desk workload
```

Attended demand is reconstructed as:

```text
scheduled appointments
- no-shows
- same-day cancellations
```

and capacity censoring is identified when attended demand exceeds completed
visits.

## Scientific evidence chain

The target decision was not made from intuition. It was built in three stages.

### 1. Capacity-target benchmark

Completed-visits and attended-demand models were evaluated on identical
fixed-origin folds and scored against realised attended demand.

On realised capacity-censored days, attended-demand forecasting improved WAPE,
MAE, mean shortfall, bias and underforecast rate. On uncensored days,
completed-visits forecasting remained modestly better. The evidence therefore
did **not** support replacing completed visits everywhere.

### 2. Staffing decision benchmark

The next benchmark held the front-desk forecast, staffing rules, roster caps and
cost coefficients fixed and changed only the clinical target.

On censored days, attended-demand staffing reduced both total cost and unmet
demand relative to completed-visits staffing. On uncensored days, the direction
reversed. Again, no pure target dominated globally.

### 3. Prospectively frozen hybrid policy

Before evaluating the hybrid, the switching rule was frozen:

```text
if completed-visits 90% upper conformal bound >= known clinic capacity:
    use attended-demand forecast for clinicians/nurses
else:
    use completed-visits forecast for clinicians/nurses

front desk always uses scheduled appointments
```

The realised `capacity_censored` outcome is **never** an input to the switch.
It is evaluation-only.

Across four outer 28-day folds, the frozen hybrid averaged:

- about **9.31% fewer unmet visits** than completed-visits-only staffing for
  about **0.70% higher total cost**;
- about **0.32% lower total cost** and **4.59% fewer unmet visits** than
  attended-demand-only staffing.

On realised capacity-censored days, the hybrid beat both pure policies. The
trigger is useful but not a perfect classifier: in the confirmatory run it
fired on 83.64% of censored days and 24.26% of uncensored days.

These numbers are conditional on the synthetic generator, staffing productivity
assumptions and cost coefficients. They are **not** real-clinic performance
claims.

## Forecast evaluation contract

The operational planning horizon is a fixed-origin multi-day forecast.
Therefore the primary evaluation asks each model to predict the entire holdout
horizon from one origin.

For lag-based global ML:

```text
train to origin
      ↓
drop future target / outcome columns
      ↓
recursive 28-day forecast
      ↓
score against held-out actuals
```

Teacher-forced predictions that use realised values from inside the test window
are not used in the primary benchmark or conformal calibration. Historical
one-fold teacher-forced global-ML WAPE values are retired.

## Architecture

There are now two explicit serving paths.

```text
                         ┌──────────────── legacy compatibility ────────────────┐
processed data → models → completed-visits batch → outputs/forecasts, staffing │
                         └──────────────────────┬───────────────────────────────┘
                                                │
                                                ▼
                                      unversioned FastAPI

                         ┌──────────────── hybrid decision path ────────────────┐
processed data → three targets → conformal intervals → frozen hybrid switch    │
                         → role-specific staffing → monitoring artefact          │
                         └──────────────────────┬───────────────────────────────┘
                                                │
                                                ▼
                                             /v2 API
```

See [`docs/architecture.md`](docs/architecture.md) for the full data flow.

## Quick start

This project uses Poetry and targets **Python 3.11**.

```bash
poetry env use 3.11
poetry install
poetry run python scripts/generate_data.py
poetry run pytest
```

Run the legacy completed-visits batch path:

```bash
poetry run python scripts/run_batch_forecast.py --horizon 28
```

Run the operational role-specific hybrid path:

```bash
poetry run python scripts/run_role_specific_batch.py --horizon 28
```

Start the API:

```bash
poetry run uvicorn clinic_forecast.api.main:app --reload
```

Interactive docs are available at:

```text
http://127.0.0.1:8000/docs
```

## Serving API

The API deliberately keeps two compatibility surfaces.

### Legacy unversioned contract

These endpoints continue to serve the original completed-visits batch outputs:

```text
GET  /health
GET  /clinics
GET  /forecasts
GET  /staffing
POST /scenario/marketing
```

### Versioned hybrid contract

These endpoints serve the operational role-specific artefacts:

```text
GET /v2/health
GET /v2/forecasts
GET /v2/staffing
GET /v2/hybrid-monitoring
```

`/v2/forecasts` exposes both candidate clinical forecasts and intervals,
scheduled-demand forecasts, known clinic capacity, `capacity_pressure`,
`hybrid_target`, and the selected hybrid clinical forecast. This makes the
staffing decision auditable from the response itself.

The API trains nothing and recomputes no hybrid decision at request time; it
serves immutable batch artefacts. See
[`docs/api_v2_contract.md`](docs/api_v2_contract.md).

## Main package structure

```text
src/clinic_forecast/
├── backtesting.py          fixed-origin recursive evaluation
├── capacity.py             attended/unmet-demand reconstruction
├── capacity_benchmark.py   paired target benchmark
├── decision_benchmark.py   paired staffing-policy benchmark
├── hybrid_policy.py        prospectively frozen switch
├── hybrid_benchmark.py     three-policy confirmatory benchmark
├── hybrid_monitoring.py    descriptive switch-use monitoring
├── contracts.py            data contracts
├── data.py                 synthetic network generator
├── features.py             leakage-safe feature engineering
├── intervals.py            split-conformal intervals
├── metrics.py              shared forecast metrics
├── reconciliation.py       hierarchical reconciliation
├── staffing.py             transparent staffing rules and cost scenarios
├── monitoring.py           drift + quality monitoring
├── registry.py             local model registry
├── role_specific.py        attended/completed/scheduled target forecasts
├── models/                 statistical, ML and optional model families
├── pipelines/
│   ├── batch_inference.py      legacy completed-visits batch path
│   └── role_specific_batch.py  operational hybrid batch path
└── api/main.py             legacy + /v2 read-only serving
```

## Optional dependencies

The core PoC runs without heavy optional dependencies.

```bash
poetry install --with optional
```

Optional tools include Prophet, XGBoost, LightGBM, the Nixtla ecosystem,
PyTorch/LSTM, Chronos and TimeGPT. Optional models return the common forecast
schema, but only models executed under the same fixed-origin multi-fold contract
belong in the primary production-selection comparison.

## Notebooks

| # | Notebook | Focus |
| --- | --- | --- |
| 00 | Business problem and PoC design | Decisions, data entities, evaluation design |
| 01 | Synthetic data generation | Simulation design |
| 02 | EDA and forecastability | Demand structure |
| 03 | Statistical models | Baselines, SARIMAX, Prophet |
| 04 | Global ML forecaster | Features and recursive forecasting |
| 05 | Optional benchmarks | LSTM and TimeGPT |
| 06 | Staffing decision layer | Staffing rules, costs, no-shows |
| 07 | Hierarchical reconciliation | Clinic / region / network coherence |
| 08 | Marketing scenario planning | Predictive what-if analysis |
| 09 | Monitoring and retraining | Drift alerts and retraining policy |
| 10 | Executive summary | Historical end-to-end narrative |
| 11 | Fixed-origin model benchmark | Multi-fold 28-day benchmark |

Notebook 10 predates the final hybrid evidence chain. Where its single-target
staffing story differs from the committed evidence under `reports/evidence/`,
the committed benchmark results are authoritative.

## Metrics

Forecast evaluation reports WAPE, bias, MAE, RMSE, sMAPE and interval coverage.
Decision evaluation adds:

- total cost;
- regular staffing cost;
- overtime cost;
- understaffing cost;
- idle cost;
- unmet visits;
- understaffed-day rate;
- clinician and nurse staff-days.

## Evidence and reproducibility

Committed evidence:

- [`reports/evidence/capacity_target_benchmark/RESULTS.md`](reports/evidence/capacity_target_benchmark/RESULTS.md)
- [`reports/evidence/staffing_decision_benchmark/interpretation.md`](reports/evidence/staffing_decision_benchmark/interpretation.md)
- [`reports/evidence/hybrid_policy_benchmark/RESULT.md`](reports/evidence/hybrid_policy_benchmark/RESULT.md)

The hybrid benchmark was evaluated only after its rule was frozen. Its full
row-level paired decisions remain in the referenced GitHub Actions artefact;
summary and provenance are committed in the repository.

## Quality gates

CI runs:

- Ruff;
- mypy;
- pytest;
- notebook smoke execution;
- capacity-target benchmark evidence regression;
- staffing-decision benchmark evidence regression;
- hybrid-policy benchmark evidence regression.

## Responsible ML documentation

- [`reports/model_card.md`](reports/model_card.md) — intended/out-of-scope use,
  target semantics, confirmatory evidence, limitations and human review.
- [`docs/operational_risk.md`](docs/operational_risk.md) — forecast, data,
  decision-process and governance risks.
- [`docs/evaluation_strategy.md`](docs/evaluation_strategy.md) — fixed-origin
  evaluation and conformal-calibration contract.
- [`docs/hybrid_policy.md`](docs/hybrid_policy.md) — frozen prospective switch.
- [`docs/api_v2_contract.md`](docs/api_v2_contract.md) — versioned serving
  semantics.

## Data note

The included data are synthetic. They mimic common healthcare-network demand
patterns without exposing patient-level data or protected health information.
Absolute accuracy and cost figures demonstrate methodology; they are not claims
about a real healthcare network.

## License

Released under the [MIT License](LICENSE). See the model card and operational
risk register before adapting the project to real operations.
