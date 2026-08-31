"""Robustness replication for the frozen capacity-aware hybrid policy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.hybrid_benchmark import (
    HybridPolicyBenchmarkConfig,
    run_hybrid_policy_benchmark,
    summarize_hybrid_policy_benchmark,
)
from clinic_forecast.staffing import StaffingCosts, StaffingRules

ROBUSTNESS_SEEDS: tuple[int, ...] = (42, 142, 242, 342)
ROBUSTNESS_CAPACITY_MULTIPLIERS: tuple[float, ...] = (0.8, 1.0, 1.2)
REFERENCE_SEED = 42
REFERENCE_CAPACITY_MULTIPLIER = 1.0


@dataclass(frozen=True)
class HybridRobustnessCellResult:
    """One frozen seed/capacity robustness cell."""

    scores: pd.DataFrame
    decisions: pd.DataFrame
    summary: pd.DataFrame
    cell_summary: pd.DataFrame


def capacity_label(multiplier: float) -> str:
    """Return a stable filename-safe capacity label."""
    return f"{multiplier:.1f}".replace(".", "p")


def apply_capacity_counterfactual(
    usage: pd.DataFrame,
    metadata: pd.DataFrame,
    capacity_multiplier: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Change only capacity-dependent fields after latent demand is generated."""
    if capacity_multiplier <= 0:
        raise ValueError("capacity_multiplier must be positive.")

    usage_required = {
        "clinic_id",
        "scheduled_appointments",
        "no_show_count",
        "same_day_cancellations",
        "visits",
        "daily_capacity",
        "capacity_utilization",
    }
    metadata_required = {"clinic_id", "daily_capacity"}
    usage_missing = usage_required.difference(usage.columns)
    metadata_missing = metadata_required.difference(metadata.columns)
    if usage_missing:
        raise ValueError(f"Usage missing required columns: {sorted(usage_missing)}")
    if metadata_missing:
        raise ValueError(f"Metadata missing required columns: {sorted(metadata_missing)}")

    adjusted_metadata = metadata.copy()
    scaled_capacity = np.floor(
        adjusted_metadata["daily_capacity"].astype(float) * capacity_multiplier + 0.5
    )
    adjusted_metadata["daily_capacity"] = np.maximum(1, scaled_capacity).astype(int)
    capacity_by_clinic = adjusted_metadata.set_index("clinic_id")["daily_capacity"]

    adjusted_usage = usage.copy()
    adjusted_usage["daily_capacity"] = adjusted_usage["clinic_id"].map(capacity_by_clinic)
    if adjusted_usage["daily_capacity"].isna().any():
        raise ValueError("Usage contains clinic_id values absent from metadata.")
    adjusted_usage["daily_capacity"] = adjusted_usage["daily_capacity"].astype(int)

    attended = (
        adjusted_usage["scheduled_appointments"].astype(int)
        - adjusted_usage["no_show_count"].astype(int)
        - adjusted_usage["same_day_cancellations"].astype(int)
    ).clip(lower=0)
    adjusted_usage["visits"] = np.minimum(
        attended.to_numpy(dtype=int),
        adjusted_usage["daily_capacity"].to_numpy(dtype=int),
    )
    adjusted_usage["capacity_utilization"] = (
        adjusted_usage["visits"] / adjusted_usage["daily_capacity"]
    )
    return adjusted_usage, adjusted_metadata


def _pct_change(value: float, reference: float) -> float:
    if reference == 0:
        return float("nan")
    return 100.0 * (value / reference - 1.0)


def _slice_metrics(
    summary: pd.DataFrame,
    policy: str,
    slice_name: str,
) -> pd.Series:
    row = summary[(summary["policy"] == policy) & (summary["slice"] == slice_name)]
    if len(row) != 1:
        raise ValueError(f"Expected one summary row for {policy}/{slice_name}, got {len(row)}.")
    return row.iloc[0]


def _strictly_dominates(
    summary: pd.DataFrame,
    candidate: str,
    comparators: tuple[str, ...],
    slice_name: str,
) -> bool:
    candidate_row = _slice_metrics(summary, candidate, slice_name)
    for comparator in comparators:
        comparator_row = _slice_metrics(summary, comparator, slice_name)
        if not (
            float(candidate_row["total_cost_mean"]) < float(comparator_row["total_cost_mean"])
            and float(candidate_row["unmet_visits_mean"])
            < float(comparator_row["unmet_visits_mean"])
        ):
            return False
    return True


