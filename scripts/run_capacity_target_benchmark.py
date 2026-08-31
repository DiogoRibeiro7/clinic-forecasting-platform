"""Run the paired capacity-target benchmark and write reproducible CSV evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from clinic_forecast.capacity_benchmark import (
    CapacityTargetBenchmarkConfig,
    run_capacity_target_benchmark,
    summarize_capacity_target_benchmark,
)


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=root / "data" / "processed" / "clinic_daily_usage.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "reports" / "outputs" / "capacity_target_benchmark",
    )
    parser.add_argument("--initial-train-days", type=int, default=365 * 3)
    parser.add_argument("--horizon", type=int, default=28)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--estimator", choices=["hgb", "xgboost", "lightgbm"], default="hgb")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    usage = pd.read_csv(args.data, parse_dates=["date"])
    scores, predictions = run_capacity_target_benchmark(
        usage,
        CapacityTargetBenchmarkConfig(
            initial_train_days=args.initial_train_days,
            horizon_days=args.horizon,
            max_folds=args.folds,
            estimator=args.estimator,
        ),
    )
    summary = summarize_capacity_target_benchmark(scores)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scores.to_csv(args.output_dir / "fold_scores.csv", index=False)
    predictions.to_csv(args.output_dir / "paired_predictions.csv", index=False)
    summary.to_csv(args.output_dir / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Wrote benchmark evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
