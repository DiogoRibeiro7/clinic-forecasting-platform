# Changelog

All notable changes to this project are documented here.

The format follows Keep a Changelog conventions. This repository does not use
this file to imply that a GitHub release or package publication has already
occurred; release publication remains an explicit manual action.

## Unreleased

### Changed

- Keep package, FastAPI and release metadata under one version contract.
- Add explicit production-readiness and evidence-boundary governance checks.
- Add executable portfolio serving-readiness verification.

## 0.3.0

This version represents the current portfolio state after the forecasting,
decision-science, NHS GPAD external-validity, immutable serving-provenance and
production-readiness work converged.

### Added

- fixed-origin recursive multi-model forecasting benchmarks;
- split-conformal uncertainty and coverage audits;
- role-specific attended/completed/scheduled demand forecasting;
- prospectively frozen capacity-aware hybrid staffing policy;
- paired target, staffing and hybrid-policy evidence;
- NHS England GPAD external-validity benchmark and quality gates;
- immutable role-specific serving snapshots and provenance manifests;
- versioned read-only /v2 API contract and provenance endpoint;
- scheduled retraining rehearsal and optional-model-stack integration workflow;
- production-readiness boundary and governance regression checks;
- executable local portfolio readiness verification.

### Evidence boundary

- Synthetic staffing-policy evidence remains distinct from the NHS forecasting
  result.
- Public GPAD supports forecasting claims about observed attended appointment
  activity only.
- Real latent demand, capacity, unmet demand and staffing-policy benefit remain
  blocked pending governed operational evidence.
- Production-shaped engineering does not imply clinical deployment readiness.
