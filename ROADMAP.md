# Roadmap

This roadmap reflects the repository state after the immutable serving-provenance work merged in PRs #54 and #55. The current forecasting, synthetic decision-science and NHS GPAD external-validity programme is complete at the evidence boundary supported by the available data.

The remaining work is therefore split into two categories:

1. **unblocked repository hardening** that can be completed now; and
2. **operational-data-dependent validation** that must not be simulated or inferred from public GPAD.

## Current priority — unblocked

### 1. Production-readiness boundary

- [ ] **Add an explicit production-readiness checklist separating portfolio/demo capabilities from claims that require a governed clinical deployment environment.**

The checklist should cover, at minimum:

- data ownership, access control, privacy review and retention;
- production source contracts and schema-change ownership;
- model validation, approval, promotion and rollback authority;
- monitoring, incident response, service ownership and operational SLOs;
- security, dependency and secret-management expectations;
- retraining approval and change-control requirements;
- auditability of source data, configuration, model versions and served artefacts;
- human review responsibilities for staffing recommendations;
- explicit labels for `implemented in this portfolio`, `requires deployment integration`, and `requires governed clinical evidence`.

After the checklist exists, use it to perform a repository-wide readiness review rather than adding more production-shaped features without a stated deployment requirement.

## Blocked by operational data

The public NHS GPAD source validates forecasting of observed attended appointment activity only. It does **not** identify latent demand, usable patient-facing capacity, unmet demand, staffing efficiency, waiting pressure or causal staffing-policy effects.

The following work is therefore intentionally blocked until the required operational evidence exists:

- [ ] Acquire or define a governed demand-attempt dataset containing request/booking-attempt timestamps, requested or preferred service date or urgency, booked/deferred/redirected/unfulfilled outcome, waitlist/triage/backlog state and cancellation/rebooking lifecycle.
- [ ] Acquire a defensible patient-facing capacity measure: appointment slots by day/role, or rosters/hours with administrative, training and break time distinguishable and an explicit productivity conversion.
- [ ] Define the joint identification and governance contract for demand, capacity and outcomes before any real latent-demand, capacity-censoring, unmet-demand or staffing-policy validation.
- [ ] Add realised post-horizon evaluation of hybrid-switch precision/recall once the corresponding outcomes are actually observable.
- [ ] Compare forecast-mean, upper-interval and transparent rule-based staffing policies on held-out realised demand once that estimand is observed.
- [ ] Add waiting-time or queue-pressure metrics only when a defensible operational source exists.
- [ ] Prospectively freeze a real staffing-policy validation design only after both demand and capacity are identified. Do not infer capacity from throughput or FTE alone.

## Deferred research — not current roadmap work

The constrained optimiser experiment is closed for the current synthetic setup and remains `tradeoff_do_not_promote` because its cost reduction came with approximately doubled unmet demand.

- A future optimiser must be treated as a **new model class** with a prospectively defined service constraint and objective. Do not retune the rejected optimiser after observing its result.
- Do not retune the frozen hybrid switch using its confirmatory or robustness failures. A materially different switch requires a new prospective design and new evidence.
- Additional model families or tuning should be added only to answer an explicit new question under the fixed-origin evaluation contract, not to expand the model zoo for its own sake.

## Completed scientific and engineering programme

### Forecasting and validation

- [x] Define typed aggregate clinic-by-day contracts and a reproducible synthetic healthcare-network generator with seasonality, changepoints, marketing effects, overdispersion and capacity censoring.
- [x] Implement seasonal-naive and moving-average baselines, per-clinic SARIMAX, optional Prophet, pooled global ML, Nixtla wrappers, LSTM and foundation-model wrappers behind a common forecast schema.
- [x] Implement rolling-origin validation and deployment-matched fixed-origin recursive evaluation for lag-based global ML.
- [x] Replace the retired teacher-forced headline comparison with a fresh multi-fold recursive benchmark.
- [x] Implement split-conformal intervals calibrated from recursive rolling-fold residuals.
- [x] Report target and policy performance by exact horizon and weekly horizon bands, including paired origin-level uncertainty and descriptive exact sign tests.
- [x] Audit 90% conformal coverage prequentially by fold, horizon and clinic.
- [x] Add a source-locked England & Wales holiday calendar while preserving legacy calendar semantics for frozen synthetic evidence.
- [x] Characterise the NHS origins where seasonal naive beat HGB as an exploratory post-confirmatory analysis without introducing a switching rule or reinterpretation of the frozen result.

