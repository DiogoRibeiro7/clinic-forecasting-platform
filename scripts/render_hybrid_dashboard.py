"""Render the latest role-specific hybrid monitoring dashboard."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from clinic_forecast.hybrid_dashboard import render_hybrid_monitoring_dashboard


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--monitoring-csv",
        type=Path,
        default=root / "outputs" / "role_specific" / "monitoring" / "latest.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "outputs" / "role_specific" / "dashboard.html",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.monitoring_csv.exists():
        raise FileNotFoundError(
            f"Hybrid monitoring artifact not found: {args.monitoring_csv}. "
            "Run `make batch-forecast` first."
        )
    frame = pd.read_csv(args.monitoring_csv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_hybrid_monitoring_dashboard(frame))
    print(f"Hybrid monitoring dashboard: {args.output}")


if __name__ == "__main__":
    main()
