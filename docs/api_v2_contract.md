# Versioned hybrid-serving API contract

The existing unversioned API remains the compatibility surface for the legacy completed-visits batch outputs. Its response models and file locations are unchanged.

The hybrid role-specific outputs are served only under `/v2`.

## Routes

- `GET /v2/health` reports availability of role-specific forecast, staffing and hybrid-monitoring artefacts.
- `GET /v2/forecasts` returns attended-demand, completed-visits and scheduled-appointments forecasts with conformal intervals, known clinic capacity, the frozen capacity-pressure indicator and the selected hybrid clinical forecast.
- `GET /v2/staffing` returns the hybrid-target decision together with mean and upper staffing plans.
- `GET /v2/hybrid-monitoring` returns the descriptive switch-use summary produced by the role-specific batch pipeline.

The hybrid rule is not recomputed inside the API. The API serves the immutable decision artefacts written by the batch pipeline, keeping model fitting, conformal calibration and target selection outside request handling.

The unversioned `/forecasts`, `/staffing`, `/health` and marketing-scenario endpoints continue to read the legacy `outputs/forecasts` and `outputs/staffing` paths. No silent semantic migration is performed.
