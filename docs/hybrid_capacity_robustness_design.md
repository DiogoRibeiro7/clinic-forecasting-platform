# Frozen hybrid capacity-robustness design

This document freezes a robustness replication of the already-selected capacity-aware hybrid clinical staffing policy before any new stress-test cell is evaluated.

The objective is not to retune the hybrid switch. It is to test whether the original qualitative cost/service frontier persists across independent stochastic realisations and deliberately tighter or looser clinic capacity.

## Frozen policy

The hybrid selector is unchanged:

\[
U^V_{c,t} \ge K_c
\Rightarrow
\text{use attended-demand clinical forecast},
\]

otherwise use the completed-visits clinical forecast.

Here \(U^V_{c,t}\) is the 90% upper split-conformal bound for completed visits and \(K_c\) is clinic daily capacity.

The 90% coverage level, forecasting models, target definitions, staffing rules and costs are not tuned in this replication.

## Simulation matrix

The robustness matrix contains exactly 12 prospectively fixed cells:

\[
\mathcal S=\{42,142,242,342\}
\]

crossed with

\[
\mathcal K=\{0.8,1.0,1.2\}.
\]

The seeds follow the deterministic sequence \(42+100j\), \(j=0,1,2,3\). Seed 42 with capacity multiplier 1.0 is the existing reference cell. The remaining 11 cells are new.

All other `SyntheticDataConfig` settings remain at their current defaults:

- start date: 2022-01-01;
- end date: 2025-12-31;
- clinics: 12;
- seasonality strength: 1.0;
- marketing strength: 1.0;
- noise level: 1.0.

No seed or capacity cell may be removed, replaced or added after results are observed.

## Capacity intervention

Capacity is perturbed **after** the synthetic latent demand path has been generated so that the experiment changes capacity pressure without simultaneously rescaling scheduled demand.

For each generated clinic-day define reconstructed attended demand

\[
A_{c,t}
=
\text{scheduled appointments}_{c,t}
-
\text{no shows}_{c,t}
-
\text{same-day cancellations}_{c,t}.
\]

For capacity multiplier \(q\in\{0.8,1.0,1.2\}\), the counterfactual clinic capacity is

\[
K_c^{(q)}
=
\max\left\{1,\left\lfloor qK_c+0.5\right\rfloor\right\}.
\]

The same adjusted capacity is written to both clinic metadata and the matching usage rows.

Completed visits are then recomputed as

\[
V_{c,t}^{(q)}=\min\{A_{c,t},K_c^{(q)}\},
\]

and capacity utilisation is recomputed as

\[
V_{c,t}^{(q)}/K_c^{(q)}.
\]

Scheduled appointments, no-shows, cancellations, marketing, calendar features and all other latent-demand drivers remain unchanged within a seed across the three capacity cells.

This intervention is a synthetic stress test, not a claim that real clinics can instantaneously scale capacity by 20%.

## Forecasting and evaluation contract

Every cell uses the same frozen benchmark configuration as the original confirmatory hybrid result:

- outer initial training: 1,095 days;
- horizon: 28 days;
- outer folds: 4;
- estimator: HGB;
- conformal coverage: 0.90;
- inner initial training: 730 days;
- inner folds: 4.

The three policies remain:

1. attended-demand-only clinical staffing;
2. completed-visits-only clinical staffing;
3. frozen capacity-aware hybrid clinical staffing.

Front-desk staffing remains based on scheduled appointments and is identical across the three clinical target policies.

The existing legacy staffing evaluator is retained for direct comparability with the original hybrid-policy evidence. This robustness study does not use the later optimiser-v2 evaluator because it is replicating the original hybrid policy experiment, not the rejected optimiser experiment.

## Primary qualitative replication criterion

For each cell, use the mean across its four outer folds on the **all-days** slice.

A cell is classified as a qualitative replication only when both strict inequalities hold:

\[
\boxed{
U_H < U_V
}
\]

and

\[
\boxed{
C_H < C_A
}
\]

where:

- \(U_H\) is hybrid unmet visits;
- \(U_V\) is completed-visits-only unmet visits;
- \(C_H\) is hybrid total cost;
- \(C_A\) is attended-demand-only total cost.

This asks whether the hybrid preserves the two directional advantages observed in the original confirmatory result: better service than completed-visits-only and lower cost than attended-demand-only.

No willingness-to-pay threshold, non-inferiority margin or weighted utility is introduced.

Report the replication status of every cell individually, plus the count of qualifying cells among all 12 and among the 11 genuinely new cells. Do not replace this with a post-hoc majority threshold.

## Secondary diagnostics

For each cell report:

- total cost and unmet visits for all three policies;
- relative hybrid-vs-completed cost and unmet-demand changes;
- relative hybrid-vs-attended cost and unmet-demand changes;
- realised censoring rate;
- hybrid capacity-pressure trigger rate;
- trigger sensitivity on realised censored days;
- trigger false-positive rate on realised uncensored days;
- censored and uncensored cost/service slices.

A secondary descriptive flag may record whether hybrid Pareto-dominates both pure policies on realised censored days, as it did in the original seed-42 reference result. This flag is not the primary replication criterion.

## Interpretation rules

This experiment is a robustness audit of a frozen synthetic policy. It does not create a new tuning loop.

- If all cells replicate qualitatively, report broad robustness over this predefined capacity perturbation range and seed set.
- If any cell fails, report the exact failing seed/capacity conditions and the direction of failure.
- Do not change the 90% conformal threshold, policy rule, cost coefficients, model family, seeds or capacity multipliers in response to failures.
- Do not automatically withdraw or promote a real-world policy from synthetic robustness results; real deployment still requires governed real-data validation.

The complete 12-cell table is the evidence. No cells may be hidden because they are inconvenient.

## Provenance

The future evidence runner must record for every cell:

- repository commit SHA;
- seed;
- capacity multiplier;
- generator configuration;
- benchmark configuration;
- Python and Poetry versions.

Machine-readable cell-level summaries and the full replication table must be uploaded as a GitHub Actions artifact. A compact result and provenance record should be committed after the confirmatory run.

## Non-goals

This design does not:

- retune or refit the hybrid switch;
- search across seeds or capacity perturbations;
- alter demand-generation strength parameters;
- revisit the rejected clinical optimiser;
- introduce new costs or service-level weights;
- claim external validity for real clinics.
