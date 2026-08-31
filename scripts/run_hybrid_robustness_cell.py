"""Run one frozen hybrid capacity-robustness cell."""

from __future__ import annotations

import argparse
from pathlib import Path

from clinic_forecast.hybrid_benchmark import HybridPolicyBenchmarkConfig
from clinic_forecast.hybrid_robustness import (
    ROBUSTNESS_CAPACITY_MULTIPLIERS,
    ROBUSTNESS_SEEDS,
    capacity_label,
    run_hybrid_robustness_cell,
)
from clinic_forecast.staffing import load_staffing_config


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, choices=ROBUSTNESS_SEEDS, required=True)
    parser.add_argument(
        "--capacity-multiplier",
        type=float,
        choices=ROBUSTNESS_CAPACITY_MULTIPLIERS,
        required=True,
    )
    parser.add_argument("--initial-train-days", type=int, default=1095)
    parser.add_argument("--horizon", type=int, default=28)
    parser.add_argument("--folds", type=int, default=4)
    parser.add_argument("--inner-initial-train-days", type=int, default=730)
    parser.add_argument("--inner-folds", type=int, default=4)
    parser.add_argument("--coverage", type=float, default=0.9)
    parser.add_argument("--estimator", choices=["hgb"], default="hgb")
    parser.add_argument(
        "--staffing-config",
        type=Path,
        default=root / "configs" / "staffing.yaml",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=root / "reports" / "outputs" / "hybrid_capacity_robustness",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rules, costs = load_staffing_config(args.staffing_config)
    result = run_hybrid_robustness_cell(
        seed=args.seed,
        capacity_multiplier=args.capacity_multiplier,
        benchmark_config=HybridPolicyBenchmarkConfig(
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
    cell_dir = args.output_root / f"seed_{args.seed}_cap_{capacity_label(args.capacity_multiplier)}"
    cell_dir.mkdir(parents=True, exist_ok=True)
    result.scores.to_csv(cell_dir / "fold_scores.csv", index=False)
    result.summary.to_csv(cell_dir / "summary.csv", index=False)
    result.cell_summary.to_csv(cell_dir / "cell_summary.csv", index=False)
    print(result.cell_summary.to_string(index=False))


if __name__ == "__main__":
    main()
