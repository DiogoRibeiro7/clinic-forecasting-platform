"""Role-specific forecasting and staffing helpers.

Clinical staffing may use either attended demand or completed visits. Front-desk
workload starts earlier in the funnel, so it is sized from scheduled
appointments. All targets use the same fixed-origin recursive forecast contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from clinic_forecast.capacity import add_capacity_targets
from clinic_forecast.intervals import ConformalIntervals
from clinic_forecast.models.global_ml import GlobalMLForecaster
from clinic_forecast.staffing import StaffingRules, recommend_staffing
from clinic_forecast.validation import RollingOriginSplitter

Estimator = Literal["hgb", "xgboost", "lightgbm"]
CLINICAL_TARGET = "attended_demand"
COMPLETED_TARGET = "visits"
FRONTDESK_TARGET = "scheduled_appointments"

SAME_DAY_OUTCOMES: frozenset[str] = frozenset(
    {
        "visits",
        "scheduled_appointments",
        "attended_demand",
        "unmet_demand",
        "capacity_censored",
        "no_show_count",
        "same_day_cancellations",
        "no_show_rate",
        "capacity_utilization",
    }
)


def prepare_target_history(data: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """Return training history containing the target but no other same-day outcome."""
    frame = add_capacity_targets(data)
    if target_col not in frame.columns:
        raise ValueError(f"Unknown role-specific target column: {target_col}")
    drop = [
        column
        for column in SAME_DAY_OUTCOMES
        if column != target_col and column in frame
    ]
    return frame.drop(columns=drop).copy()


def prepare_target_future(data: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """Return a future information set with all realised outcomes removed."""
    frame = add_capacity_targets(data)
    drop = [
        column
        for column in SAME_DAY_OUTCOMES.union({target_col})
        if column in frame
    ]
    return frame.drop(columns=drop).copy()


def recursive_target_forecast(
    train: pd.DataFrame,
    test: pd.DataFrame,
    target_col: str,
    estimator: Estimator = "hgb",
) -> pd.DataFrame:
    """Forecast a complete holdout horizon recursively from one fixed origin."""
    history = prepare_target_history(train, target_col)
    future = prepare_target_future(test, target_col)
    model = GlobalMLForecaster(target_col=target_col, estimator=estimator).fit(history)
    forecast = model.forecast(history=history, future=future)
    forecast["target"] = target_col
    return forecast


def calibrate_target_intervals(
    usage: pd.DataFrame,
    target_col: str,
    estimator: Estimator = "hgb",
    coverage: float = 0.9,
    initial_train_days: int = 365,
    horizon_days: int = 28,
    max_folds: int = 4,
) -> tuple[ConformalIntervals, pd.DataFrame]:
    """Calibrate split-conformal intervals from fixed-origin recursive residuals."""
    enriched = add_capacity_targets(usage)
    splitter = RollingOriginSplitter(
        initial_train_days=initial_train_days,
        horizon_days=horizon_days,
        max_folds=max_folds,
    )
    rows: list[pd.DataFrame] = []
    for train, test, fold in splitter.split(enriched):
        prediction = recursive_target_forecast(
            train=train,
            test=test,
            target_col=target_col,
            estimator=estimator,
        )
        rows.append(
            test[["clinic_id", "date", target_col]]
            .merge(
                prediction[["clinic_id", "date", "forecast"]],
                on=["clinic_id", "date"],
                how="inner",
            )
            .assign(fold=fold.fold_id)
        )
    calibration = pd.concat(rows, ignore_index=True)
    intervals = ConformalIntervals(coverage=coverage, group_col="clinic_id").fit(
        calibration,
        actual_col=target_col,
    )
    return intervals, calibration


@dataclass(frozen=True)
class RoleSpecificForecasts:
    """Target-specific point forecasts and intervals for one common horizon."""

    frame: pd.DataFrame
    clinical_model_name: str
    completed_model_name: str
    frontdesk_model_name: str


def _forecast_target(
    history: pd.DataFrame,
    future: pd.DataFrame,
    target_col: str,
    intervals: ConformalIntervals,
    estimator: Estimator,
    prefix: str,
    model_col: str,
) -> pd.DataFrame:
    """Fit one target model and attach its conformal interval."""
    target_history = prepare_target_history(history, target_col)
    model = GlobalMLForecaster(target_col=target_col, estimator=estimator).fit(
        target_history
    )
    target_future = future.drop(
        columns=[column for column in SAME_DAY_OUTCOMES if column in future.columns],
        errors="ignore",
    )
    forecast = model.forecast(target_history, target_future)
    return intervals.apply(forecast).rename(
        columns={
            "forecast": f"{prefix}_forecast",
            "y_pred": f"{prefix}_pred",
            "y_lower": f"{prefix}_lower",
            "y_upper": f"{prefix}_upper",
            "model": model_col,
        }
    )


def forecast_role_targets(
    history: pd.DataFrame,
    future: pd.DataFrame,
    clinical_intervals: ConformalIntervals,
    completed_intervals: ConformalIntervals,
    frontdesk_intervals: ConformalIntervals,
    estimator: Estimator = "hgb",
) -> RoleSpecificForecasts:
    """Forecast attended, completed and scheduled demand from one fixed origin."""
    clinical = _forecast_target(
        history,
        future,
        CLINICAL_TARGET,
        clinical_intervals,
        estimator,
        "attended",
        "clinical_model",
    )
    completed = _forecast_target(
        history,
        future,
        COMPLETED_TARGET,
        completed_intervals,
        estimator,
        "completed",
        "completed_model",
    )
    frontdesk = _forecast_target(
        history,
        future,
        FRONTDESK_TARGET,
        frontdesk_intervals,
        estimator,
        "scheduled",
        "frontdesk_model",
    )

    merged = clinical.merge(
        completed[
            [
                "clinic_id",
                "date",
                "completed_model",
                "completed_forecast",
                "completed_pred",
                "completed_lower",
                "completed_upper",
            ]
        ],
        on=["clinic_id", "date"],
        how="inner",
    ).merge(
        frontdesk[
            [
                "clinic_id",
                "date",
                "frontdesk_model",
                "scheduled_forecast",
                "scheduled_pred",
                "scheduled_lower",
                "scheduled_upper",
            ]
        ],
        on=["clinic_id", "date"],
        how="inner",
    )
    return RoleSpecificForecasts(
        frame=merged,
        clinical_model_name=f"global_ml_{estimator}_{CLINICAL_TARGET}",
        completed_model_name=f"global_ml_{estimator}_{COMPLETED_TARGET}",
        frontdesk_model_name=f"global_ml_{estimator}_{FRONTDESK_TARGET}",
    )


def recommend_role_specific_staffing(
    forecasts: pd.DataFrame,
    clinical_col: str = "attended_pred",
    frontdesk_col: str = "scheduled_pred",
    rules: StaffingRules | None = None,
) -> pd.DataFrame:
    """Size clinical roles and front desk from their selected demand targets."""
    missing = {clinical_col, frontdesk_col}.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Role-specific forecasts missing columns: {sorted(missing)}")

    clinical_plan = recommend_staffing(
        forecasts,
        forecast_col=clinical_col,
        rules=rules,
    )
    frontdesk_plan = recommend_staffing(
        forecasts,
        forecast_col=frontdesk_col,
        rules=rules,
    )
    output = forecasts.copy()
    output["recommended_clinicians"] = clinical_plan["recommended_clinicians"]
    output["recommended_nurses"] = clinical_plan["recommended_nurses"]
    output["recommended_frontdesk"] = frontdesk_plan["recommended_frontdesk"]
    return output


__all__ = [
    "CLINICAL_TARGET",
    "COMPLETED_TARGET",
    "FRONTDESK_TARGET",
    "RoleSpecificForecasts",
    "SAME_DAY_OUTCOMES",
    "calibrate_target_intervals",
    "forecast_role_targets",
    "prepare_target_future",
    "prepare_target_history",
    "recommend_role_specific_staffing",
    "recursive_target_forecast",
]
