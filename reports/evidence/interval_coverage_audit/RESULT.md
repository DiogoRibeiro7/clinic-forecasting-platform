# Conformal interval coverage audit result

## Evidence identity

This note records the first successful post-merge run of the frozen prequential conformal-coverage audit introduced by PR #43.

- implementation merge commit: `6f76b2b9f92e466442d9b407e91d97e5ba032591`
- workflow run: `33876556996`
- companion post-merge CI run: `33876556768`
- artifact id: `9938096892`
- artifact digest: `sha256:5a156e047c715589214674434b5c50cfbc87b8673cfd87c96c1f986a05792cec`
- synthetic seed: `42`
- estimator: global HGB
- nominal coverage: `90%`
- outer folds: `8`
- initial calibration folds: `4`
- held-out evaluation folds: `4`
- forecast horizon: `28` days
- calibration/evaluation mode: fixed-origin recursive, prequential, open clinic-days only
- clinics: `12`

The companion post-merge CI run and the dedicated coverage workflow both completed successfully on the exact implementation merge commit.

## Primary estimand

The uncertainty estimand is **open clinic-days only**.

Closed clinic-days are deterministic zeros in the serving contract and are therefore not used to calibrate or score the primary conformal coverage metric. They remain in the audit evidence only to verify that the served point forecast and both interval bounds are exactly zero.

This distinction prevents deterministic closures from artificially increasing empirical coverage or reducing average interval width.

## Primary result

Across the 1,191 held-out open clinic-days in folds 5–8:

- empirical coverage: **93.619%**
- nominal coverage: **90%**
- mean interval width: **88.644 visits**

The full served panel contains 1,344 clinic-days, including 153 closed clinic-days. All closed rows were served as exact zero intervals:

- closed zero-served rate: **100%**
- all-day served coverage, including deterministic closures: `94.345%`

The primary scientific quantity remains the 93.619% open-day coverage, not the all-day served coverage.

## Fold stability

Coverage remained above nominal in every held-out fold:

| Fold | Open-day coverage | Open-day observations |
| ---: | ---: | ---: |
| 5 | 92.440% | 291 |
| 6 | 94.667% | 300 |
| 7 | 94.667% | 300 |
| 8 | 92.667% | 300 |

This indicates that the aggregate result is not driven by one unusually favourable evaluation period.

## Weekly horizon bands

Empirical open-day coverage by seven-day forecast band was:

| Horizon band | Coverage | Mean interval width | Open-day observations |
| --- | ---: | ---: | ---: |
| days 1–7 | 92.333% | 88.857 | 300 |
| days 8–14 | 94.502% | 88.824 | 291 |
| days 15–21 | 95.000% | 88.516 | 300 |
| days 22–28 | 92.667% | 88.386 | 300 |

All four weekly bands exceeded the 90% nominal target.

## Horizon-level diagnostics

Coverage is not uniform at every individual horizon. Eight of the 28 horizons fell below 90%:

- day 1: `83.333%` (`n=12`)
- day 2: `89.583%` (`n=48`)
- day 3: `89.583%` (`n=48`)
- day 5: `87.500%` (`n=48`)
- day 9: `89.744%` (`n=39`)
- day 16: `87.500%` (`n=48`)
- day 23: `83.333%` (`n=48`)
- day 25: `87.500%` (`n=48`)

Day 1 has especially small support because many clinics are closed on that recurring weekday in the frozen fold schedule, so its 83.333% estimate is based on only 12 open clinic-days.

These local deviations do not contradict the marginal split-conformal target: the implemented intervals do not claim exact conditional coverage for every horizon.

## Clinic-level diagnostics

All 12 clinics achieved at least 90% held-out open-day coverage.

The weakest clinic was `CLINIC_007` at `90.179%` over 112 open clinic-days. The strongest was `CLINIC_006` at `96.842%` over 95 open clinic-days.

Interval widths varied materially across clinics, from about 39 visits for the narrowest clinics to about 140 visits for the widest, reflecting heterogeneous residual scale. Coverage therefore should not be interpreted without interval width.

## Interpretation

The defensible conclusion is:

> Under the frozen seed-42 synthetic network and a strictly prequential fixed-origin recursive audit, the per-clinic split-conformal intervals achieve slightly conservative marginal coverage on held-out open clinic-days. Coverage is stable across the four evaluation folds and all four weekly horizon bands, while individual horizon estimates show localized undercoverage that should remain visible rather than being hidden by the pooled result.

This is synthetic validation of the interval mechanism. It does not establish conditional coverage guarantees, and it does not replace the separate NHS GPAD external-validity result.

## Post-result rule

The 90% target, fold schedule, open-day estimand and prequential calibration order are now frozen for this evidence record. Any horizon-specific calibration, alternative grouping rule, or changed nominal target would constitute a new follow-up analysis and must not be presented as the same audit.
