"""Clinic forecasting platform package."""

__version__ = "0.3.0"

from clinic_forecast.data import generate_synthetic_healthcare_data
from clinic_forecast.metrics import ForecastMetrics, compute_metrics

__all__ = [
    "__version__",
    "ForecastMetrics",
    "compute_metrics",
    "generate_synthetic_healthcare_data",
]
