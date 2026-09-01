"""Calendar-support audit for the frozen NHS England GPAD archive."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast
from zipfile import ZipFile

import pandas as pd

from clinic_forecast.nhs_gpad import (
    build_gpad_status_map,
    canonicalize_gpad_status,
    config_string_list,
    load_gpad_config,
    parse_gpad_dates,
    parse_nonnegative_integer_counts,
    read_gpad_csv_member,
    resolve_schema,
    sha256_file,
)

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


def _load_coverage(archive: ZipFile, encoding: str) -> pd.DataFrame:
    if COVERAGE_FILE not in archive.namelist():
        raise ValueError(f"Frozen GPAD archive is missing {COVERAGE_FILE}.")
    frame = read_gpad_csv_member(archive, COVERAGE_FILE, encoding)
    missing = set(COVERAGE_COLUMNS.values()).difference(frame.columns)
    if missing:
        raise ValueError(f"GPAD coverage file missing columns: {sorted(missing)}")

    output = pd.DataFrame(
        {semantic: frame[column] for semantic, column in COVERAGE_COLUMNS.items()}
    )
    output["sub_icb_code"] = output["sub_icb_code"].astype("string").str.strip()
    output["appointment_month"] = _parse_month(output["appointment_month"])
    for column in (
        "included_practices",
        "open_practices",
        "included_patients",
        "open_patients",
    ):
        output[column] = parse_nonnegative_integer_counts(
            output[column],
            field_name=f"coverage:{column}",
        )

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
    *,
    encoding: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, int, dict[str, str]]:
    date_formats = config_string_list(config, "date_formats")
    status_mapping = build_gpad_status_map(config)
    parts: list[pd.DataFrame] = []
    zero_count_rows = 0
    daily_names: dict[str, str] = {}
    schema_failures: list[str] = []

    for member in sorted(archive.namelist()):
        if not member.casefold().endswith(".csv") or member == COVERAGE_FILE:
            continue
        frame = read_gpad_csv_member(archive, member, encoding)
        columns = [str(column) for column in frame.columns]
        try:
            resolved = resolve_schema(columns, config)
        except ValueError as exc:
            schema_failures.append(f"{member}: {exc}")
            continue

        dates = parse_gpad_dates(frame[resolved["appointment_date"]], date_formats)
        counts = parse_nonnegative_integer_counts(
            frame[resolved["count_of_appointments"]],
            field_name=f"{member}:count_of_appointments",
        )

        raw_status = frame[resolved["appointment_status"]].astype("string")
        canonical = raw_status.map(
            lambda value: canonicalize_gpad_status(value, status_mapping)
        )
        if (canonical == "unmapped").any():
            values = sorted(raw_status[canonical == "unmapped"].dropna().astype(str).unique())
            raise ValueError(f"Unmapped GPAD status values in {member}: {values}")

        geo_code = frame[resolved["sub_icb_code"]].astype("string").str.strip()
        geo_name = frame[resolved["sub_icb_name"]].astype("string").str.strip()
        part = pd.DataFrame(
            {
                "sub_icb_code": geo_code,
                "sub_icb_name": geo_name,
                "date": dates,
                "status": canonical,
                "appointments": counts,
            }
        )
        part = part[(part["date"] >= start) & (part["date"] <= end)].copy()
        zero_count_rows += int((part["appointments"] == 0).sum())
        parts.append(part)

        for code, name in (
            part[["sub_icb_code", "sub_icb_name"]]
            .drop_duplicates()
            .itertuples(index=False, name=None)
        ):
            existing = daily_names.get(str(code))
            if existing is not None and existing != str(name):
                raise ValueError(
                    f"Conflicting GPAD sub-ICB names for {code}: {existing!r} vs {name!r}."
                )
            daily_names[str(code)] = str(name)

    if schema_failures:
        detail = " | ".join(schema_failures[:10])
        raise ValueError(f"GPAD daily schema failures detected: {detail}")
    if not parts:
        raise ValueError("No daily GPAD files matched the frozen schema.")

    raw = pd.concat(parts, ignore_index=True)
    if raw.empty:
        raise ValueError("No GPAD daily rows fall inside the frozen source window.")

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
    return daily, zero_count_rows, daily_names


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
    expected_months = pd.period_range(start=start, end=end, freq="M").nunique()
    encoding = str(config.get("csv_encoding", "utf-8-sig"))

    with ZipFile(archive_path) as archive:
        coverage = _load_coverage(archive, encoding)
        daily, zero_count_rows, daily_names = _load_daily_support(
            archive,
            config,
            encoding=encoding,
            start=start,
            end=end,
        )

    coverage_window = coverage[
        (coverage["appointment_month"] >= start.to_period("M").to_timestamp())
        & (coverage["appointment_month"] <= end.to_period("M").to_timestamp())
    ].copy()
    coverage_codes = sorted(coverage_window["sub_icb_code"].dropna().astype(str).unique())
    if not coverage_codes:
        raise ValueError("No coverage geographies fall inside the frozen source window.")

    daily_codes = set(daily["sub_icb_code"].dropna().astype(str).unique())
    unexpected_daily_codes = sorted(daily_codes.difference(coverage_codes))
    if unexpected_daily_codes:
        raise ValueError(
            "Daily GPAD contains sub-ICBs absent from the coverage table: "
            f"{unexpected_daily_codes}"
        )

    geographies = pd.DataFrame({"sub_icb_code": coverage_codes})
    geographies["sub_icb_name"] = geographies["sub_icb_code"].map(daily_names)

    full_grid = geographies.merge(pd.DataFrame({"date": calendar}), how="cross")
    full_grid["appointment_month"] = full_grid["date"].dt.to_period("M").dt.to_timestamp()
    full_grid = full_grid.merge(
        daily,
        on=["sub_icb_code", "sub_icb_name", "date"],
        how="left",
        validate="one_to_one",
    )
    full_grid = full_grid.merge(
        coverage_window,
        on=["sub_icb_code", "appointment_month"],
        how="left",
        validate="many_to_one",
    )
    full_grid["source_day_present"] = full_grid["published_rows"].notna()
    full_grid["attended_row_present"] = (
        full_grid["attended_row_present"].astype("boolean").fillna(False).astype(bool)
    )
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

    complete_months = coverage_window[coverage_window["complete_coverage"]]
    complete_all = (
        coverage_window.groupby("sub_icb_code", observed=True)["complete_coverage"]
        .agg([("months", "size"), ("all_complete", "all")])
        .reset_index()
    )
    geographies_complete_all_months = int(
        (
            (complete_all["months"] == expected_months)
            & complete_all["all_complete"]
        ).sum()
    )

    complete_mask = full_grid["complete_coverage"].fillna(False)
    summary: dict[str, object] = {
        "archive_sha256": observed_sha,
        "geographies": len(geographies),
        "calendar_days": len(calendar),
        "calendar_grid_rows": len(full_grid),
        "coverage_rows": len(coverage_window),
        "expected_months": expected_months,
        "complete_coverage_months": int(complete_months.shape[0]),
        "coverage_months_total": int(coverage_window.shape[0]),
        "geographies_complete_all_months": geographies_complete_all_months,
        "practice_coverage_ratio_min": float(coverage_window["practice_coverage_ratio"].min()),
        "practice_coverage_ratio_median": float(
            coverage_window["practice_coverage_ratio"].median()
        ),
        "patient_coverage_ratio_min": float(coverage_window["patient_coverage_ratio"].min()),
        "patient_coverage_ratio_median": float(
            coverage_window["patient_coverage_ratio"].median()
        ),
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
        coverage_monthly=coverage_window,
        calendar_support=full_grid,
        summary=summary,
    )


__all__ = [
    "GPADCalendarSupportResult",
    "run_gpad_calendar_support_audit",
]
