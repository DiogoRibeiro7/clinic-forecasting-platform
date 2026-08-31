# Horizon-resolved hybrid policy audit

## Verdict

The frozen 13-origin × 28-horizon audit does **not** show a simple deterioration of the selected hybrid policy with forecast horizon.

Across exact forecast days, the original strict qualitative criterion is met on 12 of 28 horizons:

`1, 2, 3, 8, 10, 14, 15, 16, 17, 19, 25, 28`.

The service direction, hybrid unmet visits lower than completed-visits-only, holds strictly on 17 of 28 horizons. Five horizons reverse that mean direction (`4, 11, 12, 18, 24`) and six are exact mean ties (`5, 6, 13, 20, 26, 27`).

The cost direction, hybrid total cost lower than attended-demand-only, holds on 23 of 28 horizons. Cost reversals occur at horizons `7, 9, 21, 22, 23`; the only contiguous cost-reversal run is horizons 21–23.

No exact horizon is worse than both pure policies simultaneously under the two original primary directions.

## Weekly bands

The preregistered week-level aggregates preserve both original qualitative directions in **all four weeks**:

- week 1: hybrid cost vs attended = -1680.97; hybrid unmet vs completed = -23.23;
- week 2: -1698.82; -15.43;
- week 3: -2514.26; -12.42;
- week 4: -1405.38; -14.14.

Thus the day-level reversals are intermittent rather than evidence of a monotone late-horizon collapse. Horizon 28 itself again satisfies both strict directions.

Origin-level sign consistency is heterogeneous. The week-4 service contrast remains directionally strong (8 negative, 1 positive, 4 zero origins; exact sign-test p = 0.0391), while week-4 cost is much less origin-consistent (8 negative, 5 positive; p = 0.5811). These p-values are descriptive diagnostics only, exactly as frozen in the design.

## Interpretation

The pooled 28-day advantage is not an artefact of only the earliest forecast days. It persists when the horizon is divided into four preregistered weekly blocks. However, exact-day results are noisy and the strict two-direction criterion is not satisfied on every day.

This supports retaining the existing hybrid policy without horizon-specific retuning. The operational limitation is not a deterministic day-of-horizon cutoff; it is that cost and service advantages vary materially across forecast origins and individual horizons, so production monitoring should remain horizon-resolved.

No threshold, estimator, conformal level, staffing rule, cost model or horizon-specific policy is changed by this audit.

## Provenance

- clean evidence workflow run: `33436984922`
- artifact id: `9774888459`
- artifact SHA-256: `8fe3f1c6a0e8a8eae47b914c4618214861ab72c673f65e0eaeed47985b44006b`
- evidence commit SHA reported by workflow: `3ebdebe7207da66921ab870cbd9b1b30a685c92b`
- seed: 42
- outer origins: 13
- initial training: 1095 days
- horizon/step: 28/28 days
- inner calibration: 730 days, 4 folds
- coverage: 0.90
- estimator: HGB
- Python: 3.11.16
- Poetry: 2.4.2
