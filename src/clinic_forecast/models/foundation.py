"""Optional foundation-model forecasting benchmarks.

Zero-shot time-series foundation models: no per-network training, the model
is pre-trained and forecasts each clinic's series directly. Three are wired
here behind guarded imports:

- **TimesFM** (Google) — :func:`timesfm_panel_forecast`.
- **Chronos** (Amazon) — :func:`chronos_panel_forecast`.
- **Lag-Llama** — :func:`lag_llama_panel_forecast`.

All three return the project's common forecast schema
``[id_col, date_col, forecast, model]`` and share
:func:`foundation_panel_forecast`, which applies a per-series ``predict``
callable across the panel. Running them for real downloads large pretrained
weights (typically from Hugging Face); for a healthcare network, sending
demand data to a hosted model would also need a data-governance review.

Each wrapper accepts an injectable ``predict_fn`` so the panel-shaping logic
is unit-tested without downloading weights or importing heavy libraries.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

_INSTALL_HINT = "Run `poetry install --with optional` and download the model weights."

#: A per-series zero-shot predictor: (history values, horizon) -> point forecast.
PredictFn = Callable[[np.ndarray, int], np.ndarray]


def foundation_panel_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    predict_fn: PredictFn,
    model_name: str,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
) -> pd.DataFrame:
    """Apply a per-series zero-shot predictor across the clinic panel.

    Parameters
    ----------
    predict_fn:
        Callable mapping ``(history_values, horizon)`` to a length-horizon
        array of point forecasts for one series.
    future:
        Provides the forecast dates per clinic; target values are ignored.
    """
    forecasts: list[pd.DataFrame] = []
    for clinic_id, future_group in future.groupby(id_col, observed=True):
        history = (
            train.loc[train[id_col] == clinic_id]
            .sort_values(date_col)[target_col]
            .to_numpy(dtype=float)
        )
        if history.size == 0:
            raise ValueError(f"No training history for {clinic_id}.")
        future_group = future_group.sort_values(date_col)
        horizon = len(future_group)
        prediction = np.asarray(predict_fn(history, horizon), dtype=float)
        if prediction.shape[0] != horizon:
            raise ValueError(
                f"Predictor returned {prediction.shape[0]} steps, expected {horizon}."
            )
        local = future_group[[id_col, date_col]].copy()
        local["forecast"] = np.clip(prediction, 0, None)
        local["model"] = model_name
        forecasts.append(local)
    return pd.concat(forecasts, ignore_index=True)


def timesfm_panel_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    checkpoint: str = "google/timesfm-1.0-200m",
    predict_fn: PredictFn | None = None,
    **panel_kwargs: str,
) -> pd.DataFrame:
    """Zero-shot forecast with Google TimesFM.

    Pass ``predict_fn`` to inject a predictor (tests); otherwise a TimesFM
    model is loaded from ``checkpoint``.
    """
    if predict_fn is None:
        try:
            import timesfm
        except ImportError as exc:
            raise ImportError(f"TimesFM is not installed. {_INSTALL_HINT}") from exc

        model = timesfm.TimesFm(checkpoint=checkpoint)  # type: ignore[attr-defined]

        def predict_fn(history: np.ndarray, horizon: int) -> np.ndarray:
            point, _ = model.forecast([history], freq=[0])
            return np.asarray(point[0])[:horizon]

    return foundation_panel_forecast(train, future, predict_fn, "timesfm", **panel_kwargs)


def chronos_panel_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    checkpoint: str = "amazon/chronos-t5-small",
    predict_fn: PredictFn | None = None,
    **panel_kwargs: str,
) -> pd.DataFrame:
    """Zero-shot forecast with Amazon Chronos.

    Pass ``predict_fn`` to inject a predictor (tests); otherwise a Chronos
    pipeline is loaded from ``checkpoint``.
    """
    if predict_fn is None:
        try:
            import torch
            from chronos import ChronosPipeline
        except ImportError as exc:
            raise ImportError(f"Chronos is not installed. {_INSTALL_HINT}") from exc

        pipeline = ChronosPipeline.from_pretrained(checkpoint)

        def predict_fn(history: np.ndarray, horizon: int) -> np.ndarray:
            context = torch.tensor(history, dtype=torch.float32)
            forecast = pipeline.predict(context, prediction_length=horizon)
            median = np.median(forecast[0].numpy(), axis=0)
            return np.asarray(median, dtype=float)

    return foundation_panel_forecast(train, future, predict_fn, "chronos", **panel_kwargs)


def lag_llama_panel_forecast(
    train: pd.DataFrame,
    future: pd.DataFrame,
    checkpoint_path: str = "lag-llama.ckpt",
    predict_fn: PredictFn | None = None,
    **panel_kwargs: str,
) -> pd.DataFrame:
    """Zero-shot forecast with Lag-Llama.

    Lag-Llama is a research model installed from source with a downloaded
    checkpoint. Pass ``predict_fn`` to inject a predictor (tests); otherwise
    the wrapper raises a clear error pointing at the checkpoint requirement.
    """
    if predict_fn is None:
        try:
            from lag_llama.gluon.estimator import LagLlamaEstimator  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "Lag-Llama is not installed. Install it from source "
                "(https://github.com/time-series-foundation-models/lag-llama) "
                f"and provide a checkpoint at {checkpoint_path!r}."
            ) from exc
        raise NotImplementedError(
            "Lag-Llama requires a downloaded checkpoint and a GluonTS prediction "
            "loop; provide predict_fn to integrate your loaded estimator."
        )

    return foundation_panel_forecast(train, future, predict_fn, "lag_llama", **panel_kwargs)
