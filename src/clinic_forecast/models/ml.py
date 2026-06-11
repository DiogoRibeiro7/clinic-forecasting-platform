"""Global machine-learning forecaster for panel time series."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from clinic_forecast.features import make_supervised_frame


@dataclass
class GlobalMLForecaster:
    """Global recursive forecaster based on lag features.

    The default estimator is scikit-learn's histogram gradient boosting regressor.
    It gives an XGBoost-style tree-based baseline without requiring a heavy
    optional dependency.
    """

    target_col: str = "visits"
    date_col: str = "date"
    id_col: str = "clinic_id"

    def __post_init__(self) -> None:
        self.model = Pipeline(
            steps=[
                ("scaler", StandardScaler(with_mean=False)),
                ("regressor", HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06, random_state=42)),
            ]
        )
        self.feature_columns_: list[str] | None = None

    def fit(self, data: pd.DataFrame) -> "GlobalMLForecaster":
        """Fit the global forecasting model."""
        supervised = make_supervised_frame(data, group_col=self.id_col, target_col=self.target_col)
        drop_cols = {
            self.target_col,
            self.date_col,
            self.id_col,
            "region",
            "clinic_size",
            "specialty",
            "scheduled_appointments",
            "capacity_utilization",
        }
        self.feature_columns_ = [col for col in supervised.columns if col not in drop_cols]
        x_train = supervised[self.feature_columns_]
        y_train = supervised[self.target_col]
        self.model.fit(x_train, y_train)
        return self

    def predict_known_future(self, data: pd.DataFrame) -> pd.DataFrame:
        """Predict rows where lag features can be computed from known history.

        This method is useful for backtesting because the test dataframe contains
        the actual target values, allowing lag features to be created cleanly.
        A production recursive forecaster would feed predictions back as lags.
        """
        if self.feature_columns_ is None:
            raise RuntimeError("The model must be fitted before prediction.")

        supervised = make_supervised_frame(data, group_col=self.id_col, target_col=self.target_col)
        missing = set(self.feature_columns_).difference(supervised.columns)
        for col in missing:
            supervised[col] = 0
        yhat = self.model.predict(supervised[self.feature_columns_])
        output = supervised[[self.id_col, self.date_col, self.target_col]].copy()
        output["forecast"] = np.clip(yhat, a_min=0, a_max=None)
        output["model"] = "global_ml_hgb"
        return output
