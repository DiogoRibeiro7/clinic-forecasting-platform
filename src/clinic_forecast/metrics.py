"""Forecast evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ForecastMetrics:
    """Container for common forecast metrics."""

    mae: float
    rmse: float
    mape: float
    smape: float
    wape: float
    bias: float


def _as_float_array(values: pd.Series | np.ndarray | list[float]) -> np.ndarray:
    """Convert input values to a one-dimensional float array."""
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise ValueError("Metric inputs must be one-dimensional.")
    return array


def compute_metrics(
    y_true: pd.Series | np.ndarray | list[float],
    y_pred: pd.Series | np.ndarray | list[float],
) -> ForecastMetrics:
    """Compute standard forecasting metrics.

    Parameters
    ----------
    y_true:
        Observed values.
    y_pred:
        Forecast values.

    Returns
    -------
    ForecastMetrics
        MAE, RMSE, MAPE, sMAPE, WAPE and bias.
    """
    actual = _as_float_array(y_true)
    pred = _as_float_array(y_pred)

    if len(actual) != len(pred):
        raise ValueError("y_true and y_pred must have the same length.")
    if len(actual) == 0:
        raise ValueError("Metric inputs cannot be empty.")

    error = pred - actual
    abs_error = np.abs(error)
    non_zero = actual != 0

    mae = float(np.mean(abs_error))
    rmse = float(np.sqrt(np.mean(error**2)))
    if non_zero.any():
        mape = float(np.mean(abs_error[non_zero] / np.abs(actual[non_zero])) * 100)
    else:
        mape = float("nan")
    denominator = np.abs(actual) + np.abs(pred)
    smape_terms = np.divide(
        2 * abs_error, denominator, out=np.zeros_like(abs_error), where=denominator != 0
    )
    smape = float(np.mean(smape_terms) * 100)
    wape = float(abs_error.sum() / np.maximum(np.abs(actual).sum(), 1e-12) * 100)
    bias = float(error.sum() / np.maximum(np.abs(actual).sum(), 1e-12) * 100)

    return ForecastMetrics(mae=mae, rmse=rmse, mape=mape, smape=smape, wape=wape, bias=bias)


def metrics_by_group(
    data: pd.DataFrame,
    group_col: str,
    actual_col: str,
    forecast_col: str,
) -> pd.DataFrame:
    """Compute forecast metrics by group."""
    rows: list[dict[str, float | str]] = []
    for group, frame in data.groupby(group_col, observed=True):
        metrics = compute_metrics(frame[actual_col], frame[forecast_col])
        rows.append({group_col: str(group), **metrics.__dict__})
    return pd.DataFrame(rows)
