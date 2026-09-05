from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from clinic_forecast.capacity import add_capacity_targets, validate_capacity_targets
from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.pipelines.role_specific_batch import (
    RoleSpecificBatchConfig,
    run_role_specific_batch,
)
from clinic_forecast.role_specific import (
    CLINICAL_TARGET,
    COMPLETED_TARGET,
    FRONTDESK_TARGET,
    prepare_target_history,
    recommend_role_specific_staffing,
    recursive_target_forecast,
)
from clinic_forecast.staffing import StaffingRules


def make_usage() -> pd.DataFrame:
    return generate_network_data(
        SyntheticDataConfig(start_date="2024-01-01", end_date="2024-09-30", n_clinics=4)
    ).usage


def test_capacity_targets_match_generator_funnel() -> None:
    frame = add_capacity_targets(make_usage())
    expected_attended = (
        frame["scheduled_appointments"]
        - frame["no_show_count"]
        - frame["same_day_cancellations"]
    ).astype(float).rename("attended_demand")
    expected_unmet = (
        frame["attended_demand"] - frame["visits"]
    ).astype(float).rename("unmet_demand")

    pd.testing.assert_series_equal(frame["attended_demand"], expected_attended)
    pd.testing.assert_series_equal(frame["unmet_demand"], expected_unmet)
    assert (
        frame["capacity_censored"]
        == (frame["unmet_demand"] > 0).astype(int)
    ).all()
    validate_capacity_targets(frame)


def test_target_history_removes_contemporaneous_outcomes() -> None:
    usage = make_usage()
    clinical = prepare_target_history(usage, CLINICAL_TARGET)
    completed = prepare_target_history(usage, COMPLETED_TARGET)
    frontdesk = prepare_target_history(usage, FRONTDESK_TARGET)

    assert CLINICAL_TARGET in clinical.columns
    assert FRONTDESK_TARGET not in clinical.columns
    assert COMPLETED_TARGET not in clinical.columns

    assert COMPLETED_TARGET in completed.columns
    assert CLINICAL_TARGET not in completed.columns
    assert FRONTDESK_TARGET not in completed.columns

    assert FRONTDESK_TARGET in frontdesk.columns
    assert CLINICAL_TARGET not in frontdesk.columns
    assert COMPLETED_TARGET not in frontdesk.columns


def test_recursive_target_forecast_ignores_holdout_outcomes() -> None:
    usage = make_usage()
    cutoff = usage["date"].max() - pd.Timedelta(days=14)
    train = usage[usage["date"] <= cutoff]
    test = usage[usage["date"] > cutoff]

    clean = recursive_target_forecast(train, test, target_col=CLINICAL_TARGET)
    poisoned = test.copy()
    poisoned["visits"] = 0
    poisoned["scheduled_appointments"] = 100_000
    poisoned["no_show_count"] = 99_000
    poisoned["same_day_cancellations"] = 900
    leaked = recursive_target_forecast(train, poisoned, target_col=CLINICAL_TARGET)
    pd.testing.assert_frame_equal(clean, leaked)


def test_role_specific_staffing_uses_distinct_targets() -> None:
    forecast = pd.DataFrame(
        {
            "clinic_id": ["A"],
            "date": [pd.Timestamp("2026-01-01")],
            "attended_pred": [36.0],
            "scheduled_pred": [71.0],
        }
    )
    plan = recommend_role_specific_staffing(
        forecast,
        rules=StaffingRules(buffer_ratio=0.0),
    )
    assert int(plan.loc[0, "recommended_clinicians"]) == 2
    assert int(plan.loc[0, "recommended_nurses"]) == 2
    assert int(plan.loc[0, "recommended_frontdesk"]) == 3


@pytest.fixture(scope="module")
def processed_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("role_specific_processed")
    network = generate_network_data(
        SyntheticDataConfig(start_date="2024-01-01", end_date="2024-12-31", n_clinics=3)
    )
    network.usage.to_csv(directory / "clinic_daily_usage.csv", index=False)
    network.metadata.to_csv(directory / "clinic_metadata.csv", index=False)
    return directory


