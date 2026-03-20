# FAQ

## Why OpenRouter only?

The MVP standardizes on one OpenAI-compatible HTTP surface with a single API key and model slugs. Vendor-specific SDKs are avoided so routing and policy stay centralized. You can still target many models **through** OpenRouter.

## Why pgvector if search is not in MVP?

Embeddings are computed and stored on ingest so **semantic search can ship later without backfilling** every historical file, unless you explicitly choose a summary-only mode elsewhere.

## Why one process for HTTP and Discord?

Simplicity: shared memory for the ingest queue, one config load, one database pool. Horizontal scaling would require a durable queue or out-of-process workers (out of MVP scope).

## What happens if onboarding fails on guild join?

Auto-onboarding is best-effort and logged. An admin can run **`/forest init`** after fixing permissions, OpenRouter, or database issues.

## Why a markdown list for `/forest files` instead of an interactive tree UI?

`/forest files` renders a **nested bullet list** (Markdown: indented `-` lines, bold folder names, `[filename](url)` for files) so Discord can **linkify** URLs. It stays **paginated** by line for message limits. A clickable hierarchical navigator is out of MVP scope.

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

**`forest/services/`**, operating on **`forest/integrations/`** types and repositories — not inside `platforms/discord`.

## How do tests run without a real database?

`tests/conftest.py` sets placeholder env vars so imports succeed. Unit tests avoid DB calls; integration tests are **opt-in** via `FOREST_RUN_DB_INTEGRATION=1`.
