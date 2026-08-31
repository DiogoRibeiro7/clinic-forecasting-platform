# Model Card — Clinic Forecasting and Staffing PoC

This card follows the spirit of Mitchell et al. (2019). It documents a
**proof of concept**: production-style design, but trained and evaluated
entirely on synthetic data.

## Intended use

- **Throughput forecasting:** forecast daily completed visits per clinic over a
  28-day horizon for monitoring and compatibility with the original serving path.
- **Clinical staffing:** use the prospectively frozen capacity-aware hybrid
  policy. Completed-visits demand is used by default; the policy switches to
  attended-demand forecasting when the 90% upper split-conformal bound for
  completed visits reaches or exceeds known clinic capacity.
- **Front-desk staffing:** use scheduled appointments, which represent workload
  earlier in the demand funnel.
- **Intended users:** regional operations managers, clinic managers and network
  capacity planners, with a data team operating the pipeline.
- **Decision support, not automation:** outputs inform human roster decisions;
  they do not change rosters automatically.

## Out-of-scope use

The system **must not** be used for:

- Patient-level prediction, clinical diagnosis, treatment or triage decisions.
- Individual staff performance assessment.
- Any decision affecting an identifiable patient or clinician.
- Automated rostering without human review.
- Real-world deployment **as-is**: it is trained on synthetic data and would
  require retraining and revalidation on real, governed data first.

## Data assumptions

- Aggregate clinic-by-day operational data only; **no patient-level fields** and
  no protected health information.
- Inputs available at forecast time: history (lags, rolling stats), calendar and
  opening days, planned marketing spend, static clinic metadata and known daily
  capacity.
- Marketing spend in the forecast horizon is a **plan assumption** (carried
  forward by weekday in the batch pipeline), not a known fact.
- The hybrid switch uses only forecast-time information. Realised
  `capacity_censored` is evaluation-only and is never used to choose the target.

### Synthetic data limitations

- Magnitudes, seasonality strengths and marketing elasticities are simulated,
  not estimated from a real network. **Absolute accuracy and cost figures
  demonstrate the method; they are not benchmarks for any real clinic.**
- The simulation cannot contain failure modes nobody thought to simulate. Real
  data will have data-quality issues, structural breaks and exogenous shocks
  absent here.

## Forecast and decision targets

The system deliberately separates measurement from decision targets:

- **Completed visits (`visits`)** — observed throughput and the legacy API target.
- **Attended demand (`attended_demand`)** — reconstructed pre-capacity demand,
  used when the hybrid policy detects prospective capacity pressure.
- **Scheduled appointments (`scheduled_appointments`)** — front-desk workload
  target.

Completed visits are capped by clinic capacity in the synthetic generator and
therefore understate demand on capacity-censored days. The repository now
reconstructs attended demand from scheduled appointments, no-shows and
same-day cancellations and evaluates that target explicitly.

The confirmatory decision evidence does **not** support attended-demand staffing
everywhere. In the frozen four-fold benchmark, the capacity-aware hybrid was
preferred among the three tested policies: it reduced unmet demand by about
9.31% versus completed-visits-only staffing for about 0.70% higher total cost,
and it Pareto-dominated attended-demand-only staffing overall (about 0.32%
lower cost and 4.59% lower unmet demand). On realised capacity-censored days it
also beat both pure policies. These figures are conditional on the synthetic
generator, staffing productivity assumptions and cost coefficients.

The frozen trigger fired on 83.64% of realised censored days and 24.26% of
uncensored days in that benchmark. It is therefore an operational pressure
signal, **not** a perfect censoring classifier.

## Evaluation

- **Protocol:** rolling-origin, fixed-origin backtesting
  (`RollingOriginSplitter`); training always ends strictly before each test
  window.
- **Information set:** primary multi-day evaluation forecasts the complete
  holdout horizon from the fold origin. Lag-based global ML is recursive;
  realised targets inside the test window are not used as future lag inputs.
- **Primary forecast metric:** WAPE. Bias is tracked separately because staffing
  costs are asymmetric. MAPE is descriptive only.
