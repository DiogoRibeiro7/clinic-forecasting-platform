# Roadmap

## Stage 1 — PoC foundation

- [x] Define the business problem.
- [x] Create synthetic healthcare-network data.
- [x] Add clinic metadata, marketing data and operational capacity fields.
- [x] Implement core metrics and rolling-origin validation.
- [x] Implement baseline and SARIMAX models.
- [x] Implement global ML forecasting with lag features.
- [x] Convert forecasts into staffing recommendations.

## Stage 2 — Model quality

- [ ] Add hierarchical reconciliation across network, region and clinic levels.
- [ ] Add prediction intervals for ML models using conformal calibration.
- [ ] Add model selection per clinic based on rolling backtests.
- [ ] Add holiday calendars for target geographies.
- [ ] Add no-show forecasting as a second target.
- [ ] Add waiting-time proxy metrics.

## Stage 3 — Production design

- [ ] Add feature-store style data contracts.
- [ ] Add batch inference pipeline.
- [ ] Add model registry metadata.
- [ ] Add monitoring for forecast drift, bias and volume shifts.
- [ ] Add scheduled retraining logic.
- [ ] Add FastAPI endpoints for forecast retrieval.

## Stage 4 — Business impact

- [ ] Estimate overtime reduction.
- [ ] Estimate idle capacity reduction.
- [ ] Add clinic-level budget impact.
- [ ] Add scenario planning for marketing campaigns.
- [ ] Add what-if simulation for opening hours and appointment slots.

## Stage 5 — Advanced methods

- [ ] Add Temporal Fusion Transformer or N-BEATS.
- [ ] Add TimeGPT benchmarking.
- [ ] Add probabilistic forecasting.
- [ ] Add hierarchical probabilistic forecasts.
- [ ] Add causal impact analysis for marketing campaigns.
