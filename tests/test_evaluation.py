from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from clinic_forecast.evaluation import (
    add_horizon,
    comparison_table,
    evaluate_forecasts,
    rank_models,
)


def make_scored(n_days: int = 10) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    frames = []
    for model, error in [("good", 1.0), ("bad", 10.0)]:
        for clinic, level in [("A", 100.0), ("B", 50.0)]:
            frames.append(
                pd.DataFrame(
                    {
                        "model": model,
                        "clinic_id": clinic,
                        "region": "north" if clinic == "A" else "south",
                        "date": dates,
                        "visits": level,
                        "forecast": level + error,
                    }
                )
            )
    return pd.concat(frames, ignore_index=True)


def test_evaluate_forecasts_by_model() -> None:
    results = evaluate_forecasts(make_scored())

    assert set(results["model"]) == {"good", "bad"}
    good = results.set_index("model").loc["good"]
    bad = results.set_index("model").loc["bad"]
    assert good["mae"] == pytest.approx(1.0)
    assert bad["mae"] == pytest.approx(10.0)
    assert good["wape"] < bad["wape"]


def test_evaluate_forecasts_grouped_by_clinic_and_region() -> None:
    by_clinic = evaluate_forecasts(make_scored(), group_cols=["clinic_id"])
    assert len(by_clinic) == 4  # 2 models x 2 clinics

    by_region = evaluate_forecasts(make_scored(), group_cols=["region"])
    assert set(by_region["region"]) == {"north", "south"}


def test_evaluate_forecasts_by_horizon() -> None:
    scored = add_horizon(make_scored(), origin="2024-12-31")
    by_horizon = evaluate_forecasts(scored, group_cols=["horizon_days"])
    assert by_horizon["horizon_days"].max() == 10


def test_add_horizon_rejects_rows_before_origin() -> None:
    with pytest.raises(ValueError, match="after the forecast origin"):
        add_horizon(make_scored(), origin="2025-01-05")


def test_zero_volume_actuals_do_not_break_metrics() -> None:
    frame = pd.DataFrame(
        {
            "model": "m",
            "clinic_id": "A",
            "date": pd.date_range("2025-01-01", periods=5),
            "visits": 0.0,
            "forecast": 2.0,
        }
    )
    results = evaluate_forecasts(frame)
    assert np.isfinite(results.loc[0, "wape"])
    assert np.isfinite(results.loc[0, "smape"])


def test_missing_forecasts_are_dropped_and_counted() -> None:
    frame = make_scored()
    frame.loc[frame.index[:5], "forecast"] = np.nan
    results = evaluate_forecasts(frame)

    affected = results.set_index(["model"]).loc["good"]
    assert affected["n_missing_forecasts"].sum() == 5
    assert np.isfinite(affected["mae"]).all()


def test_all_missing_group_is_skipped() -> None:
    frame = make_scored()
    frame.loc[frame["model"] == "bad", "forecast"] = np.nan
    results = evaluate_forecasts(frame)
    assert set(results["model"]) == {"good"}


def test_interval_coverage_and_width() -> None:
    frame = make_scored()
    frame["lower"] = frame["visits"] - 5
    frame["upper"] = frame["visits"] + 5
    results = evaluate_forecasts(frame, lower_col="lower", upper_col="upper")

    good = results.set_index("model").loc["good"]
    bad = results.set_index("model").loc["bad"]
    assert good["coverage"] == pytest.approx(1.0)  # error 1 inside +/-5
    assert bad["coverage"] == pytest.approx(1.0)  # actuals always inside the band
    assert good["interval_width"] == pytest.approx(10.0)


def test_rank_models_orders_by_primary_metric() -> None:
    ranked = rank_models(evaluate_forecasts(make_scored(), group_cols=["clinic_id"]))
    assert list(ranked["model"]) == ["good", "bad"]
    assert list(ranked["rank"]) == [1, 2]


def test_comparison_table_is_model_by_metric() -> None:
    table = comparison_table(evaluate_forecasts(make_scored()))
    assert list(table.index) == ["good", "bad"]
    assert "wape" in table.columns


def test_missing_columns_raise() -> None:
    with pytest.raises(ValueError, match="model"):
        evaluate_forecasts(make_scored().drop(columns=["model"]))
    with pytest.raises(ValueError, match="Unknown metric"):
        rank_models(evaluate_forecasts(make_scored()), primary_metric="nope")
