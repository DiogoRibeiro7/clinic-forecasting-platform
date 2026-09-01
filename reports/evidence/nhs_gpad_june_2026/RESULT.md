# NHS GPAD June 2026 source quality result

This note records the successful discovery/data-quality run for the frozen NHS England **Appointments in General Practice, June 2026** daily archive. It is a source-quality result only. No external forecasting model or staffing-policy result is reported here.

## Frozen source

- Archive: `Appointments_GP_Daily_CSV_Jun_26.zip`
- Observed SHA-256: `c5092aebe42158b2cdad5552b66e5f5e275bb07dbed2bd337dffd22178035c7f`
- Archive bytes: `54,713,507`
- Retrieval timestamp: `2026-09-01T06:56:20Z`
- Workflow run: `33479756588`
- Artifact: `9789483852`

The observed checksum is now locked in `config/nhs_gpad_june_2026.json`. Future byte changes at the frozen URL must fail provenance validation.

## Schema result

The archive contains 31 CSV files:

- 30 monthly daily appointment files were recognized by the explicit schema map;
- 1 coverage file (`APPOINTMENTS_GP_COVERAGE.csv`) was correctly not treated as a daily appointment file.

All 30 daily files use one resolved schema:

- date: `Appointment_Date`;
- status: `APPT_STATUS`;
- count: `COUNT_OF_APPOINTMENTS`;
- sub-ICB code: `SUB_ICB_LOCATION_CODE`;
- sub-ICB name: `SUB_ICB_LOCATION_NAME`;
- HCP type: `HCP_TYPE`;
- booking lead time: `TIME_BETWEEN_BOOK_AND_APPT`;
- ICB code: `ICB_ONS_CODE`;
- region code: `REGION_ONS_CODE`.

The archive uses compact dates such as `01APR2024`, represented by the explicitly accepted format `%d%b%Y`.

## Appointment-status result

The only observed status values are:

- `Attended`;
- `DNA`;
- `Unknown`.

All map explicitly to the canonical status set. The unmapped-status appointment fraction is exactly `0.0`.

Totals across the frozen source window are:

- attended: `838,269,788` appointments;
- did not attend: `40,167,842` appointments;
- unknown: `56,657,240` appointments.

## Prepared attended-activity panel

The attended sub-ICB × day derivation contains:

- date range: `2024-01-01` through `2026-06-30`;
- 106 unique sub-ICB codes;
- 87,883 observed sub-ICB/day rows;
- zero negative appointment counts;
- zero duplicate sub-ICB/day semantic keys.

The source is therefore suitable for the frozen **observed-activity forecasting** bridge, subject to an explicit calendar-gap policy before modelling.

## Calendar-gap finding

Only 8 of 106 sub-ICBs have an attended row on every calendar day in the frozen window. Across all sub-ICBs, the median number of missing calendar days is 78 and the maximum is 269.

These gaps are retained as missing observations. They are **not** converted to zero appointments in this source-quality phase. A forecasting benchmark must freeze how incomplete geography calendars are handled before any model result is observed.

## Identification boundary

This successful source-quality result does not change the external-validity boundary. GPAD identifies observed appointment activity, but it does not identify latent patient demand, usable patient-facing capacity, unmet demand, capacity censoring, staffing effects, or the hybrid capacity-pressure switch's real-world accuracy.
