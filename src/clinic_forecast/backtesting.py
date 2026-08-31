"""Deployment-matched backtesting helpers.

The platform makes one forecast for an entire future horizon from a fixed
origin. Backtests therefore must not feed realised targets from inside the
holdout window back into lag features. These helpers make that contract
explicit and reusable by notebooks, benchmarks and conformal calibration.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from clinic_forecast.models.global_ml import GlobalMLForecaster

Forecaster = Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]


def strip_future_outcomes(
    future: pd.DataFrame,
    target_col: str = "visits",
) -> pd.DataFrame:
    """Remove target and same-day outcome columns from a future frame.

    A fixed-origin forecast may use only information available at the origin
    plus genuinely known future inputs such as calendar and planned marketing.
    """
    forbidden = {
        target_col,
        "scheduled_appointments",
        "no_show_count",
        "same_day_cancellations",
        "no_show_rate",
        "capacity_utilization",
    }
    return future.drop(columns=[c for c in forbidden if c in future.columns]).copy()


def recursive_global_ml_forecast(
    train: pd.DataFrame,
    test: pd.DataFrame,
    estimator: str = "hgb",
    target_col: str = "visits",
) -> pd.DataFrame:
    """Fit global ML on ``train`` and forecast the full test horizon recursively.

    The realised target values in ``test`` are deliberately discarded before
    forecasting. This matches the batch deployment mechanism and prevents
    teacher-forcing leakage inside multi-day holdout windows.
    """
    model = GlobalMLForecaster(target_col=target_col, estimator=estimator).fit(train)  # type: ignore[arg-type]
    future = strip_future_outcomes(test, target_col=target_col)
    return model.forecast(history=train, future=future)


def make_recursive_global_ml_adapter(
    estimator: str = "hgb",
    target_col: str = "visits",
) -> Forecaster:
    """Return a benchmark-compatible fixed-origin global-ML forecaster."""

    def forecaster(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
        return recursive_global_ml_forecast(
            train=train,
            test=test,
            estimator=estimator,
            target_col=target_col,
        )

    return forecaster
