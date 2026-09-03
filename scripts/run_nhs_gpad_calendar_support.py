from __future__ import annotations

import argparse
import json
from pathlib import Path

from clinic_forecast.nhs_gpad_dataexcept import run_gpad_calendar_support_audit_structured


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit NHS GPAD calendar support.")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/nhs_gpad_june_2026.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/outputs/nhs_gpad_calendar_support"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_gpad_calendar_support_audit_structured(args.archive, args.config)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.coverage_monthly.to_csv(args.output_dir / "coverage_monthly.csv", index=False)
    result.calendar_support.to_csv(args.output_dir / "calendar_support.csv", index=False)
    (args.output_dir / "summary.json").write_text(
        json.dumps(result.summary, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result.summary, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
