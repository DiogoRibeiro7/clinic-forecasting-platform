"""Plotting helpers used by notebooks."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def plot_actual_vs_forecast(
    data: pd.DataFrame,
    date_col: str = "date",
    actual_col: str = "visits",
    forecast_col: str = "forecast",
    title: str = "Actual vs forecast",
) -> None:
    """Plot actual and forecasted values."""
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(pd.to_datetime(data[date_col]), data[actual_col], label="actual")
    ax.plot(pd.to_datetime(data[date_col]), data[forecast_col], label="forecast")
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Visits")
    ax.legend()
    fig.tight_layout()
    plt.show()
