# Extensions

This section describes how Forest is shaped for **future work** without requiring rewrites of core logic.

## New chat platforms (e.g. Slack)

The MVP leaves a **`forest/platforms/slack/`** stub without SDK dependencies.

To add a platform:

1. Implement an adapter under `forest/platforms/<name>/` that translates native events into **`IngestPayload`** (and channel lists into whatever onboarding needs).
2. Keep **`Workspace.platform`** and **`platform_workspace_id`** as the neutral keys; avoid Discord-only column names on shared models.
3. Register platform-specific slash or shortcut UX only inside that adapter package; core **`services/`** should continue to accept canonical DTOs.

Onboarding today assumes a list of **text channel names** for the LLM; another platform should supply an equivalent list of “rooms” or conversations for seeding.

## Semantic search (post-MVP)

Planned direction (not implemented in MVP):

- **Repository** method: vector similarity search over `FileNode.embedding` filtered by workspace and `node_type=file`.
- **User entry**: `/forest find` or analogous command per platform.
- **Index tuning**: IVFFlat/HNSW when data volume warrants it.

Because embeddings are stored on ingest, enabling search later avoids a full historical backfill in the default design.

## Telemetry (post-MVP)

Planned direction:

- A thin **`forest/telemetry/`** (or similar) facade so `services/` and `platforms/` stay free of vendor imports.
- FastAPI **`/metrics`**, OpenTelemetry, or hosted APM — product choice.

MVP intentionally uses **logging only**.

## Configuration extensions

New features should extend **`Settings`** via `pydantic-settings`, document variables in `.env.example`, and avoid hardcoding secrets.

## Documentation site (`forest.docs`)

The Markdown under `docs/` is written to be ingested by a static site generator later (MkDocs, Sphinx with MyST, etc.). See [docs/README.md](README.md) for maintainer notes on wiring a build.