def summarize_robustness_cell(
    seed: int,
    capacity_multiplier: float,
    scores: pd.DataFrame,
    decisions: pd.DataFrame,
) -> pd.DataFrame:
    """Create the preregistered one-row result for one robustness cell."""
    summary = summarize_hybrid_policy_benchmark(scores)
    attended = _slice_metrics(summary, "attended_demand", "all")
    completed = _slice_metrics(summary, "completed_visits", "all")
    hybrid = _slice_metrics(summary, "hybrid", "all")

    attended_cost = float(attended["total_cost_mean"])
    completed_cost = float(completed["total_cost_mean"])
    hybrid_cost = float(hybrid["total_cost_mean"])
    attended_unmet = float(attended["unmet_visits_mean"])
    completed_unmet = float(completed["unmet_visits_mean"])
    hybrid_unmet = float(hybrid["unmet_visits_mean"])

    hybrid_rows = decisions[decisions["policy"] == "hybrid"].copy()
    if hybrid_rows.empty:
        raise ValueError("Hybrid decisions are missing from the robustness cell.")
    censoring = hybrid_rows["capacity_censored"].astype(bool)
    pressure = hybrid_rows["capacity_pressure"].astype(bool)
    censored = hybrid_rows[censoring]
    uncensored = hybrid_rows[~censoring]

    qualitative_replication = hybrid_unmet < completed_unmet and hybrid_cost < attended_cost
    censored_pareto = _strictly_dominates(
        summary,
        "hybrid",
        ("attended_demand", "completed_visits"),
        "censored",
    )

    return pd.DataFrame(
        [
            {
                "seed": seed,
                "capacity_multiplier": capacity_multiplier,
                "is_reference_cell": (
                    seed == REFERENCE_SEED
                    and capacity_multiplier == REFERENCE_CAPACITY_MULTIPLIER
                ),
                "qualitative_replication": qualitative_replication,
                "attended_total_cost_mean": attended_cost,
                "completed_total_cost_mean": completed_cost,
                "hybrid_total_cost_mean": hybrid_cost,
                "attended_unmet_visits_mean": attended_unmet,
                "completed_unmet_visits_mean": completed_unmet,
                "hybrid_unmet_visits_mean": hybrid_unmet,
                "hybrid_vs_completed_cost_change_pct": _pct_change(
                    hybrid_cost, completed_cost
                ),
                "hybrid_vs_completed_unmet_change_pct": _pct_change(
                    hybrid_unmet, completed_unmet
                ),
                "hybrid_vs_attended_cost_change_pct": _pct_change(
                    hybrid_cost, attended_cost
                ),
                "hybrid_vs_attended_unmet_change_pct": _pct_change(
                    hybrid_unmet, attended_unmet
                ),
                "censoring_rate": float(censoring.mean()),
                "capacity_pressure_rate": float(pressure.mean()),
                "trigger_sensitivity_censored": (
                    float(censored["capacity_pressure"].mean())
                    if not censored.empty
                    else float("nan")
                ),
                "trigger_false_positive_rate_uncensored": (
                    float(uncensored["capacity_pressure"].mean())
                    if not uncensored.empty
                    else float("nan")
                ),
                "hybrid_pareto_dominates_both_censored": censored_pareto,
            }
        ]
    )


def run_hybrid_robustness_cell(
    seed: int,
    capacity_multiplier: float,
    benchmark_config: HybridPolicyBenchmarkConfig | None = None,
    rules: StaffingRules | None = None,
    costs: StaffingCosts | None = None,
) -> HybridRobustnessCellResult:
    """Generate and evaluate one preregistered seed/capacity cell."""
    if seed not in ROBUSTNESS_SEEDS:
        raise ValueError(f"Seed {seed} is outside the frozen robustness matrix.")
    if capacity_multiplier not in ROBUSTNESS_CAPACITY_MULTIPLIERS:
        raise ValueError(
            f"Capacity multiplier {capacity_multiplier} is outside the frozen robustness matrix."
        )

    generator_config = SyntheticDataConfig(random_seed=seed)
    network = generate_network_data(generator_config)
    usage, metadata = apply_capacity_counterfactual(
        network.usage,
        network.metadata,
        capacity_multiplier,
    )
    scores, decisions = run_hybrid_policy_benchmark(
        usage=usage,
        metadata=metadata,
        config=benchmark_config or HybridPolicyBenchmarkConfig(),
        rules=rules,
        costs=costs,
    )
    summary = summarize_hybrid_policy_benchmark(scores)
    cell_summary = summarize_robustness_cell(
        seed=seed,
        capacity_multiplier=capacity_multiplier,
        scores=scores,
        decisions=decisions,
    )
    return HybridRobustnessCellResult(
        scores=scores,
        decisions=decisions,
        summary=summary,
        cell_summary=cell_summary,
    )


def aggregate_robustness_cells(cells: list[pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate and aggregate the complete frozen 12-cell evidence table."""
    if not cells:
        raise ValueError("No robustness cells were supplied.")
    table = pd.concat(cells, ignore_index=True)
    expected = {
        (seed, multiplier)
        for seed in ROBUSTNESS_SEEDS
        for multiplier in ROBUSTNESS_CAPACITY_MULTIPLIERS
    }
    observed = {
        (int(row.seed), float(row.capacity_multiplier))
        for row in table[["seed", "capacity_multiplier"]].itertuples(index=False)
    }
    if observed != expected or len(table) != len(expected):
        missing = sorted(expected.difference(observed))
        extra = sorted(observed.difference(expected))
        raise ValueError(
            "Robustness evidence must contain each frozen cell exactly once; "
            f"missing={missing}, extra={extra}, rows={len(table)}."
        )

    table = table.sort_values(["seed", "capacity_multiplier"]).reset_index(drop=True)
    new_cells = table[~table["is_reference_cell"].astype(bool)]
    overview = pd.DataFrame(
        [
            {
                "n_cells": int(len(table)),
                "n_qualitative_replications": int(
                    table["qualitative_replication"].astype(bool).sum()
                ),
                "all_cells_replicate": bool(
                    table["qualitative_replication"].astype(bool).all()
                ),
                "n_new_cells": int(len(new_cells)),
                "n_new_qualitative_replications": int(
                    new_cells["qualitative_replication"].astype(bool).sum()
                ),
                "all_new_cells_replicate": bool(
                    new_cells["qualitative_replication"].astype(bool).all()
                ),
            }
        ]
    )
    return table, overview


__all__ = [
    "REFERENCE_CAPACITY_MULTIPLIER",
    "REFERENCE_SEED",
    "ROBUSTNESS_CAPACITY_MULTIPLIERS",
    "ROBUSTNESS_SEEDS",
    "HybridRobustnessCellResult",
    "aggregate_robustness_cells",
    "apply_capacity_counterfactual",
    "capacity_label",
    "run_hybrid_robustness_cell",
    "summarize_robustness_cell",
]
