"""Confirmatory NHS GPAD forecasting benchmark under the frozen panel policy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import comb
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from clinic_forecast.evaluation import add_horizon, evaluate_forecasts
from clinic_forecast.models.baseline import moving_average_forecast, seasonal_naive_forecast
from clinic_forecast.models.global_ml import GlobalMLForecaster
from clinic_forecast.nhs_gpad import GPADQualityResult, load_gpad_config, run_gpad_quality_gate
from clinic_forecast.nhs_gpad_calendar import (
    GPADCalendarSupportResult,
    run_gpad_calendar_support_audit,
)

PRIMARY_METRICS = ("mae", "wape", "rmse", "bias")
EXPECTED_MODELS = ("seasonal_naive", "moving_average_28", "global_ml_hgb")


@dataclass(frozen=True)
class NHSGPADBenchmarkResult:
    """All machine-readable outputs from the frozen external benchmark."""

    quality: GPADQualityResult
    calendar_support: GPADCalendarSupportResult
    panel: pd.DataFrame
    origin_boundaries: pd.DataFrame
    forecasts: pd.DataFrame
    fold_scores: pd.DataFrame
    paired_model_contrasts: pd.DataFrame
    horizon_scores: pd.DataFrame
    horizon_band_scores: pd.DataFrame
    geography_scores: pd.DataFrame
    summary: dict[str, object]


def load_panel_policy(path: str | Path) -> dict[str, object]:
    """Load the prospectively frozen NHS panel policy."""
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise TypeError("NHS GPAD panel policy must be a mapping.")
    return cast(dict[str, object], loaded)


def _mapping(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a mapping.")
    return cast(dict[str, object], value)


def _list(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list.")
    return cast(list[object], value)


def prepare_confirmatory_panel(
    calendar_support: pd.DataFrame,
    policy: dict[str, object],
) -> pd.DataFrame:
    """Apply the frozen geography and observed-attendance zero policy."""
    geography_policy = _mapping(policy["geography_policy"], "geography_policy")
    eligible_raw = _list(
        geography_policy["eligible_sub_icb_codes"],
        "geography_policy.eligible_sub_icb_codes",
    )
    eligible = [str(code) for code in eligible_raw]
    if len(eligible) != len(set(eligible)):
        raise ValueError("Frozen eligible sub-ICB codes contain duplicates.")

    required = {
        "sub_icb_code",
        "date",
        "source_support_class",
        "attended_appointments",
        "complete_coverage",
    }
    missing = required.difference(calendar_support.columns)
    if missing:
        raise ValueError(f"Calendar support is missing required columns: {sorted(missing)}")

    frame = calendar_support.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["sub_icb_code"] = frame["sub_icb_code"].astype("string")
    selected = frame[frame["sub_icb_code"].isin(eligible)].copy()

    observed_codes = sorted(selected["sub_icb_code"].dropna().astype(str).unique())
    if observed_codes != sorted(eligible):
        raise ValueError(
            "Calendar-support geography set does not match the frozen eligible set: "
            f"expected={sorted(eligible)}, observed={observed_codes}."
        )
    if selected.duplicated(["sub_icb_code", "date"]).any():
        raise ValueError("Duplicate sub-ICB/day rows in frozen calendar support.")
    if not selected["complete_coverage"].fillna(False).astype(bool).all():
        raise ValueError("Frozen confirmatory panel contains an incomplete-coverage month.")

    date_start = pd.Timestamp(str(policy["date_start"]))
    date_end = pd.Timestamp(str(policy["date_end"]))
    expected_days = int(policy["calendar_days"])
    expected_rows = int(policy["panel_rows"])
    expected_calendar = pd.date_range(date_start, date_end, freq="D")
    if len(expected_calendar) != expected_days:
        raise ValueError("Frozen calendar_days does not match the configured date range.")

    selected = selected[(selected["date"] >= date_start) & (selected["date"] <= date_end)].copy()
    if len(selected) != expected_rows:
        raise ValueError(
            f"Frozen panel row count mismatch: expected={expected_rows}, observed={len(selected)}."
        )
    counts_by_code = selected.groupby("sub_icb_code", observed=True)["date"].nunique()
    if not (counts_by_code == expected_days).all():
        raise ValueError("Every eligible sub-ICB must have the complete frozen calendar.")

    expected_support = _mapping(
        policy["support_counts_within_eligible_panel"],
        "support_counts_within_eligible_panel",
    )
    actual_support = selected["source_support_class"].value_counts().to_dict()
    for status in ("attended_present", "other_status_only", "no_published_rows"):
        if int(actual_support.get(status, 0)) != int(expected_support[status]):
            raise ValueError(
                f"Frozen support count mismatch for {status}: "
                f"expected={expected_support[status]}, observed={actual_support.get(status, 0)}."
            )

    panel = selected[
        ["sub_icb_code", "date", "source_support_class", "attended_appointments"]
    ].copy()
    panel["visits"] = pd.to_numeric(panel["attended_appointments"], errors="coerce").fillna(0)
    if (panel["visits"] < 0).any():
        raise ValueError("Negative attended appointments in frozen panel.")
    panel["visits"] = panel["visits"].astype("int64")
    panel = panel.rename(columns={"sub_icb_code": "clinic_id"}).drop(
        columns=["attended_appointments"]
    )
    return panel.sort_values(["clinic_id", "date"]).reset_index(drop=True)


def origin_boundaries_from_policy(policy: dict[str, object]) -> pd.DataFrame:
    """Return and validate the exact prospectively frozen outer origins."""
    validation = _mapping(policy["validation"], "validation")
    origins_raw = _list(validation["origins"], "validation.origins")
    rows: list[dict[str, object]] = []
    for raw in origins_raw:
        item = _mapping(raw, "validation.origin")
        rows.append(
            {
                "origin": int(item["origin"]),
                "train_end": pd.Timestamp(str(item["train_end"])),
                "test_start": pd.Timestamp(str(item["test_start"])),
                "test_end": pd.Timestamp(str(item["test_end"])),
            }
        )
    frame = pd.DataFrame(rows).sort_values("origin").reset_index(drop=True)
    expected_origins = int(validation["outer_origins"])
    horizon = int(validation["forecast_horizon_days"])
    step = int(validation["step_days"])
    if len(frame) != expected_origins:
        raise ValueError(
            f"Expected {expected_origins} frozen origins; observed {len(frame)}."
        )
    if frame["origin"].tolist() != list(range(1, expected_origins + 1)):
        raise ValueError("Frozen origin identifiers must be consecutive starting at 1.")
    durations = (frame["test_end"] - frame["test_start"]).dt.days + 1
    if not (durations == horizon).all():
        raise ValueError("Every frozen test interval must equal the forecast horizon.")
    if not ((frame["test_start"] - frame["train_end"]).dt.days == 1).all():
        raise ValueError("Every frozen test window must begin the day after training ends.")
    if len(frame) > 1:
        origin_steps = frame["test_start"].diff().dropna().dt.days
        if not (origin_steps == step).all():
            raise ValueError("Frozen test starts do not follow the configured step size.")
    return frame


def _run_origin_models(
    panel: pd.DataFrame,
    *,
    origin: int,
    train_end: pd.Timestamp,
    test_start: pd.Timestamp,
    test_end: pd.Timestamp,
) -> pd.DataFrame:
    train = panel[panel["date"] <= train_end][["clinic_id", "date", "visits"]].copy()
    actual = panel[
        (panel["date"] >= test_start) & (panel["date"] <= test_end)
    ][["clinic_id", "date", "visits"]].copy()
    if train.empty or actual.empty:
        raise ValueError(f"Origin {origin} has an empty train or test frame.")

    geography_count = panel["clinic_id"].nunique()
    expected_test_rows = geography_count * ((test_end - test_start).days + 1)
    if len(actual) != expected_test_rows:
        raise ValueError(
            f"Origin {origin} test panel is incomplete: "
            f"expected={expected_test_rows}, observed={len(actual)}."
        )
    future = actual[["clinic_id", "date"]].copy()

    seasonal = seasonal_naive_forecast(
        train,
        future,
        id_col="clinic_id",
        date_col="date",
        target_col="visits",
        season_length=7,
    )
    moving = moving_average_forecast(
        train,
        future,
        id_col="clinic_id",
        date_col="date",
        target_col="visits",
        window=28,
    )
    hgb = GlobalMLForecaster(
        target_col="visits",
        date_col="date",
        id_col="clinic_id",
        estimator="hgb",
        random_state=42,
    )
    hgb.fit(train)
    global_forecast = hgb.forecast(train, future)

    stacked = pd.concat([seasonal, moving, global_forecast], ignore_index=True)
    stacked["date"] = pd.to_datetime(stacked["date"])
    if set(stacked["model"].unique()) != set(EXPECTED_MODELS):
        raise ValueError(f"Origin {origin} returned an unexpected model set.")
    model_counts = stacked.groupby("model", observed=True).size()
    if not (model_counts == expected_test_rows).all():
        raise ValueError(f"Origin {origin} produced an incomplete forecast panel.")
    if stacked.duplicated(["model", "clinic_id", "date"]).any():
        raise ValueError(f"Origin {origin} produced duplicate forecast keys.")

    scored = stacked.merge(
        actual,
        on=["clinic_id", "date"],
        how="left",
        validate="many_to_one",
    )
    if scored["visits"].isna().any() or scored["forecast"].isna().any():
        raise ValueError(f"Origin {origin} contains missing actuals or forecasts.")
    scored["origin"] = origin
    scored = add_horizon(scored, train_end, date_col="date")
    scored["horizon_band"] = pd.cut(
        scored["horizon_days"],
        bins=[0, 7, 14, 21, 28],
        labels=["01-07", "08-14", "15-21", "22-28"],
        include_lowest=True,
    ).astype("string")
    return scored[
        [
            "origin",
            "clinic_id",
            "date",
            "horizon_days",
            "horizon_band",
            "model",
            "visits",
            "forecast",
        ]
    ].sort_values(["origin", "model", "clinic_id", "date"])


def _two_sided_sign_test_p(positive: int, negative: int) -> float:
    """Exact two-sided sign-test p-value, excluding zero differences."""
    n = positive + negative
    if n == 0:
        return 1.0
    k = min(positive, negative)
    lower_tail = sum(comb(n, i) for i in range(k + 1)) / (2**n)
    return float(min(1.0, 2.0 * lower_tail))


def paired_model_contrasts(
    fold_scores: pd.DataFrame,
    *,
    expected_origins: int,
    baseline_model: str = "seasonal_naive",
) -> pd.DataFrame:
    """Summarize origin-paired model-minus-baseline metric differences."""
    rows: list[dict[str, object]] = []
    for model in sorted(set(fold_scores["model"]) - {baseline_model}):
        for metric in PRIMARY_METRICS:
            baseline = fold_scores[fold_scores["model"] == baseline_model][
                ["origin", metric]
            ].rename(columns={metric: "baseline"})
            comparator = fold_scores[fold_scores["model"] == model][
                ["origin", metric]
            ].rename(columns={metric: "comparator"})
            paired = comparator.merge(baseline, on="origin", how="inner", validate="one_to_one")
            if len(paired) != expected_origins:
                raise ValueError(
                    f"Paired contrast {model}/{metric} has {len(paired)} origins; "
                    f"expected {expected_origins}."
                )
            difference = paired["comparator"] - paired["baseline"]
            zero = np.isclose(difference.to_numpy(dtype=float), 0.0, atol=1e-12, rtol=0.0)
            positive = int(((difference > 0).to_numpy() & ~zero).sum())
            negative = int(((difference < 0).to_numpy() & ~zero).sum())
            zero_count = int(zero.sum())
            nonzero = positive + negative
            if positive > negative:
                dominant_sign = "positive"
            elif negative > positive:
                dominant_sign = "negative"
            else:
                dominant_sign = "tie"
            rows.append(
                {
                    "model": model,
                    "baseline_model": baseline_model,
                    "metric": metric,
                    "difference_definition": "model_minus_seasonal_naive",
                    "n_origins": expected_origins,
                    "mean_difference": float(difference.mean()),
                    "median_difference": float(difference.median()),
                    "sd_difference": float(difference.std(ddof=1)),
                    "min_difference": float(difference.min()),
                    "max_difference": float(difference.max()),
                    "positive_count": positive,
                    "negative_count": negative,
                    "zero_count": zero_count,
                    "dominant_nonzero_sign": dominant_sign,
                    "dominant_nonzero_sign_consistency": (
                        float(max(positive, negative) / nonzero) if nonzero else float("nan")
                    ),
                    "exact_two_sided_sign_test_p": _two_sided_sign_test_p(
                        positive, negative
                    ),
                }
            )
    return pd.DataFrame(rows)


def run_confirmatory_benchmark(
    archive_path: str | Path,
    source_config_path: str | Path,
    panel_policy_path: str | Path,
    *,
    retrieval_timestamp_utc: str,
) -> NHSGPADBenchmarkResult:
    """Run the frozen 19-origin NHS forecasting benchmark without tuning."""
    policy = load_panel_policy(panel_policy_path)
    source_config = load_gpad_config(source_config_path)
    source = _mapping(source_config["source"], "source")
    if str(source.get("expected_sha256")) != str(policy["source_archive_sha256"]):
        raise ValueError("Source config and frozen panel policy disagree on archive SHA-256.")

    quality = run_gpad_quality_gate(
        archive_path,
        source_config_path,
        retrieval_timestamp_utc=retrieval_timestamp_utc,
    )
    calendar = run_gpad_calendar_support_audit(archive_path, source_config_path)
    panel = prepare_confirmatory_panel(calendar.calendar_support, policy)
    boundaries = origin_boundaries_from_policy(policy)

    validation = _mapping(policy["validation"], "validation")
    initial_training_days = int(validation["initial_training_days"])
    first_train_end = pd.Timestamp(boundaries.iloc[0]["train_end"])
    first_train_start = pd.Timestamp(str(policy["date_start"]))
    if (first_train_end - first_train_start).days + 1 != initial_training_days:
        raise ValueError("First frozen training window does not match initial_training_days.")

    forecast_parts: list[pd.DataFrame] = []
    for row in boundaries.itertuples(index=False):
        forecast_parts.append(
            _run_origin_models(
                panel,
                origin=int(row.origin),
                train_end=pd.Timestamp(row.train_end),
                test_start=pd.Timestamp(row.test_start),
                test_end=pd.Timestamp(row.test_end),
            )
        )
    forecasts = pd.concat(forecast_parts, ignore_index=True)

    expected_origins = int(validation["outer_origins"])
    expected_per_model = (
        expected_origins
        * int(policy["geography_policy"]["eligible_geographies"])  # type: ignore[index]
        * int(validation["forecast_horizon_days"])
    )
    counts = forecasts.groupby("model", observed=True).size()
    if not (counts == expected_per_model).all():
        raise ValueError(
            "Frozen benchmark forecast row count mismatch by model: "
            f"expected={expected_per_model}, observed={counts.to_dict()}."
        )

    fold_scores = evaluate_forecasts(
        forecasts,
        actual_col="visits",
        forecast_col="forecast",
        group_cols=["origin"],
    ).sort_values(["origin", "model"])
    fold_scores = fold_scores.merge(boundaries, on="origin", how="left", validate="many_to_one")

    contrasts = paired_model_contrasts(
        fold_scores,
        expected_origins=expected_origins,
    )
    horizon_scores = evaluate_forecasts(
        forecasts,
        actual_col="visits",
        forecast_col="forecast",
        group_cols=["horizon_days"],
    ).sort_values(["horizon_days", "model"])
    horizon_band_scores = evaluate_forecasts(
        forecasts,
        actual_col="visits",
        forecast_col="forecast",
        group_cols=["horizon_band"],
    ).sort_values(["horizon_band", "model"])
    geography_scores = evaluate_forecasts(
        forecasts,
        actual_col="visits",
        forecast_col="forecast",
        group_cols=["clinic_id"],
    ).sort_values(["clinic_id", "model"])

    summary: dict[str, object] = {
        "source_archive_sha256": str(policy["source_archive_sha256"]),
        "date_start": str(policy["date_start"]),
        "date_end": str(policy["date_end"]),
        "panel_rows": len(panel),
        "eligible_geographies": int(panel["clinic_id"].nunique()),
        "outer_origins": expected_origins,
        "forecast_horizon_days": int(validation["forecast_horizon_days"]),
        "models": list(EXPECTED_MODELS),
        "forecast_rows": len(forecasts),
        "forecast_rows_per_model": counts.to_dict(),
        "primary_metrics": list(PRIMARY_METRICS),
        "paired_unit": "outer_origin",
        "real_data_estimand": "observed attended GP appointments",
        "policy_estimands_out_of_scope": [
            "latent demand",
            "usable capacity",
            "unmet demand",
            "staffing effects",
        ],
    }
    return NHSGPADBenchmarkResult(
        quality=quality,
        calendar_support=calendar,
        panel=panel,
        origin_boundaries=boundaries,
        forecasts=forecasts,
        fold_scores=fold_scores.reset_index(drop=True),
        paired_model_contrasts=contrasts.reset_index(drop=True),
        horizon_scores=horizon_scores.reset_index(drop=True),
        horizon_band_scores=horizon_band_scores.reset_index(drop=True),
        geography_scores=geography_scores.reset_index(drop=True),
        summary=summary,
    )


__all__ = [
    "NHSGPADBenchmarkResult",
    "load_panel_policy",
    "origin_boundaries_from_policy",
    "paired_model_contrasts",
    "prepare_confirmatory_panel",
    "run_confirmatory_benchmark",
]
