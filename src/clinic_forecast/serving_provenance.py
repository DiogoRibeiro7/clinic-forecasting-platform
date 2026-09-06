"""Immutable provenance manifests for role-specific serving runs.

The role-specific batch pipeline writes mutable ``latest.csv`` aliases for local
convenience, but serving must be traceable to immutable artifacts.  This module
creates and validates the manifest that links one serving run to its exact
source revision, input files, configuration, model-registry records, and output
artifacts.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Final, Mapping, cast
from uuid import uuid4

SERVING_PROVENANCE_SCHEMA_VERSION: Final = 1


@dataclass(frozen=True)
class FileFingerprint:
    """Portable identity for one file used or produced by a serving run."""

    path: str
    sha256: str
    size_bytes: int

    @classmethod
    def from_mapping(cls, value: object, *, label: str) -> FileFingerprint:
        """Parse and validate a fingerprint loaded from JSON."""
        mapping = _string_mapping(value, label=label)
        path = mapping.get("path")
        digest = mapping.get("sha256")
        size = mapping.get("size_bytes")
        if not isinstance(path, str) or not path:
            raise ValueError(f"{label}.path must be a non-empty string.")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"{label}.sha256 must be a 64-character digest.")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError(f"{label}.size_bytes must be a non-negative integer.")
        return cls(path=path, sha256=digest, size_bytes=size)


@dataclass(frozen=True)
class ModelVersionProvenance:
    """Registry identity for one target model participating in a serving run."""

    name: str
    version: int
    target: str
    trained_at: str
    registry_record: FileFingerprint

    @classmethod
    def from_mapping(cls, value: object, *, label: str) -> ModelVersionProvenance:
        """Parse and validate model provenance loaded from JSON."""
        mapping = _string_mapping(value, label=label)
        name = mapping.get("name")
        version = mapping.get("version")
        target = mapping.get("target")
        trained_at = mapping.get("trained_at")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{label}.name must be a non-empty string.")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError(f"{label}.version must be a positive integer.")
        if not isinstance(target, str) or not target:
            raise ValueError(f"{label}.target must be a non-empty string.")
        if not isinstance(trained_at, str) or not trained_at:
            raise ValueError(f"{label}.trained_at must be a non-empty string.")
        return cls(
            name=name,
            version=version,
            target=target,
            trained_at=trained_at,
            registry_record=FileFingerprint.from_mapping(
                mapping.get("registry_record"), label=f"{label}.registry_record"
            ),
        )


@dataclass(frozen=True)
class ServingRunManifest:
    """Complete traceability record for one immutable role-specific serving run."""

    schema_version: int
    run_id: str
    created_at: str
    source_revision: str
    origin: str
    config_sha256: str
    config: dict[str, object]
    inputs: dict[str, FileFingerprint]
    models: dict[str, ModelVersionProvenance]
    artifacts: dict[str, FileFingerprint]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the manifest."""
        return cast(dict[str, object], asdict(self))

    @classmethod
    def from_mapping(cls, value: object) -> ServingRunManifest:
        """Parse and validate a serving manifest loaded from JSON."""
        mapping = _string_mapping(value, label="serving manifest")
        schema_version = mapping.get("schema_version")
        run_id = mapping.get("run_id")
        created_at = mapping.get("created_at")
        source_revision = mapping.get("source_revision")
        origin = mapping.get("origin")
        config_sha256 = mapping.get("config_sha256")
        if schema_version != SERVING_PROVENANCE_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported serving provenance schema version: "
                f"{schema_version!r}; expected {SERVING_PROVENANCE_SCHEMA_VERSION}."
            )
        for field_name, field_value in (
            ("run_id", run_id),
            ("created_at", created_at),
            ("source_revision", source_revision),
            ("origin", origin),
            ("config_sha256", config_sha256),
        ):
            if not isinstance(field_value, str) or not field_value:
                raise ValueError(f"serving manifest {field_name} must be a non-empty string.")
        if len(cast(str, config_sha256)) != 64:
            raise ValueError("serving manifest config_sha256 must be a 64-character digest.")

        config = _string_mapping(mapping.get("config"), label="serving manifest config")
        input_mapping = _string_mapping(mapping.get("inputs"), label="serving manifest inputs")
        model_mapping = _string_mapping(mapping.get("models"), label="serving manifest models")
        artifact_mapping = _string_mapping(
            mapping.get("artifacts"), label="serving manifest artifacts"
        )
        inputs = {
            name: FileFingerprint.from_mapping(item, label=f"serving manifest inputs.{name}")
            for name, item in input_mapping.items()
        }
        models = {
            name: ModelVersionProvenance.from_mapping(
                item, label=f"serving manifest models.{name}"
            )
            for name, item in model_mapping.items()
        }
        artifacts = {
            name: FileFingerprint.from_mapping(
                item, label=f"serving manifest artifacts.{name}"
            )
            for name, item in artifact_mapping.items()
        }
        required_artifacts = {"forecasts", "staffing", "monitoring"}
        missing = sorted(required_artifacts.difference(artifacts))
        if missing:
            raise ValueError(f"serving manifest is missing artifacts: {missing}.")
        return cls(
            schema_version=SERVING_PROVENANCE_SCHEMA_VERSION,
            run_id=cast(str, run_id),
            created_at=cast(str, created_at),
            source_revision=cast(str, source_revision),
            origin=cast(str, origin),
            config_sha256=cast(str, config_sha256),
            config=config,
            inputs=inputs,
            models=models,
            artifacts=artifacts,
        )


