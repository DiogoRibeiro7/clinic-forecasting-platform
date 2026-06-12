"""Optional LSTM baseline for panel time-series forecasting.

PyTorch is an optional dependency; everything torch-specific is guarded so
the core project works without it. The dataset preparation is plain NumPy
and is tested without torch.

Framing: the LSTM is a *benchmark*, not the expected winner. On a panel of a
dozen clinics with strong calendar structure, gradient-boosted trees on
engineered features are hard to beat; the LSTM's value is showing what a
sequence model adds (or does not) for the same data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SequenceDataset:
    """Sliding-window dataset for sequence-to-horizon forecasting.

    Attributes
    ----------
    inputs:
        Array of shape ``(n_samples, window)`` — standardised demand history.
    targets:
        Array of shape ``(n_samples, horizon)`` — standardised future demand.
    clinic_indices:
        Integer clinic index per sample, shape ``(n_samples,)`` (for the
        embedding layer).
    clinic_to_index:
        Mapping clinic_id -> embedding index.
    scaler:
        Mapping clinic_id -> (mean, std) used for standardisation.
    """

    inputs: np.ndarray
    targets: np.ndarray
    clinic_indices: np.ndarray
    clinic_to_index: dict[str, int]
    scaler: dict[str, tuple[float, float]]


def make_sequence_dataset(
    usage: pd.DataFrame,
    window: int = 28,
    horizon: int = 28,
    id_col: str = "clinic_id",
    date_col: str = "date",
    target_col: str = "visits",
) -> SequenceDataset:
    """Build per-clinic sliding windows with per-clinic standardisation.

    Windows never cross clinic boundaries; each clinic's series is
    standardised with its own mean and standard deviation so the model sees
    comparable scales across small and large clinics.
    """
    if window <= 0 or horizon <= 0:
        raise ValueError("window and horizon must be positive.")

    inputs: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    clinic_indices: list[int] = []
    clinic_to_index: dict[str, int] = {}
    scaler: dict[str, tuple[float, float]] = {}

    frame = usage.sort_values([id_col, date_col])
    for clinic_id, clinic_frame in frame.groupby(id_col, observed=True):
        series = clinic_frame[target_col].to_numpy(dtype=np.float32)
        if len(series) < window + horizon:
            continue
        mean = float(series.mean())
        std = float(series.std()) or 1.0
        scaled = (series - mean) / std

        index = clinic_to_index.setdefault(str(clinic_id), len(clinic_to_index))
        scaler[str(clinic_id)] = (mean, std)
        for start in range(len(scaled) - window - horizon + 1):
            inputs.append(scaled[start : start + window])
            targets.append(scaled[start + window : start + window + horizon])
            clinic_indices.append(index)

    if not inputs:
        raise ValueError("No clinic has enough history for the requested window and horizon.")
    return SequenceDataset(
        inputs=np.stack(inputs),
        targets=np.stack(targets),
        clinic_indices=np.asarray(clinic_indices, dtype=np.int64),
        clinic_to_index=clinic_to_index,
        scaler=scaler,
    )


@dataclass
class LSTMForecaster:
    """Small sequence-to-horizon LSTM with clinic embeddings (optional torch).

    Parameters mirror common practice for a lightweight benchmark: one LSTM
    layer, a clinic embedding concatenated to the encoded sequence state and
    a linear head emitting the whole horizon at once.
    """

    window: int = 28
    horizon: int = 28
    hidden_size: int = 32
    embedding_dim: int = 4
    epochs: int = 40
    learning_rate: float = 1e-3
    batch_size: int = 256
    val_fraction: float = 0.2
    patience: int = 5
    seed: int = 42
    _net: Any = field(default=None, init=False, repr=False)
    _dataset: SequenceDataset | None = field(default=None, init=False, repr=False)

    def _require_torch(self) -> Any:
        try:
            import torch
        except ImportError as exc:
            raise ImportError(
                "PyTorch is not installed. Run `poetry install --with optional` "
                "to enable the LSTM benchmark."
            ) from exc
        return torch

    def _build_net(self, n_clinics: int) -> Any:
        torch = self._require_torch()

        class _Net(torch.nn.Module):  # type: ignore[misc, name-defined]
            def __init__(self, hidden: int, emb_dim: int, horizon: int) -> None:
                super().__init__()
                self.embedding = torch.nn.Embedding(n_clinics, emb_dim)
                self.lstm = torch.nn.LSTM(input_size=1, hidden_size=hidden, batch_first=True)
                self.head = torch.nn.Linear(hidden + emb_dim, horizon)

            def forward(self, sequence: Any, clinic_index: Any) -> Any:
                _, (hidden_state, _) = self.lstm(sequence.unsqueeze(-1))
                features = torch.cat(
                    [hidden_state[-1], self.embedding(clinic_index)], dim=1
                )
                return self.head(features)

        return _Net(self.hidden_size, self.embedding_dim, self.horizon)

    def fit(self, usage: pd.DataFrame, verbose: bool = False) -> LSTMForecaster:
        """Train with a chronological validation split and early stopping."""
        torch = self._require_torch()
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)

        dataset = make_sequence_dataset(usage, window=self.window, horizon=self.horizon)
        self._dataset = dataset
        n_samples = len(dataset.inputs)
        split = int(n_samples * (1 - self.val_fraction))

        def tensors(low: int, high: int) -> tuple[Any, Any, Any]:
            return (
                torch.from_numpy(dataset.inputs[low:high]),
                torch.from_numpy(dataset.targets[low:high]),
                torch.from_numpy(dataset.clinic_indices[low:high]),
            )

        x_train, y_train, c_train = tensors(0, split)
        x_val, y_val, c_val = tensors(split, n_samples)

        net = self._build_net(len(dataset.clinic_to_index))
        optimiser = torch.optim.Adam(net.parameters(), lr=self.learning_rate)
        loss_fn = torch.nn.MSELoss()

        best_val = float("inf")
        best_state = None
        stale = 0
        for epoch in range(self.epochs):
            net.train()
            permutation = torch.randperm(len(x_train))
            for start in range(0, len(x_train), self.batch_size):
                batch = permutation[start : start + self.batch_size]
                optimiser.zero_grad()
                prediction = net(x_train[batch], c_train[batch])
                loss = loss_fn(prediction, y_train[batch])
                loss.backward()
                optimiser.step()

            net.eval()
            with torch.no_grad():
                val_loss = float(loss_fn(net(x_val, c_val), y_val))
            if verbose:
                print(f"epoch {epoch + 1:3d}  val_loss {val_loss:.4f}")
            if val_loss < best_val - 1e-5:
                best_val = val_loss
                best_state = {k: v.clone() for k, v in net.state_dict().items()}
                stale = 0
            else:
                stale += 1
                if stale >= self.patience:
                    break

        if best_state is not None:
            net.load_state_dict(best_state)
        self._net = net
        return self

    def forecast(self, history: pd.DataFrame) -> pd.DataFrame:
        """Forecast the next ``horizon`` days per clinic from the last window.

        Returns the common ``[clinic_id, date, forecast, model]`` schema with
        per-clinic de-standardised, non-negative values.
        """
        torch = self._require_torch()
        if self._net is None or self._dataset is None:
            raise RuntimeError("The model must be fitted before forecasting.")

        rows = []
        frame = history.sort_values(["clinic_id", "date"])
        origin = pd.to_datetime(frame["date"]).max()
        future_dates = pd.date_range(origin + pd.Timedelta(days=1), periods=self.horizon)

        self._net.eval()
        for clinic_id, clinic_frame in frame.groupby("clinic_id", observed=True):
            key = str(clinic_id)
            if key not in self._dataset.clinic_to_index:
                continue
            mean, std = self._dataset.scaler[key]
            series = clinic_frame["visits"].to_numpy(dtype=np.float32)[-self.window :]
            if len(series) < self.window:
                continue
            scaled = (series - mean) / std
            with torch.no_grad():
                prediction = self._net(
                    torch.from_numpy(scaled).unsqueeze(0),
                    torch.tensor([self._dataset.clinic_to_index[key]]),
                ).numpy()[0]
            values = np.clip(prediction * std + mean, 0, None)
            rows.append(
                pd.DataFrame(
                    {"clinic_id": key, "date": future_dates, "forecast": values}
                )
            )
        output = pd.concat(rows, ignore_index=True)
        output["model"] = "lstm"
        return output
