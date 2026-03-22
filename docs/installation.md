# Installation

## Prerequisites

- **Python 3.11+**
- **[Poetry](https://python-poetry.org/)** for dependency management
- **Docker** (recommended) for local **PostgreSQL + pgvector**, matching the committed `docker-compose.yml`

You need accounts and tokens for:

- A **Slack** application (bot token + signing secret). See [Slack app setup](slack-app-setup.md) for the full walkthrough.
- An **LLM** reachable via an **OpenAI-compatible** HTTP API (default: [OpenRouter](https://openrouter.ai/)). See **[LLM configuration](llm-configuration.md)** for keys, `LLM_BASE_URL`, model IDs, and embedding dimensions.

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
- `SLACK_BOT_TOKEN` — from your Slack app's OAuth & Permissions page
- `SLACK_SIGNING_SECRET` — from your Slack app's Basic Information page
- `LLM_API_KEY` (or legacy `OPENROUTER_API_KEY`)
- `CHAT_MODEL_ID`
- `EMBEDDING_MODEL_ID`

Optional:

- `LLM_BASE_URL` (or `OPENROUTER_BASE_URL`; default is OpenRouter)
- `LLM_HTTP_REFERER`, `LLM_APP_NAME` (or `OPENROUTER_*`) — OpenRouter attribution headers

## Database and Docker Compose

**Full stack (recommended for trying the app):** Postgres and the `forest` app start together. The container entrypoint runs `alembic upgrade head` before `poetry run forest`.

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

The initial Alembic revision (**`e2b3f001`**) creates **`vector(768)`** (`EMBEDDING_VECTOR_DIMENSIONS`). The app requests that size from the embedding API when the model supports a `dimensions` parameter (e.g. `text-embedding-3-small` on OpenAI or `openai/text-embedding-3-small` on OpenRouter). Your `EMBEDDING_MODEL_ID` must yield **768**-length vectors for that setup, or you must change the constant and ship a matching Alembic `ALTER COLUMN` (document any change for operators).

> **Older checkouts:** embedding dimension used to be adjusted in follow-up migrations (`e2b3f002`, `e2b3f003`). Those revisions were **removed** in favor of a single schema. If you already applied the old chain in production, do **not** reset Alembic blindly — treat this repo as a fresh baseline or migrate your DB manually.

Switching to a different embedding model or dimension is **not** only a config change if `N` changes: see **[LLM configuration → Changing embedding model](llm-configuration.md#changing-embedding-model)**.

## Running

With Docker Compose already covered above, for **host** runs with Poetry:

```bash
poetry run forest
```

The process starts a single **Uvicorn** HTTP server on port **8000**, handling Slack Events API webhooks (`/slack/events`) and health probes.

## Health endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz` | Liveness: process is running (HTTP 200, no dependency checks) |
| `GET /ready` | Readiness: tries `SELECT 1` on the configured database. Returns `{"status":"ready"}` or `{"status":"not_ready"}`. |

## Logging

Stdlib `logging` at the level set by `LOG_LEVEL` (default `INFO`). Structured fields use `extra=` dicts at key boundaries (ingest, onboarding, LLM calls).

## Graceful shutdown

`Ctrl-C` or `SIGINT` stops Uvicorn. In-flight `asyncio` tasks (e.g. background ingest or onboarding) may be cancelled; the follow-up message will not be posted if the process exits before onboarding completes.

## Verify install

- Run unit tests: `poetry run pytest`
- Optional DB integration tests: see root README (`FOREST_RUN_DB_INTEGRATION=1`)

Next: [Deployment](deployment.md) for remote hosting on AWS or GCP.
