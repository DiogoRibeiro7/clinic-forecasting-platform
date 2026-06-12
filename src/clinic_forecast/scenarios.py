"""What-if scenario planning for marketing-driven demand.

A scenario edits the *known future inputs* (planned marketing spend by
channel, campaign flags) for selected clinics or regions, re-runs the
forecasting model on the edited future, and compares demand and staffing
against the baseline plan.

This is model-based what-if analysis, not causal inference: the model's
spend-demand relationship is predictive (learned from observational history
where campaigns correlate with seasons), so scenario deltas should be read as
"what the model expects under this plan", never as proof of marketing
effectiveness.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from clinic_forecast.models.global_ml import GlobalMLForecaster
from clinic_forecast.staffing import StaffingRules, recommend_staffing

SPEND_CHANNEL_PREFIX = "spend_"


@dataclass(frozen=True)
class MarketingScenario:
    """One edit to the planned marketing inputs.

    Parameters
    ----------
    name:
        Scenario label used in output frames.
    spend_multiplier:
        Scales planned spend on the selected channels/clinics.
    channels:
        Channel names (e.g. ``("search", "social")``) to scale; all spend
        channels when None.
    clinic_ids / regions:
        Restrict the edit to these clinics or regions; the whole network
        when both are None. Regions require metadata.
    set_campaign_active:
        Force the campaign flag on (True) or off (False) for selected rows.
    """

    name: str
    spend_multiplier: float = 1.0
    channels: tuple[str, ...] | None = None
    clinic_ids: tuple[str, ...] | None = None
    regions: tuple[str, ...] | None = None
    set_campaign_active: bool | None = None

    def validate(self) -> None:
        """Validate scenario parameters."""
        if self.spend_multiplier < 0:
            raise ValueError("spend_multiplier cannot be negative.")
        if not self.name:
            raise ValueError("Scenario name cannot be empty.")


def apply_marketing_scenario(
    future: pd.DataFrame,
    scenario: MarketingScenario,
    metadata: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return a copy of the future inputs with the scenario edits applied.

    Spend channel columns (``spend_*``) are scaled and ``marketing_spend`` is
    recomputed as their sum, keeping the inputs internally consistent.
    """
    scenario.validate()
    frame = future.copy()

    mask = pd.Series(True, index=frame.index)
    if scenario.clinic_ids is not None:
        unknown = set(scenario.clinic_ids) - set(frame["clinic_id"].unique())
        if unknown:
            raise ValueError(f"Unknown clinic_ids in scenario: {sorted(unknown)}")
        mask &= frame["clinic_id"].isin(scenario.clinic_ids)
    if scenario.regions is not None:
        if "region" in frame.columns:
            region_of = frame["region"]
        elif metadata is not None:
            region_map = metadata.set_index("clinic_id")["region"]
            region_of = frame["clinic_id"].map(region_map)
        else:
            raise ValueError("Region scenarios need a region column or metadata.")
        unknown = set(scenario.regions) - set(region_of.dropna().unique())
        if unknown:
            raise ValueError(f"Unknown regions in scenario: {sorted(unknown)}")
        mask &= region_of.isin(scenario.regions)

    channel_cols = [c for c in frame.columns if c.startswith(SPEND_CHANNEL_PREFIX)]
    if scenario.channels is not None:
        requested = [f"{SPEND_CHANNEL_PREFIX}{name}" for name in scenario.channels]
        unknown_channels = sorted(set(requested) - set(channel_cols))
        if unknown_channels:
            raise ValueError(f"Unknown spend channels: {unknown_channels}")
        channel_cols = requested

    for column in channel_cols:
        frame.loc[mask, column] = frame.loc[mask, column] * scenario.spend_multiplier

    all_channels = [c for c in frame.columns if c.startswith(SPEND_CHANNEL_PREFIX)]
    if all_channels:
        frame["marketing_spend"] = frame[all_channels].sum(axis=1)
    elif "marketing_spend" in frame.columns:
        frame.loc[mask, "marketing_spend"] = (
            frame.loc[mask, "marketing_spend"] * scenario.spend_multiplier
        )

    if scenario.set_campaign_active is not None and "campaign_active" in frame.columns:
        frame.loc[mask, "campaign_active"] = int(scenario.set_campaign_active)
    return frame


def scenario_forecasts(
    model: GlobalMLForecaster,
    history: pd.DataFrame,
    future: pd.DataFrame,
    scenarios: list[MarketingScenario],
    metadata: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Forecast the baseline plus each scenario; return one long frame.

    The output has a ``scenario`` column ("baseline" first) and, for each
    scenario row, ``incremental_visits`` versus the baseline forecast for the
    same clinic-day.
    """
    baseline = model.forecast(history=history, future=future).assign(scenario="baseline")
    frames = [baseline]
    for scenario in scenarios:
        edited = apply_marketing_scenario(future, scenario, metadata=metadata)
        forecast = model.forecast(history=history, future=edited)
        frames.append(forecast.assign(scenario=scenario.name))

    combined = pd.concat(frames, ignore_index=True)
    baseline_lookup = baseline.set_index(["clinic_id", "date"])["forecast"]
    keys = pd.MultiIndex.from_frame(combined[["clinic_id", "date"]])
    combined["incremental_visits"] = combined["forecast"] - baseline_lookup.reindex(keys).values
    return combined


def scenario_staffing_impact(
    forecasts: pd.DataFrame,
    rules: StaffingRules | None = None,
) -> pd.DataFrame:
    """Summarise demand and clinician-staffing impact per scenario.

    Returns one row per scenario with total forecast visits, incremental
    visits vs baseline, total clinician-days and the clinician-day delta.
    """
    staffing_rules = rules or StaffingRules()
    rows = []
    for scenario, frame in forecasts.groupby("scenario", observed=True):
        plan = recommend_staffing(frame, forecast_col="forecast", rules=staffing_rules)
        rows.append(
            {
                "scenario": scenario,
                "total_visits": float(frame["forecast"].sum()),
                "incremental_visits": float(frame["incremental_visits"].sum()),
                "clinician_days": int(plan["recommended_clinicians"].sum()),
            }
        )
    summary = pd.DataFrame(rows).set_index("scenario")
    summary["clinician_day_delta"] = (
        summary["clinician_days"] - summary.loc["baseline", "clinician_days"]
    )
    return summary.sort_values("total_visits").reset_index()
