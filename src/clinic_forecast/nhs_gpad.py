"""Adapter and data-quality gate for NHS England GPAD daily-count archives."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import TextIOWrapper
from pathlib import Path
from typing import cast
from zipfile import ZipFile

import pandas as pd


@dataclass(frozen=True)
class GPADQualityResult:
    source_manifest: dict[str, object]
    schema_inventory: pd.DataFrame
    data_quality: pd.DataFrame
    quality_summary: dict[str, object]
    prepared_daily: pd.DataFrame


def load_gpad_config(path: str | Path) -> dict[str, object]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("GPAD configuration must be a mapping.")
    return cast(dict[str, object], loaded)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config_string_list(config: dict[str, object], key: str) -> list[str]:
    """Read a required list-valued GPAD config entry as strings."""
    raw = config[key]
    if not isinstance(raw, list):
        raise TypeError(f"{key} must be a list.")
    return [str(value) for value in raw]


def build_gpad_status_map(config: dict[str, object]) -> dict[str, list[str]]:
    """Build the canonical status map with normalized explicit aliases."""
    raw = config["status_map"]
    if not isinstance(raw, dict):
        raise TypeError("status_map must be a mapping.")
    output: dict[str, list[str]] = {}
    for key, aliases in raw.items():
        if not isinstance(aliases, list):
            raise TypeError(f"status_map aliases for {key!r} must be a list.")
        output[str(key)] = [str(alias).strip().casefold() for alias in aliases]
    return output


def _resolve_alias(columns: list[str], aliases: list[str]) -> str | None:
    matches = [alias for alias in aliases if alias in columns]
    if len(matches) > 1:
        raise ValueError(f"Multiple explicit aliases present for one field: {matches}")
    return matches[0] if matches else None


def resolve_schema(columns: list[str], config: dict[str, object]) -> dict[str, str]:
    required = config["required_fields"]
    optional = config["optional_fields"]
    if not isinstance(required, dict) or not isinstance(optional, dict):
        raise TypeError(
            "Schema configuration must contain required_fields and optional_fields maps."
        )

    resolved: dict[str, str] = {}
    missing: list[str] = []
    for semantic, aliases_raw in required.items():
        aliases = [str(value) for value in aliases_raw]
        match = _resolve_alias(columns, aliases)
        if match is None:
            missing.append(str(semantic))
        else:
            resolved[str(semantic)] = match
    if missing:
        raise ValueError(
            "Required GPAD semantic fields not resolved: "
            f"{missing}; columns={columns}"
        )

    for semantic, aliases_raw in optional.items():
        aliases = [str(value) for value in aliases_raw]
        match = _resolve_alias(columns, aliases)
        if match is not None:
            resolved[str(semantic)] = match
    return resolved


def parse_gpad_dates(values: pd.Series, formats: list[str]) -> pd.Series:
    """Parse GPAD dates using only the explicitly allowed date formats."""
    output = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    text = values.astype("string")
    for date_format in formats:
        unresolved = output.isna() & text.notna()
        if not unresolved.any():
            break
        parsed = pd.to_datetime(text[unresolved], format=date_format, errors="coerce")
        output.loc[unresolved] = parsed
    if output.isna().any():
        examples = text[output.isna()].dropna().head(10).tolist()
        raise ValueError(f"GPAD dates could not be parsed deterministically; examples={examples}")
    return output


def canonicalize_gpad_status(value: object, status_map: dict[str, list[str]]) -> str:
    """Map one published appointment status through the explicit canonical aliases."""
    normalized = str(value).strip().casefold()
    for canonical, aliases in status_map.items():
        if normalized in aliases:
            return canonical
    return "unmapped"


def parse_nonnegative_integer_counts(values: pd.Series, *, field_name: str) -> pd.Series:
    """Parse source count lexemes exactly with a vectorized integer fast path."""
    maximum = 2**63 - 1
    maximum_text = str(maximum)
    text = values.astype("string").str.strip()
    missing = text.isna() | text.eq("")
    if missing.any():
        raise ValueError(f"Missing values in GPAD count field {field_name}.")

    parsed = pd.Series(0, index=values.index, dtype="int64")
    plain_integer = text.str.fullmatch(r"\+?\d+")
    if plain_integer.any():
        canonical = text[plain_integer].str.replace(r"^\+", "", regex=True).str.lstrip("0")
        canonical = canonical.mask(canonical.eq(""), "0")
        too_long = canonical.str.len() > len(maximum_text)
        too_large_at_limit = (canonical.str.len() == len(maximum_text)) & (
            canonical > maximum_text
        )
        if (too_long | too_large_at_limit).any():
            raise ValueError(f"GPAD count field {field_name} exceeds int64 range.")
        parsed.loc[canonical.index] = canonical.astype("int64")

    maximum_decimal = Decimal(maximum)
    for index, token in text[~plain_integer].items():
        try:
            decimal_value = Decimal(str(token))
        except InvalidOperation as exc:
            raise ValueError(
                f"Invalid numeric value in GPAD count field {field_name}: {token!r}."
            ) from exc
        if not decimal_value.is_finite():
            raise ValueError(
                f"Non-finite value in GPAD count field {field_name}: {token!r}."
            )
        if decimal_value != decimal_value.to_integral_value():
            raise ValueError(
                f"Non-integral values in GPAD count field {field_name}; example={token!r}."
            )
        if decimal_value < 0:
            raise ValueError(f"Negative values in GPAD count field {field_name}.")
        if decimal_value > maximum_decimal:
            raise ValueError(f"GPAD count field {field_name} exceeds int64 range.")
        parsed.at[index] = int(decimal_value)
    return parsed


def read_gpad_csv_member(archive: ZipFile, member: str, encoding: str) -> pd.DataFrame:
    """Read one archive CSV while preserving source lexemes for validation."""
    with archive.open(member) as raw:
        wrapper = TextIOWrapper(raw, encoding=encoding, newline="")
        return pd.read_csv(wrapper, low_memory=False, dtype="string")


def run_gpad_quality_gate(
    archive_path: str | Path,
    config_path: str | Path,
    *,
    retrieval_timestamp_utc: str,
) -> GPADQualityResult:
    archive_path = Path(archive_path)
    config = load_gpad_config(config_path)
    source = config["source"]
    if not isinstance(source, dict):
        raise TypeError("GPAD source configuration must be a mapping.")

    observed_sha256 = sha256_file(archive_path)
    expected_sha256 = source.get("expected_sha256")
    if expected_sha256 and str(expected_sha256) != observed_sha256:
        raise ValueError(
            "GPAD archive bytes changed at the frozen source URL: "
            f"expected={expected_sha256}, observed={observed_sha256}."
        )

    source_manifest: dict[str, object] = {
        **source,
        "retrieval_timestamp_utc": retrieval_timestamp_utc,
        "archive_sha256": observed_sha256,
        "archive_bytes": archive_path.stat().st_size,
    }

    encoding = str(config.get("csv_encoding", "utf-8-sig"))
    formats = config_string_list(config, "date_formats")
    status_map = build_gpad_status_map(config)

    schema_rows: list[dict[str, object]] = []
    quality_rows: list[dict[str, object]] = []
    prepared_parts: list[pd.DataFrame] = []
    observed_statuses: set[str] = set()

    with ZipFile(archive_path) as archive:
        csv_members = sorted(
            member for member in archive.namelist() if member.casefold().endswith(".csv")
        )
        if not csv_members:
            raise ValueError("Official GPAD archive contains no CSV files.")

        for member in csv_members:
            frame = read_gpad_csv_member(archive, member, encoding)
            columns = [str(column) for column in frame.columns]
            resolved: dict[str, str] | None
            error: str | None = None
            try:
                resolved = resolve_schema(columns, config)
            except ValueError as exc:
                resolved = None
                error = str(exc)

            schema_rows.append(
                {
                    "file": member,
                    "rows": len(frame),
                    "columns": json.dumps(columns),
                    "recognized_daily_data": resolved is not None,
                    "resolved_schema": json.dumps(resolved or {}, sort_keys=True),
                    "schema_error": error,
                }
            )
            if resolved is None:
                continue

            dates = parse_gpad_dates(frame[resolved["appointment_date"]], formats)
            counts = parse_nonnegative_integer_counts(
                frame[resolved["count_of_appointments"]],
                field_name=f"{member}:count_of_appointments",
            )

            raw_status = frame[resolved["appointment_status"]].astype("string").fillna("<NA>")
            observed_statuses.update(raw_status.astype(str).unique().tolist())
            canonical = raw_status.map(
                lambda value: canonicalize_gpad_status(value, status_map)
            )

            geo_code = frame[resolved["sub_icb_code"]].astype("string").str.strip()
            geo_name = frame[resolved["sub_icb_name"]].astype("string").str.strip()
            canonical_frame = pd.DataFrame(
                {
                    "source_file": member,
                    "date": dates,
                    "sub_icb_code": geo_code,
                    "sub_icb_name": geo_name,
                    "appointment_status_raw": raw_status,
                    "appointment_status": canonical,
                    "appointments": counts,
                }
            )
            prepared_parts.append(canonical_frame)
            quality_rows.append(
                {
                    "file": member,
                    "rows": len(frame),
                    "date_min": dates.min(),
                    "date_max": dates.max(),
                    "unique_sub_icb": geo_code.nunique(dropna=True),
                    "negative_count_rows": 0,
                    "unmapped_status_rows": int((canonical == "unmapped").sum()),
                    "unmapped_status_fraction": float((canonical == "unmapped").mean()),
                }
            )

    if not prepared_parts:
        raise ValueError("No GPAD daily CSV matched the explicit schema map.")

    raw = pd.concat(prepared_parts, ignore_index=True)
    start = pd.Timestamp(str(source["date_start"]))
    end = pd.Timestamp(str(source["date_end"]))
    raw = raw[(raw["date"] >= start) & (raw["date"] <= end)].copy()
    if raw.empty:
        raise ValueError("No recognized GPAD rows fall inside the frozen source window.")

    attended = raw[raw["appointment_status"] == "attended"].copy()
    if attended.empty:
        raise ValueError(
            "Required primary-target status 'attended' was not identified. "
            f"Observed status values={sorted(observed_statuses)}"
        )

    prepared_daily = (
        attended.groupby(["sub_icb_code", "sub_icb_name", "date"], observed=True)["appointments"]
        .sum()
        .rename("attended_appointments")
        .reset_index()
        .sort_values(["sub_icb_code", "date"])
        .reset_index(drop=True)
    )
    duplicate_keys = int(
        prepared_daily.duplicated(["sub_icb_code", "date"], keep=False).sum()
    )
    if duplicate_keys:
        raise ValueError(f"Duplicate sub-ICB/day semantic keys remain: {duplicate_keys} rows.")

    full_calendar = pd.date_range(start, end, freq="D")
    geography_rows: list[dict[str, object]] = []
    for code, group in prepared_daily.groupby("sub_icb_code", observed=True):
        dates = pd.DatetimeIndex(group["date"].unique())
        missing = full_calendar.difference(dates)
        geography_rows.append(
            {
                "file": "__geography__",
                "rows": len(group),
                "date_min": dates.min() if len(dates) else pd.NaT,
                "date_max": dates.max() if len(dates) else pd.NaT,
                "unique_sub_icb": 1,
                "negative_count_rows": 0,
                "unmapped_status_rows": 0,
                "unmapped_status_fraction": 0.0,
                "sub_icb_code": str(code),
                "missing_calendar_days": len(missing),
            }
        )
    data_quality = pd.concat(
        [pd.DataFrame(quality_rows), pd.DataFrame(geography_rows)],
        ignore_index=True,
        sort=False,
    )

    totals = raw.groupby("appointment_status", observed=True)["appointments"].sum().to_dict()
    quality_summary: dict[str, object] = {
        "recognized_csv_files": len(prepared_parts),
        "inventory_csv_files": len(schema_rows),
        "prepared_rows": len(prepared_daily),
        "date_min": prepared_daily["date"].min().date().isoformat(),
        "date_max": prepared_daily["date"].max().date().isoformat(),
        "unique_sub_icb": int(prepared_daily["sub_icb_code"].nunique()),
        "duplicate_semantic_key_rows": duplicate_keys,
        "negative_count_rows": 0,
        "observed_status_values": sorted(observed_statuses),
        "appointments_by_canonical_status": totals,
        "unmapped_status_appointment_fraction": float(
            totals.get("unmapped", 0) / max(1, sum(int(value) for value in totals.values()))
        ),
        "geographies_with_full_calendar": int(
            sum(row["missing_calendar_days"] == 0 for row in geography_rows)
        ),
        "geographies_total": len(geography_rows),
    }
    return GPADQualityResult(
        source_manifest=source_manifest,
        schema_inventory=pd.DataFrame(schema_rows),
        data_quality=data_quality,
        quality_summary=quality_summary,
        prepared_daily=prepared_daily,
    )


__all__ = [
    "GPADQualityResult",
    "build_gpad_status_map",
    "canonicalize_gpad_status",
    "config_string_list",
    "load_gpad_config",
    "parse_gpad_dates",
    "parse_nonnegative_integer_counts",
    "read_gpad_csv_member",
    "resolve_schema",
    "run_gpad_quality_gate",
    "sha256_file",
]
