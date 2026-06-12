# Model Card — Clinic Usage Forecasting PoC

This card follows the spirit of Mitchell et al. (2019). It documents a
**proof of concept**: production-style design, but trained and evaluated
entirely on synthetic data.

## Intended use

- **Primary:** forecast daily completed visits per clinic over a 28-day
  horizon and convert those forecasts into staffing recommendations and cost
  scenarios for operational planning (rosters, overtime/float allocation,
  marketing-coordination what-ifs).
- **Intended users:** regional operations managers, clinic managers and
  network capacity planners, with a data team operating the pipeline.
- **Decision support, not automation:** outputs inform human roster decisions;
  they do not change rosters automatically.

## Out-of-scope use

The model **must not** be used for:

- Patient-level prediction, clinical diagnosis, treatment or triage decisions.
- Individual staff performance assessment.
- Any decision affecting an identifiable patient or clinician.
- Automated rostering without human review.
- Real-world deployment **as-is**: it is trained on synthetic data and would
  require retraining and revalidation on real, governed data first.

## Data assumptions

- Aggregate clinic-by-day operational data only; **no patient-level fields**
  and no protected health information.
- Inputs available at forecast time: history (lags, rolling stats), calendar
  and opening days, planned marketing spend, and static clinic metadata.
- Marketing spend in the forecast horizon is a **plan assumption** (carried
  forward by weekday in the batch pipeline), not a known fact.

### Synthetic data limitations

- Magnitudes, seasonality strengths and marketing elasticities are simulated,
  not estimated from a real network. **Absolute accuracy and cost figures
  demonstrate the method; they are not benchmarks for any real clinic.**
- The simulation cannot contain failure modes nobody thought to simulate. Real
  data will have data-quality issues, structural breaks and exogenous shocks
  absent here.

## Forecast targets

- **Primary:** completed visits per clinic per day.
- **Secondary:** scheduled appointments and the attrition rate (no-shows +
  same-day cancellations), enabling staffing of front-desk to *scheduled* and
  clinicians to *expected completed* demand.

## Evaluation

- **Protocol:** rolling-origin backtesting (`RollingOriginSplitter`); training
  always ends strictly before each 28-day test window.
- **Primary metric:** WAPE (robust to closure zeros, volume-weighted). Bias is
  tracked separately because staffing costs are asymmetric. MAPE is reported
  but not relied upon (undefined on zero-visit days).
- **Bar to clear:** the seasonal-naive baseline, on every fold.
- **Uncertainty:** split conformal intervals, evaluated by realised coverage
  and width on held-out folds.

## Known failure modes

- **Demand episodes** (e.g. flu waves) are visible only once underway; no
  model anticipates their onset from the demand series alone. These dominate
  residual error.
- **Capacity censoring:** on days a clinic hits capacity, recorded visits
  understate true demand, biasing peak-day forecasts low.
- **Recursive horizon decay:** deployment-mode multi-step forecasts feed
  predictions back as lags; error grows with horizon.
- **Cold-start clinics:** clinics with little history rely on metadata and
  cross-clinic structure; expect wider intervals and weaker accuracy.
- **Plan-vs-actual marketing:** if executed spend diverges from the assumed
  plan, the marketing-driven part of the forecast is wrong.

## Operational risks

See [`docs/operational_risk.md`](../docs/operational_risk.md) for the full
risk register. The headline operational risk is **systematic under-forecasting
causing chronic understaffing** — costlier than the equivalent overstaffing —
which is why bias is monitored per clinic and conservative (interval
upper-bound) staffing is offered.

## Bias and fairness (clinic / region level)

- This is an **operational** model: "fairness" here means no clinic or region
  is *systematically* worse-served than others, not a protected-attribute
  analysis (no demographic data is used or available).
- Per-clinic WAPE spread is reported in every evaluation; small or volatile
  clinics carry higher relative error. Monitoring per-clinic bias guards
  against one region quietly absorbing most of the forecast error.
- Volume-weighted network metrics can hide poor service to small clinics;
  per-clinic metrics are always reported alongside.

## Human review process

- Staffing recommendations are reviewed by operations managers before rosters
  change; the model never edits a roster directly.
- Alerts from the monitoring layer trigger manual review of the affected
  clinics' recommendations until resolved.
- Marketing scenarios are presented as model-based what-ifs, explicitly not
  causal claims.

## Monitoring and retraining triggers

Implemented in `clinic_forecast.monitoring` with thresholds in
`configs/monitoring.yaml`; demonstrated in notebook 09.

- Track WAPE, bias and interval coverage per clinic and region.
- Track demand-volume, marketing-spend and capacity-utilisation shifts vs a
  reference window.
- **Retrain** on volume-shift + WAPE-degradation agreement for a clinic, or on
  persistent bias across two windows; **recalibrate intervals** alongside any
  retraining (their residuals are stale by definition).
- **Fix the input, not the model**, on a marketing-spend shift alone.
