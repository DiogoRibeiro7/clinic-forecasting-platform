"""Run the paired clinical staffing decision benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from clinic_forecast.decision_benchmark import (
    StaffingDecisionBenchmarkConfig,
    run_staffing_decision_benchmark,
    summarize_staffing_decision_benchmark,
)
from clinic_forecast.staffing import load_staffing_config


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=root / "data" / "processed" / "clinic_daily_usage.csv",
    )
    parser.add_argument(
        "--staffing-config",
        type=Path,
        default=root / "configs" / "staffing.yaml",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "reports" / "outputs" / "staffing_decision_benchmark",
    )
    parser.add_argument("--initial-train-days", type=int, default=365 * 3)
    parser.add_argument("--horizon", type=int, default=28)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--estimator", choices=["hgb", "xgboost", "lightgbm"], default="hgb")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    usage = pd.read_csv(args.data, parse_dates=["date"])
    rules, costs = load_staffing_config(args.staffing_config)
    scores, decisions = run_staffing_decision_benchmark(
        usage,
        StaffingDecisionBenchmarkConfig(
            initial_train_days=args.initial_train_days,
            horizon_days=args.horizon,
            max_folds=args.folds,
            estimator=args.estimator,
        ),
        rules=rules,
        costs=costs,
    )
    summary = summarize_staffing_decision_benchmark(scores)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scores.to_csv(args.output_dir / "fold_scores.csv", index=False)
    decisions.to_csv(args.output_dir / "paired_decisions.csv", index=False)
    summary.to_csv(args.output_dir / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Wrote decision benchmark evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
