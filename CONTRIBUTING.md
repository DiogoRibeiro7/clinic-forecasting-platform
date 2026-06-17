# Contributing

Thanks for your interest in this project. It is a portfolio-grade proof of
concept, so contributions are welcome but the scope is intentionally bounded —
please open an issue to discuss anything substantial before sending a pull
request.

## Development setup

The project targets **Python 3.11** and uses [Poetry](https://python-poetry.org/).

```bash
poetry env use 3.11
poetry install                 # core deps
poetry install --with optional # adds the full model zoo (Prophet, XGBoost,
                               # LightGBM, the Nixtla ecosystem, torch, Chronos)
poetry run python scripts/generate_data.py
```

> The numba-based Nixtla packages (`statsforecast`, `mlforecast`) are unstable
> on Windows + Python 3.12; use Python 3.11. See the README "Optional
> dependencies" note for details.

## Before you open a pull request

All three gates must pass — they are exactly what CI runs:

```bash
make lint           # ruff + mypy (strict typing on src/)
make test           # pytest
make notebook-check # executes notebooks 00, 01 and 06 end to end
```

`make format` applies ruff's autofixes if the lint step complains.

## Expectations for changes

- **Tests for non-trivial logic.** New behaviour should come with a test;
  optional-dependency code is tested through its injectable seam (a mock
  forecaster / `predict_fn`) so the suite never needs the heavy library.
- **Typed and documented.** Public functions get type hints and a docstring;
  `mypy src` must stay clean.
- **Optional stays optional.** Heavy or platform-specific models live behind
  guarded imports and return the project's common forecast schema
  (`clinic_id, date, forecast, model`). The core PoC must run without them.
- **No real or patient-level data.** All data is synthetic and PHI-free; keep
  it that way.
- **Notebooks ship executed.** If you change a notebook, re-run it top to
  bottom on the 3.11 env so committed outputs stay consistent.
- **Commits.** Clear, present-tense messages; group related changes.

## Reporting issues

Open a GitHub issue with steps to reproduce, the expected vs actual behaviour,
and your OS / Python version. For modelling questions, include the relevant
notebook or script and the metrics you are seeing.

## Code of conduct

By participating you agree to uphold the [Code of Conduct](CODE_OF_CONDUCT.md).
