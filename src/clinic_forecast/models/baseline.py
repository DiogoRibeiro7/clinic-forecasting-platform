"""Simple baseline forecasting models."""

from __future__ import annotations

import numpy as np
import pandas as pd


def seasonal_naive_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    season_length: int = 7,
) -> pd.DataFrame:
    """Forecast future values by repeating the value from one season ago.

    For daily clinic data, the default season is seven days.
    """
    required = {id_col, date_col, target_col}
    missing = required.difference(train.columns)
    if missing:
        raise ValueError(f"Training data is missing required columns: {sorted(missing)}")

    train_sorted = train.copy().sort_values([id_col, date_col])
    future_sorted = future.copy().sort_values([id_col, date_col])
    forecasts: list[pd.DataFrame] = []

    for clinic_id, test_group in future_sorted.groupby(id_col, observed=True):
        history = train_sorted.loc[train_sorted[id_col] == clinic_id, target_col].to_numpy(dtype=float)
        if len(history) == 0:
            raise ValueError(f"No training history found for {clinic_id}.")
        if len(history) < season_length:
            value = float(np.mean(history))
            yhat = np.repeat(value, len(test_group))
        else:
            pattern = history[-season_length:]
            repeats = int(np.ceil(len(test_group) / season_length))
            yhat = np.tile(pattern, repeats)[: len(test_group)]
        local = test_group[[id_col, date_col]].copy()
        local["forecast"] = yhat
        local["model"] = "seasonal_naive"
        forecasts.append(local)

    return pd.concat(forecasts, ignore_index=True)


def moving_average_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    window: int = 28,
) -> pd.DataFrame:
    """Forecast with a clinic-level moving average."""
    if window <= 0:
        raise ValueError("window must be positive.")

    forecasts: list[pd.DataFrame] = []
    for clinic_id, test_group in future.groupby(id_col, observed=True):
        history = train.loc[train[id_col] == clinic_id, target_col].tail(window)
        if history.empty:
            raise ValueError(f"No training history found for {clinic_id}.")
        local = test_group[[id_col, date_col]].copy()
        local["forecast"] = float(history.mean())
        local["model"] = f"moving_average_{window}"
        forecasts.append(local)
    return pd.concat(forecasts, ignore_index=True)
