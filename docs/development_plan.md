# Development Plan

Audit date: 2026-06-11. This plan is the result of a full repository audit (source
package, tests, scripts, notebooks, configs, Docker and docs) and maps each
improvement to concrete files. It follows the staged structure in `ROADMAP.md`
and the task prompts in `AGENTS.md`.

## Current strengths

- **Clean, typed package layout.** All logic lives under `src/clinic_forecast/`
  with type hints and docstrings on public functions, matching the coding
  standards in `AGENTS.md`.
- **Deterministic, PHI-free synthetic data.** `data.py` generates clinic-level
  aggregates with seeded randomness, realistic weekday/seasonal/marketing
  effects, and no patient-level fields.
- **Leakage-aware feature engineering.** `features.py` shifts before rolling
  (`grouped.shift(1).rolling(...)`), so rolling statistics never see the
  current target.
- **Robust metric definitions.** `metrics.py` guards WAPE/sMAPE/bias against
  zero denominators and exposes `metrics_by_group` for per-clinic scoring.
- **Correct validation primitives.** `validation.py` implements rolling-origin
  windows with a minimum-training-days guard.
- **Model breadth with safe optional imports.** Seasonal naive and moving
  average (`models/baseline.py`), per-clinic SARIMAX with exogenous support
  (`models/sarimax.py`), a global HistGradientBoosting forecaster
  (`models/ml.py`), and Prophet/TimeGPT behind guarded imports.
- **A real decision layer.** `staffing.py` converts forecasts into role-level
  staffing recommendations with minimums, buffers and gap analysis.
- **Working scaffolding.** Tests for core logic, `Makefile`, `Dockerfile`,
  FastAPI stub (`api/main.py`), docs and a staged roadmap.

## Missing pieces (mapped to files and prompts)

| # | Gap | Where it shows today | Fix lands in | Prompt |
|---|-----|----------------------|--------------|--------|
| 1 | No data contracts or schema validation | `scripts/generate_data.py` and `scripts/run_poc.py` write/read CSVs unvalidated | `src/clinic_forecast/contracts.py`, `tests/test_contracts.py` | 2 |
| 2 | Synthetic data lacks holidays, marketing channels, cancellations, staffing-by-role output, and tunable seasonality/marketing/noise strength | `data.py` (`SyntheticDataConfig` has only dates, clinic count, seed); generator writes 3 CSVs to `data/raw/` instead of the 4 contract files under `data/processed/` | `data.py`, `scripts/generate_data.py`, notebook 01 | 3 |
| 3 | Validation API is minimal: no step size, max folds, or per-clinic splitting; no fold summaries | `validation.py` (`rolling_origin_windows` generator only) | `RollingOriginSplitter` in `validation.py`, notebooks 03–04 | 5 |
| 4 | No shared model-comparison utilities; metric logic risks being re-implemented per notebook | only `metrics_by_group` exists | `src/clinic_forecast/evaluation.py`, `tests/test_evaluation.py` | 6 |
| 5 | SARIMAX uses one fixed order; no candidate selection; Prophet output schema differs from other models | `models/sarimax.py` hard-codes `(1,1,1)(1,0,1,7)`; `optional_prophet.py` returns `yhat*` columns | `src/clinic_forecast/models/` wrappers, notebook 03 | 7 |
| 6 | Global ML model only supports backtest-style prediction (`predict_known_future`); no recursive/direct multi-step forecasting of unseen futures; one-hot alignment between fit and predict is fragile (zero-filled); `StandardScaler` adds nothing for trees; expanding means and explicit marketing/metadata feature joins missing; **bug:** rolling statistics in `add_lag_features` are computed over the concatenated panel (`grouped.shift(1)` returns a flat Series), so windows bleed across clinic boundaries | `models/ml.py`, `features.py` | `models/global_ml.py`, `features.py`, notebook 04 | 8 |
| 7 | No uncertainty quantification anywhere | forecasts are point-only | `src/clinic_forecast/intervals.py` (split conformal, grouped calibration) | 9 |
| 8 | No hierarchical aggregation/reconciliation | region exists in metadata but is never used for coherence | `src/clinic_forecast/reconciliation.py`, notebook 07 | 10 |
| 9 | No-show rate is generated but never modelled; staffing uses raw visits only | `data.py` emits `no_show_rate`, `scheduled_appointments`; nothing consumes them | target definitions + models, staffing updates | 11 |
| 10 | Staffing layer ignores `configs/staffing.yaml` (defaults are duplicated in code), and has no costs, overtime, capacity caps or scenario comparison | `staffing.py`, `configs/staffing.yaml` | `staffing.py` (+config loader), notebook 06 | 12 |
| 11 | No scenario planning for marketing | — | `src/clinic_forecast/scenarios.py`, notebook 08 | 13 |
| 12 | Pipelines are stubs: `pipelines/forecast.py` and `pipelines/train.py` are 10-line wrappers; no batch inference, no persisted outputs | `src/clinic_forecast/pipelines/` | `pipelines/batch_inference.py`, `scripts/run_batch_forecast.py` | 14 |
| 13 | No model registry metadata | — | `src/clinic_forecast/registry.py`, `outputs/model_registry/` | 15 |
| 14 | No monitoring or drift checks | — | `src/clinic_forecast/monitoring.py`, `configs/monitoring.yaml`, notebook 09 | 16 |
| 15 | API serves only `/health` and a single-row `/staffing`; no forecast retrieval, no clinic listing, no API tests | `api/main.py` | `api/` endpoints + `tests/test_api.py` | 17 |
| 16 | No demo workflow: Makefile lacks batch-forecast/notebook targets, no `docs/demo_guide.md` | `Makefile`, `Dockerfile` | Makefile targets, demo guide | 18 |
| 17 | No CI | no `.github/` | `.github/workflows/ci.yml` | 19 |
| 18 | No notebook execution checks | notebooks unverified | `scripts/run_notebook.py`, `make notebook-check` | 20 |
| 19 | TimeGPT wrapper lacks mock tests and a common output schema guarantee | `models/optional_timegpt.py` | `models/timegpt.py` + mock test | 21 |
| 20 | No deep-learning baseline module | notebook 05 only references hooks | `models/lstm.py` (optional Torch) | 22 |
| 21 | No executive summary notebook | notebooks stop at staffing (06) | `notebooks/10_executive_summary_forecasting_to_staffing.ipynb` | 23 |
| 22 | `reports/model_card.md` is thin; no operational risk register | `reports/model_card.md` | model card sections, `docs/operational_risk.md` | 24 |
| 23 | README lacks architecture diagram, CI badge, API examples and reviewer guidance | `README.md` | final polish | 25 |