def _string_mapping(value: object, *, label: str) -> dict[str, object]:
    """Return a JSON mapping whose keys are all strings."""
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object with string keys.")
    return cast(dict[str, object], value)


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a file without loading it fully into memory."""
    target = Path(path)
    digest = sha256()
    with target.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint_file(path: str | Path, *, display_path: str) -> FileFingerprint:
    """Fingerprint an existing file while recording a portable display path."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"Cannot fingerprint missing file: {target}")
    return FileFingerprint(
        path=display_path,
        sha256=sha256_file(target),
        size_bytes=target.stat().st_size,
    )


def canonical_config_sha256(config: Mapping[str, object]) -> str:
    """Hash a configuration mapping using deterministic canonical JSON."""
    encoded = json.dumps(
        dict(config), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def create_run_id(origin: str, estimator: str) -> str:
    """Create a collision-resistant identifier that remains human-readable."""
    compact_origin = origin.replace("-", "")
    return f"{compact_origin}-{estimator}-{uuid4().hex[:12]}"


def resolve_source_revision(
    *,
    explicit: str | None = None,
    repo_root: str | Path | None = None,
) -> str:
    """Resolve the source revision from explicit input, CI, or the local Git checkout."""
    if explicit and explicit.strip():
        return explicit.strip()
    for variable in ("CLINIC_FORECAST_SOURCE_REVISION", "GITHUB_SHA"):
        value = os.getenv(variable)
        if value and value.strip():
            return value.strip()

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    revision = completed.stdout.strip()
    return revision or "unknown"


def now_utc_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 form."""
    return datetime.now(UTC).isoformat()


def write_serving_manifest(
    manifest: ServingRunManifest,
    *,
    immutable_path: str | Path,
    latest_path: str | Path,
) -> None:
    """Write the same manifest to its immutable run path and latest pointer path."""
    payload = json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n"
    immutable = Path(immutable_path)
    latest = Path(latest_path)
    immutable.parent.mkdir(parents=True, exist_ok=True)
    latest.parent.mkdir(parents=True, exist_ok=True)
    immutable.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")


def load_serving_manifest(path: str | Path) -> ServingRunManifest:
    """Load and validate a persisted serving manifest."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"Serving provenance manifest not found: {target}")
    raw: object = json.loads(target.read_text(encoding="utf-8"))
    return ServingRunManifest.from_mapping(raw)


def resolve_output_artifact(output_dir: str | Path, fingerprint: FileFingerprint) -> Path:
    """Resolve a manifest artifact path while preventing traversal outside output_dir."""
    relative = Path(fingerprint.path)
    if relative.is_absolute():
        raise ValueError(f"Serving artifact path must be relative: {fingerprint.path}")
    root = Path(output_dir).resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Serving artifact path escapes the configured output directory: {fingerprint.path}"
        ) from exc
    return candidate


def verify_file_fingerprint(path: str | Path, expected: FileFingerprint) -> None:
    """Fail when an artifact no longer matches the manifest identity."""
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"Serving artifact not found: {target}")
    actual_size = target.stat().st_size
    if actual_size != expected.size_bytes:
        raise ValueError(
            f"Serving artifact size mismatch for {expected.path}: "
            f"{actual_size} != {expected.size_bytes}."
        )
    actual_digest = sha256_file(target)
    if actual_digest != expected.sha256:
        raise ValueError(
            f"Serving artifact SHA-256 mismatch for {expected.path}: "
            f"{actual_digest} != {expected.sha256}."
        )


__all__ = [
    "FileFingerprint",
    "ModelVersionProvenance",
    "SERVING_PROVENANCE_SCHEMA_VERSION",
    "ServingRunManifest",
    "canonical_config_sha256",
    "create_run_id",
    "fingerprint_file",
    "load_serving_manifest",
    "now_utc_iso",
    "resolve_output_artifact",
    "resolve_source_revision",
    "sha256_file",
    "verify_file_fingerprint",
    "write_serving_manifest",
]
