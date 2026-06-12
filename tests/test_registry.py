from __future__ import annotations

from pathlib import Path

import pytest

from clinic_forecast.registry import LocalModelRegistry


def register_sample(registry: LocalModelRegistry, wape: float = 20.0) -> None:
    registry.register(
        name="global_ml_hgb",
        train_start="2022-01-01",
        train_end="2025-12-31",
        horizon_days=28,
        metrics={"calibration_wape": wape},
        features=["lag_1", "lag_7"],
        params={"estimator": "hgb"},
        artifact_paths={"forecasts": "outputs/forecasts/latest.csv"},
    )


def test_register_and_load_round_trip(tmp_path: Path) -> None:
    registry = LocalModelRegistry(tmp_path)
    register_sample(registry)

    record = registry.load("global_ml_hgb", 1)
    assert record.version == 1
    assert record.metrics["calibration_wape"] == 20.0
    assert record.features == ["lag_1", "lag_7"]
    assert (tmp_path / "global_ml_hgb_v1.json").exists()


def test_versions_auto_increment_and_latest(tmp_path: Path) -> None:
    registry = LocalModelRegistry(tmp_path)
    register_sample(registry, wape=22.0)
    register_sample(registry, wape=19.5)

    latest = registry.latest("global_ml_hgb")
    assert latest is not None
    assert latest.version == 2
    assert latest.metrics["calibration_wape"] == 19.5


def test_latest_returns_none_for_unregistered(tmp_path: Path) -> None:
    assert LocalModelRegistry(tmp_path).latest("nothing") is None


def test_compare_returns_metric_columns(tmp_path: Path) -> None:
    registry = LocalModelRegistry(tmp_path)
    register_sample(registry, wape=22.0)
    register_sample(registry, wape=19.5)

    table = registry.compare()
    assert list(table["version"]) == [1, 2]
    assert "metric_calibration_wape" in table.columns


def test_invalid_name_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid model name"):
        LocalModelRegistry(tmp_path).register(
            name="bad/name", train_start="2022-01-01", train_end="2025-12-31", horizon_days=28
        )


def test_records_are_human_readable_json(tmp_path: Path) -> None:
    registry = LocalModelRegistry(tmp_path)
    register_sample(registry)
    text = (tmp_path / "global_ml_hgb_v1.json").read_text(encoding="utf-8")
    assert text.startswith("{\n  ")  # indented, not minified
    assert '"calibration_wape"' in text
