# 森 forest

`森 forest` is a lightweight intelligence layer that manages your workspace knowledge directly from your chats, _so that you don't have to_.

Naturally, teams will share files from different platforms and discuss them in chat — forest listens and organizes.

<p align="center">
  <img src="public/forest-flow.png" alt="Teams share files and discuss them in Slack — forest connects to those conversations and builds a knowledge layer." />
</p>

Say _sayionara_ to organizing these yourself (or even worse, having someone else organize them!); just let your teammates create/store them in their platforms of preference, and let `森 forest` manage the rest.

## Usage


Browse your workspace tree with `@forest show`.

<p align="center">
  <img src="public/forest-show.png" alt="@forest find lets you search by natural language — ask for 'ui mockup Tim and I discussed' and get the file along with the conversation context." width="700" />
</p>

Find any file by context with `@forest find`.


<p align="center">
  <img src="public/forest-find.png" alt="@forest show returns a virtual file tree organized by topic — engineering, design, fundraising — pulling files from GitHub, Figma, Notion, and more." width="700" />
</p>



## Self Hosting

For full privacy, we let _you_ host it — it's simple to set up, just follow the steps below.

### Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- Docker (for local Postgres + pgvector)

### Remote setup

TODO

### Local setup

1. Copy environment template and fill in secrets:

   ```bash
   cp .env.example .env
   ```

   Set `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `OPENROUTER_API_KEY`, `CHAT_MODEL_ID`, and `EMBEDDING_MODEL_ID`. For **Docker Compose**, `DATABASE_URL` in `.env` can stay `localhost`; the `forest` service overrides it to reach the `postgres` container.

   After migrations, the `file_nodes.embedding` column is **`vector(3072)`** (see `EMBEDDING_VECTOR_DIMENSIONS` in code and Alembic `e2b3f002`). Use an OpenRouter embedding model whose output size matches (many large embedding models use 3072). If you use a **1536**-dim model instead, change the model constant and add an Alembic migration to match, or pick a 3072-dim model.

2. Run everything with Docker Compose (Postgres + Forest: migrations, then HTTP server):

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

#### Testing Slack against localhost (cloudflared)

Slack needs a **public HTTPS** URL; it cannot POST to `localhost`. Use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/) (`cloudflared`) to expose your local server:

1. Install `cloudflared` (see Cloudflare’s docs for your OS).
2. Start Forest on port **8000** (Compose or `poetry run forest` as above).
3. In another terminal, run (use **`127.0.0.1`**, not `localhost`, so the tunnel hits the same IPv4 socket Uvicorn binds to on macOS):

   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```

4. Copy the **`https://….trycloudflare.com`** URL from the output (it changes each run unless you use a named tunnel). **That hostname only works while this `cloudflared` process is running** — if you restart it, use the new URL.
5. Check the tunnel (replace the host with yours):

   ```bash
   curl -sS https://<tunnel-host>/healthz
   ```

   Expect `{"status":"ok"}`. `GET /` returns a small JSON map with the same paths if you want a quick sanity check in the browser.

   If you see **404** with almost no body: the tunnel hostname may be from an old run, or `cloudflared` is not forwarding to a running Forest on port **8000**. Confirm first: `curl -sS http://127.0.0.1:8000/healthz` on the machine where Forest runs.

6. In your Slack app ([api.slack.com/apps](https://api.slack.com/apps)), set:
   - **Event Subscriptions** → Request URL: `https://<tunnel-host>/slack/events`

Invite the bot to any channel you use for tests. Keep both Forest and `cloudflared` running while developing.

### Slack

Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps):

1. **Event Subscriptions**: set Request URL to `https://<host>/slack/events` (production host, or your [cloudflared](#testing-slack-against-localhost-cloudflared) URL locally). Subscribe to `app_mention` and `message.channels`.
2. **OAuth & Permissions**: add scopes `app_mentions:read`, `channels:history`, `channels:read`, `chat:write`, `files:read`. Install to your workspace.
3. Copy the **Bot User OAuth Token** and **Signing Secret** into `.env`.

Mention commands:

- `@forest help` — short overview (anyone).
- `@forest init` — scans readable channels (full message history, subject to transcript size limits in settings) and seeds the virtual tree. Posts the result to the channel when complete.
- `@forest update` — same scan + re-merge new directories; does not replay ingest for old messages.
- `@forest show` — captured files as a nested list with links.

### Tests

Unit tests run without a live database. Optional DB integration tests:

```bash
export FOREST_RUN_DB_INTEGRATION=1
# Postgres running with migrations applied (see above)
poetry run pytest
```

## More Documentation

Longer-form docs (purpose, architecture, installation, FAQ) live under [docs/](docs/index.md).



## TODOs

- Add remote self hosting
- Semantic search (`@forest find`) and pgvector ANN tuning (repository search, query embeddings, ANN index).
- Telemetry (`/metrics`, OpenTelemetry, or similar) and a small observability facade.
