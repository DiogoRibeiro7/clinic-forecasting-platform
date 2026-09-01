"""Calendar-support audit for the frozen NHS England GPAD archive."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast
from zipfile import ZipFile

import pandas as pd

from clinic_forecast.nhs_gpad import load_gpad_config, resolve_schema, sha256_file

COVERAGE_FILE = "APPOINTMENTS_GP_COVERAGE.csv"
COVERAGE_COLUMNS = {
    "sub_icb_code": "SUB_ICB_LOCATION_CODE",
    "appointment_month": "Appointment_Month",
    "included_practices": "Included Practices",
    "open_practices": "Open Practices",
    "included_patients": "Patients registered at included practices",
    "open_patients": "Patients registered at open practices",
}
MONTH_FORMATS = ("%b-%y", "%b%Y", "%Y-%m", "%d%b%Y")


@dataclass(frozen=True)
class GPADCalendarSupportResult:
    """Outputs of the pre-model GPAD calendar-support audit."""

    coverage_monthly: pd.DataFrame
    calendar_support: pd.DataFrame
    summary: dict[str, object]


def _parse_month(values: pd.Series) -> pd.Series:
    text = values.astype("string").str.strip()
    output = pd.Series(pd.NaT, index=text.index, dtype="datetime64[ns]")
    for month_format in MONTH_FORMATS:
        unresolved = output.isna() & text.notna()
        if not unresolved.any():
            break
        parsed = pd.to_datetime(text[unresolved], format=month_format, errors="coerce")
        output.loc[unresolved] = parsed
    if output.isna().any():
        examples = text[output.isna()].dropna().head(10).tolist()
        raise ValueError(
            "GPAD coverage months could not be parsed deterministically; "
            f"examples={examples}"
        )
    return output.dt.to_period("M").dt.to_timestamp()


def _require_list(config: dict[str, object], key: str) -> list[str]:
    raw = config[key]
    if not isinstance(raw, list):
        raise TypeError(f"{key} must be a list.")
    return [str(value) for value in raw]


def _parse_dates(values: pd.Series, formats: list[str]) -> pd.Series:
    text = values.astype("string")
    output = pd.Series(pd.NaT, index=text.index, dtype="datetime64[ns]")
    for date_format in formats:
        unresolved = output.isna() & text.notna()
        if not unresolved.any():
            break
        parsed = pd.to_datetime(text[unresolved], format=date_format, errors="coerce")
        output.loc[unresolved] = parsed
    if output.isna().any():
        examples = text[output.isna()].dropna().head(10).tolist()
        raise ValueError(
            "GPAD daily dates could not be parsed deterministically; "
            f"examples={examples}"
        )
    return output


def _status_map(config: dict[str, object]) -> dict[str, list[str]]:
    raw = config["status_map"]
    if not isinstance(raw, dict):
        raise TypeError("status_map must be a mapping.")
    output: dict[str, list[str]] = {}
    for key, aliases in raw.items():
        if not isinstance(aliases, list):
            raise TypeError(f"status_map aliases for {key!r} must be a list.")
        output[str(key)] = [str(alias).strip().casefold() for alias in aliases]
    return output


def _canonical_status(value: object, mapping: dict[str, list[str]]) -> str:
    normalized = str(value).strip().casefold()
    for canonical, aliases in mapping.items():
        if normalized in aliases:
            return canonical
    return "unmapped"


def _load_coverage(archive: ZipFile) -> pd.DataFrame:
    if COVERAGE_FILE not in archive.namelist():
        raise ValueError(f"Frozen GPAD archive is missing {COVERAGE_FILE}.")
    with archive.open(COVERAGE_FILE) as handle:
        frame = pd.read_csv(handle, low_memory=False)
    missing = set(COVERAGE_COLUMNS.values()).difference(frame.columns)
    if missing:
        raise ValueError(f"GPAD coverage file missing columns: {sorted(missing)}")

    output = pd.DataFrame(
        {
            semantic: frame[column]
            for semantic, column in COVERAGE_COLUMNS.items()
        }
    )
    output["appointment_month"] = _parse_month(output["appointment_month"])
    for column in (
        "included_practices",
        "open_practices",
        "included_patients",
        "open_patients",
    ):
        output[column] = pd.to_numeric(output[column], errors="raise").astype("int64")
        if (output[column] < 0).any():
            raise ValueError(f"Negative values in GPAD coverage column {column}.")

    if output.duplicated(["sub_icb_code", "appointment_month"]).any():
        raise ValueError("Duplicate sub-ICB/month rows in GPAD coverage file.")
    if (output["included_practices"] > output["open_practices"]).any():
        raise ValueError("Included practice count exceeds open practice count.")
    if (output["included_patients"] > output["open_patients"]).any():
        raise ValueError("Included patient count exceeds open patient count.")

    output["practice_coverage_ratio"] = output["included_practices"].div(
        output["open_practices"].where(output["open_practices"] > 0)
    )
    output["patient_coverage_ratio"] = output["included_patients"].div(
        output["open_patients"].where(output["open_patients"] > 0)
    )
    output["complete_practice_coverage"] = (
        output["included_practices"] == output["open_practices"]
    )
    output["complete_patient_coverage"] = (
        output["included_patients"] == output["open_patients"]
    )
    output["complete_coverage"] = (
        output["complete_practice_coverage"] & output["complete_patient_coverage"]
    )
    return output.sort_values(["sub_icb_code", "appointment_month"]).reset_index(drop=True)


def _load_daily_support(
    archive: ZipFile,
    config: dict[str, object],
) -> tuple[pd.DataFrame, int]:
    date_formats = _require_list(config, "date_formats")
    status_mapping = _status_map(config)
    parts: list[pd.DataFrame] = []
    zero_count_rows = 0

    for member in sorted(archive.namelist()):
        if not member.casefold().endswith(".csv") or member == COVERAGE_FILE:
            continue
        with archive.open(member) as handle:
            frame = pd.read_csv(handle, low_memory=False)
        columns = [str(column) for column in frame.columns]
        try:
            resolved = resolve_schema(columns, config)
        except ValueError:
            continue

        dates = _parse_dates(frame[resolved["appointment_date"]], date_formats)
        counts = pd.to_numeric(frame[resolved["count_of_appointments"]], errors="raise")
        if counts.isna().any() or (counts < 0).any():
            raise ValueError(f"Invalid appointment counts in {member}.")
        zero_count_rows += int((counts == 0).sum())

        raw_status = frame[resolved["appointment_status"]].astype("string")
        canonical = raw_status.map(lambda value: _canonical_status(value, status_mapping))
        if (canonical == "unmapped").any():
            values = sorted(raw_status[canonical == "unmapped"].dropna().astype(str).unique())
            raise ValueError(f"Unmapped GPAD status values in {member}: {values}")

        part = pd.DataFrame(
            {
                "sub_icb_code": frame[resolved["sub_icb_code"]].astype("string").str.strip(),
                "sub_icb_name": frame[resolved["sub_icb_name"]].astype("string").str.strip(),
                "date": dates,
                "status": canonical,
                "appointments": counts.astype("int64"),
            }
        )
        parts.append(part)

    if not parts:
        raise ValueError("No daily GPAD files matched the frozen schema.")
    raw = pd.concat(parts, ignore_index=True)

    daily = (
        raw.groupby(["sub_icb_code", "sub_icb_name", "date"], observed=True)
        .agg(
            published_appointments=("appointments", "sum"),
            published_rows=("appointments", "size"),
        )
        .reset_index()
    )
    attended = (
        raw[raw["status"] == "attended"]
        .groupby(["sub_icb_code", "date"], observed=True)["appointments"]
        .agg([("attended_appointments", "sum"), ("attended_rows", "size")])
        .reset_index()
    )
    daily = daily.merge(attended, on=["sub_icb_code", "date"], how="left")
    daily["attended_rows"] = daily["attended_rows"].fillna(0).astype("int64")
    daily["attended_row_present"] = daily["attended_rows"] > 0
    return daily, zero_count_rows


def run_gpad_calendar_support_audit(
    archive_path: str | Path,
    config_path: str | Path,
) -> GPADCalendarSupportResult:
    """Audit sparse daily rows against monthly GPAD publication coverage."""
    archive_path = Path(archive_path)
    config = load_gpad_config(config_path)
    source_raw = config["source"]
    if not isinstance(source_raw, dict):
        raise TypeError("source must be a mapping.")
    source = cast(dict[str, object], source_raw)
    expected_sha = source.get("expected_sha256")
    observed_sha = sha256_file(archive_path)
    if not expected_sha or str(expected_sha) != observed_sha:
        raise ValueError(
            "Calendar-support audit requires the locked GPAD archive bytes: "
            f"expected={expected_sha}, observed={observed_sha}."
        )

    start = pd.Timestamp(str(source["date_start"]))
    end = pd.Timestamp(str(source["date_end"]))
    calendar = pd.date_range(start, end, freq="D")

    with ZipFile(archive_path) as archive:
        coverage = _load_coverage(archive)
        daily, zero_count_rows = _load_daily_support(archive, config)

    geographies = (
        daily[["sub_icb_code", "sub_icb_name"]]
        .drop_duplicates()
        .sort_values("sub_icb_code")
        .reset_index(drop=True)
    )
    full_grid = geographies.merge(
        pd.DataFrame({"date": calendar}),
        how="cross",
    )
    full_grid["appointment_month"] = full_grid["date"].dt.to_period("M").dt.to_timestamp()
    full_grid = full_grid.merge(
        daily,
        on=["sub_icb_code", "sub_icb_name", "date"],
        how="left",
        validate="one_to_one",
    )
    full_grid = full_grid.merge(
        coverage,
        on=["sub_icb_code", "appointment_month"],
        how="left",
        validate="many_to_one",
    )
    full_grid["source_day_present"] = full_grid["published_rows"].notna()
    full_grid["attended_row_present"] = full_grid["attended_row_present"].fillna(False)
    full_grid["source_support_class"] = "no_published_rows"
    full_grid.loc[
        full_grid["source_day_present"] & ~full_grid["attended_row_present"],
        "source_support_class",
    ] = "other_status_only"
    full_grid.loc[
        full_grid["attended_row_present"],
        "source_support_class",
    ] = "attended_present"

    expected_rows = len(geographies) * len(calendar)
    if len(full_grid) != expected_rows:
        raise ValueError(f"Expected {expected_rows} geography-day rows; got {len(full_grid)}.")

    complete_months = coverage[coverage["complete_coverage"]]
    complete_all = (
        coverage.groupby("sub_icb_code", observed=True)["complete_coverage"]
        .agg([("months", "size"), ("all_complete", "all")])
        .reset_index()
    )
    geographies_complete_all_months = int(
        ((complete_all["months"] == 30) & complete_all["all_complete"]).sum()
    )

    complete_mask = full_grid["complete_coverage"].fillna(False)
    summary: dict[str, object] = {
        "archive_sha256": observed_sha,
        "geographies": len(geographies),
        "calendar_days": len(calendar),
        "calendar_grid_rows": len(full_grid),
        "coverage_rows": len(coverage),
        "complete_coverage_months": int(complete_months.shape[0]),
        "coverage_months_total": int(coverage.shape[0]),
        "geographies_complete_all_30_months": geographies_complete_all_months,
        "practice_coverage_ratio_min": float(coverage["practice_coverage_ratio"].min()),
        "practice_coverage_ratio_median": float(coverage["practice_coverage_ratio"].median()),
        "patient_coverage_ratio_min": float(coverage["patient_coverage_ratio"].min()),
        "patient_coverage_ratio_median": float(coverage["patient_coverage_ratio"].median()),
        "source_zero_count_rows": zero_count_rows,
        "days_with_any_published_rows": int(full_grid["source_day_present"].sum()),
        "days_with_no_published_rows": int((~full_grid["source_day_present"]).sum()),
        "days_other_status_only": int(
            (full_grid["source_support_class"] == "other_status_only").sum()
        ),
        "complete_coverage_days_no_published_rows": int(
            (complete_mask & ~full_grid["source_day_present"]).sum()
        ),
        "complete_coverage_days_other_status_only": int(
            (complete_mask & (full_grid["source_support_class"] == "other_status_only")).sum()
        ),
        "complete_coverage_days_attended_present": int(
            (complete_mask & full_grid["attended_row_present"]).sum()
        ),
    }
    return GPADCalendarSupportResult(
        coverage_monthly=coverage,
        calendar_support=full_grid,
        summary=summary,
    )


__all__ = [
    "GPADCalendarSupportResult",
    "run_gpad_calendar_support_audit",
]
