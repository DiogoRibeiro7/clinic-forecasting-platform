from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.contracts import (
    DataContractError,
    validate_clinic_metadata,
    validate_clinic_usage,
    validate_marketing,
    validate_staffing_rules,
)
from clinic_forecast.data import SyntheticDataConfig, generate_synthetic_healthcare_data

SMALL_CONFIG = SyntheticDataConfig(start_date="2024-01-01", end_date="2024-03-31", n_clinics=3)


@pytest.fixture(scope="module")
def synthetic_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return generate_synthetic_healthcare_data(SMALL_CONFIG)


def test_valid_synthetic_usage_passes(synthetic_data) -> None:
    usage, _, _ = synthetic_data
    assert validate_clinic_usage(usage) is usage


def test_valid_synthetic_metadata_passes(synthetic_data) -> None:
    _, metadata, _ = synthetic_data
    assert validate_clinic_metadata(metadata) is metadata


def test_valid_synthetic_marketing_passes(synthetic_data) -> None:
    _, _, marketing = synthetic_data
    assert validate_marketing(marketing) is marketing


def test_usage_missing_column_fails(synthetic_data) -> None:
    usage, _, _ = synthetic_data
    with pytest.raises(DataContractError, match=r"\[clinic_usage\].*visits"):
        validate_clinic_usage(usage.drop(columns=["visits"]))


def test_usage_negative_visits_fail(synthetic_data) -> None:
    usage, _, _ = synthetic_data
    broken = usage.copy()
    broken.loc[broken.index[0], "visits"] = -5
    with pytest.raises(DataContractError, match="negative"):
        validate_clinic_usage(broken)


def test_usage_duplicate_clinic_day_fails(synthetic_data) -> None:
    usage, _, _ = synthetic_data
    broken = pd.concat([usage, usage.head(1)], ignore_index=True)
    broken = broken.sort_values(["clinic_id", "date"]).reset_index(drop=True)
    with pytest.raises(DataContractError, match="not unique"):
        validate_clinic_usage(broken)


def test_usage_unsorted_dates_fail(synthetic_data) -> None:
    usage, _, _ = synthetic_data
    broken = usage.iloc[::-1].reset_index(drop=True)
    with pytest.raises(DataContractError, match="ascending order"):
        validate_clinic_usage(broken)


def test_usage_no_show_rate_out_of_range_fails(synthetic_data) -> None:
    usage, _, _ = synthetic_data
    broken = usage.copy()
    broken.loc[broken.index[0], "no_show_rate"] = 1.4
    with pytest.raises(DataContractError, match="between 0 and 1"):
        validate_clinic_usage(broken)


def test_usage_scheduled_below_visits_fails(synthetic_data) -> None:
    usage, _, _ = synthetic_data
    broken = usage.copy()
    broken.loc[broken.index[0], "scheduled_appointments"] = 0
    broken.loc[broken.index[0], "visits"] = 10
    with pytest.raises(DataContractError, match="cannot exceed"):
        validate_clinic_usage(broken)


def test_metadata_duplicate_clinic_fails(synthetic_data) -> None:
    _, metadata, _ = synthetic_data
    broken = pd.concat([metadata, metadata.head(1)], ignore_index=True)
    with pytest.raises(DataContractError, match="not unique"):
        validate_clinic_metadata(broken)


def test_metadata_unknown_clinic_size_fails(synthetic_data) -> None:
    _, metadata, _ = synthetic_data
    broken = metadata.copy()
    broken.loc[broken.index[0], "clinic_size"] = "gigantic"
    with pytest.raises(DataContractError, match="gigantic"):
        validate_clinic_metadata(broken)


def test_marketing_non_binary_campaign_flag_fails(synthetic_data) -> None:
    _, _, marketing = synthetic_data
    broken = marketing.copy()
    broken.loc[broken.index[0], "campaign_active"] = 3
    with pytest.raises(DataContractError, match="binary"):
        validate_marketing(broken)


def test_empty_frame_fails() -> None:
    with pytest.raises(DataContractError, match="empty"):
        validate_clinic_usage(pd.DataFrame())


def test_valid_staffing_rules_pass() -> None:
    rules = {
        "visits_per_clinician_day": 18,
        "visits_per_nurse_day": 24,
        "visits_per_frontdesk_day": 35,
        "minimum_clinicians": 1,
        "minimum_nurses": 1,
        "minimum_frontdesk": 1,
        "buffer_ratio": 0.12,
    }
    assert validate_staffing_rules(rules) is rules


def test_staffing_rules_missing_key_fails() -> None:
    with pytest.raises(DataContractError, match="Missing required keys"):
        validate_staffing_rules({"buffer_ratio": 0.1})


def test_staffing_rules_non_positive_productivity_fails() -> None:
    rules = {
        "visits_per_clinician_day": 0,
        "visits_per_nurse_day": 24,
        "visits_per_frontdesk_day": 35,
        "minimum_clinicians": 1,
        "minimum_nurses": 1,
        "minimum_frontdesk": 1,
        "buffer_ratio": 0.12,
    }
    with pytest.raises(DataContractError, match="visits_per_clinician_day"):
        validate_staffing_rules(rules)


def test_staffing_rules_negative_buffer_fails() -> None:
    rules = {
        "visits_per_clinician_day": 18,
        "visits_per_nurse_day": 24,
        "visits_per_frontdesk_day": 35,
        "minimum_clinicians": 1,
        "minimum_nurses": 1,
        "minimum_frontdesk": 1,
        "buffer_ratio": -0.2,
    }
    with pytest.raises(DataContractError, match="buffer_ratio"):
        validate_staffing_rules(rules)
