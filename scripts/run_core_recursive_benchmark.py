from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from clinic_forecast.core_benchmark_runner import run_core_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the frozen core recursive benchmark.")
    parser.add_argument(
        "--usage",
        type=Path,
        default=Path("data/processed/clinic_daily_usage.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/outputs/core_recursive_benchmark"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    usage = pd.read_csv(args.usage, parse_dates=["date"])
    result = run_core_benchmark(usage)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "specification.json").write_text(
        json.dumps(result.specification, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    result.fold_boundaries.to_csv(args.output_dir / "fold_boundaries.csv", index=False)
    result.forecast_rows.to_csv(args.output_dir / "forecast_rows.csv", index=False)
    result.fold_scores.to_csv(args.output_dir / "fold_scores.csv", index=False)
    result.leaderboard.to_csv(args.output_dir / "leaderboard.csv", index=False)
    result.paired_contrasts.to_csv(args.output_dir / "paired_contrasts.csv", index=False)
    result.horizon_scores.to_csv(args.output_dir / "horizon_scores.csv", index=False)
    result.clinic_scores.to_csv(args.output_dir / "clinic_scores.csv", index=False)

    print(result.leaderboard.to_string(index=False))


if __name__ == "__main__":
    main()
