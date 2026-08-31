"""Exact integer optimiser for clinical staffing under the frozen v2 design."""

from __future__ import annotations

import pandas as pd

from clinic_forecast.staffing import StaffingCosts, StaffingRules
from clinic_forecast.staffing_v2 import clinical_candidate_cost


def optimize_clinical_staffing(
    frame: pd.DataFrame,
    demand_col: str = "hybrid_clinical_forecast",
    rules: StaffingRules | None = None,
    costs: StaffingCosts | None = None,
) -> pd.DataFrame:
    """Choose clinician/nurse integers by exact enumeration for each clinic-day."""
    staffing_rules = rules or StaffingRules()
    staffing_rules.validate()
    cost_model = costs or StaffingCosts()
    cost_model.validate()
    if staffing_rules.max_clinicians is None or staffing_rules.max_nurses is None:
        raise ValueError("Clinical optimiser requires finite max_clinicians and max_nurses.")
    if demand_col not in frame.columns:
        raise ValueError(f"Missing demand column: {demand_col}")

    output = frame.copy()
    clinicians: list[int] = []
    nurses: list[int] = []
    for _, row in output.iterrows():
        if "is_open" in output.columns and not bool(row["is_open"]):
            clinicians.append(0)
            nurses.append(0)
            continue
        best_key: tuple[float, float, int, int, int] | None = None
        best_pair: tuple[int, int] | None = None
        for n_clinicians in range(
            staffing_rules.minimum_clinicians,
            staffing_rules.max_clinicians + 1,
        ):
            for n_nurses in range(
                staffing_rules.minimum_nurses,
                staffing_rules.max_nurses + 1,
            ):
                candidate = clinical_candidate_cost(
                    demand=float(row[demand_col]),
                    clinicians=n_clinicians,
                    nurses=n_nurses,
                    rules=staffing_rules,
                    costs=cost_model,
                )
                key = (
                    candidate.total_cost,
                    candidate.unmet_visits,
                    n_clinicians + n_nurses,
                    n_clinicians,
                    n_nurses,
                )
                if best_key is None or key < best_key:
                    best_key = key
                    best_pair = (n_clinicians, n_nurses)
        assert best_pair is not None
        clinicians.append(best_pair[0])
        nurses.append(best_pair[1])

    output["recommended_clinicians"] = clinicians
    output["recommended_nurses"] = nurses
    return output


__all__ = ["optimize_clinical_staffing"]
