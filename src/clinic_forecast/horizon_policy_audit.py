"""Horizon-resolved audit of the frozen capacity-aware hybrid policy."""

from __future__ import annotations

from dataclasses import dataclass
from math import comb

import pandas as pd

from clinic_forecast.hybrid_benchmark import (
    HybridPolicyBenchmarkConfig,
    run_hybrid_policy_benchmark,
)
from clinic_forecast.staffing import StaffingCosts, StaffingRules
from clinic_forecast.validation import RollingOriginSplitter

EXPECTED_OUTER_ORIGINS = 13
EXPECTED_HORIZONS = 28
PRIMARY_POLICIES = ("attended_demand", "completed_visits", "hybrid")
HORIZON_BANDS: tuple[tuple[str, int, int], ...] = (
    ("week_1", 1, 7),
    ("week_2", 8, 14),
    ("week_3", 15, 21),
    ("week_4", 22, 28),
)


@dataclass(frozen=True)
class HorizonPolicyAuditResult:
    """Machine-readable outputs of the frozen horizon-policy audit."""

    origin_boundaries: pd.DataFrame
    origin_horizon_policy: pd.DataFrame
    paired_contrasts: pd.DataFrame
    horizon_uncertainty: pd.DataFrame
    weekly_band_uncertainty: pd.DataFrame
    horizon_flags: pd.DataFrame


def exact_sign_test_pvalue(differences: pd.Series) -> float:
    """Two-sided exact sign-test p-value, excluding exact zero differences."""
    values = pd.to_numeric(differences, errors="raise").to_numpy(dtype=float)
    nonzero = values[values != 0.0]
    n = int(len(nonzero))
    if n == 0:
        return 1.0
    n_negative = int((nonzero < 0).sum())
    n_positive = n - n_negative
    tail = min(n_negative, n_positive)
    one_sided = sum(comb(n, k) for k in range(tail + 1)) / (2**n)
    return float(min(1.0, 2.0 * one_sided))


def _origin_boundaries(usage: pd.DataFrame) -> pd.DataFrame:
    splitter = RollingOriginSplitter(
        initial_train_days=1095,
        horizon_days=EXPECTED_HORIZONS,
        step_days=EXPECTED_HORIZONS,
        max_folds=None,
        window="expanding",
    )
    folds = splitter.folds(usage)
    if len(folds) != EXPECTED_OUTER_ORIGINS:
        raise ValueError(
            "Frozen horizon audit requires exactly "
            f"{EXPECTED_OUTER_ORIGINS} outer origins; got {len(folds)}."
        )
    return pd.DataFrame(
        [
            {
                "fold": fold.fold_id,
                "train_start": fold.train_start,
                "train_end": fold.train_end,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
            }
            for fold in folds
        ]
    )


def assign_horizon_index(decisions: pd.DataFrame) -> pd.DataFrame:
    """Assign horizon 1..28 from the ordered test dates within each outer origin."""
    required = {"fold", "date"}
    missing = required.difference(decisions.columns)
    if missing:
        raise ValueError(f"Decisions missing horizon keys: {sorted(missing)}")

    output = decisions.copy()
    output["date"] = pd.to_datetime(output["date"])
    unique_dates = (
        output[["fold", "date"]]
        .drop_duplicates()
        .sort_values(["fold", "date"])
        .reset_index(drop=True)
    )
    unique_dates["horizon"] = unique_dates.groupby("fold").cumcount() + 1
    counts = unique_dates.groupby("fold")["horizon"].max()
    if len(counts) != EXPECTED_OUTER_ORIGINS or not (counts == EXPECTED_HORIZONS).all():
        raise ValueError(
            "Frozen horizon audit requires 13 origins with exactly 28 horizons each; "
            f"observed={counts.to_dict()}."
        )
    return output.merge(unique_dates, on=["fold", "date"], how="left", validate="many_to_one")


