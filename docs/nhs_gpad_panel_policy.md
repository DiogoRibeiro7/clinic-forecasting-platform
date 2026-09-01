# Frozen NHS GPAD panel policy

This note freezes the calendar and geography policy for the first NHS England GPAD confirmatory forecasting benchmark. It is downstream of the locked June 2026 source and the hardened calendar-support audit. No forecast scores were inspected when this policy was chosen.

## Evidence basis

The frozen NHS GPAD archive has SHA-256:

`c5092aebe42158b2cdad5552b66e5f5e275bb07dbed2bd337dffd22178035c7f`

The hardened calendar-support evidence is workflow run `33504870013`, artifact `9799202494`.

Across the frozen period 2024-01-01 through 2026-06-30:

- 106 sub-ICBs are represented in the coverage table;
- 3,180 sub-ICB-month coverage rows are present;
- 1,867 sub-ICB-months have both complete practice coverage and complete registered-patient coverage;
- 31 sub-ICBs have complete practice and patient coverage in all 30 frozen months;
- the source contains zero explicit zero-count rows.

The source therefore behaves as a sparse positive-count table: a missing row cannot be interpreted as zero until publication coverage has first been established.

## Confirmatory geography set

The primary benchmark uses only the 31 sub-ICBs whose practice and registered-patient coverage are complete in every frozen month. The exact codes are stored in `config/nhs_gpad_panel_policy.json` and are immutable for the confirmatory run.

The remaining 75 sub-ICBs remain part of source-quality and coverage reporting but are excluded from confirmatory forecast scoring. They must not be reintroduced after model performance is observed.

This produces a complete panel of

\[
31 \times 912 = 28{,}272
\]

sub-ICB-day observations.

## Zero rule

Within the 31 prospectively eligible sub-ICBs:

1. if an `Attended` row is published, use its published attended appointment count;
2. if the geography-day contains only other appointment statuses, set observed attended appointments to zero;
3. if the geography-day contains no published rows, set observed attended appointments to zero.

The third rule is permitted only because the geography is already restricted to complete practice and patient coverage for the corresponding month and because the frozen archive contains no explicit zero-count rows. It is a statement about **observed attended activity in the published GPAD table**, not latent demand or capacity.

Within the eligible panel the hardened audit observed:

- 25,095 `attended_present` geography-days;
- 478 `other_status_only` geography-days;
- 2,699 `no_published_rows` geography-days.

No zero-filling is permitted for the 75 incomplete-coverage sub-ICBs in the confirmatory benchmark.

## Validation origins

The temporal design remains the previously frozen expanding-window benchmark:

- 365 initial training days;
- 28-day forecast horizon;
- 28-day step;
- 19 non-overlapping outer origins.

All exact boundaries are stored in `config/nhs_gpad_panel_policy.json`. The first test interval is 2024-12-31 through 2025-01-27 and the nineteenth is 2026-05-19 through 2026-06-15.

The final 15 source days after the nineteenth 28-day test window remain unused by the confirmatory outer-origin design. They must not be converted into an additional shorter fold.

## Interpretation boundary

The prepared panel identifies only observed attended GP appointment activity. Zero-filled rows do **not** identify:

- latent appointment demand;
- failed booking attempts;
- unmet demand;
- patient-facing capacity;
- capacity censoring;
- staffing optimality;
- causal operational effects.

The hybrid staffing policy therefore remains outside the scope of this external benchmark.

## Freeze rule

Any future change to the eligible geography list, zero rule, source checksum, or outer-origin boundaries requires an explicit new design version before model scores are inspected. The first confirmatory NHS forecasting run must consume this frozen policy unchanged.
