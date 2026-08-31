# Clinical staffing optimiser benchmark result

This result applies the prospectively frozen design in `docs/clinical_staffing_optimizer_design.md`. It compares the current hybrid clinical staffing rule with the exact clinician/nurse optimiser while holding forecasting, the frozen hybrid target selector, front-desk staffing, roster caps, productivity assumptions and cost coefficients fixed.

## Primary result

Across the four 28-day outer fixed-origin folds, the mean all-day result was:

| Policy | Total cost | Unmet visits | Understaffed rate | Clinician-days | Nurse-days |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hybrid rule mean | 2,051,124.49 | 1,439.20 | 0.1882 | 1,726.25 | 1,324.25 |
| Hybrid optimiser mean | 1,959,319.97 | 2,855.90 | 0.3512 | 1,506.25 | 1,155.25 |

Relative to the current hybrid rule, the optimiser changed:

- total cost by **-4.48%**;
- unmet visits by **+98.44%**.

The preregistered promotion rule requires the optimiser to be weakly better on both total cost and unmet visits, with at least one strict improvement. The optimiser lowers cost but materially worsens unmet service. Therefore the frozen verdict is:

`tradeoff_do_not_promote`

The optimiser is **not promoted** into the operational staffing path.

## Fold consistency

The direction is consistent across all four outer folds: the optimiser lowers total cost in every fold and increases unmet visits in every fold. Cost reductions range from about 3.1% to 5.8%, while unmet visits increase by about 77% to 133%.

This is therefore not a case where a favourable mean hides a reversed fold. Under the current cost coefficients, exact cost minimisation systematically chooses leaner clinical rosters and accepts substantially more unmet demand.

## Interpretation

This benchmark answers a narrower question than the earlier hybrid-policy work. It does not invalidate the hybrid target selector. Both policies receive the same hybrid point forecast; only the conversion from that forecast to clinician/nurse headcounts changes.

The result shows that the existing configured monetary objective does **not** encode a service preference strong enough to make pure cost minimisation operationally acceptable under the preregistered Pareto criterion. Introducing a stronger unmet-demand penalty, a service-level constraint, a waiting-time objective or another utility trade-off would define a different decision problem and must be prospectively registered before evaluation.

The current transparent hybrid staffing rule therefore remains the operational policy for this synthetic PoC.

## Evidence provenance

- GitHub Actions run: `33419008858`
- Evidence job: `Clinical staffing optimiser evidence`
- PR head SHA: `21f0ecfb354103ac74b3a0e963a414c6fad97e1d`
- workflow synthetic merge SHA recorded by runner: `c16b5b7bcf34a998b259cf5460f23322ba7487eb`
- artifact id: `9768192669`
- artifact SHA-256: `d73d8ba551cd8c2c1ed1e05192cee9f0981fba47688d046cd3e54c7108c4a3db`
- Python: `3.11.16`
- Poetry: `2.4.2`

The row-level paired decisions remain in the immutable Actions artifact. The repository commits the compact fold scores, summary, promotion verdict and provenance.

## Scope

All results are conditional on the synthetic generator, current staffing productivity assumptions, current costs and current roster caps. This is decision-method evidence for the PoC, not a real-clinic deployment claim or a population-level statistical inference from four folds.
