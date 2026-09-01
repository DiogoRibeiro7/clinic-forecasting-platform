from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from clinic_forecast.nhs_gpad_calendar import run_gpad_calendar_support_audit
from clinic_forecast.nhs_gpad import sha256_file


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    archive_path = tmp_path / "gpad.zip"
    coverage = pd.DataFrame(
        {
            "SUB_ICB_LOCATION_CODE": ["A", "A"],
            "ICB_ONS_CODE": ["X", "X"],
            "REGION_CODE": ["R", "R"],
            "Appointment_Month": ["Jan-24", "Feb-24"],
            "Included Practices": [2, 2],
            "Open Practices": [2, 2],
            "Patients registered at included practices": [100, 100],
            "Patients registered at open practices": [100, 100],
        }
    )
    daily = pd.DataFrame(
        {
            "SUB_ICB_LOCATION_CODE": ["A", "A", "A"],
            "SUB_ICB_LOCATION_NAME": ["Area A", "Area A", "Area A"],
            "Appointment_Date": ["01JAN2024", "01JAN2024", "02JAN2024"],
            "APPT_STATUS": ["Attended", "DNA", "DNA"],
            "COUNT_OF_APPOINTMENTS": [10, 1, 1],
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


def test_calendar_support_distinguishes_other_status_from_no_rows(tmp_path: Path) -> None:
    archive_path, config_path = _write_fixture(tmp_path)
    result = run_gpad_calendar_support_audit(archive_path, config_path)

    support = result.calendar_support.set_index("date")
    assert support.loc[pd.Timestamp("2024-01-01"), "source_support_class"] == "attended_present"
    assert support.loc[pd.Timestamp("2024-01-02"), "source_support_class"] == "other_status_only"
    assert support.loc[pd.Timestamp("2024-01-03"), "source_support_class"] == "no_published_rows"
    assert result.summary["geographies_complete_all_30_months"] == 0


def test_calendar_support_requires_locked_archive_bytes(tmp_path: Path) -> None:
    archive_path, config_path = _write_fixture(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["source"]["expected_sha256"] = "0" * 64
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(ValueError, match="requires the locked GPAD archive bytes"):
        run_gpad_calendar_support_audit(archive_path, config_path)
