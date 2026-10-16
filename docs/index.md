# Clinic Forecasting Platform

A portfolio-grade proof of concept for clinic demand forecasting, uncertainty quantification and staffing decision support.

The repository is organised around a decision chain rather than a model leaderboard:

```text
validated clinic data
→ fixed-origin forecasts
→ calibrated uncertainty
→ demand-target selection
→ staffing decisions
→ cost / unmet-demand evaluation
→ monitoring and serving
```

## Start here

- Use the [10-minute demo guide](demo_guide.md) for a compact walkthrough.
- Read the [evaluation strategy](evaluation_strategy.md) for the fixed-origin and conformal-calibration contract.
- Read the [hybrid policy](hybrid_policy.md) for the prospectively frozen staffing target switch.
- Read the [architecture](architecture.md) and [API v2 contract](api_v2_contract.md) for immutable serving and provenance.
- Read [production readiness](production_readiness.md) before interpreting operational engineering as deployment readiness.

## Evidence boundary

The repository combines three evidence layers that must remain distinct:

1. synthetic forecasting and staffing decision evidence;
2. NHS GPAD external-validity evidence for observed attended appointment activity;
3. operational and serving engineering.

Public GPAD does not identify latent demand, usable capacity, waiting pressure, unmet demand or causal staffing-policy effects. Those claims remain blocked until governed operational data exist.

## Production boundary

This project is production-shaped, but it is not a clinically validated production deployment. CI, immutable serving artefacts, scheduled retraining rehearsals, monitoring and documentation publication do not change that boundary.

The authoritative classification of what is implemented, what requires deployment integration and what requires governed clinical evidence is maintained in [production readiness](production_readiness.md).
