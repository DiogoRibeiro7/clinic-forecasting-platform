"""Confirmatory benchmark for the frozen clinical staffing optimiser design."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from clinic_forecast.clinical_optimizer import optimize_clinical_staffing
from clinic_forecast.hybrid_benchmark import (
    HybridPolicyBenchmarkConfig,
    run_hybrid_policy_benchmark,
)
from clinic_forecast.role_specific import CLINICAL_TARGET
from clinic_forecast.staffing import StaffingCosts, StaffingRules
from clinic_forecast.staffing_v2 import staffing_plan_cost_v2

RULE_POLICY = "hybrid_rule_mean"
OPTIMIZER_POLICY = "hybrid_optimizer_mean"


@dataclass(frozen=True)
class OptimizerBenchmarkResult:
    """Fold scores, paired decisions and frozen promotion assessment."""

    scores: pd.DataFrame
    decisions: pd.DataFrame
    summary: pd.DataFrame
    promotion: pd.DataFrame


def _score(costed: pd.DataFrame) -> dict[str, float | int]:
    return {
        "n_obs": int(len(costed)),
        "total_cost": float(costed["total_cost"].sum()),
        "regular_cost": float(costed["regular_cost"].sum()),
        "regular_clinical_cost": float(costed["regular_clinical_cost"].sum()),
        "frontdesk_regular_cost": float(costed["frontdesk_regular_cost"].sum()),
        "overtime_cost": float(costed["overtime_cost"].sum()),
        "clinician_overtime_cost": float(costed["clinician_overtime_cost"].sum()),
        "nurse_overtime_cost": float(costed["nurse_overtime_cost"].sum()),
        "understaffing_cost": float(costed["understaffing_cost"].sum()),
        "idle_clinical_cost": float(costed["idle_clinical_cost"].sum()),
        "unmet_visits": float(costed["unmet_visits"].sum()),
        "understaffed_rate": float((costed["unmet_visits"] > 0).mean()),
        "clinician_days": int(costed["recommended_clinicians"].sum()),
        "nurse_days": int(costed["recommended_nurses"].sum()),
        "frontdesk_days": int(costed["recommended_frontdesk"].sum()),
    }


def compare_hybrid_rule_and_optimizer(
    hybrid_decisions: pd.DataFrame,
    rules: StaffingRules,
    costs: StaffingCosts,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rescore frozen hybrid-rule decisions and exact optimiser decisions with v2 loss."""
    required = {
        "fold",
        "clinic_id",
        "date",
        "is_open",
        "capacity_censored",
        CLINICAL_TARGET,
        "hybrid_clinical_forecast",
        "recommended_clinicians",
        "recommended_nurses",
        "recommended_frontdesk",
    }
    missing = required.difference(hybrid_decisions.columns)
    if missing:
        raise ValueError(f"Hybrid decisions missing columns: {sorted(missing)}")

    rule_plan = hybrid_decisions.copy()
    optimizer_plan = optimize_clinical_staffing(
        hybrid_decisions,
        demand_col="hybrid_clinical_forecast",
        rules=rules,
        costs=costs,
    )
    optimizer_plan["recommended_frontdesk"] = rule_plan["recommended_frontdesk"].to_numpy()

    score_rows: list[dict[str, object]] = []
    decision_rows: list[pd.DataFrame] = []
    for policy, plan in ((RULE_POLICY, rule_plan), (OPTIMIZER_POLICY, optimizer_plan)):
        costed = staffing_plan_cost_v2(
            plan,
            demand_col=CLINICAL_TARGET,
            rules=rules,
            costs=costs,
        )
        costed["policy"] = policy
        decision_rows.append(costed)
        for fold, fold_frame in costed.groupby("fold", observed=True):
            for slice_name, frame in {
                "all": fold_frame,
                "censored": fold_frame[fold_frame["capacity_censored"] == 1],
                "uncensored": fold_frame[fold_frame["capacity_censored"] == 0],
            }.items():
                score_rows.append(
                    {
                        "fold": int(fold),
                        "policy": policy,
                        "slice": slice_name,
                        **_score(frame),
                    }
                )

    return pd.DataFrame(score_rows), pd.concat(decision_rows, ignore_index=True)


