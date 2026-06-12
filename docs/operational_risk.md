# Operational risk register

A practical register for running this forecasting system in a healthcare
network. Likelihood and impact are qualitative (Low / Medium / High); the
point is the **mitigation** and **owner** columns — what is actually done and
who does it. Risks are grouped by where they bite.

Severity = how bad if it happens and goes unmitigated.

## Forecast-quality risks

| # | Risk | Likelihood | Severity | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- |
| F1 | **Systematic under-forecasting → chronic understaffing.** Bias compounds into waiting times, overtime and burnout. | Medium | High | Per-clinic bias monitoring (`monitoring.py`); conservative interval-upper-bound staffing option; bias alert triggers manual roster review. | Data team + Ops |
| F2 | **Accuracy decay after a demand regime change** (new contract, competitor closure). | Medium | Medium | WAPE-degradation + volume-shift alerts; retrain-and-recalibrate trigger on agreement. | Data team |
| F3 | **Capacity-censored peaks** under-forecast true demand on the busiest days. | High | Medium | Documented bias; prefer scheduled-appointment target for capacity planning; conservative staffing on flagged high-utilisation clinics. | Data team |
| F4 | **Horizon error growth** in recursive multi-step forecasts. | High | Low | Intervals calibrated on recursive residuals absorb it; horizon-WAPE reported (notebook 04). | Data team |
| F5 | **Cold-start clinics** (little history) forecast poorly. | Medium | Medium | Wider intervals by construction; top-down reconciliation option for allocation; manual review for first N weeks. | Data team + Ops |

## Data and input risks

| # | Risk | Likelihood | Severity | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- |
| D1 | **Bad input data** (late, malformed, duplicated) silently corrupts forecasts. | Medium | High | Data contracts (`contracts.py`) fail the batch run loudly before any forecast is produced. | Data Eng |
| D2 | **Marketing plan ≠ executed spend**, so the marketing-driven forecast is wrong. | Medium | Medium | Spend-shift monitoring; scenarios framed as plan-dependent; treat as an input fix, not a model fault. | Marketing + Data |
| D3 | **Schema/feature drift** (new clinic attributes, renamed columns). | Low | Medium | Contracts + typed pipeline; CI catches breakage before deploy. | Data Eng |

## Decision and process risks

| # | Risk | Likelihood | Severity | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- |
| P1 | **Over-trust / automation bias** — managers follow numbers without judgement. | Medium | High | Decision-support framing; human sign-off required; intervals and cost trade-offs surfaced, not just a point number. | Ops leadership |
| P2 | **Cost coefficients wrong or stale**, flipping the scenario ranking. | Medium | Medium | All coefficients in `configs/staffing.yaml`; scenarios presented as a function of penalty beliefs (notebook 06). | Finance + Ops |
| P3 | **Marketing scenarios misread as causal claims.** | Medium | Medium | Explicit "model-based what-if, not causal" framing in code, API and notebook 08. | Data team |
| P4 | **No human review of an alerting clinic** before rosters set. | Low | High | Monitoring report routed to the responsible manager; alerting clinics flagged for mandatory review. | Ops |

## Governance and compliance risks

| # | Risk | Likelihood | Severity | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- |
| G1 | **PoC deployed as-is** on real operations without revalidation. | Low | High | Model card "out-of-scope" section; synthetic-data limitations stated everywhere; deployment gated on retraining + revalidation on governed data. | Leadership |
| G2 | **Demand data sent to external services** (e.g. TimeGPT) without review. | Low | Medium | TimeGPT is optional, off by default, key-gated; governance note in code and notebook 05. | Data team + Compliance |
| G3 | **Reproducibility loss** (cannot recreate a past forecast). | Low | Medium | Seeded generation, committed lock file, model registry records training window + metrics + artefact paths per run. | Data Eng |

## Escalation summary

- **Stop the line** (do not publish forecasts): D1 contract failure, or any
  forecast the monitoring layer flags across multiple checks for a
  high-volume clinic.
- **Retrain + recalibrate:** F2/F5 triggers — volume shift with WAPE
  degradation, or persistent bias across two windows.
- **Fix inputs, not the model:** D2 marketing-spend shifts.
- **Human-review-then-proceed:** single-window quality alerts with no input
  shift (likely a demand episode — do not churn the model on noise).
