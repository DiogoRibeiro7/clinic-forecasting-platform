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
make readiness-check # after a role-specific batch run; verifies local serving provenance
make release-check   # validates release metadata only; never tags or publishes
make package-check   # builds wheel/sdist and smoke-tests the built wheel
make docs-build       # builds the MkDocs documentation site
make pre-commit       # runs local Ruff + mypy hooks over the repository
make actionlint        # validates GitHub Actions YAML and expressions
make markdownlint      # validates Markdown structure
make yamllint          # validates YAML syntax and structure
make link-check        # checks internal and external Markdown links
make sbom              # generates a reproducible CycloneDX SBOM
make container-scan    # scans the Docker image for fixable CRITICAL CVEs
```

`make format` applies ruff's autofixes if the lint step complains.

For local commit-time checks, install the hook once:

```bash
make pre-commit-install
```

The hook reuses the Poetry environment for Ruff and mypy, so there is no second
lint/type-check configuration to maintain. `make pre-commit` runs the same
hooks manually across all files.

GitHub Actions workflows are validated separately with actionlint 1.7.12.
Python code is also scanned by GitHub CodeQL in CI for code-level security issues.
Run `make actionlint` locally when changing files under `.github/workflows/`.
This requires Go locally but does not modify the Poetry environment.

Documentation tooling is intentionally isolated from the Poetry application lock.
`make docs-build` and `make docs-serve` install MkDocs 1.6.1 in an isolated
`pipx` environment and inject MkDocs Material 9.7.7 into it, so documentation
changes do not perturb runtime dependencies.

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

For potential security vulnerabilities, do **not** publish exploit details in a
public issue. Follow [`SECURITY.md`](SECURITY.md) for private reporting guidance.

## Code of conduct

By participating you agree to uphold the [Code of Conduct](CODE_OF_CONDUCT.md).

## Documentation linting

Markdown files are validated with markdownlint-cli2 0.23.3. The configuration
keeps structural checks enabled while disabling line-length, inline-HTML and
bare-URL rules to avoid low-value churn in scientific and technical prose.

Run locally with:

```bash
make markdownlint
```

## YAML linting

YAML files are validated with yamllint 1.38.0. The repository configuration
disables line-length, document-start and truthy-key checks so GitHub Actions
syntax such as `on:` is not treated as a style defect, while structural YAML
validation remains active.

Run locally with:

```bash
make yamllint
```

## Editor consistency

The repository includes a root `.editorconfig` so supported editors use the same
UTF-8, LF, final-newline and indentation conventions. Python uses four spaces,
YAML and JSON use two spaces, and Makefile recipes retain tabs.

## Software bill of materials

`make sbom` generates a reproducible CycloneDX 1.6 JSON SBOM from the locked
Poetry dependency graph and records its SHA-256 digest under `reports/sbom/`.
The CI workflow uploads those files as artifacts when dependency metadata changes.

The SBOM is dependency inventory/provenance metadata. It is not a vulnerability
scan, signature, SLSA attestation, or production-readiness certificate.

## Link checking

Markdown links are checked with Lychee 0.24.2. CI scans repository Markdown for
broken internal and external links while keeping the application environment
untouched.

Run locally with Docker:

```bash
make link-check
```


## Container vulnerability scanning

The Docker image is scanned with Trivy 0.76.0. CI reports HIGH and CRITICAL
findings and fails only on fixable CRITICAL vulnerabilities, which keeps the
security gate actionable rather than permanently red because of upstream
unfixed issues.

Run locally with:

```bash
make container-scan
```
