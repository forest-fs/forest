# Purpose

## What Forest is

Forest is a **virtual filesystem** backed by a database, not by blobs on disk. It records:

- Where a shared link or attachment *belongs* in a folder tree (LLM-suggested path).
- **Pointers** (URLs), **message jump links**, **short summaries**, and **embeddings** for future semantic search.

The MVP targets **Discord only**. Other chat systems are intentionally out of scope until a separate adapter is written.

## Problems it addresses

- **Serendipitous sharing** in fast-moving channels buries important links and files.
- **Manual filing** does not scale; Forest automates placement using context and an existing directory scaffold.
- **Search later**: vectors are stored on ingest so enabling similarity search later does not require a full backfill (see [Extensions](extensions.md)).

## MVP scope

In scope:

- Discord bot with passive `on_message` ingest (attachments + HTTP(S) URLs).
- Onboarding: seed directory tree from channel names (LLM) on guild join or `/forest init`.
- Browse: flat, paginated `/forest files` (no interactive tree UI).
- OpenRouter-only LLM access (OpenAI-compatible HTTP).
- PostgreSQL with **pgvector**, FastAPI **healthz** / **ready**, stdlib logging.

Explicitly out of scope for the initial build (may be documented as future work):

- Semantic search UI (`/forest find`) and ANN index tuning.
- Full telemetry (metrics, tracing, `/metrics`).
- Storing file bytes, malware scanning, or enterprise ACLs per folder.
- Slack, Teams, or other platforms (layout is reserved; see [Extensions](extensions.md)).

## Who this documentation is for

- **Operators**: install, configure, run, and observe the service.
- **Contributors**: understand boundaries between `platforms/`, `integrations/`, and `services/`.
- **Future doc site maintainers**: same Markdown can feed MkDocs/Sphinx.
