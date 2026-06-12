from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from clinic_forecast.features import (
    add_lag_features,
    add_marketing_features,
    make_supervised_frame,
)


def make_two_clinic_panel() -> pd.DataFrame:
    """Clinic A has huge values, clinic B small ones: any cross-clinic
    contamination of windows is immediately visible."""
    dates = pd.date_range("2025-01-01", periods=40, freq="D")
    a = pd.DataFrame({"date": dates, "clinic_id": "A", "visits": 1000.0})
    b = pd.DataFrame({"date": dates, "clinic_id": "B", "visits": 10.0})
    return pd.concat([a, b], ignore_index=True)


def test_lags_do_not_cross_clinic_boundaries() -> None:
    frame = add_lag_features(make_two_clinic_panel(), group_col="clinic_id", target_col="visits")
    b_first = frame[(frame["clinic_id"] == "B")].sort_values("date").iloc[0]
    assert np.isnan(b_first["lag_1"])  # not clinic A's last value


def test_rolling_windows_do_not_cross_clinic_boundaries() -> None:
    frame = add_lag_features(make_two_clinic_panel(), group_col="clinic_id", target_col="visits")
    b_rows = frame[frame["clinic_id"] == "B"].sort_values("date")

    # First 7 rows of B cannot have a complete 7-day window; under the old
    # bug they were filled using clinic A's tail (values near 1000).
    assert b_rows["rolling_mean_7"].head(7).isna().all()
    complete = b_rows["rolling_mean_7"].dropna()
    assert (complete == 10.0).all()


def test_rolling_mean_excludes_current_day() -> None:
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    frame = pd.DataFrame({"date": dates, "clinic_id": "A", "visits": np.arange(10.0)})
    out = add_lag_features(frame, group_col="clinic_id", target_col="visits",
                           lags=(1,), rolling_windows=(3,))
    # Row index 3 (visits=3): window over shifted values [0,1,2] -> mean 1
    assert out.iloc[3]["rolling_mean_3"] == pytest.approx(1.0)


def test_expanding_mean_uses_only_past_values() -> None:
    dates = pd.date_range("2025-01-01", periods=5, freq="D")
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    frame = pd.DataFrame({"date": dates, "clinic_id": "A", "visits": values})
    out = add_lag_features(frame, group_col="clinic_id", target_col="visits")
    assert np.isnan(out.iloc[0]["expanding_mean"])
    assert out.iloc[1]["expanding_mean"] == pytest.approx(10.0)
    assert out.iloc[4]["expanding_mean"] == pytest.approx(25.0)  # mean of first four


def test_marketing_features_lag_within_clinic() -> None:
    frame = make_two_clinic_panel()
    frame["marketing_spend"] = np.where(frame["clinic_id"] == "A", 500.0, 5.0)
    out = add_marketing_features(frame)
    b_first = out[out["clinic_id"] == "B"].sort_values("date").iloc[0]
    assert np.isnan(b_first["marketing_spend_lag_1"])
    b_complete = out[out["clinic_id"] == "B"]["marketing_spend_rolling_7"].dropna()
    assert (b_complete == 5.0).all()


def test_supervised_frame_keeps_rows_when_dropna_false() -> None:
    frame = make_two_clinic_panel()
    strict = make_supervised_frame(frame)
    loose = make_supervised_frame(frame, dropna=False)
    assert len(loose) == len(frame)
    assert len(strict) < len(loose)  # warm-up rows dropped for training
