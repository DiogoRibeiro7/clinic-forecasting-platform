"""Configuration objects for the clinic forecasting project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """Common repository paths used by scripts and notebooks."""

    root: Path
    raw_data: Path
    processed_data: Path
    reports: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "ProjectPaths":
        """Build a path configuration from a repository root."""
        root_path = Path(root).resolve()
        return cls(
            root=root_path,
            raw_data=root_path / "data" / "raw",
            processed_data=root_path / "data" / "processed",
            reports=root_path / "reports",
        )


@dataclass(frozen=True)
class ForecastConfig:
    """Forecasting configuration shared across models."""

    horizon_days: int = 28
    validation_windows: int = 4
    minimum_train_days: int = 365
    target_col: str = "visits"
    date_col: str = "date"
    id_col: str = "clinic_id"
