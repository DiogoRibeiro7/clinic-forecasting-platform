# NHS GPAD origin-regime characterization — exploratory design lock

## Status and scientific boundary

This is an **exploratory/descriptive follow-up** to the already-frozen NHS GPAD confirmatory benchmark. It is motivated by the observed temporal heterogeneity in that benchmark: global HGB had lower WAPE than seasonal naive in 11 of 19 frozen outer origins, while seasonal naive was better in 8 of 19.

Nothing in this analysis changes or re-scores the confirmatory benchmark. The frozen panel, source archive, zero policy, 19 outer origins, 28-day horizon, models, hyperparameters, forecasts and confirmatory interpretation remain immutable.

The purpose is only to characterize what was happening in the observed appointment-activity series during origins where the relative model ranking differed. Findings are hypothesis-generating and must not be used to claim a new validated regime-switching policy.

## Frozen source evidence

The analysis must consume the canonical confirmatory workflow artifact rather than rerun the benchmark:

- confirmatory implementation merge: `78e92f96c44f3805a7634be8415ef72d767778ae`
- workflow run: `33759927072`
- artifact id: `9895107732`
- artifact digest: `sha256:50732a9c6b95cfd053357c6f4654000613728cc15598a39858a612e1d8784571`
- source archive SHA-256: `c5092aebe42158b2cdad5552b66e5f5e275bb07dbed2bd337dffd22178035c7f`
- panel: 31 frozen sub-ICBs × 912 calendar days
- confirmatory origins: 19

Required artifact inputs are `fold_scores.csv`, `origin_boundaries.csv`, `forecast_rows.csv` and `prepared_attended_sub_icb_day.csv`.

## Fixed outcome label

For descriptive grouping only, each origin is labelled from the frozen confirmatory scores:

- `hgb_better`: HGB WAPE < seasonal-naive WAPE;
- `seasonal_better`: HGB WAPE > seasonal-naive WAPE.

Ties, if any, are retained as `tie`; no tolerance is introduced after inspection.

This label is an observed benchmark outcome, not a prediction target for a fitted classifier.

## Frozen descriptors

All descriptors below are calculated once for every one of the 19 fixed origins. No additional descriptor may be added in response to the resulting separation between winner groups without being explicitly labelled as a later exploratory extension.

### Calendar position

- test start and end dates;
- start month and calendar quarter;
- number of distinct months touched by the 28-day test window.

No holiday feature is retrofitted into the frozen benchmark. Calendar descriptors are annotations only.

### Target level and dispersion

Using observed attended GP appointment counts across the frozen 31-sub-ICB panel:

- trailing 28-day pre-origin mean and standard deviation;
- test-window mean and standard deviation;
- coefficient of variation for the trailing and test windows, defined as standard deviation divided by mean when mean is positive;
- test-to-trailing mean ratio.

### Sparse/zero activity

- trailing 28-day zero-row fraction;
- test-window zero-row fraction.

A zero remains an observed publication-domain attended count under the frozen GPAD zero policy. It is not interpreted as latent zero demand.

### Aggregate level-shift diagnostics

Construct the daily network total by summing the 31 sub-ICBs for each date. Record:

- trailing 28-day network-total mean and standard deviation;
- first-7-test-day network-total mean;
- full-test network-total mean;
- standardized first-week level shift: `(first_7_test_mean - trailing_28_mean) / trailing_28_sd` when the trailing standard deviation is positive;
- relative full-test level shift: `(test_mean - trailing_28_mean) / trailing_28_mean` when the trailing mean is positive.

These quantities describe realized changes around each fixed forecast origin. They are not available ex ante in the same form and therefore must not be presented as deployable switching rules.

### Geography composition of relative error

From the already-frozen forecast rows, compute within each origin and sub-ICB the WAPE for HGB and seasonal naive, then record:

- number and fraction of sub-ICBs where HGB has lower WAPE;
- median sub-ICB HGB-minus-seasonal WAPE difference;
- maximum positive sub-ICB WAPE difference (largest HGB disadvantage);
- minimum sub-ICB WAPE difference (largest HGB advantage).

No sub-ICB is dropped, reweighted or selected after inspection.

## Planned summaries

The result package will contain:

1. one row per origin with the fixed winner label, frozen WAPEs and all descriptors above;
2. a winner-group descriptive table reporting count, median and interquartile range for numeric descriptors;
3. a chronological origin table so temporal clustering can be inspected directly;
4. a short interpretation note identifying visually/materially different descriptors without significance testing or a fitted predictive model.

No multiple-testing procedure is needed because no null-hypothesis significance tests are planned.

## Interpretation constraints

Permitted language includes statements such as “the eight seasonal-naive-winning origins tended to coincide with larger realized level shifts” if supported descriptively.

Not permitted from this analysis alone:

- a claim that a descriptor causally explains model failure;
- a claim that the descriptor predicts future winner regimes;
- a new model-selection or switching policy;
- tuning HGB, changing the seasonal baseline, changing the panel, or dropping difficult origins;
- relabelling the original confirmatory result;
- inference about latent demand, usable capacity, unmet demand, staffing efficiency or causal staffing effects.

Any deployable regime-switching rule would require a separate prospectively frozen design using only information available before each forecast origin and a new untouched evaluation set.