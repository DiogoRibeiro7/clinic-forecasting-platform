# Production Readiness Boundary

This repository is a **portfolio-grade proof of concept**, not a clinically governed production deployment. It deliberately contains production-shaped engineering so that forecasting, uncertainty, decision support, monitoring, retraining rehearsal, immutable serving and auditability can be reviewed end to end.

Production-shaped code is not, by itself, evidence of production readiness.

This review classifies each requirement using exactly three states:

- **Implemented in this portfolio** — the repository contains the capability and it is testable from committed code, configuration, evidence or workflows.
- **Requires deployment integration** — the capability depends on an organisation's runtime, security, ownership, approval or service-management environment and cannot be truthfully completed inside this repository alone.
- **Requires governed clinical evidence** — the claim depends on operational data or prospective clinical/operational validation that the synthetic system and public NHS GPAD data cannot supply.

## Executive boundary

The repository is strong evidence for fixed-origin recursive forecasting, split-conformal uncertainty, frozen hybrid decision logic, transparent staffing calculations, reproducible benchmark evidence, immutable serving artefacts and source/model/config fingerprints, descriptive monitoring, deterministic retraining rehearsal, and human-review-oriented API outputs.

It is **not** evidence for lawful production processing of identifiable or confidential healthcare data, validated patient-facing capacity or latent demand, approved automated staffing changes, an operational SLO/on-call/incident process, production authentication or secret rotation, or prospective clinical benefit from the synthetic staffing policy.

## Readiness matrix

