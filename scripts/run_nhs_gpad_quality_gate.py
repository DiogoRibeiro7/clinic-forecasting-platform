from __future__ import annotations

import argparse
import json
from pathlib import Path

from clinic_forecast.nhs_gpad import run_gpad_quality_gate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the frozen NHS GPAD daily archive.")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/nhs_gpad_june_2026.json"),
    )
    parser.add_argument("--retrieval-timestamp-utc", required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/outputs/nhs_gpad_quality_gate"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_gpad_quality_gate(
        archive_path=args.archive,
        config_path=args.config,
        retrieval_timestamp_utc=args.retrieval_timestamp_utc,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "source_manifest.json").write_text(
        json.dumps(result.source_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result.schema_inventory.to_csv(args.output_dir / "schema_inventory.csv", index=False)
    result.data_quality.to_csv(args.output_dir / "data_quality.csv", index=False)
    (args.output_dir / "quality_summary.json").write_text(
        json.dumps(result.quality_summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    result.prepared_daily.to_csv(args.output_dir / "prepared_attended_sub_icb_day.csv", index=False)
    print(json.dumps(result.quality_summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
