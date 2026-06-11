# Model Card — Clinic Usage Forecasting PoC

## Intended use

Forecast daily clinic usage and estimate staffing requirements for healthcare-network planning.

## Out of scope

This PoC must not be used for patient-level prediction, clinical diagnosis, treatment decisions or triage.

## Data

Synthetic data generated to resemble clinic operations. It contains no protected health information.

## Target

Daily clinic visits by clinic.

## Main risks

- Forecast bias can lead to systematic understaffing.
- Marketing campaigns can create distribution shifts.
- Clinic-level data can be sparse.
- Special events and local outbreaks may be missing from input data.

## Monitoring recommendations

- Track WAPE and bias by clinic.
- Track residual drift after large campaigns.
- Track under-forecasting during peak demand periods.
- Recalibrate staffing buffers when service levels change.
