"""Production-style batch forecasting pipeline.

One call runs the full chain the notebooks develop interactively:

1. Load the processed contract CSVs and validate them.
2. Calibrate per-clinic conformal intervals on deployment-matched rolling folds.
3. Fit the global ML model on all history.
4. Build a future frame (calendar, opening days, carried-forward marketing
   plan) and forecast the horizon recursively.
5. Attach prediction intervals; zero out closed days.
6. Convert mean and upper-bound forecasts into staffing recommendations.
7. Write dated CSV outputs plus a stable ``latest`` copy for serving.

The pipeline is local-first: plain CSV in, plain CSV out, no services.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import pandas as pd

from clinic_forecast.backtesting import recursive_global_ml_forecast
from clinic_forecast.contracts import validate_clinic_metadata, validate_clinic_usage
from clinic_forecast.holiday_calendar import HolidayCalendarName, holiday_mask
from clinic_forecast.intervals import ConformalIntervals
from clinic_forecast.metrics import compute_metrics
from clinic_forecast.models.global_ml import GlobalMLForecaster
from clinic_forecast.registry import LocalModelRegistry
from clinic_forecast.staffing import StaffingRules, load_staffing_config, recommend_staffing
from clinic_forecast.validation import RollingOriginSplitter

logger = logging.getLogger(__name__)

MARKETING_CARRY_COLUMNS = (
    "marketing_spend",
    "campaign_active",
    "spend_search",
    "spend_social",
    "spend_email",
    "spend_local",
)


@dataclass(frozen=True)
class BatchForecastConfig:
    """Configuration for one batch forecasting run."""

    data_dir: Path
    output_dir: Path
    horizon_days: int = 28
    estimator: Literal["hgb", "xgboost", "lightgbm"] = "hgb"
    coverage: float = 0.9
    calibration_folds: int = 4
    initial_train_days: int = 365
    staffing_config: Path | None = None
    holiday_calendar: HolidayCalendarName | None = None


@dataclass(frozen=True)
class BatchForecastResult:
    """Paths and key figures produced by a batch run."""

    forecast_path: Path
    staffing_path: Path
    origin: pd.Timestamp
    horizon_days: int
    n_clinics: int


def _manifest_calendar(data_dir: Path) -> HolidayCalendarName | None:
    manifest_path = data_dir / "generation_manifest.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Could not read generation manifest: {manifest_path}") from exc
    value = payload.get("holiday_calendar")
    if value not in {"legacy_fixed", "england_wales"}:
        raise ValueError(
            "generation_manifest.json has an unsupported holiday_calendar: "
            f"{value!r}"
        )
    return cast(HolidayCalendarName, value)


def _resolve_holiday_calendar(config: BatchForecastConfig) -> HolidayCalendarName:
    recorded = _manifest_calendar(Path(config.data_dir))
    requested = config.holiday_calendar
    if recorded is None:
        return requested or "legacy_fixed"
    if requested is not None and requested != recorded:
        raise ValueError(
            "Batch holiday calendar does not match generation provenance: "
            f"requested={requested!r}, recorded={recorded!r}."
        )
    return recorded


def make_future_frame(
    usage: pd.DataFrame,
    metadata: pd.DataFrame,
    horizon_days: int,
    holiday_calendar: HolidayCalendarName = "legacy_fixed",
) -> pd.DataFrame:
    """Build the known-inputs frame for the forecast horizon.

    Calendar structure (dates, holidays, opening days) is deterministic.
    Marketing inputs are a *plan assumption*: each clinic's spend and campaign
    flags are carried forward by weekday from its last four weeks. A real
    deployment would replace this with the actual marketing plan.
    """
    origin = pd.to_datetime(usage["date"]).max()
    future_dates = pd.date_range(
        origin + pd.Timedelta(days=1), periods=horizon_days, freq="D"
    )

    recent = usage[pd.to_datetime(usage["date"]) > origin - pd.Timedelta(days=28)].copy()
    recent["day_of_week"] = pd.to_datetime(recent["date"]).dt.dayofweek
    carry_cols = [c for c in MARKETING_CARRY_COLUMNS if c in usage.columns]
    weekday_plan = (
        recent.groupby(["clinic_id", "day_of_week"], observed=True)[carry_cols]
        .mean()
        .reset_index()
    )
    if "campaign_active" in weekday_plan.columns:
        weekday_plan["campaign_active"] = (weekday_plan["campaign_active"] >= 0.5).astype(int)

    frames = []
    holiday_flags = holiday_mask(future_dates, holiday_calendar).astype(int)
    for _, clinic in metadata.iterrows():
        frame = pd.DataFrame({"date": future_dates})
        frame["clinic_id"] = clinic["clinic_id"]
        frame["day_of_week"] = frame["date"].dt.dayofweek
        frame["is_holiday"] = holiday_flags
        weekend_open = bool(clinic.get("weekend_open", 0))
        closed_sunday = (frame["day_of_week"] == 6) & (not weekend_open)
        closed_holiday = (frame["is_holiday"] == 1) & (not weekend_open)
        frame["is_open"] = (~(closed_sunday | closed_holiday)).astype(int)
        frames.append(frame)

    future = pd.concat(frames, ignore_index=True)
    future = future.merge(weekday_plan, on=["clinic_id", "day_of_week"], how="left")
    for col in carry_cols:
        future[col] = future[col].fillna(0.0)
    future = future.merge(metadata, on="clinic_id", how="left")
    return future.drop(columns=["day_of_week"])


def _calibrate_intervals(
    usage: pd.DataFrame, config: BatchForecastConfig
) -> tuple[ConformalIntervals, pd.DataFrame]:
    """Fit conformal intervals on deployment-matched rolling residuals.

    Every fold forecasts its complete holdout horizon recursively from the
    fold origin. Realised targets inside the holdout are never used to build
    lag features. The resulting residual distribution therefore matches the
    batch deployment mechanism instead of a teacher-forced one-step process.
    """
    splitter = RollingOriginSplitter(
        initial_train_days=config.initial_train_days,
        horizon_days=config.horizon_days,
        max_folds=config.calibration_folds,
    )
    calibration_frames: list[pd.DataFrame] = []
    for fold_train, fold_test, fold in splitter.split(usage):
        logger.info("Calibration fold %s: train to %s", fold.fold_id, fold.train_end.date())
        predictions = recursive_global_ml_forecast(
            train=fold_train,
            test=fold_test,
            estimator=config.estimator,
        )
        calibration_frames.append(
            fold_test.merge(
                predictions[["clinic_id", "date", "forecast"]],
                on=["clinic_id", "date"],
                how="inner",
            ).assign(fold=fold.fold_id)
        )
    calibration = pd.concat(calibration_frames, ignore_index=True)
    intervals = ConformalIntervals(coverage=config.coverage, group_col="clinic_id").fit(
        calibration
    )
    return intervals, calibration


def run_batch_forecast(config: BatchForecastConfig) -> BatchForecastResult:
    """Run the full batch pipeline and write forecast and staffing CSVs."""
    usage_path = Path(config.data_dir) / "clinic_daily_usage.csv"
    metadata_path = Path(config.data_dir) / "clinic_metadata.csv"
    if not usage_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            f"Processed data not found in {config.data_dir}. "
            "Run `poetry run python scripts/generate_data.py` first."
        )

    logger.info("Loading and validating data from %s", config.data_dir)
    usage = pd.read_csv(usage_path, parse_dates=["date"])
    metadata = pd.read_csv(metadata_path)
    validate_clinic_usage(usage)
    validate_clinic_metadata(metadata)
    holiday_calendar = _resolve_holiday_calendar(config)
    logger.info("Using holiday calendar: %s", holiday_calendar)

    logger.info(
        "Calibrating %.0f%% conformal intervals on %s fixed-origin folds",
        config.coverage * 100,
        config.calibration_folds,
    )
    conformal, calibration = _calibrate_intervals(usage, config)

    logger.info("Fitting %s model on full history", config.estimator)
    model = GlobalMLForecaster(estimator=config.estimator).fit(usage)

    origin = usage["date"].max()
    future = make_future_frame(
        usage,
        metadata,
        config.horizon_days,
        holiday_calendar=holiday_calendar,
    )
    logger.info(
        "Forecasting %s days for %s clinics from origin %s",
        config.horizon_days,
        metadata["clinic_id"].nunique(),
        origin.date(),
    )
    forecast = model.forecast(history=usage, future=future)
    forecast = forecast.merge(
        future[["clinic_id", "date", "is_open"]], on=["clinic_id", "date"], how="left"
    )
    forecast = conformal.apply(forecast)

    closed = forecast["is_open"] == 0
    forecast.loc[closed, ["forecast", "y_pred", "y_lower", "y_upper"]] = 0.0
    logger.info("Zeroed %s closed clinic-days", int(closed.sum()))

    if config.staffing_config is not None:
        rules, _ = load_staffing_config(config.staffing_config)
    else:
        rules = StaffingRules()
    no_buffer = StaffingRules(
        **{
            **rules.__dict__,
            "buffer_ratio": 0.0,
        }
    )
    mean_plan = recommend_staffing(forecast, forecast_col="y_pred", rules=no_buffer)
    upper_plan = recommend_staffing(forecast, forecast_col="y_upper", rules=no_buffer)
    staffing = mean_plan[
        [
            "clinic_id",
            "date",
            "recommended_clinicians",
            "recommended_nurses",
            "recommended_frontdesk",
        ]
    ].rename(columns=lambda c: c.replace("recommended_", "mean_plan_"))
    for col in ["recommended_clinicians", "recommended_nurses", "recommended_frontdesk"]:
        staffing[col.replace("recommended_", "upper_plan_")] = upper_plan[col]
    staffing.loc[forecast["is_open"] == 0, staffing.columns[2:]] = 0

    forecast_dir = Path(config.output_dir) / "forecasts"
    staffing_dir = Path(config.output_dir) / "staffing"
    forecast_dir.mkdir(parents=True, exist_ok=True)
    staffing_dir.mkdir(parents=True, exist_ok=True)

    stamp = origin.strftime("%Y%m%d")
    forecast_out = forecast[
        ["clinic_id", "date", "model", "is_open", "y_pred", "y_lower", "y_upper"]
    ]
    forecast_path = forecast_dir / f"forecast_{stamp}.csv"
    forecast_out.to_csv(forecast_path, index=False)
    forecast_out.to_csv(forecast_dir / "latest.csv", index=False)

    staffing_path = staffing_dir / f"staffing_{stamp}.csv"
    staffing.to_csv(staffing_path, index=False)
    staffing.to_csv(staffing_dir / "latest.csv", index=False)

    calibration_metrics = compute_metrics(calibration["visits"], calibration["forecast"])
    registry = LocalModelRegistry(Path(config.output_dir) / "model_registry")
    record = registry.register(
        name=model.model_name,
        train_start=str(usage["date"].min().date()),
        train_end=str(origin.date()),
        horizon_days=config.horizon_days,
        metrics={
            "calibration_wape": round(calibration_metrics.wape, 3),
            "calibration_mae": round(calibration_metrics.mae, 3),
            "calibration_bias": round(calibration_metrics.bias, 3),
            "interval_coverage_target": config.coverage,
        },
        features=model.feature_columns_ or [],
        params={
            "estimator": config.estimator,
            "calibration_folds": config.calibration_folds,
            "calibration_mode": "fixed_origin_recursive",
            "holiday_calendar": holiday_calendar,
        },
        artifact_paths={
            "forecasts": str(forecast_path),
            "staffing": str(staffing_path),
        },
    )
    logger.info(
        "Registered %s v%s (recursive calibration WAPE %.1f%%)",
        record.name,
        record.version,
        calibration_metrics.wape,
    )

    logger.info("Wrote %s and %s", forecast_path, staffing_path)
    return BatchForecastResult(
        forecast_path=forecast_path,
        staffing_path=staffing_path,
        origin=origin,
        horizon_days=config.horizon_days,
        n_clinics=int(metadata["clinic_id"].nunique()),
    )


__all__ = [
    "BatchForecastConfig",
    "BatchForecastResult",
    "make_future_frame",
    "run_batch_forecast",
]
