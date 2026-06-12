"""Convert clinic demand forecasts into staffing recommendations and costs.

The decision layer is rule-based and fully transparent: every number traces
to an assumption in ``configs/staffing.yaml``. Three pieces compose:

- :class:`StaffingRules` — productivity, minimums, maximum roster capacity
  and the overtime stretch threshold.
- :class:`StaffingCosts` — day rates per role, the overtime premium, an
  understaffing penalty per unserved visit and an idle-capacity penalty.
- :func:`compare_staffing_scenarios` — costs alternative staffing plans
  (e.g. current static roster vs forecast-mean vs conservative upper-bound)
  against realised demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from pathlib import Path

import pandas as pd
import yaml

from clinic_forecast.contracts import validate_staffing_rules


@dataclass(frozen=True)
class StaffingRules:
    """Productivity, coverage and capacity assumptions for staffing conversion."""

    visits_per_clinician_day: int = 18
    visits_per_nurse_day: int = 24
    visits_per_frontdesk_day: int = 35
    minimum_clinicians: int = 1
    minimum_nurses: int = 1
    minimum_frontdesk: int = 1
    buffer_ratio: float = 0.12
    max_clinicians: int | None = None
    max_nurses: int | None = None
    max_frontdesk: int | None = None
    overtime_threshold: float = 1.2

    def validate(self) -> None:
        """Validate staffing rules."""
        positive_ints = [
            self.visits_per_clinician_day,
            self.visits_per_nurse_day,
            self.visits_per_frontdesk_day,
            self.minimum_clinicians,
            self.minimum_nurses,
            self.minimum_frontdesk,
        ]
        if any(value <= 0 for value in positive_ints):
            raise ValueError("Staffing productivity and minimums must be positive.")
        if self.buffer_ratio < 0:
            raise ValueError("buffer_ratio cannot be negative.")
        if self.overtime_threshold < 1.0:
            raise ValueError("overtime_threshold must be at least 1.0 (1.0 disables overtime).")
        for name, maximum, minimum in [
            ("max_clinicians", self.max_clinicians, self.minimum_clinicians),
            ("max_nurses", self.max_nurses, self.minimum_nurses),
            ("max_frontdesk", self.max_frontdesk, self.minimum_frontdesk),
        ]:
            if maximum is not None and maximum < minimum:
                raise ValueError(f"{name} cannot be below the corresponding minimum.")


@dataclass(frozen=True)
class StaffingCosts:
    """Cost assumptions for staffing plans (currency units per day or visit)."""

    clinician_day_cost: float = 600.0
    nurse_day_cost: float = 350.0
    frontdesk_day_cost: float = 200.0
    overtime_multiplier: float = 1.5
    understaffing_penalty_per_visit: float = 80.0
    idle_penalty_ratio: float = 0.5

    def validate(self) -> None:
        """Validate cost assumptions."""
        if min(self.clinician_day_cost, self.nurse_day_cost, self.frontdesk_day_cost) <= 0:
            raise ValueError("Day costs must be positive.")
        if self.overtime_multiplier < 1.0:
            raise ValueError("overtime_multiplier must be at least 1.0.")
        if self.understaffing_penalty_per_visit < 0 or self.idle_penalty_ratio < 0:
            raise ValueError("Penalties cannot be negative.")


def load_staffing_config(path: str | Path) -> tuple[StaffingRules, StaffingCosts]:
    """Load and validate staffing rules and costs from a YAML config file."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "staffing" not in raw:
        raise ValueError(f"Config {path} must contain a 'staffing' section.")
    validate_staffing_rules(raw["staffing"])
    rules = StaffingRules(**raw["staffing"])
    rules.validate()
    costs = StaffingCosts(**raw.get("costs", {}))
    costs.validate()
    return rules, costs


def recommend_staffing(
    forecast: pd.DataFrame,
    forecast_col: str = "forecast",
    rules: StaffingRules | None = None,
) -> pd.DataFrame:
    """Convert forecasted demand into staffing recommendations.

    Recommendations respect role minimums and, when configured, maximum
    roster capacity per clinic (`max_*` in the rules).
    """
    if forecast_col not in forecast.columns:
        raise ValueError(f"Missing forecast column: {forecast_col}")

    staffing_rules = rules or StaffingRules()
    staffing_rules.validate()
    frame = forecast.copy()
    buffered_demand = frame[forecast_col].clip(lower=0) * (1 + staffing_rules.buffer_ratio)

    def _required_staff(
        visits_per_staff_day: int, minimum: int, maximum: int | None
    ) -> pd.Series:
        staff = buffered_demand.apply(
            lambda value: max(minimum, ceil(value / visits_per_staff_day))
        )
        if maximum is not None:
            staff = staff.clip(upper=maximum)
        return staff

    frame["recommended_clinicians"] = _required_staff(
        staffing_rules.visits_per_clinician_day,
        staffing_rules.minimum_clinicians,
        staffing_rules.max_clinicians,
    )
    frame["recommended_nurses"] = _required_staff(
        staffing_rules.visits_per_nurse_day,
        staffing_rules.minimum_nurses,
        staffing_rules.max_nurses,
    )
    frame["recommended_frontdesk"] = _required_staff(
        staffing_rules.visits_per_frontdesk_day,
        staffing_rules.minimum_frontdesk,
        staffing_rules.max_frontdesk,
    )
    return frame