def _copy_processed_dir(source: Path, destination: Path) -> Path:
    destination.mkdir()
    for filename in ("clinic_daily_usage.csv", "clinic_metadata.csv"):
        shutil.copy2(source / filename, destination / filename)
    return destination


def test_role_specific_batch_smoke(processed_dir: Path, tmp_path: Path) -> None:
    result = run_role_specific_batch(
        RoleSpecificBatchConfig(
            data_dir=processed_dir,
            output_dir=tmp_path / "outputs",
            horizon_days=7,
            calibration_folds=2,
            initial_train_days=180,
        )
    )
    forecasts = pd.read_csv(result.forecast_path)
    staffing = pd.read_csv(result.staffing_path)
    monitoring = pd.read_csv(result.monitoring_path)

    assert len(forecasts) == 7 * 3
    assert {
        "attended_pred",
        "attended_lower",
        "attended_upper",
        "completed_pred",
        "completed_lower",
        "completed_upper",
        "scheduled_pred",
        "scheduled_lower",
        "scheduled_upper",
        "daily_capacity",
        "capacity_pressure",
        "hybrid_target",
        "hybrid_clinical_forecast",
        "hybrid_clinical_upper",
    }.issubset(forecasts.columns)

    expected_pressure = (
        forecasts["completed_upper"] >= forecasts["daily_capacity"]
    ).astype(int)
    assert forecasts["capacity_pressure"].tolist() == expected_pressure.tolist()

    expected_hybrid = forecasts["completed_pred"].where(
        forecasts["capacity_pressure"] == 0,
        forecasts["attended_pred"],
    )
    assert np.allclose(forecasts["hybrid_clinical_forecast"], expected_hybrid)

    assert {
        "capacity_pressure",
        "hybrid_target",
        "mean_plan_clinicians",
        "mean_plan_nurses",
        "mean_plan_frontdesk",
        "upper_plan_clinicians",
        "upper_plan_nurses",
        "upper_plan_frontdesk",
    }.issubset(staffing.columns)

    assert {"clinic", "network"}.issubset(set(monitoring["level"]))
    assert (monitoring["capacity_pressure_rate"].between(0.0, 1.0)).all()
    assert (monitoring["attended_demand_selected_rate"].between(0.0, 1.0)).all()

    assert (forecasts["attended_lower"] <= forecasts["attended_pred"]).all()
    assert (forecasts["completed_lower"] <= forecasts["completed_pred"]).all()
    assert (forecasts["scheduled_lower"] <= forecasts["scheduled_pred"]).all()


def test_role_specific_batch_inherits_generation_calendar(
    processed_dir: Path, tmp_path: Path
) -> None:
    isolated_dir = _copy_processed_dir(processed_dir, tmp_path / "england_wales_processed")
    (isolated_dir / "generation_manifest.json").write_text(
        json.dumps({"holiday_calendar": "england_wales"})
    )
    result = run_role_specific_batch(
        RoleSpecificBatchConfig(
            data_dir=isolated_dir,
            output_dir=tmp_path / "outputs",
            horizon_days=7,
            calibration_folds=2,
            initial_train_days=180,
        )
    )
    from clinic_forecast.registry import LocalModelRegistry

    registry = LocalModelRegistry(result.forecast_path.parents[2] / "model_registry")
    record = registry.latest("global_ml_hgb_attended_demand")
    assert record is not None
    assert record.params["holiday_calendar"] == "england_wales"


def test_role_specific_batch_rejects_calendar_mismatch(
    processed_dir: Path, tmp_path: Path
) -> None:
    isolated_dir = _copy_processed_dir(processed_dir, tmp_path / "mismatch_processed")
    (isolated_dir / "generation_manifest.json").write_text(
        json.dumps({"holiday_calendar": "england_wales"})
    )
    config = RoleSpecificBatchConfig(
        data_dir=isolated_dir,
        output_dir=tmp_path / "outputs",
        horizon_days=7,
        calibration_folds=2,
        initial_train_days=180,
        holiday_calendar="legacy_fixed",
    )
    with pytest.raises(ValueError, match="does not match generation provenance"):
        run_role_specific_batch(config)
