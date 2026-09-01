from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from clinic_forecast.nhs_gpad_benchmark import (
    origin_boundaries_from_policy,
    paired_model_contrasts,
    prepare_confirmatory_panel,
)


def _policy() -> dict[str, object]:
    return {
        "date_start": "2024-01-01",
        "date_end": "2024-01-03",
        "calendar_days": 3,
        "panel_rows": 6,
        "geography_policy": {
            "eligible_sub_icb_codes": ["A", "B"],
            "eligible_geographies": 2,
        },
        "support_counts_within_eligible_panel": {
            "attended_present": 2,
            "other_status_only": 1,
            "no_published_rows": 3,
        },
        "validation": {
            "initial_training_days": 3,
            "forecast_horizon_days": 2,
            "step_days": 2,
            "outer_origins": 2,
            "origins": [
                {
                    "origin": 1,
                    "train_end": "2024-01-03",
                    "test_start": "2024-01-04",
                    "test_end": "2024-01-05",
                },
                {
                    "origin": 2,
                    "train_end": "2024-01-05",
                    "test_start": "2024-01-06",
                    "test_end": "2024-01-07",
                },
            ],
        },
    }


def _calendar_support() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sub_icb_code": ["A", "A", "A", "B", "B", "B"],
            "date": pd.to_datetime(
                [
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-01",
                    "2024-01-02",
                    "2024-01-03",
                ]
            ),
            "source_support_class": [
                "attended_present",
                "other_status_only",
                "no_published_rows",
                "attended_present",
                "no_published_rows",
                "no_published_rows",
            ],
            "attended_appointments": [5, pd.NA, pd.NA, 7, pd.NA, pd.NA],
            "complete_coverage": [True] * 6,
        }
    )


def test_prepare_confirmatory_panel_applies_only_frozen_zero_policy() -> None:
    panel = prepare_confirmatory_panel(_calendar_support(), _policy())

    assert len(panel) == 6
    assert panel["clinic_id"].unique().tolist() == ["A", "B"]
    assert panel["visits"].tolist() == [5, 0, 0, 7, 0, 0]


def test_prepare_confirmatory_panel_rejects_incomplete_coverage() -> None:
    support = _calendar_support()
    support.loc[0, "complete_coverage"] = False
    with pytest.raises(ValueError, match="incomplete-coverage"):
        prepare_confirmatory_panel(support, _policy())


def test_origin_boundaries_validate_exact_frozen_windows() -> None:
    boundaries = origin_boundaries_from_policy(_policy())
    assert boundaries["origin"].tolist() == [1, 2]
    assert boundaries["train_end"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-03",
        "2024-01-05",
    ]


def test_origin_boundaries_reject_retroactive_step_change() -> None:
    policy = json.loads(json.dumps(_policy()))
    policy["validation"]["origins"][1]["test_start"] = "2024-01-07"
    with pytest.raises(ValueError, match="day after training ends|step size"):
        origin_boundaries_from_policy(policy)


def test_paired_model_contrasts_pair_only_on_outer_origin() -> None:
    fold_scores = pd.DataFrame(
        {
            "origin": [1, 2, 3, 1, 2, 3, 1, 2, 3],
            "model": [
                "seasonal_naive",
                "seasonal_naive",
                "seasonal_naive",
                "moving_average_28",
                "moving_average_28",
                "moving_average_28",
                "global_ml_hgb",
                "global_ml_hgb",
                "global_ml_hgb",
            ],
            "mae": [10.0, 10.0, 10.0, 8.0, 11.0, 10.0, 7.0, 8.0, 9.0],
            "wape": [20.0, 20.0, 20.0, 18.0, 21.0, 20.0, 17.0, 18.0, 19.0],
            "rmse": [12.0, 12.0, 12.0, 10.0, 13.0, 12.0, 9.0, 10.0, 11.0],
            "bias": [1.0, 1.0, 1.0, 0.0, 2.0, 1.0, -1.0, 0.0, 1.0],
        }
    )

    contrasts = paired_model_contrasts(fold_scores, expected_origins=3)
    hgb_mae = contrasts[(contrasts["model"] == "global_ml_hgb") & (contrasts["metric"] == "mae")].iloc[0]
    assert hgb_mae["negative_count"] == 3
    assert hgb_mae["positive_count"] == 0
    assert hgb_mae["zero_count"] == 0
    assert hgb_mae["dominant_nonzero_sign"] == "negative"
    assert hgb_mae["exact_two_sided_sign_test_p"] == pytest.approx(0.25)
