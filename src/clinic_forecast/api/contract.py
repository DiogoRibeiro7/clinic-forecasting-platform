"""Stable schema contract for the versioned role-specific serving API."""

from __future__ import annotations

from typing import Final, Literal

import pandas as pd

V2_CONTRACT_VERSION: Final = "2.0.0"
V2_CONTRACT_HEADER: Final = "X-Clinic-Forecast-Contract-Version"
V2_RUN_ID_HEADER: Final = "X-Clinic-Forecast-Run-Id"

V2ArtifactKind = Literal["forecasts", "staffing", "monitoring"]

V2_FORECAST_REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "clinic_id",
        "date",
        "is_open",
        "daily_capacity",
        "attended_pred",
        "attended_lower",
        "attended_upper",
        "completed_pred",
        "completed_lower",
        "completed_upper",
        "scheduled_pred",
        "scheduled_lower",
        "scheduled_upper",
        "capacity_pressure",
        "hybrid_target",
        "hybrid_clinical_forecast",
        "hybrid_clinical_upper",
    }
)

V2_STAFFING_REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "clinic_id",
        "date",
        "daily_capacity",
        "capacity_pressure",
        "hybrid_target",
        "mean_plan_clinicians",
        "mean_plan_nurses",
        "mean_plan_frontdesk",
        "upper_plan_clinicians",
        "upper_plan_nurses",
        "upper_plan_frontdesk",
    }
)

V2_MONITORING_REQUIRED_COLUMNS: Final[frozenset[str]] = frozenset(
    {
        "level",
        "group",
        "n_open_days",
        "capacity_pressure_days",
        "capacity_pressure_rate",
        "attended_demand_selected_days",
        "attended_demand_selected_rate",
        "mean_completed_upper_capacity_ratio",
    }
)

V2_REQUIRED_COLUMNS: Final[dict[V2ArtifactKind, frozenset[str]]] = {
    "forecasts": V2_FORECAST_REQUIRED_COLUMNS,
    "staffing": V2_STAFFING_REQUIRED_COLUMNS,
    "monitoring": V2_MONITORING_REQUIRED_COLUMNS,
}


def validate_v2_artifact(frame: pd.DataFrame, kind: V2ArtifactKind) -> None:
    """Fail when a role-specific artifact does not satisfy the frozen v2 schema."""
    required = V2_REQUIRED_COLUMNS[kind]
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            f"Role-specific {kind} artifact is incompatible with serving contract "
            f"{V2_CONTRACT_VERSION}: missing columns {missing}."
        )


__all__ = [
    "V2ArtifactKind",
    "V2_CONTRACT_HEADER",
    "V2_CONTRACT_VERSION",
    "V2_FORECAST_REQUIRED_COLUMNS",
    "V2_MONITORING_REQUIRED_COLUMNS",
    "V2_REQUIRED_COLUMNS",
    "V2_RUN_ID_HEADER",
    "V2_STAFFING_REQUIRED_COLUMNS",
    "validate_v2_artifact",
]
