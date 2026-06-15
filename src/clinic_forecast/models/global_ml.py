"""Global machine-learning forecaster for multi-clinic panel time series.

One model is trained on the pooled panel using lag, rolling, calendar,
metadata and marketing features. Two prediction modes are supported:

- :meth:`GlobalMLForecaster.predict_known_future` for backtesting, where the
  test window's actuals exist and lag features can be built from them.
- :meth:`GlobalMLForecaster.forecast` for true deployment-style prediction,
  where future targets are unknown and predictions are fed back recursively
  as lag inputs, one day at a time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from clinic_forecast.features import OUTCOME_COLUMNS, make_supervised_frame

Estimator = Literal["hgb", "xgboost", "lightgbm"]


def _build_estimator(estimator: Estimator, random_state: int) -> Any:
    """Create the underlying regressor; XGBoost/LightGBM are optional deps."""
    if estimator == "hgb":
        return HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.06, random_state=random_state
        )
    if estimator == "xgboost":
        try:
            from xgboost import XGBRegressor
        except ImportError as exc:
            raise ImportError(
                "XGBoost is not installed. Run `poetry install --with optional` "
                "or use estimator='hgb'."
            ) from exc
        return XGBRegressor(
            n_estimators=400,
            learning_rate=0.06,
            max_depth=6,
            random_state=random_state,
            n_jobs=-1,
        )
    if estimator == "lightgbm":
        try:
            from lightgbm import LGBMRegressor
        except ImportError as exc:
            raise ImportError(
                "LightGBM is not installed. Run `poetry install --with optional` "
                "or use estimator='hgb'."
            ) from exc
        return LGBMRegressor(
            n_estimators=400,
            learning_rate=0.06,
            max_depth=6,
            random_state=random_state,
            n_jobs=-1,
            verbose=-1,
        )
    raise ValueError(
        f"Unknown estimator: {estimator!r}; expected 'hgb', 'xgboost' or 'lightgbm'."
    )


@dataclass
class GlobalMLForecaster:
    """Global recursive forecaster based on lag features.

    Parameters
    ----------
    estimator:
        ``"hgb"`` (scikit-learn HistGradientBoostingRegressor, default),
        ``"xgboost"`` or ``"lightgbm"`` (both optional dependencies).
    target_col, date_col, id_col:
        Panel column names.
    random_state:
        Seed for the underlying estimator.
    """

    target_col: str = "visits"
    date_col: str = "date"
    id_col: str = "clinic_id"
    estimator: Estimator = "hgb"
    random_state: int = 42
    feature_columns_: list[str] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.model = _build_estimator(self.estimator, self.random_state)

    @property
    def model_name(self) -> str:
        """Label written into the ``model`` column of forecast outputs."""
        return f"global_ml_{self.estimator}"

    def _feature_columns(self, supervised: pd.DataFrame) -> list[str]:
        drop = {
            self.target_col,
            self.date_col,
            self.id_col,
            "region",
            "clinic_size",
            "specialty",
            *OUTCOME_COLUMNS,
        }
        return [
            col
            for col in supervised.columns
            if col not in drop and supervised[col].dtype.kind in "ifb"
        ]

    def fit(self, data: pd.DataFrame) -> GlobalMLForecaster:
        """Fit the global forecasting model on a panel of historical data."""
        supervised = make_supervised_frame(
            data, group_col=self.id_col, target_col=self.target_col
        )
        self.feature_columns_ = self._feature_columns(supervised)
        self.model.fit(supervised[self.feature_columns_], supervised[self.target_col])
        return self

    def _design_matrix(self, supervised: pd.DataFrame) -> pd.DataFrame:
        """Align a supervised frame with the training feature columns."""
        if self.feature_columns_ is None:
            raise RuntimeError("The model must be fitted before prediction.")
        missing = [col for col in self.feature_columns_ if col not in supervised.columns]
        aligned = supervised.copy()
        for col in missing:
            aligned[col] = 0  # unseen one-hot category
        return aligned[self.feature_columns_]

    def predict_known_future(self, data: pd.DataFrame) -> pd.DataFrame:
        """Predict rows whose lag features can be computed from known history.

        Intended for backtesting: ``data`` holds history plus the test window
        with actual target values, so lag features for test rows come from
        values that were genuinely observable at forecast time.
        """
        supervised = make_supervised_frame(
            data, group_col=self.id_col, target_col=self.target_col
        )
        yhat = self.model.predict(self._design_matrix(supervised))
        output = supervised[[self.id_col, self.date_col, self.target_col]].copy()
        output["forecast"] = np.clip(yhat, a_min=0, a_max=None)
        output["model"] = self.model_name
        return output

    def forecast(self, history: pd.DataFrame, future: pd.DataFrame) -> pd.DataFrame:
        """Recursive multi-step forecast for a future window without targets.

        Parameters
        ----------
        history:
            Observed panel up to the forecast origin (must include the
            target column).
        future:
            Future rows with known inputs only (calendar position is derived
            from ``date_col``; marketing/metadata columns are used if
            present). Any target column present is ignored.

        Returns
        -------
        pandas.DataFrame
            One row per future (clinic, date) with ``forecast`` and ``model``
            columns. Predictions for day t are fed back as lag inputs for
            day t+1 and onward.
        """
        if self.feature_columns_ is None:
            raise RuntimeError("The model must be fitted before prediction.")

        work = history.copy()
        work[self.date_col] = pd.to_datetime(work[self.date_col])
        future_frame = future.copy()
        future_frame[self.date_col] = pd.to_datetime(future_frame[self.date_col])
        future_frame = future_frame.drop(
            columns=[c for c in (self.target_col, *OUTCOME_COLUMNS) if c in future_frame],
        )

        origin = work[self.date_col].max()
        if (future_frame[self.date_col] <= origin).any():
            raise ValueError("All future rows must be after the end of history.")

        results: list[pd.DataFrame] = []
        for date in sorted(future_frame[self.date_col].unique()):
            day_rows = future_frame[future_frame[self.date_col] == date].copy()
            day_rows[self.target_col] = np.nan
            combined = pd.concat([work, day_rows], ignore_index=True)
            supervised = make_supervised_frame(
                combined, group_col=self.id_col, target_col=self.target_col, dropna=False
            )
            day_supervised = supervised[supervised[self.date_col] == date]
            yhat = np.clip(
                self.model.predict(self._design_matrix(day_supervised)), 0, None
            )

            day_result = day_rows[[self.id_col, self.date_col]].copy()
            day_result["forecast"] = yhat
            results.append(day_result)

            day_rows[self.target_col] = yhat
            work = pd.concat([work, day_rows], ignore_index=True)

        forecast_frame = pd.concat(results, ignore_index=True)
        forecast_frame["model"] = self.model_name
        return forecast_frame

    def permutation_importance_frame(
        self, data: pd.DataFrame, n_repeats: int = 5, top_n: int = 20
    ) -> pd.DataFrame:
        """Permutation feature importance on a held-out panel slice."""
        from sklearn.inspection import permutation_importance

        supervised = make_supervised_frame(
            data, group_col=self.id_col, target_col=self.target_col
        )
        result = permutation_importance(
            self.model,
            self._design_matrix(supervised),
            supervised[self.target_col],
            n_repeats=n_repeats,
            random_state=self.random_state,
        )
        importance = pd.DataFrame(
            {
                "feature": self.feature_columns_,
                "importance_mean": result.importances_mean,
                "importance_std": result.importances_std,
            }
        ).sort_values("importance_mean", ascending=False)
        return importance.head(top_n).reset_index(drop=True)
