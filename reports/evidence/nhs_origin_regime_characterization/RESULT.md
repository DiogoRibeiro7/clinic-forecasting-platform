# NHS GPAD origin-regime characterization — exploratory result

## Evidence identity

This result is an exploratory/descriptive follow-up to the frozen NHS GPAD confirmatory benchmark. It uses the descriptor set frozen in `DESIGN.md` before winner-group separation was inspected.

The analysis consumes the canonical confirmatory artifact directly:

- confirmatory implementation merge: `78e92f96c44f3805a7634be8415ef72d767778ae`
- workflow run: `33759927072`
- artifact id: `9895107732`
- artifact digest: `sha256:50732a9c6b95cfd053357c6f4654000613728cc15598a39858a612e1d8784571`
- source archive SHA-256: `c5092aebe42158b2cdad5552b66e5f5e275bb07dbed2bd337dffd22178035c7f`
- panel: 31 frozen sub-ICBs × 912 days
- origins: 19 fixed 28-day outer origins

No forecast was rerun or changed. The fixed confirmatory split remains 11 HGB-winning origins and 8 seasonal-naive-winning origins.

## Main descriptive finding

The eight seasonal-naive-winning origins do **not** separate cleanly from HGB-winning origins on the pre-specified realized level-shift, volatility, or zero-frequency descriptors.

For example:

| Descriptor | HGB-winning origins, median [IQR] | Seasonal-winning origins, median [IQR] |
| --- | ---: | ---: |
| Test / trailing-28 mean ratio | 1.028 [0.977, 1.091] | 0.969 [0.936, 1.047] |
| Standardized first-week level shift | 0.014 [-0.123, 0.129] | -0.022 [-0.044, 0.079] |
| Relative full-test level shift | +2.85% [-2.26%, +9.07%] | -3.11% [-6.35%, +4.70%] |
| Test zero-row fraction | 10.02% [9.10%, 12.44%] | 11.92% [10.63%, 12.90%] |
| Test coefficient of variation | 1.019 [1.008, 1.070] | 1.065 [1.017, 1.086] |

The seasonal-naive-winning group has a somewhat lower median test-to-trailing level ratio and a somewhat higher median zero fraction/CV, but the IQRs overlap substantially. On these 19 origins there is no defensible single scalar threshold that emerges as an obvious ex-post regime separator.

That is important because it argues against inventing a switching rule from the current evidence.

## Calendar clustering

The strongest simple temporal pattern is calendar position.

Seasonal naive was better at origins:

- 2025-01-28 to 2025-02-24;
- 2025-03-25 to 2025-04-21;
- 2025-05-20 to 2025-06-16;
- 2025-06-17 to 2025-07-14;
- 2025-07-15 to 2025-08-11;
- 2025-08-12 to 2025-09-08;
- 2026-03-24 to 2026-04-20;
- 2026-04-21 to 2026-05-18.

Quarter-of-test-start counts were:

| Start quarter | HGB better | Seasonal naive better |
| --- | ---: | ---: |
| Q1 | 3 | 3 |
| Q2 | 2 | 3 |
| Q3 | 1 | 2 |
| Q4 | 5 | 0 |

All five Q4-starting origins favored HGB. Conversely, seasonal-naive wins clustered in late winter through summer, with the two largest positive HGB-minus-seasonal WAPE differences occurring in the late-March 2025 and late-March 2026 origins.

This is descriptive evidence of temporal seasonality/regime dependence, not evidence that quarter or month can be used prospectively to choose a model.

## Geography composition

The origin-level ranking is usually broad across geographies rather than being driven by a single sub-ICB.

The median fraction of sub-ICBs where HGB had lower WAPE was:

- **93.55%** [80.65%, 100%] in HGB-winning origins;
- **20.97%** [0%, 52.42%] in seasonal-naive-winning origins.

In four of the eight seasonal-naive-winning origins, HGB lost in all 31 sub-ICBs. In contrast, several HGB-winning origins showed HGB gains in all 31 sub-ICBs.

This temporal breadth is consistent with the confirmatory observation that spatial generalization was strong overall (30/31 pooled sub-ICBs favored HGB), while relative performance still changed substantially by time origin.

## What this does and does not suggest

The descriptive evidence supports two follow-up hypotheses:

1. calendar/seasonal structure may be an important source of temporal ranking changes between a learned global model and a seven-day seasonal baseline;
2. some weak HGB origins appear to be network-wide temporal episodes rather than isolated geography failures.

It does **not** identify a validated switching mechanism. In particular, the realized level-shift measures use outcomes from the forecast window and cannot be used ex ante as written.

No model, geography, origin, feature or hyperparameter should be changed because of this result and then presented as part of the original confirmatory benchmark.

A genuine model-switching experiment would need a new prospective design that freezes candidate ex-ante signals available before each origin, freezes the switching rule without access to future winner labels, and evaluates it on a new untouched period.

## Files

- `origin_regime_descriptors.csv`: one row for each of the 19 frozen origins;
- `winner_group_summary.csv`: median and interquartile range by observed winner group;
- `DESIGN.md`: pre-result descriptor and interpretation lock.

The observed estimand remains published attended GP appointment activity. This analysis does not identify latent demand, usable capacity, unmet demand, staffing efficiency, waiting-time effects or causal policy outcomes.