def staffing_gap(
    recommended: pd.DataFrame,
    metadata: pd.DataFrame,
    id_col: str = "clinic_id",
) -> pd.DataFrame:
    """Compare recommended staffing with baseline staffing levels."""
    required = {id_col, "base_clinicians", "base_nurses", "base_frontdesk"}
    missing = required.difference(metadata.columns)
    if missing:
        raise ValueError(f"Metadata missing required columns: {sorted(missing)}")

    frame = recommended.merge(metadata[list(required)], on=id_col, how="left")
    frame["clinician_gap"] = frame["recommended_clinicians"] - frame["base_clinicians"]
    frame["nurse_gap"] = frame["recommended_nurses"] - frame["base_nurses"]
    frame["frontdesk_gap"] = frame["recommended_frontdesk"] - frame["base_frontdesk"]
    return frame


def staffing_plan_cost(
    plan: pd.DataFrame,
    demand_col: str = "visits",
    clinician_col: str = "recommended_clinicians",
    nurse_col: str = "recommended_nurses",
    frontdesk_col: str = "recommended_frontdesk",
    rules: StaffingRules | None = None,
    costs: StaffingCosts | None = None,
) -> pd.DataFrame:
    """Cost a staffing plan against (realised or assumed) demand.

    Cost components per clinic-day, computed on the clinician dimension
    (the binding clinical resource) plus regular costs for all roles:

    - ``regular_cost``: staffed headcount x day rates for all three roles.
    - ``overtime_cost``: demand above regular clinician capacity, served by
      stretching up to ``overtime_threshold`` x capacity at the overtime
      premium.
    - ``understaffing_cost``: demand beyond even the overtime stretch,
      penalised per unserved visit.
    - ``idle_cost``: spare clinician capacity, charged at a fraction of the
      day rate (idle staff still cost money but retain some option value).
    """
    staffing_rules = rules or StaffingRules()
    staffing_rules.validate()
    cost_model = costs or StaffingCosts()
    cost_model.validate()

    required = {demand_col, clinician_col, nurse_col, frontdesk_col}
    missing = required.difference(plan.columns)
    if missing:
        raise ValueError(f"Plan missing required columns: {sorted(missing)}")

    frame = plan.copy()
    demand = frame[demand_col].clip(lower=0)
    capacity = frame[clinician_col] * staffing_rules.visits_per_clinician_day
    stretch_capacity = capacity * (staffing_rules.overtime_threshold - 1.0)

    overflow = (demand - capacity).clip(lower=0)
    served_overtime = pd.concat([overflow, stretch_capacity], axis=1).min(axis=1)
    unmet = overflow - served_overtime
    idle = (capacity - demand).clip(lower=0)

    frame["regular_cost"] = (
        frame[clinician_col] * cost_model.clinician_day_cost
        + frame[nurse_col] * cost_model.nurse_day_cost
        + frame[frontdesk_col] * cost_model.frontdesk_day_cost
    )
    overtime_days = served_overtime / staffing_rules.visits_per_clinician_day
    frame["overtime_cost"] = (
        overtime_days * cost_model.clinician_day_cost * cost_model.overtime_multiplier
    )
    frame["understaffing_cost"] = unmet * cost_model.understaffing_penalty_per_visit
    idle_days = idle / staffing_rules.visits_per_clinician_day
    frame["idle_cost"] = (
        idle_days * cost_model.clinician_day_cost * cost_model.idle_penalty_ratio
    )
    frame["total_cost"] = (
        frame["regular_cost"]
        + frame["overtime_cost"]
        + frame["understaffing_cost"]
        + frame["idle_cost"]
    )
    frame["unmet_visits"] = unmet
    return frame


def compare_staffing_scenarios(
    scenarios: dict[str, pd.DataFrame],
    rules: StaffingRules | None = None,
    costs: StaffingCosts | None = None,
    demand_col: str = "visits",
) -> pd.DataFrame:
    """Summarise total costs for alternative staffing plans against demand.

    Parameters
    ----------
    scenarios:
        Mapping of scenario name to a plan frame holding the demand column
        and the three ``recommended_*`` staffing columns.

    Returns
    -------
    pandas.DataFrame
        One row per scenario with summed cost components, total cost and
        understaffed clinic-day counts, sorted by total cost.
    """
    rows: list[dict[str, object]] = []
    for name, plan in scenarios.items():
        costed = staffing_plan_cost(plan, demand_col=demand_col, rules=rules, costs=costs)
        rows.append(
            {
                "scenario": name,
                "regular_cost": costed["regular_cost"].sum(),
                "overtime_cost": costed["overtime_cost"].sum(),
                "understaffing_cost": costed["understaffing_cost"].sum(),
                "idle_cost": costed["idle_cost"].sum(),
                "total_cost": costed["total_cost"].sum(),
                "understaffed_days": int((costed["unmet_visits"] > 0).sum()),
                "clinician_days": int(costed["recommended_clinicians"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("total_cost").reset_index(drop=True)
