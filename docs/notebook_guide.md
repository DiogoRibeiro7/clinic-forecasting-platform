# Notebook Guide

## Reading order

Reviewers should start with **notebook 10** (the executive summary) and dip
into 01-06 for implementation depth. The notebooks build on each other in
numeric order.

## 00 — Business problem and PoC design

Frames the decisions the system supports, the data entities, the evaluation
design (rolling-origin backtesting, WAPE and bias) and explicit scope limits.

## 01 — Synthetic healthcare data generation

Documents the simulation design — overdispersed counts, demand episodes,
trend changepoints, holidays, opening days, marketing channels with adstock —
and writes the four contract CSVs to `data/processed/`.

## 02 — EDA and forecastability assessment

Quantifies the demand structure (weekday/monthly/holiday effects, regional
divergence, capacity censoring, no-show behaviour) and derives the modelling
strategy, including the seasonal-naive error floor every model must beat.

## 03 — Statistical models

Baselines and per-clinic SARIMAX with exogenous marketing/holiday inputs,
evaluated across rolling folds; discusses where classical models stop scaling.

## 04 — Global ML forecaster

One gradient-boosted model for the whole panel: leakage-safe feature design,
fold-by-fold comparison against the baseline, per-clinic error distribution,
permutation importance, conformal prediction intervals and deployment-mode
recursive forecasting.

## 05 — LSTM and TimeGPT optional models

What the optional deep-learning and foundation-model benchmarks would add,
what they cost, and how the cells degrade gracefully when the optional
dependencies are absent.

## 06 — Staffing optimisation

Converts forecasts into rosters and money: staffing gaps against baseline
rosters, conservative planning from conformal upper bounds, and a costed
scenario comparison (static roster vs mean plan vs upper plan).

## 10 — Executive summary

The end-to-end story for technical and non-technical reviewers, with minimal
code and every number computed live.

## 11 — Comprehensive model benchmark

Runs every installed model family — baselines, SARIMAX, Prophet, the global
gradient-boosted models (HGB/XGBoost/LightGBM), and (where available) the
Nixtla ecosystem, deep-learning and foundation models — through one shared
benchmark harness on identical folds, producing a single leaderboard. Requires
the optional dependencies for the non-core models; gracefully skips any that
are unavailable.

## Running the notebooks

Generate the data first — notebooks 02-06 and 10 read the processed CSVs:

```bash
poetry run python scripts/generate_data.py
```

Execute the lightweight smoke set (00, 01, 06) headlessly:

```bash
make notebook-check
# or directly, with any selection of notebooks:
poetry run python scripts/run_notebook.py notebooks/02_eda_and_forecasting_validation.ipynb
```

The runner executes notebooks in place with the project kernel and prints the
first failing cell's error. If a notebook needs data that has not been
generated yet, it fails fast with the command to run. CI runs the same smoke
set on every push.
