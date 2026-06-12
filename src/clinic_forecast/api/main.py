"""FastAPI forecast-serving layer.

Serves the artefacts written by the batch pipeline
(`scripts/run_batch_forecast.py`): clinic metadata, demand forecasts with
prediction intervals and staffing recommendations. The API is deliberately
read-only and file-backed — no database, no in-request model training — so it
can run anywhere the batch outputs exist.

Configuration via environment variables (useful for tests and Docker):

- ``CLINIC_FORECAST_OUTPUT_DIR``: directory holding ``forecasts/latest.csv``
  and ``staffing/latest.csv`` (default: ``<repo>/outputs``).
- ``CLINIC_FORECAST_DATA_DIR``: directory holding ``clinic_metadata.csv``
  (default: ``<repo>/data/processed``).
"""

from __future__ import annotations

import os
from datetime import date as date_type
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

_REPO_ROOT = Path(__file__).resolve().parents[3]

app = FastAPI(
    title="Clinic Forecasting Platform",
    version="0.2.0",
    description="Read-only serving API for batch demand forecasts and staffing plans.",
)


def _output_dir() -> Path:
    return Path(os.getenv("CLINIC_FORECAST_OUTPUT_DIR", _REPO_ROOT / "outputs"))


def _data_dir() -> Path:
    return Path(os.getenv("CLINIC_FORECAST_DATA_DIR", _REPO_ROOT / "data" / "processed"))


def _load_csv(path: Path, what: str, hint: str) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"{what} not available: {path}. {hint}")
    if what == "Clinic metadata":
        return pd.read_csv(path)
    return pd.read_csv(path, parse_dates=["date"])


def _load_metadata() -> pd.DataFrame:
    return _load_csv(
        _data_dir() / "clinic_metadata.csv",
        "Clinic metadata",
        "Run `poetry run python scripts/generate_data.py` first.",
    )


def _load_latest(kind: str) -> pd.DataFrame:
    return _load_csv(
        _output_dir() / kind / "latest.csv",
        f"{kind.capitalize()} outputs",
        "Run `poetry run python scripts/run_batch_forecast.py` first.",
    )


