# Core recursive multi-model benchmark result

## Evidence identity

This note records the first successful post-merge run of the frozen core recursive benchmark introduced by PR #41.

- implementation merge commit: `736e10ab6188fb2ded09dfeb2caec6c1ab199d7e`
- workflow run: `33808185066`
- artifact id: `9913769282`
- artifact digest: `sha256:ce895bf79384fa057b6fe416c9eda67bf3730bbf2f568c734178eb3ff42d6570`
- Python: `3.11.16`
- Poetry: `2.4.2`
- synthetic seed: `42`
- validation: expanding rolling origin
- initial training window: `365` days
- forecast horizon: `28` days
- step: `28` days
- outer folds: `8`
- clinics: `12`
- evaluation contract: fixed-origin full-horizon forecasting with no teacher forcing

## Canonical leaderboard

The corrected deployment-matched benchmark ranks the four core models as follows by mean outer-fold WAPE:

| Rank | Model | Mean WAPE | SD across folds |
| ---: | --- | ---: | ---: |
| 1 | global HGB | 22.873% | 1.614% |
| 2 | SARIMAX | 24.416% | 2.413% |
| 3 | seasonal naive | 32.175% | 5.558% |
| 4 | moving average 28 | 36.525% | 1.944% |

Mean outer-fold accuracy metrics were:

| Model | MAE | RMSE | WAPE | Bias |
| --- | ---: | ---: | ---: | ---: |
| global HGB | 18.044 | 25.189 | 22.873% | -2.303% |
| SARIMAX | 19.272 | 26.119 | 24.416% | 1.476% |
| seasonal naive | 25.462 | 36.522 | 32.175% | -0.644% |
| moving average 28 | 28.847 | 37.656 | 36.525% | 1.925% |

Bias is signed and is reported as an operational diagnostic rather than a lower-is-always-better ranking metric.

## Paired fold evidence against seasonal naive

Global HGB improved MAE, RMSE and WAPE relative to seasonal naive in **all 8 of 8 outer folds**.

- mean WAPE difference: `-9.302` percentage points
- median WAPE difference: `-8.436` percentage points
- mean MAE difference: `-7.418`
- mean RMSE difference: `-11.333`

SARIMAX also improved MAE, RMSE and WAPE relative to seasonal naive in **all 8 of 8 outer folds**.

- mean WAPE difference: `-7.759` percentage points
- median WAPE difference: `-6.947` percentage points
- mean MAE difference: `-6.190`
- mean RMSE difference: `-10.403`

The moving-average baseline was worse than seasonal naive on WAPE in 7 of 8 folds.

## HGB versus SARIMAX

HGB had lower WAPE than SARIMAX in **7 of 8 folds**. The only exception was fold 4, where the two models were effectively tied:

- HGB WAPE: `21.894%`
- SARIMAX WAPE: `21.819%`
- difference: `+0.075` percentage points

Across folds, HGB minus SARIMAX WAPE averaged `-1.543` percentage points.

Spatially, HGB had lower WAPE than SARIMAX in **10 of 12 clinics**. SARIMAX was better in `CLINIC_002` and `CLINIC_007`, by only about `0.101` and `0.731` WAPE points respectively.

## Horizon diagnostics

Across the 28 forecast horizons:

- HGB beat seasonal naive on WAPE at **27 of 28** horizons;
- SARIMAX beat seasonal naive at **24 of 28** horizons;
- HGB beat SARIMAX at **20 of 28** horizons.

The only horizon where seasonal naive beat HGB was horizon 1. HGB was worse than SARIMAX at horizons 2, 3, 5, 7, 16, 19, 23 and 28.

Using the four seven-day horizon bands, HGB had lower pooled WAPE than seasonal naive in every band:

| Horizon band | HGB WAPE | SARIMAX WAPE | Seasonal-naive WAPE |
| --- | ---: | ---: | ---: |
| days 1–7 | 22.540% | 22.185% | 30.494% |
| days 8–14 | 22.736% | 26.028% | 34.473% |
| days 15–21 | 22.362% | 24.001% | 30.664% |
| days 22–28 | 23.562% | 25.290% | 33.158% |

SARIMAX is slightly better over days 1–7, while HGB is clearly better over the remaining three bands.

## Interpretation

This benchmark supersedes the retired teacher-forced one-fold headline numbers.

The defensible conclusion is:

> Under the frozen 8-origin, 28-day, fixed-origin recursive benchmark on the seed-42 synthetic network, global HGB is the strongest core model overall. It outperforms seasonal naive on MAE, RMSE and WAPE in every outer fold and is generally better than SARIMAX, although SARIMAX remains competitive at short horizons and in a small minority of folds/clinics.

This is synthetic evidence. It does not replace the separate NHS GPAD external-validity result, and it does not validate latent-demand or staffing-policy claims on real operational data.

## Post-result rule

The four-model benchmark definition, fold schedule and seed should not be changed in response to these scores and then presented as the same benchmark. Any expanded heavy-model stack, alternate seed, or different fold design is a new exploratory or prospectively frozen follow-up analysis.
