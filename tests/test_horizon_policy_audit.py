from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.horizon_policy_audit import (
    EXPECTED_HORIZONS,
    EXPECTED_OUTER_ORIGINS,
    aggregate_origin_horizon_policy,
    assign_horizon_index,
    exact_sign_test_pvalue,
    horizon_qualitative_flags,
    paired_horizon_contrasts,
    summarize_horizon_uncertainty,
    summarize_weekly_bands,
)


def _synthetic_decisions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for fold in range(1, EXPECTED_OUTER_ORIGINS + 1):
        start = pd.Timestamp("2025-01-01") + pd.Timedelta(days=(fold - 1) * 28)
        for horizon in range(1, EXPECTED_HORIZONS + 1):
            date = start + pd.Timedelta(days=horizon - 1)
            for policy, cost_shift, unmet_shift in (
                ("attended_demand", 20.0, -1.0),
                ("completed_visits", 0.0, 2.0),
                ("hybrid", 10.0, 0.0),
            ):
                rows.append(
                    {
                        "fold": fold,
                        "date": date,
                        "policy": policy,
                        "total_cost": 100.0 + cost_shift,
                        "regular_cost": 80.0,
                        "overtime_cost": 5.0,
                        "understaffing_cost": 10.0,
                        "idle_cost": 5.0,
                        "unmet_visits": 5.0 + unmet_shift,
                        "recommended_clinicians": 2,
                        "recommended_nurses": 3,
                        "capacity_pressure": int(horizon % 2 == 0),
                        "capacity_censored": int(horizon % 3 == 0),
                    }
                )
    return pd.DataFrame(rows)


def test_assign_horizon_index_requires_full_13_by_28_shape() -> None:
    decisions = _synthetic_decisions()
    assigned = assign_horizon_index(decisions)
    assert assigned["fold"].nunique() == EXPECTED_OUTER_ORIGINS
    assert assigned.groupby("fold")["horizon"].nunique().eq(EXPECTED_HORIZONS).all()

    truncated = decisions[~((decisions["fold"] == 13) & (decisions["date"] == decisions["date"].max()))]
    with pytest.raises(ValueError, match="13 origins with exactly 28 horizons"):
        assign_horizon_index(truncated)


def test_exact_sign_test_excludes_zero_differences() -> None:
    values = pd.Series([-1.0, -2.0, 0.0, 3.0])
    assert exact_sign_test_pvalue(values) == pytest.approx(1.0)
    assert exact_sign_test_pvalue(pd.Series([-1.0] * 13)) == pytest.approx(2 / 8192)


def test_horizon_aggregates_and_contrasts_use_origin_pairing() -> None:
    assigned = assign_horizon_index(_synthetic_decisions())
    aggregates = aggregate_origin_horizon_policy(assigned)
    assert len(aggregates) == EXPECTED_OUTER_ORIGINS * EXPECTED_HORIZONS * 3

    contrasts = paired_horizon_contrasts(aggregates)
    assert len(contrasts) == EXPECTED_OUTER_ORIGINS * EXPECTED_HORIZONS * 4
    uncertainty = summarize_horizon_uncertainty(contrasts)
    assert uncertainty["n_origins"].eq(EXPECTED_OUTER_ORIGINS).all()

    flags = horizon_qualitative_flags(uncertainty)
    assert flags["both_original_directions"].all()
    assert len(flags) == EXPECTED_HORIZONS


def test_weekly_bands_are_preregistered_four_week_blocks() -> None:
    assigned = assign_horizon_index(_synthetic_decisions())
    aggregates = aggregate_origin_horizon_policy(assigned)
    contrasts = paired_horizon_contrasts(aggregates)
    weekly = summarize_weekly_bands(contrasts)
    assert set(weekly["band"]) == {"week_1", "week_2", "week_3", "week_4"}
    assert weekly["n_origins"].eq(EXPECTED_OUTER_ORIGINS).all()
