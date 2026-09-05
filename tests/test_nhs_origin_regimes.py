from __future__ import annotations

import pandas as pd

from clinic_forecast.nhs_origin_regimes import characterize_origins, summarize_winner_groups


def _fixture_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2025-01-01", "2025-02-25", freq="D")
    panel_rows = []
    for clinic_id, offset in [("A", 0), ("B", 5)]:
        for i, date in enumerate(dates):
            panel_rows.append(
                {
                    "clinic_id": clinic_id,
                    "date": date,
                    "visits": 100 + offset + (i % 7) * 3,
                }
            )
    panel = pd.DataFrame(panel_rows)
    boundaries = pd.DataFrame(
        {
            "origin": [1],
            "train_end": [pd.Timestamp("2025-01-28")],
            "test_start": [pd.Timestamp("2025-01-29")],
            "test_end": [pd.Timestamp("2025-02-25")],
        }
    )
    fold_scores = pd.DataFrame(
        [
            {
                "model": "global_ml_hgb",
                "origin": 1,
                "wape": 5.0,
                "train_end": "2025-01-28",
                "test_start": "2025-01-29",
                "test_end": "2025-02-25",
            },
            {
                "model": "seasonal_naive",
                "origin": 1,
                "wape": 8.0,
                "train_end": "2025-01-28",
                "test_start": "2025-01-29",
                "test_end": "2025-02-25",
            },
        ]
    )
    forecast_rows = []
    test_panel = panel[panel["date"].between("2025-01-29", "2025-02-25")]
    for row in test_panel.itertuples(index=False):
        forecast_rows.extend(
            [
                {
                    "origin": 1,
                    "clinic_id": row.clinic_id,
                    "date": row.date,
                    "model": "global_ml_hgb",
                    "visits": row.visits,
                    "forecast": row.visits + 2,
                },
                {
                    "origin": 1,
                    "clinic_id": row.clinic_id,
                    "date": row.date,
                    "model": "seasonal_naive",
                    "visits": row.visits,
                    "forecast": row.visits + 6,
                },
            ]
        )
    return fold_scores, boundaries, panel, pd.DataFrame(forecast_rows)


def test_characterize_origins_preserves_frozen_winner_and_windows() -> None:
    fold_scores, boundaries, panel, forecast_rows = _fixture_frames()
    result = characterize_origins(fold_scores, boundaries, panel, forecast_rows)

    assert len(result) == 1
    row = result.iloc[0]
    assert row["winner"] == "hgb_better"
    assert row["hgb_minus_seasonal_wape"] == -3.0
    assert row["start_month"] == 1
    assert row["months_touched"] == 2
    assert row["hgb_better_geographies"] == 2
    assert row["hgb_better_geography_fraction"] == 1.0
    assert row["trailing_zero_fraction"] == 0.0
    assert row["test_zero_fraction"] == 0.0


def test_winner_group_summary_reports_median_and_iqr() -> None:
    fold_scores, boundaries, panel, forecast_rows = _fixture_frames()
    result = characterize_origins(fold_scores, boundaries, panel, forecast_rows)
    summary = summarize_winner_groups(result)

    target = summary[
        (summary["winner"] == "hgb_better")
        & (summary["descriptor"] == "hgb_minus_seasonal_wape")
    ].iloc[0]
    assert target["n"] == 1
    assert target["median"] == -3.0
    assert target["q25"] == -3.0
    assert target["q75"] == -3.0
