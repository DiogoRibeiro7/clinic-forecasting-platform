.PHONY: install data poc test lint format api batch-forecast legacy-batch-forecast \
	notebook-check notebooks docker-build docker-test docker-batch docker-legacy-batch docker-api

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

test:
	poetry run pytest

lint:
	poetry run ruff check src tests scripts
	poetry run mypy src

format:
	poetry run ruff format src tests scripts
	poetry run ruff check --fix src tests scripts

api:
	poetry run uvicorn clinic_forecast.api.main:app --reload

notebook-check:
	poetry run python scripts/run_notebook.py

notebooks:
	poetry run jupyter lab

# --- Docker demo ---
IMAGE ?= clinic-forecast

docker-build:
	docker build -t $(IMAGE) .

# The demo image is main-only; install dev tools + tests at run time.
docker-test: docker-build
	docker run --rm $(IMAGE) sh -c "poetry install --only dev --no-interaction && pytest -q"

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