### Demand and decision science

- [x] Implement transparent staffing rules, mean and upper-interval plans, cost evaluation, hierarchical reconciliation, no-show modelling and explicitly non-causal marketing scenarios.
- [x] Reconstruct pre-capacity attended demand, unmet demand and capacity censoring in the synthetic system.
- [x] Add role-specific attended-demand, completed-visits and scheduled-appointments forecasting.
- [x] Commit paired target evidence showing attended-demand forecasting improves censored-period demand estimation while completed visits remain competitive when uncensored.
- [x] Commit paired staffing evidence showing target selection is a cost/service trade-off.
- [x] Prospectively freeze, confirm and robustness-test the capacity-aware hybrid clinical target switch without post-hoc threshold changes.
- [x] Audit hybrid policy performance by exact horizon and weekly bands.
- [x] Promote the frozen hybrid into the role-specific batch path and expose capacity pressure, selected target and descriptive switch-rate monitoring.
- [x] Evaluate the constrained clinical optimiser prospectively and retain the transparent rule-based policy after the optimiser returned `tradeoff_do_not_promote`.

### NHS GPAD external-validity bridge

- [x] Add the NHS England GPAD June 2026 adapter, source/schema mapping, provenance and fail-closed quality gate.
- [x] Lock the official archive identity by SHA-256 and byte size.
- [x] Audit source calendar support and official monthly practice/patient coverage before modelling.
- [x] Prospectively freeze the 31-sub-ICB confirmatory panel, sparse-row zero policy and all 19 outer origins.
- [x] Run the first post-merge confirmatory benchmark without pre-merge access to external model scores.
- [x] Record the immutable confirmatory result and interpretation boundary.

The frozen NHS result supports aggregate forecasting generalisation to observed attended GP appointment activity: recursive global HGB improved pooled MAE/WAPE/RMSE relative to seasonal naive, with gains in all four weekly horizon bands and 30/31 eligible sub-ICBs. The improvement was not temporally universal: seasonal naive remained better in 8/19 outer origins.

### Serving and operational maturity

- [x] Add batch inference, local model-registry metadata, forecast-quality/drift monitoring, Docker, CI, notebook smoke checks, model-card and operational-risk documentation.
- [x] Version the role-specific serving contract under `/v2`, add a discoverable contract endpoint and fail closed on incompatible artefact schemas.
- [x] Promote the role-specific hybrid path as the primary serving surface while preserving explicit legacy compatibility routes and commands.
- [x] Surface descriptive hybrid switch-rate monitoring in the operational dashboard without claiming realised switch correctness.
- [x] Add a weekly/manual integration workflow for the heavy optional model stack, including local StatsForecast/MLForecast/NeuralForecast execution and exact environment provenance.
- [x] Add weekly/manual scheduled retraining orchestration as a deterministic synthetic portfolio rehearsal reusing the existing role-specific training path.
- [x] Add immutable serving provenance with `role_specific/runs/<run_id>/`, one-run-per-model-version binding, exact source revision, input/config/output and registry SHA-256 identities, `latest_manifest.json`, `/v2/provenance`, `X-Clinic-Forecast-Run-Id` and fail-closed artefact verification.
- [x] Document the immutable serving-provenance contract and pre-provenance compatibility fallback.

## Evidence discipline

- Frozen synthetic policy evidence must remain distinct from the NHS forecasting benchmark.
- The NHS confirmatory result must not be retuned or re-labelled after inspection.
- Follow-up analyses motivated by the NHS result are exploratory unless prospectively frozen in a new design before scoring.
- Public GPAD supports claims about observed appointment activity only; it does not validate the synthetic latent-demand or staffing-policy layer.
- Operational maturity features must not be presented as evidence of clinical deployment readiness. The production-readiness checklist is the explicit boundary for those claims.
