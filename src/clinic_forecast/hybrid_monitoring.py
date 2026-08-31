"""Descriptive monitoring for the frozen capacity-aware hybrid policy."""

from __future__ import annotations

import pandas as pd


def _summary_row(level: str, group: str, frame: pd.DataFrame) -> dict[str, object]:
    """Summarise hybrid-policy use over open clinic-days."""
    n_days = int(len(frame))
    pressure_days = int(frame["capacity_pressure"].sum())
    attended_days = int((frame["hybrid_target"] == "attended_demand").sum())
    ratio = frame["completed_upper"] / frame["daily_capacity"].clip(lower=1e-9)
    return {
        "level": level,
        "group": group,
        "n_open_days": n_days,
        "capacity_pressure_days": pressure_days,
        "capacity_pressure_rate": pressure_days / n_days if n_days else 0.0,
        "attended_demand_selected_days": attended_days,
        "attended_demand_selected_rate": attended_days / n_days if n_days else 0.0,
        "mean_completed_upper_capacity_ratio": float(ratio.mean()) if n_days else 0.0,
    }


def hybrid_policy_usage_summary(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Summarise when the operational hybrid policy switches clinical targets.

    The summary is descriptive only. It deliberately defines no alert threshold,
    because no monitoring threshold has been prospectively validated.
    """
    required = {
        "clinic_id",
        "capacity_pressure",
        "hybrid_target",
        "completed_upper",
        "daily_capacity",
    }
    missing = required.difference(forecasts.columns)
    if missing:
        raise ValueError(f"Hybrid monitoring missing columns: {sorted(missing)}")

    frame = forecasts.copy()
    if "is_open" in frame.columns:
        frame = frame[frame["is_open"].astype(bool)].copy()

    rows = [
        _summary_row("clinic", str(clinic_id), group)
        for clinic_id, group in frame.groupby("clinic_id", observed=True)
    ]
    rows.append(_summary_row("network", "all", frame))
    return pd.DataFrame(rows)


__all__ = ["hybrid_policy_usage_summary"]
