"""Descriptive characterization of frozen NHS GPAD benchmark origins.

This module consumes already-scored confirmatory benchmark outputs. It never
fits or reruns a forecasting model. The descriptors are frozen in
``reports/evidence/nhs_origin_regime_characterization/DESIGN.md`` and are
exploratory only.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

HGB_MODEL = "global_ml_hgb"
SEASONAL_MODEL = "seasonal_naive"

_REQUIRED_FOLD_COLUMNS = {
    "model",
    "origin",
    "wape",
    "train_end",
    "test_start",
    "test_end",
}
_REQUIRED_PANEL_COLUMNS = {"clinic_id", "date", "visits"}
_REQUIRED_FORECAST_COLUMNS = {"origin", "clinic_id", "date", "model", "visits", "forecast"}


def _require_columns(frame: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = sorted(set(required).difference(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def _wape(actual: pd.Series, forecast: pd.Series) -> float:
    denominator = float(actual.abs().sum())
    if denominator == 0:
        return float("nan")
    return 100.0 * float((actual - forecast).abs().sum()) / denominator


def _origin_geography_differences(forecast_rows: pd.DataFrame, origin: int) -> pd.Series:
    origin_rows = forecast_rows[
        (forecast_rows["origin"] == origin)
        & forecast_rows["model"].isin([HGB_MODEL, SEASONAL_MODEL])
    ]
    differences: dict[str, float] = {}
    for clinic_id, clinic_rows in origin_rows.groupby("clinic_id", observed=True):
        model_wape: dict[str, float] = {}
        for model, model_rows in clinic_rows.groupby("model", observed=True):
            model_wape[str(model)] = _wape(model_rows["visits"], model_rows["forecast"])
        if HGB_MODEL not in model_wape or SEASONAL_MODEL not in model_wape:
            raise ValueError(
                f"Origin {origin}, clinic {clinic_id!r} is missing HGB or seasonal forecasts."
            )
        differences[str(clinic_id)] = model_wape[HGB_MODEL] - model_wape[SEASONAL_MODEL]
    if not differences:
        raise ValueError(f"Origin {origin} has no geography-level forecast rows.")
    return pd.Series(differences, dtype=float)


def characterize_origins(
    fold_scores: pd.DataFrame,
    origin_boundaries: pd.DataFrame,
    panel: pd.DataFrame,
    forecast_rows: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate the prospectively frozen descriptive regime table."""
    _require_columns(fold_scores, _REQUIRED_FOLD_COLUMNS, "fold_scores")
    _require_columns(origin_boundaries, {"origin", "train_end", "test_start", "test_end"}, "origin_boundaries")
    _require_columns(panel, _REQUIRED_PANEL_COLUMNS, "panel")
    _require_columns(forecast_rows, _REQUIRED_FORECAST_COLUMNS, "forecast_rows")

    scores = fold_scores.copy()
    boundaries = origin_boundaries.copy()
    observed = panel.copy()
    forecasts = forecast_rows.copy()

    for column in ["train_end", "test_start", "test_end"]:
        scores[column] = pd.to_datetime(scores[column])
        boundaries[column] = pd.to_datetime(boundaries[column])
    observed["date"] = pd.to_datetime(observed["date"])
    forecasts["date"] = pd.to_datetime(forecasts["date"])

    score_wide = scores.pivot(index="origin", columns="model", values="wape")
    for required_model in [HGB_MODEL, SEASONAL_MODEL]:
        if required_model not in score_wide.columns:
            raise ValueError(f"fold_scores is missing model {required_model!r}.")

    daily_network = observed.groupby("date", as_index=False, observed=True)["visits"].sum()
    daily_network = daily_network.rename(columns={"visits": "network_total"})

    rows: list[dict[str, object]] = []
    for boundary in boundaries.sort_values("origin").itertuples(index=False):
        origin = int(boundary.origin)
        train_end = pd.Timestamp(boundary.train_end)
        test_start = pd.Timestamp(boundary.test_start)
        test_end = pd.Timestamp(boundary.test_end)
        trailing_start = train_end - pd.Timedelta(days=27)

        trailing = observed[observed["date"].between(trailing_start, train_end)]
        test = observed[observed["date"].between(test_start, test_end)]
        trailing_network = daily_network[daily_network["date"].between(trailing_start, train_end)]
        test_network = daily_network[daily_network["date"].between(test_start, test_end)]
        first_week = test_network.sort_values("date").head(7)

        if trailing.empty or test.empty or len(first_week) != 7:
            raise ValueError(f"Origin {origin} does not have the expected descriptor windows.")

        hgb_wape = float(score_wide.loc[origin, HGB_MODEL])
        seasonal_wape = float(score_wide.loc[origin, SEASONAL_MODEL])
        winner = (
            "hgb_better"
            if hgb_wape < seasonal_wape
            else "seasonal_better"
            if hgb_wape > seasonal_wape
            else "tie"
        )

        trailing_mean = float(trailing["visits"].mean())
        trailing_sd = float(trailing["visits"].std(ddof=1))
        test_mean = float(test["visits"].mean())
        test_sd = float(test["visits"].std(ddof=1))
        trailing_network_mean = float(trailing_network["network_total"].mean())
        trailing_network_sd = float(trailing_network["network_total"].std(ddof=1))
        first_week_mean = float(first_week["network_total"].mean())
        test_network_mean = float(test_network["network_total"].mean())
        geography_diff = _origin_geography_differences(forecasts, origin)

        rows.append(
            {
                "origin": origin,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "winner": winner,
                "hgb_wape": hgb_wape,
                "seasonal_wape": seasonal_wape,
                "hgb_minus_seasonal_wape": hgb_wape - seasonal_wape,
                "start_month": int(test_start.month),
                "start_quarter": int(test_start.quarter),
                "months_touched": int(test["date"].dt.to_period("M").nunique()),
                "trailing_mean": trailing_mean,
                "trailing_sd": trailing_sd,
                "test_mean": test_mean,
                "test_sd": test_sd,
                "trailing_cv": trailing_sd / trailing_mean if trailing_mean > 0 else np.nan,
                "test_cv": test_sd / test_mean if test_mean > 0 else np.nan,
                "test_to_trailing_mean_ratio": (
                    test_mean / trailing_mean if trailing_mean > 0 else np.nan
                ),
                "trailing_zero_fraction": float((trailing["visits"] == 0).mean()),
                "test_zero_fraction": float((test["visits"] == 0).mean()),
                "trailing_network_mean": trailing_network_mean,
                "trailing_network_sd": trailing_network_sd,
                "first7_test_network_mean": first_week_mean,
                "test_network_mean": test_network_mean,
                "standardized_first_week_shift": (
                    (first_week_mean - trailing_network_mean) / trailing_network_sd
                    if trailing_network_sd > 0
                    else np.nan
                ),
                "relative_full_test_shift": (
                    (test_network_mean - trailing_network_mean) / trailing_network_mean
                    if trailing_network_mean > 0
                    else np.nan
                ),
                "hgb_better_geographies": int((geography_diff < 0).sum()),
                "hgb_better_geography_fraction": float((geography_diff < 0).mean()),
                "median_geo_wape_diff": float(geography_diff.median()),
                "max_geo_wape_diff": float(geography_diff.max()),
                "min_geo_wape_diff": float(geography_diff.min()),
            }
        )

    return pd.DataFrame(rows)


def summarize_winner_groups(origin_table: pd.DataFrame) -> pd.DataFrame:
    """Return median and IQR summaries for every numeric frozen descriptor."""
    if "winner" not in origin_table.columns:
        raise ValueError("origin_table is missing 'winner'.")
    excluded = {"origin", "start_month", "start_quarter", "months_touched"}
    numeric_columns = [
        column
        for column in origin_table.select_dtypes(include=[np.number]).columns
        if column not in excluded
    ]
    rows: list[dict[str, object]] = []
    for winner, group in origin_table.groupby("winner", observed=True):
        for descriptor in numeric_columns:
            values = group[descriptor].dropna()
            rows.append(
                {
                    "winner": winner,
                    "descriptor": descriptor,
                    "n": int(len(values)),
                    "median": float(values.median()),
                    "q25": float(values.quantile(0.25)),
                    "q75": float(values.quantile(0.75)),
                }
            )
    return pd.DataFrame(rows)


__all__ = ["characterize_origins", "summarize_winner_groups"]