Infrastructure issues found and fixed during the audit:

- `.gitignore` contained a bare `models/` pattern that silently excluded
  `src/clinic_forecast/models/` from version control (now anchored to `/models/`).
- `poetry.lock` was not committed; it now is, so installs are reproducible.

## Recommended implementation order

Follows the suggested order in the prompts document; each step leaves
`poetry run pytest` green.

1. **Prompt 2 — Data contracts** (`contracts.py`). Foundation for everything
   downstream; cheap, high signal.
2. **Prompt 3 — Richer synthetic data.** Unblocks no-show, scenario and
   monitoring work; defines the four processed CSV contracts.
3. **Prompt 5 — `RollingOriginSplitter`.** Validation correctness before model
   work.
4. **Prompt 6 — Evaluation utilities.** One metric implementation everywhere.
5. **Prompt 8 — Global ML pipeline.** The modelling centrepiece.
6. **Prompt 9 — Conformal intervals.** Uncertainty for staffing decisions.
7. **Prompt 12 — Staffing optimisation.** Costs, overtime, conservative plans.
8. **Prompt 14 — Batch inference.** Production-style outputs feeding the API.
9. **Prompt 17 — FastAPI layer.** Serve batch outputs; API tests.
10. **Prompt 23 — Executive notebook.** The story for reviewers.
11. **Prompt 25 — Final polish.** README, lint, type-check, figures.

Then the advanced extensions: Prompt 10 (hierarchical), 11 (no-show), 13
(scenarios), 16 (monitoring), 15 (registry), 19–20 (CI and notebook checks),
21–22 (TimeGPT, LSTM), 24 (model card and risk docs). Prompts 4 and 7
(EDA and statistical-model notebook upgrades) slot in whenever notebooks are
revisited, ideally after Prompt 3 changes the data files.

## Risks and trade-offs

- **Runtime creep.** SARIMAX candidate grids (Prompt 7) and per-clinic
  backtests multiply quickly: keep grids tiny and cap folds; CI must not run
  heavy notebooks.
- **Optional dependency drift.** Prophet, Torch, XGBoost and Nixtla must stay
  behind guarded imports; a single unguarded import breaks the core install.
  Tests must pass with `--only main` dependencies.
- **One-hot alignment in the global model.** Re-encoding categoricals at
  predict time is fragile; moving to a fitted encoder (or category dtype with
  `HistGradientBoostingRegressor`'s native categorical support) removes a
  whole bug class.
- **Recursive forecasting leakage.** When `predict_known_future` is replaced
  with true multi-step forecasting, lag features must be fed from predictions,
  never future actuals. Leakage tests (Prompt 8) are the guard.
- **Windows/Linux split.** Development happens on Windows; CI will run Linux.
  Avoid path assumptions (`ProjectPaths` already helps) and pin Poetry in CI.
- **Mypy strictness.** `disallow_untyped_defs` is on; new modules must be
  typed from the start or CI gates will need documented exclusions.
- **Scope discipline.** The biggest portfolio risk is half-finished breadth.
  Each prompt should land complete (code + tests + notebook narrative) before
  the next starts.

## Expected portfolio impact

| Improvement | Impact | Why |
|---|---|---|
| Data contracts (P2) | High | Signals production data-engineering maturity; rare in portfolio projects |
| Richer synthetic data (P3) | High | Makes every downstream notebook more convincing |
| Rolling-origin splitter (P5) | High | Correct time-series validation is a key interview differentiator |
| Evaluation utilities (P6) | Medium | Consistency; enables honest model comparison tables |
| Global ML pipeline (P8) | High | Core ML engineering showcase: leakage control, panel features |
| Conformal intervals (P9) | High | Modern, practical UQ; directly feeds conservative staffing |
| Staffing optimisation (P12) | High | Connects ML to money — the business story |
| Batch inference + registry (P14/15) | Medium-High | Production-style MLOps without infrastructure claims |
| FastAPI layer (P17) | Medium | Demonstrates serving; keep it honest and small |
| Monitoring (P16) | Medium | Operations thinking; pairs well with the model card |
| Executive notebook (P23) | High | The first thing a hiring manager opens |
| CI + notebook checks (P19/20) | Medium | Proof the repo actually runs |
| Hierarchical, no-show, scenarios (P10/11/13) | Medium | Depth differentiators once the core is solid |
| TimeGPT/LSTM (P21/22) | Low-Medium | Nice-to-have benchmarks; keep clearly optional |
