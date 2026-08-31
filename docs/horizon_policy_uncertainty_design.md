# Frozen horizon-resolved policy and uncertainty audit

This document prospectively freezes a horizon-resolved audit of the already-selected capacity-aware hybrid clinical staffing policy. The purpose is to determine whether the policy's cost/service behaviour is stable across forecast horizons rather than only in pooled 28-day summaries.

This is an audit of an existing frozen policy, not a new tuning experiment.

## Frozen policy and data-generating process

Use the current default synthetic generator exactly as configured for the existing seed-42 reference network:

- start date: 2022-01-01;
- end date: 2025-12-31;
- clinics: 12;
- random seed: 42;
- seasonality strength: 1.0;
- marketing strength: 1.0;
- noise level: 1.0.

Use the already-frozen capacity-aware hybrid selector without modification:

\[
U^V_{c,t} \ge K_c
\Rightarrow
\text{attended-demand clinical forecast},
\]

otherwise use the completed-visits clinical forecast.

The 90% conformal level, HGB estimator, staffing rules, staffing costs, target definitions and legacy staffing evaluator are unchanged.

## Rolling-origin design

Use:

- initial training window: 1,095 days;
- horizon: 28 days;
- step: 28 days;
- expanding training window;
- all feasible non-overlapping outer origins.

For the fixed 2022-01-01 through 2025-12-31 calendar this yields exactly **13 outer origins**. The implementation must verify that 13 origins are present; otherwise the audit fails rather than silently changing sample size.

The nested conformal calibration remains:

- inner initial training: 730 days;
- inner horizon: 28 days;
- inner folds: 4;
- coverage: 0.90.

## Horizon definition

Within each outer origin, assign each test date a horizon index

\[
h \in \{1,\ldots,28\},
\]

where \(h=1\) is the first date after the forecast origin and \(h=28\) is the last date in the fixed test window.

All clinics sharing the same outer origin and calendar date share the same horizon index.

## Policies

Audit the same three clinical staffing policies used in the original hybrid experiment:

1. `attended_demand`;
2. `completed_visits`;
3. `hybrid`.

Front-desk staffing remains based on scheduled appointments and is identical across the three clinical policies.

## Primary horizon-level outcomes

For every outer origin, horizon \(h\), and policy, aggregate across clinics before comparing policies.

Primary outcomes:

- total cost;
- unmet visits;
- understaffed clinic-day rate;
- clinician-days;
- nurse-days.

Secondary outcomes:

- regular cost;
- overtime cost;
- understaffing cost;
- idle cost;
- capacity-pressure rate;
- hybrid switch rate;
- realised capacity-censoring rate.

The primary comparison remains the **all clinic-days** slice. Censored and uncensored horizon summaries may be reported descriptively but are not used to redefine the policy.

## Paired horizon contrasts

For each horizon \(h\), compute origin-level paired contrasts for:

### Hybrid versus completed-visits-only

\[
\Delta C_{H,V}(h)
=
C_H(h)-C_V(h),
\]

\[
\Delta U_{H,V}(h)
=
U_H(h)-U_V(h).
\]

### Hybrid versus attended-demand-only

\[
\Delta C_{H,A}(h)
=
C_H(h)-C_A(h),
\]

\[
\Delta U_{H,A}(h)
=
U_H(h)-U_A(h).
\]

The unit of pairing is the **outer origin**, not the clinic-day and not the clinic. Each horizon therefore has 13 paired observations per contrast.

## Uncertainty summaries

Because the number of outer origins is modest and the objective is descriptive robustness rather than population-level inference, report for each horizon and contrast:

- mean paired difference;
- median paired difference;
- standard deviation across origins;
- minimum and maximum origin-level difference;
- number of origins with negative difference;
- number of origins with positive difference;
- sign-consistency rate;
- a two-sided exact paired sign-test p-value as a descriptive diagnostic only.

Do **not** report row-wise standard errors, cluster on clinic-days, or treat the 12 clinics within an origin as independent replications.

Do **not** use the sign-test p-value as a promotion, withdrawal, or threshold-tuning criterion.

## Horizon bands

In addition to the exact 28 horizons, report four preregistered descriptive bands:

- week 1: horizons 1–7;
- week 2: horizons 8–14;
- week 3: horizons 15–21;
- week 4: horizons 22–28.

Band summaries must be computed from the already-produced origin × horizon aggregates. They are descriptive and do not replace the exact-horizon table.

## Interpretation rules

This audit asks whether the original pooled result hides horizon-specific reversals.

Report explicitly:

- horizons where hybrid has lower mean unmet demand than completed-only;
- horizons where hybrid has lower mean total cost than attended-only;
- horizons satisfying both original qualitative directions;
- horizons where either direction reverses;
- whether any reversal is isolated or persists across a contiguous horizon range;
- whether sign consistency across the 13 origins weakens materially with horizon.

No post-hoc horizon cutoff may be used to redefine the operational policy.

If the hybrid advantage weakens or reverses late in the horizon, report that as a monitoring/deployment limitation rather than retuning the 90% switch in this audit.

## Deliverables

The evidence run must write machine-readable files containing:

1. outer-origin boundaries and horizon mapping;
2. origin × horizon × policy aggregates;
3. exact-horizon paired contrasts;
4. uncertainty summaries for all four primary cost/service contrasts;
5. week-band summaries;
6. horizon-level qualitative-direction flags;
7. exact run provenance.

A compact result note may be committed only after the evidence run completes.

## Non-goals

This audit does not:

- change the hybrid switch;
- change conformal coverage;
- change the estimator;
- tune a horizon-specific threshold;
- select a different policy by horizon;
- modify staffing costs or capacities;
- claim population-level statistical inference from 13 synthetic origins;
- revisit the rejected clinical optimiser.
