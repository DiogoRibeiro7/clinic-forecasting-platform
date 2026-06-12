from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.models.global_ml import GlobalMLForecaster


@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    return generate_network_data(
        SyntheticDataConfig(start_date="2024-01-01", end_date="2024-09-30", n_clinics=4)
    ).usage


@pytest.fixture(scope="module")
def split(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff = panel["date"].max() - pd.Timedelta(days=14)
    return panel[panel["date"] <= cutoff], panel[panel["date"] > cutoff]


def test_predict_known_future_covers_all_clinics(panel, split) -> None:
    train, test = split
    model = GlobalMLForecaster().fit(train)
    predictions = model.predict_known_future(panel)
    predictions = predictions[predictions["date"] > train["date"].max()]

    assert set(predictions["clinic_id"]) == set(panel["clinic_id"])
    assert (predictions["forecast"] >= 0).all()
    assert (predictions["model"] == "global_ml_hgb").all()


def test_recursive_forecast_without_targets(split) -> None:
    train, test = split
    model = GlobalMLForecaster().fit(train)
    future = test.drop(columns=["visits"])
    forecast = model.forecast(history=train, future=future)

    assert len(forecast) == len(test)
    assert set(forecast["clinic_id"]) == set(test["clinic_id"])
    assert forecast["date"].min() == test["date"].min()
    assert forecast["date"].max() == test["date"].max()
    assert (forecast["forecast"] >= 0).all()
    assert forecast["forecast"].notna().all()


def test_recursive_forecast_ignores_leaked_targets(split) -> None:
    train, test = split
    model = GlobalMLForecaster().fit(train)

    poisoned = test.copy()
    poisoned["visits"] = 10_000.0  # absurd values that must not influence output
    clean = model.forecast(history=train, future=test.drop(columns=["visits"]))
    leaked = model.forecast(history=train, future=poisoned)
    pd.testing.assert_frame_equal(clean, leaked)


def test_forecast_rejects_overlapping_future(split) -> None:
    train, _ = split
    model = GlobalMLForecaster().fit(train)
    with pytest.raises(ValueError, match="after the end of history"):
        model.forecast(history=train, future=train.tail(10))


def test_predict_before_fit_raises(split) -> None:
    _, test = split
    model = GlobalMLForecaster()
    with pytest.raises(RuntimeError, match="fitted"):
        model.predict_known_future(test)


def test_outcome_columns_are_not_features(split) -> None:
    train, _ = split
    model = GlobalMLForecaster().fit(train)
    assert model.feature_columns_ is not None
    forbidden = {
        "no_show_rate",
        "no_show_count",
        "same_day_cancellations",
        "scheduled_appointments",
        "capacity_utilization",
    }
    assert forbidden.isdisjoint(model.feature_columns_)


def test_xgboost_estimator_is_optional(split) -> None:
    train, _ = split
    pytest.importorskip("xgboost")
    model = GlobalMLForecaster(estimator="xgboost").fit(train)
    assert model.model_name == "global_ml_xgboost"


def test_unknown_estimator_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown estimator"):
        GlobalMLForecaster(estimator="catboost")  # type: ignore[arg-type]


def test_permutation_importance_returns_ranked_features(split) -> None:
    train, test = split
    model = GlobalMLForecaster().fit(train)
    importance = model.permutation_importance_frame(
        pd.concat([train.tail(2000), test]), n_repeats=2, top_n=10
    )
    assert list(importance.columns) == ["feature", "importance_mean", "importance_std"]
    assert len(importance) == 10
    assert importance["importance_mean"].is_monotonic_decreasing
