from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import pytest

from clinic_forecast.api.main import app


@pytest.fixture()
def api_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "processed"
    output_dir = tmp_path / "outputs"
    (output_dir / "forecasts").mkdir(parents=True)
    (output_dir / "staffing").mkdir(parents=True)
    (output_dir / "role_specific" / "forecasts").mkdir(parents=True)
    (output_dir / "role_specific" / "staffing").mkdir(parents=True)
    (output_dir / "role_specific" / "monitoring").mkdir(parents=True)
    data_dir.mkdir()

    pd.DataFrame(
        {
            "clinic_id": ["CLINIC_001", "CLINIC_002"],
            "region": ["north", "south"],
            "clinic_size": ["small", "large"],
            "specialty": ["primary_care", "urgent_care"],
            "daily_capacity": [80, 220],
            "base_clinicians": [4, 11],
            "base_nurses": [5, 14],
            "base_frontdesk": [2, 6],
            "weekend_open": [0, 1],
        }
    ).to_csv(data_dir / "clinic_metadata.csv", index=False)

    dates = pd.date_range("2026-01-01", periods=7, freq="D")
    forecast_rows = []
    staffing_rows = []
    role_forecast_rows = []
    role_staffing_rows = []
    for clinic in ["CLINIC_001", "CLINIC_002"]:
        capacity = 80.0 if clinic == "CLINIC_001" else 220.0
        for idx, d in enumerate(dates):
            forecast_rows.append(
                {
                    "clinic_id": clinic,
                    "date": d,
                    "model": "global_ml_hgb",
                    "is_open": 1,
                    "y_pred": 50.0,
                    "y_lower": 30.0,
                    "y_upper": 70.0,
                }
            )
            staffing_rows.append(
                {
                    "clinic_id": clinic,
                    "date": d,
                    "mean_plan_clinicians": 3,
                    "mean_plan_nurses": 3,
                    "mean_plan_frontdesk": 2,
                    "upper_plan_clinicians": 4,
                    "upper_plan_nurses": 3,
                    "upper_plan_frontdesk": 2,
                }
            )
            pressure = int(clinic == "CLINIC_001" and idx % 2 == 0)
            attended = 90.0
            completed = 70.0
            role_forecast_rows.append(
                {
                    "clinic_id": clinic,
                    "date": d,
                    "is_open": 1,
                    "daily_capacity": capacity,
                    "attended_pred": attended,
                    "attended_lower": 75.0,
                    "attended_upper": 105.0,
                    "completed_pred": completed,
                    "completed_lower": 60.0,
                    "completed_upper": 85.0 if pressure else 75.0,
                    "scheduled_pred": 100.0,
                    "scheduled_lower": 85.0,
                    "scheduled_upper": 115.0,
                    "capacity_pressure": pressure,
                    "hybrid_target": "attended_demand" if pressure else "completed_visits",
                    "hybrid_clinical_forecast": attended if pressure else completed,
                    "hybrid_clinical_upper": 105.0 if pressure else (85.0 if pressure else 75.0),
                }
            )
            role_staffing_rows.append(
                {
                    "clinic_id": clinic,
                    "date": d,
                    "daily_capacity": capacity,
                    "capacity_pressure": pressure,
                    "hybrid_target": "attended_demand" if pressure else "completed_visits",
                    "mean_plan_clinicians": 5 if pressure else 4,
                    "mean_plan_nurses": 4 if pressure else 3,
                    "mean_plan_frontdesk": 3,
                    "upper_plan_clinicians": 6 if pressure else 5,
                    "upper_plan_nurses": 5 if pressure else 4,
                    "upper_plan_frontdesk": 4,
                }
            )

    pd.DataFrame(forecast_rows).to_csv(output_dir / "forecasts" / "latest.csv", index=False)
    pd.DataFrame(staffing_rows).to_csv(output_dir / "staffing" / "latest.csv", index=False)
    pd.DataFrame(role_forecast_rows).to_csv(
        output_dir / "role_specific" / "forecasts" / "latest.csv", index=False
    )
    pd.DataFrame(role_staffing_rows).to_csv(
        output_dir / "role_specific" / "staffing" / "latest.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "level": "clinic",
                "group": "CLINIC_001",
                "n_open_days": 7,
                "capacity_pressure_days": 4,
                "capacity_pressure_rate": 4 / 7,
                "attended_demand_selected_days": 4,
                "attended_demand_selected_rate": 4 / 7,
                "mean_completed_upper_capacity_ratio": 1.01,
            },
            {
                "level": "network",
                "group": "all",
                "n_open_days": 14,
                "capacity_pressure_days": 4,
                "capacity_pressure_rate": 4 / 14,
                "attended_demand_selected_days": 4,
                "attended_demand_selected_rate": 4 / 14,
                "mean_completed_upper_capacity_ratio": 0.65,
            },
        ]
    ).to_csv(output_dir / "role_specific" / "monitoring" / "latest.csv", index=False)

    monkeypatch.setenv("CLINIC_FORECAST_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CLINIC_FORECAST_OUTPUT_DIR", str(output_dir))


