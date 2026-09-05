"""Synthetic healthcare-network data generation.

The generator creates aggregate clinic-level operational data. It is intentionally
free of patient-level fields and protected health information.

Simulation design
-----------------
Demand is generated in the order a real network experiences it:

1. Expected scheduled appointments are driven by clinic size, specialty,
   a clinic-specific weekday profile, winter/summer seasonality with a
   clinic-specific phase, public holidays, a piecewise trend with random
   changepoints, marketing pressure with adstock carryover and diminishing
   returns, and a persistent AR(1) demand-episode process (flu waves, local
   events).
2. Scheduled appointments are drawn from a negative binomial (overdispersed)
   distribution around that expectation.
3. No-shows and same-day cancellations remove a stochastic share of the
   schedule; the base no-show rate differs by clinic.
4. Completed visits are capped by the clinic's daily capacity.

Clinics that are not open on weekends (every specialty except urgent care)
have zero scheduled activity on Sundays and reduced Saturdays. Marketing spend
is split across search, social, email and local channels, with campaigns
concentrated in January and the autumn enrolment season.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import pandas as pd

from clinic_forecast.holiday_calendar import (
    LEGACY_FIXED_HOLIDAYS,
    HolidayCalendarName,
    holiday_mask,
)

SPECIALTIES: Final[tuple[str, ...]] = (
    "primary_care",
    "urgent_care",
    "cardiology",
    "orthopedics",
    "pediatrics",
)

REGIONS: Final[tuple[str, ...]] = ("north", "south", "east", "west")

MARKETING_CHANNELS: Final[tuple[str, ...]] = ("search", "social", "email", "local")

#: Backwards-compatible alias for the original fixed month/day holiday set.
PUBLIC_HOLIDAYS: Final[tuple[tuple[int, int], ...]] = tuple(sorted(LEGACY_FIXED_HOLIDAYS))

_CHANNEL_WEIGHTS: Final[dict[str, float]] = {
    "search": 0.40,
    "social": 0.25,
    "email": 0.15,
    "local": 0.20,
}


@dataclass(frozen=True)
class SyntheticDataConfig:
    """Configuration for synthetic healthcare-network data.

    Parameters
    ----------
    start_date, end_date:
        Inclusive simulation date range.
    n_clinics:
        Number of clinics in the network (minimum 2).
    random_seed:
        Seed for all stochastic components; identical seeds produce
        identical data.
    seasonality_strength:
        Scales weekday, winter/summer and yearly seasonal effects.
        0 removes seasonality, 1 is the default intensity.
    marketing_strength:
        Scales the demand response to marketing spend. 0 makes demand
        independent of marketing.
    noise_level:
        Scales observation noise and the variability of no-show and
        cancellation rates. 0 keeps only structural variation.
    holiday_calendar:
        Holiday semantics used for calendar features and clinic closures.
        ``legacy_fixed`` preserves frozen benchmark compatibility;
        ``england_wales`` uses the source-locked GOV.UK bank-holiday snapshot.
    """

    start_date: str = "2022-01-01"
    end_date: str = "2025-12-31"
    n_clinics: int = 12
    random_seed: int = 42
    seasonality_strength: float = 1.0
    marketing_strength: float = 1.0
    noise_level: float = 1.0
    holiday_calendar: HolidayCalendarName = "legacy_fixed"


@dataclass(frozen=True)
class SyntheticHealthcareData:
    """Container for the four generated network tables."""

    usage: pd.DataFrame
    metadata: pd.DataFrame
    marketing: pd.DataFrame
    staffing: pd.DataFrame


def _validate_config(config: SyntheticDataConfig) -> None:
    """Validate synthetic data generation parameters."""
    if config.n_clinics < 2:
        raise ValueError("n_clinics must be at least 2.")
    if pd.Timestamp(config.start_date) >= pd.Timestamp(config.end_date):
        raise ValueError("start_date must be earlier than end_date.")
    for name in ("seasonality_strength", "marketing_strength", "noise_level"):
        if getattr(config, name) < 0:
            raise ValueError(f"{name} cannot be negative.")


def _scaled(base: float, strength: float) -> float:
    """Scale a multiplicative effect of the form (1 + delta) by a strength factor."""
    return 1.0 + strength * (base - 1.0)


def _ar1_episode_shock(
    rng: np.random.Generator, n_days: int, noise_level: float, persistence: float = 0.88
) -> np.ndarray:
    """Multiplicative AR(1) demand-episode process.

    Models persistent, unpredictable demand waves (flu outbreaks, local events):
    deviations last for days to weeks rather than resetting every day, which is
    what makes real demand series hard to forecast from calendar features alone.
    """
    innovations = rng.normal(0, 0.045 * noise_level, size=n_days)
    log_shock = np.zeros(n_days)
    for t in range(1, n_days):
        log_shock[t] = persistence * log_shock[t - 1] + innovations[t]
    return np.exp(log_shock)


def _piecewise_trend(rng: np.random.Generator, n_days: int) -> np.ndarray:
    """Piecewise-linear trend with random changepoints.

    Real clinics do not grow along one straight line: competitors open,
    clinicians leave, referral patterns change. Each segment gets its own
    slope, including possible decline.
    """
    n_changepoints = int(rng.integers(1, 4))
    earliest, latest = int(n_days * 0.15), int(n_days * 0.85)
    changepoints = np.sort(rng.choice(np.arange(earliest, latest), n_changepoints, replace=False))
    boundaries = np.concatenate([[0], changepoints, [n_days]])

    daily_slope = np.empty(n_days)
    for left, right in zip(boundaries[:-1], boundaries[1:], strict=True):
        daily_slope[left:right] = rng.normal(0.0001, 0.0002)
    return np.clip(1.0 + np.cumsum(daily_slope), 0.6, 1.35)


def _adstock(spend: np.ndarray, carryover: float = 0.5) -> np.ndarray:
    """Geometric adstock: marketing effects persist beyond the spend day."""
    stocked = np.empty_like(spend, dtype=float)
    running = 0.0
    for t, value in enumerate(spend):
        running = value + carryover * running
        stocked[t] = running
    return stocked


def _negative_binomial(
    rng: np.random.Generator, mean: np.ndarray, dispersion: float = 18.0
) -> np.ndarray:
    """Draw overdispersed counts with the given mean.

    Uses the gamma-Poisson mixture: variance = mean + mean^2 / dispersion,
    which matches the variance-above-Poisson behaviour of real appointment
    counts. Zero-mean entries (closed days) stay exactly zero.
    """
    counts = np.zeros(len(mean), dtype=np.int64)
    positive = mean > 0
    if positive.any():
        rate = rng.gamma(shape=dispersion, scale=mean[positive] / dispersion)
        counts[positive] = rng.poisson(rate)
    return counts


def make_clinic_metadata(config: SyntheticDataConfig) -> pd.DataFrame:
    """Create clinic-level metadata.

    Parameters
    ----------
    config:
        Synthetic data configuration.

    Returns
    -------
    pandas.DataFrame
        One row per clinic with region, specialty, capacity, baseline staffing
        and weekend opening information.
    """
    _validate_config(config)
    rng = np.random.default_rng(config.random_seed)

    rows: list[dict[str, object]] = []
    for idx in range(config.n_clinics):
        clinic_size = rng.choice(["small", "medium", "large"], p=[0.35, 0.45, 0.20])
        base_capacity = {"small": 80, "medium": 140, "large": 220}[clinic_size]
        specialty = SPECIALTIES[idx % len(SPECIALTIES)]
        rows.append(
            {
                "clinic_id": f"CLINIC_{idx + 1:03d}",
                "region": REGIONS[idx % len(REGIONS)],
                "clinic_size": clinic_size,
                "specialty": specialty,
                "daily_capacity": int(base_capacity + rng.normal(0, 8)),
                "base_clinicians": int({"small": 4, "medium": 7, "large": 11}[clinic_size]),
                "base_nurses": int({"small": 5, "medium": 9, "large": 14}[clinic_size]),
                "base_frontdesk": int({"small": 2, "medium": 4, "large": 6}[clinic_size]),
                "weekend_open": int(specialty == "urgent_care"),
            }
        )

    return pd.DataFrame(rows)


def _calendar_frame(config: SyntheticDataConfig) -> pd.DataFrame:
    """Create a daily calendar frame with seasonality and holiday drivers."""
    dates = pd.date_range(config.start_date, config.end_date, freq="D")
    calendar = pd.DataFrame({"date": dates})
    calendar["day_of_week"] = calendar["date"].dt.dayofweek
    calendar["month"] = calendar["date"].dt.month
    calendar["week_of_year"] = calendar["date"].dt.isocalendar().week.astype(int)
    calendar["is_weekend"] = calendar["day_of_week"].isin([5, 6]).astype(int)
    calendar["is_monday"] = (calendar["day_of_week"] == 0).astype(int)
    calendar["is_winter"] = calendar["month"].isin([12, 1, 2]).astype(int)
    calendar["is_summer"] = calendar["month"].isin([6, 7, 8]).astype(int)
    calendar["is_holiday"] = holiday_mask(
        calendar["date"], config.holiday_calendar
    ).astype(int)
    calendar["yearly_season"] = np.sin(2 * np.pi * calendar["date"].dt.dayofyear / 365.25)
    return calendar


def _marketing_frame(config: SyntheticDataConfig, metadata: pd.DataFrame) -> pd.DataFrame:
    """Create clinic-level daily marketing activity split by channel."""
    rng = np.random.default_rng(config.random_seed + 7)
    calendar = _calendar_frame(config)
    frames: list[pd.DataFrame] = []

    for clinic in metadata["clinic_id"].tolist():
        local = calendar[["date", "month"]].copy()
        campaign_probability = np.where(local["month"].isin([1, 9, 10]), 0.14, 0.06)
        local["campaign_active"] = rng.binomial(1, campaign_probability)
        base_spend = rng.uniform(200, 900)
        campaign_spend = rng.uniform(900, 2500)

        for channel in MARKETING_CHANNELS:
            weight = _CHANNEL_WEIGHTS[channel]
            channel_noise = rng.normal(0, 30 * config.noise_level, size=len(local))
            local[f"spend_{channel}"] = (
                base_spend * weight
                + local["campaign_active"] * campaign_spend * weight
                + channel_noise
            ).clip(lower=0)

        spend_columns = [f"spend_{channel}" for channel in MARKETING_CHANNELS]
        local["marketing_spend"] = local[spend_columns].sum(axis=1)
        local["clinic_id"] = clinic
        frames.append(local.drop(columns="month"))

    return pd.concat(frames, ignore_index=True)


def _staffing_frame(
    config: SyntheticDataConfig,
    metadata: pd.DataFrame,
    open_by_clinic: dict[str, np.ndarray],
    calendar: pd.DataFrame,
) -> pd.DataFrame:
    """Create historical daily staffing levels by role for each clinic."""
    rng = np.random.default_rng(config.random_seed + 13)
    frames: list[pd.DataFrame] = []

    for _, clinic in metadata.iterrows():
        clinic_id = str(clinic["clinic_id"])
        is_open = open_by_clinic[clinic_id]
        weekend = calendar["is_weekend"].to_numpy()
        weekend_factor = np.where(weekend == 1, 0.6, 1.0)

        local = calendar[["date"]].copy()
        local["clinic_id"] = clinic_id
        for role, base_col in (
            ("clinicians", "base_clinicians"),
            ("nurses", "base_nurses"),
            ("frontdesk", "base_frontdesk"),
        ):
            base = float(clinic[base_col])
            jitter = rng.normal(0, 0.4 * config.noise_level, size=len(local))
            staffed = np.rint(base * weekend_factor + jitter).clip(min=1)
            local[role] = np.where(is_open, staffed, 0).astype(np.int64)
        frames.append(local)

    return pd.concat(frames, ignore_index=True)


def generate_network_data(
    config: SyntheticDataConfig | None = None,
) -> SyntheticHealthcareData:
    """Generate the four synthetic network tables.

    Parameters
    ----------
    config:
        Optional synthetic data configuration. Defaults to a four-year,
        12-clinic network.

    Returns
    -------
    SyntheticHealthcareData
        Daily usage, clinic metadata, daily marketing by channel and daily
        staffing levels by role.
    """
    cfg = config or SyntheticDataConfig()
    _validate_config(cfg)

    rng = np.random.default_rng(cfg.random_seed)
    metadata = make_clinic_metadata(cfg)
    calendar = _calendar_frame(cfg)
    marketing = _marketing_frame(cfg, metadata)

    open_by_clinic: dict[str, np.ndarray] = {}
    rows: list[pd.DataFrame] = []
    for _, clinic in metadata.iterrows():
        clinic_id = str(clinic["clinic_id"])
        clinic_frame = calendar.copy()
        clinic_frame["clinic_id"] = clinic_id
        clinic_frame = clinic_frame.merge(marketing, on=["clinic_id", "date"], how="left")

        capacity = float(clinic["daily_capacity"])
        weekend_open = bool(clinic["weekend_open"])
        size_multiplier = {"small": 0.46, "medium": 0.62, "large": 0.80}[str(clinic["clinic_size"])]
        specialty_multiplier = {
            "primary_care": 0.92,
            "urgent_care": 0.96,
            "cardiology": 0.72,
            "orthopedics": 0.76,
            "pediatrics": 0.82,
        }[str(clinic["specialty"])]

        weekday_profile = {0: 1.18, 1: 1.06, 2: 1.00, 3: 1.02, 4: 0.96}
        if weekend_open:
            weekday_profile.update({5: 0.85, 6: 0.70})
        else:
            weekday_profile.update({5: 0.48, 6: 0.0})
        weekday_jitter = rng.normal(0, 0.06, size=7)
        weekday_effect = clinic_frame["day_of_week"].map(
            {
                day: (
                    _scaled(value * (1 + weekday_jitter[day]), cfg.seasonality_strength)
                    if value > 0
                    else 0.0
                )
                for day, value in weekday_profile.items()
            }
        )

        is_open = (weekday_effect.to_numpy() > 0) & (
            (clinic_frame["is_holiday"].to_numpy() == 0) | weekend_open
        )
        open_by_clinic[clinic_id] = is_open

        n_days = len(clinic_frame)
        winter_effect = _scaled(1.16, cfg.seasonality_strength) ** clinic_frame["is_winter"]
        summer_effect = _scaled(0.92, cfg.seasonality_strength) ** clinic_frame["is_summer"]
        holiday_effect = np.where(clinic_frame["is_holiday"] == 1, 0.35, 1.0)

        adstocked_spend = _adstock(clinic_frame["marketing_spend"].to_numpy(dtype=float))
        campaign_effect = 1.0 + cfg.marketing_strength * 0.085 * np.log1p(adstocked_spend / 900.0)

        trend = _piecewise_trend(rng, n_days)
        episode_shock = _ar1_episode_shock(rng, n_days, cfg.noise_level)
        seasonal_phase = rng.uniform(-0.35, 0.35)
        day_of_year = clinic_frame["date"].dt.dayofyear.to_numpy()
        yearly_season = np.sin(2 * np.pi * day_of_year / 365.25 + seasonal_phase)
        local_noise = rng.normal(0, 6.0 * cfg.noise_level, size=n_days)

        expected_scheduled = (
            capacity
            * size_multiplier
            * specialty_multiplier
            * weekday_effect
            * winter_effect
            * summer_effect
            * holiday_effect
            * campaign_effect
            * trend
            * episode_shock
            + 10 * cfg.seasonality_strength * yearly_season
            + local_noise
        )
        expected_scheduled = np.where(is_open, np.clip(expected_scheduled, 1, None), 0.0)
        scheduled = _negative_binomial(rng, expected_scheduled)

        base_no_show = rng.uniform(0.05, 0.13)
        no_show_rate = np.clip(
            base_no_show
            + 0.02 * clinic_frame["is_monday"]
            + rng.normal(0, 0.012 * cfg.noise_level, size=n_days),
            0.02,
            0.25,
        )
        cancellation_rate = np.clip(
            0.035 + rng.normal(0, 0.008 * cfg.noise_level, size=len(clinic_frame)),
            0.005,
            0.12,
        )

        no_shows = rng.binomial(scheduled, no_show_rate).astype(np.int64)
        cancellations = rng.binomial(scheduled - no_shows, cancellation_rate).astype(np.int64)
        visits = np.minimum(scheduled - no_shows - cancellations, np.int64(capacity))

        clinic_frame["scheduled_appointments"] = scheduled
        clinic_frame["no_show_count"] = no_shows
        clinic_frame["same_day_cancellations"] = cancellations
        clinic_frame["no_show_rate"] = no_show_rate
        clinic_frame["visits"] = visits
        clinic_frame["is_open"] = is_open.astype(int)
        clinic_frame["capacity_utilization"] = visits / capacity
        rows.append(clinic_frame)

    usage = pd.concat(rows, ignore_index=True)
    usage = usage.merge(metadata, on="clinic_id", how="left")
    usage = usage.sort_values(["clinic_id", "date"]).reset_index(drop=True)

    staffing = _staffing_frame(cfg, metadata, open_by_clinic, calendar)
    staffing = staffing.sort_values(["clinic_id", "date"]).reset_index(drop=True)

    return SyntheticHealthcareData(
        usage=usage, metadata=metadata, marketing=marketing, staffing=staffing
    )


def generate_synthetic_healthcare_data(
    config: SyntheticDataConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate synthetic clinic usage, clinic metadata and marketing data.

    Compatibility wrapper around :func:`generate_network_data` that preserves
    the original three-frame return shape used by the earlier notebooks.
    """
    network = generate_network_data(config)
    return network.usage, network.metadata, network.marketing
