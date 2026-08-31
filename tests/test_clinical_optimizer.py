from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.clinical_optimizer import optimize_clinical_staffing
from clinic_forecast.staffing import StaffingCosts, StaffingRules
from clinic_forecast.staffing_v2 import clinical_candidate_cost, staffing_plan_cost_v2


def test_two_resource_capacity_uses_binding_role() -> None:
    frame = pd.DataFrame(
        {
            "visits": [50.0],
            "recommended_clinicians": [3],
            "recommended_nurses": [1],
            "recommended_frontdesk": [1],
        }
    )
    costed = staffing_plan_cost_v2(frame)
    assert costed.loc[0, "clinical_regular_capacity"] == 24.0
    assert costed.loc[0, "unmet_visits"] == pytest.approx(21.2)


def test_candidate_cost_matches_frame_evaluator() -> None:
    rules = StaffingRules(max_clinicians=16, max_nurses=20)
    costs = StaffingCosts()
    scalar = clinical_candidate_cost(50.0, 3, 2, rules, costs)
    frame = pd.DataFrame(
        {
            "visits": [50.0],
            "recommended_clinicians": [3],
            "recommended_nurses": [2],
            "recommended_frontdesk": [0],
        }
    )
    costed = staffing_plan_cost_v2(frame, rules=rules, costs=costs)
    assert scalar.total_cost == pytest.approx(costed.loc[0, "total_cost"])
    assert scalar.unmet_visits == pytest.approx(costed.loc[0, "unmet_visits"])


def test_optimizer_finds_exact_lowest_cost_pair() -> None:
    rules = StaffingRules(max_clinicians=3, max_nurses=3, buffer_ratio=0.0)
    frame = pd.DataFrame({"hybrid_clinical_forecast": [50.0], "is_open": [1]})
    optimized = optimize_clinical_staffing(frame, rules=rules)
    assert int(optimized.loc[0, "recommended_clinicians"]) == 3
    assert int(optimized.loc[0, "recommended_nurses"]) == 2


def test_optimizer_zeroes_closed_days() -> None:
    rules = StaffingRules(max_clinicians=3, max_nurses=3)
    frame = pd.DataFrame({"hybrid_clinical_forecast": [50.0], "is_open": [0]})
    optimized = optimize_clinical_staffing(frame, rules=rules)
    assert int(optimized.loc[0, "recommended_clinicians"]) == 0
    assert int(optimized.loc[0, "recommended_nurses"]) == 0


def test_optimizer_requires_finite_clinical_caps() -> None:
    frame = pd.DataFrame({"hybrid_clinical_forecast": [50.0]})
    with pytest.raises(ValueError, match="finite"):
        optimize_clinical_staffing(frame, rules=StaffingRules())
