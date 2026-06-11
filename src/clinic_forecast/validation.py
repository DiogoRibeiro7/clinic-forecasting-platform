"""Temporal validation utilities.

The central tool is :class:`RollingOriginSplitter`, which produces
forward-chaining rolling-origin folds for single series or multi-clinic
panels. Training data always ends strictly before the test window starts, so
no future observation can leak into model fitting.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass(frozen=True)
class Fold:
    """One rolling-origin validation fold (all bounds inclusive)."""

    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


@dataclass(frozen=True)
class RollingOriginSplitter:
    """Forward-chaining rolling-origin splitter for time-series validation.

    The first fold trains on the first ``initial_train_days`` distinct dates
    and tests on the following ``horizon_days``. Each subsequent fold moves
    the forecast origin forward by ``step_days`` (default: the horizon, i.e.
    non-overlapping test windows).

    Parameters
    ----------
    initial_train_days:
        Number of distinct dates in the first training window.
    horizon_days:
        Number of distinct dates in each test window.
    step_days:
        Days the origin advances between folds. Defaults to ``horizon_days``.
    max_folds:
        Optional cap on the number of folds.
    window:
        ``"expanding"`` (default) keeps the training start fixed at the first
        date; ``"sliding"`` keeps the training window at a constant
        ``initial_train_days`` length.
    date_col:
        Name of the date column.

    Examples
    --------
    >>> import pandas as pd
    >>> frame = pd.DataFrame({
    ...     "date": pd.date_range("2024-01-01", periods=120, freq="D"),
    ...     "visits": range(120),
    ... })
    >>> splitter = RollingOriginSplitter(initial_train_days=60, horizon_days=28)
    >>> [fold.fold_id for fold in splitter.folds(frame)]
    [1, 2]
    >>> train, test, fold = next(splitter.split(frame))
    >>> bool(train["date"].max() < test["date"].min())
    True
    """

    initial_train_days: int = 365
    horizon_days: int = 28
    step_days: int | None = None
    max_folds: int | None = None
    window: Literal["expanding", "sliding"] = "expanding"
    date_col: str = "date"

    def __post_init__(self) -> None:
        if self.initial_train_days <= 0 or self.horizon_days <= 0:
            raise ValueError("initial_train_days and horizon_days must be positive.")
        if self.step_days is not None and self.step_days <= 0:
            raise ValueError("step_days must be positive when provided.")
        if self.max_folds is not None and self.max_folds <= 0:
            raise ValueError("max_folds must be positive when provided.")
        if self.window not in ("expanding", "sliding"):
            raise ValueError("window must be 'expanding' or 'sliding'.")

    @property
    def effective_step_days(self) -> int:
        """Origin advance between folds; defaults to the forecast horizon."""
        return self.step_days if self.step_days is not None else self.horizon_days

    def _distinct_dates(self, data: pd.DataFrame) -> pd.DatetimeIndex:
        if self.date_col not in data.columns:
            raise ValueError(f"Missing date column: {self.date_col}")
        dates = pd.DatetimeIndex(pd.to_datetime(data[self.date_col].unique())).sort_values()
        if len(dates) < self.initial_train_days + self.horizon_days:
            raise ValueError(
                "Not enough history: need at least "
                f"{self.initial_train_days + self.horizon_days} distinct dates, "
                f"got {len(dates)}."
            )
        return dates

    def folds(self, data: pd.DataFrame) -> list[Fold]:
        """Compute fold boundaries from the distinct dates in ``data``."""
        dates = self._distinct_dates(data)
        step = self.effective_step_days
        folds: list[Fold] = []
        origin = self.initial_train_days  # index of the first test date
        fold_id = 1
        while origin + self.horizon_days <= len(dates):
            is_expanding = self.window == "expanding"
            train_start_idx = 0 if is_expanding else origin - self.initial_train_days
            folds.append(
                Fold(
                    fold_id=fold_id,
                    train_start=dates[train_start_idx],
                    train_end=dates[origin - 1],
                    test_start=dates[origin],
                    test_end=dates[origin + self.horizon_days - 1],
                )
            )
            if self.max_folds is not None and fold_id >= self.max_folds:
                break
            origin += step
            fold_id += 1
        return folds

    def split(
        self, data: pd.DataFrame
    ) -> Iterator[tuple[pd.DataFrame, pd.DataFrame, Fold]]:
        """Yield ``(train, test, fold)`` triples.

        Training rows satisfy ``train_start <= date <= train_end`` and test
        rows ``test_start <= date <= test_end``; the two ranges never overlap.
        """
        frame = data.copy()
        frame[self.date_col] = pd.to_datetime(frame[self.date_col])
        for fold in self.folds(frame):
            train_mask = (frame[self.date_col] >= fold.train_start) & (
                frame[self.date_col] <= fold.train_end
            )
            test_mask = (frame[self.date_col] >= fold.test_start) & (
                frame[self.date_col] <= fold.test_end
            )
            yield frame[train_mask].copy(), frame[test_mask].copy(), fold

    def split_by_clinic(
        self, data: pd.DataFrame, id_col: str = "clinic_id"
    ) -> Iterator[tuple[str, pd.DataFrame, pd.DataFrame, Fold]]:
        """Yield ``(clinic_id, train, test, fold)`` using each clinic's own timeline.

        Useful when clinics have different history lengths; fold boundaries
        are computed independently per clinic.
        """
        if id_col not in data.columns:
            raise ValueError(f"Missing id column: {id_col}")
        for clinic_id, clinic_frame in data.groupby(id_col, observed=True):
            for train, test, fold in self.split(clinic_frame):
                yield str(clinic_id), train, test, fold

    def summary(self, data: pd.DataFrame) -> pd.DataFrame:
        """Return a one-row-per-fold summary frame for ``data``."""
        return summarize_folds(data, self)


def summarize_folds(data: pd.DataFrame, splitter: RollingOriginSplitter) -> pd.DataFrame:
    """Summarise fold boundaries and row counts for a dataset.

    Returns
    -------
    pandas.DataFrame
        One row per fold with date bounds, distinct-day counts and row counts.
    """
    rows: list[dict[str, object]] = []
    for train, test, fold in splitter.split(data):
        rows.append(
            {
                "fold_id": fold.fold_id,
                "train_start": fold.train_start,
                "train_end": fold.train_end,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "train_days": train[splitter.date_col].nunique(),
                "test_days": test[splitter.date_col].nunique(),
                "train_rows": len(train),
                "test_rows": len(test),
            }
        )
    return pd.DataFrame(rows)


@dataclass(frozen=True)
class BacktestWindow:
    """One rolling-origin validation window (legacy API)."""

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
    """Yield rolling-origin validation windows (legacy API).

    Prefer :class:`RollingOriginSplitter` for new code; this function is kept
    for backwards compatibility with the earlier notebooks.

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
    """Split data into train and test sets for a backtest window (legacy API)."""
    frame = data.copy()
    frame[date_col] = pd.to_datetime(frame[date_col])
    train = frame[(frame[date_col] >= window.train_start) & (frame[date_col] <= window.train_end)]
    test = frame[(frame[date_col] >= window.test_start) & (frame[date_col] <= window.test_end)]
    return train.copy(), test.copy()
