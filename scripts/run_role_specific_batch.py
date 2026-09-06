"""Run the capacity-aware role-specific clinic forecasting pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from clinic_forecast.pipelines.role_specific_batch import (
    RoleSpecificBatchConfig,
    run_role_specific_batch,
)
from clinic_forecast.serving_snapshot import (
    ServingSnapshotRequest,
    snapshot_role_specific_serving_run,
)


def parse_args() -> argparse.Namespace:
    """Parse role-specific batch options."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizon", type=int, default=28)
    parser.add_argument(
        "--estimator",
        choices=["hgb", "xgboost", "lightgbm"],
        default="hgb",
    )
    parser.add_argument("--coverage", type=float, default=0.9)
    parser.add_argument("--calibration-folds", type=int, default=4)
    parser.add_argument("--initial-train-days", type=int, default=365)
    parser.add_argument("--data-dir", type=Path, default=root / "data" / "processed")
    parser.add_argument("--output-dir", type=Path, default=root / "outputs")
    parser.add_argument(
        "--staffing-config",
        type=Path,
        default=root / "configs" / "staffing.yaml",
    )
    parser.add_argument(
        "--holiday-calendar",
        choices=["legacy_fixed", "england_wales"],
        default=None,
        help=(
            "Optional holiday-calendar override. If generation_manifest.json exists, "
            "the override must match its recorded calendar."
        ),
    )
    return parser.parse_args()


def main() -> None:
    """Run the batch pipeline, snapshot immutable provenance, and print outputs."""
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    config = RoleSpecificBatchConfig(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        horizon_days=args.horizon,
        estimator=args.estimator,
        coverage=args.coverage,
        calibration_folds=args.calibration_folds,
        initial_train_days=args.initial_train_days,
        staffing_config=args.staffing_config,
        holiday_calendar=args.holiday_calendar,
    )
    result = run_role_specific_batch(config)
    manifest = snapshot_role_specific_serving_run(
        ServingSnapshotRequest(
            output_dir=config.output_dir,
            data_dir=config.data_dir,
            origin=str(result.origin.date()),
            estimator=config.estimator,
            horizon_days=config.horizon_days,
            coverage=config.coverage,
            calibration_folds=config.calibration_folds,
            initial_train_days=config.initial_train_days,
            staffing_config=config.staffing_config,
            requested_holiday_calendar=config.holiday_calendar,
            forecast_path=result.forecast_path,
            staffing_path=result.staffing_path,
            monitoring_path=result.monitoring_path,
            repo_root=root,
        )
    )
    print(
        f"Forecast origin {result.origin.date()}, {result.horizon_days} days, "
        f"{result.n_clinics} clinics."
    )
    print(f"Role-specific forecasts: {result.forecast_path}")
    print(f"Role-specific staffing:  {result.staffing_path}")
    print(f"Hybrid monitoring:       {result.monitoring_path}")
    print(f"Serving run:             {manifest.run_id}")
    print(
        "Serving provenance:    "
        f"{config.output_dir / 'role_specific' / 'runs' / manifest.run_id / 'manifest.json'}"
    )


if __name__ == "__main__":
    main()
