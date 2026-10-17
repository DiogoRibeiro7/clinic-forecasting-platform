.PHONY: install data poc test lint format api batch-forecast legacy-batch-forecast dashboard \
	readiness-check release-check package-check notebook-check notebooks pre-commit-install pre-commit actionlint markdownlint yamllint link-check sbom license-report docs-install docs-build docs-serve docker-build docker-test container-scan docker-batch \
	docker-legacy-batch docker-api

install:
	poetry install

data:
	poetry run python scripts/generate_data.py

poc:
	poetry run python scripts/run_poc.py

# Primary operational path: produces the role-specific artifacts served by /v2.
batch-forecast:
	poetry run python scripts/run_role_specific_batch.py --horizon 28

# Backward-compatible completed-visits path for legacy unversioned routes.
legacy-batch-forecast:
	poetry run python scripts/run_batch_forecast.py --horizon 28

# Render the latest role-specific hybrid monitoring artifact as standalone HTML.
dashboard:
	poetry run python scripts/render_hybrid_dashboard.py

# Verify only the local portfolio serving boundary; this is not production certification.
readiness-check:
	poetry run python scripts/verify_portfolio_readiness.py --output-dir outputs

# Validate release metadata only; this target never tags or publishes.
release-check:
	poetry run python scripts/verify_release_metadata.py

# Build wheel/sdist and smoke-test the wheel in a fresh local virtual environment.
package-check:
	rm -rf dist .package-smoke
	poetry build
	test "$(find dist -maxdepth 1 -name '*.whl' | wc -l)" -eq 1
	test "$(find dist -maxdepth 1 -name '*.tar.gz' | wc -l)" -eq 1
	python -m venv .package-smoke
	.package-smoke/bin/python -m pip install --upgrade pip
	.package-smoke/bin/python -m pip install dist/*.whl
	.package-smoke/bin/python -c "import clinic_forecast; from importlib.metadata import version; assert clinic_forecast.__version__ == version('clinic-forecasting-platform')"

test:
	poetry run pytest

lint:
	poetry run ruff check src tests scripts
	poetry run mypy src

format:
	poetry run ruff format src tests scripts
	poetry run ruff check --fix src tests scripts

# Pre-commit itself is isolated from the Poetry application environment.
pre-commit-install:
	pipx install "pre-commit==4.3.0" --force
	pre-commit install

pre-commit:
	pipx run --spec "pre-commit==4.3.0" pre-commit run --all-files

# Validate GitHub Actions syntax and expressions with the same version used in CI.
actionlint:
	go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12

# Validate Markdown structure with the same version used in CI.
markdownlint:
	npx --yes markdownlint-cli2@0.23.3

# Validate repository YAML with the same version used in CI.
yamllint:
	pipx run --spec "yamllint==1.38.0" yamllint .

# Check internal and external links across Markdown files.
link-check:
	docker run --rm -v "$(pwd):/input" lycheeverse/lychee:0.24.2 --no-progress --accept 200,206,429 "/input/**/*.md"

# Generate a reproducible CycloneDX 1.6 SBOM from pyproject.toml + poetry.lock.
sbom:
	mkdir -p reports/sbom
	pipx run --spec "cyclonedx-bom==7.5.0" cyclonedx-py poetry --spec-version 1.6 --output-format JSON --output-reproducible --validate --output-file reports/sbom/cyclonedx.json .
	sha256sum reports/sbom/cyclonedx.json > reports/sbom/cyclonedx.json.sha256

# Generate dependency-license inventory from the installed main environment.
license-report:
	mkdir -p reports/licenses
	poetry run python -m pip install "pip-licenses==5.5.5"
	poetry run pip-licenses --format=json --with-urls --with-description --output-file reports/licenses/dependencies.json
	poetry run pip-licenses --format=markdown --with-urls --with-description --output-file reports/licenses/dependencies.md

api:
	poetry run uvicorn clinic_forecast.api.main:app --reload

notebook-check:
	poetry run python scripts/run_notebook.py

notebooks:
	poetry run jupyter lab

# Documentation tooling is isolated from the application dependency lock.
docs-install:
	pipx install "mkdocs==1.6.1" --force
	pipx inject mkdocs "mkdocs-material==9.7.7"

docs-build: docs-install
	mkdocs build

docs-serve: docs-install
	mkdocs serve

# --- Docker demo ---
IMAGE ?= clinic-forecast

docker-build:
	docker build -t $(IMAGE) .

# The demo image is main-only; install dev tools + tests at run time.
docker-test: docker-build
	docker run --rm $(IMAGE) sh -c "poetry install --only dev --no-interaction && pytest -q"

# Scan the locally built image and fail on fixable CRITICAL vulnerabilities.
container-scan: docker-build
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.76.0 image --severity CRITICAL --ignore-unfixed --exit-code 1 $(IMAGE)

# Primary Docker batch path: populate role-specific /v2 artifacts.
docker-batch: docker-build
	docker run --rm -v "$(CURDIR)/outputs:/app/outputs" $(IMAGE) \
		python scripts/run_role_specific_batch.py --horizon 28

# Compatibility Docker batch path for legacy unversioned endpoints.
docker-legacy-batch: docker-build
	docker run --rm -v "$(CURDIR)/outputs:/app/outputs" $(IMAGE) \
		python scripts/run_batch_forecast.py --horizon 28

docker-api: docker-build
	docker run --rm -p 8000:8000 -v "$(CURDIR)/outputs:/app/outputs" $(IMAGE)
