# Serving promotion decision

## Decision

The versioned role-specific `/v2` API is the primary serving surface for forecast and staffing outputs.

The legacy unversioned completed-visits routes remain available for backward compatibility, but they are no longer the operational default for new integrations or demo workflows.

## Primary path

Generate the primary serving artifacts with:

```bash
make batch-forecast
```

or directly:

```bash
poetry run python scripts/run_role_specific_batch.py --horizon 28
```

These artifacts are served through:

- `GET /v2/contract`
- `GET /v2/health`
- `GET /v2/forecasts`
- `GET /v2/staffing`
- `GET /v2/hybrid-monitoring`

The `/v2` contract is versioned as `2.0.0` and returned in the `X-Clinic-Forecast-Contract-Version` response header.

## Why `/v2` is promoted

The role-specific path preserves the distinctions that matter for the decision layer:

- attended demand for the clinical target under forecast-time capacity pressure;
- completed visits when the frozen hybrid rule does not trigger;
- scheduled appointments for front-desk workload;
- calibrated intervals for all three targets;
- capacity pressure and the selected hybrid target;
- role-specific staffing recommendations;
- hybrid switch-use monitoring.

The legacy path exposes only completed-visits forecasts and cannot represent the promoted hybrid decision policy without losing target semantics.

## Compatibility policy

The legacy commands remain available:

```bash
make legacy-batch-forecast
make docker-legacy-batch
```

They continue to populate the unversioned `/forecasts` and `/staffing` routes. Existing consumers are therefore not broken by this promotion.

New integrations should not depend on the legacy routes. Any future breaking change to the promoted serving surface requires a new contract version rather than silently changing `/v2` response semantics.

## Scope boundary

This is an engineering promotion, not new scientific evidence. It does not alter the frozen forecasting benchmarks, the hybrid switching rule, the NHS confirmatory result, or the exploratory NHS origin-regime analysis.

The marketing scenario endpoint remains on the legacy unversioned surface because it has a separate model-based, non-causal contract and has not yet been designed as part of `/v2`.
