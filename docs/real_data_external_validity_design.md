# Frozen real-data external-validity bridge

This document prospectively freezes the first real-data bridge for `clinic-forecasting-platform`.

The purpose is to test whether the forecasting layer generalises from the synthetic clinic network to observed primary-care activity while keeping the limits of public data explicit. This is **not** a validation of the latent-demand hybrid staffing policy.

## External source

Use the NHS England **Appointments in General Practice, June 2026** publication and its official daily-count archive as the sole source for the first external benchmark.

Frozen source identity:

- publication: `Appointments in General Practice, June 2026`;
- publisher: NHS England;
- daily-count coverage: 2024-01-01 through 2026-06-30;
- official archive: `Appointments_GP_Daily_CSV_Jun_26.zip`;
- source geography: England;
- public-sector reuse terms: Open Government Licence attribution requirements apply.

The raw archive is not committed to Git. The acquisition step must record:

- source URL;
- retrieval timestamp in UTC;
- archive SHA-256;
- archive byte size;
- publication month;
- licence/attribution text used in derived outputs.

If the official archive changes bytes at the same URL, the benchmark must fail provenance comparison and require an explicit source-version update rather than silently consuming new bytes.

## What GPAD identifies

The external benchmark may use only quantities directly supported by the publication, including observed appointment activity and published appointment dimensions such as date, appointment status, healthcare-professional type, appointment mode and booking-to-appointment lead time where present in the downloaded files.

For the primary benchmark, aggregate to:

\[
\boxed{\text{sub-ICB} \times \text{calendar day}}
\]

and define the primary target as:

\[
Y_{g,t}=\text{observed attended GP appointments in sub-ICB }g\text{ on day }t.
\]

The adapter must retain enough status information to construct and audit, where available:

- attended appointments;
- did-not-attend appointments;
- other/unknown appointment-status counts;
- total recorded appointments.

No synthetic clinic identifier may be mapped one-to-one onto an NHS practice or sub-ICB. The external benchmark is a separate evaluation domain.

## What GPAD does not identify

The NHS England publication explicitly does not provide a reliable measure of healthcare demand or patient-facing capacity. Therefore the following synthetic estimands remain **unidentified** from GPAD alone:

- latent attended demand before capacity censoring;
- unmet visits;
- true capacity-censoring events;
- daily patient-facing slot capacity;
- the hybrid capacity-pressure switch's true-positive/false-positive behaviour;
- clinical staffing optimality or staffing cost/service effects.

The external benchmark must not infer any of those quantities by treating completed appointments, recorded slots, clinician counts, or observed utilisation as equivalent to latent demand or usable capacity.

The hybrid policy is therefore out of scope for the first GPAD benchmark.

## Minimum future operational data for latent-demand identification

A later real-policy validation requires operational data that jointly identify demand attempts and usable capacity.

At minimum, one of the following demand-side structures is required:

1. appointment requests including requests that were not immediately booked;
2. a timestamped waiting list / callback queue / triage queue;
3. booking attempts with an outcome such as booked, deferred, redirected or unfulfilled;
4. another auditable measure of patient demand attempts independent of completed activity.

And at least one defensible capacity-side structure is required:

1. patient-facing appointment slots by clinic/day and role;
2. rostered patient-facing clinical hours converted to capacity under an explicit productivity model;
3. slot-level availability with administrative/training/break blocks distinguishable from patient-facing availability;
4. another operational capacity measure whose interpretation is documented and auditable.

Without both sides, the real-data hybrid-policy estimand remains partially identified or unidentified and must be reported as such.

## Adapter contract

Add a dedicated NHS GPAD adapter rather than forcing the existing synthetic schema onto the source.

The adapter must:

1. read the official archive without mutating the raw files;
2. inventory every contained CSV and its schema;
3. normalize dates and geography codes explicitly;
4. map published appointment status values into a documented canonical status set;
5. aggregate the frozen primary target to sub-ICB × day;
6. preserve raw published dimensions needed for audit tables;
7. emit a machine-readable source/schema manifest;
8. reject duplicate semantic keys after aggregation;
9. reject negative counts;
10. report missing calendar days and geography discontinuities rather than silently imputing them.

Any upstream column-name variation must be handled through an explicit schema map stored in the repository. No fuzzy column guessing is permitted in the production adapter.

## External forecasting benchmark

The benchmark evaluates forecasting generalisation only.

### Data window

