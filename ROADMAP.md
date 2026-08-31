# Roadmap

The original roadmap described the first PoC plan and became stale as later stages were implemented. This version distinguishes implemented platform capabilities from remaining scientific and operational work.

## Implemented

### Forecasting and validation

- [x] Define the business problem and aggregate clinic-by-day data contract.
- [x] Generate reproducible synthetic healthcare-network data with seasonality, changepoints, marketing effects, overdispersion and persistent demand episodes.
- [x] Implement seasonal-naive and moving-average baselines.
- [x] Implement per-clinic SARIMAX and optional Prophet.
- [x] Implement pooled global ML forecasting with HGB, XGBoost and LightGBM.
- [x] Implement optional Nixtla, LSTM and foundation-model wrappers behind a common forecast schema.
- [x] Implement rolling-origin temporal validation.
- [x] Implement deployment-matched fixed-origin recursive backtesting for lag-based global ML.
- [x] Replace the retired one-fold teacher-forced headline benchmark with a multi-fold fixed-origin benchmark.
- [x] Implement split-conformal intervals calibrated from recursive rolling-fold residuals.

### Demand and decision layers

- [x] Implement transparent staffing decision rules and cost scenarios.
- [x] Implement mean-forecast and interval-upper-bound staffing plans.
- [x] Implement bottom-up, top-down and middle-out hierarchical reconciliation.
- [x] Implement no-show modelling as a secondary target.
- [x] Implement model-based marketing what-if scenarios with explicit non-causal framing.
- [x] Reconstruct pre-capacity attended demand from scheduled demand, no-shows and cancellations.
- [x] Quantify unmet demand and capacity censoring explicitly.
- [x] Add a role-specific forecasting path for attended, completed and scheduled demand.
- [x] Commit paired target evidence showing attended demand improves censored-period forecasting.
- [x] Commit paired staffing evidence showing target choice is a cost/service trade-off.
- [x] Freeze a capacity-aware hybrid switch before evaluating it.
- [x] Confirm the frozen hybrid improves the overall cost/service frontier.
- [x] Promote the frozen hybrid into the role-specific batch staffing path.
- [x] Expose capacity pressure, selected clinical target and switch-rate monitoring.

### Production-shaped engineering

- [x] Add typed data contracts.
- [x] Add a batch inference pipeline.
- [x] Add local model-registry metadata.
- [x] Add monitoring for forecast quality, bias, volume shifts and interval coverage.
- [x] Add descriptive monitoring for hybrid-policy switch frequency.
- [x] Add FastAPI endpoints for forecast and staffing retrieval.
- [x] Add Docker, CI, model-card and operational-risk documentation.

## Next scientific work

- [ ] Regenerate and commit a fresh general multi-model benchmark artifact after the recursive evaluation fix; do not reuse retired teacher-forced WAPE values.
- [ ] Report target and policy performance by forecast horizon rather than only pooled over 28 days.
- [ ] Add paired uncertainty for model and policy differences across rolling origins.
- [ ] Evaluate interval coverage by horizon and clinic, not only pooled across calibration residuals.
- [ ] Replicate the frozen hybrid policy across alternate synthetic seeds and demand/capacity regimes without changing its switch.
- [ ] Add holiday calendars for an explicitly selected deployment geography.
- [ ] Define how latent attended demand would be identified from real operational data where it is not directly reconstructible.

## Next integration work

- [ ] Version the serving contract before exposing scheduled, attended and hybrid clinical forecasts through the API.
- [ ] Decide whether the role-specific hybrid path should replace the legacy completed-visits serving path.
- [ ] Surface hybrid switch-rate monitoring in the operational dashboard.
- [ ] Add realised post-horizon evaluation of switch precision/recall once outcomes become available.

## Next decision-science work

- [ ] Decide whether the staffing layer remains a transparent rule-based decision policy or becomes a genuine constrained optimisation model; keep naming consistent with the implementation.
- [ ] If optimisation is added, include roster limits, overtime, unmet-demand penalties and integer staffing decisions in the objective/constraints.
- [ ] Compare forecast-mean, upper-interval and cost-optimal staffing policies on held-out realised demand.
- [ ] Add waiting-time or queue-pressure proxy metrics.

## Operational maturity

- [ ] Add a scheduled/manual integration workflow that installs and executes the heavy optional model stack.
- [x] Persist benchmark provenance for the target, staffing and hybrid evidence runs.
- [ ] Add scheduled retraining orchestration rather than only retraining signals.
- [ ] Add real-data adapters and governance checks before any non-synthetic deployment claim.
