"""Benchmark capacity-censored completed visits against attended demand targets.

The comparison asks whether training on observed completed visits reproduces a
capacity ceiling when the operational objective is to staff for demand that
would attend if capacity were unconstrained. Both candidate models use the same
fixed-origin recursive forecasting contract and are scored against attended
demand on identical rolling-origin folds.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from clinic_forecast.capacity import add_capacity_targets
from clinic_forecast.metrics import compute_metrics
from clinic_forecast.role_specific import CLINICAL_TARGET, recursive_target_forecast
from clinic_forecast.validation import RollingOriginSplitter

COMPLETED_TARGET = "visits"


@dataclass(frozen=True)
class CapacityTargetBenchmarkConfig:
    """Configuration for the paired capacity-target benchmark."""

    initial_train_days: int = 365 * 3
    horizon_days: int = 28
    max_folds: int = 4
    estimator: str = "hgb"


def _score_slice(
    frame: pd.DataFrame,
    forecast_col: str,
    actual_col: str = CLINICAL_TARGET,
) -> dict[str, float | int]:
    if frame.empty:
        return {
            "n_obs": 0,
            "wape": float("nan"),
            "mae": float("nan"),
            "bias": float("nan"),
            "mean_shortfall": float("nan"),
            "underforecast_rate": float("nan"),
        }
    metrics = compute_metrics(frame[actual_col], frame[forecast_col])
    shortfall = (frame[actual_col] - frame[forecast_col]).clip(lower=0)
    return {
        "n_obs": int(len(frame)),
        "wape": metrics.wape,
        "mae": metrics.mae,
        "bias": metrics.bias,
        "mean_shortfall": float(shortfall.mean()),
        "underforecast_rate": float((frame[forecast_col] < frame[actual_col]).mean()),
    }


def run_capacity_target_benchmark(
    usage: pd.DataFrame,
    config: CapacityTargetBenchmarkConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run paired fixed-origin forecasts for completed and attended targets.

    Returns
    -------
    scores:
        One row per fold, model target, and evaluation slice (all/censored/
        uncensored), always scored against realised pre-capacity attended
        demand.
    predictions:
        Row-level paired predictions with the censoring indicator retained.
    """
    cfg = config or CapacityTargetBenchmarkConfig()
    enriched = add_capacity_targets(usage)
    splitter = RollingOriginSplitter(
        initial_train_days=cfg.initial_train_days,
        horizon_days=cfg.horizon_days,
        max_folds=cfg.max_folds,
    )

    score_rows: list[dict[str, object]] = []
    prediction_rows: list[pd.DataFrame] = []
    for train, test, fold in splitter.split(enriched):
        attended_prediction = recursive_target_forecast(
            train=train,
            test=test,
            target_col=CLINICAL_TARGET,
            estimator=cfg.estimator,  # type: ignore[arg-type]
        ).rename(columns={"forecast": "forecast_attended_target"})
        completed_prediction = recursive_target_forecast(
            train=train,
            test=test,
            target_col=COMPLETED_TARGET,
            estimator=cfg.estimator,  # type: ignore[arg-type]
        ).rename(columns={"forecast": "forecast_completed_target"})

        paired = test[
            ["clinic_id", "date", CLINICAL_TARGET, COMPLETED_TARGET, "capacity_censored"]
        ].merge(
            attended_prediction[["clinic_id", "date", "forecast_attended_target"]],
            on=["clinic_id", "date"],
            how="inner",
        ).merge(
            completed_prediction[["clinic_id", "date", "forecast_completed_target"]],
            on=["clinic_id", "date"],
            how="inner",
        )
        paired["fold"] = fold.fold_id
        paired["horizon_days"] = (pd.to_datetime(paired["date"]) - fold.train_end).dt.days
        prediction_rows.append(paired)

        slices = {
            "all": paired,
            "censored": paired[paired["capacity_censored"] == 1],
            "uncensored": paired[paired["capacity_censored"] == 0],
        }
        for model_target, forecast_col in (
            (CLINICAL_TARGET, "forecast_attended_target"),
            (COMPLETED_TARGET, "forecast_completed_target"),
        ):
            for slice_name, slice_frame in slices.items():
                score_rows.append(
                    {
                        "fold": fold.fold_id,
                        "model_target": model_target,
                        "evaluation_target": CLINICAL_TARGET,
                        "slice": slice_name,
                        **_score_slice(slice_frame, forecast_col),
                    }
                )

    if not prediction_rows:
        raise RuntimeError("No rolling-origin folds were available for the requested benchmark.")
    return pd.DataFrame(score_rows), pd.concat(prediction_rows, ignore_index=True)


def summarize_capacity_target_benchmark(scores: pd.DataFrame) -> pd.DataFrame:
    """Summarise benchmark metrics across folds with mean and fold dispersion."""
    metric_cols = ["wape", "mae", "bias", "mean_shortfall", "underforecast_rate"]
    grouped = scores.groupby(["model_target", "slice"], observed=True)[metric_cols]
    means = grouped.mean().add_suffix("_mean")
    stds = grouped.std().add_suffix("_std")
    counts = grouped.size().rename("n_folds")
    return means.join(stds).join(counts).reset_index()


__all__ = [
    "COMPLETED_TARGET",
    "CapacityTargetBenchmarkConfig",
    "run_capacity_target_benchmark",
    "summarize_capacity_target_benchmark",
]
