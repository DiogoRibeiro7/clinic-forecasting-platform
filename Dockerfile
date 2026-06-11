FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.3

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY configs ./configs

RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-interaction --no-ansi

CMD ["uvicorn", "clinic_forecast.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
