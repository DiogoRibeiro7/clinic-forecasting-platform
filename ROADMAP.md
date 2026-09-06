# Roadmap

This roadmap reflects the current repository state after the frozen NHS GPAD external-validity benchmark. The original PoC and synthetic decision-policy milestones are largely complete; remaining work is now split between scientific validation, serving/operations, and genuinely new real-world identification work.

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
- [x] Report frozen target and policy performance by forecast horizon and by weekly horizon bands.
- [x] Add paired origin-level uncertainty summaries and exact descriptive sign tests for frozen comparisons.
- [x] Record the fresh four-model recursive benchmark artifact and immutable result note.
- [x] Audit 90% conformal coverage prequentially on held-out open clinic-days by fold, horizon and clinic.

### Demand and decision layers

- [x] Implement transparent staffing decision rules and cost scenarios.
- [x] Implement mean-forecast and interval-upper-bound staffing plans.
- [x] Implement bottom-up, top-down and middle-out hierarchical reconciliation.
- [x] Implement no-show modelling as a secondary target.
- [x] Implement model-based marketing what-if scenarios with explicit non-causal framing.
- [x] Reconstruct pre-capacity attended demand from scheduled demand, no-shows and cancellations in the synthetic system.
- [x] Quantify unmet demand and capacity censoring explicitly in the synthetic system.
- [x] Add a role-specific forecasting path for attended, completed and scheduled demand.
- [x] Commit paired target evidence showing attended demand improves censored-period forecasting.
- [x] Commit paired staffing evidence showing target choice is a cost/service trade-off.
- [x] Freeze a capacity-aware hybrid switch before evaluating it.
- [x] Confirm the frozen hybrid improves the overall synthetic cost/service frontier.
- [x] Replicate the frozen hybrid across alternate synthetic seeds and demand/capacity regimes without changing the switch.
- [x] Audit frozen hybrid performance by individual forecast horizon and weekly horizon bands.
- [x] Promote the frozen hybrid into the role-specific batch staffing path.
- [x] Expose capacity pressure, selected clinical target and switch-rate monitoring.
- [x] Evaluate the proposed constrained optimizer against the transparent rule-based policy and record `tradeoff_do_not_promote`; retain the rule-based policy as the promoted implementation.

### Real-data external-validity bridge

- [x] Add the NHS England GPAD June 2026 adapter and provenance/quality gate.
- [x] Lock the official archive identity by SHA-256 and byte size.
- [x] Audit source calendar support and official monthly practice/patient coverage.
- [x] Harden exact count parsing and acquisition provenance after review.
- [x] Prospectively freeze a confirmatory panel of 31 fully covered sub-ICBs across the full 912-day window.
- [x] Freeze the zero policy for sparse positive-count GPAD rows and all 19 outer origins before model scoring.
- [x] Run the first post-merge confirmatory NHS benchmark without pre-merge access to external scores.
- [x] Record the immutable confirmatory result and interpretation boundary.

The frozen NHS result supports aggregate forecasting generalization to observed attended GP appointment activity: recursive global HGB improved pooled MAE/WAPE/RMSE relative to seasonal naive, with gains in all four weekly horizon bands and 30/31 eligible sub-ICBs. The improvement was not temporally universal: seasonal naive remained better in 8/19 outer origins. The public GPAD source does not identify latent demand, usable capacity, unmet demand, staffing efficiency or causal policy effects.

### Production-shaped engineering

- [x] Add typed data contracts.
- [x] Add a batch inference pipeline.
- [x] Add local model-registry metadata.
- [x] Add monitoring for forecast quality, bias, volume shifts and interval coverage.
- [x] Add descriptive monitoring for hybrid-policy switch frequency.
- [x] Add FastAPI endpoints for forecast and staffing retrieval.
- [x] Add Docker, CI, model-card and operational-risk documentation.
- [x] Persist provenance for target, staffing, hybrid, optimizer, GPAD quality/calendar and GPAD confirmatory evidence runs.

## Next scientific work

1. [x] **Regenerate and commit a fresh general multi-model benchmark artifact under deployment-matched recursive evaluation.** Completed with the frozen 8-fold seed-42 core benchmark and immutable result note; retired teacher-forced headline values remain superseded.
2. [x] **Audit conformal interval coverage by forecast horizon and clinic.** Completed with a frozen 90% prequential audit on held-out open clinic-days, including fold, horizon, weekly-band and clinic diagnostics plus deterministic closed-day serving checks.
3. [x] **Add holiday calendars for an explicitly selected deployment geography.** Completed prospectively with a source-locked England & Wales bank-holiday calendar, generation provenance and batch inheritance; legacy fixed-date semantics remain the default for frozen synthetic evidence.
4. [x] **Characterize temporal regimes behind the 8/19 NHS origins where seasonal naive beat HGB.** Completed as an explicitly exploratory analysis of the canonical confirmatory artifact using a descriptor set frozen before winner-group inspection. Level, dispersion, zero-frequency and realised shift distributions overlapped substantially; calendar clustering was the clearest descriptive signal, and several seasonal-naive wins were broad network-wide episodes rather than isolated geography failures. No switching rule or confirmatory reinterpretation was introduced.

