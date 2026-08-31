# Latent attended demand and capacity censoring

The original proof of concept used completed visits as the primary forecast target. That is appropriate for describing observed throughput, but it is not the cleanest target for staffing decisions because completed visits are mechanically capped by clinic capacity.

The role-specific path makes the demand funnel explicit:

```text
scheduled appointments
        ↓ no-shows / cancellations
attended demand before capacity
        ↓ clinic capacity
completed visits
        + unmet demand
```

The synthetic data already contains every component needed to reconstruct the pre-capacity quantity without inventing a new stochastic variable:

\[
D^{attended}_{c,t}
=
S_{c,t}-N_{c,t}-C_{c,t},
\]

where \(S\) is scheduled appointments, \(N\) no-shows and \(C\) same-day cancellations. Observed visits satisfy

\[
V_{c,t}\le D^{attended}_{c,t},
\]

and the hidden demand created by the capacity constraint is

\[
U_{c,t}=D^{attended}_{c,t}-V_{c,t}\ge0.
\]

## Decision targets

The new batch path uses different targets for different operational roles:

- clinicians and nurses: **attended demand before capacity**;
- front desk: **scheduled appointments**;
- completed visits: retained as an observed throughput and monitoring outcome.

This prevents an existing capacity ceiling from becoming a self-fulfilling target for future clinical staffing.

## Forecast information set

Both role-specific models use the same fixed-origin recursive contract introduced in the forecasting-validity correction. Same-day outcomes such as visits, no-shows, cancellations, attended demand and capacity-censoring indicators are removed from the contemporaneous feature set. Only historical target values plus information genuinely available at the origin or planned for the horizon may enter prediction.

## Scope

This is deliberately a synthetic-data identification improvement. In a real clinic network, pre-capacity attended demand may not be directly observed and would require a defensible operational proxy, queue/turn-away data, or a censoring model. The repository does not claim otherwise.
