from __future__ import annotations

import pandas as pd
import pytest

import clinic_forecast.core_benchmark as registry
import clinic_forecast.core_benchmark_runner as runner
from clinic_forecast.core_benchmark import CoreBenchmarkSpec


def _panel(days: int = 18) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    rows: list[dict[str, object]] = []
    for clinic_id, offset in (("A", 0), ("B", 10)):
        for index, date in enumerate(dates):
            rows.append(
                {
                    "clinic_id": clinic_id,
                    "date": date,
                    "visits": 100 + offset + index,
                    "scheduled_appointments": 120 + offset + index,
                    "no_show_count": 2,
                }
            )
    return pd.DataFrame(rows)


def test_core_spec_freezes_non_overlapping_fixed_origin_design() -> None:
    spec = CoreBenchmarkSpec()
    assert spec.initial_train_days == 365
    assert spec.horizon_days == 28
    assert spec.step_days == 28
    assert spec.max_folds == 8
    assert spec.synthetic_seed == 42
    assert spec.splitter().effective_step_days == 28


def test_sarimax_adapter_strips_future_outcomes(monkeypatch: pytest.MonkeyPatch) -> None:
    observed_columns: set[str] = set()

    def fake_sarimax(train: pd.DataFrame, future: pd.DataFrame, **kwargs: object) -> pd.DataFrame:
        del train, kwargs
        observed_columns.update(str(column) for column in future.columns)
        result = future[["clinic_id", "date"]].copy()
        result["forecast"] = 1.0
        result["model"] = "sarimax"
        return result

    monkeypatch.setattr(registry, "sarimax_panel_forecast", fake_sarimax)
    forecaster = registry.core_forecasters()["sarimax"]
    panel = _panel(10)
    forecaster(panel.iloc[:12], panel.iloc[12:])

    assert "visits" not in observed_columns
    assert "scheduled_appointments" not in observed_columns
    assert "no_show_count" not in observed_columns


def test_runner_requires_complete_model_and_fold_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    def make_forecaster(name: str, adjustment: float):
        def forecaster(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
            means = train.groupby("clinic_id", observed=True)["visits"].mean()
            output = test[["clinic_id", "date"]].copy()
            output["forecast"] = output["clinic_id"].map(means).astype(float) + adjustment
            output["model"] = name
            return output

        return forecaster

    monkeypatch.setattr(
        runner,
        "core_forecasters",
        lambda: {
            "seasonal_naive": make_forecaster("seasonal_naive", 0.0),
            "moving_average_28": make_forecaster("moving_average_28", 1.0),
            "sarimax": make_forecaster("sarimax", 2.0),
            "global_ml_hgb": make_forecaster("global_ml_hgb", -1.0),
        },
    )
    spec = CoreBenchmarkSpec(
        initial_train_days=14,
        horizon_days=2,
        step_days=2,
        max_folds=2,
    )
    result = runner.run_core_benchmark(_panel(), spec)

    assert result.fold_scores["fold"].nunique() == 2
    assert set(result.fold_scores["model"]) == {
        "seasonal_naive",
        "moving_average_28",
        "sarimax",
        "global_ml_hgb",
    }
    assert result.horizon_scores["horizon_days"].unique().tolist() == [1, 2]
    assert len(result.paired_contrasts) == 3 * len(runner.PRIMARY_METRICS)
    assert result.specification["evaluation_contract"] == (
        "fixed-origin full-horizon; no teacher forcing"
    )
