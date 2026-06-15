"""Run many forecasters head-to-head on the same rolling-origin folds.

A *forecaster* here is any callable ``(train, test) -> forecast_frame`` whose
output carries ``clinic_id``, ``date`` and ``forecast`` columns — the
project's common schema, which every model wrapper produces. This lets a
single harness compare baselines, statistical models, global ML, the Nixtla
ecosystem and foundation models on identical data.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pandas as pd

from clinic_forecast.evaluation import comparison_table, evaluate_forecasts, rank_models
from clinic_forecast.validation import RollingOriginSplitter

logger = logging.getLogger(__name__)

Forecaster = Callable[[pd.DataFrame, pd.DataFrame], pd.DataFrame]


def run_benchmark(
    usage: pd.DataFrame,
    forecasters: dict[str, Forecaster],
    splitter: RollingOriginSplitter,
    actual_col: str = "visits",
    id_col: str = "clinic_id",
    date_col: str = "date",
    on_error: str = "skip",
) -> pd.DataFrame:
    """Score every forecaster on every fold and return a long scored frame.

    Parameters
    ----------
    forecasters:
        Mapping of model name to a ``(train, test) -> forecast_frame`` callable.
    on_error:
        ``"skip"`` (default) logs and drops a model that raises on a fold —
        so an uninstalled optional model does not abort the benchmark;
        ``"raise"`` re-raises.

    Returns
    -------
    pandas.DataFrame
        Test rows joined to each model's forecast, with ``model`` and ``fold``
        columns — ready for :func:`clinic_forecast.evaluation.evaluate_forecasts`.
    """
    if on_error not in ("skip", "raise"):
        raise ValueError("on_error must be 'skip' or 'raise'.")

    scored: list[pd.DataFrame] = []
    for train, test, fold in splitter.split(usage):
        for name, forecaster in forecasters.items():
            try:
                forecast = forecaster(train, test)
            except Exception as exc:  # noqa: BLE001
                if on_error == "raise":
                    raise
                logger.warning("model %r failed on fold %s: %s", name, fold.fold_id, exc)
                continue
            merged = test.merge(
                forecast[[id_col, date_col, "forecast"]],
                on=[id_col, date_col],
                how="inner",
            )
            if merged.empty:
                logger.warning("model %r produced no aligned rows on fold %s", name, fold.fold_id)
                continue
            merged["model"] = name
            merged["fold"] = fold.fold_id
            scored.append(merged)

    if not scored:
        raise RuntimeError("No model produced any forecasts; nothing to benchmark.")
    return pd.concat(scored, ignore_index=True)


def benchmark_leaderboard(
    scored: pd.DataFrame,
    actual_col: str = "visits",
    primary_metric: str = "wape",
) -> pd.DataFrame:
    """Rank benchmarked models by mean of a primary metric across folds."""
    per_fold = evaluate_forecasts(scored, actual_col=actual_col, group_cols=["fold"])
    return rank_models(per_fold, primary_metric=primary_metric)


def benchmark_metric_table(
    scored: pd.DataFrame,
    actual_col: str = "visits",
) -> pd.DataFrame:
    """Model-by-metric comparison table (means across folds)."""
    per_fold = evaluate_forecasts(scored, actual_col=actual_col, group_cols=["fold"])
    return comparison_table(per_fold)
