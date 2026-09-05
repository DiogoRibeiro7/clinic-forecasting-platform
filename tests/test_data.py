from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.data import (
    MARKETING_CHANNELS,
    SyntheticDataConfig,
    SyntheticHealthcareData,
    generate_network_data,
    generate_synthetic_healthcare_data,
)

CONFIG = SyntheticDataConfig(start_date="2024-01-01", end_date="2024-06-30", n_clinics=5)


@pytest.fixture(scope="module")
def network() -> SyntheticHealthcareData:
    return generate_network_data(CONFIG)


def test_generate_synthetic_healthcare_data_has_expected_columns() -> None:
    usage, metadata, marketing = generate_synthetic_healthcare_data(
        SyntheticDataConfig(start_date="2024-01-01", end_date="2024-01-31", n_clinics=3)
    )

    assert not usage.empty
    assert not metadata.empty
    assert not marketing.empty
    assert {"date", "clinic_id", "visits", "marketing_spend", "campaign_active"}.issubset(
        usage.columns
    )
    assert pd.to_datetime(usage["date"]).min() == pd.Timestamp("2024-01-01")
    assert pd.to_datetime(usage["date"]).max() == pd.Timestamp("2024-01-31")


def test_generated_data_has_one_row_per_clinic_day() -> None:
    usage, _, _ = generate_synthetic_healthcare_data(
        SyntheticDataConfig(start_date="2024-01-01", end_date="2024-01-10", n_clinics=4)
    )

    assert len(usage) == 4 * 10
    assert usage[["clinic_id", "date"]].duplicated().sum() == 0


def test_same_seed_produces_identical_data() -> None:
    first = generate_network_data(CONFIG)
    second = generate_network_data(CONFIG)

    pd.testing.assert_frame_equal(first.usage, second.usage)
    pd.testing.assert_frame_equal(first.metadata, second.metadata)
    pd.testing.assert_frame_equal(first.marketing, second.marketing)
    pd.testing.assert_frame_equal(first.staffing, second.staffing)


def test_default_calendar_preserves_explicit_legacy_semantics() -> None:
    default = generate_network_data(
        SyntheticDataConfig(start_date="2024-03-28", end_date="2024-04-03", n_clinics=3)
    )
    explicit = generate_network_data(
        SyntheticDataConfig(
            start_date="2024-03-28",
            end_date="2024-04-03",
            n_clinics=3,
            holiday_calendar="legacy_fixed",
        )
    )
    pd.testing.assert_frame_equal(default.usage, explicit.usage)
    pd.testing.assert_frame_equal(default.staffing, explicit.staffing)


def test_england_wales_calendar_marks_movable_bank_holiday() -> None:
    network = generate_network_data(
        SyntheticDataConfig(
            start_date="2024-03-28",
            end_date="2024-04-03",
            n_clinics=3,
            holiday_calendar="england_wales",
        )
    )
    easter_monday = network.usage[network.usage["date"] == pd.Timestamp("2024-04-01")]
    assert not easter_monday.empty
    assert (easter_monday["is_holiday"] == 1).all()
    non_urgent = easter_monday[easter_monday["weekend_open"] == 0]
    assert not non_urgent.empty
    assert (non_urgent["is_open"] == 0).all()
    assert (non_urgent["visits"] == 0).all()


def test_different_seed_produces_different_visits(network: SyntheticHealthcareData) -> None:
    other = generate_network_data(
        SyntheticDataConfig(
            start_date=CONFIG.start_date,
            end_date=CONFIG.end_date,
            n_clinics=CONFIG.n_clinics,
            random_seed=CONFIG.random_seed + 1,
        )
    )
    assert not network.usage["visits"].equals(other.usage["visits"])


def test_visits_never_exceed_capacity_or_schedule(network: SyntheticHealthcareData) -> None:
    usage = network.usage
    assert (usage["visits"] <= usage["daily_capacity"]).all()
    assert (usage["visits"] <= usage["scheduled_appointments"]).all()
    assert (usage["visits"] >= 0).all()


