from __future__ import annotations

import pandas as pd

from clinic_forecast.staffing import StaffingRules, recommend_staffing


def test_recommend_staffing_respects_minimums() -> None:
    forecast = pd.DataFrame({"forecast": [0.0], "clinic_id": ["A"], "date": ["2025-01-01"]})
    output = recommend_staffing(forecast, rules=StaffingRules())

    assert output.loc[0, "recommended_clinicians"] == 1
    assert output.loc[0, "recommended_nurses"] == 1
    assert output.loc[0, "recommended_frontdesk"] == 1


def test_recommend_staffing_scales_with_demand() -> None:
    forecast = pd.DataFrame({"forecast": [200.0], "clinic_id": ["A"], "date": ["2025-01-01"]})
    output = recommend_staffing(forecast, rules=StaffingRules(buffer_ratio=0.0))

    assert output.loc[0, "recommended_clinicians"] == 12
    assert output.loc[0, "recommended_nurses"] == 9
    assert output.loc[0, "recommended_frontdesk"] == 6
