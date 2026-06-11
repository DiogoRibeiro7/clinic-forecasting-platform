from __future__ import annotations

import pytest

from clinic_forecast.metrics import compute_metrics


def test_compute_metrics_returns_expected_zero_error() -> None:
    metrics = compute_metrics([10, 20, 30], [10, 20, 30])

    assert metrics.mae == 0
    assert metrics.rmse == 0
    assert metrics.wape == 0
    assert metrics.bias == 0


def test_compute_metrics_rejects_different_lengths() -> None:
    with pytest.raises(ValueError):
        compute_metrics([1, 2], [1])
