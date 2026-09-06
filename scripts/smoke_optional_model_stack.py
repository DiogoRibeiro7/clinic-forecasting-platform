"""Exercise the installable optional forecasting stack without external services.

This smoke runner is intended for the scheduled/manual GitHub Actions workflow.
It imports every dependency declared in Poetry's ``optional`` group and executes
small local forecasts for StatsForecast, MLForecast, and NeuralForecast. Hosted
TimeGPT and pretrained Chronos are import-gated only: the smoke must not require
API credentials, network inference, or model-weight downloads.
"""

from __future__ import annotations

import importlib
from typing import Final

import numpy as np
import pandas as pd

from clinic_forecast.models.nixtla_models import (
    mlforecast_panel_forecast,
    neuralforecast_panel_forecast,
    statsforecast_panel_forecast,
)

_OPTIONAL_MODULES: Final[tuple[str, ...]] = (
    "prophet",
    "xgboost",
    "torch",
    "nixtla",
    "statsforecast",
    "mlforecast",
    "lightgbm",
    "neuralforecast",
    "numba",
    "chronos",
)


def _make_panel(n_days: int = 84) -> pd.DataFrame:
    """Return a deterministic one-clinic panel large enough for short lag models."""
    if n_days < 35:
        raise ValueError("n_days must be at least 35 for the optional-model smoke.")

    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    day = np.arange(n_days, dtype=float)
    visits = 60.0 + 5.0 * np.sin(2.0 * np.pi * day / 7.0) + 0.05 * day
    return pd.DataFrame({"clinic_id": "smoke", "date": dates, "visits": visits})


def _assert_common_forecast(frame: pd.DataFrame, *, model: str, horizon: int) -> None:
    """Fail fast when an optional wrapper stops satisfying the common schema."""
    expected_columns = ["clinic_id", "date", "forecast", "model"]
    if list(frame.columns) != expected_columns:
        raise AssertionError(f"{model} returned columns {list(frame.columns)!r}.")
    if len(frame) != horizon:
        raise AssertionError(f"{model} returned {len(frame)} rows; expected {horizon}.")
    if frame["forecast"].isna().any() or (frame["forecast"] < 0).any():
        raise AssertionError(f"{model} returned invalid forecast values.")


def _import_optional_modules() -> None:
    """Import every package represented by the Poetry optional dependency group."""
    for module_name in _OPTIONAL_MODULES:
        importlib.import_module(module_name)
        print(f"import ok: {module_name}")


def _run_local_forecast_smokes() -> None:
    """Fit tiny local models that require no credentials or downloaded checkpoints."""
    panel = _make_panel()
    horizon = 2

    stats = statsforecast_panel_forecast(
        panel,
        horizon=horizon,
        model="SeasonalNaive",
        season_length=7,
    )
    _assert_common_forecast(stats, model="StatsForecast", horizon=horizon)
    print("forecast ok: StatsForecast SeasonalNaive")

    for estimator in ("lightgbm", "xgboost"):
        machine_learning = mlforecast_panel_forecast(
            panel,
            horizon=horizon,
            estimator=estimator,
            lags=(1, 7, 14),
        )
        _assert_common_forecast(
            machine_learning,
            model=f"MLForecast {estimator}",
            horizon=horizon,
        )
        print(f"forecast ok: MLForecast {estimator}")

    neural = neuralforecast_panel_forecast(
        panel,
        horizon=horizon,
        model="NHITS",
        input_size=14,
        max_steps=1,
    )
    _assert_common_forecast(neural, model="NeuralForecast NHITS", horizon=horizon)
    print("forecast ok: NeuralForecast NHITS")


def main() -> None:
    """Run deterministic import and local-execution checks for optional models."""
    _import_optional_modules()
    _run_local_forecast_smokes()
    print("Optional model stack smoke completed successfully.")


if __name__ == "__main__":
    main()
