"""Forecast and data monitoring with threshold-based alerts.

Production forecasting fails quietly: a model keeps emitting plausible
numbers while its inputs or its accuracy drift. The checks here compare a
recent window against forecasts and against a reference history window, and
emit a tidy alerts table. Every check is a plain threshold from
``configs/monitoring.yaml`` — explainable to an operations team, no anomaly
black boxes.

Checks implemented:

- **Forecast bias** by clinic and by region (systematic over/under-forecast).
- **WAPE level** by clinic, plus **degradation** versus a reference WAPE
  (e.g. the registry's calibration metric at training time).
- **Demand volume shift**: recent mean visits vs a reference window.
- **Marketing spend shift**: recent mean spend vs the reference window.
- **Capacity utilisation shift**: change in mean utilisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from clinic_forecast.metrics import compute_metrics


@dataclass(frozen=True)
class MonitoringThresholds:
    """Alert thresholds; values are deliberately simple and documented."""

    max_abs_bias_pct: float = 10.0
    max_wape_pct: float = 30.0
    max_wape_degradation_ratio: float = 1.3
    max_volume_shift_ratio: float = 0.25
    max_spend_shift_ratio: float = 0.5
    max_utilization_shift: float = 0.15

    def validate(self) -> None:
        """Validate thresholds."""
        values = self.__dict__.values()
        if any(value <= 0 for value in values):
            raise ValueError("All monitoring thresholds must be positive.")
        if self.max_wape_degradation_ratio < 1.0:
            raise ValueError("max_wape_degradation_ratio must be at least 1.0.")


def load_monitoring_config(path: str | Path) -> MonitoringThresholds:
    """Load monitoring thresholds from a YAML config file."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "thresholds" not in raw:
        raise ValueError(f"Config {path} must contain a 'thresholds' section.")
    thresholds = MonitoringThresholds(**raw["thresholds"])
    thresholds.validate()
    return thresholds


def _alert_row(
    level: str, group: str, check: str, value: float, threshold: float, alert: bool
) -> dict[str, object]:
    return {
        "level": level,
        "group": group,
        "check": check,
        "value": round(float(value), 3),
        "threshold": threshold,
        "alert": bool(alert),
    }


def forecast_quality_alerts(
    scored: pd.DataFrame,
    thresholds: MonitoringThresholds | None = None,
    reference_wape: dict[str, float] | None = None,
    actual_col: str = "visits",
    forecast_col: str = "forecast",
    region_col: str | None = "region",
) -> pd.DataFrame:
    """Bias and WAPE alerts from a scored forecast window.

    Parameters
    ----------
    scored:
        Frame with actuals and forecasts per clinic-day for the monitored
        window; a region column enables regional bias checks.
    reference_wape:
        Optional mapping clinic_id -> WAPE at training/calibration time, used
        for the degradation check.
    """
    limits = thresholds or MonitoringThresholds()
    limits.validate()
    rows: list[dict[str, object]] = []

    for clinic_id, frame in scored.groupby("clinic_id", observed=True):
        metrics = compute_metrics(frame[actual_col], frame[forecast_col])
        rows.append(
            _alert_row(
                "clinic", str(clinic_id), "abs_bias_pct",
                abs(metrics.bias), limits.max_abs_bias_pct,
                abs(metrics.bias) > limits.max_abs_bias_pct,
            )
        )
        rows.append(
            _alert_row(
                "clinic", str(clinic_id), "wape_pct",
                metrics.wape, limits.max_wape_pct,
                metrics.wape > limits.max_wape_pct,
            )
        )
        if reference_wape and str(clinic_id) in reference_wape:
            ratio = metrics.wape / max(reference_wape[str(clinic_id)], 1e-9)
            rows.append(
                _alert_row(
                    "clinic", str(clinic_id), "wape_degradation_ratio",
                    ratio, limits.max_wape_degradation_ratio,
                    ratio > limits.max_wape_degradation_ratio,
                )
            )

    if region_col is not None and region_col in scored.columns:
        for region, frame in scored.groupby(region_col, observed=True):
            metrics = compute_metrics(frame[actual_col], frame[forecast_col])
            rows.append(
                _alert_row(
                    "region", str(region), "abs_bias_pct",
                    abs(metrics.bias), limits.max_abs_bias_pct,
                    abs(metrics.bias) > limits.max_abs_bias_pct,
                )
            )
    return pd.DataFrame(rows)


def _shift_ratio(recent: pd.Series, reference: pd.Series) -> float:
    reference_mean = float(reference.mean())
    if reference_mean == 0:
        return 0.0
    return float(recent.mean()) / reference_mean - 1.0


def distribution_shift_alerts(
    recent: pd.DataFrame,
    reference: pd.DataFrame,
    thresholds: MonitoringThresholds | None = None,
) -> pd.DataFrame:
    """Volume, marketing-spend and utilisation shift alerts per clinic.

    ``recent`` and ``reference`` are usage frames (open days recommended) for
    the monitored window and a stable comparison window respectively.
    """
    limits = thresholds or MonitoringThresholds()
    limits.validate()
    rows: list[dict[str, object]] = []

    checks = [
        ("visits", "volume_shift_ratio", limits.max_volume_shift_ratio, True),
        ("marketing_spend", "spend_shift_ratio", limits.max_spend_shift_ratio, True),
        ("capacity_utilization", "utilization_shift", limits.max_utilization_shift, False),
    ]
    for clinic_id, recent_frame in recent.groupby("clinic_id", observed=True):
        reference_frame = reference[reference["clinic_id"] == clinic_id]
        if reference_frame.empty:
            continue
        for column, check, threshold, relative in checks:
            if column not in recent.columns or column not in reference.columns:
                continue
            if relative:
                value = abs(_shift_ratio(recent_frame[column], reference_frame[column]))
            else:
                value = abs(
                    float(recent_frame[column].mean()) - float(reference_frame[column].mean())
                )
            rows.append(
                _alert_row("clinic", str(clinic_id), check, value, threshold, value > threshold)
            )
    return pd.DataFrame(rows)


def monitoring_report(
    scored: pd.DataFrame,
    recent: pd.DataFrame,
    reference: pd.DataFrame,
    thresholds: MonitoringThresholds | None = None,
    reference_wape: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Full monitoring report: forecast quality plus distribution shifts.

    Returns a tidy frame (level, group, check, value, threshold, alert)
    sorted with triggered alerts first.
    """
    quality = forecast_quality_alerts(scored, thresholds, reference_wape)
    shifts = distribution_shift_alerts(recent, reference, thresholds)
    report = pd.concat([quality, shifts], ignore_index=True)
    return report.sort_values(
        ["alert", "level", "group", "check"], ascending=[False, True, True, True]
    ).reset_index(drop=True)
