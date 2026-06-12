FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

# Install dependencies first for layer caching. Only the main group is
# installed: optional deep-learning / foundation-model packages stay out of
# the demo image to keep it light.
COPY pyproject.toml poetry.lock README.md ./
COPY src ./src
RUN poetry install --only main --no-interaction --no-ansi

# Project files needed to run the demo end to end.
COPY scripts ./scripts
COPY configs ./configs
COPY Makefile ./Makefile

# Generate the synthetic data at build time so the image is demo-ready.
RUN python scripts/generate_data.py

EXPOSE 8000

# Default: serve the API. Populate outputs first with the batch pipeline, e.g.
# `docker run --rm clinic-forecast python scripts/run_batch_forecast.py`.
CMD ["uvicorn", "clinic_forecast.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