| Area | Requirement | Status | Repository evidence | What is still required |
| --- | --- | --- | --- | --- |
| Data governance | Aggregate typed input contracts and fail-closed validation | **Implemented in this portfolio** | src/clinic_forecast/contracts.py and NHS GPAD adapter/quality workflows | Production source owners must accept and operate the contracts. |
| Data governance | Data ownership and named accountable source owner | **Requires deployment integration** | Synthetic generator and public GPAD provenance identify technical sources, not organisational ownership | Named business/data owners, stewardship responsibilities and escalation path. |
| Data governance | Privacy review and lawful basis | **Requires deployment integration** | Model card explicitly excludes patient-level data; repository contains synthetic aggregate data | DPIA/privacy review, lawful basis, minimisation and purpose limitation for real data. |
| Data governance | Retention, deletion and archival policy | **Requires deployment integration** | Immutable local artefacts demonstrate retention mechanics only | Organisation-approved retention schedule and deletion/archive controls. |
| Data governance | Real demand-attempt and capacity identification | **Requires governed clinical evidence** | Roadmap explicitly blocks real latent-demand/capacity claims | Governed operational data identifying demand attempts, capacity, backlog/waitlist and outcomes. |
| Access control | API authentication and authorisation | **Requires deployment integration** | FastAPI exposes read-only contracts but no production identity layer | SSO/service identity, RBAC/ABAC, least-privilege scopes and access review. |
| Access control | Filesystem/storage permissions | **Requires deployment integration** | Local immutable run bundles and manifest verification exist | Managed storage, service accounts, encryption/access policies and separation of duties. |
| Secrets | Secrets absent from committed configuration | **Implemented in this portfolio** | .env.example; optional external models are key-gated and off by default | — |
| Secrets | Production secret storage and rotation | **Requires deployment integration** | No cloud secret manager is assumed | Secret manager, rotation policy, audit trail and break-glass procedure. |
| Source contracts | Typed schema and validation ownership in code | **Implemented in this portfolio** | Contracts, validation modules, GPAD schema/quality gates | — |
| Source contracts | Schema-change approval and producer/consumer ownership | **Requires deployment integration** | CI detects code/schema breakage but cannot govern upstream systems | Named producer/consumer owners, compatibility policy and change-notification process. |
| Forecast validation | Deployment-matched fixed-origin recursive evaluation | **Implemented in this portfolio** | backtesting.py, recursive benchmarks, committed evidence | — |
| Forecast validation | Real operational revalidation before deployment | **Requires governed clinical evidence** | Public NHS result validates observed attended appointment activity only | Governed target data, agreed estimands, acceptance criteria and independent validation period. |
| Uncertainty | Split-conformal intervals under recursive evaluation | **Implemented in this portfolio** | intervals.py and interval coverage audit workflow | — |
| Uncertainty | Production calibration under real drift/regime change | **Requires governed clinical evidence** | Synthetic/GPAD evidence cannot establish future operational coverage | Prospective coverage monitoring and recalibration policy on real deployment data. |
| Staffing policy | Frozen transparent hybrid rule | **Implemented in this portfolio** | hybrid_policy.py plus confirmatory and robustness evidence | — |
| Staffing policy | Real latent-demand/capacity staffing benefit | **Requires governed clinical evidence** | Synthetic evidence only; GPAD cannot identify these quantities | Prospective held-out operational validation with defensible demand/capacity outcomes. |
| Staffing policy | Human approval of staffing recommendations | **Requires deployment integration** | Model card states decision support and human sign-off | Named approver roles, review SLA, override capture and escalation process. |
| Model promotion | Versioned local registry and immutable model/run binding | **Implemented in this portfolio** | registry.py, serving_snapshot.py, serving_provenance.py | — |
| Model promotion | Approval authority for promotion/rollback | **Requires deployment integration** | Repository records versions but has no organisational approver | Named model owner, independent reviewer, approval record and rollback authority. |
| Rollback | Immutable prior serving runs are retained and identifiable | **Implemented in this portfolio** | role_specific/runs/<run_id>, latest_manifest.json and SHA-256 verification | — |
| Rollback | Operational rollback runbook and deployment control | **Requires deployment integration** | Local artefacts make rollback technically possible, not operationally governed | Deployment mechanism, rollback decision owner, test cadence and recovery objective. |
| Retraining | Deterministic scheduled retraining rehearsal | **Implemented in this portfolio** | .github/workflows/scheduled_retraining.yml and retraining.py | — |
| Retraining | Automatic promotion after retraining | **Requires deployment integration** | Rehearsal verifies coherent artefacts; it does not approve clinical suitability | Approval gate, champion/challenger policy, evidence review and controlled deployment. |
| Change control | Code review, CI and benchmark evidence gates | **Implemented in this portfolio** | CI, evidence workflows and immutable benchmark outputs | — |
| Change control | Organisational change record and release approval | **Requires deployment integration** | Git history/PRs are engineering evidence only | Change-management ticketing, approvers, release window and deployment record. |
| Monitoring | Forecast quality, bias, drift and interval monitoring logic | **Implemented in this portfolio** | monitoring.py, monitoring config and model card | — |
| Monitoring | Hybrid switch-use monitoring | **Implemented in this portfolio** | hybrid_monitoring.py and /v2/hybrid-monitoring | — |
| Monitoring | Real post-horizon switch precision/recall | **Requires governed clinical evidence** | Roadmap explicitly blocks this until realised outcomes exist | Real capacity/demand outcomes after each served horizon. |
| SLOs | Health endpoint and fail-closed serving checks | **Implemented in this portfolio** | /health, /v2/health and manifest fingerprint checks | — |
| SLOs | Availability/latency/freshness SLOs | **Requires deployment integration** | No production traffic or infrastructure exists | SLO definitions, measurement source, alert thresholds and error budget. |
| Incident response | Technical failures surface loudly | **Implemented in this portfolio** | Contracts and serving provenance fail closed | — |
| Incident response | On-call ownership and incident-management process | **Requires deployment integration** | No organisational service-management layer exists | On-call rota, severity model, communications, incident log and post-incident review. |
| Security | Dependency pinning/lockfile and CI checks | **Implemented in this portfolio** | poetry.lock, Dependabot and CI | — |
| Security | Vulnerability-management SLA and security review | **Requires deployment integration** | Dependency updates exist, but no production security function is represented | Security owner, vulnerability SLA, scanning policy, threat model and review cadence. |
| Security | Network boundary, TLS, WAF/rate limiting | **Requires deployment integration** | Local FastAPI/Docker demo only | Managed ingress, TLS termination, rate limiting, network policy and abuse controls. |
| Auditability | Source revision, config, inputs, models and outputs fingerprinted | **Implemented in this portfolio** | Serving provenance manifest and immutable run snapshots | — |
| Auditability | Central audit-log retention and access review | **Requires deployment integration** | Local manifests are not a central audit system | Immutable audit sink, retention policy, access controls and reviewer process. |
| Serving | Batch/serving separation and read-only API | **Implemented in this portfolio** | Architecture docs and /v2 immutable serving contract | — |
| Serving | Production deployment topology and HA | **Requires deployment integration** | Docker image is a demo packaging boundary | Deployment platform, scaling, redundancy, backup and disaster recovery. |
| Clinical evidence | Public GPAD external-validity result for observed attended activity | **Implemented in this portfolio** | Frozen NHS confirmatory benchmark | — |
| Clinical evidence | Evidence for real unmet demand, capacity censoring and staffing effects | **Requires governed clinical evidence** | Synthetic decision science only | Governed operational outcomes and prospective validation. |
| Human factors | Recommendations expose target, capacity pressure and uncertainty | **Implemented in this portfolio** | /v2/forecasts, /v2/staffing and model card | — |
| Human factors | Usability, override behaviour and automation-bias evaluation | **Requires governed clinical evidence** | Human review is specified but not studied in real operations | Prospective user research, override logging and safety/usability review. |

