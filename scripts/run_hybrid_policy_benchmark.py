"""Run the frozen capacity-aware hybrid policy benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from clinic_forecast.hybrid_benchmark import (
    HybridPolicyBenchmarkConfig,
    run_hybrid_policy_benchmark,
    summarize_hybrid_policy_benchmark,
)
from clinic_forecast.staffing import load_staffing_config


def parse_args() -> argparse.Namespace:
    """Parse benchmark options."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=root / "data" / "processed",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "reports" / "outputs" / "hybrid_policy_benchmark",
    )
    parser.add_argument(
        "--staffing-config",
        type=Path,
        default=root / "configs" / "staffing.yaml",
    )
    parser.add_argument("--initial-train-days", type=int, default=365 * 3)
    parser.add_argument("--horizon", type=int, default=28)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--inner-initial-train-days", type=int, default=365 * 2)
    parser.add_argument("--inner-folds", type=int, default=4)
    parser.add_argument("--coverage", type=float, default=0.9)
    parser.add_argument(
        "--estimator",
        choices=["hgb", "xgboost", "lightgbm"],
        default="hgb",
    )
    return parser.parse_args()


def main() -> None:
    """Execute the prospectively frozen hybrid benchmark and write CSV evidence."""
    args = parse_args()
    usage = pd.read_csv(args.data_dir / "clinic_daily_usage.csv", parse_dates=["date"])
    metadata = pd.read_csv(args.data_dir / "clinic_metadata.csv")
    rules, costs = load_staffing_config(args.staffing_config)
    scores, decisions = run_hybrid_policy_benchmark(
        usage,
        metadata,
        HybridPolicyBenchmarkConfig(
            initial_train_days=args.initial_train_days,
            horizon_days=args.horizon,
            max_folds=args.folds,
            estimator=args.estimator,
            coverage=args.coverage,
            inner_initial_train_days=args.inner_initial_train_days,
            inner_folds=args.inner_folds,
        ),
        rules=rules,
        costs=costs,
    )
    summary = summarize_hybrid_policy_benchmark(scores)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scores.to_csv(args.output_dir / "fold_scores.csv", index=False)
    decisions.to_csv(args.output_dir / "paired_decisions.csv", index=False)
    summary.to_csv(args.output_dir / "summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"Wrote hybrid benchmark evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
