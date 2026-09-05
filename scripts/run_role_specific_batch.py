"""Run the capacity-aware role-specific clinic forecasting pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from clinic_forecast.pipelines.role_specific_batch import (
    RoleSpecificBatchConfig,
    run_role_specific_batch,
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
    """Run the role-specific batch pipeline and print artifact locations."""
    args = parse_args()
    result = run_role_specific_batch(
        RoleSpecificBatchConfig(
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
    )
    print(
        f"Forecast origin {result.origin.date()}, {result.horizon_days} days, "
        f"{result.n_clinics} clinics."
    )
    print(f"Role-specific forecasts: {result.forecast_path}")
    print(f"Role-specific staffing:  {result.staffing_path}")
    print(f"Hybrid monitoring:       {result.monitoring_path}")


if __name__ == "__main__":
    main()
