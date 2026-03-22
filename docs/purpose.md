# Purpose

## What `森 forest` is

`森 forest` is a cross platform **virtual filesystem** created, designed and managed by an LLM, derived on your company chats. Every file in the system is just a link to its original location in the platform of origin.


## Problems it addresses

- **Serendipitous sharing** in fast-moving channels buries important links and files.
- **Manual filing** does not scale; `森 forest` automates placement using context and an existing directory scaffold.
- **cross-platform mess**: teams will scatter their company knowledge across different platforms that don't talk to each other; `森 forest` is a lightweight tree that connects it all together.

## Scope & Future Work

Currently supported:

- `森 forest` only supports Slack for now, but future chat applications will be supported if there's enough interest.
- On initialization, `森 forest` scans all conversations and files and builds an initial filesystem, no matter how old or big the history is.
- By using an **OpenAI-compatible** LLM API (OpenRouter by default), `森 forest` lets _you_ provide your model of choice; see [LLM configuration](llm-configuration.md).

Future work:

- Semantic search UI (`@forest find`) and ANN index tuning.
- Full telemetry (metrics, tracing, `/metrics`).
- Storing file bytes, malware scanning, or enterprise ACLs per folder.

## Who this documentation is for

- **Developers of all kinds wishing to optimize their companys time**: install, configure, run, and observe the service.
- **Contributors**: understand boundaries between `platforms/`, `integrations/`, and `services/`.
- **Future doc site maintainers**: same Markdown can feed MkDocs/Sphinx.
