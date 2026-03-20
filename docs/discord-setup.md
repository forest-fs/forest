# Discord application and bot token

Forest needs a **Discord bot token** (`DISCORD_TOKEN` in `.env`). This page walks through creating an application, copying the token, enabling intents, and inviting the bot.

Official reference: [Discord — Getting started](https://discord.com/developers/docs/getting-started) and the Developer Portal sections for **Bot** and **OAuth2**.

## 1. Open the Developer Portal

Go to [Discord Developer Portal — Applications](https://discord.com/developers/applications) and sign in.

## 2. Create or select an application

- Click **New Application**, choose a name (for example Forest), and create it; or open an existing application.

## 3. Add a bot user

- In the left sidebar, open **Bot**.
- If there is no bot yet, use **Add Bot** and confirm.

## 4. Copy the token

- Under **TOKEN**, use **Reset Token** (or **View Token** when shown), then **Copy**.
- Paste the value into `.env` as **`DISCORD_TOKEN`**. Do not commit it or paste it into logs.

If a token is exposed, use **Reset Token** in the same place immediately; the previous token stops working.

## 5. Enable intents (required for Forest)

Still on the **Bot** page, under **Privileged Gateway Intents**:

- Turn on **MESSAGE CONTENT INTENT**. Forest reads message text to detect links and to build routing context.
- Enable **SERVER MEMBERS INTENT** only if you add features that need member lists; the MVP does not require it by default.

Forest also relies on guild and message behavior consistent with your README (e.g. reading channels and registering slash commands).

## 6. Invite the bot to your Discord server

Discord calls this a **server** (guild), not a “workspace.” You add the bot by opening an install link generated in the Developer Portal.

1. In the left sidebar, open **OAuth2**, then **URL Generator**.
2. Under **SCOPES**, enable:
   - **`bot`**
   - **`applications.commands`** (required so slash commands such as `/forest` can register)
3. After you select **`bot`**, the **BOT PERMISSIONS** section appears. Enable at least what Forest needs (see [Usage](usage.md) and the root README), for example:
   - View channels
   - Read messages / message history
   - Embed links
   - Use slash commands (and send messages if you want the bot to reply in channels)
4. Scroll down and copy the **Generated URL**.
5. Paste the URL into your browser, choose the **server** where you have rights to add bots, and confirm the **Authorize** prompt.

You need permission to manage or add integrations on that server (often **Manage Server** or **Administrator**, depending on how your community configures roles). If your server does not appear in the list, your account does not have sufficient rights there.

If slash commands do not show up immediately after install, wait a few minutes, restart the bot, or during development set **`DISCORD_SYNC_GUILD_ID`** in `.env` to your server id for faster guild-scoped command sync (see root README).

## 7. Wire into Forest

After `.env` contains `DISCORD_TOKEN`, start Forest (see [Startup and operations](startup.md)). If commands do not appear, check intent settings, bot presence in the server, and logs for connection or permission errors.
