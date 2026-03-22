# Startup and operations

## Running

With `.env` filled in (at least Slack and OpenRouter variables):

```bash
poetry run forest
```

Or via Docker Compose (entrypoint runs migrations then starts the app):

```bash
docker compose up --build
```

The process starts a single **Uvicorn** HTTP server, which handles:

- Slack Events API webhooks (`/slack/events`) — passive ingest and mention commands
- Health probes (`/healthz`, `/ready`)

## Health endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz` | Liveness: process is running (HTTP 200, no dependency checks) |
| `GET /ready` | Readiness: tries `SELECT 1` on the configured database. Returns `{"status":"ready"}` or `{"status":"not_ready"}`. |

## Logging

Stdlib `logging` at the level set by `LOG_LEVEL` (default `INFO`). Structured fields use `extra=` dicts at key boundaries (ingest, onboarding, LLM calls). No distributed tracing in the current version.

## Graceful shutdown

`Ctrl-C` or `SIGINT` stops Uvicorn. In-flight `asyncio` tasks (e.g. background ingest or onboarding) may be cancelled; the follow-up message will not be posted if the process exits before onboarding completes. This is acceptable for self-hosted single-container deployments.
