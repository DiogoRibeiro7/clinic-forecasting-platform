# NHS GPAD confirmatory benchmark result

## Frozen evidence identity

This note records the first post-merge confirmatory NHS GPAD forecasting benchmark. It summarizes the immutable artifact produced from the prospectively frozen design and does not change the model, panel, zero policy, or outer-origin definitions.

- implementation merge commit: `78e92f96c44f3805a7634be8415ef72d767778ae`
- workflow run: `33759927072`
- artifact id: `9895107732`
- artifact digest: `sha256:50732a9c6b95cfd053357c6f4654000613728cc15598a39858a612e1d8784571`
- source archive SHA-256: `c5092aebe42158b2cdad5552b66e5f5e275bb07dbed2bd337dffd22178035c7f`
- source window: 2024-01-01 through 2026-06-30
- confirmatory panel: 31 sub-ICBs × 912 days = 28,272 rows
- outer origins: 19
- forecast horizon: 28 days
- forecast rows per model: 16,492
- total scored forecast rows: 49,476
- workflow provenance status: `success`

The observed estimand is **attended GP appointments**. The benchmark does not identify latent demand, usable capacity, unmet demand, staffing efficiency, or causal staffing effects.

## Primary result

The recursive global HGB model improved aggregate forecast accuracy relative to the frozen seven-day seasonal-naive baseline, but the improvement was not uniform across outer origins.

| Model | Pooled MAE | Pooled WAPE | Pooled RMSE | Pooled bias |
| --- | ---: | ---: | ---: | ---: |
| global HGB | 597.654 | 12.303% | 1,485.153 | -4.084% |
| seasonal naive | 806.377 | 16.600% | 2,258.133 | -3.716% |
| moving average 28 | 2,918.082 | 60.072% | 3,869.081 | -0.504% |

Relative to seasonal naive, global HGB reduced pooled MAE by about 25.9%, pooled WAPE by 4.30 percentage points, and pooled RMSE by about 34.2%. Its pooled bias was slightly more negative.

Across the 19 frozen outer origins, global HGB had lower WAPE than seasonal naive in **11** origins and higher WAPE in **8**. The mean origin-paired WAPE difference was **-4.170 percentage points** and the median difference was **-0.284 points**. The exact two-sided sign-test p-value was **0.648**. The sign test is descriptive only and is not a promotion gate under the frozen design.

The same 11-versus-8 origin split occurred for MAE and RMSE. Therefore the result supports an aggregate external-generalization claim, but it does **not** support a claim that HGB consistently dominates the seasonal-naive benchmark at every temporal origin.

## Horizon diagnostics

Global HGB had lower pooled WAPE than seasonal naive in all four prospectively frozen weekly horizon bands:

| Horizon band | HGB WAPE | Seasonal-naive WAPE | HGB minus seasonal |
| --- | ---: | ---: | ---: |
| days 1–7 | 10.223% | 12.965% | -2.742 pp |
| days 8–14 | 12.764% | 17.801% | -5.037 pp |
| days 15–21 | 11.433% | 14.202% | -2.769 pp |
| days 22–28 | 14.832% | 21.542% | -6.710 pp |

At individual horizons, global HGB had lower WAPE at **19 of 28** horizons and higher WAPE at 9 of 28. The individual-horizon pattern is therefore heterogeneous even though all four pre-specified weekly bands favor HGB.

## Geography diagnostics

Global HGB had lower pooled WAPE than seasonal naive in **30 of 31** eligible sub-ICBs. The only geography with higher HGB WAPE was `70F`, where the difference was approximately +2.93 percentage points. No geography is removed or reweighted in response to this result.

This geography result is stronger than the origin-level result: spatially, the HGB improvement is broad; temporally, performance remains regime-dependent.

## Moving-average baseline

The frozen 28-day moving-average baseline performed poorly. Relative to seasonal naive:

- WAPE was worse in **19 of 19** origins;
- MAE was worse in **19 of 19** origins;
- the mean WAPE difference was +43.551 percentage points;
- the exact two-sided sign-test p-value for WAPE was approximately `0.000004`.

This is evidence against the 28-day moving average as a competitive external baseline for this GPAD panel. It is recorded as a result, not removed or retuned after inspection.

## Interpretation

The first real-data bridge supports the following statement:

> Under the prospectively frozen 31-sub-ICB, 19-origin NHS GPAD benchmark, the repository's recursive global HGB forecasting approach generalized to observed attended GP appointment activity in aggregate, with lower pooled error than seasonal naive and broad gains across geographies and weekly horizon bands. However, the improvement was not temporally uniform: seasonal naive remained better in 8 of 19 outer origins.

It does **not** support claims that:

- HGB universally dominates seasonal naive;
- the hybrid staffing policy is externally validated;
- latent demand or unmet demand has been identified;
- usable patient-facing capacity has been measured;
- staffing cost, waiting time, or service outcomes would improve causally.

Those claims remain outside the identification boundary of the public GPAD data.

## Post-result rule

No panel, origin, feature, model, or hyperparameter change should be justified by these scores and then presented as part of this confirmatory benchmark. Any later model expansion, robustness analysis, or alternative geography treatment must be explicitly labeled as a new exploratory or prospectively frozen follow-up analysis.
