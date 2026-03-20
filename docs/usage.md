# Usage

For creating the Discord application and obtaining **`DISCORD_TOKEN`**, see [Discord setup](discord-setup.md).

## Discord: end user and admin flows

### Permissions and intents

In the Discord Developer Portal, enable **Message Content Intent** and the guild/message intents your deployment needs.

Bot permissions should include, at minimum:

- Read messages and message history (to build context and detect content).
- Embed links (for readable slash responses).
- Use slash commands.

### Slash commands

| Command | Who | Behavior |
|---------|-----|----------|
| `/forest help` | Any member | Ephemeral summary of commands, ingest behavior, and admin vs user actions. |
| `/forest init` | Members with **Manage Server** | Scans **all readable** text channels and **active forum threads** (full message history via the API), builds capped transcripts, then runs onboarding: upserts a `Workspace`, LLM folder tree, directory `FileNode` rows, `is_initialized`. Skips if already initialized (use `update` to re-merge). Large servers rely on **char budgets** (see env below). |
| `/forest update` | Members with **Manage Server** | **After** init: same history scan + LLM again; **merges** new folder paths (`ensure_path`). Does not delete nodes or re-enqueue ingest for old messages; re-send attachments/links if you need those stored again. |
| `/forest files` | Any member allowed by your server policy | Shows **file** nodes as a **nested markdown bullet list** (bold `**/folder/**`, `[filename](url)` on files), paginated by line (`page` argument). No interactive picker in MVP. |

On **guild join**, the bot attempts the same onboarding as `/forest init` (best effort; failures are logged).

### Passive ingest

Human messages (non-bot) in guild text channels that contain **attachments** or **HTTP(S) URLs** in the body may enqueue an ingest job:

- Prior channel messages are pulled for **context** (subject to permissions).
- Each attachment and each distinct URL can become a separate file row after routing and embedding.

If the workspace is not initialized yet, ingest is skipped until `/forest init` (or successful auto-onboarding) completes.

## Configuration surface (high level)

Operators set environment variables (see [Installation](installation.md) and `.env.example`):

- Database URL (async SQLAlchemy).
- Discord token; optional dev guild id for faster slash sync.
- OpenRouter API key, base URL, optional referer/title headers.
- Chat and embedding **model ids** (slugs on OpenRouter).
- **Onboarding history budgets** (optional): `FOREST_ONBOARDING_HISTORY_PER_CHANNEL_CHARS`, `FOREST_ONBOARDING_HISTORY_TOTAL_CHARS`, `FOREST_ONBOARDING_HISTORY_OLDEST_FIRST` — cap how much message text is passed to the LLM per channel and in total (defaults are set in `config.py`). The bot still **iterates** every message until the per-channel budget is filled (newest-first by default).

**Embedding dimension** in the database (currently 3072 in the schema; see migrations) must match the chosen embedding model output.

## Operational cautions

- **Rate limits**: Discord API and OpenRouter; the bot uses a bounded queue and per-guild semaphores to reduce bursts.
- **Secrets**: never commit `.env` or paste tokens into logs at INFO level.
