"""Optional TimeGPT (Nixtla) foundation-model benchmark.

TimeGPT is an external, paid API: the SDK is an optional dependency, the key
comes from the environment, and **no part of the core project depends on
it**. The wrapper exists so the benchmark is one function call when enabled,
returns the same output schema as every other model in the project, and
fails with actionable messages when it is not configured.

Governance note: calling TimeGPT sends the demand series to an external
service. For a real healthcare network that requires a data-processing
review even for aggregate, non-patient data.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd

MODEL_NAME = "timegpt"


def timegpt_available() -> bool:
    """True when the Nixtla SDK is importable and an API key is configured."""
    try:
        import nixtla  # noqa: F401
    except ImportError:
        return False
    return bool(os.getenv("NIXTLA_API_KEY"))


def timegpt_forecast(
    data: pd.DataFrame,
    horizon: int,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    api_key: str | None = None,
    client: Any | None = None,
) -> pd.DataFrame:
    """Forecast with TimeGPT through the Nixtla SDK.

    Parameters
    ----------
    data:
        Long-format history with id, date and target columns.
    horizon:
        Days to forecast per series.
    api_key:
        Overrides the ``NIXTLA_API_KEY`` environment variable.
    client:
        Pre-built client (used by tests to avoid real API calls). Must expose
        ``forecast(df=..., h=..., time_col=..., target_col=..., id_col=...)``.

    Returns
    -------
    pandas.DataFrame
        ``[id_col, date_col, forecast, model]`` — the same schema as the
        project's other forecasters.
    """
    missing = {id_col, date_col, target_col}.difference(data.columns)
    if missing:
        raise ValueError(f"Input data missing columns: {sorted(missing)}")
    if horizon <= 0:
        raise ValueError("horizon must be positive.")

    if client is None:
        try:
            from nixtla import NixtlaClient
        except ImportError as exc:
            raise ImportError(
                "Nixtla SDK is not installed. Run `poetry install --with optional` "
                "to enable the TimeGPT benchmark."
            ) from exc
        key = api_key or os.getenv("NIXTLA_API_KEY")
        if not key:
            raise ValueError(
                "A Nixtla API key is required: set NIXTLA_API_KEY (see .env.example) "
                "or pass api_key."
            )
        client = NixtlaClient(api_key=key)

    long_frame = data[[id_col, date_col, target_col]].rename(
        columns={id_col: "unique_id", date_col: "ds", target_col: "y"}
    )
    raw = client.forecast(df=long_frame, h=horizon, time_col="ds", target_col="y",
                          id_col="unique_id")

    value_col = "TimeGPT" if "TimeGPT" in raw.columns else "y"
    output = raw.rename(
        columns={"unique_id": id_col, "ds": date_col, value_col: "forecast"}
    )[[id_col, date_col, "forecast"]].copy()
    output["forecast"] = output["forecast"].clip(lower=0)
    output["model"] = MODEL_NAME
    return output