def summarize_optimizer_benchmark(scores: pd.DataFrame) -> pd.DataFrame:
    """Summarise paired outer-fold cost and service metrics."""
    metrics = [
        "total_cost",
        "regular_cost",
        "regular_clinical_cost",
        "frontdesk_regular_cost",
        "overtime_cost",
        "clinician_overtime_cost",
        "nurse_overtime_cost",
        "understaffing_cost",
        "idle_clinical_cost",
        "unmet_visits",
        "understaffed_rate",
        "clinician_days",
        "nurse_days",
        "frontdesk_days",
    ]
    grouped = scores.groupby(["policy", "slice"], observed=True)[metrics]
    return (
        grouped.mean()
        .add_suffix("_mean")
        .join(grouped.std().add_suffix("_std"))
        .join(grouped.size().rename("n_folds"))
        .reset_index()
    )


def assess_optimizer_promotion(summary: pd.DataFrame) -> pd.DataFrame:
    """Apply the prospectively frozen cost/service Pareto promotion rule."""
    all_rows = summary[summary["slice"] == "all"].set_index("policy")
    missing = {RULE_POLICY, OPTIMIZER_POLICY}.difference(all_rows.index)
    if missing:
        raise ValueError(f"Summary missing primary policies: {sorted(missing)}")

    rule_cost = float(all_rows.loc[RULE_POLICY, "total_cost_mean"])
    optimizer_cost = float(all_rows.loc[OPTIMIZER_POLICY, "total_cost_mean"])
    rule_unmet = float(all_rows.loc[RULE_POLICY, "unmet_visits_mean"])
    optimizer_unmet = float(all_rows.loc[OPTIMIZER_POLICY, "unmet_visits_mean"])

    weak_cost = optimizer_cost <= rule_cost
    weak_unmet = optimizer_unmet <= rule_unmet
    strict = optimizer_cost < rule_cost or optimizer_unmet < rule_unmet
    promote = weak_cost and weak_unmet and strict

    if promote:
        verdict = "promote"
    elif weak_cost and weak_unmet:
        verdict = "no_change"
    else:
        verdict = "tradeoff_do_not_promote"

    return pd.DataFrame(
        [
            {
                "rule_total_cost_mean": rule_cost,
                "optimizer_total_cost_mean": optimizer_cost,
                "total_cost_change_pct": 100.0 * (optimizer_cost / rule_cost - 1.0),
                "rule_unmet_visits_mean": rule_unmet,
                "optimizer_unmet_visits_mean": optimizer_unmet,
                "unmet_visits_change_pct": 100.0 * (optimizer_unmet / rule_unmet - 1.0),
                "weakly_better_total_cost": weak_cost,
                "weakly_better_unmet_visits": weak_unmet,
                "at_least_one_strict_improvement": strict,
                "promotion_verdict": verdict,
            }
        ]
    )


def run_optimizer_benchmark(
    usage: pd.DataFrame,
    metadata: pd.DataFrame,
    config: HybridPolicyBenchmarkConfig | None = None,
    rules: StaffingRules | None = None,
    costs: StaffingCosts | None = None,
) -> OptimizerBenchmarkResult:
    """Run the frozen hybrid rule vs optimiser comparison."""
    staffing_rules = rules or StaffingRules()
    cost_model = costs or StaffingCosts()
    _, legacy_decisions = run_hybrid_policy_benchmark(
        usage=usage,
        metadata=metadata,
        config=config,
        rules=staffing_rules,
        costs=cost_model,
    )
    hybrid_decisions = legacy_decisions[legacy_decisions["policy"] == "hybrid"].copy()
    scores, decisions = compare_hybrid_rule_and_optimizer(
        hybrid_decisions,
        rules=staffing_rules,
        costs=cost_model,
    )
    summary = summarize_optimizer_benchmark(scores)
    promotion = assess_optimizer_promotion(summary)
    return OptimizerBenchmarkResult(
        scores=scores,
        decisions=decisions,
        summary=summary,
        promotion=promotion,
    )


__all__ = [
    "OPTIMIZER_POLICY",
    "RULE_POLICY",
    "OptimizerBenchmarkResult",
    "assess_optimizer_promotion",
    "compare_hybrid_rule_and_optimizer",
    "run_optimizer_benchmark",
    "summarize_optimizer_benchmark",
]
