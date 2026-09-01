from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from clinic_forecast.nhs_gpad import resolve_schema, run_gpad_quality_gate


def _config(tmp_path: Path, *, expected_sha256: str | None = None) -> Path:
    config = {
        "source": {
            "publication": "test",
            "publisher": "NHS England",
            "publication_date": "2026-07-30",
            "archive_name": "test.zip",
            "archive_url": "https://example.invalid/test.zip",
            "expected_sha256": expected_sha256,
            "date_start": "2024-01-01",
            "date_end": "2024-01-03",
            "licence": "Open Government Licence v3.0",
            "attribution": "test attribution",
        },
        "csv_encoding": "utf-8-sig",
        "date_formats": ["%Y-%m-%d"],
        "required_fields": {
            "appointment_date": ["Appointment_Date", "APPT_DATE"],
            "appointment_status": ["Appointment_Status", "APPT_STATUS"],
            "count_of_appointments": ["Count_Of_Appointments", "COUNT_OF_APPOINTMENTS"],
            "sub_icb_code": ["SUB_ICB_LOCATION_CODE"],
            "sub_icb_name": ["SUB_ICB_LOCATION_NAME"],
        },
        "optional_fields": {"hcp_type": ["HCP_Type", "HCP_TYPE"]},
        "status_map": {
            "attended": ["attended"],
            "did_not_attend": ["did not attend", "dna"],
            "unknown": ["unknown"],
        },
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def _archive(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    path = tmp_path / "test.zip"
    frame = pd.DataFrame(rows)
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("daily.csv", frame.to_csv(index=False))
        archive.writestr("coverage.csv", "Practice,Coverage\nA,1\n")
    return path


def _rows() -> list[dict[str, object]]:
    return [
        {
            "Appointment_Date": "2024-01-01",
            "Appointment_Status": "Attended",
            "Count_Of_Appointments": 10,
            "SUB_ICB_LOCATION_CODE": "X1",
            "SUB_ICB_LOCATION_NAME": "Alpha",
            "HCP_Type": "GP",
        },
        {
            "Appointment_Date": "2024-01-01",
            "Appointment_Status": "DNA",
            "Count_Of_Appointments": 2,
            "SUB_ICB_LOCATION_CODE": "X1",
            "SUB_ICB_LOCATION_NAME": "Alpha",
            "HCP_Type": "GP",
        },
        {
            "Appointment_Date": "2024-01-02",
            "Appointment_Status": "Mystery",
            "Count_Of_Appointments": 3,
            "SUB_ICB_LOCATION_CODE": "X1",
            "SUB_ICB_LOCATION_NAME": "Alpha",
            "HCP_Type": "GP",
        },
        {
            "Appointment_Date": "2024-01-03",
            "Appointment_Status": "Attended",
            "Count_Of_Appointments": 12,
            "SUB_ICB_LOCATION_CODE": "X1",
            "SUB_ICB_LOCATION_NAME": "Alpha",
            "HCP_Type": "GP",
        },
    ]


def test_resolve_schema_uses_only_explicit_aliases() -> None:
    config = {
        "required_fields": {
            "appointment_date": ["Appointment_Date"],
            "appointment_status": ["Appointment_Status"],
        },
        "optional_fields": {},
    }
    assert resolve_schema(["Appointment_Date", "Appointment_Status"], config) == {
        "appointment_date": "Appointment_Date",
        "appointment_status": "Appointment_Status",
    }
    with pytest.raises(ValueError, match="not resolved"):
        resolve_schema(["appointment date", "Appointment_Status"], config)


def test_quality_gate_inventories_unknown_status_without_treating_it_as_attended(
    tmp_path: Path,
) -> None:
    archive = _archive(tmp_path, _rows())
    result = run_gpad_quality_gate(
        archive,
        _config(tmp_path),
        retrieval_timestamp_utc="2026-08-31T21:00:00Z",
    )
    assert result.quality_summary["recognized_csv_files"] == 1
    assert result.quality_summary["observed_status_values"] == ["Attended", "DNA", "Mystery"]
    assert result.prepared_daily["attended_appointments"].tolist() == [10, 12]
    totals = result.quality_summary["appointments_by_canonical_status"]
    assert totals["unmapped"] == 3


def test_quality_gate_rejects_negative_counts(tmp_path: Path) -> None:
    rows = _rows()
    rows[0]["Count_Of_Appointments"] = -1
    with pytest.raises(ValueError, match="Negative values in GPAD count field"):
        run_gpad_quality_gate(
            _archive(tmp_path, rows),
            _config(tmp_path),
            retrieval_timestamp_utc="2026-08-31T21:00:00Z",
        )


def test_quality_gate_rejects_changed_frozen_bytes(tmp_path: Path) -> None:
    archive = _archive(tmp_path, _rows())
    with pytest.raises(ValueError, match="archive bytes changed"):
        run_gpad_quality_gate(
            archive,
            _config(tmp_path, expected_sha256="0" * 64),
            retrieval_timestamp_utc="2026-08-31T21:00:00Z",
        )
