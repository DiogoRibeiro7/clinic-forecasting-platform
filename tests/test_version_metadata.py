from __future__ import annotations

import tomllib
from pathlib import Path

from clinic_forecast import __version__
from clinic_forecast.api.contract import V2_CONTRACT_VERSION
from clinic_forecast.api.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_project_package_and_api_versions_match() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["tool"]["poetry"]["version"]

    assert project_version == "0.3.0"
    assert __version__ == project_version
    assert app.version == project_version


def test_v2_contract_version_is_independent_from_package_version() -> None:
    assert V2_CONTRACT_VERSION == "2.0.0"
    assert V2_CONTRACT_VERSION != __version__
