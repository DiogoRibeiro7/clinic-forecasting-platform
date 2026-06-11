"""Optional TimeGPT integration through Nixtla."""

from __future__ import annotations

import os

import pandas as pd


def timegpt_forecast(
    data: pd.DataFrame,
    horizon: int,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    api_key: str | None = None,
) -> pd.DataFrame:
    """Call TimeGPT through the Nixtla SDK.

    This function is optional and requires `NIXTLA_API_KEY`.
    """
    try:
        from nixtla import NixtlaClient
    except ImportError as exc:
        raise ImportError(
            "Nixtla SDK is not installed. Run `poetry install --with optional` to enable it."
        ) from exc

    key = api_key or os.getenv("NIXTLA_API_KEY")
    if not key:
        raise ValueError("A Nixtla API key is required. Set NIXTLA_API_KEY or pass api_key.")

    client = NixtlaClient(api_key=key)
    frame = data[[id_col, date_col, target_col]].rename(
        columns={id_col: "unique_id", date_col: "ds", target_col: "y"}
    )
    forecast = client.forecast(
        df=frame, h=horizon, time_col="ds", target_col="y", id_col="unique_id"
    )
    return forecast.rename(columns={"unique_id": id_col, "ds": date_col})
