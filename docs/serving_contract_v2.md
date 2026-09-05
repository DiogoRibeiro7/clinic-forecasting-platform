# Serving contract v2

The `/v2` API routes expose the role-specific forecasting and staffing artefacts. This contract is intentionally separate from the unversioned legacy completed-visits API.

## Contract identity

- contract version: `2.0.0`
- response header: `X-Clinic-Forecast-Contract-Version`
- discovery endpoint: `GET /v2/contract`

Every successful `/v2` response includes the contract-version header. The discovery endpoint publishes the required artifact columns for forecasts, staffing and hybrid monitoring.

## Compatibility rule

The body shape of existing `/v2/forecasts`, `/v2/staffing`, `/v2/health` and `/v2/hybrid-monitoring` responses is preserved. Contract identity is added through the response header and the separate discovery endpoint rather than by wrapping existing payloads.

A future incompatible response-schema change requires a new contract version and, when necessary, a new route namespace rather than silently changing the meaning of `v2`.

## Fail-closed artifact validation

Before serving a role-specific artifact, the API validates that the CSV contains the required columns for contract `2.0.0`.

If a required column is missing, the endpoint returns HTTP `503` with a controlled contract-incompatibility message. It does not continue with partial data and does not expose an internal `KeyError` as an HTTP `500`.

The required fields are defined centrally in `src/clinic_forecast/api/contract.py` and surfaced by `GET /v2/contract`.

## Forecast contract

The forecast artifact must contain, at minimum:

- clinic/date/open status and daily capacity;
- attended-demand point and interval forecasts;
- completed-visits point and interval forecasts;
- scheduled-demand point and interval forecasts;
- capacity-pressure indicator;
- selected hybrid target;
- selected clinical point forecast and upper interval.

These fields describe the current role-specific synthetic decision path. They do not make a claim that latent demand or usable capacity has been identified in NHS GPAD data.

## Staffing contract

The staffing artifact must contain, at minimum:

- clinic/date and daily capacity;
- capacity-pressure indicator and selected hybrid target;
- mean-plan clinicians, nurses and front-desk recommendations;
- upper-plan clinicians, nurses and front-desk recommendations.

## Hybrid-monitoring contract

The monitoring artifact must contain, at minimum:

- aggregation level and group;
- open-day count;
- capacity-pressure count and rate;
- attended-demand-selection count and rate;
- mean completed-upper-to-capacity ratio.

This monitoring remains descriptive. It is not evidence that the hybrid policy is externally validated on NHS staffing outcomes.
