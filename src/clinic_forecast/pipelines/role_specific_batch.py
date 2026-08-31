"""Role-specific batch forecast path for capacity-aware staffing decisions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from clinic_forecast.capacity import add_capacity_targets, validate_capacity_targets
from clinic_forecast.contracts import validate_clinic_metadata, validate_clinic_usage
from clinic_forecast.metrics import compute_metrics
from clinic_forecast.pipelines.batch_inference import make_future_frame
from clinic_forecast.registry import LocalModelRegistry
from clinic_forecast.role_specific import (
    CLINICAL_TARGET,
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


@dataclass(frozen=True)
class RoleSpecificBatchResult:
    """Paths and core metadata from one role-specific batch run."""

    forecast_path: Path
    staffing_path: Path
    origin: pd.Timestamp
    horizon_days: int
    n_clinics: int


def run_role_specific_batch(config: RoleSpecificBatchConfig) -> RoleSpecificBatchResult:
    """Forecast role-relevant targets and produce transparent staffing plans."""
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
    frontdesk_intervals, frontdesk_calibration = calibrate_target_intervals(
        enriched,
        target_col=FRONTDESK_TARGET,
        estimator=config.estimator,
        coverage=config.coverage,
        initial_train_days=config.initial_train_days,
        horizon_days=config.horizon_days,
        max_folds=config.calibration_folds,
    )

    future = make_future_frame(enriched, metadata, config.horizon_days)
    role_forecasts = forecast_role_targets(
        history=enriched,
        future=future,
        clinical_intervals=clinical_intervals,
        frontdesk_intervals=frontdesk_intervals,
        estimator=config.estimator,
    ).frame
    role_forecasts = role_forecasts.merge(
        future[["clinic_id", "date", "is_open"]],
        on=["clinic_id", "date"],
        how="left",
    )

    interval_columns = [
        "attended_forecast",
        "attended_pred",
        "attended_lower",
        "attended_upper",
        "scheduled_forecast",
        "scheduled_pred",
        "scheduled_lower",
        "scheduled_upper",
    ]
    closed = role_forecasts["is_open"] == 0
    role_forecasts.loc[closed, interval_columns] = 0.0

    if config.staffing_config is None:
        rules = StaffingRules()
    else:
        rules, _ = load_staffing_config(config.staffing_config)
    interval_rules = StaffingRules(**{**rules.__dict__, "buffer_ratio": 0.0})

    mean_plan = recommend_role_specific_staffing(
        role_forecasts,
        clinical_col="attended_pred",
        frontdesk_col="scheduled_pred",
        rules=interval_rules,
    )
    upper_plan = recommend_role_specific_staffing(
        role_forecasts,
        clinical_col="attended_upper",
        frontdesk_col="scheduled_upper",
        rules=interval_rules,
    )
    staffing = mean_plan[
        [
            "clinic_id",
            "date",
            "recommended_clinicians",
            "recommended_nurses",
            "recommended_frontdesk",
        ]
    ].rename(columns=lambda column: column.replace("recommended_", "mean_plan_"))
    for column in ["recommended_clinicians", "recommended_nurses", "recommended_frontdesk"]:
        staffing[column.replace("recommended_", "upper_plan_")] = upper_plan[column]
    staffing.loc[closed.to_numpy(), staffing.columns[2:]] = 0

    root = config.output_dir / "role_specific"
    forecast_dir = root / "forecasts"
    staffing_dir = root / "staffing"
    forecast_dir.mkdir(parents=True, exist_ok=True)
    staffing_dir.mkdir(parents=True, exist_ok=True)

    origin = enriched["date"].max()
    stamp = origin.strftime("%Y%m%d")
    forecast_path = forecast_dir / f"forecast_{stamp}.csv"
    staffing_path = staffing_dir / f"staffing_{stamp}.csv"
    role_forecasts.to_csv(forecast_path, index=False)
    role_forecasts.to_csv(forecast_dir / "latest.csv", index=False)
    staffing.to_csv(staffing_path, index=False)
    staffing.to_csv(staffing_dir / "latest.csv", index=False)

    registry = LocalModelRegistry(config.output_dir / "model_registry")
    calibration_runs = [
        (CLINICAL_TARGET, clinical_calibration),
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
            },
            artifact_paths={
                "forecasts": str(forecast_path),
                "staffing": str(staffing_path),
            },
        )

    return RoleSpecificBatchResult(
        forecast_path=forecast_path,
        staffing_path=staffing_path,
        origin=origin,
        horizon_days=config.horizon_days,
        n_clinics=int(metadata["clinic_id"].nunique()),
    )


__all__ = ["RoleSpecificBatchConfig", "RoleSpecificBatchResult", "run_role_specific_batch"]
