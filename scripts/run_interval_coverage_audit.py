from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from clinic_forecast.interval_coverage_audit import (
    IntervalCoverageAuditSpec,
    run_interval_coverage_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the frozen prequential conformal interval coverage audit."
    )
    parser.add_argument(
        "--usage",
        type=Path,
        default=Path("data/processed/clinic_daily_usage.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/outputs/interval_coverage_audit"),
    )
    args = parser.parse_args()

    usage = pd.read_csv(args.usage, parse_dates=["date"])
    spec = IntervalCoverageAuditSpec()
    result = run_interval_coverage_audit(usage, spec)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result.audit_rows.to_csv(args.output_dir / "audit_rows.csv", index=False)
    result.fold_scores.to_csv(args.output_dir / "fold_scores.csv", index=False)
    result.horizon_scores.to_csv(args.output_dir / "horizon_scores.csv", index=False)
    result.clinic_scores.to_csv(args.output_dir / "clinic_scores.csv", index=False)
    (args.output_dir / "summary.json").write_text(
        json.dumps(result.summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "specification.json").write_text(
        json.dumps(
            {
                "coverage": spec.coverage,
                "calibration_folds": spec.calibration_folds,
                "estimator": spec.estimator,
                "initial_train_days": spec.benchmark.initial_train_days,
                "horizon_days": spec.benchmark.horizon_days,
                "step_days": spec.benchmark.step_days,
                "max_folds": spec.benchmark.max_folds,
                "window": spec.benchmark.window,
                "synthetic_seed": spec.benchmark.synthetic_seed,
                "evaluation_mode": "fixed_origin_recursive_prequential",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result.summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
