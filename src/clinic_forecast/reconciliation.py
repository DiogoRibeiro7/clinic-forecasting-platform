"""Hierarchical aggregation and forecast reconciliation.

The network has a three-level hierarchy: clinics roll up to regions, regions
roll up to the network total. Forecasts made independently at different
levels almost never agree — clinic forecasts summed up do not match a
network-level forecast — which destroys trust the first time a regional
budget meeting and a clinic roster quote different numbers.

Reconciliation makes one coherent set of numbers. Three transparent methods:

- **Bottom-up**: sum clinic forecasts to get region and network numbers.
  Coherent by construction; quality depends entirely on the clinic model.
- **Top-down**: forecast the network total, split it down to clinics using
  historical proportions. Robust totals, blind to clinic-level dynamics.
- **Middle-out**: forecast regions, split down to clinics by within-region
  proportions and sum up to the network.
"""

from __future__ import annotations

import pandas as pd

LEVELS = ("clinic", "region", "network")
NETWORK_NODE = "network"


def _with_region(frame: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    if "region" in frame.columns:
        return frame.copy()
    return frame.merge(metadata[["clinic_id", "region"]], on="clinic_id", how="left")


def build_hierarchy_frame(
    data: pd.DataFrame,
    metadata: pd.DataFrame,
    value_col: str = "visits",
) -> pd.DataFrame:
    """Aggregate a clinic-level frame to all hierarchy levels.

    Returns a long frame with columns ``level``, ``node``, ``date`` and
    ``value_col``: one row per clinic-date, region-date and network-date.
    """
    frame = _with_region(data, metadata)
    clinic = frame[["clinic_id", "date", value_col]].rename(columns={"clinic_id": "node"})
    clinic["level"] = "clinic"

    region = (
        frame.groupby(["region", "date"], as_index=False, observed=True)[value_col]
        .sum()
        .rename(columns={"region": "node"})
    )
    region["level"] = "region"

    network = frame.groupby("date", as_index=False)[value_col].sum()
    network["node"] = NETWORK_NODE
    network["level"] = "network"

    columns = ["level", "node", "date", value_col]
    return pd.concat([clinic[columns], region[columns], network[columns]], ignore_index=True)


def historical_proportions(
    usage: pd.DataFrame,
    metadata: pd.DataFrame,
    within: str = "network",
    value_col: str = "visits",
) -> pd.Series:
    """Average historical share of each clinic within the network or its region.

    Parameters
    ----------
    within:
        ``"network"`` gives each clinic's share of network volume;
        ``"region"`` gives each clinic's share of its own region's volume.
    """
    if within not in ("network", "region"):
        raise ValueError("within must be 'network' or 'region'.")
    frame = _with_region(usage, metadata)
    clinic_totals = frame.groupby("clinic_id", observed=True)[value_col].sum()
    if within == "network":
        return clinic_totals / clinic_totals.sum()
    region_of = metadata.set_index("clinic_id")["region"]
    region_totals = clinic_totals.groupby(region_of).transform("sum")
    return clinic_totals / region_totals


def reconcile_bottom_up(
    clinic_forecasts: pd.DataFrame,
    metadata: pd.DataFrame,
    forecast_col: str = "forecast",
) -> pd.DataFrame:
    """Sum clinic-level forecasts up the hierarchy (coherent by construction)."""
    required = {"clinic_id", "date", forecast_col}
    missing = required.difference(clinic_forecasts.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    hierarchy = build_hierarchy_frame(clinic_forecasts, metadata, value_col=forecast_col)
    hierarchy["method"] = "bottom_up"
    return hierarchy


def reconcile_top_down(
    network_forecast: pd.DataFrame,
    usage: pd.DataFrame,
    metadata: pd.DataFrame,
    forecast_col: str = "forecast",
) -> pd.DataFrame:
    """Split a network-total forecast down to clinics by historical proportions.

    Parameters
    ----------
    network_forecast:
        One row per date with the network-total forecast.
    usage:
        Historical clinic-level data used to estimate proportions.
    """
    if not {"date", forecast_col}.issubset(network_forecast.columns):
        raise ValueError(f"network_forecast needs columns ['date', '{forecast_col}'].")
    shares = historical_proportions(usage, metadata, within="network")

    clinic_rows = []
    for clinic_id, share in shares.items():
        rows = network_forecast[["date", forecast_col]].copy()
        rows["clinic_id"] = clinic_id
        rows[forecast_col] = rows[forecast_col] * share
        clinic_rows.append(rows)
    clinics = pd.concat(clinic_rows, ignore_index=True)

    hierarchy = build_hierarchy_frame(clinics, metadata, value_col=forecast_col)
    hierarchy["method"] = "top_down"
    return hierarchy


def reconcile_middle_out(
    region_forecasts: pd.DataFrame,
    usage: pd.DataFrame,
    metadata: pd.DataFrame,
    forecast_col: str = "forecast",
) -> pd.DataFrame:
    """Split region-level forecasts to clinics; sum regions to the network.

    Parameters
    ----------
    region_forecasts:
        One row per (region, date) with the regional forecast.
    """
    if not {"region", "date", forecast_col}.issubset(region_forecasts.columns):
        raise ValueError(
            f"region_forecasts needs columns ['region', 'date', '{forecast_col}']."
        )
    shares = historical_proportions(usage, metadata, within="region")
    region_of = metadata.set_index("clinic_id")["region"]

    clinic_rows = []
    for clinic_id, share in shares.items():
        region = region_of[clinic_id]
        rows = region_forecasts[region_forecasts["region"] == region][
            ["date", forecast_col]
        ].copy()
        rows["clinic_id"] = clinic_id
        rows[forecast_col] = rows[forecast_col] * share
        clinic_rows.append(rows)
    clinics = pd.concat(clinic_rows, ignore_index=True)

    hierarchy = build_hierarchy_frame(clinics, metadata, value_col=forecast_col)
    hierarchy["method"] = "middle_out"
    return hierarchy


def assert_coherent(
    hierarchy: pd.DataFrame,
    metadata: pd.DataFrame | None = None,
    value_col: str = "forecast",
    tolerance: float = 1e-6,
) -> None:
    """Raise if clinic values do not sum to region and network values.

    When metadata is provided, clinic-to-region sums are checked per region;
    clinic-to-network and region-to-network sums are always checked.
    """
    clinic = hierarchy[hierarchy["level"] == "clinic"]
    region = hierarchy[hierarchy["level"] == "region"]
    network = hierarchy[hierarchy["level"] == "network"].set_index("date")[value_col]

    clinic_to_network = clinic.groupby("date")[value_col].sum()
    if not (clinic_to_network - network).abs().le(tolerance).all():
        raise AssertionError("Clinic forecasts do not sum to the network forecast.")

    region_to_network = region.groupby("date")[value_col].sum()
    if not (region_to_network - network).abs().le(tolerance).all():
        raise AssertionError("Region forecasts do not sum to the network forecast.")

    if metadata is not None:
        region_of = metadata.set_index("clinic_id")["region"]
        clinic_regions = clinic.assign(region=clinic["node"].map(region_of))
        clinic_to_region = clinic_regions.groupby(["region", "date"], observed=True)[
            value_col
        ].sum()
        region_values = region.set_index(["node", "date"])[value_col]
        region_values.index.names = ["region", "date"]
        diff = (clinic_to_region - region_values).abs()
        if not diff.le(tolerance).all():
            raise AssertionError("Clinic forecasts do not sum to their region forecasts.")
