"""Training pipeline helpers."""

from __future__ import annotations

from clinic_forecast.models.ml import GlobalMLForecaster


def build_global_ml_forecaster() -> GlobalMLForecaster:
    """Create the default global ML forecaster."""
    return GlobalMLForecaster()
