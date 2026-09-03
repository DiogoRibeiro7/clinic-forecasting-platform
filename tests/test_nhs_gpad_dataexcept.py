from __future__ import annotations

from pathlib import Path

import pytest
from dataexcept import DataLoadingError, DataValidationError, MissingDataError, SchemaMismatchError

import clinic_forecast.nhs_gpad_dataexcept as boundary


def test_quality_boundary_wraps_loading_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("missing archive")

    monkeypatch.setattr(boundary, "run_gpad_quality_gate", fail)
    with pytest.raises(DataLoadingError) as error:
        boundary.run_gpad_quality_gate_structured(
            Path("missing.zip"),
            Path("config.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )
    assert error.value.source == "missing.zip"
    assert isinstance(error.value.original, FileNotFoundError)


def test_quality_boundary_classifies_schema_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    message = "Required GPAD semantic fields not resolved: ['date']"

    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError(message)

    monkeypatch.setattr(boundary, "run_gpad_quality_gate", fail)
    with pytest.raises(SchemaMismatchError) as error:
        boundary.run_gpad_quality_gate_structured(
            Path("archive.zip"),
            Path("config.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )
    assert error.value.expected == "frozen NHS GPAD schema contract"
    assert error.value.found == message


def test_calendar_boundary_classifies_coverage_schema_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = "GPAD coverage file missing columns: ['Included Practices']"

    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError(message)

    monkeypatch.setattr(boundary, "run_gpad_calendar_support_audit", fail)
    with pytest.raises(SchemaMismatchError) as error:
        boundary.run_gpad_calendar_support_audit_structured(
            Path("archive.zip"), Path("config.json")
        )
    assert error.value.found == message


def test_calendar_boundary_classifies_missing_source_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = "No GPAD daily rows fall inside the frozen source window."

    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError(message)

    monkeypatch.setattr(boundary, "run_gpad_calendar_support_audit", fail)
    with pytest.raises(MissingDataError) as error:
        boundary.run_gpad_calendar_support_audit_structured(
            Path("archive.zip"), Path("config.json")
        )
    assert error.value.feature == "nhs_gpad_source"


def test_quality_boundary_classifies_missing_attended_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = "Required primary-target status 'attended' was not identified."

    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError(message)

    monkeypatch.setattr(boundary, "run_gpad_quality_gate", fail)
    with pytest.raises(MissingDataError) as error:
        boundary.run_gpad_quality_gate_structured(
            Path("archive.zip"),
            Path("config.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )
    assert error.value.feature == "attended"


def test_benchmark_boundary_classifies_empty_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError("Origin 4 has an empty train or test frame.")

    monkeypatch.setattr(boundary, "run_confirmatory_benchmark", fail)
    with pytest.raises(MissingDataError) as error:
        boundary.run_confirmatory_benchmark_structured(
            Path("archive.zip"),
            Path("config.json"),
            Path("policy.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )
    assert error.value.feature == "benchmark_window"


def test_benchmark_boundary_classifies_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = "Frozen panel row count mismatch: expected=10, observed=9."

    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError(message)

    monkeypatch.setattr(boundary, "run_confirmatory_benchmark", fail)
    with pytest.raises(DataValidationError) as error:
        boundary.run_confirmatory_benchmark_structured(
            Path("archive.zip"),
            Path("config.json"),
            Path("policy.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )
    assert error.value.field == "nhs_gpad"
    assert error.value.value == message


def test_benchmark_missing_columns_are_validation_not_missing_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = "Calendar support is missing required columns: ['complete_coverage']"

    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError(message)

    monkeypatch.setattr(boundary, "run_confirmatory_benchmark", fail)
    with pytest.raises(DataValidationError):
        boundary.run_confirmatory_benchmark_structured(
            Path("archive.zip"),
            Path("config.json"),
            Path("policy.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )


def test_unknown_value_error_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise ValueError("Malformed internal configuration value")

    monkeypatch.setattr(boundary, "run_gpad_quality_gate", fail)
    with pytest.raises(ValueError, match="Malformed internal configuration value"):
        boundary.run_gpad_quality_gate_structured(
            Path("archive.zip"),
            Path("config.json"),
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )


def test_config_file_io_error_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = Path("config.json")

    def fail(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError(2, "No such file", str(config_path))

    monkeypatch.setattr(boundary, "run_gpad_quality_gate", fail)
    with pytest.raises(FileNotFoundError):
        boundary.run_gpad_quality_gate_structured(
            Path("archive.zip"),
            config_path,
            retrieval_timestamp_utc="2026-09-03T00:00:00Z",
        )