def _filter_window(
    frame: pd.DataFrame,
    clinic_id: str,
    start_date: date_type | None,
    end_date: date_type | None,
) -> pd.DataFrame:
    metadata = _load_metadata()
    if clinic_id not in set(metadata["clinic_id"]):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown clinic_id '{clinic_id}'. See GET /clinics for valid ids.",
        )
    selected = frame[frame["clinic_id"] == clinic_id]
    if start_date is not None:
        selected = selected[selected["date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        selected = selected[selected["date"] <= pd.Timestamp(end_date)]
    if selected.empty:
        available_min = frame["date"].min().date()
        available_max = frame["date"].max().date()
        raise HTTPException(
            status_code=404,
            detail=(
                f"No rows for '{clinic_id}' in the requested window; "
                f"available dates are {available_min} to {available_max}."
            ),
        )
    return selected.sort_values("date")


class HealthResponse(BaseModel):
    """API health and artefact availability."""

    status: str
    forecasts_available: bool
    staffing_available: bool


class ClinicInfo(BaseModel):
    """One clinic's metadata."""

    clinic_id: str
    region: str
    clinic_size: str
    specialty: str
    daily_capacity: int
    weekend_open: bool


class ForecastPoint(BaseModel):
    """One clinic-day forecast with prediction interval."""

    clinic_id: str
    date: date_type
    model: str
    is_open: bool
    y_pred: float
    y_lower: float
    y_upper: float


class StaffingPoint(BaseModel):
    """One clinic-day staffing recommendation under both plans."""

    clinic_id: str
    date: date_type
    mean_plan_clinicians: int
    mean_plan_nurses: int
    mean_plan_frontdesk: int
    upper_plan_clinicians: int
    upper_plan_nurses: int
    upper_plan_frontdesk: int


class MarketingScenarioRequest(BaseModel):
    """What-if request: scale planned marketing spend for selected clinics."""

    clinic_ids: list[str] | None = Field(
        default=None, description="Clinics to adjust; all clinics when omitted."
    )
    spend_multiplier: float = Field(
        gt=0, le=10, description="Multiplier applied to planned marketing spend."
    )


class MarketingScenarioPoint(BaseModel):
    """Baseline vs scenario forecast for one clinic-day."""

    clinic_id: str
    date: date_type
    baseline_forecast: float
    scenario_forecast: float
    incremental_visits: float


class MarketingScenarioResponse(BaseModel):
    """Scenario summary plus per-day detail."""

    spend_multiplier: float
    assumed_elasticity: float
    total_incremental_visits: float
    points: list[MarketingScenarioPoint]


#: Demand uplift per unit change in log-spend. A documented placeholder
#: assumption until the model-based scenario module replaces it; the value is
#: in the range estimated from the historical spend-demand relationship.
MARKETING_LOG_ELASTICITY = 0.08


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service status and whether batch artefacts are present."""
    return HealthResponse(
        status="ok",
        forecasts_available=(_output_dir() / "forecasts" / "latest.csv").exists(),
        staffing_available=(_output_dir() / "staffing" / "latest.csv").exists(),
    )


@app.get("/clinics", response_model=list[ClinicInfo])
def clinics() -> list[ClinicInfo]:
    """List clinics in the network."""
    metadata = _load_metadata()
    return [
        ClinicInfo(
            clinic_id=row["clinic_id"],
            region=row["region"],
            clinic_size=row["clinic_size"],
            specialty=row["specialty"],
            daily_capacity=int(row["daily_capacity"]),
            weekend_open=bool(row["weekend_open"]),
        )
        for _, row in metadata.iterrows()
    ]


@app.get("/forecasts", response_model=list[ForecastPoint])
def forecasts(
    clinic_id: Annotated[str, Query(description="Clinic identifier, e.g. CLINIC_001")],
    start_date: Annotated[date_type | None, Query()] = None,
    end_date: Annotated[date_type | None, Query()] = None,
) -> list[ForecastPoint]:
    """Return forecast points with intervals for one clinic."""
    frame = _filter_window(_load_latest("forecasts"), clinic_id, start_date, end_date)
    return [
        ForecastPoint(
            clinic_id=row["clinic_id"],
            date=row["date"].date(),
            model=row["model"],
            is_open=bool(row["is_open"]),
            y_pred=float(row["y_pred"]),
            y_lower=float(row["y_lower"]),
            y_upper=float(row["y_upper"]),
        )
        for _, row in frame.iterrows()
    ]


@app.get("/staffing", response_model=list[StaffingPoint])
def staffing(
    clinic_id: Annotated[str, Query(description="Clinic identifier, e.g. CLINIC_001")],
    start_date: Annotated[date_type | None, Query()] = None,
    end_date: Annotated[date_type | None, Query()] = None,
) -> list[StaffingPoint]:
    """Return staffing recommendations (mean and conservative plans)."""
    frame = _filter_window(_load_latest("staffing"), clinic_id, start_date, end_date)
    return [
        StaffingPoint(
            clinic_id=row["clinic_id"],
            date=row["date"].date(),
            mean_plan_clinicians=int(row["mean_plan_clinicians"]),
            mean_plan_nurses=int(row["mean_plan_nurses"]),
            mean_plan_frontdesk=int(row["mean_plan_frontdesk"]),
            upper_plan_clinicians=int(row["upper_plan_clinicians"]),
            upper_plan_nurses=int(row["upper_plan_nurses"]),
            upper_plan_frontdesk=int(row["upper_plan_frontdesk"]),
        )
        for _, row in frame.iterrows()
    ]


@app.post("/scenario/marketing", response_model=MarketingScenarioResponse)
def marketing_scenario(request: MarketingScenarioRequest) -> MarketingScenarioResponse:
    """Estimate forecast impact of scaling planned marketing spend.

    Applies a documented log-elasticity assumption to the latest baseline
    forecasts. This is model-based what-if analysis under an explicit
    assumption, not a causal claim about marketing effectiveness.
    """
    import math

    frame = _load_latest("forecasts")
    metadata = _load_metadata()
    valid_ids = set(metadata["clinic_id"])
    targets = request.clinic_ids or sorted(valid_ids)
    unknown = sorted(set(targets) - valid_ids)
    if unknown:
        raise HTTPException(status_code=404, detail=f"Unknown clinic_ids: {unknown}.")

    uplift = 1.0 + MARKETING_LOG_ELASTICITY * math.log(request.spend_multiplier)
    selected = frame[frame["clinic_id"].isin(targets) & (frame["is_open"] == 1)]

    points = []
    for _, row in selected.sort_values(["clinic_id", "date"]).iterrows():
        scenario_value = float(row["y_pred"]) * uplift
        points.append(
            MarketingScenarioPoint(
                clinic_id=row["clinic_id"],
                date=row["date"].date(),
                baseline_forecast=float(row["y_pred"]),
                scenario_forecast=scenario_value,
                incremental_visits=scenario_value - float(row["y_pred"]),
            )
        )
    return MarketingScenarioResponse(
        spend_multiplier=request.spend_multiplier,
        assumed_elasticity=MARKETING_LOG_ELASTICITY,
        total_incremental_visits=float(sum(p.incremental_visits for p in points)),
        points=points,
    )
