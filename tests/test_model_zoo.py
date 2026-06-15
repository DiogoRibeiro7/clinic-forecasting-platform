"""Tests for the model zoo wrappers and benchmark harness.

The heavy native libraries (statsforecast, mlforecast, neuralforecast, torch
foundation models) are NOT imported here: their crash modes are
platform-specific and irrelevant to the wrapper logic. Instead each wrapper
is exercised through its injectable ``forecaster`` / ``predict_fn`` seam with
a lightweight mock, which is exactly the schema contract the real libraries
must satisfy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from clinic_forecast.benchmark import (
    benchmark_leaderboard,
    benchmark_metric_table,
    run_benchmark,
)
from clinic_forecast.models.baseline import moving_average_forecast, seasonal_naive_forecast
from clinic_forecast.models.foundation import (
    chronos_panel_forecast,
    foundation_panel_forecast,
    lag_llama_panel_forecast,
    timesfm_panel_forecast,
)
from clinic_forecast.models.nixtla_models import (
    mlforecast_panel_forecast,
    neuralforecast_panel_forecast,
    statsforecast_panel_forecast,
)
from clinic_forecast.validation import RollingOriginSplitter


def make_panel(n_days: int = 140, clinics: tuple[str, ...] = ("A", "B")) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    frames = []
    for i, cid in enumerate(clinics):
        weekly = 8 * np.sin(2 * np.pi * np.arange(n_days) / 7)
        visits = (50 * (i + 1) + weekly + np.arange(n_days) * 0.1).clip(min=1)
        frames.append(pd.DataFrame({"clinic_id": cid, "date": dates, "visits": visits}))
    return pd.concat(frames, ignore_index=True)


def split_panel(panel: pd.DataFrame, horizon: int = 14) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff = panel["date"].max() - pd.Timedelta(days=horizon)
    return panel[panel["date"] <= cutoff], panel[panel["date"] > cutoff]


# ----------------- Nixtla wrappers (mock forecaster objects) -----------------


class MockStatsForecast:
    """Mimics StatsForecast.forecast output."""

    def forecast(self, df, h):  # noqa: ANN001
        rows = []
        for uid, frame in df.groupby("unique_id"):
            last = frame["ds"].max()
            dates = pd.date_range(last + pd.Timedelta(days=1), periods=h)
            rows.append(pd.DataFrame({"unique_id": uid, "ds": dates,
                                      "AutoETS": float(frame["y"].mean())}))
        return pd.concat(rows, ignore_index=True)


class MockTrainPredict:
    """Mimics MLForecast / NeuralForecast fit + predict."""

    def __init__(self, value_col: str) -> None:
        self.value_col = value_col
        self._df = None
        self._h = None

    def fit(self, df):  # noqa: ANN001
        self._df = df
        return self

    def predict(self, h=None):  # noqa: ANN001
        horizon = h if h is not None else self._h or 14
        rows = []
        for uid, frame in self._df.groupby("unique_id"):
            last = frame["ds"].max()
            dates = pd.date_range(last + pd.Timedelta(days=1), periods=horizon)
            rows.append(pd.DataFrame({"unique_id": uid, "ds": dates,
                                      self.value_col: float(frame["y"].mean())}))
        return pd.concat(rows, ignore_index=True)


def test_statsforecast_wrapper_common_schema() -> None:
    train, _ = split_panel(make_panel())
    out = statsforecast_panel_forecast(train, horizon=14, forecaster=MockStatsForecast())
    assert list(out.columns) == ["clinic_id", "date", "forecast", "model"]
    assert (out["model"] == "statsforecast_AutoETS").all()
    assert len(out) == 14 * 2
    assert (out["forecast"] >= 0).all()


def test_mlforecast_wrapper_common_schema() -> None:
    train, _ = split_panel(make_panel())
    out = mlforecast_panel_forecast(train, horizon=14, forecaster=MockTrainPredict("ml"))
    assert (out["model"] == "mlforecast_lightgbm").all()
    assert len(out) == 14 * 2
    assert set(out["clinic_id"]) == {"A", "B"}


def test_neuralforecast_wrapper_common_schema() -> None:
    train, _ = split_panel(make_panel())
    out = neuralforecast_panel_forecast(train, horizon=14, forecaster=MockTrainPredict("NHITS"))
    assert (out["model"] == "neuralforecast_NHITS").all()
    assert len(out) == 14 * 2


def test_nixtla_wrappers_validate_horizon() -> None:
    train, _ = split_panel(make_panel())
    with pytest.raises(ValueError, match="horizon"):
        statsforecast_panel_forecast(train, horizon=0, forecaster=MockStatsForecast())


def test_uninstalled_library_raises_clear_import_error() -> None:
    train, _ = split_panel(make_panel())
    # No forecaster injected and the real libs aren't importable in this path
    # only if absent; assert the error type/message contract via monkeypatch.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        if name.startswith(("statsforecast", "mlforecast", "neuralforecast")):
            raise ImportError("blocked")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = fake_import
    try:
        with pytest.raises(ImportError, match="poetry install --with optional"):
            statsforecast_panel_forecast(train, horizon=7)
    finally:
        builtins.__import__ = real_import


# ----------------- Foundation wrappers (injected predict_fn) -----------------


def mean_predict_fn(history: np.ndarray, horizon: int) -> np.ndarray:
    return np.repeat(history[-7:].mean(), horizon)


def test_foundation_panel_forecast_applies_predictor() -> None:
    train, test = split_panel(make_panel())
    out = foundation_panel_forecast(train, test, mean_predict_fn, "demo")
    assert list(out.columns) == ["clinic_id", "date", "forecast", "model"]
    assert len(out) == len(test)
    assert (out["forecast"] >= 0).all()


def test_foundation_wrappers_use_injected_predict_fn() -> None:
    train, test = split_panel(make_panel())
    for wrapper, name in [
        (timesfm_panel_forecast, "timesfm"),
        (chronos_panel_forecast, "chronos"),
        (lag_llama_panel_forecast, "lag_llama"),
    ]:
        out = wrapper(train, test, predict_fn=mean_predict_fn)
        assert (out["model"] == name).all()
        assert len(out) == len(test)


def test_foundation_predictor_wrong_length_raises() -> None:
    train, test = split_panel(make_panel())

    def bad_fn(history: np.ndarray, horizon: int) -> np.ndarray:
        return np.zeros(horizon + 1)

    with pytest.raises(ValueError, match="expected"):
        foundation_panel_forecast(train, test, bad_fn, "bad")


# ----------------- Benchmark harness -----------------


def test_run_benchmark_scores_multiple_models() -> None:
    panel = make_panel(n_days=200)
    splitter = RollingOriginSplitter(initial_train_days=120, horizon_days=28, max_folds=2)
    forecasters = {
        "seasonal_naive": lambda tr, te: seasonal_naive_forecast(train=tr, future=te),
        "moving_average": lambda tr, te: moving_average_forecast(train=tr, future=te, window=28),
    }
    scored = run_benchmark(panel, forecasters, splitter)

    assert set(scored["model"]) == {"seasonal_naive", "moving_average"}
    assert set(scored["fold"]) == {1, 2}

    board = benchmark_leaderboard(scored)
    assert list(board.columns[:2]) == ["model", "wape_mean"]
    assert board["rank"].tolist() == [1, 2]
    assert "wape" in benchmark_metric_table(scored).columns


def test_run_benchmark_skips_failing_model() -> None:
    panel = make_panel(n_days=200)
    splitter = RollingOriginSplitter(initial_train_days=120, horizon_days=28, max_folds=1)

    def broken(train, test):  # noqa: ANN001
        raise RuntimeError("model not installed")

    forecasters = {
        "good": lambda tr, te: seasonal_naive_forecast(train=tr, future=te),
        "broken": broken,
    }
    scored = run_benchmark(panel, forecasters, splitter, on_error="skip")
    assert set(scored["model"]) == {"good"}

    with pytest.raises(RuntimeError, match="not installed"):
        run_benchmark(panel, {"broken": broken}, splitter, on_error="raise")
