"""Role-specific batch forecast path for capacity-aware staffing decisions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from clinic_forecast.capacity import add_capacity_targets, validate_capacity_targets
from clinic_forecast.contracts import validate_clinic_metadata, validate_clinic_usage
from clinic_forecast.holiday_calendar import HolidayCalendarName
from clinic_forecast.hybrid_monitoring import hybrid_policy_usage_summary
from clinic_forecast.hybrid_policy import select_hybrid_clinical_forecast
from clinic_forecast.metrics import compute_metrics
from clinic_forecast.pipelines.batch_inference import make_future_frame, resolve_holiday_calendar
from clinic_forecast.registry import LocalModelRegistry
from clinic_forecast.role_specific import (
    CLINICAL_TARGET,
    COMPLETED_TARGET,
    FRONTDESK_TARGET,
    calibrate_target_intervals,
    forecast_role_targets,
    recommend_role_specific_staffing,
)
from clinic_forecast.staffing import StaffingRules, load_staffing_config

Estimator = Literal["hgb", "xgboost", "lightgbm"]


@dataclass(frozen=True)
class RoleSpecificBatchConfig:
    """Configuration for the role-specific batch path."""

    data_dir: Path
    output_dir: Path
    horizon_days: int = 28
    estimator: Estimator = "hgb"
    coverage: float = 0.9
    calibration_folds: int = 4
    initial_train_days: int = 365
    staffing_config: Path | None = None
    holiday_calendar: HolidayCalendarName | None = None


@dataclass(frozen=True)
class RoleSpecificBatchResult:
    """Paths and core metadata from one role-specific batch run."""

    forecast_path: Path
    staffing_path: Path
    monitoring_path: Path
    origin: pd.Timestamp
    horizon_days: int
    n_clinics: int


def _selected_upper_bound(forecasts: pd.DataFrame) -> pd.Series:
    """Return the upper interval for whichever clinical target the policy selected."""
    return forecasts["completed_upper"].where(
        forecasts["capacity_pressure"] == 0,
        forecasts["attended_upper"],
    )


def run_role_specific_batch(config: RoleSpecificBatchConfig) -> RoleSpecificBatchResult:
    """Forecast role-relevant targets and produce hybrid clinical staffing plans."""
    usage_path = config.data_dir / "clinic_daily_usage.csv"
    metadata_path = config.data_dir / "clinic_metadata.csv"
    if not usage_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            f"Processed data not found in {config.data_dir}. "
            "Run `poetry run python scripts/generate_data.py` first."
        )

    usage = pd.read_csv(usage_path, parse_dates=["date"])
    metadata = pd.read_csv(metadata_path)
    validate_clinic_usage(usage)
    validate_clinic_metadata(metadata)
    holiday_calendar = resolve_holiday_calendar(config.data_dir, config.holiday_calendar)
    enriched = add_capacity_targets(usage)
    validate_capacity_targets(enriched)

    clinical_intervals, clinical_calibration = calibrate_target_intervals(
        enriched,
        target_col=CLINICAL_TARGET,
        estimator=config.estimator,
        coverage=config.coverage,
        initial_train_days=config.initial_train_days,
        horizon_days=config.horizon_days,
        max_folds=config.calibration_folds,
    )
    completed_intervals, completed_calibration = calibrate_target_intervals(
        enriched,
        target_col=COMPLETED_TARGET,
        estimator=config.estimator,
        coverage=config.coverage,
        initial_train_days=config.initial_train_days,
        horizon_days=config.horizon_days,
        max_folds=config.calibration_folds,
    )
    frontdesk_intervals, frontdesk_calibration = calibrate_target_intervals(
        enriched,
        target_col=FRONTDESK_TARGET,
        estimator=config.estimator,
        coverage=config.coverage,
        initial_train_days=config.initial_train_days,
        horizon_days=config.horizon_days,
        max_folds=config.calibration_folds,
    )

    future = make_future_frame(
        enriched,
        metadata,
        config.horizon_days,
        holiday_calendar=holiday_calendar,
    )
    role_forecasts = forecast_role_targets(
        history=enriched,
        future=future,
        clinical_intervals=clinical_intervals,
        completed_intervals=completed_intervals,
        frontdesk_intervals=frontdesk_intervals,
        estimator=config.estimator,
    ).frame
    role_forecasts = role_forecasts.merge(
        future[["clinic_id", "date", "is_open", "daily_capacity"]],
        on=["clinic_id", "date"],
        how="left",
    )

    interval_columns = [
        "attended_forecast",
        "attended_pred",
        "attended_lower",
        "attended_upper",
        "completed_forecast",
        "completed_pred",
        "completed_lower",
        "completed_upper",
        "scheduled_forecast",
        "scheduled_pred",
        "scheduled_lower",
        "scheduled_upper",
    ]
    closed = role_forecasts["is_open"] == 0
    role_forecasts.loc[closed, interval_columns] = 0.0

    role_forecasts = select_hybrid_clinical_forecast(
        role_forecasts,
        completed_point_col="completed_pred",
        completed_upper_col="completed_upper",
        attended_point_col="attended_pred",
        capacity_col="daily_capacity",
    )
    role_forecasts["hybrid_clinical_upper"] = _selected_upper_bound(role_forecasts)

    if config.staffing_config is None:
        rules = StaffingRules()
    else:
        rules, _ = load_staffing_config(config.staffing_config)
    interval_rules = StaffingRules(**{**rules.__dict__, "buffer_ratio": 0.0})

    mean_plan = recommend_role_specific_staffing(
        role_forecasts,
        clinical_col="hybrid_clinical_forecast",
        frontdesk_col="scheduled_pred",
        rules=interval_rules,
    )
    upper_plan = recommend_role_specific_staffing(
        role_forecasts,
        clinical_col="hybrid_clinical_upper",
        frontdesk_col="scheduled_upper",
        rules=interval_rules,
    )
    staffing = mean_plan[
        [
            "clinic_id",
            "date",
            "daily_capacity",
            "capacity_pressure",
            "hybrid_target",
            "recommended_clinicians",
            "recommended_nurses",
            "recommended_frontdesk",
        ]
    ].rename(columns=lambda column: column.replace("recommended_", "mean_plan_"))
    plan_columns = [
        "mean_plan_clinicians",
        "mean_plan_nurses",
        "mean_plan_frontdesk",
    ]
    for column in [
        "recommended_clinicians",
        "recommended_nurses",
        "recommended_frontdesk",
    ]:
        upper_name = column.replace("recommended_", "upper_plan_")
        staffing[upper_name] = upper_plan[column]
        plan_columns.append(upper_name)
    staffing.loc[closed.to_numpy(), plan_columns] = 0

    monitoring = hybrid_policy_usage_summary(role_forecasts)

    root = config.output_dir / "role_specific"
    forecast_dir = root / "forecasts"
    staffing_dir = root / "staffing"
    monitoring_dir = root / "monitoring"
    forecast_dir.mkdir(parents=True, exist_ok=True)
    staffing_dir.mkdir(parents=True, exist_ok=True)
    monitoring_dir.mkdir(parents=True, exist_ok=True)

    origin = enriched["date"].max()
    stamp = origin.strftime("%Y%m%d")
    forecast_path = forecast_dir / f"forecast_{stamp}.csv"
    staffing_path = staffing_dir / f"staffing_{stamp}.csv"
    monitoring_path = monitoring_dir / f"hybrid_policy_{stamp}.csv"
    role_forecasts.to_csv(forecast_path, index=False)
    role_forecasts.to_csv(forecast_dir / "latest.csv", index=False)
    staffing.to_csv(staffing_path, index=False)
    staffing.to_csv(staffing_dir / "latest.csv", index=False)
    monitoring.to_csv(monitoring_path, index=False)
    monitoring.to_csv(monitoring_dir / "latest.csv", index=False)

    registry = LocalModelRegistry(config.output_dir / "model_registry")
    calibration_runs = [
        (CLINICAL_TARGET, clinical_calibration),
        (COMPLETED_TARGET, completed_calibration),
        (FRONTDESK_TARGET, frontdesk_calibration),
    ]
    for target_col, calibration in calibration_runs:
        metrics = compute_metrics(calibration[target_col], calibration["forecast"])
        registry.register(
            name=f"global_ml_{config.estimator}_{target_col}",
            train_start=str(enriched["date"].min().date()),
            train_end=str(origin.date()),
            horizon_days=config.horizon_days,
            metrics={
                "calibration_wape": round(metrics.wape, 3),
                "calibration_mae": round(metrics.mae, 3),
                "calibration_bias": round(metrics.bias, 3),
                "interval_coverage_target": config.coverage,
            },
            params={
                "estimator": config.estimator,
                "target_col": target_col,
                "calibration_folds": config.calibration_folds,
                "calibration_mode": "fixed_origin_recursive",
                "clinical_policy": "capacity_upper_conformal_hybrid_v1",
                "holiday_calendar": holiday_calendar,
            },
            artifact_paths={
                "forecasts": str(forecast_path),
                "staffing": str(staffing_path),
                "hybrid_monitoring": str(monitoring_path),
            },
        )

    return RoleSpecificBatchResult(
        forecast_path=forecast_path,
        staffing_path=staffing_path,
        monitoring_path=monitoring_path,
        origin=origin,
        horizon_days=config.horizon_days,
        n_clinics=int(metadata["clinic_id"].nunique()),
    )


__all__ = [
    "RoleSpecificBatchConfig",
    "RoleSpecificBatchResult",
    "run_role_specific_batch",
]
