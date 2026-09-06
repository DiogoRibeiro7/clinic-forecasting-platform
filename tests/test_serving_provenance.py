from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi import HTTPException, Response

from clinic_forecast.api.contract import V2_RUN_ID_HEADER
from clinic_forecast.api.main import v2_provenance
from clinic_forecast.registry import LocalModelRegistry
from clinic_forecast.role_specific import CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET
from clinic_forecast.serving_provenance import load_serving_manifest, verify_file_fingerprint
from clinic_forecast.serving_snapshot import (
    ServingSnapshotRequest,
    snapshot_role_specific_serving_run,
)


def _write_source_artifacts(root: Path, horizon: int = 2) -> tuple[Path, Path, Path]:
    role_root = root / "role_specific"
    forecast_dir = role_root / "forecasts"
    staffing_dir = role_root / "staffing"
    monitoring_dir = role_root / "monitoring"
    forecast_dir.mkdir(parents=True)
    staffing_dir.mkdir(parents=True)
    monitoring_dir.mkdir(parents=True)

    dates = pd.date_range("2026-01-01", periods=horizon, freq="D")
    forecasts = pd.DataFrame(
        {
            "clinic_id": ["A"] * horizon,
            "date": dates,
            "is_open": [1] * horizon,
            "daily_capacity": [100.0] * horizon,
            "attended_pred": [90.0] * horizon,
            "attended_lower": [80.0] * horizon,
            "attended_upper": [100.0] * horizon,
            "completed_pred": [85.0] * horizon,
            "completed_lower": [75.0] * horizon,
            "completed_upper": [95.0] * horizon,
            "scheduled_pred": [110.0] * horizon,
            "scheduled_lower": [100.0] * horizon,
            "scheduled_upper": [120.0] * horizon,
            "capacity_pressure": [0] * horizon,
            "hybrid_target": ["visits"] * horizon,
            "hybrid_clinical_forecast": [85.0] * horizon,
            "hybrid_clinical_upper": [95.0] * horizon,
        }
    )
    staffing = pd.DataFrame(
        {
            "clinic_id": ["A"] * horizon,
            "date": dates,
            "daily_capacity": [100.0] * horizon,
            "capacity_pressure": [0] * horizon,
            "hybrid_target": ["visits"] * horizon,
            "mean_plan_clinicians": [5] * horizon,
            "mean_plan_nurses": [3] * horizon,
            "mean_plan_frontdesk": [2] * horizon,
            "upper_plan_clinicians": [6] * horizon,
            "upper_plan_nurses": [4] * horizon,
            "upper_plan_frontdesk": [3] * horizon,
        }
    )
    monitoring = pd.DataFrame(
        [
            {
                "level": "network",
                "group": "all",
                "n_open_days": horizon,
                "capacity_pressure_days": 0,
                "capacity_pressure_rate": 0.0,
                "attended_demand_selected_days": 0,
                "attended_demand_selected_rate": 0.0,
                "mean_completed_upper_capacity_ratio": 0.95,
            }
        ]
    )
    forecast_path = forecast_dir / "forecast_20251231.csv"
    staffing_path = staffing_dir / "staffing_20251231.csv"
    monitoring_path = monitoring_dir / "hybrid_policy_20251231.csv"
    forecasts.to_csv(forecast_path, index=False)
    staffing.to_csv(staffing_path, index=False)
    monitoring.to_csv(monitoring_path, index=False)
    forecasts.to_csv(forecast_dir / "latest.csv", index=False)
    staffing.to_csv(staffing_dir / "latest.csv", index=False)
    monitoring.to_csv(monitoring_dir / "latest.csv", index=False)
    return forecast_path, staffing_path, monitoring_path


def _write_inputs(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"clinic_id": ["A"], "date": ["2025-12-31"], "visits": [80]}).to_csv(
        data_dir / "clinic_daily_usage.csv", index=False
    )
    pd.DataFrame({"clinic_id": ["A"], "daily_capacity": [100]}).to_csv(
        data_dir / "clinic_metadata.csv", index=False
    )
    (data_dir / "generation_manifest.json").write_text(
        json.dumps({"holiday_calendar": "legacy_fixed"}), encoding="utf-8"
    )


