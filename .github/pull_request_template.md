## Summary

<!-- What changed and why? -->

## Change classification

- [ ] Engineering / maintenance only
- [ ] Forecasting / evaluation logic
- [ ] Staffing / decision logic
- [ ] Data contract / validation
- [ ] /v2 serving / provenance
- [ ] Monitoring / retraining
- [ ] Documentation / governance
- [ ] Research / evidence

## Evidence and decision boundaries

- [ ] No frozen benchmark or confirmatory evidence changes.
- [ ] If evidence changes, the affected evidence and prospective evaluation contract are described below.
- [ ] NHS GPAD claims remain limited to observed attended appointment activity.
- [ ] Synthetic staffing / latent-demand evidence is not presented as real-clinic evidence.
- [ ] No post-hoc retuning of the frozen hybrid rule or rejected optimiser was introduced.

Evidence impact:

<!-- "None" or describe exactly what evidence changes and why. -->

## Serving and compatibility

- [ ] No /v2 contract change.
- [ ] If /v2 changes, contract-version implications are documented.
- [ ] Immutable serving provenance / manifest semantics remain valid or are explicitly migrated.

Compatibility notes:

<!-- "None" or describe. -->

## Production-readiness boundary

- [ ] This PR does not imply that production-shaped code is clinical deployment readiness.
- [ ] Any deployment-integration requirement is documented rather than simulated locally.
- [ ] Any governed-clinical-evidence requirement remains blocked unless new governed evidence is supplied.

## Validation

- [ ] `make lint`
- [ ] `make test`
- [ ] Relevant notebook / evidence workflow checks
- [ ] `make readiness-check` when role-specific serving artefacts are affected
- [ ] `make release-check` when release metadata is affected

## Security and data

- [ ] No secrets are committed.
- [ ] No patient-level or confidential healthcare data are included.
- [ ] Potential security vulnerabilities were not disclosed in public PR text beyond what is safe to publish.
