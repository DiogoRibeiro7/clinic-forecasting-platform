"""Prospectively frozen capacity-aware hybrid clinical staffing policy."""

from __future__ import annotations

import pandas as pd


def select_hybrid_clinical_forecast(
    frame: pd.DataFrame,
    *,
    completed_point_col: str = "forecast_completed_target",
    completed_upper_col: str = "completed_upper",
    attended_point_col: str = "forecast_attended_target",
    capacity_col: str = "daily_capacity",
) -> pd.DataFrame:
    """Select the clinical demand target using only forecast-time information.

    The switch is frozen prospectively: use attended-demand forecasting when
    the 90% upper conformal bound for completed visits reaches or exceeds known
    clinic capacity; otherwise retain the completed-visits forecast.
    """
    required = {
        completed_point_col,
        completed_upper_col,
        attended_point_col,
        capacity_col,
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Hybrid policy missing columns: {sorted(missing)}")

    output = frame.copy()
    output["capacity_pressure"] = (
        output[completed_upper_col] >= output[capacity_col]
    ).astype(int)
    output["hybrid_clinical_forecast"] = output[completed_point_col].where(
        output["capacity_pressure"] == 0,
        output[attended_point_col],
    )
    output["hybrid_target"] = output["capacity_pressure"].map(
        {0: "completed_visits", 1: "attended_demand"}
    )
    return output


__all__ = ["select_hybrid_clinical_forecast"]
