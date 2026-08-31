# Frozen clinical staffing optimiser design

This document freezes the decision-science contract before implementation or held-out comparison. It does not report an optimiser result.

## Scope

The new optimiser changes only the **clinical staffing decision rule**. The forecasting system, frozen hybrid target selector and front-desk rule are held fixed.

For each open clinic-day:

- clinical planning demand is the already-selected `hybrid_clinical_forecast` point forecast;
- front desk continues to use the scheduled-appointments point forecast and the existing deterministic staffing rule;
- the optimiser chooses integer clinician and nurse counts only;
- closed clinic-days have zero staffing and are not optimised.

This isolates the effect of replacing the current clinical headcount conversion rule with a genuine cost-minimising decision rule.

## Why the legacy cost function is not changed

`staffing_plan_cost()` is retained unchanged because the committed staffing-target and hybrid-policy evidence was produced with that evaluator. Replacing its clinician-only capacity semantics in place would silently change the meaning of historical evidence.

The optimiser will therefore introduce a separate **decision-layer v2 cost evaluator**. Both the current hybrid rule policy and the optimiser will be rescored with the same v2 evaluator in the new benchmark.

## Decision variables and bounds

For clinic-day \((c,t)\), let

\[
n_c \in \mathbb Z,\qquad n_n \in \mathbb Z
\]

be clinician and nurse headcounts.

They satisfy the existing configured bounds:

\[
m_c \le n_c \le M_c,
\qquad
m_n \le n_n \le M_n.
\]

The optimiser requires finite configured maxima. If either clinical maximum is absent, execution fails rather than inventing a new roster cap.

With current configuration:

\[
1\le n_c\le16,
\qquad
1\le n_n\le20.
\]

The finite feasible set is therefore small enough for exact enumeration; no approximate numerical optimiser or new solver dependency is required.

## Clinical service model

Let

\[
p_c=18,
\qquad
p_n=24
\]

be clinician and nurse regular daily productivities, and let \(\theta=1.2\) be the configured overtime stretch factor.

Regular role capacities are

\[
C_c=p_c n_c,
\qquad
C_n=p_n n_n.
\]

The clinical pathway requires both resources, so regular clinical capacity is

\[
\boxed{C_{\mathrm{clinical}}=\min(C_c,C_n)}.
\]

For planning demand \(d\), the maximum volume that can be served after role-specific overtime stretch is

\[
S=\min\{d,\theta C_c,\theta C_n\}.
\]

Unmet demand is

\[
U=d-S.
\]

Role-specific overtime workload is

\[
O_c=\max(S-C_c,0),
\qquad
O_n=\max(S-C_n,0),
\]

and unused regular capacity is

\[
I_c=\max(C_c-S,0),
\qquad
I_n=\max(C_n-S,0).
\]

This avoids the current clinician-only shortcut and correctly allows one role to be the binding resource while the other still has spare regular capacity.

## Frozen objective

The optimiser reuses the existing staffing cost coefficients; it introduces no new economic weight.

Let \(c_c,c_n\) be clinician and nurse day costs, \(\mu\) the overtime multiplier, \(\pi\) the unmet-visit penalty and \(\rho\) the idle penalty ratio.

The clinical objective for candidate \((n_c,n_n)\) is

\[
\begin{aligned}
L(n_c,n_n;d)
={}&c_c n_c+c_n n_n\\
&+\mu\left(c_c\frac{O_c}{p_c}+c_n\frac{O_n}{p_n}\right)\\
&+\pi U\\
&+\rho\left(c_c\frac{I_c}{p_c}+c_n\frac{I_n}{p_n}\right).
\end{aligned}
\]

The selected staffing pair is the exact minimiser over the finite feasible grid.

Ties are resolved deterministically by lexicographic minimisation of

\[
\bigl(L,\ U,\ n_c+n_n,\ n_c,\ n_n\bigr).
\]

## Front-desk treatment

Front-desk staffing is intentionally not optimised in this experiment.

The existing cost model contains no prospectively validated front-desk queue or unmet-workload penalty. Optimising front desk under only positive regular day cost would mechanically choose the minimum headcount, while introducing a new penalty would add an unregistered economic assumption.

Therefore every compared policy uses the same scheduled-appointments point forecast and existing zero-buffer front-desk staffing rule. Front-desk regular cost remains part of total cost but is identical across the primary comparator policies.

## Benchmark design

The future implementation/evidence PR must preserve the already-frozen forecasting contract:

- same synthetic generator and staffing configuration;
- same four 28-day outer fixed-origin folds;
- same HGB estimator;
- same nested training-only 90% conformal calibration;
- same frozen hybrid target-selection rule;
- no threshold or cost-weight tuning after the optimiser result is observed.

Primary policies:

1. `hybrid_rule_mean`: current zero-buffer clinician/nurse ceiling rule using the hybrid clinical point forecast;
2. `hybrid_optimizer_mean`: exact clinical optimiser using the identical hybrid clinical point forecast.

A clinical upper-bound rule may be reported as a **secondary descriptive comparator**, but it is not part of the primary optimiser-vs-rule estimand.

All policies are evaluated with the new v2 two-resource cost evaluator against realised attended demand. The front-desk plan is identical across primary policies.

## Primary outputs

Report paired outer-fold results for:

- total cost;
- regular clinical cost;
- clinician overtime cost;
- nurse overtime cost;
- understaffing cost;
- idle clinical cost;
- unmet visits;
- understaffed clinic-day rate;
- clinician-days;
- nurse-days.

Retain all/censored/uncensored diagnostic slices, but the primary deployment comparison is the all-day result.

## Promotion rule

No post-hoc willingness-to-pay or non-inferiority threshold will be invented.

The optimiser is an automatic promotion candidate only if, on the mean paired outer-fold result, it is weakly better than the current rule on both

\[
\text{total cost}
\quad\text{and}\quad
\text{unmet visits},
\]

with at least one strict improvement.

If cost and service move in opposite directions, report the trade-off and do not promote the optimiser without a separately registered utility or service-level criterion.

With four outer folds, the benchmark is evidence for this synthetic decision problem, not a population-level statistical claim.

## Non-goals

This gate does not:

- change the frozen hybrid forecasting rule;
- change legacy `staffing_plan_cost()` or reinterpret earlier evidence;
- optimise front-desk staffing;
- introduce queueing/waiting-time penalties;
- tune costs, productivity, overtime limits or roster caps;
- claim relevance to real clinics without real-data identification and validation.
