.PHONY: install data poc test lint format api

install:
	poetry install

data:
	poetry run python scripts/generate_data.py

poc:
	poetry run python scripts/run_poc.py

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
