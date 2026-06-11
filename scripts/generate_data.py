"""Generate synthetic data for the clinic forecasting PoC.

Writes the four contract CSV files under `data/processed/`:
clinic_daily_usage.csv, clinic_metadata.csv, marketing_daily.csv and
staffing_daily.csv. Re-running with the same seed produces identical files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from clinic_forecast.contracts import (
    validate_clinic_metadata,
    validate_clinic_usage,
    validate_marketing,
    validate_staffing_daily,
)
from clinic_forecast.data import SyntheticDataConfig, generate_network_data


def parse_args() -> argparse.Namespace:
    """Parse generator options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2022-01-01", help="First simulated day.")
    parser.add_argument("--end-date", default="2025-12-31", help="Last simulated day.")
    parser.add_argument("--n-clinics", type=int, default=12, help="Number of clinics.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--seasonality-strength",
        type=float,
        default=1.0,
        help="Scale of weekday/seasonal effects (0 disables them).",
    )
    parser.add_argument(
        "--marketing-strength",
        type=float,
        default=1.0,
        help="Scale of demand response to marketing spend.",
    )
    parser.add_argument(
        "--noise-level",
        type=float,
        default=1.0,
        help="Scale of observation noise (0 keeps only structural variation).",
    )
    return parser.parse_args()


def main() -> None:
    """Generate, validate and write the processed CSV files."""
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    config = SyntheticDataConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        n_clinics=args.n_clinics,
        random_seed=args.seed,
        seasonality_strength=args.seasonality_strength,
        marketing_strength=args.marketing_strength,
        noise_level=args.noise_level,
    )
    network = generate_network_data(config)
    validate_clinic_usage(network.usage)
    validate_clinic_metadata(network.metadata)
    validate_marketing(network.marketing)
    validate_staffing_daily(network.staffing)

    network.usage.to_csv(output_dir / "clinic_daily_usage.csv", index=False)
    network.metadata.to_csv(output_dir / "clinic_metadata.csv", index=False)
    network.marketing.to_csv(output_dir / "marketing_daily.csv", index=False)
    network.staffing.to_csv(output_dir / "staffing_daily.csv", index=False)

    print(f"Wrote {len(network.usage):,} usage rows to {output_dir / 'clinic_daily_usage.csv'}")
    print(f"Wrote {len(network.metadata):,} clinics to {output_dir / 'clinic_metadata.csv'}")
    marketing_path = output_dir / "marketing_daily.csv"
    print(f"Wrote {len(network.marketing):,} marketing rows to {marketing_path}")
    print(f"Wrote {len(network.staffing):,} staffing rows to {output_dir / 'staffing_daily.csv'}")


if __name__ == "__main__":
    main()
