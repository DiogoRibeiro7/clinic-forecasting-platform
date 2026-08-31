# Hybrid capacity-robustness result

This result applies the prospectively frozen design in `docs/hybrid_capacity_robustness_design.md`.

The study crossed four fixed seeds, 42, 142, 242 and 342, with capacity multipliers 0.8, 1.0 and 1.2. The hybrid policy, 90% conformal switch, HGB forecasting model, four 28-day outer folds, nested calibration, staffing rules, costs and legacy evaluator were unchanged.

## Result

The preregistered qualitative criterion was satisfied in **11 of 12 cells** and in **10 of the 11 genuinely new cells**.

The criterion required both:

\[
U_H < U_V
\]

and

\[
C_H < C_A,
\]

where hybrid must have lower unmet visits than completed-visits-only and lower total cost than attended-demand-only on the all-days four-fold mean.

Therefore the result supports **strong but not universal robustness** over the predefined seed and capacity range. It does not justify claiming that the hybrid policy dominates across every capacity regime.

## Single failing cell

The only failure was:

- seed: **42**;
- capacity multiplier: **1.2**.

In that cell, realised capacity censoring fell to approximately **2.98%** of clinic-days and the hybrid trigger rate fell to approximately **10.49%**. The hybrid policy was:

- **0.316% worse on unmet visits than completed-visits-only**;
- **0.168% more expensive than attended-demand-only**.

The strict qualitative criterion therefore fails on both sides in this cell.

This failure is retained exactly as observed. It is not rounded away, excluded, reweighted or used to retune the 90% switch.

## Interpretation

The robustness pattern is consistent with the purpose of the hybrid policy. When capacity pressure is meaningful, the switch usually preserves the original frontier advantage: it reduces unmet demand relative to completed-visits-only while avoiding the full cost of attended-demand-only staffing.

The lone failure occurs in a high-capacity regime where realised censoring is very rare, so there is little latent-demand truncation for the hybrid mechanism to correct. Under that condition, the small switching overhead is no longer guaranteed to beat both pure policies under strict inequalities.

This is an explanatory interpretation of the frozen result, not a new rule. No censoring threshold or capacity-dependent override is introduced.

## Provenance

- GitHub Actions robustness run: `33424991489`
- aggregate artifact id: `9770444642`
- aggregate artifact SHA-256: `c06091e8d1334e44250fc3d0ab8a0302c184fab44d0d17328d537527b36d9d80`
- workflow PR head SHA: `e7ddd518bf511e31a14b30e975d98dc8abe000c3`
- workflow synthetic merge SHA recorded in aggregate provenance: `cc3623aae2d4811c18842c2f4ce6b29b36f96c36`
- Python: `3.11.16`
- Poetry: `2.4.2`

The complete machine-readable 12-cell table is committed beside this result. The underlying per-cell fold outputs remain available in the immutable GitHub Actions artifacts.

## Scope

These are synthetic robustness results over a predefined four-seed, three-capacity grid. They strengthen the evidence for the frozen hybrid policy within this PoC, but they do not establish real-clinic external validity or justify changing the switch without a new prospective design.
