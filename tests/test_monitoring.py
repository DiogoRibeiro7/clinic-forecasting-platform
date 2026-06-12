from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from clinic_forecast.monitoring import (
    MonitoringThresholds,
    distribution_shift_alerts,
    forecast_quality_alerts,
    load_monitoring_config,
    monitoring_report,
)


def make_scored(bias: float = 0.0, noise: float = 1.0, clinic: str = "A") -> pd.DataFrame:
    rng = np.random.default_rng(0)
    actual = rng.uniform(80, 120, 56)
    return pd.DataFrame(
        {
            "clinic_id": clinic,
            "region": "north",
            "visits": actual,
            "forecast": actual * (1 + bias) + rng.normal(0, noise, 56),
        }
    )


def make_usage(level: float, spend: float = 500.0, util: float = 0.6) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "clinic_id": "A",
            "visits": [level] * 28,
            "marketing_spend": [spend] * 28,
            "capacity_utilization": [util] * 28,
        }
    )


def test_healthy_forecasts_trigger_no_alerts() -> None:
    report = forecast_quality_alerts(make_scored(bias=0.01))
    assert not report["alert"].any()


def test_large_bias_triggers_clinic_and_region_alerts() -> None:
    report = forecast_quality_alerts(make_scored(bias=0.2))
    triggered = report[report["alert"]]
    assert {"clinic", "region"}.issubset(set(triggered["level"]))
    assert "abs_bias_pct" in set(triggered["check"])


def test_wape_degradation_uses_reference() -> None:
    scored = make_scored(bias=0.0, noise=15.0)
    report = forecast_quality_alerts(scored, reference_wape={"A": 2.0})
    degradation = report[report["check"] == "wape_degradation_ratio"]
    assert len(degradation) == 1
    assert degradation.iloc[0]["alert"]


def test_stable_distributions_trigger_no_alerts() -> None:
    report = distribution_shift_alerts(make_usage(100.0), make_usage(102.0))
    assert not report["alert"].any()


def test_volume_and_spend_shifts_trigger() -> None:
    recent = make_usage(level=160.0, spend=1200.0, util=0.9)
    reference = make_usage(level=100.0, spend=500.0, util=0.6)
    report = distribution_shift_alerts(recent, reference)
    triggered = set(report[report["alert"]]["check"])
    assert triggered == {"volume_shift_ratio", "spend_shift_ratio", "utilization_shift"}


def test_monitoring_report_sorts_alerts_first() -> None:
    report = monitoring_report(
        scored=make_scored(bias=0.2),
        recent=make_usage(100.0),
        reference=make_usage(101.0),
    )
    assert report.iloc[0]["alert"]
    assert not report.iloc[-1]["alert"]


def test_invalid_thresholds_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        MonitoringThresholds(max_abs_bias_pct=0).validate()
    with pytest.raises(ValueError, match="degradation"):
        MonitoringThresholds(max_wape_degradation_ratio=0.9).validate()


def test_repo_monitoring_config_loads() -> None:
    config_path = Path(__file__).resolve().parents[1] / "configs" / "monitoring.yaml"
    thresholds = load_monitoring_config(config_path)
    assert thresholds.max_wape_pct == 35.0


def test_config_requires_thresholds_section(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("nope: 1", encoding="utf-8")
    with pytest.raises(ValueError, match="thresholds"):
        load_monitoring_config(path)
