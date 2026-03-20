# Forest documentation

Forest passively captures links and file attachments from Discord, uses an LLM (via OpenRouter) to place each item in a **virtual folder tree**, stores metadata and embeddings in PostgreSQL (pgvector), and exposes a simple slash command to browse captured files.

This documentation is maintained as Markdown in the repository. A future standalone docs site (for example branded as Forest docs or `forest.docs`) can point at these same sources with MkDocs, Sphinx, or another static generator.

## Contents

1. [Purpose](purpose.md) — product intent, scope, and non-goals  
2. [Usage](usage.md) — Discord commands, permissions, and operator workflow  
3. [Discord setup](discord-setup.md) — application, bot token, intents, invite URL  
4. [Architecture](architecture.md) — components, boundaries, and runtime model  
5. [Installation](installation.md) — environment, Poetry, database, migrations  
6. [Startup and operations](startup.md) — running the process, health endpoints, logging  
7. [Extensions](extensions.md) — new chat platforms and post-MVP features  
8. [FAQ](faq.md) — troubleshooting and design choices  

For a concise quick start, see the root [README](../README.md).
