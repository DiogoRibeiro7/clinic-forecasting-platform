"""Switch notebooks 03/04 to the shared evaluation utilities (temp script)."""

import json


def set_cell(nb: dict, idx: int, text: str) -> None:
    assert nb["cells"][idx]["cell_type"] == "code", f"cell {idx} is not code"
    nb["cells"][idx]["source"] = text.strip().splitlines(keepends=True)
    nb["cells"][idx]["outputs"] = []
    nb["cells"][idx]["execution_count"] = None


# ---------------- notebook 03 ----------------
path = "notebooks/03_statistical_models_sarimax_prophet.ipynb"
nb = json.load(open(path, encoding="utf-8"))

set_cell(nb, 6, """
from clinic_forecast.evaluation import comparison_table, evaluate_forecasts
from clinic_forecast.models.baseline import moving_average_forecast, seasonal_naive_forecast

scored_baselines = []
for train, test, fold in splitter.split(usage):
    for forecaster in [
        lambda tr, te: seasonal_naive_forecast(train=tr, future=te),
        lambda tr, te: moving_average_forecast(train=tr, future=te, window=28),
    ]:
        scored = test.merge(forecaster(train, test), on=["clinic_id", "date"], how="left")
        scored["fold"] = fold.fold_id
        scored_baselines.append(scored)

scored_baselines = pd.concat(scored_baselines, ignore_index=True)
baseline_results = evaluate_forecasts(scored_baselines, group_cols=["fold"])
comparison_table(baseline_results)
""")

set_cell(nb, 7, """
baseline_results[["model", "fold", "mae", "rmse", "wape", "bias"]].round(2)
""")

set_cell(nb, 10, """
from clinic_forecast.models.sarimax import sarimax_panel_forecast

selected_clinics = ["CLINIC_001", "CLINIC_002", "CLINIC_003"]
*_, (train, test, last_fold) = splitter.split(usage)
train_small = train[train["clinic_id"].isin(selected_clinics)]
test_small = test[test["clinic_id"].isin(selected_clinics)]

sarimax_fcst = sarimax_panel_forecast(
    train=train_small,
    future=test_small,
    exog_cols=["marketing_spend", "campaign_active", "is_holiday"],
)
scored_sarimax = test_small.merge(sarimax_fcst, on=["clinic_id", "date"], how="left")
scored_naive_small = test_small.merge(
    seasonal_naive_forecast(train=train_small, future=test_small),
    on=["clinic_id", "date"],
    how="left",
)

statistical = pd.concat([scored_sarimax, scored_naive_small], ignore_index=True)
comparison_table(evaluate_forecasts(statistical))
""")

json.dump(nb, open(path, "w", encoding="utf-8"), indent=1)
print("patched 03")

# ---------------- notebook 04 ----------------
path = "notebooks/04_global_ml_forecaster_xgboost_style.ipynb"
nb = json.load(open(path, encoding="utf-8"))

set_cell(nb, 6, """
from clinic_forecast.evaluation import evaluate_forecasts

scored_folds = []
for train, test, fold in splitter.split(usage):
    model = GlobalMLForecaster()
    model.fit(train)

    combined = pd.concat([train, test], ignore_index=True).sort_values(["clinic_id", "date"])
    predictions = model.predict_known_future(combined)
    predictions = predictions[predictions["date"] >= fold.test_start]

    scored = test.merge(
        predictions[["clinic_id", "date", "forecast", "model"]],
        on=["clinic_id", "date"], how="inner",
    )
    scored_naive = test.merge(
        seasonal_naive_forecast(train=train, future=test),
        on=["clinic_id", "date"], how="left",
    )
    for frame in (scored, scored_naive):
        frame["fold"] = fold.fold_id
    scored_folds.extend([scored, scored_naive])

scored_folds = pd.concat(scored_folds, ignore_index=True)
fold_metrics = evaluate_forecasts(scored_folds, group_cols=["fold"])
fold_metrics.pivot(index="fold", columns="model", values=["wape", "bias"]).round(2)
""")

set_cell(nb, 7, """
wide = fold_metrics.pivot(index="fold", columns="model", values="wape")
improvement = 1 - wide["global_ml_hgb"] / wide["seasonal_naive"]
print("WAPE improvement over seasonal naive: "
      + ", ".join(f"fold {i}: {v:.0%}" for i, v in improvement.items()))

last_fold_id = scored_folds["fold"].max()
last_scored = scored_folds[
    (scored_folds["fold"] == last_fold_id) & (scored_folds["model"] == "global_ml_hgb")
]
""")

set_cell(nb, 9, """
clinic_metrics = (
    evaluate_forecasts(last_scored, group_cols=["clinic_id"])
    .sort_values("wape")
    .reset_index(drop=True)
)
clinic_metrics[["clinic_id", "mae", "rmse", "wape", "bias", "n_obs"]].round(2)
""")

json.dump(nb, open(path, "w", encoding="utf-8"), indent=1)
print("patched 04")
