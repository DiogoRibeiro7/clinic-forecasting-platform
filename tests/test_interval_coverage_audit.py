from __future__ import annotations

import pandas as pd
import pytest

import clinic_forecast.interval_coverage_audit as audit
from clinic_forecast.data import SyntheticDataConfig, generate_network_data
from clinic_forecast.interval_coverage_audit import (
    IntervalCoverageAuditSpec,
    run_interval_coverage_audit,
)


def _usage() -> pd.DataFrame:
    network = generate_network_data(
        SyntheticDataConfig(
            start_date="2022-01-01",
            end_date="2025-12-31",
            n_clinics=12,
            random_seed=42,
        )
    )
    return network.usage


def test_audit_uses_only_prior_folds_for_interval_calibration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_training_ends: list[pd.Timestamp] = []

    def fake_recursive_forecast(
        train: pd.DataFrame,
        test: pd.DataFrame,
        estimator: str = "hgb",
        target_col: str = "visits",
    ) -> pd.DataFrame:
        del estimator
        seen_training_ends.append(pd.to_datetime(train["date"]).max())
        return test[["clinic_id", "date"]].assign(
            forecast=test[target_col].astype(float).to_numpy()
        )

    monkeypatch.setattr(audit, "recursive_global_ml_forecast", fake_recursive_forecast)
    result = run_interval_coverage_audit(_usage())

    assert len(seen_training_ends) == 8
    assert seen_training_ends == sorted(seen_training_ends)
    assert result.summary["initial_calibration_folds"] == 4
    assert result.summary["evaluation_folds"] == 4
    assert result.audit_rows["fold"].unique().tolist() == [5, 6, 7, 8]

    rows_by_fold = result.audit_rows.groupby("fold", observed=True)["calibration_folds"].first()
    assert rows_by_fold.to_dict() == {5: 4, 6: 5, 7: 6, 8: 7}


def test_audit_reports_complete_horizon_and_clinic_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_recursive_forecast(
        train: pd.DataFrame,
        test: pd.DataFrame,
        estimator: str = "hgb",
        target_col: str = "visits",
    ) -> pd.DataFrame:
        del train, estimator
        return test[["clinic_id", "date"]].assign(
            forecast=test[target_col].astype(float).to_numpy()
        )

    monkeypatch.setattr(audit, "recursive_global_ml_forecast", fake_recursive_forecast)
    result = run_interval_coverage_audit(_usage())

    assert result.horizon_scores["horizon_days"].tolist() == list(range(1, 29))
    assert result.clinic_scores["clinic_id"].nunique() == 12
    assert result.fold_scores["fold"].tolist() == [5, 6, 7, 8]
    assert result.summary["coverage"] == pytest.approx(1.0)
    assert result.summary["horizons"] == 28
    assert result.summary["clinics"] == 12


def test_spec_requires_at_least_one_held_out_fold() -> None:
    with pytest.raises(ValueError, match="leave at least one evaluation fold"):
        IntervalCoverageAuditSpec(calibration_folds=8)
