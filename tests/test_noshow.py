from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.noshow import (
    ATTRITION_TARGET,
    AttritionRateForecaster,
    build_noshow_targets,
    expected_completed_visits,
    forecast_attrition_rate_baseline,
)


@pytest.fixture(scope="module")
def usage() -> pd.DataFrame:
    return generate_network_data(
        SyntheticDataConfig(start_date="2024-01-01", end_date="2024-09-30", n_clinics=4)
    ).usage


@pytest.fixture(scope="module")
def split(usage: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff = usage["date"].max() - pd.Timedelta(days=14)
    return usage[usage["date"] <= cutoff], usage[usage["date"] > cutoff]


def test_target_construction_identity(usage) -> None:
    targets = build_noshow_targets(usage)
    open_days = targets[targets["scheduled_appointments"] > 0]

    reconstructed = (
        open_days["realised_no_show_rate"] + open_days["cancellation_rate"]
    )
    pd.testing.assert_series_equal(
        reconstructed, open_days[ATTRITION_TARGET], check_names=False
    )
    assert targets[ATTRITION_TARGET].between(0, 1).all()

    closed = targets[targets["scheduled_appointments"] == 0]
    assert (closed[ATTRITION_TARGET] == 0).all()


def test_target_construction_requires_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        build_noshow_targets(pd.DataFrame({"clinic_id": ["A"]}))


def test_baseline_rate_forecast_shape_and_bounds(split) -> None:
    train, test = split
    baseline = forecast_attrition_rate_baseline(train, test)

    assert len(baseline) == len(test)
    assert baseline["forecast"].between(0, 1).all()
    assert (baseline["model"] == "attrition_historical_mean").all()


def test_baseline_captures_clinic_differences(split) -> None:
    train, test = split
    baseline = forecast_attrition_rate_baseline(train, test, by_weekday=False)
    per_clinic = baseline.groupby("clinic_id")["forecast"].first()
    assert per_clinic.nunique() > 1  # clinic-specific base rates survive


def test_ml_rate_model_excludes_leaky_features(split) -> None:
    train, _ = split
    model = AttritionRateForecaster().fit(train)
    features = model.feature_columns_ or []
    assert "visits" not in features
    assert "scheduled_appointments" not in features
    assert "no_show_count" not in features


def test_ml_rate_predictions_are_valid_rates(split) -> None:
    train, test = split
    model = AttritionRateForecaster().fit(train)
    combined = pd.concat([train, test], ignore_index=True).sort_values(["clinic_id", "date"])
    prediction = model.predict_known_future(combined)
    prediction = prediction[prediction["date"] > train["date"].max()]

    assert prediction["forecast"].between(0, 1).all()
    assert set(prediction["clinic_id"]) == set(test["clinic_id"])


def test_expected_completed_visits_combines_targets() -> None:
    schedule = pd.DataFrame(
        {"clinic_id": ["A", "A"], "date": ["2025-01-01", "2025-01-02"], "forecast": [100.0, 50.0]}
    )
    rates = pd.DataFrame(
        {"clinic_id": ["A", "A"], "date": ["2025-01-01", "2025-01-02"], "forecast": [0.1, 0.2]}
    )
    combined = expected_completed_visits(schedule, rates)
    assert combined.loc[0, "expected_completed"] == pytest.approx(90.0)
    assert combined.loc[1, "expected_completed"] == pytest.approx(40.0)
