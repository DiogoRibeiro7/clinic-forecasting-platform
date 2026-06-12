"""SARIMAX forecasting utilities.

Beyond a single fixed-order fit, :func:`select_sarimax_order` runs a small
backtest-based search over a handful of sensible candidate orders and picks
the one with the lowest holdout WAPE, with a hard cap on the number of
candidates so runtime stays bounded. The default grid is deliberately tiny:
exhaustive SARIMAX search does not pay for itself on operational daily data.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from clinic_forecast.metrics import compute_metrics

Order = tuple[int, int, int]
SeasonalOrder = tuple[int, int, int, int]

#: Small default candidate grid (non-seasonal order, seasonal order).
DEFAULT_SARIMAX_CANDIDATES: tuple[tuple[Order, SeasonalOrder], ...] = (
    ((1, 1, 1), (1, 0, 1, 7)),
    ((2, 1, 1), (1, 0, 1, 7)),
    ((1, 1, 2), (0, 1, 1, 7)),
    ((0, 1, 1), (1, 0, 0, 7)),
    ((1, 0, 1), (1, 1, 0, 7)),
)


@dataclass(frozen=True)
class SarimaxSelection:
    """Result of a SARIMAX candidate search for one clinic."""

    order: Order
    seasonal_order: SeasonalOrder
    wape: float
    candidates_tried: int


def sarimax_forecast_one_clinic(
    train: pd.DataFrame,
    future: pd.DataFrame,
    target_col: str = "visits",
    exog_cols: list[str] | None = None,
    order: tuple[int, int, int] = (1, 1, 1),
    seasonal_order: tuple[int, int, int, int] = (1, 0, 1, 7),
) -> pd.Series:
    """Fit SARIMAX for one clinic and forecast the future horizon."""
    if target_col not in train.columns:
        raise ValueError(f"Missing target column: {target_col}")

    y_train = train[target_col].astype(float)
    train_exog = train[exog_cols].astype(float) if exog_cols else None
    future_exog = future[exog_cols].astype(float) if exog_cols else None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SARIMAX(
            y_train,
            exog=train_exog,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        result = model.fit(disp=False, maxiter=80)
        forecast = result.forecast(steps=len(future), exog=future_exog)

    return pd.Series(forecast.to_numpy(), index=future.index, name="forecast")


def select_sarimax_order(
    train: pd.DataFrame,
    target_col: str = "visits",
    exog_cols: list[str] | None = None,
    candidates: tuple[tuple[Order, SeasonalOrder], ...] = DEFAULT_SARIMAX_CANDIDATES,
    validation_days: int = 28,
    max_candidates: int = 5,
) -> SarimaxSelection:
    """Pick a SARIMAX order by backtest WAPE on a holdout tail.

    The last ``validation_days`` of ``train`` form an internal holdout. Each
    candidate (up to ``max_candidates``) is fit on the remainder and scored;
    the lowest-WAPE candidate wins. Candidates that fail to fit are skipped.
    """
    if validation_days <= 0:
        raise ValueError("validation_days must be positive.")
    ordered = train.sort_values("date")
    if len(ordered) <= validation_days + 14:
        raise ValueError("Not enough history to select a SARIMAX order.")

    inner_train = ordered.iloc[:-validation_days]
    holdout = ordered.iloc[-validation_days:]
    actual = holdout[target_col].astype(float).to_numpy()

    best: SarimaxSelection | None = None
    tried = 0
    for order, seasonal_order in candidates[:max_candidates]:
        tried += 1
        try:
            yhat = sarimax_forecast_one_clinic(
                train=inner_train,
                future=holdout,
                target_col=target_col,
                exog_cols=exog_cols,
                order=order,
                seasonal_order=seasonal_order,
            )
        except (ValueError, np.linalg.LinAlgError):
            continue
        wape = compute_metrics(actual, yhat.to_numpy()).wape
        if best is None or wape < best.wape:
            best = SarimaxSelection(
                order=order, seasonal_order=seasonal_order, wape=wape, candidates_tried=tried
            )

    if best is None:
        # Every candidate failed; fall back to the canonical order.
        return SarimaxSelection((1, 1, 1), (1, 0, 1, 7), wape=float("nan"), candidates_tried=tried)
    return best


def sarimax_panel_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    exog_cols: list[str] | None = None,
    auto_order: bool = False,
    validation_days: int = 28,
) -> pd.DataFrame:
    """Fit one SARIMAX model per clinic and return panel forecasts.

    With ``auto_order=True`` each clinic's order is chosen by
    :func:`select_sarimax_order` on its own history; otherwise the canonical
    ``(1,1,1)(1,0,1,7)`` order is used for every clinic.
    """
    forecasts: list[pd.DataFrame] = []
    for clinic_id, future_group in future.groupby(id_col, observed=True):
        train_group = train.loc[train[id_col] == clinic_id].sort_values(date_col)
        future_group = future_group.sort_values(date_col)

        if auto_order:
            selection = select_sarimax_order(
                train_group,
                target_col=target_col,
                exog_cols=exog_cols,
                validation_days=validation_days,
            )
            order, seasonal_order = selection.order, selection.seasonal_order
        else:
            order, seasonal_order = (1, 1, 1), (1, 0, 1, 7)

        yhat = sarimax_forecast_one_clinic(
            train=train_group,
            future=future_group,
            target_col=target_col,
            exog_cols=exog_cols,
            order=order,
            seasonal_order=seasonal_order,
        )
        local = future_group[[id_col, date_col]].copy()
        local["forecast"] = yhat.to_numpy()
        local["model"] = "sarimax_auto" if auto_order else "sarimax"
        forecasts.append(local)
    return pd.concat(forecasts, ignore_index=True)
