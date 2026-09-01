from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from clinic_forecast.nhs_gpad import sha256_file
from clinic_forecast.nhs_gpad_calendar import run_gpad_calendar_support_audit


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    archive_path = tmp_path / "gpad.zip"
    coverage = pd.DataFrame(
        {
            "SUB_ICB_LOCATION_CODE": ["A", "A", "B", "B"],
            "ICB_ONS_CODE": ["X", "X", "X", "X"],
            "REGION_CODE": ["R", "R", "R", "R"],
            "Appointment_Month": ["Jan-24", "Feb-24", "Jan-24", "Feb-24"],
            "Included Practices": [2, 1, 1, 1],
            "Open Practices": [2, 2, 1, 1],
            "Patients registered at included practices": [100, 50, 80, 80],
            "Patients registered at open practices": [100, 100, 80, 80],
        }
    )
    daily = pd.DataFrame(
        {
            "SUB_ICB_LOCATION_CODE": ["A", "A", "A"],
            "SUB_ICB_LOCATION_NAME": ["Area A", "Area A", "Area A"],
            "Appointment_Date": ["01JAN2024", "01JAN2024", "02JAN2024"],
            "APPT_STATUS": ["Attended", "DNA", "DNA"],
            "COUNT_OF_APPOINTMENTS": [10, 1, 0],
        }
    )
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("APPOINTMENTS_GP_COVERAGE.csv", coverage.to_csv(index=False))
        archive.writestr("SUB_ICB_LOCATION_CSV_Jan_24.csv", daily.to_csv(index=False))

    config = {
        "source": {
            "expected_sha256": None,
            "date_start": "2024-01-01",
            "date_end": "2024-02-29",
        },
        "csv_encoding": "utf-8-sig",
        "date_formats": ["%d%b%Y"],
        "required_fields": {
            "appointment_date": ["Appointment_Date"],
            "appointment_status": ["APPT_STATUS"],
            "count_of_appointments": ["COUNT_OF_APPOINTMENTS"],
            "sub_icb_code": ["SUB_ICB_LOCATION_CODE"],
            "sub_icb_name": ["SUB_ICB_LOCATION_NAME"],
        },
        "optional_fields": {},
        "status_map": {
            "attended": ["attended"],
            "did_not_attend": ["dna"],
            "unknown": ["unknown"],
        },
    }
    config["source"]["expected_sha256"] = sha256_file(archive_path)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return archive_path, config_path


def _relock_config(archive_path: Path, config_path: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["source"]["expected_sha256"] = sha256_file(archive_path)
    config_path.write_text(json.dumps(config), encoding="utf-8")


def test_calendar_support_distinguishes_source_support_classes(tmp_path: Path) -> None:
    archive_path, config_path = _write_fixture(tmp_path)
    result = run_gpad_calendar_support_audit(archive_path, config_path)

    area_a = result.calendar_support[result.calendar_support["sub_icb_code"] == "A"].set_index(
        "date"
    )
    assert area_a.loc[pd.Timestamp("2024-01-01"), "source_support_class"] == "attended_present"
    assert area_a.loc[pd.Timestamp("2024-01-02"), "source_support_class"] == "other_status_only"
    assert area_a.loc[pd.Timestamp("2024-01-03"), "source_support_class"] == "no_published_rows"

    area_b = result.calendar_support[result.calendar_support["sub_icb_code"] == "B"]
    assert len(area_b) == 60
    assert set(area_b["source_support_class"]) == {"no_published_rows"}


def test_calendar_support_reports_coverage_and_zero_counts(tmp_path: Path) -> None:
    archive_path, config_path = _write_fixture(tmp_path)
    result = run_gpad_calendar_support_audit(archive_path, config_path)

    coverage = result.coverage_monthly.set_index(["sub_icb_code", "appointment_month"])
    feb_a = coverage.loc[("A", pd.Timestamp("2024-02-01"))]
    assert feb_a["practice_coverage_ratio"] == pytest.approx(0.5)
    assert feb_a["patient_coverage_ratio"] == pytest.approx(0.5)

    assert result.summary["source_zero_count_rows"] == 1
    assert result.summary["expected_months"] == 2
    assert result.summary["geographies_complete_all_months"] == 1
    assert result.summary["complete_coverage_days_attended_present"] == 1
    assert result.summary["complete_coverage_days_other_status_only"] == 1
    assert result.summary["complete_coverage_days_no_published_rows"] == 89


def test_calendar_support_rejects_fractional_counts(tmp_path: Path) -> None:
    archive_path, config_path = _write_fixture(tmp_path)
    with ZipFile(archive_path, "a") as archive:
        archive.writestr(
            "SUB_ICB_LOCATION_CSV_Fractional.csv",
            "SUB_ICB_LOCATION_CODE,SUB_ICB_LOCATION_NAME,Appointment_Date,APPT_STATUS,"
            "COUNT_OF_APPOINTMENTS\nA,Area A,03JAN2024,Attended,1.5\n",
        )
    _relock_config(archive_path, config_path)

    with pytest.raises(ValueError, match="Non-integral values"):
        run_gpad_calendar_support_audit(archive_path, config_path)


def test_calendar_support_rejects_fraction_beyond_float_precision(tmp_path: Path) -> None:
    archive_path, config_path = _write_fixture(tmp_path)
    with ZipFile(archive_path, "a") as archive:
        archive.writestr(
            "SUB_ICB_LOCATION_CSV_Precision.csv",
            "SUB_ICB_LOCATION_CODE,SUB_ICB_LOCATION_NAME,Appointment_Date,APPT_STATUS,"
            "COUNT_OF_APPOINTMENTS\nA,Area A,03JAN2024,Attended,1.0000000000000001\n",
        )
    _relock_config(archive_path, config_path)

    with pytest.raises(ValueError, match="Non-integral values"):
        run_gpad_calendar_support_audit(archive_path, config_path)


def test_calendar_support_fails_on_daily_schema_drift(tmp_path: Path) -> None:
    archive_path, config_path = _write_fixture(tmp_path)
    with ZipFile(archive_path, "a") as archive:
        archive.writestr("SUB_ICB_LOCATION_CSV_Bad.csv", "unexpected,value\n1,2\n")
    _relock_config(archive_path, config_path)

    with pytest.raises(ValueError, match="daily schema failures"):
        run_gpad_calendar_support_audit(archive_path, config_path)


def test_calendar_support_requires_locked_archive_bytes(tmp_path: Path) -> None:
    archive_path, config_path = _write_fixture(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["source"]["expected_sha256"] = "0" * 64
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="requires the locked GPAD archive bytes"):
        run_gpad_calendar_support_audit(archive_path, config_path)
