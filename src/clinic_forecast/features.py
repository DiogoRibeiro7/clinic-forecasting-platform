"""Feature engineering utilities for time-series forecasting."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def add_calendar_features(data: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Add calendar features to a dataframe.

    Parameters
    ----------
    data:
        Input dataframe.
    date_col:
        Name of the date column.

    Returns
    -------
    pandas.DataFrame
        Copy of the input dataframe with calendar features.
    """
    if date_col not in data.columns:
        raise ValueError(f"Missing date column: {date_col}")

    frame = data.copy()
    frame[date_col] = pd.to_datetime(frame[date_col])
    frame["day_of_week"] = frame[date_col].dt.dayofweek
    frame["month"] = frame[date_col].dt.month
    frame["week_of_year"] = frame[date_col].dt.isocalendar().week.astype(int)
    frame["is_weekend"] = frame["day_of_week"].isin([5, 6]).astype(int)
    frame["day_of_year"] = frame[date_col].dt.dayofyear
    return frame


def add_lag_features(
    data: pd.DataFrame,
    group_col: str,
    target_col: str,
    lags: Iterable[int] = (1, 7, 14, 28),
    rolling_windows: Iterable[int] = (7, 14, 28),
) -> pd.DataFrame:
    """Add lag and rolling mean features for panel time series.

    The function sorts by group and date if a `date` column is present.
    """
    required = {group_col, target_col}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    sort_cols = [group_col]
    if "date" in data.columns:
        sort_cols.append("date")

    frame = data.copy().sort_values(sort_cols)
    grouped = frame.groupby(group_col, observed=True)[target_col]

    for lag in lags:
        if lag <= 0:
            raise ValueError("All lags must be positive integers.")
        frame[f"lag_{lag}"] = grouped.shift(lag)

    for window in rolling_windows:
        if window <= 1:
            raise ValueError("Rolling windows must be greater than 1.")
        frame[f"rolling_mean_{window}"] = grouped.shift(1).rolling(window=window).mean().reset_index(
            level=0, drop=True
        )
        frame[f"rolling_std_{window}"] = grouped.shift(1).rolling(window=window).std().reset_index(
            level=0, drop=True
        )

    return frame


def make_supervised_frame(
    data: pd.DataFrame,
    group_col: str = "clinic_id",
    target_col: str = "visits",
) -> pd.DataFrame:
    """Create a supervised learning frame for global forecasting models."""
    frame = add_calendar_features(data)
    frame = add_lag_features(frame, group_col=group_col, target_col=target_col)
    categorical_cols = [
        col for col in ["clinic_id", "region", "clinic_size", "specialty"] if col in frame.columns
    ]
    encoded = pd.get_dummies(
        frame[categorical_cols],
        prefix=categorical_cols,
        drop_first=False,
        dtype=int,
    )
    frame = pd.concat([frame, encoded], axis=1)
    return frame.dropna().reset_index(drop=True)
