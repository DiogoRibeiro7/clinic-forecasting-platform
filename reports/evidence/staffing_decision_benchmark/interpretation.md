# Staffing decision benchmark — interpretation

The paired decision benchmark compares two clinical staffing policies on the same four fixed-origin 28-day folds. Both policies use the same scheduled-appointments forecast for front-desk staffing and the same staffing rules, roster caps, overtime assumptions and cost coefficients. Only the clinical forecast target changes.

- `attended_demand`: clinicians and nurses are sized from pre-capacity attended-demand forecasts.
- `completed_visits`: clinicians and nurses are sized from completed-visit forecasts.

Both policies are costed against realised pre-capacity attended demand.

## Result

Across all clinic-days, attended-demand staffing costs about 1.0% more on average (1,986,721 versus 1,966,615 currency units per fold) while reducing unmet demand by about 4.9% (1,346.8 versus 1,416.9 visits per fold).

On capacity-censored clinic-days, attended-demand staffing is strictly better under the frozen cost model: total cost is about 0.8% lower (389,639 versus 392,816), unmet demand is about 12.4% lower (910.1 versus 1,038.9), and the understaffed-day rate falls by about 11.4% relative (0.750 versus 0.847). It achieves this by scheduling roughly 12 additional clinician-days and 10 additional nurse-days per fold on the censored slice.

On uncensored days, the trade-off reverses. Attended-demand staffing costs about 1.5% more and produces more unmet demand than completed-visit staffing. That is consistent with the forecasting benchmark, where completed visits was modestly more accurate on uncensored periods.

## Decision implication

The evidence does not support one globally dominant clinical staffing target. It supports a capacity-aware policy:

- use attended-demand forecasting where capacity censoring is material or likely;
- retain completed-visits forecasting for observed-throughput planning and uncensored operating regimes;
- keep front-desk staffing tied to scheduled appointments.

A production migration should therefore be conditional on capacity pressure rather than replacing the completed-visits target everywhere. The next scientific gate is to define a prospective switching rule using information available at forecast origin, then evaluate that hybrid policy on held-out folds without tuning the threshold after seeing its result.
