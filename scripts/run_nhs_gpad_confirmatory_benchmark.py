from __future__ import annotations

import argparse
import json
from pathlib import Path

from clinic_forecast.nhs_gpad_benchmark import run_confirmatory_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen NHS GPAD confirmatory benchmark.")
    parser.add_argument("--archive", required=True)
    parser.add_argument(
        "--source-config",
        default="config/nhs_gpad_june_2026.json",
    )
    parser.add_argument(
        "--panel-policy",
        default="config/nhs_gpad_panel_policy.json",
    )
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument(
        "--output-dir",
        default="reports/outputs/nhs_gpad_confirmatory_benchmark",
    )
    args = parser.parse_args()

    result = run_confirmatory_benchmark(
        args.archive,
        args.source_config,
        args.panel_policy,
        retrieval_timestamp_utc=args.retrieved_at,
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result.quality.source_manifest_path if False else None
    (output_dir / "source_manifest.json").write_text(
        json.dumps(result.quality.source_manifest, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    result.quality.schema_inventory.to_csv(output_dir / "schema_inventory.csv", index=False)
    result.quality.data_quality.to_csv(output_dir / "data_quality.csv", index=False)
    (output_dir / "quality_summary.json").write_text(
        json.dumps(result.quality.quality_summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    result.panel.to_csv(output_dir / "prepared_attended_sub_icb_day.csv", index=False)
    result.origin_boundaries.to_csv(output_dir / "origin_boundaries.csv", index=False)
    result.forecasts.to_csv(output_dir / "forecast_rows.csv", index=False)
    result.fold_scores.to_csv(output_dir / "fold_scores.csv", index=False)
    result.paired_model_contrasts.to_csv(output_dir / "paired_model_contrasts.csv", index=False)
    result.horizon_scores.to_csv(output_dir / "horizon_scores.csv", index=False)
    result.horizon_band_scores.to_csv(output_dir / "horizon_band_scores.csv", index=False)
    result.geography_scores.to_csv(output_dir / "geography_scores.csv", index=False)
    (output_dir / "benchmark_summary.json").write_text(
        json.dumps(result.summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
