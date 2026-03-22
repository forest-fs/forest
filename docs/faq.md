# FAQ

## Why OpenRouter as the default?

The app uses **one** HTTP client for an **OpenAI-shaped** API (`AsyncOpenAI` + `base_url`). **Default:** **`LLM_BASE_URL`** is **OpenRouter** (one key, model slugs like `openai/...`). **Alternatively:** point **`LLM_BASE_URL`** at **direct OpenAI**, **Azure OpenAI**, **Ollama**, or any other **OpenAI-compatible** base URL — then use **that** provider’s API key and model IDs (not OpenRouter slugs). See **[LLM configuration](llm-configuration.md)**.

## Why pgvector if search is not in scope yet?

Embeddings are computed and stored on ingest so **semantic search can ship later without backfilling** every historical file.

## Why one HTTP process?

Simplicity: shared memory for background tasks, one config load, one database pool. Slack webhooks + health routes all run in a single Uvicorn process.

## What happens if onboarding fails?

The error is logged and the result is posted back to the Slack channel. An admin can run **`@forest init`** again after fixing permissions, LLM configuration, or database issues.

## Why a text list for `@forest show` instead of an interactive tree UI?

`@forest show` renders a **nested bullet list** (indented `-` lines, bold folder names, `<url|name>` for files) using Slack mrkdwn. A clickable hierarchical navigator is out of scope for now.

## Can I run without Docker?

Yes, if you provide PostgreSQL with the **vector** extension yourself and set `DATABASE_URL` accordingly. The repo includes Compose as the **baseline** for local development and CI parity.

## How do I change embedding dimensions? / `expected X dimensions, not Y`

The `file_nodes.embedding` column is `vector(N)` and must match your embedding model's output length. The default schema is **`vector(768)`** (revision `e2b3f001`), with **`text-embedding-3-small`**-style models and the API `dimensions` parameter (see [LLM configuration](llm-configuration.md)).

If you see a dimension mismatch, align three places:

1. **`EMBEDDING_VECTOR_DIMENSIONS`** and `Vector(...)` in `forest/models/file_node.py`
2. **Alembic** migration for the column (`vector(N)` in the DB)
3. **`EMBEDDING_MODEL_ID`** for your LLM endpoint — pick a model whose output length is **N**

Then rebuild and restart. If you change embedding dimension or model after data exists, plan a **re-embedding** strategy; see [LLM configuration → Changing embedding model](llm-configuration.md#changing-embedding-model).

## Is duplicate content avoided?

Ingest uses an **`external_key`** (hash of source URL and message id) with a partial unique index per workspace. Collisions on path or key surface as database integrity errors and are handled per cue.

## Where do I add business logic that must stay platform-independent?

**`forest/services/`**, operating on **`forest/integrations/`** types and repositories — not inside `platforms/slack`.

## How do tests run without a real database?

`tests/conftest.py` sets placeholder env vars so imports succeed. Unit tests avoid DB calls; integration tests are **opt-in** via `FOREST_RUN_DB_INTEGRATION=1`.
