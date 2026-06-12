from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.pipelines.batch_inference import (
    BatchForecastConfig,
    make_future_frame,
    run_batch_forecast,
)


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("processed")
    network = generate_network_data(
        SyntheticDataConfig(start_date="2024-01-01", end_date="2024-12-31", n_clinics=3)
    )
    network.usage.to_csv(directory / "clinic_daily_usage.csv", index=False)
    network.metadata.to_csv(directory / "clinic_metadata.csv", index=False)
    return directory


def small_config(data_dir: Path, output_dir: Path) -> BatchForecastConfig:
    return BatchForecastConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        horizon_days=7,
        calibration_folds=2,
        initial_train_days=180,
    )


def test_make_future_frame_calendar_and_marketing(data_dir: Path) -> None:
    usage = pd.read_csv(data_dir / "clinic_daily_usage.csv", parse_dates=["date"])
    metadata = pd.read_csv(data_dir / "clinic_metadata.csv")
    future = make_future_frame(usage, metadata, horizon_days=14)

    assert len(future) == 14 * len(metadata)
    assert future["date"].min() == usage["date"].max() + pd.Timedelta(days=1)
    assert {"is_open", "is_holiday", "marketing_spend"}.issubset(future.columns)
    assert future["marketing_spend"].notna().all()

    closed_sunday = future[
        (future["date"].dt.dayofweek == 6) & (future["weekend_open"] == 0)
    ]
    assert (closed_sunday["is_open"] == 0).all()


def test_batch_pipeline_smoke(data_dir: Path, tmp_path: Path) -> None:
    result = run_batch_forecast(small_config(data_dir, tmp_path / "outputs"))

    forecast = pd.read_csv(result.forecast_path, parse_dates=["date"])
    staffing = pd.read_csv(result.staffing_path, parse_dates=["date"])

    assert result.n_clinics == 3
    assert len(forecast) == 7 * 3
    assert {"y_pred", "y_lower", "y_upper", "is_open"}.issubset(forecast.columns)
    assert (forecast["y_lower"] <= forecast["y_pred"]).all()
    assert (forecast["y_pred"] <= forecast["y_upper"]).all()
    assert (forecast["y_pred"] >= 0).all()

    closed = forecast[forecast["is_open"] == 0]
    if not closed.empty:
        assert (closed[["y_pred", "y_lower", "y_upper"]] == 0).all().all()

    assert {"mean_plan_clinicians", "upper_plan_clinicians"}.issubset(staffing.columns)
    open_days = forecast["is_open"] == 1
    merged = staffing.merge(forecast[["clinic_id", "date", "is_open"]], on=["clinic_id", "date"])
    open_staffing = merged[merged["is_open"] == 1]
    assert (
        open_staffing["upper_plan_clinicians"] >= open_staffing["mean_plan_clinicians"]
    ).all()
    assert open_days.any()

    latest = result.forecast_path.parent / "latest.csv"
    assert latest.exists()
    pd.testing.assert_frame_equal(pd.read_csv(latest), pd.read_csv(result.forecast_path))


def test_batch_pipeline_missing_data_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="generate_data"):
        run_batch_forecast(small_config(tmp_path / "nowhere", tmp_path / "outputs"))
