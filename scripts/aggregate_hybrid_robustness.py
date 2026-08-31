"""Aggregate the complete frozen 12-cell hybrid robustness evidence table."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from clinic_forecast.hybrid_robustness import aggregate_robustness_cells


def parse_args() -> argparse.Namespace:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=Path,
        default=root / "reports" / "outputs" / "hybrid_capacity_robustness",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "reports" / "outputs" / "hybrid_capacity_robustness_aggregate",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files = sorted(args.input_root.glob("seed_*_cap_*/cell_summary.csv"))
    cells = [pd.read_csv(path) for path in files]
    table, overview = aggregate_robustness_cells(cells)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.output_dir / "replication_table.csv", index=False)
    overview.to_csv(args.output_dir / "overview.csv", index=False)
    print(overview.to_string(index=False))
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
