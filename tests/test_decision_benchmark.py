from __future__ import annotations

import pandas as pd

from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.decision_benchmark import (
    StaffingDecisionBenchmarkConfig,
    _score_costed,
    run_staffing_decision_benchmark,
    summarize_staffing_decision_benchmark,
)
from clinic_forecast.staffing import StaffingRules


def test_score_costed_reports_decision_metrics() -> None:
    costed = pd.DataFrame(
        {
            "regular_cost": [100.0, 120.0],
            "overtime_cost": [10.0, 0.0],
            "understaffing_cost": [20.0, 0.0],
            "idle_cost": [0.0, 5.0],
            "total_cost": [130.0, 125.0],
            "unmet_visits": [2.0, 0.0],
            "recommended_clinicians": [2, 2],
            "recommended_nurses": [2, 2],
            "recommended_frontdesk": [1, 1],
        }
    )
    scored = _score_costed(costed)
    assert scored["n_obs"] == 2
    assert scored["total_cost"] == 255.0
    assert scored["unmet_visits"] == 2.0
    assert scored["understaffed_rate"] == 0.5


def test_decision_benchmark_pairs_policies_and_frontdesk() -> None:
    usage = generate_network_data(
        SyntheticDataConfig(start_date="2023-01-01", end_date="2024-12-31", n_clinics=4)
    ).usage
    scores, decisions = run_staffing_decision_benchmark(
        usage,
        StaffingDecisionBenchmarkConfig(
            initial_train_days=365,
            horizon_days=14,
            max_folds=2,
            estimator="hgb",
        ),
        rules=StaffingRules(buffer_ratio=0.0),
    )
    assert set(scores["policy"]) == {"attended_demand", "completed_visits"}
    assert set(scores["slice"]) == {"all", "censored", "uncensored"}
    assert set(scores["fold"]) == {1, 2}

    frontdesk = decisions.pivot_table(
        index=["fold", "clinic_id", "date"],
        columns="policy",
        values="recommended_frontdesk",
    )
    assert (frontdesk["attended_demand"] == frontdesk["completed_visits"]).all()

    closed = decisions[decisions["is_open"] == 0]
    if not closed.empty:
        assert (
            closed[
                [
                    "recommended_clinicians",
                    "recommended_nurses",
                    "recommended_frontdesk",
                ]
            ]
            == 0
        ).all().all()


def test_decision_summary_has_fold_dispersion() -> None:
    scores = pd.DataFrame(
        {
            "fold": [1, 2, 1, 2],
            "policy": ["attended_demand"] * 2 + ["completed_visits"] * 2,
            "slice": ["all"] * 4,
            "total_cost": [100.0, 110.0, 120.0, 125.0],
            "cost_per_day": [10.0, 11.0, 12.0, 12.5],
            "regular_cost": [80.0, 85.0, 90.0, 92.0],
            "overtime_cost": [5.0, 5.0, 8.0, 8.0],
            "understaffing_cost": [10.0, 15.0, 18.0, 20.0],
            "idle_cost": [5.0, 5.0, 4.0, 5.0],
            "unmet_visits": [1.0, 2.0, 3.0, 4.0],
            "understaffed_rate": [0.1, 0.2, 0.3, 0.4],
            "clinician_days": [10, 11, 9, 10],
            "nurse_days": [12, 13, 11, 12],
            "frontdesk_days": [5, 5, 5, 5],
        }
    )
    summary = summarize_staffing_decision_benchmark(scores)
    assert set(summary["policy"]) == {"attended_demand", "completed_visits"}
    assert (summary["n_folds"] == 2).all()
    assert "total_cost_mean" in summary.columns
    assert "unmet_visits_std" in summary.columns
