"""Synthetic healthcare-network data generation.

The generator creates aggregate clinic-level operational data. It is intentionally
free of patient-level fields and protected health information.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

SPECIALTIES: Final[tuple[str, ...]] = (
    "primary_care",
    "urgent_care",
    "cardiology",
    "orthopedics",
    "pediatrics",
)

REGIONS: Final[tuple[str, ...]] = ("north", "south", "east", "west")


@dataclass(frozen=True)
class SyntheticDataConfig:
    """Configuration for synthetic healthcare-network data."""

    start_date: str = "2022-01-01"
    end_date: str = "2025-12-31"
    n_clinics: int = 12
    random_seed: int = 42


def _validate_config(config: SyntheticDataConfig) -> None:
    """Validate synthetic data generation parameters."""
    if config.n_clinics < 2:
        raise ValueError("n_clinics must be at least 2.")
    if pd.Timestamp(config.start_date) >= pd.Timestamp(config.end_date):
        raise ValueError("start_date must be earlier than end_date.")


def make_clinic_metadata(config: SyntheticDataConfig) -> pd.DataFrame:
    """Create clinic-level metadata.

    Parameters
    ----------
    config:
        Synthetic data configuration.

    Returns
    -------
    pandas.DataFrame
        One row per clinic with capacity and specialty information.
    """
    _validate_config(config)
    rng = np.random.default_rng(config.random_seed)

    rows: list[dict[str, object]] = []
    for idx in range(config.n_clinics):
        clinic_size = rng.choice(["small", "medium", "large"], p=[0.35, 0.45, 0.20])
        base_capacity = {"small": 80, "medium": 140, "large": 220}[clinic_size]
        rows.append(
            {
                "clinic_id": f"CLINIC_{idx + 1:03d}",
                "region": REGIONS[idx % len(REGIONS)],
                "clinic_size": clinic_size,
                "specialty": SPECIALTIES[idx % len(SPECIALTIES)],
                "daily_capacity": int(base_capacity + rng.normal(0, 8)),
                "base_clinicians": int({"small": 4, "medium": 7, "large": 11}[clinic_size]),
                "base_nurses": int({"small": 5, "medium": 9, "large": 14}[clinic_size]),
                "base_frontdesk": int({"small": 2, "medium": 4, "large": 6}[clinic_size]),
            }
        )

    metadata = pd.DataFrame(rows)
    return metadata


def _calendar_frame(config: SyntheticDataConfig) -> pd.DataFrame:
    """Create a daily calendar frame with seasonality drivers."""
    dates = pd.date_range(config.start_date, config.end_date, freq="D")
    calendar = pd.DataFrame({"date": dates})
    calendar["day_of_week"] = calendar["date"].dt.dayofweek
    calendar["month"] = calendar["date"].dt.month
    calendar["week_of_year"] = calendar["date"].dt.isocalendar().week.astype(int)
    calendar["is_weekend"] = calendar["day_of_week"].isin([5, 6]).astype(int)
    calendar["is_monday"] = (calendar["day_of_week"] == 0).astype(int)
    calendar["is_winter"] = calendar["month"].isin([12, 1, 2]).astype(int)
    calendar["is_summer"] = calendar["month"].isin([6, 7, 8]).astype(int)
    calendar["yearly_season"] = np.sin(2 * np.pi * calendar["date"].dt.dayofyear / 365.25)
    return calendar


def _marketing_frame(config: SyntheticDataConfig, metadata: pd.DataFrame) -> pd.DataFrame:
    """Create clinic-level marketing features."""
    rng = np.random.default_rng(config.random_seed + 7)
    calendar = _calendar_frame(config)
    frames: list[pd.DataFrame] = []

    for clinic in metadata["clinic_id"].tolist():
        local = calendar[["date", "month"]].copy()
        campaign_probability = np.where(local["month"].isin([1, 9, 10]), 0.14, 0.06)
        local["campaign_active"] = rng.binomial(1, campaign_probability)
        base_spend = rng.uniform(200, 900)
        local["marketing_spend"] = (
            base_spend
            + local["campaign_active"] * rng.uniform(900, 2500)
            + rng.normal(0, 120, size=len(local))
        ).clip(lower=0)
        local["clinic_id"] = clinic
        frames.append(local.drop(columns="month"))

    return pd.concat(frames, ignore_index=True)


def generate_synthetic_healthcare_data(
    config: SyntheticDataConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate synthetic clinic usage, clinic metadata and marketing data.

    Parameters
    ----------
    config:
        Optional synthetic data configuration. Defaults to a four-year,
        12-clinic network.

    Returns
    -------
    tuple[pandas.DataFrame, pandas.DataFrame, pandas.DataFrame]
        Usage data, clinic metadata and marketing data.
    """
    cfg = config or SyntheticDataConfig()
    _validate_config(cfg)

    rng = np.random.default_rng(cfg.random_seed)
    metadata = make_clinic_metadata(cfg)
    calendar = _calendar_frame(cfg)
    marketing = _marketing_frame(cfg, metadata)

    rows: list[pd.DataFrame] = []
    for _, clinic in metadata.iterrows():
        clinic_frame = calendar.copy()
        clinic_frame["clinic_id"] = clinic["clinic_id"]
        clinic_frame = clinic_frame.merge(marketing, on=["clinic_id", "date"], how="left")

        capacity = float(clinic["daily_capacity"])
        size_multiplier = {"small": 0.55, "medium": 0.78, "large": 1.02}[str(clinic["clinic_size"])]
        specialty_multiplier = {
            "primary_care": 1.00,
            "urgent_care": 1.15,
            "cardiology": 0.72,
            "orthopedics": 0.76,
            "pediatrics": 0.88,
        }[str(clinic["specialty"])]

        weekday_effect = clinic_frame["day_of_week"].map(
            {0: 1.18, 1: 1.06, 2: 1.00, 3: 1.02, 4: 0.96, 5: 0.48, 6: 0.26}
        )
        winter_effect = 1.0 + 0.16 * clinic_frame["is_winter"]
        summer_effect = 1.0 - 0.08 * clinic_frame["is_summer"]
        campaign_effect = 1.0 + 0.00008 * clinic_frame["marketing_spend"]
        trend = 1.0 + np.linspace(0.0, rng.uniform(0.04, 0.18), len(clinic_frame))
        local_noise = rng.normal(0, 6.0, size=len(clinic_frame))

        expected_visits = (
            capacity
            * size_multiplier
            * specialty_multiplier
            * weekday_effect
            * winter_effect
            * summer_effect
            * campaign_effect
            * trend
            + 10 * clinic_frame["yearly_season"]
            + local_noise
        )
        visits = rng.poisson(np.clip(expected_visits, 1, None)).astype(int)
        no_show_rate = np.clip(
            0.08
            + 0.02 * clinic_frame["is_monday"]
            + rng.normal(0, 0.012, size=len(clinic_frame)),
            0.02,
            0.22,
        )

        clinic_frame["scheduled_appointments"] = np.ceil(visits / (1 - no_show_rate)).astype(int)
        clinic_frame["no_show_rate"] = no_show_rate
        clinic_frame["visits"] = visits
        clinic_frame["capacity_utilization"] = visits / capacity
        rows.append(clinic_frame)

    usage = pd.concat(rows, ignore_index=True)
    usage = usage.merge(metadata, on="clinic_id", how="left")
    usage = usage.sort_values(["clinic_id", "date"]).reset_index(drop=True)
    return usage, metadata, marketing
