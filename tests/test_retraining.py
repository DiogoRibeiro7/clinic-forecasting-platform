from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from clinic_forecast.api.contract import V2_MONITORING_REQUIRED_COLUMNS
from clinic_forecast.registry import LocalModelRegistry
from clinic_forecast.retraining import verify_role_specific_retraining
from clinic_forecast.role_specific import CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET


def _write_serving_artifacts(root: Path, horizon: int = 2) -> None:
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
        ],
        columns=sorted(V2_MONITORING_REQUIRED_COLUMNS),
    )

    forecasts.to_csv(forecast_dir / "latest.csv", index=False)
    staffing.to_csv(staffing_dir / "latest.csv", index=False)
    monitoring.to_csv(monitoring_dir / "latest.csv", index=False)
    forecasts.to_csv(forecast_dir / "forecast_20260101.csv", index=False)
    staffing.to_csv(staffing_dir / "staffing_20260101.csv", index=False)
    monitoring.to_csv(monitoring_dir / "hybrid_policy_20260101.csv", index=False)


def _write_registry(root: Path, horizon: int = 2) -> None:
    registry = LocalModelRegistry(root / "model_registry")
    artifact_paths = {
        "forecasts": str(root / "role_specific" / "forecasts" / "forecast_20260101.csv"),
        "staffing": str(root / "role_specific" / "staffing" / "staffing_20260101.csv"),
        "hybrid_monitoring": str(
            root / "role_specific" / "monitoring" / "hybrid_policy_20260101.csv"
        ),
    }
    for target in (CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET):
        registry.register(
            name=f"global_ml_hgb_{target}",
            train_start="2025-01-01",
            train_end="2025-12-31",
            horizon_days=horizon,
            artifact_paths=artifact_paths,
            trained_at="2026-01-01T00:00:00+00:00",
        )


def test_verify_role_specific_retraining_accepts_coherent_run(tmp_path: Path) -> None:
    _write_serving_artifacts(tmp_path)
    _write_registry(tmp_path)

    summary = verify_role_specific_retraining(tmp_path)

    assert summary.train_end == "2025-12-31"
    assert summary.horizon_days == 2
    assert summary.n_clinics == 1
    assert set(summary.model_versions) == {
        f"global_ml_hgb_{CLINICAL_TARGET}",
        f"global_ml_hgb_{COMPLETED_TARGET}",
        f"global_ml_hgb_{FRONTDESK_TARGET}",
    }


def test_verify_role_specific_retraining_rejects_missing_model(tmp_path: Path) -> None:
    _write_serving_artifacts(tmp_path)
    registry = LocalModelRegistry(tmp_path / "model_registry")
    for target in (CLINICAL_TARGET, COMPLETED_TARGET):
        registry.register(
            name=f"global_ml_hgb_{target}",
            train_start="2025-01-01",
            train_end="2025-12-31",
            horizon_days=2,
        )

    with pytest.raises(ValueError, match="missing required model"):
        verify_role_specific_retraining(tmp_path)


def test_verify_role_specific_retraining_rejects_horizon_mismatch(tmp_path: Path) -> None:
    _write_serving_artifacts(tmp_path, horizon=2)
    _write_registry(tmp_path, horizon=3)

    with pytest.raises(ValueError, match="horizon does not match"):
        verify_role_specific_retraining(tmp_path)
