"""Paired decision benchmark for clinical staffing target choice."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from clinic_forecast.capacity import add_capacity_targets
from clinic_forecast.role_specific import (
    CLINICAL_TARGET,
    FRONTDESK_TARGET,
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
class StaffingDecisionBenchmarkConfig:
    initial_train_days: int = 365 * 3
    horizon_days: int = 28
    max_folds: int = 4
    estimator: str = "hgb"


def _zero_closed_staffing(plan: pd.DataFrame, is_open: pd.Series) -> pd.DataFrame:
    frame = plan.copy()
    cols = ["recommended_clinicians", "recommended_nurses", "recommended_frontdesk"]
    frame.loc[~is_open.astype(bool).to_numpy(), cols] = 0
    return frame


def _build_policy(
    paired: pd.DataFrame,
    clinical_forecast_col: str,
    rules: StaffingRules,
) -> pd.DataFrame:
    no_buffer = StaffingRules(**{**rules.__dict__, "buffer_ratio": 0.0})
    clinical = recommend_staffing(paired, forecast_col=clinical_forecast_col, rules=no_buffer)
    frontdesk = recommend_staffing(paired, forecast_col="forecast_scheduled_target", rules=no_buffer)
    plan = paired.copy()
    plan["recommended_clinicians"] = clinical["recommended_clinicians"]
    plan["recommended_nurses"] = clinical["recommended_nurses"]
    plan["recommended_frontdesk"] = frontdesk["recommended_frontdesk"]
    return _zero_closed_staffing(plan, paired["is_open"])


def _score_costed(costed: pd.DataFrame) -> dict[str, float | int]:
    n = len(costed)
    return {
        "n_obs": int(n),
        "regular_cost": float(costed["regular_cost"].sum()),
        "overtime_cost": float(costed["overtime_cost"].sum()),
        "understaffing_cost": float(costed["understaffing_cost"].sum()),
        "idle_cost": float(costed["idle_cost"].sum()),
        "total_cost": float(costed["total_cost"].sum()),
        "cost_per_day": float(costed["total_cost"].mean()) if n else float("nan"),
        "unmet_visits": float(costed["unmet_visits"].sum()),
        "understaffed_rate": float((costed["unmet_visits"] > 0).mean()) if n else float("nan"),
        "clinician_days": int(costed["recommended_clinicians"].sum()),
        "nurse_days": int(costed["recommended_nurses"].sum()),
        "frontdesk_days": int(costed["recommended_frontdesk"].sum()),
    }


def run_staffing_decision_benchmark(
    usage: pd.DataFrame,
    config: StaffingDecisionBenchmarkConfig | None = None,
    rules: StaffingRules | None = None,
    costs: StaffingCosts | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare completed-visit vs attended-demand clinical staffing policies."""
    cfg = config or StaffingDecisionBenchmarkConfig()
    staffing_rules = rules or StaffingRules()
    cost_model = costs or StaffingCosts()
    enriched = add_capacity_targets(usage)
    splitter = RollingOriginSplitter(
        initial_train_days=cfg.initial_train_days,
        horizon_days=cfg.horizon_days,
        max_folds=cfg.max_folds,
    )

    score_rows: list[dict[str, object]] = []
    decision_rows: list[pd.DataFrame] = []
    for train, test, fold in splitter.split(enriched):
        forecasts: dict[str, pd.DataFrame] = {}
        for target in (CLINICAL_TARGET, COMPLETED_TARGET, FRONTDESK_TARGET):
            forecasts[target] = recursive_target_forecast(
                train=train,
                test=test,
                target_col=target,
                estimator=cfg.estimator,  # type: ignore[arg-type]
            )

        paired = test[
            [
                "clinic_id",
                "date",
                "is_open",
                CLINICAL_TARGET,
                "capacity_censored",
            ]
        ].copy()
        paired = paired.merge(
            forecasts[CLINICAL_TARGET][["clinic_id", "date", "forecast"]].rename(
                columns={"forecast": "forecast_attended_target"}
            ),
            on=["clinic_id", "date"],
        ).merge(
            forecasts[COMPLETED_TARGET][["clinic_id", "date", "forecast"]].rename(
                columns={"forecast": "forecast_completed_target"}
            ),
            on=["clinic_id", "date"],
        ).merge(
            forecasts[FRONTDESK_TARGET][["clinic_id", "date", "forecast"]].rename(
                columns={"forecast": "forecast_scheduled_target"}
            ),
            on=["clinic_id", "date"],
        )
        paired["fold"] = fold.fold_id
        paired["horizon_days"] = (pd.to_datetime(paired["date"]) - fold.train_end).dt.days

        policies = {
            "attended_demand": _build_policy(
                paired, "forecast_attended_target", staffing_rules
            ),
            "completed_visits": _build_policy(
                paired, "forecast_completed_target", staffing_rules
            ),
        }
        for policy_name, plan in policies.items():
            costed = staffing_plan_cost(
                plan,
                demand_col=CLINICAL_TARGET,
                rules=staffing_rules,
                costs=cost_model,
            )
            costed["policy"] = policy_name
            costed["fold"] = fold.fold_id
            decision_rows.append(costed)
            slices = {
                "all": costed,
                "censored": costed[costed["capacity_censored"] == 1],
                "uncensored": costed[costed["capacity_censored"] == 0],
            }
            for slice_name, frame in slices.items():
                score_rows.append(
                    {
                        "fold": fold.fold_id,
                        "policy": policy_name,
                        "slice": slice_name,
                        **_score_costed(frame),
                    }
                )

    return pd.DataFrame(score_rows), pd.concat(decision_rows, ignore_index=True)


def summarize_staffing_decision_benchmark(scores: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "total_cost",
        "cost_per_day",
        "regular_cost",
        "overtime_cost",
        "understaffing_cost",
        "idle_cost",
        "unmet_visits",
        "understaffed_rate",
        "clinician_days",
        "nurse_days",
        "frontdesk_days",
    ]
    grouped = scores.groupby(["policy", "slice"], observed=True)[metrics]
    return (
        grouped.mean().add_suffix("_mean")
        .join(grouped.std().add_suffix("_std"))
        .join(grouped.size().rename("n_folds"))
        .reset_index()
    )


__all__ = [
    "StaffingDecisionBenchmarkConfig",
    "run_staffing_decision_benchmark",
    "summarize_staffing_decision_benchmark",
]
