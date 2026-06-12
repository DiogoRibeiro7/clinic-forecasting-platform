"""Model comparison utilities.

All metric values come from :func:`clinic_forecast.metrics.compute_metrics`,
so every notebook and pipeline shares one set of metric definitions. The
functions here handle the bookkeeping around those metrics: grouping by model,
clinic, region or horizon, prediction-interval quality, ranking and concise
comparison tables.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from clinic_forecast.metrics import compute_metrics

METRIC_COLUMNS = ["mae", "rmse", "mape", "smape", "wape", "bias"]


def add_horizon(
    data: pd.DataFrame,
    origin: pd.Timestamp | str,
    date_col: str = "date",
) -> pd.DataFrame:
    """Add a ``horizon_days`` column: days between the forecast origin and each row.

    Parameters
    ----------
    data:
        Scored forecast frame.
    origin:
        The forecast origin (last training date). Horizon 1 is the first
        forecast day.
    date_col:
        Date column name.
    """
    frame = data.copy()
    origin_ts = pd.Timestamp(origin)
    frame["horizon_days"] = (pd.to_datetime(frame[date_col]) - origin_ts).dt.days
    if (frame["horizon_days"] <= 0).any():
        raise ValueError("All rows must be after the forecast origin.")
    return frame


def evaluate_forecasts(
    data: pd.DataFrame,
    model_col: str = "model",
    actual_col: str = "visits",
    forecast_col: str = "forecast",
    group_cols: list[str] | None = None,
    lower_col: str | None = None,
    upper_col: str | None = None,
) -> pd.DataFrame:
    """Compute metrics per model and optional extra grouping columns.

    Rows with a missing forecast are dropped (and counted in the
    ``n_missing_forecasts`` column) rather than poisoning the metrics; groups
    left empty after dropping are skipped.

    Parameters
    ----------
    data:
        Long frame with one row per (model, entity, date) holding actuals and
        forecasts. Multiple models are stacked with ``model_col`` labelling.
    group_cols:
        Extra grouping columns, e.g. ``["clinic_id"]``, ``["region"]`` or
        ``["fold"]`` / ``["horizon_days"]``.
    lower_col, upper_col:
        Optional prediction-interval bounds. When both are given, the output
        gains ``coverage`` (share of actuals inside the interval) and
        ``interval_width`` (mean upper - lower).

    Returns
    -------
    pandas.DataFrame
        One row per (model, *group_cols*) with metric columns.
    """
    if model_col not in data.columns:
        raise ValueError(f"Missing model column: {model_col}")
    keys = [model_col] + (group_cols or [])
    missing_cols = set(keys + [actual_col, forecast_col]).difference(data.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns: {sorted(missing_cols)}")

    rows: list[dict[str, object]] = []
    for group_key, frame in data.groupby(keys, observed=True):
        key_values = group_key if isinstance(group_key, tuple) else (group_key,)
        valid = frame.dropna(subset=[forecast_col])
        n_missing = len(frame) - len(valid)
        if valid.empty:
            continue
        metrics = compute_metrics(valid[actual_col], valid[forecast_col])
        row: dict[str, object] = dict(zip(keys, key_values, strict=True))
        row.update(metrics.__dict__)
        row["n_obs"] = len(valid)
        row["n_missing_forecasts"] = n_missing
        if lower_col is not None and upper_col is not None:
            inside = (valid[actual_col] >= valid[lower_col]) & (
                valid[actual_col] <= valid[upper_col]
            )
            row["coverage"] = float(inside.mean())
            row["interval_width"] = float((valid[upper_col] - valid[lower_col]).mean())
        rows.append(row)
    return pd.DataFrame(rows)


def rank_models(
    results: pd.DataFrame,
    primary_metric: str = "wape",
    model_col: str = "model",
) -> pd.DataFrame:
    """Rank models by the mean of a primary metric (lower is better).

    Parameters
    ----------
    results:
        Output of :func:`evaluate_forecasts` (possibly grouped).
    primary_metric:
        Metric column used for ranking.
    """
    if primary_metric not in results.columns:
        raise ValueError(f"Unknown metric column: {primary_metric}")
    summary = (
        results.groupby(model_col, observed=True)[primary_metric]
        .agg(["mean", "std", "count"])
        .sort_values("mean")
        .rename(
            columns={
                "mean": f"{primary_metric}_mean",
                "std": f"{primary_metric}_std",
                "count": "n_groups",
            }
        )
    )
    summary["rank"] = np.arange(1, len(summary) + 1)
    return summary.reset_index()


def comparison_table(
    results: pd.DataFrame,
    model_col: str = "model",
    metrics: tuple[str, ...] = ("mae", "rmse", "wape", "bias"),
) -> pd.DataFrame:
    """Build a concise model-by-metric comparison table (means across groups)."""
    available = [m for m in metrics if m in results.columns]
    extra = [m for m in ("coverage", "interval_width") if m in results.columns]
    table = (
        results.groupby(model_col, observed=True)[available + extra]
        .mean()
        .sort_values(available[0] if available else extra[0])
    )
    return table.round(3)
