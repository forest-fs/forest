# Creating the Slack app

This page walks through creating a Slack app, granting it the required permissions, and wiring the tokens into `forest`'s `.env`.

## 1. Create the app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and sign in.
2. Click **Create New App** → choose **From scratch**.
3. Give it a name (e.g. **`forest`**) and pick the workspace you want to develop in.
4. Click **Create App**.

## 2. Copy the Signing Secret

You need this before `forest` can verify that incoming webhooks actually come from Slack.

1. In the left sidebar, open **Basic Information**.
2. Under **App Credentials**, find **Signing Secret** and click **Show**.
3. Copy the value into `.env` as `SLACK_SIGNING_SECRET`.

## 3. Add bot token scopes

1. In the left sidebar, open **OAuth & Permissions**.
2. Scroll to **Scopes** → **Bot Token Scopes**.
3. Add each of the following scopes:

   | Scope | Why `forest` needs it |
   |-------|---------------------|
   | `app_mentions:read` | Receive `@`forest`` mention commands |
   | `channels:history` | Read message history for ingest context and onboarding scan |
   | `channels:join` | Auto-join public channels during onboarding so `forest` can read history and receive events without manual invites |
   | `channels:read` | List public channels for onboarding |
   | `chat:write` | Post responses to mention commands |
   | `files:read` | Access file metadata from messages |

## 4. Install the app to your workspace

1. Still on **OAuth & Permissions**, scroll to the top and click **Install to Workspace** (or **Reinstall** if already installed).
2. Review the permissions and click **Allow**.
3. You will be redirected back; copy the **Bot User OAuth Token** (starts with `xoxb-`) into `.env` as `SLACK_BOT_TOKEN`.

## 5. Configure Event Subscriptions

`forest` receives Slack messages via the Events API, not a WebSocket connection. Slack needs a public HTTPS URL to send events to.

> **Local development**: use `cloudflared tunnel --url http://127.0.0.1:8000` to get a temporary public URL. See the [README](../README.md#testing-slack-against-localhost-cloudflared) for the full setup.

1. In the left sidebar, open **Event Subscriptions**.
2. Toggle **Enable Events** on.
3. Set the **Request URL** to `https://<your-host>/slack/events`. Slack will immediately send a verification challenge — `forest` handles this automatically and Slack should show a green **Verified** tick.
4. Under **Subscribe to bot events**, click **Add Bot User Event** and add:
   - `app_mention` — `@`forest`` mention commands (init, show, etc.)
   - `message.channels` — messages in public channels the bot has joined

5. Click **Save Changes**.

## 6. Verify it's working

With `forest` running and the tunnel active:

```bash
curl -sS https://<tunnel-host>/healthz
```

Then in any public channel, type `@`forest` help`. You should get the overview message back immediately.

When you run `@`forest` init`, `forest` automatically joins all public channels to read their history and listen for new messages — no manual `/invite` needed.

## Summary of `.env` values from this guide

```bash
SLACK_BOT_TOKEN=xoxb-...        # OAuth & Permissions → Bot User OAuth Token
SLACK_SIGNING_SECRET=...        # Basic Information → App Credentials → Signing Secret
```
