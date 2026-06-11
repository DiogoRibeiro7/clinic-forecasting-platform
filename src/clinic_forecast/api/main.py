"""FastAPI application for forecast-serving demonstration."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from clinic_forecast.staffing import StaffingRules, recommend_staffing

app = FastAPI(title="Clinic Forecasting Platform", version="0.1.0")


class HealthResponse(BaseModel):
    """API health response."""

    status: Literal["ok"]


class StaffingRequest(BaseModel):
    """Request body for staffing recommendations."""

    clinic_id: str
    date: str
    forecast: float = Field(ge=0)


class StaffingResponse(BaseModel):
    """Staffing recommendation response."""

    clinic_id: str
    date: str
    forecast: float
    recommended_clinicians: int
    recommended_nurses: int
    recommended_frontdesk: int


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return service health."""
    return HealthResponse(status="ok")


@app.post("/staffing", response_model=StaffingResponse)
def staffing(request: StaffingRequest) -> StaffingResponse:
    """Convert a single demand forecast into staffing recommendations."""
    import pandas as pd

    forecast = pd.DataFrame([request.model_dump()])
    recommended = recommend_staffing(forecast, rules=StaffingRules())
    row = recommended.iloc[0]
    return StaffingResponse(
        clinic_id=str(row["clinic_id"]),
        date=str(row["date"]),
        forecast=float(row["forecast"]),
        recommended_clinicians=int(row["recommended_clinicians"]),
        recommended_nurses=int(row["recommended_nurses"]),
        recommended_frontdesk=int(row["recommended_frontdesk"]),
    )
