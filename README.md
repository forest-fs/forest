# 森 forest

`森 forest` is a lightweight intelligence layer that manages your workspace knowledge directly from your chats, _so that you don't have to_.

Naturally, teams will share files from different platforms and discuss them in chat — forest listens and organizes.

<p align="center">
  <img src="public/forest-flow.png" alt="Teams share files and discuss them in Slack — forest connects to those conversations and builds a knowledge layer." />
</p>

Say _sayionara_ to organizing these yourself (or even worse, having someone else organize them!); just let your teammates create/store them in their platforms of preference, and let `森 forest` manage the rest.

## Usage


Browse your workspace tree with `@forest show`, or fomd any file by context with `@forest find`.

<p align="center">
  <img src="public/forest-show.png" alt="@forest find lets you search by natural language — ask for 'ui mockup Tim and I discussed' and get the file along with the conversation context." width="700" />
</p>



## Self Hosting

For full privacy, we let _you_ host it — it's simple to set up, just follow the steps below.

### Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/)
- Docker (for local Postgres + pgvector)

### Slack

Create a Slack app, add the required scopes and event subscriptions, then copy the bot token and signing secret into `.env`. Full walkthrough: **[docs/slack-app-setup.md](docs/slack-app-setup.md)**.

### Local setup

1. Copy environment template and fill in secrets:

   ```bash
   cp .env.example .env
   ```

   Set `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `LLM_API_KEY` (or `OPENROUTER_API_KEY`), `CHAT_MODEL_ID`, and `EMBEDDING_MODEL_ID`. **Default** URL is **OpenRouter**; to use **direct OpenAI** or another **OpenAI-compatible** API instead, set `LLM_BASE_URL` — see **[docs/llm-configuration.md](docs/llm-configuration.md)**.

2. Run everything with Docker Compose (Postgres + Forest):

   ```bash
   docker compose up --build
   ```

   Or run **only Postgres** and use Poetry on the host:

   ```bash
   docker compose up -d postgres
   poetry install
   poetry run alembic upgrade head
   poetry run forest
   ```

   HTTP is on port **8000**. `GET /healthz` for liveness, `GET /ready` for DB readiness.

3. Slack needs a **public HTTPS** URL. For local dev, use [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/):

   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```

   Copy the `https://….trycloudflare.com` URL and set it as your Slack app's **Event Subscriptions → Request URL** (`https://<tunnel-host>/slack/events`).

Full local setup details (migrations, embedding dimensions, troubleshooting): **[docs/installation.md](docs/installation.md)**. LLM endpoints and model IDs: **[docs/llm-configuration.md](docs/llm-configuration.md)**.

### Remote setup (AWS / GCP)

Forest is a single container + managed Postgres — the pattern is the same on any cloud:

1. **Provision PostgreSQL with pgvector** (RDS on AWS, Cloud SQL on GCP).
2. **Push the Docker image** to a container registry (ECR / Artifact Registry).
3. **Deploy the container** with environment variables pointing at the database and your Slack/LLM credentials (`LLM_API_KEY` or `OPENROUTER_API_KEY`; see [LLM configuration](docs/llm-configuration.md)).
4. **Point Slack** at the public HTTPS endpoint (`https://<host>/slack/events`).

| | AWS | GCP |
|---|---|---|
| **Database** | RDS PostgreSQL 16 (`CREATE EXTENSION vector`) | Cloud SQL PostgreSQL 16 (`cloudsql.enable_pgvector=on`) |
| **Compute** | ECS Fargate + ALB, or App Runner | Cloud Run |
| **Registry** | ECR | Artifact Registry |
| **HTTPS** | ALB with ACM cert, or App Runner built-in | Cloud Run built-in |
| **Secrets** | Secrets Manager / SSM Parameter Store | Secret Manager |

Full step-by-step CLI commands for both providers: **[docs/deployment.md](docs/deployment.md)**.

### Tests

```bash
poetry run pytest
```

For DB integration tests, set `FOREST_RUN_DB_INTEGRATION=1` with Postgres running.

## More Documentation

Longer-form docs (purpose, architecture, installation, LLM setup, FAQ) live under [docs/](docs/index.md).

## TODOs

- Semantic search (`@forest find`) and pgvector ANN tuning (repository search, query embeddings, ANN index).
- Telemetry (`/metrics`, OpenTelemetry, or similar) and a small observability facade.
