"""Execution and evidence helpers for the frozen core recursive benchmark."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from clinic_forecast.benchmark import run_benchmark
from clinic_forecast.core_benchmark import CoreBenchmarkSpec, core_forecasters
from clinic_forecast.evaluation import add_horizon, evaluate_forecasts, rank_models

PRIMARY_METRICS = ("mae", "rmse", "wape", "bias")
BASELINE_MODEL = "seasonal_naive"


@dataclass(frozen=True)
class CoreBenchmarkResult:
    """Machine-readable outputs from one frozen core benchmark run."""

    specification: dict[str, object]
    fold_boundaries: pd.DataFrame
    forecast_rows: pd.DataFrame
    fold_scores: pd.DataFrame
    leaderboard: pd.DataFrame
    paired_contrasts: pd.DataFrame
    horizon_scores: pd.DataFrame
    clinic_scores: pd.DataFrame


def _paired_contrasts(fold_scores: pd.DataFrame) -> pd.DataFrame:
    """Compute model-minus-seasonal-naive paired differences by outer fold."""
    rows: list[dict[str, object]] = []
    models = sorted(set(fold_scores["model"]) - {BASELINE_MODEL})
    baseline = fold_scores[fold_scores["model"] == BASELINE_MODEL]
    expected_folds = int(baseline["fold"].nunique())

    for model in models:
        comparator = fold_scores[fold_scores["model"] == model]
        for metric in PRIMARY_METRICS:
            paired = comparator[["fold", metric]].merge(
                baseline[["fold", metric]],
                on="fold",
                suffixes=("_model", "_baseline"),
                validate="one_to_one",
            )
            if len(paired) != expected_folds:
                raise ValueError(
                    f"Paired contrast for {model}/{metric} has {len(paired)} folds; "
                    f"expected {expected_folds}."
                )
            difference = paired[f"{metric}_model"] - paired[f"{metric}_baseline"]
            zero = np.isclose(difference.to_numpy(dtype=float), 0.0, atol=1e-12, rtol=0.0)
            rows.append(
                {
                    "model": model,
                    "baseline_model": BASELINE_MODEL,
                    "metric": metric,
                    "n_folds": expected_folds,
                    "mean_difference": float(difference.mean()),
                    "median_difference": float(difference.median()),
                    "sd_difference": float(difference.std(ddof=1)),
                    "better_fold_count": int(((difference < 0).to_numpy() & ~zero).sum()),
                    "worse_fold_count": int(((difference > 0).to_numpy() & ~zero).sum()),
                    "tie_fold_count": int(zero.sum()),
                }
            )
    return pd.DataFrame(rows)


def run_core_benchmark(
    usage: pd.DataFrame,
    spec: CoreBenchmarkSpec | None = None,
) -> CoreBenchmarkResult:
    """Run the frozen core model set under deployment-matched evaluation."""
    benchmark_spec = spec or CoreBenchmarkSpec()
    splitter = benchmark_spec.splitter()
    scored = run_benchmark(
        usage,
        core_forecasters(),
        splitter,
        on_error="raise",
    )

    boundaries = splitter.summary(usage).rename(columns={"fold_id": "fold"})
    boundary_map = boundaries.set_index("fold")["train_end"]
    parts: list[pd.DataFrame] = []
    for fold, frame in scored.groupby("fold", observed=True):
        origin = pd.Timestamp(boundary_map.loc[int(fold)])
        parts.append(add_horizon(frame, origin))
    forecast_rows = pd.concat(parts, ignore_index=True)

    fold_scores = evaluate_forecasts(
        forecast_rows,
        group_cols=["fold"],
    ).sort_values(["fold", "model"])
    leaderboard = rank_models(fold_scores, primary_metric="wape")
    paired = _paired_contrasts(fold_scores)
    horizon_scores = evaluate_forecasts(
        forecast_rows,
        group_cols=["horizon_days"],
    ).sort_values(["horizon_days", "model"])
    clinic_scores = evaluate_forecasts(
        forecast_rows,
        group_cols=["clinic_id"],
    ).sort_values(["clinic_id", "model"])

    expected_models = set(core_forecasters())
    observed_models = set(fold_scores["model"])
    if observed_models != expected_models:
        raise ValueError(
            "Core benchmark model set mismatch: "
            f"expected={sorted(expected_models)}, observed={sorted(observed_models)}."
        )
    if fold_scores["fold"].nunique() != benchmark_spec.max_folds:
        raise ValueError(
            f"Expected {benchmark_spec.max_folds} benchmark folds; "
            f"observed {fold_scores['fold'].nunique()}."
        )

    specification: dict[str, object] = {
        **asdict(benchmark_spec),
        "models": sorted(expected_models),
        "primary_metric": "wape",
        "co_primary_diagnostic": "bias",
        "evaluation_contract": "fixed-origin full-horizon; no teacher forcing",
    }
    return CoreBenchmarkResult(
        specification=specification,
        fold_boundaries=boundaries,
        forecast_rows=forecast_rows,
        fold_scores=fold_scores.reset_index(drop=True),
        leaderboard=leaderboard.reset_index(drop=True),
        paired_contrasts=paired.reset_index(drop=True),
        horizon_scores=horizon_scores.reset_index(drop=True),
        clinic_scores=clinic_scores.reset_index(drop=True),
    )


__all__ = ["CoreBenchmarkResult", "run_core_benchmark"]
