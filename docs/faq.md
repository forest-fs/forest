# FAQ

## Why OpenRouter only?

The MVP standardizes on one OpenAI-compatible HTTP surface with a single API key and model slugs. Vendor-specific SDKs are avoided so routing and policy stay centralized. You can still target many models **through** OpenRouter.

## Why pgvector if search is not in scope yet?

Embeddings are computed and stored on ingest so **semantic search can ship later without backfilling** every historical file.

## Why one HTTP process?

Simplicity: shared memory for background tasks, one config load, one database pool. Slack webhooks + health routes all run in a single Uvicorn process.

## What happens if onboarding fails?

The error is logged and the result is posted back to the Slack channel. An admin can run **`@forest init`** again after fixing permissions, OpenRouter, or database issues.

## Why a text list for `@forest show` instead of an interactive tree UI?

`@forest show` renders a **nested bullet list** (indented `-` lines, bold folder names, `<url|name>` for files) using Slack mrkdwn. A clickable hierarchical navigator is out of scope for now.

## Can I run without Docker?

Yes, if you provide PostgreSQL with the **vector** extension yourself and set `DATABASE_URL` accordingly. The repo includes Compose as the **baseline** for local development and CI parity.

## How do I change embedding dimensions?

Align three places: constant **`EMBEDDING_VECTOR_DIMENSIONS`** and `Vector(...)` in `forest/models/file_node.py`, **Alembic** migrations (`vector(N)` in the DB), and an `EMBEDDING_MODEL_ID` on OpenRouter whose output length is **N**.

The default schema after all migrations is **3072** (revision `e2b3f002`). If you see `expected 1536 dimensions, not 3072` (or the opposite), your model output and the database column disagree: run `poetry run alembic upgrade head`, or switch models, or add a migration to change `N`.

## ``expected X dimensions, not Y`` when ingesting?

The embedding API returned length **Y** but the `file_nodes.embedding` column is `vector(X)`. Fix by using a model with output size **X**, or migrate the column to `vector(Y)` and update `EMBEDDING_VECTOR_DIMENSIONS` to match (then rebuild/restart).

## Is duplicate content avoided?

Ingest uses an **`external_key`** (hash of source URL and message id) with a partial unique index per workspace. Collisions on path or key surface as database integrity errors and are handled per cue.

## Where do I add business logic that must stay platform-independent?

**`forest/services/`**, operating on **`forest/integrations/`** types and repositories — not inside `platforms/slack`.

## How do tests run without a real database?

`tests/conftest.py` sets placeholder env vars so imports succeed. Unit tests avoid DB calls; integration tests are **opt-in** via `FOREST_RUN_DB_INTEGRATION=1`.
