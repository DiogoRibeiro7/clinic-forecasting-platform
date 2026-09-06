# Versioned hybrid-serving API contract

The existing unversioned API remains the compatibility surface for the legacy completed-visits batch outputs. Its response models and file locations are unchanged.

The hybrid role-specific outputs are served only under `/v2`.

## Routes

- `GET /v2/health` reports availability of role-specific forecast, staffing and hybrid-monitoring artefacts.
- `GET /v2/forecasts` returns attended-demand, completed-visits and scheduled-appointments forecasts with conformal intervals, known clinic capacity, the frozen capacity-pressure indicator and the selected hybrid clinical forecast.
- `GET /v2/staffing` returns the hybrid-target decision together with mean and upper staffing plans.
- `GET /v2/hybrid-monitoring` returns the descriptive switch-use summary produced by the role-specific batch pipeline.
- `GET /v2/provenance` returns the exact serving-run identity, source revision, configuration hash, input fingerprints, target-model registry versions and immutable output fingerprints for the current role-specific run.

## Contract and run identity

Successful `/v2` responses include `X-Clinic-Forecast-Contract-Version: 2.0.0`.

When a provenance manifest exists, responses that serve role-specific artefacts also include `X-Clinic-Forecast-Run-Id`. That identifier names an immutable bundle under `outputs/role_specific/runs/<run_id>/` containing the forecast, staffing, monitoring and manifest files for one completed batch run.

The batch CLI still writes `latest.csv` aliases for local compatibility, but a provenance-enabled `/v2` request does not trust those mutable aliases. It resolves the immutable files named by `outputs/role_specific/latest_manifest.json` and verifies each file's size and SHA-256 before serving it. A path escape, missing file or fingerprint mismatch fails closed with HTTP 503.

The manifest records:

- the serving run ID and creation timestamp;
- forecast origin and source-code revision;
- a canonical SHA-256 of the operational batch configuration;
- SHA-256 and size for the processed usage and clinic-metadata inputs, plus generation/staffing configuration when present;
- the exact registry name and version for the attended-demand, completed-visits and scheduled-appointments target models;
- SHA-256 and size for each registry record and each immutable serving artefact.

A newly registered model version may be bound to only one serving run. A same-origin rerun therefore creates fresh registry versions and a new run ID instead of overwriting the provenance of an earlier run.

For local outputs created before serving provenance was introduced, `/v2/forecasts`, `/v2/staffing` and `/v2/hybrid-monitoring` retain the previous `latest.csv` fallback. `GET /v2/provenance` requires a provenance-enabled run and returns HTTP 503 when no manifest is available.

## Request-time boundary

The hybrid rule is not recomputed inside the API. The API serves decision artefacts written by the batch pipeline, keeping model fitting, conformal calibration and target selection outside request handling.

The unversioned `/forecasts`, `/staffing`, `/health` and marketing-scenario endpoints continue to read the legacy `outputs/forecasts` and `outputs/staffing` paths. No silent semantic migration is performed.
