"""Characterize temporal regimes in the frozen NHS GPAD confirmatory artifact."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from clinic_forecast.nhs_origin_regimes import characterize_origins, summarize_winner_groups


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact_dir", type=Path, help="Extracted canonical confirmatory artifact.")
    parser.add_argument("output_dir", type=Path, help="Directory for descriptive CSV outputs.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    artifact_dir = args.artifact_dir
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    fold_scores = pd.read_csv(artifact_dir / "fold_scores.csv")
    origin_boundaries = pd.read_csv(artifact_dir / "origin_boundaries.csv")
    panel = pd.read_csv(artifact_dir / "prepared_attended_sub_icb_day.csv")
    forecast_rows = pd.read_csv(artifact_dir / "forecast_rows.csv")

    origin_table = characterize_origins(
        fold_scores=fold_scores,
        origin_boundaries=origin_boundaries,
        panel=panel,
        forecast_rows=forecast_rows,
    )
    group_summary = summarize_winner_groups(origin_table)

    origin_table.to_csv(output_dir / "origin_regime_descriptors.csv", index=False)
    group_summary.to_csv(output_dir / "winner_group_summary.csv", index=False)

    counts = origin_table["winner"].value_counts().to_dict()
    print(f"Wrote {len(origin_table)} frozen-origin descriptors to {output_dir}")
    print(f"Winner counts: {counts}")


if __name__ == "__main__":
    main()
