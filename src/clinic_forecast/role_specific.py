"""Role-specific forecasting and staffing helpers.

Clinical staff should be sized from demand that would attend if capacity were
unconstrained. Front-desk workload starts earlier in the funnel, so it is sized
from scheduled appointments. Both targets are evaluated with the same
fixed-origin recursive contract as the production forecast path.
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
    drop = [column for column in SAME_DAY_OUTCOMES if column != target_col and column in frame]
    return frame.drop(columns=drop).copy()


def prepare_target_future(data: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """Return a future information set with all realised outcomes removed."""
    frame = add_capacity_targets(data)
    drop = [column for column in SAME_DAY_OUTCOMES.union({target_col}) if column in frame]
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
    frontdesk_model_name: str


def forecast_role_targets(
    history: pd.DataFrame,
    future: pd.DataFrame,
    clinical_intervals: ConformalIntervals,
    frontdesk_intervals: ConformalIntervals,
    estimator: Estimator = "hgb",
) -> RoleSpecificForecasts:
    """Forecast attended and scheduled demand from the same fixed origin."""
    clinical_history = prepare_target_history(history, CLINICAL_TARGET)
    frontdesk_history = prepare_target_history(history, FRONTDESK_TARGET)

    clinical_model = GlobalMLForecaster(
        target_col=CLINICAL_TARGET,
        estimator=estimator,
    ).fit(clinical_history)
    frontdesk_model = GlobalMLForecaster(
        target_col=FRONTDESK_TARGET,
        estimator=estimator,
    ).fit(frontdesk_history)

    clinical_future = future.drop(
        columns=[column for column in SAME_DAY_OUTCOMES if column in future.columns],
        errors="ignore",
    )
    frontdesk_future = clinical_future.copy()

    clinical = clinical_model.forecast(clinical_history, clinical_future)
    clinical = clinical_intervals.apply(clinical).rename(
        columns={
            "forecast": "attended_forecast",
            "y_pred": "attended_pred",
            "y_lower": "attended_lower",
            "y_upper": "attended_upper",
            "model": "clinical_model",
        }
    )
    frontdesk = frontdesk_model.forecast(frontdesk_history, frontdesk_future)
    frontdesk = frontdesk_intervals.apply(frontdesk).rename(
        columns={
            "forecast": "scheduled_forecast",
            "y_pred": "scheduled_pred",
            "y_lower": "scheduled_lower",
            "y_upper": "scheduled_upper",
            "model": "frontdesk_model",
        }
    )
    merged = clinical.merge(
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
        frontdesk_model_name=f"global_ml_{estimator}_{FRONTDESK_TARGET}",
    )


def recommend_role_specific_staffing(
    forecasts: pd.DataFrame,
    clinical_col: str = "attended_pred",
    frontdesk_col: str = "scheduled_pred",
    rules: StaffingRules | None = None,
) -> pd.DataFrame:
    """Size clinical roles from attended demand and front desk from scheduled demand."""
    missing = {clinical_col, frontdesk_col}.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Role-specific forecasts missing columns: {sorted(missing)}")

    clinical_plan = recommend_staffing(forecasts, forecast_col=clinical_col, rules=rules)
    frontdesk_plan = recommend_staffing(forecasts, forecast_col=frontdesk_col, rules=rules)
    output = forecasts.copy()
    output["recommended_clinicians"] = clinical_plan["recommended_clinicians"]
    output["recommended_nurses"] = clinical_plan["recommended_nurses"]
    output["recommended_frontdesk"] = frontdesk_plan["recommended_frontdesk"]
    return output


__all__ = [
    "CLINICAL_TARGET",
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
