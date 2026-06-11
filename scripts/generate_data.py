"""Generate synthetic data for the clinic forecasting PoC."""

from __future__ import annotations

from pathlib import Path

from clinic_forecast.data import SyntheticDataConfig, generate_synthetic_healthcare_data


def main() -> None:
    """Generate raw CSV files under `data/raw`."""
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    usage, metadata, marketing = generate_synthetic_healthcare_data(SyntheticDataConfig())
    usage.to_csv(output_dir / "clinic_usage.csv", index=False)
    metadata.to_csv(output_dir / "clinic_metadata.csv", index=False)
    marketing.to_csv(output_dir / "marketing.csv", index=False)

    print(f"Wrote {len(usage):,} usage rows to {output_dir / 'clinic_usage.csv'}")


if __name__ == "__main__":
    main()
