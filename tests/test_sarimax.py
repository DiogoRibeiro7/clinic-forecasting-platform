from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from clinic_forecast.models.sarimax import (
    DEFAULT_SARIMAX_CANDIDATES,
    sarimax_panel_forecast,
    select_sarimax_order,
)


def make_clinic(n_days: int = 200, clinic: str = "A", seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    weekly = 10 * np.sin(2 * np.pi * np.arange(n_days) / 7)
    visits = (60 + weekly + rng.normal(0, 4, n_days)).clip(min=1)
    return pd.DataFrame(
        {"clinic_id": clinic, "date": dates, "visits": visits,
         "marketing_spend": rng.uniform(200, 600, n_days)}
    )


def test_select_sarimax_order_returns_valid_candidate() -> None:
    selection = select_sarimax_order(make_clinic(), validation_days=21)
    assert (selection.order, selection.seasonal_order) in DEFAULT_SARIMAX_CANDIDATES
    assert selection.candidates_tried >= 1
    assert np.isfinite(selection.wape)


def test_max_candidates_limits_search() -> None:
    selection = select_sarimax_order(make_clinic(), validation_days=21, max_candidates=2)
    assert selection.candidates_tried <= 2


def test_select_requires_enough_history() -> None:
    with pytest.raises(ValueError, match="Not enough history"):
        select_sarimax_order(make_clinic(n_days=30), validation_days=28)


def test_panel_forecast_fixed_order_shapes() -> None:
    panel = pd.concat([make_clinic(clinic="A", seed=1), make_clinic(clinic="B", seed=2)],
                      ignore_index=True)
    cutoff = panel["date"].max() - pd.Timedelta(days=14)
    train, future = panel[panel["date"] <= cutoff], panel[panel["date"] > cutoff]

    forecast = sarimax_panel_forecast(train, future)
    assert len(forecast) == len(future)
    assert set(forecast["clinic_id"]) == {"A", "B"}
    assert (forecast["model"] == "sarimax").all()


def test_panel_forecast_auto_order_labels_model() -> None:
    panel = make_clinic(clinic="A", seed=3)
    cutoff = panel["date"].max() - pd.Timedelta(days=14)
    train, future = panel[panel["date"] <= cutoff], panel[panel["date"] > cutoff]

    forecast = sarimax_panel_forecast(train, future, auto_order=True, validation_days=21)
    assert (forecast["model"] == "sarimax_auto").all()
    assert forecast["forecast"].notna().all()
