"""Verify the locally provable portfolio serving-readiness boundary."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from clinic_forecast.readiness import verify_portfolio_readiness


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Verify immutable serving artefacts, v2 schemas, provenance, and model "
            "bindings. This is not production or clinical certification."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Root output directory containing role_specific and model_registry.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the portfolio readiness verification."""
    args = parse_args()
    summary = verify_portfolio_readiness(args.output_dir)
    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