def aggregate_origin_horizon_policy(decisions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate clinic-days within each origin/horizon/policy before comparison."""
    required = {
        "fold",
        "horizon",
        "policy",
        "total_cost",
        "regular_cost",
        "overtime_cost",
        "understaffing_cost",
        "idle_cost",
        "unmet_visits",
        "recommended_clinicians",
        "recommended_nurses",
        "capacity_pressure",
        "capacity_censored",
    }
    missing = required.difference(decisions.columns)
    if missing:
        raise ValueError(f"Decisions missing audit columns: {sorted(missing)}")

    frame = decisions.copy()
    frame["understaffed"] = (frame["unmet_visits"] > 0).astype(float)
    grouped = frame.groupby(["fold", "horizon", "policy"], observed=True)
    aggregate = grouped.agg(
        n_clinic_days=("unmet_visits", "size"),
        total_cost=("total_cost", "sum"),
        regular_cost=("regular_cost", "sum"),
        overtime_cost=("overtime_cost", "sum"),
        understaffing_cost=("understaffing_cost", "sum"),
        idle_cost=("idle_cost", "sum"),
        unmet_visits=("unmet_visits", "sum"),
        understaffed_rate=("understaffed", "mean"),
        clinician_days=("recommended_clinicians", "sum"),
        nurse_days=("recommended_nurses", "sum"),
        capacity_pressure_rate=("capacity_pressure", "mean"),
        hybrid_switch_rate=("capacity_pressure", "mean"),
        capacity_censoring_rate=("capacity_censored", "mean"),
    ).reset_index()

    observed_policies = set(aggregate["policy"].astype(str).unique())
    if observed_policies != set(PRIMARY_POLICIES):
        raise ValueError(f"Unexpected policy set: {sorted(observed_policies)}")
    expected_rows = EXPECTED_OUTER_ORIGINS * EXPECTED_HORIZONS * len(PRIMARY_POLICIES)
    if len(aggregate) != expected_rows:
        raise ValueError(
            f"Expected {expected_rows} origin/horizon/policy rows; got {len(aggregate)}."
        )
    return aggregate


def paired_horizon_contrasts(aggregates: pd.DataFrame) -> pd.DataFrame:
    """Create the four frozen origin-level cost/service contrasts for each horizon."""
    rows: list[dict[str, object]] = []
    for comparator in ("completed_visits", "attended_demand"):
        for outcome in ("total_cost", "unmet_visits"):
            pivot = aggregates.pivot(
                index=["fold", "horizon"],
                columns="policy",
                values=outcome,
            )
            if "hybrid" not in pivot.columns or comparator not in pivot.columns:
                raise ValueError(f"Missing policies for {comparator}/{outcome} contrast.")
            difference = pivot["hybrid"] - pivot[comparator]
            for (fold, horizon), value in difference.items():
                rows.append(
                    {
                        "fold": int(fold),
                        "horizon": int(horizon),
                        "comparator": comparator,
                        "outcome": outcome,
                        "difference": float(value),
                    }
                )
    contrasts = pd.DataFrame(rows)
    expected_rows = EXPECTED_OUTER_ORIGINS * EXPECTED_HORIZONS * 4
    if len(contrasts) != expected_rows:
        raise ValueError(f"Expected {expected_rows} paired contrasts; got {len(contrasts)}.")
    return contrasts.sort_values(["horizon", "comparator", "outcome", "fold"]).reset_index(
        drop=True
    )


def _summarize_difference_group(group: pd.DataFrame) -> pd.Series:
    values = group["difference"].astype(float)
    n_negative = int((values < 0).sum())
    n_positive = int((values > 0).sum())
    n_zero = int((values == 0).sum())
    n_nonzero = n_negative + n_positive
    sign_consistency = (
        max(n_negative, n_positive) / n_nonzero if n_nonzero > 0 else float("nan")
    )
    return pd.Series(
        {
            "n_origins": int(len(values)),
            "mean_difference": float(values.mean()),
            "median_difference": float(values.median()),
            "std_difference": float(values.std(ddof=1)),
            "min_difference": float(values.min()),
            "max_difference": float(values.max()),
            "n_negative": n_negative,
            "n_positive": n_positive,
            "n_zero": n_zero,
            "sign_consistency_rate": float(sign_consistency),
            "exact_sign_test_pvalue": exact_sign_test_pvalue(values),
        }
    )


def summarize_horizon_uncertainty(contrasts: pd.DataFrame) -> pd.DataFrame:
    """Summarise paired differences across the 13 outer origins at each horizon."""
    summary = (
        contrasts.groupby(["horizon", "comparator", "outcome"], observed=True)
        .apply(_summarize_difference_group, include_groups=False)
        .reset_index()
    )
    if not (summary["n_origins"] == EXPECTED_OUTER_ORIGINS).all():
        raise ValueError("Every horizon contrast must contain exactly 13 paired origins.")
    return summary


def _horizon_band(horizon: int) -> str:
    for label, start, end in HORIZON_BANDS:
        if start <= horizon <= end:
            return label
    raise ValueError(f"Horizon {horizon} is outside the frozen 1..28 range.")


def summarize_weekly_bands(contrasts: pd.DataFrame) -> pd.DataFrame:
    """Summarise additive cost/service contrasts within the four frozen horizon bands."""
    frame = contrasts.copy()
    frame["band"] = frame["horizon"].map(_horizon_band)
    origin_band = (
        frame.groupby(["fold", "band", "comparator", "outcome"], observed=True)["difference"]
        .sum()
        .reset_index()
    )
    summary = (
        origin_band.groupby(["band", "comparator", "outcome"], observed=True)
        .apply(_summarize_difference_group, include_groups=False)
        .reset_index()
    )
    if not (summary["n_origins"] == EXPECTED_OUTER_ORIGINS).all():
        raise ValueError("Every weekly-band contrast must contain exactly 13 paired origins.")
    order = {label: index for index, (label, _, _) in enumerate(HORIZON_BANDS)}
    summary["band_order"] = summary["band"].map(order)
    return summary.sort_values(["band_order", "comparator", "outcome"]).drop(
        columns="band_order"
    ).reset_index(drop=True)


def horizon_qualitative_flags(uncertainty: pd.DataFrame) -> pd.DataFrame:
    """Apply the original two qualitative directions independently at each horizon."""
    key = uncertainty.set_index(["horizon", "comparator", "outcome"])
    rows: list[dict[str, object]] = []
    for horizon in range(1, EXPECTED_HORIZONS + 1):
        service = float(
            key.loc[(horizon, "completed_visits", "unmet_visits"), "mean_difference"]
        )
        cost = float(key.loc[(horizon, "attended_demand", "total_cost"), "mean_difference"])
        lower_unmet = service < 0.0
        lower_cost = cost < 0.0
        rows.append(
            {
                "horizon": horizon,
                "hybrid_vs_completed_unmet_mean_difference": service,
                "hybrid_vs_attended_cost_mean_difference": cost,
                "lower_unmet_than_completed": lower_unmet,
                "lower_cost_than_attended": lower_cost,
                "both_original_directions": lower_unmet and lower_cost,
                "service_direction_reversal": not lower_unmet,
                "cost_direction_reversal": not lower_cost,
            }
        )
    return pd.DataFrame(rows)


def run_horizon_policy_audit(
    usage: pd.DataFrame,
    metadata: pd.DataFrame,
    rules: StaffingRules | None = None,
    costs: StaffingCosts | None = None,
) -> HorizonPolicyAuditResult:
    """Run the prospectively frozen 13-origin, 28-horizon policy audit."""
    origin_boundaries = _origin_boundaries(usage)
    config = HybridPolicyBenchmarkConfig(
        initial_train_days=1095,
        horizon_days=EXPECTED_HORIZONS,
        max_folds=EXPECTED_OUTER_ORIGINS,
        estimator="hgb",
        coverage=0.9,
        inner_initial_train_days=730,
        inner_folds=4,
    )
    _, decisions = run_hybrid_policy_benchmark(
        usage=usage,
        metadata=metadata,
        config=config,
        rules=rules,
        costs=costs,
    )
    decisions = assign_horizon_index(decisions)
    aggregates = aggregate_origin_horizon_policy(decisions)
    contrasts = paired_horizon_contrasts(aggregates)
    uncertainty = summarize_horizon_uncertainty(contrasts)
    weekly = summarize_weekly_bands(contrasts)
    flags = horizon_qualitative_flags(uncertainty)
    return HorizonPolicyAuditResult(
        origin_boundaries=origin_boundaries,
        origin_horizon_policy=aggregates,
        paired_contrasts=contrasts,
        horizon_uncertainty=uncertainty,
        weekly_band_uncertainty=weekly,
        horizon_flags=flags,
    )


__all__ = [
    "EXPECTED_HORIZONS",
    "EXPECTED_OUTER_ORIGINS",
    "HORIZON_BANDS",
    "HorizonPolicyAuditResult",
    "aggregate_origin_horizon_policy",
    "assign_horizon_index",
    "exact_sign_test_pvalue",
    "horizon_qualitative_flags",
    "paired_horizon_contrasts",
    "run_horizon_policy_audit",
    "summarize_horizon_uncertainty",
    "summarize_weekly_bands",
]
