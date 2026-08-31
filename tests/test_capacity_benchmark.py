from __future__ import annotations

import numpy as np
import pandas as pd

from clinic_forecast.capacity_benchmark import (
    CapacityTargetBenchmarkConfig,
    _score_slice,
    run_capacity_target_benchmark,
    summarize_capacity_target_benchmark,
)
from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.role_specific import CLINICAL_TARGET


def test_score_slice_reports_underforecasting() -> None:
    frame = pd.DataFrame(
        {
            CLINICAL_TARGET: [10.0, 20.0, 30.0],
            "forecast": [8.0, 20.0, 25.0],
        }
    )
    scored = _score_slice(frame, "forecast")
    assert scored["n_obs"] == 3
    assert np.isclose(float(scored["mean_shortfall"]), 7.0 / 3.0)
    assert np.isclose(float(scored["underforecast_rate"]), 2.0 / 3.0)


def test_capacity_target_benchmark_is_paired_and_scored_against_attended_demand() -> None:
    usage = generate_network_data(
        SyntheticDataConfig(start_date="2023-01-01", end_date="2024-12-31", n_clinics=4)
    ).usage
    scores, predictions = run_capacity_target_benchmark(
        usage,
        CapacityTargetBenchmarkConfig(
            initial_train_days=365,
            horizon_days=14,
            max_folds=2,
            estimator="hgb",
        ),
    )

    assert set(scores["model_target"]) == {"visits", "attended_demand"}
    assert set(scores["evaluation_target"]) == {"attended_demand"}
    assert set(scores["slice"]) == {"all", "censored", "uncensored"}
    assert set(scores["fold"]) == {1, 2}
    assert {
        "forecast_attended_target",
        "forecast_completed_target",
        "capacity_censored",
        "horizon_days",
    }.issubset(predictions.columns)

    paired_counts = (
        scores[scores["slice"] == "all"]
        .groupby("fold", observed=True)["n_obs"]
        .nunique()
    )
    assert (paired_counts == 1).all()


def test_capacity_target_summary_has_fold_dispersion() -> None:
    scores = pd.DataFrame(
        {
            "fold": [1, 2, 1, 2],
            "model_target": ["visits", "visits", "attended_demand", "attended_demand"],
            "slice": ["censored"] * 4,
            "wape": [20.0, 22.0, 15.0, 17.0],
            "mae": [5.0, 6.0, 4.0, 4.5],
            "bias": [-10.0, -12.0, -4.0, -5.0],
            "mean_shortfall": [3.0, 4.0, 1.5, 2.0],
            "underforecast_rate": [0.8, 0.9, 0.6, 0.65],
        }
    )
    summary = summarize_capacity_target_benchmark(scores)
    assert set(summary["model_target"]) == {"visits", "attended_demand"}
    assert (summary["n_folds"] == 2).all()
    assert "wape_mean" in summary.columns
    assert "wape_std" in summary.columns
