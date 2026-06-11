"""SARIMAX forecasting utilities."""

from __future__ import annotations

import warnings

import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX


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


def sarimax_panel_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    exog_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Fit one SARIMAX model per clinic and return panel forecasts."""
    forecasts: list[pd.DataFrame] = []
    for clinic_id, future_group in future.groupby(id_col, observed=True):
        train_group = train.loc[train[id_col] == clinic_id].sort_values(date_col)
        future_group = future_group.sort_values(date_col)
        yhat = sarimax_forecast_one_clinic(
            train=train_group,
            future=future_group,
            target_col=target_col,
            exog_cols=exog_cols,
        )
        local = future_group[[id_col, date_col]].copy()
        local["forecast"] = yhat.to_numpy()
        local["model"] = "sarimax"
        forecasts.append(local)
    return pd.concat(forecasts, ignore_index=True)
