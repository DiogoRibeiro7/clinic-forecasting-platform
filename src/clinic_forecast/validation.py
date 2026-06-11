"""Temporal validation utilities."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BacktestWindow:
    """One rolling-origin validation window."""

    window_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def rolling_origin_windows(
    data: pd.DataFrame,
    date_col: str = "date",
    horizon_days: int = 28,
    n_windows: int = 4,
    min_train_days: int = 365,
) -> Iterator[BacktestWindow]:
    """Yield rolling-origin validation windows.

    Parameters
    ----------
    data:
        Input time-series dataframe.
    date_col:
        Date column name.
    horizon_days:
        Forecast horizon in days.
    n_windows:
        Number of validation windows.
    min_train_days:
        Minimum number of training days before the first test window.
    """
    if date_col not in data.columns:
        raise ValueError(f"Missing date column: {date_col}")
    if horizon_days <= 0 or n_windows <= 0 or min_train_days <= 0:
        raise ValueError("horizon_days, n_windows and min_train_days must be positive.")

    dates = pd.Series(pd.to_datetime(data[date_col].unique())).sort_values().reset_index(drop=True)
    if len(dates) < min_train_days + horizon_days:
        raise ValueError("Not enough history for the requested validation setup.")

    final_test_end_idx = len(dates) - 1
    for idx in range(n_windows):
        test_end_idx = final_test_end_idx - (n_windows - idx - 1) * horizon_days
        test_start_idx = test_end_idx - horizon_days + 1
        train_end_idx = test_start_idx - 1
        train_start_idx = 0

        if train_end_idx - train_start_idx + 1 < min_train_days:
            continue

        yield BacktestWindow(
            window_id=idx + 1,
            train_start=pd.Timestamp(dates.iloc[train_start_idx]),
            train_end=pd.Timestamp(dates.iloc[train_end_idx]),
            test_start=pd.Timestamp(dates.iloc[test_start_idx]),
            test_end=pd.Timestamp(dates.iloc[test_end_idx]),
        )


def split_window(
    data: pd.DataFrame,
    window: BacktestWindow,
    date_col: str = "date",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split data into train and test sets for a backtest window."""
    frame = data.copy()
    frame[date_col] = pd.to_datetime(frame[date_col])
    train = frame[(frame[date_col] >= window.train_start) & (frame[date_col] <= window.train_end)]
    test = frame[(frame[date_col] >= window.test_start) & (frame[date_col] <= window.test_end)]
    return train.copy(), test.copy()
