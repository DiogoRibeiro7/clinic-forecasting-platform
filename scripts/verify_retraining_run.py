"""Verify outputs from one scheduled role-specific retraining rehearsal."""

from __future__ import annotations

import argparse
from pathlib import Path

from clinic_forecast.retraining import verify_role_specific_retraining


def parse_args() -> argparse.Namespace:
    """Parse retraining-verification options."""
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "outputs",
        help="Root output directory written by the role-specific batch pipeline.",
    )
    parser.add_argument(
        "--estimator",
        choices=["hgb", "xgboost", "lightgbm"],
        default="hgb",
    )
    return parser.parse_args()


def main() -> None:
    """Validate the scheduled retraining outputs and print a compact summary."""
    args = parse_args()
    summary = verify_role_specific_retraining(args.output_dir, estimator=args.estimator)
    print(
        "Retraining rehearsal verified: "
        f"train_end={summary.train_end}, horizon={summary.horizon_days}, "
        f"clinics={summary.n_clinics}."
    )
    for name, version in sorted(summary.model_versions.items()):
        print(f"Registered model: {name} v{version}")


if __name__ == "__main__":
    main()
