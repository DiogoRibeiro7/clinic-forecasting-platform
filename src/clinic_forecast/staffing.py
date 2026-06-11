"""Convert clinic demand forecasts into staffing recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import pandas as pd


@dataclass(frozen=True)
class StaffingRules:
    """Productivity and safety-buffer assumptions for staffing conversion."""

    visits_per_clinician_day: int = 18
    visits_per_nurse_day: int = 24
    visits_per_frontdesk_day: int = 35
    minimum_clinicians: int = 1
    minimum_nurses: int = 1
    minimum_frontdesk: int = 1
    buffer_ratio: float = 0.12

    def validate(self) -> None:
        """Validate staffing rules."""
        positive_ints = [
            self.visits_per_clinician_day,
            self.visits_per_nurse_day,
            self.visits_per_frontdesk_day,
            self.minimum_clinicians,
            self.minimum_nurses,
            self.minimum_frontdesk,
        ]
        if any(value <= 0 for value in positive_ints):
            raise ValueError("Staffing productivity and minimums must be positive.")
        if self.buffer_ratio < 0:
            raise ValueError("buffer_ratio cannot be negative.")


def recommend_staffing(
    forecast: pd.DataFrame,
    forecast_col: str = "forecast",
    rules: StaffingRules | None = None,
) -> pd.DataFrame:
    """Convert forecasted demand into staffing recommendations."""
    if forecast_col not in forecast.columns:
        raise ValueError(f"Missing forecast column: {forecast_col}")

    staffing_rules = rules or StaffingRules()
    staffing_rules.validate()
    frame = forecast.copy()
    buffered_demand = frame[forecast_col].clip(lower=0) * (1 + staffing_rules.buffer_ratio)

    frame["recommended_clinicians"] = buffered_demand.apply(
        lambda value: max(staffing_rules.minimum_clinicians, ceil(value / staffing_rules.visits_per_clinician_day))
    )
    frame["recommended_nurses"] = buffered_demand.apply(
        lambda value: max(staffing_rules.minimum_nurses, ceil(value / staffing_rules.visits_per_nurse_day))
    )
    frame["recommended_frontdesk"] = buffered_demand.apply(
        lambda value: max(staffing_rules.minimum_frontdesk, ceil(value / staffing_rules.visits_per_frontdesk_day))
    )
    return frame


def staffing_gap(
    recommended: pd.DataFrame,
    metadata: pd.DataFrame,
    id_col: str = "clinic_id",
) -> pd.DataFrame:
    """Compare recommended staffing with baseline staffing levels."""
    required = {id_col, "base_clinicians", "base_nurses", "base_frontdesk"}
    missing = required.difference(metadata.columns)
    if missing:
        raise ValueError(f"Metadata missing required columns: {sorted(missing)}")

    frame = recommended.merge(metadata[list(required)], on=id_col, how="left")
    frame["clinician_gap"] = frame["recommended_clinicians"] - frame["base_clinicians"]
    frame["nurse_gap"] = frame["recommended_nurses"] - frame["base_nurses"]
    frame["frontdesk_gap"] = frame["recommended_frontdesk"] - frame["base_frontdesk"]
    return frame
