from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.models.global_ml import GlobalMLForecaster
from clinic_forecast.pipelines.batch_inference import make_future_frame
from clinic_forecast.scenarios import (
    MarketingScenario,
    apply_marketing_scenario,
    scenario_forecasts,
    scenario_staffing_impact,
)


@pytest.fixture(scope="module")
def network():
    return generate_network_data(
        SyntheticDataConfig(start_date="2024-01-01", end_date="2024-09-30", n_clinics=4)
    )


@pytest.fixture(scope="module")
def future(network) -> pd.DataFrame:
    return make_future_frame(network.usage, network.metadata, horizon_days=7)


def test_spend_multiplier_scales_selected_clinics_only(future) -> None:
    target = future["clinic_id"].iloc[0]
    scenario = MarketingScenario(name="boost", spend_multiplier=2.0, clinic_ids=(target,))
    edited = apply_marketing_scenario(future, scenario)

    boosted = edited[edited["clinic_id"] == target]["marketing_spend"]
    original = future[future["clinic_id"] == target]["marketing_spend"]
    pd.testing.assert_series_equal(boosted, original * 2.0, check_names=False)

    untouched_ids = future["clinic_id"] != target
    pd.testing.assert_series_equal(
        edited.loc[untouched_ids, "marketing_spend"],
        future.loc[untouched_ids, "marketing_spend"],
    )


def test_channel_restriction_recomputes_total(future) -> None:
    scenario = MarketingScenario(name="search_only", spend_multiplier=3.0, channels=("search",))
    edited = apply_marketing_scenario(future, scenario)
    expected = future["spend_search"] * 3.0 + future[
        ["spend_social", "spend_email", "spend_local"]
    ].sum(axis=1)
    pd.testing.assert_series_equal(
        edited["marketing_spend"], expected, check_names=False
    )


def test_region_scenario_sets_campaign_flag(network, future) -> None:
    region = network.metadata["region"].iloc[0]
    scenario = MarketingScenario(name="regional", regions=(region,), set_campaign_active=True)
    edited = apply_marketing_scenario(future, scenario, metadata=network.metadata)

    region_clinics = set(
        network.metadata[network.metadata["region"] == region]["clinic_id"]
    )
    flagged = edited[edited["clinic_id"].isin(region_clinics)]
    assert (flagged["campaign_active"] == 1).all()


def test_unknown_targets_raise(future) -> None:
    with pytest.raises(ValueError, match="Unknown clinic_ids"):
        apply_marketing_scenario(
            future, MarketingScenario(name="x", clinic_ids=("NOPE",))
        )
    with pytest.raises(ValueError, match="Unknown spend channels"):
        apply_marketing_scenario(
            future, MarketingScenario(name="x", channels=("radio",))
        )


def test_invalid_scenario_rejected() -> None:
    with pytest.raises(ValueError, match="spend_multiplier"):
        MarketingScenario(name="bad", spend_multiplier=-1.0).validate()


def test_scenario_forecasts_are_reproducible_and_complete(network, future) -> None:
    model = GlobalMLForecaster().fit(network.usage)
    scenarios = [MarketingScenario(name="double_spend", spend_multiplier=2.0)]

    first = scenario_forecasts(model, network.usage, future, scenarios)
    second = scenario_forecasts(model, network.usage, future, scenarios)
    pd.testing.assert_frame_equal(first, second)

    assert set(first["scenario"]) == {"baseline", "double_spend"}
    baseline_rows = first[first["scenario"] == "baseline"]
    assert (baseline_rows["incremental_visits"] == 0).all()
    assert len(first) == 2 * len(future)


def test_staffing_impact_has_baseline_delta_zero(network, future) -> None:
    model = GlobalMLForecaster().fit(network.usage)
    forecasts = scenario_forecasts(
        model, network.usage, future,
        [MarketingScenario(name="half_spend", spend_multiplier=0.5)],
    )
    impact = scenario_staffing_impact(forecasts)
    baseline = impact.set_index("scenario").loc["baseline"]
    assert baseline["clinician_day_delta"] == 0
    assert set(impact["scenario"]) == {"baseline", "half_spend"}
