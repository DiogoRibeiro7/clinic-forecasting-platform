from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.holiday_calendar import (
    ENGLAND_WALES_SNAPSHOT_DATE,
    ENGLAND_WALES_SOURCE_URL,
    holiday_mask,
)


def test_england_wales_calendar_includes_movable_and_one_off_dates() -> None:
    dates = pd.to_datetime(
        [
            "2024-03-29",  # Good Friday
            "2024-04-01",  # Easter Monday
            "2022-06-03",  # Platinum Jubilee
            "2022-09-19",  # State funeral
            "2023-05-08",  # Coronation bank holiday
            "2024-04-02",  # ordinary Tuesday
        ]
    )

    assert holiday_mask(dates, "england_wales").tolist() == [True, True, True, True, True, False]


def test_england_wales_calendar_includes_substitute_days() -> None:
    dates = pd.to_datetime(
        [
            "2022-01-03",  # New Year substitute
            "2022-12-27",  # Christmas substitute
            "2026-12-28",  # Boxing Day substitute
            "2028-01-03",  # New Year substitute
        ]
    )

    assert holiday_mask(dates, "england_wales").all()


def test_legacy_calendar_preserves_original_recurring_semantics() -> None:
    dates = pd.to_datetime(["2024-05-01", "2024-05-06", "2024-12-24", "2024-12-31"])

    assert holiday_mask(dates, "legacy_fixed").tolist() == [True, False, True, True]


def test_england_wales_calendar_fails_closed_outside_locked_snapshot() -> None:
    with pytest.raises(ValueError, match="source-locked"):
        holiday_mask(pd.to_datetime(["2029-01-01"]), "england_wales")


def test_calendar_source_identity_is_explicit() -> None:
    assert ENGLAND_WALES_SOURCE_URL == "https://www.gov.uk/bank-holidays.json"
    assert ENGLAND_WALES_SNAPSHOT_DATE == "2026-09-04"
