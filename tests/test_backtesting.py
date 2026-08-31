from __future__ import annotations

import pandas as pd

from clinic_forecast.backtesting import (
    make_recursive_global_ml_adapter,
    recursive_global_ml_forecast,
    strip_future_outcomes,
)
from clinic_forecast.data import SyntheticDataConfig, generate_network_data


def _split_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    usage = generate_network_data(
        SyntheticDataConfig(
            start_date="2024-01-01",
            end_date="2024-10-31",
            n_clinics=3,
            random_seed=123,
        )
    ).usage
    cutoff = pd.Timestamp("2024-10-03")
    return usage[usage["date"] <= cutoff], usage[usage["date"] > cutoff]


def test_strip_future_outcomes_removes_unavailable_columns() -> None:
    _, test = _split_panel()
    future = strip_future_outcomes(test)
    forbidden = {
        "visits",
        "scheduled_appointments",
        "no_show_count",
        "same_day_cancellations",
        "no_show_rate",
        "capacity_utilization",
    }
    assert forbidden.isdisjoint(future.columns)
    assert {"clinic_id", "date", "marketing_spend"}.issubset(future.columns)


def test_recursive_backtest_is_invariant_to_poisoned_future_targets() -> None:
    train, test = _split_panel()
    clean = recursive_global_ml_forecast(train, test)

    poisoned = test.copy()
    poisoned["visits"] = 1_000_000.0
    poisoned["scheduled_appointments"] = 2_000_000.0
    poisoned["no_show_count"] = 999_999.0
    poisoned["capacity_utilization"] = 999.0
    poisoned_forecast = recursive_global_ml_forecast(train, poisoned)

    pd.testing.assert_frame_equal(clean, poisoned_forecast)


def test_recursive_adapter_matches_direct_recursive_forecast() -> None:
    train, test = _split_panel()
    direct = recursive_global_ml_forecast(train, test)
    adapted = make_recursive_global_ml_adapter()(train, test)
    pd.testing.assert_frame_equal(direct, adapted)
