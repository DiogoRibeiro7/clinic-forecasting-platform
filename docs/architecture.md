# Architecture

The PoC is local-first and file-backed: plain CSV in, plain CSV out, no
database or services required. It is structured so each piece could be lifted
into a production pipeline unchanged.

## Data flow

```text
Synthetic generator (data.py)
        │   scripts/generate_data.py  +  contracts.py (validate)
        ▼
data/processed/  ── clinic_daily_usage, clinic_metadata, marketing_daily, staffing_daily
        │
        ▼
Feature pipeline (features.py)         leakage-safe lags / rolling / expanding / marketing
        │
        ▼
Models (models/)                       baseline · SARIMAX(+auto) · global ML · LSTM* · TimeGPT* · Prophet*
        │
        ▼
Evaluation (evaluation.py, validation.py, metrics.py)   rolling-origin folds, shared metrics
        │
        ▼
Uncertainty (intervals.py)             split conformal, per-clinic calibration
        │
        ▼
Decision layer (staffing.py)           rules → costs → scenarios; reconciliation.py for coherence
        │
        ▼
Batch pipeline (pipelines/batch_inference.py)   orchestrates all of the above
        │   scripts/run_batch_forecast.py
        ▼
outputs/  ── forecasts/latest.csv · staffing/latest.csv · model_registry/*.json
        │
        ▼
Serving API (api/main.py)              read-only: /health /clinics /forecasts /staffing /scenario/marketing
        │
        ▼
Monitoring (monitoring.py)             drift + quality alerts → retraining triggers

* optional dependency, guarded import, not required by the core path
```

## Design choices

- **Contracts at the boundary.** Every dataset is validated against an
  explicit schema before any modelling, so bad data fails loudly and early
  rather than producing plausible-but-wrong forecasts.
- **One metric definition, shared everywhere.** `metrics.py` is the single
  source; `evaluation.py` only groups and ranks. Notebooks never re-implement
  a metric.
- **Leakage safety is structural.** Rolling/expanding features are computed
  per clinic on shifted series; the splitter guarantees train ends before
  test; recursive forecasting feeds predictions back as lags.
- **Uncertainty drives decisions.** Conformal intervals, not a flat buffer,
  size the staffing safety margin per clinic.
- **MLOps without infrastructure.** Batch outputs, a JSON model registry and
  a read-only API give a production-shaped workflow that still runs on a
  laptop or in one Docker container.

## From PoC to production

The notebooks are the analytical narrative; the package under
`src/clinic_forecast` is the reusable, tested code. To productionise:

- Swap the synthetic generator for governed real data behind the same
  contracts.
- Replace the carried-forward marketing assumption with the real plan feed.
- Schedule `run_batch_forecast.py`; route the monitoring report to owners and
  wire its triggers to retraining.
- Put the API behind auth and a real store if request volume requires it.
