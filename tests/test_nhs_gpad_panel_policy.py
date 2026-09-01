from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

POLICY_PATH = Path("config/nhs_gpad_panel_policy.json")


def _policy() -> dict[str, object]:
    loaded = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_frozen_panel_dimensions_and_geography_partition() -> None:
    policy = _policy()
    geography = policy["geography_policy"]
    assert isinstance(geography, dict)
    codes = geography["eligible_sub_icb_codes"]
    assert isinstance(codes, list)

    assert len(codes) == 31
    assert len(set(codes)) == 31
    assert geography["eligible_geographies"] == 31
    assert geography["excluded_geographies"] == 75
    assert policy["calendar_days"] == 912
    assert policy["panel_rows"] == 31 * 912 == 28272


def test_frozen_support_counts_cover_panel() -> None:
    policy = _policy()
    support = policy["support_counts_within_eligible_panel"]
    assert isinstance(support, dict)
    assert (
        support["attended_present"]
        + support["other_status_only"]
        + support["no_published_rows"]
        == policy["panel_rows"]
    )


def test_frozen_outer_origins_recompute_exactly() -> None:
    policy = _policy()
    validation = policy["validation"]
    assert isinstance(validation, dict)
    origins = validation["origins"]
    assert isinstance(origins, list)

    start = date.fromisoformat(str(policy["date_start"]))
    horizon = int(validation["forecast_horizon_days"])
    step = int(validation["step_days"])
    initial = int(validation["initial_training_days"])

    assert len(origins) == validation["outer_origins"] == 19
    for index, origin_raw in enumerate(origins, start=1):
        assert isinstance(origin_raw, dict)
        expected_train_end = start + timedelta(days=initial - 1 + step * (index - 1))
        expected_test_start = expected_train_end + timedelta(days=1)
        expected_test_end = expected_test_start + timedelta(days=horizon - 1)

        assert origin_raw["origin"] == index
        assert date.fromisoformat(str(origin_raw["train_end"])) == expected_train_end
        assert date.fromisoformat(str(origin_raw["test_start"])) == expected_test_start
        assert date.fromisoformat(str(origin_raw["test_end"])) == expected_test_end

    final_end = date.fromisoformat(str(origins[-1]["test_end"]))
    source_end = date.fromisoformat(str(policy["date_end"]))
    assert (source_end - final_end).days == 15
