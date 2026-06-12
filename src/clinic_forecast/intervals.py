"""Split conformal prediction intervals for demand forecasts.

The approach is deliberately simple and assumption-light: absolute residuals
from past validation folds form a calibration set, and the empirical
``coverage`` quantile of those residuals (with the standard finite-sample
correction) becomes a symmetric half-width around new point forecasts.

Optional grouped calibration (by clinic, region or volume tier) gives each
group its own half-width; groups with too little calibration data fall back
to the global quantile, as do groups never seen during calibration.

Honest caveats, also surfaced in the notebooks: split conformal assumes
calibration and future residuals are exchangeable. Demand episodes violate
this locally (residuals cluster), so realised coverage on a specific month
can deviate from the nominal level even when long-run coverage holds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


def _conformal_quantile(abs_residuals: np.ndarray, coverage: float) -> float:
    """Finite-sample-corrected residual quantile for split conformal."""
    n = len(abs_residuals)
    level = min(1.0, math.ceil((n + 1) * coverage) / n)
    return float(np.quantile(abs_residuals, level, method="higher"))


@dataclass
class ConformalIntervals:
    """Symmetric split-conformal intervals calibrated on validation residuals.

    Parameters
    ----------
    coverage:
        Target coverage level, default 0.9 (90% intervals).
    group_col:
        Optional grouping column (e.g. ``"clinic_id"`` or ``"region"``) for
        per-group calibration.
    min_calibration_size:
        Minimum residuals a group needs for its own quantile; smaller groups
        fall back to the global quantile.

    Examples
    --------
    >>> import pandas as pd
    >>> calibration = pd.DataFrame({
    ...     "clinic_id": ["A"] * 50,
    ...     "visits": range(50),
    ...     "forecast": [v + 2.0 for v in range(50)],
    ... })
    >>> ci = ConformalIntervals(coverage=0.9).fit(calibration)
    >>> out = ci.apply(pd.DataFrame({"clinic_id": ["A"], "forecast": [100.0]}))
    >>> bool(out.loc[0, "y_lower"] <= 100.0 <= out.loc[0, "y_upper"])
    True
    """

    coverage: float = 0.9
    group_col: str | None = None
    min_calibration_size: int = 30
    global_half_width_: float | None = field(default=None, init=False, repr=False)
    group_half_widths_: dict[str, float] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        if not 0.0 < self.coverage < 1.0:
            raise ValueError("coverage must be strictly between 0 and 1.")
        if self.min_calibration_size < 1:
            raise ValueError("min_calibration_size must be positive.")

    def fit(
        self,
        calibration: pd.DataFrame,
        actual_col: str = "visits",
        forecast_col: str = "forecast",
    ) -> ConformalIntervals:
        """Calibrate half-widths from scored validation forecasts.

        Parameters
        ----------
        calibration:
            Frame with actuals and point forecasts from past validation
            folds. Rows with missing forecasts are ignored.
        """
        required = {actual_col, forecast_col}
        if self.group_col is not None:
            required.add(self.group_col)
        missing = required.difference(calibration.columns)
        if missing:
            raise ValueError(f"Calibration data missing columns: {sorted(missing)}")

        valid = calibration.dropna(subset=[actual_col, forecast_col])
        if len(valid) < self.min_calibration_size:
            raise ValueError(
                f"Need at least {self.min_calibration_size} calibration rows, "
                f"got {len(valid)}."
            )

        residuals = (valid[actual_col] - valid[forecast_col]).abs().to_numpy()
        self.global_half_width_ = _conformal_quantile(residuals, self.coverage)

        self.group_half_widths_ = {}
        if self.group_col is not None:
            for group, frame in valid.groupby(self.group_col, observed=True):
                if len(frame) >= self.min_calibration_size:
                    group_residuals = (
                        (frame[actual_col] - frame[forecast_col]).abs().to_numpy()
                    )
                    self.group_half_widths_[str(group)] = _conformal_quantile(
                        group_residuals, self.coverage
                    )
        return self

    def half_width_for(self, group: str | None = None) -> float:
        """Half-width for a group, falling back to the global quantile."""
        if self.global_half_width_ is None:
            raise RuntimeError("ConformalIntervals must be fitted before use.")
        if group is not None and group in self.group_half_widths_:
            return self.group_half_widths_[group]
        return self.global_half_width_

    def apply(
        self,
        forecast: pd.DataFrame,
        forecast_col: str = "forecast",
        floor: float = 0.0,
    ) -> pd.DataFrame:
        """Attach ``y_pred``, ``y_lower`` and ``y_upper`` columns to forecasts.

        Lower bounds are floored at ``floor`` (demand cannot be negative).
        """
        if self.global_half_width_ is None:
            raise RuntimeError("ConformalIntervals must be fitted before use.")
        if forecast_col not in forecast.columns:
            raise ValueError(f"Missing forecast column: {forecast_col}")

        frame = forecast.copy()
        if self.group_col is not None and self.group_col in frame.columns:
            widths = frame[self.group_col].astype(str).map(self.half_width_for)
        else:
            widths = pd.Series(self.global_half_width_, index=frame.index)

        frame["y_pred"] = frame[forecast_col]
        frame["y_lower"] = (frame[forecast_col] - widths).clip(lower=floor)
        frame["y_upper"] = frame[forecast_col] + widths
        return frame
