# 森 forest

`森 forest` is a lightweight intelligence layer that manages your workspace knowledge directly from your chats, _so that you don't have to_.

Naturally, teams will share files from different platforms and discuss them in chat — forest listens and organizes.

<p align="center">
  <img src="public/forest-flow.png" alt="Teams create cross-platform files and discuss them in Discord, Slack, or Teams — forest connects to those conversations and builds a knowledge layer." />
</p>

Say _sayionara_ to organizing these yourself (or even worse, having someone else organize them!); just let your teammates create/store them in their platforms of preference, and let `森 forest` manage the rest.

## Usage


Browse your workspace tree with `/forest show`.

<p align="center">
  <img src="public/forest-show.png" alt="/forest find lets you search by natural language — ask for 'ui mockup Tim and I discussed' and get the file along with the conversation context." width="700" />
</p>

Find any file by context with `/forest find`.


<p align="center">
  <img src="public/forest-find.png" alt="/forest show returns a virtual file tree organized by topic — engineering, design, fundraising — pulling files from GitHub, Figma, Notion, and more." width="700" />
</p>



## Self Hosting
For full privacy, we let _you_ host it, it's simple to set up, just follow the steps below.

### Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- Docker (for local Postgres + pgvector)

### Local setup

1. Copy environment template and fill in secrets:

   ```bash
   cp .env.example .env
   ```

   Set `DISCORD_TOKEN`, `OPENROUTER_API_KEY`, `CHAT_MODEL_ID`, and `EMBEDDING_MODEL_ID`. For **Docker Compose**, `DATABASE_URL` in `.env` can stay `localhost`; the `forest` service overrides it to reach the `postgres` container.

   After migrations, the `file_nodes.embedding` column is **`vector(3072)`** (see `EMBEDDING_VECTOR_DIMENSIONS` in code and Alembic `e2b3f002`). Use an OpenRouter embedding model whose output size matches (many large embedding models use 3072). If you use a **1536**-dim model instead, change the model constant and add an Alembic migration to match, or pick a 3072-dim model.

2. Run everything with Docker Compose (Postgres + Forest: migrations, then bot + HTTP):

   ```bash
   docker compose up --build
   ```

   The Forest image runs `alembic upgrade head` on startup, then `poetry run forest`. HTTP is on port **8000** (override host mapping with `FOREST_HTTP_PORT` if needed).

   Or run **only Postgres** and use Poetry on the host:

   ```bash
   docker compose up -d postgres
   poetry install
   export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://forest:forest@localhost:5432/forest}"
   poetry run alembic upgrade head
   poetry run forest
   ```

   Alembic uses a sync URL internally (`+psycopg2`); the dev dependency `psycopg2-binary` covers host runs; the Docker image installs it for migration startup.

   - `GET /healthz` — process up
   - `GET /ready` — database reachable

### Discord

Enable **Message Content Intent** (and guild/message intents as needed) in the Developer Portal. Bot permissions: read messages, read history, embed links, use slash commands.

Slash commands:

- `/forest help` — short overview (anyone).
- `/forest init` — scans readable channels (full message history, subject to transcript size limits in settings) and seeds the virtual tree (requires Manage Server). Also runs automatically when the bot joins a guild.
- `/forest update` — same scan + re-merge new directories (recovery / layout refresh); does not replay ingest jobs for old messages.
- `/forest files` — flat paginated list of captured files with paths and links.

Optional `DISCORD_SYNC_GUILD_ID` in `.env` speeds up slash command sync while developing.


### Tests

Unit tests run without a live database. Optional DB integration tests:

```bash
export FOREST_RUN_DB_INTEGRATION=1
# Postgres running with migrations applied (see above)
poetry run pytest
```

## More Documentation

Longer-form docs (purpose, architecture, installation, FAQ, and notes for a future static site such as `forest.docs`) live under [docs/](docs/index.md). For the Discord bot token and invite flow, see [docs/discord-setup.md](docs/discord-setup.md).



## TODOs

- Semantic search (`/forest find`) and pgvector ANN tuning (repository search, query embeddings, ANN index).
- Telemetry (`/metrics`, OpenTelemetry, or similar) and a small observability facade.
