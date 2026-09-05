"""FastAPI forecast-serving layer.

The unversioned routes preserve the legacy completed-visits serving contract.
Versioned ``/v2`` routes expose the role-specific hybrid decision artefacts
written by ``scripts/run_role_specific_batch.py``. The API is read-only and
never trains models or recomputes the hybrid switch inside request handling.
"""

from __future__ import annotations

import os
from datetime import date as date_type
from pathlib import Path
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from clinic_forecast.api.contract import (
    V2_CONTRACT_HEADER,
    V2_CONTRACT_VERSION,
    V2_REQUIRED_COLUMNS,
    V2ArtifactKind,
    validate_v2_artifact,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

app = FastAPI(
    title="Clinic Forecasting Platform",
    version="0.3.0",
    description="Read-only serving API for batch demand forecasts and staffing plans.",
)


def _output_dir() -> Path:
    return Path(os.getenv("CLINIC_FORECAST_OUTPUT_DIR", _REPO_ROOT / "outputs"))


def _data_dir() -> Path:
    return Path(os.getenv("CLINIC_FORECAST_DATA_DIR", _REPO_ROOT / "data" / "processed"))


def _load_csv(path: Path, what: str, hint: str) -> pd.DataFrame:
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"{what} not available: {path}. {hint}")
    if what in {"Clinic metadata", "Hybrid monitoring outputs"}:
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


def _load_role_latest(kind: V2ArtifactKind) -> pd.DataFrame:
    what = "Hybrid monitoring outputs" if kind == "monitoring" else f"Role-specific {kind} outputs"
    frame = _load_csv(
        _output_dir() / "role_specific" / kind / "latest.csv",
        what,
        "Run `poetry run python scripts/run_role_specific_batch.py` first.",
    )
    try:
        validate_v2_artifact(frame, kind)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return frame


def _set_v2_contract_header(response: Response) -> None:
    response.headers[V2_CONTRACT_HEADER] = V2_CONTRACT_VERSION


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
    """Legacy API health and artefact availability."""

    status: str
    forecasts_available: bool
    staffing_available: bool


class V2HealthResponse(BaseModel):
    """Availability of versioned hybrid-serving artefacts."""

    status: str
    forecasts_available: bool
    staffing_available: bool
    hybrid_monitoring_available: bool


class V2ContractResponse(BaseModel):
    """Discoverable schema identity for the role-specific serving contract."""

    contract_version: str
    version_header: str
    required_columns: dict[str, list[str]]


class ClinicInfo(BaseModel):
    """One clinic's metadata."""

    clinic_id: str
    region: str
    clinic_size: str
    specialty: str
    daily_capacity: int
    weekend_open: bool


class ForecastPoint(BaseModel):
    """One legacy clinic-day completed-visits forecast."""

    clinic_id: str
    date: date_type
    model: str
    is_open: bool
    y_pred: float
    y_lower: float
    y_upper: float


class V2ForecastPoint(BaseModel):
    """Auditable role-specific forecasts and frozen hybrid target selection."""

    clinic_id: str
    date: date_type
    is_open: bool
    daily_capacity: float
    attended_pred: float
    attended_lower: float
    attended_upper: float
    completed_pred: float
    completed_lower: float
    completed_upper: float
    scheduled_pred: float
    scheduled_lower: float
    scheduled_upper: float
    capacity_pressure: bool
    hybrid_target: str
    hybrid_clinical_forecast: float
    hybrid_clinical_upper: float


class StaffingPoint(BaseModel):
    """One legacy clinic-day staffing recommendation under both plans."""

    clinic_id: str
    date: date_type
    mean_plan_clinicians: int
    mean_plan_nurses: int
    mean_plan_frontdesk: int
    upper_plan_clinicians: int
    upper_plan_nurses: int
    upper_plan_frontdesk: int


class V2StaffingPoint(StaffingPoint):
    """Hybrid staffing recommendation with target-selection metadata."""

    daily_capacity: float
    capacity_pressure: bool
    hybrid_target: str


class HybridMonitoringPoint(BaseModel):
    """Descriptive use of the frozen hybrid switch."""

    level: str
    group: str
    n_open_days: int
    capacity_pressure_days: int
    capacity_pressure_rate: float
    attended_demand_selected_days: int
    attended_demand_selected_rate: float
    mean_completed_upper_capacity_ratio: float


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


