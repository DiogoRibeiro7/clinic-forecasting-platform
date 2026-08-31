from __future__ import annotations

import pandas as pd

from clinic_forecast.hybrid_policy import select_hybrid_clinical_forecast


def test_hybrid_switch_uses_completed_upper_bound_against_known_capacity() -> None:
    frame = pd.DataFrame(
        {
            "forecast_completed_target": [80.0, 80.0],
            "completed_upper": [95.0, 105.0],
            "forecast_attended_target": [90.0, 120.0],
            "daily_capacity": [100.0, 100.0],
        }
    )
    result = select_hybrid_clinical_forecast(frame)
    assert result["capacity_pressure"].tolist() == [0, 1]
    assert result["hybrid_clinical_forecast"].tolist() == [80.0, 120.0]
    assert result["hybrid_target"].tolist() == ["completed_visits", "attended_demand"]


def test_hybrid_switch_does_not_require_realised_censoring() -> None:
    frame = pd.DataFrame(
        {
            "forecast_completed_target": [80.0],
            "completed_upper": [101.0],
            "forecast_attended_target": [110.0],
            "daily_capacity": [100.0],
        }
    )
    result = select_hybrid_clinical_forecast(frame)
    assert "capacity_censored" not in result.columns
    assert int(result.loc[0, "capacity_pressure"]) == 1
