from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from clinic_forecast.staffing import (
    StaffingCosts,
    StaffingRules,
    compare_staffing_scenarios,
    load_staffing_config,
    recommend_staffing,
    staffing_plan_cost,
)


def plan_frame(
    visits: float, clinicians: int, nurses: int = 1, frontdesk: int = 1
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "clinic_id": ["A"],
            "date": ["2025-01-01"],
            "visits": [visits],
            "recommended_clinicians": [clinicians],
            "recommended_nurses": [nurses],
            "recommended_frontdesk": [frontdesk],
        }
    )


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


def test_recommend_staffing_caps_at_maximum() -> None:
    forecast = pd.DataFrame({"forecast": [10_000.0], "clinic_id": ["A"], "date": ["2025-01-01"]})
    rules = StaffingRules(max_clinicians=10, max_nurses=12, max_frontdesk=5)
    output = recommend_staffing(forecast, rules=rules)

    assert output.loc[0, "recommended_clinicians"] == 10
    assert output.loc[0, "recommended_nurses"] == 12
    assert output.loc[0, "recommended_frontdesk"] == 5


def test_invalid_rules_rejected() -> None:
    with pytest.raises(ValueError, match="overtime_threshold"):
        StaffingRules(overtime_threshold=0.8).validate()
    with pytest.raises(ValueError, match="max_clinicians"):
        StaffingRules(minimum_clinicians=3, max_clinicians=2).validate()


def test_cost_low_demand_is_mostly_idle() -> None:
    # 4 clinicians = 72 capacity, demand 18 -> 54 idle visits = 3 idle days
    costed = staffing_plan_cost(plan_frame(visits=18.0, clinicians=4))
    assert costed.loc[0, "overtime_cost"] == 0
    assert costed.loc[0, "understaffing_cost"] == 0
    assert costed.loc[0, "idle_cost"] == pytest.approx(3 * 600 * 0.5)


def test_cost_moderate_overflow_served_by_overtime() -> None:
    # 2 clinicians = 36 capacity, threshold 1.2 -> stretch 7.2; demand 40
    costed = staffing_plan_cost(plan_frame(visits=40.0, clinicians=2))
    assert costed.loc[0, "unmet_visits"] == 0
    expected_overtime = (4 / 18) * 600 * 1.5
    assert costed.loc[0, "overtime_cost"] == pytest.approx(expected_overtime)
    assert costed.loc[0, "understaffing_cost"] == 0


def test_cost_extreme_demand_hits_understaffing_penalty() -> None:
    # 2 clinicians = 36 capacity + 7.2 stretch = 43.2; demand 60 -> 16.8 unmet
    costed = staffing_plan_cost(plan_frame(visits=60.0, clinicians=2))
    assert costed.loc[0, "unmet_visits"] == pytest.approx(16.8)
    assert costed.loc[0, "understaffing_cost"] == pytest.approx(16.8 * 80.0)


def test_invalid_costs_rejected() -> None:
    with pytest.raises(ValueError, match="overtime_multiplier"):
        StaffingCosts(overtime_multiplier=0.5).validate()


def test_compare_staffing_scenarios_orders_by_total_cost() -> None:
    demand = 100.0
    lean = plan_frame(demand, clinicians=2)  # heavy understaffing
    sized = plan_frame(demand, clinicians=6)  # close to demand
    bloated = plan_frame(demand, clinicians=16)  # heavy idle

    summary = compare_staffing_scenarios({"lean": lean, "sized": sized, "bloated": bloated})
    assert summary.loc[0, "scenario"] == "sized"
    assert summary["total_cost"].is_monotonic_increasing
    lean_row = summary.set_index("scenario").loc["lean"]
    assert lean_row["understaffed_days"] == 1


def test_load_staffing_config_round_trip(tmp_path: Path) -> None:
    config = tmp_path / "staffing.yaml"
    config.write_text(
        """
staffing:
  visits_per_clinician_day: 18
  visits_per_nurse_day: 24
  visits_per_frontdesk_day: 35
  minimum_clinicians: 1
  minimum_nurses: 1
  minimum_frontdesk: 1
  buffer_ratio: 0.12
  max_clinicians: 16
  overtime_threshold: 1.2
costs:
  clinician_day_cost: 600.0
  overtime_multiplier: 1.5
""",
        encoding="utf-8",
    )
    rules, costs = load_staffing_config(config)
    assert rules.max_clinicians == 16
    assert costs.overtime_multiplier == 1.5


def test_load_staffing_config_requires_staffing_section(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text("other: 1", encoding="utf-8")
    with pytest.raises(ValueError, match="staffing"):
        load_staffing_config(config)


def test_repo_config_file_is_valid() -> None:
    repo_config = Path(__file__).resolve().parents[1] / "configs" / "staffing.yaml"
    rules, costs = load_staffing_config(repo_config)
    rules.validate()
    costs.validate()
