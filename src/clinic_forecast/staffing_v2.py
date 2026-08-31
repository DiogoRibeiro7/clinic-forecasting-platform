"""Decision-layer v2 staffing costs with clinician and nurse bottlenecks.

This module deliberately does not replace :mod:`clinic_forecast.staffing`.
The legacy evaluator remains unchanged so previously committed staffing and
hybrid-policy evidence retains its original semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from clinic_forecast.staffing import StaffingCosts, StaffingRules


@dataclass(frozen=True)
class ClinicalCandidateCost:
    """Scalar clinical cost components for one candidate staffing pair."""

    total_cost: float
    regular_clinical_cost: float
    clinician_overtime_cost: float
    nurse_overtime_cost: float
    understaffing_cost: float
    idle_clinical_cost: float
    unmet_visits: float


def clinical_candidate_cost(
    demand: float,
    clinicians: int,
    nurses: int,
    rules: StaffingRules,
    costs: StaffingCosts,
) -> ClinicalCandidateCost:
    """Cost one clinician/nurse pair under the frozen two-resource service model."""
    rules.validate()
    costs.validate()
    if clinicians < 0 or nurses < 0:
        raise ValueError("Clinical headcounts cannot be negative.")

    demand_value = max(float(demand), 0.0)
    clinician_capacity = clinicians * rules.visits_per_clinician_day
    nurse_capacity = nurses * rules.visits_per_nurse_day
    clinician_stretch = clinician_capacity * rules.overtime_threshold
    nurse_stretch = nurse_capacity * rules.overtime_threshold

    served = min(demand_value, clinician_stretch, nurse_stretch)
    unmet = max(demand_value - served, 0.0)
    clinician_overtime = max(served - clinician_capacity, 0.0)
    nurse_overtime = max(served - nurse_capacity, 0.0)
    clinician_idle = max(clinician_capacity - served, 0.0)
    nurse_idle = max(nurse_capacity - served, 0.0)

    regular_clinical_cost = (
        clinicians * costs.clinician_day_cost + nurses * costs.nurse_day_cost
    )
    clinician_overtime_cost = (
        clinician_overtime
        / rules.visits_per_clinician_day
        * costs.clinician_day_cost
        * costs.overtime_multiplier
    )
    nurse_overtime_cost = (
        nurse_overtime
        / rules.visits_per_nurse_day
        * costs.nurse_day_cost
        * costs.overtime_multiplier
    )
    understaffing_cost = unmet * costs.understaffing_penalty_per_visit
    idle_clinical_cost = costs.idle_penalty_ratio * (
        clinician_idle / rules.visits_per_clinician_day * costs.clinician_day_cost
        + nurse_idle / rules.visits_per_nurse_day * costs.nurse_day_cost
    )
    total_cost = (
        regular_clinical_cost
        + clinician_overtime_cost
        + nurse_overtime_cost
        + understaffing_cost
        + idle_clinical_cost
    )
    return ClinicalCandidateCost(
        total_cost=total_cost,
        regular_clinical_cost=regular_clinical_cost,
        clinician_overtime_cost=clinician_overtime_cost,
        nurse_overtime_cost=nurse_overtime_cost,
        understaffing_cost=understaffing_cost,
        idle_clinical_cost=idle_clinical_cost,
        unmet_visits=unmet,
    )


def staffing_plan_cost_v2(
    plan: pd.DataFrame,
    demand_col: str = "visits",
    clinician_col: str = "recommended_clinicians",
    nurse_col: str = "recommended_nurses",
    frontdesk_col: str = "recommended_frontdesk",
    rules: StaffingRules | None = None,
    costs: StaffingCosts | None = None,
) -> pd.DataFrame:
    """Cost a staffing plan with both clinical roles constraining service.

    The served clinical volume is bounded by the overtime-stretched capacity
    of both clinicians and nurses. Front-desk cost is regular headcount cost
    only and is identical across the primary optimiser benchmark policies.
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
    if (frame[[clinician_col, nurse_col, frontdesk_col]] < 0).any().any():
        raise ValueError("Staffing headcounts cannot be negative.")

    demand = frame[demand_col].clip(lower=0).astype(float)
    clinician_capacity = (
        frame[clinician_col].astype(float) * staffing_rules.visits_per_clinician_day
    )
    nurse_capacity = frame[nurse_col].astype(float) * staffing_rules.visits_per_nurse_day
    clinician_stretch = clinician_capacity * staffing_rules.overtime_threshold
    nurse_stretch = nurse_capacity * staffing_rules.overtime_threshold
    served = pd.concat(
        [demand, clinician_stretch, nurse_stretch],
        axis=1,
    ).min(axis=1)

    unmet = (demand - served).clip(lower=0)
    clinician_overtime = (served - clinician_capacity).clip(lower=0)
    nurse_overtime = (served - nurse_capacity).clip(lower=0)
    clinician_idle = (clinician_capacity - served).clip(lower=0)
    nurse_idle = (nurse_capacity - served).clip(lower=0)

    frame["clinical_regular_capacity"] = pd.concat(
        [clinician_capacity, nurse_capacity], axis=1
    ).min(axis=1)
    frame["served_visits"] = served
    frame["regular_clinical_cost"] = (
        frame[clinician_col] * cost_model.clinician_day_cost
        + frame[nurse_col] * cost_model.nurse_day_cost
    )
    frame["frontdesk_regular_cost"] = frame[frontdesk_col] * cost_model.frontdesk_day_cost
    frame["regular_cost"] = frame["regular_clinical_cost"] + frame["frontdesk_regular_cost"]
    frame["clinician_overtime_cost"] = (
        clinician_overtime
        / staffing_rules.visits_per_clinician_day
        * cost_model.clinician_day_cost
        * cost_model.overtime_multiplier
    )
    frame["nurse_overtime_cost"] = (
        nurse_overtime
        / staffing_rules.visits_per_nurse_day
        * cost_model.nurse_day_cost
        * cost_model.overtime_multiplier
    )
    frame["overtime_cost"] = (
        frame["clinician_overtime_cost"] + frame["nurse_overtime_cost"]
    )
    frame["understaffing_cost"] = unmet * cost_model.understaffing_penalty_per_visit
    frame["clinician_idle_cost"] = (
        clinician_idle
        / staffing_rules.visits_per_clinician_day
        * cost_model.clinician_day_cost
        * cost_model.idle_penalty_ratio
    )
    frame["nurse_idle_cost"] = (
        nurse_idle
        / staffing_rules.visits_per_nurse_day
        * cost_model.nurse_day_cost
        * cost_model.idle_penalty_ratio
    )
    frame["idle_clinical_cost"] = frame["clinician_idle_cost"] + frame["nurse_idle_cost"]
    frame["idle_cost"] = frame["idle_clinical_cost"]
    frame["total_cost"] = (
        frame["regular_cost"]
        + frame["overtime_cost"]
        + frame["understaffing_cost"]
        + frame["idle_clinical_cost"]
    )
    frame["unmet_visits"] = unmet
    return frame


__all__ = [
    "ClinicalCandidateCost",
    "clinical_candidate_cost",
    "staffing_plan_cost_v2",
]
