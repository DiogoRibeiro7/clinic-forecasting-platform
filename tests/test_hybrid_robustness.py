from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.hybrid_robustness import (
    ROBUSTNESS_CAPACITY_MULTIPLIERS,
    ROBUSTNESS_SEEDS,
    aggregate_robustness_cells,
    apply_capacity_counterfactual,
)


def _cell(seed: int, capacity: float, replicate: bool = True) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "seed": seed,
                "capacity_multiplier": capacity,
                "is_reference_cell": seed == 42 and capacity == 1.0,
                "qualitative_replication": replicate,
            }
        ]
    )


def test_capacity_multiplier_one_preserves_reference_capacity_and_visits() -> None:
    network = generate_network_data(SyntheticDataConfig(random_seed=42))
    usage, metadata = apply_capacity_counterfactual(network.usage, network.metadata, 1.0)

    pd.testing.assert_series_equal(
        usage["daily_capacity"],
        network.usage["daily_capacity"],
        check_names=False,
    )
    pd.testing.assert_series_equal(
        usage["visits"],
        network.usage["visits"],
        check_names=False,
    )
    pd.testing.assert_series_equal(
        metadata["daily_capacity"],
        network.metadata["daily_capacity"],
        check_names=False,
    )


def test_capacity_counterfactual_preserves_latent_attended_components() -> None:
    network = generate_network_data(SyntheticDataConfig(random_seed=142))
    usage, _ = apply_capacity_counterfactual(network.usage, network.metadata, 0.8)

    for column in (
        "scheduled_appointments",
        "no_show_count",
        "same_day_cancellations",
    ):
        pd.testing.assert_series_equal(usage[column], network.usage[column], check_names=False)

    attended = (
        usage["scheduled_appointments"]
        - usage["no_show_count"]
        - usage["same_day_cancellations"]
    )
    assert (usage["visits"] <= attended).all()
    assert (usage["visits"] <= usage["daily_capacity"]).all()


def test_aggregate_requires_all_twelve_frozen_cells() -> None:
    cells = [
        _cell(seed, capacity)
        for seed in ROBUSTNESS_SEEDS
        for capacity in ROBUSTNESS_CAPACITY_MULTIPLIERS
    ]
    table, overview = aggregate_robustness_cells(cells)

    assert len(table) == 12
    assert overview.loc[0, "n_cells"] == 12
    assert overview.loc[0, "n_new_cells"] == 11
    assert bool(overview.loc[0, "all_cells_replicate"])

    with pytest.raises(ValueError, match="each frozen cell exactly once"):
        aggregate_robustness_cells(cells[:-1])


def test_aggregate_reports_failures_without_hiding_cells() -> None:
    cells = [
        _cell(seed, capacity, replicate=not (seed == 242 and capacity == 1.2))
        for seed in ROBUSTNESS_SEEDS
        for capacity in ROBUSTNESS_CAPACITY_MULTIPLIERS
    ]
    table, overview = aggregate_robustness_cells(cells)

    assert len(table) == 12
    assert overview.loc[0, "n_qualitative_replications"] == 11
    assert not bool(overview.loc[0, "all_cells_replicate"])
    assert overview.loc[0, "n_new_qualitative_replications"] == 10
    assert not bool(overview.loc[0, "all_new_cells_replicate"])