def test_schedule_decomposes_into_visits_noshows_and_cancellations(
    network: SyntheticHealthcareData,
) -> None:
    usage = network.usage
    uncapped = usage["visits"] < usage["daily_capacity"]
    reconstructed = (
        usage.loc[uncapped, "visits"]
        + usage.loc[uncapped, "no_show_count"]
        + usage.loc[uncapped, "same_day_cancellations"]
    )
    assert reconstructed.equals(usage.loc[uncapped, "scheduled_appointments"])


def test_weekend_closed_clinics_have_no_sunday_activity(
    network: SyntheticHealthcareData,
) -> None:
    usage = network.usage.copy()
    usage["day_of_week"] = pd.to_datetime(usage["date"]).dt.dayofweek
    closed = usage[(usage["weekend_open"] == 0) & (usage["day_of_week"] == 6)]
    assert not closed.empty
    assert (closed["scheduled_appointments"] == 0).all()
    assert (closed["visits"] == 0).all()


def test_holidays_close_non_urgent_clinics(network: SyntheticHealthcareData) -> None:
    usage = network.usage
    holiday_rows = usage[(usage["is_holiday"] == 1) & (usage["weekend_open"] == 0)]
    assert not holiday_rows.empty
    assert (holiday_rows["visits"] == 0).all()


def test_weekday_demand_exceeds_saturday_demand(network: SyntheticHealthcareData) -> None:
    usage = network.usage.copy()
    usage["day_of_week"] = pd.to_datetime(usage["date"]).dt.dayofweek
    open_rows = usage[usage["is_open"] == 1]
    weekday_mean = open_rows.loc[open_rows["day_of_week"] < 5, "visits"].mean()
    saturday_mean = open_rows.loc[open_rows["day_of_week"] == 5, "visits"].mean()
    assert weekday_mean > saturday_mean


def test_marketing_channels_sum_to_total_spend(network: SyntheticHealthcareData) -> None:
    marketing = network.marketing
    channel_cols = [f"spend_{channel}" for channel in MARKETING_CHANNELS]
    assert set(channel_cols).issubset(marketing.columns)
    totals = marketing[channel_cols].sum(axis=1)
    pd.testing.assert_series_equal(
        totals, marketing["marketing_spend"], check_names=False, rtol=1e-9
    )


def test_staffing_levels_follow_opening_days(network: SyntheticHealthcareData) -> None:
    staffing = network.staffing.merge(
        network.usage[["clinic_id", "date", "is_open"]], on=["clinic_id", "date"]
    )
    closed = staffing[staffing["is_open"] == 0]
    open_days = staffing[staffing["is_open"] == 1]
    assert (closed[["clinicians", "nurses", "frontdesk"]] == 0).all().all()
    assert (open_days[["clinicians", "nurses", "frontdesk"]] >= 1).all().all()


def test_zero_seasonality_flattens_weekday_profile() -> None:
    flat = generate_network_data(
        SyntheticDataConfig(
            start_date="2024-01-01",
            end_date="2024-06-30",
            n_clinics=4,
            seasonality_strength=0.0,
        )
    )
    usage = flat.usage.copy()
    usage["day_of_week"] = pd.to_datetime(usage["date"]).dt.dayofweek
    open_weekdays = usage[(usage["is_open"] == 1) & (usage["day_of_week"] < 5)]
    weekday_means = open_weekdays.groupby("day_of_week")["visits"].mean()
    assert weekday_means.max() / weekday_means.min() < 1.1


def test_invalid_strengths_are_rejected() -> None:
    with pytest.raises(ValueError, match="noise_level"):
        generate_network_data(
            SyntheticDataConfig(start_date="2024-01-01", end_date="2024-02-01", noise_level=-1.0)
        )
