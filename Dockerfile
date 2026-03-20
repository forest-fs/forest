# Forest: Discord bot + FastAPI in one process.
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    POETRY_NO_ANSI=1

WORKDIR /app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock ./
COPY forest ./forest
COPY alembic ./alembic
COPY alembic.ini ./
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Main deps + package; psycopg2-binary for Alembic (sync migrations) in entrypoint.
RUN poetry install --only main --no-interaction --no-ansi \
    && pip install --no-cache-dir "psycopg2-binary>=2.9,<3"

RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
