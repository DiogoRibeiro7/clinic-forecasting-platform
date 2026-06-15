"""Wrappers for the Nixtla forecasting ecosystem.

Three frameworks, one common interface and output schema:

- :func:`statsforecast_panel_forecast` — StatsForecast (AutoARIMA, AutoETS, …).
- :func:`mlforecast_panel_forecast` — MLForecast with LightGBM / XGBoost.
- :func:`neuralforecast_panel_forecast` — NeuralForecast (NHITS, NBEATS, …).

Each takes a clinic-level panel and returns the project's common forecast
schema ``[id_col, date_col, forecast, model]``. All imports are lazy and
guarded so the core project never depends on these packages, and each wrapper
accepts a pre-built ``forecaster`` object so the schema-shaping logic can be
unit-tested without importing the heavy native libraries.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

_INSTALL_HINT = "Run `poetry install --with optional` to enable it."


def _to_long(
    panel: pd.DataFrame, id_col: str, date_col: str, target_col: str
) -> pd.DataFrame:
    """Convert a clinic panel to Nixtla long format (unique_id, ds, y)."""
    return panel[[id_col, date_col, target_col]].rename(
        columns={id_col: "unique_id", date_col: "ds", target_col: "y"}
    )


def _from_nixtla_output(
    forecast: pd.DataFrame,
    model_value_col: str,
    model_name: str,
    id_col: str,
    date_col: str,
) -> pd.DataFrame:
    """Reshape a Nixtla forecast frame into the common schema."""
    if model_value_col not in forecast.columns:
        # Fall back to the first non-key column (model column name varies).
        candidates = [c for c in forecast.columns if c not in ("unique_id", "ds")]
        if not candidates:
            raise ValueError("Forecast output has no model column.")
        model_value_col = candidates[0]
    output = forecast.rename(
        columns={"unique_id": id_col, "ds": date_col, model_value_col: "forecast"}
    )[[id_col, date_col, "forecast"]].copy()
    output["forecast"] = output["forecast"].clip(lower=0)
    output["model"] = model_name
    return output


def statsforecast_panel_forecast(
    train: pd.DataFrame,
    horizon: int,
    season_length: int = 7,
    model: str = "AutoETS",
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    freq: str = "D",
    forecaster: Any | None = None,
) -> pd.DataFrame:
    """Forecast with StatsForecast (AutoARIMA / AutoETS / ...).

    Parameters
    ----------
    model:
        ``"AutoETS"`` (default), ``"AutoARIMA"`` or ``"SeasonalNaive"``.
    forecaster:
        Pre-built ``StatsForecast`` instance (used by tests). When omitted a
        StatsForecast with the requested model is constructed.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive.")
    long_df = _to_long(train, id_col, date_col, target_col)

    if forecaster is None:
        try:
            from statsforecast import StatsForecast
            from statsforecast import models as sf_models
        except ImportError as exc:
            raise ImportError(f"StatsForecast is not installed. {_INSTALL_HINT}") from exc
        if not hasattr(sf_models, model):
            raise ValueError(f"Unknown StatsForecast model: {model!r}.")
        model_obj = getattr(sf_models, model)(season_length=season_length)
        forecaster = StatsForecast(models=[model_obj], freq=freq, n_jobs=1)

    forecast = forecaster.forecast(df=long_df, h=horizon)
    return _from_nixtla_output(forecast, model, f"statsforecast_{model}", id_col, date_col)


def mlforecast_panel_forecast(
    train: pd.DataFrame,
    horizon: int,
    estimator: str = "lightgbm",
    lags: tuple[int, ...] = (1, 7, 14, 28),
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    freq: str = "D",
    forecaster: Any | None = None,
) -> pd.DataFrame:
    """Forecast with MLForecast using a LightGBM or XGBoost base learner.

    Parameters
    ----------
    estimator:
        ``"lightgbm"`` (default) or ``"xgboost"``.
    forecaster:
        Pre-built ``MLForecast`` instance (used by tests).
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive.")
    long_df = _to_long(train, id_col, date_col, target_col)

    if forecaster is None:
        try:
            from mlforecast import MLForecast
        except ImportError as exc:
            raise ImportError(f"MLForecast is not installed. {_INSTALL_HINT}") from exc
        if estimator == "lightgbm":
            from lightgbm import LGBMRegressor

            base = LGBMRegressor(n_estimators=300, learning_rate=0.06, verbose=-1, n_jobs=-1)
        elif estimator == "xgboost":
            from xgboost import XGBRegressor

            base = XGBRegressor(n_estimators=300, learning_rate=0.06, n_jobs=-1)
        else:
            raise ValueError(f"Unknown estimator: {estimator!r}; expected lightgbm or xgboost.")
        forecaster = MLForecast(models={"ml": base}, freq=freq, lags=list(lags))

    forecaster.fit(long_df)
    forecast = forecaster.predict(h=horizon)
    return _from_nixtla_output(forecast, "ml", f"mlforecast_{estimator}", id_col, date_col)


def neuralforecast_panel_forecast(
    train: pd.DataFrame,
    horizon: int,
    model: str = "NHITS",
    input_size: int = 56,
    max_steps: int = 200,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
    freq: str = "D",
    forecaster: Any | None = None,
) -> pd.DataFrame:
    """Forecast with NeuralForecast (NHITS / NBEATS / ...).

    Parameters
    ----------
    model:
        ``"NHITS"`` (default) or ``"NBEATS"``.
    forecaster:
        Pre-built ``NeuralForecast`` instance (used by tests).
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive.")
    long_df = _to_long(train, id_col, date_col, target_col)

    if forecaster is None:
        try:
            from neuralforecast import NeuralForecast
            from neuralforecast import models as nf_models
        except ImportError as exc:
            raise ImportError(f"NeuralForecast is not installed. {_INSTALL_HINT}") from exc
        if not hasattr(nf_models, model):
            raise ValueError(f"Unknown NeuralForecast model: {model!r}.")
        model_obj = getattr(nf_models, model)(
            h=horizon, input_size=input_size, max_steps=max_steps
        )
        forecaster = NeuralForecast(models=[model_obj], freq=freq)

    forecaster.fit(long_df)
    forecast = forecaster.predict()
    return _from_nixtla_output(forecast, model, f"neuralforecast_{model}", id_col, date_col)
