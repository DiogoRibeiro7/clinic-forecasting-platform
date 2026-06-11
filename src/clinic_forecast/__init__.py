"""Clinic forecasting platform package."""

from clinic_forecast.data import generate_synthetic_healthcare_data
from clinic_forecast.metrics import ForecastMetrics, compute_metrics

__all__ = [
    "ForecastMetrics",
    "compute_metrics",
    "generate_synthetic_healthcare_data",
]
