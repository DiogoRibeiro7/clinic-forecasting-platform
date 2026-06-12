"""No-show and cancellation forecasting.

Scheduled demand and realised demand are different operational quantities:
rooms and front-desk load follow the *schedule*, clinical workload follows
*completed visits*, and the gap between them — no-shows plus same-day
cancellations — is itself forecastable. This module adds the second target:

- :func:`build_noshow_targets` derives the realised attrition quantities.
- :func:`forecast_attrition_rate_baseline` — per-clinic (optionally
  per-weekday) historical mean rate, the baseline any model must beat.
- :class:`AttritionRateForecaster` — the global ML model retargeted at the
  attrition rate, with same-day outcome columns (including visits) removed
  so the rate is predicted from history and calendar only.
- :func:`expected_completed_visits` converts a schedule forecast plus a rate
  forecast into expected completed visits.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from clinic_forecast.models.global_ml import GlobalMLForecaster

ATTRITION_TARGET = "attrition_rate"

#: Columns that are same-day outcomes relative to the attrition target.
_LEAKY_FOR_RATE = ("visits", "capacity_utilization")


def build_noshow_targets(usage: pd.DataFrame) -> pd.DataFrame:
    """Derive attrition targets from the usage table.

    Adds, per clinic-day:

    - ``realised_no_show_rate`` = no-shows / scheduled (0 on closed days);
    - ``cancellation_rate`` = cancellations / scheduled (0 on closed days);
    - ``attrition_rate`` = (no-shows + cancellations) / scheduled — the share
      of the schedule that produced no completed visit.
    """
    required = {"scheduled_appointments", "no_show_count", "same_day_cancellations"}
    missing = required.difference(usage.columns)
    if missing:
        raise ValueError(f"Usage data missing required columns: {sorted(missing)}")

    frame = usage.copy()
    scheduled = frame["scheduled_appointments"].astype(float)
    safe = scheduled.replace(0, np.nan)
    frame["realised_no_show_rate"] = (frame["no_show_count"] / safe).fillna(0.0)
    frame["cancellation_rate"] = (frame["same_day_cancellations"] / safe).fillna(0.0)
    frame[ATTRITION_TARGET] = (
        (frame["no_show_count"] + frame["same_day_cancellations"]) / safe
    ).fillna(0.0)
    return frame


def forecast_attrition_rate_baseline(
    train: pd.DataFrame,
    future: pd.DataFrame,
    by_weekday: bool = True,
) -> pd.DataFrame:
    """Baseline attrition-rate forecast: per-clinic historical mean rate.

    With ``by_weekday`` the mean is computed per clinic and day of week,
    capturing the Monday effect; clinic-weekday cells unseen in training fall
    back to the clinic mean.
    """
    train_targets = build_noshow_targets(train)
    open_train = train_targets[train_targets["scheduled_appointments"] > 0].copy()

    clinic_mean = open_train.groupby("clinic_id", observed=True)[ATTRITION_TARGET].mean()
    output = future[["clinic_id", "date"]].copy()
    output["date"] = pd.to_datetime(output["date"])

    if by_weekday:
        open_train["dow"] = pd.to_datetime(open_train["date"]).dt.dayofweek
        cell_mean = open_train.groupby(["clinic_id", "dow"], observed=True)[
            ATTRITION_TARGET
        ].mean()
        output["dow"] = output["date"].dt.dayofweek
        keys = pd.MultiIndex.from_frame(output[["clinic_id", "dow"]])
        output["forecast"] = cell_mean.reindex(keys).to_numpy()
        output = output.drop(columns="dow")
    else:
        output["forecast"] = np.nan
    output["forecast"] = output["forecast"].fillna(
        output["clinic_id"].map(clinic_mean)
    )
    output["model"] = "attrition_historical_mean"
    return output


@dataclass
class AttritionRateForecaster:
    """Global ML regression for the attrition rate.

    Wraps :class:`GlobalMLForecaster` with the rate target and removes
    same-day outcome columns (notably ``visits``) so the rate is predicted
    from its own history, calendar structure and clinic identity only.
    """

    random_state: int = 42
    _model: GlobalMLForecaster = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._model = GlobalMLForecaster(
            target_col=ATTRITION_TARGET, random_state=self.random_state
        )

    @staticmethod
    def _rate_frame(usage: pd.DataFrame) -> pd.DataFrame:
        frame = build_noshow_targets(usage)
        drop = [c for c in _LEAKY_FOR_RATE if c in frame.columns]
        return frame.drop(columns=drop)

    def fit(self, train: pd.DataFrame) -> AttritionRateForecaster:
        """Fit on historical usage (targets derived internally)."""
        self._model.fit(self._rate_frame(train))
        return self

    @property
    def feature_columns_(self) -> list[str] | None:
        """Feature columns used by the underlying model."""
        return self._model.feature_columns_

    def predict_known_future(self, usage: pd.DataFrame) -> pd.DataFrame:
        """Backtest-style prediction; rates are clipped to [0, 1]."""
        prediction = self._model.predict_known_future(self._rate_frame(usage))
        prediction["forecast"] = prediction["forecast"].clip(0.0, 1.0)
        prediction["model"] = "attrition_global_ml"
        return prediction


def expected_completed_visits(
    schedule_forecast: pd.DataFrame,
    rate_forecast: pd.DataFrame,
    schedule_col: str = "forecast",
    rate_col: str = "forecast",
) -> pd.DataFrame:
    """Combine a schedule forecast with an attrition-rate forecast.

    Returns one row per clinic-day with ``scheduled``, ``attrition_rate`` and
    ``expected_completed`` = scheduled x (1 - rate).
    """
    schedule = schedule_forecast[["clinic_id", "date", schedule_col]].rename(
        columns={schedule_col: "scheduled"}
    )
    rates = rate_forecast[["clinic_id", "date", rate_col]].rename(
        columns={rate_col: "attrition_rate"}
    )
    combined = schedule.merge(rates, on=["clinic_id", "date"], how="inner")
    combined["attrition_rate"] = combined["attrition_rate"].clip(0.0, 1.0)
    combined["expected_completed"] = combined["scheduled"] * (1 - combined["attrition_rate"])
    return combined