def _write_registry(output_dir: Path, horizon: int = 2) -> None:
    registry = LocalModelRegistry(output_dir / "model_registry")
    for target in (CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET):
        registry.register(
            name=f"global_ml_hgb_{target}",
            train_start="2025-01-01",
            train_end="2025-12-31",
            horizon_days=horizon,
            params={"holiday_calendar": "legacy_fixed", "target_col": target},
            trained_at="2026-01-01T00:00:00+00:00",
        )


def _snapshot_request(tmp_path: Path) -> ServingSnapshotRequest:
    output_dir = tmp_path / "outputs"
    data_dir = tmp_path / "processed"
    _write_inputs(data_dir)
    forecast_path, staffing_path, monitoring_path = _write_source_artifacts(output_dir)
    _write_registry(output_dir)
    return ServingSnapshotRequest(
        output_dir=output_dir,
        data_dir=data_dir,
        origin="2025-12-31",
        estimator="hgb",
        horizon_days=2,
        coverage=0.9,
        calibration_folds=2,
        initial_train_days=180,
        staffing_config=None,
        requested_holiday_calendar=None,
        forecast_path=forecast_path,
        staffing_path=staffing_path,
        monitoring_path=monitoring_path,
        source_revision="abc123",
    )


def test_snapshot_creates_immutable_traceable_run(tmp_path: Path) -> None:
    request = _snapshot_request(tmp_path)

    manifest = snapshot_role_specific_serving_run(request)
    run_dir = request.output_dir / "role_specific" / "runs" / manifest.run_id

    assert manifest.source_revision == "abc123"
    assert manifest.config["resolved_holiday_calendar"] == "legacy_fixed"
    assert (run_dir / "manifest.json").is_file()
    assert load_serving_manifest(
        request.output_dir / "role_specific" / "latest_manifest.json"
    ).run_id == manifest.run_id
    for fingerprint in manifest.artifacts.values():
        immutable_path = request.output_dir / fingerprint.path
        verify_file_fingerprint(immutable_path, fingerprint)

    registry = LocalModelRegistry(request.output_dir / "model_registry")
    for target in (CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET):
        record = registry.latest(f"global_ml_hgb_{target}")
        assert record is not None
        assert record.params["serving_run_id"] == manifest.run_id
        assert manifest.run_id in record.artifact_paths["forecasts"]


def test_snapshot_rejects_already_bound_registry_version(tmp_path: Path) -> None:
    request = _snapshot_request(tmp_path)
    snapshot_role_specific_serving_run(request)

    with pytest.raises(ValueError, match="already bound"):
        snapshot_role_specific_serving_run(request)


def test_same_origin_rerun_does_not_overwrite_prior_bundle(tmp_path: Path) -> None:
    request = _snapshot_request(tmp_path)
    first = snapshot_role_specific_serving_run(request)
    first_forecast = request.output_dir / first.artifacts["forecasts"].path
    first_bytes = first_forecast.read_bytes()

    # A real rerun trains/registers fresh versions before creating its serving snapshot.
    _write_registry(request.output_dir)
    second = snapshot_role_specific_serving_run(request)

    assert first.run_id != second.run_id
    assert first_forecast.read_bytes() == first_bytes
    assert (request.output_dir / second.artifacts["forecasts"].path).is_file()
    first_manifest = load_serving_manifest(
        request.output_dir / "role_specific" / "runs" / first.run_id / "manifest.json"
    )
    for model in first_manifest.models.values():
        verify_file_fingerprint(request.output_dir / model.registry_record.path, model.registry_record)


def test_v2_provenance_exposes_run_id_and_detects_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _snapshot_request(tmp_path)
    manifest = snapshot_role_specific_serving_run(request)
    monkeypatch.setenv("CLINIC_FORECAST_OUTPUT_DIR", str(request.output_dir))

    response = Response()
    body = v2_provenance(response)

    assert body["run_id"] == manifest.run_id
    assert response.headers[V2_RUN_ID_HEADER] == manifest.run_id

    forecast_path = request.output_dir / manifest.artifacts["forecasts"].path
    forecast_path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(HTTPException) as exc_info:
        v2_provenance(Response())
    assert exc_info.value.status_code == 503
    assert "provenance mismatch" in str(exc_info.value.detail).lower()