## Repository-wide readiness review

### Implemented strengths

The repository already demonstrates several capabilities worth preserving in a real deployment:

1. Forecasting evaluation matches deployment: the full horizon is forecast from one origin and realised holdout targets are not fed back into recursive lag features.
2. Uncertainty is tied to the same forecast mechanism: conformal calibration uses recursive rolling-fold residuals.
3. Decision evidence is separated from forecast evidence: synthetic staffing claims are not conflated with the NHS GPAD result.
4. The hybrid switch was prospectively frozen before confirmatory evaluation.
5. Serving is read-only and immutable: /v2 resolves a manifest-selected run and validates file identity before serving.
6. Model/run provenance is explicit: source revision, config, inputs, registry versions and output artefacts are fingerprinted.
7. Retraining is rehearsed without automatic promotion.
8. Human review is part of the documented decision contract.

### Deployment integration gaps

The repository should not attempt to simulate these with more local code:

- identity, authentication and role-based access;
- production storage permissions and encryption controls;
- secret management and rotation;
- deployment promotion and rollback authority;
- SLOs, incident response and on-call ownership;
- schema-change governance across upstream producers;
- security review, vulnerability SLAs and network controls;
- central audit-log retention and access reviews;
- formal release/change-management records.

These are organisational/runtime integrations. Their absence is not a modelling defect; claiming they are solved by a local PoC would be misleading.

### Governed-evidence gaps

The following claims remain scientifically blocked:

- latent demand and unmet demand in a real clinic network;
- usable patient-facing clinical capacity;
- real capacity censoring;
- causal or prospective staffing-policy benefit;
- waiting-time or queue-pressure impact;
- realised hybrid-switch precision/recall;
- clinical/operational safety of model-assisted staffing decisions;
- human-factors performance under real managerial workflows.

Public NHS GPAD validates forecasting of observed attended appointment activity. It cannot identify those quantities.

## Executable local portfolio check

The repository includes a narrow executable check for capabilities that can be
proven locally from persisted artefacts:

```bash
make readiness-check
```

or:

```bash
poetry run python scripts/verify_portfolio_readiness.py --output-dir outputs
```

The check verifies:

- a valid latest role-specific serving manifest;
- SHA-256/size identity of immutable forecast, staffing and monitoring artefacts;
- frozen v2 schema compatibility for all three artefacts;
- the exact attended-demand, completed-visits and scheduled-appointments model bindings;
- registry-record fingerprints, serving-run IDs and configuration hashes;
- the current contract version, source revision, run ID and model versions.

A successful result is labelled `portfolio_ready`. That label means only that
the repository-controlled serving contract is internally coherent.

It does **not** validate authentication, privacy, lawful basis, secret handling,
network security, SLOs, incident response, deployment infrastructure, human
factors, real capacity/latent demand, or clinical/staffing effectiveness. Those
remain in the deployment-integration and governed-evidence categories above.

## Promotion boundary

A real deployment should not promote this repository directly.

At minimum, promotion would require governed source data and ownership, privacy/security review, production source contracts, real operational validation against agreed estimands, documented model approval and rollback authority, monitored SLOs and incident ownership, retraining/change-control approval, and recorded human-review responsibilities.

Until those conditions exist, the correct description is:

> **Production-shaped forecasting and decision-support portfolio with explicit evidence and governance boundaries — not a clinically validated production service.**
