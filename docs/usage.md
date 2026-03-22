# Usage

## Mention commands

Mention `@forest` in any channel the bot has joined to run a command.

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

## Operational cautions

- **Rate limits**: Slack API and OpenRouter; the app uses per-workspace semaphores to reduce bursts.
- **Secrets**: never commit `.env` or paste tokens into logs at INFO level.