def request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    """Issue one request against the FastAPI app without TestClient."""

    async def _send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_send())


def test_health_reports_artefacts(api_env: None) -> None:
    response = request("GET", "/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["forecasts_available"] is True
    assert body["staffing_available"] is True


def test_v2_health_reports_role_specific_artefacts(api_env: None) -> None:
    response = request("GET", "/v2/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "ok",
        "forecasts_available": True,
        "staffing_available": True,
        "hybrid_monitoring_available": True,
    }


def test_clinics_lists_metadata(api_env: None) -> None:
    response = request("GET", "/clinics")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["clinic_id"] == "CLINIC_001"
    assert body[1]["weekend_open"] is True


def test_forecasts_filters_by_clinic_and_window(api_env: None) -> None:
    response = request(
        "GET",
        "/forecasts",
        params={
            "clinic_id": "CLINIC_001",
            "start_date": "2026-01-02",
            "end_date": "2026-01-04",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert all(p["clinic_id"] == "CLINIC_001" for p in body)
    assert body[0]["y_lower"] <= body[0]["y_pred"] <= body[0]["y_upper"]
    assert "hybrid_target" not in body[0]


def test_v2_forecasts_exposes_auditable_hybrid_decision(api_env: None) -> None:
    response = request("GET", "/v2/forecasts", params={"clinic_id": "CLINIC_001"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 7
    assert {p["hybrid_target"] for p in body} == {"attended_demand", "completed_visits"}
    pressured = next(p for p in body if p["capacity_pressure"])
    assert pressured["hybrid_clinical_forecast"] == pressured["attended_pred"]
    unpressured = next(p for p in body if not p["capacity_pressure"])
    assert unpressured["hybrid_clinical_forecast"] == unpressured["completed_pred"]


def test_forecasts_unknown_clinic_404(api_env: None) -> None:
    response = request("GET", "/forecasts", params={"clinic_id": "CLINIC_999"})
    assert response.status_code == 404
    assert "Unknown clinic_id" in response.json()["detail"]


def test_forecasts_empty_window_404_with_available_range(api_env: None) -> None:
    response = request(
        "GET", "/forecasts", params={"clinic_id": "CLINIC_001", "start_date": "2030-01-01"}
    )
    assert response.status_code == 404
    assert "available dates" in response.json()["detail"]


def test_staffing_returns_both_plans(api_env: None) -> None:
    response = request("GET", "/staffing", params={"clinic_id": "CLINIC_002"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 7
    assert body[0]["upper_plan_clinicians"] >= body[0]["mean_plan_clinicians"]
    assert "hybrid_target" not in body[0]


def test_v2_staffing_exposes_selected_target(api_env: None) -> None:
    response = request("GET", "/v2/staffing", params={"clinic_id": "CLINIC_001"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 7
    assert body[0]["hybrid_target"] in {"attended_demand", "completed_visits"}
    assert body[0]["upper_plan_clinicians"] >= body[0]["mean_plan_clinicians"]


def test_v2_hybrid_monitoring_returns_descriptive_summary(api_env: None) -> None:
    response = request("GET", "/v2/hybrid-monitoring")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[-1]["level"] == "network"
    assert body[-1]["group"] == "all"


def test_missing_outputs_returns_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINIC_FORECAST_OUTPUT_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("CLINIC_FORECAST_DATA_DIR", str(tmp_path / "empty"))
    response = request("GET", "/forecasts", params={"clinic_id": "CLINIC_001"})
    assert response.status_code == 503
    assert "run_batch_forecast" in response.json()["detail"]


def test_v2_missing_outputs_returns_503(api_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINIC_FORECAST_OUTPUT_DIR", str(tmp_path / "empty"))
    response = request("GET", "/v2/forecasts", params={"clinic_id": "CLINIC_001"})
    assert response.status_code == 503
    assert "run_role_specific_batch" in response.json()["detail"]


def test_marketing_scenario_scales_open_days(api_env: None) -> None:
    response = request(
        "POST",
        "/scenario/marketing",
        json={"clinic_ids": ["CLINIC_001"], "spend_multiplier": 2.0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["spend_multiplier"] == 2.0
    assert body["total_incremental_visits"] > 0
    point = body["points"][0]
    assert point["scenario_forecast"] > point["baseline_forecast"]


def test_marketing_scenario_unknown_clinic_404(api_env: None) -> None:
    response = request(
        "POST",
        "/scenario/marketing",
        json={"clinic_ids": ["CLINIC_404"], "spend_multiplier": 1.5},
    )
    assert response.status_code == 404


def test_marketing_scenario_rejects_invalid_multiplier(api_env: None) -> None:
    response = request("POST", "/scenario/marketing", json={"spend_multiplier": 0})
    assert response.status_code == 422
