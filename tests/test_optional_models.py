from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from clinic_forecast.models.lstm import make_sequence_dataset
from clinic_forecast.models.timegpt import timegpt_forecast


def make_panel(n_days: int = 90, clinics: tuple[str, ...] = ("A", "B")) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    frames = [
        pd.DataFrame({"clinic_id": cid, "date": dates,
                      "visits": np.linspace(50, 80, n_days) * (i + 1)})
        for i, cid in enumerate(clinics)
    ]
    return pd.concat(frames, ignore_index=True)


class MockNixtlaClient:
    """Stands in for nixtla.NixtlaClient without any network access."""

    def forecast(self, df, h, time_col, target_col, id_col):  # noqa: ANN001
        rows = []
        for unique_id, frame in df.groupby(id_col):
            last_date = pd.to_datetime(frame[time_col]).max()
            dates = pd.date_range(last_date + pd.Timedelta(days=1), periods=h)
            rows.append(
                pd.DataFrame(
                    {id_col: unique_id, time_col: dates, "TimeGPT": float(frame[target_col].mean())}
                )
            )
        return pd.concat(rows, ignore_index=True)


# ---------------- TimeGPT wrapper ----------------


def test_timegpt_forecast_with_mock_client_matches_common_schema() -> None:
    panel = make_panel()
    output = timegpt_forecast(panel, horizon=7, client=MockNixtlaClient())

    assert list(output.columns) == ["clinic_id", "date", "forecast", "model"]
    assert (output["model"] == "timegpt").all()
    assert len(output) == 7 * 2
    assert output["date"].min() == panel["date"].max() + pd.Timedelta(days=1)
    assert (output["forecast"] >= 0).all()


def test_timegpt_forecast_validates_inputs() -> None:
    with pytest.raises(ValueError, match="missing columns"):
        timegpt_forecast(pd.DataFrame({"clinic_id": []}), horizon=7, client=MockNixtlaClient())
    with pytest.raises(ValueError, match="horizon"):
        timegpt_forecast(make_panel(), horizon=0, client=MockNixtlaClient())


def test_timegpt_requires_key_when_sdk_present_or_import_error() -> None:
    # Without a client we need either the SDK + key, or we get a clear error.
    with pytest.raises((ImportError, ValueError), match="Nixtla|API key"):
        timegpt_forecast(make_panel(), horizon=7, api_key=None)


# ---------------- LSTM dataset (no torch required) ----------------


def test_sequence_dataset_shapes_and_isolation() -> None:
    dataset = make_sequence_dataset(make_panel(n_days=90), window=14, horizon=7)

    expected_per_clinic = 90 - 14 - 7 + 1
    assert dataset.inputs.shape == (2 * expected_per_clinic, 14)
    assert dataset.targets.shape == (2 * expected_per_clinic, 7)
    assert dataset.clinic_indices.shape == (2 * expected_per_clinic,)
    assert set(dataset.clinic_to_index) == {"A", "B"}
    # Standardisation is per clinic: each clinic's pooled values ~ mean 0.
    for clinic, index in dataset.clinic_to_index.items():
        values = dataset.inputs[dataset.clinic_indices == index]
        assert abs(values.mean()) < 0.5, clinic


def test_sequence_dataset_skips_short_series() -> None:
    long_panel = make_panel(n_days=90, clinics=("A",))
    short_panel = make_panel(n_days=10, clinics=("B",))
    dataset = make_sequence_dataset(
        pd.concat([long_panel, short_panel], ignore_index=True), window=14, horizon=7
    )
    assert set(dataset.clinic_to_index) == {"A"}


def test_sequence_dataset_rejects_impossible_setup() -> None:
    with pytest.raises(ValueError, match="enough history"):
        make_sequence_dataset(make_panel(n_days=10), window=14, horizon=7)
    with pytest.raises(ValueError, match="positive"):
        make_sequence_dataset(make_panel(), window=0, horizon=7)


# ---------------- LSTM model (torch optional) ----------------


def test_lstm_fit_and_forecast_shapes() -> None:
    pytest.importorskip("torch")
    from clinic_forecast.models.lstm import LSTMForecaster

    panel = make_panel(n_days=120)
    model = LSTMForecaster(window=14, horizon=7, epochs=2, patience=2).fit(panel)
    forecast = model.forecast(panel)

    assert len(forecast) == 7 * 2
    assert (forecast["forecast"] >= 0).all()
    assert (forecast["model"] == "lstm").all()
