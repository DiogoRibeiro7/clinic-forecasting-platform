"""Dependency-free HTML dashboard for hybrid-policy monitoring."""

from __future__ import annotations

from html import escape

import pandas as pd

_REQUIRED_COLUMNS = {
    "level",
    "group",
    "n_open_days",
    "capacity_pressure_days",
    "capacity_pressure_rate",
    "attended_demand_selected_days",
    "attended_demand_selected_rate",
    "mean_completed_upper_capacity_ratio",
}


def _percentage(value: float | int) -> str:
    return f"{100.0 * float(value):.1f}%"


def _validate(frame: pd.DataFrame) -> None:
    missing = sorted(_REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ValueError(f"Hybrid monitoring dashboard is missing columns: {missing}")
    network = frame[(frame["level"] == "network") & (frame["group"] == "all")]
    if len(network) != 1:
        raise ValueError("Hybrid monitoring dashboard requires exactly one network/all row.")


def render_hybrid_monitoring_dashboard(frame: pd.DataFrame) -> str:
    """Render the latest hybrid-monitoring summary as standalone HTML."""
    _validate(frame)
    network = frame[(frame["level"] == "network") & (frame["group"] == "all")].iloc[0]
    clinics = frame[frame["level"] == "clinic"].sort_values("group")

    rows = []
    for row in clinics.itertuples(index=False):
        rows.append(
            "<tr>"
            f"<td>{escape(str(row.group))}</td>"
            f"<td>{int(row.n_open_days)}</td>"
            f"<td>{_percentage(row.capacity_pressure_rate)}</td>"
            f"<td>{_percentage(row.attended_demand_selected_rate)}</td>"
            f"<td>{float(row.mean_completed_upper_capacity_ratio):.3f}</td>"
            "</tr>"
        )

    clinic_table = "".join(rows) or '<tr><td colspan="5">No clinic rows available.</td></tr>'
    open_days = int(network["n_open_days"])
    pressure_rate = _percentage(network["capacity_pressure_rate"])
    selected_rate = _percentage(network["attended_demand_selected_rate"])

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hybrid policy monitoring</title>
  <style>
    body {{
      font-family: system-ui, sans-serif;
      max-width: 1100px;
      margin: 2rem auto;
      padding: 0 1rem;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 1rem;
    }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }}
    .value {{ font-size: 2rem; font-weight: 700; margin-top: .25rem; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 2rem; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: .65rem; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    .note {{ color: #555; margin-top: 1rem; }}
  </style>
</head>
<body>
  <h1>Hybrid policy monitoring</h1>
  <p class="note">
    Descriptive latest-run monitoring only.
    These rates are not realised switch precision or recall.
  </p>
  <section class="cards">
    <div class="card">
      <div>Open clinic-days</div>
      <div class="value">{open_days}</div>
    </div>
    <div class="card">
      <div>Capacity-pressure rate</div>
      <div class="value">{pressure_rate}</div>
    </div>
    <div class="card">
      <div>Attended-demand selected rate</div>
      <div class="value">{selected_rate}</div>
    </div>
  </section>
  <h2>Clinic detail</h2>
  <table>
    <thead>
      <tr>
        <th>Clinic</th>
        <th>Open days</th>
        <th>Pressure rate</th>
        <th>Attended selected</th>
        <th>Upper/capacity ratio</th>
      </tr>
    </thead>
    <tbody>{clinic_table}</tbody>
  </table>
</body>
</html>
"""


__all__ = ["render_hybrid_monitoring_dashboard"]
