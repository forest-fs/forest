# Documentation source

This directory holds human-written documentation as Markdown files. It is the intended home for a future published docs site (for example under a `forest.docs` project name or subdomain).

## Layout

| File | Topic |
|------|--------|
| [index.md](index.md) | Overview and table of contents |
| [purpose.md](purpose.md) | Why Forest exists and what it does |
| [usage.md](usage.md) | Day-to-day use (operators and Discord users) |
| [discord-setup.md](discord-setup.md) | Bot token, intents, invite link |
| [architecture.md](architecture.md) | System design and data flow |
| [installation.md](installation.md) | Prerequisites and install steps |
| [startup.md](startup.md) | Run, health checks, and operations |
| [extensions.md](extensions.md) | Adding platforms and post-MVP hooks |
| [faq.md](faq.md) | Common questions |

## Future site integration

To turn this folder into a static site later, typical options are:

- **MkDocs**: add `mkdocs.yml` with `docs_dir: .` (or point `nav` at these files) and use `mkdocs-material` or similar.
- **Sphinx + MyST**: add `docs/conf.py`, enable `myst_parser`, and include these `.md` files with `toctree`.

No build tooling is required for the MVP; reading the Markdown in the repository is enough.