- **Decision metrics:** total, regular, overtime, understaffing and idle cost;
  unmet visits; understaffed-day rate; and staff-days.
- **Baseline:** seasonal naive remains the minimum forecast reference model.
  Historical one-fold teacher-forced global-ML WAPE values are retired.
- **Uncertainty:** split-conformal intervals are calibrated from recursive
  rolling-fold residuals produced by the same forecast mechanism used in the
  batch pipeline.
- **Hybrid policy evidence:** the switch was prospectively frozen before its
  confirmatory benchmark; no threshold search was performed after seeing the
  result.

## Known failure modes

- **Demand episodes** (e.g. flu waves) are visible only once underway; no model
  anticipates their onset from the demand series alone. These dominate residual
  error.
- **Capacity censoring:** completed visits understate pre-capacity demand on busy
  days.
- **Pressure false positives:** the hybrid trigger can switch to attended demand
  on days that later prove uncensored; this is why completed-visits-only remains
  better on the uncensored slice of the confirmatory benchmark.
- **Recursive horizon decay:** deployment-mode multi-step forecasts feed
  predictions back as lags; error can grow with horizon.
- **Cold-start clinics:** clinics with little history rely on metadata and
  cross-clinic structure; expect wider intervals and weaker accuracy.
- **Plan-vs-actual marketing:** if executed spend diverges from the assumed plan,
  the marketing-driven part of the forecast is wrong.

## Operational risks

See [`docs/operational_risk.md`](../docs/operational_risk.md) for the full risk
register. A central operational risk is systematic under-forecasting causing
chronic understaffing. The hybrid decision layer addresses one specific source
of that risk—capacity-censored throughput—without claiming to solve all sources
of demand uncertainty.

## Bias and fairness (clinic / region level)

- This is an **operational** model: "fairness" here means no clinic or region is
  systematically worse-served than others, not a protected-attribute analysis
  (no demographic data is used or available).
- Per-clinic WAPE spread should be reported in every formal evaluation; small or
  volatile clinics generally carry higher relative error.
- Volume-weighted network metrics can hide poor service to small clinics;
  per-clinic metrics must be reported alongside network summaries.

## Human review process

- Staffing recommendations are reviewed by operations managers before rosters
  change; the model never edits a roster directly.
- Hybrid outputs expose `daily_capacity`, `capacity_pressure`, `hybrid_target`
  and both candidate target forecasts so the decision can be audited.
- Alerts from the monitoring layer trigger manual review of the affected
  clinics' recommendations until resolved.
- Marketing scenarios are presented as model-based what-ifs, explicitly not
  causal claims.

## Serving contracts

The API has two explicit compatibility surfaces:

- The unversioned `/forecasts`, `/staffing`, `/health` and marketing-scenario
  endpoints retain the original completed-visits batch contract.
- `/v2/forecasts`, `/v2/staffing`, `/v2/hybrid-monitoring` and `/v2/health`
  serve the operational role-specific hybrid artefacts.

The API never recomputes the hybrid rule or trains models at request time. It
serves immutable batch artefacts. See
[`docs/api_v2_contract.md`](../docs/api_v2_contract.md).

## Monitoring and retraining triggers

General forecast monitoring is implemented in `clinic_forecast.monitoring` with
thresholds in `configs/monitoring.yaml`; hybrid-policy usage is summarised
separately by `clinic_forecast.hybrid_monitoring`.

- Track WAPE, bias and interval coverage per clinic and region.
- Track demand-volume, marketing-spend and capacity-utilisation shifts versus a
  reference window.
- Track hybrid switch counts/rates and the completed-upper-bound-to-capacity
  ratio descriptively by clinic and network.
- No post-hoc alert threshold has been assigned to hybrid switch frequency.
- **Retrain** on volume-shift + WAPE-degradation agreement for a clinic, or on
  persistent bias across two windows; **recalibrate intervals** alongside any
  retraining.
- **Fix the input, not the model**, on a marketing-spend shift alone.
