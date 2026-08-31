# Frozen capacity-aware hybrid policy

This policy is frozen before evaluating its performance.

For each clinic-day, clinical staffing uses completed-visits demand unless the 90% upper split-conformal bound for completed visits reaches or exceeds the clinic's known daily capacity. In that case, staffing switches to the attended-demand forecast.

Formally, with completed-visits upper bound \(U_{c,t}^{V}\) and known capacity \(K_c\),

\[
T_{c,t}=\begin{cases}
\text{attended demand}, & U_{c,t}^{V}\ge K_c,\\
\text{completed visits}, & U_{c,t}^{V}<K_c.
\end{cases}
\]

The rule is deliberately not tuned to previous benchmark results. It uses only quantities available at the forecast origin: historical data used for conformal calibration, the completed-visits forecast distribution, and static clinic capacity. The realised `capacity_censored` indicator is evaluation-only and never enters the switch.

Front-desk staffing remains based on scheduled appointments under every policy. The hybrid evaluation therefore changes only the clinical target-selection rule.
