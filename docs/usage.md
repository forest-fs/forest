# Usage

## Slack app setup

For a full step-by-step walkthrough (creating the app, scopes, tokens, and event subscriptions), see [Slack app setup](slack-app-setup.md).

**Short version:**

1. Create an app at [api.slack.com/apps](https://api.slack.com/apps) and add bot scopes: `app_mentions:read`, `channels:history`, `channels:read`, `chat:write`, `files:read`.
2. **Event Subscriptions**: enable events, set Request URL `https://<host>/slack/events`, subscribe to `app_mention` and `message.channels`.
3. Install to your workspace; copy **Bot User OAuth Token** → `SLACK_BOT_TOKEN` and **Signing Secret** → `SLACK_SIGNING_SECRET` into `.env`.

## Mention commands

Mention `@Forest` in any channel the bot has joined to run a command.

| Mention | Who | Behavior |
|---------|-----|----------|
| `@forest help` | Any member | Overview of commands, ingest behavior, and admin vs user actions. |
| `@forest init` | Workspace admins | Scans all readable channels (full message history, subject to budget settings), builds capped transcripts, then runs onboarding: upserts a `Workspace`, LLM folder tree, directory `FileNode` rows, `is_initialized`. Posts result to the channel when complete. |
| `@forest update` | Workspace admins | After init: same history scan + LLM again; merges new folder paths. Does not delete nodes or replay ingest for old messages. |
| `@forest show` | Any member | Shows file nodes as a nested list with Slack mrkdwn links. |

## Passive ingest

Human messages in channels where the bot is a member that contain **attachments** or **HTTP(S) URLs** trigger ingest:

- Recent channel messages are pulled for **context** (best-effort).
- Each attachment and each distinct URL can become a separate file row after routing and embedding.

If the workspace is not initialized yet, ingest is skipped until `@forest init` completes.

## Configuration surface (high level)

Operators set environment variables (see `.env.example`):

- Database URL (async SQLAlchemy).
- Slack bot token and signing secret.
- OpenRouter API key, base URL, optional referer/title headers.
- Chat and embedding **model ids** (slugs on OpenRouter).
- **Onboarding history budgets** (optional): `FOREST_ONBOARDING_HISTORY_PER_CHANNEL_CHARS`, `FOREST_ONBOARDING_HISTORY_TOTAL_CHARS`, `FOREST_ONBOARDING_HISTORY_OLDEST_FIRST` — cap how much message text is passed to the LLM per channel and in total (defaults are set in `config.py`).

**Embedding dimension** in the database (currently 3072 in the schema; see migrations) must match the chosen embedding model output.

## Operational cautions

- **Rate limits**: Slack API and OpenRouter; the app uses per-workspace semaphores to reduce bursts.
- **Secrets**: never commit `.env` or paste tokens into logs at INFO level.
