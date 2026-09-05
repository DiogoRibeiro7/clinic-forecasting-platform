from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.hybrid_dashboard import render_hybrid_monitoring_dashboard


def monitoring_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "level": "clinic",
                "group": "CLINIC_001",
                "n_open_days": 10,
                "capacity_pressure_days": 4,
                "capacity_pressure_rate": 0.4,
                "attended_demand_selected_days": 4,
                "attended_demand_selected_rate": 0.4,
                "mean_completed_upper_capacity_ratio": 1.01,
            },
            {
                "level": "network",
                "group": "all",
                "n_open_days": 20,
                "capacity_pressure_days": 5,
                "capacity_pressure_rate": 0.25,
                "attended_demand_selected_days": 5,
                "attended_demand_selected_rate": 0.25,
                "mean_completed_upper_capacity_ratio": 0.77,
            },
        ]
    )


def test_dashboard_renders_network_and_clinic_metrics() -> None:
    html = render_hybrid_monitoring_dashboard(monitoring_frame())

    assert "Hybrid policy monitoring" in html
    assert "25.0%" in html
    assert "CLINIC_001" in html
    assert "40.0%" in html
    assert "realised switch precision or recall" in html


def test_dashboard_escapes_clinic_labels() -> None:
    frame = monitoring_frame()
    frame.loc[0, "group"] = "<script>alert(1)</script>"

    html = render_hybrid_monitoring_dashboard(frame)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_dashboard_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        render_hybrid_monitoring_dashboard(monitoring_frame().drop(columns=["capacity_pressure_rate"]))


def test_dashboard_requires_single_network_row() -> None:
    frame = monitoring_frame()
    frame = pd.concat([frame, frame[frame["level"] == "network"]], ignore_index=True)

    with pytest.raises(ValueError, match="exactly one network/all row"):
        render_hybrid_monitoring_dashboard(frame)
