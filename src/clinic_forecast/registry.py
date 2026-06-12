"""Lightweight local model registry.

Tracks model metadata, metrics and artefact paths as human-readable JSON
files under a registry directory (by default ``outputs/model_registry/``) —
no MLflow, no server, no database. Each registration gets an auto-incremented
version; the latest version of a model is resolvable by name, and registered
models can be compared as a dataframe.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

_VERSION_PATTERN = re.compile(r"^(?P<name>.+)_v(?P<version>\d+)\.json$")


@dataclass(frozen=True)
class ModelRecord:
    """Metadata for one registered model version."""

    name: str
    version: int
    trained_at: str
    train_start: str
    train_end: str
    horizon_days: int
    metrics: dict[str, float] = field(default_factory=dict)
    features: list[str] = field(default_factory=list)
    params: dict[str, object] = field(default_factory=dict)
    artifact_paths: dict[str, str] = field(default_factory=dict)


class LocalModelRegistry:
    """File-backed model registry storing one JSON document per version."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _record_path(self, name: str, version: int) -> Path:
        return self.root / f"{name}_v{version}.json"

    def _versions(self, name: str) -> list[int]:
        versions = []
        for path in self.root.glob(f"{name}_v*.json"):
            match = _VERSION_PATTERN.match(path.name)
            if match and match.group("name") == name:
                versions.append(int(match.group("version")))
        return sorted(versions)

    def register(
        self,
        name: str,
        train_start: str,
        train_end: str,
        horizon_days: int,
        metrics: dict[str, float] | None = None,
        features: list[str] | None = None,
        params: dict[str, object] | None = None,
        artifact_paths: dict[str, str] | None = None,
        trained_at: str | None = None,
    ) -> ModelRecord:
        """Register a new model version and write its JSON record.

        Parameters
        ----------
        name:
            Model name; versions auto-increment per name.
        trained_at:
            ISO timestamp; defaults to now (UTC).
        """
        if not name or "/" in name or "\\" in name:
            raise ValueError(f"Invalid model name: {name!r}")
        existing = self._versions(name)
        version = (existing[-1] + 1) if existing else 1
        record = ModelRecord(
            name=name,
            version=version,
            trained_at=trained_at or datetime.now(UTC).isoformat(),
            train_start=str(train_start),
            train_end=str(train_end),
            horizon_days=horizon_days,
            metrics=metrics or {},
            features=features or [],
            params=params or {},
            artifact_paths=artifact_paths or {},
        )
        path = self._record_path(name, version)
        path.write_text(json.dumps(asdict(record), indent=2), encoding="utf-8")
        return record

    def load(self, name: str, version: int) -> ModelRecord:
        """Load a specific model version."""
        path = self._record_path(name, version)
        if not path.exists():
            raise FileNotFoundError(f"No registry record at {path}.")
        return ModelRecord(**json.loads(path.read_text(encoding="utf-8")))

    def latest(self, name: str) -> ModelRecord | None:
        """Return the most recent version of a model, or None if unregistered."""
        versions = self._versions(name)
        if not versions:
            return None
        return self.load(name, versions[-1])

    def list_records(self, name: str | None = None) -> list[ModelRecord]:
        """List all records, optionally filtered by model name."""
        records = []
        for path in sorted(self.root.glob("*.json")):
            match = _VERSION_PATTERN.match(path.name)
            if match is None:
                continue
            if name is not None and match.group("name") != name:
                continue
            records.append(self.load(match.group("name"), int(match.group("version"))))
        return sorted(records, key=lambda r: (r.name, r.version))

    def compare(self, name: str | None = None) -> pd.DataFrame:
        """Compare registered models as a flat dataframe (metrics expanded)."""
        rows = []
        for record in self.list_records(name):
            row: dict[str, object] = {
                "name": record.name,
                "version": record.version,
                "trained_at": record.trained_at,
                "train_end": record.train_end,
                "horizon_days": record.horizon_days,
                "n_features": len(record.features),
            }
            row.update({f"metric_{k}": v for k, v in record.metrics.items()})
            rows.append(row)
        return pd.DataFrame(rows)
