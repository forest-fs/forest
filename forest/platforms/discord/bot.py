"""
Discord application: slash commands, passive message ingest queue, command sync.

Implements ``/forest help``, ``/forest init``, ``/forest update``, and ``/forest files``; ingest runs in
a background worker with per-guild concurrency limits.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands

from forest.config import get_settings
from forest.db.session import session_scope
from forest.platforms.discord.history_scan import collect_channel_histories_for_onboarding
from forest.platforms.discord.payloads import build_ingest_payload
from forest.repositories.file_node_repo import FileNodeRepository
from forest.repositories.workspace_repo import WorkspaceRepository
from forest.services.ingest import process_ingest
from forest.services.llm.service import LLMService
from forest.services.onboarding import run_onboarding_for_workspace

_log = logging.getLogger(__name__)

forest_group = app_commands.Group(name="forest", description="Forest virtual file tree")

_FOREST_HELP_TEXT = (
    "**Forest** captures attachments and links from this server into a virtual folder tree.\n\n"
    "**Commands**\n"
    "• `/forest help` — this overview\n"
    "• `/forest init` — **Manage Server**: scan readable channels (full message history) and seed the folder tree via the LLM (once per server unless you use `update`)\n"
    "• `/forest update` — **Manage Server**: same scan + re-merge new folders (keeps existing files)\n"
    "• `/forest files` — list captured files (optional `page`)\n\n"
    "**Ingest** — After init, normal messages that include attachments or `http(s)` URLs may be stored. "
    "Forest does not replay old messages; resend content if an ingest failed.\n\n"
    "Full detail for operators is in the Forest repo (**README** and **docs/usage.md**)."
)


@forest_group.command(name="help", description="What Forest does and how to use slash commands")
async def forest_help(interaction: discord.Interaction) -> None:
    """Slash: short reference for end users and admins (no permission gate)."""
    await interaction.response.send_message(_FOREST_HELP_TEXT, ephemeral=True)


@forest_group.command(name="init", description="Seed the folder tree for this server (admin)")
@app_commands.checks.has_permissions(manage_guild=True)
async def forest_init(interaction: discord.Interaction) -> None:
    """
    Slash: scan all readable text history, then seed workspace directories via LLM (admin only).

    Parameters
    ----------
    interaction : discord.Interaction
        Discord interaction; must be in a guild.

    Notes
    -----
    Deferral is ephemeral. If onboarding already completed, replies with a short
    message instead of re-running; use ``/forest update`` to merge a fresh
    LLM tree into the existing directories.
    """
    await interaction.response.defer(ephemeral=True)
    if interaction.guild is None:
        await interaction.followup.send("Run this command inside a server.")
        return
    settings = get_settings()
    llm = LLMService(settings)
    scan = await collect_channel_histories_for_onboarding(
        interaction.guild,
        per_channel_char_budget=settings.onboarding_history_per_channel_chars,
        total_char_budget=settings.onboarding_history_total_chars,
        oldest_first=settings.onboarding_history_oldest_first,
    )
    try:
        async with session_scope() as session:
            did = await run_onboarding_for_workspace(
                session,
                platform="discord",
                platform_workspace_id=str(interaction.guild.id),
                text_channel_names=scan.channel_names,
                guild_name=interaction.guild.name,
                llm=llm,
                force=False,
                channel_histories=scan.histories_as_json(),
            )
    except Exception:
        _log.exception(
            "forest init failed",
            extra={
                "operation": "slash_init",
                "guild_id": str(interaction.guild.id),
            },
        )
        await interaction.followup.send("Initialization failed. Check server logs.")
        return
    if did:
        await interaction.followup.send("Forest initialized. Folder tree created.")
    else:
        await interaction.followup.send("Forest is already initialized for this server.")


@forest_group.command(
    name="update",
    description="Re-run folder tree from channels (merge; admin; requires prior init)",
)
@app_commands.checks.has_permissions(manage_guild=True)
async def forest_update(interaction: discord.Interaction) -> None:
    """
    Slash: re-scan message history and call the onboarding LLM again (admin only).

    Existing directories and files are kept; only missing paths from the new tree
    are created. Does not enqueue ingest for old attachments/links again.
    """
    await interaction.response.defer(ephemeral=True)
    if interaction.guild is None:
        await interaction.followup.send("Run this command inside a server.")
        return
    settings = get_settings()
    llm = LLMService(settings)
    scan = await collect_channel_histories_for_onboarding(
        interaction.guild,
        per_channel_char_budget=settings.onboarding_history_per_channel_chars,
        total_char_budget=settings.onboarding_history_total_chars,
        oldest_first=settings.onboarding_history_oldest_first,
    )
    try:
        async with session_scope() as session:
            repos = WorkspaceRepository(session)
            ws = await repos.get_by_platform_ids(
                platform="discord",
                platform_workspace_id=str(interaction.guild.id),
            )
            if ws is None or not ws.is_initialized:
                await interaction.followup.send(
                    "Forest is not initialized yet. Run `/forest init` first."
                )
                return
            await run_onboarding_for_workspace(
                session,
                platform="discord",
                platform_workspace_id=str(interaction.guild.id),
                text_channel_names=scan.channel_names,
                guild_name=interaction.guild.name,
                llm=llm,
                force=True,
                channel_histories=scan.histories_as_json(),
            )
    except Exception:
        _log.exception(
            "forest update failed",
            extra={
                "operation": "slash_update",
                "guild_id": str(interaction.guild.id),
            },
        )
        await interaction.followup.send("Update failed. Check server logs.")
        return
    await interaction.followup.send(
        "Folder tree refreshed. New directories from the latest layout were merged "
        "(existing files and paths were not removed). Re-send attachments or links "
        "if an earlier ingest failed."
    )


@forest_group.command(name="files", description="List captured files (flat, paginated)")
@app_commands.describe(page="Page number (starts at 1)")
async def forest_files(interaction: discord.Interaction, page: int = 1) -> None:
    """
    Slash: list all stored file leaves as plain lines (path + link), paginated.

    Parameters
    ----------
    interaction : discord.Interaction
        Guild interaction required.
    page : int, optional
        1-based page index; clamped to valid range.

    Notes
    -----
    Output is truncated to stay within Discord message size limits. No interactive
    tree UI in MVP.
    """
    await interaction.response.defer(ephemeral=True)
    if interaction.guild is None:
        await interaction.followup.send("Run this command inside a server.")
        return
    if page < 1:
        page = 1
    page_size = 15
    async with session_scope() as session:
        ws_repo = WorkspaceRepository(session)
        files_repo = FileNodeRepository(session)
        ws = await ws_repo.get_by_platform_ids("discord", str(interaction.guild.id))
        if ws is None or not ws.is_initialized:
            await interaction.followup.send(
                "Forest is not initialized yet. Ask an admin to run /forest init."
            )
            return
        nodes = await files_repo.list_files_flat(ws.id)
    if not nodes:
        await interaction.followup.send("No files captured yet.")
        return
    lines: list[str] = []
    for n in nodes:
        link = n.source_url or n.message_url or ""
        line = f"`{n.full_path}` — {link}" if link else f"`{n.full_path}`"
        lines.append(line[:350])
    total_pages = max(1, (len(lines) + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * page_size
    chunk = lines[start : start + page_size]
    body = "\n".join(chunk)
    header = f"Page {page} of {total_pages} — {len(nodes)} file(s)\n\n"
    text = header + body
    if len(text) > 3900:
        text = text[:3890] + "\n…"
    await interaction.followup.send(text)


class ForestBot(commands.Bot):
    """
    Discord client with ingest queue, LLM service, and slash command registration.

    Notes
    -----
    ``command_prefix`` is a zero-width space so prefix commands are effectively
    disabled; UX is slash-only in MVP.

    Ingest uses ``asyncio.Queue`` with ``maxsize`` for backpressure; drops are logged
    at WARNING. Per-guild semaphores throttle OpenRouter concurrency.
    """

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(command_prefix="\u200b", intents=intents)
        self.llm = LLMService()
        self.ingest_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._guild_semaphores: dict[str, asyncio.Semaphore] = defaultdict(
            lambda: asyncio.Semaphore(2)
        )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """
        Handle permission and generic slash errors with user-visible messages.

        Parameters
        ----------
        interaction : discord.Interaction
            Failing interaction.
        error : app_commands.AppCommandError
            Error raised by an application command.
        """
        if isinstance(error, app_commands.MissingPermissions):
            msg = "You need the Manage Server permission to run that command."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return
        _log.exception("app command error", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("Something went wrong.", ephemeral=True)

    async def setup_hook(self) -> None:
        """
        Register slash group, start ingest worker, sync commands to Discord API.

        Notes
        -----
        Command sync uses optional ``DISCORD_SYNC_GUILD_ID`` for faster iteration.
        """
        self.tree.add_command(forest_group)
        self.loop.create_task(self._ingest_worker_loop())
        await self._sync_commands()

    async def _sync_commands(self) -> None:
        """Push slash command definitions globally or to a dev guild (when configured)."""
        settings = get_settings()
        guild_id = settings.discord_sync_guild_id
        try:
            if guild_id:
                gid = int(guild_id)
                synced = await self.tree.sync(guild=discord.Object(id=gid))
                _log.info("synced %s guild command(s) to guild %s", len(synced), gid)
            else:
                synced = await self.tree.sync()
                _log.info("synced %s global command(s)", len(synced))
        except Exception:
            _log.exception("command sync failed")

    async def _ingest_worker_loop(self) -> None:
        """
        Long-running consumer: dequeue payloads, process with per-guild semaphore.

        Notes
        -----
        Runs forever until process exit; exceptions are logged per job without
        stopping the worker.
        """
        while True:
            payload = await self.ingest_queue.get()
            sem = self._guild_semaphores[payload.workspace_key]
            try:
                async with sem:
                    await process_ingest(payload, self.llm)
            except Exception:
                _log.exception(
                    "ingest worker failed",
                    extra={
                        "operation": "ingest_worker",
                        "guild_id": payload.workspace_key,
                    },
                )
            finally:
                self.ingest_queue.task_done()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """
        Auto-onboarding when the bot joins a server (best-effort).

        Parameters
        ----------
        guild : discord.Guild
            Guild the bot was added to.

        Notes
        -----
        Failures are logged; operators can recover with ``/forest init`` or
        ``/forest update`` (after a successful init) to merge a fresh tree.
        """
        settings = get_settings()
        llm = LLMService(settings)
        scan = await collect_channel_histories_for_onboarding(
            guild,
            per_channel_char_budget=settings.onboarding_history_per_channel_chars,
            total_char_budget=settings.onboarding_history_total_chars,
            oldest_first=settings.onboarding_history_oldest_first,
        )
        try:
            async with session_scope() as session:
                await run_onboarding_for_workspace(
                    session,
                    platform="discord",
                    platform_workspace_id=str(guild.id),
                    text_channel_names=scan.channel_names,
                    guild_name=guild.name,
                    llm=llm,
                    force=False,
                    channel_histories=scan.histories_as_json(),
                )
        except Exception:
            _log.exception(
                "on_guild_join onboarding failed",
                extra={"operation": "on_guild_join", "guild_id": str(guild.id)},
            )

    async def on_message(self, message: discord.Message) -> None:
        """
        Passive listener: enqueue ingest work when a human posts links/attachments.

        Parameters
        ----------
        message : discord.Message
            Incoming guild message.

        Notes
        -----
        Ignores bots and DMs. Non-blocking enqueue; queue full drops are logged.
        """
        if message.author.bot:
            return
        if message.guild is None:
            return
        payload = await build_ingest_payload(message)
        if payload is None:
            return
        try:
            self.ingest_queue.put_nowait(payload)
        except asyncio.QueueFull:
            _log.warning(
                "ingest queue full; dropping message",
                extra={
                    "operation": "ingest_enqueue",
                    "guild_id": str(message.guild.id),
                },
            )


def create_bot() -> ForestBot:
    """
    Factory for a configured :class:`ForestBot` instance.

    Returns
    -------
    ForestBot
        Bot ready for :func:`run_bot`.
    """
    return ForestBot()


async def run_bot(bot: ForestBot) -> None:
    """
    Connect to Discord using ``DISCORD_TOKEN`` from settings (blocking until disconnect).

    Parameters
    ----------
    bot : ForestBot
        Bot from :func:`create_bot`.
    """
    token = get_settings().discord_token.get_secret_value()
    await bot.start(token)
