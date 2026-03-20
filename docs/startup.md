# Startup and operations

## Run the application

### Docker Compose (Postgres + Forest)

With `.env` filled in (at least Discord and OpenRouter variables):

```bash
docker compose up --build
```

Forest listens on **port 8000** by default; set `FOREST_HTTP_PORT` on the host to change the published port mapping. Migrations run automatically on container start.

### Poetry on the host

From the repository root with `.env` populated and migrations applied:

```bash
poetry run forest
```

This starts:

- The **Discord** bot (gateway connection, slash commands, message listener).
- **Uvicorn** serving the FastAPI app from the same asyncio loop.

There is no separate worker process in the MVP; ingest jobs are processed in-process on a background task owned by the bot.

## HTTP endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz` | **Liveness** — process is running; does not check the database. |
| `GET /ready` | **Readiness** — runs `SELECT 1` against PostgreSQL; returns `not_ready` on failure. |

Default bind is `HOST` / `PORT` from settings (`0.0.0.0:8000` unless overridden).

## Logging

`LOG_LEVEL` controls stdlib logging (default `INFO`). Key `extra` fields include `operation`, `guild_id`, `workspace_id`, and `llm_backend=openrouter` at LLM boundaries.

Do not configure logging to print secrets (tokens, API keys).

## Discord slash command sync

On startup, the bot syncs application commands either:

- **Globally** (default), or
- To a **single guild** when `DISCORD_SYNC_GUILD_ID` is set (faster iteration while developing).

If sync fails, check logs; permissions and intent misconfiguration often show up as runtime errors when handling messages or commands.

## Failure modes (operator checklist)

- **Database down**: `/ready` fails; ingest and slash commands that need DB will error or skip.
- **OpenRouter errors**: routing may fall back to `/Inbox`; repeated failures should be visible in logs with retry warnings.
- **Queue full**: ingest enqueue logs a warning and drops the message (bounded queue protects the gateway thread).

## Graceful shutdown

Interrupt the process (e.g. Ctrl+C); `KeyboardInterrupt` is handled in the main entrypoint so shutdown is orderly at the Python level. In-flight ingest jobs may be lost (no durable queue in MVP).
