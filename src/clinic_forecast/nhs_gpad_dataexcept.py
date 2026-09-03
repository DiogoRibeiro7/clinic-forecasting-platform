"""Structured DataExcept boundary for operational NHS GPAD workflows."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn
from zipfile import BadZipFile

from dataexcept import (
    DataLoadingError,
    DataValidationError,
    MissingDataError,
    SchemaMismatchError,
)

from clinic_forecast.nhs_gpad import GPADQualityResult, run_gpad_quality_gate
from clinic_forecast.nhs_gpad_benchmark import (
    NHSGPADBenchmarkResult,
    run_confirmatory_benchmark,
)
from clinic_forecast.nhs_gpad_calendar import (
    GPADCalendarSupportResult,
    run_gpad_calendar_support_audit,
)


def _raise_structured_data_error(exc: ValueError) -> NoReturn:
    """Translate a proven GPAD data failure into the DataExcept hierarchy."""
    message = str(exc)
    lowered = message.casefold()
    if "schema" in lowered or "semantic fields" in lowered or "explicit aliases" in lowered:
        raise SchemaMismatchError(
            expected="frozen NHS GPAD schema contract",
            found=message,
        ) from exc
    if message.startswith("No ") or "contains no csv" in lowered or "is missing" in lowered:
        raise MissingDataError("nhs_gpad_source", message=message) from exc
    raise DataValidationError("nhs_gpad", message, message=message) from exc


def run_gpad_quality_gate_structured(
    archive_path: str | Path,
    config_path: str | Path,
    *,
    retrieval_timestamp_utc: str,
) -> GPADQualityResult:
    """Run the GPAD quality gate with structured operational exceptions."""
    try:
        return run_gpad_quality_gate(
            archive_path,
            config_path,
            retrieval_timestamp_utc=retrieval_timestamp_utc,
        )
    except (OSError, BadZipFile) as exc:
        raise DataLoadingError(str(archive_path), exc) from exc
    except ValueError as exc:
        _raise_structured_data_error(exc)


def run_gpad_calendar_support_audit_structured(
    archive_path: str | Path,
    config_path: str | Path,
) -> GPADCalendarSupportResult:
    """Run the calendar-support audit with structured operational exceptions."""
    try:
        return run_gpad_calendar_support_audit(archive_path, config_path)
    except (OSError, BadZipFile) as exc:
        raise DataLoadingError(str(archive_path), exc) from exc
    except ValueError as exc:
        _raise_structured_data_error(exc)


def run_confirmatory_benchmark_structured(
    archive_path: str | Path,
    source_config_path: str | Path,
    panel_policy_path: str | Path,
    *,
    retrieval_timestamp_utc: str,
) -> NHSGPADBenchmarkResult:
    """Run the frozen benchmark with structured data-boundary exceptions."""
    try:
        return run_confirmatory_benchmark(
            archive_path,
            source_config_path,
            panel_policy_path,
            retrieval_timestamp_utc=retrieval_timestamp_utc,
        )
    except (OSError, BadZipFile) as exc:
        raise DataLoadingError(str(archive_path), exc) from exc
    except ValueError as exc:
        _raise_structured_data_error(exc)


__all__ = [
    "run_confirmatory_benchmark_structured",
    "run_gpad_calendar_support_audit_structured",
    "run_gpad_quality_gate_structured",
]