## Real policy identification — still open

The NHS GPAD forecasting bridge is complete, but the real staffing-policy estimand remains unidentified from public GPAD alone.

- [ ] Acquire or define a governed operational dataset containing demand attempts independently of completed activity: request/booking-attempt timestamps, requested/preferred service date or urgency, booked/deferred/redirected/unfulfilled outcome, waitlist/triage/backlog and cancellation/rebooking lifecycle.
- [ ] Acquire a defensible patient-facing capacity measure: appointment slots by day/role, or rosters/hours with administrative, training and break time distinguishable and an explicit productivity conversion.
- [ ] Define the joint identification and governance contract before any real latent-demand, capacity-censoring, unmet-demand or staffing-policy validation.
- [ ] Only after both demand and capacity are identified, prospectively freeze a real policy-validation design. Do not infer capacity from throughput or FTE alone.

## Next integration work

- [x] Version the serving contract before exposing scheduled, attended and hybrid clinical forecasts through the API. Completed with the explicit `/v2` contract version, version header, discovery endpoint and fail-closed artifact schema validation.
- [x] Decide whether the role-specific hybrid path should replace the legacy completed-visits serving path. The versioned `/v2` role-specific contract is now the primary serving surface and operational batch default; legacy unversioned routes and commands remain compatibility-only.
- [x] Surface hybrid switch-rate monitoring in the operational dashboard. Completed with a dependency-free HTML renderer and `make dashboard`, using the existing latest role-specific monitoring artifact. The dashboard displays descriptive network and clinic switch-use metrics only; it does not claim realised switch correctness.
- [ ] Add realised post-horizon evaluation of switch precision/recall once appropriate outcomes become available.

## Next decision-science work

The optimizer experiment is closed for the current synthetic setup: it reduced cost but approximately doubled unmet demand and is recorded as `tradeoff_do_not_promote`.

- [x] Decide whether the current staffing layer remains the promoted transparent rule-based decision policy rather than the tested constrained optimizer.
- [ ] If a future optimizer is researched, treat it as a new model class with a prospectively defined service constraint/objective rather than tuning the rejected optimizer after seeing its result.
- [ ] Compare forecast-mean, upper-interval and transparent rule-based staffing policies on held-out realised demand where the estimand is actually observed.
- [ ] Add waiting-time or queue-pressure proxy metrics when a defensible operational source is available.

## Operational maturity

- [x] Add a scheduled/manual integration workflow that installs and executes the heavy optional model stack. Completed with a weekly/manual Python 3.11 workflow that installs Poetry's optional group, runs the optional-wrapper regression tests, verifies all declared optional imports, executes small local StatsForecast/MLForecast/NeuralForecast forecasts, avoids hosted inference and pretrained-weight downloads, and uploads exact environment provenance.
- [x] Add scheduled retraining orchestration rather than only retraining signals. Completed as a weekly/manual portfolio rehearsal on deterministic synthetic data. It reuses the existing role-specific batch training path, validates v2 serving schemas and the three target registry records, checks common training cutoff/horizon and persisted artifact paths, and uploads the complete serving/registry/provenance bundle. It is not a claim of autonomous clinical retraining or model promotion on governed production data.
- [x] Version persisted model artifacts and serving metadata so a forecast response can be traced to exact model/data/config provenance. Completed with immutable `role_specific/runs/<run_id>/` bundles, SHA-256 identities for input/config/output and registry records, source revision, one-run-per-model-version binding, `latest_manifest.json`, `/v2/provenance`, `X-Clinic-Forecast-Run-Id`, and fail-closed artifact verification before provenance-enabled serving. Pre-provenance local outputs retain the compatibility fallback.
- [ ] Add an explicit production-readiness checklist separating portfolio/demo capabilities from claims that require a governed clinical deployment environment.

## Evidence discipline

- Frozen synthetic policy evidence must remain distinct from the NHS forecasting benchmark.
- The NHS confirmatory result must not be retuned or re-labelled after inspection.
- Follow-up analyses motivated by the NHS result are exploratory unless prospectively frozen in a new design before scoring.
- Public GPAD supports claims about observed appointment activity only; it does not validate the synthetic latent-demand or staffing-policy layer.
