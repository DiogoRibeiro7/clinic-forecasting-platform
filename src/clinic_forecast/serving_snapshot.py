"""Snapshot completed role-specific batch outputs into immutable serving runs.

The forecasting pipeline remains responsible only for scientific computation.
This module runs after a successful batch and captures the operational identity
of that run: immutable output copies, exact input hashes, configuration, source
revision, and the three registry versions that produced the serving artifacts.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from clinic_forecast.registry import LocalModelRegistry, ModelRecord
from clinic_forecast.role_specific import CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET
from clinic_forecast.serving_provenance import (
    FileFingerprint,
    ModelVersionProvenance,
    SERVING_PROVENANCE_SCHEMA_VERSION,
    ServingRunManifest,
    canonical_config_sha256,
    create_run_id,
    fingerprint_file,
    now_utc_iso,
    resolve_source_revision,
    write_serving_manifest,
)


@dataclass(frozen=True)
class ServingSnapshotRequest:
    """Inputs needed to snapshot one completed role-specific batch run."""

    output_dir: Path
    data_dir: Path
    origin: str
    estimator: str
    horizon_days: int
    coverage: float
    calibration_folds: int
    initial_train_days: int
    staffing_config: Path | None
    requested_holiday_calendar: str | None
    forecast_path: Path
    staffing_path: Path
    monitoring_path: Path
    source_revision: str | None = None
    repo_root: Path | None = None

    def validate(self) -> None:
        """Fail before mutation when required snapshot inputs are invalid."""
        if not self.origin:
            raise ValueError("Serving snapshot origin must be non-empty.")
        if not self.estimator:
            raise ValueError("Serving snapshot estimator must be non-empty.")
        if self.horizon_days <= 0:
            raise ValueError("Serving snapshot horizon_days must be positive.")
        if not 0.0 < self.coverage < 1.0:
            raise ValueError("Serving snapshot coverage must be between zero and one.")
        if self.calibration_folds <= 0:
            raise ValueError("Serving snapshot calibration_folds must be positive.")
        if self.initial_train_days <= 0:
            raise ValueError("Serving snapshot initial_train_days must be positive.")
        for path in (self.forecast_path, self.staffing_path, self.monitoring_path):
            if not path.is_file():
                raise FileNotFoundError(f"Serving snapshot artifact not found: {path}")


_TARGETS = (CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET)


def _model_name(estimator: str, target: str) -> str:
    return f"global_ml_{estimator}_{target}"


def _load_records(request: ServingSnapshotRequest) -> dict[str, ModelRecord]:
    registry = LocalModelRegistry(request.output_dir / "model_registry")
    records: dict[str, ModelRecord] = {}
    for target in _TARGETS:
        name = _model_name(request.estimator, target)
        record = registry.latest(name)
        if record is None:
            raise ValueError(f"Cannot snapshot serving run: registry model {name!r} is missing.")
        if record.params.get("serving_run_id") is not None:
            raise ValueError(
                f"Cannot snapshot serving run: registry model {name!r} version "
                f"{record.version} is already bound to serving run "
                f"{record.params['serving_run_id']!r}."
            )
        if record.train_end != request.origin:
            raise ValueError(
                f"Cannot snapshot serving run: {name!r} has train_end={record.train_end!r}, "
                f"expected {request.origin!r}."
            )
        if record.horizon_days != request.horizon_days:
            raise ValueError(
                f"Cannot snapshot serving run: {name!r} has horizon {record.horizon_days}, "
                f"expected {request.horizon_days}."
            )
        records[target] = record
    return records


def _resolved_holiday_calendar(records: dict[str, ModelRecord]) -> str:
    values = {str(record.params.get("holiday_calendar", "unknown")) for record in records.values()}
    if len(values) != 1:
        raise ValueError(f"Role-specific registry records disagree on holiday calendar: {values}.")
    return next(iter(values))


def _config_mapping(
    request: ServingSnapshotRequest,
    records: dict[str, ModelRecord],
) -> dict[str, object]:
    return {
        "estimator": request.estimator,
        "horizon_days": request.horizon_days,
        "coverage": request.coverage,
        "calibration_folds": request.calibration_folds,
        "initial_train_days": request.initial_train_days,
        "requested_holiday_calendar": request.requested_holiday_calendar,
        "resolved_holiday_calendar": _resolved_holiday_calendar(records),
        "clinical_policy": "capacity_upper_conformal_hybrid_v1",
        "targets": list(_TARGETS),
    }


def _copy_immutable_artifacts(
    request: ServingSnapshotRequest,
    run_dir: Path,
) -> dict[str, Path]:
    run_dir.mkdir(parents=True, exist_ok=False)
    paths = {
        "forecasts": run_dir / "forecasts.csv",
        "staffing": run_dir / "staffing.csv",
        "monitoring": run_dir / "monitoring.csv",
    }
    sources = {
        "forecasts": request.forecast_path,
        "staffing": request.staffing_path,
        "monitoring": request.monitoring_path,
    }
    for name, source in sources.items():
        shutil.copy2(source, paths[name])
    return paths


def _update_registry_records(
    request: ServingSnapshotRequest,
    records: dict[str, ModelRecord],
    artifact_paths: dict[str, Path],
    *,
    run_id: str,
    config_sha256: str,
) -> dict[str, Path]:
    registry_root = request.output_dir / "model_registry"
    record_paths: dict[str, Path] = {}
    immutable_artifacts = {
        "forecasts": str(artifact_paths["forecasts"]),
        "staffing": str(artifact_paths["staffing"]),
        "hybrid_monitoring": str(artifact_paths["monitoring"]),
    }
    for target, record in records.items():
        params = {
            **record.params,
            "serving_run_id": run_id,
            "serving_config_sha256": config_sha256,
        }
        updated = replace(record, params=params, artifact_paths=immutable_artifacts)
        path = registry_root / f"{record.name}_v{record.version}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Registry record disappeared before snapshot: {path}")
        path.write_text(json.dumps(asdict(updated), indent=2) + "\n", encoding="utf-8")
        record_paths[target] = path
    return record_paths


def _input_fingerprints(request: ServingSnapshotRequest) -> dict[str, FileFingerprint]:
    fingerprints: dict[str, FileFingerprint] = {}
    for filename in ("clinic_daily_usage.csv", "clinic_metadata.csv"):
        path = request.data_dir / filename
        fingerprints[filename] = fingerprint_file(path, display_path=filename)

    generation_manifest = request.data_dir / "generation_manifest.json"
    if generation_manifest.is_file():
        fingerprints["generation_manifest.json"] = fingerprint_file(
            generation_manifest, display_path="generation_manifest.json"
        )

    if request.staffing_config is not None:
        if not request.staffing_config.is_file():
            raise FileNotFoundError(
                f"Serving snapshot staffing configuration not found: {request.staffing_config}"
            )
        fingerprints["staffing_config"] = fingerprint_file(
            request.staffing_config,
            display_path=request.staffing_config.name,
        )
    return fingerprints


def snapshot_role_specific_serving_run(
    request: ServingSnapshotRequest,
) -> ServingRunManifest:
    """Persist one completed batch as an immutable, fully traceable serving run."""
    request.validate()
    records = _load_records(request)
    config = _config_mapping(request, records)
    config_sha256 = canonical_config_sha256(config)
    run_id = create_run_id(request.origin, request.estimator)
    run_dir = request.output_dir / "role_specific" / "runs" / run_id

    artifact_paths = _copy_immutable_artifacts(request, run_dir)
    record_paths = _update_registry_records(
        request,
        records,
        artifact_paths,
        run_id=run_id,
        config_sha256=config_sha256,
    )

    output_root = request.output_dir.resolve()
    artifacts = {
        name: fingerprint_file(
            path,
            display_path=str(path.resolve().relative_to(output_root)),
        )
        for name, path in artifact_paths.items()
    }
    models = {
        target: ModelVersionProvenance(
            name=records[target].name,
            version=records[target].version,
            target=target,
            trained_at=records[target].trained_at,
            registry_record=fingerprint_file(
                record_paths[target],
                display_path=str(record_paths[target].resolve().relative_to(output_root)),
            ),
        )
        for target in _TARGETS
    }
    manifest = ServingRunManifest(
        schema_version=SERVING_PROVENANCE_SCHEMA_VERSION,
        run_id=run_id,
        created_at=now_utc_iso(),
        source_revision=resolve_source_revision(
            explicit=request.source_revision,
            repo_root=request.repo_root,
        ),
        origin=request.origin,
        config_sha256=config_sha256,
        config=config,
        inputs=_input_fingerprints(request),
        models=models,
        artifacts=artifacts,
    )
    write_serving_manifest(
        manifest,
        immutable_path=run_dir / "manifest.json",
        latest_path=request.output_dir / "role_specific" / "latest_manifest.json",
    )
    return manifest


__all__ = ["ServingSnapshotRequest", "snapshot_role_specific_serving_run"]
