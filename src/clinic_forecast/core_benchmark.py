"""Frozen core multi-model benchmark under fixed-origin recursive evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from clinic_forecast.backtesting import make_recursive_global_ml_adapter, strip_future_outcomes
from clinic_forecast.benchmark import Forecaster
from clinic_forecast.models.baseline import moving_average_forecast, seasonal_naive_forecast
from clinic_forecast.models.sarimax import sarimax_panel_forecast
from clinic_forecast.validation import RollingOriginSplitter


@dataclass(frozen=True)
class CoreBenchmarkSpec:
    """Prospectively fixed settings for the core reproducible benchmark."""

    initial_train_days: int = 365
    horizon_days: int = 28
    step_days: int = 28
    max_folds: int = 8
    window: str = "expanding"
    synthetic_seed: int = 42

    def splitter(self) -> RollingOriginSplitter:
        """Build the exact rolling-origin splitter used by this benchmark."""
        return RollingOriginSplitter(
            initial_train_days=self.initial_train_days,
            horizon_days=self.horizon_days,
            step_days=self.step_days,
            max_folds=self.max_folds,
            window="expanding",
        )


def _seasonal_naive(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    future = strip_future_outcomes(test)
    return seasonal_naive_forecast(train, future, season_length=7)


def _moving_average_28(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    future = strip_future_outcomes(test)
    return moving_average_forecast(train, future, window=28)


def _sarimax(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    future = strip_future_outcomes(test)
    return sarimax_panel_forecast(train, future, auto_order=False)


def core_forecasters() -> dict[str, Forecaster]:
    """Return the frozen core benchmark model registry.

    Every adapter receives the full held-out test frame but strips realised
    outcome columns before forecasting. Global HGB additionally uses the
    deployment-matched recursive path, so no holdout target is fed back into
    lag features.
    """
    return {
        "seasonal_naive": _seasonal_naive,
        "moving_average_28": _moving_average_28,
        "sarimax": _sarimax,
        "global_ml_hgb": make_recursive_global_ml_adapter("hgb"),
    }


__all__ = ["CoreBenchmarkSpec", "core_forecasters"]
