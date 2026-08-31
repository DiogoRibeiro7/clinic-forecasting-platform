"""Run the frozen horizon-resolved hybrid policy uncertainty audit."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from clinic_forecast.horizon_policy_audit import run_horizon_policy_audit
from clinic_forecast.staffing import load_staffing_config


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=root / "data" / "processed"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "reports" / "outputs" / "horizon_policy_audit",
    )
    parser.add_argument(
        "--staffing-config", type=Path, default=root / "configs" / "staffing.yaml"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    usage = pd.read_csv(args.data_dir / "clinic_daily_usage.csv", parse_dates=["date"])
    metadata = pd.read_csv(args.data_dir / "clinic_metadata.csv")
    rules, costs = load_staffing_config(args.staffing_config)
    result = run_horizon_policy_audit(usage, metadata, rules=rules, costs=costs)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.origin_boundaries.to_csv(args.output_dir / "origin_boundaries.csv", index=False)
    result.origin_horizon_policy.to_csv(
        args.output_dir / "origin_horizon_policy.csv", index=False
    )
    result.paired_contrasts.to_csv(args.output_dir / "paired_contrasts.csv", index=False)
    result.horizon_uncertainty.to_csv(
        args.output_dir / "horizon_uncertainty.csv", index=False
    )
    result.weekly_band_uncertainty.to_csv(
        args.output_dir / "weekly_band_uncertainty.csv", index=False
    )
    result.horizon_flags.to_csv(args.output_dir / "horizon_flags.csv", index=False)

    print(result.horizon_flags.to_string(index=False))
    print(f"Wrote horizon-policy audit evidence to {args.output_dir}")


if __name__ == "__main__":
    main()
