"""Run a compact end-to-end PoC from data generation to staffing recommendations."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from clinic_forecast.data import generate_synthetic_healthcare_data
from clinic_forecast.metrics import compute_metrics
from clinic_forecast.models.baseline import seasonal_naive_forecast
from clinic_forecast.staffing import recommend_staffing


def main() -> None:
    """Run a fast baseline forecasting PoC."""
    root = Path(__file__).resolve().parents[1]
    output_dir = root / "reports" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    usage, _, _ = generate_synthetic_healthcare_data()
    usage["date"] = pd.to_datetime(usage["date"])
    cutoff = usage["date"].max() - pd.Timedelta(days=28)
    train = usage[usage["date"] <= cutoff]
    test = usage[usage["date"] > cutoff]

    forecast = seasonal_naive_forecast(train=train, future=test)
    scored = test.merge(forecast, on=["clinic_id", "date"], how="left")
    metrics = compute_metrics(scored["visits"], scored["forecast"])
    staffing = recommend_staffing(forecast)

    scored.to_csv(output_dir / "baseline_forecast.csv", index=False)
    staffing.to_csv(output_dir / "staffing_recommendations.csv", index=False)

    print("Baseline metrics")
    print(metrics)
    print(f"Wrote outputs to {output_dir}")


if __name__ == "__main__":
    main()