MARKETING_LOG_ELASTICITY = 0.08


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return legacy service status and batch artefact availability."""
    return HealthResponse(
        status="ok",
        forecasts_available=(_output_dir() / "forecasts" / "latest.csv").exists(),
        staffing_available=(_output_dir() / "staffing" / "latest.csv").exists(),
    )


@app.get("/v2/health", response_model=V2HealthResponse)
def v2_health(response: Response) -> V2HealthResponse:
    """Return availability of the role-specific hybrid serving artefacts."""
    _set_v2_contract_header(response)
    root = _output_dir() / "role_specific"
    return V2HealthResponse(
        status="ok",
        forecasts_available=(root / "forecasts" / "latest.csv").exists(),
        staffing_available=(root / "staffing" / "latest.csv").exists(),
        hybrid_monitoring_available=(root / "monitoring" / "latest.csv").exists(),
    )


@app.get("/v2/contract", response_model=V2ContractResponse)
def v2_contract(response: Response) -> V2ContractResponse:
    """Return the immutable identity and required fields of serving contract v2."""
    _set_v2_contract_header(response)
    return V2ContractResponse(
        contract_version=V2_CONTRACT_VERSION,
        version_header=V2_CONTRACT_HEADER,
        required_columns={
            kind: sorted(columns) for kind, columns in V2_REQUIRED_COLUMNS.items()
        },
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
    """Return legacy completed-visits forecasts for one clinic."""
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


@app.get("/v2/forecasts", response_model=list[V2ForecastPoint])
def v2_forecasts(
    response: Response,
    clinic_id: Annotated[str, Query(description="Clinic identifier, e.g. CLINIC_001")],
    start_date: Annotated[date_type | None, Query()] = None,
    end_date: Annotated[date_type | None, Query()] = None,
) -> list[V2ForecastPoint]:
    """Return role-specific forecasts and the frozen hybrid decision."""
    _set_v2_contract_header(response)
    frame = _filter_window(_load_role_latest("forecasts"), clinic_id, start_date, end_date)
    return [
        V2ForecastPoint(
            clinic_id=row["clinic_id"],
            date=row["date"].date(),
            is_open=bool(row["is_open"]),
            daily_capacity=float(row["daily_capacity"]),
            attended_pred=float(row["attended_pred"]),
            attended_lower=float(row["attended_lower"]),
            attended_upper=float(row["attended_upper"]),
            completed_pred=float(row["completed_pred"]),
            completed_lower=float(row["completed_lower"]),
            completed_upper=float(row["completed_upper"]),
            scheduled_pred=float(row["scheduled_pred"]),
            scheduled_lower=float(row["scheduled_lower"]),
            scheduled_upper=float(row["scheduled_upper"]),
            capacity_pressure=bool(row["capacity_pressure"]),
            hybrid_target=str(row["hybrid_target"]),
            hybrid_clinical_forecast=float(row["hybrid_clinical_forecast"]),
            hybrid_clinical_upper=float(row["hybrid_clinical_upper"]),
        )
        for _, row in frame.iterrows()
    ]


@app.get("/staffing", response_model=list[StaffingPoint])
def staffing(
    clinic_id: Annotated[str, Query(description="Clinic identifier, e.g. CLINIC_001")],
    start_date: Annotated[date_type | None, Query()] = None,
    end_date: Annotated[date_type | None, Query()] = None,
) -> list[StaffingPoint]:
    """Return legacy staffing recommendations."""
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


@app.get("/v2/staffing", response_model=list[V2StaffingPoint])
def v2_staffing(
    response: Response,
    clinic_id: Annotated[str, Query(description="Clinic identifier, e.g. CLINIC_001")],
    start_date: Annotated[date_type | None, Query()] = None,
    end_date: Annotated[date_type | None, Query()] = None,
) -> list[V2StaffingPoint]:
    """Return hybrid staffing plans with the selected clinical target."""
    _set_v2_contract_header(response)
    frame = _filter_window(_load_role_latest("staffing"), clinic_id, start_date, end_date)
    return [
        V2StaffingPoint(
            clinic_id=row["clinic_id"],
            date=row["date"].date(),
            daily_capacity=float(row["daily_capacity"]),
            capacity_pressure=bool(row["capacity_pressure"]),
            hybrid_target=str(row["hybrid_target"]),
            mean_plan_clinicians=int(row["mean_plan_clinicians"]),
            mean_plan_nurses=int(row["mean_plan_nurses"]),
            mean_plan_frontdesk=int(row["mean_plan_frontdesk"]),
            upper_plan_clinicians=int(row["upper_plan_clinicians"]),
            upper_plan_nurses=int(row["upper_plan_nurses"]),
            upper_plan_frontdesk=int(row["upper_plan_frontdesk"]),
        )
        for _, row in frame.iterrows()
    ]


@app.get("/v2/hybrid-monitoring", response_model=list[HybridMonitoringPoint])
def v2_hybrid_monitoring(response: Response) -> list[HybridMonitoringPoint]:
    """Return descriptive switch-use monitoring for the latest role-specific run."""
    _set_v2_contract_header(response)
    frame = _load_role_latest("monitoring")
    return [HybridMonitoringPoint(**row.to_dict()) for _, row in frame.iterrows()]


@app.post("/scenario/marketing", response_model=MarketingScenarioResponse)
def marketing_scenario(request: MarketingScenarioRequest) -> MarketingScenarioResponse:
    """Estimate forecast impact of scaling planned marketing spend.

    Applies a documented log-elasticity assumption to the latest legacy
    baseline forecasts. This remains a model-based what-if, not a causal claim.
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
