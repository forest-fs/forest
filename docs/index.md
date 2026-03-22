# `森 forest` documentation

`森 forest` passively captures links and file attachments from Slack, uses an LLM (**OpenRouter by default**, or any **OpenAI-compatible** API you configure) to place each item in a **virtual folder tree**, stores metadata and embeddings in PostgreSQL (pgvector), and exposes simple mention commands (`@forest`) to browse captured files.

This documentation is maintained as Markdown in the repository. A future standalone docs site can point at these same sources with MkDocs, Sphinx, or another static generator.

## Contents

1. [Purpose](purpose.md) — product intent, scope, and non-goals  
2. [Usage](usage.md) — Slack commands, permissions, and operator workflow  
3. [Architecture](architecture.md) — components, boundaries, and runtime model  
4. [Slack app setup](slack-app-setup.md) — create the app, scopes, tokens, event subscriptions  
5. [Installation](installation.md) — local setup, database, migrations, running, and health endpoints  
6. [LLM configuration](llm-configuration.md) — API keys, base URL, model IDs, embedding dimensions  
7. [Deployment](deployment.md) — remote self-hosting on AWS (ECS / App Runner) and GCP (Cloud Run)  
8. [Extensions](extensions.md) — new chat platforms and post-MVP features  
9. [FAQ](faq.md) — troubleshooting and design choices  

For a concise quick start, see the root [README](../README.md).
