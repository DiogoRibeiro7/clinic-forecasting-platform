# Roadmap

The original roadmap described the first PoC plan and became stale as later stages were implemented. This version distinguishes **implemented platform capabilities** from the remaining scientific and operational work.

## Implemented

### Forecasting and validation

- [x] Define the business problem and aggregate clinic-by-day data contract.
- [x] Generate reproducible synthetic healthcare-network data with seasonality, changepoints, marketing effects, overdispersion and persistent demand episodes.
- [x] Implement seasonal-naive and moving-average baselines.
- [x] Implement per-clinic SARIMAX and optional Prophet.
- [x] Implement pooled global ML forecasting with HGB, XGBoost and LightGBM.
- [x] Implement optional Nixtla, LSTM and foundation-model wrappers behind a common forecast schema.
- [x] Implement rolling-origin temporal validation.
- [x] Implement deployment-matched **fixed-origin recursive** backtesting for lag-based global ML.
- [x] Replace the retired one-fold teacher-forced headline benchmark with a multi-fold fixed-origin benchmark.
- [x] Implement split-conformal intervals calibrated from recursive rolling-fold residuals.

### Decision and hierarchy layers

- [x] Implement transparent staffing decision rules and cost scenarios.
- [x] Implement mean-forecast and interval-upper-bound staffing plans.
- [x] Implement bottom-up, top-down and middle-out hierarchical reconciliation.
- [x] Implement no-show modelling as a secondary target.
- [x] Implement model-based marketing what-if scenarios with explicit non-causal framing.

### Production-shaped engineering

- [x] Add typed data contracts.
- [x] Add a batch inference pipeline.
- [x] Add local model-registry metadata.
- [x] Add monitoring for forecast quality, bias, volume shifts and interval coverage.
- [x] Add FastAPI endpoints for forecast and staffing retrieval.
- [x] Add Docker, CI, model-card and operational-risk documentation.

## Next scientific work

- [ ] Regenerate and commit a fresh multi-fold benchmark artifact after the recursive evaluation fix; do not reuse the retired teacher-forced WAPE values.
- [ ] Report performance by forecast horizon as well as pooled WAPE and bias.
- [ ] Add paired uncertainty for model-to-model benchmark differences across rolling origins.
- [ ] Distinguish latent attended demand from capacity-censored completed visits in the synthetic generator.
- [ ] Use role-relevant demand targets: scheduled demand for front-desk planning and expected attended demand for clinical staffing.
- [ ] Evaluate interval coverage by horizon and clinic, not only pooled across calibration residuals.
- [ ] Add holiday calendars for an explicitly selected deployment geography.

## Next decision-science work

- [ ] Decide whether the staffing layer remains a transparent rule-based decision policy or becomes a genuine constrained optimisation model; keep naming consistent with the implementation.
- [ ] If optimisation is added, include roster limits, overtime, unmet-demand penalties and integer staffing decisions in the objective/constraints.
- [ ] Compare forecast-mean, upper-interval and cost-optimal staffing policies on held-out realised demand.
- [ ] Add waiting-time or queue-pressure proxy metrics.

## Operational maturity

- [ ] Add a scheduled/manual integration workflow that installs and executes the heavy optional model stack.
- [ ] Persist benchmark provenance: commit SHA, environment, folds, model configuration and random seeds.
- [ ] Add scheduled retraining orchestration rather than only retraining signals.
- [ ] Add real-data adapters and governance checks before any non-synthetic deployment claim.
