from __future__ import annotations

import pandas as pd
import pytest

from clinic_forecast.validation import (
    RollingOriginSplitter,
    rolling_origin_windows,
    summarize_folds,
)


def make_panel(n_days: int = 200, clinics: tuple[str, ...] = ("A", "B")) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    frames = [
        pd.DataFrame({"date": dates, "clinic_id": clinic, "visits": range(n_days)})
        for clinic in clinics
    ]
    return pd.concat(frames, ignore_index=True)


def test_expected_number_of_folds() -> None:
    data = make_panel(n_days=365 + 28 * 3)
    splitter = RollingOriginSplitter(initial_train_days=365, horizon_days=28)
    assert len(splitter.folds(data)) == 3


def test_max_folds_caps_fold_count() -> None:
    data = make_panel(n_days=365 + 28 * 5)
    splitter = RollingOriginSplitter(initial_train_days=365, horizon_days=28, max_folds=2)
    assert len(splitter.folds(data)) == 2


def test_step_days_controls_origin_advance() -> None:
    data = make_panel(n_days=120)
    splitter = RollingOriginSplitter(initial_train_days=60, horizon_days=28, step_days=7)
    folds = splitter.folds(data)
    deltas = {
        (later.test_start - earlier.test_start).days
        for earlier, later in zip(folds[:-1], folds[1:], strict=True)
    }
    assert deltas == {7}


def test_fold_boundaries_are_contiguous_and_inclusive() -> None:
    data = make_panel(n_days=130)
    splitter = RollingOriginSplitter(initial_train_days=90, horizon_days=14)
    fold = splitter.folds(data)[0]

    assert fold.train_start == pd.Timestamp("2024-01-01")
    assert (fold.train_end - fold.train_start).days + 1 == 90
    assert (fold.test_start - fold.train_end).days == 1
    assert (fold.test_end - fold.test_start).days + 1 == 14


def test_no_overlap_between_train_and_test() -> None:
    data = make_panel(n_days=160)
    splitter = RollingOriginSplitter(initial_train_days=90, horizon_days=21)
    for train, test, _ in splitter.split(data):
        assert train["date"].max() < test["date"].min()
        assert set(train["date"]).isdisjoint(set(test["date"]))


def test_expanding_window_grows_and_sliding_window_stays_fixed() -> None:
    data = make_panel(n_days=200)
    expanding = RollingOriginSplitter(initial_train_days=90, horizon_days=28)
    sliding = RollingOriginSplitter(
        initial_train_days=90, horizon_days=28, window="sliding"
    )

    expanding_lengths = [
        (fold.train_end - fold.train_start).days + 1 for fold in expanding.folds(data)
    ]
    sliding_lengths = [
        (fold.train_end - fold.train_start).days + 1 for fold in sliding.folds(data)
    ]
    assert expanding_lengths == sorted(expanding_lengths)
    assert expanding_lengths[0] < expanding_lengths[-1]
    assert set(sliding_lengths) == {90}


def test_split_includes_all_clinics_in_each_fold() -> None:
    data = make_panel(n_days=130, clinics=("A", "B", "C"))
    splitter = RollingOriginSplitter(initial_train_days=90, horizon_days=14)
    for train, test, _ in splitter.split(data):
        assert set(train["clinic_id"]) == {"A", "B", "C"}
        assert set(test["clinic_id"]) == {"A", "B", "C"}


def test_split_by_clinic_handles_unequal_histories() -> None:
    long_history = make_panel(n_days=130, clinics=("A",))
    short_history = make_panel(n_days=104, clinics=("B",))
    data = pd.concat([long_history, short_history], ignore_index=True)
    splitter = RollingOriginSplitter(initial_train_days=90, horizon_days=14)

    fold_counts: dict[str, int] = {}
    for clinic_id, train, test, _ in splitter.split_by_clinic(data):
        assert set(train["clinic_id"]) == {clinic_id}
        assert set(test["clinic_id"]) == {clinic_id}
        fold_counts[clinic_id] = fold_counts.get(clinic_id, 0) + 1

    assert fold_counts == {"A": 2, "B": 1}


def test_summarize_folds_reports_counts() -> None:
    data = make_panel(n_days=130, clinics=("A", "B"))
    splitter = RollingOriginSplitter(initial_train_days=90, horizon_days=14)
    summary = summarize_folds(data, splitter)

    assert list(summary["fold_id"]) == [1, 2]
    assert (summary["test_days"] == 14).all()
    assert (summary["test_rows"] == 14 * 2).all()
    assert summary.loc[0, "train_rows"] == 90 * 2


def test_insufficient_history_raises() -> None:
    data = make_panel(n_days=100)
    splitter = RollingOriginSplitter(initial_train_days=90, horizon_days=28)
    with pytest.raises(ValueError, match="Not enough history"):
        splitter.folds(data)


def test_invalid_parameters_are_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        RollingOriginSplitter(initial_train_days=0)
    with pytest.raises(ValueError, match="step_days"):
        RollingOriginSplitter(step_days=0)
    with pytest.raises(ValueError, match="max_folds"):
        RollingOriginSplitter(max_folds=0)


def test_legacy_rolling_origin_windows_still_works() -> None:
    dates = pd.date_range("2023-01-01", periods=500, freq="D")
    data = pd.DataFrame({"date": dates, "visits": range(len(dates))})
    windows = list(rolling_origin_windows(data, horizon_days=28, n_windows=3, min_train_days=365))

    assert len(windows) == 3
    assert windows[0].test_start < windows[-1].test_start
