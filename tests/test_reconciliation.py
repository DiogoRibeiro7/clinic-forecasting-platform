from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from clinic_forecast.reconciliation import (
    assert_coherent,
    build_hierarchy_frame,
    historical_proportions,
    reconcile_bottom_up,
    reconcile_middle_out,
    reconcile_top_down,
)


@pytest.fixture()
def metadata() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "clinic_id": ["C1", "C2", "C3", "C4"],
            "region": ["north", "north", "south", "south"],
        }
    )


@pytest.fixture()
def usage(metadata: pd.DataFrame) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=30, freq="D")
    levels = {"C1": 100.0, "C2": 50.0, "C3": 80.0, "C4": 20.0}
    frames = [
        pd.DataFrame({"clinic_id": cid, "date": dates, "visits": level})
        for cid, level in levels.items()
    ]
    return pd.concat(frames, ignore_index=True)


@pytest.fixture()
def clinic_forecasts(usage: pd.DataFrame) -> pd.DataFrame:
    future = usage[usage["date"] > "2025-01-23"].copy()
    return future.rename(columns={"visits": "forecast"})


def test_build_hierarchy_frame_levels(usage, metadata) -> None:
    hierarchy = build_hierarchy_frame(usage, metadata)
    assert set(hierarchy["level"]) == {"clinic", "region", "network"}
    network = hierarchy[hierarchy["level"] == "network"]
    assert (network["visits"] == 250.0).all()
    north = hierarchy[(hierarchy["level"] == "region") & (hierarchy["node"] == "north")]
    assert (north["visits"] == 150.0).all()


def test_historical_proportions_sum_to_one(usage, metadata) -> None:
    network_shares = historical_proportions(usage, metadata, within="network")
    assert network_shares.sum() == pytest.approx(1.0)
    assert network_shares["C1"] == pytest.approx(100 / 250)

    region_shares = historical_proportions(usage, metadata, within="region")
    assert region_shares["C1"] + region_shares["C2"] == pytest.approx(1.0)
    assert region_shares["C3"] == pytest.approx(80 / 100)


def test_bottom_up_is_coherent(clinic_forecasts, metadata) -> None:
    hierarchy = reconcile_bottom_up(clinic_forecasts, metadata)
    assert_coherent(hierarchy, metadata)
    network = hierarchy[hierarchy["level"] == "network"]
    assert (network["forecast"] == 250.0).all()


def test_top_down_is_coherent_and_matches_total(usage, metadata) -> None:
    dates = pd.date_range("2025-02-01", periods=7, freq="D")
    network_forecast = pd.DataFrame({"date": dates, "forecast": 300.0})
    hierarchy = reconcile_top_down(network_forecast, usage, metadata)
    assert_coherent(hierarchy, metadata)

    clinic = hierarchy[hierarchy["level"] == "clinic"]
    c1 = clinic[clinic["node"] == "C1"]
    assert np.allclose(c1["forecast"], 300.0 * (100 / 250))


def test_middle_out_is_coherent(usage, metadata) -> None:
    dates = pd.date_range("2025-02-01", periods=7, freq="D")
    region_forecast = pd.concat(
        [
            pd.DataFrame({"region": "north", "date": dates, "forecast": 180.0}),
            pd.DataFrame({"region": "south", "date": dates, "forecast": 90.0}),
        ],
        ignore_index=True,
    )
    hierarchy = reconcile_middle_out(region_forecast, usage, metadata)
    assert_coherent(hierarchy, metadata)

    clinic = hierarchy[hierarchy["level"] == "clinic"]
    c3 = clinic[clinic["node"] == "C3"]
    assert np.allclose(c3["forecast"], 90.0 * (80 / 100))


def test_assert_coherent_catches_incoherence(clinic_forecasts, metadata) -> None:
    hierarchy = reconcile_bottom_up(clinic_forecasts, metadata)
    broken = hierarchy.copy()
    broken.loc[broken["level"] == "network", "forecast"] += 10
    with pytest.raises(AssertionError, match="network"):
        assert_coherent(broken, metadata)


def test_missing_columns_raise(metadata, usage) -> None:
    with pytest.raises(ValueError, match="Missing required columns"):
        reconcile_bottom_up(pd.DataFrame({"clinic_id": ["C1"]}), metadata)
    with pytest.raises(ValueError, match="network_forecast"):
        reconcile_top_down(pd.DataFrame({"date": []}), usage, metadata)
    with pytest.raises(ValueError, match="within"):
        historical_proportions(usage, metadata, within="cluster")
