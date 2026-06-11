"""Forecasting pipeline helpers."""

from __future__ import annotations

import pandas as pd

from clinic_forecast.models.baseline import seasonal_naive_forecast
from clinic_forecast.staffing import StaffingRules, recommend_staffing


def baseline_staffing_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    rules: StaffingRules | None = None,
) -> pd.DataFrame:
    """Run a seasonal naive forecast and convert it into staffing recommendations."""
    forecast = seasonal_naive_forecast(train=train, future=future)
    return recommend_staffing(forecast, rules=rules)
