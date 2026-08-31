"""Prospective benchmark for the frozen capacity-aware hybrid policy."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from clinic_forecast.capacity import add_capacity_targets
from clinic_forecast.hybrid_policy import select_hybrid_clinical_forecast
from clinic_forecast.role_specific import (
    CLINICAL_TARGET,
    FRONTDESK_TARGET,
    calibrate_target_intervals,
    recursive_target_forecast,
)
from clinic_forecast.staffing import (
    StaffingCosts,
    StaffingRules,
    recommend_staffing,
    staffing_plan_cost,
)
from clinic_forecast.validation import RollingOriginSplitter

COMPLETED_TARGET = "visits"


@dataclass(frozen=True)
class HybridPolicyBenchmarkConfig:
    initial_train_days: int = 365 * 3
    horizon_days: int = 28
    max_folds: int = 4
    estimator: str = "hgb"
    coverage: float = 0.9
    inner_initial_train_days: int = 365 * 2
    inner_folds: int = 4


def _staff_policy(
    frame: pd.DataFrame,
    clinical_col: str,
    rules: StaffingRules,
) -> pd.DataFrame:
    no_buffer = StaffingRules(**{**rules.__dict__, "buffer_ratio": 0.0})
    clinical = recommend_staffing(frame, forecast_col=clinical_col, rules=no_buffer)
    frontdesk = recommend_staffing(
        frame,
        forecast_col="forecast_scheduled_target",
        rules=no_buffer,
    )
    plan = frame.copy()
    plan["recommended_clinicians"] = clinical["recommended_clinicians"]
    plan["recommended_nurses"] = clinical["recommended_nurses"]
    plan["recommended_frontdesk"] = frontdesk["recommended_frontdesk"]
    closed = ~plan["is_open"].astype(bool)
    staffing_cols = [
        "recommended_clinicians",
        "recommended_nurses",
        "recommended_frontdesk",
    ]
    plan.loc[closed, staffing_cols] = 0
    return plan


def _score(costed: pd.DataFrame) -> dict[str, float | int]:
    return {
        "n_obs": int(len(costed)),
        "total_cost": float(costed["total_cost"].sum()),
        "regular_cost": float(costed["regular_cost"].sum()),
        "overtime_cost": float(costed["overtime_cost"].sum()),
        "understaffing_cost": float(costed["understaffing_cost"].sum()),
        "idle_cost": float(costed["idle_cost"].sum()),
        "unmet_visits": float(costed["unmet_visits"].sum()),
        "understaffed_rate": float((costed["unmet_visits"] > 0).mean()),
        "capacity_pressure_rate": float(costed["capacity_pressure"].mean()),
        "clinician_days": int(costed["recommended_clinicians"].sum()),
        "nurse_days": int(costed["recommended_nurses"].sum()),
    }


def run_hybrid_policy_benchmark(
    usage: pd.DataFrame,
    metadata: pd.DataFrame,
    config: HybridPolicyBenchmarkConfig | None = None,
    rules: StaffingRules | None = None,
    costs: StaffingCosts | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare the frozen hybrid policy with both pure target policies."""
    cfg = config or HybridPolicyBenchmarkConfig()
    staffing_rules = rules or StaffingRules()
    cost_model = costs or StaffingCosts()
    enriched = add_capacity_targets(usage)
    capacity = metadata[["clinic_id", "daily_capacity"]].copy()
    splitter = RollingOriginSplitter(
        initial_train_days=cfg.initial_train_days,
        horizon_days=cfg.horizon_days,
        max_folds=cfg.max_folds,
    )

    score_rows: list[dict[str, object]] = []
    decision_rows: list[pd.DataFrame] = []
    for train, test, fold in splitter.split(enriched):
        completed_intervals, _ = calibrate_target_intervals(
            train,
            target_col=COMPLETED_TARGET,
            estimator=cfg.estimator,  # type: ignore[arg-type]
            coverage=cfg.coverage,
            initial_train_days=cfg.inner_initial_train_days,
            horizon_days=cfg.horizon_days,
            max_folds=cfg.inner_folds,
        )
        forecasts: dict[str, pd.DataFrame] = {}
        for target in (CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET):
            forecasts[target] = recursive_target_forecast(
                train=train,
                test=test,
                target_col=target,
                estimator=cfg.estimator,  # type: ignore[arg-type]
            )

        completed = completed_intervals.apply(forecasts[COMPLETED_TARGET]).rename(
            columns={"y_upper": "completed_upper"}
        )
        paired = test[
            ["clinic_id", "date", "is_open", CLINICAL_TARGET, "capacity_censored"]
        ].copy()
        paired = paired.merge(capacity, on="clinic_id", how="left")
        paired = paired.merge(
            forecasts[CLINICAL_TARGET][["clinic_id", "date", "forecast"]].rename(
                columns={"forecast": "forecast_attended_target"}
            ),
            on=["clinic_id", "date"],
        ).merge(
            completed[["clinic_id", "date", "forecast", "completed_upper"]].rename(
                columns={"forecast": "forecast_completed_target"}
            ),
            on=["clinic_id", "date"],
        ).merge(
            forecasts[FRONTDESK_TARGET][["clinic_id", "date", "forecast"]].rename(
                columns={"forecast": "forecast_scheduled_target"}
            ),
            on=["clinic_id", "date"],
        )
        paired = select_hybrid_clinical_forecast(paired)
        paired["fold"] = fold.fold_id

        policy_columns = {
            "attended_demand": "forecast_attended_target",
            "completed_visits": "forecast_completed_target",
            "hybrid": "hybrid_clinical_forecast",
        }
        for policy, forecast_col in policy_columns.items():
            plan = _staff_policy(paired, forecast_col, staffing_rules)
            costed = staffing_plan_cost(
                plan,
                demand_col=CLINICAL_TARGET,
                rules=staffing_rules,
                costs=cost_model,
            )
            costed["policy"] = policy
            costed["fold"] = fold.fold_id
            decision_rows.append(costed)
            for slice_name, frame in {
                "all": costed,
                "censored": costed[costed["capacity_censored"] == 1],
                "uncensored": costed[costed["capacity_censored"] == 0],
            }.items():
                score_rows.append(
                    {
                        "fold": fold.fold_id,
                        "policy": policy,
                        "slice": slice_name,
                        **_score(frame),
                    }
                )

    return pd.DataFrame(score_rows), pd.concat(decision_rows, ignore_index=True)


def summarize_hybrid_policy_benchmark(scores: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "total_cost",
        "regular_cost",
        "overtime_cost",
        "understaffing_cost",
        "idle_cost",
        "unmet_visits",
        "understaffed_rate",
        "capacity_pressure_rate",
        "clinician_days",
        "nurse_days",
    ]
    grouped = scores.groupby(["policy", "slice"], observed=True)[metrics]
    return (
        grouped.mean().add_suffix("_mean")
        .join(grouped.std().add_suffix("_std"))
        .join(grouped.size().rename("n_folds"))
        .reset_index()
    )


__all__ = [
    "HybridPolicyBenchmarkConfig",
    "run_hybrid_policy_benchmark",
    "summarize_hybrid_policy_benchmark",
]
