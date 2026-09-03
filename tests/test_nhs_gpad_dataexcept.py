from __future__ import annotations

from pathlib import Path

import pytest
from dataexcept import DataLoadingError, DataValidationError, MissingDataError, SchemaMismatchError

import clinic_forecast.nhs_gpad_dataexcept as boundary


def test_quality_boundary_wraps_loading_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("missing archive")

    monkeypatch.setattr(boundary, "run_gpad_quality_gate", fail)
    with pytest.raises(DataLoadingError):
        boundary.run_gpad_quality_gate_structured(
            Path("missing.zip"),
            Path("config.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )


def test_quality_boundary_classifies_schema_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError("Required GPAD semantic fields not resolved: ['date']")

    monkeypatch.setattr(boundary, "run_gpad_quality_gate", fail)
    with pytest.raises(SchemaMismatchError):
        boundary.run_gpad_quality_gate_structured(
            Path("archive.zip"),
            Path("config.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )


def test_calendar_boundary_classifies_missing_data(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError("No GPAD daily rows fall inside the frozen source window.")

    monkeypatch.setattr(boundary, "run_gpad_calendar_support_audit", fail)
    with pytest.raises(MissingDataError):
        boundary.run_gpad_calendar_support_audit_structured(
            Path("archive.zip"), Path("config.json")
        )


def test_benchmark_boundary_classifies_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError("Frozen panel row count mismatch: expected=10, observed=9.")

    monkeypatch.setattr(boundary, "run_confirmatory_benchmark", fail)
    with pytest.raises(DataValidationError):
        boundary.run_confirmatory_benchmark_structured(
            Path("archive.zip"),
            Path("config.json"),
            Path("policy.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )
