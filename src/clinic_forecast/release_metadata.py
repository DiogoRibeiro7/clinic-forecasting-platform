"""Release metadata validation for manual project releases."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml

from clinic_forecast import __version__
from clinic_forecast.api.contract import V2_CONTRACT_VERSION
from clinic_forecast.api.main import app


@dataclass(frozen=True)
class ReleaseMetadataSummary:
    """Validated release identities for the current repository state."""

    version: str
    citation_version: str
    api_version: str
    contract_version: str


def verify_release_metadata(repo_root: str | Path) -> ReleaseMetadataSummary:
    """Validate project, package, API, citation and changelog version identity."""
    root = Path(repo_root)

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = str(pyproject["tool"]["poetry"]["version"])
    if project_version != __version__:
        raise ValueError(
            f"Project/package version mismatch: {project_version} != {__version__}."
        )

    api_version = str(app.version)
    if api_version != project_version:
        raise ValueError(
            f"Project/API version mismatch: {project_version} != {api_version}."
        )

    citation_raw = yaml.safe_load((root / "CITATION.cff").read_text(encoding="utf-8"))
    if not isinstance(citation_raw, dict):
        raise ValueError("CITATION.cff must contain a YAML mapping.")
    citation_version = str(citation_raw.get("version", ""))
    if citation_version != project_version:
        raise ValueError(
            "Project/citation version mismatch: "
            f"{project_version} != {citation_version}."
        )

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    version_heading = re.compile(
        rf"^## {re.escape(project_version)}\s*$",
        flags=re.MULTILINE,
    )
    if version_heading.search(changelog) is None:
        raise ValueError(
            f"CHANGELOG.md is missing a section for version {project_version}."
        )
    if "## Unreleased" not in changelog:
        raise ValueError("CHANGELOG.md must retain an Unreleased section.")

    return ReleaseMetadataSummary(
        version=project_version,
        citation_version=citation_version,
        api_version=api_version,
        contract_version=V2_CONTRACT_VERSION,
    )


__all__ = ["ReleaseMetadataSummary", "verify_release_metadata"]
