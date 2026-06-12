"""Run the batch forecasting pipeline.

Trains the global ML model on the processed data, forecasts the configured
horizon with conformal prediction intervals, derives staffing
recommendations and writes CSVs under `outputs/forecasts/` and
`outputs/staffing/` (dated files plus a stable `latest.csv` for serving).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from clinic_forecast.pipelines.batch_inference import BatchForecastConfig, run_batch_forecast


def parse_args() -> argparse.Namespace:
    """Parse batch pipeline options."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizon", type=int, default=28, help="Forecast horizon in days.")
    parser.add_argument(
        "--estimator",
        choices=["hgb", "xgboost"],
        default="hgb",
        help="Underlying model (xgboost requires the optional dependency group).",
    )
    parser.add_argument(
        "--coverage",
        type=float,
        default=0.9,
        help="Prediction-interval coverage; the upper bound drives conservative staffing.",
    )
    parser.add_argument(
        "--calibration-folds",
        type=int,
        default=2,
        help="Rolling validation folds used to calibrate intervals.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=root / "data" / "processed",
        help="Directory holding the processed contract CSVs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "outputs",
        help="Directory for forecast and staffing outputs.",
    )
    parser.add_argument(
        "--staffing-config",
        type=Path,
        default=root / "configs" / "staffing.yaml",
        help="Staffing rules YAML.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the batch pipeline with CLI options."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    result = run_batch_forecast(
        BatchForecastConfig(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            horizon_days=args.horizon,
            estimator=args.estimator,
            coverage=args.coverage,
            calibration_folds=args.calibration_folds,
            staffing_config=args.staffing_config,
        )
    )
    print(
        f"Forecast origin {result.origin.date()}, {result.horizon_days} days, "
        f"{result.n_clinics} clinics."
    )
    print(f"Forecasts: {result.forecast_path}")
    print(f"Staffing:  {result.staffing_path}")


if __name__ == "__main__":
    main()
