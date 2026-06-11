from __future__ import annotations

import pandas as pd

from clinic_forecast.validation import rolling_origin_windows


def test_rolling_origin_windows_returns_expected_number() -> None:
    dates = pd.date_range("2023-01-01", periods=500, freq="D")
    data = pd.DataFrame({"date": dates, "visits": range(len(dates))})
    windows = list(rolling_origin_windows(data, horizon_days=28, n_windows=3, min_train_days=365))

    assert len(windows) == 3
    assert windows[0].test_start < windows[-1].test_start
