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
    for clinic in ["CLINIC_001", "CLINIC_002"]:
        for d in dates:
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
    pd.DataFrame(forecast_rows).to_csv(output_dir / "forecasts" / "latest.csv", index=False)
    pd.DataFrame(staffing_rows).to_csv(output_dir / "staffing" / "latest.csv", index=False)

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


def test_forecasts_unknown_clinic_404(api_env: None) -> None:
    response = request("GET", "/forecasts", params={"clinic_id": "CLINIC_999"})
    assert response.status_code == 404
    assert "Unknown clinic_id" in response.json()["detail"]


def test_forecasts_empty_window_404_with_available_range(api_env: None) -> None:
    response = request(
        "GET",
        "/forecasts", params={"clinic_id": "CLINIC_001", "start_date": "2030-01-01"}
    )
    assert response.status_code == 404
    assert "available dates" in response.json()["detail"]


def test_staffing_returns_both_plans(api_env: None) -> None:
    response = request("GET", "/staffing", params={"clinic_id": "CLINIC_002"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 7
    assert body[0]["upper_plan_clinicians"] >= body[0]["mean_plan_clinicians"]


def test_missing_outputs_returns_503(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINIC_FORECAST_OUTPUT_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("CLINIC_FORECAST_DATA_DIR", str(tmp_path / "empty"))
    response = request("GET", "/forecasts", params={"clinic_id": "CLINIC_001"})
    assert response.status_code == 503
    assert "run_batch_forecast" in response.json()["detail"]


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
