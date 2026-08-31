"""Capacity-censoring targets for aggregate clinic demand.

The historical ``visits`` field is an observed outcome after clinic capacity is
applied. For staffing decisions that can itself be a biased target: on a
saturated day, completed visits are lower than the demand that presented for
care. This module reconstructs the pre-capacity attended-demand quantity from
fields already present in the synthetic data and makes the censoring explicit.
"""

from __future__ import annotations

import pandas as pd

REQUIRED_SOURCE_COLUMNS: tuple[str, ...] = (
    "scheduled_appointments",
    "no_show_count",
    "same_day_cancellations",
    "visits",
)

DERIVED_CAPACITY_COLUMNS: tuple[str, ...] = (
    "attended_demand",
    "unmet_demand",
    "capacity_censored",
)


def add_capacity_targets(data: pd.DataFrame) -> pd.DataFrame:
    """Add pre-capacity attended demand and censoring diagnostics.

    ``attended_demand`` is the realised appointment demand remaining after
    no-shows and same-day cancellations but before capacity is applied.
    ``unmet_demand`` is the part of that demand that could not become a
    completed visit because the observed ``visits`` series was capped.
    """
    missing = set(REQUIRED_SOURCE_COLUMNS).difference(data.columns)
    if missing:
        raise ValueError(f"Capacity-target inputs missing columns: {sorted(missing)}")

    frame = data.copy()
    scheduled = pd.to_numeric(frame["scheduled_appointments"], errors="raise")
    no_shows = pd.to_numeric(frame["no_show_count"], errors="raise")
    cancellations = pd.to_numeric(frame["same_day_cancellations"], errors="raise")
    visits = pd.to_numeric(frame["visits"], errors="raise")

    attended = scheduled - no_shows - cancellations
    if (attended < 0).any():
        raise ValueError("No-shows plus cancellations cannot exceed scheduled appointments.")
    if (visits < 0).any():
        raise ValueError("Completed visits cannot be negative.")
    if (visits > attended).any():
        raise ValueError("Completed visits cannot exceed pre-capacity attended demand.")

    frame["attended_demand"] = attended.astype(float)
    frame["unmet_demand"] = (attended - visits).astype(float)
    frame["capacity_censored"] = (frame["unmet_demand"] > 0).astype(int)
    return frame


def validate_capacity_targets(data: pd.DataFrame) -> pd.DataFrame:
    """Validate the algebraic identities of the derived capacity targets."""
    required = set(REQUIRED_SOURCE_COLUMNS).union(DERIVED_CAPACITY_COLUMNS)
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"Capacity-target frame missing columns: {sorted(missing)}")

    expected = add_capacity_targets(data)
    for column in DERIVED_CAPACITY_COLUMNS:
        left = pd.to_numeric(data[column], errors="raise").reset_index(drop=True)
        right = pd.to_numeric(expected[column], errors="raise").reset_index(drop=True)
        if not left.equals(right):
            n_bad = int((left != right).sum())
            raise ValueError(f"Column {column!r} violates its capacity identity on {n_bad} rows.")
    return data


__all__ = [
    "DERIVED_CAPACITY_COLUMNS",
    "REQUIRED_SOURCE_COLUMNS",
    "add_capacity_targets",
    "validate_capacity_targets",
]