Use the full frozen daily-count window:

- start: 2024-01-01;
- end: 2026-06-30;
- 912 calendar days.

Calendar gaps in the source remain explicit. A benchmark run must record how many source dates are present globally and per geography before modelling.

### Validation design

Use:

- initial training window: 365 calendar days;
- forecast horizon: 28 days;
- step: 28 days;
- expanding window;
- all feasible non-overlapping outer origins;
- exactly **19** outer origins for a complete 912-day calendar.

If the prepared panel does not support exactly 19 global origins after the frozen calendar policy is applied, the run must fail and report the reason rather than changing the split retrospectively.

### Models

The primary model comparison is intentionally small and transparent:

1. seasonal-naive baseline using the previous 7-day seasonal value;
2. moving-average baseline already implemented in the repository;
3. global HGB model using the repository's deployment-matched recursive forecasting path.

Do not add Prophet, XGBoost, LightGBM, Nixtla, neural models or foundation models to the confirmatory external benchmark. Those can be exploratory follow-up work after the primary benchmark is recorded.

### Features

Only information available by forecast origin may be used.

Allowed feature classes:

- calendar features derived from date;
- lagged and rolling target features computed recursively without future leakage;
- stable geography identifiers encoded through the existing global-model contract where supported.

Do not use future appointment-status composition, future lead-time distribution, future mode mix or any other quantity that would not be known at forecast time.

## Primary metrics

Report by outer origin and pooled descriptively across origins:

- MAE;
- WAPE;
- RMSE;
- mean error / bias.

For pairwise model comparisons, the unit of pairing is the outer origin, not sub-ICB-day rows.

For each model-vs-seasonal-naive contrast report:

- mean paired metric difference;
- median paired difference;
- SD;
- min/max;
- positive/negative/zero origin counts;
- dominant non-zero sign consistency;
- exact two-sided sign-test p-value as a descriptive diagnostic only.

No p-value is a promotion gate.

## Horizon and geography diagnostics

Report descriptive diagnostics for:

- horizons 1 through 28;
- the frozen bands 1–7, 8–14, 15–21, 22–28;
- each sub-ICB with sufficient history;
- distribution of errors across geographies.

Do not remove poorly performing geographies after seeing results. Any geography excluded for insufficient history or schema failure must be listed before model scoring.

## Data-quality gate

Before forecasting, produce a frozen quality report with at least:

- archive checksum and file inventory;
- row count per source CSV;
- parsed date range;
- unique geography count;
- status-value inventory;
- missing-date count by geography;
- duplicate semantic-key count;
- negative-count check;
- total appointments by status;
- fraction of rows with unknown/unmapped status;
- geographies entering/leaving during the period.

The benchmark must not run if:

- dates cannot be parsed deterministically;
- semantic duplicates remain after the documented aggregation;
- negative appointment counts are present;
- required primary-target status values cannot be identified;
- source provenance is incomplete.

Other data-quality findings are reported rather than automatically hidden.

## Interpretation rules

The external benchmark can support claims of the form:

> The repository's forecasting approach generalised, or failed to generalise, to observed NHS England primary-care appointment activity under the frozen temporal benchmark.

It cannot support claims of the form:

> The hybrid latent-demand staffing policy is externally validated on NHS data.

It also cannot support claims about:

- unmet patient demand;
- capacity censoring;
- staffing efficiency;
- waiting-time reduction;
- causal operational impact.

Those require operational data with the identification structure specified above.

## Deliverables

The implementation/evidence phase must produce:

1. `source_manifest.json` with URL, checksum, retrieval timestamp, publication identity and licence attribution;
2. `schema_inventory.csv`;
3. `data_quality.csv` plus a compact quality summary;
4. prepared sub-ICB × day target data or a reproducible derivation recipe, subject to source redistribution terms;
5. `origin_boundaries.csv`;
6. `fold_scores.csv`;
7. `paired_model_contrasts.csv`;
8. `horizon_scores.csv`;
9. `geography_scores.csv`;
10. exact run provenance and environment snapshot;
11. a compact result note committed only after the frozen run completes.

## Non-goals

This phase does not:

- validate the hybrid staffing switch on real data;
- estimate latent demand from completed activity alone;
- infer capacity from observed appointment throughput;
- tune models after inspecting external results;
- select geographies post hoc;
- make causal claims;
- claim NHS endorsement or deployment;
- ingest patient-level confidential data.
