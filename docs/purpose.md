# Purpose

## What Forest is

Forest is a **virtual filesystem** backed by a database, not by blobs on disk. It records:

- Where a shared link or attachment *belongs* in a folder tree (LLM-suggested path).
- **Pointers** (URLs), **message jump links**, **short summaries**, and **embeddings** for future semantic search.

The current version targets **Slack** via the Events API and bot mention commands.

## Problems it addresses

- **Serendipitous sharing** in fast-moving channels buries important links and files.
- **Manual filing** does not scale; Forest automates placement using context and an existing directory scaffold.
- **Search later**: vectors are stored on ingest so enabling similarity search later does not require a full backfill (see [Extensions](extensions.md)).

## Scope

In scope:

- Slack Events API passive ingest (attachments + HTTP(S) URLs).
- Onboarding: seed directory tree from channel names and history (LLM) via `@forest init`.
- Browse: `@forest show` as a nested list with Slack mrkdwn links.
- OpenRouter-only LLM access (OpenAI-compatible HTTP).
- PostgreSQL with **pgvector**, FastAPI **healthz** / **ready**, stdlib logging.

Explicitly out of scope (may be documented as future work):

- Semantic search UI (`@forest find`) and ANN index tuning.
- Full telemetry (metrics, tracing, `/metrics`).
- Storing file bytes, malware scanning, or enterprise ACLs per folder.

## Who this documentation is for

- **Operators**: install, configure, run, and observe the service.
- **Contributors**: understand boundaries between `platforms/`, `integrations/`, and `services/`.
- **Future doc site maintainers**: same Markdown can feed MkDocs/Sphinx.
