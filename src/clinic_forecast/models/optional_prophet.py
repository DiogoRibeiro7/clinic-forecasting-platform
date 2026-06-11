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
