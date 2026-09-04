"""Held-out coverage audit for deployment-matched conformal intervals."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from clinic_forecast.backtesting import recursive_global_ml_forecast
from clinic_forecast.core_benchmark import CoreBenchmarkSpec
from clinic_forecast.evaluation import add_horizon
from clinic_forecast.intervals import ConformalIntervals

FROZEN_COVERAGE = 0.9


@dataclass(frozen=True)
class IntervalCoverageAuditSpec:
    """Frozen settings for the recursive conformal coverage audit."""

    coverage: float = FROZEN_COVERAGE
    calibration_folds: int = 4
    estimator: str = "hgb"
    benchmark: CoreBenchmarkSpec = CoreBenchmarkSpec()

    def __post_init__(self) -> None:
        if self.coverage != FROZEN_COVERAGE:
            raise ValueError("coverage is frozen at 0.9 for this audit.")
        if self.calibration_folds < 1:
            raise ValueError("calibration_folds must be positive.")
        if self.calibration_folds >= self.benchmark.max_folds:
            raise ValueError("calibration_folds must leave at least one evaluation fold.")


@dataclass(frozen=True)
class IntervalCoverageAuditResult:
    """Evidence frames produced by one held-out interval coverage audit."""

    audit_rows: pd.DataFrame
    fold_scores: pd.DataFrame
    horizon_scores: pd.DataFrame
    clinic_scores: pd.DataFrame
    summary: dict[str, object]


def _coverage_summary(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Summarise open-day uncertainty and served all-day interval behaviour."""
    rows: list[dict[str, object]] = []
    grouped = frame.groupby(group_cols, observed=True) if group_cols else [((), frame)]
    for group_key, group in grouped:
        key_values = group_key if isinstance(group_key, tuple) else (group_key,)
        row = dict(zip(group_cols, key_values, strict=True))
        open_rows = group[group["is_open"]]
        closed_rows = group[~group["is_open"]]
        if open_rows.empty:
            coverage = float("nan")
            mean_width = float("nan")
        else:
            coverage = float(open_rows["covered"].mean())
            mean_width = float(open_rows["interval_width"].mean())
        closed_zero_served = (
            (
                (closed_rows["y_pred"] == 0.0)
                & (closed_rows["y_lower"] == 0.0)
                & (closed_rows["y_upper"] == 0.0)
            )
            if not closed_rows.empty
            else pd.Series(dtype=bool)
        )
        row.update(
            {
                "coverage": coverage,
                "mean_interval_width": mean_width,
                "n_obs": len(open_rows),
                "n_served_obs": len(group),
                "n_closed_days": len(closed_rows),
                "served_coverage": float(group["covered"].mean()),
                "served_mean_interval_width": float(group["interval_width"].mean()),
                "closed_zero_served_rate": (
                    float(closed_zero_served.mean())
                    if not closed_zero_served.empty
                    else float("nan")
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def run_interval_coverage_audit(
    usage: pd.DataFrame,
    spec: IntervalCoverageAuditSpec | None = None,
) -> IntervalCoverageAuditResult:
    """Audit conformal coverage only on folds unseen during calibration.

    The first ``calibration_folds`` recursive HGB folds seed the calibration
    residual pool. Each later fold is forecast from its fixed origin, receives
    intervals fitted only on earlier folds, is scored, and is appended to the
    calibration pool for the next evaluation fold. This prequential ordering
    prevents evaluation residuals from influencing their own interval width.

    Conformal uncertainty is calibrated and scored on open clinic-days only.
    Closed clinic-days are deterministic zeros in the batch-serving contract;
    they remain in ``audit_rows`` solely to verify that the served point and
    interval bounds are all exactly zero, and do not inflate primary coverage.
    """
    audit_spec = spec or IntervalCoverageAuditSpec()
    if "is_open" not in usage.columns:
        raise ValueError("Interval coverage audit requires an is_open column.")
    if usage["is_open"].isna().any():
        raise ValueError("Interval coverage audit does not allow missing is_open values.")

    splitter = audit_spec.benchmark.splitter()
    calibration_frames: list[pd.DataFrame] = []
    evaluation_frames: list[pd.DataFrame] = []

    folds = list(splitter.split(usage))
    if len(folds) != audit_spec.benchmark.max_folds:
        raise ValueError(
            "Interval coverage audit requires the frozen fold count: "
            f"expected={audit_spec.benchmark.max_folds}, observed={len(folds)}."
        )

    for train, test, fold in folds:
        predictions = recursive_global_ml_forecast(
            train=train,
            test=test,
            estimator=audit_spec.estimator,
        )
        scored = test.merge(
            predictions[["clinic_id", "date", "forecast"]],
            on=["clinic_id", "date"],
            how="inner",
            validate="one_to_one",
        )
        scored = add_horizon(scored, fold.train_end)
        scored["fold"] = fold.fold_id
        scored["origin"] = fold.train_end
        scored["is_open"] = scored["is_open"].astype(bool)
        open_scored = scored[scored["is_open"]].copy()
        if open_scored.empty:
            raise ValueError(f"Fold {fold.fold_id} contains no open clinic-days.")

        if fold.fold_id <= audit_spec.calibration_folds:
            calibration_frames.append(open_scored)
            continue

        calibration = pd.concat(calibration_frames, ignore_index=True)
        intervals = ConformalIntervals(
            coverage=audit_spec.coverage,
            group_col="clinic_id",
        ).fit(calibration)
        evaluated = intervals.apply(scored)

        closed = ~evaluated["is_open"]
        if closed.any():
            evaluated.loc[closed, ["forecast", "y_pred", "y_lower", "y_upper"]] = 0.0

        evaluated["covered"] = (
            (evaluated["visits"] >= evaluated["y_lower"])
            & (evaluated["visits"] <= evaluated["y_upper"])
        )
        evaluated["interval_width"] = evaluated["y_upper"] - evaluated["y_lower"]
        evaluated["calibration_rows"] = len(calibration)
        evaluated["calibration_folds"] = len(calibration_frames)
        evaluation_frames.append(evaluated)
        calibration_frames.append(open_scored)

    if not evaluation_frames:
        raise RuntimeError("Interval coverage audit produced no held-out evaluation folds.")

    audit_rows = pd.concat(evaluation_frames, ignore_index=True)
    expected_evaluation_folds = audit_spec.benchmark.max_folds - audit_spec.calibration_folds
    observed_evaluation_folds = int(audit_rows["fold"].nunique())
    if observed_evaluation_folds != expected_evaluation_folds:
        raise ValueError(
            "Interval coverage evaluation fold count drifted: "
            f"expected={expected_evaluation_folds}, observed={observed_evaluation_folds}."
        )

    fold_scores = _coverage_summary(audit_rows, ["fold"])
    horizon_scores = _coverage_summary(audit_rows, ["horizon_days"])
    clinic_scores = _coverage_summary(audit_rows, ["clinic_id"])
    overall = _coverage_summary(audit_rows, []).iloc[0]

    summary: dict[str, object] = {
        "nominal_coverage": audit_spec.coverage,
        "primary_estimand": "open_clinic_days",
        "estimator": audit_spec.estimator,
        "calibration_mode": "fixed_origin_recursive_prequential_open_days",
        "initial_calibration_folds": audit_spec.calibration_folds,
        "evaluation_folds": expected_evaluation_folds,
        "coverage": float(overall["coverage"]),
        "mean_interval_width": float(overall["mean_interval_width"]),
        "n_obs": int(overall["n_obs"]),
        "n_served_obs": int(overall["n_served_obs"]),
        "n_closed_days": int(overall["n_closed_days"]),
        "served_coverage": float(overall["served_coverage"]),
        "served_mean_interval_width": float(overall["served_mean_interval_width"]),
        "closed_zero_served_rate": float(overall["closed_zero_served_rate"]),
        "horizons": int(horizon_scores["horizon_days"].nunique()),
        "clinics": int(clinic_scores["clinic_id"].nunique()),
    }
    return IntervalCoverageAuditResult(
        audit_rows=audit_rows,
        fold_scores=fold_scores,
        horizon_scores=horizon_scores,
        clinic_scores=clinic_scores,
        summary=summary,
    )


__all__ = [
    "FROZEN_COVERAGE",
    "IntervalCoverageAuditResult",
    "IntervalCoverageAuditSpec",
    "run_interval_coverage_audit",
]
