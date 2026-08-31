# Architecture

The PoC is local-first and file-backed: plain CSV in, plain CSV out, no
database or services required. It is structured so each piece could be lifted
into a production pipeline unchanged.

## Data flow

```text
Synthetic generator (data.py)
        │   scripts/generate_data.py + contracts.py (validate)
        ▼
data/processed/ ── clinic_daily_usage, clinic_metadata, marketing_daily, staffing_daily
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
        ├──────────────────────────────────────────────────────┐
        ▼                                                      ▼
Legacy completed-visits path                         Role-specific hybrid path
pipelines/batch_inference.py                         pipelines/role_specific_batch.py
scripts/run_batch_forecast.py                        scripts/run_role_specific_batch.py
        │                                                      │
        ▼                                                      ▼
outputs/forecasts/latest.csv                         outputs/role_specific/forecasts/latest.csv
outputs/staffing/latest.csv                          outputs/role_specific/staffing/latest.csv
                                                     outputs/role_specific/monitoring/latest.csv
        │                                                      │
        └───────────────────────────┬──────────────────────────┘
                                    ▼
                           FastAPI serving layer
             legacy: /health /forecasts /staffing /scenario/marketing
             v2:     /v2/health /v2/forecasts /v2/staffing /v2/hybrid-monitoring
                                    │
                                    ▼
Monitoring (monitoring.py, hybrid_monitoring.py)

* optional dependency, guarded import, not required by the core path
```

## Hybrid decision path

The role-specific batch forecasts three demand quantities from the same fixed
origin:

- completed visits for throughput and the default clinical target;
- attended demand for capacity-pressured clinical staffing;
- scheduled appointments for front-desk staffing.

For each clinic-day, the frozen hybrid policy compares the 90% upper
split-conformal bound for completed visits with known daily clinic capacity.
If the upper bound reaches or exceeds capacity, clinicians and nurses are sized
from attended demand; otherwise they are sized from completed visits. Front
desk always uses scheduled appointments.

The switch is computed in the batch pipeline and written into the artefacts as
`capacity_pressure` and `hybrid_target`. The API never recomputes it.

## Design choices

- **Contracts at the boundary.** Every dataset is validated against an explicit
  schema before modelling, so bad data fails loudly and early rather than
  producing plausible-but-wrong forecasts.
- **One metric definition, shared everywhere.** `metrics.py` is the single
  source; `evaluation.py` only groups and ranks. Notebooks never re-implement a
  metric.
- **Leakage safety is structural.** Rolling/expanding features are computed per
  clinic on shifted series; the splitter guarantees train ends before test;
  recursive forecasting feeds predictions back as lags.
- **Target selection is prospective.** Realised `capacity_censored` is used only
  for evaluation. The operational hybrid switch uses historical conformal
  residuals, forecast distributions and known capacity.
- **Uncertainty drives decisions.** Conformal intervals are part of both the
  staffing safety margin and the hybrid pressure trigger.
- **Serving semantics are versioned.** The unversioned API preserves the legacy
  completed-visits contract; `/v2` exposes the hybrid role-specific contract.
- **MLOps without infrastructure.** Batch outputs, a JSON model registry and a
  read-only API give a production-shaped workflow that still runs on a laptop
  or in one Docker container.

## From PoC to production

The notebooks are the analytical narrative; the package under
`src/clinic_forecast` is the reusable, tested code. To productionise:

- Swap the synthetic generator for governed real data behind the same contracts.
- Establish how pre-capacity attended demand is observed or estimated in the
  real operating system; the synthetic reconstruction is not automatically
  transferable.
- Replace the carried-forward marketing assumption with the real plan feed.
- Schedule the role-specific batch path and route both general forecast
  monitoring and hybrid switch-use summaries to operational owners.
- Validate staffing productivity, cost coefficients and the frozen hybrid
  trigger on real held-out operations before changing real rosters.
- Put the API behind auth and a real store if request volume requires it.
