"""Feature engineering utilities for panel time-series forecasting.

All history-derived features are leakage-safe by construction:

- Lags shift by at least one step within each clinic.
- Rolling and expanding statistics are computed on the *shifted* series, so a
  row's feature never includes that row's own target.
- All grouped statistics are computed per clinic; windows never cross clinic
  boundaries.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

#: Same-day operational outcomes; never valid as features for the visit target.
OUTCOME_COLUMNS: tuple[str, ...] = (
    "scheduled_appointments",
    "no_show_count",
    "same_day_cancellations",
    "no_show_rate",
    "capacity_utilization",
)


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
    add_expanding_mean: bool = True,
) -> pd.DataFrame:
    """Add per-clinic lag, rolling and expanding features.

    The function sorts by group and date if a `date` column is present.
    Rolling and expanding statistics are computed within each group on the
    one-step-shifted target, so windows never cross clinic boundaries and
    never include the current row's value.
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

    shifted = grouped.shift(1)
    shifted_by_group = shifted.groupby(frame[group_col], observed=True)
    for window in rolling_windows:
        if window <= 1:
            raise ValueError("Rolling windows must be greater than 1.")
        frame[f"rolling_mean_{window}"] = shifted_by_group.transform(
            lambda s, w=window: s.rolling(w).mean()
        )
        frame[f"rolling_std_{window}"] = shifted_by_group.transform(
            lambda s, w=window: s.rolling(w).std()
        )

    if add_expanding_mean:
        frame["expanding_mean"] = shifted_by_group.transform(lambda s: s.expanding().mean())

    return frame


def add_marketing_features(
    data: pd.DataFrame,
    group_col: str = "clinic_id",
    spend_col: str = "marketing_spend",
    lags: Iterable[int] = (1, 7),
    rolling_window: int = 7,
) -> pd.DataFrame:
    """Add lagged and short-window rolling marketing-spend features per clinic.

    Spend itself is a *known* future input (budgets are planned), so the
    same-day value is kept; lags and the rolling mean capture carryover
    (adstock-like) effects.
    """
    if spend_col not in data.columns:
        return data

    sort_cols = [group_col] + (["date"] if "date" in data.columns else [])
    frame = data.copy().sort_values(sort_cols)
    grouped = frame.groupby(group_col, observed=True)[spend_col]
    for lag in lags:
        frame[f"{spend_col}_lag_{lag}"] = grouped.shift(lag)
    frame[f"{spend_col}_rolling_{rolling_window}"] = grouped.transform(
        lambda s: s.shift(1).rolling(rolling_window).mean()
    )
    return frame


def make_supervised_frame(
    data: pd.DataFrame,
    group_col: str = "clinic_id",
    target_col: str = "visits",
    dropna: bool = True,
) -> pd.DataFrame:
    """Create a supervised learning frame for global forecasting models.

    Parameters
    ----------
    dropna:
        When True (training), drop rows with incomplete features. When False
        (recursive prediction), keep all rows; tree models that tolerate NaN
        can still predict on early-history rows.
    """
    frame = add_calendar_features(data)
    frame = add_lag_features(frame, group_col=group_col, target_col=target_col)
    frame = add_marketing_features(frame, group_col=group_col)

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
    if dropna:
        feature_cols = [col for col in frame.columns if col != target_col]
        frame = frame.dropna(subset=[c for c in feature_cols if frame[c].dtype.kind in "fc"])
        frame = frame.dropna(subset=[target_col])
    return frame.reset_index(drop=True)
