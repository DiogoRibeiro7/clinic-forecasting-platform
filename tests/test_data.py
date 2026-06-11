from __future__ import annotations

import pandas as pd

from clinic_forecast.data import SyntheticDataConfig, generate_synthetic_healthcare_data


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
