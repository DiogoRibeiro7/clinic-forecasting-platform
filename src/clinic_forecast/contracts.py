"""Data contracts for the clinic forecasting platform.

Each public function validates one dataframe (or configuration mapping) against
an explicit contract: required columns, types, date ordering, value ranges,
key uniqueness and missing values in critical fields. Violations raise
:class:`DataContractError` with a message that names the contract and the
offending columns or rows, so failures surface early and are easy to act on.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import NoReturn

import pandas as pd

CLINIC_SIZES: frozenset[str] = frozenset({"small", "medium", "large"})


class DataContractError(ValueError):
    """Raised when data violates one of the platform's data contracts."""


def _fail(contract: str, message: str) -> NoReturn:
    raise DataContractError(f"[{contract}] {message}")


def _require_dataframe(frame: pd.DataFrame, contract: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        _fail(contract, f"Expected a pandas DataFrame, got {type(frame).__name__}.")
    if frame.empty:
        _fail(contract, "DataFrame is empty.")


def _require_columns(frame: pd.DataFrame, required: Iterable[str], contract: str) -> None:
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        _fail(contract, f"Missing required columns: {missing}.")


def _require_no_missing(frame: pd.DataFrame, columns: Iterable[str], contract: str) -> None:
    for column in columns:
        n_missing = int(frame[column].isna().sum())
        if n_missing:
            _fail(contract, f"Column '{column}' has {n_missing} missing values.")


def _require_non_negative(frame: pd.DataFrame, columns: Iterable[str], contract: str) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any():
            _fail(contract, f"Column '{column}' contains non-numeric values.")
        if (values < 0).any():
            n_bad = int((values < 0).sum())
            _fail(contract, f"Column '{column}' has {n_bad} negative values; expected >= 0.")


def _require_unique_key(frame: pd.DataFrame, key: list[str], contract: str) -> None:
    n_duplicates = int(frame.duplicated(subset=key).sum())
    if n_duplicates:
        _fail(contract, f"Key {key} is not unique: {n_duplicates} duplicate rows.")


def _parse_dates(frame: pd.DataFrame, date_col: str, contract: str) -> pd.Series:
    try:
        return pd.to_datetime(frame[date_col])
    except (ValueError, TypeError):
        _fail(contract, f"Column '{date_col}' contains values that cannot be parsed as dates.")
    raise AssertionError("unreachable")


def _require_sorted_dates_within_group(
    frame: pd.DataFrame,
    group_col: str,
    date_col: str,
    contract: str,
) -> None:
    dates = _parse_dates(frame, date_col, contract)
    out_of_order = dates.groupby(frame[group_col], observed=True).diff() < pd.Timedelta(0)
    if out_of_order.any():
        bad_groups = sorted(frame.loc[out_of_order, group_col].unique().tolist())
        _fail(
            contract,
            f"Dates are not in ascending order within '{group_col}' for: {bad_groups[:5]}.",
        )


def validate_clinic_usage(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate daily clinic usage data.

    Parameters
    ----------
    frame:
        One row per clinic per day with realised and scheduled demand.

    Returns
    -------
    pandas.DataFrame
        The validated input frame, unchanged, to allow call chaining.

    Raises
    ------
    DataContractError
        If the frame violates the clinic-usage contract.
    """
    contract = "clinic_usage"
    _require_dataframe(frame, contract)
    _require_columns(
        frame,
        [
            "clinic_id",
            "date",
            "visits",
            "scheduled_appointments",
            "no_show_rate",
            "marketing_spend",
            "campaign_active",
        ],
        contract,
    )
    _require_no_missing(frame, ["clinic_id", "date", "visits"], contract)
    _require_non_negative(
        frame, ["visits", "scheduled_appointments", "marketing_spend"], contract
    )
    _require_unique_key(frame, ["clinic_id", "date"], contract)
    _require_sorted_dates_within_group(frame, "clinic_id", "date", contract)

    rates = pd.to_numeric(frame["no_show_rate"], errors="coerce")
    if rates.isna().any() or (rates < 0).any() or (rates > 1).any():
        _fail(contract, "Column 'no_show_rate' must contain values between 0 and 1.")

    if (frame["scheduled_appointments"] < frame["visits"]).any():
        n_bad = int((frame["scheduled_appointments"] < frame["visits"]).sum())
        _fail(
            contract,
            f"'scheduled_appointments' is below 'visits' on {n_bad} rows; "
            "completed visits cannot exceed what was scheduled.",
        )
    return frame


def validate_clinic_metadata(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate clinic metadata.

    Raises
    ------
    DataContractError
        If the frame violates the clinic-metadata contract.
    """
    contract = "clinic_metadata"
    _require_dataframe(frame, contract)
    _require_columns(
        frame,
        [
            "clinic_id",
            "region",
            "clinic_size",
            "specialty",
            "daily_capacity",
            "base_clinicians",
            "base_nurses",
            "base_frontdesk",
        ],
        contract,
    )
    _require_no_missing(frame, list(frame.columns), contract)
    _require_unique_key(frame, ["clinic_id"], contract)
    _require_non_negative(
        frame,
        ["daily_capacity", "base_clinicians", "base_nurses", "base_frontdesk"],
        contract,
    )

    if (frame["daily_capacity"] <= 0).any():
        _fail(contract, "Column 'daily_capacity' must be strictly positive.")

    unknown_sizes = sorted(set(frame["clinic_size"].unique()).difference(CLINIC_SIZES))
    if unknown_sizes:
        _fail(
            contract,
            f"Column 'clinic_size' has unknown values {unknown_sizes}; "
            f"expected one of {sorted(CLINIC_SIZES)}.",
        )
    return frame


def validate_marketing(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate daily marketing activity data.

    Raises
    ------
    DataContractError
        If the frame violates the marketing contract.
    """
    contract = "marketing"
    _require_dataframe(frame, contract)
    _require_columns(frame, ["clinic_id", "date", "marketing_spend", "campaign_active"], contract)
    _require_no_missing(frame, ["clinic_id", "date", "marketing_spend"], contract)
    _require_non_negative(frame, ["marketing_spend"], contract)
    _require_unique_key(frame, ["clinic_id", "date"], contract)
    _require_sorted_dates_within_group(frame, "clinic_id", "date", contract)

    flags = set(pd.unique(frame["campaign_active"]))
    if not flags.issubset({0, 1}):
        _fail(contract, f"Column 'campaign_active' must be binary; found values {sorted(flags)}.")

    channel_columns = [col for col in frame.columns if col.startswith("spend_")]
    if channel_columns:
        _require_non_negative(frame, channel_columns, contract)
    return frame


def validate_staffing_daily(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate daily staffing levels by role.

    Raises
    ------
    DataContractError
        If the frame violates the staffing-daily contract.
    """
    contract = "staffing_daily"
    _require_dataframe(frame, contract)
    _require_columns(frame, ["clinic_id", "date", "clinicians", "nurses", "frontdesk"], contract)
    _require_no_missing(frame, ["clinic_id", "date"], contract)
    _require_non_negative(frame, ["clinicians", "nurses", "frontdesk"], contract)
    _require_unique_key(frame, ["clinic_id", "date"], contract)
    _require_sorted_dates_within_group(frame, "clinic_id", "date", contract)
    return frame


def validate_staffing_rules(rules: Mapping[str, object]) -> Mapping[str, object]:
    """Validate a staffing-rules mapping, e.g. the `staffing` section of a YAML config.

    Raises
    ------
    DataContractError
        If required keys are missing or values are out of range.
    """
    contract = "staffing_rules"
    required_positive = [
        "visits_per_clinician_day",
        "visits_per_nurse_day",
        "visits_per_frontdesk_day",
        "minimum_clinicians",
        "minimum_nurses",
        "minimum_frontdesk",
    ]
    missing = sorted(set(required_positive + ["buffer_ratio"]).difference(rules))
    if missing:
        _fail(contract, f"Missing required keys: {missing}.")

    for key in required_positive:
        value = rules[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            _fail(contract, f"Key '{key}' must be a positive integer, got {value!r}.")

    buffer_ratio = rules["buffer_ratio"]
    if not isinstance(buffer_ratio, int | float) or isinstance(buffer_ratio, bool):
        _fail(contract, f"Key 'buffer_ratio' must be numeric, got {buffer_ratio!r}.")
    if float(buffer_ratio) < 0:
        _fail(contract, f"Key 'buffer_ratio' cannot be negative, got {buffer_ratio!r}.")
    return rules
