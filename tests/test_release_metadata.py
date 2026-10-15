from __future__ import annotations

from pathlib import Path

import pytest

from clinic_forecast import __version__
from clinic_forecast.api.contract import V2_CONTRACT_VERSION
from clinic_forecast.release_metadata import verify_release_metadata

ROOT = Path(__file__).resolve().parents[1]


def _write_release_fixture(
    root: Path,
    *,
    project_version: str = "0.3.0",
    citation_version: str = "0.3.0",
    changelog_version: str = "0.3.0",
) -> None:
    (root / "pyproject.toml").write_text(
        (
            "[tool.poetry]\n"
            'name = "clinic-forecasting-platform"\n'
            f'version = "{project_version}"\n'
        ),
        encoding="utf-8",
    )
    (root / "CITATION.cff").write_text(
        (
            "cff-version: 1.2.0\n"
            'title: "Clinic Forecasting Platform"\n'
            f'version: "{citation_version}"\n'
        ),
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## Unreleased\n\n## {changelog_version}\n",
        encoding="utf-8",
    )


def test_repository_release_metadata_is_consistent() -> None:
    summary = verify_release_metadata(ROOT)

    assert summary.version == __version__ == "0.3.0"
    assert summary.api_version == __version__
    assert summary.citation_version == __version__
    assert summary.contract_version == V2_CONTRACT_VERSION == "2.0.0"


def test_release_metadata_rejects_citation_version_drift(tmp_path: Path) -> None:
    _write_release_fixture(tmp_path, citation_version="0.2.0")

    with pytest.raises(ValueError, match="citation version mismatch"):
        verify_release_metadata(tmp_path)


def test_release_metadata_requires_matching_changelog_section(tmp_path: Path) -> None:
    _write_release_fixture(tmp_path, changelog_version="0.2.0")

    with pytest.raises(ValueError, match="missing a section"):
        verify_release_metadata(tmp_path)
