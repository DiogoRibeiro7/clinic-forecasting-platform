"""Optional Prophet integration.

Prophet is intentionally kept behind an optional import because installation can
be heavier than the core PoC dependencies.
"""

from __future__ import annotations

import pandas as pd


def prophet_forecast_one_clinic(
    train: pd.DataFrame,
    periods: int,
    date_col: str = "date",
    target_col: str = "visits",
) -> pd.DataFrame:
    """Fit Prophet for one clinic and return a future forecast.

    Raises
    ------
    ImportError
        If Prophet is not installed.
    """
    try:
        from prophet import Prophet
    except ImportError as exc:
        raise ImportError(
            "Prophet is not installed. Run `poetry install --with optional` to enable it."
        ) from exc

    prophet_train = train[[date_col, target_col]].rename(columns={date_col: "ds", target_col: "y"})
    model = Prophet(weekly_seasonality=True, yearly_seasonality=True, daily_seasonality=False)
    model.fit(prophet_train)
    future = model.make_future_dataframe(periods=periods, freq="D", include_history=False)
    forecast = model.predict(future)
    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].rename(columns={"ds": date_col})


def prophet_panel_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    add_holiday_regressor: bool = True,
) -> pd.DataFrame:
    """Fit one Prophet model per clinic and return panel forecasts.

    Returns the project's common forecast schema
    (``[id_col, date_col, forecast, model]``) so Prophet can be compared and
    consumed exactly like every other model. Forecasts are clipped at zero.
    Forecast dates are taken from ``future``; only its calendar is used, not
    its target values.

    Raises
    ------
    ImportError
        If Prophet is not installed.
    """
    try:
        from prophet import Prophet
    except ImportError as exc:
        raise ImportError(
            "Prophet is not installed. Run `poetry install --with optional` to enable it."
        ) from exc

    use_holiday = add_holiday_regressor and "is_holiday" in train.columns and (
        "is_holiday" in future.columns
    )

    forecasts: list[pd.DataFrame] = []
    for clinic_id, future_group in future.groupby(id_col, observed=True):
        train_group = train.loc[train[id_col] == clinic_id].sort_values(date_col)
        future_group = future_group.sort_values(date_col)

        fit_frame = train_group[[date_col, target_col]].rename(
            columns={date_col: "ds", target_col: "y"}
        )
        model = Prophet(
            weekly_seasonality=True, yearly_seasonality=True, daily_seasonality=False
        )
        if use_holiday:
            fit_frame["is_holiday"] = train_group["is_holiday"].to_numpy()
            model.add_regressor("is_holiday")
        model.fit(fit_frame)

        horizon_frame = future_group[[date_col]].rename(columns={date_col: "ds"})
        if use_holiday:
            horizon_frame["is_holiday"] = future_group["is_holiday"].to_numpy()
        predicted = model.predict(horizon_frame)

        local = future_group[[id_col, date_col]].copy()
        local["forecast"] = predicted["yhat"].clip(lower=0).to_numpy()
        local["model"] = "prophet"
        forecasts.append(local)

    return pd.concat(forecasts, ignore_index=True)
