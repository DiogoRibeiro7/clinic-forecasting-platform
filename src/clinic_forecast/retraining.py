"""Verification helpers for scheduled role-specific retraining rehearsals.

The repository's role-specific batch pipeline already performs model fitting,
interval calibration, artifact persistence, and local registry updates.  This
module does not introduce a second training implementation.  It verifies that
one orchestration run produced a coherent set of serving artifacts and registry
records before the workflow reports success.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from clinic_forecast.api.contract import V2ArtifactKind, validate_v2_artifact
from clinic_forecast.registry import LocalModelRegistry, ModelRecord
from clinic_forecast.role_specific import CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET

Estimator = Literal["hgb", "xgboost", "lightgbm"]


@dataclass(frozen=True)
class RetrainingRunSummary:
    """Validated metadata for one role-specific retraining run."""

    output_dir: Path
    train_end: str
    horizon_days: int
    n_clinics: int
    model_versions: dict[str, int]


def _read_serving_artifact(path: Path, kind: V2ArtifactKind) -> pd.DataFrame:
    """Read one persisted serving artifact and validate its frozen v2 schema."""
    if not path.is_file():
        raise FileNotFoundError(f"Retraining artifact not found: {path}")
    frame = pd.read_csv(path)
    validate_v2_artifact(frame, kind)
    return frame


def _required_model_names(estimator: Estimator) -> tuple[str, ...]:
    """Return the three role-specific model names written by the batch pipeline."""
    return tuple(
        f"global_ml_{estimator}_{target}"
        for target in (CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET)
    )


def _load_required_records(
    registry: LocalModelRegistry,
    estimator: Estimator,
) -> dict[str, ModelRecord]:
    """Load the latest registry record for every role-specific target."""
    records: dict[str, ModelRecord] = {}
    for name in _required_model_names(estimator):
        record = registry.latest(name)
        if record is None:
            raise ValueError(f"Retraining registry is missing required model {name!r}.")
        records[name] = record
    return records


def _validate_registered_artifacts(records: dict[str, ModelRecord]) -> None:
    """Require each model record to point at the three persisted batch artifacts."""
    required_keys = {"forecasts", "staffing", "hybrid_monitoring"}
    for name, record in records.items():
        missing = sorted(required_keys.difference(record.artifact_paths))
        if missing:
            raise ValueError(f"Registry record {name!r} is missing artifact paths: {missing}.")
        for key in sorted(required_keys):
            path = Path(record.artifact_paths[key])
            if not path.is_file():
                raise FileNotFoundError(
                    f"Registry record {name!r} points to missing {key} artifact: {path}"
                )


def verify_role_specific_retraining(
    output_dir: str | Path,
    estimator: Estimator = "hgb",
) -> RetrainingRunSummary:
    """Verify that one scheduled retraining run produced coherent persisted outputs.

    This check is intentionally operational rather than statistical.  It verifies
    schema compatibility, registry completeness, a common training cutoff and
    horizon across the three target models, and existence of every artifact path
    recorded in the registry.  It does not decide whether a retrained model is
    clinically suitable for deployment.
    """
    root = Path(output_dir)
    role_root = root / "role_specific"
    forecasts = _read_serving_artifact(role_root / "forecasts" / "latest.csv", "forecasts")
    staffing = _read_serving_artifact(role_root / "staffing" / "latest.csv", "staffing")
    _read_serving_artifact(role_root / "monitoring" / "latest.csv", "monitoring")

    registry_root = root / "model_registry"
    if not registry_root.is_dir():
        raise FileNotFoundError(f"Retraining registry directory not found: {registry_root}")
    records = _load_required_records(LocalModelRegistry(registry_root), estimator)
    _validate_registered_artifacts(records)

    train_ends = {record.train_end for record in records.values()}
    if len(train_ends) != 1:
        raise ValueError(f"Role-specific models have inconsistent training cutoffs: {train_ends}.")
    horizons = {record.horizon_days for record in records.values()}
    if len(horizons) != 1:
        raise ValueError(f"Role-specific models have inconsistent horizons: {horizons}.")

    train_end = next(iter(train_ends))
    horizon_days = next(iter(horizons))
    forecast_dates = pd.to_datetime(forecasts["date"], errors="raise")
    staffing_dates = pd.to_datetime(staffing["date"], errors="raise")
    if forecast_dates.nunique() != horizon_days:
        raise ValueError(
            "Forecast artifact horizon does not match the registry: "
            f"{forecast_dates.nunique()} dates versus {horizon_days}."
        )
    if staffing_dates.nunique() != horizon_days:
        raise ValueError(
            "Staffing artifact horizon does not match the registry: "
            f"{staffing_dates.nunique()} dates versus {horizon_days}."
        )

    forecast_clinics = set(forecasts["clinic_id"].astype(str))
    staffing_clinics = set(staffing["clinic_id"].astype(str))
    if forecast_clinics != staffing_clinics:
        raise ValueError("Forecast and staffing artifacts contain different clinic sets.")

    return RetrainingRunSummary(
        output_dir=root,
        train_end=train_end,
        horizon_days=horizon_days,
        n_clinics=len(forecast_clinics),
        model_versions={name: record.version for name, record in records.items()},
    )


__all__ = ["RetrainingRunSummary", "verify_role_specific_retraining"]
