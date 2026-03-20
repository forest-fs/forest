# Installation

## Prerequisites

- **Python 3.11+**
- **[Poetry](https://python-poetry.org/)** for dependency management
- **Docker** (recommended) for local **PostgreSQL + pgvector**, matching the committed `docker-compose.yml`

You need accounts and tokens for:

- A **Discord** application and bot user. Step-by-step: [Discord setup](discord-setup.md).
- **[OpenRouter](https://openrouter.ai/)** (API key and chosen model slugs).

## Clone and install Python dependencies

```bash
cd forest-fs
poetry install
```

Development tools (pytest, ruff, Alembic sync driver) live in the `dev` group; `poetry install` includes them per `pyproject.toml` groups as configured in your workflow.

## Environment file

```bash
cp .env.example .env
```

Set at least:

- `DATABASE_URL` — for **host** runs, default points at Postgres on `localhost`. The **`forest` Docker Compose service** overrides this to use the Compose network hostname `postgres` (you can keep `localhost` in `.env` when using Compose; see root README).
- `DISCORD_TOKEN` — from the Discord Developer Portal; see [Discord setup](discord-setup.md)
- `OPENROUTER_API_KEY`
- `CHAT_MODEL_ID`
- `EMBEDDING_MODEL_ID`

Optional:

- `DISCORD_SYNC_GUILD_ID` — speeds up slash command sync during development.
- `OPENROUTER_HTTP_REFERER`, `OPENROUTER_APP_NAME` — OpenRouter attribution headers.

## Database and Docker Compose

**Full stack (recommended for trying the app):** Postgres and the Forest app start together. The container entrypoint runs `alembic upgrade head` before `poetry run forest`.

```bash
docker compose up --build
```

**Postgres only** (for local development with Poetry on the host):

```bash
docker compose up -d postgres
```

## Migrations (host / manual)

Alembic reads `DATABASE_URL` and rewrites `+asyncpg` to `+psycopg2` internally. For host runs, install the dev dependency `psycopg2-binary` (Poetry dev group).

```bash
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://forest:forest@localhost:5432/forest}"
poetry run alembic upgrade head
```

Docker images install `psycopg2-binary` for the same Alembic step inside `docker-entrypoint.sh`.

## Embedding dimension

After the initial revision and **`e2b3f002`**, the ORM uses **`vector(3072)`** (`EMBEDDING_VECTOR_DIMENSIONS`). Your `EMBEDDING_MODEL_ID` must output **3072**-length vectors, or you must change the constant and ship a matching Alembic `ALTER COLUMN` (document any change in README for operators).

## Verify install

- Run unit tests: `poetry run pytest`
- Optional DB integration tests: see root README (`FOREST_RUN_DB_INTEGRATION=1`)

Next: [Startup and operations](startup.md).
