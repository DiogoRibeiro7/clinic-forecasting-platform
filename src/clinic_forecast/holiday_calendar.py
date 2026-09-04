"""Reproducible holiday calendars for synthetic and prospective deployment runs.

The historical ``legacy_fixed`` calendar preserves the original PoC semantics so
previously frozen synthetic benchmarks remain reproducible. New deployment-shaped
runs can explicitly select ``england_wales``, which is source-locked to the
GOV.UK Bank Holidays API snapshot recorded below.
"""

from __future__ import annotations

from typing import Final, Literal

import numpy as np
import pandas as pd

HolidayCalendarName = Literal["legacy_fixed", "england_wales"]

LEGACY_FIXED_HOLIDAYS: Final[frozenset[tuple[int, int]]] = frozenset(
    {
        (1, 1),
        (5, 1),
        (12, 24),
        (12, 25),
        (12, 26),
        (12, 31),
    }
)

ENGLAND_WALES_SOURCE_URL: Final[str] = "https://www.gov.uk/bank-holidays.json"
ENGLAND_WALES_SNAPSHOT_DATE: Final[str] = "2026-09-04"
ENGLAND_WALES_SUPPORTED_START: Final[pd.Timestamp] = pd.Timestamp("2022-01-01")
ENGLAND_WALES_SUPPORTED_END: Final[pd.Timestamp] = pd.Timestamp("2028-12-31")

# Exact dates published for the England and Wales division of the GOV.UK Bank
# Holidays API at the snapshot date above. This intentionally includes
# substitute days and one-off holidays rather than approximating them from
# recurring month/day rules.
ENGLAND_WALES_BANK_HOLIDAYS: Final[frozenset[pd.Timestamp]] = frozenset(
    pd.Timestamp(value)
    for value in (
        "2022-01-03",
        "2022-04-15",
        "2022-04-18",
        "2022-05-02",
        "2022-06-02",
        "2022-06-03",
        "2022-08-29",
        "2022-09-19",
        "2022-12-26",
        "2022-12-27",
        "2023-01-02",
        "2023-04-07",
        "2023-04-10",
        "2023-05-01",
        "2023-05-08",
        "2023-05-29",
        "2023-08-28",
        "2023-12-25",
        "2023-12-26",
        "2024-01-01",
        "2024-03-29",
        "2024-04-01",
        "2024-05-06",
        "2024-05-27",
        "2024-08-26",
        "2024-12-25",
        "2024-12-26",
        "2025-01-01",
        "2025-04-18",
        "2025-04-21",
        "2025-05-05",
        "2025-05-26",
        "2025-08-25",
        "2025-12-25",
        "2025-12-26",
        "2026-01-01",
        "2026-04-03",
        "2026-04-06",
        "2026-05-04",
        "2026-05-25",
        "2026-08-31",
        "2026-12-25",
        "2026-12-28",
        "2027-01-01",
        "2027-03-26",
        "2027-03-29",
        "2027-05-03",
        "2027-05-31",
        "2027-08-30",
        "2027-12-27",
        "2027-12-28",
        "2028-01-03",
        "2028-04-14",
        "2028-04-17",
        "2028-05-01",
        "2028-05-29",
        "2028-08-28",
        "2028-12-25",
        "2028-12-26",
    )
)


def _validate_england_wales_range(index: pd.DatetimeIndex) -> None:
    if index.empty:
        return
    start = index.min()
    end = index.max()
    if start < ENGLAND_WALES_SUPPORTED_START or end > ENGLAND_WALES_SUPPORTED_END:
        raise ValueError(
            "england_wales holiday calendar is source-locked to "
            f"{ENGLAND_WALES_SUPPORTED_START.date()} through "
            f"{ENGLAND_WALES_SUPPORTED_END.date()}; requested "
            f"{start.date()} through {end.date()}. Refresh the GOV.UK snapshot "
            "before extending this deployment calendar."
        )


def holiday_mask(
    dates: pd.Series | pd.DatetimeIndex | list[pd.Timestamp],
    calendar: HolidayCalendarName,
) -> np.ndarray:
    """Return one boolean holiday flag per date for the selected calendar."""
    index = pd.DatetimeIndex(pd.to_datetime(dates)).normalize()
    if calendar == "legacy_fixed":
        return np.fromiter(
            ((stamp.month, stamp.day) in LEGACY_FIXED_HOLIDAYS for stamp in index),
            dtype=bool,
            count=len(index),
        )
    if calendar == "england_wales":
        _validate_england_wales_range(index)
        return np.fromiter(
            (stamp in ENGLAND_WALES_BANK_HOLIDAYS for stamp in index),
            dtype=bool,
            count=len(index),
        )
    raise ValueError(f"Unsupported holiday calendar: {calendar!r}")


__all__ = [
    "ENGLAND_WALES_BANK_HOLIDAYS",
    "ENGLAND_WALES_SNAPSHOT_DATE",
    "ENGLAND_WALES_SOURCE_URL",
    "ENGLAND_WALES_SUPPORTED_END",
    "ENGLAND_WALES_SUPPORTED_START",
    "HolidayCalendarName",
    "LEGACY_FIXED_HOLIDAYS",
    "holiday_mask",
]
