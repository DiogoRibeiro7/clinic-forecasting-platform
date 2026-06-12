from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from clinic_forecast.intervals import ConformalIntervals


def make_calibration(
    n: int = 200, scale: float = 5.0, clinic: str = "A", seed: int = 0
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    forecast = rng.uniform(50, 150, n)
    actual = forecast + rng.normal(0, scale, n)
    return pd.DataFrame({"clinic_id": clinic, "visits": actual, "forecast": forecast})


def test_interval_bounds_are_ordered_and_non_negative() -> None:
    ci = ConformalIntervals().fit(make_calibration())
    out = ci.apply(pd.DataFrame({"forecast": [0.5, 10.0, 100.0]}))

    assert (out["y_lower"] <= out["y_pred"]).all()
    assert (out["y_pred"] <= out["y_upper"]).all()
    assert (out["y_lower"] >= 0).all()
    assert out.loc[0, "y_lower"] == 0.0  # floored


def test_empirical_coverage_close_to_target() -> None:
    ci = ConformalIntervals(coverage=0.9).fit(make_calibration(n=1000, seed=1))
    fresh = make_calibration(n=2000, seed=2)
    out = ci.apply(fresh)
    covered = ((fresh["visits"] >= out["y_lower"]) & (fresh["visits"] <= out["y_upper"])).mean()
    assert 0.87 <= covered <= 0.93


def test_higher_coverage_widens_intervals() -> None:
    calibration = make_calibration(n=500)
    narrow = ConformalIntervals(coverage=0.8).fit(calibration)
    wide = ConformalIntervals(coverage=0.95).fit(calibration)
    assert wide.half_width_for() > narrow.half_width_for()


def test_grouped_calibration_gives_group_specific_widths() -> None:
    calibration = pd.concat(
        [
            make_calibration(n=200, scale=2.0, clinic="quiet", seed=3),
            make_calibration(n=200, scale=20.0, clinic="noisy", seed=4),
        ],
        ignore_index=True,
    )
    ci = ConformalIntervals(group_col="clinic_id").fit(calibration)
    assert ci.half_width_for("noisy") > ci.half_width_for("quiet")


def test_small_group_falls_back_to_global() -> None:
    calibration = pd.concat(
        [
            make_calibration(n=200, scale=5.0, clinic="big", seed=5),
            make_calibration(n=5, scale=50.0, clinic="tiny", seed=6),
        ],
        ignore_index=True,
    )
    ci = ConformalIntervals(group_col="clinic_id", min_calibration_size=30).fit(calibration)
    assert "tiny" not in ci.group_half_widths_
    assert ci.half_width_for("tiny") == ci.half_width_for(None)


def test_unseen_group_falls_back_to_global() -> None:
    ci = ConformalIntervals(group_col="clinic_id").fit(make_calibration())
    out = ci.apply(pd.DataFrame({"clinic_id": ["never_seen"], "forecast": [80.0]}))
    expected_width = 2 * ci.half_width_for(None)
    assert out.loc[0, "y_upper"] - out.loc[0, "y_lower"] == pytest.approx(expected_width)


def test_apply_before_fit_raises() -> None:
    with pytest.raises(RuntimeError, match="fitted"):
        ConformalIntervals().apply(pd.DataFrame({"forecast": [1.0]}))


def test_invalid_parameters_rejected() -> None:
    with pytest.raises(ValueError, match="coverage"):
        ConformalIntervals(coverage=1.0)
    with pytest.raises(ValueError, match="calibration rows"):
        ConformalIntervals().fit(make_calibration(n=10))
    with pytest.raises(ValueError, match="missing columns"):
        ConformalIntervals().fit(pd.DataFrame({"forecast": [1.0] * 50}))
