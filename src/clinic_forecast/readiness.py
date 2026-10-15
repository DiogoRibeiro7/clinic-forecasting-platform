"""Executable local readiness checks for the portfolio serving boundary."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from clinic_forecast.api.contract import V2_CONTRACT_VERSION, V2ArtifactKind, validate_v2_artifact
from clinic_forecast.registry import LocalModelRegistry
from clinic_forecast.serving_provenance import (
    ServingRunManifest,
    load_serving_manifest,
    resolve_output_artifact,
    verify_file_fingerprint,
)


@dataclass(frozen=True)
class PortfolioReadinessSummary:
    """Verified local serving state for the portfolio demo."""

    contract_version: str
    run_id: str
    source_revision: str
    artifact_rows: dict[str, int]
    model_versions: dict[str, int]

    @property
    def status(self) -> str:
        """Return the local readiness status label."""
        return "portfolio_ready"


def _read_validated_artifact(
    output_dir: Path,
    manifest: ServingRunManifest,
    kind: V2ArtifactKind,
) -> pd.DataFrame:
    """Resolve, fingerprint-check, load and schema-check one serving artefact."""
    fingerprint = manifest.artifacts[kind]
    path = resolve_output_artifact(output_dir, fingerprint)
    verify_file_fingerprint(path, fingerprint)
    frame = pd.read_csv(path)
    validate_v2_artifact(frame, kind)
    return frame


def verify_portfolio_readiness(output_dir: str | Path) -> PortfolioReadinessSummary:
    """Verify locally provable serving-readiness invariants.

    This check validates only repository-controlled artefacts and contracts. It is
    not production, privacy, security, SLO or clinical-effectiveness certification.
    """
    root = Path(output_dir)
    manifest_path = root / "role_specific" / "latest_manifest.json"
    manifest = load_serving_manifest(manifest_path)

    artifact_rows: dict[str, int] = {}
    for kind in ("forecasts", "staffing", "monitoring"):
        frame = _read_validated_artifact(root, manifest, kind)
        artifact_rows[kind] = len(frame)

    if set(manifest.models) != {
        "attended_demand",
        "visits",
        "scheduled_appointments",
    }:
        raise ValueError(
            "Serving manifest must bind exactly attended_demand, visits, and "
            "scheduled_appointments models."
        )

    registry = LocalModelRegistry(root / "model_registry")
    model_versions: dict[str, int] = {}
    for target, model in manifest.models.items():
        registry_path = resolve_output_artifact(root, model.registry_record)
        verify_file_fingerprint(registry_path, model.registry_record)
        record = registry.load(model.name, model.version)
        if record.version != model.version:
            raise ValueError(
                f"Registry version mismatch for {model.name!r}: "
                f"{record.version} != {model.version}."
            )
        if record.params.get("serving_run_id") != manifest.run_id:
            raise ValueError(
                f"Registry model {model.name!r} is not bound to serving run "
                f"{manifest.run_id!r}."
            )
        if record.params.get("serving_config_sha256") != manifest.config_sha256:
            raise ValueError(
                f"Registry model {model.name!r} does not match serving configuration."
            )
        model_versions[target] = model.version

    return PortfolioReadinessSummary(
        contract_version=V2_CONTRACT_VERSION,
        run_id=manifest.run_id,
        source_revision=manifest.source_revision,
        artifact_rows=artifact_rows,
        model_versions=model_versions,
    )


__all__ = ["PortfolioReadinessSummary", "verify_portfolio_readiness"]
