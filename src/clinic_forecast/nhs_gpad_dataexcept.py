"""Structured DataExcept boundary for operational NHS GPAD workflows."""

from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile

from dataexcept import (
    DataExceptError,
    DataLoadingError,
    DataValidationError,
    MissingDataError,
    SchemaMismatchError,
)
from pandas.errors import EmptyDataError, ParserError

from clinic_forecast.nhs_gpad import GPADQualityResult, run_gpad_quality_gate
from clinic_forecast.nhs_gpad_benchmark import (
    NHSGPADBenchmarkResult,
    run_confirmatory_benchmark,
)
from clinic_forecast.nhs_gpad_calendar import (
    GPADCalendarSupportResult,
    run_gpad_calendar_support_audit,
)

_SCHEMA_MARKERS = (
    "required gpad semantic fields not resolved",
    "multiple explicit aliases present for one field",
    "gpad daily schema failures detected",
    "gpad coverage file missing columns",
)

_VALIDATION_MARKERS = (
    "gpad dates could not be parsed deterministically",
    "gpad coverage months could not be parsed deterministically",
    "missing values in gpad count field",
    "exceeds int64 range",
    "invalid numeric value in gpad count field",
    "non-finite value in gpad count field",
    "non-integral values in gpad count field",
    "negative values in gpad count field",
    "gpad archive bytes changed at the frozen source url",
    "duplicate sub-icb/day semantic keys remain",
    "duplicate sub-icb/month rows in gpad coverage file",
    "included practice count exceeds open practice count",
    "included patient count exceeds open patient count",
    "unmapped gpad status values",
    "conflicting gpad sub-icb names",
    "calendar-support audit requires the locked gpad archive bytes",
    "daily gpad contains sub-icbs absent from the coverage table",
    "geography-day rows; got",
    "calendar support is missing required columns",
    "frozen eligible sub-icb codes contain duplicates",
    "calendar-support geography set does not match",
    "duplicate sub-icb/day rows in frozen calendar support",
    "frozen confirmatory panel contains an incomplete-coverage month",
    "frozen calendar_days does not match",
    "frozen panel row count mismatch",
    "every eligible sub-icb must have the complete frozen calendar",
    "frozen support count mismatch",
    "negative attended appointments in frozen panel",
    "test panel is incomplete",
)

_MISSING_SOURCE_MARKERS = (
    "official gpad archive contains no csv files",
    "no gpad daily csv matched the explicit schema map",
    "no recognized gpad rows fall inside the frozen source window",
    "frozen gpad archive is missing appointments_gp_coverage.csv",
    "no daily gpad files matched the frozen schema",
    "no gpad daily rows fall inside the frozen source window",
    "no coverage geographies fall inside the frozen source window",
)


def _structured_data_error(exc: ValueError) -> DataExceptError | None:
    """Classify only known operational GPAD data failures.

    Unknown ``ValueError`` instances are deliberately not translated. This
    keeps malformed configuration and ordinary programming errors native.
    """
    message = str(exc)
    lowered = message.casefold()

    if any(marker in lowered for marker in _SCHEMA_MARKERS):
        return SchemaMismatchError(
            expected="frozen NHS GPAD schema contract",
            found=message,
        )

    if "required primary-target status 'attended' was not identified" in lowered:
        return MissingDataError("attended", message=message)
    if "has an empty train or test frame" in lowered:
        return MissingDataError("benchmark_window", message=message)
    if "contains missing actuals or forecasts" in lowered:
        return MissingDataError("benchmark_actual_or_forecast", message=message)
    if any(marker in lowered for marker in _MISSING_SOURCE_MARKERS):
        return MissingDataError("nhs_gpad_source", message=message)

    if any(marker in lowered for marker in _VALIDATION_MARKERS):
        return DataValidationError("nhs_gpad", message, message=message)

    return None


def _is_config_io_error(exc: OSError, config_paths: tuple[str | Path, ...]) -> bool:
    """Return whether an I/O failure came from a configuration path."""
    if exc.filename is None:
        return False
    error_path = Path(str(exc.filename))
    return any(error_path == Path(path) for path in config_paths)


def _raise_loading_error(archive_path: str | Path, exc: Exception) -> None:
    raise DataLoadingError(str(archive_path), exc) from exc


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
    except OSError as exc:
        if _is_config_io_error(exc, (config_path,)):
            raise
        _raise_loading_error(archive_path, exc)
    except (BadZipFile, UnicodeError, ParserError, EmptyDataError) as exc:
        _raise_loading_error(archive_path, exc)
    except ValueError as exc:
        structured = _structured_data_error(exc)
        if structured is None:
            raise
        raise structured from exc


def run_gpad_calendar_support_audit_structured(
    archive_path: str | Path,
    config_path: str | Path,
) -> GPADCalendarSupportResult:
    """Run the calendar-support audit with structured operational exceptions."""
    try:
        return run_gpad_calendar_support_audit(archive_path, config_path)
    except OSError as exc:
        if _is_config_io_error(exc, (config_path,)):
            raise
        _raise_loading_error(archive_path, exc)
    except (BadZipFile, UnicodeError, ParserError, EmptyDataError) as exc:
        _raise_loading_error(archive_path, exc)
    except ValueError as exc:
        structured = _structured_data_error(exc)
        if structured is None:
            raise
        raise structured from exc


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
    except OSError as exc:
        if _is_config_io_error(exc, (source_config_path, panel_policy_path)):
            raise
        _raise_loading_error(archive_path, exc)
    except (BadZipFile, UnicodeError, ParserError, EmptyDataError) as exc:
        _raise_loading_error(archive_path, exc)
    except ValueError as exc:
        structured = _structured_data_error(exc)
        if structured is None:
            raise
        raise structured from exc


__all__ = [
    "run_confirmatory_benchmark_structured",
    "run_gpad_calendar_support_audit_structured",
    "run_gpad_quality_gate_structured",
]
