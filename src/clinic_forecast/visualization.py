"""Plotting helpers used by notebooks.

All functions use Matplotlib only and return the Axes object so notebooks can
annotate or restyle figures without re-plotting.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def plot_actual_vs_forecast(
    data: pd.DataFrame,
    date_col: str = "date",
    actual_col: str = "visits",
    forecast_col: str = "forecast",
    title: str = "Actual vs forecast",
) -> plt.Axes:
    """Plot actual and forecasted values over time."""
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(pd.to_datetime(data[date_col]), data[actual_col], label="actual")
    ax.plot(pd.to_datetime(data[date_col]), data[forecast_col], label="forecast")
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Visits")
    ax.legend()
    fig.tight_layout()
    return ax


def plot_network_demand(
    data: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "visits",
    rolling_days: int = 28,
    title: str = "Network daily demand",
) -> plt.Axes:
    """Plot network-level daily demand with a rolling-mean overlay."""
    daily = data.groupby(date_col, as_index=False)[value_col].sum()
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(daily[date_col], daily[value_col], linewidth=0.5, alpha=0.55, label="daily")
    ax.plot(
        daily[date_col],
        daily[value_col].rolling(rolling_days, center=True).mean(),
        linewidth=1.8,
        label=f"{rolling_days}-day rolling mean",
    )
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel(value_col)
    ax.legend()
    fig.tight_layout()
    return ax


def plot_weekday_profile(
    data: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "visits",
    group_col: str | None = None,
    title: str = "Average demand by day of week",
) -> plt.Axes:
    """Plot mean demand by day of week, optionally one line per group."""
    frame = data.copy()
    frame["_dow"] = pd.to_datetime(frame[date_col]).dt.dayofweek
    fig, ax = plt.subplots(figsize=(8, 4))
    if group_col is None:
        profile = frame.groupby("_dow")[value_col].mean()
        ax.plot(profile.index, profile.values, marker="o")
    else:
        for group, group_frame in frame.groupby(group_col, observed=True):
            profile = group_frame.groupby("_dow")[value_col].mean()
            ax.plot(profile.index, profile.values, marker="o", label=str(group), alpha=0.8)
        ax.legend(title=group_col, fontsize=8)
    ax.set_xticks(range(7), WEEKDAY_LABELS)
    ax.set_title(title)
    ax.set_ylabel(f"mean {value_col}")
    fig.tight_layout()
    return ax


def plot_monthly_profile(
    data: pd.DataFrame,
    date_col: str = "date",
    value_col: str = "visits",
    title: str = "Average demand by month",
) -> plt.Axes:
    """Plot mean demand by calendar month."""
    frame = data.copy()
    frame["_month"] = pd.to_datetime(frame[date_col]).dt.month
    profile = frame.groupby("_month")[value_col].mean()
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(profile.index, profile.values)
    ax.set_xticks(range(1, 13))
    ax.set_title(title)
    ax.set_xlabel("Month")
    ax.set_ylabel(f"mean {value_col}")
    fig.tight_layout()
    return ax


def plot_clinic_ranking(
    data: pd.DataFrame,
    id_col: str = "clinic_id",
    value_col: str = "visits",
    title: str = "Total demand by clinic",
) -> plt.Axes:
    """Plot total demand per clinic, sorted, to show volume concentration."""
    totals = data.groupby(id_col, observed=True)[value_col].sum().sort_values()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(totals.index, totals.values)
    ax.set_title(title)
    ax.set_xlabel(f"total {value_col}")
    fig.tight_layout()
    return ax


def plot_spend_vs_demand(
    data: pd.DataFrame,
    spend_col: str = "marketing_spend",
    value_col: str = "visits",
    sample: int = 2000,
    title: str = "Marketing spend vs demand",
) -> plt.Axes:
    """Scatter marketing spend against demand on open days."""
    frame = data if len(data) <= sample else data.sample(sample, random_state=0)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(frame[spend_col], frame[value_col], s=8, alpha=0.35)
    ax.set_title(title)
    ax.set_xlabel(spend_col)
    ax.set_ylabel(value_col)
    fig.tight_layout()
    return ax


def plot_utilization_distribution(
    data: pd.DataFrame,
    utilization_col: str = "capacity_utilization",
    title: str = "Capacity utilisation distribution (open days)",
) -> plt.Axes:
    """Histogram of capacity utilisation across clinic-days."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(data[utilization_col], bins=40)
    ax.axvline(1.0, linestyle="--", linewidth=1.2, label="capacity")
    ax.set_title(title)
    ax.set_xlabel("visits / daily capacity")
    ax.set_ylabel("clinic-days")
    ax.legend()
    fig.tight_layout()
    return ax
